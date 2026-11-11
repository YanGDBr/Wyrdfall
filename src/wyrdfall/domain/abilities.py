from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from wyrdfall.domain.challenges import ChallengeDef
from wyrdfall.domain.models import Archetype, Effect


class TargetMode(str, Enum):
    SELF = "self"
    SINGLE_ENEMY = "single_enemy"
    ALL_ENEMIES = "all_enemies"
    SINGLE_ALLY = "single_ally"
    ALL_ALLIES = "all_allies"


class Ability(BaseModel):
    id: str
    name: str
    description: str = ""
    resource_cost: float = 0.0
    target_mode: TargetMode
    effects: list[Effect] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    # Fixed weight added to archetype_usage once per cast (see
    # domain/combat.py::resolve) -- docs/design/10-sistemas-de-build.md §5.
    archetype_weight: dict[Archetype, float] = Field(default_factory=dict)
    # Only usable while a matching weapon type is equipped (see
    # domain/weapons.py); CombatEngine.legal_abilities filters on this.
    required_weapon_type: str | None = None
    # docs/design/10-sistemas-de-build.md §3.9: Defender is "sempre uma
    # opção a mais no menu de ação" -- never takes an Active Ability Slot
    # (domain/slots.py) and is always offered in combat.
    universal: bool = False
    # Minigame de Habilidade (docs/design/11-habilidades.md §9): the
    # player's client runs it before submitting and only the score
    # travels (Action.challenge_score). None = no minigame, the norm.
    challenge: ChallengeDef | None = None
    # Tipos de Custo (docs/design/11-habilidades.md §7). resource_cost is
    # the pool cost (§7.1) -- or, with pays_with_hp (§7.2 Sangue), a
    # fraction of the caster's CURRENT HP, never lethal. cooldown_turns
    # (§7.3) is time, charges_per_rest (§7.4) is finite uses refilled at
    # a rest / Área transition. A single ability may combine them.
    pays_with_hp: bool = False
    cooldown_turns: int = 0
    # capped activations per combat (Natureza Dual's form switch, 04-racas.md);
    # Stat.EXTRA_USES_PER_COMBAT raises the cap. Reset at start_encounter.
    uses_per_combat: int | None = None
    charges_per_rest: int | None = None
    # Combo por Sequência (§8.2): +COMBO_SEQUENCE_BONUS when the caster's
    # last ability was one of these ids.
    combo_from: list[str] = Field(default_factory=list)
    # Papel (docs/design/11-habilidades.md §4.4): informal, for UI ordering
    # and enemy AI hints -- never a build rule. Empty = infer_role().
    role: str = ""
    # Gates for "botão de pânico" abilities: only usable at or below this
    # HP fraction, and/or once per run (Character.used_once_per_run).
    requires_hp_below: float | None = None
    once_per_run: bool = False

    @property
    def requires_target(self) -> bool:
        return self.target_mode in (TargetMode.SINGLE_ENEMY, TargetMode.SINGLE_ALLY)


ROLE_ORDER = ["Dano", "Controle", "Debuff", "Buff", "Cura", "Utilidade", "Invocação"]


def infer_role(ability: Ability) -> str:
    """docs/design/11-habilidades.md §4.4's table, from the ability's own
    effects: an explicit Ability.role wins; otherwise the first matching
    row. Statuses are read only by target side (self/ally = Buff, enemy =
    Debuff), since the ability doesn't know the status definition."""
    if ability.role:
        return ability.role
    kinds = [e.kind for e in ability.effects]
    from wyrdfall.domain.models import EffectKind  # local: models imports nothing from here

    if EffectKind.SUMMON in kinds:
        return "Invocação"
    if EffectKind.DAMAGE in kinds:
        return "Dano"
    if EffectKind.HEAL in kinds or EffectKind.APPLY_SHIELD in kinds:
        return "Cura"
    if EffectKind.RESTORE_RESOURCE in kinds or EffectKind.CLEANSE in kinds or EffectKind.REVIVE in kinds:
        return "Utilidade"
    if EffectKind.APPLY_STATUS in kinds:
        if ability.target_mode in (TargetMode.SINGLE_ENEMY, TargetMode.ALL_ENEMIES):
            return "Controle" if any(t in ability.tags for t in ("control",)) else "Debuff"
        return "Buff"
    return "Utilidade"
