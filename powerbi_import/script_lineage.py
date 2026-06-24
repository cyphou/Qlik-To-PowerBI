"""Script lineage — parse Qlik load script into a lineage graph.

Analyzes LOAD/FROM/RESIDENT/JOIN/CONCATENATE/MAPPING/STORE statements
in a Qlik load script to build a data flow graph showing how tables
are derived from sources and each other.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger('qlik_to_powerbi.script_lineage')

__all__ = [
    'ScriptNode', 'ScriptEdge', 'ScriptLineageGraph',
    'parse_script_lineage',
]  # to_mermaid is a method on ScriptLineageGraph


@dataclass
class ScriptNode:
    """A node in the script lineage graph."""
    name: str
    kind: str  # 'table', 'source', 'inline', 'variable', 'mapping'
    fields: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {'name': self.name, 'kind': self.kind}
        if self.fields:
            d['fields'] = self.fields
        if self.metadata:
            d['metadata'] = self.metadata
        return d


@dataclass
class ScriptEdge:
    """An edge in the script lineage graph."""
    source: str
    target: str
    operation: str = 'load'  # 'load', 'resident', 'join', 'concatenate', 'mapping', 'store'
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            'source': self.source,
            'target': self.target,
            'operation': self.operation,
        }
        if self.metadata:
            d['metadata'] = self.metadata
        return d


class ScriptLineageGraph:
    """Lineage graph built from Qlik load script analysis."""

    def __init__(self):
        self.nodes: Dict[str, ScriptNode] = {}
        self.edges: List[ScriptEdge] = []

    def add_node(self, name: str, kind: str, fields: Optional[List[str]] = None,
                 **metadata) -> ScriptNode:
        node = ScriptNode(name=name, kind=kind, fields=fields or [],
                         metadata=metadata)
        self.nodes[name] = node
        return node

    def add_edge(self, source: str, target: str, operation: str = 'load',
                 **metadata) -> ScriptEdge:
        edge = ScriptEdge(source=source, target=target,
                         operation=operation, metadata=metadata)
        self.edges.append(edge)
        return edge

    def get_source_tables(self) -> List[str]:
        """Get tables that are only sources (no incoming edges)."""
        targets = {e.target for e in self.edges}
        sources = {e.source for e in self.edges}
        return [s for s in sources if s not in targets]

    def get_derived_tables(self) -> List[str]:
        """Get tables that have at least one incoming edge."""
        return list({e.target for e in self.edges})

    def get_ancestors(self, node_name: str) -> Set[str]:
        """Find all upstream ancestors of a node."""
        ancestors: Set[str] = set()
        queue = [node_name]
        while queue:
            current = queue.pop(0)
            for edge in self.edges:
                if edge.target == current and edge.source not in ancestors:
                    ancestors.add(edge.source)
                    queue.append(edge.source)
        return ancestors

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    @property
    def edge_count(self) -> int:
        return len(self.edges)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'node_count': self.node_count,
            'edge_count': self.edge_count,
            'source_tables': self.get_source_tables(),
            'derived_tables': self.get_derived_tables(),
            'nodes': [n.to_dict() for n in self.nodes.values()],
            'edges': [e.to_dict() for e in self.edges],
        }

    def to_mermaid(self, direction: str = 'LR') -> str:
        """Generate a Mermaid flowchart string for this lineage graph.

        Args:
            direction: Mermaid graph direction. One of LR, TD, RL, BT.

        Returns:
            A Mermaid ``graph <direction>`` block as a string.
        """
        _SHAPE: Dict[str, str] = {
            'source': '[("{}")] ',
            'table': '["{}"]	',
            'inline': '("{}")	',
            'mapping': '{{"{}"}}	',
            'variable': '(("{}"))',
        }
        _safe = re.compile(r'[^\w]')

        def node_id(name: str) -> str:
            return 'N_' + _safe.sub('_', name)[:30]

        lines = [f'graph {direction}']
        for name, node in self.nodes.items():
            nid = node_id(name)
            template = _SHAPE.get(node.kind, '["{}"]	')
            label = name.replace('"', "'")
            shape = template.format(label).strip()
            lines.append(f'    {nid}{shape}')

        _OP_ARROW: Dict[str, str] = {
            'load': '-->',
            'resident': '-. resident .->',
            'join': '==>',
            'concatenate': '--o',
            'mapping': '-. mapping .->',
            'store': '-.->',
        }
        for edge in self.edges:
            src = node_id(edge.source)
            tgt = node_id(edge.target)
            arrow = _OP_ARROW.get(edge.operation, '-->')
            lines.append(f'    {src} {arrow}|{edge.operation}| {tgt}')

        return '\n'.join(lines)


# ── Regex patterns for Qlik script parsing ──────────────────────

_TABLE_NAME_RE = re.compile(
    r'^\s*(?:\[([^\]]+)\]|(\w+))\s*:\s*$',
    re.MULTILINE,
)

_LOAD_FIELDS_RE = re.compile(
    r'\bLOAD\b\s+(.*?)(?:\bFROM\b|\bRESIDENT\b|\bINLINE\b|\bAUTOGENERATE\b|;)',
    re.IGNORECASE | re.DOTALL,
)

_FROM_RE = re.compile(
    r'\bFROM\b\s+(?:\[([^\]]+)\]|"([^"]+)"|(\S+))',
    re.IGNORECASE,
)

_RESIDENT_RE = re.compile(
    r'\bRESIDENT\b\s+(?:\[([^\]]+)\]|(\w+))',
    re.IGNORECASE,
)

_JOIN_RE = re.compile(
    r'\b((?:INNER|LEFT|RIGHT|OUTER|CROSS)?\s*JOIN)\b',
    re.IGNORECASE,
)

_CONCATENATE_RE = re.compile(
    r'\bCONCATENATE\b(?:\s*\(\s*(?:\[([^\]]+)\]|(\w+))\s*\))?',
    re.IGNORECASE,
)

_MAPPING_LOAD_RE = re.compile(
    r'\bMAPPING\s+LOAD\b',
    re.IGNORECASE,
)

_STORE_RE = re.compile(
    r'\bSTORE\b\s+(?:\[([^\]]+)\]|(\w+))\s+INTO\b\s+(?:\[([^\]]+)\]|"([^"]+)"|(\S+))',
    re.IGNORECASE,
)

_INLINE_RE = re.compile(
    r'\bINLINE\b\s*\[',
    re.IGNORECASE,
)

_LET_SET_RE = re.compile(
    r'^\s*(?:LET|SET)\s+(\w+)\s*=',
    re.IGNORECASE | re.MULTILINE,
)


def _extract_fields(field_str: str) -> List[str]:
    """Extract field names from a LOAD field list."""
    fields = []
    # Simplified: split on commas, strip AS aliases
    parts = field_str.split(',')
    for part in parts:
        part = part.strip()
        if not part or part == '*':
            if part == '*':
                fields.append('*')
            continue
        # Handle AS alias
        as_match = re.search(r'\bAS\b\s+(?:\[([^\]]+)\]|(\w+))', part, re.IGNORECASE)
        if as_match:
            name = as_match.group(1) or as_match.group(2) or ''
            if name:
                fields.append(name)
        else:
            # Use the last identifier
            bracket_match = re.findall(r'\[([^\]]+)\]', part)
            if bracket_match:
                fields.append(bracket_match[-1])
            else:
                # Simple field name
                clean = re.sub(r'\(.*?\)', '', part).strip()
                if clean and re.match(r'^[\w\s]+$', clean):
                    fields.append(clean.strip())
    return fields


def parse_script_lineage(script: str) -> ScriptLineageGraph:
    """Parse a Qlik load script and build a lineage graph.

    Args:
        script: The full Qlik load script text.

    Returns:
        A ScriptLineageGraph with nodes and edges.
    """
    graph = ScriptLineageGraph()

    if not script or not script.strip():
        return graph

    # Split into statements (rough: split on semicolons)
    statements = re.split(r';', script)

    current_table = ''
    is_join = False
    is_concatenate = False
    concat_target = ''

    for stmt in statements:
        stmt = stmt.strip()
        if not stmt:
            continue

        # Check for table label
        label_match = _TABLE_NAME_RE.search(stmt)
        if label_match:
            current_table = label_match.group(1) or label_match.group(2) or ''
            # Remove the label from the statement for further parsing
            stmt = _TABLE_NAME_RE.sub('', stmt, count=1).strip()

        # Check for CONCATENATE
        concat_match = _CONCATENATE_RE.search(stmt)
        if concat_match:
            is_concatenate = True
            concat_target = concat_match.group(1) or concat_match.group(2) or ''

        # Check for JOIN
        join_match = _JOIN_RE.search(stmt)
        if join_match:
            is_join = True

        # Check for MAPPING LOAD
        is_mapping = bool(_MAPPING_LOAD_RE.search(stmt))

        # Check for LET/SET variables
        var_match = _LET_SET_RE.search(stmt)
        if var_match:
            var_name = var_match.group(1)
            graph.add_node(var_name, 'variable')
            continue

        # Check for STORE
        store_match = _STORE_RE.search(stmt)
        if store_match:
            src = store_match.group(1) or store_match.group(2) or ''
            dest = store_match.group(3) or store_match.group(4) or store_match.group(5) or ''
            if src and dest:
                if dest not in graph.nodes:
                    graph.add_node(dest, 'source')
                graph.add_edge(src, dest, 'store')
            continue

        # Check for LOAD statement
        load_match = _LOAD_FIELDS_RE.search(stmt)
        if not load_match:
            continue

        field_str = load_match.group(1)
        fields = _extract_fields(field_str)

        table_name = current_table or f'Table_{graph.node_count + 1}'
        node_kind = 'mapping' if is_mapping else 'table'

        # Determine source
        from_match = _FROM_RE.search(stmt)
        resident_match = _RESIDENT_RE.search(stmt)
        inline_match = _INLINE_RE.search(stmt)

        if from_match:
            source_name = from_match.group(1) or from_match.group(2) or from_match.group(3) or ''
            if source_name:
                if source_name not in graph.nodes:
                    graph.add_node(source_name, 'source')
                if table_name not in graph.nodes:
                    graph.add_node(table_name, node_kind, fields=fields)
                operation = 'join' if is_join else 'concatenate' if is_concatenate else 'load'
                graph.add_edge(source_name, table_name, operation)

        elif resident_match:
            source_table = resident_match.group(1) or resident_match.group(2) or ''
            if source_table:
                if table_name not in graph.nodes:
                    graph.add_node(table_name, node_kind, fields=fields)
                operation = 'join' if is_join else 'concatenate' if is_concatenate else 'resident'
                graph.add_edge(source_table, table_name, operation)

        elif inline_match:
            if table_name not in graph.nodes:
                graph.add_node(table_name, 'inline', fields=fields)

        else:
            if table_name not in graph.nodes:
                graph.add_node(table_name, node_kind, fields=fields)

        # Handle CONCATENATE target linkage
        if is_concatenate and concat_target and concat_target != table_name:
            if concat_target not in graph.nodes:
                graph.add_node(concat_target, 'table')
            graph.add_edge(table_name, concat_target, 'concatenate')

        # Reset flags
        current_table = ''
        is_join = False
        is_concatenate = False
        concat_target = ''

    return graph
