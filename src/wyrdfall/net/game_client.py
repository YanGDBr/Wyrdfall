"""The one interface every screen talks to.

Solo play, a multiplayer host's own view, and a remote joiner are all just
different :class:`GameClient` implementations. A screen never touches
:class:`~wyrdfall.engine.session.GameSession` or a websocket directly --
it reads state through this interface and dispatches actions through it,
so the exact same screens drive all three modes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable

from wyrdfall.domain.abilities import Ability
from wyrdfall.domain.attributes import Atributo
from wyrdfall.domain.models import EvolutionVariants
from wyrdfall.domain.character import Ruleset
from wyrdfall.domain.combat import Action, CombatEngine, CombatState, ParryResult
from wyrdfall.domain.cards import CARD_DEFS
from wyrdfall.domain.content import CONSUMABLE_DEFS
from wyrdfall.domain.dungeon import DungeonDef, RoomType
from wyrdfall.domain.run import RunState, ShopState
from wyrdfall.domain.shop import shop_card_for, shop_stock_for
from wyrdfall.domain.slots import Stance
from wyrdfall.domain.special_rooms import resolved_room_type
from wyrdfall.engine.session import GameSession, RestChoice, SessionError
from wyrdfall.persistence.store import RunSummary
from wyrdfall.net.protocol import PartyReadiness


class GameClient(ABC):
    ruleset: Ruleset

    @property
    def is_paused(self) -> bool:
        return False

    @property
    def connection_status(self) -> str:
        return ""

    @property
    def can_decide_for_party(self) -> bool:
        return True

    def get_readiness(self) -> PartyReadiness | None:
        return None  # Solo advances immediately.

    async def set_party_ready(self, token: str, ready: bool) -> None:
        return

    async def cancel_ready(self) -> None:
        vote = self.get_readiness()
        if vote is not None and vote.ready_ids & self.local_character_ids():
            await self.set_party_ready(vote.token, False)

    def _require_control(self, character_id: str) -> None:
        if character_id not in self.local_character_ids():
            raise SessionError("Você só pode alterar seu próprio personagem.")

    def close(self) -> None:
        """Release transport subscriptions when the application leaves."""

    def __init__(self) -> None:
        self._listeners: list[Callable[[], None]] = []

    def on_update(self, callback: Callable[[], None]) -> None:
        """Registers a callback fired whenever cached state changes --
        immediately for local play, whenever a server broadcast arrives
        for a remote client. Screens use this as their single refresh
        signal instead of polling. Always pair with :meth:`off_update`
        when the screen unmounts, or dead screens pile up as listeners."""
        self._listeners.append(callback)

    def off_update(self, callback: Callable[[], None]) -> None:
        if callback in self._listeners:
            self._listeners.remove(callback)

    def _notify(self) -> None:
        for callback in list(self._listeners):
            callback()

    # -- state reads ---------------------------------------------------------

    @abstractmethod
    def get_run(self) -> RunState: ...

    @abstractmethod
    def get_combat_state(self) -> CombatState | None: ...

    @abstractmethod
    def get_dungeon(self) -> DungeonDef: ...

    @abstractmethod
    def local_character_ids(self) -> set[str]:
        """The party member id(s) this client is allowed to act for."""

    @abstractmethod
    def get_last_summary(self) -> RunSummary | None: ...

    def is_dungeon_cleared(self) -> bool:
        run = self.get_run()
        return run.encounter_index >= len(self.get_dungeon().encounters)

    def current_encounter(self):
        return self.get_dungeon().encounters[self.get_run().encounter_index]

    def current_room_type(self) -> RoomType:
        """A "special" node resolved to forge/rest/shop from the run seed --
        a pure read over the broadcast RunState, so a joiner computes the
        same answer as the host without a message."""
        return resolved_room_type(self.get_run(), self.current_encounter())

    def shop_stock(self) -> list[str]:
        run = self.get_run()
        state = run.shop if run.shop is not None and run.shop.node_index == run.encounter_index else None
        return shop_stock_for(run, state or ShopState(node_index=run.encounter_index), CONSUMABLE_DEFS)

    def shop_sold_slots(self) -> list[int]:
        run = self.get_run()
        if run.shop is None or run.shop.node_index != run.encounter_index:
            return []
        return list(run.shop.sold)

    def shop_card(self) -> str:
        run = self.get_run()
        state = run.shop if run.shop is not None and run.shop.node_index == run.encounter_index else None
        return shop_card_for(run, state or ShopState(node_index=run.encounter_index), CARD_DEFS, self.ruleset.abilities)

    def shop_card_sold(self) -> bool:
        run = self.get_run()
        return run.shop is not None and run.shop.node_index == run.encounter_index and run.shop.card_sold

    def legal_abilities(self, actor_id: str) -> list[Ability]:
        state = self.get_combat_state()
        if state is None:
            return []
        return CombatEngine(self.ruleset).legal_abilities(state, actor_id)

    def legal_target_ids(self, actor_id: str, ability: Ability) -> list[str]:
        state = self.get_combat_state()
        if state is None:
            return []
        return CombatEngine(self.ruleset).legal_target_ids(state, actor_id, ability)

    # -- actions -----------------------------------------------------------

    @abstractmethod
    async def allocate_talent(self, character_id: str, node_id: str) -> None: ...

    @abstractmethod
    async def allocate_attribute(self, character_id: str, attribute: Atributo) -> None: ...

    @abstractmethod
    async def evolve_specialization(
        self, character_id: str, specialization_id: str, variants: EvolutionVariants | None = None,
    ) -> None: ...

    @abstractmethod
    async def equip_weapon(self, character_id: str, weapon_type_id: str) -> None: ...

    @abstractmethod
    async def socket_rune(self, character_id: str, rune_id: str, ability_id: str | None) -> None: ...

    @abstractmethod
    async def unsocket_rune(self, character_id: str, rune_id: str, ability_id: str | None) -> None: ...

    @abstractmethod
    async def absorb_rune(self, character_id: str, rune_id: str) -> None: ...

    @abstractmethod
    async def equip_armor(self, character_id: str, slot: str, item_id: str) -> None: ...

    @abstractmethod
    async def transfer_equipment(self, character_id: str, recipient_id: str, item_id: str) -> None: ...

    @abstractmethod
    async def unequip_armor(self, character_id: str, slot: str) -> None: ...

    @abstractmethod
    async def equip_accessory(self, character_id: str, item_id: str) -> None: ...

    @abstractmethod
    async def unequip_accessory(self, character_id: str, item_id: str) -> None: ...

    @abstractmethod
    async def socket_enchantment(self, character_id: str, item_id: str, enchantment_id: str) -> None: ...

    @abstractmethod
    async def reroll_enchantment(self, character_id: str, item_id: str, slot_index: int) -> None: ...

    @abstractmethod
    async def combine_runes(self, rune_id: str) -> None: ...

    @abstractmethod
    async def start_current_encounter(self) -> None: ...

    @abstractmethod
    async def resolve_rest(self, choice: RestChoice) -> None:
        """Sala de Descanso: Acampar or Meditar. Consumes the node and
        moves the run on; the outcome shows up through get_run() via the
        usual on_update notification, same as every other action."""

    @abstractmethod
    async def resolve_event(self, option_id: str) -> None:
        """Evento: picks one of the current node's options. Same contract
        as resolve_rest -- consumes the node, outcome arrives via on_update."""

    @abstractmethod
    async def use_consumable(self, character_id: str, consumable_id: str) -> None:
        """Drinks one potion from the party pouch for one character, between
        fights. Outcome arrives via on_update like every other action."""

    @abstractmethod
    async def buy_consumable(self, slot: int) -> None:
        """Vendedor: buys the item in one stock slot into the party pouch."""

    @abstractmethod
    async def reroll_shop(self) -> None:
        """Vendedor: pays to re-draw the whole stock."""

    @abstractmethod
    async def leave_node(self) -> None:
        """Consumes a Vendedor/Forja de Campo node and moves the run on."""

    @abstractmethod
    async def accept_contract(self, contract_id: str) -> None:
        """Contratos de Run: takes one of the offered contracts."""

    @abstractmethod
    async def decline_contracts(self) -> None:
        """Contratos de Run: drops whatever is still on offer."""

    @abstractmethod
    async def choose_card(self, character_id: str, card_id: str) -> None:
        """Takes one card from that character's pending 1-of-3 offer."""

    @abstractmethod
    async def skip_card(self, character_id: str) -> None:
        """Declines that character's pending offer."""

    @abstractmethod
    async def buy_card(self, character_id: str) -> None:
        """Vendedor: buys the shelf's one Carta for that character."""

    @abstractmethod
    async def equip_ability(self, character_id: str, ability_id: str) -> None:
        """Puts a pool ability into one of the character's Active Ability Slots."""

    @abstractmethod
    async def unequip_ability(self, character_id: str, ability_id: str) -> None: ...

    @abstractmethod
    async def set_stance(self, character_id: str, stance: Stance) -> None:
        """Postura: free switch, once per turn in combat; a standing choice
        between fights."""

    @abstractmethod
    async def submit_action(self, action: Action) -> None: ...

    @abstractmethod
    async def respond_to_parry(self, character_id: str, result: ParryResult) -> None: ...

    @abstractmethod
    async def resolve_ai_if_needed(self) -> None:
        """Advances one enemy turn if it's currently an AI's turn. A no-op
        for remote clients -- only the host ever drives enemy AI."""

    @abstractmethod
    async def advance_after_combat(self) -> None:
        """Called when 'Continue' is pressed after an encounter ends. The
        actual outcome (back to the dungeon, or the run is over) shows up
        through get_combat_state()/get_last_summary() via the usual
        on_update notification -- this call doesn't return it directly,
        so local and remote clients behave identically to their callers."""


    @abstractmethod
    async def abandon_run(self) -> None:
        """Finalize a voluntary defeat before the app credits its result."""


class LocalGameClient(GameClient):
    """Used for solo play, and as the host's own view of its GameSession."""

    def __init__(self, session: GameSession, controlled_character_ids: set[str] | None = None):
        super().__init__()
        self.session = session
        self.ruleset = session.ruleset
        self._controlled = ({c.id for c in session.run.party} if controlled_character_ids is None
                            else set(controlled_character_ids))
        self._last_summary: RunSummary | None = None

    def get_run(self) -> RunState:
        return self.session.run

    def get_combat_state(self) -> CombatState | None:
        return self.session.combat_state

    def get_dungeon(self) -> DungeonDef:
        return self.session.dungeon

    def local_character_ids(self) -> set[str]:
        return self._controlled

    def get_last_summary(self) -> RunSummary | None:
        return self._last_summary

    async def allocate_talent(self, character_id: str, node_id: str) -> None:
        self._require_control(character_id)
        self.session.allocate_talent(character_id, node_id)
        self._notify()

    async def allocate_attribute(self, character_id: str, attribute: Atributo) -> None:
        self._require_control(character_id)
        self.session.allocate_attribute(character_id, attribute)
        self._notify()

    async def evolve_specialization(
        self, character_id: str, specialization_id: str, variants: EvolutionVariants | None = None,
    ) -> None:
        self._require_control(character_id)
        if not self.session.evolve_specialization(character_id, specialization_id, variants):
            raise SessionError("Essa evolução ou variante já não está disponível.")
        self._notify()

    async def equip_weapon(self, character_id: str, weapon_type_id: str) -> None:
        self._require_control(character_id)
        self.session.equip_weapon(character_id, weapon_type_id)
        self._notify()

    async def socket_rune(self, character_id: str, rune_id: str, ability_id: str | None) -> None:
        self._require_control(character_id)
        self.session.socket_rune(character_id, rune_id, ability_id)
        self._notify()

    async def unsocket_rune(self, character_id: str, rune_id: str, ability_id: str | None) -> None:
        self._require_control(character_id)
        self.session.unsocket_rune(character_id, rune_id, ability_id)

    async def absorb_rune(self, character_id: str, rune_id: str) -> None:
        self._require_control(character_id)
        self.session.absorb_rune(character_id, rune_id)
        self._notify()

    async def equip_armor(self, character_id: str, slot: str, item_id: str) -> None:
        self._require_control(character_id)
        self.session.equip_armor(character_id, slot, item_id)
        self._notify()

    async def transfer_equipment(self, character_id: str, recipient_id: str, item_id: str) -> None:
        self._require_control(character_id)
        if not self.session.transfer_equipment(character_id, recipient_id, item_id):
            raise SessionError("Não foi possível entregar. Confira o dono da peça e o destinatário.")
        self._notify()

    async def unequip_armor(self, character_id: str, slot: str) -> None:
        self._require_control(character_id)
        self.session.unequip_armor(character_id, slot)
        self._notify()

    async def equip_accessory(self, character_id: str, item_id: str) -> None:
        self._require_control(character_id)
        self.session.equip_accessory(character_id, item_id)
        self._notify()

    async def unequip_accessory(self, character_id: str, item_id: str) -> None:
        self._require_control(character_id)
        self.session.unequip_accessory(character_id, item_id)
        self._notify()

    async def socket_enchantment(self, character_id: str, item_id: str, enchantment_id: str) -> None:
        self._require_control(character_id)
        if not self.session.socket_enchantment(character_id, item_id, enchantment_id):
            raise SessionError("Não foi possível encantar. Confira a Forja, a peça e o custo.")
        self._notify()

    async def reroll_enchantment(self, character_id: str, item_id: str, slot_index: int) -> None:
        self._require_control(character_id)
        if not self.session.reroll_enchantment(character_id, item_id, slot_index):
            raise SessionError("Não foi possível rerolar. Confira a Forja, o item e o custo.")
        self._notify()

    async def combine_runes(self, rune_id: str) -> None:
        if not self.session.combine_runes(rune_id):
            raise SessionError("Não foi possível combinar. Confira a Forja, as runas e o custo.")
        self._notify()

    async def start_current_encounter(self) -> None:
        self.session.start_current_encounter()
        self._notify()

    async def resolve_rest(self, choice: RestChoice) -> None:
        self.session.resolve_rest(choice)
        self._notify()

    async def resolve_event(self, option_id: str) -> None:
        self.session.resolve_event(option_id)
        self._notify()

    async def use_consumable(self, character_id: str, consumable_id: str) -> None:
        self._require_control(character_id)
        self.session.use_consumable(character_id, consumable_id)
        self._notify()

    async def buy_consumable(self, slot: int) -> None:
        self.session.buy_consumable(slot)
        self._notify()

    async def reroll_shop(self) -> None:
        self.session.reroll_shop()
        self._notify()

    async def leave_node(self) -> None:
        self.session.leave_node()
        self._notify()

    async def accept_contract(self, contract_id: str) -> None:
        self.session.accept_contract(contract_id)
        self._notify()

    async def decline_contracts(self) -> None:
        self.session.decline_contracts()
        self._notify()

    async def choose_card(self, character_id: str, card_id: str) -> None:
        self._require_control(character_id)
        self.session.choose_card(character_id, card_id)
        self._notify()

    async def skip_card(self, character_id: str) -> None:
        self._require_control(character_id)
        self.session.skip_card(character_id)
        self._notify()

    async def buy_card(self, character_id: str) -> None:
        self._require_control(character_id)
        self.session.buy_card(character_id)
        self._notify()

    async def equip_ability(self, character_id: str, ability_id: str) -> None:
        self._require_control(character_id)
        self.session.equip_ability(character_id, ability_id)
        self._notify()

    async def unequip_ability(self, character_id: str, ability_id: str) -> None:
        self._require_control(character_id)
        self.session.unequip_ability(character_id, ability_id)
        self._notify()

    async def set_stance(self, character_id: str, stance: Stance) -> None:
        self._require_control(character_id)
        self.session.set_stance(character_id, stance)
        self._notify()

    async def submit_action(self, action: Action) -> None:
        self._require_control(action.actor_id)
        self.session.submit_action(action)
        self._notify()

    async def respond_to_parry(self, character_id: str, result: ParryResult) -> None:
        self._require_control(character_id)
        self.session.resolve_parry_response(character_id, result)
        self._notify()

    async def resolve_ai_if_needed(self) -> None:
        state = self.session.combat_state
        if state is None or state.is_over or state.pending_parry is not None:
            return
        actor = state.combatants[state.current_actor_id()]
        if actor.acts_automatically:
            self.session.resolve_ai_turn()
            self._notify()

    async def advance_after_combat(self) -> None:
        summary = self.session.resolve_continue_after_combat()
        if summary is not None:
            self._last_summary = summary
        self._notify()

    async def abandon_run(self) -> None:
        self._last_summary = self.session.abandon_run()
