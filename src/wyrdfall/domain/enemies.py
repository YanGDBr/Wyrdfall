from __future__ import annotations

from pydantic import BaseModel, Field

from wyrdfall.domain.character import Character, EnemyPhase
from wyrdfall.domain.models import DamageElement, StatBlock, TriggeredEffect


class EnemyDef(BaseModel):
    id: str
    name: str
    base_stats: StatBlock
    abilities: list[str] = Field(default_factory=list)
    triggered_effects: list[TriggeredEffect] = Field(default_factory=list)
    currency_reward: int = 1
    vigor_reward: int = 0
    # Empty means no phase system -- `abilities` above is used unchanged for
    # the whole fight, exactly like every enemy before this field existed.
    phases: list[EnemyPhase] = Field(default_factory=list)
    # Fase 7 -- same categorical status immunity as Character.
    # status_immunities (see domain/races.py), just sourced from an
    # EnemyDef instead of a RaceDef.
    status_immunities: set[str] = Field(default_factory=set)
    # Fase 7 -- same one-time survive-a-lethal-hit mechanism as
    # RaceDef.grants_cheat_death (Humano's "Nunca Desista"), just
    # sourced from an EnemyDef -- Área 10's Carne Amaldiçoada "fica
    # Latente" trait reuses it rather than needing a new mechanic.
    grants_cheat_death: bool = False
    # Fase 7 (Área 11) -- same mechanisms as Character.
    # immune_while_allies_alive/absorbs_damage_element, just sourced
    # from an EnemyDef (Nyxelle's conditional immunity/Arcane-heals).
    immune_while_allies_alive: set[str] = Field(default_factory=set)
    absorbs_damage_element: DamageElement | None = None
    # 13-chefes.md §10 (O Inominável): phases drawn at random on each
    # Postura break, never repeating the last one; and how many summons a
    # phase-entry summon may keep alive at once (§8, A Mãe Pútrida's Brotos).
    random_phase_on_break: bool = False
    summon_cap: int = 3


def instantiate_enemy(enemy_def: EnemyDef, instance_id: str, stat_multiplier: float = 1.0) -> Character:
    stats = enemy_def.base_stats.model_copy()
    if stat_multiplier != 1.0:
        stats.max_hp *= stat_multiplier
        stats.attack *= stat_multiplier

    abilities = list(enemy_def.phases[0].abilities) if enemy_def.phases else list(enemy_def.abilities)
    return Character(
        id=instance_id,
        name=enemy_def.name,
        class_id=enemy_def.id,
        base_stats=stats,
        current_hp=stats.max_hp,
        current_resource=stats.max_resource,
        current_poise=stats.max_poise,
        abilities=abilities,
        passive_triggered_effects=list(enemy_def.triggered_effects),
        enemy_phases=list(enemy_def.phases),
        random_phase_on_break=enemy_def.random_phase_on_break,
        phase_modifiers=list(enemy_def.phases[0].modifiers) if enemy_def.phases else [],
        status_immunities=set(enemy_def.status_immunities),
        can_cheat_death=enemy_def.grants_cheat_death,
        immune_while_allies_alive=set(enemy_def.immune_while_allies_alive),
        absorbs_damage_element=enemy_def.absorbs_damage_element,
        is_player=False,
    )
