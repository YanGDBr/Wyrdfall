"""Talent tree build system, backed by networkx for prerequisite queries.

The MVP class uses this as its sole build system, but the data shape here
(nodes granting Modifiers/TriggeredEffects/abilities) is exactly the shape
relics, cards, and gear affixes will use later -- only the *allocation
rules* (a graph with prerequisites) are specific to talent trees.
"""

from __future__ import annotations

import networkx as nx
from pydantic import BaseModel, Field

from wyrdfall.domain.models import Modifier, TriggeredEffect


class TalentNode(BaseModel):
    id: str
    name: str
    description: str = ""
    cost: int = 1
    modifiers: list[Modifier] = Field(default_factory=list)
    triggered_effects: list[TriggeredEffect] = Field(default_factory=list)
    grants_ability: str | None = None
    is_keystone: bool = False
    require_all_prerequisites: bool = False


class TalentTreeDef(BaseModel):
    id: str
    name: str
    nodes: list[TalentNode]
    edges: list[tuple[str, str]] = Field(default_factory=list)  # (prerequisite_id, node_id)

    def node_map(self) -> dict[str, TalentNode]:
        return {node.id: node for node in self.nodes}

    def build_graph(self) -> nx.DiGraph:
        graph: nx.DiGraph = nx.DiGraph()
        for node in self.nodes:
            graph.add_node(node.id)
        for prerequisite_id, node_id in self.edges:
            graph.add_edge(prerequisite_id, node_id)
        return graph


class TalentTree:
    """Runtime wrapper: a :class:`TalentTreeDef` plus the networkx graph
    built from it, offering allocation-legality queries."""

    def __init__(self, definition: TalentTreeDef):
        self.definition = definition
        self.nodes = definition.node_map()
        self.graph = definition.build_graph()
        cycle = list(nx.simple_cycles(self.graph))
        if cycle:
            raise ValueError(f"Talent tree {definition.id!r} contains a cycle: {cycle[0]}")

    def can_allocate(self, node_id: str, allocated: set[str]) -> bool:
        if node_id not in self.nodes or node_id in allocated:
            return False
        prerequisites = list(self.graph.predecessors(node_id))
        if not prerequisites:
            return True
        node = self.nodes[node_id]
        if node.require_all_prerequisites:
            return all(p in allocated for p in prerequisites)
        return any(p in allocated for p in prerequisites)

    def allocatable_nodes(self, allocated: set[str]) -> list[str]:
        return [node_id for node_id in self.nodes if self.can_allocate(node_id, allocated)]

    def modifiers_for(self, allocated: set[str]) -> list[Modifier]:
        return [mod for node_id in allocated for mod in self.nodes[node_id].modifiers]

    def triggered_effects_for(self, allocated: set[str]) -> list[TriggeredEffect]:
        return [effect for node_id in allocated for effect in self.nodes[node_id].triggered_effects]

    def granted_abilities_for(self, allocated: set[str]) -> list[str]:
        return [
            self.nodes[node_id].grants_ability
            for node_id in allocated
            if self.nodes[node_id].grants_ability
        ]

    def points_spent(self, allocated: set[str]) -> int:
        return sum(self.nodes[node_id].cost for node_id in allocated if node_id in self.nodes)
