import random

import pytest

from tests.test_combat import make_ruleset, make_hero, make_goblin
from tests.test_runes import make_full_session
from wyrdfall.domain.combat import Action, CombatEngine


def fight_damage(rune_ability, ability="strike"):
    hero = make_hero(resource=10)
    hero.ability_rune_slots = {rune_ability: ["rune_might"]}
    enemy = make_goblin()
    enemy.current_hp = enemy.base_stats.max_hp = 100
    engine = CombatEngine(make_ruleset(), random.Random(1))
    state = engine.start_encounter([hero], [enemy])
    engine.resolve(state, Action(actor_id="hero", ability_id=ability, target_ids=["goblin"]))
    assert state.combatants["hero"].computed_stats(engine.ruleset).attack == 5
    return 100 - state.combatants["goblin"].current_hp


def test_rune_only_modifies_the_selected_ability():
    assert fight_damage("strike") == pytest.approx(fight_damage("fireball") + 3)


def test_unslotted_ability_cannot_grant_a_passive_bonus():
    session = make_full_session()
    hero = session.run.party[0]
    hero.abilities.append("reckless_smash")
    session.run.rune_inventory = ["rune_might"]
    before = hero.computed_stats(session.ruleset).attack
    assert session.socket_rune(hero.id, "rune_might", "reckless_smash")
    assert hero.computed_stats(session.ruleset).attack == before
    assert "reckless_smash" not in hero.equipped_abilities


def test_body_only_rune_rejected_without_consumption():
    session = make_full_session()
    session.run.rune_inventory = ["rune_vitality"]
    assert not session.socket_rune("hero", "rune_vitality", "strike")
    assert session.run.rune_inventory == ["rune_vitality"]
    assert not session.run.party[0].ability_rune_slots


def test_ability_scope_is_rebuilt_when_a_parry_resumes_the_attack():
    from wyrdfall.domain.combat import ParryResult
    hero = make_hero()
    hero.can_parry = True
    enemy = make_goblin()
    enemy.base_stats.speed = 20
    enemy.ability_rune_slots = {"bite": ["rune_might"]}
    engine = CombatEngine(make_ruleset(), random.Random(1))
    state = engine.start_encounter([hero], [enemy])
    engine.resolve(state, Action(actor_id="goblin", ability_id="bite", target_ids=["hero"]))
    assert state.pending_parry is not None
    assert state.combatants["hero"].current_hp == 30
    engine.resolve_parry(state, ParryResult.DECLINED)
    assert state.combatants["hero"].current_hp == pytest.approx(24)
    assert state.combatants["goblin"].computed_stats(engine.ruleset).attack == 2


def test_ability_proc_does_not_fire_for_a_different_ability():
    for socket, expected in (("strike", 1), ("fireball", 0)):
        hero = make_hero(resource=4)
        hero.current_resource = 0
        hero.ability_rune_slots = {socket: ["rune_ember"]}
        enemy = make_goblin()
        enemy.current_hp = enemy.base_stats.max_hp = 100
        engine = CombatEngine(make_ruleset(), random.Random(1))
        state = engine.start_encounter([hero], [enemy])
        before = state.combatants["hero"].current_resource
        engine.resolve(state, Action(actor_id="hero", ability_id="strike", target_ids=["goblin"]))
        assert state.combatants["hero"].current_resource == before + expected
