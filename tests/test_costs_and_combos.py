"""docs/design/11-habilidades.md §7 (Tipos de Custo, recursos alternativos)
and §8 (Pontos de Combo, Combo por Sequência, Combo em Equipe)."""

import random

import pytest

from wyrdfall.domain.abilities import Ability, TargetMode
from wyrdfall.domain.character import RESOURCE_NAMES, Character, ResourceKind, Ruleset
from wyrdfall.domain.combat import (
    ADRENALINE_PER_TURN,
    COMBO_POINT_SCALING,
    COMBO_SEQUENCE_BONUS,
    FURY_DECAY_PER_IDLE_TURN,
    FURY_PER_HIT_TAKEN,
    Action,
    CombatEngine,
    CombatError,
)
from wyrdfall.domain.content import CLASS_DEFS, build_ruleset
from wyrdfall.domain.dungeon import DungeonDef, EncounterDef
from wyrdfall.domain.factory import create_player_character
from wyrdfall.domain.models import ActiveStatus, Effect, EffectKind, Stat, StatBlock, StatusEffectDef
from wyrdfall.domain.run import RunState
from wyrdfall.engine.session import GameSession


def _dmg(amount=4.0, **kw) -> Effect:
    return Effect(kind=EffectKind.DAMAGE, amount=amount, **kw)


def _ruleset(**abilities) -> Ruleset:
    base = {
        "strike": Ability(id="strike", name="Strike", target_mode=TargetMode.SINGLE_ENEMY, effects=[_dmg()]),
        "guard": Ability(id="guard", name="Defender", target_mode=TargetMode.SELF, universal=True, effects=[]),
        "bite": Ability(id="bite", name="Bite", target_mode=TargetMode.SINGLE_ENEMY, effects=[_dmg(2.0)]),
        "costly": Ability(id="costly", name="Costly", resource_cost=2, target_mode=TargetMode.SINGLE_ENEMY, effects=[_dmg()]),
    }
    base.update(abilities)
    return Ruleset(abilities=base, statuses={
        "marcado_para_combo": StatusEffectDef(id="marcado_para_combo", name="Marcado", team_combo_bonus=0.5),
    })


def _hero(cid="hero", kind=ResourceKind.MANA, abilities=("strike", "costly", "guard"), resource=0.0, hp=30, speed=10):
    stats = StatBlock(max_hp=hp, attack=0, defense=0, speed=speed, crit_chance=0.0, max_resource=5, resource_regen_per_turn=0.0)
    return Character(id=cid, name=cid.title(), class_id="w", base_stats=stats, current_hp=hp, current_resource=resource,
                     abilities=list(abilities), equipped_abilities=list(abilities), resource_kind=kind)


def _goblin(cid="goblin", hp=100, speed=5, attack=2):
    stats = StatBlock(max_hp=hp, attack=attack, defense=0, speed=speed, crit_chance=0.0, max_resource=0)
    return Character(id=cid, name=cid.title(), class_id="g", base_stats=stats, current_hp=hp, current_resource=0,
                     abilities=["bite"], is_player=False)


def _act(engine, state, actor_id, ability_id, target=None):
    return engine.resolve(state, Action(actor_id=actor_id, ability_id=ability_id, target_ids=[target] if target else []))


# -- §7.1 resource kinds --------------------------------------------------------


def test_fury_rises_on_hits_taken_and_cools_after_an_idle_turn():
    engine = CombatEngine(_ruleset(), rng=random.Random(1))
    state = engine.start_encounter([_hero(kind=ResourceKind.FURY)], [_goblin()])
    _act(engine, state, "hero", "strike", "goblin")  # hero idles resource-wise
    engine.resolve_ai_turn(state)  # goblin bites -> fury +1
    hero = state.combatants["hero"]
    # the bite raised it, then the hero's own turn start (no spend last
    # turn) cooled it right back down -- both are in the log
    assert any("Fúria de Hero sobe" in line for line in state.log)
    assert any("esfria" in line for line in state.log)
    assert hero.current_resource == pytest.approx(FURY_PER_HIT_TAKEN - FURY_DECAY_PER_IDLE_TURN)

    hero.current_resource = 3.0
    _act(engine, state, "hero", "costly", "goblin")  # spends -> no decay next turn
    engine.resolve_ai_turn(state)
    assert hero.current_resource == pytest.approx(3.0 - 2 + FURY_PER_HIT_TAKEN)


def test_adrenaline_rises_every_own_turn_and_mana_does_not():
    engine = CombatEngine(_ruleset(), rng=random.Random(1))
    state = engine.start_encounter([_hero(kind=ResourceKind.ADRENALINE)], [_goblin(attack=0)])
    assert state.combatants["hero"].current_resource == ADRENALINE_PER_TURN  # first turn start already counted
    _act(engine, state, "hero", "strike", "goblin")
    engine.resolve_ai_turn(state)
    assert state.combatants["hero"].current_resource == 2 * ADRENALINE_PER_TURN

    engine = CombatEngine(_ruleset(), rng=random.Random(1))
    state = engine.start_encounter([_hero(kind=ResourceKind.MANA)], [_goblin(attack=0)])
    _act(engine, state, "hero", "strike", "goblin")
    engine.resolve_ai_turn(state)
    assert state.combatants["hero"].current_resource == 0.0  # only regen/Focus fill Mana


def test_combo_points_build_on_hits_and_a_finisher_needs_and_spends_them_all():
    builder = Ability(id="jab", name="Jab", target_mode=TargetMode.SINGLE_ENEMY, tags=["combo_builder"], effects=[_dmg(1.0)])
    finisher = Ability(id="fin", name="Finisher", target_mode=TargetMode.SINGLE_ENEMY, tags=["combo_finisher"], effects=[_dmg(10.0)])
    engine = CombatEngine(_ruleset(jab=builder, fin=finisher), rng=random.Random(1))
    state = engine.start_encounter([_hero(kind=ResourceKind.COMBO_POINTS, abilities=("jab", "fin"))], [_goblin(attack=0)])
    hero = state.combatants["hero"]
    assert "fin" not in {a.id for a in engine.legal_abilities(state, "hero")}  # no points yet
    with pytest.raises(CombatError):
        _act(engine, state, "hero", "fin", "goblin")

    for _ in range(3):
        _act(engine, state, "hero", "jab", "goblin")
        engine.resolve_ai_turn(state)
    assert hero.current_resource == 3.0
    hp_before = state.combatants["goblin"].current_hp
    _act(engine, state, "hero", "fin", "goblin")
    assert hero.current_resource == 0.0
    assert hp_before - state.combatants["goblin"].current_hp == pytest.approx(10.0 * (1 + COMBO_POINT_SCALING * 3))

    # a MANA character never gains points from the same builder
    engine = CombatEngine(_ruleset(jab=builder, fin=finisher), rng=random.Random(1))
    state = engine.start_encounter([_hero(kind=ResourceKind.MANA, abilities=("jab", "fin"))], [_goblin(attack=0)])
    _act(engine, state, "hero", "jab", "goblin")
    assert state.combatants["hero"].current_resource == 0.0


# -- §7.2-7.4 costs ---------------------------------------------------------------


def test_sangue_pays_a_fraction_of_current_hp_and_is_never_lethal():
    blood = Ability(id="blood", name="Blood", resource_cost=0.5, pays_with_hp=True, target_mode=TargetMode.SINGLE_ENEMY, effects=[_dmg()])
    engine = CombatEngine(_ruleset(blood=blood), rng=random.Random(1))
    state = engine.start_encounter([_hero(abilities=("blood",), hp=20)], [_goblin(attack=0)])
    hero = state.combatants["hero"]
    _act(engine, state, "hero", "blood", "goblin")
    assert hero.current_hp == 10.0  # half of current, no resource touched
    assert hero.current_resource == 0.0
    engine.resolve_ai_turn(state)
    hero.current_hp = 1.0
    assert "blood" not in {a.id for a in engine.legal_abilities(state, "hero")}  # 1 HP can't pay
    hero.current_hp = 1.5
    _act(engine, state, "hero", "blood", "goblin")
    assert hero.current_hp == pytest.approx(1.0)  # floored, never lethal


def test_cooldown_blocks_the_ability_and_ticks_back_at_the_owners_turn_ends():
    big = Ability(id="big", name="Big", cooldown_turns=2, target_mode=TargetMode.SINGLE_ENEMY, effects=[_dmg()])
    engine = CombatEngine(_ruleset(big=big), rng=random.Random(1))
    state = engine.start_encounter([_hero(abilities=("big", "strike"))], [_goblin(attack=0)])
    hero = state.combatants["hero"]
    _act(engine, state, "hero", "big", "goblin")
    assert hero.cooldowns["big"] == 2
    engine.resolve_ai_turn(state)
    assert "big" not in {a.id for a in engine.legal_abilities(state, "hero")}
    with pytest.raises(CombatError):
        _act(engine, state, "hero", "big", "goblin")
    _act(engine, state, "hero", "strike", "goblin")  # own turn end -> 1
    engine.resolve_ai_turn(state)
    assert hero.cooldowns["big"] == 1
    _act(engine, state, "hero", "strike", "goblin")  # -> 0, gone
    engine.resolve_ai_turn(state)
    assert "big" not in hero.cooldowns
    assert "big" in {a.id for a in engine.legal_abilities(state, "hero")}


def test_charges_deplete_per_use_and_refill_on_rest_and_area_transition():
    ruleset = build_ruleset()
    class_def = CLASS_DEFS["guardiao"]
    from wyrdfall.domain.content import TALENT_TREES

    hero = create_player_character("hero", "Hero", class_def, TALENT_TREES[class_def.talent_tree_id], ruleset=ruleset)
    dungeon = DungeonDef(id="t", name="t", encounters=[
        EncounterDef(id="rest", name="r", room_type="rest"),
        EncounterDef(id="boss", name="b", enemy_ids=["goblin"], is_boss=True),
    ])
    session = GameSession(RunState(run_id="r", seed=1, dungeon_id="t", party=[hero]), ruleset, dict(TALENT_TREES), dungeon=dungeon)
    session._grant_ability(hero, "heartwood_bloom")  # 2 cargas por descanso
    assert hero.charges["heartwood_bloom"] == 2
    hero.charges["heartwood_bloom"] = 0
    session.resolve_rest("meditar")
    assert hero.charges["heartwood_bloom"] == 2  # either rest choice refills

    hero.charges["heartwood_bloom"] = 0
    hero.equipped_abilities = ["heartwood_bloom"]
    state = session.start_current_encounter()
    assert "heartwood_bloom" not in {a.id for a in session.combat_engine.legal_abilities(state, "hero")}
    from tests.test_session import play_encounter_to_completion

    hero.equipped_abilities = ["shield_bash"]
    session.run.party[0].equipped_abilities = ["shield_bash"]
    session.combat_state = None
    play_encounter_to_completion(session)
    assert session.encounter_victory
    session.collect_victory_reward_and_advance()  # boss -> Área transition refills
    assert session.run.party[0].charges["heartwood_bloom"] == 2


# -- §8.2 / §8.4 combos ------------------------------------------------------------


def test_sequence_combo_fires_only_right_after_the_named_ability():
    follow = Ability(id="follow", name="Follow", combo_from=["strike"], target_mode=TargetMode.SINGLE_ENEMY, effects=[_dmg(4.0)])
    engine = CombatEngine(_ruleset(follow=follow), rng=random.Random(1))
    state = engine.start_encounter([_hero(abilities=("strike", "follow"))], [_goblin(attack=0)])
    goblin = state.combatants["goblin"]
    _act(engine, state, "hero", "follow", "goblin")  # nothing before it
    assert goblin.current_hp == 96
    engine.resolve_ai_turn(state)
    _act(engine, state, "hero", "strike", "goblin")
    engine.resolve_ai_turn(state)
    log = _act(engine, state, "hero", "follow", "goblin")
    assert any("Combo!" in line for line in log)
    assert goblin.current_hp == pytest.approx(96 - 4 - 4 * (1 + COMBO_SEQUENCE_BONUS))


def test_team_combo_needs_a_different_ally_and_never_fires_solo_or_for_an_enemy():
    mark = Ability(id="mark", name="Mark", target_mode=TargetMode.SINGLE_ENEMY, effects=[
        Effect(kind=EffectKind.APPLY_STATUS, status_id="marcado_para_combo", duration=2),
    ])
    engine = CombatEngine(_ruleset(mark=mark), rng=random.Random(1))
    a, b = _hero("a", abilities=("mark", "strike"), speed=10), _hero("b", abilities=("strike",), speed=9)
    state = engine.start_encounter([a, b], [_goblin(attack=0, speed=1)])
    goblin = state.combatants["goblin"]
    _act(engine, state, "a", "mark", "goblin")
    assert goblin.statuses[0].source_id == "a"
    log = _act(engine, state, "b", "strike", "goblin")  # a different ally cashes it in
    assert any("Combo em equipe" in line for line in log)
    assert goblin.current_hp == 100 - 4 * 1.5
    assert goblin.statuses == []  # consumed

    # the marker's own hit does nothing special
    state.turn_index = state.turn_order.index("a")
    _act(engine, state, "a", "mark", "goblin")
    state.turn_index = state.turn_order.index("a")
    hp = goblin.current_hp
    _act(engine, state, "a", "strike", "goblin")
    assert goblin.current_hp == hp - 4
    assert goblin.statuses  # still marked

    # an enemy hitting a marked party member with an enemy-applied mark is the same rule, but a mark
    # from the other side never counts: put A's mark on B and let the goblin bite
    state.combatants["b"].statuses.append(ActiveStatus(status_id="marcado_para_combo", remaining_duration=2, source_id="a"))
    state.turn_index = state.turn_order.index("goblin")
    hp_b = state.combatants["b"].current_hp
    engine.resolve(state, Action(actor_id="goblin", ability_id="bite", target_ids=["b"]))
    assert state.combatants["b"].current_hp == hp_b - 2
    assert state.combatants["b"].statuses  # untouched


def test_content_wires_the_kinds_costs_and_combos():
    ruleset = build_ruleset()
    assert {c: d.resource_kind for c, d in CLASS_DEFS.items()} == {
        "runeguard": ResourceKind.FURY, "patrulheiro": ResourceKind.COMBO_POINTS,
        "mistico": ResourceKind.MANA, "guardiao": ResourceKind.ADRENALINE,
    }
    assert set(RESOURCE_NAMES) == set(ResourceKind)
    assert "combo_builder" in ruleset.abilities["aimed_shot"].tags
    assert "combo_finisher" in ruleset.abilities["multi_shot"].tags
    assert ruleset.abilities["reap_the_thread"].pays_with_hp
    assert ruleset.abilities["titanic_blow"].cooldown_turns == 2
    assert ruleset.abilities["arcane_cataclysm"].cooldown_turns == 3
    assert ruleset.abilities["heartwood_bloom"].charges_per_rest == 2
    assert ruleset.abilities["storm_of_blows"].combo_from == ["reckless_smash"]
    assert ruleset.statuses["marcado_para_combo"].team_combo_bonus > 0
    assert any(e.status_id == "marcado_para_combo" for e in ruleset.abilities["companion_peck"].effects)
    hero = create_player_character("h", "H", CLASS_DEFS["patrulheiro"], None, ruleset=ruleset)
    assert hero.resource_kind == ResourceKind.COMBO_POINTS
