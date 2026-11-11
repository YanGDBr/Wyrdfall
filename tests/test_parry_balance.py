import random

import pytest
from textual import events

from tests.test_combat import make_goblin, make_hero, make_ruleset
from wyrdfall.domain.challenges import ChallengeDef, parry_challenge
from wyrdfall.domain.combat import Action, CombatEngine, ParryResult
from wyrdfall.ui.screens.skill_challenge import SkillChallengeScreen


def test_parry_window_is_shorter_variable_and_independent_of_offensive_challenges():
    rng = random.Random(27)
    challenges = [parry_challenge(rng) for _ in range(20)]
    for challenge in challenges:
        assert (challenge.hit_window_end - challenge.hit_window_start) * challenge.duration_seconds == pytest.approx(0.125)
        assert 0 < challenge.hit_window_start < challenge.hit_window_end < 1
        assert challenge.tick_seconds < 0.02
    assert len({c.hit_window_start for c in challenges}) == 20
    assert ChallengeDef().duration_seconds == 2.0
    assert ChallengeDef().hit_window_end - ChallengeDef().hit_window_start == pytest.approx(0.2)


def test_counterattack_only_deals_35_percent_attack_before_defenses():
    engine = CombatEngine(make_ruleset(), rng=random.Random(1))
    hero = make_hero()
    hero.can_parry = True
    goblin = make_goblin()
    goblin.base_stats.max_hp = goblin.current_hp = 100
    state = engine.start_encounter([hero], [goblin])
    engine.resolve(state, Action(actor_id="hero", ability_id="strike", target_ids=["goblin"]))
    engine.resolve_ai_turn(state)
    before = state.combatants["goblin"].current_hp
    engine.resolve_parry(state, ParryResult.SUCCESS)
    assert before - state.combatants["goblin"].current_hp == pytest.approx(5 * 0.35)
    assert state.combatants["hero"].current_hp == 30


@pytest.mark.parametrize("progress, expected", [(0.399, ParryResult.FAILURE), (0.4, ParryResult.SUCCESS),
    (0.4999, ParryResult.SUCCESS), (0.5, ParryResult.FAILURE), (1.1, ParryResult.FAILURE)])
def test_hit_uses_exact_elapsed_time_even_if_animation_did_not_tick(monkeypatch, progress, expected):
    screen = SkillChallengeScreen("Hero", "Enemy", ChallengeDef(
        duration_seconds=1.25, hit_window_start=0.4, hit_window_end=0.5))
    screen._started_at = 100.0
    screen._elapsed = 0.0  # stale animation must not grant a late success
    monkeypatch.setattr("wyrdfall.ui.screens.skill_challenge.monotonic", lambda: 100.0 + progress * 1.25)
    monkeypatch.setattr(screen, "_minigame_key", lambda: "space")
    results = []
    monkeypatch.setattr(screen, "_finish", results.append)
    screen.on_key(events.Key("space", " "))
    assert results == [expected]
