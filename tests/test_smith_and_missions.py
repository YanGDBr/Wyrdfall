"""docs/design/08-itens-crafting.md's permanent layer: materials that
persist between runs, the Ferreiro's recipes (starting gear, the Construto),
Missões da Guilda -- plus 04-racas.md's Portal Feérico unlock for Fada."""

import pytest

from wyrdfall.domain.content import CLASS_DEFS, TALENT_TREES, build_ruleset
from wyrdfall.domain.dungeon import DungeonDef, EncounterDef
from wyrdfall.domain.events import EventDef, EventOptionDef
from wyrdfall.domain.factory import create_player_character
from wyrdfall.domain.guild_missions import GUILD_MISSION_DEFS, MissionProgressInput
from wyrdfall.domain.items import EQUIPMENT_DEFS, Rarity
from wyrdfall.domain.run import RunState
from wyrdfall.domain.runes import RUNE_DEFS
from wyrdfall.domain.smith import RECIPE_DEFS
from wyrdfall.engine.session import GameSession
from wyrdfall.net.game_client import LocalGameClient
from wyrdfall.persistence.store import MetaProgressionState, RunSummary, load_meta_progression, save_meta_progression
from tests.test_session import play_encounter_to_completion


def _summary(victory: bool, run_id="r") -> RunSummary:
    return RunSummary(run_id=run_id, class_id="runeguard", floor_reached=3, victory=victory)


# -- materiais persistentes + Ferreiro ------------------------------------------------


def test_materials_persist_across_runs_won_or_lost():
    meta = MetaProgressionState()
    meta.record_run(_summary(False), ecos_earned=0, materials={Rarity.COMUM: 2, Rarity.RARO: 1})
    meta.record_run(_summary(True, run_id="r2"), ecos_earned=0, materials={Rarity.COMUM: 1, Rarity.LENDARIO: 1})
    assert meta.materials == {Rarity.COMUM: 3, Rarity.RARO: 1, Rarity.LENDARIO: 1}


def test_recipes_are_sane_and_crafting_pays_once():
    for recipe in RECIPE_DEFS.values():
        assert recipe.cost_ecos > 0 and recipe.cost_materials
        assert (recipe.grants_item_id in EQUIPMENT_DEFS) or recipe.unlocks_race or (recipe.grants_rune_id in RUNE_DEFS)
    meta = MetaProgressionState(ecos=100, materials={Rarity.COMUM: 3})
    assert meta.can_craft("craft_traveler_cap")
    assert not meta.can_craft("craft_guardian_helm")  # no Raro
    assert not meta.can_craft("nao_existe")
    assert meta.craft("craft_traveler_cap") is True
    assert meta.starting_gear == ["traveler_cap"]
    assert meta.materials[Rarity.COMUM] == 1 and meta.ecos == 90
    assert meta.craft("craft_traveler_cap") is False  # once
    assert MetaProgressionState(ecos=0, materials={Rarity.COMUM: 9}).craft("craft_traveler_cap") is False


def test_the_construto_recipe_unlocks_the_race_exactly_once():
    meta = MetaProgressionState(ecos=100, materials={Rarity.LENDARIO: 2, Rarity.RARO: 4})
    assert "construto" not in meta.unlocked_races
    assert meta.craft("construir_construto") is True
    assert "construto" in meta.unlocked_races
    assert meta.materials[Rarity.LENDARIO] == 1
    assert meta.craft("construir_construto") is False
    assert not meta.can_craft("construir_construto")


def test_starting_gear_reaches_a_new_runs_inventory_but_is_not_equipped(tmp_path, monkeypatch):
    monkeypatch.setattr("wyrdfall.persistence.store.save_db_path", lambda: tmp_path / "wyrdfall.db")
    from wyrdfall.app import WyrdfallApp

    app = WyrdfallApp()
    app.meta.ecos = 100
    app.meta.materials = {Rarity.COMUM: 4}
    app.meta.craft("craft_traveler_cap")
    app.meta.craft("craft_traveler_boots")
    run = app.start_new_run().get_run()
    assert sorted(p.definition_id for p in run.equipment_instances.values() if not p.definition_id.startswith("basic_")) == ["traveler_boots", "traveler_cap"]
    assert run.party[0].equipped_armor == {}


# -- Missões da Guilda --------------------------------------------------------------------


def test_each_mission_reads_its_counter_and_pays_its_unlock_once():
    data = MissionProgressInput(bosses_defeated_ids={"a", "b"}, runs_finished=9, risk_free_victories=3)
    assert not GUILD_MISSION_DEFS["cacador_de_chefes"].is_complete(data)
    assert not GUILD_MISSION_DEFS["peregrino"].is_complete(data)
    assert GUILD_MISSION_DEFS["ascese"].is_complete(data)

    meta = MetaProgressionState()
    for i in range(3):
        meta.record_run(_summary(True, f"w{i}"), ecos_earned=0, boss_ids=[f"boss_{i}"], used_risk_pact=False)
    assert meta.risk_free_victories == 3 and meta.bosses_defeated_ids == {"boss_0", "boss_1", "boss_2"}
    slots_before = meta.vantagem_slots
    completed = meta.complete_missions()
    assert set(completed) == {"cacador_de_chefes", "ascese"}
    assert "portao_submerso" in meta.unlocked_portals
    assert meta.vantagem_slots == slots_before + 1
    assert meta.complete_missions() == []  # never twice

    for i in range(7):
        meta.record_run(_summary(False, f"l{i}"), ecos_earned=0)
    assert meta.complete_missions() == ["peregrino"]
    assert "tartaruga_de_pedra" in meta.unlocked_companions

    risky = MetaProgressionState()
    risky.record_run(_summary(True), ecos_earned=0, used_risk_pact=True)
    assert risky.risk_free_victories == 0


def test_a_boss_win_records_the_boss_id_and_bank_time_feeds_the_missions(tmp_path, monkeypatch):
    monkeypatch.setattr("wyrdfall.persistence.store.save_db_path", lambda: tmp_path / "wyrdfall.db")
    from wyrdfall.app import WyrdfallApp

    ruleset = build_ruleset()
    class_def = CLASS_DEFS["runeguard"]
    hero = create_player_character("hero", "Hero", class_def, TALENT_TREES[class_def.talent_tree_id], ruleset=ruleset)
    dungeon = DungeonDef(id="t", name="t", encounters=[EncounterDef(id="boss_x", name="b", enemy_ids=["goblin"], is_boss=True)])
    session = GameSession(RunState(run_id="r", seed=1, dungeon_id="t", party=[hero]), ruleset, dict(TALENT_TREES), dungeon=dungeon)
    session.run.materials = {Rarity.RARO: 1}
    play_encounter_to_completion(session)
    assert session.encounter_victory
    session.collect_victory_reward_and_advance()
    summary = session.finalize_run()
    assert session.run.defeated_boss_ids == ["boss_x"]

    app = WyrdfallApp()
    app.client = LocalGameClient(session)
    app.client._last_summary = summary
    app.bank_run_reward()
    assert "boss_x" in app.meta.bosses_defeated_ids
    assert app.meta.materials.get(Rarity.RARO, 0) >= 1
    assert app.meta.risk_free_victories == 1


# -- Fada: Portal Feérico ---------------------------------------------------------------------


def test_the_portal_feerico_unlocks_fada_at_bank_time(tmp_path, monkeypatch):
    monkeypatch.setattr("wyrdfall.persistence.store.save_db_path", lambda: tmp_path / "wyrdfall.db")
    from wyrdfall.app import WyrdfallApp
    from wyrdfall.domain.content import EVENT_DEFS

    assert EVENT_DEFS["portal_feerico"].option("atravessar").unlocks_race == "fada"
    portal = EventDef(id="only", name="Only", text="...", options=[
        EventOptionDef(id="atravessar", label="a", outcome_text="", unlocks_race="fada"),
    ])
    monkeypatch.setattr("wyrdfall.engine.session.EVENT_DEFS", {"only": portal})
    ruleset = build_ruleset()
    class_def = CLASS_DEFS["runeguard"]
    hero = create_player_character("hero", "Hero", class_def, TALENT_TREES[class_def.talent_tree_id], ruleset=ruleset)
    dungeon = DungeonDef(id="t", name="t", encounters=[EncounterDef(id="ev", name="e", room_type="event")])
    session = GameSession(RunState(run_id="r", seed=1, dungeon_id="t", party=[hero]), ruleset, dict(TALENT_TREES), dungeon=dungeon)
    session.resolve_event("atravessar")
    assert session.run.race_unlocks == ["fada"]
    summary = session.finalize_run()

    app = WyrdfallApp()
    assert "fada" not in app.meta.unlocked_races
    app.client = LocalGameClient(session)
    app.client._last_summary = summary
    app.bank_run_reward()
    assert "fada" in app.meta.unlocked_races


def test_new_meta_fields_round_trip_through_the_save(tmp_path):
    meta = MetaProgressionState(ecos=100, materials={Rarity.COMUM: 2, Rarity.LENDARIO: 1, Rarity.RARO: 2})
    meta.craft("craft_traveler_cap")
    meta.craft("construir_construto")
    meta.record_run(_summary(True), ecos_earned=0, boss_ids=["b1"])
    meta.complete_missions()
    path = tmp_path / "w.db"
    save_meta_progression(meta, path)
    reloaded = load_meta_progression(path)
    assert reloaded.materials == meta.materials
    assert reloaded.starting_gear == ["traveler_cap"] and reloaded.crafted_recipes == meta.crafted_recipes
    assert reloaded.bosses_defeated_ids == {"b1"} and reloaded.risk_free_victories == 1
    assert "construto" in reloaded.unlocked_races
