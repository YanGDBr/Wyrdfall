import random

from wyrdfall.domain.combat import CombatEngine
from wyrdfall.domain.content import CLASS_DEFS, ENEMY_DEFS, TALENT_TREES, build_ruleset
from wyrdfall.domain.dungeon import DungeonDef, EncounterDef
from wyrdfall.domain.enemies import instantiate_enemy
from wyrdfall.domain.factory import create_player_character
from wyrdfall.domain.run import RunState
from wyrdfall.domain.slots import ACTIVE_SLOTS_CAP, active_ability_slots
from wyrdfall.engine.session import GameSession


def make_session(starting_talent_points=0) -> GameSession:
    ruleset = build_ruleset()
    class_def = CLASS_DEFS["runeguard"]
    tree = TALENT_TREES["runeguard_path"]
    hero = create_player_character(
        "hero", "Hero", class_def, tree, ruleset=ruleset, starting_talent_points=starting_talent_points
    )
    dungeon = DungeonDef(id="t", name="t", encounters=[EncounterDef(id="e1", name="f", enemy_ids=["goblin"])])
    run = RunState(run_id="r", seed=1, dungeon_id="t", party=[hero])
    return GameSession(run, ruleset, {tree.definition.id: tree}, dungeon=dungeon)


def test_slot_count_follows_the_documented_level_table():
    # docs/design/10-sistemas-de-build.md §4: 4, +1 at levels 3/6/9/12, cap 8
    assert [active_ability_slots(lv) for lv in (1, 2, 3, 5, 6, 9, 12, 20)] == [4, 4, 5, 5, 6, 7, 8, 8]
    assert active_ability_slots(99) == ACTIVE_SLOTS_CAP


def test_a_fresh_hero_has_its_starters_equipped_except_the_universal_defender():
    session = make_session()
    hero = session.run.party[0]
    assert "guard" in hero.abilities
    assert "guard" not in hero.equipped_abilities
    assert set(hero.equipped_abilities) == set(hero.abilities) - {"guard"}
    assert session.ruleset.abilities["guard"].universal and session.ruleset.abilities["guard"].name == "Defender"


def test_only_equipped_or_universal_abilities_are_legal_in_combat_for_players():
    session = make_session()
    hero = session.run.party[0]
    hero.abilities.append("reckless_smash")  # in the pool, not slotted
    engine = CombatEngine(session.ruleset, rng=random.Random(1))
    state = engine.start_encounter([hero], [instantiate_enemy(ENEMY_DEFS["goblin"], "g")])

    legal = {a.id for a in engine.legal_abilities(state, "hero")}
    assert "guard" in legal  # universal, never needs a slot
    assert "strike" in legal
    assert "reckless_smash" not in legal

    state.combatants["hero"].equipped_abilities.append("reckless_smash")
    assert "reckless_smash" in {a.id for a in engine.legal_abilities(state, "hero")}
    # enemies have no slots -- their whole kit stays legal
    assert [a.id for a in engine.legal_abilities(state, "g")] == ENEMY_DEFS["goblin"].abilities


def test_equip_and_unequip_respect_the_pool_the_cap_and_universality():
    session = make_session()
    hero = session.run.party[0]
    hero.abilities.extend(["reckless_smash", "multi_shot", "meteor"])
    assert len(hero.equipped_abilities) == 2  # strike, focus

    assert session.equip_ability("hero", "reckless_smash") is True
    assert session.equip_ability("hero", "multi_shot") is True
    assert len(hero.equipped_abilities) == 4 == active_ability_slots(hero.level)
    assert session.equip_ability("hero", "meteor") is False  # slots full
    assert session.equip_ability("hero", "guard") is False  # universal, never slotted
    assert session.equip_ability("hero", "annihilate") is False  # not in the pool
    assert session.equip_ability("hero", "strike") is False  # already equipped

    assert session.unequip_ability("hero", "strike") is True
    assert session.equip_ability("hero", "meteor") is True
    assert session.unequip_ability("hero", "strike") is False


def test_a_granted_ability_is_auto_equipped_while_a_slot_is_free_and_not_once_full():
    session = make_session(starting_talent_points=10)
    hero = session.run.party[0]
    assert session.allocate_talent("hero", "r1") is True
    assert session.allocate_talent("hero", "r2") is True  # grants rune_smash
    assert "rune_smash" in hero.abilities and "rune_smash" in hero.equipped_abilities

    hero.equipped_abilities = ["strike", "focus", "rune_smash", "reckless_smash"]  # full at level 1
    hero.card_offer = ["chicote_de_chamas"]
    session.choose_card("hero", "chicote_de_chamas")
    assert "card_flame_lash" in hero.abilities
    assert "card_flame_lash" not in hero.equipped_abilities  # pool grew, loadout didn't
