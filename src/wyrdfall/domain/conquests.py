"""Conquistas: flags observed off state the game already tracks, each
awarding a fixed Ecos amount once, ever (docs/design/06-economia-progressao.md).

Deliberately cheap to add to: every condition here reads fields RunState/
Character already carry for other reasons (race unlocks, the leveling
system, Parry) -- no new content or tracking was needed to wire this up.
"""

from __future__ import annotations

from pydantic import BaseModel

from wyrdfall.domain.run import RunState
from wyrdfall.persistence.store import MetaProgressionState, RunSummary


class ConquistaDef(BaseModel):
    id: str
    name: str
    description: str
    ecos_reward: int


CONQUEST_DEFS: dict[str, ConquistaDef] = {
    "first_victory": ConquistaDef(
        id="first_victory",
        name="Primeira Vitória",
        description="Complete uma run com vitória.",
        ecos_reward=20,
    ),
    "reach_level_5": ConquistaDef(
        id="reach_level_5",
        name="Veterano",
        description="Alcance o Nível 5 com um personagem.",
        ecos_reward=15,
    ),
    "defeat_hollow_knight": ConquistaDef(
        id="defeat_hollow_knight",
        name="O Trono Cai",
        description="Derrote o Cavaleiro Oco.",
        ecos_reward=25,
    ),
    "flawless_encounter": ConquistaDef(
        id="flawless_encounter",
        name="Impecável",
        description="Vença um encontro sem sofrer nenhum dano.",
        ecos_reward=15,
    ),
    "parried_successfully": ConquistaDef(
        id="parried_successfully",
        name="Contragolpe",
        description="Apare um ataque com sucesso.",
        ecos_reward=10,
    ),
}


def check_conquests(run: RunState, summary: RunSummary, meta: MetaProgressionState) -> list[str]:
    newly_completed = []
    for conquest_id, condition in _CONDITIONS.items():
        if conquest_id not in meta.completed_conquests and condition(run, summary):
            newly_completed.append(conquest_id)
    return newly_completed


_CONDITIONS = {
    "first_victory": lambda run, summary: summary.victory,
    "reach_level_5": lambda run, summary: any(c.level >= 5 for c in run.party),
    "defeat_hollow_knight": lambda run, summary: summary.victory and run.bosses_defeated >= 1,
    "flawless_encounter": lambda run, summary: run.had_flawless_encounter,
    "parried_successfully": lambda run, summary: run.parried_successfully,
}
