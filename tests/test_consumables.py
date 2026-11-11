import random

import pytest

from wyrdfall.domain.consumables import CONSUMABLE_SLOTS
from wyrdfall.domain.content import CLASS_DEFS, CONSUMABLE_DEFS, TALENT_TREES, build_ruleset
from wyrdfall.domain.dungeon import DungeonDef, EncounterDef
from wyrdfall.domain.factory import create_player_character
from wyrdfall.domain.loot import roll_consumable_drop
from wyrdfall.domain.run import RunState
from wyrdfall.engine.session import GameSession, SessionError


def make_session(seed=1, consumables=()) -> GameSession:
    ruleset = build_ruleset()
    class_def = CLASS_DEFS["runeguard"]
    tree = TALENT_TREES["runeguard_path"]
    hero = create_player_character("hero", "Hero", class_def, tree, ruleset=ruleset, starting_talent_points=0)
    dungeon = DungeonDef(
        id="test", name="Test",
        encounters=[EncounterDef(id="e1", name="Fight", enemy_ids=["goblin"])],
    )
    run = RunState(run_id="run1", seed=seed, dungeon_id=dungeon.id, party=[hero], consumables=list(consumables))
    return GameSession(run, ruleset, {tree.definition.id: tree}, dungeon=dungeon)


# -- drops ---------------------------------------------------------------------


def test_a_boss_always_drops_a_consumable_and_a_normal_fight_only_sometimes():
    boss = EncounterDef(id="b", name="Boss", enemy_ids=["goblin"], is_boss=True)
    normal = EncounterDef(id="n", name="Normal", enemy_ids=["goblin"])
    for seed in range(20):
        assert roll_consumable_drop(boss, 0, random.Random(seed), CONSUMABLE_DEFS) in CONSUMABLE_DEFS
    outcomes = {roll_consumable_drop(normal, 0, random.Random(seed), CONSUMABLE_DEFS) for seed in range(60)}
    assert None in outcomes and (outcomes - {None})


def test_the_pouch_never_exceeds_its_cap(monkeypatch):
    monkeypatch.setattr("wyrdfall.engine.session.roll_consumable_drop", lambda *a, **k: "pocao_de_vida")
    session = make_session(consumables=["elixir"] * CONSUMABLE_SLOTS)
    from tests.test_session import play_encounter_to_completion

    play_encounter_to_completion(session)
    assert session.encounter_victory is True
    session.collect_victory_reward_and_advance()
    assert len(session.run.consumables) == CONSUMABLE_SLOTS


def test_a_found_consumable_lands_in_the_pouch(monkeypatch):
    monkeypatch.setattr("wyrdfall.engine.session.roll_consumable_drop", lambda *a, **k: "pocao_de_vida")
    session = make_session()
    from tests.test_session import play_encounter_to_completion

    play_encounter_to_completion(session)
    session.collect_victory_reward_and_advance()
    assert session.run.consumables == ["pocao_de_vida"]


# -- using ---------------------------------------------------------------------


def test_using_a_potion_heals_capped_at_max_and_removes_exactly_one():
    session = make_session(consumables=["pocao_de_vida", "pocao_de_vida"])
    hero = session.run.party[0]
    max_hp = hero.computed_stats(session.ruleset).max_hp
    hero.current_hp = 1.0

    session.use_consumable("hero", "pocao_de_vida")
    assert hero.current_hp == pytest.approx(1.0 + 0.40 * max_hp)
    assert session.run.consumables == ["pocao_de_vida"]

    hero.current_hp = max_hp - 1.0
    session.use_consumable("hero", "pocao_de_vida")
    assert hero.current_hp == pytest.approx(max_hp)
    assert session.run.consumables == []


def test_using_a_resource_potion_restores_resource():
    session = make_session(consumables=["pocao_de_resolucao"])
    hero = session.run.party[0]
    max_resource = hero.computed_stats(session.ruleset).max_resource
    hero.current_resource = 0.0
    session.use_consumable("hero", "pocao_de_resolucao")
    assert hero.current_resource == pytest.approx(0.50 * max_resource)


def test_using_something_not_in_the_pouch_or_for_an_unknown_character_is_rejected():
    session = make_session(consumables=["elixir"])
    with pytest.raises(SessionError):
        session.use_consumable("hero", "pocao_de_vida")
    with pytest.raises(SessionError):
        session.use_consumable("nobody", "elixir")
    with pytest.raises(SessionError):
        session.use_consumable("hero", "nao_existe")
    assert session.run.consumables == ["elixir"]


# -- Tomos (10-sistemas-de-build.md §3.8) -------------------------------------


def test_reading_a_tomo_teaches_the_ability_once_and_consumes_the_tomo():
    session = make_session(consumables=["tomo_do_mistico", "tomo_do_mistico"])
    hero = session.run.party[0]
    assert "tome_arcane_pulse" not in hero.abilities
    hp_before = hero.current_hp
    session.use_consumable("hero", "tomo_do_mistico")
    assert "tome_arcane_pulse" in hero.abilities
    assert "tome_arcane_pulse" in hero.equipped_abilities  # a slot was free
    assert hero.current_hp == hp_before  # a Tomo isn't a potion
    assert session.run.consumables == ["tomo_do_mistico"]
    session.use_consumable("hero", "tomo_do_mistico")  # reading it twice is harmless
    assert hero.abilities.count("tome_arcane_pulse") == 1


def test_tomos_are_priced_and_in_the_vendedor_and_drop_pools():
    from wyrdfall.domain.content import CONSUMABLE_DEFS
    from wyrdfall.domain.shop import CONSUMABLE_PRICES

    tomos = [c for c in CONSUMABLE_DEFS.values() if c.teaches_ability]
    assert len(tomos) == 4
    for tomo in tomos:
        assert tomo.id in CONSUMABLE_PRICES
        assert tomo.heal_fraction == 0 and tomo.resource_fraction == 0
