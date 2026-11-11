"""Consumíveis (docs/design/08-itens-crafting.md, 14-estrutura-da-run.md
§6): single-use potions that heal or restore resource "na hora". Found
as drops (and, once the Vendedor exists, bought); kept in a small
party-wide pouch."""

from __future__ import annotations

from pydantic import BaseModel

# docs/design/14-estrutura-da-run.md §6's "carga pequena (proposta: 3
# no inventário)" -- a first-guess cap like every other number there.
CONSUMABLE_SLOTS = 3


class ConsumableDef(BaseModel):
    id: str
    name: str
    description: str
    heal_fraction: float = 0.0  # of the user's max HP
    resource_fraction: float = 0.0  # of the user's max resource
    # Tomos (docs/design/10-sistemas-de-build.md §3.8): reading one teaches
    # an ability permanently for the run -- it enters the pool (and an
    # Active Ability Slot if one is free), the Tomo is gone. A Tomo of
    # another archetype is the second cross-archetype channel next to
    # weapon abilities.
    teaches_ability: str | None = None
