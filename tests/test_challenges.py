"""Minigames de Habilidade (docs/design/11-habilidades.md §9) -- the domain
side: only the score reaches CombatEngine, and it scales the effect
between the challenge's floor and 1.0 ("errar reduz, nunca zera")."""

import random

import pytest

from wyrdfall.domain.abilities import Ability, TargetMode
from wyrdfall.domain.challenges import ChallengeDef, ChallengeKind, challenge_multiplier, clamp_score
from wyrdfall.domain.character import Character, Ruleset
from wyrdfall.domain.combat import Action, CombatEngine
from wyrdfall.domain.content import build_ruleset
from wyrdfall.domain.models import Effect, EffectKind, Stat, StatBlock


def test_multiplier_runs_from_the_floor_to_one_and_the_score_is_clamped():
    challenge = ChallengeDef(min_factor=0.5)
    assert challenge_multiplier(challenge, 0.0) == pytest.approx(0.5)
    assert challenge_multiplier(challenge, 0.5) == pytest.approx(0.75)
    assert challenge_multiplier(challenge, 1.0) == pytest.approx(1.0)
    assert challenge_multiplier(challenge, None) == pytest.approx(0.5)  # missing = the floor, never nothing
    assert clamp_score(7.0) == 1.0 and clamp_score(-3.0) == 0.0
    assert challenge_multiplier(ChallengeDef(min_factor=1.0), 0.0) == pytest.approx(1.0)  # Precisão never reduces


def _ruleset(challenge: ChallengeDef | None, crit_chance_matters: bool = False) -> Ruleset:
    heavy = Ability(
        id="heavy", name="Heavy", target_mode=TargetMode.SINGLE_ENEMY,
        effects=[Effect(kind=EffectKind.DAMAGE, amount=4, scales_with=Stat.ATTACK, scale_factor=1.0)],
        challenge=challenge,
    )
    bite = Ability(
        id="bite", name="Bite", target_mode=TargetMode.SINGLE_ENEMY,
        effects=[Effect(kind=EffectKind.DAMAGE, amount=2, scales_with=Stat.ATTACK, scale_factor=1.0)],
        challenge=challenge if crit_chance_matters else None,
    )
    return Ruleset(abilities={"heavy": heavy, "bite": bite}, statuses={})


def _hero() -> Character:
    stats = StatBlock(max_hp=30, attack=5, defense=1, speed=10, crit_chance=0.0, crit_mult=2.0, max_resource=0)
    return Character(id="hero", name="Hero", class_id="w", base_stats=stats, current_hp=30, current_resource=0,
                     abilities=["heavy"], equipped_abilities=["heavy"])


def _goblin() -> Character:
    stats = StatBlock(max_hp=50, attack=2, defense=0, speed=5, crit_chance=0.0, crit_mult=1.5, max_resource=0)
    return Character(id="goblin", name="Goblin", class_id="g", base_stats=stats, current_hp=50, current_resource=0,
                     abilities=["bite"], is_player=False)


def _damage_dealt(challenge, score, seed=1) -> float:
    engine = CombatEngine(_ruleset(challenge), rng=random.Random(seed))
    state = engine.start_encounter([_hero()], [_goblin()])
    engine.resolve(state, Action(actor_id="hero", ability_id="heavy", target_ids=["goblin"], challenge_score=score))
    return 50 - state.combatants["goblin"].current_hp


def test_a_missed_minigame_deals_the_floor_fraction_of_a_perfect_one():
    challenge = ChallengeDef(kind=ChallengeKind.SEQUENCE, min_factor=0.5)
    perfect = _damage_dealt(challenge, 1.0)
    missed = _damage_dealt(challenge, 0.0)
    skipped = _damage_dealt(challenge, None)
    assert perfect == 9.0  # 4 + 5 attack - 0 defense
    assert missed == pytest.approx(4.5) and skipped == missed  # reduced, never zeroed
    assert _damage_dealt(challenge, 0.5) == pytest.approx(6.75)
    assert _damage_dealt(challenge, 5.0) == perfect  # clamped
    assert _damage_dealt(None, 0.0) == perfect  # no minigame on the ability -> score ignored


def test_the_log_reports_the_minigame_outcome():
    engine = CombatEngine(_ruleset(ChallengeDef(min_factor=0.5)), rng=random.Random(1))
    state = engine.start_encounter([_hero()], [_goblin()])
    log = engine.resolve(state, Action(actor_id="hero", ability_id="heavy", target_ids=["goblin"], challenge_score=0.5))
    assert any("Minigame: 50%" in line and "x0.75" in line for line in log)


def test_a_perfect_precisao_forces_the_crit_and_never_reduces():
    challenge = ChallengeDef(kind=ChallengeKind.PRECISION, min_factor=1.0, crit_on_perfect=True)
    assert _damage_dealt(challenge, 1.0) == 18.0  # 9 x crit_mult 2.0 with 0% crit chance
    assert _damage_dealt(challenge, 0.0) == 9.0  # a miss is just a normal hit


def test_enemies_never_play_minigames():
    engine = CombatEngine(_ruleset(ChallengeDef(min_factor=0.1), crit_chance_matters=True), rng=random.Random(1))
    state = engine.start_encounter([_hero()], [_goblin()])
    engine.resolve(state, Action(actor_id="hero", ability_id="heavy", target_ids=["goblin"], challenge_score=1.0))
    engine.resolve_ai_turn(state)  # the goblin's bite carries a challenge it can't play -- full damage
    assert state.combatants["hero"].current_hp == 30 - (2 + 2 - 1)


def test_only_the_four_stage2_signatures_carry_a_minigame_one_of_each_kind():
    ruleset = build_ruleset()
    carriers = {a.id: a.challenge.kind for a in ruleset.abilities.values() if a.challenge is not None}
    assert carriers == {
        "storm_of_blows": ChallengeKind.SEQUENCE,
        "arcane_cataclysm": ChallengeKind.CHANNEL,
        "fortune_shot": ChallengeKind.PRECISION,
        "titanic_blow": ChallengeKind.TIMING,
    }
    assert ruleset.abilities["fortune_shot"].challenge.crit_on_perfect
    assert ruleset.abilities["fortune_shot"].challenge.min_factor == 1.0
