"""Terreno & ambiente (docs/design/01-mecanicas.md §11, 07-mundo-dificuldade.md
"Tema elemental por área"): a TerrainDef grants Modifiers to EVERY
combatant of an encounter -- party and enemies alike, "risco e
oportunidade". Stamped onto each combatant's transient
Character.terrain_modifiers by CombatEngine.start_encounter and read by
computed_stats; never part of a character's own passives, and stripped
when the session syncs the fight back into the run."""

from __future__ import annotations

from pydantic import BaseModel, Field

from wyrdfall.domain.models import Modifier


class TerrainDef(BaseModel):
    id: str
    name: str
    description: str
    modifiers: list[Modifier] = Field(default_factory=list)
