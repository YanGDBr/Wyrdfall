"""docs/design/01-mecanicas.md §4 (Silêncio, Provocar, Medo as engine-
respected control), §1.3 Execução, §1.4 Overkill/Cleave and §8's
Effect.chance."""

import random

import pytest

from wyrdfall.domain.abilities import Ability, TargetMode
from wyrdfall.domain.character import Character, Ruleset
from wyrdfall.domain.combat import Action, CombatEngine, CombatError
from wyrdfall.domain.content import CLASS_DEFS, ENEMY_DEFS, build_ruleset
from wyrdfall.domain.models import ActiveStatus, Effect, EffectKind, Stat, StatBlock, StatusEffectDef


def _ruleset(**extra_abilities) -> Ruleset:
    abilities = {
        "strike": Ability(id="strike", name="Strike", target_mode=TargetMode.SINGLE_ENEMY,
                          effects=[Effect(kind=EffectKind.DAMAGE, amount=4, scales_with=Stat.ATTACK, scale_factor=1.0)]),
        "bolt": Ability(id="bolt", name="Bolt", target_mode=TargetMode.SINGLE_ENEMY, tags=["magic"],
                        effects=[Effect(kind=EffectKind.DAMAGE, amount=4, scales_with=Stat.ATTACK, scale_factor=1.0)]),
        "guard": Ability(id="guard", name="Defender", target_mode=TargetMode.SELF, universal=True,
                         effects=[Effect(kind=EffectKind.APPLY_STATUS, status_id="guarding", duration=1)]),
        "bite": Ability(id="bite", name="Bite", target_mode=TargetMode.SINGLE_ENEMY,
                        effects=[Effect(kind=EffectKind.DAMAGE, amount=2, scales_with=Stat.ATTACK, scale_factor=1.0)]),
        **extra_abilities,
    }
    statuses = {
        "guarding": StatusEffectDef(id="guarding", name="Defendendo"),
        "silencio": StatusEffectDef(id="silencio", name="Silêncio", silences=True),
        "provocado": StatusEffectDef(id="provocado", name="Provocado", taunts=True),
        "fear": StatusEffectDef(id="fear", name="Medo", fail_chance=1.0),
        "poisoned": StatusEffectDef(id="poisoned", name="Envenenado"),
    }
    return Ruleset(abilities=abilities, statuses=statuses)


def _hero(cid="hero", abilities=("strike", "bolt", "guard"), resource=5, hp=30, speed=10) -> Character:
    stats = StatBlock(max_hp=hp, attack=5, defense=0, speed=speed, crit_chance=0.0, max_resource=resource)
    return Character(id=cid, name=cid.title(), class_id="w", base_stats=stats, current_hp=hp, current_resource=resource,
                     abilities=list(abilities), equipped_abilities=list(abilities))


def _goblin(cid="goblin", hp=10, speed=5) -> Character:
    stats = StatBlock(max_hp=hp, attack=2, defense=0, speed=speed, crit_chance=0.0, max_resource=0)
    return Character(id=cid, name=cid.title(), class_id="g", base_stats=stats, current_hp=hp, current_resource=0,
                     abilities=["bite"], is_player=False)


def test_silence_hides_magic_abilities_and_resolve_rejects_them():
    engine = CombatEngine(_ruleset(), rng=random.Random(1))
    state = engine.start_encounter([_hero()], [_goblin()])
    hero = state.combatants["hero"]
    assert {a.id for a in engine.legal_abilities(state, "hero")} >= {"strike", "bolt"}
    hero.statuses.append(ActiveStatus(status_id="silencio", remaining_duration=2))
    assert "bolt" not in {a.id for a in engine.legal_abilities(state, "hero")}
    assert "strike" in {a.id for a in engine.legal_abilities(state, "hero")}
    with pytest.raises(CombatError):
        engine.resolve(state, Action(actor_id="hero", ability_id="bolt", target_ids=["goblin"]))
    engine.resolve(state, Action(actor_id="hero", ability_id="strike", target_ids=["goblin"]))  # still fine


def test_taunt_forces_the_target_onto_the_taunter_until_they_fall_or_it_expires():
    engine = CombatEngine(_ruleset(), rng=random.Random(1))
    tank, mage = _hero("tank", speed=10), _hero("mage", speed=9)
    goblin = _goblin(speed=1)
    state = engine.start_encounter([tank, mage], [goblin])
    bite = engine.ruleset.abilities["bite"]
    assert set(engine.legal_target_ids(state, "goblin", bite)) == {"tank", "mage"}

    # the tank applies Provocar -- through _apply_effect so source_id is recorded
    engine._apply_effect(state, "tank", "goblin", Effect(kind=EffectKind.APPLY_STATUS, status_id="provocado", duration=2))
    assert state.combatants["goblin"].statuses[0].source_id == "tank"
    assert engine.legal_target_ids(state, "goblin", bite) == ["tank"]

    # the taunter falling releases the goblin
    state.combatants["tank"].current_hp = 0.0
    assert engine.legal_target_ids(state, "goblin", bite) == ["mage"]

    # and so does the status expiring
    state.combatants["tank"].current_hp = 30.0
    state.combatants["goblin"].statuses = []
    assert set(engine.legal_target_ids(state, "goblin", bite)) == {"tank", "mage"}


def test_the_ai_obeys_a_taunt():
    engine = CombatEngine(_ruleset(), rng=random.Random(3))
    tank, mage = _hero("tank", speed=10), _hero("mage", speed=9, hp=5)  # the AI would love the weak mage
    state = engine.start_encounter([tank, mage], [_goblin(speed=1)])
    engine.resolve(state, Action(actor_id="tank", ability_id="guard"))
    engine.resolve(state, Action(actor_id="mage", ability_id="guard"))
    engine._apply_effect(state, "tank", "goblin", Effect(kind=EffectKind.APPLY_STATUS, status_id="provocado", duration=2))
    assert state.current_actor_id() == "goblin"
    log = engine.resolve_ai_turn(state)
    assert any("Tank sofre" in line for line in log)
    assert state.combatants["mage"].current_hp == 5


def test_fear_can_turn_an_action_into_defender_without_spending_resource():
    engine = CombatEngine(_ruleset(), rng=random.Random(1))
    state = engine.start_encounter([_hero()], [_goblin()])
    hero = state.combatants["hero"]
    hero.statuses.append(ActiveStatus(status_id="fear", remaining_duration=2))
    costly = engine.ruleset.abilities["strike"].model_copy(update={"resource_cost": 3.0})
    engine.ruleset.abilities["strike"] = costly
    log = engine.resolve(state, Action(actor_id="hero", ability_id="strike", target_ids=["goblin"]))
    assert any("hesita de medo" in line for line in log)
    assert hero.current_resource == 5  # nothing spent
    assert any(s.status_id == "guarding" for s in hero.statuses)
    assert state.combatants["goblin"].current_hp == 10  # the strike never landed
    assert state.current_actor_id() == "goblin"  # the turn was spent

    # Defender itself is never blocked by fear
    hero.statuses = [ActiveStatus(status_id="fear", remaining_duration=2)]
    state.turn_index = state.turn_order.index("hero")
    log = engine.resolve(state, Action(actor_id="hero", ability_id="guard"))
    assert not any("hesita" in line for line in log)


def test_effect_chance_zero_never_applies_and_one_always_does():
    poison = Ability(id="poison", name="Poison", target_mode=TargetMode.SINGLE_ENEMY, effects=[
        Effect(kind=EffectKind.DAMAGE, amount=1),
        Effect(kind=EffectKind.APPLY_STATUS, status_id="poisoned", duration=2, chance=0.0),
    ])
    engine = CombatEngine(_ruleset(poison=poison), rng=random.Random(1))
    state = engine.start_encounter([_hero(abilities=("poison",))], [_goblin()])
    engine.resolve(state, Action(actor_id="hero", ability_id="poison", target_ids=["goblin"]))
    assert state.combatants["goblin"].statuses == []
    assert state.combatants["goblin"].current_hp == 9  # the certain part still landed

    sure = poison.model_copy(update={"effects": [poison.effects[0], poison.effects[1].model_copy(update={"chance": 1.0})]})
    engine = CombatEngine(_ruleset(poison=sure), rng=random.Random(1))
    state = engine.start_encounter([_hero(abilities=("poison",))], [_goblin()])
    engine.resolve(state, Action(actor_id="hero", ability_id="poison", target_ids=["goblin"]))
    assert [s.status_id for s in state.combatants["goblin"].statuses] == ["poisoned"]


def test_execute_bonus_applies_only_below_the_threshold():
    execute = Ability(id="execute", name="Execute", target_mode=TargetMode.SINGLE_ENEMY, effects=[
        Effect(kind=EffectKind.DAMAGE, amount=4, execute_threshold=0.30, execute_bonus=1.0),
    ])
    engine = CombatEngine(_ruleset(execute=execute), rng=random.Random(1))
    state = engine.start_encounter([_hero(abilities=("execute",))], [_goblin(hp=100)])
    engine.resolve(state, Action(actor_id="hero", ability_id="execute", target_ids=["goblin"]))
    assert state.combatants["goblin"].current_hp == 96  # 4, no bonus at 100%

    state.combatants["goblin"].current_hp = 20.0  # 20% -- below the 30% line
    state.turn_index = state.turn_order.index("hero")
    log = engine.resolve(state, Action(actor_id="hero", ability_id="execute", target_ids=["goblin"]))
    assert state.combatants["goblin"].current_hp == 12  # 4 x 2
    assert any("Execução!" in line for line in log)


def test_cleave_overflow_spills_onto_the_next_enemy_exactly_once():
    cleave = Ability(id="cleave", name="Cleave", target_mode=TargetMode.SINGLE_ENEMY, tags=["cleave"],
                     effects=[Effect(kind=EffectKind.DAMAGE, amount=25)])
    engine = CombatEngine(_ruleset(cleave=cleave), rng=random.Random(1))
    state = engine.start_encounter([_hero(abilities=("cleave",))], [_goblin("g1", hp=10), _goblin("g2", hp=10), _goblin("g3", hp=10)])
    log = engine.resolve(state, Action(actor_id="hero", ability_id="cleave", target_ids=["g1"]))
    assert state.combatants["g1"].current_hp == 0
    assert state.combatants["g2"].current_hp == 0  # 15 overflow kills g2 too...
    assert state.combatants["g3"].current_hp == 10  # ...but the overflow never cleaves again
    assert sum("atravessa" in line for line in log) == 1

    # without the tag, the same hit stops at the first target
    plain = cleave.model_copy(update={"tags": []})
    engine = CombatEngine(_ruleset(cleave=plain), rng=random.Random(1))
    state = engine.start_encounter([_hero(abilities=("cleave",))], [_goblin("g1", hp=10), _goblin("g2", hp=10)])
    engine.resolve(state, Action(actor_id="hero", ability_id="cleave", target_ids=["g1"]))
    assert state.combatants["g2"].current_hp == 10


def test_content_carries_the_new_control_and_offense_pieces():
    ruleset = build_ruleset()
    assert ruleset.statuses["silencio"].silences and ruleset.statuses["provocado"].taunts
    assert ruleset.statuses["fear"].fail_chance > 0
    assert "taunt" in CLASS_DEFS["guardiao"].starting_abilities
    assert ruleset.abilities["taunt"].effects[0].status_id == "provocado"
    assert "mad_copyist_silence" in ENEMY_DEFS["copista_louco"].abilities
    assert "cleave" in ruleset.abilities["weapon_cleave"].tags
    assert ruleset.abilities["war_incarnate"].effects[0].execute_threshold == 0.30
    assert any(e.chance < 1.0 for e in ruleset.abilities["hybrid_spectral_call"].effects)
