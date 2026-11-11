"""Core primitives shared by every build system (talents, relics, cards, gear).

The whole "extremely buildable" premise rests on one idea: no matter which
build system granted a bonus, it always boils down to a :class:`Modifier`
(a stat change) and/or a :class:`TriggeredEffect` (an event-driven rule).
The combat engine only ever consumes these two primitives, so a talent node,
a relic, a card, and a gear affix are all interchangeable from its point of
view.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Archetype(str, Enum):
    """The 4 Arquétipos Base (docs/design/05-classes.md §1)."""

    GUERREIRO = "guerreiro"
    PATRULHEIRO = "patrulheiro"
    MISTICO = "mistico"
    GUARDIAO = "guardiao"


class Alignment(str, Enum):
    """The 3 Alinhamento bands (docs/design/05-classes.md §4), derived
    from Character.alignment_score by domain/specializations.py::
    alignment_category -- never stored directly."""

    BONDOSO = "bondoso"
    MALIGNO = "maligno"
    NEUTRO = "neutro"


class Stat(str, Enum):
    """Field names intentionally match :class:`StatBlock` attributes so a
    ``Stat`` can be used directly with ``getattr``/``setattr``."""

    MAX_HP = "max_hp"
    ATTACK = "attack"
    DEFENSE = "defense"
    SPEED = "speed"
    CRIT_CHANCE = "crit_chance"
    CRIT_MULT = "crit_mult"
    MAX_RESOURCE = "max_resource"
    DODGE_CHANCE = "dodge_chance"
    BLOCK_CHANCE = "block_chance"
    BLOCK_PERCENT = "block_percent"
    LIFESTEAL_PERCENT = "lifesteal_percent"
    CRIT_RESIST = "crit_resist"
    STATUS_RESIST = "status_resist"
    ARMOR_PENETRATION_PERCENT = "armor_penetration_percent"
    PHYSICAL_DAMAGE_PERCENT = "physical_damage_percent"
    ELEMENTAL_DAMAGE_PERCENT = "elemental_damage_percent"
    GENERAL_ELEMENTAL_RESIST = "general_elemental_resist"
    FIRE_RESIST = "fire_resist"
    ICE_RESIST = "ice_resist"
    ARCANE_RESIST = "arcane_resist"
    POISON_RESIST = "poison_resist"
    SHADOW_RESIST = "shadow_resist"
    HOLY_RESIST = "holy_resist"
    LIGHTNING_RESIST = "lightning_resist"
    EARTH_RESIST = "earth_resist"
    WATER_RESIST = "water_resist"
    AIR_RESIST = "air_resist"
    HEALING_DONE_PERCENT = "healing_done_percent"
    HEALING_RECEIVED_PERCENT = "healing_received_percent"
    RESOURCE_REGEN_PER_TURN = "resource_regen_per_turn"
    PROC_CHANCE_PERCENT = "proc_chance_percent"
    MAX_POISE = "max_poise"
    WEAPON_DAMAGE_PERCENT = "weapon_damage_percent"
    PHYSICAL_VULNERABILITY_PERCENT = "physical_vulnerability_percent"
    # extra activations for abilities capped by Ability.uses_per_combat
    # (the Meio-celestial's "trocar de forma 2x por combate" upgrade)
    EXTRA_USES_PER_COMBAT = "extra_uses_per_combat"
    EXTRA_ACTIVE_SLOTS = "extra_active_slots"


class StatBlock(BaseModel):
    max_hp: float = 20.0
    attack: float = 5.0
    defense: float = 2.0
    speed: float = 5.0
    crit_chance: float = 0.05
    crit_mult: float = 1.5
    max_resource: float = 4.0
    dodge_chance: float = 0.0
    block_chance: float = 0.0
    block_percent: float = 0.0
    lifesteal_percent: float = 0.0
    crit_resist: float = 0.0
    status_resist: float = 0.0
    armor_penetration_percent: float = 0.0
    physical_damage_percent: float = 0.0
    elemental_damage_percent: float = 0.0
    general_elemental_resist: float = 0.0
    fire_resist: float = 0.0
    ice_resist: float = 0.0
    arcane_resist: float = 0.0
    poison_resist: float = 0.0
    shadow_resist: float = 0.0
    holy_resist: float = 0.0
    lightning_resist: float = 0.0
    earth_resist: float = 0.0
    water_resist: float = 0.0
    air_resist: float = 0.0
    healing_done_percent: float = 0.0
    # Reduces (or, if negative-valued elsewhere, would increase) HEAL
    # effects landing on this character specifically -- separate from
    # healing_done_percent, which is the caster's own outgoing modifier.
    healing_received_percent: float = 0.0
    resource_regen_per_turn: float = 0.0
    proc_chance_percent: float = 0.0
    max_poise: float = 0.0
    # Applies to all damage regardless of element (docs/design/
    # 10-sistemas-de-build.md §2) -- separate from physical_damage_percent/
    # elemental_damage_percent, which stay element-specific and PERCENT-kind.
    weapon_damage_percent: float = 0.0
    # A defender-side weakness to Physical damage specifically -- unlike
    # every other element, Physical damage is modeled as raw-defense, not
    # a resist percent, so _elemental_resistance's generic path doesn't
    # cover it (docs/design/04-racas.md's Fada "-20% Físico").
    physical_vulnerability_percent: float = 0.0
    extra_uses_per_combat: float = 0.0
    extra_active_slots: float = 0.0

    def get(self, stat: Stat) -> float:
        return getattr(self, stat.value)


class ModifierKind(str, Enum):
    FLAT = "flat"
    PERCENT = "percent"  # additive percent, sums with other percent modifiers
    MORE = "more"  # multiplicative, each applied independently ("increased" vs "more")


class Modifier(BaseModel):
    stat: Stat
    kind: ModifierKind
    value: float
    source: str
    # Conditional modifiers: an "element:<id>" tag makes an
    # ELEMENTAL_DAMAGE_PERCENT modifier apply to that element only
    # (Character.element_damage_bonus) -- compute_stats skips it.
    tags: list[str] = Field(default_factory=list)


ELEMENT_TAG_PREFIX = "element:"


def element_tag(element: DamageElement) -> str:
    return f"{ELEMENT_TAG_PREFIX}{element.value}"


def compute_stats(base: StatBlock, modifiers: list[Modifier]) -> StatBlock:
    """Flat modifiers add first, then all percent modifiers sum and apply
    once, then each "more" modifier multiplies independently."""

    flat: dict[Stat, float] = {}
    percent: dict[Stat, float] = {}
    more: dict[Stat, list[float]] = {}

    for mod in modifiers:
        if any(tag.startswith(ELEMENT_TAG_PREFIX) for tag in mod.tags):
            continue  # element-conditional: applied per hit, not to the stat block
        if mod.kind is ModifierKind.FLAT:
            flat[mod.stat] = flat.get(mod.stat, 0.0) + mod.value
        elif mod.kind is ModifierKind.PERCENT:
            percent[mod.stat] = percent.get(mod.stat, 0.0) + mod.value
        else:
            more.setdefault(mod.stat, []).append(mod.value)

    result = base.model_copy()
    for stat in Stat:
        value = base.get(stat) + flat.get(stat, 0.0)
        value *= 1.0 + percent.get(stat, 0.0)
        for more_value in more.get(stat, []):
            value *= 1.0 + more_value
        setattr(result, stat.value, value)
    return result


class TriggerEvent(str, Enum):
    ON_COMBAT_START = "on_combat_start"
    ON_TURN_START = "on_turn_start"
    ON_TURN_END = "on_turn_end"
    ON_ABILITY_CAST = "on_ability_cast"
    ON_HIT = "on_hit"
    ON_CRIT = "on_crit"
    ON_KILL = "on_kill"
    ON_TAKE_DAMAGE = "on_take_damage"
    ON_DODGE = "on_dodge"
    ON_BLOCK = "on_block"
    ON_PARRY_SUCCESS = "on_parry_success"
    ON_PARRY_FAIL = "on_parry_fail"
    ON_DEATH = "on_death"
    # docs/design/11-habilidades.md §14 -- the three group-play triggers:
    # fired on every living same-side combatant when one of them goes
    # down (context = the downed one); on the revived character when a
    # REVIVE brings them back mid-fight (context = the reviver); on the
    # attacker who consumed a Combo em Equipe mark (context = the target).
    ON_ALLY_DOWNED = "on_ally_downed"
    ON_REVIVE = "on_revive"
    ON_TEAM_COMBO = "on_team_combo"
    # 01-mecanicas.md §13: on the actor whose Combo por Sequência just
    # chained (context = none); on the attacker who broke a Postura
    # (context = the target) and on the broken target (context = attacker).
    ON_COMBO_EXTEND = "on_combo_extend"
    ON_POISE_BREAK = "on_poise_break"


class EffectKind(str, Enum):
    DAMAGE = "damage"
    HEAL = "heal"
    APPLY_STATUS = "apply_status"
    RESTORE_RESOURCE = "restore_resource"
    APPLY_SHIELD = "apply_shield"
    # Fase 7 -- Área 5's Enguia-Espectral (docs/design/12-monstros.md
    # §3.5): unlike RESTORE_RESOURCE (which only ever adds), this both
    # reduces the target's resource AND restores the same amount to the
    # source -- the resource-economy mirror of lifesteal_percent, which
    # already does this for HP inside _apply_damage.
    DRAIN_RESOURCE = "drain_resource"
    # docs/design/11-habilidades.md §5 -- the last three of the catalog:
    # CLEANSE strips harmful statuses (amount: 0 = all, N = up to N),
    # REVIVE brings a downed ally back at `amount` x max HP (the rare
    # in-combat version of the Incapacitado rule), SUMMON adds a temporary
    # combatant (Ruleset.summons[summon_id]) on the caster's side for this
    # combat only -- explicitly NOT the Companheiro.
    CLEANSE = "cleanse"
    REVIVE = "revive"
    # docs/design/11-habilidades.md §5 TRANSFORM: temporarily swaps the
    # target's kit/appearance (Ruleset.transforms[transform_id]) -- the
    # Licantropo's Forma de Fera, the Meio-celestial's form switch.
    TRANSFORM = "transform"
    SUMMON = "summon"
    # Renascido's "Abraçar a Morte" (04-racas.md): `amount` turns of
    # immunity to fatal damage (HP floors at 1), and `scale_factor` = the
    # fraction of max HP lost for the rest of the run (a permanent
    # modifier on the caster).
    DEATH_WARD = "death_ward"


class DamageElement(str, Enum):
    """The 11 damage types from docs/design/02-elementos.md. Only PHYSICAL,
    FIRE and ICE have real resistance-stat plumbing so far (Fase 2) -- the
    rest exist now so later phases never have to touch this enum again."""

    PHYSICAL = "physical"
    FIRE = "fire"
    ICE = "ice"
    LIGHTNING = "lightning"
    WATER = "water"
    EARTH = "earth"
    AIR = "air"
    POISON = "poison"
    HOLY = "holy"
    SHADOW = "shadow"
    ARCANE = "arcane"


class EvolutionVariants(BaseModel, frozen=True):
    """Variants earned in this run. Empty fields keep the base specialization."""

    race_id: str | None = None
    alignment: Alignment | None = None
    element: DamageElement | None = None


class Effect(BaseModel):
    """A single data-driven effect. Kept as data (not a callable) so it stays
    serializable for the network layer and safe to evaluate on any host."""

    kind: EffectKind
    amount: float = 0.0
    scales_with: Stat | None = None
    scale_factor: float = 0.0
    status_id: str | None = None
    duration: int = 0
    stacks: int = 1
    damage_element: DamageElement = DamageElement.PHYSICAL
    poise_damage: float = 0.0
    # Raio's defining element mechanic (docs/design/02-elementos.md):
    # "X% do dano acerta um segundo inimigo aleatório". 0.0 (the
    # default) means no chain -- every other element/effect is
    # unaffected. See CombatEngine._apply_damage's tail for the hop.
    chain_percent: float = 0.0
    # Sagrado's "dano bônus contra tags undead/cursed" (docs/design/
    # 02-elementos.md) -- generic, not hardcoded to those two ids.
    # Empty list (the default) means no bonus. See CombatEngine.
    # _apply_damage, which checks this against Character.tags.
    bonus_vs_tags: list[str] = Field(default_factory=list)
    bonus_vs_tags_bonus: float = 0.0
    # Arcano's defining element mechanic (Área 11, Paradoxo Ambulante/
    # Eco Arcano): "elemento de dano aleatório a cada turno" -- when
    # True, CombatEngine._apply_damage picks the actual element via its
    # own rng at resolution time instead of using damage_element above,
    # so no build has a "correct" resistance against it.
    random_damage_element: bool = False
    # Arcano's other defining mechanic (Área 11, Livro Errante):
    # "ignora uma fração de resistência elemental do alvo". Multiplies
    # down the target's computed elemental resist before CombatEngine.
    # _apply_damage's existing damage floor.
    resist_penetration_percent: float = 0.0
    # Minigames de Habilidade (domain/challenges.py): a perfect Precisão
    # forces the crit instead of rolling for it. Set only on the per-
    # action effect copies CombatEngine.resolve makes -- never authored.
    guaranteed_crit: bool = False
    # docs/design/01-mecanicas.md §8: a per-effect proc chance, so an
    # ability can carry a probabilistic secondary effect ("30% de chance
    # de atordoar") without a separate talent. 1.0 (the default) never
    # rolls, so existing seeds are untouched.
    chance: float = 1.0
    # §1.3 Execução: bonus damage against targets at or below a fraction
    # of their max HP. None = no execute component.
    execute_threshold: float | None = None
    execute_bonus: float = 0.0
    # §1.4 Overkill/Cleave: damage past the kill spills onto the next
    # living target of the same side, once. Set per action by
    # CombatEngine when the ability carries the "cleave" tag -- never
    # authored directly on an Effect.
    cleave: bool = False
    # SUMMON only: which Ruleset.summons entry to bring in.
    summon_id: str | None = None
    # TRANSFORM only: which Ruleset.transforms entry the target takes.
    transform_id: str | None = None

    def resolve_amount(self, source_stats: StatBlock) -> float:
        value = self.amount
        if self.scales_with is not None:
            value += source_stats.get(self.scales_with) * self.scale_factor
        return value


class TriggeredEffect(BaseModel):
    """A passive rule granted by a talent/relic/card/affix: "when X happens,
    do Y" (e.g. on-crit apply Burn). ``chance`` allows partial-proc passives.

    ``applies_to`` picks who the effect targets: "self" (the character that
    owns the passive) or "context" (the other party involved in the
    triggering event -- e.g. the enemy just hit for an on-crit rider, or the
    attacker for an on-take-damage thorns rider).
    """

    trigger: TriggerEvent
    effect: Effect
    chance: float = 1.0
    source: str = ""
    applies_to: str = "self"  # "self" | "context"


class StatusEffectDef(BaseModel):
    """Definition of a buff/debuff, looked up by id from a :class:`Ruleset`."""

    id: str
    name: str
    max_stacks: int = 1
    modifiers: list[Modifier] = Field(default_factory=list)
    tick_effect: Effect | None = None
    tick_trigger: TriggerEvent = TriggerEvent.ON_TURN_START
    # Fase 7 -- Terra<->Ar Reação Elemental (docs/design/
    # 11-habilidades.md §8.3): applying this status strips the named one
    # from the same target instead of letting both stack (e.g.
    # Fragmentado <-> Desequilibrado). None (the default) means no
    # exclusion -- every other status is unaffected.
    exclusive_with: str | None = None
    # docs/design/01-mecanicas.md §4 -- the control statuses the engine
    # *respects* rather than just carrying: Silêncio blocks "magic"-tagged
    # abilities; Provocar forces the owner's single-target picks onto
    # whoever applied it (ActiveStatus.source_id); Medo gives each action
    # a chance to fail into Defender before the cost is paid.
    silences: bool = False
    taunts: bool = False
    fail_chance: float = 0.0
    # docs/design/11-habilidades.md §8.4 Combo em Equipe: while this
    # status is on a target, a hit from a DIFFERENT ally than the one who
    # applied it consumes the mark and deals this much extra (fraction).
    # Never fires solo -- the marker's own hits don't count.
    team_combo_bonus: float = 0.0

    @property
    def is_harmful(self) -> bool:
        """What CLEANSE strips: any negative modifier, a damaging tick, or
        a control flag. Buffs (positive modifiers, healing ticks) stay."""
        if self.silences or self.taunts or self.fail_chance > 0:
            return True
        if self.tick_effect is not None and self.tick_effect.kind in (EffectKind.DAMAGE, EffectKind.DRAIN_RESOURCE):
            return True
        return any(mod.value < 0 for mod in self.modifiers)

    def modifiers_for_stacks(self, stacks: int) -> list[Modifier]:
        out = []
        for mod in self.modifiers:
            out.append(mod.model_copy(update={"value": mod.value * stacks}))
        return out


class ActiveStatus(BaseModel):
    status_id: str
    stacks: int = 1
    remaining_duration: int = 1
    # who applied it -- what Provocar reads to know whom to force
    source_id: str | None = None
