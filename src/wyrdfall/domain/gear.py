"""Serializable individual pieces. Catalogs live in items.py."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class EquipmentInstance(BaseModel):
    id: str
    definition_id: str
    rarity: Literal["comum", "raro", "lendario"]
    enchantments: list[str] = Field(default_factory=list)
    owner_id: str | None = None
