"""GameClient for the host's own screens -- reads/writes the HostServer's
session directly (no socket to itself), but through the exact same
GameClient methods a joiner uses, and stays in sync with joiners because
every one of those methods goes through HostServer's broadcast path."""

from __future__ import annotations

from wyrdfall.domain.attributes import Atributo
from wyrdfall.domain.models import EvolutionVariants
from wyrdfall.domain.combat import Action, CombatState, ParryResult
from wyrdfall.domain.dungeon import DungeonDef
from wyrdfall.domain.run import RunState
from wyrdfall.domain.slots import Stance
from wyrdfall.engine.session import RestChoice, SessionError
from wyrdfall.net.game_client import GameClient
from wyrdfall.net.server import HostServer
from wyrdfall.persistence.store import RunSummary


class HostGameClient(GameClient):
    async def _call(self, command, *args) -> None:
        try:
            await command(*args)
        except SessionError:
            if not self.is_paused:
                raise
            self._notify()

    @property
    def is_paused(self) -> bool:
        return bool(self.server.disconnected_ids)

    @property
    def connection_status(self) -> str:
        names = [self.server.players.get(pid, pid) for pid in self.server.disconnected_ids]
        return "Run pausada — aguardando reconexão: " + ", ".join(names) if names else ""

    def get_readiness(self):
        return self.server.get_readiness()

    async def set_party_ready(self, token: str, ready: bool) -> None:
        await self._call(self.server.set_ready, self.server.host_player_id, token, ready)

    def __init__(self, server: HostServer):
        super().__init__()
        self.server = server
        self.ruleset = server.ruleset
        server.on_state_change(self._notify)

    def get_run(self) -> RunState:
        assert self.server.session is not None
        return self.server.session.run

    def close(self) -> None:
        self.server.off_state_change(self._notify)

    def get_combat_state(self) -> CombatState | None:
        assert self.server.session is not None
        return self.server.session.combat_state

    def get_dungeon(self) -> DungeonDef:
        assert self.server.session is not None
        return self.server.session.dungeon

    def local_character_ids(self) -> set[str]:
        return {self.server.host_player_id}

    def get_last_summary(self) -> RunSummary | None:
        return self.server.last_summary

    async def allocate_talent(self, character_id: str, node_id: str) -> None:
        self._require_control(character_id)
        await self._call(self.server.allocate_talent, character_id, node_id)

    async def allocate_attribute(self, character_id: str, attribute: Atributo) -> None:
        self._require_control(character_id)
        await self._call(self.server.allocate_attribute, character_id, attribute)

    async def evolve_specialization(
        self, character_id: str, specialization_id: str, variants: EvolutionVariants | None = None,
    ) -> None:
        self._require_control(character_id)
        await self._call(self.server.evolve_specialization, character_id, specialization_id, variants)

    async def equip_weapon(self, character_id: str, weapon_type_id: str) -> None:
        self._require_control(character_id)
        await self._call(self.server.equip_weapon, character_id, weapon_type_id)

    async def socket_rune(self, character_id: str, rune_id: str, ability_id: str | None) -> None:
        self._require_control(character_id)
        await self._call(self.server.socket_rune, character_id, rune_id, ability_id)

    async def unsocket_rune(self, character_id: str, rune_id: str, ability_id: str | None) -> None:
        self._require_control(character_id)
        await self._call(self.server.unsocket_rune, character_id, rune_id, ability_id)

    async def absorb_rune(self, character_id: str, rune_id: str) -> None:
        self._require_control(character_id)
        await self._call(self.server.absorb_rune, character_id, rune_id)

    async def equip_armor(self, character_id: str, slot: str, item_id: str) -> None:
        self._require_control(character_id)
        await self._call(self.server.equip_armor, character_id, slot, item_id)

    async def transfer_equipment(self, character_id: str, recipient_id: str, item_id: str) -> None:
        self._require_control(character_id)
        await self._call(self.server.transfer_equipment, character_id, recipient_id, item_id)

    async def unequip_armor(self, character_id: str, slot: str) -> None:
        self._require_control(character_id)
        await self._call(self.server.unequip_armor, character_id, slot)

    async def equip_accessory(self, character_id: str, item_id: str) -> None:
        self._require_control(character_id)
        await self._call(self.server.equip_accessory, character_id, item_id)

    async def unequip_accessory(self, character_id: str, item_id: str) -> None:
        self._require_control(character_id)
        await self._call(self.server.unequip_accessory, character_id, item_id)

    async def socket_enchantment(self, character_id: str, item_id: str, enchantment_id: str) -> None:
        self._require_control(character_id)
        await self._call(self.server.socket_enchantment, character_id, item_id, enchantment_id)

    async def reroll_enchantment(self, character_id: str, item_id: str, slot_index: int) -> None:
        self._require_control(character_id)
        await self._call(self.server.reroll_enchantment, character_id, item_id, slot_index)

    async def combine_runes(self, rune_id: str) -> None:
        await self._call(self.server.combine_runes, rune_id)

    async def start_current_encounter(self) -> None:
        await self._call(self.server.start_current_encounter)

    async def resolve_rest(self, choice: RestChoice) -> None:
        await self._call(self.server.resolve_rest, choice)

    async def resolve_event(self, option_id: str) -> None:
        await self._call(self.server.resolve_event, option_id)

    async def use_consumable(self, character_id: str, consumable_id: str) -> None:
        self._require_control(character_id)
        await self._call(self.server.use_consumable, character_id, consumable_id)

    async def buy_consumable(self, slot: int) -> None:
        await self._call(self.server.buy_consumable, slot)

    async def reroll_shop(self) -> None:
        await self._call(self.server.reroll_shop)

    async def leave_node(self) -> None:
        await self._call(self.server.leave_node)

    async def accept_contract(self, contract_id: str) -> None:
        await self._call(self.server.accept_contract, contract_id)

    async def decline_contracts(self) -> None:
        await self._call(self.server.decline_contracts)

    async def choose_card(self, character_id: str, card_id: str) -> None:
        self._require_control(character_id)
        await self._call(self.server.choose_card, character_id, card_id)

    async def skip_card(self, character_id: str) -> None:
        self._require_control(character_id)
        await self._call(self.server.skip_card, character_id)

    async def buy_card(self, character_id: str) -> None:
        self._require_control(character_id)
        await self._call(self.server.buy_card, character_id)

    async def equip_ability(self, character_id: str, ability_id: str) -> None:
        self._require_control(character_id)
        await self._call(self.server.equip_ability, character_id, ability_id)

    async def unequip_ability(self, character_id: str, ability_id: str) -> None:
        self._require_control(character_id)
        await self._call(self.server.unequip_ability, character_id, ability_id)

    async def set_stance(self, character_id: str, stance: Stance) -> None:
        self._require_control(character_id)
        await self._call(self.server.set_stance, character_id, stance)

    async def submit_action(self, action: Action) -> None:
        self._require_control(action.actor_id)
        await self._call(self.server.submit_action, self.server.host_player_id, action)

    async def respond_to_parry(self, character_id: str, result: ParryResult) -> None:
        self._require_control(character_id)
        await self._call(self.server.respond_to_parry, self.server.host_player_id, character_id, result)

    async def resolve_ai_if_needed(self) -> None:
        await self._call(self.server.resolve_ai_if_needed)

    async def advance_after_combat(self) -> None:
        await self._call(self.server.advance_after_combat)

    async def abandon_run(self) -> None:
        await self._call(self.server.abandon_run)
