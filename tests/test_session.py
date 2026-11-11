import pytest

from wyrdfall.domain.attributes import Atributo
from wyrdfall.domain.combat import Action, ParryResult
from wyrdfall.domain.content import CLASS_DEFS, TALENT_TREES, build_ruleset
from wyrdfall.domain.dungeon import DungeonDef, EncounterDef
from wyrdfall.domain.economy import ecos_for_run
from wyrdfall.domain.factory import create_player_character
from wyrdfall.domain.run import RunState
from wyrdfall.engine.session import REST_HEAL_FRACTION, GameSession, SessionError
from wyrdfall.persistence.store import MetaProgressionState


def make_session(seed=1, starting_talent_points=1):
    ruleset = build_ruleset()
    class_def = CLASS_DEFS["runeguard"]
    tree = TALENT_TREES["runeguard_path"]
    hero = create_player_character(
        "hero", "Hero", class_def, tree, ruleset=ruleset, starting_talent_points=starting_talent_points
    )
    run = RunState(run_id="run1", seed=seed, dungeon_id="the_hollow_barrow", party=[hero])
    return GameSession(run, ruleset, {tree.definition.id: tree})


def play_encounter_to_completion(session, turn_limit=300):
    session.start_current_encounter()
    turns = 0
    while not session.encounter_is_over and turns < turn_limit:
        actor_id = session.combat_state.current_actor_id()
        if not session.combat_state.combatants[actor_id].acts_automatically:
            ability = session.combat_engine.legal_abilities(session.combat_state, actor_id)[0]
            targets = session.combat_engine.legal_target_ids(session.combat_state, actor_id, ability)
            target_ids = targets[:1] if ability.requires_target else []
            session.submit_action(Action(actor_id=actor_id, ability_id=ability.id, target_ids=target_ids))
        else:
            session.resolve_ai_turn()
        turns += 1
    assert turns < turn_limit


def test_allocate_talent_before_first_fight_spends_the_point():
    session = make_session()
    hero = session.run.party[0]
    assert hero.build.talent_tree.points_available == 1

    assert session.allocate_talent("hero", "r1") is True
    assert "r1" in hero.build.talent_tree.allocated
    assert hero.build.talent_tree.points_available == 0
    assert session.allocate_talent("hero", "d1") is False  # can't afford a second


def test_allocate_talent_rejects_illegal_nodes():
    session = make_session(starting_talent_points=5)
    # r3 requires r2, which requires r1 -- neither allocated yet
    assert session.allocate_talent("hero", "r3") is False


def test_winning_an_encounter_grants_currency_and_a_talent_point_and_advances():
    session = make_session(seed=123)
    hero = session.run.party[0]
    play_encounter_to_completion(session)
    assert session.encounter_victory is True

    reward = session.collect_victory_reward_and_advance()
    assert reward > 0
    assert session.run.currency_earned == reward
    assert session.run.encounter_index == 1
    assert hero.build.talent_tree.points_available == 1  # 0 spent + 1 granted for the win
    assert hero.statuses == []  # transient combat statuses don't carry over


def test_allocate_attribute_spends_a_point():
    session = make_session()
    hero = session.run.party[0]
    hero.attribute_points_available = 2

    assert session.allocate_attribute("hero", Atributo.STRENGTH) is True
    assert hero.attribute_points[Atributo.STRENGTH] == 1
    assert hero.attribute_points_available == 1

    assert session.allocate_attribute("hero", Atributo.STRENGTH) is True
    assert hero.attribute_points[Atributo.STRENGTH] == 2
    assert hero.attribute_points_available == 0

    assert session.allocate_attribute("hero", Atributo.STRENGTH) is False  # none left


def test_winning_first_encounter_grants_vigor_and_levels_up():
    session = make_session(seed=123)
    assert session.run.party[0].level == 1

    play_encounter_to_completion(session)
    session.collect_victory_reward_and_advance()

    # combat replaces run.party with fresh copies synced from combat_state
    # (see GameSession._sync_party_from_combat) -- re-fetch rather than
    # holding a reference from before the fight started.
    hero = session.run.party[0]
    # e1 is 2 goblins, 8 vigor each = 16; level 1->2 costs 15, leaving 1 over
    assert hero.level == 2
    assert hero.vigor == pytest.approx(1.0)
    assert hero.attribute_points_available == 2
    assert hero.build.talent_tree.points_available == 3  # 1 starting + 1 for the win + 1 for the level


def test_resolve_parry_response_applies_the_outcome_and_rejects_the_wrong_defender():
    session = make_session(seed=123)
    hero = session.run.party[0]
    hero.can_parry = True  # must be set before start_current_encounter deep-copies the party
    session.start_current_encounter()

    ability = session.combat_engine.legal_abilities(session.combat_state, "hero")[0]
    targets = session.combat_engine.legal_target_ids(session.combat_state, "hero", ability)
    session.submit_action(
        Action(actor_id="hero", ability_id=ability.id, target_ids=targets[:1] if ability.requires_target else [])
    )

    session.resolve_ai_turn()  # goblin's bite is melee -> pauses for parry instead of resolving
    assert session.combat_state.pending_parry is not None
    assert session.combat_state.pending_parry.defender_id == "hero"

    with pytest.raises(SessionError):
        session.resolve_parry_response("not-hero", ParryResult.DECLINED)

    log = session.resolve_parry_response("hero", ParryResult.DECLINED)
    assert session.combat_state.pending_parry is None
    assert log


def make_boss_only_session(seed=1) -> GameSession:
    """A minimal one-encounter dungeon marking its single fight as a boss,
    against a real but weak enemy (goblin) -- isolates the race-unlock
    wiring from needing to survive the full, escalating-difficulty MVP
    dungeon just to reach its actual boss."""
    ruleset = build_ruleset()
    class_def = CLASS_DEFS["runeguard"]
    tree = TALENT_TREES["runeguard_path"]
    hero = create_player_character("hero", "Hero", class_def, tree, ruleset=ruleset, starting_talent_points=0)
    dungeon = DungeonDef(
        id="test-boss-dungeon",
        name="Test",
        encounters=[EncounterDef(id="e1", name="Boss", enemy_ids=["goblin"], is_boss=True)],
    )
    run = RunState(run_id="run1", seed=seed, dungeon_id=dungeon.id, party=[hero])
    return GameSession(run, ruleset, {tree.definition.id: tree}, dungeon=dungeon)


def test_winning_the_boss_encounter_without_healing_makes_dwarf_eligible():
    session = make_boss_only_session()
    play_encounter_to_completion(session)
    assert session.encounter_victory is True

    session.collect_victory_reward_and_advance()

    assert session.run.bosses_defeated == 1
    # Runeguard's default kit (strike/guard/focus) has no heal ability --
    # nothing ever sets used_heal_this_encounter, so the condition holds.
    assert "dwarf" in session.newly_eligible_races


def test_dwarf_is_not_eligible_if_a_heal_was_used_during_the_boss_fight():
    session = make_boss_only_session()
    play_encounter_to_completion(session)
    assert session.encounter_victory is True

    # simulate a heal having been used at some point during the fight --
    # exercises the eligibility wiring without needing a heal ability on
    # the MVP kit specifically.
    session.combat_state.used_heal_this_encounter = True

    session.collect_victory_reward_and_advance()

    assert "dwarf" not in session.newly_eligible_races


def test_winning_a_boss_encounter_fully_heals_and_restores_resource():
    # docs/design/14-estrutura-da-run.md §6/§8 -- full heal only when a
    # run moves to its next Área (right after a boss falls).
    session = make_boss_only_session()
    play_encounter_to_completion(session)
    assert session.encounter_victory is True

    hero = session.run.party[0]
    hero.current_hp = 1.0
    hero.current_resource = 0.0

    session.collect_victory_reward_and_advance()

    hero = session.run.party[0]
    stats = hero.computed_stats(session.ruleset)
    assert hero.current_hp == stats.max_hp
    assert hero.current_resource == stats.max_resource


def test_winning_a_non_boss_encounter_does_not_heal():
    session = make_session(seed=123)  # e1 is 2 goblins, not a boss
    play_encounter_to_completion(session)
    assert session.encounter_victory is True

    hero = session.run.party[0]
    hero.current_hp = 1.0
    # high enough level that this encounter's vigor reward can't trigger a
    # level-up -- isolates the boss-only heal from apply_level_ups' own,
    # unrelated 25%-heal-on-level-up
    hero.level = 50

    session.collect_victory_reward_and_advance()

    hero = session.run.party[0]
    assert hero.current_hp == 1.0  # no auto-heal between combats inside an Área


def test_winning_a_boss_encounter_always_drops_an_item_and_material():
    session = make_boss_only_session()
    play_encounter_to_completion(session)
    assert session.encounter_victory is True

    session.collect_victory_reward_and_advance()

    assert len([p for p in session.run.equipment_instances.values() if not p.definition_id.startswith("basic_")]) == 1
    assert sum(session.run.materials.values()) == 2  # boss encounters grant 2 of one rarity


def test_winning_a_normal_encounter_can_add_to_inventory_and_materials():
    # seed=123 is the same fixed seed test_winning_an_encounter_grants_
    # currency_and_a_talent_point_and_advances already uses -- picked
    # here specifically because its own loot roll (a separate RNG stream,
    # see RunState.loot_rng) happens to succeed.
    session = make_session(seed=123)
    play_encounter_to_completion(session)
    assert session.encounter_victory is True

    session.collect_victory_reward_and_advance()

    assert len([p for p in session.run.equipment_instances.values() if not p.definition_id.startswith("basic_")]) == 1
    assert sum(session.run.materials.values()) == 1


def test_dwarf_is_not_eligible_on_a_non_boss_win():
    session = make_session(seed=123)
    play_encounter_to_completion(session)
    assert session.encounter_victory is True

    session.collect_victory_reward_and_advance()

    assert "dwarf" not in session.newly_eligible_races


def make_rest_session(seed=1) -> GameSession:
    """A rest node followed by one goblin fight -- isolates Sala de
    Descanso from needing to reach one inside the real dungeon."""
    ruleset = build_ruleset()
    class_def = CLASS_DEFS["runeguard"]
    tree = TALENT_TREES["runeguard_path"]
    hero = create_player_character("hero", "Hero", class_def, tree, ruleset=ruleset, starting_talent_points=0)
    dungeon = DungeonDef(
        id="test-rest-dungeon",
        name="Test",
        encounters=[
            EncounterDef(id="r1", name="Descanso", room_type="rest"),
            EncounterDef(id="e1", name="Fight", enemy_ids=["goblin"]),
        ],
    )
    run = RunState(run_id="run1", seed=seed, dungeon_id=dungeon.id, party=[hero])
    return GameSession(run, ruleset, {tree.definition.id: tree}, dungeon=dungeon)


def test_acampar_heals_a_fraction_of_max_hp_and_advances():
    session = make_rest_session()
    hero = session.run.party[0]
    max_hp = hero.computed_stats(session.ruleset).max_hp
    hero.current_hp = 1.0
    points_before = hero.build.talent_tree.points_available
    currency_before = session.run.currency_earned

    session.resolve_rest("acampar")

    assert hero.current_hp == pytest.approx(1.0 + REST_HEAL_FRACTION * max_hp)
    assert hero.build.talent_tree.points_available == points_before  # not a combat won
    assert session.run.currency_earned == currency_before
    assert session.run.encounter_index == 1


def test_acampar_never_heals_past_max_hp():
    session = make_rest_session()
    hero = session.run.party[0]
    max_hp = hero.computed_stats(session.ruleset).max_hp
    hero.current_hp = max_hp - 1.0

    session.resolve_rest("acampar")

    assert hero.current_hp == pytest.approx(max_hp)


def test_meditar_grants_a_talent_point_without_healing_and_advances():
    session = make_rest_session()
    hero = session.run.party[0]
    hero.current_hp = 1.0
    points_before = hero.build.talent_tree.points_available

    session.resolve_rest("meditar")

    assert hero.current_hp == 1.0
    assert hero.build.talent_tree.points_available == points_before + 1
    assert session.run.encounter_index == 1


def test_a_rest_node_cannot_be_entered_as_a_combat_and_a_combat_cannot_be_rested():
    session = make_rest_session()
    with pytest.raises(SessionError):
        session.start_current_encounter()

    session.resolve_rest("acampar")  # now on the goblin fight
    with pytest.raises(SessionError):
        session.resolve_rest("acampar")
    play_encounter_to_completion(session)  # the fight itself still works
    assert session.encounter_is_over


def test_running_the_dungeon_to_its_conclusion_produces_a_consistent_summary():
    session = make_session(seed=99, starting_talent_points=0)
    while not session.run_is_over:
        room_type = session.current_room_type
        if room_type == "rest":
            session.resolve_rest("acampar")
            continue
        if room_type == "event":
            session.resolve_event(session.current_event.options[-1].id)  # no event's last option has a cost
            continue
        if room_type in ("shop", "forge"):
            session.leave_node()
            continue
        play_encounter_to_completion(session)
        if session.encounter_victory:
            session.collect_victory_reward_and_advance()
        else:
            break

    assert session.run_is_over
    summary = session.finalize_run()
    ecos_earned = ecos_for_run(
        floors_completed=summary.floor_reached,
        bosses_defeated=session.run.bosses_defeated,
        fragments_remaining=session.run.currency_earned,
    )
    meta = MetaProgressionState()
    meta.record_run(summary, ecos_earned=ecos_earned)
    assert summary.victory == session.run_was_victorious
    assert meta.ecos == ecos_earned
    assert 0 <= summary.floor_reached <= 11
