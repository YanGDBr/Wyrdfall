"""Ferreiro (docs/design/08-itens-crafting.md "Crafting em duas camadas"):
the permanent, hub-side layer -- recipes paid with the materials that
persist between runs (MetaProgressionState.materials) plus Ecos. Two
kinds of result:

- equipamento "de partida": an EquipmentDef every future run starts with
  in its inventory ("se o jogador quiser equipá-los" -- never auto-
  equipped);
- Construir o Construto: the race's unlock (04-racas.md), literally a
  recipe using Lendário material -- the one direct hook between races
  and crafting.

Crafting runes is deliberately absent: runes aren't scarce yet (any
RUNE_DEFS entry can be socketed in a run), so a crafted rune would mean
nothing until a rune inventory exists.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from wyrdfall.domain.runes import RUNE_DEFS
from wyrdfall.domain.items import EQUIPMENT_DEFS, Rarity


class RecipeDef(BaseModel):
    id: str
    name: str
    description: str
    cost_ecos: int
    cost_materials: dict[Rarity, int] = Field(default_factory=dict)
    grants_item_id: str | None = None
    unlocks_race: str | None = None
    # "craftar itens/runas novas do zero": a rune every future run starts with
    grants_rune_id: str | None = None


def _gear(item_id: str, rarity: Rarity, count: int, ecos: int) -> RecipeDef:
    item = EQUIPMENT_DEFS[item_id]
    return RecipeDef(
        id=f"craft_{item_id}", name=item.name,
        description=f"Equipamento de partida: toda run futura começa com {item.name} no inventário.",
        cost_ecos=ecos, cost_materials={rarity: count}, grants_item_id=item_id,
    )


def _rune(rune_id: str, ecos: int) -> RecipeDef:
    rune = RUNE_DEFS[rune_id]
    return RecipeDef(
        id=f"craft_{rune_id}", name=rune.name,
        description=f"Runa de partida: toda run futura começa com {rune.name} no inventário de runas.",
        cost_ecos=ecos, cost_materials={Rarity.COMUM: 1}, grants_rune_id=rune_id,
    )


RECIPE_DEFS: dict[str, RecipeDef] = {
    "craft_traveler_cap": _gear("traveler_cap", Rarity.COMUM, 2, 10),
    "craft_traveler_tunic": _gear("traveler_tunic", Rarity.COMUM, 2, 10),
    "craft_traveler_boots": _gear("traveler_boots", Rarity.COMUM, 2, 10),
    "craft_guardian_helm": _gear("guardian_helm", Rarity.RARO, 2, 25),
    "craft_guardian_chest": _gear("guardian_chest", Rarity.RARO, 2, 25),
    "craft_guardian_greaves": _gear("guardian_greaves", Rarity.RARO, 2, 25),
    "craft_rune_might": _rune("rune_might", 8),
    "craft_rune_bulwark": _rune("rune_bulwark", 8),
    "craft_rune_focus": _rune("rune_focus", 12),
    "construir_construto": RecipeDef(
        id="construir_construto", name="Construir o Construto",
        description="Monta um corpo inorgânico com material Lendário -- desbloqueia a raça Construto.",
        cost_ecos=40, cost_materials={Rarity.LENDARIO: 1, Rarity.RARO: 2}, unlocks_race="construto",
    ),
}
