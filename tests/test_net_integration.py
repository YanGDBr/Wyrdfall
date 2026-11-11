"""End-to-end test of the multiplayer stack: a real HostServer listening on
localhost, a real websocket-connected joiner, both driven through the exact
GameClient interface the UI uses -- HostGameClient for the host's own view,
RemoteGameClient for the joiner. This is the automated substitute for the
"two local terminals" manual smoke test described in the project plan.
"""

from __future__ import annotations

import asyncio

import pytest

from wyrdfall.domain.combat import Action, ParryResult
from wyrdfall.domain.content import build_ruleset
from wyrdfall.domain.loadout import PlayerLoadout
from wyrdfall.domain.models import Archetype, DamageElement, EvolutionVariants
from wyrdfall.net.client import NetworkConnection
from wyrdfall.net.host_client import HostGameClient
from wyrdfall.net.protocol import ClientHello, ServerStateUpdate, ServerWelcome, decode_server_message, encode
from wyrdfall.net.remote_client import RemoteGameClient
from wyrdfall.net import server as server_module
from wyrdfall.net.server import HostServer


@pytest.mark.asyncio
@pytest.mark.parametrize("version", [1, 3, 4, 5, 6, 7, None])
async def test_incompatible_or_unversioned_clients_are_rejected(version):
    import json
    from wyrdfall.net.protocol import ServerError
    server = HostServer(build_ruleset(), host_player_id="host", host_player_name="Host")
    await server.start(port=0, host="127.0.0.1")
    connection = NetworkConnection(f"ws://127.0.0.1:{server.port}")
    received = []
    connection.on_message(received.append)
    try:
        await connection.connect()
        payload = {"type": "client_hello", "player_name": "Old client"}
        if version is not None:
            payload["protocol_version"] = version
        await connection._ws.send(json.dumps(payload))
        await wait_until(lambda: any(isinstance(message, ServerError) for message in received))
        assert len(server.players) == 1
    finally:
        await connection.close()
        await server.stop()


async def wait_until(predicate, timeout: float = 5.0, interval: float = 0.02) -> None:
    async def _poll():
        while not predicate():
            await asyncio.sleep(interval)

    await asyncio.wait_for(_poll(), timeout=timeout)


async def act_for(client, actor_id: str) -> None:
    ability = client.legal_abilities(actor_id)[0]
    targets = client.legal_target_ids(actor_id, ability)
    target_ids = targets[:1] if ability.requires_target else []
    await client.submit_action(Action(actor_id=actor_id, ability_id=ability.id, target_ids=target_ids))


@pytest.fixture
async def two_player_clients(monkeypatch):
    monkeypatch.setattr(server_module, "AI_TURN_DELAY_SECONDS", 0.01)
    ruleset = build_ruleset()
    server = HostServer(ruleset, host_player_id="host", host_player_name="Hosty")
    await server.start(port=0, host="127.0.0.1")

    connection = NetworkConnection(f"ws://127.0.0.1:{server.port}")
    received: list = []
    connection.on_message(received.append)
    await connection.connect()
    await connection.send(ClientHello(player_name="Joiny"))

    await wait_until(lambda: any(isinstance(m, ServerWelcome) for m in received))
    welcome = next(m for m in received if isinstance(m, ServerWelcome))

    await server.start_run()
    await wait_until(lambda: any(isinstance(m, ServerStateUpdate) for m in received))
    initial_state = next(m for m in received if isinstance(m, ServerStateUpdate))

    host_client = HostGameClient(server)
    remote_client = RemoteGameClient(connection, ruleset, welcome.player_id, initial_state)

    yield server, host_client, remote_client

    await connection.close()
    await server.stop()


@pytest.mark.asyncio
async def test_lobby_has_both_players_before_the_run_starts():
    ruleset = build_ruleset()
    server = HostServer(ruleset, host_player_id="host", host_player_name="Hosty")
    await server.start(port=0, host="127.0.0.1")
    connection = NetworkConnection(f"ws://127.0.0.1:{server.port}")
    received: list = []
    connection.on_message(received.append)
    await connection.connect()
    await connection.send(ClientHello(player_name="Joiny"))

    await wait_until(lambda: len(server.players) == 2)
    assert set(server.players.values()) == {"Hosty", "Joiny"}

    await connection.close()
    await server.stop()


@pytest.mark.asyncio
async def test_each_player_brings_their_own_archetype_race_and_seals():
    # docs/design/09-roadmap.md Fase 5a "critério de pronto": two co-op
    # players pick *different* Arquétipos Base; 14 §1: Raça + Selamentos
    # are each player's own too. The joiner's loadout rides in ClientHello.
    ruleset = build_ruleset()
    server = HostServer(ruleset, host_player_id="host", host_player_name="Hosty", class_id="mistico")
    await server.start(port=0, host="127.0.0.1")
    connection = NetworkConnection(f"ws://127.0.0.1:{server.port}")
    received: list = []
    connection.on_message(received.append)
    await connection.connect()
    await connection.send(ClientHello(
        player_name="Joiny",
        loadout=PlayerLoadout(
            class_id="runeguard", race_id="dwarf", sealed_archetypes={Archetype.MISTICO},
            sealed_elements={DamageElement.FIRE}, can_parry=True,
        ),
    ))
    await wait_until(lambda: len(server.players) == 2)
    welcome = next(m for m in received if isinstance(m, ServerWelcome))
    assert welcome.class_id == "runeguard"  # the joiner's own, not the host's
    lobby = {p.name: (p.class_id, p.race_id) for p in server.lobby_players()}
    assert lobby == {"Hosty": ("mistico", "human"), "Joiny": ("runeguard", "dwarf")}

    session = await server.start_run()
    by_name = {c.name: c for c in session.run.party}
    assert by_name["Hosty"].class_id == "mistico"
    joiner = by_name["Joiny"]
    assert joiner.class_id == "runeguard" and joiner.race_id == "dwarf" and joiner.can_parry
    assert joiner.sealed_archetypes == {Archetype.MISTICO} and joiner.sealed_elements == {DamageElement.FIRE}

    await connection.close()
    await server.stop()


@pytest.mark.asyncio
async def test_hosts_pacts_and_ascension_apply_to_the_whole_party():
    ruleset = build_ruleset()
    server = HostServer(
        ruleset, host_player_id="host", host_player_name="Hosty",
        pacts=["fio_afiado", "sangue_fino"], ascension_level=1,
    )
    await server.start(port=0, host="127.0.0.1")
    connection = NetworkConnection(f"ws://127.0.0.1:{server.port}")
    connection.on_message(lambda _m: None)
    await connection.connect()
    await connection.send(ClientHello(player_name="Joiny"))
    await wait_until(lambda: len(server.players) == 2)

    session = await server.start_run()
    assert session.run.active_pacts == ["fio_afiado", "sangue_fino"]
    assert session.run.ascension_level == 1 and session.run.wyrd_meter == 15.0
    for character in session.run.party:
        sources = {m.source for m in character.permanent_modifiers}
        assert {"pact_fio_afiado", "pact_sangue_fino"} <= sources

    await connection.close()
    await server.stop()


@pytest.mark.asyncio
async def test_hosts_companion_joins_the_host_only_and_reaches_the_joiner():
    ruleset = build_ruleset()
    server = HostServer(ruleset, host_player_id="host", host_player_name="Hosty", companion_id="lobo_cinzento")
    await server.start(port=0, host="127.0.0.1")
    connection = NetworkConnection(f"ws://127.0.0.1:{server.port}")
    received: list = []
    connection.on_message(received.append)
    await connection.connect()
    await connection.send(ClientHello(player_name="Joiny"))
    await wait_until(lambda: len(server.players) == 2)

    session = await server.start_run()
    assert [c.owner_id for c in session.run.companions] == ["host"]  # one companion, the host's
    assert {c.id for c in session.run.party} == {"host", *[pid for pid in server.players if pid != "host"]}

    await wait_until(lambda: any(isinstance(m, ServerStateUpdate) for m in received))
    latest = [m for m in received if isinstance(m, ServerStateUpdate)][-1]
    assert [c.class_id for c in latest.run.companions] == ["lobo_cinzento"]

    await connection.close()
    await server.stop()


@pytest.mark.asyncio
async def test_joiner_rebuilds_the_hosts_chosen_portal_dungeon():
    # Fase 7: the host picks a Portal de Entrada; a joiner must walk the
    # same encounter list, not the default full MVP_DUNGEON.
    from wyrdfall.domain.content import build_dungeon_for_portal

    ruleset = build_ruleset()
    server = HostServer(
        ruleset, host_player_id="host", host_player_name="Hosty",
        dungeon=build_dungeon_for_portal("portao_do_gelo"),
    )
    await server.start(port=0, host="127.0.0.1")
    connection = NetworkConnection(f"ws://127.0.0.1:{server.port}")
    received: list = []
    connection.on_message(received.append)
    await connection.connect()
    await connection.send(ClientHello(player_name="Joiny"))
    await wait_until(lambda: any(isinstance(m, ServerWelcome) for m in received))
    welcome = next(m for m in received if isinstance(m, ServerWelcome))

    await server.start_run()
    await wait_until(lambda: any(isinstance(m, ServerStateUpdate) for m in received))
    initial_state = next(m for m in received if isinstance(m, ServerStateUpdate))
    remote_client = RemoteGameClient(connection, ruleset, welcome.player_id, initial_state)

    assert remote_client.get_dungeon().id == "portao_do_gelo"
    assert remote_client.get_dungeon().encounters == HostGameClient(server).get_dungeon().encounters
    assert remote_client.current_encounter().area_id == "the_frozen_pinnacle"

    await connection.close()
    await server.stop()


@pytest.mark.asyncio
async def test_two_player_party_is_built_on_run_start(two_player_clients):
    server, host_client, remote_client = two_player_clients
    run = host_client.get_run()
    assert {c.id for c in run.party} == {"host", remote_client.player_id}
    # the joiner's cached view matches the host's authoritative one
    assert {c.id for c in remote_client.get_run().party} == {"host", remote_client.player_id}


@pytest.mark.asyncio
async def test_joiner_can_allocate_a_talent_and_host_sees_it(two_player_clients):
    server, host_client, remote_client = two_player_clients
    await remote_client.allocate_talent(remote_client.player_id, "r1")
    await wait_until(
        lambda: "r1" in next(c for c in host_client.get_run().party if c.id == remote_client.player_id).build.talent_tree.allocated
    )


@pytest.mark.asyncio
async def test_host_resolves_rest_and_joiner_follows(two_player_clients, monkeypatch):
    server, host_client, remote_client = two_player_clients
    # jump the shared run to the first Sala Especial and force it to be a Descanso
    monkeypatch.setattr("wyrdfall.domain.special_rooms.special_room_type_for", lambda run: "rest")
    encounters = host_client.get_dungeon().encounters
    rest_index = next(i for i, e in enumerate(encounters) if e.room_type == "special")
    server.session.run.encounter_index = rest_index
    for character in server.session.run.party:
        character.current_hp = 1.0
    await server._broadcast_state()
    await wait_until(lambda: remote_client.get_run().encounter_index == rest_index)

    errors = []
    remote_client.on_error(errors.append)
    await remote_client.resolve_rest("acampar")
    await wait_until(lambda: bool(errors))
    assert "host" in errors[-1]
    await host_client.resolve_rest("acampar")
    await wait_until(lambda: remote_client.get_readiness().action is not None)
    await remote_client.set_party_ready(remote_client.get_readiness().token, True)
    await wait_until(lambda: host_client.get_run().encounter_index == rest_index + 1)
    assert all(c.current_hp > 1.0 for c in host_client.get_run().party)
    await wait_until(lambda: remote_client.get_run().encounter_index == rest_index + 1)


@pytest.mark.asyncio
async def test_joiner_can_shop_but_everyone_confirms_leaving(two_player_clients, monkeypatch):
    from wyrdfall.domain.shop import CONSUMABLE_PRICES

    server, host_client, remote_client = two_player_clients
    monkeypatch.setattr("wyrdfall.domain.special_rooms.special_room_type_for", lambda run: "shop")
    encounters = host_client.get_dungeon().encounters
    shop_index = next(i for i, e in enumerate(encounters) if e.room_type == "special")
    server.session.run.encounter_index = shop_index
    server.session.run.currency_earned = 100
    await server._broadcast_state()
    await wait_until(lambda: remote_client.get_run().encounter_index == shop_index)

    # the joiner computes the same shelf as the host from the broadcast run
    assert remote_client.shop_stock() == server.session.shop_stock()
    price = CONSUMABLE_PRICES[remote_client.shop_stock()[0]]

    await remote_client.buy_consumable(0)
    await wait_until(lambda: host_client.get_run().consumables == [server.session.shop_stock()[0]])
    assert host_client.get_run().currency_earned == 100 - price
    await wait_until(lambda: remote_client.shop_sold_slots() == [0])

    errors = []
    remote_client.on_error(errors.append)
    await remote_client.leave_node()
    await wait_until(lambda: remote_client.player_id in server.get_readiness().ready_ids)
    assert host_client.get_run().encounter_index == shop_index
    assert not errors
    await host_client.leave_node()
    await wait_until(lambda: host_client.get_run().encounter_index == shop_index + 1)
    assert host_client.get_run().shop is None


async def test_delayed_purchase_is_rejected_after_shop_reroll(two_player_clients, monkeypatch):
    from wyrdfall.net.protocol import ClientBuyConsumable

    server, host, guest = two_player_clients
    monkeypatch.setattr("wyrdfall.domain.special_rooms.special_room_type_for", lambda run: "shop")
    index = next(i for i, e in enumerate(host.get_dungeon().encounters) if e.room_type == "special")
    server.session.run.encounter_index = index
    server.session.run.currency_earned = 100
    await server._broadcast_state()
    await wait_until(lambda: guest.get_run().encounter_index == index)
    delayed = ClientBuyConsumable(slot=0, revision=guest._revision)

    await host.reroll_shop()
    await wait_until(lambda: guest.get_run().shop is not None and guest.get_run().shop.rerolls == 1)
    before = server.session.run.model_copy(deep=True)
    errors = []
    guest.on_error(errors.append)
    await guest.connection.send(delayed)
    await wait_until(lambda: bool(errors))
    assert "estado da run mudou" in errors[-1]
    assert server.session.run == before

    await guest.buy_consumable(0)
    await wait_until(lambda: guest.shop_sold_slots() == [0])
    assert server.session.run.consumables == [server.session.shop_stock()[0]]


async def test_command_from_before_host_restart_is_rejected(two_player_clients):
    from wyrdfall.domain.attributes import Atributo
    from wyrdfall.net.protocol import ClientAllocateAttribute
    from wyrdfall.persistence.checkpoint import RunCheckpoint

    server, host, guest = two_player_clients
    hero = next(c for c in server.session.run.party if c.id == guest.player_id)
    hero.attribute_points_available = 2
    await server._broadcast_state()
    await wait_until(lambda: guest._revision == server._state_revision)
    delayed = ClientAllocateAttribute(revision=guest._revision, character_id=guest.player_id, attribute=Atributo.LUCK)
    snapshot = RunCheckpoint.from_session(
        server.session, mode="host", player_id="host", port=server.port,
        players=server.players, loadouts=server.loadouts, tokens=server.resume_tokens,
    )
    await server.stop()
    resumed = HostServer.from_checkpoint(snapshot, server.ruleset)
    await resumed.start(port=snapshot.port, host="127.0.0.1")
    try:
        await wait_until(lambda: not guest.is_paused and guest._revision == resumed._state_revision)
        errors = []
        guest.on_error(errors.append)
        before = resumed.session.run.model_copy(deep=True)
        await guest.connection.send(delayed)
        await wait_until(lambda: bool(errors))
        assert "estado da run mudou" in errors[-1]
        assert resumed.session.run == before
        await guest.allocate_attribute(guest.player_id, Atributo.LUCK)
        await wait_until(lambda: next(c for c in guest.get_run().party if c.id == guest.player_id).attribute_points_available == 1)
    finally:
        await guest.connection.close()
        await resumed.stop()


@pytest.mark.asyncio
async def test_joiner_chooses_a_card_from_their_own_offer_and_host_sees_it(two_player_clients):
    server, host_client, remote_client = two_player_clients
    joiner_id = remote_client.player_id
    joiner_character = next(c for c in server.session.run.party if c.id == joiner_id)
    host_character = next(c for c in server.session.run.party if c.id == "host")
    joiner_character.card_offer = ["pedra_de_amolar", "botas_leves", "manto_puido"]
    host_character.card_offer = ["anel_de_sangue"]
    await server._broadcast_state()
    await wait_until(
        lambda: next(c for c in remote_client.get_run().party if c.id == joiner_id).card_offer == ["pedra_de_amolar", "botas_leves", "manto_puido"]
    )

    await remote_client.choose_card(joiner_id, "botas_leves")
    await wait_until(lambda: next(c for c in host_client.get_run().party if c.id == joiner_id).cards == ["botas_leves"])
    # only the joiner's own offer was consumed
    assert next(c for c in host_client.get_run().party if c.id == joiner_id).card_offer == []
    assert next(c for c in host_client.get_run().party if c.id == "host").card_offer == ["anel_de_sangue"]


@pytest.mark.asyncio
async def test_joiner_can_manage_ability_slots_and_stance_and_host_sees_it(two_player_clients):
    server, host_client, remote_client = two_player_clients
    joiner_id = remote_client.player_id

    def joiner_on_host():
        return next(c for c in host_client.get_run().party if c.id == joiner_id)

    await remote_client.unequip_ability(joiner_id, "strike")
    await wait_until(lambda: "strike" not in joiner_on_host().equipped_abilities)
    await remote_client.equip_ability(joiner_id, "strike")
    await wait_until(lambda: "strike" in joiner_on_host().equipped_abilities)

    await remote_client.set_stance(joiner_id, "evasive")
    await wait_until(lambda: joiner_on_host().current_stance == "evasive")

    # a player can't set someone else's stance
    errors: list[str] = []
    remote_client.on_error(errors.append)
    await remote_client.set_stance("host", "offensive")
    await wait_until(lambda: len(errors) == 1)
    assert next(c for c in host_client.get_run().party if c.id == "host").current_stance == "none"


@pytest.mark.asyncio
async def test_host_resolves_event_and_joiner_sees_alignment(two_player_clients):
    from wyrdfall.domain.content import EVENT_DEFS
    from wyrdfall.domain.events import event_for_node

    server, host_client, remote_client = two_player_clients
    encounters = host_client.get_dungeon().encounters
    event_index = next(i for i, e in enumerate(encounters) if e.room_type == "event")
    server.session.run.encounter_index = event_index
    await server._broadcast_state()
    await wait_until(lambda: remote_client.get_run().encounter_index == event_index)

    # the joiner computes the same event locally from the broadcast run
    event = event_for_node(remote_client.get_run(), EVENT_DEFS)
    assert event.id == server.session.current_event.id
    option = event.options[-1]  # the drawn event is seed-dependent; no event's last option has a cost

    errors = []
    remote_client.on_error(errors.append)
    await remote_client.resolve_event(option.id)
    await wait_until(lambda: bool(errors))
    assert "host" in errors[-1]
    await host_client.resolve_event(option.id)
    await wait_until(lambda: remote_client.get_readiness().action is not None)
    await remote_client.set_party_ready(remote_client.get_readiness().token, True)
    await wait_until(lambda: host_client.get_run().encounter_index == event_index + 1)
    assert all(c.alignment_score == option.alignment_shift for c in host_client.get_run().party)


@pytest.mark.asyncio
async def test_joiner_can_drink_a_potion_for_their_own_character_and_host_sees_it(two_player_clients):
    server, host_client, remote_client = two_player_clients
    joiner_id = remote_client.player_id
    server.session.run.consumables.append("pocao_de_vida")
    joiner_character = next(c for c in server.session.run.party if c.id == joiner_id)
    joiner_character.current_hp = 1.0
    await server._broadcast_state()
    await wait_until(lambda: remote_client.get_run().consumables == ["pocao_de_vida"])

    await remote_client.use_consumable(joiner_id, "pocao_de_vida")
    await wait_until(lambda: host_client.get_run().consumables == [])
    assert next(c for c in host_client.get_run().party if c.id == joiner_id).current_hp > 1.0


@pytest.mark.asyncio
async def test_joiner_can_evolve_a_qualifying_specialization_and_host_sees_it(two_player_clients):
    server, host_client, remote_client = two_player_clients
    joiner_character = next(c for c in server.session.run.party if c.id == remote_client.player_id)
    joiner_character.level = 5
    joiner_character.archetype_usage = {Archetype.GUERREIRO: 100.0}
    joiner_character.elemental_usage = {DamageElement.PHYSICAL: 100.0}

    errors = []
    remote_client.on_error(errors.append)
    await remote_client.evolve_specialization(remote_client.player_id, "berserker", EvolutionVariants(race_id="elf"))
    await wait_until(lambda: bool(errors))
    assert joiner_character.specialization_id is None

    choice = EvolutionVariants(race_id="human", element=DamageElement.PHYSICAL)
    await remote_client.evolve_specialization(remote_client.player_id, "berserker", choice)
    await wait_until(
        lambda: next(c for c in host_client.get_run().party if c.id == remote_client.player_id).specialization_id
        == "berserker"
    )
    assert joiner_character.evolution_variants == choice
    # the joiner's own cached view agrees too
    await wait_until(
        lambda: next(c for c in remote_client.get_run().party if c.id == remote_client.player_id).specialization_id
        == "berserker"
    )
    assert next(c for c in remote_client.get_run().party if c.id == remote_client.player_id).evolution_variants == choice


@pytest.mark.asyncio
async def test_joiner_can_equip_a_weapon_and_host_sees_it(two_player_clients):
    server, host_client, remote_client = two_player_clients
    await remote_client.equip_weapon(remote_client.player_id, "greatsword")
    await wait_until(
        lambda: next(c for c in host_client.get_run().party if c.id == remote_client.player_id).equipped_weapon_type
        == "greatsword"
    )


@pytest.mark.asyncio
async def test_joiner_can_socket_and_unsocket_a_body_rune_and_host_sees_it(two_player_clients):
    server, host_client, remote_client = two_player_clients

    def joiner_body_runes():
        return next(c for c in host_client.get_run().party if c.id == remote_client.player_id).body_rune_slots

    server.session.run.rune_inventory.append("rune_might")  # runes are drops: the party must own one
    await remote_client.socket_rune(remote_client.player_id, "rune_might", None)
    await wait_until(lambda: "rune_might" in joiner_body_runes())

    await remote_client.unsocket_rune(remote_client.player_id, "rune_might", None)
    await wait_until(lambda: "rune_might" not in joiner_body_runes())


@pytest.mark.asyncio
async def test_joiner_can_equip_armor_and_host_sees_it(two_player_clients):
    server, host_client, remote_client = two_player_clients
    from wyrdfall.domain.inventory import add_equipment
    piece = add_equipment(server.session.run, "traveler_cap")

    await remote_client.equip_armor(remote_client.player_id, "head", piece.id)
    await wait_until(
        lambda: next(c for c in host_client.get_run().party if c.id == remote_client.player_id).equipped_armor.get("head")
        == piece.id
    )


@pytest.mark.asyncio
async def test_a_player_cannot_act_for_someone_elses_character(two_player_clients):
    server, host_client, remote_client = two_player_clients
    errors: list[str] = []
    remote_client.on_error(errors.append)
    # the joiner tries to act on the host's hero -- illegal
    await remote_client.submit_action(Action(actor_id="host", ability_id="strike", target_ids=[]))
    await wait_until(lambda: len(errors) > 0)
    assert "próprio personagem" in errors[0]


@pytest.mark.asyncio
async def test_full_co_op_encounter_resolves_and_both_sides_see_the_outcome(two_player_clients):
    server, host_client, remote_client = two_player_clients

    await host_client.start_current_encounter()
    await remote_client.start_current_encounter()
    await wait_until(lambda: remote_client.get_combat_state() is not None)

    turns = 0
    while turns < 200:
        state = host_client.get_combat_state()
        if state is None or state.is_over:
            break
        actor_id = state.current_actor_id()
        actor = state.combatants[actor_id]
        if not actor.is_player:
            # the host resolves AI turns itself; just wait for the (authoritative,
            # live) host state to move past this actor before checking again
            await wait_until(lambda aid=actor_id: host_client.get_combat_state().is_over or host_client.get_combat_state().current_actor_id() != aid, timeout=5.0)
        elif actor_id == "host":
            await act_for(host_client, actor_id)
        else:
            await act_for(remote_client, actor_id)
            # submit_action for a remote client is fire-and-forget (just a socket
            # send); wait for the host's authoritative state to actually move on
            await wait_until(lambda aid=actor_id: host_client.get_combat_state().is_over or host_client.get_combat_state().current_actor_id() != aid, timeout=5.0)
        # let the joiner's cached view catch up with whatever the host just broadcast
        await wait_until(lambda: remote_client.get_combat_state() is not None and (remote_client.get_combat_state().is_over or remote_client.get_combat_state().current_actor_id() == host_client.get_combat_state().current_actor_id()), timeout=5.0)
        turns += 1

    assert turns < 200
    assert host_client.get_combat_state().is_over

    await host_client.advance_after_combat()
    await wait_until(lambda: remote_client.get_readiness() is not None)
    await remote_client.advance_after_combat()
    await wait_until(lambda: remote_client.get_combat_state() is None or remote_client.get_last_summary() is not None)

    if host_client.get_combat_state() is None and host_client.get_last_summary() is None:
        # victory but the dungeon isn't cleared yet -- back in the dungeon phase
        assert remote_client.get_combat_state() is None
        assert host_client.get_run().encounter_index == 1
    else:
        # defeat, or the dungeon was cleared -- the run produced a summary everyone can see
        assert host_client.get_last_summary() is not None
        assert remote_client.get_last_summary() is not None
        assert host_client.get_last_summary().run_id == remote_client.get_last_summary().run_id


@pytest.mark.asyncio
async def test_parry_pauses_ai_turns_until_the_targeted_client_responds(two_player_clients):
    """A parry pause blocks the coroutine that triggered it (submit_action's
    _drive_ai_turns awaits a Future) until a *different* connection's message
    resolves it -- exactly like two separate real processes, but in this
    single-process test the triggering call must run as its own task, or
    this test coroutine would deadlock awaiting itself. See HostServer._drive_ai_turns."""
    server, host_client, remote_client = two_player_clients
    for character in server.session.run.party:
        character.can_parry = True

    await host_client.start_current_encounter()
    await remote_client.start_current_encounter()
    await wait_until(lambda: remote_client.get_combat_state() is not None)

    def pending():
        state = host_client.get_combat_state()
        return state.pending_parry if state is not None else None

    pending_task: asyncio.Task | None = None
    turns = 0
    while turns < 20 and pending() is None:
        state = host_client.get_combat_state()
        if state.is_over:
            break
        actor_id = state.current_actor_id()
        actor = state.combatants[actor_id]
        if actor.is_player:
            client = host_client if actor_id == "host" else remote_client
            task = asyncio.create_task(act_for(client, actor_id))
            await wait_until(lambda: pending() is not None or task.done(), timeout=5.0)
            if pending() is not None:
                pending_task = task
                break
            await task  # no parry this time -- propagate any exception
        else:
            await wait_until(
                lambda aid=actor_id: pending() is not None
                or host_client.get_combat_state().is_over
                or host_client.get_combat_state().current_actor_id() != aid,
                timeout=5.0,
            )
        turns += 1

    assert pending() is not None, "no melee hit against a can_parry party member within 20 turns"
    defender_id = pending().defender_id
    defender_client = host_client if defender_id == "host" else remote_client

    # the un-targeted side's cached view also shows the pause
    other_client = remote_client if defender_client is host_client else host_client
    await wait_until(lambda: other_client.get_combat_state() is not None and other_client.get_combat_state().pending_parry is not None)

    request_id = pending().request_id
    await wait_until(lambda: (
        defender_client.get_combat_state().pending_parry is not None
        and defender_client.get_combat_state().pending_parry.request_id == request_id
    ))
    await defender_client.respond_to_parry(defender_id, ParryResult.DECLINED)
    await wait_until(lambda: pending() is None)
    await wait_until(lambda: other_client.get_combat_state().pending_parry is None)

    if pending_task is not None:
        await asyncio.wait_for(pending_task, timeout=5.0)
