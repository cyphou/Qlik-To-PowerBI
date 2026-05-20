"""Dependency graph — data-lineage and cross-app dependency analysis.

Builds a directed graph of datasource → table → measure → visual dependencies
and detects cycles, orphans, and critical paths. Also supports cross-app
dependency tracking for portfolio migrations.
"""

from __future__ import annotations

import json
import logging
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


@dataclass
class Node:
    """Graph node representing a migration artifact."""
    id: str
    kind: str               # 'datasource', 'table', 'measure', 'visual', 'app'
    label: str = ''
    app_name: str = ''
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        return isinstance(other, Node) and self.id == other.id


@dataclass
class Edge:
    """Directed edge between two nodes."""
    source: str
    target: str
    relation: str = 'depends_on'

    def __hash__(self):
        return hash((self.source, self.target, self.relation))

    def __eq__(self, other):
        return (isinstance(other, Edge) and
                self.source == other.source and
                self.target == other.target and
                self.relation == other.relation)


class DependencyGraph:
    """Directed dependency graph for migration artifacts."""

    def __init__(self):
        self.nodes: Dict[str, Node] = {}
        self.edges: Set[Edge] = set()
        self._adj: Dict[str, Set[str]] = {}   # forward adjacency
        self._radj: Dict[str, Set[str]] = {}  # reverse adjacency

    def add_node(self, node_id: str, kind: str, label: str = '',
                 app_name: str = '', **metadata) -> Node:
        """Add a node to the graph."""
        if node_id in self.nodes:
            return self.nodes[node_id]
        node = Node(id=node_id, kind=kind, label=label or node_id,
                    app_name=app_name, metadata=metadata)
        self.nodes[node_id] = node
        self._adj.setdefault(node_id, set())
        self._radj.setdefault(node_id, set())
        return node

    def add_edge(self, source: str, target: str,
                 relation: str = 'depends_on') -> Edge:
        """Add a directed edge from source to target."""
        edge = Edge(source=source, target=target, relation=relation)
        self.edges.add(edge)
        self._adj.setdefault(source, set()).add(target)
        self._radj.setdefault(target, set()).add(source)
        return edge

    def successors(self, node_id: str) -> Set[str]:
        """Nodes that depend on this node."""
        return self._adj.get(node_id, set())

    def predecessors(self, node_id: str) -> Set[str]:
        """Nodes this node depends on."""
        return self._radj.get(node_id, set())

    def roots(self) -> List[str]:
        """Nodes with no incoming edges (datasources typically)."""
        return [n for n in self.nodes if not self._radj.get(n)]

    def leaves(self) -> List[str]:
        """Nodes with no outgoing edges (visuals typically)."""
        return [n for n in self.nodes if not self._adj.get(n)]

    def orphans(self) -> List[str]:
        """Nodes with no edges at all."""
        return [n for n in self.nodes
                if not self._adj.get(n) and not self._radj.get(n)]

    # ── Cycle detection ───────────────────────────────────────────

    def detect_cycles(self) -> List[List[str]]:
        """Find all cycles in the graph using DFS."""
        cycles: List[List[str]] = []
        visited: Set[str] = set()
        rec_stack: Set[str] = set()
        path: List[str] = []

        def dfs(node_id: str) -> None:
            visited.add(node_id)
            rec_stack.add(node_id)
            path.append(node_id)

            for neighbor in self._adj.get(node_id, set()):
                if neighbor not in visited:
                    dfs(neighbor)
                elif neighbor in rec_stack:
                    idx = path.index(neighbor)
                    cycle = path[idx:] + [neighbor]
                    cycles.append(cycle)

            path.pop()
            rec_stack.discard(node_id)

        for node_id in self.nodes:
            if node_id not in visited:
                dfs(node_id)

        return cycles

    # ── Topological sort ──────────────────────────────────────────

    def topological_sort(self) -> List[str]:
        """Kahn's algorithm — returns empty list if cycles exist."""
        in_degree = {n: 0 for n in self.nodes}
        for edge in self.edges:
            in_degree[edge.target] = in_degree.get(edge.target, 0) + 1

        queue = deque(n for n, d in in_degree.items() if d == 0)
        result: List[str] = []

        while queue:
            node = queue.popleft()
            result.append(node)
            for neighbor in self._adj.get(node, set()):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        return result if len(result) == len(self.nodes) else []

    # ── Critical path ─────────────────────────────────────────────

    def critical_path(self) -> List[str]:
        """Find the longest path (most dependency hops).

        Returns the list of node IDs on the critical path.
        """
        topo = self.topological_sort()
        if not topo:
            return []

        dist: Dict[str, int] = {n: 0 for n in topo}
        parent: Dict[str, Optional[str]] = {n: None for n in topo}

        for node in topo:
            for neighbor in self._adj.get(node, set()):
                if dist[node] + 1 > dist[neighbor]:
                    dist[neighbor] = dist[node] + 1
                    parent[neighbor] = node

        end = max(topo, key=lambda n: dist[n])
        path: List[str] = []
        current: Optional[str] = end
        while current is not None:
            path.append(current)
            current = parent[current]
        path.reverse()
        return path

    # ── Impact analysis ───────────────────────────────────────────

    def downstream_impact(self, node_id: str) -> Set[str]:
        """All nodes transitively downstream of a given node."""
        visited: Set[str] = set()
        queue = deque([node_id])
        while queue:
            current = queue.popleft()
            for neighbor in self._adj.get(current, set()):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
        return visited

    def upstream_deps(self, node_id: str) -> Set[str]:
        """All nodes transitively upstream of a given node."""
        visited: Set[str] = set()
        queue = deque([node_id])
        while queue:
            current = queue.popleft()
            for neighbor in self._radj.get(current, set()):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
        return visited

    # ── Build from extraction data ────────────────────────────────

    @classmethod
    def from_extraction(cls, extraction: Dict[str, Any],
                        app_name: str = '') -> 'DependencyGraph':
        """Build graph from Qlik extraction data.

        Expected keys: 'datasources', 'tables', 'measures', 'visuals'.
        """
        graph = cls()

        for ds in extraction.get('datasources', []):
            ds_id = f"ds:{ds.get('name', 'unknown')}"
            graph.add_node(ds_id, 'datasource',
                          label=ds.get('name', ''),
                          app_name=app_name)

        for tbl in extraction.get('tables', []):
            tbl_name = tbl.get('name', 'unknown')
            tbl_id = f"tbl:{tbl_name}"
            graph.add_node(tbl_id, 'table',
                          label=tbl_name,
                          app_name=app_name)

            ds_name = tbl.get('datasource', '')
            if ds_name:
                ds_id = f"ds:{ds_name}"
                if ds_id not in graph.nodes:
                    graph.add_node(ds_id, 'datasource',
                                  label=ds_name, app_name=app_name)
                graph.add_edge(ds_id, tbl_id, 'feeds')

        for msr in extraction.get('measures', []):
            msr_name = msr.get('name', 'unknown')
            msr_id = f"msr:{msr_name}"
            graph.add_node(msr_id, 'measure',
                          label=msr_name,
                          app_name=app_name)

            tbl_name = msr.get('table', '')
            if tbl_name:
                tbl_id = f"tbl:{tbl_name}"
                if tbl_id not in graph.nodes:
                    graph.add_node(tbl_id, 'table',
                                  label=tbl_name, app_name=app_name)
                graph.add_edge(tbl_id, msr_id, 'contains')

        for viz in extraction.get('visuals', []):
            viz_id = f"viz:{viz.get('id', viz.get('name', 'unknown'))}"
            graph.add_node(viz_id, 'visual',
                          label=viz.get('name', viz.get('type', '')),
                          app_name=app_name)

            for ref in viz.get('measures', []):
                msr_id = f"msr:{ref}"
                if msr_id in graph.nodes:
                    graph.add_edge(msr_id, viz_id, 'used_by')

            for ref in viz.get('fields', []):
                parts = ref.split('.', 1)
                if len(parts) == 2:
                    tbl_id = f"tbl:{parts[0]}"
                    if tbl_id in graph.nodes:
                        graph.add_edge(tbl_id, viz_id, 'used_by')

        return graph

    # ── Serialization ─────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        return {
            'node_count': len(self.nodes),
            'edge_count': len(self.edges),
            'nodes': [
                {'id': n.id, 'kind': n.kind, 'label': n.label,
                 'app_name': n.app_name}
                for n in self.nodes.values()
            ],
            'edges': [
                {'source': e.source, 'target': e.target,
                 'relation': e.relation}
                for e in self.edges
            ],
        }

    def to_mermaid(self) -> str:
        """Generate a Mermaid graph diagram."""
        lines = ['graph LR']
        for node in self.nodes.values():
            safe_label = node.label.replace('"', "'")
            lines.append(f'    {node.id}["{safe_label}"]')
        for edge in self.edges:
            lines.append(f'    {edge.source} -->|{edge.relation}| {edge.target}')
        return '\n'.join(lines)
