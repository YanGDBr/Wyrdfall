"""Missões da Guilda (docs/design/08-itens-crafting.md "Missões"):
persistent chains tracked across many runs, each paying one big, unique
unlock -- a Portal, a Companheiro, a permanent slot. Progress is read
straight from MetaProgressionState counters (the same buy-once/flag
pattern as Conquistas), evaluated once per finished run in
WyrdfallApp.bank_run_reward.

Kept free of a persistence-layer import: progress functions take the
counters they need, not the state object, same boundary as
domain/races.py::check_meta_race_unlock.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal

from pydantic import BaseModel, ConfigDict


class MissionProgressInput(BaseModel):
    """The slice of meta-progression a mission can read."""

    bosses_defeated_ids: set[str] = set()
    runs_finished: int = 0
    risk_free_victories: int = 0


RewardKind = Literal["portal", "companion", "vantagem_slot"]


class GuildMissionDef(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: str
    name: str
    description: str
    target: int
    progress: Callable[[MissionProgressInput], int]
    reward_kind: RewardKind
    reward_id: str = ""
    reward_text: str = ""

    def is_complete(self, data: MissionProgressInput) -> bool:
        return self.progress(data) >= self.target


GUILD_MISSION_DEFS: dict[str, GuildMissionDef] = {
    "cacador_de_chefes": GuildMissionDef(
        id="cacador_de_chefes", name="Caçador de Chefes",
        description="Derrote 3 chefes de Área diferentes.",
        target=3, progress=lambda d: len(d.bosses_defeated_ids),
        reward_kind="portal", reward_id="portao_submerso", reward_text="Desbloqueia o Portão Submerso.",
    ),
    "peregrino": GuildMissionDef(
        id="peregrino", name="Peregrino do Wyrd",
        description="Termine 10 runs, vencendo ou não.",
        target=10, progress=lambda d: d.runs_finished,
        reward_kind="companion", reward_id="tartaruga_de_pedra", reward_text="Desbloqueia a Tartaruga de Pedra.",
    ),
    "ascese": GuildMissionDef(
        id="ascese", name="Ascese",
        description="Vença 3 runs sem nenhum Pacto de Risco equipado.",
        target=3, progress=lambda d: d.risk_free_victories,
        reward_kind="vantagem_slot", reward_text="+1 slot permanente de Vantagem.",
    ),
}
