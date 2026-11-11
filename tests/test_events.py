import pytest

from wyrdfall.domain.content import CLASS_DEFS, EVENT_DEFS, TALENT_TREES, build_ruleset
from wyrdfall.domain.dungeon import DungeonDef, EncounterDef
from wyrdfall.domain.events import EventDef, EventOptionDef, event_for_node
from wyrdfall.domain.factory import create_player_character
from wyrdfall.domain.models import Archetype
from wyrdfall.domain.run import RunState
from wyrdfall.domain.specializations import SPECIALIZATION_DEFS, qualifies
from wyrdfall.engine.session import GameSession, SessionError


def make_event_session(class_id="runeguard", seed=1, currency=0) -> GameSession:
    """Two Evento nodes back to back (so a second choice is possible),
    then one goblin fight -- isolates events from the real dungeon."""
    ruleset = build_ruleset()
    class_def = CLASS_DEFS[class_id]
    tree = TALENT_TREES[class_def.talent_tree_id]
    hero = create_player_character("hero", "Hero", class_def, tree, ruleset=ruleset, starting_talent_points=0)
    dungeon = DungeonDef(
        id="test-event-dungeon",
        name="Test",
        encounters=[
            EncounterDef(id="ev1", name="Evento", room_type="event"),
            EncounterDef(id="ev2", name="Evento", room_type="event"),
            EncounterDef(id="e1", name="Fight", enemy_ids=["goblin"]),
        ],
    )
    run = RunState(run_id="run1", seed=seed, dungeon_id=dungeon.id, party=[hero], currency_earned=currency)
    return GameSession(run, ruleset, dict(TALENT_TREES), dungeon=dungeon)


# -- the pool ------------------------------------------------------------------


def test_every_event_has_at_least_two_options_with_unique_ids():
    for event in EVENT_DEFS.values():
        assert len(event.options) >= 2, event.id
        assert len({o.id for o in event.options}) == len(event.options), event.id
        assert event.text and event.name, event.id


def test_the_pool_covers_every_outcome_kind():
    options = [o for e in EVENT_DEFS.values() for o in e.options]
    assert any(o.alignment_shift > 0 for o in options)
    assert any(o.alignment_shift < 0 for o in options)
    assert any(o.heal_fraction > 0 for o in options)
    assert any(o.damage_fraction > 0 for o in options)
    assert any(o.currency_delta > 0 for o in options)
    assert any(o.currency_delta < 0 for o in options)
    assert any(o.talent_points > 0 for o in options)


def test_event_for_node_is_deterministic_per_seed_and_index_and_varies_across_indices():
    run = RunState(run_id="r", seed=7, dungeon_id="d", party=[])
    first = event_for_node(run, EVENT_DEFS)
    assert event_for_node(run, EVENT_DEFS) is first
    picks = set()
    for index in range(30):
        run.encounter_index = index
        picks.add(event_for_node(run, EVENT_DEFS).id)
    assert len(picks) > 1


# -- resolving -----------------------------------------------------------------


def _single_event_pool(option: EventOptionDef) -> dict[str, EventDef]:
    return {"only": EventDef(id="only", name="Only", text="...", options=[option, EventOptionDef(id="skip", label="s", outcome_text="")])}


def test_resolve_event_applies_alignment_heal_damage_talent_and_currency(monkeypatch):
    session = make_event_session(currency=5)
    hero = session.run.party[0]
    max_hp = hero.computed_stats(session.ruleset).max_hp
    hero.current_hp = max_hp / 2
    option = EventOptionDef(
        id="x", label="x", outcome_text="", alignment_shift=15.0, heal_fraction=0.25, currency_delta=8, talent_points=1,
    )
    monkeypatch.setattr("wyrdfall.engine.session.EVENT_DEFS", _single_event_pool(option))

    session.resolve_event("x")

    assert hero.alignment_score == 15.0
    assert hero.current_hp == pytest.approx(max_hp / 2 + 0.25 * max_hp)
    assert hero.build.talent_tree.points_available == 1
    assert session.run.currency_earned == 13
    assert session.run.encounter_index == 1


def test_resolve_event_never_kills_and_never_overheals(monkeypatch):
    session = make_event_session()
    hero = session.run.party[0]
    max_hp = hero.computed_stats(session.ruleset).max_hp
    hero.current_hp = 2.0
    monkeypatch.setattr(
        "wyrdfall.engine.session.EVENT_DEFS",
        _single_event_pool(EventOptionDef(id="hurt", label="h", outcome_text="", damage_fraction=0.9)),
    )
    session.resolve_event("hurt")
    assert hero.current_hp == 1.0

    hero.current_hp = max_hp - 1.0
    monkeypatch.setattr(
        "wyrdfall.engine.session.EVENT_DEFS",
        _single_event_pool(EventOptionDef(id="heal", label="h", outcome_text="", heal_fraction=0.9)),
    )
    session.resolve_event("heal")
    assert hero.current_hp == pytest.approx(max_hp)


def test_alignment_is_clamped_to_the_documented_range(monkeypatch):
    session = make_event_session()
    hero = session.run.party[0]
    hero.alignment_score = 95.0
    monkeypatch.setattr(
        "wyrdfall.engine.session.EVENT_DEFS",
        _single_event_pool(EventOptionDef(id="good", label="g", outcome_text="", alignment_shift=15.0)),
    )
    session.resolve_event("good")
    assert hero.alignment_score == 100.0


def test_an_unaffordable_cost_is_rejected_and_nothing_changes(monkeypatch):
    session = make_event_session(currency=3)
    hero = session.run.party[0]
    monkeypatch.setattr(
        "wyrdfall.engine.session.EVENT_DEFS",
        _single_event_pool(EventOptionDef(id="pay", label="p", outcome_text="", currency_delta=-10, talent_points=1)),
    )
    with pytest.raises(SessionError):
        session.resolve_event("pay")
    assert session.run.currency_earned == 3
    assert hero.build.talent_tree.points_available == 0
    assert session.run.encounter_index == 0


def test_unknown_option_and_non_event_node_are_rejected():
    session = make_event_session()
    with pytest.raises(SessionError):
        session.resolve_event("nao_existe")
    session.run.encounter_index = 2  # the goblin fight
    with pytest.raises(SessionError):
        session.resolve_event("poupar")
    with pytest.raises(SessionError):
        _ = session.current_event


def test_two_bondoso_choices_make_an_alignment_signature_reachable(monkeypatch):
    # docs/design/05-classes.md §4: Bondoso at >= +30, two +15 choices
    session = make_event_session(class_id="guardiao")
    hero = session.run.party[0]
    hero.level = 5
    hero.archetype_usage = {Archetype.GUARDIAO: 100.0}
    assert not qualifies(hero, SPECIALIZATION_DEFS["guardiao_da_floresta"])

    monkeypatch.setattr(
        "wyrdfall.engine.session.EVENT_DEFS",
        _single_event_pool(EventOptionDef(id="poupar", label="p", outcome_text="", alignment_shift=15.0)),
    )
    session.resolve_event("poupar")
    session.resolve_event("poupar")

    assert hero.alignment_score == 30.0
    assert qualifies(hero, SPECIALIZATION_DEFS["guardiao_da_floresta"])
