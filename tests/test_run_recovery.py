from tests.ui_helpers import click_button
import asyncio
import random

import pytest

from tests.test_net_integration import two_player_clients, wait_until
from tests.test_session import make_session
from wyrdfall.domain.combat import Action, ParryResult
from wyrdfall.domain.content import build_ruleset
from wyrdfall.engine.session import SessionError
from wyrdfall.net.client import NetworkConnection
from wyrdfall.net.protocol import ClientHello, ServerError
from wyrdfall.net.server import HostServer
from wyrdfall.persistence.checkpoint import RunCheckpoint, load_checkpoint, save_checkpoint, clear_checkpoint


def host_snapshot(server):
    return RunCheckpoint.from_session(server.session, mode="host", player_id=server.host_player_id,
        player_name=server.players[server.host_player_id], players=server.players,
        loadouts=server.loadouts, tokens=server.resume_tokens, port=server.port)


@pytest.fixture
def save_path(tmp_path, monkeypatch):
    path = tmp_path / "profile.db"
    monkeypatch.setattr("wyrdfall.persistence.store.save_db_path", lambda: path)
    return path


def test_checkpoint_roundtrip_preserves_combat_rng_and_next_action(save_path):
    session = make_session(seed=937)
    state = session.start_current_encounter()
    session.run.party[0].cards = ["rei_vidro"]
    save_checkpoint(RunCheckpoint.from_session(session, mode="solo"))
    saved = load_checkpoint()
    restored = saved.restore_session(session.ruleset)
    assert restored.combat_state == session.combat_state
    assert restored.run == session.run
    assert restored.combat_engine.rng.getstate() == session.combat_engine.rng.getstate()
    actor = state.current_actor_id()
    if state.combatants[actor].acts_automatically:
        session.resolve_ai_turn()
        restored.resolve_ai_turn()
    else:
        action = Action(actor_id=actor, ability_id="guard")
        session.submit_action(action)
        restored.submit_action(action)
    assert restored.combat_state == session.combat_state
    assert restored.run == session.run
    assert restored.combat_engine.rng.getstate() == session.combat_engine.rng.getstate()
    clear_checkpoint("another-run")
    assert load_checkpoint() is not None
    clear_checkpoint(session.run.run_id)
    assert load_checkpoint() is None


def test_invalid_checkpoint_does_not_replace_previous_save(save_path):
    session = make_session()
    save_checkpoint(RunCheckpoint.from_session(session, mode="solo"))
    saved = load_checkpoint()
    invalid = saved.model_copy(update={"rng_state": object()})
    with pytest.raises(Exception):
        save_checkpoint(invalid)
    assert load_checkpoint() == saved


async def test_accidental_drop_preserves_player_and_automatically_reconnects(two_player_clients):
    server, host, guest = two_player_clients
    gid = guest.player_id
    hero = next(c for c in server.session.run.party if c.id == gid)
    hero.current_hp = 7
    hero.cards = ["rei_vidro", "primeiro_sopro"]
    await server._broadcast_state()
    await guest.connection._ws.close()
    await wait_until(lambda: gid in server.disconnected_ids)
    assert host.is_paused
    assert not server.session.run.is_complete
    with pytest.raises(SessionError, match="pausada"):
        await server.start_current_encounter()
    await host.start_current_encounter()  # UI commands safely wait instead of crashing
    assert host.get_combat_state() is None
    await wait_until(lambda: not server.disconnected_ids and not guest.is_paused)
    assert guest.player_id == gid
    rejoined = next(c for c in guest.get_run().party if c.id == gid)
    assert rejoined.current_hp == 7
    assert rejoined.cards == ["rei_vidro", "primeiro_sopro"]
    assert not guest.get_last_summary()
    assert len(server.session.run.party) == 2


async def test_parry_is_preserved_while_offline_and_reissued(two_player_clients, monkeypatch):
    from tests.test_coop_reliability import guest_parry
    server, host, guest = two_player_clients
    pending = await guest_parry(server, host, guest, monkeypatch)
    old_id = pending.request_id
    rng = server.session.combat_engine.rng.getstate()
    hp = server.session.combat_state.combatants[guest.player_id].current_hp
    await guest.connection._ws.close()
    await wait_until(lambda: bool(server.disconnected_ids))
    assert server.session.combat_state.pending_parry.request_id != old_id
    await asyncio.sleep(.15)
    assert server.session.combat_engine.rng.getstate() == rng
    assert server.session.combat_state.combatants[guest.player_id].current_hp == hp
    assert server.last_summary is None
    await wait_until(lambda: not guest.is_paused)
    await guest.respond_to_parry(guest.player_id, ParryResult.DECLINED)
    await wait_until(lambda: server.session.combat_state.pending_parry is not pending)


async def test_host_restart_restores_full_run_and_accepts_original_guest(two_player_clients):
    server, host, guest = two_player_clients
    await host.start_current_encounter()
    await guest.start_current_encounter()
    await wait_until(lambda: guest.get_combat_state() is not None)
    saved = RunCheckpoint.model_validate_json(host_snapshot(server).model_dump_json())
    await server.stop()
    await wait_until(lambda: guest.is_paused)
    assert guest.get_last_summary() is None
    replacement = HostServer.from_checkpoint(saved, server.ruleset)
    await replacement.start(port=saved.port, host="127.0.0.1")
    try:
        assert replacement.disconnected_ids == {guest.player_id}
        assert replacement.session.combat_state == saved.combat
        await wait_until(lambda: not guest.is_paused and not replacement.disconnected_ids)
        assert guest.get_run().run_id == saved.run.run_id
        assert guest.get_combat_state() == replacement.session.combat_state
        assert replacement.session.run.party == saved.run.party
    finally:
        await guest.connection.close()
        await replacement.stop()


@pytest.mark.parametrize("case", ["invalid_token", "wrong_run", "already_connected"])
async def test_invalid_resume_credentials_cannot_take_a_character(two_player_clients, case):
    server, host, guest = two_player_clients
    connection = NetworkConnection(guest.connection.uri)
    messages = []
    connection.on_message(messages.append)
    await connection.connect()
    try:
        await connection.send(ClientHello(player_name="Intruder",
            resume_token="invalid" if case == "invalid_token" else guest.connection.resume_token,
            run_id="different" if case == "wrong_run" else server.session.run.run_id))
        await wait_until(lambda: any(isinstance(m, ServerError) for m in messages))
        assert len(server.session.run.party) == 2
        assert not server.disconnected_ids
    finally:
        await connection.close()


async def test_explicit_abandon_is_not_a_recoverable_disconnect(two_player_clients):
    server, host, guest = two_player_clients
    token = guest.connection.resume_token
    await guest.abandon_run()
    await wait_until(lambda: guest.player_id not in server.resume_tokens)
    assert token not in server.resume_tokens.values()
    assert len(server.session.run.party) == 1
    assert not server.session.run.is_complete
    assert not guest.get_last_summary().victory


async def test_solo_autosave_resume_in_battle_and_reward_once(save_path):
    from wyrdfall.app import WyrdfallApp
    from wyrdfall.ui.screens.dungeon import DungeonScreen
    from wyrdfall.ui.screens.combat import CombatScreen
    app = WyrdfallApp()
    async with app.run_test(size=(120, 50)) as pilot:
        client = app.start_new_run()
        assert load_checkpoint().mode == "solo"
        await app.push_screen(DungeonScreen())
        await client.start_current_encounter()
        await pilot.pause(.1)
        saved = load_checkpoint()
        assert saved.combat is not None
        await app.suspend_run()
        assert app.client is None
        assert load_checkpoint().run.run_id == saved.run.run_id
        await pilot.pause()
        await click_button(pilot, "#resume_run")
        await pilot.pause()
        await click_button(pilot, "#resume-confirm")
        await pilot.pause(.1)
        assert isinstance(app.screen, CombatScreen)
        assert app.client.get_run().run_id == saved.run.run_id
        assert app.client.get_combat_state() == saved.combat
        await app.abandon_run()
        assert load_checkpoint() is None
        assert app.meta.total_deaths == 1


async def test_guest_saved_credentials_resume_after_reopening(save_path, two_player_clients):
    from wyrdfall.app import WyrdfallApp
    from wyrdfall.ui.screens.dungeon import DungeonScreen
    server, host, guest = two_player_clients
    app = WyrdfallApp()
    async with app.run_test(size=(120, 50)) as pilot:
        app.client = guest
        app.net_connection = guest.connection
        app.attach_autosave()
        await app.push_screen(DungeonScreen())
        saved = load_checkpoint()
        assert saved.resume_token == guest.connection.resume_token
        await app.suspend_run()
        await wait_until(lambda: host.is_paused)
        await app.resume_saved_run()
        await wait_until(lambda: not app.client.is_paused)
        assert app.client.player_id == saved.player_id
        assert len(server.session.run.party) == 2
        assert app.client.get_run().run_id == saved.run.run_id
        await app.leave_multiplayer()


async def test_host_can_resume_saved_lobby_port_and_wait_for_guests(save_path, two_player_clients):
    from wyrdfall.app import WyrdfallApp
    server, host, guest = two_player_clients
    saved = host_snapshot(server)
    save_checkpoint(saved)
    await server.stop()
    await wait_until(lambda: guest.is_paused)
    app = WyrdfallApp()
    async with app.run_test(size=(120, 50)) as pilot:
        await app.resume_saved_run()
        assert app.host_server.port == saved.port
        await wait_until(lambda: not app.client.is_paused and not guest.is_paused)
        assert app.client.get_run().run_id == saved.run.run_id
        assert load_checkpoint().mode == "host"
        await app.suspend_run()


async def test_failed_save_does_not_close_a_running_game(save_path, monkeypatch):
    import sqlite3
    from wyrdfall.app import WyrdfallApp
    app = WyrdfallApp()
    async with app.run_test() as pilot:
        client = app.start_new_run()
        previous = load_checkpoint()
        def fail(snapshot):
            raise sqlite3.OperationalError("disk full")
        monkeypatch.setattr("wyrdfall.persistence.checkpoint.save_checkpoint", fail)
        with pytest.raises(OSError, match="autosave falhou"):
            await app.suspend_run()
        assert app.client is client
        assert not client.get_run().is_complete
        assert load_checkpoint() == previous


async def test_clicks_while_group_is_offline_do_not_crash_or_change_builds(two_player_clients):
    from wyrdfall.domain.attributes import Atributo
    server, host, guest = two_player_clients
    await guest.connection.close()
    await wait_until(lambda: host.is_paused and guest.is_paused)
    before = server.session.run.model_copy(deep=True)
    await host.allocate_attribute("host", Atributo.STRENGTH)
    await guest.allocate_attribute(guest.player_id, Atributo.STRENGTH)
    assert server.session.run == before


async def test_socket_closing_during_a_build_click_is_recoverable(two_player_clients, monkeypatch):
    from wyrdfall.domain.attributes import Atributo
    from wyrdfall.net.client import ConnectionError_
    server, host, guest = two_player_clients
    async def broken_send(message):
        raise ConnectionError_("connection lost")
    monkeypatch.setattr(guest.connection, "send", broken_send)
    before = server.session.run.model_copy(deep=True)
    await guest.allocate_attribute(guest.player_id, Atributo.STRENGTH)
    assert guest.is_paused
    assert server.session.run == before


async def test_reconnect_keeps_retrying_until_old_socket_is_released(two_player_clients):
    from wyrdfall.net.protocol import ServerStateUpdate
    server, host, guest = two_player_clients
    retry = NetworkConnection(guest.connection.uri)
    retry.resume_token = guest.connection.resume_token
    retry.run_id = server.session.run.run_id
    messages = []
    retry.on_message(messages.append)
    retry.resume_in_background()
    try:
        await wait_until(lambda: any(isinstance(m, ServerError) for m in messages))
        assert not retry._terminal
        assert len(server.connections) == 1
        await guest.connection.close()
        await wait_until(lambda: any(isinstance(m, ServerStateUpdate) for m in messages))
        assert not server.disconnected_ids
        assert len(server.session.run.party) == 2
    finally:
        await retry.close()


@pytest.mark.parametrize("portal", ["portao_da_fornalha", "portao_do_gelo", "portao_da_tempestade"])
async def test_host_can_select_portal_after_starting_lobby(save_path, portal):
    from wyrdfall.app import WyrdfallApp
    app = WyrdfallApp()
    async with app.run_test(size=(110, 45)) as pilot:
        await click_button(pilot, "#host")
        await pilot.pause()
        await click_button(pilot, "#start_server")
        await wait_until(lambda: app.host_server is not None)
        await pilot.pause()
        button = app.screen.query_one("#portal_" + portal)
        button.scroll_visible(immediate=True)
        await pilot.pause()
        await click_button(pilot, "#portal_" + portal)
        assert app.host_server.dungeon.id == portal
        app.screen.query_one("#start_run").scroll_visible(immediate=True)
        await pilot.pause()
        await click_button(pilot, "#start_run")
        assert app.client.get_dungeon().id == portal
        assert load_checkpoint().dungeon.id == portal
        await app.suspend_run()
