"""Per-run equipment/material drops (docs/design/08-itens-crafting.md).
A pure function, same shape as domain/dungeon.py::difficulty_multiplier
-- the caller (engine/session.py::collect_victory_reward_and_advance)
applies the result to RunState.inventory/materials.

Atributo.LUCK already scales CRIT_MULT/PROC_CHANCE_PERCENT elsewhere
(domain/attributes.py), but "chance to find loot" isn't a combat stat,
so this reads attribute_points[LUCK] directly rather than adding a new
Stat/Modifier for it. First-guess balance numbers, like every other
rate in this corpus -- not final.
"""

from __future__ import annotations

import random

from wyrdfall.domain.consumables import ConsumableDef
from wyrdfall.domain.dungeon import EncounterDef
from wyrdfall.domain.items import EQUIPMENT_DEFS, Rarity

_BASE_DROP_CHANCE = 0.35
_DROP_CHANCE_PER_FLOOR = 0.03
_DROP_CHANCE_PER_LUCK_POINT = 0.02

_RARITY_WEIGHTS: dict[Rarity, float] = {
    Rarity.COMUM: 0.65,
    Rarity.RARO: 0.30,
    Rarity.LENDARIO: 0.05,
}


def roll_encounter_drops(
    encounter: EncounterDef, floor_index: int, luck_points: int, rng: random.Random,
) -> tuple[list[str], dict[Rarity, int]]:
    """Returns (found EquipmentDef ids, material counts by rarity) for one
    won encounter. A boss encounter always drops at least one item and
    an extra material; a normal encounter rolls once against a chance
    that scales with dungeon depth and the party's invested Sorte."""
    chance = _BASE_DROP_CHANCE + _DROP_CHANCE_PER_FLOOR * floor_index + _DROP_CHANCE_PER_LUCK_POINT * luck_points
    if not encounter.is_boss and rng.random() >= min(chance, 1.0):
        return [], {}

    rarity = _roll_rarity(rng)
    candidates = [item.id for item in EQUIPMENT_DEFS.values() if item.rarity == rarity and item.random_drop]
    item_id = rng.choice(candidates) if candidates else rng.choice(list(EQUIPMENT_DEFS))
    materials = {rarity: 2 if encounter.is_boss else 1}
    return [item_id], materials


BOSS_REWARDS = {"hollow_knight": "hollow_aegis", "ashkarion": "ashkarion_staff", "viuva_de_gelo": "widow_bow"}
BOSS_REWARDS.update({
    "voltharion": "storm_lens", "maremoto": "tidal_mantle", "terrakon": "mountain_heart",
    "zephyra": "last_gale", "mae_putrida": "rot_diadem", "solyth": "fallen_halo",
    "o_inominavel": "veil_shroud", "nyxelle": "fractured_page", "tecela_desfeita": "destiny_thread",
})


def boss_reward_for(encounter, party) -> str | None:
    if not encounter.is_boss:
        return None
    for enemy_id in encounter.enemy_ids:
        if enemy_id not in BOSS_REWARDS:
            continue
        item_id = BOSS_REWARDS[enemy_id]
        item = EQUIPMENT_DEFS[item_id]
        if any(item.required_element not in hero.sealed_elements for hero in party):
            return item_id
        # Same rare tier and enchantment budget, useful without an elemental kit.
        return "crown_of_ages" if item.rarity == Rarity.LENDARIO else "amulet_of_vigor"
    return None


_BASE_CONSUMABLE_CHANCE = 0.25
_CONSUMABLE_CHANCE_PER_LUCK_POINT = 0.02


def roll_consumable_drop(
    encounter: EncounterDef, luck_points: int, rng: random.Random, pool: dict[str, ConsumableDef],
) -> str | None:
    """One ConsumableDef id found on a won encounter, or None. A boss
    always drops one; a normal encounter rolls once against a chance
    that scales with invested Sorte. Takes RunState.consumable_rng() --
    never loot_rng -- so it can't perturb the equipment roll above."""
    if not encounter.is_boss and rng.random() >= min(_BASE_CONSUMABLE_CHANCE + _CONSUMABLE_CHANCE_PER_LUCK_POINT * luck_points, 1.0):
        return None
    return rng.choice(sorted(pool))


_BASE_RUNE_CHANCE = 0.30
_RUNE_CHANCE_PER_LUCK_POINT = 0.02


def roll_rune_drop(encounter: EncounterDef, luck_points: int, rng: random.Random, pool: list[str]) -> str | None:
    """One RuneDef id found on a won encounter, or None (08-itens-crafting.md
    "Drops: Runas"). A boss always drops one. Takes RunState.rune_rng()."""
    if not pool:
        return None
    if not encounter.is_boss and rng.random() >= min(_BASE_RUNE_CHANCE + _RUNE_CHANCE_PER_LUCK_POINT * luck_points, 1.0):
        return None
    return rng.choice(sorted(pool))


def _roll_rarity(rng: random.Random) -> Rarity:
    roll = rng.random()
    cumulative = 0.0
    for rarity, weight in _RARITY_WEIGHTS.items():
        cumulative += weight
        if roll < cumulative:
            return rarity
    return Rarity.COMUM
