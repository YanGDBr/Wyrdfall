"""Orchestrates one full run: talent allocation between fights, starting
each encounter's CombatEngine, and computing the run's final outcome.

This is the one place the actual game simulation lives, for both solo play
and a multiplayer host. It is wrapped by a :class:`wyrdfall.net.game_client.GameClient`
(LocalGameClient for solo/host, RemoteGameClient for a joiner) so that UI
screens never call GameSession directly -- they always go through that
common interface, which is what makes solo, hosting, and joining drive the
exact same screens.
"""

from __future__ import annotations

import random
from typing import Literal

from wyrdfall.domain.attributes import Atributo
from wyrdfall.domain.cards import sealed_card_ids, CARD_DEFS, CARD_PRICES_BY_RARITY, roll_card_offer
from wyrdfall.domain.character import Character, Ruleset
from wyrdfall.domain.blessings import BLESSING_DEFS, heal_fraction_per_node_for, roll_blessing
from wyrdfall.domain.combat import Action, CombatEngine, CombatState, ParryResult
from wyrdfall.domain.contracts import CONTRACT_DEFS
from wyrdfall.domain.models import EffectKind, EvolutionVariants
from wyrdfall.domain.sealing import is_sealed_source
from wyrdfall.domain.content.terrain import AREA_TERRAINS
from wyrdfall.domain.companions import COMPANION_REVIVE_FRACTION, rescale_companion
from wyrdfall.domain.consumables import CONSUMABLE_SLOTS
from wyrdfall.domain.content import CONSUMABLE_DEFS, ENEMY_DEFS, EVENT_DEFS, MVP_DUNGEON
from wyrdfall.domain.dungeon import DungeonDef, RoomType, difficulty_multiplier
from wyrdfall.domain.enemies import instantiate_enemy
from wyrdfall.domain.events import event_rng, EventDef, event_for_node
from wyrdfall.domain.factory import recompute_passive_effects
from wyrdfall.domain.items import ACCESSORY_SLOTS, ENCHANTMENT_DEFS, ENCHANTMENT_SLOTS_BY_RARITY, EQUIPMENT_DEFS, Rarity, equipped_item_ids
from wyrdfall.domain.inventory import add_equipment, initialize_weapons, sync_equipment
from wyrdfall.domain.items import compatible_piece, enchantment_choices
from wyrdfall.domain.leveling import apply_level_ups
from wyrdfall.domain.loot import roll_consumable_drop, roll_encounter_drops, roll_rune_drop
from wyrdfall.domain.race_evolution import apply_race_evolution, pending_race_evolution
from wyrdfall.domain.races import RACE_DEFS, check_race_unlock
from wyrdfall.domain.run import RunState, ShopState
from wyrdfall.domain.runes import ABILITY_RUNE_SLOTS_PER_ABILITY, BODY_RUNE_SLOTS, RUNE_DEFS, RUNE_DROP_POOL, supports_ability_socket
from wyrdfall.domain.shop import CONSUMABLE_PRICES, SHOP_REROLL_COST, shop_card_for, shop_stock_for
from wyrdfall.domain.slots import Stance
from wyrdfall.domain.special_rooms import resolved_room_type
from wyrdfall.domain.specializations import (
    SPECIALIZATION_DEFS,
    STAGE2_DEFS,
    evolution_variant_choices,
    merge_evolution_variants,
    qualifies_stage2,
    qualifying_specializations,
)
from wyrdfall.domain.talents import TalentTree
from wyrdfall.domain.weapons import WEAPON_TYPE_DEFS
from wyrdfall.domain.wyrd import add_wyrd, danger_multiplier, reward_multiplier
from wyrdfall.persistence.store import RunSummary


class SessionError(Exception):
    pass


# Character level at which Stage-1 Especialização evolution becomes
# available (docs/design/05-classes.md §6). Public so the UI can gate the
# "Evoluir" button without duplicating the number -- evolve_specialization
# itself always re-checks it server-side.
EVOLUTION_LEVEL = 5
# ...and the Estágio 2 level (docs/design/05b-classes-roster.md §10).
EVOLUTION_STAGE2_LEVEL = 10

# Forja de Campo's Fragmentos cost for one reroll (docs/design/
# 08-itens-crafting.md), on top of 1 material matching the item's own
# rarity -- first-guess balance number, like every other rate here.
REROLL_ENCHANTMENT_FRAGMENTOS_COST = 10
# Forja de Campo's rune combine (08-itens-crafting.md): Fragmentos + 1 material Comum
COMBINE_RUNES_FRAGMENTOS_COST = 10

# Incapacitado/Reviver (docs/design/11-habilidades.md §5, user-resolved):
# a party member downed in a fight the group still wins comes back for
# free at this fraction of max HP.
REVIVE_ON_VICTORY_FRACTION = 0.10
# Medidor do Wyrd gain for a Renascido's "Abraçar a Morte" (09-roadmap.md
# decision 1) -- same magnitude as a Pacto de Risco.
WYRD_PER_EMBRACE = 15.0

# Sala de Descanso (docs/design/14-estrutura-da-run.md §5): "Acampar"
# heals "uma fração alta do PV máximo" -- the doc gives no number, so
# this is a first-guess balance rate like every other one here.
REST_HEAL_FRACTION = 0.6
RestChoice = Literal["acampar", "meditar"]


class GameSession:
    def __init__(
        self,
        run: RunState,
        ruleset: Ruleset,
        talent_trees: dict[str, TalentTree],
        dungeon: DungeonDef = MVP_DUNGEON,
    ):
        self.run = run
        initialize_weapons(run)
        self.ruleset = ruleset
        self.talent_trees = talent_trees
        self.dungeon = dungeon
        self.combat_engine: CombatEngine | None = None
        self.combat_state: CombatState | None = None
        self._final_summary: RunSummary | None = None
        # Populated by collect_victory_reward_and_advance, read by the
        # caller (WyrdfallApp.bank_run_reward) right after -- computed from
        # combat_state, which that same call nulls out at its end, so it
        # can't be recomputed later from run state alone.
        self.newly_eligible_races: list[str] = []

    @property
    def can_manage_build(self) -> bool:
        return not self.run.is_complete and self.combat_state is None

    def _require_management(self) -> None:
        if not self.can_manage_build:
            raise SessionError("Altere a build e resolva salas somente fora de combate, numa run ativa.")

    # -- dungeon / encounter flow ----------------------------------------

    @property
    def is_dungeon_cleared(self) -> bool:
        return self.run.encounter_index >= len(self.dungeon.encounters)

    @property
    def current_encounter(self):
        if self.is_dungeon_cleared:
            raise SessionError("No encounters remain; the dungeon is cleared.")
        return self.dungeon.encounters[self.run.encounter_index]

    @property
    def current_room_type(self) -> RoomType:
        """What the current node actually is -- a "special" node resolves to
        forge/rest/shop from the run seed (domain/special_rooms.py)."""
        return resolved_room_type(self.run, self.current_encounter)

    @property
    def can_use_forge(self) -> bool:
        return self.can_manage_build and not self.is_dungeon_cleared and self.current_room_type == "forge"

    def start_current_encounter(self) -> CombatState:
        if self.run.is_complete or self.combat_state is not None:
            raise SessionError("Já existe um combate pendente ou a run terminou.")
        encounter = self.current_encounter
        if self.current_room_type != "combat":
            raise SessionError("Este nó não é um combate -- resolva-o pela sua própria escolha.")
        # Fase 8: Pactos de Risco, Ascensão and the Medidor do Wyrd all feed
        # one danger multiplier on top of the position/party-size one.
        multiplier = difficulty_multiplier(self.run.encounter_index, len(self.run.party)) * danger_multiplier(self.run)
        enemies = [
            instantiate_enemy(ENEMY_DEFS[enemy_id], f"{enemy_id}_{i}", stat_multiplier=multiplier)
            for i, enemy_id in enumerate(encounter.enemy_ids)
        ]
        self.combat_engine = CombatEngine(self.ruleset, rng=self.run.encounter_rng())
        self._prepare_companions()
        # Terreno (07-mundo-dificuldade.md): the Área's element shows in the arena
        terrain = AREA_TERRAINS.get(encounter.area_id)
        self.combat_state = self.combat_engine.start_encounter(
            [*self.run.party, *self.run.companions], enemies, terrain=terrain,
        )
        self.run.discovered_enemy_ids.update(encounter.enemy_ids)
        return self.combat_state

    def _prepare_companions(self) -> None:
        """Fase 9 (domain/companions.py): a Companheiro is "convocado" at
        every encounter start -- rescaled to its owner's current level,
        and brought back at COMPANION_REVIVE_FRACTION if it fell last time
        (a downed companion is never lost for the run)."""
        for companion in self.run.companions:
            owner = next((c for c in self.run.party if c.id == companion.owner_id), None)
            if owner is not None:
                rescale_companion(companion, owner)
            if not companion.is_alive:
                companion.current_hp = COMPANION_REVIVE_FRACTION * companion.computed_stats(self.ruleset).max_hp
            companion.statuses = []
            companion.shield_hp = 0.0

    def submit_action(self, action: Action) -> list[str]:
        if self.combat_engine is None or self.combat_state is None:
            raise SessionError("No encounter in progress.")
        log = self.combat_engine.resolve(self.combat_state, action)
        self._sync_party_from_combat()
        ability = self.ruleset.abilities.get(action.ability_id)
        if ability is not None and any(e.kind == EffectKind.DEATH_WARD for e in ability.effects):
            # 09-roadmap.md decision 1: "Abraçar a Morte" is the meter's third source
            if action.actor_id not in self.run.wyrd_embraces:
                self.run.wyrd_embraces.append(action.actor_id)
                add_wyrd(self.run, WYRD_PER_EMBRACE)
        return log

    def resolve_ai_turn(self) -> list[str]:
        if self.combat_engine is None or self.combat_state is None:
            raise SessionError("No encounter in progress.")
        log = self.combat_engine.resolve_ai_turn(self.combat_state)
        self._sync_party_from_combat()
        return log

    def resolve_parry_response(self, character_id: str, result: ParryResult) -> list[str]:
        if self.combat_engine is None or self.combat_state is None:
            raise SessionError("No encounter in progress.")
        pending = self.combat_state.pending_parry
        if pending is None or pending.defender_id != character_id:
            raise SessionError("Não há um aparo pendente para este personagem.")
        log = self.combat_engine.resolve_parry(self.combat_state, result)
        self._sync_party_from_combat()
        return log

    def _sync_party_from_combat(self) -> None:
        assert self.combat_state is not None
        updated: list[Character] = []
        for character in self.run.party:
            latest = self.combat_state.combatants.get(character.id)
            updated.append(latest if latest is not None else character)
        self.run.party = updated
        self.run.companions = [
            self.combat_state.combatants.get(companion.id, companion) for companion in self.run.companions
        ]

    @property
    def encounter_is_over(self) -> bool:
        return self.combat_state is not None and self.combat_state.is_over

    @property
    def encounter_victory(self) -> bool | None:
        return self.combat_state.victory if self.combat_state else None

    def collect_victory_reward_and_advance(self) -> int:
        """Called once after a won encounter: banks currency, grants a
        talent point to every party member, clears transient combat
        statuses (they don't carry between fights), and moves the dungeon
        pointer forward."""
        if not (self.combat_state and self.combat_state.victory):
            raise SessionError("Cannot advance: current encounter was not won.")
        encounter = self.current_encounter
        reward = round(sum(ENEMY_DEFS[eid].currency_reward for eid in encounter.enemy_ids) * reward_multiplier(self.run))
        vigor_reward = sum(ENEMY_DEFS[eid].vigor_reward for eid in encounter.enemy_ids)
        self.run.currency_earned += reward
        if encounter.is_boss:
            self.run.bosses_defeated += 1
            if encounter.id not in self.run.defeated_boss_ids:
                self.run.defeated_boss_ids.append(encounter.id)
        if self.combat_state.had_successful_parry:
            self.run.parried_successfully = True
        if self.combat_state.damage_taken_this_encounter == 0:
            self.run.had_flawless_encounter = True
        self.newly_eligible_races = [
            race_id
            for race_id in RACE_DEFS
            if race_id != "human" and check_race_unlock(race_id, encounter=encounter, combat_state=self.combat_state)
        ]
        for character in self.run.party:
            unlocks = self.run.race_unlocks_by_character.setdefault(character.id, set())
            unlocks.update(race_id for race_id in RACE_DEFS if check_race_unlock(
                race_id, encounter=encounter, combat_state=self.combat_state, participant_id=character.id,
            ))
        luck_points = sum(c.attribute_points.get(Atributo.LUCK, 0) for c in self.run.party)
        dropped_items, dropped_materials = roll_encounter_drops(
            encounter, self.run.encounter_index, luck_points, self.run.loot_rng()
        )
        from wyrdfall.domain.loot import boss_reward_for
        boss_item = boss_reward_for(encounter, self.run.party)
        if boss_item:
            dropped_items = [boss_item]
            dropped_materials = {EQUIPMENT_DEFS[boss_item].rarity: 2}
        enchant_rng = random.Random(self.run.seed * 17_000_003 + self.run.encounter_index)
        for definition_id in dropped_items:
            element = EQUIPMENT_DEFS[definition_id].required_element
            # Random pieces always have an affix compatible with at least one
            # human. A boss's elemental signature is guaranteed when usable.
            pool = sorted({eid for hero in self.run.party for eid in enchantment_choices(hero)})
            if boss_item == "hollow_aegis":
                pool = [eid for eid in pool if ENCHANTMENT_DEFS[eid].required_element is None]
            enchant = f"ench_{element.value}" if boss_item and element else enchant_rng.choice(pool)
            add_equipment(self.run, definition_id, enchantments=[enchant])
        for rarity, count in dropped_materials.items():
            self.run.materials[rarity] = self.run.materials.get(rarity, 0) + count
        consumable_id = roll_consumable_drop(encounter, luck_points, self.run.consumable_rng(), CONSUMABLE_DEFS)
        rune_id = roll_rune_drop(encounter, luck_points, self.run.rune_rng(), RUNE_DROP_POOL)
        if rune_id is not None:
            self.run.rune_inventory.append(rune_id)
        if consumable_id is not None and len(self.run.consumables) < CONSUMABLE_SLOTS:
            self.run.consumables.append(consumable_id)
        for index, character in enumerate(self.run.party):
            if character.is_incapacitated:
                # 11-habilidades.md §5: "grupo vence com alguém Incapacitado ->
                # revive automaticamente com 10% do PV máximo"
                character.current_hp = max(1.0, REVIVE_ON_VICTORY_FRACTION * character.computed_stats(self.ruleset).max_hp)
            character.statuses = []
            character.build.talent_tree.points_available += 1
            character.vigor += vigor_reward
            tree = self.talent_trees.get(_talent_tree_id_for(character))
            apply_level_ups(character, self.ruleset, tree)
            # docs/design/14-estrutura-da-run.md §5: "escolha 1-de-3 Cartas"
            # after every won fight -- a fresh offer replaces an unclaimed one
            character.card_offer = roll_card_offer(
                encounter.is_elite or encounter.is_boss, self.run.card_rng(index), CARD_DEFS,
                exclude=sealed_card_ids(character, CARD_DEFS, self.ruleset.abilities),
            )
            if encounter.is_boss:
                # docs/design/14-estrutura-da-run.md §6/§8 -- full heal only
                # when a run moves to its next Área (right after a boss
                # falls), never between regular combats inside one. After
                # apply_level_ups so a level gained on this very kill is
                # already reflected in max_hp/max_resource.
                stats = character.computed_stats(self.ruleset)
                character.current_hp = stats.max_hp
                character.current_resource = stats.max_resource
        if encounter.is_boss:
            for companion in self.run.companions:
                companion.current_hp = companion.computed_stats(self.ruleset).max_hp
            self._refill_charges()
            self._settle_race_evolutions(first_boss=self.run.bosses_defeated == 1)
        reward += self._settle_contracts(encounter)
        self._strip_terrain()
        if encounter.is_elite:
            # Bênçãos (06-economia-progressao.md): the "recompensa de sala" source
            self._grant_blessing(roll_blessing(self.run.blessing_rng(), BLESSING_DEFS, self._party_blessings()))
        self._advance_node()
        self.combat_engine = None
        self.combat_state = None
        return reward

    def _strip_terrain(self) -> None:
        """The Terreno (and a TRANSFORM) is the arena's, never the
        character's: the run's copies (which ARE the combat objects while a
        fight is on) lose them the moment the fight is settled."""
        for character in [*self.run.party, *self.run.companions]:
            if character.terrain_modifiers:
                character.terrain_modifiers = []
            if character.active_transform_id is not None:
                character.active_transform_id = None
                character.transform_turns_left = 0
                character.transform_modifiers = []

    def _settle_race_evolutions(self, *, first_boss: bool) -> None:
        """Evolução de raça (04-racas.md item 5) keyed on run facts only the
        session sees: an Área just ended (a boss fell) and whether it was
        the run's first. Also resets the per-Área counters afterwards."""
        for character in self.run.party:
            evolution = pending_race_evolution(character, area_completed=True, first_boss=first_boss)
            if evolution is not None:
                apply_race_evolution(character, evolution)
                self.run.race_evolution_log.append(f"{character.name} evolui: {evolution.name}!")
            character.used_non_physical_this_area = False

    def absorb_rune(self, character_id: str, rune_id: str) -> bool:
        """Construto (04-racas.md): "pode absorver permanentemente (só nesta
        run) o efeito de uma runa ... sem precisar de um item para
        carregá-la" -- once per run, the rune counts as socketed without
        taking a slot (see runes.py::_all_socketed_rune_ids)."""
        if not self.can_manage_build:
            return False
        character = next((c for c in self.run.party if c.id == character_id), None)
        if character is None or character.race_id != "construto" or rune_id not in self.run.rune_inventory:
            return False
        if character.absorbed_rune_id is not None or self.combat_state is not None:
            return False
        self.run.rune_inventory.remove(rune_id)
        character.absorbed_rune_id = rune_id
        tree = self.talent_trees.get(_talent_tree_id_for(character))
        recompute_passive_effects(character, tree)
        return True

    def _advance_node(self) -> None:
        """The one place the run moves to its next node -- so per-node
        hooks (a Bênção's "cura X% ao trocar de sala") have a single home."""
        self.run.encounter_index += 1
        for character in self.run.party:
            fraction = heal_fraction_per_node_for(character)
            if fraction > 0 and character.is_alive:
                max_hp = character.computed_stats(self.ruleset).max_hp
                character.current_hp = min(max_hp, character.current_hp + fraction * max_hp)

    # -- bênçãos (docs/design/06-economia-progressao.md) ----------------------------

    def _party_blessings(self) -> list[str]:
        return list(self.run.party[0].blessings) if self.run.party else []

    def _grant_blessing(self, blessing_id: str | None) -> None:
        """A Bênção is a run-level seasoning: everyone in the party gets it,
        nobody gets it twice."""
        if blessing_id is None or blessing_id not in BLESSING_DEFS:
            return
        for character in self.run.party:
            if blessing_id not in character.blessings:
                character.blessings.append(blessing_id)
            recompute_passive_effects(character, self.talent_trees.get(_talent_tree_id_for(character)))

    # -- contratos de run (docs/design/08-itens-crafting.md) ------------------------

    def accept_contract(self, contract_id: str) -> bool:
        if not self.can_manage_build:
            return False
        if contract_id not in self.run.contract_offer or contract_id not in CONTRACT_DEFS:
            return False
        self.run.contract_offer.remove(contract_id)
        self.run.accepted_contracts.append(contract_id)
        return True

    def decline_contracts(self) -> None:
        self._require_management()
        self.run.contract_offer = []

    def _settle_contracts(self, encounter) -> int:
        """After a won encounter: every accepted, not-yet-completed contract
        whose condition the fight met pays its Fragmentos now and banks its
        Ecos for the end of the run. Each completes at most once."""
        assert self.combat_state is not None
        earned = 0
        for contract_id in list(self.run.accepted_contracts):
            contract = CONTRACT_DEFS.get(contract_id)
            if contract is None or contract_id in self.run.completed_contracts:
                continue
            if contract.boss_only and not encounter.is_boss:
                continue
            if contract.check(self.combat_state):
                self.run.completed_contracts.append(contract_id)
                self.run.currency_earned += contract.reward_fragments
                self.run.contract_ecos += contract.reward_ecos
                earned += contract.reward_fragments
        return earned

    # -- sala de descanso (Fase 7) ---------------------------------------------

    def resolve_rest(self, choice: RestChoice) -> None:
        """Sala de Descanso (docs/design/14-estrutura-da-run.md §5): Acampar
        heals the whole party, Meditar grants everyone a Ponto de Talento
        instead. Either way the node is consumed and the run moves on --
        no currency/vigor/talent-for-a-win, a rest isn't a combat."""
        self._require_management()
        if self.combat_state is not None:
            raise SessionError("Há um combate em andamento.")
        if self.current_room_type != "rest":
            raise SessionError("O nó atual não é uma Sala de Descanso.")
        if choice not in ("acampar", "meditar"):
            raise SessionError("Escolha de descanso inválida.")
        for character in self.run.party:
            if choice == "acampar":
                max_hp = character.computed_stats(self.ruleset).max_hp
                character.current_hp = min(max_hp, character.current_hp + REST_HEAL_FRACTION * max_hp)
            else:
                character.build.talent_tree.points_available += 1
        if choice == "acampar":
            for companion in self.run.companions:
                max_hp = companion.computed_stats(self.ruleset).max_hp
                companion.current_hp = min(max_hp, companion.current_hp + REST_HEAL_FRACTION * max_hp)
        self._refill_charges()  # 11-habilidades.md §7.4: cargas recarregam no descanso, seja qual for a escolha
        self._advance_node()

    def _refill_charges(self) -> None:
        for character in self.run.party:
            for ability_id in character.abilities:
                ability = self.ruleset.abilities.get(ability_id)
                if ability is not None and ability.charges_per_rest is not None:
                    character.charges[ability_id] = ability.charges_per_rest

    # -- evento (Fase 7) --------------------------------------------------------

    @property
    def current_event(self) -> EventDef:
        """The Evento drawn for the current node -- deterministic from the
        run seed + node index, so every client computes the same one."""
        if self.current_encounter.room_type != "event":
            raise SessionError("O nó atual não é um Evento.")
        return event_for_node(self.run, EVENT_DEFS)

    def resolve_event(self, option_id: str) -> None:
        """Applies one option of the current Evento to the whole party and
        moves the run on. An Evento never kills (damage floors at 1 PV) and
        never forces a combat (docs/design/14-estrutura-da-run.md §5)."""
        self._require_management()
        if self.combat_state is not None:
            raise SessionError("Há um combate em andamento.")
        option = self.current_event.option(option_id)
        if option is None:
            raise SessionError("Essa opção não existe neste Evento.")
        if option.currency_delta < 0 and self.run.currency_earned < -option.currency_delta:
            raise SessionError("Fragmentos insuficientes para essa escolha.")
        self.run.currency_earned += option.currency_delta
        add_wyrd(self.run, option.wyrd_risk)
        for character in self.run.party:
            max_hp = character.computed_stats(self.ruleset).max_hp
            if option.heal_fraction > 0:
                character.current_hp = min(max_hp, character.current_hp + option.heal_fraction * max_hp)
            if option.damage_fraction > 0:
                character.current_hp = max(1.0, character.current_hp - option.damage_fraction * max_hp)
            character.build.talent_tree.points_available += option.talent_points
            # docs/design/05-classes.md §4: -100 (Maligno) to +100 (Bondoso)
            character.alignment_score = max(-100.0, min(100.0, character.alignment_score + option.alignment_shift))
            if option.card_id is not None:
                self._grant_card(character, option.card_id)
        if option.unlocks_race and option.unlocks_race not in self.run.race_unlocks:
            self.run.race_unlocks.append(option.unlocks_race)
        if option.blessing:
            # an altar (06-economia-progressao.md): one Bênção for the party
            self._grant_blessing(roll_blessing(event_rng(self.run), BLESSING_DEFS, self._party_blessings()))
        self._advance_node()

    # -- cartas (Fase 7) --------------------------------------------------------

    def _grant_card(self, character: Character, card_id: str) -> None:
        card = CARD_DEFS[card_id]
        character.cards.append(card_id)
        if card.grants_ability is not None:
            self._grant_ability(character, card.grants_ability)
        recompute_passive_effects(character, self.talent_trees.get(_talent_tree_id_for(character)))

    # -- slots de habilidade ativa / postura (Fase 7) ---------------------------

    def _grant_ability(self, character: Character, ability_id: str) -> None:
        """Every way an ability enters a character's pool (talent keystone,
        active Carta) goes through here: it's added to the pool and, while
        an Active Ability Slot is still free, equipped too -- so nothing
        changes for the player until the pool actually outgrows the slots
        (docs/design/10-sistemas-de-build.md §4)."""
        ability = self.ruleset.abilities.get(ability_id)
        if ability is not None and is_sealed_source(
            character, archetype_weight=ability.archetype_weight,
            damage_elements=[e.damage_element for e in ability.effects if e.kind == EffectKind.DAMAGE],
        ):
            return  # Selamentos (10-sistemas-de-build.md §7): a sealed source never enters the pool
        if ability_id not in character.abilities:
            character.abilities.append(ability_id)
        if ability is not None and ability.charges_per_rest is not None and ability_id not in character.charges:
            character.charges[ability_id] = ability.charges_per_rest  # §7.4: a fresh ability comes fully charged
        if ability is None or ability.universal or ability_id in character.equipped_abilities:
            return
        if len(character.equipped_abilities) < character.active_slot_capacity:
            character.equipped_abilities.append(ability_id)

    def equip_ability(self, character_id: str, ability_id: str) -> bool:
        if not self.can_manage_build:
            return False
        character = next((c for c in self.run.party if c.id == character_id), None)
        ability = self.ruleset.abilities.get(ability_id)
        if character is None or ability is None or ability.universal:
            return False
        if ability_id not in character.abilities or ability_id in character.equipped_abilities:
            return False
        if len(character.equipped_abilities) >= character.active_slot_capacity:
            return False
        character.equipped_abilities.append(ability_id)
        return True

    def unequip_ability(self, character_id: str, ability_id: str) -> bool:
        if not self.can_manage_build:
            return False
        character = next((c for c in self.run.party if c.id == character_id), None)
        if character is None or ability_id not in character.equipped_abilities:
            return False
        character.equipped_abilities.remove(ability_id)
        return True

    def set_stance(self, character_id: str, stance: Stance) -> list[str]:
        """Postura (docs/design/10-sistemas-de-build.md §3.9). Mid-combat it
        goes through the engine (own turn, once per turn); between fights
        it's just the character's standing choice for the next one."""
        if self.run.is_complete or stance not in ("none", "offensive", "evasive", "precise"):
            raise SessionError("Não é possível escolher essa postura neste estado.")
        if self.combat_engine is not None and self.combat_state is not None:
            log = self.combat_engine.set_stance(self.combat_state, character_id, stance)
            self._sync_party_from_combat()
            return log
        character = next((c for c in self.run.party if c.id == character_id), None)
        if character is None:
            raise SessionError("Personagem desconhecido.")
        character.current_stance = stance
        return []

    def choose_card(self, character_id: str, card_id: str) -> None:
        """Takes one card from that character's pending 1-of-3 offer
        (docs/design/10-sistemas-de-build.md §3.7): a passive applies
        immediately and forever this run, an active one's ability joins
        the character's pool."""
        self._require_management()
        character = next((c for c in self.run.party if c.id == character_id), None)
        if character is None or card_id not in character.card_offer or card_id not in CARD_DEFS:
            raise SessionError("Essa Carta não está na oferta deste personagem.")
        self._grant_card(character, card_id)
        character.card_offer = []

    def skip_card(self, character_id: str) -> None:
        self._require_management()
        character = next((c for c in self.run.party if c.id == character_id), None)
        if character is None or not character.card_offer:
            raise SessionError("Este personagem não tem uma oferta de Carta pendente.")
        character.card_offer = []

    def shop_card(self) -> str:
        if self.current_room_type != "shop":
            raise SessionError("O nó atual não é um Vendedor.")
        return shop_card_for(self.run, self.shop_state(), CARD_DEFS, self.ruleset.abilities)

    def buy_card(self, character_id: str) -> None:
        self._require_management()
        card_id = self.shop_card()
        state = self.shop_state()
        character = next((c for c in self.run.party if c.id == character_id), None)
        if character is None:
            raise SessionError("Personagem desconhecido.")
        if state.card_sold:
            raise SessionError("Essa Carta já foi vendida.")
        price = CARD_PRICES_BY_RARITY[CARD_DEFS[card_id].rarity]
        if self.run.currency_earned < price:
            raise SessionError("Fragmentos insuficientes.")
        self.run.currency_earned -= price
        self._grant_card(character, card_id)
        state.card_sold = True

    # -- consumíveis (Fase 7) ------------------------------------------------

    def use_consumable(self, character_id: str, consumable_id: str) -> None:
        """Drinks one potion from the party pouch for one character, between
        fights (docs/design/14-estrutura-da-run.md §6). Mid-combat use is
        deferred -- it needs a combat-engine action, not a session call."""
        if self.run.is_complete:
            raise SessionError("A run já terminou.")
        character = next((c for c in self.run.party if c.id == character_id), None)
        consumable = CONSUMABLE_DEFS.get(consumable_id)
        if character is None or consumable is None or consumable_id not in self.run.consumables:
            raise SessionError("Esse consumível não está na bolsa do grupo.")
        if self.combat_state is not None:
            # mid-fight: a real combat action (14-estrutura-da-run.md §6),
            # validated and turn-spending inside the engine
            assert self.combat_engine is not None
            self.combat_engine.use_consumable(self.combat_state, character_id, consumable)
            self.run.consumables.remove(consumable_id)
            self._sync_party_from_combat()
            return
        self.run.consumables.remove(consumable_id)
        if consumable.teaches_ability is not None:
            # a Tomo (docs/design/10-sistemas-de-build.md §3.8): taught once,
            # permanent for the run, slotted if a slot is free
            self._grant_ability(character, consumable.teaches_ability)
        stats = character.computed_stats(self.ruleset)
        if consumable.heal_fraction > 0:
            character.current_hp = min(stats.max_hp, character.current_hp + consumable.heal_fraction * stats.max_hp)
        if consumable.resource_fraction > 0:
            character.current_resource = min(
                stats.max_resource, character.current_resource + consumable.resource_fraction * stats.max_resource
            )

    # -- vendedor / forja como nó (Fase 7) --------------------------------------

    def shop_state(self) -> ShopState:
        """The current Vendedor visit's mutable state, reset lazily whenever
        the run has moved to a different node since it was last touched."""
        if self.run.shop is None or self.run.shop.node_index != self.run.encounter_index:
            self.run.shop = ShopState(node_index=self.run.encounter_index)
        return self.run.shop

    def shop_stock(self) -> list[str]:
        if self.current_room_type != "shop":
            raise SessionError("O nó atual não é um Vendedor.")
        return shop_stock_for(self.run, self.shop_state(), CONSUMABLE_DEFS)

    def buy_consumable(self, slot: int) -> None:
        self._require_management()
        stock = self.shop_stock()
        state = self.shop_state()
        if not (0 <= slot < len(stock)) or slot in state.sold:
            raise SessionError("Esse item não está mais à venda.")
        if len(self.run.consumables) >= CONSUMABLE_SLOTS:
            raise SessionError("A bolsa do grupo está cheia.")
        price = CONSUMABLE_PRICES[stock[slot]]
        if self.run.currency_earned < price:
            raise SessionError("Fragmentos insuficientes.")
        self.run.currency_earned -= price
        self.run.consumables.append(stock[slot])
        state.sold.append(slot)

    def reroll_shop(self) -> None:
        self._require_management()
        self.shop_stock()  # validates the node
        if self.run.currency_earned < SHOP_REROLL_COST:
            raise SessionError("Fragmentos insuficientes.")
        self.run.currency_earned -= SHOP_REROLL_COST
        state = self.shop_state()
        state.rerolls += 1
        state.sold = []
        state.card_sold = False

    def leave_node(self) -> None:
        """Consumes a Vendedor or Forja de Campo node -- unlike rest/event,
        those are visited freely and only end when the party moves on."""
        self._require_management()
        if self.combat_state is not None:
            raise SessionError("Há um combate em andamento.")
        if self.current_room_type not in ("shop", "forge"):
            raise SessionError("O nó atual não é um Vendedor nem uma Forja de Campo.")
        self.run.shop = None
        self._advance_node()

    # -- talents -----------------------------------------------------------

    def allocate_talent(self, character_id: str, node_id: str) -> bool:
        if not self.can_manage_build:
            return False
        character = next((c for c in self.run.party if c.id == character_id), None)
        if character is None:
            return False
        tree = self.talent_trees.get(_talent_tree_id_for(character))
        if tree is None:
            return False
        state = character.build.talent_tree
        node = tree.nodes.get(node_id)
        if node is None or node.cost > state.points_available:
            return False
        if not tree.can_allocate(node_id, state.allocated):
            return False
        granted = self.ruleset.abilities.get(node.grants_ability) if node.grants_ability else None
        if granted is not None and is_sealed_source(
            character, archetype_weight=granted.archetype_weight,
            damage_elements=[e.damage_element for e in granted.effects if e.kind == EffectKind.DAMAGE],
        ):
            return False  # Selamentos: a node granting a sealed ability never appears as an option

        state.allocated.add(node_id)
        state.points_available -= node.cost
        recompute_passive_effects(character, tree)
        for ability_id in tree.granted_abilities_for(state.allocated):
            self._grant_ability(character, ability_id)
        return True

    # -- especialização (Fase 5) ----------------------------------------------

    def evolve_specialization(
        self, character_id: str, specialization_id: str, variants: EvolutionVariants | None = None,
    ) -> bool:
        """Revalidate the specialization and all proposed additions before changing the build."""
        if not self.can_manage_build:
            return False
        character = next((c for c in self.run.party if c.id == character_id), None)
        additions = variants or EvolutionVariants()
        if character is None or additions not in evolution_variant_choices(character):
            return False
        if specialization_id in STAGE2_DEFS:
            if not self._evolve_stage2(character, specialization_id):
                return False
        else:
            if character.specialization_id is not None or character.level < EVOLUTION_LEVEL:
                return False
            spec = SPECIALIZATION_DEFS.get(specialization_id)
            if spec is None or spec not in qualifying_specializations(character):
                return False
            character.specialization_id = specialization_id
        character.evolution_variants = merge_evolution_variants(character.evolution_variants, additions)
        recompute_passive_effects(character, self.talent_trees.get(_talent_tree_id_for(character)))
        return True

    def _evolve_stage2(self, character: Character, stage2_id: str) -> bool:
        """Estágio 2 (docs/design/05b-classes-roster.md §10): same shape as
        Stage 1 -- level 10, exactly once, re-validated against the
        character's *current* axes, never the ones they had at Stage 1."""
        if character.specialization_id is None or character.stage2_specialization_id is not None:
            return False
        if character.level < EVOLUTION_STAGE2_LEVEL:
            return False
        stage2 = STAGE2_DEFS.get(stage2_id)
        if stage2 is None or not qualifies_stage2(character, stage2):
            return False
        character.stage2_specialization_id = stage2_id
        return True

    # -- attributes ----------------------------------------------------------

    def allocate_attribute(self, character_id: str, attribute: Atributo) -> bool:
        if not self.can_manage_build:
            return False
        character = next((c for c in self.run.party if c.id == character_id), None)
        if character is None or character.attribute_points_available <= 0:
            return False
        character.attribute_points_available -= 1
        character.attribute_points[attribute] = character.attribute_points.get(attribute, 0) + 1
        tree = self.talent_trees.get(_talent_tree_id_for(character))
        recompute_passive_effects(character, tree)
        return True

    # -- equipamento (Fase 5c) -------------------------------------------------

    def equip_weapon(self, character_id: str, weapon_type_id: str) -> bool:
        """Equip a specific piece. A type ID selects the personal basic weapon."""
        if not self.can_manage_build:
            return False
        character = next((c for c in self.run.party if c.id == character_id), None)
        if character is None:
            return False
        if weapon_type_id in WEAPON_TYPE_DEFS:
            weapon_type_id = next((p.id for p in self.run.equipment_instances.values()
                                  if p.definition_id == f"basic_{weapon_type_id}" and p.owner_id == character_id), "")
        piece = self._available_piece(character, weapon_type_id)
        if piece is None:
            return False
        item = EQUIPMENT_DEFS[piece.definition_id]
        if item.slot != "weapon" or item.required_element in character.sealed_elements:
            return False
        character.equipped_weapon_type = item.weapon_type_id
        character.equipped_weapon_id = piece.id
        piece.owner_id = character_id
        sync_equipment(self.run, character)
        # Habilidades Exclusivas de Arma (10-sistemas-de-build.md §3.4):
        # granted on first equip and kept in the pool afterwards -- swapping
        # weapons only greys them out (CombatEngine.legal_abilities).
        for ability_id in WEAPON_TYPE_DEFS[item.weapon_type_id].granted_abilities:
            self._grant_ability(character, ability_id)
        tree = self.talent_trees.get(_talent_tree_id_for(character))
        recompute_passive_effects(character, tree)
        return True

    def socket_rune(self, character_id: str, rune_id: str, ability_id: str | None = None) -> bool:
        """``ability_id=None`` sockets into a body slot; otherwise the
        rune goes into that ability's own slot pool. Both pools
        have separate scopes: body bonuses are global, ability bonuses
        apply only to that ability. The rune must be in RunState.rune_inventory (08-itens-
        crafting.md: runes are drops) and leaves it while socketed."""
        if not self.can_manage_build:
            return False
        character = next((c for c in self.run.party if c.id == character_id), None)
        if character is None or rune_id not in RUNE_DEFS or rune_id not in self.run.rune_inventory:
            return False
        if ability_id is None:
            if rune_id in character.body_rune_slots or len(character.body_rune_slots) >= BODY_RUNE_SLOTS:
                return False
            character.body_rune_slots.append(rune_id)
        else:
            if ability_id not in character.abilities or not supports_ability_socket(RUNE_DEFS[rune_id]):
                return False
            socketed = character.ability_rune_slots.setdefault(ability_id, [])
            if rune_id in socketed or len(socketed) >= ABILITY_RUNE_SLOTS_PER_ABILITY:
                return False
            socketed.append(rune_id)
        self.run.rune_inventory.remove(rune_id)
        tree = self.talent_trees.get(_talent_tree_id_for(character))
        recompute_passive_effects(character, tree)
        return True

    def unsocket_rune(self, character_id: str, rune_id: str, ability_id: str | None = None) -> bool:
        if not self.can_manage_build:
            return False
        character = next((c for c in self.run.party if c.id == character_id), None)
        if character is None:
            return False
        if ability_id is None:
            if rune_id not in character.body_rune_slots:
                return False
            character.body_rune_slots.remove(rune_id)
        else:
            socketed = character.ability_rune_slots.get(ability_id, [])
            if rune_id not in socketed:
                return False
            socketed.remove(rune_id)
        self.run.rune_inventory.append(rune_id)
        tree = self.talent_trees.get(_talent_tree_id_for(character))
        recompute_passive_effects(character, tree)
        return True

    def combine_runes(self, rune_id: str) -> bool:
        """Forja de Campo (08-itens-crafting.md): "combinar 2 runas numa runa
        seguinte" -- two copies of the same rune in the inventory + Fragmentos
        + 1 material Comum become one tier-2 rune, still to be socketed."""
        if not self.can_use_forge:
            return False
        rune = RUNE_DEFS.get(rune_id)
        if rune is None or rune.upgrades_to is None or self.run.rune_inventory.count(rune_id) < 2:
            return False
        if self.run.currency_earned < COMBINE_RUNES_FRAGMENTOS_COST or self.run.materials.get(Rarity.COMUM, 0) < 1:
            return False
        self.run.currency_earned -= COMBINE_RUNES_FRAGMENTOS_COST
        self.run.materials[Rarity.COMUM] -= 1
        for _ in range(2):
            self.run.rune_inventory.remove(rune_id)
        self.run.rune_inventory.append(rune.upgrades_to)
        return True

    # -- equipamento: armadura/acessórios/encantamentos (Fase 6) ---------------

    def _available_piece(self, character, item_id):
        piece = self.run.equipment_instances.get(item_id)
        # Compatibility for scripts using a unique catalog ID. Network/UI use
        # exact instance IDs; an ambiguous catalog reference cannot select a copy.
        if piece is None and item_id in EQUIPMENT_DEFS:
            candidates = [p for p in self.run.equipment_instances.values()
                          if p.definition_id == item_id and p.owner_id in (None, character.id)]
            piece = candidates[0] if len(candidates) == 1 else None
        if piece is None or piece.id not in self.run.inventory or piece.owner_id not in (None, character.id):
            return None
        if not compatible_piece(piece, character):
            return None
        if any(piece.id in equipped_item_ids(c) for c in self.run.party if c.id != character.id):
            return None
        return piece

    def _refresh_equipment(self, character):
        sync_equipment(self.run, character)
        recompute_passive_effects(character, self.talent_trees.get(_talent_tree_id_for(character)))

    def equip_armor(self, character_id: str, slot: str, item_id: str) -> bool:
        if not self.can_manage_build:
            return False
        character = next((c for c in self.run.party if c.id == character_id), None)
        piece = self._available_piece(character, item_id) if character else None
        if piece is None or slot not in ("head", "body", "legs"):
            return False
        item = EQUIPMENT_DEFS[piece.definition_id]
        if item.slot != slot or item.required_element in character.sealed_elements:
            return False
        character.equipped_armor[slot] = piece.id
        piece.owner_id = character_id
        self._refresh_equipment(character)
        return True

    def unequip_armor(self, character_id: str, slot: str) -> bool:
        if not self.can_manage_build:
            return False
        character = next((c for c in self.run.party if c.id == character_id), None)
        if character is None or slot not in character.equipped_armor:
            return False
        del character.equipped_armor[slot]
        self._refresh_equipment(character)
        return True

    def equip_accessory(self, character_id: str, item_id: str) -> bool:
        if not self.can_manage_build:
            return False
        character = next((c for c in self.run.party if c.id == character_id), None)
        piece = self._available_piece(character, item_id) if character else None
        if piece is None or EQUIPMENT_DEFS[piece.definition_id].slot != "accessory":
            return False
        if piece.id in equipped_item_ids(character) or len(character.equipped_accessories) >= ACCESSORY_SLOTS:
            return False
        character.equipped_accessories.append(piece.id)
        piece.owner_id = character_id
        self._refresh_equipment(character)
        return True

    def _has_free_equipment_copy(self, item_id: str) -> bool:
        return item_id in self.run.inventory and not any(item_id in equipped_item_ids(c) for c in self.run.party)

    def unequip_accessory(self, character_id: str, item_id: str) -> bool:
        if not self.can_manage_build:
            return False
        character = next((c for c in self.run.party if c.id == character_id), None)
        piece = self._available_piece(character, item_id) if character else None
        if piece is None or piece.id not in character.equipped_accessories:
            return False
        character.equipped_accessories.remove(piece.id)
        self._refresh_equipment(character)
        return True

    def transfer_equipment(self, character_id: str, recipient_id: str, item_id: str) -> bool:
        """The sender gives their piece, unequipping it atomically if necessary.

        Receiving never replaces the recipient's build. The normal ownership
        boundary authenticates character_id in all three clients/the server.
        """
        if not self.can_manage_build or character_id == recipient_id:
            return False
        sender = next((c for c in self.run.party if c.id == character_id), None)
        recipient = next((c for c in self.run.party if c.id == recipient_id), None)
        piece = self.run.equipment_instances.get(item_id)
        if sender is None or recipient is None or piece is None or piece.owner_id != character_id:
            return False
        if piece.id not in self.run.inventory:
            return False
        item = EQUIPMENT_DEFS[piece.definition_id]
        if not compatible_piece(piece, recipient):
            return False
        sender.equipped_armor = {s: i for s, i in sender.equipped_armor.items() if i != item_id}
        sender.equipped_accessories = [i for i in sender.equipped_accessories if i != item_id]
        if sender.equipped_weapon_id == item_id:
            sender.equipped_weapon_id = None
            sender.equipped_weapon_type = None
        piece.owner_id = recipient_id
        self._refresh_equipment(sender)
        return True

    def socket_enchantment(self, character_id: str, item_id: str, enchantment_id: str) -> bool:
        """Field Forge engraving service: 10 fragments and one matching material."""
        if not self.can_use_forge:
            return False
        character = next((c for c in self.run.party if c.id == character_id), None)
        piece = self._available_piece(character, item_id) if character else None
        if piece is None or piece.id not in equipped_item_ids(character) or enchantment_id not in enchantment_choices(character):
            return False
        if enchantment_id in piece.enchantments or len(piece.enchantments) >= ENCHANTMENT_SLOTS_BY_RARITY[piece.rarity]:
            return False
        if self.run.currency_earned < REROLL_ENCHANTMENT_FRAGMENTOS_COST or self.run.materials.get(piece.rarity, 0) < 1:
            return False
        self.run.currency_earned -= REROLL_ENCHANTMENT_FRAGMENTOS_COST
        self.run.materials[piece.rarity] -= 1
        piece.enchantments.append(enchantment_id)
        self.run.forge_operations += 1
        self._refresh_equipment(character)
        return True

    def reroll_enchantment(self, character_id: str, item_id: str, slot_index: int) -> bool:
        if not self.can_use_forge:
            return False
        character = next((c for c in self.run.party if c.id == character_id), None)
        piece = self._available_piece(character, item_id) if character else None
        if piece is None or piece.id not in equipped_item_ids(character):
            return False
        socketed = piece.enchantments
        if not (0 <= slot_index < len(socketed)):
            return False
        if self.run.currency_earned < REROLL_ENCHANTMENT_FRAGMENTOS_COST or self.run.materials.get(piece.rarity, 0) < 1:
            return False
        candidates = [eid for eid in enchantment_choices(character) if eid not in socketed]
        if not candidates:
            return False
        rng = random.Random(self.run.seed * 13_000_003 + self.run.forge_operations)
        result = rng.choice(candidates)
        self.run.currency_earned -= REROLL_ENCHANTMENT_FRAGMENTOS_COST
        self.run.materials[piece.rarity] -= 1
        socketed[slot_index] = result
        self.run.forge_operations += 1
        self._refresh_equipment(character)
        return True

    # -- run lifecycle -------------------------------------------------------

    @property
    def run_is_over(self) -> bool:
        if self.run.is_complete:
            return True
        if self.combat_state is not None and self.combat_state.victory is False:
            return True
        return self.is_dungeon_cleared

    @property
    def run_was_victorious(self) -> bool:
        if self.run.is_complete:
            return self.run.victory is True
        if self.combat_state is not None and self.combat_state.victory is False:
            return False
        return self.is_dungeon_cleared

    def finalize_run(self) -> RunSummary:
        """Computes the run's outcome. Deliberately does not touch any
        MetaProgressionState -- banking currency is a per-player concern
        (each connected player banks the same reward to their own local
        save), handled by the caller (see WyrdfallApp.bank_run_reward)."""
        if self.run.is_complete or not self.run_is_over:
            raise SessionError("A run não pode ser finalizada neste estado.")
        return self._finish_run(self.run_was_victorious)

    def abandon_run(self) -> RunSummary:
        """Voluntary defeat preserves only progress already earned."""
        if self._final_summary is not None:
            return self._final_summary
        if self.run.is_complete:
            raise SessionError("A run já foi finalizada.")
        return self._finish_run(False)

    def _finish_run(self, victory: bool) -> RunSummary:
        self._strip_terrain()
        floor_reached = min(self.run.encounter_index, len(self.dungeon.encounters))
        summary = RunSummary(
            run_id=self.run.run_id,
            class_id=self.run.party[0].class_id if self.run.party else "unknown",
            floor_reached=floor_reached,
            victory=victory,
        )
        self.run.is_complete = True
        self.run.victory = victory
        self.combat_engine = None
        self.combat_state = None
        self._final_summary = summary
        return summary

    def resolve_continue_after_combat(self) -> RunSummary | None:
        """What happens when 'Continue' is pressed after an encounter ends:
        victory banks the reward and either returns to the dungeon (None)
        or, if that was the last encounter, finalizes the run; defeat
        finalizes it immediately. The one place this branching lives --
        both the local UI and the network host call it identically."""
        if self.combat_state is None:
            raise SessionError("No finished encounter to continue from.")
        if not self.combat_state.is_over:
            raise SessionError("O combate ainda não terminou.")
        if self.combat_state.victory:
            self.collect_victory_reward_and_advance()
            if self.is_dungeon_cleared:
                return self.finalize_run()
            return None
        return self.finalize_run()


def _talent_tree_id_for(character: Character) -> str | None:
    """The tree a character allocates on right now: the branch of its
    latest evolution grafted onto ITS OWN base archetype's nodes (every
    branch exists on all four bases -- content/specializations.py::
    _rebase_fixed_trees), falling back to the authored tree id."""
    from wyrdfall.domain.content import CLASS_DEFS, TALENT_TREES

    def own_base(spec_id: str, fallback: str | None) -> str | None:
        candidate = f"{character.base_archetype.value}_{spec_id}_path"
        return candidate if candidate in TALENT_TREES else fallback

    if character.stage2_specialization_id is not None:
        stage2 = STAGE2_DEFS.get(character.stage2_specialization_id)
        if stage2 is not None and (stage2.hybrid_branch or stage2.granted_tree_id is not None):
            return own_base(stage2.id, stage2.granted_tree_id)
    if character.specialization_id is not None:
        spec = SPECIALIZATION_DEFS.get(character.specialization_id)
        if spec is not None and (spec.hybrid_branch or spec.granted_tree_id is not None):
            return own_base(spec.id, spec.granted_tree_id)
    class_def = CLASS_DEFS.get(character.class_id)
    return class_def.talent_tree_id if class_def else None
