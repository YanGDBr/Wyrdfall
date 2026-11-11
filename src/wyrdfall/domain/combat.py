"""Deterministic, turn-based combat engine.

No spatial grid: every encounter is "party vs. a group of enemies," turns
proceed in a fixed initiative order computed once at encounter start, and
every action -- whether typed by a local player, sent over the network by a
remote client, or chosen by enemy AI -- flows through the same
:meth:`CombatEngine.resolve` call. UI and networking code are callers of
this engine; they never duplicate its rules.
"""

from __future__ import annotations

import random
import uuid
from contextlib import contextmanager
from enum import Enum

from pydantic import BaseModel, Field

from wyrdfall.domain.abilities import Ability, TargetMode
from wyrdfall.domain.challenges import challenge_multiplier, clamp_score
from wyrdfall.domain.race_evolution import apply_race_evolution, pending_race_evolution
from wyrdfall.domain.character import Character, EnemyPhase, ResourceKind, Ruleset
from wyrdfall.domain.consumables import ConsumableDef
from wyrdfall.domain.runes import rune_modifiers_for, rune_triggered_effects_for
from wyrdfall.domain.models import (
    ActiveStatus,
    DamageElement,
    Effect,
    EffectKind,
    Modifier,
    ModifierKind,
    Stat,
    StatBlock,
    TriggerEvent,
)
from wyrdfall.domain.slots import STANCE_DAMAGE_BONUS, STANCE_DODGE_BONUS, STANCE_NAMES, STANCE_PRECISION, Stance
from wyrdfall.domain.specializations import ELEMENTAL_VARIANT_DAMAGE
from wyrdfall.domain.terrain import TerrainDef

_MAX_ELEMENTAL_RESIST = 0.9
_MIN_ELEMENTAL_RESIST = -1.0
_PARRY_FAIL_MULTIPLIER = 1.20
# 13-chefes.md §8: a phase-entry summon keeps at most this many alive
_PHASE_SUMMON_CAP = 3
# Recursos alternativos (docs/design/01-mecanicas.md §7) -- first-guess
# generation rates, like every other balance number here.
FURY_PER_HIT_TAKEN = 1.0
FURY_DECAY_PER_IDLE_TURN = 1.0
ADRENALINE_PER_TURN = 1.0
COMBO_POINTS_PER_HIT = 1.0
# Pontos de Combo (11-habilidades.md §8.1): a finisher's damage/heal
# scale by 1 + COMBO_POINT_SCALING x points spent.
COMBO_POINT_SCALING = 0.25
# Combo por Sequência (§8.2) bonus when Ability.combo_from matches.
COMBO_SEQUENCE_BONUS = 0.5
# nested trigger reactions allowed before the engine stops echoing (see
# CombatEngine._fire_trigger_for) -- 3 lets A->B->A style exchanges play
# out once without two Espinhos ever ping-ponging forever
MAX_TRIGGER_DEPTH = 3
# 04-racas.md Licantropo: Instinto stacks in one combat that flip the
# Forma de Fera (content/transforms.py) on
LYCAN_TRANSFORM_STACKS = 6


class CombatError(Exception):
    """Raised when an action is illegal (wrong turn, bad target, etc.)."""


class ParryResult(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    DECLINED = "declined"


class PendingParry(BaseModel):
    """Set when a melee attack from an enemy targets a can_parry player --
    combat pauses (the turn does not advance) until resolve_parry() is
    called with that player's response. Scoped to single-target melee only
    (docs/design/01-mecanicas.md §2.3), so no "remaining targets" tracking
    is needed."""

    attacker_id: str
    request_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    defender_id: str
    ability_id: str


class Action(BaseModel):
    actor_id: str
    ability_id: str
    target_ids: list[str] = Field(default_factory=list)
    # Minigame de Habilidade score (0..1) the actor's own client produced
    # for an ability with Ability.challenge; ignored otherwise. Missing
    # on such an ability counts as 0 -- the floor, never nothing.
    challenge_score: float | None = Field(default=None, allow_inf_nan=False)


class CombatState(BaseModel):
    combatants: dict[str, Character]
    turn_order: list[str]
    turn_index: int = 0
    round_number: int = 1
    log: list[str] = Field(default_factory=list)
    is_over: bool = False
    victory: bool | None = None
    pending_parry: PendingParry | None = None
    # Terreno (domain/terrain.py) active in this fight, for the UI
    terrain_id: str | None = None
    # Party-wide flags for the whole encounter, consulted by race-unlock
    # checks (docs/design/04-racas.md) and a Conquista
    # (docs/design/06-economia-progressao.md) once it ends.
    used_heal_this_encounter: bool = False
    took_elemental_damage_this_encounter: bool = False
    healing_participants: set[str] = Field(default_factory=set)
    elemental_damage_recipients: set[str] = Field(default_factory=set)
    damage_taken_this_encounter: float = 0.0
    had_successful_parry: bool = False

    def current_actor_id(self) -> str:
        return self.turn_order[self.turn_index]

    def party_ids(self) -> list[str]:
        return [cid for cid, c in self.combatants.items() if c.is_player]

    def enemy_ids(self) -> list[str]:
        return [cid for cid, c in self.combatants.items() if not c.is_player]

    def alive(self, combatant_id: str) -> bool:
        return self.combatants[combatant_id].is_alive


class CombatEngine:
    def __init__(self, ruleset: Ruleset, rng: random.Random | None = None):
        self.ruleset = ruleset
        self.rng = rng or random.Random()
        # how deep triggered effects are currently nested (see _fire_trigger_for)
        self._trigger_depth = 0

    # -- public API ---------------------------------------------------

    def start_encounter(
        self, party: list[Character], enemies: list[Character], terrain: TerrainDef | None = None,
    ) -> CombatState:
        combatants = {c.id: c.model_copy(deep=True) for c in [*party, *enemies]}
        for combatant in combatants.values():
            combatant.last_ability_id = None  # sequence combos never carry across fights
            combatant.cooldowns = {}
            combatant.spent_resource_last_turn = False
            combatant.poise_breaks = 0
            combatant.uses_this_combat = {}
            # Terreno (01-mecanicas.md §11): the same modifiers on everyone
            combatant.terrain_modifiers = list(terrain.modifiers) if terrain is not None else []
        order = self._compute_turn_order(combatants)
        state = CombatState(
            combatants=combatants, turn_order=order, turn_index=-1, round_number=1,
            terrain_id=terrain.id if terrain is not None else None,
        )
        if terrain is not None:
            self._log(state, f"Terreno: {terrain.name} -- {terrain.description}")
        for combatant_id in order:
            self._fire_trigger_for(state, combatant_id, TriggerEvent.ON_COMBAT_START)
        self._advance_turn(state)
        return state

    def recover_turn(self, state: CombatState) -> bool:
        """Skip a defeated actor left at the head of an older checkpoint."""
        if state.is_over or state.pending_parry is not None or state.alive(state.current_actor_id()):
            return False
        self._advance_turn(state)
        return True

    def _kit_for(self, actor: Character) -> list[str]:
        """TRANSFORM (11-habilidades.md §5): a form with its own abilities
        replaces the kit while active; universal actions (Defender) stay."""
        transform = self.ruleset.transforms.get(actor.active_transform_id or "")
        if transform is None or not transform.granted_abilities:
            return list(actor.abilities)
        universal = [aid for aid in actor.abilities if aid in self.ruleset.abilities and self.ruleset.abilities[aid].universal]
        return [*transform.granted_abilities, *universal]

    def legal_abilities(self, state: CombatState, actor_id: str) -> list[Ability]:
        actor = state.combatants[actor_id]
        abilities = []
        transform = self.ruleset.transforms.get(actor.active_transform_id or "")
        transformed_kit = bool(transform and transform.granted_abilities)
        for ability_id in self._kit_for(actor):
            ability = self.ruleset.abilities.get(ability_id)
            if ability is None or not self._can_afford(actor, ability):
                continue
            if "magic" in ability.tags and self._is_silenced(actor):
                continue
            if transformed_kit and not ability.universal:
                abilities.append(ability)  # the form's kit ignores slots/weapon requirements
                continue
            if ability.required_weapon_type is not None and ability.required_weapon_type != actor.equipped_weapon_type:
                continue
            # docs/design/10-sistemas-de-build.md §4: a player only gets what's
            # in their Active Ability Slots, plus universal actions (Defender).
            # Enemies have no slots -- their whole kit is always on the table.
            if actor.is_player and not actor.is_companion and not ability.universal and ability_id not in actor.equipped_abilities:
                continue
            if "magic" in ability.tags and self._is_silenced(actor):
                continue
            abilities.append(ability)
        return abilities

    # -- tipos de custo (docs/design/11-habilidades.md §7) -------------------

    def _can_afford(self, actor: Character, ability: Ability) -> bool:
        if actor.cooldowns.get(ability.id, 0) > 0:
            return False
        if ability.charges_per_rest is not None and actor.charges.get(ability.id, 0) <= 0:
            return False
        if ability.pays_with_hp:
            return actor.current_hp > 1.0  # Sangue is never lethal, so 1 HP can't pay
        if ability.once_per_run and ability.id in actor.used_once_per_run:
            return False
        if ability.uses_per_combat is not None:
            cap = ability.uses_per_combat + int(actor.computed_stats(self.ruleset).extra_uses_per_combat)
            if actor.uses_this_combat.get(ability.id, 0) >= cap:
                return False
        if ability.requires_hp_below is not None:
            if actor.current_hp > ability.requires_hp_below * max(1.0, actor.computed_stats(self.ruleset).max_hp):
                return False
        if "combo_finisher" in ability.tags and actor.current_resource < 1.0:
            return False
        return actor.current_resource >= ability.resource_cost

    def _pay_cost(self, state: CombatState, actor: Character, ability: Ability) -> float:
        """Pays every cost type the ability carries; returns the combo
        points spent (0 unless it's a finisher)."""
        points_spent = 0.0
        if ability.pays_with_hp:
            hp_cost = min(actor.current_hp - 1.0, actor.current_hp * ability.resource_cost)
            actor.current_hp -= max(0.0, hp_cost)
            self._log(state, f"  {actor.name} paga {hp_cost:.0f} de PV em sangue.")
        elif "combo_finisher" in ability.tags:
            points_spent = actor.current_resource
            actor.current_resource = 0.0
            self._log(state, f"  {actor.name} gasta {points_spent:.0f} Pontos de Combo!")
        else:
            actor.current_resource -= ability.resource_cost
        if ability.resource_cost > 0 or points_spent > 0:
            actor.spent_resource_last_turn = True
        if ability.once_per_run:
            actor.used_once_per_run.add(ability.id)
        if ability.uses_per_combat is not None:
            actor.uses_this_combat[ability.id] = actor.uses_this_combat.get(ability.id, 0) + 1
        if ability.cooldown_turns > 0:
            # +1 because the casting turn's own end ticks it right away --
            # this keeps "cooldown N" meaning N full own turns unavailable
            actor.cooldowns[ability.id] = ability.cooldown_turns + 1
        if ability.charges_per_rest is not None:
            actor.charges[ability.id] = max(0, actor.charges.get(ability.id, 0) - 1)
        return points_spent

    def _tick_cooldowns(self, actor: Character) -> None:
        for ability_id, turns in list(actor.cooldowns.items()):
            if turns <= 1:
                del actor.cooldowns[ability_id]
            else:
                actor.cooldowns[ability_id] = turns - 1

    def _generate_resource_at_turn_start(self, state: CombatState, character: Character) -> None:
        stats = character.computed_stats(self.ruleset)
        if character.resource_kind == ResourceKind.ADRENALINE:
            gained = min(ADRENALINE_PER_TURN, stats.max_resource - character.current_resource)
            if gained > 0:
                character.current_resource += gained
                self._log(state, f"  {character.name} ganha {gained:.0f} de Adrenalina.")
        elif character.resource_kind == ResourceKind.FURY and not character.spent_resource_last_turn:
            lost = min(FURY_DECAY_PER_IDLE_TURN, character.current_resource)
            if lost > 0:
                character.current_resource -= lost
                self._log(state, f"  A Fúria de {character.name} esfria ({lost:.0f}).")
        character.spent_resource_last_turn = False

    # -- controle de grupo (docs/design/01-mecanicas.md §4) ----------------

    def _control_statuses(self, character: Character):
        for active in character.statuses:
            status_def = self.ruleset.statuses.get(active.status_id)
            if status_def is not None:
                yield active, status_def

    def _is_silenced(self, character: Character) -> bool:
        return any(status_def.silences for _, status_def in self._control_statuses(character))

    def _taunted_by(self, state: CombatState, character: Character) -> str | None:
        """The living taunter this character must target, if any."""
        for active, status_def in self._control_statuses(character):
            if status_def.taunts and active.source_id and state.alive(active.source_id):
                return active.source_id
        return None

    def _fear_fail_chance(self, character: Character) -> float:
        return max((status_def.fail_chance for _, status_def in self._control_statuses(character)), default=0.0)

    def use_consumable(self, state: CombatState, actor_id: str, consumable: ConsumableDef) -> list[str]:
        """Consumível em combate (docs/design/14-estrutura-da-run.md §6): a
        real action on the actor's own turn -- heals/restores, then the
        turn is spent. Tomos are out-of-combat only (nobody reads mid-fight)."""
        if state.is_over:
            raise CombatError("O combate já terminou.")
        if state.pending_parry is not None:
            raise CombatError("Há um aparo pendente -- resolva-o antes de continuar o combate.")
        if state.current_actor_id() != actor_id:
            raise CombatError("Não é a vez deste combatente.")
        if consumable.teaches_ability is not None:
            raise CombatError("Um Tomo não se lê no meio de um combate.")
        actor = state.combatants[actor_id]
        start_log_len = len(state.log)
        stats = actor.computed_stats(self.ruleset)
        self._log(state, f"{actor.name} usa {consumable.name}.")
        if consumable.heal_fraction > 0:
            healed = min(stats.max_hp - actor.current_hp, consumable.heal_fraction * stats.max_hp)
            actor.current_hp += max(0.0, healed)
            state.used_heal_this_encounter = True
            state.healing_participants.add(actor_id)
            self._log(state, f"  {actor.name} recupera {max(0.0, healed):.0f} de PV.")
        if consumable.resource_fraction > 0:
            restored = min(stats.max_resource - actor.current_resource, consumable.resource_fraction * stats.max_resource)
            actor.current_resource += max(0.0, restored)
            self._log(state, f"  {actor.name} recupera {max(0.0, restored):.0f} de recurso.")
        self._finish_action(state, actor_id)
        return state.log[start_log_len:]

    def set_stance(self, state: CombatState, actor_id: str, stance: Stance) -> list[str]:
        """Postura (docs/design/10-sistemas-de-build.md §3.9): a free switch,
        once per turn, on the actor's own turn. Doesn't advance the turn."""
        if state.is_over:
            raise CombatError("O combate já terminou.")
        if state.pending_parry is not None:
            raise CombatError("Há um aparo pendente -- resolva-o antes de trocar de postura.")
        if state.current_actor_id() != actor_id:
            raise CombatError("Só dá pra trocar de postura no próprio turno.")
        actor = state.combatants[actor_id]
        if actor.stance_switched_this_turn:
            raise CombatError("A postura já foi trocada neste turno.")
        if stance == actor.current_stance:
            raise CombatError("Essa já é a postura atual.")
        start_log_len = len(state.log)
        actor.current_stance = stance
        actor.stance_switched_this_turn = True
        self._log(state, f"{actor.name} assume a postura {STANCE_NAMES[stance]}.")
        return state.log[start_log_len:]

    def legal_target_ids(self, state: CombatState, actor_id: str, ability: Ability) -> list[str]:
        actor = state.combatants[actor_id]
        own_side = state.party_ids() if actor.is_player else state.enemy_ids()
        other_side = state.enemy_ids() if actor.is_player else state.party_ids()
        if ability.target_mode == TargetMode.SELF:
            return [actor_id]
        if ability.target_mode == TargetMode.SINGLE_ENEMY:
            # Provocar: a taunted actor's single-target picks are the
            # taunter only, as long as the taunter lives and is a legal
            # target at all
            taunter = self._taunted_by(state, actor)
            if taunter is not None and taunter in other_side:
                return [taunter]
            return [cid for cid in other_side if state.alive(cid)]
        if ability.target_mode == TargetMode.ALL_ENEMIES:
            return [cid for cid in other_side if state.alive(cid)]
        if ability.target_mode in (TargetMode.SINGLE_ALLY, TargetMode.ALL_ALLIES):
            if any(e.kind == EffectKind.REVIVE for e in ability.effects):
                # REVIVE reaches the downed too (the only thing that does)
                return [cid for cid in own_side if state.alive(cid) or state.combatants[cid].is_incapacitated]
            return [cid for cid in own_side if state.alive(cid)]
        return []

    def resolve(self, state: CombatState, action: Action) -> list[str]:
        with self._ability_scope(action.actor_id, action.ability_id):
            return self._resolve_action(state, action)

    @contextmanager
    def _ability_scope(self, actor_id: str, ability_id: str):
        previous = getattr(self, "_active_ability", None)
        self._active_ability = (actor_id, ability_id)
        try:
            yield
        finally:
            self._active_ability = previous

    def _scoped_character(self, character: Character) -> Character:
        active = getattr(self, "_active_ability", None)
        if active is None or active[0] != character.id:
            return character
        return character.model_copy(update={
            "passive_modifiers": [*character.passive_modifiers, *rune_modifiers_for(character, active[1])],
        })

    def _resolve_action(self, state: CombatState, action: Action) -> list[str]:
        if state.is_over:
            raise CombatError("O combate já terminou.")
        if state.pending_parry is not None:
            raise CombatError("Há um aparo pendente -- resolva-o antes de continuar o combate.")
        if action.actor_id != state.current_actor_id():
            raise CombatError("Não é a vez deste combatente.")
        actor = state.combatants.get(action.actor_id)
        if actor is None or not actor.is_alive:
            raise CombatError("O personagem não é um combatente válido e vivo.")
        ability = self.ruleset.abilities.get(action.ability_id)
        if ability is None or action.ability_id not in self._kit_for(actor):
            raise CombatError(f"Habilidade desconhecida ou indisponível: {action.ability_id!r}.")
        if ability not in self.legal_abilities(state, actor.id):
            raise CombatError("Habilidade não equipada ou indisponível neste turno.")
        if ability.required_weapon_type is not None and ability.required_weapon_type != actor.equipped_weapon_type and not actor.active_transform_id:
            raise CombatError(f"Requer arma equipada: {ability.required_weapon_type!r}.")
        if not self._can_afford(actor, ability):
            raise CombatError("Sem recurso, cargas ou fora do tempo de recarga para usar esta habilidade.")
        if "magic" in ability.tags and self._is_silenced(actor):
            raise CombatError("Silenciado -- não dá pra usar habilidades mágicas.")

        legal_targets = set(self.legal_target_ids(state, action.actor_id, ability))
        if ability.requires_target:
            if not action.target_ids or any(t not in legal_targets for t in action.target_ids):
                raise CombatError("Alvo inválido ou ausente.")
            targets = action.target_ids[:1]
        else:
            targets = sorted(legal_targets)

        # Medo (docs/design/01-mecanicas.md §4): rolled before the cost is
        # paid; a failed action becomes Defender, the turn is spent.
        fail_chance = self._fear_fail_chance(actor)
        if fail_chance > 0 and not ability.universal and self.rng.random() < fail_chance:
            start_log_len = len(state.log)
            self._log(state, f"{actor.name} hesita de medo e só consegue se defender!")
            guard = self.ruleset.abilities.get("guard")
            if guard is not None:
                for effect in guard.effects:
                    self._apply_effect(state, action.actor_id, action.actor_id, effect)
            self._finish_action(state, action.actor_id)
            return state.log[start_log_len:]

        start_log_len = len(state.log)
        if "magic" in ability.tags:
            actor.used_non_physical_this_area = True
        self._log(state, f"{actor.name} usa {ability.name}.")
        points_spent = self._pay_cost(state, actor, ability)
        combo_ready = bool(ability.combo_from) and actor.last_ability_id in ability.combo_from
        actor.last_ability_id = ability.id
        # Afinidade de Arquétipo is fixed-weight-per-cast, not per effect/
        # target -- it measures how central this archetype was to the
        # actor's turn decisions, not how big the resulting numbers were
        # (see domain/specializations.py::archetype_affinity).
        for archetype, weight in ability.archetype_weight.items():
            actor.archetype_usage[archetype] = actor.archetype_usage.get(archetype, 0.0) + weight
        self._fire_trigger_for(state, action.actor_id, TriggerEvent.ON_ABILITY_CAST)

        if self._is_parryable(state, actor, ability, targets):
            state.pending_parry = PendingParry(
                attacker_id=action.actor_id, defender_id=targets[0], ability_id=ability.id
            )
            return state.log[start_log_len:]

        effects = self._challenge_adjusted_effects(state, actor, ability, action.challenge_score)
        effects = self._combo_adjusted_effects(state, actor, ability, effects, points_spent, combo_ready)
        if combo_ready:
            self._fire_trigger_for(state, action.actor_id, TriggerEvent.ON_COMBO_EXTEND)
        hp_before = {tid: state.combatants[tid].current_hp for tid in targets if tid in state.combatants}
        for target_id in targets:
            for effect in effects:
                self._apply_effect(state, action.actor_id, target_id, effect)
        if "combo_builder" in ability.tags and actor.resource_kind == ResourceKind.COMBO_POINTS:
            landed = any(state.combatants[tid].current_hp < hp for tid, hp in hp_before.items())
            if landed:
                stats = actor.computed_stats(self.ruleset)
                actor.current_resource = min(stats.max_resource, actor.current_resource + COMBO_POINTS_PER_HIT)
                self._log(state, f"  {actor.name} acumula um Ponto de Combo ({actor.current_resource:.0f}).")

        self._finish_action(state, action.actor_id)
        return state.log[start_log_len:]

    def _combo_adjusted_effects(
        self, state: CombatState, actor: Character, ability: Ability, effects: list[Effect],
        points_spent: float, combo_ready: bool,
    ) -> list[Effect]:
        """Combos (docs/design/11-habilidades.md §8.1/§8.2): a finisher
        scales with the points it just spent; a sequence combo scales when
        the previous cast was one of combo_from. Both are multipliers on
        the per-action copies, same idiom as the minigame score."""
        multiplier = 1.0
        if points_spent > 0:
            multiplier *= 1.0 + COMBO_POINT_SCALING * points_spent
        if combo_ready:
            multiplier *= 1.0 + COMBO_SEQUENCE_BONUS
            self._log(state, f"  Combo! {ability.name} encadeia com a habilidade anterior.")
        if multiplier == 1.0:
            return effects
        return [
            e.model_copy(update={"amount": e.amount * multiplier, "scale_factor": e.scale_factor * multiplier})
            if e.kind in (EffectKind.DAMAGE, EffectKind.HEAL) else e
            for e in effects
        ]

    def _challenge_adjusted_effects(
        self, state: CombatState, actor: Character, ability: Ability, score: float | None
    ) -> list[Effect]:
        """Minigames de Habilidade (docs/design/11-habilidades.md §9): the
        client-side score scales the ability's damage/heal between the
        challenge's floor and 1.0 -- "errar reduz, nunca zera" -- and a
        perfect Precisão forces the crit. Enemies never play minigames."""
        effects = ability.effects
        if "cleave" in ability.tags:
            # Overkill/Cleave (01-mecanicas.md §1.4) is an ability tag; the
            # engine carries it on the per-action damage copies
            effects = [
                e.model_copy(update={"cleave": True}) if e.kind == EffectKind.DAMAGE else e for e in effects
            ]
        challenge = ability.challenge
        if challenge is None or not actor.is_player:
            return effects
        score = clamp_score(score)
        multiplier = challenge_multiplier(challenge, score)
        perfect = score >= 1.0
        self._log(state, f"  Minigame: {score * 100:.0f}% -- efeito x{multiplier:.2f}{' (Crítico garantido!)' if perfect and challenge.crit_on_perfect else ''}.")
        adjusted = []
        for effect in effects:
            if effect.kind in (EffectKind.DAMAGE, EffectKind.HEAL):
                effect = effect.model_copy(
                    update={
                        "amount": effect.amount * multiplier,
                        "scale_factor": effect.scale_factor * multiplier,
                        "guaranteed_crit": effect.guaranteed_crit or (perfect and challenge.crit_on_perfect),
                    }
                )
            adjusted.append(effect)
        return adjusted

    def _is_parryable(self, state: CombatState, actor: Character, ability: Ability, targets: list[str]) -> bool:
        if actor.is_player or "melee" not in ability.tags or ability.target_mode != TargetMode.SINGLE_ENEMY:
            return False
        if len(targets) != 1:
            return False
        defender = state.combatants.get(targets[0])
        return bool(defender is not None and defender.can_parry)

    def resolve_parry(self, state: CombatState, result: ParryResult) -> list[str]:
        pending = state.pending_parry
        if pending is None:
            raise CombatError("Não há um aparo pendente para resolver.")
        with self._ability_scope(pending.attacker_id, pending.ability_id):
            return self._resolve_parry(state, result)

    def _resolve_parry(self, state: CombatState, result: ParryResult) -> list[str]:
        pending = state.pending_parry
        if pending is None:
            raise CombatError("Não há um aparo pendente para resolver.")
        state.pending_parry = None
        attacker = state.combatants.get(pending.attacker_id)
        defender = state.combatants.get(pending.defender_id)
        ability = self.ruleset.abilities.get(pending.ability_id)
        start_log_len = len(state.log)

        if attacker is None or defender is None or ability is None:
            self._finish_action(state, pending.attacker_id)
            return state.log[start_log_len:]

        if result is ParryResult.SUCCESS:
            self._log(state, f"  {defender.name} apara o ataque de {attacker.name}!")
            self._fire_trigger_for(state, pending.defender_id, TriggerEvent.ON_PARRY_SUCCESS, context_id=pending.attacker_id)
            state.had_successful_parry = True
            counter = Effect(kind=EffectKind.DAMAGE, amount=0.0, scales_with=Stat.ATTACK, scale_factor=0.35)
            self._apply_effect(state, pending.defender_id, pending.attacker_id, counter)
        else:
            if result is ParryResult.FAILURE:
                self._log(state, f"  {defender.name} falha ao tentar aparar!")
                self._fire_trigger_for(state, pending.defender_id, TriggerEvent.ON_PARRY_FAIL, context_id=pending.attacker_id)
            for effect in ability.effects:
                if effect.kind == EffectKind.DAMAGE and result is ParryResult.FAILURE:
                    effect = effect.model_copy(
                        update={
                            "amount": effect.amount * _PARRY_FAIL_MULTIPLIER,
                            "scale_factor": effect.scale_factor * _PARRY_FAIL_MULTIPLIER,
                        }
                    )
                self._apply_effect(state, pending.attacker_id, pending.defender_id, effect)

        self._finish_action(state, pending.attacker_id)
        return state.log[start_log_len:]

    def _finish_action(self, state: CombatState, actor_id: str) -> None:
        self._active_ability = None
        self._check_victory(state)
        actor = state.combatants.get(actor_id)
        if actor is not None:
            self._tick_cooldowns(actor)  # 11-habilidades.md §7.3: decremented at the owner's turn end
        if not state.is_over:
            self._fire_trigger_for(state, actor_id, TriggerEvent.ON_TURN_END)
            self._advance_turn(state)

    def resolve_ai_turn(self, state: CombatState) -> list[str]:
        if state.pending_parry is not None:
            raise CombatError("Há um aparo pendente -- resolva-o antes de continuar o combate.")
        actor_id = state.current_actor_id()
        actor = state.combatants[actor_id]
        if not actor.acts_automatically:
            raise CombatError("resolve_ai_turn called on a player-controlled combatant.")

        candidates = [ability.id for ability in self.legal_abilities(state, actor_id)
                      if self.legal_target_ids(state, actor_id, ability)]
        if not candidates:
            start_log_len = len(state.log)
            self._log(state, f"{actor.name} não tem o que fazer e passa a vez.")
            self._check_victory(state)
            if not state.is_over:
                self._advance_turn(state)
            return state.log[start_log_len:]

        ability_id = self.rng.choice(candidates)
        ability = self.ruleset.abilities[ability_id]
        legal_targets = self.legal_target_ids(state, actor_id, ability)
        target_ids: list[str] = []
        if ability.requires_target and legal_targets:
            target_ids = [self._choose_ai_target(state, legal_targets)]

        return self.resolve(state, Action(actor_id=actor_id, ability_id=ability_id, target_ids=target_ids))

    # -- internals ------------------------------------------------------

    def _log(self, state: CombatState, text: str) -> None:
        state.log.append(text)

    def _choose_ai_target(self, state: CombatState, candidates: list[str]) -> str:
        def hp_fraction(cid: str) -> float:
            combatant = state.combatants[cid]
            stats = combatant.computed_stats(self.ruleset)
            return combatant.current_hp / max(1.0, stats.max_hp)

        weights = [max(0.05, 1.0 - hp_fraction(cid)) + 0.1 for cid in candidates]
        return self.rng.choices(candidates, weights=weights, k=1)[0]

    def _compute_turn_order(self, combatants: dict[str, Character]) -> list[str]:
        def speed_of(cid: str) -> float:
            return combatants[cid].computed_stats(self.ruleset).speed

        ids = list(combatants.keys())
        ids.sort(key=lambda cid: (-speed_of(cid), 0 if combatants[cid].is_player else 1, cid))
        return ids

    def _advance_index(self, state: CombatState) -> bool:
        """Move turn_index to the next living combatant. Returns True if a new round began."""
        n = len(state.turn_order)
        idx = state.turn_index
        wrapped = False
        for _ in range(n):
            idx += 1
            if idx >= n:
                idx = 0
                wrapped = True
            if state.alive(state.turn_order[idx]):
                state.turn_index = idx
                return wrapped
        return wrapped

    def _advance_turn(self, state: CombatState) -> None:
        self._check_victory(state)
        while not state.is_over:
            if self._advance_index(state):
                state.round_number += 1
            if self._begin_turn(state, state.current_actor_id()):
                break

    def _begin_turn(self, state: CombatState, actor_id: str) -> bool:
        """Prepare the actor's turn and report whether they can act."""
        character = state.combatants[actor_id]
        character.stance_switched_this_turn = False
        if character.death_ward_turns > 0:
            character.death_ward_turns -= 1
        if character.active_transform_id and character.transform_turns_left > 0:
            character.transform_turns_left -= 1
            if character.transform_turns_left == 0:
                self._end_transform(state, character)
        if character.stunned_turns > 0:
            character.stunned_turns -= 1
            self._log(state, f"  {character.name} está atordoado e perde o turno!")
            return False
        self._fire_trigger_for(state, actor_id, TriggerEvent.ON_TURN_START)
        self._tick_statuses(state, actor_id)
        self._regen_resource(state, actor_id)
        if character.is_alive:
            self._generate_resource_at_turn_start(state, character)
        self._check_victory(state)
        return character.is_alive

    def _regen_resource(self, state: CombatState, character_id: str) -> None:
        character = state.combatants.get(character_id)
        if character is None or not character.is_alive:
            return
        stats = character.computed_stats(self.ruleset)
        if stats.resource_regen_per_turn <= 0:
            return
        before = character.current_resource
        character.current_resource = min(stats.max_resource, before + stats.resource_regen_per_turn)
        if character.current_resource > before:
            self._log(state, f"  {character.name} regenera {character.current_resource - before:.0f} de Resolução.")

    def _tick_statuses(self, state: CombatState, character_id: str) -> None:
        character = state.combatants.get(character_id)
        if character is None:
            return
        remaining: list[ActiveStatus] = []
        for active in character.statuses:
            active.remaining_duration -= 1
            if active.remaining_duration > 0:
                remaining.append(active)
            else:
                status_def = self.ruleset.statuses.get(active.status_id)
                name = status_def.name if status_def else active.status_id
                self._log(state, f"  {name} desaparece de {character.name}.")
        character.statuses = remaining

    def _check_victory(self, state: CombatState) -> None:
        if state.is_over:
            return
        # Fase 9: a live Companheiro with a dead party is still a defeat
        party_alive = any(state.alive(cid) for cid in state.party_ids() if not state.combatants[cid].is_companion)
        enemies_alive = any(state.alive(cid) for cid in state.enemy_ids())
        if not enemies_alive:
            state.is_over = True
            state.victory = True
            self._log(state, "Vitória!")
        elif not party_alive:
            state.is_over = True
            state.victory = False
            self._log(state, "O grupo caiu...")

    def _apply_status(
        self, state: CombatState, target: Character, status_id: str, duration: int, stacks: int,
        source_id: str | None = None,
    ) -> None:
        status_def = self.ruleset.statuses.get(status_id)
        if status_def is None:
            return
        if status_id in target.status_immunities:
            self._log(state, f"  {target.name} é imune a {status_def.name}.")
            return
        target_stats = target.computed_stats(self.ruleset)
        if target_stats.status_resist > 0 and self.rng.random() < target_stats.status_resist:
            self._log(state, f"  {target.name} resiste ao efeito: {status_def.name}.")
            return
        if status_def.exclusive_with and any(s.status_id == status_def.exclusive_with for s in target.statuses):
            target.statuses = [s for s in target.statuses if s.status_id != status_def.exclusive_with]
            self._log(state, f"  {status_def.name} anula o efeito oposto em {target.name}.")
        existing = next((s for s in target.statuses if s.status_id == status_id), None)
        if existing is not None:
            existing.stacks = min(status_def.max_stacks, existing.stacks + stacks)
            existing.remaining_duration = max(existing.remaining_duration, duration)
            if source_id is not None:
                existing.source_id = source_id  # the latest taunter wins
        else:
            target.statuses.append(
                ActiveStatus(
                    status_id=status_id,
                    stacks=min(status_def.max_stacks, max(1, stacks)),
                    remaining_duration=duration,
                    source_id=source_id,
                )
            )
        self._log(state, f"  {target.name} recebe o efeito: {status_def.name}.")
        if status_id == "instinto_selvagem" and target.race_id == "licantropo" and not target.active_transform_id:
            # 04-racas.md Licantropo: "ao atingir um número alto de stacks de
            # Instinto num único combate, transforma-se ... pelo resto daquele combate"
            stacks_now = next((s.stacks for s in target.statuses if s.status_id == "instinto_selvagem"), 0)
            if stacks_now >= LYCAN_TRANSFORM_STACKS and "forma_de_fera" in self.ruleset.transforms:
                self._transform(state, target, "forma_de_fera")

    def _transform(self, state: CombatState, target: Character, transform_id: str) -> None:
        transform = self.ruleset.transforms.get(transform_id)
        if transform is None or not target.is_alive:
            return
        target.active_transform_id = transform.id
        target.transform_turns_left = transform.duration
        target.transform_modifiers = list(transform.modifiers)
        target.transformed_this_run = True
        self._log(state, f"  {target.name} se transforma: {transform.name}!")

    def _end_transform(self, state: CombatState, target: Character) -> None:
        transform = self.ruleset.transforms.get(target.active_transform_id or "")
        target.active_transform_id = None
        target.transform_turns_left = 0
        target.transform_modifiers = []
        if transform is not None:
            self._log(state, f"  {target.name} volta à forma normal ({transform.name} termina).")

    def _check_race_evolution(self, state: CombatState, character: Character) -> None:
        """Evolução de raça (04-racas.md item 5) for the conditions a fight
        can satisfy on its own -- Orc's PV threshold, Elfo's crits, Fada's
        procs. Boss/Área-keyed ones live in GameSession."""
        evolution = pending_race_evolution(character, max_hp=character.computed_stats(self.ruleset).max_hp)
        if evolution is None:
            return
        apply_race_evolution(character, evolution)
        self._log(state, f"  {character.name} evolui: {evolution.name}!")
        for effect in evolution.on_evolve_effects:
            self._apply_effect(state, character.id, character.id, effect)

    def _apply_effect(self, state: CombatState, source_id: str, target_id: str, effect: Effect) -> None:
        source = state.combatants.get(source_id)
        target = state.combatants.get(target_id)
        if source is None or target is None:
            return
        if effect.kind == EffectKind.REVIVE:
            # the one effect that acts on a downed target -- checked before
            # the alive gate below
            if target.is_incapacitated:
                max_hp = target.computed_stats(self.ruleset).max_hp
                target.current_hp = max(1.0, effect.amount * max_hp)
                target.statuses = []
                self._log(state, f"  {target.name} volta à luta com {target.current_hp:.0f} PV!")
                self._fire_trigger_for(state, target_id, TriggerEvent.ON_REVIVE, context_id=source_id)
            return
        if not target.is_alive:
            return
        # docs/design/01-mecanicas.md §8: per-effect proc chance (1.0 never
        # rolls, so it costs nothing on the rng stream)
        if effect.chance < 1.0 and self.rng.random() >= effect.chance:
            return
        source_stats = self._scoped_character(source).computed_stats(self.ruleset)

        if effect.kind == EffectKind.DAMAGE:
            self._apply_damage(state, source, source_stats, target, effect)

        elif effect.kind == EffectKind.HEAL:
            target_stats = target.computed_stats(self.ruleset)
            amount = (
                effect.resolve_amount(source_stats)
                * (1.0 + source_stats.healing_done_percent)
                * (1.0 + target_stats.healing_received_percent)
            )
            target.current_hp = min(target_stats.max_hp, target.current_hp + amount)
            self._log(state, f"  {target.name} recupera {amount:.0f} de PV.")
            if target.is_player:
                state.used_heal_this_encounter = True
                state.healing_participants.add(target.owner_id or target.id)
                if source.is_player:
                    state.healing_participants.add(source.owner_id or source.id)

        elif effect.kind == EffectKind.RESTORE_RESOURCE:
            target_stats = target.computed_stats(self.ruleset)
            amount = effect.resolve_amount(source_stats)
            target.current_resource = min(target_stats.max_resource, target.current_resource + amount)
            self._log(state, f"  {target.name} recupera {amount:.0f} de Resolução.")

        elif effect.kind == EffectKind.DRAIN_RESOURCE:
            amount = effect.resolve_amount(source_stats)
            drained = min(target.current_resource, amount)
            target.current_resource -= drained
            source.current_resource = min(source_stats.max_resource, source.current_resource + drained)
            self._log(state, f"  {source.name} rouba {drained:.0f} de Resolução de {target.name}.")

        elif effect.kind == EffectKind.APPLY_SHIELD:
            amount = effect.resolve_amount(source_stats)
            target.shield_hp += amount
            self._log(state, f"  {target.name} ganha um escudo de {amount:.0f}.")

        elif effect.kind == EffectKind.APPLY_STATUS and effect.status_id:
            self._apply_status(state, target, effect.status_id, effect.duration, effect.stacks, source_id=source_id)

        elif effect.kind == EffectKind.CLEANSE:
            self._cleanse(state, target, int(effect.amount))

        elif effect.kind == EffectKind.DEATH_WARD:
            # Abraçar a Morte (04-racas.md): immune to fatal damage for
            # `amount` turns, at the price of `scale_factor` of max HP for
            # the rest of the run
            target.death_ward_turns = max(target.death_ward_turns, int(effect.amount))
            if effect.scale_factor > 0:
                target.permanent_modifiers.append(
                    Modifier(stat=Stat.MAX_HP, kind=ModifierKind.PERCENT, value=-effect.scale_factor, source="death_ward")
                )
                target.passive_modifiers.append(target.permanent_modifiers[-1])
                max_hp = target.computed_stats(self.ruleset).max_hp
                target.current_hp = min(target.current_hp, max_hp)
            self._log(state, f"  {target.name} abraça a morte -- e a morte recua, por enquanto.")

        elif effect.kind == EffectKind.SUMMON and effect.summon_id:
            self._summon(state, source, effect.summon_id)

        elif effect.kind == EffectKind.TRANSFORM and effect.transform_id:
            self._transform(state, target, effect.transform_id)

    def _cleanse(self, state: CombatState, target: Character, count: int) -> None:
        """CLEANSE (11-habilidades.md §5): strips harmful statuses, most
        recent first -- all of them when count is 0, else up to count."""
        harmful = [
            s for s in reversed(target.statuses)
            if (d := self.ruleset.statuses.get(s.status_id)) is not None and d.is_harmful
        ]
        if count > 0:
            harmful = harmful[:count]
        if not harmful:
            return
        removed = set(id(s) for s in harmful)
        target.statuses = [s for s in target.statuses if id(s) not in removed]
        names = ", ".join(self.ruleset.statuses[s.status_id].name for s in harmful)
        self._log(state, f"  {target.name} se livra de: {names}.")

    def _summon(self, state: CombatState, source: Character, summon_id: str) -> None:
        """SUMMON (11-habilidades.md §5): a temporary combatant on the
        summoner's side, acting on its own (is_companion), appended to the
        end of the turn order. Lives in CombatState only -- the session
        never syncs it to the run, so it's gone with the fight."""
        summon_def = self.ruleset.summons.get(summon_id)
        if summon_def is None:
            return
        index = sum(1 for cid in state.combatants if cid.startswith(f"{source.id}_summon_"))
        instance_id = f"{source.id}_summon_{index}"
        stats = summon_def.base_stats.model_copy()
        summon = Character(
            id=instance_id, name=summon_def.name, class_id=summon_def.id, base_stats=stats,
            current_hp=stats.max_hp, current_resource=stats.max_resource, current_poise=stats.max_poise,
            abilities=list(summon_def.abilities), equipped_abilities=list(summon_def.abilities),
            tags=set(summon_def.tags), is_player=source.is_player, is_companion=True, owner_id=source.id,
        )
        state.combatants[instance_id] = summon
        state.turn_order.append(instance_id)
        self._log(state, f"  {source.name} invoca {summon.name}!")

    def _elemental_resistance(self, target_stats: StatBlock, element: DamageElement) -> float:
        specific = getattr(target_stats, f"{element.value}_resist", 0.0)
        total = specific + target_stats.general_elemental_resist
        return min(_MAX_ELEMENTAL_RESIST, max(_MIN_ELEMENTAL_RESIST, total))

    def _apply_damage(
        self, state: CombatState, source: Character, source_stats: StatBlock, target: Character, effect: Effect,
        *, derived_damage: bool = False,
    ) -> None:
        source_id, target_id = source.id, target.id

        # Fase 7 (Área 11, Nyxelle) -- conditional immunity while named
        # allies are alive. Checked before anything else (dodge included):
        # she isn't even rollable against while an Eco lives.
        if target.immune_while_allies_alive and any(
            state.combatants[aid].is_alive for aid in target.immune_while_allies_alive if aid in state.combatants
        ):
            self._log(state, f"  {target.name} está imune enquanto seus aliados protegem!")
            return

        target_stats = target.computed_stats(self.ruleset)

        # Posturas (docs/design/10-sistemas-de-build.md §3.9): Evasiva
        # raises the target's Esquiva, Precisa lowers the target's effective
        # Esquiva against this attacker -- both on the roll threshold only.
        dodge_chance = target_stats.dodge_chance
        if target.current_stance == "evasive":
            dodge_chance += STANCE_DODGE_BONUS
        if source.current_stance == "precise":
            dodge_chance = max(0.0, dodge_chance - STANCE_PRECISION)
        if self.rng.random() < dodge_chance:
            self._log(state, f"  {target.name} esquiva do ataque!")
            self._fire_trigger_for(state, target_id, TriggerEvent.ON_DODGE, context_id=source_id)
            return

        raw = effect.resolve_amount(source_stats)
        if effect.bonus_vs_tags and target.tags.intersection(effect.bonus_vs_tags):
            raw *= 1.0 + effect.bonus_vs_tags_bonus
        # Combo em Equipe (11-habilidades.md §8.4): a mark set by a DIFFERENT
        # ally of the attacker is consumed for bonus damage; never solo
        team_combo = False
        for active in list(target.statuses):
            status_def = self.ruleset.statuses.get(active.status_id)
            if status_def is None or status_def.team_combo_bonus <= 0 or not active.source_id:
                continue
            marker = state.combatants.get(active.source_id)
            if marker is None or marker.id == source.id or marker.is_player != source.is_player:
                continue
            raw *= 1.0 + status_def.team_combo_bonus
            target.statuses.remove(active)
            team_combo = True
            self._log(state, f"  Combo em equipe! {source.name} aproveita a marca de {marker.name}.")
            self._fire_trigger_for(state, source.id, TriggerEvent.ON_TEAM_COMBO, context_id=target.id)
            break
        # Execução (01-mecanicas.md §1.3): bonus against low-HP targets
        executing = False
        if effect.execute_threshold is not None and target.current_hp <= effect.execute_threshold * max(1.0, target_stats.max_hp):
            raw *= 1.0 + effect.execute_bonus
            executing = True
        # Ofensiva: hit harder, get hit harder -- the explicit trade-off
        if source.current_stance == "offensive":
            raw *= 1.0 + STANCE_DAMAGE_BONUS
        if target.current_stance == "offensive":
            raw *= 1.0 + STANCE_DAMAGE_BONUS
        effective_crit_chance = max(0.0, source_stats.crit_chance - target_stats.crit_resist)
        # the roll always happens so a guaranteed crit never shifts the seed
        is_crit = (self.rng.random() < effective_crit_chance) or effect.guaranteed_crit
        if is_crit:
            raw *= source_stats.crit_mult
            source.crits_landed += 1  # Elfo's Fúria Élfica counts these (domain/race_evolution.py)
        # Weapon scaling amplifies every damage instance regardless of
        # element (docs/design/10-sistemas-de-build.md §2) -- unlike
        # physical_damage_percent/elemental_damage_percent below, which
        # only apply to their own branch.
        raw *= 1.0 + source_stats.weapon_damage_percent

        # Fase 7 (Área 11) -- Arcano's "elemento de dano aleatório a cada
        # turno" (Paradoxo Ambulante/Eco Arcano). Resolved into a LOCAL
        # variable rather than mutated onto `effect` itself, since the
        # same Effect object is reused across turns/targets (mutating it
        # would leak the last roll back into the shared ability def).
        damage_element = effect.damage_element
        if effect.random_damage_element:
            damage_element = self.rng.choice([e for e in DamageElement if e != DamageElement.PHYSICAL])
        if not derived_damage and source.evolution_variants.element == damage_element:
            raw *= 1.0 + ELEMENTAL_VARIANT_DAMAGE

        # Fase 7 (Área 11, Nyxelle) -- "dano Arcano nela cura em vez de
        # ferir". Early-return: a heal skips block/shield/poise/phase/
        # lifesteal/chain entirely, none of which make sense for it.
        if damage_element == target.absorbs_damage_element:
            healed = min(target_stats.max_hp - target.current_hp, raw)
            if healed > 0:
                target.current_hp += healed
            self._log(state, f"  {target.name} absorve o dano e se cura em {healed:.0f}!")
            return

        if damage_element == DamageElement.PHYSICAL:
            raw *= 1.0 + source_stats.physical_damage_percent
            effective_defense = target_stats.defense * (1.0 - source_stats.armor_penetration_percent)
            damage = max(1.0, raw - effective_defense) * (1.0 + target_stats.physical_vulnerability_percent)
        else:
            raw *= 1.0 + source_stats.elemental_damage_percent + source.element_damage_bonus(self.ruleset, damage_element)
            resist = self._elemental_resistance(target_stats, damage_element)
            # Fase 7 (Área 11, Livro Errante) -- "ignora uma fração de
            # resistência elemental do alvo".
            resist *= 1.0 - effect.resist_penetration_percent
            damage = max(1.0, raw * (1.0 - resist))

        is_blocked = self.rng.random() < target_stats.block_chance
        if is_blocked:
            damage *= 1.0 - target_stats.block_percent

        absorbed = 0.0
        if target.shield_hp > 0:
            absorbed = min(target.shield_hp, damage)
            target.shield_hp -= absorbed
            damage -= absorbed

        new_hp = target.current_hp - damage
        overkill = max(0.0, -new_hp)
        if new_hp <= 0 and target.death_ward_turns > 0:
            target.current_hp = 1.0  # warded: fatal damage stops at 1 HP
            self._log(state, f"  {target.name} deveria cair -- mas a morte espera.")
        elif new_hp <= 0 and target.can_cheat_death and not target.cheated_death_used:
            target.cheated_death_used = True
            target.current_hp = 1.0
            self._log(state, f"  {target.name} recusa cair -- Nunca Desista!")
        else:
            target.current_hp = max(0.0, new_hp)

        if target.is_player:
            state.damage_taken_this_encounter += damage
            if damage > 0 and damage_element != DamageElement.PHYSICAL:
                state.took_elemental_damage_this_encounter = True
                state.elemental_damage_recipients.add(target.owner_id or target.id)
        if target.resource_kind == ResourceKind.FURY and damage > 0 and target.is_alive:
            gained = min(FURY_PER_HIT_TAKEN, target_stats.max_resource - target.current_resource)
            if gained > 0:
                target.current_resource += gained
                self._log(state, f"  A Fúria de {target.name} sobe ({target.current_resource:.0f}).")

        # Afinidade Elemental is magnitude-based and has no class-tree
        # exception (unlike Arquétipo above) -- every damage instance
        # counts on the source, regardless of what produced it.
        source.elemental_usage[damage_element] = source.elemental_usage.get(damage_element, 0.0) + damage

        poise_broke = False
        if effect.poise_damage > 0 and target_stats.max_poise > 0 and target.is_alive:
            target.current_poise -= effect.poise_damage
            if target.current_poise <= 0:
                target.current_poise = target_stats.max_poise
                target.stunned_turns += 1
                target.poise_breaks += 1
                poise_broke = True

        entered_new_phase = False
        if target.is_alive and target.enemy_phases:
            phases = target.enemy_phases
            if any(p.trigger == "poise_break" for p in phases):
                # 13-chefes.md: phases keyed off Postura breaks, not PV
                new_phase_index = target.current_phase_index
                if poise_broke:
                    if target.random_phase_on_break and len(phases) > 1:
                        options = [i for i in range(len(phases)) if i != target.current_phase_index]
                        new_phase_index = self.rng.choice(options)
                    else:
                        new_phase_index = min(target.poise_breaks, len(phases) - 1)
            else:
                fraction = target.current_hp / max(1.0, target_stats.max_hp)
                new_phase_index = self._resolve_phase_index(fraction, phases)
            if new_phase_index != target.current_phase_index:
                self._enter_phase(state, target, new_phase_index)
                entered_new_phase = True

        if source_stats.lifesteal_percent > 0 and damage > 0:
            healed = min(source_stats.max_hp - source.current_hp, damage * source_stats.lifesteal_percent)
            if healed > 0:
                source.current_hp += healed
                if source.is_player:
                    state.used_heal_this_encounter = True
                    state.healing_participants.add(source.owner_id or source.id)

        crit_text = " (Crítico!)" if is_crit else ""
        if executing:
            crit_text += " (Execução!)"
        block_text = " (Bloqueado)" if is_blocked else ""
        shield_text = f" ({absorbed:.0f} absorvido pelo escudo)" if absorbed > 0 else ""
        self._log(
            state,
            f"  {target.name} sofre {damage:.0f} de dano{crit_text}{block_text}{shield_text}. "
            f"({target.current_hp:.0f}/{target_stats.max_hp:.0f} PV)",
        )
        if poise_broke:
            self._log(state, f"  A postura de {target.name} se quebra! Atordoado!")
            self._fire_trigger_for(state, source_id, TriggerEvent.ON_POISE_BREAK, context_id=target_id)
            self._fire_trigger_for(state, target_id, TriggerEvent.ON_POISE_BREAK, context_id=source_id)
        if entered_new_phase:
            self._log(state, f"  {target.name} entra em uma nova fase!")
        if target.is_player:
            self._check_race_evolution(state, target)  # Orc: first time below 30% PV
        if source.is_player and is_crit:
            self._check_race_evolution(state, source)  # Elfo: crit count
        if is_blocked:
            self._fire_trigger_for(state, target_id, TriggerEvent.ON_BLOCK, context_id=source_id)
        self._fire_trigger_for(state, target_id, TriggerEvent.ON_TAKE_DAMAGE, context_id=source_id)
        self._fire_trigger_for(state, source_id, TriggerEvent.ON_HIT, context_id=target_id)
        if is_crit:
            self._fire_trigger_for(state, source_id, TriggerEvent.ON_CRIT, context_id=target_id)
        if not target.is_alive:
            self._log(state, f"  {target.name} foi derrotado!")
            self._fire_trigger_for(state, source_id, TriggerEvent.ON_KILL, context_id=target_id)
            self._fire_trigger_for(state, target_id, TriggerEvent.ON_DEATH, context_id=source_id)
            self._fire_ally_downed(state, target_id)

        if effect.chain_percent > 0 and damage > 0:
            self._apply_chain_hit(state, source, source_stats, target_id, effect, damage)
        if effect.cleave and overkill > 0 and not target.is_alive:
            self._apply_cleave_overflow(state, source, source_stats, target_id, effect, overkill)

    def _apply_cleave_overflow(
        self, state: CombatState, source: Character, source_stats: StatBlock, killed_target_id: str,
        effect: Effect, overkill: float,
    ) -> None:
        """Overkill/Cleave (docs/design/01-mecanicas.md §1.4): the damage
        that went past the kill "vaza" onto the next living target of the
        same side, through the normal pipeline, as a plain hit that can't
        cleave again (cleave defaults to False on the synthetic effect)."""
        killed = state.combatants[killed_target_id]
        side_ids = state.party_ids() if killed.is_player else state.enemy_ids()
        next_id = next((cid for cid in side_ids if cid != killed_target_id and state.alive(cid)), None)
        if next_id is None:
            return
        self._log(state, f"  O golpe atravessa e atinge {state.combatants[next_id].name}!")
        overflow = Effect(kind=EffectKind.DAMAGE, amount=overkill, damage_element=effect.damage_element)
        self._apply_damage(state, source, source_stats, state.combatants[next_id], overflow, derived_damage=True)

    def _apply_chain_hit(
        self, state: CombatState, source: Character, source_stats: StatBlock, primary_target_id: str,
        effect: Effect, primary_damage: float,
    ) -> None:
        """Raio's "encadeia" mechanic (docs/design/02-elementos.md): a
        flat percentage of the damage just dealt also hits one other
        random living target on the same side as the primary target.
        Recurses into _apply_damage with a synthetic, already-scaled
        Effect (chain_percent defaults to 0.0 on it, so this can't chain
        again) -- the secondary hit goes through the exact same dodge/
        crit/resist/block/shield/poise/phase/trigger pipeline as any
        other hit, just against a bystander."""
        primary_target = state.combatants[primary_target_id]
        side_ids = state.party_ids() if primary_target.is_player else state.enemy_ids()
        candidates = [cid for cid in side_ids if cid != primary_target_id and state.alive(cid)]
        if not candidates:
            return
        secondary_id = self.rng.choice(candidates)
        self._log(state, f"  O ataque encadeia para {state.combatants[secondary_id].name}!")
        chain_effect = Effect(
            kind=EffectKind.DAMAGE, amount=primary_damage * effect.chain_percent, damage_element=effect.damage_element,
        )
        self._apply_damage(state, source, source_stats, state.combatants[secondary_id], chain_effect, derived_damage=True)

    def _enter_phase(self, state: CombatState, target: Character, index: int) -> None:
        """Swaps the moveset, the phase's own modifiers, and brings in the
        phase's summon (if any) while the cap allows."""
        phase = target.enemy_phases[index]
        target.current_phase_index = index
        target.abilities = list(phase.abilities)
        target.phase_modifiers = list(phase.modifiers)
        if phase.summon_id is not None:
            alive_summons = sum(
                1 for cid, c in state.combatants.items()
                if cid.startswith(f"{target.id}_summon_") and c.is_alive
            )
            if alive_summons < _PHASE_SUMMON_CAP:
                self._summon(state, target, phase.summon_id)

    def _resolve_phase_index(self, hp_fraction: float, phases: list[EnemyPhase]) -> int:
        active_index = 0
        for index, phase in enumerate(phases):
            if hp_fraction <= phase.hp_ceiling:
                active_index = index
        return active_index

    def _fire_ally_downed(self, state: CombatState, downed_id: str) -> None:
        """ON_ALLY_DOWNED (11-habilidades.md §14) on every living combatant
        of the downed one's side -- a party member going Incapacitado or an
        enemy falling next to its pack alike."""
        downed = state.combatants.get(downed_id)
        if downed is None:
            return
        side = state.party_ids() if downed.is_player else state.enemy_ids()
        for ally_id in side:
            if ally_id != downed_id and state.alive(ally_id):
                self._fire_trigger_for(state, ally_id, TriggerEvent.ON_ALLY_DOWNED, context_id=downed_id)

    def _fire_trigger_for(
        self,
        state: CombatState,
        character_id: str,
        trigger: TriggerEvent,
        context_id: str | None = None,
    ) -> None:
        character = state.combatants.get(character_id)
        if character is None:
            return
        if not character.is_alive and trigger is not TriggerEvent.ON_DEATH:
            return
        # Triggers can cascade (Espinhos reflecting damage that fires another
        # Espinhos, ON_HIT feeding ON_TAKE_DAMAGE, ...). A cascade is fine, an
        # echo isn't: past MAX_TRIGGER_DEPTH nested reactions nothing more
        # fires -- found by the headless bot as an infinite recursion.
        if self._trigger_depth >= MAX_TRIGGER_DEPTH:
            return
        self._trigger_depth += 1
        try:
            self._fire_trigger_effects(state, character, character_id, trigger, context_id)
        finally:
            self._trigger_depth -= 1

    def _fire_trigger_effects(
        self, state: CombatState, character: Character, character_id: str, trigger: TriggerEvent, context_id: str | None,
    ) -> None:
        proc_bonus = 1.0 + character.computed_stats(self.ruleset).proc_chance_percent
        effects = character.all_triggered_effects(self.ruleset)
        active = getattr(self, "_active_ability", None)
        if active is not None and active[0] == character_id:
            effects = [*effects, *rune_triggered_effects_for(character, active[1])]
        for triggered in effects:
            if triggered.trigger != trigger:
                continue
            effective_chance = min(1.0, triggered.chance * proc_bonus)
            if effective_chance < 1.0:
                if self.rng.random() > effective_chance:
                    continue
                character.procs_fired += 1  # Fada's Sorte do Acaso counts these (domain/race_evolution.py)
                if character.is_player:
                    self._check_race_evolution(state, character)
            if triggered.applies_to == "all_enemies":
                opposite_side = state.enemy_ids() if character.is_player else state.party_ids()
                for target_id in opposite_side:
                    if state.alive(target_id):
                        self._apply_effect(state, character_id, target_id, triggered.effect)
                continue
            target_id = context_id if (triggered.applies_to == "context" and context_id) else character_id
            self._apply_effect(state, character_id, target_id, triggered.effect)
