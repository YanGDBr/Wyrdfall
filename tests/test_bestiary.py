import pytest

from wyrdfall.app import WyrdfallApp
from wyrdfall.domain.bestiary import BESTIARY_ENTRIES
from wyrdfall.domain.content import ENEMY_DEFS


@pytest.fixture
def app(tmp_path, monkeypatch):
    # keep tests from touching the developer's real save file
    monkeypatch.setattr("wyrdfall.persistence.store.save_db_path", lambda: tmp_path / "wyrdfall.db")
    return WyrdfallApp()


def test_every_enemy_id_has_a_bestiary_entry():
    for enemy_id in ENEMY_DEFS:
        assert enemy_id in BESTIARY_ENTRIES


def test_starting_an_encounter_discovers_its_enemies_and_nothing_else(app):
    assert app.meta.discovered_enemies == set()

    app.start_new_run()
    app.client.session.start_current_encounter()
    app.discover_enemies_in_current_encounter()

    e1_enemies = set(app.client.session.dungeon.encounters[0].enemy_ids)
    assert app.meta.discovered_enemies == e1_enemies
    # e6's hollow_knight hasn't been encountered yet
    assert "hollow_knight" not in app.meta.discovered_enemies


def test_discovering_an_encounter_with_multiple_new_enemies_records_all_of_them(app):
    # start_new_run defaults to Portão do Túmulo (Fase 7), whose path skips
    # Área 2 -- e14 "Acampamento da Nevasca" (Área 3) is this Portal's own
    # first 3-distinct-enemy encounter. Found by id rather than a hardcoded
    # index so inserted non-combat nodes (Descanso) can't shift it.
    app.start_new_run()
    encounters = app.client.get_dungeon().encounters
    app.client.get_run().encounter_index = next(i for i, e in enumerate(encounters) if e.id == "e14")
    app.client.session.start_current_encounter()
    app.discover_enemies_in_current_encounter()

    assert app.meta.discovered_enemies == {"xama_da_nevasca", "espectro_gelado", "lobo_de_gelo"}


def test_discovery_is_idempotent_and_only_saves_when_something_is_new(app, monkeypatch):
    app.start_new_run()
    saved = []
    monkeypatch.setattr(app, "save_progress", lambda: saved.append(True))

    app.client.session.start_current_encounter()
    app.discover_enemies_in_current_encounter()
    assert len(saved) == 1

    # re-running discovery for an already-discovered encounter saves nothing new
    app.discover_enemies_in_current_encounter()
    assert len(saved) == 1
