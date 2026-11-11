"""Eventos de mundo (docs/design/14-estrutura-da-run.md §5): a narrative
choice node -- never a forced combat. Each option's outcome is expressed
only in terms the run already models (PV, Fragmentos, Pontos de Talento,
Alinhamento); Wyrd Meter/Carta/Bênção outcomes are later-phase systems.

Which event a given node shows is drawn deterministically from the run
seed and the node's index (a third RNG stream next to RunState.
encounter_rng/loot_rng), so the host, every joiner and the session all
compute the same event with no extra message or state field.
"""

from __future__ import annotations

import random

from pydantic import BaseModel, Field

from wyrdfall.domain.run import RunState


class EventOptionDef(BaseModel):
    id: str
    label: str
    outcome_text: str
    # docs/design/05-classes.md §4 -- the one place Alinhamento is written
    alignment_shift: float = 0.0
    heal_fraction: float = 0.0  # of each party member's max HP
    damage_fraction: float = 0.0  # of each party member's max HP, never lethal
    currency_delta: int = 0  # negative = a cost the run must be able to pay
    talent_points: int = 0  # granted to every party member
    card_id: str | None = None  # "raramente uma Carta" -- granted to every party member
    wyrd_risk: float = 0.0  # "opção de risco": raises the Medidor do Wyrd (domain/wyrd.py)
    blessing: bool = False  # an altar: grants one random Bênção (domain/blessings.py) to the party
    unlocks_race: str | None = None  # Fada's "Portal Feérico" (04-racas.md): a race unlock banked at run end


class EventDef(BaseModel):
    id: str
    name: str
    text: str
    options: list[EventOptionDef] = Field(default_factory=list)

    def option(self, option_id: str) -> EventOptionDef | None:
        return next((o for o in self.options if o.id == option_id), None)


def event_rng(run: RunState) -> random.Random:
    return random.Random(run.seed * 3_000_003 + run.encounter_index)


def event_for_node(run: RunState, pool: dict[str, EventDef]) -> EventDef:
    ordered = [pool[key] for key in sorted(pool)]
    return event_rng(run).choice(ordered)
