import pytest

from wyrdfall.domain.attributes import Atributo, attribute_modifiers_for
from wyrdfall.domain.character import Character, Ruleset
from wyrdfall.domain.leveling import apply_level_ups, vigor_for_next_level
from wyrdfall.domain.models import ModifierKind, Stat, StatBlock


def test_attribute_modifiers_aggregate_flat_across_invested_points():
    points = {Atributo.STRENGTH: 3, Atributo.DEXTERITY: 2}
    mods = attribute_modifiers_for(points)
    assert all(m.kind == ModifierKind.FLAT for m in mods)
    max_hp_gain = sum(m.value for m in mods if m.stat == Stat.MAX_HP)
    assert max_hp_gain == pytest.approx(3 * 3.0)  # STR secondary: +3 max HP per point
    dodge_gain = sum(m.value for m in mods if m.stat == Stat.DODGE_CHANCE)
    assert dodge_gain == pytest.approx(2 * 0.003)  # DEX secondary: +0.3% dodge per point


def test_attribute_modifiers_skip_untouched_attributes():
    mods = attribute_modifiers_for({Atributo.LUCK: 1})
    assert {m.stat for m in mods} == {Stat.CRIT_MULT, Stat.PROC_CHANCE_PERCENT}


def test_attribute_modifiers_empty_for_no_investment():
    assert attribute_modifiers_for({}) == []


def test_vigor_for_next_level_grows_linearly():
    assert vigor_for_next_level(1) == 15.0  # 10 + 5*1
    assert vigor_for_next_level(2) == 20.0
    assert vigor_for_next_level(3) == 25.0


def test_apply_level_ups_grants_points_and_heals_partially():
    ruleset = Ruleset()
    hero = Character(
        id="hero", name="Hero", class_id="x", base_stats=StatBlock(max_hp=100),
        current_hp=50, current_resource=0,
        race_id="none",  # isolates this from race_modifiers_for's contribution --
        # race_id defaults to "human", which is a real race with real bonuses
        # (see domain/races.py), not a neutral placeholder -- this test is
        # about the leveling formula, not race interaction, hence the sentinel.
    )
    hero.vigor = vigor_for_next_level(1)  # exactly enough for one level

    levels = apply_level_ups(hero, ruleset, talent_tree=None)

    assert levels == 1
    assert hero.level == 2
    assert hero.vigor == 0
    assert hero.attribute_points_available == 2
    assert hero.build.talent_tree.points_available == 1
    # max_hp after +2%/level = 102; heals 25% of that (25.5) on top of 50
    assert hero.current_hp == pytest.approx(75.5)


def test_apply_level_ups_can_grant_multiple_levels_from_one_big_reward():
    ruleset = Ruleset()
    hero = Character(
        id="hero", name="Hero", class_id="x", base_stats=StatBlock(max_hp=100),
        current_hp=10, current_resource=0,
    )
    hero.vigor = vigor_for_next_level(1) + vigor_for_next_level(2)  # exactly two levels' worth

    levels = apply_level_ups(hero, ruleset, talent_tree=None)

    assert levels == 2
    assert hero.level == 3
    assert hero.vigor == 0
    assert hero.attribute_points_available == 4
    assert hero.build.talent_tree.points_available == 2


def test_apply_level_ups_is_a_noop_with_insufficient_vigor():
    ruleset = Ruleset()
    hero = Character(
        id="hero", name="Hero", class_id="x", base_stats=StatBlock(max_hp=100),
        current_hp=100, current_resource=0,
    )
    hero.vigor = vigor_for_next_level(1) - 1  # just short

    levels = apply_level_ups(hero, ruleset, talent_tree=None)

    assert levels == 0
    assert hero.level == 1
    assert hero.vigor == pytest.approx(vigor_for_next_level(1) - 1)
