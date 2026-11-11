import pytest

from wyrdfall.domain.attributes import Atributo
from wyrdfall.domain.character import Character
from wyrdfall.domain.content import CLASS_DEFS, TALENT_TREES, build_ruleset
from wyrdfall.domain.factory import create_player_character
from wyrdfall.domain.models import Alignment, Archetype, DamageElement
from wyrdfall.domain.run import RunState
from wyrdfall.domain.specializations import (
    SPECIALIZATION_DEFS,
    STAGE2_DEFS,
    alignment_category,
    evolution_offers,
    archetype_affinity,
    elemental_affinity,
    is_offerable,
    qualifies,
    qualifying_specializations,
    qualifying_stage2,
    variant_display_names,
)
from wyrdfall.engine.session import EVOLUTION_STAGE2_LEVEL, GameSession, _talent_tree_id_for


def make_bare_character(**overrides) -> Character:
    from wyrdfall.domain.models import StatBlock

    defaults = dict(
        id="hero", name="Hero", class_id="runeguard", base_stats=StatBlock(),
        current_hp=10, current_resource=0, level=5,
    )
    defaults.update(overrides)
    return Character(**defaults)


def make_full_session(class_id="runeguard", starting_talent_points=0, seed=1) -> GameSession:
    """Unlike test_session.py's make_session (a narrow single-tree dict),
    evolution needs every grafted Especialização tree available too."""
    ruleset = build_ruleset()
    class_def = CLASS_DEFS[class_id]
    tree = TALENT_TREES[class_def.talent_tree_id]
    hero = create_player_character(
        "hero", "Hero", class_def, tree, ruleset=ruleset, starting_talent_points=starting_talent_points,
    )
    hero.level = 5
    run = RunState(run_id="run1", seed=seed, dungeon_id=class_def.id, party=[hero])
    return GameSession(run, ruleset, dict(TALENT_TREES))


# -- affinity ------------------------------------------------------------------


def test_archetype_affinity_is_zero_with_no_usage():
    character = make_bare_character()
    assert archetype_affinity(character) == {a: 0.0 for a in Archetype}


def test_archetype_affinity_is_a_percentage_of_total_usage():
    character = make_bare_character(archetype_usage={Archetype.GUERREIRO: 6.0, Archetype.GUARDIAO: 2.0})
    affinity = archetype_affinity(character)
    assert affinity[Archetype.GUERREIRO] == pytest.approx(0.75)
    assert affinity[Archetype.GUARDIAO] == pytest.approx(0.25)
    assert affinity[Archetype.MISTICO] == 0.0


def test_elemental_affinity_is_empty_with_no_usage():
    character = make_bare_character()
    assert elemental_affinity(character) == {}


def test_elemental_affinity_is_a_percentage_of_total_usage():
    character = make_bare_character(elemental_usage={DamageElement.FIRE: 30.0, DamageElement.ICE: 10.0})
    affinity = elemental_affinity(character)
    assert affinity[DamageElement.FIRE] == pytest.approx(0.75)
    assert affinity[DamageElement.ICE] == pytest.approx(0.25)


def test_alignment_category_bands():
    assert alignment_category(0.0) == Alignment.NEUTRO
    assert alignment_category(29.9) == Alignment.NEUTRO
    assert alignment_category(30.0) == Alignment.BONDOSO
    assert alignment_category(100.0) == Alignment.BONDOSO
    assert alignment_category(-29.9) == Alignment.NEUTRO
    assert alignment_category(-30.0) == Alignment.MALIGNO
    assert alignment_category(-100.0) == Alignment.MALIGNO


# -- the 9 pure Especializações (Fase 5) -----------------------------------------


def _usage_satisfying_thresholds(thresholds) -> dict:
    """Builds an archetype_usage dict whose resulting affinity satisfies
    every threshold at once -- min-only archetypes get a healthy buffer
    above the floor, max-only archetypes get 0 (always within any
    positive cap), and min+max archetypes get the midpoint. Archetypes
    with no threshold at all are left out entirely (0 usage)."""
    shares: dict[Archetype, float] = {}
    for threshold in thresholds:
        if threshold.minimum is not None and threshold.maximum is not None:
            shares[threshold.archetype] = (threshold.minimum + threshold.maximum) / 2
        elif threshold.minimum is not None:
            shares[threshold.archetype] = threshold.minimum + 0.10
        elif threshold.maximum is not None:
            shares.setdefault(threshold.archetype, 0.0)
    return {archetype: share * 1000.0 for archetype, share in shares.items()}


def test_every_specialization_is_reachable_by_a_plausible_usage_profile():
    # Sanity check: for each of the 42 authored entries, a character built
    # to obviously satisfy its own thresholds actually qualifies -- catches
    # an inverted or mistyped threshold before it ships. Non-archetype
    # conditions (attribute/weapon/alignment/race) are also force-satisfied
    # directly, same technique already used for Gunner's weapon type --
    # this only proves the conditions are *encoded correctly*, not that
    # every entry is reachable through real play today (see the module
    # docstring's reachability note for what's still gated on later phases).
    for spec_id, spec in SPECIALIZATION_DEFS.items():
        usage = _usage_satisfying_thresholds(spec.thresholds)
        character = make_bare_character(archetype_usage=usage)
        if spec.required_top_attribute is not None:
            character.attribute_points = {spec.required_top_attribute: 5}
        if spec.required_attribute_in_top_two is not None:
            character.attribute_points = {spec.required_attribute_in_top_two: 5, Atributo.STRENGTH: 3}
        if spec.requires_weapon_type is not None:
            character.equipped_weapon_type = spec.requires_weapon_type
        if spec.required_alignment is not None:
            character.alignment_score = {Alignment.BONDOSO: 100.0, Alignment.MALIGNO: -100.0, Alignment.NEUTRO: 0.0}[
                spec.required_alignment
            ]
        if spec.required_race is not None:
            character.race_id = spec.required_race
        assert qualifies(character, spec), f"{spec_id} should qualify from a profile built for its own conditions"


def test_specialization_qualification_no_longer_gates_on_the_characters_own_class():
    # Fase 5b: base_archetype on SpecializationDef is now display-only
    # (used for tree-grafting on the original 9) -- qualification reads
    # only actual usage numbers, since hybrid conditions by definition
    # span more than one archetype and can't be gated by a single one.
    character = make_bare_character(archetype_usage={Archetype.GUERREIRO: 100.0})
    assert qualifies(character, SPECIALIZATION_DEFS["berserker"])


def test_guardiao_caps_exclude_a_guerreiro_leaning_build_from_berserker():
    character = make_bare_character(archetype_usage={Archetype.GUERREIRO: 65.0, Archetype.GUARDIAO: 35.0})
    # 65% Guerreiro clears the >=60% bar, but 35% Guardião blows the <=20% cap
    assert not qualifies(character, SPECIALIZATION_DEFS["berserker"])


def test_absolute_and_moderate_specializations_both_appear_at_extreme_affinity():
    character = make_bare_character(
        base_archetype=Archetype.GUERREIRO, archetype_usage={Archetype.GUERREIRO: 100.0},
    )
    offered = {spec.id for spec in qualifying_specializations(character)}
    assert {"berserker", "avatar_da_guerra"} <= offered


def test_colosso_also_requires_constitution_as_the_top_invested_attribute():
    character = make_bare_character(
        base_archetype=Archetype.GUARDIAO, archetype_usage={Archetype.GUARDIAO: 100.0},
        attribute_points={Atributo.STRENGTH: 5},
    )
    assert not qualifies(character, SPECIALIZATION_DEFS["colosso"])
    character.attribute_points = {Atributo.CONSTITUTION: 5, Atributo.STRENGTH: 2}
    assert qualifies(character, SPECIALIZATION_DEFS["colosso"])


def test_gunner_needs_an_equipped_firearm():
    character = make_bare_character(
        base_archetype=Archetype.PATRULHEIRO, archetype_usage={Archetype.PATRULHEIRO: 100.0},
    )
    assert not qualifies(character, SPECIALIZATION_DEFS["gunner"])
    character.equipped_weapon_type = "firearm"  # GameSession.equip_weapon sets this
    assert qualifies(character, SPECIALIZATION_DEFS["gunner"])


# -- Fase 5b/7: full 46-entry roster -----------------------------------------------


def test_the_full_roster_has_47_entries():
    # the 47 of 05b-classes-roster.md, Avatar Dividido included
    assert len(SPECIALIZATION_DEFS) == 9 + 2 + 17 + 4 + 1 + 5 + 9


def test_atirador_is_reachable_with_luck_among_the_top_two_attributes():
    character = make_bare_character(
        archetype_usage={Archetype.PATRULHEIRO: 100.0},
        attribute_points={Atributo.LUCK: 3, Atributo.DEXTERITY: 5},  # Luck is 2nd, not 1st
    )
    assert qualifies(character, SPECIALIZATION_DEFS["atirador"])
    # dropping Luck out of the top 2 should un-qualify it
    character.attribute_points = {Atributo.DEXTERITY: 5, Atributo.STRENGTH: 4, Atributo.LUCK: 1}
    assert not qualifies(character, SPECIALIZATION_DEFS["atirador"])


def test_encantador_requires_wisdom_as_the_single_top_attribute():
    character = make_bare_character(
        archetype_usage={Archetype.MISTICO: 100.0}, attribute_points={Atributo.WISDOM: 5},
    )
    assert qualifies(character, SPECIALIZATION_DEFS["encantador"])


def test_racial_signatures_are_reachable_for_races_with_a_real_unlock():
    # Punho de Granito/Arqueiro Élfico/Fúria Órquica/Lâmina Espectral/
    # Uivo Selvagem only need race_id + a single archetype threshold,
    # all already fully playable systems (Renascido/Licantropo shipped
    # with a real check_race_unlock/check_meta_race_unlock path -- see
    # domain/races.py).
    cases = [
        ("punho_de_granito", "dwarf", Archetype.GUARDIAO),
        ("arqueiro_elfico", "elf", Archetype.PATRULHEIRO),
        ("furia_orquica", "orc", Archetype.GUERREIRO),
        ("lamina_espectral", "renascido", Archetype.GUERREIRO),
        ("uivo_selvagem", "licantropo", Archetype.GUERREIRO),
    ]
    for spec_id, race_id, archetype in cases:
        character = make_bare_character(race_id=race_id, archetype_usage={archetype: 100.0})
        assert qualifies(character, SPECIALIZATION_DEFS[spec_id]), spec_id


def test_fada_and_construto_racial_signatures_qualify_for_their_races():
    # Fada is unlocked by the Portal Feérico Evento and Construto by the
    # Ferreiro's recipe (tests/test_smith_and_missions.py) -- both real
    # play; here only the qualification rule itself is checked.
    fada_character = make_bare_character(race_id="fada", archetype_usage={Archetype.MISTICO: 100.0})
    assert qualifies(fada_character, SPECIALIZATION_DEFS["chama_ferica"])
    construto_character = make_bare_character(race_id="construto", archetype_usage={Archetype.GUARDIAO: 100.0})
    assert qualifies(construto_character, SPECIALIZATION_DEFS["nucleo_de_batalha"])


def test_andarilho_versatil_needs_the_errante_usage_profile():
    # Humano's signature also requires the Errante do Wyrd usage profile
    # (no archetype > 35%) -- pure usage never qualifies.
    character = make_bare_character(race_id="human", archetype_usage={Archetype.GUERREIRO: 100.0})
    assert not qualifies(character, SPECIALIZATION_DEFS["andarilho_versatil"])


def test_a_hybrid_specialization_needs_mixed_usage():
    # Paladino needs both Guerreiro and Místico usage -- pure usage never
    # qualifies; mixed usage (now reachable through weapon abilities and
    # Tomos, see test_weapons.py) does.
    character = make_bare_character(archetype_usage={Archetype.GUERREIRO: 100.0})
    assert not qualifies(character, SPECIALIZATION_DEFS["paladino"])
    character.archetype_usage = {Archetype.GUERREIRO: 60.0, Archetype.MISTICO: 30.0, Archetype.GUARDIAO: 10.0}
    assert qualifies(character, SPECIALIZATION_DEFS["paladino"])


def test_every_multi_base_specialization_has_a_kit_reachable_from_each_of_its_archetypes():
    # the 17 pairs, the 4 triples, Errante + its 2 twins, Justiceiro, and
    # the 3 racial signatures whose race can be reached from any base
    hybrids = [s for s in SPECIALIZATION_DEFS.values() if s.hybrid_branch]
    assert len(hybrids) == 28
    assert all(s.granted_tree_id or s.hybrid_branch for s in SPECIALIZATION_DEFS.values())  # the whole roster has kits
    class_for = {
        Archetype.GUERREIRO: "runeguard", Archetype.PATRULHEIRO: "patrulheiro",
        Archetype.MISTICO: "mistico", Archetype.GUARDIAO: "guardiao",
    }
    for spec in hybrids:
        archetypes = [t.archetype for t in spec.thresholds if t.minimum]
        # a usage profile inside every band of this spec: minimum + 5 points,
        # which also respects the Errante-style maximums (10..35 -> 15)
        usage = {t.archetype: t.minimum * 100 + 5 for t in spec.thresholds if t.minimum}
        for base in archetypes:
            session = make_full_session(class_id=class_for[base], starting_talent_points=5)
            hero = session.run.party[0]
            hero.archetype_usage = dict(usage)
            if spec.required_race:
                hero.race_id = spec.required_race
            if spec.required_alignment is not None:
                hero.alignment_score = {"bondoso": 50.0, "maligno": -50.0, "neutro": 0.0}[spec.required_alignment.value]
            if spec.requires_weapon_type:
                assert session.equip_weapon("hero", spec.requires_weapon_type)  # Gunner-Berserker's firearm
            base_node = session.talent_trees[_talent_tree_id_for(hero)].definition.nodes[0].id
            assert session.allocate_talent("hero", base_node) is True, (spec.id, base)
            assert session.evolve_specialization("hero", spec.id) is True, (spec.id, base)
            assert _talent_tree_id_for(hero) == f"{base.value}_{spec.id}_path"
            assert base_node in hero.build.talent_tree.allocated  # nothing lost across the graft
            assert session.allocate_talent("hero", f"{spec.id}_1") is True, (spec.id, base)
            assert session.allocate_talent("hero", f"{spec.id}_keystone") is True, (spec.id, base)
            keystone = session.talent_trees[_talent_tree_id_for(hero)].definition.node_map()[f"{spec.id}_keystone"]
            assert keystone.grants_ability in hero.abilities, (spec.id, base)


def test_alignment_signature_is_gated_on_alignment_score_which_nothing_sets_yet():
    character = make_bare_character(archetype_usage={Archetype.GUERREIRO: 100.0})
    assert character.alignment_score == 0.0  # nothing shifts it yet -- always Neutro by default
    assert not qualifies(character, SPECIALIZATION_DEFS["cavaleiro_negro"])
    character.alignment_score = -60.0
    assert qualifies(character, SPECIALIZATION_DEFS["cavaleiro_negro"])


# -- Fase 5b: variant composition -------------------------------------------------


def test_variant_display_names_only_stacks_the_racial_suffix_with_no_other_axis_applicable():
    # Character.race_id defaults to "human" (Fase 3), and Humano has a
    # real universal adjective -- so the racial axis is always at least
    # potentially applicable, even for a "no variant" baseline character.
    character = make_bare_character(archetype_usage={Archetype.GUERREIRO: 100.0})
    spec = SPECIALIZATION_DEFS["berserker"]
    assert variant_display_names(character, spec) == ["Berserker", "Berserker Humano"]


def test_variant_display_names_stacks_racial_alignment_and_elemental_suffixes():
    character = make_bare_character(
        race_id="elf", alignment_score=60.0,
        archetype_usage={Archetype.GUERREIRO: 60.0, Archetype.MISTICO: 30.0, Archetype.GUARDIAO: 10.0},
        elemental_usage={DamageElement.HOLY: 80.0, DamageElement.FIRE: 20.0},
    )
    spec = SPECIALIZATION_DEFS["paladino"]
    names = set(variant_display_names(character, spec))
    assert names == {
        "Paladino",
        "Paladino Élfico",
        "Paladino Radiante",
        "Paladino de Sagrado",
        "Paladino Élfico Radiante",
        "Paladino Élfico de Sagrado",
        "Paladino Radiante de Sagrado",
        "Paladino Élfico Radiante de Sagrado",
    }


def test_reproduces_the_05_classes_md_section_7_worked_example():
    # An Elfo, Bondoso, hybrid-build character should see Paladino, its
    # stacked elemental/alignment variants, AND the signature Justiceiro,
    # all at once -- this is the phase's own criterio de pronto, encoded
    # directly since real gameplay can't reach a hybrid profile yet.
    character = make_bare_character(
        race_id="elf",
        alignment_score=45.0,
        archetype_usage={
            Archetype.GUERREIRO: 48.0, Archetype.PATRULHEIRO: 8.0,
            Archetype.MISTICO: 32.0, Archetype.GUARDIAO: 12.0,
        },
        elemental_usage={DamageElement.HOLY: 60.0, DamageElement.FIRE: 40.0},
    )
    offered_ids = {spec.id for spec in qualifying_specializations(character)}
    assert "paladino" in offered_ids
    assert "justiceiro" in offered_ids
    assert "cavaleiro_arcano" in offered_ids  # also qualifies per 05-classes.md §7

    paladino_names = set(variant_display_names(character, SPECIALIZATION_DEFS["paladino"]))
    assert {"Paladino", "Paladino de Sagrado", "Paladino Radiante", "Paladino Radiante de Sagrado"} <= paladino_names


# -- evolution (GameSession.evolve_specialization) -------------------------------


def test_evolve_rejects_below_level_5():
    session = make_full_session()
    hero = session.run.party[0]
    hero.level = 4
    hero.archetype_usage = {Archetype.GUERREIRO: 100.0}
    assert session.evolve_specialization("hero", "berserker") is False
    assert hero.specialization_id is None


def test_evolve_rejects_a_non_qualifying_specialization():
    session = make_full_session()
    hero = session.run.party[0]
    hero.archetype_usage = {Archetype.MISTICO: 100.0}  # runeguard's base_archetype is Guerreiro
    assert session.evolve_specialization("hero", "berserker") is False
    assert hero.specialization_id is None


def test_evolve_grants_the_branch_without_losing_already_allocated_base_nodes():
    session = make_full_session(starting_talent_points=5)
    hero = session.run.party[0]
    hero.archetype_usage = {Archetype.GUERREIRO: 100.0}

    assert session.allocate_talent("hero", "o1") is True
    assert session.allocate_talent("hero", "d1") is True
    allocated_before = set(hero.build.talent_tree.allocated)

    assert session.evolve_specialization("hero", "berserker") is True
    assert hero.specialization_id == "berserker"
    # nothing already allocated was lost
    assert allocated_before <= hero.build.talent_tree.allocated

    # the new branch's first node is allocatable with zero prerequisites
    assert session.allocate_talent("hero", "berserker_1") is True
    assert "reckless_smash" not in hero.abilities  # capstone not allocated yet
    assert session.allocate_talent("hero", "berserker_keystone") is True
    assert "reckless_smash" in hero.abilities


def test_evolve_grants_a_real_kit_for_each_reachable_fase_5b_specialization():
    # Fase 7: these 7 (unlike the other 30 Fase 5b entries) now have a
    # real grafted tree, same shape as the 9 puras -- one passive node,
    # one keystone granting a new signature ability.
    cases = [
        ("atirador", "patrulheiro", {Archetype.PATRULHEIRO: 100.0}, {}, {Atributo.LUCK: 3, Atributo.DEXTERITY: 5},
         "atirador_1", "atirador_keystone", "called_shot"),
        ("encantador", "mistico", {Archetype.MISTICO: 100.0}, {}, {Atributo.WISDOM: 5},
         "encantador_1", "encantador_keystone", "enchanted_blessing"),
        ("punho_de_granito", "guardiao", {Archetype.GUARDIAO: 100.0}, {"race_id": "dwarf"}, {},
         "punho_de_granito_1", "punho_de_granito_keystone", "steadfast_fist"),
        ("arqueiro_elfico", "patrulheiro", {Archetype.PATRULHEIRO: 100.0}, {"race_id": "elf"}, {},
         "arqueiro_elfico_1", "arqueiro_elfico_keystone", "elven_arrow"),
        ("furia_orquica", "runeguard", {Archetype.GUERREIRO: 100.0}, {"race_id": "orc"}, {},
         "furia_orquica_1", "furia_orquica_keystone", "unbridled_fury"),
        ("lamina_espectral", "runeguard", {Archetype.GUERREIRO: 100.0}, {"race_id": "renascido"}, {},
         "lamina_espectral_1", "lamina_espectral_keystone", "spectral_cut"),
        ("uivo_selvagem", "runeguard", {Archetype.GUERREIRO: 100.0}, {"race_id": "licantropo"}, {},
         "uivo_selvagem_1", "uivo_selvagem_keystone", "wild_howl"),
        # Alinhamento signatures -- reachable since Eventos write alignment_score
        ("guardiao_da_floresta", "guardiao", {Archetype.GUARDIAO: 100.0}, {"alignment_score": 30.0}, {},
         "guardiao_da_floresta_1", "guardiao_da_floresta_keystone", "forest_embrace"),
        ("cavaleiro_negro", "runeguard", {Archetype.GUERREIRO: 100.0}, {"alignment_score": -30.0}, {},
         "cavaleiro_negro_1", "cavaleiro_negro_keystone", "cursed_blow"),
        ("senhor_da_peste", "mistico", {Archetype.MISTICO: 100.0}, {"alignment_score": -30.0}, {},
         "senhor_da_peste_1", "senhor_da_peste_keystone", "plague"),
    ]
    for spec_id, class_id, usage, char_overrides, attribute_points, node_1, keystone, ability_id in cases:
        session = make_full_session(class_id=class_id, starting_talent_points=5)
        hero = session.run.party[0]
        hero.archetype_usage = dict(usage)
        hero.attribute_points = dict(attribute_points)
        for key, value in char_overrides.items():
            setattr(hero, key, value)

        assert SPECIALIZATION_DEFS[spec_id].granted_tree_id is not None, spec_id
        assert session.evolve_specialization("hero", spec_id) is True, spec_id
        assert hero.specialization_id == spec_id, spec_id

        assert session.allocate_talent("hero", node_1) is True, spec_id
        assert ability_id not in hero.abilities, spec_id  # capstone not allocated yet
        assert session.allocate_talent("hero", keystone) is True, spec_id
        assert ability_id in hero.abilities, spec_id


def test_evolving_twice_is_rejected():
    session = make_full_session()
    hero = session.run.party[0]
    hero.archetype_usage = {Archetype.GUERREIRO: 100.0}
    assert session.evolve_specialization("hero", "berserker") is True
    assert session.evolve_specialization("hero", "avatar_da_guerra") is False
    assert hero.specialization_id == "berserker"


# -- Fase 5c: Selamentos (offer-filtering) ---------------------------------------


def test_sealing_an_archetype_hides_a_specialization_whose_only_threshold_touches_it():
    character = make_bare_character(archetype_usage={Archetype.GUERREIRO: 100.0})
    assert qualifies(character, SPECIALIZATION_DEFS["berserker"])
    assert "berserker" in {s.id for s in qualifying_specializations(character)}

    character.sealed_archetypes = {Archetype.GUERREIRO}
    # qualifies() alone still says yes -- is_offerable() is what actually blocks it
    assert qualifies(character, SPECIALIZATION_DEFS["berserker"])
    assert "berserker" not in {s.id for s in qualifying_specializations(character)}


def test_purity_rule_blocks_a_hybrid_even_when_the_sealed_archetype_is_not_the_primary_one():
    # Paladino: Guerreiro >=40% + Místico >=20% -- sealing Místico (the
    # secondary axis) must still block it, not just sealing Guerreiro.
    character = make_bare_character(
        archetype_usage={Archetype.GUERREIRO: 60.0, Archetype.MISTICO: 30.0, Archetype.GUARDIAO: 10.0},
        sealed_archetypes={Archetype.MISTICO},
    )
    assert qualifies(character, SPECIALIZATION_DEFS["paladino"])
    assert not is_offerable(SPECIALIZATION_DEFS["paladino"], character)
    assert "paladino" not in {s.id for s in qualifying_specializations(character)}


def test_sealing_an_unrelated_archetype_does_not_affect_offerability():
    character = make_bare_character(archetype_usage={Archetype.GUERREIRO: 100.0}, sealed_archetypes={Archetype.MISTICO})
    assert is_offerable(SPECIALIZATION_DEFS["berserker"], character)
    assert "berserker" in {s.id for s in qualifying_specializations(character)}


def test_build_hero_carries_sealed_archetypes_onto_the_character():
    ruleset = build_ruleset()
    class_def = CLASS_DEFS["runeguard"]
    tree = TALENT_TREES[class_def.talent_tree_id]
    hero = create_player_character(
        "hero", "Hero", class_def, tree, ruleset=ruleset, sealed_archetypes={Archetype.MISTICO, Archetype.GUARDIAO},
    )
    assert hero.sealed_archetypes == {Archetype.MISTICO, Archetype.GUARDIAO}


# -- Fase 8: Estágio 2 (docs/design/05b-classes-roster.md §10) ------------------


def test_stage2_table_is_consistent_with_stage1_and_the_content_trees():
    ruleset = build_ruleset()
    assert not set(STAGE2_DEFS) & set(SPECIALIZATION_DEFS)  # ids never collide across stages
    for stage2 in STAGE2_DEFS.values():
        assert stage2.from_specializations and stage2.from_specializations <= set(SPECIALIZATION_DEFS), stage2.id
        if stage2.granted_tree_id is not None:
            tree = TALENT_TREES[stage2.granted_tree_id].definition
            stage1 = SPECIALIZATION_DEFS[next(iter(stage2.from_specializations))]
            stage1_tree_id = stage1.granted_tree_id or f"{stage2.granted_tree_id.split('_', 1)[0]}_{stage1.id}_path"
            stage1_tree = TALENT_TREES[stage1_tree_id].definition
            # the Stage-2 tree is the Stage-1 tree plus its own 2-node branch
            assert {n.id for n in stage1_tree.nodes} < {n.id for n in tree.nodes}, stage2.id
            keystone = tree.node_map()[f"{stage2.id}_keystone"]
            assert keystone.grants_ability in ruleset.abilities, stage2.id
    # every Stage-1 line that has a kit has a Stage-2 continuation with a kit
    with_kit = {s.id for s in SPECIALIZATION_DEFS.values() if s.granted_tree_id}
    continued = set().union(*(s.from_specializations for s in STAGE2_DEFS.values() if s.granted_tree_id))
    assert with_kit <= continued


def _stage1_evolved_session(spec_id: str, class_id: str, usage, char_overrides=None, attribute_points=None, points=5):
    session = make_full_session(class_id=class_id, starting_talent_points=points)
    hero = session.run.party[0]
    hero.archetype_usage = dict(usage)
    hero.attribute_points = dict(attribute_points or {})
    for key, value in (char_overrides or {}).items():
        setattr(hero, key, value)
    assert session.evolve_specialization("hero", spec_id) is True, spec_id
    return session, hero


def test_stage2_requires_stage1_level_10_and_a_matching_line():
    session = make_full_session()
    hero = session.run.party[0]
    hero.level = 10
    hero.archetype_usage = {Archetype.GUERREIRO: 100.0}
    assert session.evolve_specialization("hero", "senhor_da_guerra") is False  # no Stage 1 yet
    assert evolution_offers(hero) and all(o.id in SPECIALIZATION_DEFS for o in evolution_offers(hero))

    assert session.evolve_specialization("hero", "berserker") is True
    hero.level = 9
    assert session.evolve_specialization("hero", "senhor_da_guerra") is False  # below EVOLUTION_STAGE2_LEVEL
    hero.level = EVOLUTION_STAGE2_LEVEL
    assert session.evolve_specialization("hero", "encarnacao_da_batalha") is False  # ascends from Avatar, not Berserker
    assert {o.id for o in evolution_offers(hero)} == {"senhor_da_guerra"}
    assert session.evolve_specialization("hero", "senhor_da_guerra") is True
    assert hero.stage2_specialization_id == "senhor_da_guerra"
    assert session.evolve_specialization("hero", "senhor_da_guerra") is False  # twice
    assert evolution_offers(hero) == []


def test_stage2_keeps_every_allocated_node_and_its_keystone_grants_the_signature():
    session, hero = _stage1_evolved_session("berserker", "runeguard", {Archetype.GUERREIRO: 100.0}, points=8)
    assert session.allocate_talent("hero", "o1") is True
    assert session.allocate_talent("hero", "berserker_1") is True
    assert session.allocate_talent("hero", "berserker_keystone") is True
    allocated_before = set(hero.build.talent_tree.allocated)

    hero.level = EVOLUTION_STAGE2_LEVEL
    assert session.evolve_specialization("hero", "senhor_da_guerra") is True
    assert allocated_before <= hero.build.talent_tree.allocated
    assert "reckless_smash" in hero.abilities  # Stage-1 signature survives
    assert session.allocate_talent("hero", "senhor_da_guerra_1") is True
    assert "storm_of_blows" not in hero.abilities
    assert session.allocate_talent("hero", "senhor_da_guerra_keystone") is True
    assert "storm_of_blows" in hero.abilities


def test_every_reachable_stage2_line_grants_a_real_kit():
    cases = [
        ("berserker", "senhor_da_guerra", "runeguard", {Archetype.GUERREIRO: 100.0}, {}, {}),
        ("avatar_da_guerra", "encarnacao_da_batalha", "runeguard", {Archetype.GUERREIRO: 100.0}, {}, {}),
        ("cavaleiro_negro", "lorde_da_ruina", "runeguard", {Archetype.GUERREIRO: 100.0}, {"alignment_score": -30.0}, {}),
        ("furia_orquica", "senhor_da_horda", "runeguard", {Archetype.GUERREIRO: 100.0}, {"race_id": "orc"}, {}),
        ("lamina_espectral", "ceifador_espectral", "runeguard", {Archetype.GUERREIRO: 100.0}, {"race_id": "renascido"}, {}),
        ("uivo_selvagem", "alfa", "runeguard", {Archetype.GUERREIRO: 100.0}, {"race_id": "licantropo"}, {}),
        ("arqueiro", "mestre_arqueiro", "patrulheiro", {Archetype.PATRULHEIRO: 100.0}, {}, {}),
        ("atirador", "cacador_de_tesouros", "patrulheiro", {Archetype.PATRULHEIRO: 100.0}, {}, {Atributo.LUCK: 3, Atributo.DEXTERITY: 5}),
        ("predador_absoluto", "sombra_da_mata", "patrulheiro", {Archetype.PATRULHEIRO: 100.0}, {}, {}),
        ("arqueiro_elfico", "olho_da_lua", "patrulheiro", {Archetype.PATRULHEIRO: 100.0}, {"race_id": "elf"}, {}),
        ("mago", "arquimago", "mistico", {Archetype.MISTICO: 100.0}, {}, {}),
        ("encantador", "cantor_do_wyrd", "mistico", {Archetype.MISTICO: 100.0}, {}, {Atributo.WISDOM: 5}),
        ("tecelao_do_veu", "oraculo_do_veu", "mistico", {Archetype.MISTICO: 100.0}, {}, {}),
        ("senhor_da_peste", "arauto_da_praga", "mistico", {Archetype.MISTICO: 100.0}, {"alignment_score": -30.0}, {}),
        ("colosso", "tita", "guardiao", {Archetype.GUARDIAO: 100.0}, {}, {Atributo.CONSTITUTION: 5}),
        ("bastiao_eterno", "muralha_viva", "guardiao", {Archetype.GUARDIAO: 100.0}, {}, {}),
        ("guardiao_da_floresta", "coracao_da_floresta", "guardiao", {Archetype.GUARDIAO: 100.0}, {"alignment_score": 30.0}, {}),
        ("punho_de_granito", "coracao_da_montanha", "guardiao", {Archetype.GUARDIAO: 100.0}, {"race_id": "dwarf"}, {}),
    ]
    for spec_id, stage2_id, class_id, usage, overrides, attribute_points in cases:
        session, hero = _stage1_evolved_session(spec_id, class_id, usage, overrides, attribute_points)
        hero.level = EVOLUTION_STAGE2_LEVEL
        assert session.evolve_specialization("hero", stage2_id) is True, stage2_id
        keystone = f"{stage2_id}_keystone"
        ability_id = TALENT_TREES[STAGE2_DEFS[stage2_id].granted_tree_id].definition.node_map()[keystone].grants_ability
        assert session.allocate_talent("hero", f"{stage2_id}_1") is True, stage2_id
        assert session.allocate_talent("hero", keystone) is True, stage2_id
        assert ability_id in hero.abilities, stage2_id


def test_stage2_rereads_the_current_axes_the_05b_section_10_examples():
    # Mago whose Místico slipped under 70% no longer sees Arquimago
    session, hero = _stage1_evolved_session("mago", "mistico", {Archetype.MISTICO: 100.0})
    hero.level = EVOLUTION_STAGE2_LEVEL
    assert "arquimago" in {s.id for s in qualifying_stage2(hero)}
    hero.archetype_usage = {Archetype.MISTICO: 65.0, Archetype.GUERREIRO: 35.0}
    assert "arquimago" not in {s.id for s in qualifying_stage2(hero)}
    assert session.evolve_specialization("hero", "arquimago") is False

    # Guardião da Floresta who turned maligno keeps Stage 1 but loses the
    # Radiante continuation until the alignment climbs back
    session, hero = _stage1_evolved_session(
        "guardiao_da_floresta", "guardiao", {Archetype.GUARDIAO: 100.0}, {"alignment_score": 30.0}
    )
    hero.level = EVOLUTION_STAGE2_LEVEL
    assert "coracao_da_floresta" in {s.id for s in qualifying_stage2(hero)}
    hero.alignment_score = -40.0
    assert hero.specialization_id == "guardiao_da_floresta"
    assert "coracao_da_floresta" not in {s.id for s in qualifying_stage2(hero)}
    assert "Radiante" not in " ".join(variant_display_names(hero, SPECIALIZATION_DEFS["guardiao_da_floresta"]))


def test_the_doc_hybrid_stage2_examples_need_mixed_usage_and_have_kits():
    session, hero = _stage1_evolved_session("berserker", "runeguard", {Archetype.GUERREIRO: 100.0})
    hero.level = EVOLUTION_STAGE2_LEVEL
    assert "arqueiro_berserker_s2" not in {s.id for s in qualifying_stage2(hero)}
    hero.archetype_usage = {Archetype.GUERREIRO: 60.0, Archetype.PATRULHEIRO: 40.0}
    assert "arqueiro_berserker_s2" in {s.id for s in qualifying_stage2(hero)}
    assert session.evolve_specialization("hero", "arqueiro_berserker_s2") is True
    assert session.allocate_talent("hero", "arqueiro_berserker_s2_1") is True
    assert session.allocate_talent("hero", "arqueiro_berserker_s2_keystone") is True
    assert "berserker_bowstring_fury" in hero.abilities

    # Juggernaut/Colosso ascend from Cavaleiro Pesado, itself a hybrid --
    # per-base trees again, from either of its two bases
    for base, class_id in ((Archetype.GUERREIRO, "runeguard"), (Archetype.GUARDIAO, "guardiao")):
        for stage2_id, ability_id, usage in (
            ("juggernaut_s2", "juggernaut_unstoppable", {Archetype.GUERREIRO: 50.0, Archetype.GUARDIAO: 50.0}),
            ("colosso_s2", "colosso_world_weight", {Archetype.GUARDIAO: 70.0, Archetype.GUERREIRO: 30.0}),
        ):
            session, hero = _stage1_evolved_session("cavaleiro_pesado", class_id, usage, points=8)
            assert session.allocate_talent("hero", "cavaleiro_pesado_1") is True
            hero.level = EVOLUTION_STAGE2_LEVEL
            assert session.evolve_specialization("hero", stage2_id) is True, (stage2_id, base)
            assert _talent_tree_id_for(hero) == f"{base.value}_{stage2_id}_path"
            assert "cavaleiro_pesado_1" in hero.build.talent_tree.allocated
            assert session.allocate_talent("hero", f"{stage2_id}_1") is True
            assert session.allocate_talent("hero", f"{stage2_id}_keystone") is True
            assert ability_id in hero.abilities
