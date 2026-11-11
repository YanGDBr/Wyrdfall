from wyrdfall.domain.content.permanent_trees import PERMANENT_TREE_COST
from wyrdfall.domain.economy import BASE_POR_ANDAR, BONUS_POR_CHEFE, TAXA_CONVERSAO, ecos_for_run
from wyrdfall.persistence.store import (
    MetaProgressionState,
    RunSummary,
    load_meta_progression,
    save_meta_progression,
)


def test_loading_a_missing_db_returns_defaults(tmp_path):
    state = load_meta_progression(tmp_path / "new.db")
    assert state.ecos == 0
    assert state.bonus_talent_points == 0


def test_save_then_load_round_trips(tmp_path):
    db_path = tmp_path / "wyrdfall.db"
    state = MetaProgressionState()
    state.record_run(RunSummary(run_id="r1", class_id="runeguard", floor_reached=3, victory=False), ecos_earned=5)
    save_meta_progression(state, db_path)

    reloaded = load_meta_progression(db_path)
    assert reloaded.ecos == 5
    assert reloaded.best_floor_reached == 3
    assert len(reloaded.run_history) == 1
    assert reloaded.run_history[0].class_id == "runeguard"


def test_saving_twice_overwrites_rather_than_duplicating(tmp_path):
    db_path = tmp_path / "wyrdfall.db"
    state = MetaProgressionState(ecos=10)
    save_meta_progression(state, db_path)
    state.ecos = 20
    save_meta_progression(state, db_path)

    reloaded = load_meta_progression(db_path)
    assert reloaded.ecos == 20


def test_record_run_increments_total_deaths_only_on_defeat():
    state = MetaProgressionState()
    state.record_run(RunSummary(run_id="r1", class_id="runeguard", floor_reached=1, victory=True), ecos_earned=0)
    assert state.total_deaths == 0

    state.record_run(RunSummary(run_id="r2", class_id="runeguard", floor_reached=1, victory=False), ecos_earned=0)
    assert state.total_deaths == 1


def test_record_run_increments_total_victories_only_on_victory():
    state = MetaProgressionState()
    state.record_run(RunSummary(run_id="r1", class_id="runeguard", floor_reached=1, victory=False), ecos_earned=0)
    assert state.total_victories == 0

    state.record_run(RunSummary(run_id="r2", class_id="runeguard", floor_reached=1, victory=True), ecos_earned=0)
    assert state.total_victories == 1


def test_ascension_unlocks_on_the_first_victory_only_and_levels_are_bounded():
    state = MetaProgressionState()
    assert state.set_ascension_level(1) is False  # locked
    state.record_run(RunSummary(run_id="r1", class_id="runeguard", floor_reached=2, victory=False), ecos_earned=0)
    assert state.ascension_unlocked is False
    state.record_run(RunSummary(run_id="r2", class_id="runeguard", floor_reached=9, victory=True), ecos_earned=0)
    assert state.ascension_unlocked is True
    assert state.set_ascension_level(3) is True and state.ascension_level == 3
    assert state.set_ascension_level(99) is False
    assert state.set_ascension_level(0) is True


def test_pacts_and_ascension_round_trip_through_the_save(tmp_path):
    db_path = tmp_path / "wyrdfall.db"
    state = MetaProgressionState(ecos=200, ascension_unlocked=True)
    state.buy_pact("fio_afiado")
    state.toggle_pact("fio_afiado")
    state.buy_vantagem_slot()
    state.set_ascension_level(2)
    state.buy_companion("corvo_do_wyrd")
    state.set_active_companion("corvo_do_wyrd")
    save_meta_progression(state, db_path)

    reloaded = load_meta_progression(db_path)
    assert reloaded.unlocked_companions == {"corvo_do_wyrd"} and reloaded.active_companion_id == "corvo_do_wyrd"
    assert reloaded.unlocked_pacts == {"fio_afiado"}
    assert reloaded.equipped_pacts == ["fio_afiado"]
    assert reloaded.vantagem_slots == state.vantagem_slots
    assert reloaded.ascension_level == 2 and reloaded.ascension_unlocked


def test_buy_portal_unlock_requires_a_prior_victory_and_enough_ecos():
    state = MetaProgressionState(ecos=100)
    assert state.buy_portal_unlock("portao_submerso") is False  # never won a run yet

    state.total_victories = 1
    state.ecos = 0
    assert state.buy_portal_unlock("portao_submerso") is False  # can't afford it

    state.ecos = 100
    assert state.buy_portal_unlock("portao_submerso") is True
    assert "portao_submerso" in state.unlocked_portals
    assert state.ecos == 100 - 20  # PORTAL_SUBMERSO_COST

    assert state.buy_portal_unlock("portao_submerso") is False  # already unlocked


def test_buy_bonus_talent_point_spends_ecos_and_respects_cost():
    state = MetaProgressionState(ecos=2)
    assert state.buy_bonus_talent_point() is False  # cost is 3, can't afford
    state.ecos = 3
    assert state.buy_bonus_talent_point() is True
    assert state.ecos == 0
    assert state.bonus_talent_points == 1


def test_ecos_for_run_combines_floors_bosses_and_leftover_fragments():
    assert ecos_for_run(floors_completed=0, bosses_defeated=0, fragments_remaining=0) == 0
    assert ecos_for_run(floors_completed=2, bosses_defeated=0, fragments_remaining=0) == 2 * BASE_POR_ANDAR
    assert ecos_for_run(floors_completed=0, bosses_defeated=1, fragments_remaining=0) == BONUS_POR_CHEFE
    assert ecos_for_run(floors_completed=0, bosses_defeated=0, fragments_remaining=20) == round(20 * TAXA_CONVERSAO)
    assert ecos_for_run(floors_completed=3, bosses_defeated=1, fragments_remaining=10) == (
        3 * BASE_POR_ANDAR + BONUS_POR_CHEFE + round(10 * TAXA_CONVERSAO)
    )


def test_unlock_race_is_idempotent():
    state = MetaProgressionState()
    assert "dwarf" not in state.unlocked_races
    assert state.unlock_race("dwarf") is True
    assert "dwarf" in state.unlocked_races
    assert state.unlock_race("dwarf") is False


def test_complete_conquest_awards_ecos_once():
    state = MetaProgressionState()
    assert state.complete_conquest("first_victory", 20) == 20
    assert state.ecos == 20
    assert state.complete_conquest("first_victory", 20) == 0
    assert state.ecos == 20


def test_allocate_permanent_node_spends_ecos_and_records_the_node():
    state = MetaProgressionState(ecos=PERMANENT_TREE_COST)
    assert state.allocate_permanent_node("permanent_dwarf", "permanent_dwarf_1") is True
    assert state.ecos == 0
    assert state.permanent_tree_allocated["permanent_dwarf"] == {"permanent_dwarf_1"}


def test_allocate_permanent_node_rejects_insufficient_ecos():
    state = MetaProgressionState(ecos=PERMANENT_TREE_COST - 1)
    assert state.allocate_permanent_node("permanent_dwarf", "permanent_dwarf_1") is False
    assert state.permanent_tree_allocated == {}


def test_allocate_permanent_node_respects_prerequisites():
    state = MetaProgressionState(ecos=PERMANENT_TREE_COST * 3)
    # permanent_dwarf_2 requires permanent_dwarf_1 first
    assert state.allocate_permanent_node("permanent_dwarf", "permanent_dwarf_2") is False
    assert state.allocate_permanent_node("permanent_dwarf", "permanent_dwarf_1") is True
    assert state.allocate_permanent_node("permanent_dwarf", "permanent_dwarf_2") is True


def test_allocate_permanent_node_rejects_an_unknown_tree_or_node():
    state = MetaProgressionState(ecos=PERMANENT_TREE_COST * 3)
    assert state.allocate_permanent_node("not_a_tree", "whatever") is False
    assert state.allocate_permanent_node("permanent_dwarf", "not_a_node") is False


def test_allocate_permanent_node_has_no_desalocar():
    # Same "sem reset" rule as every other progression tree -- there's no
    # method to remove an already-allocated permanent node.
    state = MetaProgressionState()
    assert not hasattr(state, "deallocate_permanent_node")


def test_a_permanent_nodes_modifier_reaches_a_freshly_built_hero(tmp_path, monkeypatch):
    from wyrdfall.app import WyrdfallApp

    monkeypatch.setattr("wyrdfall.persistence.store.save_db_path", lambda: tmp_path / "wyrdfall.db")
    app = WyrdfallApp()
    app.meta.ecos = PERMANENT_TREE_COST
    app.meta.active_race_id = "human"  # the default -- confirms build_hero reads it, not hardcodes it
    assert app.meta.allocate_permanent_node("permanent_human", "permanent_human_1") is True

    hero = app.build_hero("hero", "Hero", class_id="runeguard")
    # permanent_human_1 grants +2% Crítico flat -- present among the hero's
    # baked-in permanent_modifiers regardless of anything else recomputed
    assert any(m.source == "permanent_human_1" for m in hero.permanent_modifiers)
