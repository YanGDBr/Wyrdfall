"""docs/design/11-habilidades.md §5: Incapacitado/Reviver (user-resolved
rule), CLEANSE, REVIVE, SUMMON; §4.4 role."""

import random

import pytest

from wyrdfall.domain.abilities import Ability, TargetMode, infer_role
from wyrdfall.domain.character import Character, Ruleset, SummonDef
from wyrdfall.domain.combat import Action, CombatEngine
from wyrdfall.domain.content import CLASS_DEFS, ENEMY_DEFS, TALENT_TREES, build_ruleset
from wyrdfall.domain.dungeon import DungeonDef, EncounterDef
from wyrdfall.domain.factory import create_player_character
from wyrdfall.domain.models import ActiveStatus, Effect, EffectKind, Modifier, ModifierKind, Stat, StatBlock, StatusEffectDef
from wyrdfall.domain.run import RunState
from wyrdfall.engine.session import REVIVE_ON_VICTORY_FRACTION, GameSession


def _ruleset() -> Ruleset:
    abilities = {
        "strike": Ability(id="strike", name="Strike", target_mode=TargetMode.SINGLE_ENEMY,
                          effects=[Effect(kind=EffectKind.DAMAGE, amount=4, scales_with=Stat.ATTACK, scale_factor=1.0)]),
        "bite": Ability(id="bite", name="Bite", target_mode=TargetMode.SINGLE_ENEMY,
                        effects=[Effect(kind=EffectKind.DAMAGE, amount=2, scales_with=Stat.ATTACK, scale_factor=1.0)]),
        "revive": Ability(id="revive", name="Revive", target_mode=TargetMode.SINGLE_ALLY,
                          effects=[Effect(kind=EffectKind.REVIVE, amount=0.25)]),
        "cleanse_all": Ability(id="cleanse_all", name="Cleanse", target_mode=TargetMode.SELF,
                               effects=[Effect(kind=EffectKind.CLEANSE, amount=0)]),
        "cleanse_one": Ability(id="cleanse_one", name="Cleanse1", target_mode=TargetMode.SELF,
                               effects=[Effect(kind=EffectKind.CLEANSE, amount=1)]),
        "call": Ability(id="call", name="Call", target_mode=TargetMode.SELF,
                        effects=[Effect(kind=EffectKind.SUMMON, summon_id="imp")]),
    }
    statuses = {
        "weak": StatusEffectDef(id="weak", name="Weak", modifiers=[Modifier(stat=Stat.ATTACK, kind=ModifierKind.PERCENT, value=-0.2, source="weak")]),
        "burn": StatusEffectDef(id="burn", name="Burn", tick_effect=Effect(kind=EffectKind.DAMAGE, amount=1)),
        "silence": StatusEffectDef(id="silence", name="Silence", silences=True),
        "strong": StatusEffectDef(id="strong", name="Strong", modifiers=[Modifier(stat=Stat.ATTACK, kind=ModifierKind.PERCENT, value=0.2, source="strong")]),
    }
    summons = {"imp": SummonDef(id="imp", name="Imp", base_stats=StatBlock(max_hp=5, attack=1, defense=0, speed=1, max_resource=0), abilities=["bite"])}
    return Ruleset(abilities=abilities, statuses=statuses, summons=summons)


def _hero(cid, abilities=("strike",), hp=30, speed=10):
    stats = StatBlock(max_hp=hp, attack=5, defense=0, speed=speed, crit_chance=0.0, max_resource=0)
    return Character(id=cid, name=cid.title(), class_id="w", base_stats=stats, current_hp=hp, current_resource=0,
                     abilities=list(abilities), equipped_abilities=list(abilities))


def _goblin(cid="goblin", hp=10, speed=5, abilities=("bite",)):
    stats = StatBlock(max_hp=hp, attack=2, defense=0, speed=speed, crit_chance=0.0, max_resource=0)
    return Character(id=cid, name=cid.title(), class_id="g", base_stats=stats, current_hp=hp, current_resource=0,
                     abilities=list(abilities), is_player=False)


def _act(engine, state, actor, ability, target=None):
    return engine.resolve(state, Action(actor_id=actor, ability_id=ability, target_ids=[target] if target else []))


# -- Incapacitado / Reviver (session rule) ------------------------------------------


def _coop_session():
    ruleset = build_ruleset()
    class_def = CLASS_DEFS["runeguard"]
    tree = TALENT_TREES[class_def.talent_tree_id]
    a = create_player_character("a", "A", class_def, tree, ruleset=ruleset)
    b = create_player_character("b", "B", class_def, tree, ruleset=ruleset)
    dungeon = DungeonDef(id="t", name="t", encounters=[EncounterDef(id="e1", name="f", enemy_ids=["goblin"]), EncounterDef(id="e2", name="g", enemy_ids=["goblin"])])
    return GameSession(RunState(run_id="r", seed=1, dungeon_id="t", party=[a, b]), ruleset, dict(TALENT_TREES), dungeon=dungeon)


def test_a_downed_coop_hero_is_incapacitated_skipped_and_revived_at_ten_percent_on_victory():
    session = _coop_session()
    state = session.start_current_encounter()
    b = state.combatants["b"]
    b.current_hp = 0.0
    b.statuses.append(ActiveStatus(status_id="poisoned", remaining_duration=3))
    assert b.is_incapacitated and not b.is_alive
    assert not state.is_over  # a lives on: it's not a defeat

    turns = 0
    while not session.encounter_is_over and turns < 100:
        actor_id = state.current_actor_id()
        assert actor_id != "b"  # never gets a turn while down
        actor = state.combatants[actor_id]
        if actor.acts_automatically:
            session.resolve_ai_turn()
        else:
            ability = session.combat_engine.legal_abilities(state, actor_id)[0]
            targets = session.combat_engine.legal_target_ids(state, actor_id, ability)
            session.submit_action(Action(actor_id=actor_id, ability_id=ability.id, target_ids=targets[:1]))
        turns += 1
    assert session.encounter_victory

    session.collect_victory_reward_and_advance()
    b = next(c for c in session.run.party if c.id == "b")
    assert b.is_alive and not b.is_incapacitated
    assert b.current_hp == pytest.approx(REVIVE_ON_VICTORY_FRACTION * b.computed_stats(session.ruleset).max_hp, rel=0.3)
    assert b.statuses == []


def test_when_the_whole_party_falls_it_is_still_a_defeat():
    session = _coop_session()
    state = session.start_current_encounter()
    state.combatants["a"].current_hp = 0.0
    state.combatants["b"].current_hp = 0.0
    session.combat_engine._check_victory(state)
    assert state.is_over and state.victory is False


# -- REVIVE -----------------------------------------------------------------------------


def test_revive_targets_only_the_downed_and_puts_them_back_in_the_turn_order():
    engine = CombatEngine(_ruleset(), rng=random.Random(1))
    healer, fighter = _hero("healer", ("strike", "revive"), speed=10), _hero("fighter", speed=9)
    state = engine.start_encounter([healer, fighter], [_goblin(speed=1, hp=100)])
    revive = engine.ruleset.abilities["revive"]
    assert engine.legal_target_ids(state, "healer", revive) == ["healer", "fighter"]  # alive allies too, harmlessly
    state.combatants["fighter"].current_hp = 0.0
    state.combatants["fighter"].statuses.append(ActiveStatus(status_id="burn", remaining_duration=2))
    assert "fighter" in engine.legal_target_ids(state, "healer", revive)
    assert "fighter" not in engine.legal_target_ids(state, "healer", engine.ruleset.abilities["strike"])

    log = _act(engine, state, "healer", "revive", "fighter")
    fighter = state.combatants["fighter"]
    assert fighter.current_hp == pytest.approx(0.25 * 30)
    assert fighter.statuses == []
    assert any("volta à luta" in line for line in log)
    assert state.current_actor_id() == "fighter"  # right back in the order

    # reviving someone alive does nothing
    hp = fighter.current_hp
    state.turn_index = state.turn_order.index("healer")
    _act(engine, state, "healer", "revive", "fighter")
    assert fighter.current_hp == hp


# -- CLEANSE ---------------------------------------------------------------------------


def test_cleanse_strips_harmful_statuses_only_all_or_up_to_n():
    engine = CombatEngine(_ruleset(), rng=random.Random(1))
    state = engine.start_encounter([_hero("hero", ("cleanse_all", "cleanse_one"))], [_goblin(hp=100)])
    hero = state.combatants["hero"]
    for sid in ("weak", "strong", "burn", "silence"):
        hero.statuses.append(ActiveStatus(status_id=sid, remaining_duration=3))
    _act(engine, state, "hero", "cleanse_one")
    assert [s.status_id for s in hero.statuses] == ["weak", "strong", "burn"]  # most recent harmful first
    engine.resolve_ai_turn(state)
    log = _act(engine, state, "hero", "cleanse_all")
    assert [s.status_id for s in hero.statuses] == ["strong"]  # the buff survives
    assert any("se livra de" in line for line in log)


# -- SUMMON ----------------------------------------------------------------------------


def test_summon_adds_an_auto_acting_ally_for_this_fight_only():
    engine = CombatEngine(_ruleset(), rng=random.Random(1))
    state = engine.start_encounter([_hero("hero", ("strike", "call"))], [_goblin(hp=100)])
    log = _act(engine, state, "hero", "call")
    assert any("invoca Imp" in line for line in log)
    imp = state.combatants["hero_summon_0"]
    assert imp.is_player and imp.is_companion and imp.acts_automatically and imp.owner_id == "hero"
    assert state.turn_order[-1] == "hero_summon_0"
    assert "hero_summon_0" in state.party_ids()
    engine.resolve_ai_turn(state)  # goblin
    assert state.current_actor_id() == "hero_summon_0"
    log = engine.resolve_ai_turn(state)  # the imp bites
    assert any("Imp usa Bite" in line for line in log)
    state.turn_index = state.turn_order.index("hero")
    _act(engine, state, "hero", "call")
    assert "hero_summon_1" in state.combatants  # a second one, distinct id

    # a summon alone never keeps the fight going
    state.combatants["hero"].current_hp = 0.0
    engine._check_victory(state)
    assert state.is_over and state.victory is False


def test_a_summon_never_reaches_the_run_and_an_enemy_summon_must_die_for_victory():
    ruleset = build_ruleset()
    class_def = CLASS_DEFS["mistico"]
    hero = create_player_character("hero", "Hero", class_def, TALENT_TREES[class_def.talent_tree_id], ruleset=ruleset)
    hero.abilities.append("hybrid_spectral_call")
    hero.equipped_abilities = ["hybrid_spectral_call", "arcane_bolt"]
    hero.current_resource = 10
    dungeon = DungeonDef(id="t", name="t", encounters=[EncounterDef(id="e1", name="f", enemy_ids=["goblin"])])
    session = GameSession(RunState(run_id="r", seed=1, dungeon_id="t", party=[hero]), ruleset, dict(TALENT_TREES), dungeon=dungeon)
    state = session.start_current_encounter()
    session.submit_action(Action(actor_id="hero", ability_id="hybrid_spectral_call", target_ids=[]))
    assert "hero_summon_0" in state.combatants and state.combatants["hero_summon_0"].name == "Espectro"
    assert [c.id for c in session.run.party] == ["hero"] and session.run.companions == []

    engine = CombatEngine(_ruleset(), rng=random.Random(1))
    state = engine.start_encounter([_hero("hero", hp=100)], [_goblin("caller", hp=100, abilities=("call",), speed=20)])
    engine.resolve_ai_turn(state)  # the goblin calls its imp first
    assert "caller_summon_0" in state.enemy_ids()
    state.combatants["caller"].current_hp = 0.0
    engine._check_victory(state)
    assert not state.is_over  # the imp still stands
    state.combatants["caller_summon_0"].current_hp = 0.0
    engine._check_victory(state)
    assert state.victory is True


# -- role + content -----------------------------------------------------------------------


def test_roles_follow_the_section_4_4_table_and_content_is_wired():
    ruleset = build_ruleset()
    assert infer_role(ruleset.abilities["strike"]) == "Dano"
    assert infer_role(ruleset.abilities["taunt"]) == "Controle"
    assert infer_role(ruleset.abilities["mad_copyist_silence"]) == "Controle"
    assert infer_role(ruleset.abilities["guard"]) == "Buff"
    assert infer_role(ruleset.abilities["mad_copyist_mirror"]) == "Debuff"
    assert infer_role(ruleset.abilities["living_rampart"]) == "Cura"
    assert infer_role(ruleset.abilities["focus"]) == "Utilidade"
    assert infer_role(ruleset.abilities["hybrid_spectral_call"]) == "Invocação"
    assert any(e.kind == EffectKind.REVIVE for e in ruleset.abilities["wyrd_song"].effects)
    assert any(e.kind == EffectKind.CLEANSE for e in ruleset.abilities["heartwood_bloom"].effects)
    assert "mad_copyist_draft" in ENEMY_DEFS["copista_louco"].abilities
    assert ruleset.statuses["poisoned"].is_harmful and not ruleset.statuses["empowered"].is_harmful
