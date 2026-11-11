import pytest

from wyrdfall.domain.character import Character
from wyrdfall.domain.content import CLASS_DEFS, TALENT_TREES, build_ruleset
from wyrdfall.domain.dungeon import EncounterDef
from wyrdfall.domain.factory import create_player_character
from wyrdfall.domain.items import (
    ACCESSORY_SLOTS,
    ARMOR_SET_DEFS,
    ENCHANTMENT_DEFS,
    ENCHANTMENT_SLOTS_BY_RARITY,
    EQUIPMENT_DEFS,
    Rarity,
)
from wyrdfall.domain.run import RunState
from wyrdfall.engine.session import GameSession


def test_enchantment_slots_scale_with_rarity():
    assert ENCHANTMENT_SLOTS_BY_RARITY[Rarity.COMUM] == 1
    assert ENCHANTMENT_SLOTS_BY_RARITY[Rarity.RARO] == 2
    assert ENCHANTMENT_SLOTS_BY_RARITY[Rarity.LENDARIO] == 3


def test_guardian_set_has_a_stronger_three_piece_bonus_than_two_piece():
    guardian = ARMOR_SET_DEFS["guardian"]
    two_piece_total = sum(m.value for m in guardian.two_piece_modifiers)
    three_piece_total = sum(m.value for m in guardian.three_piece_modifiers)
    assert three_piece_total > two_piece_total
    assert len(guardian.three_piece_modifiers) >= len(guardian.two_piece_modifiers)


def test_guardian_set_pieces_all_reference_the_guardian_set_id():
    guardian_pieces = [item for item in EQUIPMENT_DEFS.values() if item.set_id == "guardian"]
    assert len(guardian_pieces) == 3
    assert {item.slot for item in guardian_pieces} == {"head", "body", "legs"}


def test_equipment_catalog_covers_every_slot():
    slots = {item.slot for item in EQUIPMENT_DEFS.values()}
    assert slots == {"head", "body", "legs", "accessory", "weapon"}


def test_enchantment_catalog_is_non_empty_and_produces_modifiers():
    assert len(ENCHANTMENT_DEFS) > 0
    for enchantment in ENCHANTMENT_DEFS.values():
        assert enchantment.modifiers or enchantment.triggered_effects


# -- GameSession.equip_armor / equip_accessory / socket_enchantment ---------


def make_full_session(class_id="runeguard", seed=1, inventory=None) -> GameSession:
    ruleset = build_ruleset()
    class_def = CLASS_DEFS[class_id]
    tree = TALENT_TREES[class_def.talent_tree_id]
    hero = create_player_character("hero", "Hero", class_def, tree, ruleset=ruleset)
    run = RunState(run_id="run1", seed=seed, dungeon_id=class_def.id, party=[hero], inventory=list(inventory or []))
    return GameSession(run, ruleset, dict(TALENT_TREES))


def test_equip_armor_requires_the_item_to_be_in_the_run_inventory():
    session = make_full_session(inventory=[])
    assert session.equip_armor("hero", "head", "traveler_cap") is False


def test_equipping_armor_updates_passive_modifiers():
    session = make_full_session(inventory=["traveler_cap"])
    hero = session.run.party[0]
    before_speed = hero.computed_stats(session.ruleset).speed

    assert session.equip_armor("hero", "head", "traveler_cap") is True
    assert session.run.equipment_instances[hero.equipped_armor["head"]].definition_id == "traveler_cap"
    after_speed = hero.computed_stats(session.ruleset).speed
    assert after_speed == pytest.approx(before_speed + 1.0)


def test_equipping_wrong_slot_item_fails():
    session = make_full_session(inventory=["traveler_cap"])
    assert session.equip_armor("hero", "body", "traveler_cap") is False


def test_unequip_armor_reverts_modifiers():
    session = make_full_session(inventory=["traveler_cap"])
    hero = session.run.party[0]
    session.equip_armor("hero", "head", "traveler_cap")
    boosted_speed = hero.computed_stats(session.ruleset).speed

    assert session.unequip_armor("hero", "head") is True
    assert "head" not in hero.equipped_armor
    assert hero.computed_stats(session.ruleset).speed == pytest.approx(boosted_speed - 1.0)


def test_armor_set_bonus_only_applies_once_all_three_pieces_are_equipped():
    session = make_full_session(inventory=["guardian_helm", "guardian_chest", "guardian_greaves"])
    hero = session.run.party[0]

    session.equip_armor("hero", "head", "guardian_helm")
    two_piece_defense = hero.computed_stats(session.ruleset).defense
    session.equip_armor("hero", "body", "guardian_chest")
    # 2nd piece: 2-piece set bonus (+10% defense) should now be active.
    with_two_piece_bonus = hero.computed_stats(session.ruleset).defense
    assert with_two_piece_bonus > two_piece_defense * 1.0

    session.equip_armor("hero", "legs", "guardian_greaves")
    with_three_piece_bonus = hero.computed_stats(session.ruleset).defense
    assert with_three_piece_bonus > with_two_piece_bonus


def test_accessory_slots_are_capped_at_three():
    session = make_full_session(inventory=["ring_of_focus", "amulet_of_vigor", "crown_of_ages"])
    hero = session.run.party[0]
    for item_id in ("ring_of_focus", "amulet_of_vigor", "crown_of_ages"):
        assert session.equip_accessory("hero", item_id) is True
    assert len(hero.equipped_accessories) == ACCESSORY_SLOTS


def test_socketing_an_enchantment_is_capped_by_item_rarity():
    session = make_full_session(inventory=["traveler_cap"])  # COMUM -> 1 slot
    session.equip_armor("hero", "head", "traveler_cap")
    hero = session.run.party[0]

    session.dungeon = session.dungeon.model_copy(update={"encounters": [EncounterDef(id="forge", name="Forja", room_type="forge")]})
    session.run.currency_earned = 100
    session.run.materials[Rarity.COMUM] = 5
    assert session.socket_enchantment("hero", "traveler_cap", "ench_swiftness") is True
    assert session.socket_enchantment("hero", "traveler_cap", "ench_power") is False
    assert hero.equipment_instances[hero.equipped_armor["head"]].enchantments == ["ench_swiftness"]


def test_socketing_an_enchantment_onto_an_unequipped_item_fails():
    session = make_full_session(inventory=["traveler_cap"])
    assert session.socket_enchantment("hero", "traveler_cap", "ench_swiftness") is False


# -- GameSession.reroll_enchantment (Forja de Campo) -------------------------


def make_session_with_enchanted_item(inventory=("traveler_cap",)) -> GameSession:
    session = make_full_session(inventory=list(inventory))
    session.dungeon = session.dungeon.model_copy(
        update={"encounters": [EncounterDef(id="forge", name="Forja", room_type="forge")]},
    )
    session.equip_armor("hero", "head", "traveler_cap")
    session.run.currency_earned = 100
    session.run.materials[Rarity.COMUM] = 5
    assert session.socket_enchantment("hero", "traveler_cap", "ench_swiftness")
    return session


def test_forge_services_cannot_spend_resources_outside_the_forge():
    session = make_session_with_enchanted_item()
    session.dungeon = session.dungeon.model_copy(
        update={"encounters": [EncounterDef(id="shop", name="Vendedor", room_type="shop")]},
    )
    session.run.currency_earned = 100
    session.run.materials = {Rarity.COMUM: 2}
    session.run.rune_inventory = ["rune_might", "rune_might"]
    before = session.run.model_copy(deep=True)

    assert not session.combine_runes("rune_might")
    assert not session.reroll_enchantment("hero", "traveler_cap", 0)
    assert session.run == before


def test_reroll_fails_without_enough_fragmentos():
    session = make_session_with_enchanted_item()
    session.run.currency_earned = 0
    session.run.materials[Rarity.COMUM] = 5
    assert session.reroll_enchantment("hero", "traveler_cap", 0) is False


def test_reroll_fails_without_enough_materials():
    session = make_session_with_enchanted_item()
    session.run.currency_earned = 999
    session.run.materials = {}
    assert session.reroll_enchantment("hero", "traveler_cap", 0) is False


def test_reroll_succeeds_and_changes_the_socketed_enchantment_and_recomputes_stats():
    session = make_session_with_enchanted_item()
    session.run.currency_earned = 999
    session.run.materials[Rarity.COMUM] = 5
    hero = session.run.party[0]
    before_speed = hero.computed_stats(session.ruleset).speed  # boosted by ench_swiftness (+1 speed)

    assert session.reroll_enchantment("hero", "traveler_cap", 0) is True
    new_enchantment_id = hero.equipment_instances[hero.equipped_armor["head"]].enchantments[0]
    assert new_enchantment_id != "ench_swiftness"
    assert session.run.currency_earned == 999 - 10
    assert session.run.materials[Rarity.COMUM] == 4
    after_speed = hero.computed_stats(session.ruleset).speed
    assert after_speed == pytest.approx(before_speed - 1.0)  # ench_swiftness's bonus is gone
