from unittest.mock import AsyncMock

import pytest

from tests.test_session import make_session, make_boss_only_session, play_encounter_to_completion
from wyrdfall.domain.attributes import Atributo
from wyrdfall.domain.combat import Action, CombatError
from wyrdfall.domain.content import build_ruleset
from wyrdfall.domain.models import Archetype
from wyrdfall.domain.specializations import SPECIALIZATION_DEFS, is_offerable
from wyrdfall.engine.session import SessionError
from wyrdfall.net.protocol import ClientAllocateAttribute
from wyrdfall.net.server import HostServer
from wyrdfall.persistence.store import MetaProgressionState, RunSummary, load_meta_progression, save_meta_progression


def test_unslotted_action_is_rejected_without_mutating_state_or_rng():
    session = make_session()
    session.run.party[0].abilities.append("reckless_smash")
    state = session.start_current_encounter()
    before = state.model_dump()
    rng_before = session.combat_engine.rng.getstate()
    with pytest.raises(CombatError):
        session.submit_action(Action(actor_id="hero", ability_id="reckless_smash", target_ids=state.enemy_ids()[:1]))
    assert state.model_dump() == before
    assert session.combat_engine.rng.getstate() == rng_before


def test_active_encounter_cannot_restart_continue_or_finalize():
    session = make_session()
    state = session.start_current_encounter()
    before = state.model_dump()
    for operation in (session.start_current_encounter, session.resolve_continue_after_combat, session.finalize_run):
        with pytest.raises(SessionError):
            operation()
        assert session.combat_state is state
        assert state.model_dump() == before
        assert not session.run.is_complete


def test_upper_bound_is_not_a_sealed_archetype_association():
    hero = make_session().run.party[0]
    hero.sealed_archetypes = {Archetype.GUARDIAO}
    assert is_offerable(SPECIALIZATION_DEFS["berserker"], hero)
    hero.sealed_archetypes = {Archetype.MISTICO}
    assert not is_offerable(SPECIALIZATION_DEFS["paladino"], hero)


@pytest.mark.asyncio
async def test_guest_cannot_allocate_another_players_attribute():
    server = HostServer(build_ruleset(), host_player_id="hero", host_player_name="Host")
    server.session = make_session()
    hero = server.session.run.party[0]
    hero.attribute_points_available = 1
    server._send_error = AsyncMock()
    server._broadcast_state = AsyncMock()
    await server._handle_client_message("guest", ClientAllocateAttribute(character_id="hero", attribute=Atributo.LUCK))
    assert hero.attribute_points_available == 1
    assert hero.attribute_points.get(Atributo.LUCK, 0) == 0
    server._send_error.assert_awaited_once()
    server._broadcast_state.assert_not_awaited()


def test_reward_receipt_survives_history_truncation_and_restart(tmp_path):
    meta = MetaProgressionState()
    for number in range(25):
        meta.record_run(RunSummary(run_id=str(number), class_id="runeguard", floor_reached=1, victory=False), 5)
    path = tmp_path / "save.db"
    save_meta_progression(meta, path)
    meta = load_meta_progression(path)
    meta.record_run(RunSummary(run_id="0", class_id="runeguard", floor_reached=1, victory=False), 5)
    assert meta.ecos == 125
    assert meta.total_deaths == 25
    assert len(meta.run_history) == 20


def test_boss_unlocks_are_accumulated_in_serialized_run():
    session = make_boss_only_session()
    play_encounter_to_completion(session)
    session.collect_victory_reward_and_advance()
    assert "dwarf" in session.run.race_unlocks_by_character["hero"]
    assert "dwarf" in type(session.run).model_validate_json(session.run.model_dump_json()).race_unlocks_by_character["hero"]


def test_duplicate_transaction_returns_the_persisted_credit(tmp_path):
    from wyrdfall.persistence.store import commit_run_progress
    summary = RunSummary(run_id="same", class_id="runeguard", floor_reached=1, victory=False)
    first = MetaProgressionState()
    second = MetaProgressionState()
    first.record_run(summary, 5)
    second.record_run(summary, 99)
    path = tmp_path / "profile.db"
    commit_run_progress(first, "same", path)
    stored = commit_run_progress(second, "same", path)
    assert stored.ecos == 5
    assert stored.processed_runs["same"] == 5
    assert load_meta_progression(path).total_deaths == 1


def test_failed_reward_write_leaves_memory_uncredited(tmp_path, monkeypatch):
    from wyrdfall.app import WyrdfallApp
    monkeypatch.setattr("wyrdfall.persistence.store.save_db_path", lambda: tmp_path / "profile.db")
    app = WyrdfallApp()
    client = app.start_new_run()
    client.get_run().encounter_index = len(client.session.dungeon.encounters)
    client._last_summary = client.session.finalize_run()
    original = app.meta
    def fail(*args):
        raise OSError("disk unavailable")
    monkeypatch.setattr("wyrdfall.app.commit_run_progress", fail)
    with pytest.raises(OSError):
        app.bank_run_reward()
    assert app.meta is original
    assert not original.processed_runs
    assert original.ecos == 0


@pytest.mark.asyncio
async def test_guild_tabs_fit_and_navigate_in_a_normal_terminal(tmp_path, monkeypatch):
    from wyrdfall.app import WyrdfallApp
    from wyrdfall.ui.widgets import Tabbed
    from wyrdfall.ui.screens.meta_progression import TABS
    monkeypatch.setattr("wyrdfall.persistence.store.save_db_path", lambda: tmp_path / "profile.db")
    app = WyrdfallApp()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.click("#meta")
        await pilot.pause()
        for key, _ in TABS:
            assert await pilot.click(f"#tab_{key}")
            await pilot.pause()
            assert app.screen.query_one(Tabbed).active == key
