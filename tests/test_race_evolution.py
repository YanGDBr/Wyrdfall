"""Evolução de raça na run (docs/design/04-racas.md item 5) and the
TRANSFORM effect (11-habilidades.md §5) behind the Licantropo's Forma de
Fera."""

import pytest

from wyrdfall.domain.combat import LYCAN_TRANSFORM_STACKS, Action, CombatEngine
from wyrdfall.domain.content import CLASS_DEFS, TALENT_TREES, build_ruleset
from wyrdfall.domain.dungeon import DungeonDef, EncounterDef
from wyrdfall.domain.factory import create_player_character
from wyrdfall.domain.models import Stat
from wyrdfall.domain.race_evolution import (
    ELF_CRIT_THRESHOLD,
    FADA_PROC_THRESHOLD,
    RACE_EVOLUTION_DEFS,
    apply_race_evolution,
    pending_race_evolution,
)
from wyrdfall.domain.races import RACE_DEFS
from wyrdfall.domain.run import RunState
from wyrdfall.engine.session import GameSession


def _session(class_id="runeguard", race_id="human", encounters=None):
    ruleset = build_ruleset()
    class_def = CLASS_DEFS[class_id]
    tree = TALENT_TREES[class_def.talent_tree_id]
    hero = create_player_character("hero", "Hero", class_def, tree, ruleset=ruleset, race_id=race_id)
    dungeon = DungeonDef(
        id="t", name="t",
        encounters=encounters or [EncounterDef(id="boss", name="boss", enemy_ids=["goblin"], is_boss=True)],
    )
    return GameSession(RunState(run_id="r", seed=1, dungeon_id="t", party=[hero]), ruleset, dict(TALENT_TREES), dungeon=dungeon)


def _win_current_fight(session):
    state = session.start_current_encounter()
    for enemy_id in state.enemy_ids():
        state.combatants[enemy_id].current_hp = 0.0
    session.combat_engine._check_victory(state)
    return state


def test_every_race_has_an_in_run_evolution_of_some_form():
    # trigger-style ones live in RACE_EVOLUTION_DEFS; Renascido's is an
    # ability, Construto's a mechanic, Licantropo's a per-combat TRANSFORM;
    # Meio-celestial has none by design (04-racas.md: the form switch IS it)
    covered = set(RACE_EVOLUTION_DEFS) | {"renascido", "construto", "licantropo", "meio_celestial"}
    assert set(RACE_DEFS) <= covered
    for race_id, evolution in RACE_EVOLUTION_DEFS.items():
        assert evolution.race_id == race_id and (evolution.modifiers or evolution.on_evolve_effects)


def test_human_evolves_on_the_first_boss_and_keeps_the_resistances_for_the_run():
    session = _session(race_id="human")
    _win_current_fight(session)
    before = session.run.party[0].computed_stats(session.ruleset).fire_resist
    session.collect_victory_reward_and_advance()
    hero = session.run.party[0]
    assert hero.race_evolution_id == "abencoado_pelo_destino"
    assert hero.computed_stats(session.ruleset).fire_resist == pytest.approx(before + 0.05)
    assert session.run.race_evolution_log and "Abençoado" in session.run.race_evolution_log[0]
    # once: a second boss doesn't re-apply
    assert pending_race_evolution(hero, first_boss=True) is None


def test_dwarf_evolves_only_if_the_whole_area_used_no_magic():
    session = _session(class_id="mistico", race_id="dwarf")
    state = session.start_current_encounter()
    magic = next(a for a in session.combat_engine.legal_abilities(state, "hero") if "magic" in a.tags)
    targets = session.combat_engine.legal_target_ids(state, "hero", magic)
    session.submit_action(Action(actor_id="hero", ability_id=magic.id, target_ids=targets[:1]))
    assert state.combatants["hero"].used_non_physical_this_area is True
    state.combatants["goblin_0"].current_hp = 0.0
    session.combat_engine._check_victory(state)
    session.collect_victory_reward_and_advance()
    hero = session.run.party[0]
    assert hero.race_evolution_id is None  # the Área was tainted by a spell
    assert hero.used_non_physical_this_area is False  # ...but the counter resets per Área

    clean = _session(class_id="runeguard", race_id="dwarf")
    _win_current_fight(clean)
    clean.collect_victory_reward_and_advance()
    hero = clean.run.party[0]
    assert hero.race_evolution_id == "furia_da_forja"
    assert hero.computed_stats(clean.ruleset).armor_penetration_percent >= 0.20


def test_elf_and_fada_evolve_off_their_run_counters_mid_fight():
    session = _session(race_id="elf")
    state = session.start_current_encounter()
    hero = state.combatants["hero"]
    hero.crits_landed = ELF_CRIT_THRESHOLD - 1
    hero.base_stats.crit_chance = 1.0  # the next hit crits for sure
    mult_before = hero.computed_stats(session.ruleset).crit_mult
    strike = session.combat_engine.legal_abilities(state, "hero")[0]
    targets = session.combat_engine.legal_target_ids(state, "hero", strike)
    session.submit_action(Action(actor_id="hero", ability_id=strike.id, target_ids=targets[:1]))
    assert hero.crits_landed == ELF_CRIT_THRESHOLD
    assert hero.race_evolution_id == "furia_elfica"
    assert hero.computed_stats(session.ruleset).crit_mult == pytest.approx(mult_before + 0.5)
    assert any("Fúria Élfica" in line for line in state.log)

    fada = _session(race_id="fada").run.party[0]
    fada.procs_fired = FADA_PROC_THRESHOLD
    evolution = pending_race_evolution(fada)
    assert evolution is not None and evolution.id == "sorte_do_acaso"
    proc_before = fada.computed_stats(build_ruleset()).proc_chance_percent
    apply_race_evolution(fada, evolution)
    assert fada.computed_stats(build_ruleset()).proc_chance_percent == pytest.approx(proc_before + 0.20)


def test_orc_gets_a_second_wind_the_first_time_it_drops_below_30_percent():
    session = _session(race_id="orc")
    state = session.start_current_encounter()
    hero = state.combatants["hero"]
    max_hp = hero.computed_stats(session.ruleset).max_hp
    goblin = state.combatants["goblin_0"]
    goblin.base_stats.attack = max_hp * 0.8  # one hit takes the orc under 30%
    state.turn_index = state.turn_order.index("goblin_0")
    session.combat_engine.resolve_ai_turn(state)
    assert hero.is_alive
    assert hero.race_evolution_id == "segundo_folego"
    assert hero.current_hp > 0.30 * max_hp  # the 25% heal landed on top of what was left
    assert any(s.status_id == "segundo_folego" for s in hero.statuses)
    assert any("Segundo Fôlego" in line for line in state.log)


def test_licantropo_transforms_at_the_instinct_threshold_with_its_own_kit_for_the_rest_of_the_fight():
    session = _session(race_id="licantropo")
    state = session.start_current_encounter()
    engine = session.combat_engine
    hero = state.combatants["hero"]
    for _ in range(LYCAN_TRANSFORM_STACKS):
        engine._apply_status(state, hero, "instinto_selvagem", duration=2, stacks=1)
    assert hero.active_transform_id == "forma_de_fera"
    assert any("Forma de Fera" in line for line in state.log)
    kit = {a.id for a in engine.legal_abilities(state, "hero")}
    assert {"fera_dilacerar", "fera_mordida_voraz", "fera_uivo"} <= kit
    assert "guard" in kit and "strike" not in kit  # universal stays, the normal kit is replaced
    assert hero.computed_stats(session.ruleset).lifesteal_percent >= 0.25

    state.turn_index = state.turn_order.index("hero")
    goblin = state.combatants["goblin_0"]
    goblin.base_stats.max_hp = 10_000
    goblin.current_hp = 10_000
    engine.resolve(state, Action(actor_id="hero", ability_id="fera_dilacerar", target_ids=["goblin_0"]))
    assert goblin.current_hp < 10_000
    assert any(s.status_id == "bleeding" for s in goblin.statuses)

    # the form is the combat's, not the run's
    state.combatants["goblin_0"].current_hp = 0.0
    engine._check_victory(state)
    session.collect_victory_reward_and_advance()
    survivor = session.run.party[0]
    assert survivor.active_transform_id is None and survivor.transform_modifiers == []


def test_a_timed_transform_expires_at_its_own_turn_start():
    from wyrdfall.domain.character import TransformDef
    from wyrdfall.domain.models import Effect, EffectKind, Modifier, ModifierKind

    ruleset = build_ruleset()
    ruleset.transforms["breve"] = TransformDef(
        id="breve", name="Forma Breve", duration=1,
        modifiers=[Modifier(stat=Stat.ATTACK, kind=ModifierKind.FLAT, value=10, source="breve")],
    )
    class_def = CLASS_DEFS["runeguard"]
    hero = create_player_character("hero", "Hero", class_def, TALENT_TREES[class_def.talent_tree_id], ruleset=ruleset)
    from wyrdfall.domain.content import ENEMY_DEFS
    from wyrdfall.domain.enemies import instantiate_enemy

    engine = CombatEngine(ruleset)
    state = engine.start_encounter([hero], [instantiate_enemy(ENEMY_DEFS["goblin"], "goblin_0")])
    fighter = state.combatants["hero"]
    attack_before = fighter.computed_stats(ruleset).attack
    engine._apply_effect(state, "hero", "hero", Effect(kind=EffectKind.TRANSFORM, transform_id="breve"))
    assert fighter.active_transform_id == "breve"
    assert fighter.computed_stats(ruleset).attack == pytest.approx(attack_before + 10)
    assert {a.id for a in engine.legal_abilities(state, "hero")} >= {"strike"}  # no kit of its own: normal kit stays
    engine._begin_turn(state, "hero")
    assert fighter.active_transform_id is None
    assert fighter.computed_stats(ruleset).attack == pytest.approx(attack_before)


def test_construto_absorbs_one_rune_for_the_run_without_a_slot():
    session = _session(race_id="construto")
    session.run.rune_inventory = ["rune_might", "rune_bulwark"]
    hero = session.run.party[0]
    attack_before = hero.computed_stats(session.ruleset).attack
    assert session.absorb_rune("hero", "rune_might") is True
    assert hero.absorbed_rune_id == "rune_might" and hero.body_rune_slots == []
    assert session.run.rune_inventory == ["rune_bulwark"]  # consumed
    assert hero.computed_stats(session.ruleset).attack == pytest.approx(attack_before + 3)
    assert session.absorb_rune("hero", "rune_bulwark") is False  # once per run

    human = _session(race_id="human")
    human.run.rune_inventory = ["rune_might"]
    assert human.absorb_rune("hero", "rune_might") is False


@pytest.mark.asyncio
async def test_a_construto_absorbs_a_rune_from_the_equipment_screen(tmp_path, monkeypatch):
    monkeypatch.setattr("wyrdfall.persistence.store.save_db_path", lambda: tmp_path / "wyrdfall.db")
    from wyrdfall.app import WyrdfallApp
    from wyrdfall.ui.screens.equipment import EquipmentScreen

    app = WyrdfallApp()
    app.meta.unlock_race("construto")
    app.meta.active_race_id = "construto"
    async with app.run_test(size=(100, 250)) as pilot:
        await pilot.pause()
        await pilot.click("#new_run")
        await pilot.pause()
        await pilot.click("#class_runeguard")
        await pilot.pause()
        await pilot.click("#confirm")
        await pilot.pause()
        await pilot.click("#portal_portao_do_tumulo")
        await pilot.pause()
        hero = app.client.get_run().party[0]
        assert hero.race_id == "construto"
        app.client.get_run().rune_inventory = ["rune_might", "rune_bulwark"]
        attack_before = hero.computed_stats(app.client.ruleset).attack

        await pilot.click("#equipment")
        await pilot.pause(0.2)
        assert isinstance(app.screen, EquipmentScreen)
        await pilot.click("#tab_runas")
        await pilot.pause(0.2)
        await pilot.click("#absorb_rune_might")
        await pilot.pause(0.3)
        assert hero.absorbed_rune_id == "rune_might"
        assert hero.computed_stats(app.client.ruleset).attack == pytest.approx(attack_before + 3)
        assert not list(app.screen.query("#absorb_rune_bulwark"))  # once per run: the offer is gone
