"""Minigames de Habilidade (docs/design/11-habilidades.md §9, 01-mecanicas.md
§10): the difficulty knobs for one client-side minigame attempt and the
one rule every kind shares -- "errar reduz o efeito, nunca zera".

Only the *score* (0.0..1.0) ever leaves the client, inside
domain/combat.py::Action.challenge_score -- the same principle as Parry
(ui/screens/skill_challenge.py), whose ChallengeDef used to live in the
UI module and moved here once other minigames started sharing it.
CombatEngine.resolve turns the score into an effect multiplier via
challenge_multiplier and, for Precisão, into a guaranteed crit.

Kept to a handful of signature abilities (the Stage-2 keystones in
domain/content/abilities.py), never universal -- §9's own containment
rule.
"""

from __future__ import annotations

import random
from enum import Enum

from pydantic import BaseModel


class ChallengeKind(str, Enum):
    # Janela de Tempo: bar + cursor, hit the window (Parry's bar reused)
    TIMING = "timing"
    # Sequência: a short key sequence is shown, hidden, then repeated --
    # partial credit for X of N correct
    SEQUENCE = "sequence"
    # Canalização: keep the marker inside a drifting "good zone" for the
    # channel's duration -- credit for the fraction of time held
    CHANNEL = "channel"
    # Precisão: one of N zones flashes; pick it for a guaranteed crit
    PRECISION = "precision"


class ChallengeDef(BaseModel):
    """Difficulty knobs for one minigame attempt. Widening/narrowing the
    hit window per encounter tier (harder fights = a tighter window) is
    designed but not wired in -- every attempt uses its ability's
    authored numbers."""

    kind: ChallengeKind = ChallengeKind.TIMING
    # timing / channel
    duration_seconds: float = 2.0
    tick_seconds: float = 0.05
    bar_width: int = 30
    hit_window_start: float = 0.4
    hit_window_end: float = 0.6
    # sequence
    sequence_length: int = 4
    show_seconds: float = 1.5
    # precision
    zone_count: int = 3
    flash_seconds: float = 0.8
    # Effect multiplier at score 0 -- the floor. 1.0 means the minigame
    # never reduces (Precisão only adds the crit on a perfect pick).
    min_factor: float = 0.5
    crit_on_perfect: bool = False


def clamp_score(score: float | None) -> float:
    if score is None:
        return 0.0
    return max(0.0, min(1.0, float(score)))


def parry_challenge(rng: random.Random | None = None) -> ChallengeDef:
    """A short, variable timing window, independent of offensive challenges."""
    start = (rng or random).uniform(0.35, 0.75)
    return ChallengeDef(duration_seconds=1.25, tick_seconds=1 / 60,
                        bar_width=40, hit_window_start=start, hit_window_end=start + 0.10)


def challenge_multiplier(challenge: ChallengeDef, score: float | None) -> float:
    """Linear from min_factor (score 0) up to 1.0 (score 1) -- a miss
    reduces the effect, never zeroes it."""
    return challenge.min_factor + (1.0 - challenge.min_factor) * clamp_score(score)
