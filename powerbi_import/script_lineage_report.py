"""Script lineage report — HTML visualization of Qlik load script lineage.

Renders the ScriptLineageGraph as an interactive HTML report showing
source → table → derived table relationships.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Optional

from powerbi_import.script_lineage import ScriptLineageGraph

logger = logging.getLogger('qlik_to_powerbi.script_lineage_report')

__all__ = ['generate_script_lineage_html', 'generate_script_lineage_report']


def generate_script_lineage_html(graph: ScriptLineageGraph,
                                  app_name: str = '') -> str:
    """Generate an HTML report for a script lineage graph."""
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

    source_tables = graph.get_source_tables()
    derived_tables = graph.get_derived_tables()

    html = html_open(
        f'Script Lineage — {app_name}' if app_name else 'Script Lineage',
        subtitle=f'{graph.node_count} nodes, {graph.edge_count} edges',
    )

    # Summary cards
    cards = [
        {'value': graph.node_count, 'label': 'Total Nodes'},
        {'value': graph.edge_count, 'label': 'Total Edges'},
        {'value': len(source_tables), 'label': 'Source Tables'},
        {'value': len(derived_tables), 'label': 'Derived Tables'},
    ]
    html += stat_grid(cards)

    # Node types breakdown
    kind_counts: Dict[str, int] = {}
    for node in graph.nodes.values():
        kind_counts[node.kind] = kind_counts.get(node.kind, 0) + 1

    html += section_open('Node Types', 'Breakdown by node kind')
    headers_types = ['Kind', 'Count']
    rows_types = [[esc(k), str(v)] for k, v in sorted(kind_counts.items())]
    html += data_table(headers_types, rows_types)
    html += section_close()

    # Nodes table
    html += section_open('Nodes', 'All lineage nodes')
    headers_nodes = ['Name', 'Kind', 'Fields']
    rows_nodes = []
    for node in graph.nodes.values():
        kind_badge = {
            'source': 'warn',
            'table': 'pass',
            'inline': 'info',
            'mapping': 'info',
            'variable': '',
        }.get(node.kind, '')
        field_str = ', '.join(node.fields[:8])
        if len(node.fields) > 8:
            field_str += f' (+{len(node.fields) - 8} more)'
        rows_nodes.append([
            esc(node.name),
            badge(node.kind, kind_badge),
            esc(field_str),
        ])
    html += data_table(headers_nodes, rows_nodes)
    html += section_close()

    # Edges table
    html += section_open('Edges', 'Data flow relationships')
    headers_edges = ['Source', 'Target', 'Operation']
    rows_edges = []
    for edge in graph.edges:
        op_badge = {
            'load': 'pass',
            'resident': 'info',
            'join': 'warn',
            'concatenate': 'warn',
            'mapping': 'info',
            'store': '',
        }.get(edge.operation, '')
        rows_edges.append([
            esc(edge.source),
            esc(edge.target),
            badge(edge.operation, op_badge),
        ])
    html += data_table(headers_edges, rows_edges)
    html += section_close()

    # Mermaid diagram
    html += section_open('Flow Diagram', 'Visual lineage graph')
    mermaid_lines = ['graph LR']
    node_ids: Dict[str, str] = {}
    for i, name in enumerate(graph.nodes):
        nid = f'N{i}'
        node_ids[name] = nid
        kind = graph.nodes[name].kind
        shape = {
            'source': f'{nid}[("{esc(name)}")]',
            'table': f'{nid}["{esc(name)}"]',
            'inline': f'{nid}("{esc(name)}")',
            'mapping': f'{nid}{{"{esc(name)}"}}',
            'variable': f'{nid}(("{esc(name)}"))',
        }.get(kind, f'{nid}["{esc(name)}"]')
        mermaid_lines.append(f'    {shape}')

    for edge in graph.edges:
        src_id = node_ids.get(edge.source, '?')
        tgt_id = node_ids.get(edge.target, '?')
        if src_id != '?' and tgt_id != '?':
            label = edge.operation
            mermaid_lines.append(f'    {src_id} -->|{label}| {tgt_id}')

    mermaid_text = '\n'.join(mermaid_lines)
    html += f'''<div class="mermaid-container">
<pre class="mermaid">
{mermaid_text}
</pre>
</div>
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<script>mermaid.initialize({{startOnLoad:true}});</script>
'''
    html += section_close()

    html += html_close()
    return html


def generate_script_lineage_report(graph: ScriptLineageGraph,
                                    app_name: str = '',
                                    output_dir: str = '.') -> str:
    """Generate and save script lineage HTML report.

    Returns the path to the saved HTML file.
    """
    os.makedirs(output_dir, exist_ok=True)
    html = generate_script_lineage_html(graph, app_name)
    filename = f'{app_name or "script"}_lineage.html'
    filepath = os.path.join(output_dir, filename)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html)

    # Also save JSON
    json_path = os.path.join(output_dir, f'{app_name or "script"}_lineage.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(graph.to_dict(), f, indent=2)

    logger.info("Script lineage report saved to %s", filepath)
    return filepath
