"""GameClient for a joiner: dispatches actions over the network and renders
whatever the host last broadcast. Never touches GameSession directly."""

from __future__ import annotations

from typing import Callable
from websockets.exceptions import ConnectionClosed

from wyrdfall.domain.attributes import Atributo
from wyrdfall.domain.models import EvolutionVariants
from wyrdfall.domain.character import Ruleset
from wyrdfall.domain.combat import Action, CombatState, ParryResult
from wyrdfall.domain.content import MVP_DUNGEON, PORTAL_DEFS, build_dungeon_for_portal
from wyrdfall.domain.dungeon import DungeonDef
from wyrdfall.domain.run import RunState
from wyrdfall.domain.slots import Stance
from wyrdfall.engine.session import RestChoice, SessionError
from wyrdfall.net.client import NetworkConnection, ConnectionError_
from wyrdfall.net.game_client import GameClient
from wyrdfall.net.protocol import (
    ClientAction,
    ClientAdvance,
    ClientAllocateAttribute,
    ClientAllocateTalent,
    ClientBuyCard,
    ClientBuyConsumable,
    ClientChooseCard,
    ClientCommand,
    ClientEnterEncounter,
    ClientEquipAbility,
    ClientEquipAccessory,
    ClientEquipArmor,
    ClientTransferEquipment,
    ClientEquipWeapon,
    ClientEvolveSpecialization,
    ClientLeaveNode,
    ClientAcceptContract,
    ClientDeclineContracts,
    ClientCombineRunes,
    ClientRerollEnchantment,
    ClientRerollShop,
    ClientResolveEvent,
    ClientResolveRest,
    ClientRespondToParry,
    ClientSetReady,
    ClientLeaveRun,
    ClientSetStance,
    ClientSkipCard,
    ClientSocketEnchantment,
    ClientAbsorbRune,
    ClientSocketRune,
    ClientUnequipAbility,
    ClientUnequipAccessory,
    ClientUnequipArmor,
    ClientUnsocketRune,
    ClientUseConsumable,
    ServerError,
    ServerStateUpdate,
)
from wyrdfall.persistence.store import RunSummary


class RemoteGameClient(GameClient):
    @property
    def can_decide_for_party(self) -> bool:
        return False

    def __init__(
        self,
        connection: NetworkConnection,
        ruleset: Ruleset,
        player_id: str,
        initial_state: ServerStateUpdate,
        dungeon: DungeonDef | None = None,
    ):
        super().__init__()
        self.connection = connection
        self.ruleset = ruleset
        self.player_id = player_id
        if dungeon is None:
            # The host picked a Portal de Entrada before starting; its id
            # travels as RunState.dungeon_id, so a joiner rebuilds the same
            # DungeonDef locally rather than assuming the full MVP_DUNGEON.
            dungeon_id = initial_state.run.dungeon_id
            dungeon = build_dungeon_for_portal(dungeon_id) if dungeon_id in PORTAL_DEFS else MVP_DUNGEON
        self._dungeon = initial_state.dungeon or dungeon
        self._run: RunState = initial_state.run
        self._combat_state: CombatState | None = initial_state.combat_state
        self._last_summary: RunSummary | None = initial_state.summary
        self._readiness = initial_state.readiness
        self._revision = initial_state.revision
        self._disconnected_ids = initial_state.disconnected_ids
        self._online = connection.connected
        self._withdrawing = False
        self._error_listeners: list[Callable[[str], None]] = []
        connection.on_message(self._handle_message)
        connection.on_disconnect(self._handle_disconnect)

    def close(self) -> None:
        self.connection.off_message(self._handle_message)
        self.connection.off_disconnect(self._handle_disconnect)

    async def _send(self, message) -> None:
        if self.is_paused and not isinstance(message, ClientLeaveRun):
            self._notify()
            return  # no replay: the player reviews the authoritative state on return
        if isinstance(message, ClientCommand):
            message.revision = self._revision
        try:
            await self.connection.send(message)
        except (ConnectionClosed, ConnectionError_, OSError):
            self._online = False
            self._notify()

    def _handle_disconnect(self) -> None:
        self._online = False
        self._notify()

    @property
    def is_paused(self) -> bool:
        return self._last_summary is None and (not self._online or bool(self._disconnected_ids))

    @property
    def connection_status(self) -> str:
        if not self.is_paused:
            return ""
        if not self._online:
            if self.connection.last_error:
                return self.connection.last_error + " Salve e retome pelo menu para ajustar o endereço."
            return f"Conexão interrompida — reconectando a {self.connection.uri}. Progresso preservado."
        names = [c.name for c in self._run.party if c.id in self._disconnected_ids]
        return "Run pausada — aguardando reconexão: " + ", ".join(names)

    def on_error(self, callback: Callable[[str], None]) -> None:
        self._error_listeners.append(callback)

    def _handle_message(self, message) -> None:
        if isinstance(message, ServerStateUpdate):
            if self._withdrawing:
                return
            self._online = True
            self._disconnected_ids = message.disconnected_ids
            if message.dungeon is not None:
                self._dungeon = message.dungeon
            self._run = message.run
            self._combat_state = message.combat_state
            self._last_summary = message.summary
            self._readiness = message.readiness
            self._revision = message.revision
            self._notify()
        elif isinstance(message, ServerError):
            for callback in list(self._error_listeners):
                callback(message.message)

    # -- state reads ---------------------------------------------------------

    def get_readiness(self):
        return self._readiness

    async def set_party_ready(self, token: str, ready: bool) -> None:
        await self._send(ClientSetReady(token=token, ready=ready))

    def get_run(self) -> RunState:
        return self._run

    def get_combat_state(self) -> CombatState | None:
        return self._combat_state

    def get_dungeon(self) -> DungeonDef:
        return self._dungeon

    def local_character_ids(self) -> set[str]:
        return {self.player_id}

    def get_last_summary(self) -> RunSummary | None:
        return self._last_summary

    # -- actions: all fire-and-forget, the resulting state arrives async -----

    async def allocate_talent(self, character_id: str, node_id: str) -> None:
        await self._send(ClientAllocateTalent(character_id=character_id, node_id=node_id))

    async def allocate_attribute(self, character_id: str, attribute: Atributo) -> None:
        await self._send(ClientAllocateAttribute(character_id=character_id, attribute=attribute))

    async def evolve_specialization(
        self, character_id: str, specialization_id: str, variants: EvolutionVariants | None = None,
    ) -> None:
        await self._send(
            ClientEvolveSpecialization(character_id=character_id, specialization_id=specialization_id,
                                       variants=variants or EvolutionVariants())
        )

    async def equip_weapon(self, character_id: str, weapon_type_id: str) -> None:
        await self._send(ClientEquipWeapon(character_id=character_id, weapon_type_id=weapon_type_id))

    async def socket_rune(self, character_id: str, rune_id: str, ability_id: str | None) -> None:
        await self._send(
            ClientSocketRune(character_id=character_id, rune_id=rune_id, ability_id=ability_id)
        )

    async def unsocket_rune(self, character_id: str, rune_id: str, ability_id: str | None) -> None:
        await self._send(
            ClientUnsocketRune(character_id=character_id, rune_id=rune_id, ability_id=ability_id)
        )

    async def absorb_rune(self, character_id: str, rune_id: str) -> None:
        await self._send(ClientAbsorbRune(character_id=character_id, rune_id=rune_id))

    async def equip_armor(self, character_id: str, slot: str, item_id: str) -> None:
        await self._send(ClientEquipArmor(character_id=character_id, slot=slot, item_id=item_id))

    async def transfer_equipment(self, character_id: str, recipient_id: str, item_id: str) -> None:
        self._require_control(character_id)
        await self._send(ClientTransferEquipment(character_id=character_id, recipient_id=recipient_id, item_id=item_id))

    async def unequip_armor(self, character_id: str, slot: str) -> None:
        await self._send(ClientUnequipArmor(character_id=character_id, slot=slot))

    async def equip_accessory(self, character_id: str, item_id: str) -> None:
        await self._send(ClientEquipAccessory(character_id=character_id, item_id=item_id))

    async def unequip_accessory(self, character_id: str, item_id: str) -> None:
        await self._send(ClientUnequipAccessory(character_id=character_id, item_id=item_id))

    async def socket_enchantment(self, character_id: str, item_id: str, enchantment_id: str) -> None:
        await self._send(
            ClientSocketEnchantment(character_id=character_id, item_id=item_id, enchantment_id=enchantment_id)
        )

    async def reroll_enchantment(self, character_id: str, item_id: str, slot_index: int) -> None:
        await self._send(
            ClientRerollEnchantment(character_id=character_id, item_id=item_id, slot_index=slot_index)
        )

    async def combine_runes(self, rune_id: str) -> None:
        await self._send(ClientCombineRunes(rune_id=rune_id))

    async def start_current_encounter(self) -> None:
        vote = self.get_readiness()
        if vote is None or vote.action != "enter":
            raise SessionError("Não há esta ação aguardando prontidão.")
        await self.set_party_ready(vote.token, True)

    async def resolve_rest(self, choice: RestChoice) -> None:
        await self._send(ClientResolveRest(choice=choice))

    async def resolve_event(self, option_id: str) -> None:
        await self._send(ClientResolveEvent(option_id=option_id))

    async def use_consumable(self, character_id: str, consumable_id: str) -> None:
        await self._send(ClientUseConsumable(character_id=character_id, consumable_id=consumable_id))

    async def buy_consumable(self, slot: int) -> None:
        await self._send(ClientBuyConsumable(slot=slot))

    async def reroll_shop(self) -> None:
        await self._send(ClientRerollShop())

    async def leave_node(self) -> None:
        vote = self.get_readiness()
        if vote is None or vote.action != "leave":
            raise SessionError("Não há esta ação aguardando prontidão.")
        await self.set_party_ready(vote.token, True)

    async def accept_contract(self, contract_id: str) -> None:
        await self._send(ClientAcceptContract(contract_id=contract_id))

    async def decline_contracts(self) -> None:
        await self._send(ClientDeclineContracts())

    async def choose_card(self, character_id: str, card_id: str) -> None:
        await self._send(ClientChooseCard(character_id=character_id, card_id=card_id))

    async def skip_card(self, character_id: str) -> None:
        await self._send(ClientSkipCard(character_id=character_id))

    async def buy_card(self, character_id: str) -> None:
        await self._send(ClientBuyCard(character_id=character_id))

    async def equip_ability(self, character_id: str, ability_id: str) -> None:
        await self._send(ClientEquipAbility(character_id=character_id, ability_id=ability_id))

    async def unequip_ability(self, character_id: str, ability_id: str) -> None:
        await self._send(ClientUnequipAbility(character_id=character_id, ability_id=ability_id))

    async def set_stance(self, character_id: str, stance: Stance) -> None:
        await self._send(ClientSetStance(character_id=character_id, stance=stance))

    async def submit_action(self, action: Action) -> None:
        await self._send(ClientAction(action=action))

    async def respond_to_parry(self, character_id: str, result: ParryResult) -> None:
        pending = self._combat_state.pending_parry if self._combat_state else None
        if pending is not None:
            await self._send(ClientRespondToParry(character_id=character_id, result=result, request_id=pending.request_id))

    async def resolve_ai_if_needed(self) -> None:
        return  # only the host ever drives enemy AI

    async def advance_after_combat(self) -> None:
        vote = self.get_readiness()
        if vote is None or vote.action != "advance":
            raise SessionError("Não há esta ação aguardando prontidão.")
        await self.set_party_ready(vote.token, True)

    async def abandon_run(self) -> None:
        # Personal withdrawal cannot end the host's run. Use a snapshot
        # of the last authoritative progress to credit this player's loss.
        if self._last_summary is None:
            self._withdrawing = True
            if self.connection.connected:
                try:
                    await self._send(ClientLeaveRun())
                except (ConnectionClosed, ConnectionError_, OSError):
                    pass
            from wyrdfall.engine.session import GameSession
            snapshot = GameSession(self._run.model_copy(deep=True), self.ruleset, {}, self._dungeon)
            self._last_summary = snapshot.abandon_run()
            self._run = snapshot.run
            self._combat_state = None
