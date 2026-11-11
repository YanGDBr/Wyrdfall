from __future__ import annotations

import random

from pydantic import BaseModel, Field, model_validator
from typing import Literal
from wyrdfall.domain.gear import EquipmentInstance

from wyrdfall.domain.character import Character
from wyrdfall.domain.items import Rarity


class ShopState(BaseModel):
    """The mutable part of a Vendedor visit (domain/shop.py computes the
    stock itself from these). Reset whenever the run reaches a new node."""

    node_index: int
    rerolls: int = 0
    sold: list[int] = Field(default_factory=list)  # consumable stock slots already bought
    card_sold: bool = False


class RunState(BaseModel):
    run_id: str
    seed: int
    dungeon_id: str
    party: list[Character]
    encounter_index: int = 0
    currency_earned: int = 0
    is_complete: bool = False
    victory: bool | None = None
    bosses_defeated: int = 0
    # Missões da Guilda (domain/guild_missions.py): which Área bosses fell
    # this run (encounter ids), banked into the permanent counter.
    defeated_boss_ids: list[str] = Field(default_factory=list)
    # Evolução de raça settled outside a combat log (after a boss) -- shown
    # on the Dungeon screen; combat-time evolutions go in the combat log.
    race_evolution_log: list[str] = Field(default_factory=list)
    # Races an Evento unlocked this run (Fada's Portal Feérico, 04-racas.md);
    # applied to the save at bank time like every other meta unlock.
    race_unlocks: list[str] = Field(default_factory=list)
    race_unlocks_by_character: dict[str, set[str]] = Field(default_factory=dict)
    # who already "Abraçou a Morte" this run (Wyrd counted once per character)
    wyrd_embraces: list[str] = Field(default_factory=list)
    parried_successfully: bool = False
    had_flawless_encounter: bool = False
    # P6: instance IDs, including equipped pieces. Catalog IDs are migrated
    # only while reading old saves. The registry is the canonical item state.
    inventory: list[str] = Field(default_factory=list)
    equipment_version: Literal[1] = 1
    equipment_instances: dict[str, EquipmentInstance] = Field(default_factory=dict)
    equipment_sequence: int = 0
    equipment_initialized_for: set[str] = Field(default_factory=set)

    # Unsocketed RuneDef ids the party owns (08-itens-crafting.md: runes are
    # drops; socketing takes one out of here, unsocketing puts it back).
    rune_inventory: list[str] = Field(default_factory=list)
    # Field Forge spends this balance; only the remainder is banked to the Guild.
    materials: dict[Rarity, int] = Field(default_factory=dict)
    # Fase 7 -- the party's potion pouch (ConsumableDef ids, repeats
    # allowed), capped at domain/consumables.py::CONSUMABLE_SLOTS.
    consumables: list[str] = Field(default_factory=list)
    shop: ShopState | None = None
    # Fase 9 -- Companheiros (domain/companions.py), kept apart from
    # party on purpose: they persist between combats like party members,
    # but never take part in anything that iterates the party (level-ups,
    # Cartas, consumables, difficulty by party size, local character ids).
    companions: list[Character] = Field(default_factory=list)
    # Contratos de Run (domain/contracts.py): offered once at run start,
    # accepted or declined on the first dungeon screen, checked after each
    # won encounter; Ecos are banked with the run's reward.
    contract_offer: list[str] = Field(default_factory=list)
    accepted_contracts: list[str] = Field(default_factory=list)
    completed_contracts: list[str] = Field(default_factory=list)
    contract_ecos: int = 0
    # Fase 8 -- Pactos do Wyrd equipped for this run (lobby-wide), the
    # Ascensão level chosen for it, and the Medidor do Wyrd (domain/wyrd.py).
    active_pacts: list[str] = Field(default_factory=list)
    ascension_level: int = 0
    wyrd_meter: float = 0.0
    forge_operations: int = 0
    discovered_enemy_ids: set[str] = Field(default_factory=set)

    @model_validator(mode="after")
    def migrate_equipment(self):
        from wyrdfall.domain.inventory import migrate_inventory
        migrate_inventory(self)
        return self

    def encounter_rng(self) -> random.Random:
        """A fresh, deterministic RNG per encounter, derived from the run
        seed -- keeps the run reproducible without reusing one stream across
        every fight."""
        return random.Random(self.seed * 1_000_003 + self.encounter_index)

    def loot_rng(self) -> random.Random:
        """A separate stream from encounter_rng (different multiplier), so
        a loot roll never reproduces the same draw sequence combat's own
        rng already started with for this encounter_index."""
        return random.Random(self.seed * 2_000_003 + self.encounter_index)

    def blessing_rng(self) -> random.Random:
        """One draw per node for the Elite room-reward Bênção."""
        return random.Random(self.seed * 9_000_003 + self.encounter_index)

    def card_rng(self, character_index: int) -> random.Random:
        """One stream per party member per node, so each character's
        1-of-3 Carta offer is its own deterministic draw."""
        return random.Random(self.seed * 7_000_003 + self.encounter_index + character_index * 104_729)

    def rune_rng(self) -> random.Random:
        """Rune drops on their own stream, like consumables."""
        return random.Random(self.seed * 11_000_003 + self.encounter_index)

    def consumable_rng(self) -> random.Random:
        """Its own stream so adding potion drops never reshuffles the
        equipment/material draws loot_rng already produces for a seed."""
        return random.Random(self.seed * 4_000_003 + self.encounter_index)
