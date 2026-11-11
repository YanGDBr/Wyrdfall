"""UI-level multiplayer tests. Each test drives one real WyrdfallApp through
its Host/Join screens against a minimal real counterpart (a raw
NetworkConnection standing in for a joiner, or a raw HostServer standing in
for a host) -- exercising the actual screens without needing two full
Textual apps running concurrently (covered instead by the lower-level
end-to-end tests in test_net_integration.py).
"""

from __future__ import annotations

import asyncio

import pytest

from wyrdfall.app import WyrdfallApp
from wyrdfall.domain.content import build_ruleset
from wyrdfall.domain.models import Archetype
from wyrdfall.net import server as server_module
from wyrdfall.net.client import NetworkConnection
from wyrdfall.net.host_client import HostGameClient
from wyrdfall.net.protocol import ClientHello
from wyrdfall.net.server import HostServer
from wyrdfall.ui.screens.combat import CombatScreen
from wyrdfall.ui.screens.dungeon import DungeonScreen
from wyrdfall.ui.screens.host_join import HostSetupScreen, JoinSetupScreen
from wyrdfall.ui.screens.run_summary import RunSummaryScreen


async def wait_until(predicate, timeout: float = 5.0, interval: float = 0.02) -> None:
    async def _poll():
        while not predicate():
            await asyncio.sleep(interval)

    await asyncio.wait_for(_poll(), timeout=timeout)


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr("wyrdfall.persistence.store.save_db_path", lambda: tmp_path / "wyrdfall.db")
    return WyrdfallApp()


@pytest.mark.asyncio
async def test_host_screen_starts_a_server_and_run_with_a_connected_joiner(app):
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()
        await pilot.click("#host")
        await pilot.pause()
        assert isinstance(app.screen, HostSetupScreen)

        await pilot.click("#start_server")
        await pilot.pause()
        assert app.host_server is not None
        port = app.host_server.port

        # a bare-bones joiner connects directly, bypassing a second Textual app
        connection = NetworkConnection(f"ws://127.0.0.1:{port}")
        received: list = []
        connection.on_message(received.append)
        await connection.connect()
        await connection.send(ClientHello(player_name="Friend"))
        await wait_until(lambda: len(app.host_server.players) == 2)
        await pilot.pause()  # let the lobby-update callback repaint the screen

        await pilot.click("#start_run")
        await pilot.pause()

        assert isinstance(app.screen, DungeonScreen)
        assert isinstance(app.client, HostGameClient)
        assert {c.id for c in app.client.get_run().party} == {"host", next(iter(app.host_server.players.keys() - {"host"}))}

        await connection.close()
        await app.host_server.stop()


@pytest.mark.asyncio
async def test_join_screen_connects_and_reaches_dungeon_screen_once_host_starts(app):
    ruleset = build_ruleset()
    server = HostServer(ruleset, host_player_id="host", host_player_name="Hosty")
    await server.start(port=0, host="127.0.0.1")

    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()
        await pilot.click("#join")
        await pilot.pause()
        assert isinstance(app.screen, JoinSetupScreen)

        address_input = app.screen.query_one("#address_input")
        address_input.value = f"127.0.0.1:{server.port}"
        await pilot.click("#connect")
        await pilot.pause()

        await wait_until(lambda: len(server.players) == 2)
        await server.start_run()

        await wait_until(lambda: isinstance(app.screen, DungeonScreen))
        assert app.client is not None
        assert app.client.local_character_ids() & {c.id for c in app.client.get_run().party}

    await server.stop()


@pytest.mark.asyncio
async def test_join_screen_lets_the_player_pick_their_own_character_before_connecting(app):
    """docs/design/14 §1 / 09 Fase 5a: the joiner's Personagem (archetype +
    seals, race from their own Guild) is chosen in the lobby and reaches
    the host in ClientHello -- not the host's pick applied to everyone."""
    from wyrdfall.ui.screens.archetype_select import ArchetypeSelectScreen

    ruleset = build_ruleset()
    server = HostServer(ruleset, host_player_id="host", host_player_name="Hosty", class_id="runeguard")
    await server.start(port=0, host="127.0.0.1")

    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()
        await pilot.click("#join")
        await pilot.pause()
        await pilot.click("#pick_character")
        await pilot.pause()
        assert isinstance(app.screen, ArchetypeSelectScreen)
        await pilot.click("#class_mistico")
        await pilot.pause()
        await pilot.click("#seal_guerreiro")
        await pilot.pause()
        await pilot.click("#confirm")
        await pilot.pause()
        assert isinstance(app.screen, JoinSetupScreen)
        assert "Místico" in str(app.screen.query_one("#character-status").content)

        app.screen.query_one("#address_input").value = f"127.0.0.1:{server.port}"
        await pilot.click("#connect")
        await pilot.pause()
        await wait_until(lambda: len(server.players) == 2)
        joiner_id = next(pid for pid in server.players if pid != "host")
        assert server.loadouts[joiner_id].class_id == "mistico"
        assert server.loadouts[joiner_id].sealed_archetypes == {Archetype.GUERREIRO}

        session = await server.start_run()
        await wait_until(lambda: isinstance(app.screen, DungeonScreen))
        assert {c.class_id for c in session.run.party} == {"runeguard", "mistico"}

    await server.stop()


async def _click_first_action_button(pilot, app) -> bool:
    buttons = list(app.screen.query("#action-bar Button"))
    if not buttons:
        return False
    await pilot.click(f"#{buttons[0].id}")
    await pilot.pause()
    return True


@pytest.mark.asyncio
async def test_two_full_apps_play_a_co_op_encounter_through_continue(tmp_path, monkeypatch):
    """Regression coverage for the full host+join loop with two real
    WyrdfallApp/Textual pilots -- the scenario the project plan calls out
    as the manual multiplayer smoke test, automated here."""
    monkeypatch.setattr(server_module, "AI_TURN_DELAY_SECONDS", 0.01)
    monkeypatch.setattr("wyrdfall.persistence.store.save_db_path", lambda: tmp_path / "wyrdfall.db")

    host_app = WyrdfallApp()
    join_app = WyrdfallApp()

    async with host_app.run_test(size=(100, 40)) as host_pilot, join_app.run_test(size=(100, 40)) as join_pilot:
        await host_pilot.pause()
        await join_pilot.pause()

        await host_pilot.click("#host")
        await host_pilot.pause()
        await host_pilot.click("#start_server")
        await host_pilot.pause()
        port = host_app.host_server.port

        await join_pilot.click("#join")
        await join_pilot.pause()
        join_app.screen.query_one("#address_input").value = f"127.0.0.1:{port}"
        await join_pilot.click("#connect")
        await join_pilot.pause()

        await wait_until(lambda: len(host_app.host_server.players) == 2)
        await host_pilot.pause(0.2)
        await host_pilot.click("#start_run")
        await host_pilot.pause()

        await wait_until(lambda: isinstance(host_app.screen, DungeonScreen))
        await wait_until(lambda: isinstance(join_app.screen, DungeonScreen))

        await host_pilot.click("#party-ready", offset=(2, 1))
        await host_pilot.pause()
        assert host_app.client.get_combat_state() is None
        await join_pilot.pause()
        await join_pilot.click("#party-ready", offset=(2, 1))
        await wait_until(lambda: isinstance(host_app.screen, CombatScreen))
        await wait_until(lambda: isinstance(join_app.screen, CombatScreen))

        for _ in range(300):
            if not isinstance(host_app.screen, CombatScreen):
                break
            state = host_app.client.get_combat_state()
            if state is None:
                break
            if state.is_over:
                await host_pilot.click("#party-ready", offset=(2, 1))
                await join_pilot.pause(0.05)
                if isinstance(join_app.screen, CombatScreen) and join_app.client.get_combat_state().is_over:
                    await join_pilot.click("#party-ready", offset=(2, 1))
                continue
            actor_id = state.current_actor_id()
            if not state.combatants[actor_id].is_player:
                await host_pilot.pause(0.05)
            elif actor_id == "host":
                await _click_first_action_button(host_pilot, host_app)
            else:
                await join_pilot.pause(0.05)
                await _click_first_action_button(join_pilot, join_app)
            await host_pilot.pause()
            await join_pilot.pause()

        assert isinstance(host_app.screen, (DungeonScreen, RunSummaryScreen))
        await wait_until(lambda: isinstance(join_app.screen, (DungeonScreen, RunSummaryScreen)), timeout=5.0)

        await host_app.host_server.stop()


# Note: a two-full-Textual-app Parry test (mirroring the co-op test above)
# was attempted here and removed -- it was intermittently and sometimes
# severely flaky (occasional multi-minute hangs) in ways traced to the
# Textual test pilot's own timing under two concurrent apps, not to the
# production pause/resume mechanism itself, which is covered reliably by
# two other tests instead: test_net_integration.py::
# test_parry_pauses_ai_turns_until_the_targeted_client_responds exercises
# the exact same HostServer._drive_ai_turns/respond_to_parry bridge through
# real GameClients without the Textual UI layer, and test_ui_smoke.py::
# test_parry_prompt_appears_for_a_can_parry_hero_and_resolves_via_decline
# exercises the actual SkillChallengeScreen/CombatScreen rendering in solo
# play. Between the two, both halves of this feature are verified without
# the fragile combination of both at once.

        await host_app.host_server.stop()
