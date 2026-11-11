"""Turns a ClassDef + talent allocation into a playable Character.

Kept separate from character.py because it composes ClassDef, TalentTree,
and Ruleset together -- character.py itself stays a pure data module.
"""

from __future__ import annotations

from wyrdfall.domain.attributes import attribute_modifiers_for
from wyrdfall.domain.sealing import seal_modifiers_for
from wyrdfall.domain.blessings import blessing_modifiers_for, blessing_triggered_effects_for
from wyrdfall.domain.cards import card_modifiers_for, card_triggered_effects_for
from wyrdfall.domain.character import Character, ClassDef, Ruleset
from wyrdfall.domain.items import item_modifiers_for, item_triggered_effects_for
from wyrdfall.domain.models import DamageElement, Archetype, Modifier, ModifierKind, Stat, TriggeredEffect
from wyrdfall.domain.races import RACE_DEFS, race_modifiers_for, race_triggered_effects_for
from wyrdfall.domain.runes import rune_modifiers_for, rune_triggered_effects_for
from wyrdfall.domain.slots import active_ability_slots
from wyrdfall.domain.specializations import variant_modifiers
from wyrdfall.domain.talents import TalentTree
from wyrdfall.domain.weapons import weapon_modifiers_for


def create_player_character(
    instance_id: str,
    name: str,
    class_def: ClassDef,
    talent_tree: TalentTree | None,
    ruleset: Ruleset,
    allocated_talents: set[str] | None = None,
    starting_talent_points: int = 0,
    can_parry: bool = False,
    race_id: str = "human",
    permanent_modifiers: list[Modifier] | None = None,
    permanent_triggered_effects: list[TriggeredEffect] | None = None,
    sealed_archetypes: set[Archetype] | None = None,
    sealed_elements: set[DamageElement] | None = None,
) -> Character:
    allocated_talents = allocated_talents or set()
    abilities = list(class_def.starting_abilities)

    if talent_tree is not None:
        for ability_id in talent_tree.granted_abilities_for(allocated_talents):
            if ability_id not in abilities:
                abilities.append(ability_id)

    race = RACE_DEFS.get(race_id)
    for ability_id in (race.granted_abilities if race is not None else []):
        if ability_id not in abilities:
            abilities.append(ability_id)
    # docs/design/10-sistemas-de-build.md §4: everything a fresh character
    # knows fits its starting slots; universal abilities (Defender) never
    # take one.
    slotted = [aid for aid in abilities if not (ruleset.abilities.get(aid) and ruleset.abilities[aid].universal)]
    character = Character(
        id=instance_id,
        name=name,
        class_id=class_def.id,
        base_stats=class_def.base_stats.model_copy(),
        current_hp=0,
        current_resource=0,
        abilities=abilities,
        equipped_abilities=slotted[: active_ability_slots(1)],
        is_player=True,
        resource_kind=class_def.resource_kind,
        charges={
            aid: ruleset.abilities[aid].charges_per_rest
            for aid in abilities
            if aid in ruleset.abilities and ruleset.abilities[aid].charges_per_rest is not None
        },
        can_parry=can_parry,
        race_id=race_id,
        can_cheat_death=race.grants_cheat_death if race is not None else False,
        status_immunities=set(race.status_immunities) if race is not None else set(),
        tags=set(race.tags) if race is not None else set(),
        base_archetype=class_def.base_archetype,
        permanent_modifiers=list(permanent_modifiers or []),
        permanent_triggered_effects=list(permanent_triggered_effects or []),
        sealed_archetypes=set(sealed_archetypes or set()),
        sealed_elements=set(sealed_elements or set()),
    )
    character.build.talent_tree.allocated = set(allocated_talents)
    character.build.talent_tree.points_available = starting_talent_points
    recompute_passive_effects(character, talent_tree)

    computed = character.computed_stats(ruleset)
    character.current_hp = computed.max_hp
    character.current_resource = computed.max_resource
    return character


def recompute_passive_effects(character: Character, talent_tree: TalentTree | None) -> None:
    """Rebuilds ``passive_modifiers`` AND ``passive_triggered_effects``
    from every source at once -- allocated talent nodes, invested
    attribute points, race, and the universal +2%-max-HP-per-level bonus
    -- so no single caller wholesale-clobbers another's contribution (the
    way allocate_talent alone used to overwrite passive_triggered_effects
    with just the talent tree's, silently dropping a race's trait effect
    the first time a talent point was spent)."""
    modifiers: list[Modifier] = []
    triggered_effects: list[TriggeredEffect] = []
    if talent_tree is not None:
        modifiers.extend(talent_tree.modifiers_for(character.build.talent_tree.allocated))
        triggered_effects.extend(talent_tree.triggered_effects_for(character.build.talent_tree.allocated))
    modifiers.extend(attribute_modifiers_for(character.attribute_points))
    modifiers.extend(race_modifiers_for(character.race_id))
    modifiers.extend(variant_modifiers(character.evolution_variants))
    triggered_effects.extend(race_triggered_effects_for(character.race_id))
    modifiers.extend(weapon_modifiers_for(character))
    modifiers.extend(rune_modifiers_for(character))
    triggered_effects.extend(rune_triggered_effects_for(character))
    modifiers.extend(item_modifiers_for(character))
    triggered_effects.extend(item_triggered_effects_for(character))
    modifiers.extend(card_modifiers_for(character))
    triggered_effects.extend(card_triggered_effects_for(character))
    modifiers.extend(blessing_modifiers_for(character))
    triggered_effects.extend(blessing_triggered_effects_for(character))
    modifiers.extend(seal_modifiers_for(character))  # Selamentos' bonus curve (10-sistemas-de-build.md §7)
    modifiers.extend(character.permanent_modifiers)
    triggered_effects.extend(character.permanent_triggered_effects)
    if character.level > 1:
        modifiers.append(
            Modifier(
                stat=Stat.MAX_HP,
                kind=ModifierKind.PERCENT,
                value=0.02 * (character.level - 1),
                source="level",
            )
        )
    character.passive_modifiers = modifiers
    character.passive_triggered_effects = triggered_effects
