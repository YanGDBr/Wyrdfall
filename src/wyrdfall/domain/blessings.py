"""Bênçãos -- Passivas de Run (docs/design/06-economia-progressao.md):
found DURING the run (altars in Eventos, Elite room rewards), from a
universal pool, small and broad -- "tempero, não o motor principal da
build". Technically just one more producer of Modifier/TriggeredEffect
(domain/factory.py::recompute_passive_effects), same as Cartas; the one
extra hook is heal_fraction_per_node, applied by GameSession whenever the
run moves to its next node.

Granted to the whole party at once (a run-level seasoning), never to a
single character, and never twice -- the roll excludes what the party
already holds.
"""

from __future__ import annotations

import random

from pydantic import BaseModel, Field

from wyrdfall.domain.character import Character
from wyrdfall.domain.models import Modifier, ModifierKind, Stat, TriggeredEffect


class BlessingDef(BaseModel):
    id: str
    name: str
    description: str
    modifiers: list[Modifier] = Field(default_factory=list)
    triggered_effects: list[TriggeredEffect] = Field(default_factory=list)
    # "cura 1% do PV máximo ao trocar de sala" -- the doc's own example
    heal_fraction_per_node: float = 0.0


def _mod(stat: Stat, value: float, source: str, kind: ModifierKind = ModifierKind.FLAT) -> Modifier:
    return Modifier(stat=stat, kind=kind, value=value, source=f"blessing_{source}")


BLESSING_DEFS: dict[str, BlessingDef] = {
    "pele_do_wyrd": BlessingDef(
        id="pele_do_wyrd", name="Pele do Wyrd", description="+5% em todas as resistências elementais.",
        modifiers=[_mod(Stat.GENERAL_ELEMENTAL_RESIST, 0.05, "pele_do_wyrd")],
    ),
    "passo_leve": BlessingDef(
        id="passo_leve", name="Passo Leve", description="+5% de Esquiva.",
        modifiers=[_mod(Stat.DODGE_CHANCE, 0.05, "passo_leve")],
    ),
    "fonte_interior": BlessingDef(
        id="fonte_interior", name="Fonte Interior", description="+0.5 de recurso por turno.",
        modifiers=[_mod(Stat.RESOURCE_REGEN_PER_TURN, 0.5, "fonte_interior")],
    ),
    "gratidao": BlessingDef(
        id="gratidao", name="Gratidão", description="+5% de cura recebida.",
        modifiers=[_mod(Stat.HEALING_RECEIVED_PERCENT, 0.05, "gratidao")],
    ),
    "vento_a_favor": BlessingDef(
        id="vento_a_favor", name="Vento a Favor", description="+1 de Velocidade.",
        modifiers=[_mod(Stat.SPEED, 1.0, "vento_a_favor")],
    ),
    "folego": BlessingDef(
        id="folego", name="Fôlego", description="Cura 2% do PV máximo ao trocar de sala.",
        heal_fraction_per_node=0.02,
    ),
    "olhar_firme": BlessingDef(
        id="olhar_firme", name="Olhar Firme", description="+5% de resistência a Crítico.",
        modifiers=[_mod(Stat.CRIT_RESIST, 0.05, "olhar_firme")],
    ),
    "maos_gentis": BlessingDef(
        id="maos_gentis", name="Mãos Gentis", description="+10% de cura causada.",
        modifiers=[_mod(Stat.HEALING_DONE_PERCENT, 0.10, "maos_gentis")],
    ),
}


def roll_blessing(rng: random.Random, pool: dict[str, BlessingDef], exclude: list[str] | set[str]) -> str | None:
    candidates = sorted(bid for bid in pool if bid not in set(exclude))
    return rng.choice(candidates) if candidates else None


def blessing_modifiers_for(character: Character) -> list[Modifier]:
    out: list[Modifier] = []
    for blessing_id in character.blessings:
        blessing = BLESSING_DEFS.get(blessing_id)
        if blessing is not None:
            out.extend(blessing.modifiers)
    return out


def blessing_triggered_effects_for(character: Character) -> list[TriggeredEffect]:
    out: list[TriggeredEffect] = []
    for blessing_id in character.blessings:
        blessing = BLESSING_DEFS.get(blessing_id)
        if blessing is not None:
            out.extend(blessing.triggered_effects)
    return out


def heal_fraction_per_node_for(character: Character) -> float:
    return sum(
        BLESSING_DEFS[bid].heal_fraction_per_node for bid in character.blessings if bid in BLESSING_DEFS
    )
