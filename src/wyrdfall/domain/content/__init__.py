"""Data-driven MVP game content, built entirely on the domain layer.

This is the playable slice of Wyrdfall: the 4 Arquétipo Base classes
(each a talent-tree build), a handful of enemies, and one dungeon path.
Nothing in here is imported by the domain layer itself -- content
depends on domain, never the other way around -- so the combat/talent
engines stay testable without it.
"""

from wyrdfall.domain.content.consumables import CONSUMABLE_DEFS
from wyrdfall.domain.content.dungeon import AREA_NAMES, MVP_DUNGEON, PORTAL_DEFS, build_dungeon_for_portal
from wyrdfall.domain.content.enemies import ENEMY_DEFS
from wyrdfall.domain.content.events import EVENT_DEFS
from wyrdfall.domain.content.guardiao import GUARDIAO_CLASS, GUARDIAO_TALENT_TREE
from wyrdfall.domain.content.mistico import MISTICO_CLASS, MISTICO_TALENT_TREE
from wyrdfall.domain.content.patrulheiro import PATRULHEIRO_CLASS, PATRULHEIRO_TALENT_TREE
from wyrdfall.domain.content.ruleset import build_ruleset
from wyrdfall.domain.content.runeguard import RUNEGUARD_CLASS, RUNEGUARD_TALENT_TREE
from wyrdfall.domain.content.specializations import SPECIALIZATION_TREES

CLASS_DEFS = {
    RUNEGUARD_CLASS.id: RUNEGUARD_CLASS,
    PATRULHEIRO_CLASS.id: PATRULHEIRO_CLASS,
    MISTICO_CLASS.id: MISTICO_CLASS,
    GUARDIAO_CLASS.id: GUARDIAO_CLASS,
}
TALENT_TREES = {
    RUNEGUARD_TALENT_TREE.definition.id: RUNEGUARD_TALENT_TREE,
    PATRULHEIRO_TALENT_TREE.definition.id: PATRULHEIRO_TALENT_TREE,
    MISTICO_TALENT_TREE.definition.id: MISTICO_TALENT_TREE,
    GUARDIAO_TALENT_TREE.definition.id: GUARDIAO_TALENT_TREE,
    **SPECIALIZATION_TREES,
}

__all__ = [
    "CLASS_DEFS",
    "CONSUMABLE_DEFS",
    "TALENT_TREES",
    "ENEMY_DEFS",
    "EVENT_DEFS",
    "MVP_DUNGEON",
    "AREA_NAMES",
    "PORTAL_DEFS",
    "build_dungeon_for_portal",
    "build_ruleset",
]
