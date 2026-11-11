"""Selamentos as a real system (docs/design/10-sistemas-de-build.md §7),
consumíveis em combate (14-estrutura-da-run.md §6) and the Renascido's
"Abraçar a Morte" (04-racas.md, 09-roadmap.md decision 1)."""

import pytest

from wyrdfall.domain.combat import Action, CombatError
from wyrdfall.domain.content import CLASS_DEFS, TALENT_TREES, build_ruleset
from wyrdfall.domain.dungeon import DungeonDef, EncounterDef
from wyrdfall.domain.factory import create_player_character
from wyrdfall.domain.models import Archetype, DamageElement
from wyrdfall.domain.run import RunState
from wyrdfall.domain.sealing import archetype_seal_bonus, element_seal_bonus, is_sealed_source
from wyrdfall.engine.session import WYRD_PER_EMBRACE, GameSession


def _session(class_id="runeguard", race_id="human", sealed_archetypes=(), sealed_elements=(), encounters=None, points=0):
    ruleset = build_ruleset()
    class_def = CLASS_DEFS[class_id]
    tree = TALENT_TREES[class_def.talent_tree_id]
    hero = create_player_character(
        "hero", "Hero", class_def, tree, ruleset=ruleset, race_id=race_id, starting_talent_points=points,
        sealed_archetypes=set(sealed_archetypes), sealed_elements=set(sealed_elements),
    )
    dungeon = DungeonDef(id="t", name="t", encounters=encounters or [EncounterDef(id="e", name="e", enemy_ids=["goblin"])])
    return GameSession(RunState(run_id="r", seed=1, dungeon_id="t", party=[hero]), ruleset, dict(TALENT_TREES), dungeon=dungeon)


# -- Selamentos ---------------------------------------------------------------------------


def test_the_bonus_curves_match_the_doc():
    assert [archetype_seal_bonus(n) for n in range(4)] == pytest.approx([0.0, 0.10, 0.25, 0.50])
    assert [element_seal_bonus(n) for n in (0, 1, 4, 5, 9)] == pytest.approx([0.0, 0.05, 0.20, 0.25, 0.25])


def test_seals_show_up_as_damage_bonuses_on_the_hero():
    plain = _session().run.party[0]
    sealed = _session(sealed_archetypes=[Archetype.MISTICO, Archetype.PATRULHEIRO], sealed_elements=[DamageElement.FIRE]).run.party[0]
    ruleset = build_ruleset()
    assert sealed.computed_stats(ruleset).physical_damage_percent == pytest.approx(plain.computed_stats(ruleset).physical_damage_percent + 0.25)
    assert sealed.computed_stats(ruleset).elemental_damage_percent == pytest.approx(plain.computed_stats(ruleset).elemental_damage_percent + 0.30)


def test_strict_purity_a_partial_weight_or_a_sealed_element_blocks_the_source():
    hero = _session(sealed_archetypes=[Archetype.MISTICO], sealed_elements=[DamageElement.SHADOW]).run.party[0]
    assert is_sealed_source(hero, archetype_weight={Archetype.GUERREIRO: 0.6, Archetype.MISTICO: 0.4})
    assert not is_sealed_source(hero, archetype_weight={Archetype.GUERREIRO: 1.0})
    assert is_sealed_source(hero, damage_elements=[DamageElement.SHADOW])
    assert not is_sealed_source(hero, damage_elements=[DamageElement.PHYSICAL, DamageElement.FIRE])


def test_sealed_sources_never_enter_the_pool_weapon_tomo_keystone_and_offers():
    session = _session(sealed_archetypes=[Archetype.MISTICO], points=5)
    hero = session.run.party[0]
    # a staff's Faísca is Místico-weighted -> refused on equip
    session.equip_weapon("hero", "staff")
    assert "weapon_spark" not in hero.abilities
    session.equip_weapon("hero", "bow")
    assert "weapon_shot" in hero.abilities  # Patrulheiro isn't sealed
    # a Místico Tomo teaches nothing
    session.run.consumables.append("tomo_do_mistico")
    session.use_consumable("hero", "tomo_do_mistico")
    assert "tome_arcane_pulse" not in hero.abilities
    # a keystone granting a sealed ability can't be allocated
    hero.archetype_usage = {Archetype.GUERREIRO: 60.0, Archetype.MISTICO: 40.0}
    hero.level = 5
    assert session.evolve_specialization("hero", "paladino") is False  # sealed spec -> not offerable (already true)
    session.run.party[0].sealed_archetypes = set()
    assert session.evolve_specialization("hero", "paladino") is True
    session.run.party[0].sealed_archetypes = {Archetype.MISTICO}
    assert session.allocate_talent("hero", "paladino_1") is True
    assert session.allocate_talent("hero", "paladino_keystone") is False  # Golpe Sagrado carries Místico weight

    # card offers and the shop shelf skip sealed cards
    fire_sealed = _session(sealed_elements=[DamageElement.FIRE], encounters=[
        EncounterDef(id="e", name="e", enemy_ids=["goblin"]), EncounterDef(id="s", name="s", room_type="shop"),
    ])
    from tests.test_session import play_encounter_to_completion

    play_encounter_to_completion(fire_sealed)
    fire_sealed.collect_victory_reward_and_advance()
    assert "chicote_de_chamas" not in fire_sealed.run.party[0].card_offer
    from wyrdfall.domain.cards import sealed_card_ids

    assert "chicote_de_chamas" in sealed_card_ids(fire_sealed.run.party[0], __import__("wyrdfall.domain.cards", fromlist=["CARD_DEFS"]).CARD_DEFS, fire_sealed.ruleset.abilities)
    for rerolls in range(6):
        fire_sealed.shop_state().rerolls = rerolls
        assert fire_sealed.shop_card() != "chicote_de_chamas"


def test_the_creation_flow_carries_element_seals_into_the_run(tmp_path, monkeypatch):
    monkeypatch.setattr("wyrdfall.persistence.store.save_db_path", lambda: tmp_path / "wyrdfall.db")
    from wyrdfall.app import WyrdfallApp

    run = WyrdfallApp().start_new_run(sealed_archetypes={Archetype.MISTICO}, sealed_elements={DamageElement.ICE}).get_run()
    assert run.party[0].sealed_archetypes == {Archetype.MISTICO}
    assert run.party[0].sealed_elements == {DamageElement.ICE}


# -- consumíveis em combate ----------------------------------------------------------------


def test_drinking_a_potion_mid_fight_heals_and_spends_the_turn():
    session = _session()
    session.run.consumables = ["pocao_de_vida", "tomo_do_guerreiro"]
    state = session.start_current_encounter()
    hero = state.combatants["hero"]
    max_hp = hero.computed_stats(session.ruleset).max_hp
    hero.current_hp = 1.0
    assert state.current_actor_id() == "hero"
    session.use_consumable("hero", "pocao_de_vida")
    assert hero.current_hp == pytest.approx(min(max_hp, 1.0 + 0.40 * max_hp))
    assert session.run.consumables == ["tomo_do_guerreiro"]
    assert state.current_actor_id() != "hero"  # the turn was spent
    assert state.used_heal_this_encounter  # counts as a heal for Contratos/unlocks
    assert any("usa Poção de Vida" in line for line in state.log)

    # not on someone else's turn, and never a Tomo
    with pytest.raises(Exception):
        session.use_consumable("hero", "tomo_do_guerreiro")
    state.turn_index = state.turn_order.index("hero")
    with pytest.raises(CombatError):
        session.use_consumable("hero", "tomo_do_guerreiro")
    assert "tomo_do_guerreiro" in session.run.consumables


# -- Abraçar a Morte -------------------------------------------------------------------------


def test_only_a_renascido_below_15_percent_can_embrace_death_once_and_it_wards_a_lethal_hit():
    human = _session(race_id="human").run.party[0]
    assert "abracar_a_morte" not in human.abilities

    session = _session(race_id="renascido")
    hero = session.run.party[0]
    assert "abracar_a_morte" in hero.abilities and "abracar_a_morte" not in hero.equipped_abilities  # universal
    state = session.start_current_encounter()
    hero = state.combatants["hero"]
    engine = session.combat_engine
    assert "abracar_a_morte" not in {a.id for a in engine.legal_abilities(state, "hero")}  # healthy
    max_hp_before = hero.computed_stats(session.ruleset).max_hp
    hero.current_hp = 0.10 * max_hp_before
    assert "abracar_a_morte" in {a.id for a in engine.legal_abilities(state, "hero")}

    session.submit_action(Action(actor_id="hero", ability_id="abracar_a_morte"))
    assert hero.death_ward_turns >= 1
    assert hero.computed_stats(session.ruleset).max_hp == pytest.approx(max_hp_before * 0.8)
    assert session.run.wyrd_meter == pytest.approx(WYRD_PER_EMBRACE)

    # a lethal hit stops at 1 HP while warded
    goblin = state.combatants["goblin_0"]
    goblin.base_stats.attack = 500
    state.turn_index = state.turn_order.index("goblin_0")
    engine.resolve_ai_turn(state)
    assert hero.is_alive and hero.current_hp == 1.0
    assert any("a morte espera" in line for line in state.log)

    # once per run, and the ward expires at the hero's next turn start
    assert hero.death_ward_turns == 0
    assert "abracar_a_morte" not in {a.id for a in engine.legal_abilities(state, "hero")}
    state.turn_index = state.turn_order.index("hero")
    with pytest.raises(CombatError):
        engine.resolve(state, Action(actor_id="hero", ability_id="abracar_a_morte"))

    # the max-HP price persists into the run after the fight
    hero.current_hp = 1.0
    goblin.current_hp = 0.0
    engine._check_victory(state)
    session.collect_victory_reward_and_advance()
    assert any(m.source == "death_ward" for m in session.run.party[0].permanent_modifiers)
