"""Active Ability Slots and Posturas (docs/design/10-sistemas-de-build.md
§4 and §3.9).

Slots are "a única coisa que trava o que você pode *usar ao mesmo
tempo*": a character's ability pool (talents, kits, Cartas) can grow
without limit, but only the abilities in Character.equipped_abilities
-- plus any Ability marked ``universal`` (Defender) -- are offered in
combat. Posturas are a free tactical toggle, switchable once per turn.
"""

from __future__ import annotations

from typing import Literal

ACTIVE_SLOTS_BASE = 4
ACTIVE_SLOT_LEVELS = (3, 6, 9, 12)
ACTIVE_SLOTS_CAP = 8
LEGACY_SLOT_LEVEL = 6


def active_ability_slots(level: int, *, legacy_slot: bool = False) -> int:
    progression = sum(1 for milestone in ACTIVE_SLOT_LEVELS if level >= milestone)
    bonus = int(legacy_slot and level >= LEGACY_SLOT_LEVEL)
    return min(ACTIVE_SLOTS_CAP, ACTIVE_SLOTS_BASE + progression + bonus)


Stance = Literal["none", "offensive", "evasive", "precise"]
STANCES: tuple[Stance, ...] = ("offensive", "evasive", "precise")
STANCE_NAMES: dict[str, str] = {
    "none": "Nenhuma",
    "offensive": "Ofensiva",
    "evasive": "Evasiva",
    "precise": "Precisa",
}
# First-guess numbers from the doc's own table ("números de partida").
STANCE_DAMAGE_BONUS = 0.15  # Ofensiva: +15% dealt AND +15% taken
STANCE_DODGE_BONUS = 0.15  # Evasiva
STANCE_PRECISION = 0.15  # Precisa: the target's effective Esquiva against you
