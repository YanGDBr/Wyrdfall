from wyrdfall.domain.content import AREA_NAMES, MVP_DUNGEON, PORTAL_DEFS, build_dungeon_for_portal
from wyrdfall.domain.content.dungeon import AREA_ENCOUNTERS


def test_every_portal_path_only_uses_known_areas_and_ends_at_the_final_area():
    for portal in PORTAL_DEFS.values():
        assert all(area_id in AREA_NAMES for area_id in portal.path), portal.id
        assert portal.path[-1] == "the_unraveling_loom", portal.id


def test_the_four_base_portals_together_cover_every_non_final_area():
    non_final_areas = set(AREA_NAMES) - {"the_unraveling_loom"}
    base_portals = [p for p in PORTAL_DEFS.values() if p.unlock_condition is None]
    assert len(base_portals) == 4

    # every path also ends in the final Área, so "covered" is a superset,
    # not an exact match -- the claim is only that no non-final Área is left out
    covered = {area_id for portal in base_portals for area_id in portal.path}
    assert non_final_areas <= covered


def test_portao_submerso_is_locked_and_shorter_than_the_base_portals():
    submerso = PORTAL_DEFS["portao_submerso"]
    assert submerso.unlock_condition is not None
    base_portal_lengths = [len(p.path) for p in PORTAL_DEFS.values() if p.unlock_condition is None]
    assert len(submerso.path) < min(base_portal_lengths)


def test_area_encounters_partition_mvp_dungeon_by_area_id():
    assert sum(len(v) for v in AREA_ENCOUNTERS.values()) == len(MVP_DUNGEON.encounters)
    for area_id, encounters in AREA_ENCOUNTERS.items():
        assert all(e.area_id == area_id for e in encounters)


def test_build_dungeon_for_portal_concatenates_each_areas_encounters_in_path_order():
    dungeon = build_dungeon_for_portal("portao_do_gelo")
    portal = PORTAL_DEFS["portao_do_gelo"]
    expected = [e for area_id in portal.path for e in AREA_ENCOUNTERS[area_id]]
    assert dungeon.encounters == expected
    assert dungeon.id == "portao_do_gelo"
    # the boss of each Área along the path still ends that Área's stretch
    assert dungeon.encounters[-1].is_boss and dungeon.encounters[-1].area_id == "the_unraveling_loom"
