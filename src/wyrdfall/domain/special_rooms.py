"""Sala Especial (docs/design/14-estrutura-da-run.md §4-5): every regular
Área's node 4 is one of Forja de Campo / Descanso / Vendedor, "sorteado"
per run. Drawn from the run seed + node index like every other per-node
roll, so the host, every joiner and the session resolve the same room
without any extra message."""

from __future__ import annotations

import random
from typing import Literal

from wyrdfall.domain.dungeon import EncounterDef, RoomType
from wyrdfall.domain.run import RunState

SpecialRoomType = Literal["forge", "rest", "shop"]
_SPECIAL_ROOM_TYPES: tuple[SpecialRoomType, ...] = ("forge", "rest", "shop")


def special_room_type_for(run: RunState) -> SpecialRoomType:
    return random.Random(run.seed * 5_000_003 + run.encounter_index).choice(_SPECIAL_ROOM_TYPES)


def resolved_room_type(run: RunState, encounter: EncounterDef) -> RoomType:
    if encounter.room_type == "special":
        return special_room_type_for(run)
    return encounter.room_type
