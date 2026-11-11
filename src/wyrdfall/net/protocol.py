"""Wire messages exchanged between a host and its joiners.

Combat is turn-based, so bandwidth is a non-issue: :class:`ServerStateUpdate`
just carries the *entire* current RunState + CombatState after every change.
No delta compression, no client-side prediction -- the client is always
either fully caught up or about to be, one message behind at most.
"""

from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, Field

from wyrdfall.domain.attributes import Atributo
from wyrdfall.domain.models import EvolutionVariants
from wyrdfall.domain.combat import Action, CombatState, ParryResult
from wyrdfall.domain.loadout import PlayerLoadout
from wyrdfall.domain.dungeon import DungeonDef
from wyrdfall.domain.run import RunState
from wyrdfall.persistence.store import RunSummary

PROTOCOL_VERSION = 8


class LobbyPlayer(BaseModel):
    player_id: str
    name: str
    class_id: str = "runeguard"
    race_id: str = "human"


# -- client -> server ------------------------------------------------------


class ClientHello(BaseModel):
    resume_token: str | None = None
    run_id: str | None = None
    protocol_version: int = PROTOCOL_VERSION
    type: Literal["client_hello"] = "client_hello"
    player_name: str
    # the joiner's own Personagem + Selamentos + Guild perks -- the host
    # builds their character from this (docs/design/14 §1, 09 Fase 5a)
    loadout: PlayerLoadout = Field(default_factory=PlayerLoadout)


class ClientCommand(BaseModel):
    """A command based on the last authoritative state the player received."""

    revision: str | None = None


class ClientAllocateTalent(ClientCommand):
    type: Literal["client_allocate_talent"] = "client_allocate_talent"
    character_id: str
    node_id: str


class ClientAllocateAttribute(ClientCommand):
    type: Literal["client_allocate_attribute"] = "client_allocate_attribute"
    character_id: str
    attribute: Atributo


class ClientEnterEncounter(ClientCommand):
    type: Literal["client_enter_encounter"] = "client_enter_encounter"


class ClientSetReady(BaseModel):
    type: Literal["client_set_ready"] = "client_set_ready"
    token: str
    ready: bool


class ClientLeaveRun(BaseModel):
    type: Literal["client_leave_run"] = "client_leave_run"


class ClientAction(ClientCommand):
    type: Literal["client_action"] = "client_action"
    action: Action


class ClientAdvance(ClientCommand):
    type: Literal["client_advance"] = "client_advance"


class ClientRespondToParry(BaseModel):
    request_id: str
    type: Literal["client_respond_to_parry"] = "client_respond_to_parry"
    character_id: str
    result: ParryResult


class ClientEvolveSpecialization(ClientCommand):
    type: Literal["client_evolve_specialization"] = "client_evolve_specialization"
    character_id: str
    specialization_id: str
    variants: EvolutionVariants = Field(default_factory=EvolutionVariants)


class ClientEquipWeapon(ClientCommand):
    type: Literal["client_equip_weapon"] = "client_equip_weapon"
    character_id: str
    weapon_type_id: str


class ClientSocketRune(ClientCommand):
    type: Literal["client_socket_rune"] = "client_socket_rune"
    character_id: str
    rune_id: str
    ability_id: str | None = None


class ClientAbsorbRune(ClientCommand):
    type: Literal["client_absorb_rune"] = "client_absorb_rune"
    character_id: str
    rune_id: str


class ClientUnsocketRune(ClientCommand):
    type: Literal["client_unsocket_rune"] = "client_unsocket_rune"
    character_id: str
    rune_id: str
    ability_id: str | None = None


class ClientEquipArmor(ClientCommand):
    type: Literal["client_equip_armor"] = "client_equip_armor"
    character_id: str
    slot: str
    item_id: str


class ClientTransferEquipment(ClientCommand):
    type: Literal["client_transfer_equipment"] = "client_transfer_equipment"
    character_id: str
    recipient_id: str
    item_id: str


class ClientUnequipArmor(ClientCommand):
    type: Literal["client_unequip_armor"] = "client_unequip_armor"
    character_id: str
    slot: str


class ClientEquipAccessory(ClientCommand):
    type: Literal["client_equip_accessory"] = "client_equip_accessory"
    character_id: str
    item_id: str


class ClientUnequipAccessory(ClientCommand):
    type: Literal["client_unequip_accessory"] = "client_unequip_accessory"
    character_id: str
    item_id: str


class ClientSocketEnchantment(ClientCommand):
    type: Literal["client_socket_enchantment"] = "client_socket_enchantment"
    character_id: str
    item_id: str
    enchantment_id: str


class ClientCombineRunes(ClientCommand):
    type: Literal["client_combine_runes"] = "client_combine_runes"
    rune_id: str


class ClientRerollEnchantment(ClientCommand):
    type: Literal["client_reroll_enchantment"] = "client_reroll_enchantment"
    character_id: str
    item_id: str
    slot_index: int


class ClientResolveRest(ClientCommand):
    type: Literal["client_resolve_rest"] = "client_resolve_rest"
    choice: Literal["acampar", "meditar"]


class ClientResolveEvent(ClientCommand):
    type: Literal["client_resolve_event"] = "client_resolve_event"
    option_id: str


class ClientUseConsumable(ClientCommand):
    type: Literal["client_use_consumable"] = "client_use_consumable"
    character_id: str
    consumable_id: str


class ClientBuyConsumable(ClientCommand):
    type: Literal["client_buy_consumable"] = "client_buy_consumable"
    slot: int


class ClientRerollShop(ClientCommand):
    type: Literal["client_reroll_shop"] = "client_reroll_shop"


class ClientLeaveNode(ClientCommand):
    type: Literal["client_leave_node"] = "client_leave_node"


class ClientAcceptContract(ClientCommand):
    type: Literal["client_accept_contract"] = "client_accept_contract"
    contract_id: str


class ClientDeclineContracts(ClientCommand):
    type: Literal["client_decline_contracts"] = "client_decline_contracts"


class ClientChooseCard(ClientCommand):
    type: Literal["client_choose_card"] = "client_choose_card"
    character_id: str
    card_id: str


class ClientSkipCard(ClientCommand):
    type: Literal["client_skip_card"] = "client_skip_card"
    character_id: str


class ClientBuyCard(ClientCommand):
    type: Literal["client_buy_card"] = "client_buy_card"
    character_id: str


class ClientEquipAbility(ClientCommand):
    type: Literal["client_equip_ability"] = "client_equip_ability"
    character_id: str
    ability_id: str


class ClientUnequipAbility(ClientCommand):
    type: Literal["client_unequip_ability"] = "client_unequip_ability"
    character_id: str
    ability_id: str


class ClientSetStance(ClientCommand):
    type: Literal["client_set_stance"] = "client_set_stance"
    character_id: str
    stance: Literal["none", "offensive", "evasive", "precise"]


ClientMessage = (
    ClientHello
    | ClientLeaveRun
    | ClientSetReady
    | ClientAllocateTalent
    | ClientAllocateAttribute
    | ClientEnterEncounter
    | ClientAction
    | ClientAdvance
    | ClientRespondToParry
    | ClientEvolveSpecialization
    | ClientEquipWeapon
    | ClientSocketRune
    | ClientAbsorbRune
    | ClientUnsocketRune
    | ClientEquipArmor
    | ClientTransferEquipment
    | ClientUnequipArmor
    | ClientEquipAccessory
    | ClientUnequipAccessory
    | ClientSocketEnchantment
    | ClientRerollEnchantment
    | ClientCombineRunes
    | ClientResolveRest
    | ClientResolveEvent
    | ClientUseConsumable
    | ClientBuyConsumable
    | ClientRerollShop
    | ClientLeaveNode
    | ClientAcceptContract
    | ClientDeclineContracts
    | ClientChooseCard
    | ClientSkipCard
    | ClientBuyCard
    | ClientEquipAbility
    | ClientUnequipAbility
    | ClientSetStance
)

CLIENT_MESSAGE_TYPES: dict[str, type[BaseModel]] = {
    "client_leave_run": ClientLeaveRun,
    "client_set_ready": ClientSetReady,
    "client_hello": ClientHello,
    "client_allocate_talent": ClientAllocateTalent,
    "client_allocate_attribute": ClientAllocateAttribute,
    "client_enter_encounter": ClientEnterEncounter,
    "client_action": ClientAction,
    "client_advance": ClientAdvance,
    "client_respond_to_parry": ClientRespondToParry,
    "client_evolve_specialization": ClientEvolveSpecialization,
    "client_equip_weapon": ClientEquipWeapon,
    "client_socket_rune": ClientSocketRune,
    "client_absorb_rune": ClientAbsorbRune,
    "client_unsocket_rune": ClientUnsocketRune,
    "client_equip_armor": ClientEquipArmor,
    "client_transfer_equipment": ClientTransferEquipment,
    "client_unequip_armor": ClientUnequipArmor,
    "client_equip_accessory": ClientEquipAccessory,
    "client_unequip_accessory": ClientUnequipAccessory,
    "client_socket_enchantment": ClientSocketEnchantment,
    "client_reroll_enchantment": ClientRerollEnchantment,
    "client_combine_runes": ClientCombineRunes,
    "client_resolve_rest": ClientResolveRest,
    "client_resolve_event": ClientResolveEvent,
    "client_use_consumable": ClientUseConsumable,
    "client_buy_consumable": ClientBuyConsumable,
    "client_reroll_shop": ClientRerollShop,
    "client_leave_node": ClientLeaveNode,
    "client_accept_contract": ClientAcceptContract,
    "client_decline_contracts": ClientDeclineContracts,
    "client_choose_card": ClientChooseCard,
    "client_skip_card": ClientSkipCard,
    "client_buy_card": ClientBuyCard,
    "client_equip_ability": ClientEquipAbility,
    "client_unequip_ability": ClientUnequipAbility,
    "client_set_stance": ClientSetStance,
}


# -- server -> client --------------------------------------------------------


class ServerWelcome(BaseModel):
    resume_token: str = ""
    type: Literal["server_welcome"] = "server_welcome"
    player_id: str
    class_id: str


class ServerLobbyUpdate(BaseModel):
    type: Literal["server_lobby_update"] = "server_lobby_update"
    players: list[LobbyPlayer] = Field(default_factory=list)
    host_id: str = ""


class ServerRunStart(BaseModel):
    type: Literal["server_run_start"] = "server_run_start"


class PartyReadiness(BaseModel):
    token: str
    action: Literal["enter", "advance", "leave", "rest", "event"] | None = None
    argument: str | None = None
    label: str = "Aguardando a escolha do host"
    ready_ids: set[str] = Field(default_factory=set)


class ServerStateUpdate(BaseModel):
    revision: str | None = None
    disconnected_ids: set[str] = Field(default_factory=set)
    dungeon: DungeonDef | None = None
    type: Literal["server_state_update"] = "server_state_update"
    run: RunState
    combat_state: CombatState | None = None
    summary: RunSummary | None = None
    readiness: PartyReadiness | None = None


class ServerError(BaseModel):
    type: Literal["server_error"] = "server_error"
    message: str
    fatal: bool = False


ServerMessage = ServerWelcome | ServerLobbyUpdate | ServerRunStart | ServerStateUpdate | ServerError

SERVER_MESSAGE_TYPES: dict[str, type[BaseModel]] = {
    "server_welcome": ServerWelcome,
    "server_lobby_update": ServerLobbyUpdate,
    "server_run_start": ServerRunStart,
    "server_state_update": ServerStateUpdate,
    "server_error": ServerError,
}


class ProtocolError(Exception):
    pass


def encode(message: BaseModel) -> str:
    return message.model_dump_json()


def _decode(raw: str, registry: dict[str, type[BaseModel]]) -> BaseModel:
    from pydantic import ValidationError
    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ProtocolError("A mensagem precisa ser um objeto.")
        cls = registry.get(data.get("type"))
        if cls is None:
            raise ProtocolError("Tipo de mensagem desconhecido.")
        return cls.model_validate(data)
    except (ValueError, TypeError, ValidationError) as exc:
        raise ProtocolError("Mensagem inválida.") from exc


def decode_client_message(raw: str) -> ClientMessage:
    return _decode(raw, CLIENT_MESSAGE_TYPES)


def decode_server_message(raw: str) -> ServerMessage:
    return _decode(raw, SERVER_MESSAGE_TYPES)
