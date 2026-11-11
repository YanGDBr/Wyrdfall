import pytest

from wyrdfall.domain.character import Character
from wyrdfall.domain.combat import CombatState
from wyrdfall.domain.dungeon import EncounterDef
from wyrdfall.domain.models import ModifierKind, Stat, StatBlock
from wyrdfall.domain.races import (
    RACE_DEFS,
    RENASCIDO_DEATH_THRESHOLD,
    check_meta_race_unlock,
    check_race_unlock,
    race_modifiers_for,
    race_triggered_effects_for,
)


def test_human_grants_cheat_death_and_needs_no_unlock():
    human = RACE_DEFS["human"]
    assert human.grants_cheat_death is True
    # every attribute gets exactly +1 -- 6 attributes, at least one modifier each
    mods = race_modifiers_for("human")
    assert all(m.kind == ModifierKind.FLAT for m in mods)
    assert len(mods) > 0


def test_dwarf_modifiers_combine_attribute_bonus_elemental_profile_and_trait():
    mods = race_modifiers_for("dwarf")
    # CON secondary (+6/point * 3) + STR secondary (+3/point * 2) = 24
    max_hp_gain = sum(m.value for m in mods if m.stat == Stat.MAX_HP)
    assert max_hp_gain == pytest.approx(18.0 + 6.0)
    assert any(m.stat == Stat.FIRE_RESIST and m.value > 0 for m in mods)
    assert any(m.stat == Stat.ICE_RESIST and m.value < 0 for m in mods)
    # CON secondary status resist (+0.5%/point * 3) + the trait's own +15%
    status_resist_gain = sum(m.value for m in mods if m.stat == Stat.STATUS_RESIST)
    assert status_resist_gain == pytest.approx(0.015 + 0.15)


def test_elf_modifiers_include_negative_attribute_penalty():
    mods = race_modifiers_for("elf")
    # CON -2 secondary (max hp) must show up as a negative modifier, not be
    # silently dropped (attribute_modifiers_for only skips an exact zero)
    max_hp_gain = sum(m.value for m in mods if m.stat == Stat.MAX_HP)
    assert max_hp_gain < 0
    assert any(m.stat == Stat.DODGE_CHANCE and m.value > 0 for m in mods)  # trait
    assert any(m.stat == Stat.ARCANE_RESIST for m in mods)
    assert any(m.stat == Stat.SHADOW_RESIST and m.value < 0 for m in mods)


def test_orc_has_a_fury_on_damage_triggered_effect():
    effects = race_triggered_effects_for("orc")
    assert len(effects) == 1
    assert effects[0].applies_to == "self"


def test_unknown_race_id_returns_nothing():
    assert race_modifiers_for("nonexistent") == []
    assert race_triggered_effects_for("nonexistent") == []


def _make_combat_state(*, party_ids: list[str], enemy_ids: list[str], alive_party_ids: set[str]) -> CombatState:
    combatants: dict[str, Character] = {}
    for pid in party_ids:
        hp = 10.0 if pid in alive_party_ids else 0.0
        combatants[pid] = Character(
            id=pid, name=pid, class_id="x", base_stats=StatBlock(), current_hp=hp, current_resource=0, is_player=True
        )
    for eid in enemy_ids:
        combatants[eid] = Character(
            id=eid, name=eid, class_id="y", base_stats=StatBlock(), current_hp=10, current_resource=0, is_player=False
        )
    order = [*party_ids, *enemy_ids]
    return CombatState(combatants=combatants, turn_order=order)


def test_dwarf_unlocks_on_boss_victory_without_healing():
    boss = EncounterDef(id="e6", name="Boss", is_boss=True)
    state = _make_combat_state(party_ids=["hero"], enemy_ids=["boss"], alive_party_ids={"hero"})
    assert check_race_unlock("dwarf", encounter=boss, combat_state=state) is True

    state.used_heal_this_encounter = True
    assert check_race_unlock("dwarf", encounter=boss, combat_state=state) is False


def test_dwarf_does_not_unlock_on_a_non_boss_encounter():
    regular = EncounterDef(id="e1", name="Regular", is_boss=False)
    state = _make_combat_state(party_ids=["hero"], enemy_ids=["goblin"], alive_party_ids={"hero"})
    assert check_race_unlock("dwarf", encounter=regular, combat_state=state) is False


def test_elf_unlocks_on_boss_victory_without_elemental_damage():
    boss = EncounterDef(id="e6", name="Boss", is_boss=True)
    state = _make_combat_state(party_ids=["hero"], enemy_ids=["boss"], alive_party_ids={"hero"})
    assert check_race_unlock("elf", encounter=boss, combat_state=state) is True

    state.took_elemental_damage_this_encounter = True
    assert check_race_unlock("elf", encounter=boss, combat_state=state) is False


def test_orc_unlocks_when_the_sole_survivor_of_a_group_fight():
    group = EncounterDef(id="e2", name="Group", is_boss=False)
    state = _make_combat_state(
        party_ids=["hero", "friend"],
        enemy_ids=["g1", "g2", "g3"],
        alive_party_ids={"hero"},
    )
    assert check_race_unlock("orc", encounter=group, combat_state=state) is True


def test_orc_does_not_unlock_solo_or_with_fewer_than_3_enemies_or_two_survivors():
    small_group = EncounterDef(id="e2", name="Small Group", is_boss=False)
    two_enemies = _make_combat_state(
        party_ids=["hero", "friend"], enemy_ids=["g1", "g2"], alive_party_ids={"hero"}
    )
    assert check_race_unlock("orc", encounter=small_group, combat_state=two_enemies) is False

    solo = _make_combat_state(party_ids=["hero"], enemy_ids=["g1", "g2", "g3"], alive_party_ids={"hero"})
    assert check_race_unlock("orc", encounter=small_group, combat_state=solo) is False

    both_survive = _make_combat_state(
        party_ids=["hero", "friend"], enemy_ids=["g1", "g2", "g3"], alive_party_ids={"hero", "friend"}
    )
    assert check_race_unlock("orc", encounter=small_group, combat_state=both_survive) is False


# -- Fase 7 -- remaining races -----------------------------------------------


def test_fada_modifiers_include_proc_chance_and_physical_vulnerability():
    mods = race_modifiers_for("fada")
    assert any(m.stat == Stat.PROC_CHANCE_PERCENT and m.value == pytest.approx(0.25) for m in mods)
    assert any(m.stat == Stat.PHYSICAL_VULNERABILITY_PERCENT and m.value > 0 for m in mods)
    assert any(m.stat == Stat.HOLY_RESIST and m.value > 0 for m in mods)


def test_fada_has_no_reachable_unlock_this_round():
    boss = EncounterDef(id="e6", name="Boss", is_boss=True)
    state = _make_combat_state(party_ids=["hero"], enemy_ids=["boss"], alive_party_ids={"hero"})
    assert check_race_unlock("fada", encounter=boss, combat_state=state) is False


def test_renascido_has_healing_penalty_and_status_immunities():
    mods = race_modifiers_for("renascido")
    assert any(m.stat == Stat.HEALING_RECEIVED_PERCENT and m.value == pytest.approx(-0.30) for m in mods)
    assert any(m.stat == Stat.SHADOW_RESIST and m.value > 0 for m in mods)
    assert any(m.stat == Stat.HOLY_RESIST and m.value < 0 for m in mods)
    assert RACE_DEFS["renascido"].status_immunities == {"poisoned", "fear"}


def test_renascido_meta_unlock_needs_the_death_threshold():
    assert check_meta_race_unlock("renascido", total_deaths=RENASCIDO_DEATH_THRESHOLD - 1) is False
    assert check_meta_race_unlock("renascido", total_deaths=RENASCIDO_DEATH_THRESHOLD) is True


def test_construto_has_a_large_negative_speed_modifier_and_immunities():
    mods = race_modifiers_for("construto")
    speed_mods = [m for m in mods if m.stat == Stat.SPEED]
    assert any(m.value <= -20 for m in speed_mods)  # behind every enemy speed in the bestiary
    assert RACE_DEFS["construto"].status_immunities == {"poisoned", "bleeding", "fear"}


def test_construto_has_no_reachable_unlock_this_round():
    boss = EncounterDef(id="e6", name="Boss", is_boss=True)
    state = _make_combat_state(party_ids=["hero"], enemy_ids=["boss"], alive_party_ids={"hero"})
    assert check_race_unlock("construto", encounter=boss, combat_state=state) is False


def test_licantropo_has_a_physical_damage_bonus_and_an_instinct_trigger():
    mods = race_modifiers_for("licantropo")
    assert any(m.stat == Stat.PHYSICAL_DAMAGE_PERCENT and m.value > 0 for m in mods)
    effects = race_triggered_effects_for("licantropo")
    assert len(effects) == 1
    assert effects[0].effect.status_id == "instinto_selvagem"


def test_licantropo_unlocks_solo_against_a_group_unlike_orc():
    group = EncounterDef(id="e2", name="Group", is_boss=False)
    solo_vs_group = _make_combat_state(party_ids=["hero"], enemy_ids=["g1", "g2", "g3"], alive_party_ids={"hero"})
    assert check_race_unlock("licantropo", encounter=group, combat_state=solo_vs_group) is True
    # the exact scenario that does NOT unlock Orc (solo, no ally to lose)
    assert check_race_unlock("orc", encounter=group, combat_state=solo_vs_group) is False


def test_licantropo_does_not_unlock_in_co_op_or_with_fewer_than_3_enemies():
    group = EncounterDef(id="e2", name="Group", is_boss=False)
    co_op = _make_combat_state(
        party_ids=["hero", "friend"], enemy_ids=["g1", "g2", "g3"], alive_party_ids={"hero"}
    )
    assert check_race_unlock("licantropo", encounter=group, combat_state=co_op) is False

    solo_small_group = _make_combat_state(party_ids=["hero"], enemy_ids=["g1", "g2"], alive_party_ids={"hero"})
    assert check_race_unlock("licantropo", encounter=group, combat_state=solo_small_group) is False
