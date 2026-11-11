"""Teclas remapeáveis (docs/design/09-roadmap.md decision 7)."""

import pytest

from wyrdfall.app import WyrdfallApp
from wyrdfall.domain.keybindings import DEFAULT_KEYBINDINGS, action_for, effective_bindings, rebind
from wyrdfall.persistence.store import MetaProgressionState, load_meta_progression, save_meta_progression
from wyrdfall.ui.screens.combat import CombatScreen
from wyrdfall.ui.screens.keybindings import KeybindingsScreen
from wyrdfall.ui.screens.meta_progression import MetaProgressionScreen


def test_defaults_rebinding_and_no_shared_keys():
    assert action_for(effective_bindings({}), "3") == "action_3"
    assert action_for(effective_bindings({}), "space") == "minigame"
    overrides = rebind({}, "action_1", "q")
    bindings = effective_bindings(overrides)
    assert action_for(bindings, "q") == "action_1" and action_for(bindings, "1") is None
    # taking another action's key unbinds that action rather than sharing
    overrides = rebind(overrides, "action_2", "q")
    bindings = effective_bindings(overrides)
    assert action_for(bindings, "q") == "action_2"
    assert bindings["action_1"] == "1"  # back to its default, which is free
    assert rebind({}, "nao_existe", "x") == {}
    assert set(DEFAULT_KEYBINDINGS) == set(effective_bindings({}))


def test_bindings_persist(tmp_path):
    meta = MetaProgressionState(keybindings=rebind({}, "minigame", "enter"))
    save_meta_progression(meta, tmp_path / "w.db")
    assert load_meta_progression(tmp_path / "w.db").keybindings == {"minigame": "enter"}


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr("wyrdfall.persistence.store.save_db_path", lambda: tmp_path / "wyrdfall.db")
    return WyrdfallApp()


async def test_remapping_in_the_guild_changes_which_key_fires_an_action(app):
    async with app.run_test(size=(100, 400)) as pilot:  # the Guild is tall; same viewport as its other tests
        await pilot.pause()
        await pilot.click("#meta")
        await pilot.pause()
        assert isinstance(app.screen, MetaProgressionScreen)
        await pilot.click("#tab_opcoes")
        await pilot.pause()
        await pilot.click("#keybindings")
        await pilot.pause()
        assert isinstance(app.screen, KeybindingsScreen)
        await pilot.click("#bind_action_1")
        await pilot.pause()
        await pilot.press("q")
        await pilot.pause()
        assert app.meta.keybindings["action_1"] == "q"
        assert "q" in str(app.screen.query_one("#bind_action_1").label)
        await pilot.click("#back")
        await pilot.pause()
        await pilot.click("#back")
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
        hero.base_stats.speed = 99
        await pilot.click("#enter")
        await pilot.pause()
        assert isinstance(app.screen, CombatScreen)
        await pilot.press("1")  # the old key does nothing now
        await pilot.pause()
        assert app.screen.mode == "select_ability"
        await pilot.press("q")  # the new key picks the first ability
        await pilot.pause()
        assert app.screen.mode == "select_target" or app.client.get_combat_state().current_actor_id() != "hero"
