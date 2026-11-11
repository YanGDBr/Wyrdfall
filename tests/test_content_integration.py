import random

import pytest

from wyrdfall.domain.abilities import Ability, TargetMode
from wyrdfall.domain.character import Character
from wyrdfall.domain.combat import Action, CombatEngine
from wyrdfall.domain.content import CLASS_DEFS, ENEMY_DEFS, MVP_DUNGEON, TALENT_TREES, build_ruleset
from wyrdfall.domain.dungeon import difficulty_multiplier
from wyrdfall.domain.enemies import instantiate_enemy
from wyrdfall.domain.factory import create_player_character
from wyrdfall.domain.models import DamageElement, Effect, EffectKind, StatBlock, TriggerEvent


def _build_hero(allocated: set[str], class_id: str = "runeguard"):
    ruleset = build_ruleset()
    class_def = CLASS_DEFS[class_id]
    tree = TALENT_TREES[class_def.talent_tree_id]
    hero = create_player_character("hero", "Hero", class_def, tree, allocated_talents=allocated, ruleset=ruleset)
    return ruleset, class_def, hero


def _fight_first_encounter_to_completion(ruleset, hero, seed=42):
    encounter = MVP_DUNGEON.encounters[0]
    mult = difficulty_multiplier(floor_index=0, party_size=1)
    enemies = [
        instantiate_enemy(ENEMY_DEFS[eid], f"{eid}_{i}", stat_multiplier=mult)
        for i, eid in enumerate(encounter.enemy_ids)
    ]
    engine = CombatEngine(ruleset, rng=random.Random(seed))
    state = engine.start_encounter([hero], enemies)

    turns = 0
    while not state.is_over and turns < 200:
        actor_id = state.current_actor_id()
        if state.combatants[actor_id].is_player:
            ability = engine.legal_abilities(state, actor_id)[0]
            targets = engine.legal_target_ids(state, actor_id, ability)
            target_ids = targets[:1] if ability.requires_target else []
            engine.resolve(state, Action(actor_id=actor_id, ability_id=ability.id, target_ids=target_ids))
        else:
            engine.resolve_ai_turn(state)
        turns += 1

    assert state.is_over
    assert turns < 200


def test_runeguard_can_fight_the_first_encounter_to_completion():
    ruleset, _class_def, hero = _build_hero({"o1", "d1", "r1"})
    _fight_first_encounter_to_completion(ruleset, hero)


def test_patrulheiro_can_fight_the_first_encounter_to_completion():
    ruleset, _class_def, hero = _build_hero({"pr1", "in1"}, class_id="patrulheiro")
    _fight_first_encounter_to_completion(ruleset, hero)


def test_mistico_can_fight_the_first_encounter_to_completion():
    ruleset, _class_def, hero = _build_hero({"ar1", "sb1"}, class_id="mistico")
    _fight_first_encounter_to_completion(ruleset, hero)


def test_guardiao_can_fight_the_first_encounter_to_completion():
    ruleset, _class_def, hero = _build_hero({"rs1", "rt1"}, class_id="guardiao")
    _fight_first_encounter_to_completion(ruleset, hero)


def test_talent_allocation_grants_ability_and_bonus_hp():
    _ruleset, class_def, hero = _build_hero({"r1", "r2", "d1", "d1b"})
    assert "rune_smash" in hero.abilities
    # d1b Vitality (+5) + create_player_character's default race_id="human"
    # (+3 STR secondary, +6 CON primary -- see domain/races.py) = +14 flat
    assert hero.current_hp == class_def.base_stats.max_hp + 14


def test_all_dungeon_and_talent_ability_ids_resolve_in_the_ruleset():
    ruleset = build_ruleset()
    for tree in TALENT_TREES.values():
        for node in tree.definition.nodes:
            if node.grants_ability:
                assert node.grants_ability in ruleset.abilities

    for class_def in CLASS_DEFS.values():
        for ability_id in class_def.starting_abilities:
            assert ability_id in ruleset.abilities
        assert class_def.talent_tree_id in TALENT_TREES

    for enemy in ENEMY_DEFS.values():
        for ability_id in enemy.abilities:
            assert ability_id in ruleset.abilities
        for phase in enemy.phases:
            for ability_id in phase.abilities:
                assert ability_id in ruleset.abilities

    for encounter in MVP_DUNGEON.encounters:
        for enemy_id in encounter.enemy_ids:
            assert enemy_id in ENEMY_DEFS


def test_hollow_knight_swaps_to_a_bleed_moveset_in_its_second_phase():
    hollow_knight = ENEMY_DEFS["hollow_knight"]
    assert hollow_knight.base_stats.max_poise > 0
    assert len(hollow_knight.phases) == 2
    assert hollow_knight.phases[0].abilities == ["hollow_smite", "hollow_cleave"]
    assert hollow_knight.phases[1].abilities == ["hollow_smite", "hollow_cleave_bleed"]


# (area_id, expected encounter count, boss enemy_id) for every area shipped
# so far, in dungeon order -- extend this tuple, not the test body, when a
# new area is appended.
_AREAS_IN_ORDER = [
    # docs/design/14-estrutura-da-run.md §4: every regular Área is exactly
    # the 6-node template (Combate / Combate / Evento / Sala Especial /
    # Elite / Chefe); Área 12 is its own shorter corridor
    ("the_hollow_barrow", 6, "hollow_knight"),
    ("the_living_forges", 6, "ashkarion"),
    ("the_frozen_pinnacle", 6, "viuva_de_gelo"),
    ("the_eternal_storm", 6, "voltharion"),
    ("the_drowned_depths", 6, "maremoto"),
    ("the_forgotten_mines", 6, "terrakon"),
    ("the_floating_pinnacles", 6, "zephyra"),
    ("the_putrid_bog", 6, "mae_putrida"),
    ("the_shattered_sanctuary", 6, "solyth"),
    ("the_shadow_beneath_the_veil", 6, "o_inominavel"),
    ("the_fractured_library", 6, "nyxelle"),
    ("the_unraveling_loom", 4, "tecela_desfeita"),
]


def test_areas_are_each_only_reachable_after_the_previous_areas_boss():
    encounters = MVP_DUNGEON.encounters
    assert len(encounters) == sum(count for _, count, _ in _AREAS_IN_ORDER)

    previous_area: list = []
    for area_id, expected_count, boss_id in _AREAS_IN_ORDER:
        area = [e for e in encounters if e.area_id == area_id]
        assert len(area) == expected_count, area_id
        if previous_area:
            # sequential encounters -- each area only comes right after
            # the previous area's boss ends it
            assert encounters.index(area[0]) == encounters.index(previous_area[-1]) + 1, area_id
        # membership rather than exact equality -- Nyxelle (Área 11) is
        # the first boss encounter fought alongside named allies (her
        # Ecos), not solo like every earlier boss.
        assert area[-1].is_boss and boss_id in area[-1].enemy_ids, area_id
        previous_area = area
    assert encounters[-1] is previous_area[-1]  # the dungeon's own last encounter


def test_every_regular_area_follows_the_six_node_template():
    # docs/design/14-estrutura-da-run.md §4: Combate / Combate / Evento /
    # Sala Especial / Elite / Chefe; Área 12 has no Evento or Sala Especial.
    for area_id, _count, _boss in _AREAS_IN_ORDER:
        area = [e for e in MVP_DUNGEON.encounters if e.area_id == area_id]
        if area_id == "the_unraveling_loom":
            assert all(e.room_type == "combat" for e in area), area_id
            continue
        assert [e.room_type for e in area] == ["combat", "combat", "event", "special", "combat", "combat"], area_id
        for index in (2, 3):
            node = area[index]
            assert node.enemy_ids == [] and not node.is_boss and node.flavor_text, area_id
        assert area[-1].is_boss and not area[-2].is_boss, area_id
        # node 5 is the Elite -- the only non-boss fight with the better Carta pool
        assert [e.is_elite for e in area] == [False, False, False, False, True, False], area_id


def test_every_enemy_still_appears_in_at_least_one_encounter():
    # the 6-node trim dropped two authored fights per Área -- nothing in
    # the bestiary may have become unreachable because of it
    used = {enemy_id for e in MVP_DUNGEON.encounters for enemy_id in e.enemy_ids}
    assert set(ENEMY_DEFS) <= used


def test_ashkarion_has_three_phases_and_a_poise_bar():
    ashkarion = ENEMY_DEFS["ashkarion"]
    assert ashkarion.base_stats.max_poise > 0
    assert [p.hp_ceiling for p in ashkarion.phases] == [1.0, 0.7, 0.4]


def test_viuva_de_gelo_has_three_phases_a_poise_bar_and_is_immune_to_fear():
    viuva = ENEMY_DEFS["viuva_de_gelo"]
    assert viuva.base_stats.max_poise > 0
    assert [p.hp_ceiling for p in viuva.phases] == [1.0, 0.6, 0.3]
    assert viuva.phases[0].abilities == ["viuva_frost_bolt"]
    assert viuva.phases[1].abilities == ["viuva_frost_bolt", "viuva_ice_lance"]
    assert viuva.phases[2].abilities == ["viuva_ice_lance", "viuva_glacial_shatter"]
    assert viuva.status_immunities == {"fear"}
    assert viuva.base_stats.ice_resist > 0
    assert viuva.base_stats.fire_resist < 0


def test_cinderling_explodes_on_death():
    cinderling = ENEMY_DEFS["cinderling"]
    assert len(cinderling.triggered_effects) == 1
    trigger = cinderling.triggered_effects[0]
    assert trigger.trigger == TriggerEvent.ON_DEATH
    assert trigger.applies_to == "all_enemies"


def _let_enemy_act(engine, state, enemy_id, ability_id, target_ids):
    """Resolves player/AI turns (any legal action) until it's the given
    enemy's turn, then resolves the specific ability under test --
    avoids depending on exact turn-order speed math in each caller."""
    while state.current_actor_id() != enemy_id:
        actor_id = state.current_actor_id()
        if state.combatants[actor_id].is_player:
            ability = engine.legal_abilities(state, actor_id)[0]
            targets = engine.legal_target_ids(state, actor_id, ability)
            engine.resolve(
                state, Action(actor_id=actor_id, ability_id=ability.id, target_ids=targets[:1] if ability.requires_target else [])
            )
        else:
            engine.resolve_ai_turn(state)
    engine.resolve(state, Action(actor_id=enemy_id, ability_id=ability_id, target_ids=target_ids))


def test_lobo_de_gelo_applies_lentidao_on_hit():
    ruleset = build_ruleset()
    _r, _c, hero = _build_hero({"o1", "d1", "r1"})
    wolf = instantiate_enemy(ENEMY_DEFS["lobo_de_gelo"], "wolf")
    engine = CombatEngine(ruleset, rng=random.Random(1))
    state = engine.start_encounter([hero], [wolf])
    speed_before = state.combatants["hero"].computed_stats(ruleset).speed

    _let_enemy_act(engine, state, "wolf", "wolf_bite", ["hero"])
    assert state.combatants["hero"].computed_stats(ruleset).speed < speed_before


def test_ceifador_de_carambano_applies_fragilidade_ao_gelo_on_hit():
    ruleset = build_ruleset()
    _r, _c, hero = _build_hero({"o1", "d1", "r1"})
    ceifador = instantiate_enemy(ENEMY_DEFS["ceifador_de_carambano"], "ceifador")
    engine = CombatEngine(ruleset, rng=random.Random(1))
    state = engine.start_encounter([hero], [ceifador])
    ice_resist_before = state.combatants["hero"].computed_stats(ruleset).ice_resist

    _let_enemy_act(engine, state, "ceifador", "icicle_volley", ["hero"])
    assert state.combatants["hero"].computed_stats(ruleset).ice_resist < ice_resist_before


def test_thunderbird_strike_chains_to_a_second_party_member():
    ruleset = build_ruleset()
    _r, _c, hero = _build_hero({"o1", "d1", "r1"})
    friend = Character(
        id="friend", name="Friend", class_id="x", base_stats=StatBlock(max_hp=100, speed=1),
        current_hp=100, current_resource=0, abilities=["strike"], equipped_abilities=["strike"], is_player=True,
    )
    ave = instantiate_enemy(ENEMY_DEFS["ave_trovao"], "ave")
    engine = CombatEngine(ruleset, rng=random.Random(1))
    state = engine.start_encounter([hero, friend], [ave])
    hero_hp_before = state.combatants["hero"].current_hp
    friend_hp_before = state.combatants["friend"].current_hp

    _let_enemy_act(engine, state, "ave", "thunderbird_strike", ["hero"])
    assert state.combatants["hero"].current_hp < hero_hp_before
    # the chain should have hit the other party member too
    assert state.combatants["friend"].current_hp < friend_hp_before


def test_sentinela_eletrizada_counter_attacks_when_it_blocks():
    ruleset = build_ruleset()
    sentinela = instantiate_enemy(ENEMY_DEFS["sentinela_eletrizada"], "sentinela")
    sentinela.base_stats.block_chance = 1.0  # force the block deterministically
    hero = Character(
        id="hero", name="Hero", class_id="x", base_stats=StatBlock(max_hp=100, speed=100, attack=5),
        current_hp=100, current_resource=0, abilities=["strike"], equipped_abilities=["strike"], is_player=True,
    )
    engine = CombatEngine(ruleset, rng=random.Random(1))
    state = engine.start_encounter([hero], [sentinela])
    hero_hp_before = state.combatants["hero"].current_hp

    engine.resolve(state, Action(actor_id="hero", ability_id="strike", target_ids=["sentinela"]))
    assert state.combatants["hero"].current_hp < hero_hp_before  # the counter landed


def test_voltharion_phases_on_poise_breaks_with_an_evasion_window_and_a_lightning_identity():
    voltharion = ENEMY_DEFS["voltharion"]
    assert voltharion.base_stats.max_poise > 0
    assert all(p.trigger == "poise_break" for p in voltharion.phases)  # 13-chefes.md §4: breaks, not PV
    assert voltharion.phases[0].abilities == ["voltharion_bolt"]
    assert any(m.stat.value == "dodge_chance" and m.value > 0 for m in voltharion.phases[0].modifiers)
    assert not voltharion.phases[1].modifiers  # the veil drops after the first break
    assert voltharion.phases[2].abilities == ["voltharion_strike", "voltharion_tempest"]
    assert voltharion.base_stats.lightning_resist > 0
    assert voltharion.base_stats.earth_resist < 0


def test_enguia_espectral_drains_resource_from_target_to_self():
    ruleset = build_ruleset()
    _r, _c, hero = _build_hero({"o1", "d1", "r1"})
    hero.abilities = ["strike"]  # a fixed, resource_cost=0 kit -- isolates the drain
    enguia = instantiate_enemy(ENEMY_DEFS["enguia_espectral"], "enguia")
    enguia.current_resource = 0  # so the steal is visible on both sides
    enguia.base_stats.max_hp = 100  # survive the hero's turns before her own comes up
    enguia.current_hp = 100
    engine = CombatEngine(ruleset, rng=random.Random(1))
    state = engine.start_encounter([hero], [enguia])
    state.combatants["hero"].current_resource = 5
    # the runeguard talent kit here grants passive resource regen, which
    # ticks once more when the drain's own action-resolve advances the
    # turn back to the hero -- account for that one extra tick rather
    # than fighting the talent tree's own passive.
    hero_regen = state.combatants["hero"].computed_stats(ruleset).resource_regen_per_turn

    _let_enemy_act(engine, state, "enguia", "resource_drain", ["hero"])
    # ...and the Runeguard's resource is Fúria now (11-habilidades.md §7.1):
    # it also cools by 1 at a turn start that follows an own turn without
    # spending, which is exactly this hero's situation here.
    from wyrdfall.domain.combat import FURY_DECAY_PER_IDLE_TURN

    assert state.combatants["hero"].current_resource == pytest.approx(5 - 2 + hero_regen - FURY_DECAY_PER_IDLE_TURN)
    assert state.combatants["enguia"].current_resource == pytest.approx(2.0)


def test_encharcado_amplifies_raio_and_reduces_fogo_damage_taken():
    ruleset = build_ruleset()
    _r, _c, hero = _build_hero({"o1", "d1", "r1"})
    afogado = instantiate_enemy(ENEMY_DEFS["afogado"], "afogado")
    afogado.base_stats.max_hp = 100  # survive the hero's turns before its own comes up
    afogado.current_hp = 100
    engine = CombatEngine(ruleset, rng=random.Random(1))
    state = engine.start_encounter([hero], [afogado])
    lightning_resist_before = state.combatants["hero"].computed_stats(ruleset).lightning_resist
    fire_resist_before = state.combatants["hero"].computed_stats(ruleset).fire_resist

    _let_enemy_act(engine, state, "afogado", "drowned_grasp", ["hero"])
    hero_after = state.combatants["hero"].computed_stats(ruleset)
    assert hero_after.lightning_resist < lightning_resist_before
    assert hero_after.fire_resist > fire_resist_before


def test_maremoto_has_two_phases_and_an_extreme_terra_weakness():
    maremoto = ENEMY_DEFS["maremoto"]
    assert maremoto.base_stats.max_poise > 0
    assert [p.hp_ceiling for p in maremoto.phases] == [1.0, 0.5]
    assert maremoto.phases[1].abilities == ["maremoto_bite", "maremoto_soak", "maremoto_undertow"]
    assert maremoto.base_stats.water_resist > 0
    # documented as the first deliberately-extreme elemental weakness --
    # more negative than any prior boss's own weakness (dwarf/orc/etc.
    # race and earlier-area weaknesses top out around -0.4).
    assert maremoto.base_stats.earth_resist < -0.4
    assert maremoto.status_immunities == {"afogar"}


def test_shatter_curse_applies_fragmentado_reducing_defense():
    ruleset = build_ruleset()
    _r, _c, hero = _build_hero({"o1", "d1", "r1"})
    xama = instantiate_enemy(ENEMY_DEFS["xama_de_pedra"], "xama")
    xama.base_stats.max_hp = 100  # survive the hero's turns before its own comes up
    xama.current_hp = 100
    engine = CombatEngine(ruleset, rng=random.Random(1))
    state = engine.start_encounter([hero], [xama])
    defense_before = state.combatants["hero"].computed_stats(ruleset).defense

    _let_enemy_act(engine, state, "xama", "shatter_curse", ["hero"])
    assert state.combatants["hero"].computed_stats(ruleset).defense < defense_before


def test_guardiao_cristalino_reflects_damage_when_hit():
    ruleset = build_ruleset()
    hero = Character(
        id="hero", name="Hero", class_id="x", base_stats=StatBlock(max_hp=100, speed=100, attack=5),
        current_hp=100, current_resource=0, abilities=["strike"], equipped_abilities=["strike"], is_player=True,
    )
    guardiao = instantiate_enemy(ENEMY_DEFS["guardiao_cristalino"], "guardiao")
    engine = CombatEngine(ruleset, rng=random.Random(1))
    state = engine.start_encounter([hero], [guardiao])
    hero_hp_before = state.combatants["hero"].current_hp

    engine.resolve(state, Action(actor_id="hero", ability_id="strike", target_ids=["guardiao"]))
    assert state.combatants["hero"].current_hp < hero_hp_before  # the reflection landed


def test_terrakon_has_two_phases_a_tanky_profile_and_fragmentado_immunity():
    terrakon = ENEMY_DEFS["terrakon"]
    assert [p.hp_ceiling for p in terrakon.phases] == [1.0, 0.5]
    assert terrakon.phases[1].abilities == ["terrakon_crush", "terrakon_quake"]
    assert terrakon.status_immunities == {"fragmentado"}
    assert terrakon.base_stats.earth_resist > 0
    assert terrakon.base_stats.air_resist < 0
    # the highest Defense/max_poise/max_hp of any boss so far
    other_bosses = [ENEMY_DEFS[eid] for eid in ("ashkarion", "viuva_de_gelo", "voltharion", "maremoto")]
    assert terrakon.base_stats.defense > max(b.base_stats.defense for b in other_bosses)
    assert terrakon.base_stats.max_poise > max(b.base_stats.max_poise for b in other_bosses)
    assert terrakon.base_stats.max_hp > max(b.base_stats.max_hp for b in other_bosses)


def test_harpy_gust_applies_desequilibrado_reducing_dodge_and_block():
    ruleset = build_ruleset()
    _r, _c, hero = _build_hero({"o1", "d1", "r1"})
    harpia = instantiate_enemy(ENEMY_DEFS["harpia"], "harpia")
    harpia.base_stats.max_hp = 100  # survive the hero's turns before its own comes up
    harpia.current_hp = 100
    engine = CombatEngine(ruleset, rng=random.Random(1))
    state = engine.start_encounter([hero], [harpia])
    dodge_before = state.combatants["hero"].computed_stats(ruleset).dodge_chance
    block_before = state.combatants["hero"].computed_stats(ruleset).block_chance

    _let_enemy_act(engine, state, "harpia", "harpy_gust", ["hero"])
    hero_after = state.combatants["hero"].computed_stats(ruleset)
    assert hero_after.dodge_chance < dodge_before
    assert hero_after.block_chance < block_before


def test_fragmentado_and_desequilibrado_are_mutually_exclusive():
    ruleset = build_ruleset()
    target = Character(
        id="target", name="Target", class_id="x", base_stats=StatBlock(speed=5),
        current_hp=20, current_resource=0, abilities=[], is_player=True,
        equipped_abilities=[],
    )
    attacker = Character(
        id="attacker", name="Attacker", class_id="y", base_stats=StatBlock(speed=10),
        current_hp=20, current_resource=0, abilities=[], is_player=False,
        equipped_abilities=[],
    )
    engine = CombatEngine(ruleset, rng=random.Random(1))
    state = engine.start_encounter([target], [attacker])

    engine._apply_status(state, state.combatants["target"], "fragmentado", duration=3, stacks=1)
    assert {s.status_id for s in state.combatants["target"].statuses} == {"fragmentado"}

    engine._apply_status(state, state.combatants["target"], "desequilibrado", duration=3, stacks=1)
    ids = {s.status_id for s in state.combatants["target"].statuses}
    assert ids == {"desequilibrado"}  # fragmentado was stripped, not stacked alongside it

    engine._apply_status(state, state.combatants["target"], "fragmentado", duration=3, stacks=1)
    assert {s.status_id for s in state.combatants["target"].statuses} == {"fragmentado"}


def test_roc_menor_applies_desequilibrado_to_whoever_misses_it():
    ruleset = build_ruleset()
    hero = Character(
        id="hero", name="Hero", class_id="x", base_stats=StatBlock(max_hp=100, speed=100, attack=5),
        current_hp=100, current_resource=0, abilities=["strike"], equipped_abilities=["strike"], is_player=True,
    )
    roc = instantiate_enemy(ENEMY_DEFS["roc_menor"], "roc")
    roc.base_stats.dodge_chance = 1.0  # force the dodge deterministically
    engine = CombatEngine(ruleset, rng=random.Random(1))
    state = engine.start_encounter([hero], [roc])

    engine.resolve(state, Action(actor_id="hero", ability_id="strike", target_ids=["roc"]))
    assert any(s.status_id == "desequilibrado" for s in state.combatants["hero"].statuses)


def test_zephyra_phase_two_deals_two_hits_in_one_action():
    ruleset = build_ruleset()
    zephyra = instantiate_enemy(ENEMY_DEFS["zephyra"], "zephyra")
    dummy = Character(
        id="dummy", name="Dummy", class_id="x", base_stats=StatBlock(max_hp=300, speed=1),
        current_hp=300, current_resource=0, abilities=["strike"], equipped_abilities=["strike"], is_player=True,
    )
    engine = CombatEngine(ruleset, rng=random.Random(1))
    state = engine.start_encounter([dummy], [zephyra])
    # force phase 2 directly rather than fighting zephyra down to it
    state.combatants["zephyra"].current_phase_index = 1
    state.combatants["zephyra"].abilities = ["zephyra_double_gale"]
    hp_before = state.combatants["dummy"].current_hp

    _let_enemy_act(engine, state, "zephyra", "zephyra_double_gale", ["dummy"])
    single_hit_damage = state.combatants["zephyra"].computed_stats(ruleset).attack * 1.0 + 4.0
    # two hits landed, not one -- total damage is roughly double a lone hit
    assert (hp_before - state.combatants["dummy"].current_hp) > single_hit_damage * 1.5


def test_sanguessuga_gigante_heals_itself_via_lifesteal_on_hit():
    ruleset = build_ruleset()
    _r, _c, hero = _build_hero({"o1", "d1", "r1"})
    sanguessuga = instantiate_enemy(ENEMY_DEFS["sanguessuga_gigante"], "sanguessuga")
    sanguessuga.base_stats.max_hp = 100
    sanguessuga.current_hp = 50  # leave room to observe the heal
    sanguessuga.base_stats.speed = 100  # act first -- no preliminary hero attack to confound the reading
    engine = CombatEngine(ruleset, rng=random.Random(1))
    state = engine.start_encounter([hero], [sanguessuga])
    assert state.current_actor_id() == "sanguessuga"

    engine.resolve(state, Action(actor_id="sanguessuga", ability_id="leech_bite", target_ids=["hero"]))
    assert state.combatants["sanguessuga"].current_hp > 50


def test_esporo_ambulante_death_cloud_poisons_the_party():
    ruleset = build_ruleset()
    _r, _c, hero = _build_hero({"o1", "d1", "r1"})
    esporo = instantiate_enemy(ENEMY_DEFS["esporo_ambulante"], "esporo")
    # low enough HP that the hero's own faster turn (esporo's speed=6 <
    # the runeguard's base 8) kills it outright in a single hit
    engine = CombatEngine(ruleset, rng=random.Random(1))
    state = engine.start_encounter([hero], [esporo])
    assert state.current_actor_id() == "hero"

    engine.resolve(state, Action(actor_id="hero", ability_id="strike", target_ids=["esporo"]))
    assert state.combatants["esporo"].is_alive is False
    assert any(s.status_id == "poisoned" for s in state.combatants["hero"].statuses)


def test_mae_putrida_splits_off_a_broto_on_every_break_and_is_immune_to_her_own_poison():
    mae_putrida = ENEMY_DEFS["mae_putrida"]
    assert all(p.trigger == "poise_break" for p in mae_putrida.phases)
    assert mae_putrida.phases[0].summon_id is None
    assert all(p.summon_id == "broto_putrido" for p in mae_putrida.phases[1:])  # 13-chefes.md §8
    assert mae_putrida.phases[-1].abilities == ["putrid_mother_bite", "putrid_swarm"]
    assert mae_putrida.status_immunities == {"poisoned"}
    assert mae_putrida.base_stats.poison_resist > 0
    assert mae_putrida.base_stats.holy_resist < 0


def test_solyth_mercy_heals_the_player_party():
    ruleset = build_ruleset()
    _r, _c, hero = _build_hero({"o1", "d1", "r1"})
    hero.current_hp = 5  # leave room to observe the heal
    solyth = instantiate_enemy(ENEMY_DEFS["solyth"], "solyth")
    solyth.base_stats.max_hp = 200  # survive the hero's turns before her own comes up
    solyth.current_hp = 200
    engine = CombatEngine(ruleset, rng=random.Random(1))
    state = engine.start_encounter([hero], [solyth])

    _let_enemy_act(engine, state, "solyth", "solyth_mercy", [])
    assert state.combatants["hero"].current_hp > 5


def test_light_guardian_strike_deals_bonus_damage_to_a_renascido_hero():
    ruleset = build_ruleset()
    class_def = CLASS_DEFS["runeguard"]
    tree = TALENT_TREES[class_def.talent_tree_id]
    renascido_hero = create_player_character(
        "hero", "Hero", class_def, tree, ruleset=ruleset, race_id="renascido",
    )
    plain_hero = create_player_character("hero", "Hero", class_def, tree, ruleset=ruleset, race_id="human")
    assert "undead" in renascido_hero.tags
    assert not plain_hero.tags

    guardiao = instantiate_enemy(ENEMY_DEFS["guardiao_de_luz"], "guardiao")
    engine = CombatEngine(ruleset, rng=random.Random(1))

    state_renascido = engine.start_encounter([renascido_hero], [guardiao])
    _let_enemy_act(engine, state_renascido, "guardiao", "light_guardian_strike", ["hero"])
    renascido_hp_after = state_renascido.combatants["hero"].current_hp

    state_plain = engine.start_encounter([plain_hero], [instantiate_enemy(ENEMY_DEFS["guardiao_de_luz"], "guardiao")])
    _let_enemy_act(engine, state_plain, "guardiao", "light_guardian_strike", ["hero"])
    plain_hp_after = state_plain.combatants["hero"].current_hp

    # both heroes start from the same computed max_hp -- the Renascido
    # one should have taken strictly more damage from the same attack
    assert renascido_hp_after < plain_hp_after


def test_amaldicoado_reduces_healing_received():
    ruleset = build_ruleset()
    heal = Ability(
        id="heal", name="Heal", resource_cost=0, target_mode=TargetMode.SELF,
        effects=[Effect(kind=EffectKind.HEAL, amount=10.0)],
    )
    ruleset.abilities["heal"] = heal
    hero = Character(
        id="hero", name="Hero", class_id="x", base_stats=StatBlock(max_hp=100, speed=10),
        current_hp=50, current_resource=0, abilities=["heal"], is_player=True,
        equipped_abilities=["heal"],
    )
    engine = CombatEngine(ruleset, rng=random.Random(1))
    state = engine.start_encounter([hero], [instantiate_enemy(ENEMY_DEFS["cantor_de_hinos"], "cantor")])
    engine._apply_status(state, state.combatants["hero"], "amaldicoado", duration=3, stacks=1)

    engine.resolve(state, Action(actor_id="hero", ability_id="heal", target_ids=[]))
    # base heal 10 * (1 - 0.4) = 6
    assert state.combatants["hero"].current_hp == pytest.approx(56.0)


def test_zelote_cego_swaps_to_a_stronger_attack_below_half_hp():
    zelote = ENEMY_DEFS["zelote_cego"]
    assert [p.hp_ceiling for p in zelote.phases] == [1.0, 0.5]
    assert zelote.phases[0].abilities == ["zealot_strike"]
    assert zelote.phases[1].abilities == ["zealot_fury_strike"]


def test_whisper_fear_applies_fear_reducing_attack():
    ruleset = build_ruleset()
    _r, _c, hero = _build_hero({"o1", "d1", "r1"})
    sussurro = instantiate_enemy(ENEMY_DEFS["sussurro"], "sussurro")
    sussurro.base_stats.max_hp = 100  # survive the hero's turns before its own comes up
    sussurro.current_hp = 100
    engine = CombatEngine(ruleset, rng=random.Random(1))
    state = engine.start_encounter([hero], [sussurro])
    attack_before = state.combatants["hero"].computed_stats(ruleset).attack

    _let_enemy_act(engine, state, "sussurro", "whisper_fear", ["hero"])
    assert state.combatants["hero"].computed_stats(ruleset).attack < attack_before


def test_carne_amaldicoada_survives_a_lethal_hit_exactly_once():
    ruleset = build_ruleset()
    carne = instantiate_enemy(ENEMY_DEFS["carne_amaldicoada"], "carne")
    assert carne.can_cheat_death is True
    lethal = Effect(kind=EffectKind.DAMAGE, amount=1000.0)
    attacker = Character(
        id="attacker", name="Attacker", class_id="x", base_stats=StatBlock(speed=10),
        current_hp=10, current_resource=0, abilities=[], is_player=True,
        equipped_abilities=[],
    )
    engine = CombatEngine(ruleset, rng=random.Random(1))
    state = engine.start_encounter([attacker], [carne])

    engine._apply_damage(state, state.combatants["attacker"], attacker.computed_stats(ruleset), state.combatants["carne"], lethal)
    assert state.combatants["carne"].current_hp == pytest.approx(1.0)  # Latente -- survives once
    assert state.combatants["carne"].cheated_death_used is True

    engine._apply_damage(state, state.combatants["attacker"], attacker.computed_stats(ruleset), state.combatants["carne"], lethal)
    assert state.combatants["carne"].current_hp == pytest.approx(0.0)  # dies for good the second time


def test_devorador_de_luz_drains_resource_from_the_whole_party():
    ruleset = build_ruleset()
    hero1 = Character(
        id="hero1", name="Hero1", class_id="x", base_stats=StatBlock(max_hp=50, speed=1, max_resource=10),
        current_hp=50, current_resource=5, abilities=["strike"], equipped_abilities=["strike"], is_player=True,
    )
    hero2 = Character(
        id="hero2", name="Hero2", class_id="x", base_stats=StatBlock(max_hp=50, speed=1, max_resource=10),
        current_hp=50, current_resource=5, abilities=["strike"], equipped_abilities=["strike"], is_player=True,
    )
    devorador = instantiate_enemy(ENEMY_DEFS["devorador_de_luz"], "devorador")
    engine = CombatEngine(ruleset, rng=random.Random(1))
    state = engine.start_encounter([hero1, hero2], [devorador])

    _let_enemy_act(engine, state, "devorador", "light_devourer_drain", [])
    assert state.combatants["hero1"].current_resource < 5
    assert state.combatants["hero2"].current_resource < 5


def test_o_inominavel_draws_a_random_mask_on_each_break_and_has_near_shadow_immunity():
    inominavel = ENEMY_DEFS["o_inominavel"]
    assert inominavel.random_phase_on_break  # 13-chefes.md §10: never the same Máscara twice in a row
    assert all(p.trigger == "poise_break" for p in inominavel.phases)
    assert inominavel.phases[0].abilities == ["nameless_claws"]
    assert inominavel.phases[1].abilities == ["nameless_eyes"]
    assert inominavel.phases[2].abilities == ["nameless_mouths"]
    assert inominavel.base_stats.shadow_resist == pytest.approx(0.9)
    assert inominavel.base_stats.holy_resist < 0


def test_viuva_de_gelo_enrage_stacks_attack_turn_over_turn():
    ruleset = build_ruleset()
    viuva = instantiate_enemy(ENEMY_DEFS["viuva_de_gelo"], "viuva")
    # A high-HP stand-in target -- goblin's 10 HP wouldn't survive even one
    # of Viúva's hits, cutting the fight short before a second turn.
    dummy = Character(
        id="dummy", name="Dummy", class_id="x", base_stats=StatBlock(max_hp=200, speed=1),
        current_hp=200, current_resource=0, abilities=["strike"], equipped_abilities=["strike"], is_player=True,
    )
    engine = CombatEngine(ruleset, rng=random.Random(1))
    state = engine.start_encounter([dummy], [viuva])
    attack_after_first_turn = state.combatants["viuva"].computed_stats(ruleset).attack

    _let_enemy_act(engine, state, "viuva", "viuva_frost_bolt", ["dummy"])
    _let_enemy_act(engine, state, "viuva", "viuva_frost_bolt", ["dummy"])
    attack_after_second_turn = state.combatants["viuva"].computed_stats(ruleset).attack
    assert attack_after_second_turn > attack_after_first_turn


def test_nyxelle_is_immune_to_damage_while_either_eco_is_alive():
    ruleset = build_ruleset()
    attacker = Character(
        id="attacker", name="Attacker", class_id="x", base_stats=StatBlock(speed=10),
        current_hp=10, current_resource=0, abilities=[], is_player=True,
        equipped_abilities=[],
    )
    nyxelle = instantiate_enemy(ENEMY_DEFS["nyxelle"], "nyxelle_0")
    eco_fogo = instantiate_enemy(ENEMY_DEFS["eco_de_nyxelle_fogo"], "eco_de_nyxelle_fogo_1")
    eco_gelo = instantiate_enemy(ENEMY_DEFS["eco_de_nyxelle_gelo"], "eco_de_nyxelle_gelo_2")
    engine = CombatEngine(ruleset, rng=random.Random(1))
    state = engine.start_encounter([attacker], [nyxelle, eco_fogo, eco_gelo])
    hit = Effect(kind=EffectKind.DAMAGE, amount=50.0, damage_element=DamageElement.PHYSICAL)
    max_hp = nyxelle.base_stats.max_hp

    engine._apply_damage(state, state.combatants["attacker"], attacker.computed_stats(ruleset), state.combatants["nyxelle_0"], hit)
    assert state.combatants["nyxelle_0"].current_hp == pytest.approx(max_hp)  # both Ecos alive

    state.combatants["eco_de_nyxelle_fogo_1"].current_hp = 0
    engine._apply_damage(state, state.combatants["attacker"], attacker.computed_stats(ruleset), state.combatants["nyxelle_0"], hit)
    assert state.combatants["nyxelle_0"].current_hp == pytest.approx(max_hp)  # Eco de Gelo still alive

    state.combatants["eco_de_nyxelle_gelo_2"].current_hp = 0
    engine._apply_damage(state, state.combatants["attacker"], attacker.computed_stats(ruleset), state.combatants["nyxelle_0"], hit)
    assert state.combatants["nyxelle_0"].current_hp < max_hp  # both Ecos dead -- no longer immune


def test_nyxelle_heals_from_arcane_damage_instead_of_taking_it():
    ruleset = build_ruleset()
    attacker = Character(
        id="attacker", name="Attacker", class_id="x", base_stats=StatBlock(speed=10),
        current_hp=10, current_resource=0, abilities=[], is_player=True,
        equipped_abilities=[],
    )
    nyxelle = instantiate_enemy(ENEMY_DEFS["nyxelle"], "nyxelle_0")
    nyxelle.current_hp = nyxelle.base_stats.max_hp - 20  # room to heal
    engine = CombatEngine(ruleset, rng=random.Random(1))
    state = engine.start_encounter([attacker], [nyxelle])
    arcane_hit = Effect(kind=EffectKind.DAMAGE, amount=15.0, damage_element=DamageElement.ARCANE)

    hp_before = state.combatants["nyxelle_0"].current_hp
    engine._apply_damage(state, state.combatants["attacker"], attacker.computed_stats(ruleset), state.combatants["nyxelle_0"], arcane_hit)
    assert state.combatants["nyxelle_0"].current_hp > hp_before


def test_paradox_unstable_strike_hits_with_more_than_one_element_over_many_turns():
    ruleset = build_ruleset()
    ability = ruleset.abilities["paradox_unstable_strike"]
    effect = ability.effects[0]
    assert effect.random_damage_element is True

    attacker = Character(
        id="attacker", name="Attacker", class_id="x", base_stats=StatBlock(attack=10, speed=1),
        current_hp=10, current_resource=0, abilities=[], is_player=False,
        equipped_abilities=[],
    )
    dummy = Character(
        id="dummy", name="Dummy", class_id="x", base_stats=StatBlock(max_hp=5000, speed=1),
        current_hp=5000, current_resource=0, abilities=[], is_player=True,
        equipped_abilities=[],
    )
    engine = CombatEngine(ruleset, rng=random.Random(7))
    state = engine.start_encounter([dummy], [attacker])

    for _ in range(30):
        engine._apply_damage(
            state, state.combatants["attacker"], attacker.computed_stats(ruleset), state.combatants["dummy"], effect
        )

    elements_hit = {el for el, amt in state.combatants["attacker"].elemental_usage.items() if amt > 0}
    assert len(elements_hit) > 1


def test_wandering_book_read_resist_penetration_increases_damage_against_a_resisted_target():
    ruleset = build_ruleset()
    attacker = Character(
        id="attacker", name="Attacker", class_id="x", base_stats=StatBlock(attack=10, speed=1),
        current_hp=10, current_resource=0, abilities=[], is_player=False,
        equipped_abilities=[],
    )
    target = Character(
        id="target", name="Target", class_id="x",
        base_stats=StatBlock(max_hp=500, speed=1, arcane_resist=0.5),
        current_hp=500, current_resource=0, abilities=[], is_player=True,
        equipped_abilities=[],
    )
    plain = Effect(kind=EffectKind.DAMAGE, amount=20.0, damage_element=DamageElement.ARCANE)
    penetrating = Effect(
        kind=EffectKind.DAMAGE, amount=20.0, damage_element=DamageElement.ARCANE, resist_penetration_percent=0.5
    )
    engine = CombatEngine(ruleset, rng=random.Random(3))
    state = engine.start_encounter([target], [attacker])

    engine._apply_damage(state, state.combatants["attacker"], attacker.computed_stats(ruleset), state.combatants["target"], plain)
    plain_damage = 500.0 - state.combatants["target"].current_hp

    state.combatants["target"].current_hp = 500.0
    engine._apply_damage(state, state.combatants["attacker"], attacker.computed_stats(ruleset), state.combatants["target"], penetrating)
    penetrating_damage = 500.0 - state.combatants["target"].current_hp

    assert penetrating_damage > plain_damage


def test_copista_louco_applies_weakened_to_the_party():
    ruleset = build_ruleset()
    hero1 = Character(
        id="hero1", name="Hero1", class_id="x", base_stats=StatBlock(max_hp=50, speed=1, attack=10),
        current_hp=50, current_resource=0, abilities=["strike"], equipped_abilities=["strike"], is_player=True,
    )
    hero2 = Character(
        id="hero2", name="Hero2", class_id="x", base_stats=StatBlock(max_hp=50, speed=1, attack=10),
        current_hp=50, current_resource=0, abilities=["strike"], equipped_abilities=["strike"], is_player=True,
    )
    copista = instantiate_enemy(ENEMY_DEFS["copista_louco"], "copista")
    engine = CombatEngine(ruleset, rng=random.Random(1))
    state = engine.start_encounter([hero1, hero2], [copista])
    attack1_before = state.combatants["hero1"].computed_stats(ruleset).attack
    attack2_before = state.combatants["hero2"].computed_stats(ruleset).attack

    _let_enemy_act(engine, state, "copista", "mad_copyist_mirror", [])
    assert state.combatants["hero1"].computed_stats(ruleset).attack < attack1_before
    assert state.combatants["hero2"].computed_stats(ruleset).attack < attack2_before


def test_tecela_desfeita_has_four_phases_in_a_fixed_order_and_no_fixed_resist():
    tecela = ENEMY_DEFS["tecela_desfeita"]
    assert [p.hp_ceiling for p in tecela.phases] == [1.0, 0.66, 0.33, 0.15]
    assert tecela.phases[0].abilities == ["loom_thread_of_fire", "loom_thread_of_ice"]
    assert tecela.phases[1].abilities == ["loom_thread_of_lightning", "loom_thread_of_earth"]
    assert tecela.phases[2].abilities == ["loom_thread_of_shadow", "loom_thread_of_light"]
    assert tecela.phases[3].abilities == ["loom_broken_thread"]
    # "Nenhuma resistência elemental fixa" -- EnemyPhase can't override
    # resistances per-phase, so none is set at all (a flat, neutral
    # profile instead of one that changes per phase).
    for stat in ("fire_resist", "ice_resist", "lightning_resist", "earth_resist", "shadow_resist", "holy_resist"):
        assert getattr(tecela.base_stats, stat) == 0.0


def test_fio_partido_enrage_stacks_attack_turn_over_turn():
    ruleset = build_ruleset()
    dummy = Character(
        id="dummy", name="Dummy", class_id="x", base_stats=StatBlock(max_hp=2000, speed=1),
        current_hp=2000, current_resource=0, abilities=["strike"], equipped_abilities=["strike"], is_player=True,
    )
    tecela = instantiate_enemy(ENEMY_DEFS["tecela_desfeita"], "tecela")
    engine = CombatEngine(ruleset, rng=random.Random(1))
    state = engine.start_encounter([dummy], [tecela])
    attack_after_first_turn = state.combatants["tecela"].computed_stats(ruleset).attack

    _let_enemy_act(engine, state, "tecela", "loom_thread_of_fire", ["dummy"])
    _let_enemy_act(engine, state, "tecela", "loom_thread_of_fire", ["dummy"])
    attack_after_second_turn = state.combatants["tecela"].computed_stats(ruleset).attack
    assert attack_after_second_turn > attack_after_first_turn


def test_encharcado_increases_lightning_damage_against_tecela_desfeita():
    # Confirms the "double-primer Reação Elemental" doc mechanic needs
    # no new work -- the existing generic resist-debuffing status
    # mechanic (Água's encharcado) already applies to any enemy target,
    # her included, with no special-case immunity blocking it.
    ruleset = build_ruleset()
    attacker = Character(
        id="attacker", name="Attacker", class_id="x", base_stats=StatBlock(attack=10, speed=10),
        current_hp=10, current_resource=0, abilities=[], is_player=True,
        equipped_abilities=[],
    )
    tecela = instantiate_enemy(ENEMY_DEFS["tecela_desfeita"], "tecela")
    lightning_hit = Effect(kind=EffectKind.DAMAGE, amount=20.0, damage_element=DamageElement.LIGHTNING)
    engine = CombatEngine(ruleset, rng=random.Random(1))
    state = engine.start_encounter([attacker], [tecela])

    hp_before = state.combatants["tecela"].current_hp
    engine._apply_damage(state, state.combatants["attacker"], attacker.computed_stats(ruleset), state.combatants["tecela"], lightning_hit)
    plain_damage = hp_before - state.combatants["tecela"].current_hp

    engine._apply_status(state, state.combatants["tecela"], "encharcado", duration=3, stacks=1)
    hp_before2 = state.combatants["tecela"].current_hp
    engine._apply_damage(state, state.combatants["attacker"], attacker.computed_stats(ruleset), state.combatants["tecela"], lightning_hit)
    debuffed_damage = hp_before2 - state.combatants["tecela"].current_hp

    assert debuffed_damage > plain_damage
