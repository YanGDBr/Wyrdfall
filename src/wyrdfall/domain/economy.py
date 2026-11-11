"""Ecos reward formula for a finished run (docs/design/06-economia-progressao.md).

Ecos are the permanent currency, earned at the end of every run regardless
of victory or defeat -- progress always counts, even in a loss. Fragmentos
(the in-run currency, tracked today as RunState.currency_earned) mostly
zero out at run end except for a small conversion slice, so a hoarded
stash still has some lasting value.
"""

from __future__ import annotations

BASE_POR_ANDAR = 3
BONUS_POR_CHEFE = 10
TAXA_CONVERSAO = 0.15


def ecos_for_run(floors_completed: int, bosses_defeated: int, fragments_remaining: int) -> int:
    return (
        BASE_POR_ANDAR * floors_completed
        + BONUS_POR_CHEFE * bosses_defeated
        + round(fragments_remaining * TAXA_CONVERSAO)
    )
