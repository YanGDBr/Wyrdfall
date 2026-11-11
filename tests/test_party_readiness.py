from tests.ui_helpers import click_button
import pytest

from tests.test_net_integration import two_player_clients, wait_until
from wyrdfall.domain.attributes import Atributo
from wyrdfall.engine.session import SessionError
from wyrdfall.net.protocol import ClientSetReady, decode_client_message, encode


async def ready_guest(server, guest):
    token = server.get_readiness().token
    await wait_until(lambda: guest.get_readiness() is not None and guest.get_readiness().token == token)
    await guest.set_party_ready(token, True)


async def go_to_room(server, guest, room, monkeypatch):
    if room in ("rest", "shop", "forge"):
        monkeypatch.setattr("wyrdfall.domain.special_rooms.special_room_type_for", lambda run: room)
        kind = "special"
    else:
        kind = room
    index = next(i for i, e in enumerate(server.dungeon.encounters) if e.room_type == kind)
    server.session.run.encounter_index = index
    await server._broadcast_state()
    await wait_until(lambda: guest.get_run().encounter_index == index)
    return index


def test_ready_message_round_trips():
    original = ClientSetReady(token="room-123", ready=False)
    assert decode_client_message(encode(original)) == original


@pytest.mark.parametrize("first", ["host", "guest"])
async def test_everyone_must_confirm_and_last_ready_starts_once(two_player_clients, first):
    server, host, guest = two_player_clients
    token = server.get_readiness().token
    a, b = (host, guest) if first == "host" else (guest, host)
    await a.set_party_ready(token, True)
    await wait_until(lambda: bool(server.get_readiness().ready_ids))
    assert server.session.combat_state is None
    await b.set_party_ready(token, True)
    await wait_until(lambda: server.session.combat_state is not None)
    state = server.session.combat_state
    errors = []
    guest.on_error(errors.append)
    await guest.set_party_ready(token, True)  # duplicated packet cannot start twice
    await wait_until(lambda: bool(errors))
    assert server.session.combat_state is state
    assert server.get_readiness() is None


async def test_cancel_ready_and_build_changes_prevent_start(two_player_clients):
    server, host, guest = two_player_clients
    token = server.get_readiness().token
    await host.set_party_ready(token, True)
    await host.cancel_ready()
    assert not server.get_readiness().ready_ids
    await host.set_party_ready(token, True)
    server.session.run.party[0].attribute_points_available = 1
    await host.allocate_attribute("host", Atributo.STRENGTH)
    assert "host" not in server.get_readiness().ready_ids
    await ready_guest(server, guest)
    await wait_until(lambda: guest.player_id in server.get_readiness().ready_ids)
    assert server.session.combat_state is None
    with pytest.raises(SessionError, match="prontidão"):
        await host.set_party_ready(token, True)
    await host.set_party_ready(server.get_readiness().token, True)
    await wait_until(lambda: server.session.combat_state is not None)


async def test_guest_build_change_clears_their_confirmation(two_player_clients):
    server, host, guest = two_player_clients
    await ready_guest(server, guest)
    await wait_until(lambda: bool(server.get_readiness().ready_ids))
    hero = next(c for c in server.session.run.party if c.id == guest.player_id)
    hero.attribute_points_available = 1
    await guest.allocate_attribute(hero.id, Atributo.STRENGTH)
    await wait_until(lambda: not server.get_readiness().ready_ids)
    await host.start_current_encounter()
    assert server.session.combat_state is None


@pytest.mark.parametrize("room", ["shop", "forge", "rest", "event"])
async def test_noncombat_transition_requires_everyone(two_player_clients, monkeypatch, room):
    server, host, guest = two_player_clients
    index = await go_to_room(server, guest, room, monkeypatch)
    if room == "rest":
        await host.resolve_rest("meditar")
    elif room == "event":
        option = next(o for o in server.session.current_event.options if o.currency_delta >= 0)
        await host.resolve_event(option.id)
    else:
        await host.leave_node()
    assert server.session.run.encounter_index == index
    assert server.get_readiness().ready_ids == {"host"}
    await ready_guest(server, guest)
    await wait_until(lambda: server.session.run.encounter_index == index + 1)
    assert not server.get_readiness().ready_ids


async def test_changing_proposed_choice_invalidates_old_votes(two_player_clients, monkeypatch):
    server, host, guest = two_player_clients
    await go_to_room(server, guest, "rest", monkeypatch)
    with pytest.raises(SessionError, match="escolher"):
        await host.set_party_ready(server.get_readiness().token, True)
    await host.resolve_rest("acampar")
    old_token = server.get_readiness().token
    await host.resolve_rest("meditar")
    assert server.get_readiness().token != old_token
    errors = []
    guest.on_error(errors.append)
    await guest.set_party_ready(old_token, True)
    await wait_until(lambda: bool(errors))
    assert server.get_readiness().ready_ids == {"host"}
    assert server.session.current_room_type == "rest"


@pytest.mark.parametrize("victory", [True, False])
async def test_continue_after_combat_requires_a_new_confirmation(two_player_clients, victory):
    server, host, guest = two_player_clients
    await host.start_current_encounter()
    await ready_guest(server, guest)
    await wait_until(lambda: server.session.combat_state is not None)
    state = server.session.combat_state
    state.is_over = True
    state.victory = victory
    for cid in state.enemy_ids() if victory else state.party_ids():
        state.combatants[cid].current_hp = 0
    await server._broadcast_state()
    assert not server.get_readiness().ready_ids
    await host.advance_after_combat()
    assert server.session.combat_state is state
    await ready_guest(server, guest)
    await wait_until(lambda: server.session.run.encounter_index == 1 if victory else server.last_summary is not None)
    if victory:
        assert server.get_readiness().ready_ids == set()
    else:
        assert not server.last_summary.victory
        assert server.get_readiness() is None


async def test_departure_resets_votes_without_automatically_advancing(two_player_clients):
    server, host, guest = two_player_clients
    await host.start_current_encounter()
    await guest.abandon_run()
    await guest.connection.close()
    await wait_until(lambda: len(server.session.run.party) == 1)
    assert server.session.combat_state is None
    assert server.get_readiness() is None
    await host.start_current_encounter()
    assert server.session.combat_state is not None


@pytest.mark.parametrize("role", ["host", "guest"])
async def test_hub_primary_readiness_and_opening_build_screen(two_player_clients, tmp_path, monkeypatch, role):
    from wyrdfall.app import WyrdfallApp
    from wyrdfall.ui.screens.dungeon import DungeonScreen
    from wyrdfall.ui.screens.attributes import AttributeScreen
    from textual.widgets import Button, Static
    server, host, guest = two_player_clients
    monkeypatch.setattr("wyrdfall.persistence.store.save_db_path", lambda: tmp_path / "profile.db")
    client = host if role == "host" else guest
    app = WyrdfallApp()
    async with app.run_test(size=(110, 48)) as pilot:
        app.client = client
        await app.push_screen(DungeonScreen())
        await pilot.pause()
        assert not app.screen.query_one("#enter", Button).display
        await click_button(pilot, "#party-ready")
        await wait_until(lambda: bool(server.get_readiness().ready_ids))
        await pilot.pause()
        assert "1/2" in str(app.screen.query_one("#ready-status", Static).content)
        assert server.session.combat_state is None
        await click_button(pilot, "#attributes")
        await wait_until(lambda: not server.get_readiness().ready_ids)
        await pilot.pause()
        assert isinstance(app.screen, AttributeScreen)
        # Avoid the app taking ownership of the fixture's connection.
        await app.pop_screen()
        await app.pop_screen()


@pytest.mark.parametrize("role", ["host", "guest"])
@pytest.mark.parametrize("room", ["rest", "event", "shop", "forge"])
async def test_room_ui_waits_for_guest_and_closes_after_last_vote(two_player_clients, tmp_path, monkeypatch, room, role):
    from wyrdfall.app import WyrdfallApp
    from wyrdfall.ui.screens.dungeon import DungeonScreen
    from wyrdfall.ui.screens.rest import RestScreen
    from wyrdfall.ui.screens.event import EventScreen
    from wyrdfall.ui.screens.shop import ShopScreen
    from wyrdfall.ui.screens.forge import ForgeScreen
    server, host, guest = two_player_clients
    index = await go_to_room(server, guest, room, monkeypatch)
    monkeypatch.setattr("wyrdfall.persistence.store.save_db_path", lambda: tmp_path / "profile.db")
    app = WyrdfallApp()
    screen_type = {"rest": RestScreen, "event": EventScreen, "shop": ShopScreen, "forge": ForgeScreen}[room]
    async with app.run_test(size=(130, 55)) as pilot:
        app.client = host if role == "host" else guest
        await app.push_screen(DungeonScreen())
        await pilot.pause()
        await click_button(pilot, "#enter")
        await pilot.pause()
        assert isinstance(app.screen, screen_type)
        if role == "guest":
            if room == "rest":
                await host.resolve_rest("meditar")
            elif room == "event":
                option = next(o for o in server.session.current_event.options if o.currency_delta >= 0)
                await host.resolve_event(option.id)
            else:
                await host.leave_node()
            await wait_until(lambda: guest.get_readiness().ready_ids == {"host"})
            await pilot.pause()
            assert server.session.run.encounter_index == index
            await click_button(pilot, "#party-ready")
            await wait_until(lambda: server.session.run.encounter_index == index + 1)
            await pilot.pause()
            assert isinstance(app.screen, DungeonScreen)
            await app.pop_screen()
            return
        if room == "rest":
            await click_button(pilot, "#meditar")
        elif room == "event":
            option = next(o for o in server.session.current_event.options if o.currency_delta >= 0)
            await click_button(pilot, "#option_" + option.id)
        else:
            await click_button(pilot, "#party-ready")
        await pilot.pause()
        assert isinstance(app.screen, screen_type)
        assert server.session.run.encounter_index == index
        assert server.get_readiness().ready_ids == {"host"}
        await ready_guest(server, guest)
        await wait_until(lambda: server.session.run.encounter_index == index + 1)
        await pilot.pause()
        assert isinstance(app.screen, DungeonScreen)
        await app.pop_screen()


async def test_four_humans_must_be_ready_but_companions_do_not_vote():
    from wyrdfall.domain.companions import COMPANION_DEFS
    from wyrdfall.domain.content import build_ruleset
    from wyrdfall.domain.loadout import PlayerLoadout
    from wyrdfall.net.client import NetworkConnection
    from wyrdfall.net.protocol import ClientHello
    from wyrdfall.net.server import HostServer
    server = HostServer(build_ruleset(), "host", "Host", host_loadout=PlayerLoadout(
        companion_id=next(iter(COMPANION_DEFS))))
    await server.start(port=0, host="127.0.0.1")
    connections = []
    try:
        for i in range(3):
            conn = NetworkConnection(f"ws://127.0.0.1:{server.port}")
            await conn.connect()
            await conn.send(ClientHello(player_name=f"Guest {i}"))
            connections.append(conn)
        await wait_until(lambda: len(server.players) == 4)
        await server.start_run()
        assert server.session.run.companions
        token = server.get_readiness().token
        for pid in list(server.players)[:3]:
            await server.set_ready(pid, token, True)
            assert server.session.combat_state is None
        await server.set_ready(list(server.players)[-1], token, True)
        assert server.session.combat_state is not None
    finally:
        for conn in connections:
            await conn.close()
        await server.stop()


@pytest.mark.parametrize("room", ["shop", "forge"])
async def test_host_can_leave_room_after_last_guest_disconnects(two_player_clients, tmp_path, monkeypatch, room):
    from wyrdfall.app import WyrdfallApp
    from wyrdfall.ui.screens.dungeon import DungeonScreen
    from textual.widgets import Button
    server, host, guest = two_player_clients
    index = await go_to_room(server, guest, room, monkeypatch)
    monkeypatch.setattr("wyrdfall.persistence.store.save_db_path", lambda: tmp_path / "profile.db")
    app = WyrdfallApp()
    async with app.run_test(size=(120, 50)) as pilot:
        app.client = host
        await app.push_screen(DungeonScreen())
        await pilot.pause()
        await click_button(pilot, "#enter")
        await pilot.pause()
        assert not app.screen.query_one("#leave", Button).display
        await guest.abandon_run()
        await guest.connection.close()
        await wait_until(lambda: len(server.session.run.party) == 1)
        await pilot.pause()
        assert app.screen.query_one("#leave", Button).display
        await pilot.pause(0.2)
        button = app.screen.query_one("#leave", Button)
        assert not button.disabled
        assert await click_button(pilot, "#leave")
        await pilot.pause()
        assert server.session.run.encounter_index == index + 1
        assert isinstance(app.screen, DungeonScreen)
        await app.pop_screen()


async def test_last_ready_navigates_into_and_out_of_combat(two_player_clients, tmp_path, monkeypatch):
    from wyrdfall.app import WyrdfallApp
    from wyrdfall.ui.screens.dungeon import DungeonScreen
    from wyrdfall.ui.screens.combat import CombatScreen
    server, host, guest = two_player_clients
    monkeypatch.setattr("wyrdfall.persistence.store.save_db_path", lambda: tmp_path / "profile.db")
    app = WyrdfallApp()
    async with app.run_test(size=(120, 50)) as pilot:
        app.client = guest
        await app.push_screen(DungeonScreen())
        await pilot.pause()
        await host.start_current_encounter()
        await wait_until(lambda: guest.get_readiness().ready_ids == {"host"})
        await pilot.pause()
        await click_button(pilot, "#party-ready")
        await wait_until(lambda: isinstance(app.screen, CombatScreen))
        state = server.session.combat_state
        state.is_over = state.victory = True
        for cid in state.enemy_ids():
            state.combatants[cid].current_hp = 0
        await server._broadcast_state()
        await wait_until(lambda: guest.get_readiness() is not None)
        await pilot.pause()
        assert not guest.get_readiness().ready_ids
        await click_button(pilot, "#party-ready")
        await wait_until(lambda: guest.player_id in server.get_readiness().ready_ids)
        assert server.session.combat_state is state
        await host.advance_after_combat()
        await wait_until(lambda: isinstance(app.screen, DungeonScreen))
        assert server.session.run.encounter_index == 1
        assert server.session.combat_state is None
        await app.pop_screen()
