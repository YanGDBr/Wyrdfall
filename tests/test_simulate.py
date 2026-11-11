"""The headless playtest bot (wyrdfall.tools.simulate) and the bug it
found on its first run: a fixed Especialização tree reached from another
base archetype (Afinidade drift) must keep the character's own nodes."""

import pytest

from wyrdfall.domain.content import CLASS_DEFS, TALENT_TREES, build_ruleset
from wyrdfall.domain.dungeon import DungeonDef, EncounterDef
from wyrdfall.domain.factory import create_player_character
from wyrdfall.domain.models import Archetype
from wyrdfall.domain.run import RunState
from wyrdfall.domain.specializations import SPECIALIZATION_DEFS, STAGE2_DEFS
from wyrdfall.engine.session import EVOLUTION_LEVEL, GameSession, _talent_tree_id_for
from wyrdfall.tools.simulate import RunReport, format_report, simulate_many, simulate_run


def test_a_seeded_run_is_deterministic_and_reports_where_it_ended():
    a = simulate_run("runeguard", seed=3)
    b = simulate_run("runeguard", seed=3)
    assert isinstance(a, RunReport)
    assert (a.victory, a.floor_reached, a.died_at, a.level, a.turns) == (b.victory, b.floor_reached, b.died_at, b.level, b.turns)
    assert 0 <= a.floor_reached <= a.total_floors
    assert a.victory == (a.died_at is None)


@pytest.mark.parametrize("class_id", list(CLASS_DEFS))
@pytest.mark.parametrize("race_id", ["human", "orc", "licantropo", "meio_celestial"])
def test_every_class_and_race_plays_a_whole_run_without_raising(class_id, race_id):
    report = simulate_run(class_id, race_id=race_id, seed=5)
    assert report.turns > 0 and report.level >= 1


def test_aggregates_format_into_a_table():
    aggregates = simulate_many(["runeguard"], ["human"], runs=2, seed=11)
    text = format_report(aggregates)
    assert "Guardião das Runas / Humano" in text and "/28" in text
    assert 0.0 <= aggregates[0].win_rate <= 1.0


def test_every_specialization_branch_exists_on_all_four_bases():
    # content/specializations.py::_rebase_fixed_trees -- the fix for the
    # KeyError the bot hit when a Patrulheiro drifted into Berserker
    for spec in [*SPECIALIZATION_DEFS.values(), *STAGE2_DEFS.values()]:
        if not (spec.hybrid_branch or spec.granted_tree_id):
            continue
        for base in ("guerreiro", "patrulheiro", "mistico", "guardiao"):
            assert f"{base}_{spec.id}_path" in TALENT_TREES, (spec.id, base)


def test_a_patrulheiro_that_drifted_into_berserker_keeps_its_own_nodes():
    ruleset = build_ruleset()
    class_def = CLASS_DEFS["patrulheiro"]
    tree = TALENT_TREES[class_def.talent_tree_id]
    hero = create_player_character("hero", "Hero", class_def, tree, ruleset=ruleset, starting_talent_points=3)
    dungeon = DungeonDef(id="t", name="t", encounters=[EncounterDef(id="e", name="e", enemy_ids=["goblin"])])
    session = GameSession(RunState(run_id="r", seed=1, dungeon_id="t", party=[hero]), ruleset, dict(TALENT_TREES), dungeon=dungeon)
    first = tree.allocatable_nodes(set())[0]
    assert session.allocate_talent("hero", first) is True
    hero.level = EVOLUTION_LEVEL
    hero.archetype_usage = {Archetype.GUERREIRO: 9.0, Archetype.PATRULHEIRO: 1.0}  # sword abilities all run
    assert session.evolve_specialization("hero", "berserker") is True
    assert _talent_tree_id_for(hero) == "patrulheiro_berserker_path"
    own_tree = TALENT_TREES["patrulheiro_berserker_path"]
    assert first in own_tree.nodes and "berserker_1" in own_tree.nodes
    assert session.allocate_talent("hero", "berserker_1") is True  # the branch is reachable
    assert first in hero.build.talent_tree.allocated  # nothing was lost
