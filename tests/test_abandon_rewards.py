import pytest

from tests.test_session import make_session
from tests.test_net_integration import two_player_clients
from wyrdfall.app import WyrdfallApp
from wyrdfall.domain.items import Rarity
from wyrdfall.persistence.store import load_meta_progression


@pytest.mark.parametrize("in_combat", [False, True])
def test_abandon_is_an_idempotent_defeat_without_room_rewards(in_combat):
    session = make_session()
    if in_combat:
        session.start_current_encounter()
    session.run.currency_earned = 20
    session.run.bosses_defeated = 1
    summary = session.abandon_run()
    assert not summary.victory
    assert summary.floor_reached == 0
    assert session.run.is_complete
    assert session.run_is_over
    assert not session.run_was_victorious
    assert session.combat_state is None
    assert session.run.currency_earned == 20
    assert session.run.bosses_defeated == 1
    assert session.abandon_run() is summary


@pytest.mark.asyncio
async def test_abandon_credits_ecos_contracts_and_materials_once(tmp_path, monkeypatch):
    path = tmp_path / "profile.db"
    monkeypatch.setattr("wyrdfall.persistence.store.save_db_path", lambda: path)
    app = WyrdfallApp()
    client = app.start_new_run()
    run = client.get_run()
    run.encounter_index = 2
    run.currency_earned = 20
    run.bosses_defeated = 1
    run.contract_ecos = 4
    run.materials = {Rarity.COMUM: 2}
    await client.abandon_run()
    assert app.bank_run_reward() == 23  # 2*3 + 1*10 + round(20*.15) + 4
    await client.abandon_run()
    assert app.bank_run_reward() == 23
    saved = load_meta_progression(path)
    assert saved.ecos == 23
    assert saved.total_deaths == 1
    assert saved.total_victories == 0
    assert not saved.ascension_unlocked
    assert saved.materials == {Rarity.COMUM: 2}
    assert len(saved.run_history) == 1
    assert not saved.run_history[0].victory


@pytest.mark.asyncio
async def test_host_abandon_broadcasts_defeat_and_guest_withdrawal_is_personal(two_player_clients):
    server, host, guest = two_player_clients
    from tests.test_net_integration import wait_until
    server.session.run.encounter_index = 2
    server.session.run.currency_earned = 20
    await server._broadcast_state()
    await wait_until(lambda: guest.get_run().encounter_index == 2)
    await guest.abandon_run()
    assert guest.get_last_summary().victory is False
    assert guest.get_run().is_complete
    assert not server.session.run.is_complete
    await host.abandon_run()
    await wait_until(lambda: guest.get_last_summary().run_id == server.last_summary.run_id)
    assert not host.get_last_summary().victory
    assert server.session.run.is_complete
    assert server.session.run.victory is False


@pytest.mark.asyncio
async def test_host_abandon_shows_guest_defeat_and_credits_their_profile(two_player_clients, tmp_path, monkeypatch):
    from tests.test_net_integration import wait_until
    from wyrdfall.ui.screens.dungeon import DungeonScreen
    from wyrdfall.ui.screens.run_summary import RunSummaryScreen
    server, host, guest = two_player_clients
    monkeypatch.setattr("wyrdfall.persistence.store.save_db_path", lambda: tmp_path / "guest.db")
    app = WyrdfallApp()
    async with app.run_test(size=(100, 40)) as pilot:
        app.client = guest
        app.net_connection = guest.connection
        await app.push_screen(DungeonScreen())
        server.session.run.encounter_index = 2
        server.session.run.currency_earned = 20
        await server._broadcast_state()
        await wait_until(lambda: guest.get_run().encounter_index == 2)
        await host.abandon_run()
        await wait_until(lambda: isinstance(app.screen, RunSummaryScreen))
        await pilot.pause()
        assert app.meta.ecos == 9
        assert app.meta.total_deaths == 1
        assert not app.meta.run_history[-1].victory
        await pilot.click("#return")
        await pilot.pause()
        assert app.client is None
        assert app.meta.total_deaths == 1


@pytest.mark.asyncio
async def test_departing_guest_does_not_leave_an_uncontrolled_turn(two_player_clients):
    from tests.test_net_integration import wait_until
    server, host, guest = two_player_clients
    await guest.abandon_run()
    await guest.connection.close()
    await wait_until(lambda: len(server.session.run.party) == 1)
    assert server.session.run.party[0].id == "host"
    assert not server.session.run.is_complete
    await host.start_current_encounter()
    assert host.get_combat_state().party_ids() == ["host"]
