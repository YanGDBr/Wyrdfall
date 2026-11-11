import pytest

from wyrdfall.domain.models import Modifier, ModifierKind, Stat
from wyrdfall.domain.talents import TalentNode, TalentTree, TalentTreeDef


def build_tree() -> TalentTree:
    nodes = [
        TalentNode(
            id="a",
            name="Rooted Strength",
            cost=1,
            modifiers=[Modifier(stat=Stat.ATTACK, kind=ModifierKind.FLAT, value=2, source="a")],
        ),
        TalentNode(
            id="b",
            name="Branching Power",
            cost=1,
            modifiers=[Modifier(stat=Stat.ATTACK, kind=ModifierKind.FLAT, value=3, source="b")],
        ),
        TalentNode(
            id="c",
            name="Keystone: Convergence",
            cost=2,
            is_keystone=True,
            require_all_prerequisites=True,
            modifiers=[Modifier(stat=Stat.CRIT_MULT, kind=ModifierKind.MORE, value=0.5, source="c")],
        ),
    ]
    edges = [("a", "b"), ("a", "c"), ("b", "c")]
    return TalentTree(TalentTreeDef(id="test-tree", name="Test Tree", nodes=nodes, edges=edges))


def test_root_node_is_allocatable_with_no_prerequisites():
    tree = build_tree()
    assert tree.can_allocate("a", allocated=set())
    assert not tree.can_allocate("b", allocated=set())
    assert not tree.can_allocate("c", allocated=set())


def test_single_prerequisite_unlocks_child():
    tree = build_tree()
    assert tree.can_allocate("b", allocated={"a"})


def test_keystone_requires_all_prerequisites():
    tree = build_tree()
    assert not tree.can_allocate("c", allocated={"a"})
    assert not tree.can_allocate("c", allocated={"b"})
    assert tree.can_allocate("c", allocated={"a", "b"})


def test_already_allocated_node_is_not_reallocatable():
    tree = build_tree()
    assert not tree.can_allocate("a", allocated={"a"})


def test_modifiers_and_points_spent_aggregate_across_allocated_nodes():
    tree = build_tree()
    allocated = {"a", "b"}
    mods = tree.modifiers_for(allocated)
    assert sum(m.value for m in mods if m.stat == Stat.ATTACK) == 5
    assert tree.points_spent(allocated) == 2


def test_cycle_detection_raises_on_construction():
    nodes = [TalentNode(id="x", name="X"), TalentNode(id="y", name="Y")]
    with pytest.raises(ValueError):
        TalentTree(TalentTreeDef(id="broken", name="Broken", nodes=nodes, edges=[("x", "y"), ("y", "x")]))
