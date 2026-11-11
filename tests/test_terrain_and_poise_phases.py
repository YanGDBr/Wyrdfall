"""Terreno (docs/design/01-mecanicas.md §11, 07-mundo-dificuldade.md) and
fases por quebra de Postura (13-chefes.md: Voltharion, A Mãe Pútrida,
O Inominável)."""

import random

import pytest

from wyrdfall.domain.abilities import Ability, TargetMode
from wyrdfall.domain.character import Character, EnemyPhase, Ruleset, SummonDef
from wyrdfall.domain.combat import _PHASE_SUMMON_CAP, Action, CombatEngine
from wyrdfall.domain.content import CLASS_DEFS, TALENT_TREES, build_ruleset
from wyrdfall.domain.content.terrain import AREA_TERRAINS
from wyrdfall.domain.dungeon import DungeonDef, EncounterDef
from wyrdfall.domain.factory import create_player_character
from wyrdfall.domain.models import Effect, EffectKind, Modifier, ModifierKind, Stat, StatBlock
from wyrdfall.domain.run import RunState
from wyrdfall.domain.terrain import TerrainDef
from wyrdfall.engine.session import GameSession


def _ruleset() -> Ruleset:
    abilities = {
        "strike": Ability(id="strike", name="Strike", target_mode=TargetMode.SINGLE_ENEMY,
                          effects=[Effect(kind=EffectKind.DAMAGE, amount=1, poise_damage=10.0)]),
        "tap": Ability(id="tap", name="Tap", target_mode=TargetMode.SINGLE_ENEMY,
                       effects=[Effect(kind=EffectKind.DAMAGE, amount=1)]),
        "bite": Ability(id="bite", name="Bite", target_mode=TargetMode.SINGLE_ENEMY, effects=[Effect(kind=EffectKind.DAMAGE, amount=1)]),
        "claw": Ability(id="claw", name="Claw", target_mode=TargetMode.SINGLE_ENEMY, effects=[Effect(kind=EffectKind.DAMAGE, amount=1)]),
        "roar": Ability(id="roar", name="Roar", target_mode=TargetMode.SINGLE_ENEMY, effects=[Effect(kind=EffectKind.DAMAGE, amount=1)]),
    }
    summons = {"imp": SummonDef(id="imp", name="Imp", base_stats=StatBlock(max_hp=5, attack=1, defense=0, speed=1, max_resource=0), abilities=["bite"])}
    return Ruleset(abilities=abilities, statuses={}, summons=summons)


def _hero(abilities=("strike", "tap")):
    stats = StatBlock(max_hp=100, attack=5, defense=0, speed=10, crit_chance=0.0, max_resource=0)
    return Character(id="hero", name="Hero", class_id="w", base_stats=stats, current_hp=100, current_resource=0,
                     abilities=list(abilities), equipped_abilities=list(abilities))


def _boss(phases, random_phase=False):
    stats = StatBlock(max_hp=500, attack=0, defense=0, speed=1, crit_chance=0.0, max_resource=0, max_poise=10.0)
    return Character(id="boss", name="Boss", class_id="b", base_stats=stats, current_hp=500, current_resource=0,
                     current_poise=10.0, abilities=list(phases[0].abilities), is_player=False,
                     enemy_phases=phases, random_phase_on_break=random_phase, phase_modifiers=list(phases[0].modifiers))


def _hit(engine, state, ability="strike"):
    state.turn_index = state.turn_order.index("hero")
    engine.resolve(state, Action(actor_id="hero", ability_id=ability, target_ids=["boss"]))


# -- Terreno ---------------------------------------------------------------------------


def test_terrain_modifiers_reach_both_sides_and_only_inside_the_fight():
    terrain = TerrainDef(id="t", name="T", description="d", modifiers=[Modifier(stat=Stat.DEFENSE, kind=ModifierKind.FLAT, value=7, source="terrain_t")])
    engine = CombatEngine(_ruleset(), rng=random.Random(1))
    hero, boss = _hero(), _boss([EnemyPhase(abilities=["bite"])])
    state = engine.start_encounter([hero], [boss], terrain=terrain)
    assert state.terrain_id == "t"
    assert state.combatants["hero"].computed_stats(engine.ruleset).defense == 7
    assert state.combatants["boss"].computed_stats(engine.ruleset).defense == 7
    assert any("Terreno: T" in line for line in state.log)
    assert hero.computed_stats(engine.ruleset).defense == 0  # the run copy is untouched


def test_every_area_terrain_applies_through_the_session_and_is_stripped_on_sync():
    ruleset = build_ruleset()
    class_def = CLASS_DEFS["runeguard"]
    hero = create_player_character("hero", "Hero", class_def, TALENT_TREES[class_def.talent_tree_id], ruleset=ruleset)
    dungeon = DungeonDef(id="t", name="t", encounters=[
        EncounterDef(id="e", name="e", enemy_ids=["goblin"], area_id="the_forgotten_mines"),
    ])
    session = GameSession(RunState(run_id="r", seed=1, dungeon_id="t", party=[hero]), ruleset, dict(TALENT_TREES), dungeon=dungeon)
    base_defense = hero.computed_stats(ruleset).defense
    state = session.start_current_encounter()
    assert state.terrain_id == "the_forgotten_mines"
    assert state.combatants["hero"].computed_stats(ruleset).defense == pytest.approx(base_defense + 2)
    assert state.combatants["goblin_0"].terrain_modifiers
    from tests.test_session import play_encounter_to_completion

    session.combat_state = None
    play_encounter_to_completion(session)
    assert session.encounter_victory
    assert session.run.party[0].terrain_modifiers  # the run's copy IS the combat object while the fight is on
    session.collect_victory_reward_and_advance()
    assert session.run.party[0].terrain_modifiers == []  # gone the moment the fight is settled
    assert "the_hollow_barrow" not in AREA_TERRAINS  # the tutorial Área has none
    assert len(AREA_TERRAINS) == 11


# -- fases por quebra de Postura ----------------------------------------------------------


def test_poise_break_phases_advance_on_breaks_not_on_hp():
    phases = [
        EnemyPhase(trigger="poise_break", abilities=["bite"], modifiers=[Modifier(stat=Stat.DODGE_CHANCE, kind=ModifierKind.FLAT, value=0.5, source="veil")]),
        EnemyPhase(trigger="poise_break", abilities=["claw"]),
        EnemyPhase(trigger="poise_break", abilities=["roar"]),
    ]
    engine = CombatEngine(_ruleset(), rng=random.Random(1))
    state = engine.start_encounter([_hero()], [_boss(phases)])
    boss = state.combatants["boss"]
    assert boss.computed_stats(engine.ruleset).dodge_chance == pytest.approx(0.5)
    boss.base_stats.dodge_chance = 0.0
    boss.phase_modifiers = []  # let the test's hits land deterministically...
    boss.current_hp = 50.0  # ...and prove HP alone never moves a poise-phased boss
    _hit(engine, state, "tap")
    assert boss.current_phase_index == 0 and boss.abilities == ["bite"]

    boss.phase_modifiers = list(phases[0].modifiers)
    boss.base_stats.dodge_chance = -1.0  # cancel the veil so the strike connects
    _hit(engine, state, "strike")  # 10 poise damage = a break
    assert boss.poise_breaks == 1 and boss.current_phase_index == 1
    assert boss.abilities == ["claw"] and boss.phase_modifiers == []  # the veil dropped
    _hit(engine, state, "strike")
    assert boss.current_phase_index == 2 and boss.abilities == ["roar"]
    _hit(engine, state, "strike")
    assert boss.current_phase_index == 2  # stays on the last phase


def test_a_phase_entry_summon_appears_on_break_up_to_the_cap():
    phases = [EnemyPhase(trigger="poise_break", abilities=["bite"])] + [
        EnemyPhase(trigger="poise_break", abilities=["bite"], summon_id="imp") for _ in range(6)
    ]
    engine = CombatEngine(_ruleset(), rng=random.Random(1))
    state = engine.start_encounter([_hero()], [_boss(phases)])
    for _ in range(6):
        _hit(engine, state, "strike")
    summons = [cid for cid in state.enemy_ids() if cid.startswith("boss_summon_")]
    assert len(summons) == _PHASE_SUMMON_CAP
    assert all(state.combatants[cid].is_companion and not state.combatants[cid].is_player for cid in summons)
    # a summon must fall for the fight to end
    state.combatants["boss"].current_hp = 0.0
    engine._check_victory(state)
    assert not state.is_over


def test_random_mask_on_break_never_repeats_the_current_one():
    phases = [EnemyPhase(trigger="poise_break", abilities=[a]) for a in ("bite", "claw", "roar")]
    engine = CombatEngine(_ruleset(), rng=random.Random(5))
    state = engine.start_encounter([_hero()], [_boss(phases, random_phase=True)])
    boss = state.combatants["boss"]
    seen = [boss.current_phase_index]
    for _ in range(25):
        _hit(engine, state, "strike")
        seen.append(boss.current_phase_index)
    assert all(a != b for a, b in zip(seen, seen[1:]))
    assert len(set(seen)) == 3  # every mask shows up over 25 breaks


def test_the_three_bosses_and_the_broto_are_wired():
    from wyrdfall.domain.content import ENEMY_DEFS

    ruleset = build_ruleset()
    assert "broto_putrido" in ruleset.summons
    for boss_id in ("voltharion", "mae_putrida", "o_inominavel"):
        assert all(p.trigger == "poise_break" for p in ENEMY_DEFS[boss_id].phases), boss_id
        for phase in ENEMY_DEFS[boss_id].phases:
            assert all(a in ruleset.abilities for a in phase.abilities)
