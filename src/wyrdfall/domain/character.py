from __future__ import annotations

from wyrdfall.domain.gear import EquipmentInstance

from enum import Enum

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from wyrdfall.domain.abilities import Ability
from wyrdfall.domain.attributes import Atributo
from wyrdfall.domain.slots import Stance, active_ability_slots
from wyrdfall.domain.models import (
    ActiveStatus,
    Archetype,
    DamageElement,
    EvolutionVariants,
    Modifier,
    Stat,
    StatBlock,
    StatusEffectDef,
    TriggeredEffect,
    compute_stats,
    element_tag,
)


class SummonDef(BaseModel):
    """A temporary combatant for one combat (docs/design/11-habilidades.md
    §5 SUMMON) -- fights on the summoner's side, acts on its own, gone when
    the fight ends. Not the Companheiro (domain/companions.py)."""

    id: str
    name: str
    base_stats: StatBlock
    abilities: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class TransformDef(BaseModel):
    """A temporary form (docs/design/11-habilidades.md §5 TRANSFORM, 04-racas
    Licantropo "transforma-se... pelo resto daquele combate"): while active
    its modifiers apply and, if it has granted_abilities, they REPLACE the
    normal kit (universal actions stay). duration 0 = rest of the combat."""

    id: str
    name: str
    description: str = ""
    modifiers: list[Modifier] = Field(default_factory=list)
    granted_abilities: list[str] = Field(default_factory=list)
    duration: int = 0
    # shown next to the name in combat -- the doc's "arte ASCII diferenciada"
    glyph: str = ""


class Ruleset(BaseModel):
    """Everything the combat engine needs to resolve ids into definitions.
    Kept separate from game content so tests can build a minimal ruleset
    without importing the full MVP content pack."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    abilities: dict[str, Ability] = Field(default_factory=dict)
    statuses: dict[str, StatusEffectDef] = Field(default_factory=dict)
    summons: dict[str, SummonDef] = Field(default_factory=dict)
    transforms: dict[str, TransformDef] = Field(default_factory=dict)


class TalentTreeState(BaseModel):
    allocated: set[str] = Field(default_factory=set)
    points_available: int = 0


class BuildState(BaseModel):
    talent_tree: TalentTreeState = Field(default_factory=TalentTreeState)


class EnemyPhase(BaseModel):
    """One entry in an EnemyDef's phase list (see domain/enemies.py).
    trigger="hp_threshold" (the default): active while current_hp/max_hp
    <= hp_ceiling; the first phase has hp_ceiling=1.0 so it's active from
    the start. trigger="poise_break" (docs/design/13-chefes.md: Voltharion,
    A Mãe Pútrida, O Inominável): phase N is entered on the N-th Postura
    break instead -- hp_ceiling is ignored. Either way a phase may carry
    its own modifiers (active only while it is) and a summon that appears
    on entering it."""

    hp_ceiling: float = 1.0
    abilities: list[str] = Field(default_factory=list)
    trigger: Literal["hp_threshold", "poise_break"] = "hp_threshold"
    modifiers: list[Modifier] = Field(default_factory=list)
    summon_id: str | None = None


class ResourceKind(str, Enum):
    """How a class's pool resource fills (docs/design/01-mecanicas.md §7,
    11-habilidades.md §7.1) -- one field, four generation rules in
    domain/combat.py. resource_regen_per_turn applies to every kind on
    top, so talents/runes that add regen keep working."""

    MANA = "mana"  # a little per turn on its own (the MVP's Resolução)
    FURY = "fury"  # rises on taking damage, decays when unused
    ADRENALINE = "adrenaline"  # rises every own turn as the fight goes on
    COMBO_POINTS = "combo_points"  # rises on combo_builder hits, spent all at once by a combo_finisher


RESOURCE_NAMES: dict[ResourceKind, str] = {
    ResourceKind.MANA: "Resolução",
    ResourceKind.FURY: "Fúria",
    ResourceKind.ADRENALINE: "Adrenalina",
    ResourceKind.COMBO_POINTS: "Pontos de Combo",
}


class ClassDef(BaseModel):
    id: str
    name: str
    description: str = ""
    resource_kind: ResourceKind = ResourceKind.MANA
    base_stats: StatBlock
    starting_abilities: list[str] = Field(default_factory=list)
    talent_tree_id: str | None = None
    build_system: Literal["talent_tree", "relics", "deck", "gear"] = "talent_tree"
    base_archetype: Archetype = Archetype.GUERREIRO


class Character(BaseModel):
    id: str
    name: str
    class_id: str
    base_stats: StatBlock
    current_hp: float
    current_resource: float
    abilities: list[str] = Field(default_factory=list)
    passive_modifiers: list[Modifier] = Field(default_factory=list)
    passive_triggered_effects: list[TriggeredEffect] = Field(default_factory=list)
    statuses: list[ActiveStatus] = Field(default_factory=list)
    build: BuildState = Field(default_factory=BuildState)
    is_player: bool = True
    resource_kind: ResourceKind = ResourceKind.MANA
    # Tipos de Custo (domain/abilities.py): per-ability cooldown turns left
    # and charges left, plus the last ability cast (Combo por Sequência)
    # and whether resource was spent on the last own turn (Fúria decay).
    cooldowns: dict[str, int] = Field(default_factory=dict)
    charges: dict[str, int] = Field(default_factory=dict)
    used_once_per_run: set[str] = Field(default_factory=set)
    # DEATH_WARD (Abraçar a Morte): turns left of immunity to fatal damage
    death_ward_turns: int = 0
    last_ability_id: str | None = None
    spent_resource_last_turn: bool = False
    # Fase 9 -- Companheiro (domain/companions.py): on the party's side
    # (is_player stays True so every side check works) but driven by the
    # AI like an enemy, and owned by one party member.
    is_companion: bool = False
    owner_id: str | None = None
    can_parry: bool = False
    shield_hp: float = 0.0
    attribute_points: dict[Atributo, int] = Field(default_factory=dict)
    attribute_points_available: int = 0
    level: int = 1
    vigor: float = 0.0
    race_id: str = "human"
    can_cheat_death: bool = False
    cheated_death_used: bool = False
    current_poise: float = 0.0
    # Deliberately its own field rather than a generic ActiveStatus: the
    # generic status system decrements-then-expires inside _tick_statuses,
    # which runs *after* the stun check in _begin_turn would need to read
    # it -- same reasoning that already gave `pending_parry` its own field
    # instead of being shoehorned into an existing system.
    stunned_turns: int = 0
    enemy_phases: list[EnemyPhase] = Field(default_factory=list)
    current_phase_index: int = 0
    # 13-chefes.md: how many times this combatant's Postura broke this
    # fight -- what poise_break-triggered phases index on; and whether the
    # phase pool is drawn at random (never the same twice in a row) on
    # each break instead of in order (O Inominável's Máscaras).
    poise_breaks: int = 0
    random_phase_on_break: bool = False
    # transient, combat-only modifier slots: the active EnemyPhase's own
    # modifiers and the encounter's Terreno (domain/terrain.py)
    phase_modifiers: list[Modifier] = Field(default_factory=list)
    terrain_modifiers: list[Modifier] = Field(default_factory=list)
    # TRANSFORM (11-habilidades.md §5): the active form, its remaining
    # turns (0 = rest of the combat) and its modifiers -- combat-only,
    # stripped with the terrain when the fight settles.
    active_transform_id: str | None = None
    transform_turns_left: int = 0
    transform_modifiers: list[Modifier] = Field(default_factory=list)
    # Evolução de raça na run (04-racas.md item 5, domain/race_evolution.py):
    # which evolution fired (its modifiers live in permanent_modifiers), and
    # the per-run counters its conditions read.
    race_evolution_id: str | None = None
    crits_landed: int = 0
    procs_fired: int = 0
    used_non_physical_this_area: bool = False
    # Construto's "absorve permanentemente (só nesta run) o efeito de uma
    # runa" -- counted by runes.py like a socketed rune, without a slot.
    absorbed_rune_id: str | None = None
    # per-combat activation counts for Ability.uses_per_combat
    uses_this_combat: dict[str, int] = Field(default_factory=dict)
    # any TRANSFORM happened this run (Licantropo's evolution is per combat)
    transformed_this_run: bool = False
    # Fase 5 -- Afinidade de Arquétipo/Elemental, medida por uso durante a
    # run inteira (docs/design/10-sistemas-de-build.md §5), não por
    # snapshot do que está equipado. Incrementados em domain/combat.py.
    archetype_usage: dict[Archetype, float] = Field(default_factory=dict)
    elemental_usage: dict[DamageElement, float] = Field(default_factory=dict)
    specialization_id: str | None = None
    evolution_variants: EvolutionVariants = Field(default_factory=EvolutionVariants)
    # Fase 8 -- Estágio 2 (docs/design/05b-classes-roster.md §10): the
    # second evolution at level 10, on top of specialization_id, chosen
    # from domain/specializations.py::STAGE2_DEFS.
    stage2_specialization_id: str | None = None
    # Baked in at creation from ClassDef.base_archetype (see factory.py) so
    # domain/specializations.py can filter qualifying Especializações
    # without importing the content layer (CLASS_DEFS) -- domain code never
    # depends on content, only the other way around.
    base_archetype: Archetype = Archetype.GUERREIRO
    # Set via GameSession.equip_weapon (Fase 5c) -- feeds
    # domain/weapons.py::weapon_modifiers_for and gates
    # Ability.required_weapon_type in domain/combat.py. P6 stores the equipped
    # piece separately from this type, which still determines scaling and kit.
    equipped_weapon_type: str | None = None
    equipped_weapon_id: str | None = None
    # Equipped projections travel with combatants. RunState owns the pieces.
    equipment_instances: dict[str, EquipmentInstance] = Field(default_factory=dict)
    # Fase 7 -- categorical immunity to specific status ids (docs/design/
    # 04-racas.md's Renascido/Construto), distinct from the existing
    # chance-based status_resist roll. Baked in once at creation from
    # RaceDef.status_immunities (see factory.py), mirroring exactly how
    # can_cheat_death already flows from race.grants_cheat_death.
    status_immunities: set[str] = Field(default_factory=set)
    # Fase 7 -- creature-identity tags (docs/design/02-elementos.md's
    # Sagrado "dano bônus contra tags undead/cursed"), distinct from
    # Ability.tags (ability-format: melee/ranged/magic) and
    # Modifier.tags (conditional-modifier matching). Baked in once at
    # creation from RaceDef.tags (see factory.py), same mechanism as
    # status_immunities.
    tags: set[str] = Field(default_factory=set)
    # Fase 7 -- Active Ability Slots (docs/design/10-sistemas-de-build.md
    # §4): the subset of `abilities` a player can actually use in combat
    # (see domain/slots.py; universal abilities are always offered on top).
    # Enemies never use it -- their whole pool is always legal.
    equipped_abilities: list[str] = Field(default_factory=list)
    # Fase 7 -- Postura (§3.9). Persists between fights; the per-turn
    # switch guard is reset by CombatEngine._begin_turn.
    current_stance: Stance = "none"
    stance_switched_this_turn: bool = False
    # Fase 7 -- Cartas (docs/design/10-sistemas-de-build.md §3.7). Held
    # cards feed recompute_passive_effects like runes/items do; a pending
    # 1-of-3 offer waits here between fights until chosen or skipped (a
    # new win replaces it -- no hoarding).
    cards: list[str] = Field(default_factory=list)
    card_offer: list[str] = Field(default_factory=list)
    # Bênçãos (domain/blessings.py): run passives, granted to the whole
    # party at once; kept per character so recompute_passive_effects stays
    # a pure function of the character, same as Cartas.
    blessings: list[str] = Field(default_factory=list)
    # Fase 7 (Área 11, Nyxelle) -- generic "immune to damage while any of
    # these other combatant ids is alive". Checked first thing in
    # CombatEngine._apply_damage against CombatState.combatants; empty
    # set (the default) means always damageable, same "opt-in, inert
    # unless populated" shape as status_immunities/tags above.
    immune_while_allies_alive: set[str] = Field(default_factory=set)
    # Fase 7 (Área 11, Nyxelle) -- "dano deste elemento cura em vez de
    # ferir". None (the default) means no such element. Checked in
    # CombatEngine._apply_damage right after the resolved damage element
    # is known.
    absorbs_damage_element: DamageElement | None = None
    # Fase 5b -- docs/design/05-classes.md §4. -100 (Maligno) to +100
    # (Bondoso), resets every run. Nothing writes to this yet (world
    # events/Pactos/Missões are all later phases) -- always 0.0 (Neutro)
    # for now, but the mechanism reading it is already wired.
    alignment_score: float = 0.0
    # Fase 5c -- docs/design/10-sistemas-de-build.md §3.1-3.2. Both pools
    # contribute their Modifier/TriggeredEffect to the character globally
    # and identically (see domain/runes.py's module docstring for why) --
    # the distinction that's real this phase is capacity: ability_rune_
    # slots is keyed by ability_id (each capped at
    # runes.ABILITY_RUNE_SLOTS_PER_ABILITY), body_rune_slots is one flat
    # list capped at runes.BODY_RUNE_SLOTS.
    ability_rune_slots: dict[str, list[str]] = Field(default_factory=dict)
    body_rune_slots: list[str] = Field(default_factory=list)
    # Baked in once at creation (see factory.py) from the player's
    # MetaProgressionState.permanent_tree_allocated -- a snapshot, not
    # re-derived each recompute, since permanent trees can only change in
    # the Guild between runs, never mid-run. Stored here (not passed as a
    # transient factory argument) so every recompute_passive_effects call
    # -- from allocate_talent, equip_weapon, socket_rune, etc. -- keeps
    # including it without needing to know where it came from, the same
    # way race_id already works.
    permanent_modifiers: list[Modifier] = Field(default_factory=list)
    # same channel for "when X, do Y" rules a permanent tree grants
    # (Licantropo's faster Instinto), baked in at creation like the above
    permanent_triggered_effects: list[TriggeredEffect] = Field(default_factory=list)
    # Fase 5c -- docs/design/10-sistemas-de-build.md §7. Chosen once, at
    # run start (see ui/screens/archetype_select.py), never modified
    # after -- same "sem reset" rule as everything else here. This phase
    # only wires the offer-filtering half (domain/specializations.py::
    # is_offerable); the "+10/15/25% damage on what's left" bonus is a
    # separate, deferred piece (needs a per-archetype damage-source split
    # the engine doesn't have yet).
    sealed_archetypes: set[Archetype] = Field(default_factory=set)
    sealed_elements: set[DamageElement] = Field(default_factory=set)
    # Exact instance IDs from RunState.inventory. Three fixed armor slots
    # (head/body/legs) and three accessories. Only armor counts toward sets.
    equipped_armor: dict[str, str] = Field(default_factory=dict)
    equipped_accessories: list[str] = Field(default_factory=list)
    # Legacy migration input/read-only projection. New enchantments belong to
    # EquipmentInstance, not to the character or the catalog definition.
    item_enchantments: dict[str, list[str]] = Field(default_factory=dict)

    @property
    def is_alive(self) -> bool:
        return self.current_hp > 0

    @property
    def is_incapacitated(self) -> bool:
        """Incapacitado (docs/design/11-habilidades.md §5): a party member at
        0 HP while the fight goes on -- out of the turn order, but only the
        run's outcome decides whether that's death (defeat) or a free
        revive at REVIVE_ON_VICTORY_FRACTION (victory)."""
        return self.is_player and not self.is_companion and not self.is_alive

    @property
    def acts_automatically(self) -> bool:
        """Whose turn the engine (not a player) resolves: enemies and
        companions alike -- the one predicate every AI-turn gate uses."""
        return not self.is_player or self.is_companion

    def status_modifiers(self, ruleset: Ruleset) -> list[Modifier]:
        mods: list[Modifier] = []
        for active in self.statuses:
            status_def = ruleset.statuses.get(active.status_id)
            if status_def is not None:
                mods.extend(status_def.modifiers_for_stacks(active.stacks))
        return mods

    def computed_stats(self, ruleset: Ruleset) -> StatBlock:
        all_modifiers = [
            *self.passive_modifiers, *self.phase_modifiers, *self.terrain_modifiers, *self.transform_modifiers,
            *self.status_modifiers(ruleset),
        ]
        return compute_stats(self.base_stats, all_modifiers)

    @property
    def active_slot_capacity(self) -> int:
        legacy_slot = any(m.stat == Stat.EXTRA_ACTIVE_SLOTS and m.value > 0 for m in self.permanent_modifiers)
        return active_ability_slots(self.level, legacy_slot=legacy_slot)

    def element_damage_bonus(self, ruleset: Ruleset, element: DamageElement) -> float:
        """Sum of element-conditional ELEMENTAL_DAMAGE_PERCENT modifiers for
        this element (see models.py::element_tag) -- a per-hit multiplier
        the stat block deliberately doesn't carry."""
        tag = element_tag(element)
        return sum(
            m.value for m in [
                *self.passive_modifiers, *self.phase_modifiers, *self.terrain_modifiers, *self.transform_modifiers,
                *self.status_modifiers(ruleset),
            ]
            if m.stat == Stat.ELEMENTAL_DAMAGE_PERCENT and tag in m.tags
        )

    @property
    def race_evolved_this_run(self) -> bool:
        """04-racas.md Meio-celestial's prestige gate counts a race as
        "evoluída" once its in-run evolution actually happened, whatever
        form it takes (trigger, ability, mechanic or transform)."""
        return bool(
            self.race_evolution_id or self.absorbed_rune_id or self.transformed_this_run
            or "abracar_a_morte" in self.used_once_per_run
        )

    def all_triggered_effects(self, ruleset: Ruleset) -> list[TriggeredEffect]:
        effects = list(self.passive_triggered_effects)
        for active in self.statuses:
            status_def = ruleset.statuses.get(active.status_id)
            if status_def and status_def.tick_effect:
                effects.append(
                    TriggeredEffect(
                        trigger=status_def.tick_trigger,
                        effect=status_def.tick_effect,
                        source=status_def.name,
                        applies_to="self",
                    )
                )
        return effects

    def available_abilities(self, ruleset: Ruleset) -> list[Ability]:
        return [ruleset.abilities[aid] for aid in self.abilities if aid in ruleset.abilities]
