from wyrdfall.domain.dungeon import EncounterDef
from wyrdfall.domain.run import RunState
from wyrdfall.domain.special_rooms import resolved_room_type, special_room_type_for


def _run(seed: int, index: int = 0) -> RunState:
    return RunState(run_id="r", seed=seed, dungeon_id="d", party=[], encounter_index=index)


def test_the_draw_is_deterministic_per_seed_and_index_and_covers_all_three_types():
    assert special_room_type_for(_run(7, 3)) == special_room_type_for(_run(7, 3))
    drawn = {special_room_type_for(_run(seed, 3)) for seed in range(60)}
    assert drawn == {"forge", "rest", "shop"}
    # different nodes of the same run can draw different rooms
    assert len({special_room_type_for(_run(7, index)) for index in range(40)}) == 3


def test_resolved_room_type_only_resolves_special_nodes():
    run = _run(1)
    combat = EncounterDef(id="c", name="c", enemy_ids=["goblin"])
    event = EncounterDef(id="e", name="e", room_type="event")
    special = EncounterDef(id="s", name="s", room_type="special")
    assert resolved_room_type(run, combat) == "combat"
    assert resolved_room_type(run, event) == "event"
    assert resolved_room_type(run, special) in ("forge", "rest", "shop")
    assert resolved_room_type(run, special) == special_room_type_for(run)
