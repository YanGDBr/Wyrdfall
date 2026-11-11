"""Host-authoritative multiplayer server.

Runs *inside* the host's own Textual process as a background asyncio task
(Textual already runs on asyncio, so this shares its event loop -- no
threads, no separate process). One :class:`GameSession` lives here; every
connected joiner is a thin client that sends :mod:`wyrdfall.net.protocol`
messages and renders whatever state gets broadcast back. LAN and Tailscale
both "just work" because a joiner only ever needs the host's IP and this
port -- nothing IP-family-specific happens on either side.
"""

from __future__ import annotations

from wyrdfall.domain.items import EQUIPMENT_DEFS

import asyncio
import random
import secrets
import uuid
from typing import Callable

import websockets
import websockets.exceptions
from websockets.asyncio.server import ServerConnection

from wyrdfall.domain.attributes import Atributo
from wyrdfall.domain.models import EvolutionVariants
from wyrdfall.domain.character import Ruleset
from wyrdfall.domain.combat import Action, CombatError, ParryResult
from wyrdfall.domain.companions import COMPANION_DEFS, build_companion
from wyrdfall.domain.contracts import contract_offer_for
from wyrdfall.domain.content import MVP_DUNGEON, TALENT_TREES
from wyrdfall.domain.dungeon import DungeonDef
from wyrdfall.domain.loadout import PlayerLoadout, build_character_from_loadout
from wyrdfall.domain.run import RunState
from wyrdfall.domain.slots import Stance
from wyrdfall.domain.wyrd import starting_wyrd
from wyrdfall.engine.session import GameSession, RestChoice, SessionError
from wyrdfall.net.protocol import (
    PROTOCOL_VERSION,
    ProtocolError,
    ClientAction,
    ClientAdvance,
    ClientAllocateAttribute,
    ClientAllocateTalent,
    ClientBuyCard,
    ClientBuyConsumable,
    ClientChooseCard,
    ClientEnterEncounter,
    ClientEquipAbility,
    ClientEquipAccessory,
    ClientEquipArmor,
    ClientTransferEquipment,
    ClientEquipWeapon,
    ClientEvolveSpecialization,
    ClientHello,
    ClientLeaveRun,
    ClientLeaveNode,
    ClientAcceptContract,
    ClientDeclineContracts,
    ClientCombineRunes,
    ClientCommand,
    ClientRerollEnchantment,
    ClientRerollShop,
    ClientResolveEvent,
    ClientResolveRest,
    ClientRespondToParry,
    ClientSetReady,
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
    LobbyPlayer,
    PartyReadiness,
    ServerError,
    ServerLobbyUpdate,
    ServerRunStart,
    ServerStateUpdate,
    ServerWelcome,
    decode_client_message,
    encode,
)
from wyrdfall.persistence.store import RunSummary

AI_TURN_DELAY_SECONDS = 0.6
PARRY_TIMEOUT_SECONDS = 15.0


class HostServer:
    def __init__(
        self,
        ruleset: Ruleset,
        host_player_id: str,
        host_player_name: str,
        class_id: str = "runeguard",
        dungeon: DungeonDef = MVP_DUNGEON,
        pacts: list[str] | None = None,
        ascension_level: int = 0,
        companion_id: str | None = None,
        starting_gear: list[str] | None = None,
        host_loadout: PlayerLoadout | None = None,
        starting_runes: list[str] | None = None,
    ):
        self.ruleset = ruleset
        self.host_player_id = host_player_id
        # Personagem is per player (docs/design/09-roadmap.md Fase 5a:
        # "Arquétipos Base diferentes"): the host's loadout here, each
        # joiner's from its ClientHello. `class_id` alone still works as
        # the host's bare pick.
        self.loadouts: dict[str, PlayerLoadout] = {
            host_player_id: host_loadout or PlayerLoadout(class_id=class_id),
        }
        self.class_id = self.loadouts[host_player_id].class_id
        self.dungeon = dungeon
        # Fase 8 -- lobby-wide like class_id/dungeon: the host's equipped
        # Pactos do Wyrd and chosen Ascensão apply to the whole party.
        self.pacts = list(pacts or [])
        self.ascension_level = ascension_level
        # Fase 9 -- the host's Guild pick, attached to the host's own
        # character only (one Companheiro per co-op run, the host's --
        # same host-meta precedent as race/pacts, not lobby-wide).
        self.companion_id = companion_id
        # the host's Ferreiro gear, into the shared inventory (host-meta precedent)
        self.starting_gear = list(starting_gear or [])
        self.starting_runes = list(starting_runes or [])
        self.players: dict[str, str] = {host_player_id: host_player_name}
        self.connections: dict[str, ServerConnection] = {}
        self.session: GameSession | None = None
        self.last_summary: RunSummary | None = None
        self.port: int | None = None
        self._server = None
        self._lobby_listeners: list[Callable[[], None]] = []
        self._state_listeners: list[Callable[[], None]] = []
        self._parry_future: asyncio.Future | None = None
        self._ai_task: asyncio.Task | None = None
        self._stopping = False
        self._broadcast_lock = asyncio.Lock()
        self._state_revision = uuid.uuid4().hex
        self._readiness: PartyReadiness | None = None
        self._readiness_context = None
        self.resume_tokens: dict[str, str] = {}
        self.checkpoint_callback: Callable[[], None] | None = None

    @property
    def disconnected_ids(self) -> set[str]:
        if self.session is None or self.session.run.is_complete:
            return set()
        return {c.id for c in self.session.run.party if c.id != self.host_player_id and c.id not in self.connections}

    def _require_connected(self) -> None:
        if self.disconnected_ids:
            raise SessionError("Run pausada: aguardando a reconexão de todos os jogadores.")

    @classmethod
    def from_checkpoint(cls, snapshot, ruleset):
        server = cls(ruleset, snapshot.player_id, snapshot.player_name, dungeon=snapshot.dungeon)
        server.session = snapshot.restore_session(ruleset)
        server.players = dict(snapshot.players)
        server.loadouts = dict(snapshot.loadouts)
        server.resume_tokens = dict(snapshot.tokens)
        server.last_summary = snapshot.summary
        if server.session.combat_state is not None and server.session.combat_state.pending_parry is not None:
            server.session.combat_state.pending_parry.request_id = uuid.uuid4().hex
        return server

    def get_readiness(self) -> PartyReadiness | None:
        """Each room/finished fight gets its own vote; combat never has one."""
        session = self.session
        if session is None or session.run.is_complete or len(session.run.party) < 2:
            self._readiness = None
            self._readiness_context = None
            return None
        combat = session.combat_state
        if combat is not None and not combat.is_over:
            self._readiness = None
            self._readiness_context = None
            return None
        context = (session.run.run_id, session.run.encounter_index, id(combat))
        if context != self._readiness_context:
            self._readiness_context = context
            action, label = None, "Aguardando a escolha do host"
            if combat is not None:
                action, label = "advance", "Continuar após o combate"
            elif session.current_room_type == "combat":
                action, label = "enter", "Entrar no encontro"
            elif session.current_room_type in ("shop", "forge"):
                action, label = "leave", "Seguir viagem"
            self._readiness = PartyReadiness(token=uuid.uuid4().hex, action=action, label=label)
        return self._readiness

    def _invalidate_readiness(self, player_id: str | None = None) -> None:
        vote = self.get_readiness()
        if vote is not None:
            vote.token = uuid.uuid4().hex
            if player_id is None:
                vote.ready_ids.clear()
            else:
                vote.ready_ids.discard(player_id)

    async def set_ready(self, player_id: str, token: str, ready: bool) -> None:
        if ready:
            self._require_connected()
        vote = self.get_readiness()
        if vote is None or token != vote.token:
            raise SessionError("Esta prontidão pertence a uma etapa que já terminou.")
        if player_id not in {c.id for c in self.session.run.party}:
            raise SessionError("Você não participa desta run.")
        if ready and vote.action is None:
            raise SessionError("Aguarde o host escolher a ação do grupo.")
        if ready:
            vote.ready_ids.add(player_id)
        else:
            vote.ready_ids.discard(player_id)
        if vote.ready_ids == {c.id for c in self.session.run.party}:
            # No await between the last vote and the transition: execute once.
            try:
                self._execute_party_action(vote.action, vote.argument)
            except (SessionError, CombatError):
                vote.ready_ids.clear()
                await self._broadcast_state()
                raise
            self._readiness_context = None
            self._readiness = None
            await self._broadcast_state()
        else:
            await self._broadcast_state(advance_revision=False)

    def _execute_party_action(self, action: str, argument: str | None = None) -> None:
        if action == "enter":
            self.session.start_current_encounter()
        elif action == "advance":
            self._advance_or_finalize()
        elif action == "leave":
            self.session.leave_node()
        elif action == "rest":
            self.session.resolve_rest(argument)
        elif action == "event":
            self.session.resolve_event(argument)

    async def _request_party_action(self, action: str, argument: str | None = None) -> None:
        self._require_connected()
        vote = self.get_readiness()
        if vote is None:
            self._execute_party_action(action, argument)
            await self._broadcast_state()
            return
        if action in ("rest", "event"):
            expected = "rest" if action == "rest" else "event"
            if self.session.combat_state is not None or self.session.current_room_type != expected:
                raise SessionError("Esta ação não pertence à sala atual.")
            if action == "rest":
                if argument not in ("acampar", "meditar"):
                    raise SessionError("Escolha de descanso inválida.")
                label = "Descansar: " + argument.capitalize()
            else:
                from wyrdfall.domain.content import EVENT_DEFS
                from wyrdfall.domain.events import event_for_node
                event = event_for_node(self.session.run, EVENT_DEFS)
                option = next((o for o in event.options if o.id == argument), None)
                if option is None:
                    raise SessionError("Opção de evento inválida.")
                if self.session.run.currency_earned + option.currency_delta < 0:
                    raise SessionError("Fragmentos insuficientes para essa escolha.")
                label = "Evento: " + option.label
            if (vote.action, vote.argument) != (action, argument):
                vote = PartyReadiness(token=uuid.uuid4().hex, action=action, argument=argument, label=label)
                self._readiness = vote
        elif vote.action != action:
            raise SessionError("Esta ação não pertence à etapa atual.")
        await self.set_ready(self.host_player_id, vote.token, True)

    # -- lifecycle -------------------------------------------------------------

    async def start(self, port: int = 0, host: str = "0.0.0.0") -> int:
        self._server = await websockets.serve(self._handle_connection, host, port, ping_interval=5, ping_timeout=5)
        self.port = self._server.sockets[0].getsockname()[1]
        return self.port

    async def stop(self) -> None:
        self._stopping = True
        if self._ai_task is not None:
            self._ai_task.cancel()
            try:
                await self._ai_task
            except asyncio.CancelledError:
                pass
            self._ai_task = None
        for ws in list(self.connections.values()):
            await ws.close()
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()

    def on_lobby_update(self, callback: Callable[[], None]) -> None:
        self._lobby_listeners.append(callback)

    def off_lobby_update(self, callback: Callable[[], None]) -> None:
        if callback in self._lobby_listeners:
            self._lobby_listeners.remove(callback)

    def _notify_lobby(self) -> None:
        for callback in list(self._lobby_listeners):
            callback()

    def on_state_change(self, callback: Callable[[], None]) -> None:
        """Fired after every broadcast -- i.e. after *any* mutation to the
        session, whether it came from the host's own action or a joiner's
        message. This is how HostGameClient keeps the host's own screens in
        sync without going through a socket to itself."""
        self._state_listeners.append(callback)

    def off_state_change(self, callback: Callable[[], None]) -> None:
        if callback in self._state_listeners:
            self._state_listeners.remove(callback)

    def _notify_state(self) -> None:
        for callback in list(self._state_listeners):
            callback()

    def lobby_players(self) -> list[LobbyPlayer]:
        players = []
        for pid, name in self.players.items():
            loadout = self.loadouts.get(pid, PlayerLoadout())
            players.append(LobbyPlayer(player_id=pid, name=name, class_id=loadout.class_id, race_id=loadout.race_id))
        return players

    # -- connection handling -------------------------------------------------

    async def _handle_connection(self, ws: ServerConnection) -> None:
        player_id: str | None = None
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=10.0)
            hello = decode_client_message(raw)
            if not isinstance(hello, ClientHello):
                await ws.close()
                return
            if hello.protocol_version != PROTOCOL_VERSION or "protocol_version" not in hello.model_fields_set:
                await ws.send(encode(ServerError(message="Versão de protocolo incompatível.", fatal=True)))
                await ws.close()
                return
            if hello.resume_token:
                player_id = next((pid for pid, token in self.resume_tokens.items()
                    if secrets.compare_digest(token, hello.resume_token)), None)
                if (player_id is None or self.session is None or hello.run_id not in (None, self.session.run.run_id)):
                    player_id = None
                    await ws.send(encode(ServerError(message="Credencial de retomada inválida ou jogador já conectado.", fatal=True)))
                    await ws.close(code=1008)
                    return
                if player_id in self.connections:
                    # A half-open old socket may not have timed out yet.
                    # Reject concurrent control, but let the owner retry later.
                    player_id = None
                    await ws.send(encode(ServerError(message="Jogador ainda conectado. Aguardando a conexão anterior encerrar.")))
                    await ws.close(code=1013)
                    return
            else:
                if self.session is not None:
                    await ws.send(encode(ServerError(message="A run já começou. Retome com a credencial original.", fatal=True)))
                    await ws.close(code=1008)
                    return
                player_id = uuid.uuid4().hex[:8]
                self.players[player_id] = hello.player_name
                self.loadouts[player_id] = hello.loadout
                self.resume_tokens[player_id] = secrets.token_urlsafe(32)
            self.connections[player_id] = ws
            await ws.send(encode(ServerWelcome(player_id=player_id,
                class_id=self.loadouts[player_id].class_id, resume_token=self.resume_tokens[player_id])))
            if self.session is not None:
                self._readiness_context = None
                await self._broadcast_state()
            await self._broadcast_lobby()
            self._notify_lobby()

            async for raw in ws:
                try:
                    message = decode_client_message(raw)
                except ProtocolError:
                    await self._send_error(player_id, "Mensagem de jogo inválida.")
                    continue
                await self._handle_client_message(player_id, message)
        except asyncio.TimeoutError:
            await ws.close(code=1008, reason="Tempo de conexão esgotado")
        except ProtocolError:
            await ws.close(code=1008, reason="Mensagem inicial inválida")
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            if player_id is not None and self.connections.get(player_id) is ws:
                del self.connections[player_id]
                if self.session is None:
                    self.players.pop(player_id, None)
                    self.loadouts.pop(player_id, None)
                    self.resume_tokens.pop(player_id, None)
                elif not self._stopping and not self.session.run.is_complete:
                    # Preserve the hero and its inventory. No RNG/turn may move offline.
                    if self._ai_task is not None:
                        paused_task = self._ai_task
                        paused_task.cancel()
                        try:
                            await paused_task
                        except asyncio.CancelledError:
                            pass
                        if self._ai_task is paused_task:
                            self._ai_task = None
                    pending = self.session.combat_state.pending_parry if self.session.combat_state else None
                    if pending is not None:
                        pending.request_id = uuid.uuid4().hex
                    self._readiness_context = None
                    await self._broadcast_state()
                if not self._stopping:
                    await self._broadcast_lobby()
                    self._notify_lobby()

    async def leave_player(self, player_id: str) -> None:
        """Explicit withdrawal is different from an interrupted connection."""
        if self.session.combat_state is not None and not self.session.run.is_complete:
            await self.abandon_run()
        elif not self.session.run.is_complete:
            self.session.run.party[:] = [c for c in self.session.run.party if c.id != player_id]
            for piece in self.session.run.equipment_instances.values():
                if piece.owner_id == player_id:
                    piece.owner_id = None
            self.session.run.companions[:] = [c for c in self.session.run.companions if c.owner_id != player_id]
        self.players.pop(player_id, None)
        self.loadouts.pop(player_id, None)
        self.resume_tokens.pop(player_id, None)
        self._readiness_context = None
        await self._broadcast_state()

    async def _handle_client_message(self, player_id: str, message) -> None:
        if self.session is None or isinstance(message, ClientHello):
            return
        if isinstance(message, ClientLeaveRun):
            await self.leave_player(player_id)
            return
        if self.disconnected_ids:
            await self._send_error(player_id, "Run pausada: aguardando reconexão.")
            return
        character_id = getattr(message, "character_id", None)
        collective = (ClientEnterEncounter, ClientAdvance, ClientResolveRest, ClientResolveEvent,
                      ClientLeaveNode, ClientAcceptContract, ClientDeclineContracts)
        if isinstance(message, collective) and player_id != self.host_player_id:
            await self._send_error(player_id, "A decisão do grupo cabe ao host.")
            return
        if character_id is not None and character_id != player_id:
            await self._send_error(player_id, "Você só pode alterar seu próprio personagem.")
            return
        in_combat_allowed = (ClientUseConsumable, ClientRespondToParry, ClientSetStance)
        if character_id is not None and not isinstance(message, in_combat_allowed) and not self.session.can_manage_build:
            await self._send_error(player_id, "Altere a build somente fora de combate, numa run ativa.")
            return
        if isinstance(message, ClientCommand) and message.revision != self._state_revision:
            await self._send_error(player_id, "O estado da run mudou. Confira a atualização e tente novamente.")
            return
        try:
            if isinstance(message, ClientSetReady):
                await self.set_ready(player_id, message.token, message.ready)
                return
            elif isinstance(message, ClientAllocateTalent):
                self.session.allocate_talent(message.character_id, message.node_id)
            elif isinstance(message, ClientAllocateAttribute):
                self.session.allocate_attribute(message.character_id, message.attribute)
            elif isinstance(message, ClientEnterEncounter):
                await self.start_current_encounter()
                return
            elif isinstance(message, ClientAction):
                await self.submit_action(player_id, message.action)
                return  # submit_action already broadcasts (and drives AI turns)
            elif isinstance(message, ClientRespondToParry):
                await self.respond_to_parry(player_id, message.character_id, message.result, message.request_id)
                return  # respond_to_parry already broadcasts (and resumes AI turns)
            elif isinstance(message, ClientAdvance):
                await self.advance_after_combat()
                return
            elif isinstance(message, ClientEvolveSpecialization):
                await self.evolve_specialization(message.character_id, message.specialization_id, message.variants)
                return
            elif isinstance(message, ClientEquipWeapon):
                self.session.equip_weapon(message.character_id, message.weapon_type_id)
            elif isinstance(message, ClientSocketRune):
                self.session.socket_rune(message.character_id, message.rune_id, message.ability_id)
            elif isinstance(message, ClientAbsorbRune):
                self.session.absorb_rune(message.character_id, message.rune_id)
            elif isinstance(message, ClientUnsocketRune):
                self.session.unsocket_rune(message.character_id, message.rune_id, message.ability_id)
            elif isinstance(message, ClientEquipArmor):
                self.session.equip_armor(message.character_id, message.slot, message.item_id)
            elif isinstance(message, ClientTransferEquipment):
                await self.transfer_equipment(message.character_id, message.recipient_id, message.item_id)
                return
            elif isinstance(message, ClientUnequipArmor):
                self.session.unequip_armor(message.character_id, message.slot)
            elif isinstance(message, ClientEquipAccessory):
                self.session.equip_accessory(message.character_id, message.item_id)
            elif isinstance(message, ClientUnequipAccessory):
                self.session.unequip_accessory(message.character_id, message.item_id)
            elif isinstance(message, ClientSocketEnchantment):
                await self.socket_enchantment(message.character_id, message.item_id, message.enchantment_id)
                return
            elif isinstance(message, ClientRerollEnchantment):
                await self.reroll_enchantment(message.character_id, message.item_id, message.slot_index)
                return
            elif isinstance(message, ClientCombineRunes):
                await self.combine_runes(message.rune_id)
                return
            elif isinstance(message, ClientResolveRest):
                await self.resolve_rest(message.choice)
                return
            elif isinstance(message, ClientResolveEvent):
                await self.resolve_event(message.option_id)
                return
            elif isinstance(message, ClientUseConsumable):
                self.session.use_consumable(message.character_id, message.consumable_id)
            elif isinstance(message, ClientBuyConsumable):
                self.session.buy_consumable(message.slot)
            elif isinstance(message, ClientRerollShop):
                self.session.reroll_shop()
            elif isinstance(message, ClientLeaveNode):
                await self.leave_node()
                return
            elif isinstance(message, ClientAcceptContract):
                self.session.accept_contract(message.contract_id)
            elif isinstance(message, ClientDeclineContracts):
                self.session.decline_contracts()
            elif isinstance(message, ClientChooseCard):
                self.session.choose_card(message.character_id, message.card_id)
            elif isinstance(message, ClientSkipCard):
                self.session.skip_card(message.character_id)
            elif isinstance(message, ClientBuyCard):
                self.session.buy_card(message.character_id)
            elif isinstance(message, ClientEquipAbility):
                self.session.equip_ability(message.character_id, message.ability_id)
            elif isinstance(message, ClientUnequipAbility):
                self.session.unequip_ability(message.character_id, message.ability_id)
            elif isinstance(message, ClientSetStance):
                if message.character_id != player_id:
                    await self._send_error(player_id, "Você só pode mudar a postura do seu próprio personagem.")
                    return
                self.session.set_stance(message.character_id, message.stance)
        except (SessionError, CombatError) as exc:
            # CombatError (e.g. a stale/duplicate action for a turn that has
            # already moved on) must be caught here specifically -- letting it
            # propagate out of this connection's own message loop would kill
            # that loop silently, leaving this client's future messages
            # (including, critically, a parry response) never read again.
            await self._send_error(player_id, str(exc))
            return
        shared = (ClientBuyCard, ClientUseConsumable, ClientSocketEnchantment)
        self._invalidate_readiness(None if isinstance(message, shared) else character_id)
        await self._broadcast_state()

    async def _send_error(self, player_id: str, text: str) -> None:
        ws = self.connections.get(player_id)
        if ws is not None:
            await ws.send(encode(ServerError(message=text)))

    def _ensure_ai_driver(self) -> None:
        if self._stopping or self.session is None or self.disconnected_ids:
            return
        state = self.session.combat_state
        if state is None or state.is_over:
            return
        if self._ai_task is None or self._ai_task.done():
            if state.pending_parry or state.combatants[state.current_actor_id()].acts_automatically:
                self._ai_task = asyncio.create_task(self._drive_ai_turns())

    async def _drive_ai_turns(self) -> None:
        while not self._stopping and not self.disconnected_ids:
            state = self.session.combat_state
            if state is None or state.is_over:
                return
            pending = state.pending_parry
            if pending is not None:
                future = asyncio.get_running_loop().create_future()
                self._parry_future = future
                try:
                    await self._broadcast_state()
                    await asyncio.wait_for(future, timeout=PARRY_TIMEOUT_SECONDS)
                except asyncio.TimeoutError:
                    if self.session.combat_state is state and state.pending_parry is pending:
                        self.session.resolve_parry_response(pending.defender_id, ParryResult.DECLINED)
                        state.log.append("Aparo sem resposta: o ataque segue como uma recusa.")
                        await self._broadcast_state()
                finally:
                    if self._parry_future is future:
                        self._parry_future = None
                continue
            actor = state.combatants[state.current_actor_id()]
            if not actor.acts_automatically:
                return
            await asyncio.sleep(AI_TURN_DELAY_SECONDS)
            if self.session.combat_state is not state or state.is_over or self.disconnected_ids:
                return
            self.session.resolve_ai_turn()
            # Register a parry future before publishing the request.
            if state.pending_parry is None:
                await self._broadcast_state()

    def _advance_or_finalize(self) -> None:
        assert self.session is not None
        summary = self.session.resolve_continue_after_combat()
        if summary is not None:
            self.last_summary = summary

    async def abandon_run(self) -> None:
        assert self.session is not None
        if self.last_summary is None:
            self.last_summary = self.session.abandon_run()
        if self._parry_future is not None and not self._parry_future.done():
            self._parry_future.set_result(None)
        await self._broadcast_state()

    # -- broadcasting --------------------------------------------------------

    async def _broadcast(self, message) -> None:
        async with self._broadcast_lock:
            await self._send_broadcast(message)

    async def _send_broadcast(self, message) -> None:
        raw = encode(message)
        for ws in list(self.connections.values()):
            try:
                await asyncio.wait_for(ws.send(raw), timeout=5.0)
            except (websockets.exceptions.ConnectionClosed, asyncio.TimeoutError):
                pass

    async def _broadcast_lobby(self) -> None:
        await self._broadcast(ServerLobbyUpdate(players=self.lobby_players(), host_id=self.host_player_id))

    async def _broadcast_state(self, *, advance_revision: bool = True) -> None:
        assert self.session is not None
        # Invalidate commands even when an earlier broadcast holds the send lock.
        if advance_revision:
            self._state_revision = uuid.uuid4().hex
        async with self._broadcast_lock:
            if self.checkpoint_callback is not None:
                self.checkpoint_callback()
            await self._send_broadcast(ServerStateUpdate(
                revision=self._state_revision,
                run=self.session.run, combat_state=self.session.combat_state, summary=self.last_summary,
                readiness=self.get_readiness(), disconnected_ids=self.disconnected_ids, dungeon=self.dungeon,
            ))
        self._notify_state()
        self._ensure_ai_driver()

    # -- run lifecycle, driven by the host's own UI ---------------------------

    async def start_run(self) -> GameSession:
        if self.session is not None:
            raise SessionError("Esta sessão já possui uma run.")
        party = [
            build_character_from_loadout(
                pid, name, self.loadouts.get(pid, PlayerLoadout(class_id=self.class_id)), self.ruleset, pacts=self.pacts,
            )
            for pid, name in self.players.items()
        ]
        run = RunState(
            run_id=uuid.uuid4().hex[:8],
            seed=random.randint(0, 2**31 - 1),
            dungeon_id=self.dungeon.id,
            party=party,
            active_pacts=list(self.pacts),
            ascension_level=self.ascension_level,
            wyrd_meter=starting_wyrd(self.pacts),
        )
        run.contract_offer = contract_offer_for(run.seed)
        for character in party:
            loadout = self.loadouts[character.id]
            is_host = character.id == self.host_player_id
            from wyrdfall.domain.inventory import add_equipment
            for definition_id in loadout.starting_gear or (self.starting_gear if is_host else []):
                if definition_id in EQUIPMENT_DEFS:
                    add_equipment(run, definition_id, owner_id=character.id)
            run.rune_inventory.extend(loadout.starting_runes or (self.starting_runes if is_host else []))
            companion_id = loadout.companion_id or (self.companion_id if is_host else None)
            companion_def = COMPANION_DEFS.get(companion_id or "")
            if companion_def is not None:
                run.companions.append(build_companion(companion_def, character))
        self.session = GameSession(run, self.ruleset, TALENT_TREES, dungeon=self.dungeon)
        self.last_summary = None
        await self._broadcast(ServerRunStart())
        await self._broadcast_state()
        return self.session

    # -- direct calls for the host's own local actions (no socket to itself) --
    # These go through the exact same broadcast path as a joiner's message,
    # so the host's own screens and every joiner's screens stay in lockstep.

    async def allocate_talent(self, character_id: str, node_id: str) -> None:
        assert self.session is not None
        self._require_connected()
        self.session.allocate_talent(character_id, node_id)
        self._invalidate_readiness(character_id)
        await self._broadcast_state()

    async def allocate_attribute(self, character_id: str, attribute: Atributo) -> None:
        assert self.session is not None
        self._require_connected()
        self.session.allocate_attribute(character_id, attribute)
        self._invalidate_readiness(character_id)
        await self._broadcast_state()

    async def evolve_specialization(
        self, character_id: str, specialization_id: str, variants: EvolutionVariants | None = None,
    ) -> None:
        assert self.session is not None
        self._require_connected()
        if not self.session.evolve_specialization(character_id, specialization_id, variants):
            raise SessionError("Essa evolução ou variante já não está disponível.")
        self._invalidate_readiness(character_id)
        await self._broadcast_state()

    async def equip_weapon(self, character_id: str, weapon_type_id: str) -> None:
        assert self.session is not None
        self._require_connected()
        self.session.equip_weapon(character_id, weapon_type_id)
        self._invalidate_readiness(character_id)
        await self._broadcast_state()

    async def socket_rune(self, character_id: str, rune_id: str, ability_id: str | None) -> None:
        assert self.session is not None
        self._require_connected()
        self.session.socket_rune(character_id, rune_id, ability_id)
        self._invalidate_readiness(character_id)
        await self._broadcast_state()

    async def unsocket_rune(self, character_id: str, rune_id: str, ability_id: str | None) -> None:
        assert self.session is not None
        self._require_connected()
        self.session.unsocket_rune(character_id, rune_id, ability_id)
        self._invalidate_readiness(character_id)
        await self._broadcast_state()

    async def absorb_rune(self, character_id: str, rune_id: str) -> None:
        assert self.session is not None
        self._require_connected()
        self.session.absorb_rune(character_id, rune_id)
        self._invalidate_readiness(character_id)
        await self._broadcast_state()

    async def equip_armor(self, character_id: str, slot: str, item_id: str) -> None:
        assert self.session is not None
        self._require_connected()
        self.session.equip_armor(character_id, slot, item_id)
        self._invalidate_readiness(character_id)
        await self._broadcast_state()

    async def unequip_armor(self, character_id: str, slot: str) -> None:
        assert self.session is not None
        self._require_connected()
        self.session.unequip_armor(character_id, slot)
        self._invalidate_readiness(character_id)
        await self._broadcast_state()

    async def equip_accessory(self, character_id: str, item_id: str) -> None:
        assert self.session is not None
        self._require_connected()
        self.session.equip_accessory(character_id, item_id)
        self._invalidate_readiness(character_id)
        await self._broadcast_state()

    async def unequip_accessory(self, character_id: str, item_id: str) -> None:
        assert self.session is not None
        self._require_connected()
        self.session.unequip_accessory(character_id, item_id)
        self._invalidate_readiness(character_id)
        await self._broadcast_state()

    async def socket_enchantment(self, character_id: str, item_id: str, enchantment_id: str) -> None:
        assert self.session is not None
        self._require_connected()
        if not self.session.socket_enchantment(character_id, item_id, enchantment_id):
            raise SessionError("Não foi possível encantar. Confira a Forja, a peça e o custo.")
        self._invalidate_readiness(None)
        await self._broadcast_state()

    async def transfer_equipment(self, character_id: str, recipient_id: str, item_id: str) -> None:
        assert self.session is not None
        self._require_connected()
        if not self.session.transfer_equipment(character_id, recipient_id, item_id):
            raise SessionError("Não foi possível entregar. Confira o dono da peça e o destinatário.")
        self._invalidate_readiness(None)
        await self._broadcast_state()

    async def reroll_enchantment(self, character_id: str, item_id: str, slot_index: int) -> None:
        assert self.session is not None
        self._require_connected()
        if not self.session.reroll_enchantment(character_id, item_id, slot_index):
            raise SessionError("Não foi possível rerolar. Confira a Forja, o item e o custo.")
        self._invalidate_readiness(None)
        await self._broadcast_state()

    async def combine_runes(self, rune_id: str) -> None:
        assert self.session is not None
        self._require_connected()
        if not self.session.combine_runes(rune_id):
            raise SessionError("Não foi possível combinar. Confira a Forja, as runas e o custo.")
        self._invalidate_readiness(None)
        await self._broadcast_state()

    async def start_current_encounter(self) -> None:
        await self._request_party_action("enter")

    async def resolve_rest(self, choice: RestChoice) -> None:
        await self._request_party_action("rest", choice)

    async def resolve_event(self, option_id: str) -> None:
        await self._request_party_action("event", option_id)

    async def use_consumable(self, character_id: str, consumable_id: str) -> None:
        assert self.session is not None
        self._require_connected()
        self.session.use_consumable(character_id, consumable_id)
        self._invalidate_readiness(None)
        await self._broadcast_state()

    async def buy_consumable(self, slot: int) -> None:
        assert self.session is not None
        self._require_connected()
        self.session.buy_consumable(slot)
        self._invalidate_readiness(None)
        await self._broadcast_state()

    async def reroll_shop(self) -> None:
        assert self.session is not None
        self._require_connected()
        self.session.reroll_shop()
        self._invalidate_readiness(None)
        await self._broadcast_state()

    async def leave_node(self) -> None:
        await self._request_party_action("leave")

    async def accept_contract(self, contract_id: str) -> None:
        assert self.session is not None
        self._require_connected()
        self.session.accept_contract(contract_id)
        self._invalidate_readiness(None)
        await self._broadcast_state()

    async def decline_contracts(self) -> None:
        assert self.session is not None
        self._require_connected()
        self.session.decline_contracts()
        self._invalidate_readiness(None)
        await self._broadcast_state()

    async def choose_card(self, character_id: str, card_id: str) -> None:
        assert self.session is not None
        self._require_connected()
        self.session.choose_card(character_id, card_id)
        self._invalidate_readiness(character_id)
        await self._broadcast_state()

    async def skip_card(self, character_id: str) -> None:
        assert self.session is not None
        self._require_connected()
        self.session.skip_card(character_id)
        self._invalidate_readiness(character_id)
        await self._broadcast_state()

    async def buy_card(self, character_id: str) -> None:
        assert self.session is not None
        self._require_connected()
        self.session.buy_card(character_id)
        self._invalidate_readiness(character_id)
        await self._broadcast_state()

    async def equip_ability(self, character_id: str, ability_id: str) -> None:
        assert self.session is not None
        self._require_connected()
        self.session.equip_ability(character_id, ability_id)
        self._invalidate_readiness(character_id)
        await self._broadcast_state()

    async def unequip_ability(self, character_id: str, ability_id: str) -> None:
        assert self.session is not None
        self._require_connected()
        self.session.unequip_ability(character_id, ability_id)
        self._invalidate_readiness(character_id)
        await self._broadcast_state()

    async def set_stance(self, character_id: str, stance: Stance) -> None:
        assert self.session is not None
        self._require_connected()
        self.session.set_stance(character_id, stance)
        self._invalidate_readiness(character_id)
        await self._broadcast_state()

    async def submit_action(self, player_id: str, action: Action) -> None:
        assert self.session is not None
        self._require_connected()
        if action.actor_id != player_id:
            await self._send_error(player_id, "Você só pode agir com seu próprio personagem.")
            return
        self.session.submit_action(action)
        await self._broadcast_state()
        self._ensure_ai_driver()

    async def respond_to_parry(self, player_id: str, character_id: str, result: ParryResult, request_id: str | None = None) -> None:
        assert self.session is not None
        self._require_connected()
        if character_id != player_id:
            await self._send_error(player_id, "Você só pode responder por um aparo do seu próprio personagem.")
            return
        try:
            state = self.session.combat_state
            future = self._parry_future
            pending = state.pending_parry if state else None
            if request_id is not None and (pending is None or pending.request_id != request_id):
                raise SessionError("Essa resposta pertence a um aparo que já terminou.")
            self.session.resolve_parry_response(character_id, result)
        except SessionError as exc:
            await self._send_error(player_id, str(exc))
            return
        if future is not None and not future.done():
            future.set_result(None)
        await self._broadcast_state()
        # Wakes the _drive_ai_turns loop that's been awaiting this future
        # (started back when the parry-triggering hit was resolved) -- that
        # loop resumes on its own, so this method must not also start a
        # second one, or two loops would drive AI turns concurrently.

    async def resolve_ai_if_needed(self) -> None:
        self._ensure_ai_driver()

    async def advance_after_combat(self) -> None:
        await self._request_party_action("advance")
