import pytest

from wyrdfall.domain.character import Character
from wyrdfall.domain.content import CLASS_DEFS, TALENT_TREES, build_ruleset
from wyrdfall.domain.factory import create_player_character
from wyrdfall.domain.models import ModifierKind, Stat, StatBlock
from wyrdfall.domain.run import RunState
from wyrdfall.domain.runes import (
    ABILITY_RUNE_SLOTS_PER_ABILITY,
    BODY_RUNE_SLOTS,
    RUNE_DEFS,
    rune_modifiers_for,
    rune_triggered_effects_for,
)
from wyrdfall.engine.session import GameSession


def make_bare_character(**overrides) -> Character:
    defaults = dict(id="hero", name="Hero", class_id="runeguard", base_stats=StatBlock(), current_hp=10, current_resource=0)
    defaults.update(overrides)
    return Character(**defaults)


def make_full_session(class_id="runeguard", starting_talent_points=0, seed=1) -> GameSession:
    ruleset = build_ruleset()
    class_def = CLASS_DEFS[class_id]
    tree = TALENT_TREES[class_def.talent_tree_id]
    hero = create_player_character("hero", "Hero", class_def, tree, ruleset=ruleset, starting_talent_points=starting_talent_points)
    run = RunState(run_id="run1", seed=seed, dungeon_id=class_def.id, party=[hero])
    return GameSession(run, ruleset, dict(TALENT_TREES))


# -- domain-level rune aggregation -------------------------------------------


def test_no_socketed_runes_produces_no_modifiers():
    character = make_bare_character()
    assert rune_modifiers_for(character) == []
    assert rune_triggered_effects_for(character) == []


def test_body_and_ability_runes_have_independent_scopes():
    character = make_bare_character(
        body_rune_slots=["rune_might"], ability_rune_slots={"strike": ["rune_bulwark"]},
    )
    mods = rune_modifiers_for(character)
    stats = {m.stat for m in mods}
    assert Stat.ATTACK in stats  # from the body-socketed rune_might
    assert Stat.DEFENSE not in stats
    assert {m.stat for m in rune_modifiers_for(character, "strike")} == {Stat.DEFENSE}
    assert all(m.kind == ModifierKind.FLAT for m in mods)


def test_rune_ember_contributes_a_triggered_effect():
    character = make_bare_character(body_rune_slots=["rune_ember"])
    effects = rune_triggered_effects_for(character)
    assert len(effects) == 1
    assert effects[0].source == "rune_ember"


# -- GameSession.socket_rune / unsocket_rune ---------------------------------


def test_socketing_a_body_rune_updates_passive_modifiers():
    session = make_full_session()
    session.run.rune_inventory = ["rune_might"]
    hero = session.run.party[0]
    before_attack = hero.computed_stats(session.ruleset).attack

    assert session.socket_rune("hero", "rune_might") is True
    assert "rune_might" in hero.body_rune_slots
    after_attack = hero.computed_stats(session.ruleset).attack
    assert after_attack == pytest.approx(before_attack + 3.0)


def test_body_rune_slots_are_capped():
    session = make_full_session()
    session.run.rune_inventory = list(RUNE_DEFS)
    hero = session.run.party[0]
    rune_ids = list(RUNE_DEFS.keys())
    assert len(rune_ids) > BODY_RUNE_SLOTS  # sanity: enough runes to overflow the cap

    for rune_id in rune_ids[:BODY_RUNE_SLOTS]:
        assert session.socket_rune("hero", rune_id) is True
    assert session.socket_rune("hero", rune_ids[BODY_RUNE_SLOTS]) is False
    assert len(hero.body_rune_slots) == BODY_RUNE_SLOTS


def test_ability_rune_slots_are_capped_per_ability():
    session = make_full_session()
    session.run.rune_inventory = list(RUNE_DEFS)
    hero = session.run.party[0]
    assert "strike" in hero.abilities

    rune_ids = list(RUNE_DEFS.keys())
    for rune_id in rune_ids[:ABILITY_RUNE_SLOTS_PER_ABILITY]:
        assert session.socket_rune("hero", rune_id, ability_id="strike") is True
    assert session.socket_rune("hero", rune_ids[ABILITY_RUNE_SLOTS_PER_ABILITY], ability_id="strike") is False
    assert len(hero.ability_rune_slots["strike"]) == ABILITY_RUNE_SLOTS_PER_ABILITY


def test_cannot_socket_a_rune_onto_an_ability_the_character_does_not_have():
    session = make_full_session()
    session.run.rune_inventory = ["rune_might"]
    assert session.socket_rune("hero", "rune_might", ability_id="arcane_bolt") is False


def test_unsocketing_a_rune_removes_it_and_recomputes_stats():
    session = make_full_session()
    session.run.rune_inventory = ["rune_might"]
    hero = session.run.party[0]
    session.socket_rune("hero", "rune_might")
    assert session.run.rune_inventory == []  # socketed: out of the pouch
    boosted_attack = hero.computed_stats(session.ruleset).attack

    assert session.unsocket_rune("hero", "rune_might") is True
    assert "rune_might" not in hero.body_rune_slots
    assert hero.computed_stats(session.ruleset).attack == pytest.approx(boosted_attack - 3.0)


def test_unsocketing_a_rune_not_present_fails():
    session = make_full_session()
    assert session.unsocket_rune("hero", "rune_might") is False
