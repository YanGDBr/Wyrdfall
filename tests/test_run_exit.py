import pytest
from tests.test_net_integration import wait_until
from tests.ui_helpers import click_button

from wyrdfall.app import WyrdfallApp
from wyrdfall.ui.screens.dungeon import DungeonScreen
from wyrdfall.ui.screens.main_menu import MainMenuScreen


@pytest.mark.asyncio
async def test_abandon_returns_to_menu_and_allows_another_run(tmp_path, monkeypatch):
    monkeypatch.setattr("wyrdfall.persistence.store.save_db_path", lambda: tmp_path / "profile.db")
    app = WyrdfallApp()
    async with app.run_test(size=(100, 40)) as pilot:
        for _ in range(2):
            for selector in ("#new_run", "#class_runeguard", "#confirm", "#portal_portao_do_tumulo"):
                await pilot.click(selector)
                await pilot.pause()
            assert isinstance(app.screen, DungeonScreen)
            previous_client = app.client
            if _ == 0:
                previous_client.get_run().encounter_index = 2
                previous_client.get_run().currency_earned = 20
            await click_button(pilot, "#abandon")
            await pilot.pause()
            await wait_until(lambda: isinstance(app.screen, MainMenuScreen))
            assert isinstance(app.screen, MainMenuScreen)
            assert app.client is None
            assert not previous_client._listeners
            assert app.meta.total_deaths == _ + 1
            assert app.meta.run_history[-1].victory is False
            assert app.meta.ecos == 9


@pytest.mark.asyncio
@pytest.mark.parametrize("victory", [False, True])
async def test_return_from_run_summary_cleans_up_the_combat_screens(tmp_path, monkeypatch, victory):
    from wyrdfall.ui.screens.combat import CombatScreen
    from wyrdfall.ui.screens.run_summary import RunSummaryScreen
    monkeypatch.setattr("wyrdfall.persistence.store.save_db_path", lambda: tmp_path / "profile.db")
    app = WyrdfallApp()
    async with app.run_test(size=(100, 40)) as pilot:
        client = app.start_new_run()
        if victory:
            client.get_run().encounter_index = len(client.get_dungeon().encounters) - 1
        await app.push_screen(DungeonScreen())
        await client.start_current_encounter()
        await pilot.pause()
        assert isinstance(app.screen, CombatScreen)
        state = client.get_combat_state()
        state.is_over = True
        state.victory = victory
        for cid in state.enemy_ids() if victory else state.party_ids():
            state.combatants[cid].current_hp = 0
        client._notify()
        await pilot.pause()
        await pilot.click("#combat_continue")
        await pilot.pause()
        assert isinstance(app.screen, RunSummaryScreen)
        credited = app.meta.ecos
        await pilot.click("#return")
        await pilot.pause()
        assert isinstance(app.screen, MainMenuScreen)
        assert app.client is None
        assert not client._listeners
        assert app.meta.ecos == credited


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["host", "guest"])
async def test_abandon_disconnects_multiplayer_without_crashing(tmp_path, monkeypatch, role):
    from tests.test_net_integration import wait_until
    from wyrdfall.domain.content import build_ruleset
    from wyrdfall.net.server import HostServer
    from wyrdfall.net.client import NetworkConnection
    from wyrdfall.net.host_client import HostGameClient
    from wyrdfall.net.remote_client import RemoteGameClient
    from wyrdfall.net.protocol import ClientHello, ServerWelcome, ServerStateUpdate
    monkeypatch.setattr("wyrdfall.persistence.store.save_db_path", lambda: tmp_path / "profile.db")
    app = WyrdfallApp()
    server = HostServer(build_ruleset(), host_player_id="host", host_player_name="Host")
    await server.start(port=0, host="127.0.0.1")
    try:
        async with app.run_test(size=(100, 40)) as pilot:
            if role == "guest":
                connection = NetworkConnection(f"ws://127.0.0.1:{server.port}")
                received = []
                connection.on_message(received.append)
                await connection.connect()
                app.net_connection = connection
                await connection.send(ClientHello(player_name="Guest"))
                await wait_until(lambda: any(isinstance(m, ServerWelcome) for m in received))
                welcome = next(m for m in received if isinstance(m, ServerWelcome))
                await server.start_run()
                await wait_until(lambda: any(isinstance(m, ServerStateUpdate) for m in received))
                initial = next(m for m in received if isinstance(m, ServerStateUpdate))
                app.client = RemoteGameClient(connection, app.ruleset, welcome.player_id, initial)
            else:
                await server.start_run()
                app.host_server = server
                app.client = HostGameClient(server)
            client = app.client
            await app.push_screen(DungeonScreen())
            await pilot.pause()
            await click_button(pilot, "#abandon")
            await pilot.pause()
            await wait_until(lambda: isinstance(app.screen, MainMenuScreen))
            assert isinstance(app.screen, MainMenuScreen)
            assert app.client is None
            assert app.host_server is None
            assert app.net_connection is None
            assert not client._listeners
    finally:
        await server.stop()
