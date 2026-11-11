from tests.test_races import _make_combat_state
from tests.test_session import make_session
from wyrdfall.domain.dungeon import EncounterDef
from wyrdfall.domain.races import check_race_unlock
from wyrdfall.net.game_client import LocalGameClient
from wyrdfall.app import WyrdfallApp


def test_orc_only_unlocks_for_the_survivor_and_companions_do_not_count_as_players():
    state = _make_combat_state(party_ids=["hero", "friend"], enemy_ids=["g1", "g2", "g3"], alive_party_ids={"hero"})
    encounter = EncounterDef(id="group", name="Group")
    assert check_race_unlock("orc", encounter=encounter, combat_state=state, participant_id="hero")
    assert not check_race_unlock("orc", encounter=encounter, combat_state=state, participant_id="friend")
    state.combatants["friend"].is_companion = True
    assert not check_race_unlock("orc", encounter=encounter, combat_state=state, participant_id="hero")
    assert check_race_unlock("licantropo", encounter=encounter, combat_state=state, participant_id="hero")


def test_boss_conditions_belong_to_each_participant():
    state = _make_combat_state(party_ids=["hero", "friend"], enemy_ids=["boss"], alive_party_ids={"hero", "friend"})
    encounter = EncounterDef(id="boss", name="Boss", is_boss=True)
    state.used_heal_this_encounter = True
    state.healing_participants.add("friend")
    state.took_elemental_damage_this_encounter = True
    state.elemental_damage_recipients.add("hero")
    assert check_race_unlock("dwarf", encounter=encounter, combat_state=state, participant_id="hero")
    assert not check_race_unlock("dwarf", encounter=encounter, combat_state=state, participant_id="friend")
    assert check_race_unlock("elf", encounter=encounter, combat_state=state, participant_id="friend")
    assert not check_race_unlock("elf", encounter=encounter, combat_state=state, participant_id="hero")


def test_each_profile_receives_own_unlocks_and_collective_event_rewards(tmp_path, monkeypatch):
    session = make_session()
    session.run.party.append(session.run.party[0].model_copy(deep=True, update={"id": "friend", "class_id": "patrulheiro"}))
    session.run.race_unlocks_by_character = {"hero": {"orc"}, "friend": {"elf"}}
    session.run.race_unlocks = ["fada"]
    session.run.encounter_index = len(session.dungeon.encounters)
    summary = session.finalize_run()
    for character_id, expected, excluded, class_id in (("hero", "orc", "elf", "runeguard"), ("friend", "elf", "orc", "patrulheiro")):
        monkeypatch.setattr("wyrdfall.persistence.store.save_db_path", lambda cid=character_id: tmp_path / f"{cid}.db")
        app = WyrdfallApp()
        app.client = LocalGameClient(session, controlled_character_ids={character_id})
        app.client._last_summary = summary
        app.bank_run_reward()
        assert expected in app.meta.unlocked_races
        assert excluded not in app.meta.unlocked_races
        assert "fada" in app.meta.unlocked_races
        assert app.meta.run_history[-1].class_id == class_id
        balance = app.meta.ecos
        app.bank_run_reward()
        assert app.meta.ecos == balance


def test_lifesteal_is_recorded_as_healing_for_its_owner():
    import random
    from tests.test_combat import make_hero, make_goblin, make_ruleset
    from wyrdfall.domain.combat import CombatEngine, Action
    hero = make_hero()
    hero.current_hp = 20
    hero.base_stats.lifesteal_percent = 0.5
    engine = CombatEngine(make_ruleset(), random.Random(1))
    state = engine.start_encounter([hero], [make_goblin()])
    engine.resolve(state, Action(actor_id="hero", ability_id="strike", target_ids=["goblin"]))
    assert state.healing_participants == {"hero"}
    assert state.used_heal_this_encounter


def test_elemental_damage_is_recorded_only_for_the_recipient():
    import random
    from tests.test_combat import make_hero, make_goblin, make_ruleset
    from wyrdfall.domain.combat import CombatEngine, Action
    from wyrdfall.domain.abilities import Ability, TargetMode
    from wyrdfall.domain.models import Effect, EffectKind, DamageElement
    ruleset = make_ruleset()
    ruleset.abilities["bolt"] = Ability(id="bolt", name="Bolt", target_mode=TargetMode.SINGLE_ENEMY,
                                         effects=[Effect(kind=EffectKind.DAMAGE, amount=4, damage_element=DamageElement.FIRE)])
    enemy = make_goblin()
    enemy.abilities = ["bolt"]
    enemy.base_stats.speed = 20
    hero = make_hero()
    friend = hero.model_copy(deep=True, update={"id": "friend"})
    engine = CombatEngine(ruleset, random.Random(1))
    state = engine.start_encounter([hero, friend], [enemy])
    engine.resolve(state, Action(actor_id="goblin", ability_id="bolt", target_ids=["friend"]))
    assert state.elemental_damage_recipients == {"friend"}


def test_session_assigns_orc_before_reviving_the_downed_teammate():
    from wyrdfall.domain.dungeon import DungeonDef
    session = make_session()
    session.run.party.append(session.run.party[0].model_copy(deep=True, update={"id": "friend"}))
    session.dungeon = DungeonDef(id="group", name="Group", encounters=[
        EncounterDef(id="group", name="Group", enemy_ids=["goblin", "goblin", "goblin"]),
    ])
    state = session.start_current_encounter()
    state.combatants["friend"].current_hp = 0
    for enemy_id in state.enemy_ids():
        state.combatants[enemy_id].current_hp = 0
    state.is_over = state.victory = True
    session._sync_party_from_combat()
    session.collect_victory_reward_and_advance()
    assert "orc" in session.run.race_unlocks_by_character["hero"]
    assert "orc" not in session.run.race_unlocks_by_character["friend"]
    assert session.run.party[1].is_alive
