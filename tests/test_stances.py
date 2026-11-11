import random

import pytest

from wyrdfall.domain.character import Character
from wyrdfall.domain.combat import Action, CombatEngine, CombatError
from wyrdfall.domain.content import CLASS_DEFS, ENEMY_DEFS, TALENT_TREES, build_ruleset
from wyrdfall.domain.dungeon import DungeonDef, EncounterDef
from wyrdfall.domain.enemies import instantiate_enemy
from wyrdfall.domain.factory import create_player_character
from wyrdfall.domain.models import Effect, EffectKind, StatBlock
from wyrdfall.domain.run import RunState
from wyrdfall.domain.slots import STANCE_DAMAGE_BONUS
from wyrdfall.engine.session import GameSession


def _attacker(stance="none") -> Character:
    return Character(
        id="a", name="A", class_id="x", base_stats=StatBlock(attack=10, speed=10),
        current_hp=50, current_resource=0, abilities=["strike"], equipped_abilities=["strike"],
        is_player=True, current_stance=stance,
    )


def _target(stance="none", dodge=0.0) -> Character:
    return Character(
        id="t", name="T", class_id="x", base_stats=StatBlock(max_hp=500, defense=0, dodge_chance=dodge, speed=1),
        current_hp=500, current_resource=0, abilities=[], is_player=False, current_stance=stance,
        equipped_abilities=[],
    )


def _damage_dealt(attacker: Character, target: Character, seed=1) -> float:
    ruleset = build_ruleset()
    engine = CombatEngine(ruleset, rng=random.Random(seed))
    state = engine.start_encounter([attacker], [target])
    hit = Effect(kind=EffectKind.DAMAGE, amount=20.0)
    src = state.combatants["a"]
    engine._apply_damage(state, src, src.computed_stats(ruleset), state.combatants["t"], hit)
    return 500.0 - state.combatants["t"].current_hp


def test_ofensiva_raises_damage_dealt_and_damage_taken_by_the_same_bonus():
    base = _damage_dealt(_attacker(), _target())
    assert _damage_dealt(_attacker("offensive"), _target()) == pytest.approx(base * (1 + STANCE_DAMAGE_BONUS))
    assert _damage_dealt(_attacker(), _target("offensive")) == pytest.approx(base * (1 + STANCE_DAMAGE_BONUS))


def _dodges(attacker: Character, target: Character, trials=300) -> int:
    ruleset = build_ruleset()
    dodged = 0
    for seed in range(trials):
        engine = CombatEngine(ruleset, rng=random.Random(seed))
        state = engine.start_encounter([attacker, ], [target])
        src = state.combatants["a"]
        engine._apply_damage(state, src, src.computed_stats(ruleset), state.combatants["t"], Effect(kind=EffectKind.DAMAGE, amount=5.0))
        if state.combatants["t"].current_hp == 500.0:
            dodged += 1
    return dodged


def test_evasiva_makes_the_target_dodge_more_and_precisa_makes_it_dodge_less():
    baseline = _dodges(_attacker(), _target(dodge=0.30))
    assert _dodges(_attacker(), _target("evasive", dodge=0.30)) > baseline
    assert _dodges(_attacker("precise"), _target(dodge=0.30)) < baseline
    # Precisa never pushes Esquiva below zero
    assert _dodges(_attacker("precise"), _target(dodge=0.0)) == 0


def test_switching_is_free_once_per_turn_on_your_own_turn():
    ruleset = build_ruleset()
    class_def = CLASS_DEFS["runeguard"]
    tree = TALENT_TREES["runeguard_path"]
    hero = create_player_character("hero", "Hero", class_def, tree, ruleset=ruleset)
    engine = CombatEngine(ruleset, rng=random.Random(1))
    goblin = instantiate_enemy(ENEMY_DEFS["goblin"], "g")
    state = engine.start_encounter([hero], [goblin])
    assert state.current_actor_id() == "hero"  # runeguard is faster than a goblin

    log = engine.set_stance(state, "hero", "offensive")
    assert state.combatants["hero"].current_stance == "offensive" and log
    assert state.current_actor_id() == "hero"  # a switch doesn't spend the turn
    with pytest.raises(CombatError):
        engine.set_stance(state, "hero", "evasive")  # already switched this turn
    with pytest.raises(CombatError):
        engine.set_stance(state, "g", "evasive")  # not the goblin's turn

    # act, let the goblin act, and it's a new turn: switching is allowed again
    engine.resolve(state, Action(actor_id="hero", ability_id="strike", target_ids=["g"]))
    if not state.is_over and state.current_actor_id() == "g":
        engine.resolve_ai_turn(state)
    if not state.is_over:
        assert state.current_actor_id() == "hero"
        engine.set_stance(state, "hero", "evasive")
        assert state.combatants["hero"].current_stance == "evasive"


def test_a_stance_chosen_in_combat_persists_on_the_run_party_afterwards():
    ruleset = build_ruleset()
    class_def = CLASS_DEFS["runeguard"]
    tree = TALENT_TREES["runeguard_path"]
    hero = create_player_character("hero", "Hero", class_def, tree, ruleset=ruleset)
    dungeon = DungeonDef(id="t", name="t", encounters=[EncounterDef(id="e1", name="f", enemy_ids=["goblin"])])
    session = GameSession(RunState(run_id="r", seed=1, dungeon_id="t", party=[hero]), ruleset, {tree.definition.id: tree}, dungeon=dungeon)

    session.set_stance("hero", "precise")  # between fights: just the standing choice
    assert session.run.party[0].current_stance == "precise"

    session.start_current_encounter()
    session.set_stance("hero", "offensive")  # in combat: goes through the engine
    assert session.combat_state.combatants["hero"].current_stance == "offensive"
    assert session.run.party[0].current_stance == "offensive"  # synced back to the run
