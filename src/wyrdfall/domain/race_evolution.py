"""Evolução de raça na run (docs/design/04-racas.md item 5): "sob uma
condição específica daquela run, a raça ganha um efeito extra até o fim
da run atual. Reseta a cada nova run."

One def per race with a trigger-style evolution; the condition is read
off the character's own per-run counters (Character.crits_landed,
procs_fired, used_non_physical_this_area, ...) plus the two run-level
facts only the session knows (an Área just ended / a first boss fell).
Renascido's evolution is an ability (abracar_a_morte), Construto's is a
mechanic (GameSession.absorb_rune), Licantropo's is a per-combat
TRANSFORM (content/transforms.py) -- none of those is listed here.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from wyrdfall.domain.character import Character
from wyrdfall.domain.models import Effect, EffectKind, Modifier, ModifierKind, Stat, TriggeredEffect

ELF_CRIT_THRESHOLD = 10  # "um número alto de acertos críticos numa run"
FADA_PROC_THRESHOLD = 12  # "um número alto de procs numa run"
ORC_HP_FRACTION = 0.30  # "a primeira vez que o PV cair abaixo de 30%"


class RaceEvolutionDef(BaseModel):
    id: str
    race_id: str
    name: str
    description: str
    modifiers: list[Modifier] = Field(default_factory=list)
    triggered_effects: list[TriggeredEffect] = Field(default_factory=list)
    # applied to the character the moment it evolves (only reachable for
    # evolutions that fire inside a combat -- Orc's Segundo Fôlego)
    on_evolve_effects: list[Effect] = Field(default_factory=list)


def _resist(stat: Stat, source: str) -> Modifier:
    return Modifier(stat=stat, kind=ModifierKind.FLAT, value=0.05, source=source)


RACE_EVOLUTION_DEFS: dict[str, RaceEvolutionDef] = {
    "human": RaceEvolutionDef(
        id="abencoado_pelo_destino", race_id="human", name="Abençoado pelo Destino",
        description="Ao derrotar o primeiro chefe: +5% em todas as resistências elementais pelo resto da run.",
        modifiers=[
            _resist(stat, "abencoado_pelo_destino")
            for stat in (
                Stat.FIRE_RESIST, Stat.ICE_RESIST, Stat.ARCANE_RESIST, Stat.POISON_RESIST, Stat.SHADOW_RESIST,
                Stat.HOLY_RESIST, Stat.LIGHTNING_RESIST, Stat.EARTH_RESIST, Stat.WATER_RESIST, Stat.AIR_RESIST,
            )
        ],
    ),
    "dwarf": RaceEvolutionDef(
        id="furia_da_forja", race_id="dwarf", name="Fúria da Forja",
        description="Completar uma Área só com habilidades físicas: +20% de penetração de armadura pelo resto da run.",
        modifiers=[Modifier(stat=Stat.ARMOR_PENETRATION_PERCENT, kind=ModifierKind.FLAT, value=0.20, source="furia_da_forja")],
    ),
    "elf": RaceEvolutionDef(
        id="furia_elfica", race_id="elf", name="Fúria Élfica",
        description=f"Após {ELF_CRIT_THRESHOLD} acertos críticos na run: +0,5x no multiplicador de crítico pelo resto da run.",
        modifiers=[Modifier(stat=Stat.CRIT_MULT, kind=ModifierKind.FLAT, value=0.5, source="furia_elfica")],
    ),
    "orc": RaceEvolutionDef(
        id="segundo_folego", race_id="orc", name="Segundo Fôlego",
        description="A primeira vez abaixo de 30% de PV: cura 25% do PV máximo e +25% de Ataque por 3 turnos.",
        on_evolve_effects=[
            Effect(kind=EffectKind.HEAL, scales_with=Stat.MAX_HP, scale_factor=0.25),
            Effect(kind=EffectKind.APPLY_STATUS, status_id="segundo_folego", duration=3),
        ],
    ),
    "fada": RaceEvolutionDef(
        id="sorte_do_acaso", race_id="fada", name="Sorte do Acaso",
        description=f"Após {FADA_PROC_THRESHOLD} procs na run: +20% de chance de proc e +5% de crítico pelo resto da run.",
        modifiers=[
            Modifier(stat=Stat.PROC_CHANCE_PERCENT, kind=ModifierKind.FLAT, value=0.20, source="sorte_do_acaso"),
            Modifier(stat=Stat.CRIT_CHANCE, kind=ModifierKind.FLAT, value=0.05, source="sorte_do_acaso"),
        ],
    ),
}


def pending_race_evolution(
    character: Character, *, max_hp: float = 0.0, area_completed: bool = False, first_boss: bool = False,
) -> RaceEvolutionDef | None:
    """The evolution this character has just earned, or None. Pure: the
    caller (engine mid-combat, session after a boss) applies it."""
    if character.race_evolution_id is not None or not character.is_player or character.is_companion:
        return None
    evolution = RACE_EVOLUTION_DEFS.get(character.race_id)
    if evolution is None:
        return None
    race = character.race_id
    if race == "human":
        earned = first_boss
    elif race == "dwarf":
        earned = area_completed and not character.used_non_physical_this_area
    elif race == "elf":
        earned = character.crits_landed >= ELF_CRIT_THRESHOLD
    elif race == "orc":
        earned = max_hp > 0 and character.is_alive and character.current_hp / max_hp < ORC_HP_FRACTION
    elif race == "fada":
        earned = character.procs_fired >= FADA_PROC_THRESHOLD
    else:
        earned = False
    return evolution if earned else None


def apply_race_evolution(character: Character, evolution: RaceEvolutionDef) -> None:
    """Marks the evolution and folds its effects into the character's
    run-long permanent_* lists (so any later recompute keeps them) AND the
    live passive lists (so a fight in progress feels it immediately)."""
    character.race_evolution_id = evolution.id
    character.permanent_modifiers.extend(evolution.modifiers)
    character.passive_modifiers.extend(evolution.modifiers)
    character.permanent_triggered_effects.extend(evolution.triggered_effects)
    character.passive_triggered_effects.extend(evolution.triggered_effects)
