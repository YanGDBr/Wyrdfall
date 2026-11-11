import pytest

from tests.test_equipment_instances import pair, forge
from tests.test_net_integration import wait_until
from tests.ui_helpers import click_button
from wyrdfall.app import WyrdfallApp
from wyrdfall.domain.inventory import add_equipment
from wyrdfall.net.game_client import LocalGameClient
from wyrdfall.ui.screens.equipment import EquipmentScreen
from wyrdfall.ui.screens.forge import ForgeScreen


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr("wyrdfall.persistence.store.save_db_path", lambda: tmp_path / "profile.db")
    return WyrdfallApp()


async def test_engrave_reroll_and_transfer_in_small_terminal(app):
    session = pair()
    forge(session)
    piece = add_equipment(session.run, "guardian_helm", owner_id="hero")
    session.equip_armor("hero", "head", piece.id)
    app.client = LocalGameClient(session, {"hero"})
    async with app.run_test(size=(100, 30)) as pilot:
        await app.push_screen(ForgeScreen())
        await wait_until(lambda: bool(app.screen.query(f"#engrave_options_{piece.id}")))
        await click_button(pilot, f"#engrave_options_{piece.id} CollapsibleTitle")
        await pilot.pause(.1)
        button = app.screen.query_one(f"#engrave_{piece.id}__ench_power")
        button.scroll_visible(immediate=True)
        await pilot.pause(.1)
        await click_button(pilot, f"#engrave_{piece.id}__ench_power")
        await wait_until(lambda: piece.enchantments == ["ench_power"])
        await pilot.pause(.2)
        await app.workers.wait_for_complete()
        await wait_until(lambda: bool(app.screen.query(f"#reroll_{piece.id}__0")))
        app.screen.query_one(f"#reroll_{piece.id}__0").scroll_visible(immediate=True)
        await pilot.pause(.1)
        await click_button(pilot, f"#reroll_{piece.id}__0")
        await wait_until(lambda: piece.enchantments != ["ench_power"])
        enchants = list(piece.enchantments)
        assert session.run.currency_earned == 80
        await click_button(pilot, "#done")
        await app.push_screen(EquipmentScreen())
        await pilot.pause(.1)
        await click_button(pilot, "#tab_bolsa")
        await wait_until(lambda: bool(app.screen.query(f"#transfer_{piece.id}__ally")))
        app.screen.query_one(f"#transfer_{piece.id}__ally").scroll_visible(immediate=True)
        await pilot.pause(.1)
        await click_button(pilot, f"#transfer_{piece.id}__ally")
        await wait_until(lambda: piece.owner_id == "ally")
        assert piece.enchantments == enchants
        assert not session.run.party[0].equipped_armor


async def test_late_mount_and_render_after_session_closed_do_not_crash(app):
    from wyrdfall.ui.screens.dungeon import DungeonScreen
    from wyrdfall.ui.screens.combat import CombatScreen
    session = pair()
    session.start_current_encounter()
    app.client = LocalGameClient(session, {"hero"})
    async with app.run_test(size=(100, 40)) as pilot:
        screen = CombatScreen()
        await app.push_screen(screen)
        await pilot.pause(.1)
        await app.leave_multiplayer()
        await screen.render_actions()
        await app.push_screen(DungeonScreen())
        await pilot.pause(.1)
        equipment = EquipmentScreen()
        await app.push_screen(equipment)
        await equipment._render_equipment()
        await pilot.pause(.1)
