"""Attribute point-buy system (docs/design/03-atributos.md): 6 attributes,
each feeding 3 stats at different rates. Unlike TalentTree there is no
prerequisite graph -- just a flat dict of points invested -- so this stays
a plain data-in/Modifiers-out function, tested the same way
TalentTree.modifiers_for is tested.
"""

from __future__ import annotations

from enum import Enum

from wyrdfall.domain.models import Modifier, ModifierKind, Stat


class Atributo(str, Enum):
    STRENGTH = "strength"
    DEXTERITY = "dexterity"
    CONSTITUTION = "constitution"
    INTELLIGENCE = "intelligence"
    WISDOM = "wisdom"
    LUCK = "luck"


ATTRIBUTE_NAMES: dict[Atributo, str] = {
    Atributo.STRENGTH: "Força",
    Atributo.DEXTERITY: "Destreza",
    Atributo.CONSTITUTION: "Constituição",
    Atributo.INTELLIGENCE: "Inteligência",
    Atributo.WISDOM: "Sabedoria",
    Atributo.LUCK: "Sorte",
}

# (attribute, stat, rate per point). Every rate is a FLAT addition to the
# stat's own value -- these stats (e.g. PHYSICAL_DAMAGE_PERCENT) default to
# 0.0, so a PERCENT-kind modifier on them would always resolve to zero.
# Sorte's drop-rate tertiary is left out on purpose: no loot/crafting system
# exists yet to hook it into (deferred, not silently dropped).
_RATES: list[tuple[Atributo, Stat, float]] = [
    (Atributo.STRENGTH, Stat.PHYSICAL_DAMAGE_PERCENT, 0.02),
    (Atributo.STRENGTH, Stat.MAX_HP, 3.0),
    (Atributo.STRENGTH, Stat.ARMOR_PENETRATION_PERCENT, 0.005),
    (Atributo.DEXTERITY, Stat.CRIT_CHANCE, 0.004),
    (Atributo.DEXTERITY, Stat.DODGE_CHANCE, 0.003),
    (Atributo.DEXTERITY, Stat.SPEED, 0.2),
    (Atributo.CONSTITUTION, Stat.MAX_HP, 6.0),
    (Atributo.CONSTITUTION, Stat.STATUS_RESIST, 0.005),
    (Atributo.CONSTITUTION, Stat.DEFENSE, 0.3),
    (Atributo.INTELLIGENCE, Stat.ELEMENTAL_DAMAGE_PERCENT, 0.025),
    (Atributo.INTELLIGENCE, Stat.MAX_RESOURCE, 1.0),
    (Atributo.INTELLIGENCE, Stat.GENERAL_ELEMENTAL_RESIST, 0.003),
    (Atributo.WISDOM, Stat.RESOURCE_REGEN_PER_TURN, 0.3),
    (Atributo.WISDOM, Stat.HEALING_DONE_PERCENT, 0.02),
    (Atributo.WISDOM, Stat.CRIT_RESIST, 0.003),
    (Atributo.LUCK, Stat.CRIT_MULT, 0.015),
    (Atributo.LUCK, Stat.PROC_CHANCE_PERCENT, 0.005),
]


def attribute_modifiers_for(points: dict[Atributo, int]) -> list[Modifier]:
    """``points`` is usually player-invested (always >= 0), but races
    (domain/races.py) reuse this same rate table for attribute bonuses
    that can be *negative* -- so only an exact zero is skipped, never a
    negative value, or a race's penalty would silently vanish."""
    modifiers: list[Modifier] = []
    for attribute, stat, rate in _RATES:
        invested = points.get(attribute, 0)
        if invested == 0:
            continue
        modifiers.append(
            Modifier(stat=stat, kind=ModifierKind.FLAT, value=rate * invested, source=f"attribute_{attribute.value}")
        )
    return modifiers
