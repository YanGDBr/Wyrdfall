"""Vigor (XP) accumulation and character leveling
(docs/design/14-estrutura-da-run.md §7). Kept separate from character.py
for the same reason factory.py is: it composes Character with Ruleset and
TalentTree, so the pure Character model itself stays free of that
dependency.
"""

from __future__ import annotations

from wyrdfall.domain.character import Character, Ruleset
from wyrdfall.domain.factory import recompute_passive_effects
from wyrdfall.domain.talents import TalentTree

_BASE_VIGOR = 10.0
_VIGOR_PER_LEVEL = 5.0
_ATTRIBUTE_POINTS_PER_LEVEL = 2
_TALENT_POINTS_PER_LEVEL = 1
_HEAL_FRACTION_PER_LEVEL = 0.25


def vigor_for_next_level(level: int) -> float:
    return _BASE_VIGOR + _VIGOR_PER_LEVEL * level


def apply_level_ups(character: Character, ruleset: Ruleset, talent_tree: TalentTree | None) -> int:
    """Consumes accumulated Vigor into as many level-ups as it affords.
    Recomputes passive modifiers after each level (not just once at the
    end) so the universal +2%-max-HP-per-level bonus is already baked in
    before that level's partial heal is calculated. Returns how many
    levels were gained."""
    levels_gained = 0
    while character.vigor >= vigor_for_next_level(character.level):
        character.vigor -= vigor_for_next_level(character.level)
        character.level += 1
        character.attribute_points_available += _ATTRIBUTE_POINTS_PER_LEVEL
        character.build.talent_tree.points_available += _TALENT_POINTS_PER_LEVEL
        recompute_passive_effects(character, talent_tree)
        max_hp = character.computed_stats(ruleset).max_hp
        character.current_hp = min(max_hp, character.current_hp + _HEAL_FRACTION_PER_LEVEL * max_hp)
        levels_gained += 1
    return levels_gained
