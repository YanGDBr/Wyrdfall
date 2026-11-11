"""Weapon type damage scaling (docs/design/10-sistemas-de-build.md §2):
the equipped weapon isn't a second damage source, it's a percentage
amplifier on top of whatever any ability would already deal, driven by
invested attributes. Each player starts with a basic instance of every type.
Found instances add item modifiers without replacing type scaling or its kit.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from wyrdfall.domain.attributes import Atributo
from wyrdfall.domain.character import Character
from wyrdfall.domain.models import Modifier, ModifierKind, Stat

# First-guess balance rate, like every other conversion rate in this
# corpus -- converts the weapon's weighted attribute investment into a
# WEAPON_DAMAGE_PERCENT magnitude.
_WEAPON_SCALING_RATE = 0.01


class WeaponTypeDef(BaseModel):
    id: str
    name: str
    scaling: dict[Atributo, float] = Field(default_factory=dict)
    # Habilidades Exclusivas de Arma (docs/design/10-sistemas-de-build.md
    # §3.4): granted to the pool on equip (engine/session.py::equip_weapon)
    # and only *legal* while this weapon type is equipped -- each carries
    # Ability.required_weapon_type. They carry the weapon's natural
    # archetype weight, which is what lets a character's Afinidade drift
    # across archetypes (§5: "a arma entra no cálculo assim que equipada")
    # -- the channel that makes the hybrid Especializações reachable.
    granted_abilities: list[str] = Field(default_factory=list)


WEAPON_TYPE_DEFS: dict[str, WeaponTypeDef] = {
    "sword_one_hand": WeaponTypeDef(
        id="sword_one_hand", name="Espada (uma mão)",
        scaling={Atributo.STRENGTH: 0.8, Atributo.DEXTERITY: 0.2},
        granted_abilities=["weapon_thrust"],
    ),
    "greatsword": WeaponTypeDef(
        id="greatsword", name="Espada grande (duas mãos)",
        scaling={Atributo.STRENGTH: 1.0},
        granted_abilities=["weapon_cleave"],
    ),
    "dagger": WeaponTypeDef(
        id="dagger", name="Adaga",
        scaling={Atributo.DEXTERITY: 0.8, Atributo.STRENGTH: 0.2},
        granted_abilities=["weapon_backstab"],
    ),
    "spear": WeaponTypeDef(
        id="spear", name="Lança",
        scaling={Atributo.STRENGTH: 0.5, Atributo.DEXTERITY: 0.5},
        granted_abilities=["weapon_charge"],
    ),
    "bow": WeaponTypeDef(
        id="bow", name="Arco",
        scaling={Atributo.STRENGTH: 0.4, Atributo.DEXTERITY: 0.6},
        granted_abilities=["weapon_shot"],
    ),
    "firearm": WeaponTypeDef(
        id="firearm", name="Arma de fogo",
        scaling={Atributo.DEXTERITY: 0.5, Atributo.LUCK: 0.5},
        granted_abilities=["weapon_fire"],
    ),
    "staff": WeaponTypeDef(
        id="staff", name="Cajado",
        scaling={Atributo.INTELLIGENCE: 0.7, Atributo.WISDOM: 0.3},
        granted_abilities=["weapon_spark"],
    ),
    "grimoire": WeaponTypeDef(
        id="grimoire", name="Grimório",
        scaling={Atributo.INTELLIGENCE: 0.5, Atributo.WISDOM: 0.5},
        granted_abilities=["weapon_glyph"],
    ),
    "shield": WeaponTypeDef(
        id="shield", name="Escudo",
        scaling={Atributo.CONSTITUTION: 1.0},
        granted_abilities=["weapon_bash"],
    ),
    "unarmed": WeaponTypeDef(
        id="unarmed", name="Punhos/desarmado",
        scaling={Atributo.STRENGTH: 0.5, Atributo.DEXTERITY: 0.5},
        granted_abilities=["weapon_punch"],
    ),
}


def weapon_modifiers_for(character: Character) -> list[Modifier]:
    if character.equipped_weapon_type is None:
        return []
    weapon = WEAPON_TYPE_DEFS.get(character.equipped_weapon_type)
    if weapon is None:
        return []
    weighted_points = sum(
        weight * character.attribute_points.get(attribute, 0) for attribute, weight in weapon.scaling.items()
    )
    if weighted_points <= 0:
        return []
    # FLAT, not MORE: WEAPON_DAMAGE_PERCENT defaults to 0.0, and
    # compute_stats multiplies a MORE modifier's (1+value) factor onto
    # the *running value* -- against a zero base that always resolves to
    # zero (the same zero-base pitfall domain/attributes.py's own docstring
    # already flags for PERCENT-kind modifiers on these stats). FLAT and
    # MORE are behaviorally identical here anyway, since exactly one
    # weapon is ever equipped at a time -- there's nothing else to stack
    # multiplicatively against.
    return [
        Modifier(
            stat=Stat.WEAPON_DAMAGE_PERCENT,
            kind=ModifierKind.FLAT,
            value=weighted_points * _WEAPON_SCALING_RATE,
            source=f"weapon_{weapon.id}",
        )
    ]
