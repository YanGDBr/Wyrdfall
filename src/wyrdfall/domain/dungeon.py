from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# docs/design/14-estrutura-da-run.md §4-5. "special" is what an Área's
# node 4 is *authored* as -- which Sala Especial it turns out to be
# (forge / rest / shop) is drawn per run (domain/special_rooms.py), so
# "shop" and "forge" only ever appear as resolved values, never in
# content.
RoomType = Literal["combat", "rest", "event", "special", "shop", "forge"]


class EncounterDef(BaseModel):
    id: str
    name: str
    enemy_ids: list[str] = Field(default_factory=list)  # one spawn per entry, repeats allowed
    is_boss: bool = False
    # docs/design/14-estrutura-da-run.md §5: an Elite fight rewards from a
    # better Carta pool. Set by content/dungeon.py's template on node 5.
    is_elite: bool = False
    flavor_text: str = ""
    area_id: str = ""
    room_type: RoomType = "combat"


class DungeonDef(BaseModel):
    id: str
    name: str
    encounters: list[EncounterDef]


class PortalDef(BaseModel):
    """A Portal de Entrada (docs/design/14-estrutura-da-run.md §3): an
    Área **inicial** plus a fixed path of following Áreas, always ending
    in Área 12. Different Portais give the same world graph different
    "linears" to walk -- see domain/content/dungeon.py's
    build_dungeon_for_portal for how a path turns into a DungeonDef."""

    id: str
    name: str
    path: list[str]  # area_id, in order
    unlock_condition: str | None = None


DEPTH_SCALE_PER_NODE = 0.08


def difficulty_multiplier(floor_index: int, party_size: int) -> float:
    """Enemies get tougher deeper into the dungeon, and scale up with party
    size so co-op doesn't trivialize fights. ``floor_index`` is 0-based."""

    # 07-mundo-dificuldade.md v2 ("chefe consideravelmente difícil"): was
    # 0.15/node (x5.05 at the final boss, which the headless bot never
    # reached); 0.08 lands the last boss at ~x3.2 and lets a coherent build
    # win the run without trivializing the first bosses.
    depth_scale = 1.0 + DEPTH_SCALE_PER_NODE * floor_index
    party_scale = 1.0 + 0.35 * max(0, party_size - 1)
    return depth_scale * party_scale
