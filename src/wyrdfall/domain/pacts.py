"""Pactos do Wyrd (docs/design/06-economia-progressao.md): bought once
with Ecos, then equipped/unequipped freely before each run -- a loadout,
never consumed. Vantagens are pure bonuses capped by a small number of
slots; Pactos de Risco deliberately make the run worse for more
Fragmentos/Ecos, and every one you turn on also raises the Medidor do
Wyrd (domain/wyrd.py) from the start. Mechanically a Vantagem is just
more permanent Modifiers on every party member (the same channel the
permanent trees already use), and a Risco is a number the shared
danger/reward pipeline reads.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from wyrdfall.domain.models import Modifier, ModifierKind, Stat

VANTAGEM_SLOTS_BASE = 2
PACT_SLOT_COST = 30
# First-guess numbers, like every other balance rate.
_VANTAGEM_COST = 25
_RISCO_COST = 15
_RISCO_WYRD_GAIN = 15.0


class PactDef(BaseModel):
    id: str
    name: str
    description: str
    kind: Literal["vantagem", "risco"]
    cost: int
    modifiers: list[Modifier] = Field(default_factory=list)  # applied to every party member
    enemy_power_bonus: float = 0.0  # Risco: enemies' stat multiplier
    reward_bonus: float = 0.0  # Risco: Fragmentos/Ecos multiplier
    wyrd_gain: float = 0.0  # Risco: Medidor do Wyrd at run start


PACT_DEFS: dict[str, PactDef] = {
    # -- Vantagens -----------------------------------------------------------
    "vigor_do_wyrd": PactDef(
        id="vigor_do_wyrd", name="Vigor do Wyrd", kind="vantagem", cost=_VANTAGEM_COST,
        description="+8 de PV máximo pra todo o grupo.",
        modifiers=[Modifier(stat=Stat.MAX_HP, kind=ModifierKind.FLAT, value=8, source="pact_vigor_do_wyrd")],
    ),
    "fio_afiado": PactDef(
        id="fio_afiado", name="Fio Afiado", kind="vantagem", cost=_VANTAGEM_COST,
        description="+2 de Ataque pra todo o grupo.",
        modifiers=[Modifier(stat=Stat.ATTACK, kind=ModifierKind.FLAT, value=2, source="pact_fio_afiado")],
    ),
    "passo_do_tecelao": PactDef(
        id="passo_do_tecelao", name="Passo do Tecelão", kind="vantagem", cost=_VANTAGEM_COST,
        description="+5% de chance de Esquiva pra todo o grupo.",
        modifiers=[Modifier(stat=Stat.DODGE_CHANCE, kind=ModifierKind.FLAT, value=0.05, source="pact_passo_do_tecelao")],
    ),
    "fonte_interior": PactDef(
        id="fonte_interior", name="Fonte Interior", kind="vantagem", cost=_VANTAGEM_COST,
        description="+0.5 de Resolução por turno pra todo o grupo.",
        modifiers=[
            Modifier(stat=Stat.RESOURCE_REGEN_PER_TURN, kind=ModifierKind.FLAT, value=0.5, source="pact_fonte_interior")
        ],
    ),
    # -- Pactos de Risco ---------------------------------------------------------
    "sangue_fino": PactDef(
        id="sangue_fino", name="Sangue Fino", kind="risco", cost=_RISCO_COST,
        description="-20% de PV máximo pra todo o grupo. Recompensas +25%.",
        modifiers=[Modifier(stat=Stat.MAX_HP, kind=ModifierKind.PERCENT, value=-0.20, source="pact_sangue_fino")],
        reward_bonus=0.25, wyrd_gain=_RISCO_WYRD_GAIN,
    ),
    "inimigos_ferozes": PactDef(
        id="inimigos_ferozes", name="Inimigos Ferozes", kind="risco", cost=_RISCO_COST,
        description="Inimigos +25% mais fortes. Recompensas +30%.",
        enemy_power_bonus=0.25, reward_bonus=0.30, wyrd_gain=_RISCO_WYRD_GAIN,
    ),
    "maos_tremulas": PactDef(
        id="maos_tremulas", name="Mãos Trêmulas", kind="risco", cost=_RISCO_COST,
        description="-10% de Esquiva e de chance de Bloqueio pra todo o grupo. Recompensas +20%.",
        modifiers=[
            Modifier(stat=Stat.DODGE_CHANCE, kind=ModifierKind.FLAT, value=-0.10, source="pact_maos_tremulas"),
            Modifier(stat=Stat.BLOCK_CHANCE, kind=ModifierKind.FLAT, value=-0.10, source="pact_maos_tremulas"),
        ],
        reward_bonus=0.20, wyrd_gain=_RISCO_WYRD_GAIN,
    ),
    "chamado_do_abismo": PactDef(
        id="chamado_do_abismo", name="Chamado do Abismo", kind="risco", cost=_RISCO_COST,
        description="Inimigos +15% mais fortes e -10% de PV máximo pra todo o grupo. Recompensas +40%.",
        modifiers=[Modifier(stat=Stat.MAX_HP, kind=ModifierKind.PERCENT, value=-0.10, source="pact_chamado_do_abismo")],
        enemy_power_bonus=0.15, reward_bonus=0.40, wyrd_gain=_RISCO_WYRD_GAIN,
    ),
}


def pact_modifiers_for(pact_ids: list[str]) -> list[Modifier]:
    modifiers: list[Modifier] = []
    for pact_id in pact_ids:
        pact = PACT_DEFS.get(pact_id)
        if pact is not None:
            modifiers.extend(pact.modifiers)
    return modifiers
