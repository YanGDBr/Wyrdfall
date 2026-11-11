"""The Medidor do Wyrd and the one danger/reward pipeline it shares with
Pactos de Risco and Ascensão (docs/design/09-roadmap.md decisions 1 and
5; 06-economia-progressao.md).

The meter rises with every risky choice in the run -- each Pacto de
Risco turned on at the start, every Evento option flagged as risky --
and "intensifica recompensa e perigo ao mesmo tempo": enemies get a
stat multiplier and Fragmentos/Ecos get a bigger one. Ascensão (New
Game+) stacks the same way, level by level, for players who already
won. Disclosed: the Renascido's "Abraçar a Morte" is the meter's third
documented source and doesn't exist as an action yet.
"""

from __future__ import annotations

from wyrdfall.domain.pacts import PACT_DEFS
from wyrdfall.domain.run import RunState

WYRD_MAX = 100.0
ASCENSION_MAX = 5
# First-guess balance rates, like every other number in this corpus.
_WYRD_DANGER_AT_MAX = 0.25
_WYRD_REWARD_AT_MAX = 0.50
_ASCENSION_DANGER_PER_LEVEL = 0.15
_ASCENSION_REWARD_PER_LEVEL = 0.20


def _risk_pacts(run: RunState):
    return [PACT_DEFS[pid] for pid in run.active_pacts if pid in PACT_DEFS and PACT_DEFS[pid].kind == "risco"]


def danger_multiplier(run: RunState) -> float:
    pacts = 1.0 + sum(p.enemy_power_bonus for p in _risk_pacts(run))
    ascension = 1.0 + run.ascension_level * _ASCENSION_DANGER_PER_LEVEL
    wyrd = 1.0 + (run.wyrd_meter / WYRD_MAX) * _WYRD_DANGER_AT_MAX
    return pacts * ascension * wyrd


def reward_multiplier(run: RunState) -> float:
    pacts = 1.0 + sum(p.reward_bonus for p in _risk_pacts(run))
    ascension = 1.0 + run.ascension_level * _ASCENSION_REWARD_PER_LEVEL
    wyrd = 1.0 + (run.wyrd_meter / WYRD_MAX) * _WYRD_REWARD_AT_MAX
    return pacts * ascension * wyrd


def starting_wyrd(pact_ids: list[str]) -> float:
    return min(WYRD_MAX, sum(PACT_DEFS[pid].wyrd_gain for pid in pact_ids if pid in PACT_DEFS))


def add_wyrd(run: RunState, amount: float) -> None:
    run.wyrd_meter = max(0.0, min(WYRD_MAX, run.wyrd_meter + amount))
