import pytest

from wyrdfall.domain.content import CLASS_DEFS, TALENT_TREES, build_ruleset
from wyrdfall.domain.dungeon import DungeonDef, EncounterDef
from wyrdfall.domain.events import EventDef, EventOptionDef
from wyrdfall.domain.factory import create_player_character
from wyrdfall.domain.run import RunState
from wyrdfall.domain.wyrd import ASCENSION_MAX, WYRD_MAX, add_wyrd, danger_multiplier, reward_multiplier
from wyrdfall.engine.session import GameSession
from tests.test_session import play_encounter_to_completion


def _run(**kw) -> RunState:
    return RunState(run_id="r", seed=1, dungeon_id="d", party=[], **kw)


def test_a_plain_run_has_neutral_multipliers():
    assert danger_multiplier(_run()) == pytest.approx(1.0)
    assert reward_multiplier(_run()) == pytest.approx(1.0)


def test_the_meter_raises_danger_and_reward_together_and_reward_more():
    half = _run(wyrd_meter=50.0)
    full = _run(wyrd_meter=WYRD_MAX)
    assert 1.0 < danger_multiplier(half) < danger_multiplier(full)
    assert 1.0 < reward_multiplier(half) < reward_multiplier(full)
    assert reward_multiplier(full) - 1.0 > danger_multiplier(full) - 1.0


def test_ascension_stacks_level_by_level():
    dangers = [danger_multiplier(_run(ascension_level=lv)) for lv in range(ASCENSION_MAX + 1)]
    rewards = [reward_multiplier(_run(ascension_level=lv)) for lv in range(ASCENSION_MAX + 1)]
    assert dangers == sorted(dangers) and len(set(dangers)) == ASCENSION_MAX + 1
    assert rewards == sorted(rewards) and rewards[-1] > dangers[-1]


def test_add_wyrd_clamps_to_the_range():
    run = _run(wyrd_meter=95.0)
    add_wyrd(run, 20.0)
    assert run.wyrd_meter == WYRD_MAX
    add_wyrd(run, -500.0)
    assert run.wyrd_meter == 0.0


def _event_session(option: EventOptionDef, monkeypatch) -> GameSession:
    ruleset = build_ruleset()
    class_def = CLASS_DEFS["runeguard"]
    tree = TALENT_TREES["runeguard_path"]
    hero = create_player_character("hero", "Hero", class_def, tree, ruleset=ruleset)
    dungeon = DungeonDef(id="t", name="t", encounters=[EncounterDef(id="ev", name="Evento", room_type="event")])
    pool = {"only": EventDef(id="only", name="Only", text="...", options=[option])}
    monkeypatch.setattr("wyrdfall.engine.session.EVENT_DEFS", pool)
    return GameSession(RunState(run_id="r", seed=1, dungeon_id="t", party=[hero]), ruleset, {tree.definition.id: tree}, dungeon=dungeon)


def test_a_risky_event_option_raises_the_meter_and_a_safe_one_does_not(monkeypatch):
    risky = _event_session(EventOptionDef(id="x", label="x", outcome_text="", damage_fraction=0.1, wyrd_risk=10.0), monkeypatch)
    risky.resolve_event("x")
    assert risky.run.wyrd_meter == 10.0

    safe = _event_session(EventOptionDef(id="y", label="y", outcome_text=""), monkeypatch)
    safe.resolve_event("y")
    assert safe.run.wyrd_meter == 0.0


def test_fragmentos_from_a_won_fight_are_scaled_by_the_reward_multiplier():
    ruleset = build_ruleset()
    class_def = CLASS_DEFS["runeguard"]
    tree = TALENT_TREES["runeguard_path"]

    def session() -> GameSession:
        hero = create_player_character("hero", "Hero", class_def, tree, ruleset=ruleset)
        dungeon = DungeonDef(id="t", name="t", encounters=[EncounterDef(id="e1", name="f", enemy_ids=["goblin"] * 4)])
        return GameSession(RunState(run_id="r", seed=1, dungeon_id="t", party=[hero]), ruleset, {tree.definition.id: tree}, dungeon=dungeon)

    plain = session()
    play_encounter_to_completion(plain)
    assert plain.encounter_victory is True
    base_reward = plain.collect_victory_reward_and_advance()

    boosted = session()
    play_encounter_to_completion(boosted)  # same fight, same seed -- same win
    assert boosted.encounter_victory is True
    # raise the run's risk only now, so the enemies fought were identical and
    # the only difference is the payout multiplier
    boosted.run.wyrd_meter = WYRD_MAX
    boosted.run.ascension_level = 2
    assert boosted.collect_victory_reward_and_advance() == round(base_reward * reward_multiplier(boosted.run))
    assert boosted.run.currency_earned > plain.run.currency_earned
