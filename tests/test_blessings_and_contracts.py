"""Bênçãos (docs/design/06-economia-progressao.md "Passivas de Run") and
Contratos de Run (08-itens-crafting.md "Missões")."""

import random

import pytest

from wyrdfall.domain.blessings import BLESSING_DEFS, roll_blessing
from wyrdfall.domain.combat import Action, CombatState
from wyrdfall.domain.content import CLASS_DEFS, TALENT_TREES, build_ruleset
from wyrdfall.domain.contracts import CONTRACT_DEFS, CONTRACTS_OFFERED_PER_RUN, contract_offer_for
from wyrdfall.domain.dungeon import DungeonDef, EncounterDef
from wyrdfall.domain.events import EventDef, EventOptionDef
from wyrdfall.domain.factory import create_player_character
from wyrdfall.domain.models import Stat
from wyrdfall.domain.run import RunState
from wyrdfall.engine.session import GameSession
from wyrdfall.net.protocol import ClientAcceptContract, ClientDeclineContracts, decode_client_message, encode
from tests.test_session import play_encounter_to_completion


def _session(encounters, party_size=1, seed=1) -> GameSession:
    ruleset = build_ruleset()
    class_def = CLASS_DEFS["runeguard"]
    tree = TALENT_TREES[class_def.talent_tree_id]
    party = [create_player_character(f"h{i}", f"H{i}", class_def, tree, ruleset=ruleset) for i in range(party_size)]
    dungeon = DungeonDef(id="t", name="t", encounters=encounters)
    return GameSession(RunState(run_id="r", seed=seed, dungeon_id="t", party=party), ruleset, dict(TALENT_TREES), dungeon=dungeon)


# -- Bênçãos ---------------------------------------------------------------------------


def test_blessing_pool_is_small_broad_and_the_roll_never_repeats():
    assert len(BLESSING_DEFS) >= 6
    for blessing in BLESSING_DEFS.values():
        assert blessing.name and blessing.description
        assert blessing.modifiers or blessing.triggered_effects or blessing.heal_fraction_per_node > 0
    held = list(BLESSING_DEFS)[:-1]
    assert roll_blessing(random.Random(1), BLESSING_DEFS, held) == list(BLESSING_DEFS)[-1]
    assert roll_blessing(random.Random(1), BLESSING_DEFS, list(BLESSING_DEFS)) is None


def test_a_granted_blessing_reaches_every_party_members_stats_once():
    session = _session([EncounterDef(id="e", name="e", enemy_ids=["goblin"])], party_size=2)
    before = [c.computed_stats(session.ruleset).dodge_chance for c in session.run.party]
    session._grant_blessing("passo_leve")
    session._grant_blessing("passo_leve")  # never twice
    for character, dodge in zip(session.run.party, before):
        assert character.blessings == ["passo_leve"]
        assert character.computed_stats(session.ruleset).dodge_chance == pytest.approx(dodge + 0.05)


def test_an_altar_option_grants_a_blessing_and_a_plain_one_does_not(monkeypatch):
    altar = EventDef(id="only", name="Only", text="...", options=[
        EventOptionDef(id="rezar", label="r", outcome_text="", blessing=True),
        EventOptionDef(id="seguir", label="s", outcome_text=""),
    ])
    monkeypatch.setattr("wyrdfall.engine.session.EVENT_DEFS", {"only": altar})
    session = _session([EncounterDef(id="ev", name="ev", room_type="event")])
    session.resolve_event("rezar")
    assert len(session.run.party[0].blessings) == 1
    assert session.run.party[0].blessings[0] in BLESSING_DEFS

    session = _session([EncounterDef(id="ev", name="ev", room_type="event")])
    session.resolve_event("seguir")
    assert session.run.party[0].blessings == []


def test_an_elite_victory_grants_a_blessing_and_a_normal_one_does_not():
    session = _session([
        EncounterDef(id="e1", name="n", enemy_ids=["goblin"]),
        EncounterDef(id="e2", name="e", enemy_ids=["goblin"], is_elite=True),
    ])
    play_encounter_to_completion(session)
    assert session.encounter_victory
    session.collect_victory_reward_and_advance()
    assert session.run.party[0].blessings == []
    play_encounter_to_completion(session)
    assert session.encounter_victory
    session.collect_victory_reward_and_advance()
    assert len(session.run.party[0].blessings) == 1


def test_folego_heals_a_fraction_every_time_the_run_moves_on():
    session = _session([
        EncounterDef(id="rest", name="r", room_type="rest"),
        EncounterDef(id="shop", name="s", room_type="shop"),
        EncounterDef(id="e", name="e", enemy_ids=["goblin"]),
    ])
    hero = session.run.party[0]
    session._grant_blessing("folego")
    max_hp = hero.computed_stats(session.ruleset).max_hp
    hero.current_hp = 1.0
    session.resolve_rest("meditar")  # no heal of its own
    assert hero.current_hp == pytest.approx(1.0 + 0.02 * max_hp)
    session.leave_node()
    assert hero.current_hp == pytest.approx(1.0 + 0.04 * max_hp)


# -- Contratos de Run -------------------------------------------------------------------


def test_the_offer_is_deterministic_per_seed_and_accept_decline_work():
    assert contract_offer_for(7) == contract_offer_for(7)
    assert len(contract_offer_for(7)) == CONTRACTS_OFFERED_PER_RUN
    assert all(cid in CONTRACT_DEFS for cid in contract_offer_for(7))
    seeds = {tuple(contract_offer_for(s)) for s in range(30)}
    assert len(seeds) > 1

    session = _session([EncounterDef(id="e", name="e", enemy_ids=["goblin"])])
    session.run.contract_offer = ["intocavel", "relampago"]
    assert session.accept_contract("nao_existe") is False
    assert session.accept_contract("intocavel") is True
    assert session.run.accepted_contracts == ["intocavel"] and session.run.contract_offer == ["relampago"]
    assert session.accept_contract("intocavel") is False  # no longer on offer
    session.decline_contracts()
    assert session.run.contract_offer == []


def _state(**kw) -> CombatState:
    session = _session([EncounterDef(id="e", name="e", enemy_ids=["goblin"])])
    state = session.start_current_encounter()
    for key, value in kw.items():
        setattr(state, key, value)
    return state


def test_each_contract_checks_the_fight_it_claims_to():
    assert CONTRACT_DEFS["intocavel"].check(_state(damage_taken_this_encounter=0.0))
    assert not CONTRACT_DEFS["intocavel"].check(_state(damage_taken_this_encounter=3.0))
    assert CONTRACT_DEFS["sem_cura"].check(_state(used_heal_this_encounter=False))
    assert not CONTRACT_DEFS["sem_cura"].check(_state(used_heal_this_encounter=True))
    assert CONTRACT_DEFS["relampago"].check(_state(round_number=3))
    assert not CONTRACT_DEFS["relampago"].check(_state(round_number=4))
    assert CONTRACT_DEFS["aparador"].check(_state(had_successful_parry=True))
    state = _state()
    assert CONTRACT_DEFS["firme"].check(state)
    state.combatants["h0"].current_hp = 0.0
    assert not CONTRACT_DEFS["firme"].check(state)


def test_a_completed_contract_pays_fragments_once_and_ecos_at_bank_time(tmp_path, monkeypatch):
    session = _session([
        EncounterDef(id="e1", name="a", enemy_ids=["goblin"]),
        EncounterDef(id="e2", name="b", enemy_ids=["goblin"]),
    ])
    session.run.contract_offer = ["relampago", "sem_cura"]
    session.accept_contract("relampago")
    session.accept_contract("sem_cura")
    play_encounter_to_completion(session)
    assert session.encounter_victory
    fast = session.combat_state.round_number <= 3
    before = session.run.currency_earned
    reward = session.collect_victory_reward_and_advance()
    if fast:
        assert "relampago" in session.run.completed_contracts
        assert session.run.currency_earned - before == reward
        assert reward >= CONTRACT_DEFS["relampago"].reward_fragments
        assert session.run.contract_ecos == CONTRACT_DEFS["relampago"].reward_ecos
    assert "sem_cura" not in session.run.completed_contracts  # boss_only never completes on a normal fight

    completed_before = list(session.run.completed_contracts)
    ecos_before = session.run.contract_ecos
    play_encounter_to_completion(session)
    session.collect_victory_reward_and_advance()
    assert session.run.completed_contracts == completed_before  # at most once
    assert session.run.contract_ecos == ecos_before

    # the Ecos reach the player's save through bank_run_reward
    monkeypatch.setattr("wyrdfall.persistence.store.save_db_path", lambda: tmp_path / "wyrdfall.db")
    from wyrdfall.app import WyrdfallApp
    from wyrdfall.net.game_client import LocalGameClient

    app = WyrdfallApp()
    session.run.contract_ecos = 9
    summary = session.finalize_run()
    app.client = LocalGameClient(session)
    app.client._last_summary = summary
    ecos_before = app.meta.ecos
    assert app.bank_run_reward() >= 9
    assert app.meta.ecos - ecos_before >= 9


def test_contract_messages_round_trip_and_a_new_run_carries_an_offer(tmp_path, monkeypatch):
    decoded = decode_client_message(encode(ClientAcceptContract(contract_id="firme")))
    assert isinstance(decoded, ClientAcceptContract) and decoded.contract_id == "firme"
    assert isinstance(decode_client_message(encode(ClientDeclineContracts())), ClientDeclineContracts)

    monkeypatch.setattr("wyrdfall.persistence.store.save_db_path", lambda: tmp_path / "wyrdfall.db")
    from wyrdfall.app import WyrdfallApp

    run = WyrdfallApp().start_new_run().get_run()
    assert run.contract_offer == contract_offer_for(run.seed)
