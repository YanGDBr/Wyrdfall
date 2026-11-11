"""Companheiro/Familiar (Fase 9 -- docs/design/10-sistemas-de-build.md §8,
11-habilidades.md §5's "SUMMON não é o Companheiro" note): a slot of its
own, never competing with Active Ability Slots, holding a companion with
its own mini stat-block that fights on the party's side, persists
between combats, and is unlocked/picked in the Guild (meta-progression).

Rules the sketch left open, decided here as first-guess balance like
every other rate in the codebase:
- the companion is present from the start of every combat ("convocado"
  at encounter start -- no action to spend on it);
- it acts on its own (the enemy AI's ability/target choice, on the
  party's side), so the player's turn economy is untouched;
- its stat-block scales with its owner's level (COMPANION_LEVEL_SCALING)
  instead of leveling separately;
- a downed companion isn't lost -- it returns at the next encounter at
  COMPANION_REVIVE_FRACTION of its max HP;
- it never counts for "o grupo caiu" (a live companion with a dead
  party is a defeat), never earns Afinidade for its owner (its
  abilities carry no archetype_weight), and never takes a share of
  Vigor, Cartas or consumables -- RunState keeps it apart from party.

Especialização Domador (05b-classes-roster.md §4) stays the natural home
for a companion-focused kit when that hybrid becomes reachable.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from wyrdfall.domain.character import Character
from wyrdfall.domain.models import StatBlock

COMPANION_LEVEL_SCALING = 0.10
COMPANION_REVIVE_FRACTION = 0.5


class CompanionDef(BaseModel):
    id: str
    name: str
    description: str
    cost: int
    base_stats: StatBlock
    abilities: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


COMPANION_DEFS: dict[str, CompanionDef] = {
    "lobo_cinzento": CompanionDef(
        id="lobo_cinzento", name="Lobo Cinzento",
        description="Rápido e mordedor -- ataca antes de quase todo mundo.",
        cost=20,
        base_stats=StatBlock(max_hp=14, attack=4, defense=1, speed=9, crit_chance=0.10, max_resource=0),
        abilities=["companion_bite"], tags=["beast"],
    ),
    "corvo_do_wyrd": CompanionDef(
        id="corvo_do_wyrd", name="Corvo do Wyrd",
        description="Bica de longe e deixa o alvo Enfraquecido.",
        cost=20,
        base_stats=StatBlock(max_hp=10, attack=3, defense=0, speed=8, max_resource=0),
        abilities=["companion_peck"], tags=["beast", "flying"],
    ),
    "salamandra": CompanionDef(
        id="salamandra", name="Salamandra",
        description="Cospe brasas -- dano de Fogo em quem estiver na frente.",
        cost=25,
        base_stats=StatBlock(max_hp=12, attack=4, defense=1, speed=5, fire_resist=0.5, max_resource=0),
        abilities=["companion_ember"], tags=["beast", "fire"],
    ),
    "tartaruga_de_pedra": CompanionDef(
        id="tartaruga_de_pedra", name="Tartaruga de Pedra",
        description="Lenta e dura -- absorve golpes e escuda um aliado.",
        cost=25,
        base_stats=StatBlock(max_hp=24, attack=2, defense=3, speed=2, block_chance=0.25, max_resource=0),
        abilities=["companion_shell"], tags=["beast", "earth"],
    ),
}


def companion_stats_for(companion_def: CompanionDef, owner_level: int) -> StatBlock:
    stats = companion_def.base_stats.model_copy()
    scale = 1.0 + COMPANION_LEVEL_SCALING * max(0, owner_level - 1)
    stats.max_hp *= scale
    stats.attack *= scale
    return stats


def build_companion(companion_def: CompanionDef, owner: Character) -> Character:
    stats = companion_stats_for(companion_def, owner.level)
    return Character(
        id=f"{owner.id}_companion",
        name=companion_def.name,
        class_id=companion_def.id,
        base_stats=stats,
        current_hp=stats.max_hp,
        current_resource=stats.max_resource,
        abilities=list(companion_def.abilities),
        equipped_abilities=list(companion_def.abilities),
        tags=set(companion_def.tags),
        level=owner.level,
        is_player=True,
        is_companion=True,
        owner_id=owner.id,
    )


def rescale_companion(companion: Character, owner: Character) -> None:
    """Re-derives the mini stat-block from the owner's current level at
    each encounter start -- HP fraction is preserved so growth never
    silently heals or hurts."""
    companion_def = COMPANION_DEFS.get(companion.class_id)
    if companion_def is None:
        return
    old_max = max(1.0, companion.base_stats.max_hp)
    fraction = companion.current_hp / old_max
    companion.base_stats = companion_stats_for(companion_def, owner.level)
    companion.level = owner.level
    companion.current_hp = fraction * companion.base_stats.max_hp
