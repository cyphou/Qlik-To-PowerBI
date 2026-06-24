"""Full lineage tracker — end-to-end provenance from Qlik to Power BI.

Extends the basic LineageMap with deep traversal that tracks every
transformation step: Qlik field → expression → DAX/M → TMDL column
→ visual binding.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger('qlik_to_powerbi.full_lineage')

__all__ = [
    'LineageNode', 'LineageEdge', 'FullLineageMap',
    'build_full_lineage', 'generate_lineage_html', '_kind_badge',
]


@dataclass
class LineageNode:
    """A node in the full lineage graph."""
    id: str
    kind: str  # 'qlik_field', 'qlik_measure', 'qlik_dimension', 'qlik_variable',
               # 'qlik_sheet', 'qlik_visual', 'qlik_association',
               # 'dax_measure', 'dax_column', 'm_query', 'tmdl_table',
               # 'tmdl_column', 'tmdl_measure', 'tmdl_relationship',
               # 'pbi_page', 'pbi_visual', 'pbi_filter'
    label: str = ''
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {'id': self.id, 'kind': self.kind, 'label': self.label or self.id}
        if self.metadata:
            d['metadata'] = self.metadata
        return d


@dataclass
class LineageEdge:
    """An edge in the lineage graph."""
    source: str
    target: str
    relation: str = 'transforms_to'  # 'transforms_to', 'binds_to', 'references', 'generates'
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {'source': self.source, 'target': self.target, 'relation': self.relation}
        if self.metadata:
            d['metadata'] = self.metadata
        return d


class FullLineageMap:
    """Full end-to-end lineage graph."""

    def __init__(self, app_name: str = ''):
        self.app_name = app_name
        self.nodes: Dict[str, LineageNode] = {}
        self.edges: List[LineageEdge] = []
        self.created_at = datetime.now().isoformat()

    def add_node(self, node_id: str, kind: str, label: str = '',
                 **metadata) -> LineageNode:
        node = LineageNode(id=node_id, kind=kind, label=label or node_id,
                          metadata=metadata)
        self.nodes[node_id] = node
        return node

    def add_edge(self, source: str, target: str,
                 relation: str = 'transforms_to', **metadata) -> LineageEdge:
        edge = LineageEdge(source=source, target=target,
                          relation=relation, metadata=metadata)
        self.edges.append(edge)
        return edge

    def get_ancestors(self, node_id: str) -> Set[str]:
        """Find all upstream ancestors of a node."""
        ancestors: Set[str] = set()
        queue = [node_id]
        while queue:
            current = queue.pop(0)
            for edge in self.edges:
                if edge.target == current and edge.source not in ancestors:
                    ancestors.add(edge.source)
                    queue.append(edge.source)
        return ancestors

    def get_descendants(self, node_id: str) -> Set[str]:
        """Find all downstream descendants of a node."""
        descendants: Set[str] = set()
        queue = [node_id]
        while queue:
            current = queue.pop(0)
            for edge in self.edges:
                if edge.source == current and edge.target not in descendants:
                    descendants.add(edge.target)
                    queue.append(edge.target)
        return descendants

    def get_orphans(self) -> List[str]:
        """Find nodes with no incoming or outgoing edges."""
        connected: Set[str] = set()
        for edge in self.edges:
            connected.add(edge.source)
            connected.add(edge.target)
        return [nid for nid in self.nodes if nid not in connected]

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    @property
    def edge_count(self) -> int:
        return len(self.edges)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'app_name': self.app_name,
            'created_at': self.created_at,
            'node_count': self.node_count,
            'edge_count': self.edge_count,
            'nodes': [n.to_dict() for n in self.nodes.values()],
            'edges': [e.to_dict() for e in self.edges],
        }

    def save(self, output_path: str) -> str:
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2)
        logger.info("Full lineage saved to %s (%d nodes, %d edges)",
                     output_path, self.node_count, self.edge_count)
        return output_path

    def to_mermaid(self, direction: str = 'LR', max_nodes: int = 120) -> str:
        """Generate a Mermaid flowchart string for this lineage graph.

        Args:
            direction: Mermaid graph direction — LR (default), TD, RL, or BT.
            max_nodes: Cap on nodes rendered to avoid browser freezes with huge
                       graphs (default 120). A comment is prepended when truncated.

        Returns:
            A Mermaid ``graph <direction>`` block as a string.
        """
        import re as _re

        _SHAPE: Dict[str, str] = {
            'qlik_field':        '["{label}"]',
            'qlik_measure':      '("{label}")',
            'qlik_dimension':    '("{label}")',
            'qlik_variable':     '(("{label}"))',
            'qlik_sheet':        '[/"{label}"/]',
            'qlik_visual':       '[/"{label}"/]',
            'qlik_association':  '["{label}"]',
            'dax_measure':       '{"{label}"}',
            'dax_column':        '{"{label}"}',
            'm_query':           '[("{label}")]',
            'tmdl_table':        '[["{label}"]]',
            'tmdl_column':       '["{label}"]',
            'tmdl_measure':      '{"{label}"}',
            'tmdl_relationship': '["{label}"]',
            'pbi_page':          '[/"{label}"/]',
            'pbi_visual':        '[/"{label}"/]',
            'pbi_filter':        '("{label}")',
        }
        _safe = _re.compile(r'[^\w]')

        def nid(raw: str) -> str:
            return 'N_' + _safe.sub('_', raw)[:40]

        nodes_list = list(self.nodes.values())
        truncated = len(nodes_list) > max_nodes
        visible: Set[str] = {n.id for n in nodes_list[:max_nodes]}

        lines: List[str] = []
        if truncated:
            lines.append(
                f'%% NOTE: Graph truncated to {max_nodes} of {len(self.nodes)} nodes'
            )
        lines.append(f'graph {direction}')

        for node in nodes_list[:max_nodes]:
            tmpl = _SHAPE.get(node.kind, '["{label}"]')
            label = (node.label or node.id).replace('"', "'")[:50]
            shape = tmpl.replace('{label}', label)
            lines.append(f'    {nid(node.id)}{shape}')

        _REL_ARROW: Dict[str, str] = {
            'transforms_to': '-->',
            'contains':      '--o',
            'binds_to':      '-. binds .->',
            'references':    '-. ref .->',
            'generates':     '==>',
        }
        for edge in self.edges:
            if edge.source not in visible or edge.target not in visible:
                continue
            arrow = _REL_ARROW.get(edge.relation, '-->')
            lines.append(
                f'    {nid(edge.source)} {arrow}|{edge.relation}| {nid(edge.target)}'
            )

        return '\n'.join(lines)


def build_full_lineage(app_name: str, qlik_data: Dict[str, Any],
                       calc_map: Optional[Dict[str, str]] = None,
                       model: Optional[Dict[str, Any]] = None,
                       report_state: Optional[Dict[str, Any]] = None) -> FullLineageMap:
    """Build full lineage from Qlik extraction through to PBI output.

    Args:
        app_name: Name of the Qlik app.
        qlik_data: Merged extraction data (11 JSON files).
        calc_map: Optional mapping of Qlik expression → DAX expression.
        model: Optional generated TMDL model dict.
        report_state: Optional generated report state dict.
    """
    lineage = FullLineageMap(app_name=app_name)
    calc_map = calc_map or {}

    # ── Qlik datasources → TMDL tables ──
    for ds in qlik_data.get('datasources', []):
        if not isinstance(ds, dict):
            continue
        ds_name = ds.get('name', '') or ds.get('connectionString', 'unknown')
        ds_id = f'qlik_ds_{ds_name}'
        lineage.add_node(ds_id, 'qlik_field', ds_name)

        for table in ds.get('tables', []):
            if not isinstance(table, dict):
                continue
            tname = table.get('name', '')
            t_id = f'qlik_table_{tname}'
            lineage.add_node(t_id, 'qlik_field', tname)
            lineage.add_edge(ds_id, t_id, 'contains')

            tmdl_id = f'tmdl_table_{tname}'
            lineage.add_node(tmdl_id, 'tmdl_table', tname)
            lineage.add_edge(t_id, tmdl_id, 'transforms_to')

            for col in table.get('columns', []):
                if not isinstance(col, dict):
                    continue
                cname = col.get('name', '')
                col_id = f'qlik_col_{tname}_{cname}'
                lineage.add_node(col_id, 'qlik_field', cname,
                                dataType=col.get('datatype', ''))
                lineage.add_edge(t_id, col_id, 'contains')

                tmdl_col_id = f'tmdl_col_{tname}_{cname}'
                lineage.add_node(tmdl_col_id, 'tmdl_column', cname)
                lineage.add_edge(col_id, tmdl_col_id, 'transforms_to')

    # ── Qlik measures → DAX measures ──
    for measure in qlik_data.get('measures', []):
        if not isinstance(measure, dict):
            continue
        mname = measure.get('name', '') or measure.get('title', '')
        m_id = f'qlik_measure_{mname}'
        qlik_expr = measure.get('expression', '') or measure.get('definition', '')
        lineage.add_node(m_id, 'qlik_measure', mname,
                        expression=qlik_expr[:200])

        dax_expr = calc_map.get(mname, '')
        if dax_expr:
            dax_id = f'dax_measure_{mname}'
            lineage.add_node(dax_id, 'dax_measure', mname,
                            expression=dax_expr[:200])
            lineage.add_edge(m_id, dax_id, 'transforms_to')

    # ── Qlik dimensions ──
    for dim in qlik_data.get('dimensions', []):
        if not isinstance(dim, dict):
            continue
        dname = dim.get('name', '') or dim.get('title', '')
        d_id = f'qlik_dim_{dname}'
        lineage.add_node(d_id, 'qlik_dimension', dname)

    # ── Qlik variables ──
    for var in qlik_data.get('variables', []):
        if not isinstance(var, dict):
            continue
        vname = var.get('name', '') or var.get('qName', '')
        v_id = f'qlik_var_{vname}'
        lineage.add_node(v_id, 'qlik_variable', vname,
                        definition=var.get('definition', '')[:200])

    # ── Qlik sheets → PBI pages ──
    sheets = qlik_data.get('sheets', [])
    for i, sheet in enumerate(sheets):
        if not isinstance(sheet, dict):
            continue
        sname = sheet.get('title', '') or sheet.get('name', '') or f'Sheet{i+1}'
        s_id = f'qlik_sheet_{sname}'
        lineage.add_node(s_id, 'qlik_sheet', sname)
        page_id = f'pbi_page_{sname}'
        lineage.add_node(page_id, 'pbi_page', sname)
        lineage.add_edge(s_id, page_id, 'transforms_to')

    # ── Qlik visualizations → PBI visuals ──
    for viz in qlik_data.get('visualizations', []):
        if not isinstance(viz, dict):
            continue
        vtype = viz.get('type', '') or viz.get('visualization', '')
        vid = viz.get('id', '') or viz.get('qInfo', {}).get('qId', '')
        viz_id = f'qlik_visual_{vid}'
        lineage.add_node(viz_id, 'qlik_visual', f'{vtype}:{vid}')
        pbi_viz_id = f'pbi_visual_{vid}'
        lineage.add_node(pbi_viz_id, 'pbi_visual', f'{vtype}:{vid}')
        lineage.add_edge(viz_id, pbi_viz_id, 'transforms_to')

    # ── Qlik associations → TMDL relationships ──
    for assoc in qlik_data.get('associations', []):
        if not isinstance(assoc, dict):
            continue
        aname = assoc.get('name', '') or f"{assoc.get('table1', '')}_{assoc.get('table2', '')}"
        a_id = f'qlik_assoc_{aname}'
        lineage.add_node(a_id, 'qlik_association', aname)
        rel_id = f'tmdl_rel_{aname}'
        lineage.add_node(rel_id, 'tmdl_relationship', aname)
        lineage.add_edge(a_id, rel_id, 'transforms_to')

    # ── Model-level nodes (if model provided) ──
    if model:
        for tbl in model.get('model', {}).get('tables', []) or []:
            tname = tbl.get('name', '')
            tmdl_id = f'tmdl_table_{tname}'
            if tmdl_id not in lineage.nodes:
                lineage.add_node(tmdl_id, 'tmdl_table', tname)
            for m in tbl.get('measures', []) or []:
                mname = m.get('name', '')
                mid = f'tmdl_measure_{tname}_{mname}'
                lineage.add_node(mid, 'tmdl_measure', mname,
                                expression=m.get('expression', '')[:200])
                lineage.add_edge(tmdl_id, mid, 'contains')
                # Link from DAX measure if exists
                dax_id = f'dax_measure_{mname}'
                if dax_id in lineage.nodes:
                    lineage.add_edge(dax_id, mid, 'generates')

    return lineage


def generate_lineage_html(lineage: FullLineageMap) -> str:
    """Generate an HTML visualization of the full end-to-end lineage graph.

    The report includes:
    - Summary stat cards (nodes, edges, orphans, node types)
    - Nodes-by-type breakdown table
    - Edges table (source → target with relation)
    - Orphan node list
    - Interactive Mermaid flow diagram (capped at 120 nodes)
    - Downloadable JSON lineage data
    """
    try:
        from powerbi_import.html_template import (
            html_open, html_close, section_open, section_close,
            data_table, stat_card, stat_grid, badge, esc,
        )
    except ImportError:
        from html_template import (
            html_open, html_close, section_open, section_close,
            data_table, stat_card, stat_grid, badge, esc,
        )
    import json as _json

    html = html_open(
        f'Full Lineage — {lineage.app_name}' if lineage.app_name else 'Full Lineage',
        subtitle=f'{lineage.node_count} nodes · {lineage.edge_count} edges',
    )

    # ── Summary cards ──────────────────────────────────────────
    kind_counts: Dict[str, int] = {}
    for node in lineage.nodes.values():
        kind_counts[node.kind] = kind_counts.get(node.kind, 0) + 1

    rel_counts: Dict[str, int] = {}
    for edge in lineage.edges:
        rel_counts[edge.relation] = rel_counts.get(edge.relation, 0) + 1

    orphans = lineage.get_orphans()
    cards = [
        {'value': lineage.node_count, 'label': 'Total Nodes'},
        {'value': lineage.edge_count, 'label': 'Total Edges'},
        {'value': len(orphans), 'label': 'Orphan Nodes'},
        {'value': len(kind_counts), 'label': 'Node Types'},
    ]
    html += stat_grid(cards)

    # ── Nodes by type ───────────────────────────────────────────
    html += section_open('Nodes by Type', 'Count of lineage nodes per kind')
    rows_types = [
        [badge(k, _kind_badge(k)), str(v)]
        for k, v in sorted(kind_counts.items(), key=lambda x: -x[1])
    ]
    html += data_table(['Kind', 'Count'], rows_types)
    html += section_close()

    # ── Edges table ─────────────────────────────────────────────
    html += section_open('Edges', f'All {lineage.edge_count} lineage edges')
    rows_edges = []
    _REL_BADGE: Dict[str, str] = {
        'transforms_to': 'pass',
        'contains':      'info',
        'binds_to':      'warn',
        'references':    '',
        'generates':     'pass',
    }
    for edge in lineage.edges:
        src_node = lineage.nodes.get(edge.source)
        tgt_node = lineage.nodes.get(edge.target)
        src_kind = src_node.kind if src_node else '?'
        tgt_kind = tgt_node.kind if tgt_node else '?'
        rows_edges.append([
            esc(edge.source),
            badge(src_kind, _kind_badge(src_kind)),
            badge(edge.relation, _REL_BADGE.get(edge.relation, '')),
            esc(edge.target),
            badge(tgt_kind, _kind_badge(tgt_kind)),
        ])
    html += data_table(
        ['Source', 'Source Kind', 'Relation', 'Target', 'Target Kind'],
        rows_edges,
    )
    html += section_close()

    # ── Orphan nodes ────────────────────────────────────────────
    if orphans:
        html += section_open(
            'Orphan Nodes',
            f'{len(orphans)} nodes with no edges — may indicate unmapped fields',
        )
        rows_orphans = []
        for oid in orphans[:100]:
            node = lineage.nodes[oid]
            rows_orphans.append([
                esc(node.id), badge(node.kind, _kind_badge(node.kind)), esc(node.label),
            ])
        html += data_table(['Node ID', 'Kind', 'Label'], rows_orphans)
        html += section_close()

    # ── Mermaid flow diagram ────────────────────────────────────
    mermaid_text = lineage.to_mermaid(direction='LR', max_nodes=120)
    node_cap = min(lineage.node_count, 120)
    html += section_open(
        'Flow Diagram',
        f'Visual lineage graph (showing up to 120 of {lineage.node_count} nodes)',
    )
    html += f'''<div class="mermaid-container" style="overflow:auto;max-height:600px">
<pre class="mermaid">
{mermaid_text}
</pre>
</div>
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<script>mermaid.initialize({{startOnLoad:true, maxTextSize:200000}});</script>
'''
    html += section_close()

    # ── Downloadable JSON data ──────────────────────────────────
    lineage_json = _json.dumps(lineage.to_dict(), indent=2)
    encoded = lineage_json.replace('</script>', '<\\/script>')
    html += section_open('Raw Data', 'Full lineage JSON for download/inspection')
    html += f'''<details><summary>Show JSON ({lineage.node_count} nodes, {lineage.edge_count} edges)</summary>
<pre style="max-height:400px;overflow:auto;font-size:12px">{esc(lineage_json[:8000])}{"..." if len(lineage_json) > 8000 else ""}</pre>
</details>\n'''
    html += section_close()

    html += html_close()
    return html


def _kind_badge(kind: str) -> str:
    """Return a CSS badge class for a lineage node kind."""
    _MAP: Dict[str, str] = {
        'qlik_field': 'warn',
        'qlik_measure': 'warn',
        'qlik_dimension': 'warn',
        'qlik_variable': 'warn',
        'qlik_sheet': 'warn',
        'qlik_visual': 'warn',
        'qlik_association': 'warn',
        'dax_measure': 'info',
        'dax_column': 'info',
        'm_query': 'info',
        'tmdl_table': 'pass',
        'tmdl_column': 'pass',
        'tmdl_measure': 'pass',
        'tmdl_relationship': 'pass',
        'pbi_page': '',
        'pbi_visual': '',
        'pbi_filter': '',
    }
    return _MAP.get(kind, '')
