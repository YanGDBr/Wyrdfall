from wyrdfall.domain.combat import Action
from wyrdfall.domain.run import RunState
from wyrdfall.net.protocol import (
    ClientAction,
    ClientAllocateTalent,
    ClientHello,
    ServerError,
    ServerLobbyUpdate,
    ServerStateUpdate,
    ServerWelcome,
    decode_client_message,
    decode_server_message,
    encode,
)
from wyrdfall.domain.loadout import PlayerLoadout
from wyrdfall.persistence.store import RunSummary


def test_client_hello_round_trips():
    original = ClientHello(player_name="Alice")
    decoded = decode_client_message(encode(original))
    assert isinstance(decoded, ClientHello)
    assert decoded.player_name == "Alice"
    assert decoded.loadout == PlayerLoadout()  # a bare hello still means "runeguard, human, no seals"


def test_client_hello_carries_the_players_loadout():
    from wyrdfall.domain.models import Archetype, DamageElement, Modifier, ModifierKind, Stat

    loadout = PlayerLoadout(
        class_id="mistico", race_id="elf", sealed_archetypes={Archetype.GUERREIRO},
        sealed_elements={DamageElement.ICE}, bonus_talent_points=2,
        permanent_modifiers=[Modifier(stat=Stat.MAX_HP, kind=ModifierKind.FLAT, value=5, source="permanent_x")],
    )
    decoded = decode_client_message(encode(ClientHello(player_name="Bob", loadout=loadout)))
    assert isinstance(decoded, ClientHello)
    assert decoded.loadout == loadout


def test_client_action_round_trips_a_full_action():
    original = ClientAction(
        revision="state-1",
        action=Action(actor_id="p1", ability_id="strike", target_ids=["goblin_0"], challenge_score=0.75)
    )
    decoded = decode_client_message(encode(original))
    assert isinstance(decoded, ClientAction)
    assert decoded.revision == original.revision
    assert decoded.action.actor_id == "p1"
    assert decoded.action.target_ids == ["goblin_0"]
    assert decoded.action.challenge_score == 0.75  # the minigame score rides along


def test_client_allocate_talent_round_trips():
    original = ClientAllocateTalent(character_id="p1", node_id="r1")
    decoded = decode_client_message(encode(original))
    assert isinstance(decoded, ClientAllocateTalent)
    assert decoded.node_id == "r1"


def test_server_welcome_round_trips():
    original = ServerWelcome(player_id="abc123", class_id="runeguard")
    decoded = decode_server_message(encode(original))
    assert isinstance(decoded, ServerWelcome)
    assert decoded.player_id == "abc123"


def test_server_error_round_trips():
    decoded = decode_server_message(encode(ServerError(message="nope")))
    assert isinstance(decoded, ServerError)
    assert decoded.message == "nope"


def test_server_lobby_update_round_trips_multiple_players():
    from wyrdfall.net.protocol import LobbyPlayer

    original = ServerLobbyUpdate(
        players=[LobbyPlayer(player_id="host", name="Alice"), LobbyPlayer(player_id="p2", name="Bob")],
        host_id="host",
    )
    decoded = decode_server_message(encode(original))
    assert isinstance(decoded, ServerLobbyUpdate)
    assert [p.name for p in decoded.players] == ["Alice", "Bob"]


def test_server_state_update_round_trips_summary():
    original = ServerStateUpdate(
        revision="state-1",
        run=RunState(run_id="r1", seed=1, dungeon_id="d1", party=[]),
        combat_state=None,
        summary=RunSummary(run_id="r1", class_id="runeguard", floor_reached=2, victory=True),
    )
    decoded = decode_server_message(encode(original))
    assert isinstance(decoded, ServerStateUpdate)
    assert decoded.revision == original.revision
    assert decoded.summary is not None
    assert decoded.summary.victory is True
    assert decoded.run.run_id == "r1"
