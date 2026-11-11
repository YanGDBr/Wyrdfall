"""Fase 9 -- Companheiro/Familiar (docs/design/10-sistemas-de-build.md §8):
a slot of its own, a mini stat-block, on the party's side, driven by the
AI, persistent between combats, picked in the Guild."""

import pytest

from wyrdfall.domain.combat import Action
from wyrdfall.domain.companions import (
    COMPANION_DEFS,
    COMPANION_LEVEL_SCALING,
    COMPANION_REVIVE_FRACTION,
    build_companion,
)
from wyrdfall.domain.content import CLASS_DEFS, TALENT_TREES, build_ruleset
from wyrdfall.domain.dungeon import DungeonDef, EncounterDef
from wyrdfall.domain.factory import create_player_character
from wyrdfall.domain.run import RunState
from wyrdfall.engine.session import GameSession
from wyrdfall.persistence.store import MetaProgressionState
from tests.test_session import play_encounter_to_completion


def test_every_companion_has_real_abilities_that_never_feed_the_owners_affinity():
    ruleset = build_ruleset()
    for companion in COMPANION_DEFS.values():
        assert companion.cost > 0 and companion.name and companion.description
        assert companion.abilities
        for ability_id in companion.abilities:
            ability = ruleset.abilities[ability_id]
            assert ability.archetype_weight == {}, ability_id
            assert ability.resource_cost == 0  # companions have no Resolução pool


def test_build_companion_scales_with_the_owners_level_and_takes_its_own_slot():
    ruleset = build_ruleset()
    owner = create_player_character("hero", "Hero", CLASS_DEFS["runeguard"], TALENT_TREES["runeguard_path"], ruleset=ruleset)
    wolf_def = COMPANION_DEFS["lobo_cinzento"]
    wolf = build_companion(wolf_def, owner)
    assert wolf.id == "hero_companion" and wolf.owner_id == "hero"
    assert wolf.is_player and wolf.is_companion and wolf.acts_automatically
    assert wolf.base_stats.max_hp == wolf_def.base_stats.max_hp
    assert wolf.abilities == wolf.equipped_abilities == ["companion_bite"]
    assert owner.equipped_abilities and "companion_bite" not in owner.equipped_abilities  # never an Active Ability Slot

    owner.level = 6
    grown = build_companion(wolf_def, owner)
    assert grown.base_stats.max_hp == pytest.approx(wolf_def.base_stats.max_hp * (1 + COMPANION_LEVEL_SCALING * 5))
    assert grown.base_stats.attack == pytest.approx(wolf_def.base_stats.attack * (1 + COMPANION_LEVEL_SCALING * 5))


def test_meta_buys_once_and_picks_only_what_it_owns():
    meta = MetaProgressionState(ecos=100)
    assert meta.set_active_companion("lobo_cinzento") is False  # not owned
    assert meta.buy_companion("lobo_cinzento") is True
    assert meta.ecos == 100 - COMPANION_DEFS["lobo_cinzento"].cost
    assert meta.buy_companion("lobo_cinzento") is False
    assert meta.buy_companion("nao_existe") is False
    assert meta.set_active_companion("lobo_cinzento") is True
    assert meta.active_companion_id == "lobo_cinzento"
    assert meta.set_active_companion(None) is True and meta.active_companion_id is None
    assert MetaProgressionState(ecos=0).buy_companion("lobo_cinzento") is False


def _session_with(companion_id: str, encounters: list[EncounterDef], seed: int = 1) -> GameSession:
    ruleset = build_ruleset()
    class_def = CLASS_DEFS["runeguard"]
    tree = TALENT_TREES["runeguard_path"]
    hero = create_player_character("hero", "Hero", class_def, tree, ruleset=ruleset)
    dungeon = DungeonDef(id="t", name="t", encounters=encounters)
    run = RunState(run_id="r", seed=seed, dungeon_id="t", party=[hero], companions=[build_companion(COMPANION_DEFS[companion_id], hero)])
    return GameSession(run, ruleset, {tree.definition.id: tree}, dungeon=dungeon)


def test_a_companion_fights_on_the_party_side_acts_on_its_own_and_persists_between_combats():
    session = _session_with("lobo_cinzento", [
        EncounterDef(id="e1", name="a", enemy_ids=["goblin", "goblin"]),
        EncounterDef(id="e2", name="b", enemy_ids=["goblin"]),
    ])
    state = session.start_current_encounter()
    assert "hero_companion" in state.party_ids()
    assert state.combatants["hero_companion"].acts_automatically

    # drive the fight and watch the wolf take its own turns
    wolf_acted = False
    turns = 0
    while not session.encounter_is_over and turns < 200:
        actor_id = state.current_actor_id()
        if actor_id == "hero_companion":
            log = session.resolve_ai_turn()
            assert any("Lobo Cinzento usa Mordida" in line for line in log)
            wolf_acted = True
        elif state.combatants[actor_id].acts_automatically:
            session.resolve_ai_turn()
        else:
            ability = session.combat_engine.legal_abilities(state, actor_id)[0]
            targets = session.combat_engine.legal_target_ids(state, actor_id, ability)
            session.submit_action(Action(actor_id=actor_id, ability_id=ability.id, target_ids=targets[:1]))
        turns += 1
    assert wolf_acted and session.encounter_victory

    session.collect_victory_reward_and_advance()
    wolf = session.run.companions[0]
    assert session.run.party == [session.run.party[0]]  # never joined the party list
    wolf.current_hp = 0.5 * wolf.computed_stats(session.ruleset).max_hp  # hurt between fights
    state = session.start_current_encounter()
    wolf = state.combatants["hero_companion"]
    # persisted as a fraction, not healed -- the owner may have leveled
    # since, which rescales the mini stat-block without touching the ratio
    assert wolf.current_hp == pytest.approx(0.5 * wolf.computed_stats(session.ruleset).max_hp)


def test_a_downed_companion_returns_at_the_next_encounter_and_a_live_one_does_not_prevent_defeat():
    session = _session_with("corvo_do_wyrd", [
        EncounterDef(id="e1", name="a", enemy_ids=["goblin"]),
        EncounterDef(id="e2", name="b", enemy_ids=["goblin"]),
    ])
    state = session.start_current_encounter()
    crow = state.combatants["hero_companion"]
    crow.current_hp = 0.0  # fell mid-fight
    hero = state.combatants["hero"]
    hero.current_hp = 0.0
    session.combat_engine._check_victory(state)
    assert state.is_over and state.victory is False  # a live/dead companion never counts as "the party"

    # a fresh session: the crow died last fight, the party won anyway
    session = _session_with("corvo_do_wyrd", [
        EncounterDef(id="e1", name="a", enemy_ids=["goblin"]),
        EncounterDef(id="e2", name="b", enemy_ids=["goblin"]),
    ])
    play_encounter_to_completion(session)
    assert session.encounter_victory
    session.run.companions[0].current_hp = 0.0
    session.collect_victory_reward_and_advance()
    state = session.start_current_encounter()
    crow = state.combatants["hero_companion"]
    assert crow.is_alive
    assert crow.current_hp == pytest.approx(COMPANION_REVIVE_FRACTION * crow.computed_stats(session.ruleset).max_hp)


def test_rest_and_area_transition_heal_the_companion_too():
    session = _session_with("tartaruga_de_pedra", [
        EncounterDef(id="rest", name="r", room_type="rest"),
        EncounterDef(id="boss", name="b", enemy_ids=["goblin"], is_boss=True),
    ])
    turtle = session.run.companions[0]
    max_hp = turtle.computed_stats(session.ruleset).max_hp
    turtle.current_hp = 1.0
    session.resolve_rest("acampar")
    assert turtle.current_hp > 1.0

    turtle.current_hp = 2.0
    play_encounter_to_completion(session)
    assert session.encounter_victory
    session.collect_victory_reward_and_advance()
    assert session.run.companions[0].current_hp == pytest.approx(session.run.companions[0].computed_stats(session.ruleset).max_hp)
    assert session.run.companions[0].computed_stats(session.ruleset).max_hp >= max_hp


def test_start_new_run_attaches_the_guilds_active_companion(tmp_path, monkeypatch):
    monkeypatch.setattr("wyrdfall.persistence.store.save_db_path", lambda: tmp_path / "wyrdfall.db")
    from wyrdfall.app import WyrdfallApp

    app = WyrdfallApp()
    assert app.start_new_run().get_run().companions == []  # the slot is optional
    app.meta.ecos = 100
    app.meta.buy_companion("salamandra")
    app.meta.set_active_companion("salamandra")
    run = app.start_new_run().get_run()
    assert [c.class_id for c in run.companions] == ["salamandra"]
    assert run.companions[0].owner_id == run.party[0].id
