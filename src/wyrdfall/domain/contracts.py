"""Contratos de Run (docs/design/08-itens-crafting.md "Missões"): optional
objectives offered at the start of a run -- "the game tells you before"
version of the run-condition pattern race unlocks already use -- paying
extra Fragmentos on completion and extra Ecos when the run is banked.

Offered from the run seed (two per run), accepted or declined once on
the first dungeon screen; every accepted contract is checked against the
CombatState after each won encounter (boss_only ones only after a boss)
and completes at most once per run.
"""

from __future__ import annotations

import random
from collections.abc import Callable

from pydantic import BaseModel, ConfigDict

from wyrdfall.domain.combat import CombatState

CONTRACTS_OFFERED_PER_RUN = 2


class ContractDef(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: str
    name: str
    description: str
    reward_fragments: int
    reward_ecos: int
    boss_only: bool = False
    check: Callable[[CombatState], bool]


def _no_damage(state: CombatState) -> bool:
    return state.damage_taken_this_encounter <= 0


def _no_heal(state: CombatState) -> bool:
    return not state.used_heal_this_encounter


def _fast(state: CombatState) -> bool:
    return state.round_number <= 3


def _parried(state: CombatState) -> bool:
    return state.had_successful_parry


def _everyone_standing(state: CombatState) -> bool:
    return all(state.combatants[cid].is_alive for cid in state.party_ids() if not state.combatants[cid].is_companion)


CONTRACT_DEFS: dict[str, ContractDef] = {
    "intocavel": ContractDef(
        id="intocavel", name="Intocável", description="Vença um combate sem sofrer nenhum dano.",
        reward_fragments=15, reward_ecos=3, check=_no_damage,
    ),
    "sem_cura": ContractDef(
        id="sem_cura", name="Sem Cura", description="Derrote um chefe sem usar nenhuma cura.",
        reward_fragments=30, reward_ecos=6, boss_only=True, check=_no_heal,
    ),
    "relampago": ContractDef(
        id="relampago", name="Relâmpago", description="Vença um combate em até 3 rodadas.",
        reward_fragments=12, reward_ecos=2, check=_fast,
    ),
    "aparador": ContractDef(
        id="aparador", name="Aparador", description="Vença um combate depois de aparar um ataque.",
        reward_fragments=15, reward_ecos=3, check=_parried,
    ),
    "firme": ContractDef(
        id="firme", name="Firme", description="Derrote um chefe com todo o grupo de pé.",
        reward_fragments=25, reward_ecos=5, boss_only=True, check=_everyone_standing,
    ),
}


def contract_offer_for(seed: int, pool: dict[str, ContractDef] | None = None) -> list[str]:
    """The run's two offered contracts -- deterministic per seed so host,
    joiners and a rebuilt session all see the same ones."""
    pool = pool if pool is not None else CONTRACT_DEFS
    rng = random.Random(seed * 10_000_003)
    ids = sorted(pool)
    return rng.sample(ids, min(CONTRACTS_OFFERED_PER_RUN, len(ids)))
