import asyncio

import pytest

from tests.test_net_integration import two_player_clients, wait_until
from wyrdfall.domain.combat import Action, ParryResult


@pytest.mark.asyncio
@pytest.mark.parametrize("result", list(ParryResult))
async def test_guest_last_action_can_answer_parry_on_the_same_connection(two_player_clients, monkeypatch, result):
    server, host, guest = two_player_clients
    gid = guest.player_id
    for hero in server.session.run.party:
        hero.base_stats.speed = 20 if hero.id == gid else 1
        hero.can_parry = hero.id == gid
    monkeypatch.setattr("wyrdfall.domain.combat.CombatEngine._choose_ai_target", lambda engine, state, candidates: gid)
    await host.start_current_encounter()
    await guest.start_current_encounter()
    await wait_until(lambda: guest.get_combat_state() is not None)
    try:
        await guest.submit_action(Action(actor_id=gid, ability_id="guard"))
        await wait_until(lambda: server.session.combat_state.pending_parry is not None)
        pending = server.session.combat_state.pending_parry
        await wait_until(lambda: (
            guest.get_combat_state().pending_parry is not None
            and guest.get_combat_state().pending_parry.request_id == pending.request_id
        ))
        await guest.respond_to_parry(gid, result)
        await wait_until(lambda: server.session.combat_state.pending_parry is not pending, timeout=0.5)
    finally:
        state = server.session.combat_state
        if state is not None:
            for hero in state.combatants.values():
                hero.can_parry = False
            if state.pending_parry is not None:
                server.session.resolve_parry_response(gid, ParryResult.DECLINED)
            if server._parry_future is not None and not server._parry_future.done():
                server._parry_future.set_result(None)


async def guest_parry(server, host, guest, monkeypatch):
    gid = guest.player_id
    for hero in server.session.run.party:
        hero.base_stats.speed = 20 if hero.id == gid else 1
        hero.can_parry = hero.id == gid
    monkeypatch.setattr("wyrdfall.domain.combat.CombatEngine._choose_ai_target", lambda engine, state, candidates: gid)
    await host.start_current_encounter()
    await guest.start_current_encounter()
    await wait_until(lambda: guest.get_combat_state() is not None)
    await guest.submit_action(Action(actor_id=gid, ability_id="guard"))
    await wait_until(lambda: server.session.combat_state.pending_parry is not None)
    await wait_until(lambda: guest.get_combat_state().pending_parry is not None)
    return server.session.combat_state.pending_parry


@pytest.mark.asyncio
async def test_unanswered_parry_times_out_and_resumes(two_player_clients, monkeypatch):
    server, host, guest = two_player_clients
    monkeypatch.setattr("wyrdfall.net.server.PARRY_TIMEOUT_SECONDS", 0.05)
    await guest_parry(server, host, guest, monkeypatch)
    await wait_until(lambda: any("sem resposta" in line for line in server.session.combat_state.log))
    await wait_until(lambda: server.session.combat_state.pending_parry is None and server._ai_task.done())


@pytest.mark.asyncio
async def test_old_parry_response_cannot_resolve_a_new_request(two_player_clients, monkeypatch):
    from wyrdfall.net.protocol import ClientRespondToParry
    server, host, guest = two_player_clients
    old = await guest_parry(server, host, guest, monkeypatch)
    await guest.respond_to_parry(guest.player_id, ParryResult.DECLINED)
    await wait_until(lambda: server.session.combat_state.pending_parry is not None and server.session.combat_state.pending_parry.request_id != old.request_id)
    current = server.session.combat_state.pending_parry
    errors = []
    guest.on_error(errors.append)
    await guest.connection.send(ClientRespondToParry(character_id=guest.player_id, result=ParryResult.SUCCESS, request_id=old.request_id))
    await wait_until(lambda: bool(errors))
    assert server.session.combat_state.pending_parry is current


@pytest.mark.asyncio
async def test_guest_disconnect_during_parry_pauses_without_losing_progress(two_player_clients, monkeypatch):
    server, host, guest = two_player_clients
    await guest_parry(server, host, guest, monkeypatch)
    await guest.connection.close()
    await wait_until(lambda: host.is_paused)
    assert host.get_last_summary() is None
    assert host.get_combat_state().pending_parry is not None
    assert len(server.session.run.party) == 2


@pytest.mark.asyncio
async def test_stop_releases_a_pending_parry_task(two_player_clients, monkeypatch):
    server, host, guest = two_player_clients
    await guest_parry(server, host, guest, monkeypatch)
    await asyncio.wait_for(server.stop(), timeout=2)
    assert server._ai_task is None
    assert server._parry_future is None


@pytest.mark.asyncio
async def test_repeated_ai_requests_share_one_driver(two_player_clients, monkeypatch):
    server, host, guest = two_player_clients
    pending = await guest_parry(server, host, guest, monkeypatch)
    driver = server._ai_task
    await asyncio.gather(*(server.resolve_ai_if_needed() for _ in range(20)))
    assert server._ai_task is driver
    assert server.session.combat_state.pending_parry is pending


@pytest.mark.asyncio
async def test_invalid_messages_do_not_kill_the_receive_loop(two_player_clients):
    from wyrdfall.domain.attributes import Atributo
    server, host, guest = two_player_clients
    errors = []
    guest.on_error(errors.append)
    for raw in ("{broken", "[]", '{"type":"client_allocate_attribute"}'):
        await guest.connection._ws.send(raw)
    await wait_until(lambda: len(errors) == 3)
    hero = next(c for c in server.session.run.party if c.id == guest.player_id)
    hero.attribute_points_available = 1
    await guest.allocate_attribute(guest.player_id, Atributo.LUCK)
    await wait_until(lambda: hero.attribute_points_available == 0)


@pytest.mark.asyncio
async def test_late_join_is_rejected_and_active_run_cannot_restart(two_player_clients):
    from wyrdfall.net.client import NetworkConnection
    from wyrdfall.net.protocol import ClientHello, ServerError
    from wyrdfall.engine.session import SessionError
    server, host, guest = two_player_clients
    run_id = host.get_run().run_id
    with pytest.raises(SessionError):
        await server.start_run()
    connection = NetworkConnection(f"ws://127.0.0.1:{server.port}")
    messages = []
    connection.on_message(messages.append)
    try:
        await connection.connect()
        await connection.send(ClientHello(player_name="Late"))
        await wait_until(lambda: any(isinstance(m, ServerError) for m in messages))
        assert len(server.session.run.party) == 2
        assert host.get_run().run_id == run_id
    finally:
        await connection.close()


@pytest.mark.asyncio
async def test_each_loadout_brings_its_gear_runes_and_companion():
    from wyrdfall.net.server import HostServer
    from wyrdfall.domain.content import build_ruleset
    from wyrdfall.domain.loadout import PlayerLoadout
    server = HostServer(build_ruleset(), "host", "Host", starting_gear=["traveler_cap"])
    server.players["guest"] = "Guest"
    server.loadouts["guest"] = PlayerLoadout(starting_gear=["traveler_cap"], starting_runes=["rune_might"], companion_id="lobo_cinzento")
    session = await server.start_run()
    pieces = [p for p in session.run.equipment_instances.values() if p.definition_id == "traveler_cap"]
    assert len(pieces) == 2 and pieces[0].id != pieces[1].id
    assert {p.owner_id for p in pieces} == {"host", "guest"}
    assert session.run.rune_inventory == ["rune_might"]
    assert [c.owner_id for c in session.run.companions] == ["guest"]
    assert session.equip_armor("host", "head", "traveler_cap")
    assert session.equip_armor("guest", "head", "traveler_cap")
    session.unequip_armor("guest", "head")
    session.run.inventory.remove(next(p.id for p in pieces if p.owner_id == "guest"))
    assert not session.equip_armor("guest", "head", "traveler_cap")


@pytest.mark.asyncio
@pytest.mark.parametrize("finish", ["decline", "timeout", "disconnect"])
async def test_guest_parry_modal_survives_state_broadcasts(two_player_clients, monkeypatch, tmp_path, finish):
    from wyrdfall.app import WyrdfallApp
    from wyrdfall.ui.screens.dungeon import DungeonScreen
    from wyrdfall.ui.screens.skill_challenge import SkillChallengeScreen
    server, host, guest = two_player_clients
    monkeypatch.setattr("wyrdfall.persistence.store.save_db_path", lambda: tmp_path / "guest.db")
    monkeypatch.setattr(SkillChallengeScreen, "_tick", lambda self: None)
    if finish == "timeout":
        monkeypatch.setattr("wyrdfall.net.server.PARRY_TIMEOUT_SECONDS", 2.0)
    app = WyrdfallApp()
    async with app.run_test(size=(100, 40)) as pilot:
        app.client = guest
        app.net_connection = guest.connection
        await app.push_screen(DungeonScreen())
        pending = await guest_parry(server, host, guest, monkeypatch)
        await wait_until(lambda: isinstance(app.screen, SkillChallengeScreen))
        modal = app.screen
        for _ in range(3):
            await server._broadcast_state()
            await pilot.pause()
        assert app.screen is modal
        server.session.combat_state.combatants[guest.player_id].can_parry = False
        if finish == "decline":
            await pilot.click("#decline")
        elif finish == "disconnect":
            await server.stop()
        if finish != "disconnect":
            await wait_until(lambda: server.session.combat_state.pending_parry is not pending)
        else:
            await wait_until(lambda: guest.is_paused)
            assert guest.get_last_summary() is None
        await wait_until(lambda: not isinstance(app.screen, SkillChallengeScreen))
        await pilot.pause()
        assert not isinstance(app.screen, SkillChallengeScreen)
        await app.leave_multiplayer()


@pytest.mark.asyncio
async def test_join_screen_displays_rejection_and_allows_retry(two_player_clients, tmp_path, monkeypatch):
    from wyrdfall.app import WyrdfallApp
    from textual.widgets import Button, Static
    server, host, guest = two_player_clients
    monkeypatch.setattr("wyrdfall.persistence.store.save_db_path", lambda: tmp_path / "profile.db")
    app = WyrdfallApp()
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.click("#join")
        await pilot.pause()
        app.screen.query_one("#address_input").value = f"127.0.0.1:{server.port}"
        await pilot.click("#connect")
        await wait_until(lambda: not app.screen.query_one("#connect", Button).disabled)
        await pilot.pause()
        assert "run já começou" in str(app.screen.query_one("#join-status", Static).content)
