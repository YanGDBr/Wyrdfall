import random

import pytest

from tests.test_specializations import make_full_session
from wyrdfall.domain.combat import CombatEngine
from wyrdfall.domain.factory import recompute_passive_effects
from wyrdfall.domain.models import Alignment, Archetype, DamageElement, Effect, EffectKind, EvolutionVariants, StatBlock
from wyrdfall.domain.specializations import evolution_variant_choices
from wyrdfall.engine.session import _talent_tree_id_for
from wyrdfall.persistence.checkpoint import RunCheckpoint


def test_variant_checks_seals_race_alignment_and_affinity_at_confirmation():
    session = make_full_session()
    hero = session.run.party[0]
    hero.archetype_usage = {Archetype.GUERREIRO: 100}
    hero.alignment_score = 29
    hero.elemental_usage = {DamageElement.FIRE: 50, DamageElement.PHYSICAL: 50}
    hero.sealed_elements = {DamageElement.FIRE}
    before = hero.model_copy(deep=True)
    for invalid in (
        EvolutionVariants(race_id="dwarf"),
        EvolutionVariants(alignment=Alignment.BONDOSO),
        EvolutionVariants(element=DamageElement.FIRE),
    ):
        assert not session.evolve_specialization(hero.id, "berserker", invalid)
        assert hero == before

    hero.alignment_score = 30
    choice = EvolutionVariants(race_id="human", alignment=Alignment.BONDOSO, element=DamageElement.PHYSICAL)
    assert choice in evolution_variant_choices(hero)
    assert session.evolve_specialization(hero.id, "berserker", choice)
    assert hero.evolution_variants == choice


def test_inherited_variants_and_talents_survive_stage2_and_checkpoint():
    session = make_full_session(starting_talent_points=8)
    hero = session.run.party[0]
    hero.archetype_usage = {Archetype.GUERREIRO: 100}
    hero.elemental_usage = {DamageElement.FIRE: 100}
    assert session.allocate_talent(hero.id, "o1")
    initial = EvolutionVariants(race_id="human", element=DamageElement.FIRE)
    assert session.evolve_specialization(hero.id, "berserker", initial)
    assert session.allocate_talent(hero.id, "berserker_1")
    assert session.allocate_talent(hero.id, "berserker_1_alternative")
    hero.level = 10
    hero.alignment_score = -30
    hero.elemental_usage = {DamageElement.ICE: 100}
    baseline_healing = hero.computed_stats(session.ruleset).healing_done_percent
    assert not session.evolve_specialization(hero.id, "senhor_da_guerra", EvolutionVariants(element=DamageElement.ICE))
    assert session.evolve_specialization(hero.id, "senhor_da_guerra", EvolutionVariants(alignment=Alignment.MALIGNO))
    assert hero.evolution_variants == EvolutionVariants(
        race_id="human", alignment=Alignment.MALIGNO, element=DamageElement.FIRE,
    )
    assert {"o1", "berserker_1", "berserker_1_alternative"} <= hero.build.talent_tree.allocated
    snapshot = RunCheckpoint.from_session(session, mode="solo")
    restored = RunCheckpoint.model_validate_json(snapshot.model_dump_json()).restore_session(session.ruleset)
    restored_hero = restored.run.party[0]
    stats = restored_hero.computed_stats(restored.ruleset)
    recompute_passive_effects(restored_hero, restored.talent_trees[_talent_tree_id_for(restored_hero)])
    assert restored_hero.computed_stats(restored.ruleset) == stats
    assert restored_hero.evolution_variants == hero.evolution_variants
    assert stats.healing_done_percent == pytest.approx(baseline_healing - .20)


def test_elemental_variant_boosts_matching_damage_and_changes_incoming_damage():
    session = make_full_session()
    hero = session.run.party[0]
    hero.archetype_usage = {Archetype.GUERREIRO: 100}
    hero.elemental_usage = {DamageElement.FIRE: 100}
    assert session.evolve_specialization(hero.id, "berserker", EvolutionVariants(element=DamageElement.FIRE))
    source = hero.model_copy(update={"base_stats": StatBlock(crit_chance=0)})
    target = hero.model_copy(update={"id": "enemy", "is_player": False, "base_stats": StatBlock(defense=0),
                                     "passive_modifiers": [], "current_hp": 100})
    engine = CombatEngine(session.ruleset, rng=random.Random(1))
    state = engine.start_encounter([source], [target])
    source = state.combatants[hero.id]
    target = state.combatants["enemy"]
    fire = Effect(kind=EffectKind.DAMAGE, amount=20, damage_element=DamageElement.FIRE)
    engine._apply_damage(state, source, StatBlock(crit_chance=0), target, fire)
    assert target.current_hp == pytest.approx(75)
    stats = source.computed_stats(session.ruleset)
    assert stats.fire_resist == 0
    assert stats.ice_resist == pytest.approx(-.15)
    assert stats.physical_vulnerability_percent == pytest.approx(.15)


@pytest.mark.parametrize(
    ("stage1", "stage2", "race", "usage"),
    [
        ("paladino", "sentinela_da_alvorada", "human", {"guerreiro": 60, "mistico": 40}),
        ("lamina_do_crepusculo", "fio_do_eclipse", "human", {"guerreiro": 34, "patrulheiro": 33, "mistico": 33}),
        ("avatar_dividido", "convergencia_celestial", "meio_celestial", {"mistico": 100}),
    ],
)
def test_new_ascension_preserves_the_original_branch(stage1, stage2, race, usage):
    session = make_full_session(starting_talent_points=8)
    hero = session.run.party[0]
    hero.race_id = race
    hero.archetype_usage = {Archetype(name): value for name, value in usage.items()}
    assert session.evolve_specialization(hero.id, stage1)
    assert session.allocate_talent(hero.id, f"{stage1}_1")
    assert session.allocate_talent(hero.id, f"{stage1}_keystone")
    hero.level = 10
    assert session.evolve_specialization(hero.id, stage2)
    assert session.allocate_talent(hero.id, f"{stage2}_1")
    assert session.allocate_talent(hero.id, f"{stage2}_keystone")
    assert {f"{stage1}_1", f"{stage1}_keystone"} <= hero.build.talent_tree.allocated
    assert f"{stage2}_keystone" in {effect.source for effect in hero.passive_triggered_effects}


def test_permanent_legacy_slot_unlocks_at_level_six_and_respects_the_cap():
    from wyrdfall.domain.content.permanent_trees import PERMANENT_TREES

    session = make_full_session()
    hero = session.run.party[0]
    legacy = PERMANENT_TREES["permanent_guerreiro"]
    unlocked = {f"permanent_guerreiro_{suffix}" for suffix in (1, 2, 3)}
    assert legacy.can_allocate("permanent_guerreiro_slot", unlocked)
    hero.permanent_modifiers = legacy.modifiers_for(unlocked | {"permanent_guerreiro_slot"})
    assert hero.active_slot_capacity == 5
    hero.level = 6
    assert hero.active_slot_capacity == 7
    hero.level = 12
    assert hero.active_slot_capacity == 8
