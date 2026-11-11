import pytest

from wyrdfall.domain.attributes import Atributo
from wyrdfall.domain.character import Character
from wyrdfall.domain.models import ModifierKind, Stat, StatBlock
from wyrdfall.domain.weapons import WEAPON_TYPE_DEFS, weapon_modifiers_for


def make_bare_character(**overrides) -> Character:
    defaults = dict(id="hero", name="Hero", class_id="runeguard", base_stats=StatBlock(), current_hp=10, current_resource=0)
    defaults.update(overrides)
    return Character(**defaults)


def test_no_equipped_weapon_produces_no_modifiers():
    character = make_bare_character()
    assert weapon_modifiers_for(character) == []


def test_equipped_weapon_with_no_relevant_attributes_invested_produces_no_modifiers():
    character = make_bare_character(equipped_weapon_type="greatsword")
    assert weapon_modifiers_for(character) == []


def test_greatsword_scales_purely_with_strength():
    character = make_bare_character(
        equipped_weapon_type="greatsword", attribute_points={Atributo.STRENGTH: 10, Atributo.DEXTERITY: 10},
    )
    mods = weapon_modifiers_for(character)
    assert len(mods) == 1
    mod = mods[0]
    assert mod.stat == Stat.WEAPON_DAMAGE_PERCENT
    assert mod.kind == ModifierKind.FLAT
    # scaling={STRENGTH: 1.0} -- DEXTERITY contributes nothing to a greatsword
    assert mod.value == pytest.approx(10 * 1.0 * 0.01)


def test_bow_scales_with_both_strength_and_dexterity_by_weight():
    character = make_bare_character(equipped_weapon_type="bow", attribute_points={Atributo.STRENGTH: 10, Atributo.DEXTERITY: 10})
    mods = weapon_modifiers_for(character)
    # scaling={STRENGTH: 0.4, DEXTERITY: 0.6}
    assert mods[0].value == pytest.approx((10 * 0.4 + 10 * 0.6) * 0.01)


def test_all_ten_weapon_types_from_the_design_doc_table_exist():
    assert set(WEAPON_TYPE_DEFS.keys()) == {
        "sword_one_hand", "greatsword", "dagger", "spear", "bow",
        "firearm", "staff", "grimoire", "shield", "unarmed",
    }


# -- Habilidades Exclusivas de Arma (10-sistemas-de-build.md §3.4) -- the
# cross-archetype channel ---------------------------------------------------


def _full_session(class_id="runeguard"):
    from wyrdfall.domain.content import CLASS_DEFS, TALENT_TREES, build_ruleset
    from wyrdfall.domain.dungeon import DungeonDef, EncounterDef
    from wyrdfall.domain.factory import create_player_character
    from wyrdfall.domain.run import RunState
    from wyrdfall.engine.session import GameSession

    ruleset = build_ruleset()
    class_def = CLASS_DEFS[class_id]
    tree = TALENT_TREES[class_def.talent_tree_id]
    hero = create_player_character("hero", "Hero", class_def, tree, ruleset=ruleset)
    dungeon = DungeonDef(id="t", name="t", encounters=[EncounterDef(id=f"e{i}", name="f", enemy_ids=["goblin"]) for i in range(6)])
    return GameSession(RunState(run_id="r", seed=1, dungeon_id="t", party=[hero]), ruleset, dict(TALENT_TREES), dungeon=dungeon)


def test_every_weapon_type_grants_an_ability_that_needs_that_weapon():
    from wyrdfall.domain.content import build_ruleset

    ruleset = build_ruleset()
    for weapon in WEAPON_TYPE_DEFS.values():
        assert weapon.granted_abilities, weapon.id
        for ability_id in weapon.granted_abilities:
            ability = ruleset.abilities[ability_id]
            assert ability.required_weapon_type == weapon.id
            assert ability.archetype_weight  # it moves the Afinidade meter


def test_equipping_a_staff_grants_faisca_legal_only_while_the_staff_is_equipped():
    session = _full_session()
    hero = session.run.party[0]
    assert "weapon_spark" not in hero.abilities
    assert session.equip_weapon("hero", "staff") is True
    assert "weapon_spark" in hero.abilities and "weapon_spark" in hero.equipped_abilities

    state = session.start_current_encounter()
    legal = {a.id for a in session.combat_engine.legal_abilities(state, "hero")}
    assert "weapon_spark" in legal
    state.combatants["hero"].equipped_weapon_type = "greatsword"
    legal = {a.id for a in session.combat_engine.legal_abilities(state, "hero")}
    assert "weapon_spark" not in legal  # greyed out, still in the pool
    assert "weapon_spark" in state.combatants["hero"].abilities


def test_fighting_with_a_staff_drifts_a_guerreiro_toward_mistico_and_unlocks_a_hybrid():
    from wyrdfall.domain.combat import Action
    from wyrdfall.domain.models import Archetype
    from wyrdfall.domain.specializations import qualifying_specializations

    session = _full_session()
    hero = session.run.party[0]
    session.equip_weapon("hero", "staff")
    hero.equipped_abilities = ["weapon_spark"]  # fight with the staff only
    hero.level = 5

    for _ in range(4):
        state = session.start_current_encounter()
        turns = 0
        while not session.encounter_is_over and turns < 100:
            actor_id = state.current_actor_id()
            actor = state.combatants[actor_id]
            if actor.acts_automatically:
                session.resolve_ai_turn()
            else:
                actor.current_resource = max(actor.current_resource, 1.0)  # keep casting
                targets = session.combat_engine.legal_target_ids(state, actor_id, session.ruleset.abilities["weapon_spark"])
                session.submit_action(Action(actor_id=actor_id, ability_id="weapon_spark", target_ids=targets[:1]))
            turns += 1
        assert session.encounter_victory
        session.collect_victory_reward_and_advance()
        hero = session.run.party[0]
        hero.level = 5

    assert hero.archetype_usage.get(Archetype.MISTICO, 0.0) > 0.0
    assert hero.archetype_usage.get(Archetype.GUERREIRO, 0.0) == 0.0  # never touched a Guerreiro ability
    # 100% Místico usage on a Guerreiro-base character: pure Místico picks qualify --
    # the meter follows USE, not class (05-classes.md §2)
    offered = {s.id for s in qualifying_specializations(hero)}
    assert "mago" in offered
    # ...and mixing in one Guerreiro cast makes a pair hybrid appear
    hero.archetype_usage[Archetype.GUERREIRO] = hero.archetype_usage[Archetype.MISTICO]
    offered = {s.id for s in qualifying_specializations(hero)}
    assert "cavaleiro_arcano" in offered and "paladino" in offered
    assert session.evolve_specialization("hero", "cavaleiro_arcano") is True
