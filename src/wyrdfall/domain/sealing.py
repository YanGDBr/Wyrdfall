"""Selamentos (docs/design/10-sistemas-de-build.md §7): the central
"pureza estrita" check every offer point calls, and the bonus curve.

- is_sealed_source: True when ANY archetype weight of a source touches a
  sealed archetype, or its damage element is sealed -- not just the
  primary one ("qualquer intersecção").
- seal_modifiers_for: +10% for the 1st sealed archetype, +15% for the
  2nd, +25% for the 3rd (cumulative, on damage); +5% damage per sealed
  element, capped at +25% ("a partir do 5º, o ganho marginal para").
  Both land as PHYSICAL/ELEMENTAL_DAMAGE_PERCENT modifiers -- the
  engine's existing "more damage" channel, no new stat.
"""

from __future__ import annotations

from collections.abc import Iterable

from wyrdfall.domain.character import Character
from wyrdfall.domain.models import Archetype, DamageElement, Modifier, ModifierKind, Stat

_ARCHETYPE_SEAL_STEPS = [0.10, 0.15, 0.25]
_ELEMENT_SEAL_STEP = 0.05
_ELEMENT_SEAL_CAP = 0.25


def is_sealed_source(
    character: Character,
    *,
    archetype_weight: dict[Archetype, float] | None = None,
    damage_elements: Iterable[DamageElement] = (),
) -> bool:
    if archetype_weight and any(a in character.sealed_archetypes for a, w in archetype_weight.items() if w > 0):
        return True
    return any(e in character.sealed_elements and e != DamageElement.PHYSICAL for e in damage_elements)


def archetype_seal_bonus(sealed_count: int) -> float:
    return sum(_ARCHETYPE_SEAL_STEPS[: max(0, min(sealed_count, len(_ARCHETYPE_SEAL_STEPS)))])


def element_seal_bonus(sealed_count: int) -> float:
    return min(_ELEMENT_SEAL_CAP, _ELEMENT_SEAL_STEP * max(0, sealed_count))


def seal_modifiers_for(character: Character) -> list[Modifier]:
    out: list[Modifier] = []
    archetype_bonus = archetype_seal_bonus(len(character.sealed_archetypes))
    if archetype_bonus > 0:
        out.append(Modifier(stat=Stat.PHYSICAL_DAMAGE_PERCENT, kind=ModifierKind.FLAT, value=archetype_bonus, source="seal_archetypes"))
        out.append(Modifier(stat=Stat.ELEMENTAL_DAMAGE_PERCENT, kind=ModifierKind.FLAT, value=archetype_bonus, source="seal_archetypes"))
    element_bonus = element_seal_bonus(len(character.sealed_elements))
    if element_bonus > 0:
        out.append(Modifier(stat=Stat.ELEMENTAL_DAMAGE_PERCENT, kind=ModifierKind.FLAT, value=element_bonus, source="seal_elements"))
    return out
