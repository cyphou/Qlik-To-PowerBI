"""
Lineage HTML embedding — integrate lineage visualization into migration reports.

Provides functions to embed interactive lineage diagrams into existing HTML reports,
and to generate standalone lineage visualization with vis.js for better interactivity.
"""

import json
from typing import Dict, List, Any, Optional

try:
    from powerbi_import.full_lineage import FullLineageMap, LineageNode, LineageEdge
except ImportError:
    from full_lineage import FullLineageMap, LineageNode, LineageEdge


def get_lineage_css() -> str:
    """Return CSS styles for lineage visualization."""
    return """
    .lineage-section {
        background: #fff; border-radius: 8px; padding: 20px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.12); margin-bottom: 24px;
    }
    .lineage-section h3 {
        margin-top: 0; color: #0078d4; font-size: 1.1em; margin-bottom: 12px;
    }
    .lineage-container {
        border: 1px solid #e0e0e0; border-radius: 6px;
        overflow: hidden; background: #f9f9f9; min-height: 500px;
    }
    .lineage-controls {
        padding: 12px; background: #f5f5f5; border-bottom: 1px solid #e0e0e0;
        display: flex; gap: 8px; align-items: center; flex-wrap: wrap;
    }
    .lineage-controls button {
        background: #0078d4; color: #fff; border: none;
        padding: 6px 12px; border-radius: 4px; cursor: pointer;
        font-size: 0.85em; font-weight: 500;
    }
    .lineage-controls button:hover { background: #004578; }
    .lineage-controls button.secondary {
        background: #e0e0e0; color: #333;
    }
    .lineage-controls button.secondary:hover { background: #d0d0d0; }
    .lineage-canvas {
        width: 100%; height: 600px; position: relative;
    }
    .lineage-legend {
        padding: 12px; background: #fafafa; border-top: 1px solid #e0e0e0;
        font-size: 0.85em; display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px;
    }
    .legend-item {
        display: flex; align-items: center; gap: 6px;
    }
    .legend-icon {
        width: 16px; height: 16px; border-radius: 50%; border: 2px solid #999;
    }
    .legend-icon.qlik { background: #ff9800; border-color: #f57c00; }
    .legend-icon.dax { background: #2196f3; border-color: #1565c0; }
    .legend-icon.tmdl { background: #4caf50; border-color: #388e3c; }
    .legend-icon.pbi { background: #9c27b0; border-color: #6a1b9a; }
    .lineage-stats {
        display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
        gap: 12px; padding: 12px; background: #fafafa;
        border-top: 1px solid #e0e0e0;
    }
    .lineage-stat {
        text-align: center;
    }
    .lineage-stat .value {
        font-size: 1.8em; font-weight: 700; color: #0078d4;
    }
    .lineage-stat .label {
        font-size: 0.85em; color: #666; margin-top: 4px;
    }
    .lineage-tooltip {
        background: #333; color: #fff; padding: 8px 12px;
        border-radius: 4px; font-size: 0.85em;
        position: absolute; pointer-events: none;
        box-shadow: 0 2px 8px rgba(0,0,0,0.2); z-index: 1000;
    }
    .lineage-edge-table {
        width: 100%; border-collapse: collapse; font-size: 0.85em;
    }
    .lineage-edge-table th, .lineage-edge-table td {
        border: 1px solid #e0e0e0; padding: 8px;
        text-align: left;
    }
    .lineage-edge-table th { background: #f5f5f5; font-weight: 600; }
    .lineage-edge-table tr:hover { background: #f9f9f9; }
    """


def get_lineage_javascript() -> str:
    """Return JavaScript for interactive lineage visualization."""
    return """
    <script src="https://cdnjs.cloudflare.com/ajax/libs/vis/4.21.0/vis.min.js"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/vis/4.21.0/vis.min.css" rel="stylesheet" />
    <script>
    function initLineageGraph(nodeData, edgeData, containerId) {
        // Convert data to vis.js format
        var nodes = new vis.DataSet(nodeData.map(function(n) {
            var colorMap = {
                'qlik_field': '#ff9800',
                'qlik_measure': '#ff9800',
                'qlik_dimension': '#ff9800',
                'qlik_sheet': '#ffb74d',
                'qlik_visual': '#ffb74d',
                'dax_measure': '#2196f3',
                'dax_column': '#64b5f6',
                'm_query': '#1976d2',
                'tmdl_table': '#4caf50',
                'tmdl_column': '#81c784',
                'tmdl_measure': '#66bb6a',
                'pbi_page': '#9c27b0',
                'pbi_visual': '#ba68c8',
            };
            var color = colorMap[n.kind] || '#999';
            return {
                id: n.id,
                label: n.label,
                title: n.id + ' (' + n.kind + ')',
                color: { background: color, border: color },
                shape: 'box',
                font: { size: 12 }
            };
        }));
        
        var edges = new vis.DataSet(edgeData.map(function(e) {
            return {
                from: e.source,
                to: e.target,
                label: e.relation,
                arrows: 'to',
                smooth: { type: 'continuous' }
            };
        }));
        
        var options = {
            physics: {
                enabled: true,
                stabilization: { iterations: 200 },
                barnesHut: { gravitationalConstant: -15000 }
            },
            interaction: { navigationButtons: true, keyboard: true },
            layout: { randomSeed: 42 }
        };
        
        var data = { nodes: nodes, edges: edges };
        var network = new vis.Network(document.getElementById(containerId), data, options);
        
        // Click handler for node details
        network.on('click', function(params) {
            if (params.nodes.length > 0) {
                var nodeId = params.nodes[0];
                var node = nodes.get(nodeId);
                alert('Node: ' + node.label + '\\nType: ' + node.title);
            }
        });
        
        return network;
    }
    </script>
    """


def generate_lineage_embed_html(lineage: FullLineageMap, title: str = "Data Lineage",
                               max_nodes: int = 200) -> str:
    """Generate interactive HTML for embedding lineage in reports.

    Args:
        lineage: FullLineageMap instance
        title: Section title
        max_nodes: Maximum nodes to render (large graphs may be slow)

    Returns:
        HTML string that can be embedded in reports
    """
    # Prepare data
    node_list = []
    for node_id, node in list(lineage.nodes.items())[:max_nodes]:
        node_list.append({
            'id': node_id,
            'label': node.label,
            'kind': node.kind,
            'title': node.label or node_id,
        })

    edge_list = []
    for edge in lineage.edges:
        if any(n['id'] == edge.source for n in node_list) and \
           any(n['id'] == edge.target for n in node_list):
            edge_list.append({
                'source': edge.source,
                'target': edge.target,
                'relation': edge.relation,
            })

    # Count by kind
    kind_counts = {}
    for node in node_list:
        kind_counts[node['kind']] = kind_counts.get(node['kind'], 0) + 1

    nodes_json = json.dumps(node_list)
    edges_json = json.dumps(edge_list)

    html = f'''<div class="lineage-section">
    <h3>📊 {title}</h3>
    
    <div class="lineage-stats">
        <div class="lineage-stat">
            <div class="value">{len(node_list)}</div>
            <div class="label">Nodes</div>
        </div>
        <div class="lineage-stat">
            <div class="value">{len(edge_list)}</div>
            <div class="label">Connections</div>
        </div>
        <div class="lineage-stat">
            <div class="value">{len(kind_counts)}</div>
            <div class="label">Types</div>
        </div>
    </div>

    <div class="lineage-container">
        <div class="lineage-controls">
            <button onclick="document.getElementById('lineage-canvas').style.display = 
                             document.getElementById('lineage-canvas').style.display === 'none' ? 'block' : 'none'">
                🔄 Toggle Graph
            </button>
            <button class="secondary" onclick="downloadLineageJSON()">📥 Export JSON</button>
        </div>
        <div id="lineage-canvas" class="lineage-canvas"></div>
        <div class="lineage-legend">
            <div style="grid-column: 1 / -1; font-weight: 600; padding-bottom: 8px; border-bottom: 1px solid #ccc;">
                Node Types:
            </div>
'''
    
    legend_items = {
        'qlik': ['qlik_field', 'qlik_measure', 'qlik_dimension', 'qlik_sheet', 'qlik_visual'],
        'dax': ['dax_measure', 'dax_column'],
        'tmdl': ['tmdl_table', 'tmdl_column', 'tmdl_measure'],
        'pbi': ['pbi_page', 'pbi_visual'],
    }
    
    for category, kinds in legend_items.items():
        for kind in kinds:
            if kind in kind_counts:
                html += f'''<div class="legend-item">
                    <div class="legend-icon {category}"></div>
                    <span>{kind.replace('_', ' ').title()} ({kind_counts[kind]})</span>
                </div>\n'''
    
    html += '''        </div>
    </div>
    
    <script>
    document.addEventListener('DOMContentLoaded', function() {
        var lineageNodes = ''' + nodes_json + ''';
        var lineageEdges = ''' + edges_json + ''';
        if (typeof initLineageGraph === 'function') {
            initLineageGraph(lineageNodes, lineageEdges, "lineage-canvas");
        } else {
            console.error("initLineageGraph function not found");
        }
    });
    
    function downloadLineageJSON() {
        var data = {
            nodes: lineageNodes,
            edges: lineageEdges
        };
        var dataStr = JSON.stringify(data, null, 2);
        var blob = new Blob([dataStr], {type: 'application/json'});
        var url = URL.createObjectURL(blob);
        var link = document.createElement('a');
        link.href = url;
        link.download = 'lineage.json';
        link.click();
    }
    </script>
</div>
'''
    return html


def inject_lineage_into_comparison_report(html_content: str, lineage: FullLineageMap,
                                         insert_after_section: str = "Converted Items") -> str:
    """Inject lineage visualization into an existing HTML report.

    Args:
        html_content: Existing HTML report
        lineage: FullLineageMap instance
        insert_after_section: Section heading to insert lineage after

    Returns:
        Modified HTML with lineage section injected
    """
    lineage_html = generate_lineage_embed_html(lineage, "End-to-End Data Lineage")
    
    # Try to find insertion point
    marker = f'<h2>{insert_after_section}</h2>'
    if marker in html_content:
        # Find the next closing section tag
        pos = html_content.find(marker)
        pos = html_content.find('</div>', pos) + 6  # Find next div close after heading
        html_content = html_content[:pos] + '\n' + lineage_html + '\n' + html_content[pos:]
    else:
        # Append before closing container
        if '</main>' in html_content:
            pos = html_content.find('</main>')
            html_content = html_content[:pos] + lineage_html + html_content[pos:]
        else:
            html_content = html_content.rstrip('</html>') + lineage_html + '</html>'
    
    return html_content


def add_lineage_section_to_report(base_html: str, lineage: FullLineageMap) -> str:
    """Add lineage CSS and JavaScript to the head/body of an HTML report.

    Args:
        base_html: Base HTML template
        lineage: FullLineageMap instance

    Returns:
        HTML with lineage resources injected
    """
    # Inject CSS into head
    css_inject = f'<style>\n{get_lineage_css()}\n</style>'
    if '</head>' in base_html:
        base_html = base_html.replace('</head>', css_inject + '\n</head>')
    
    # Inject JavaScript before closing body
    js_inject = f'\n{get_lineage_javascript()}'
    if '</body>' in base_html:
        base_html = base_html.replace('</body>', js_inject + '\n</body>')
    
    return base_html


def create_lineage_report_section(lineage: FullLineageMap, app_name: str = "Migration") -> str:
    """Create a complete lineage report section for standalone HTML.

    Args:
        lineage: FullLineageMap instance
        app_name: Application name

    Returns:
        Complete HTML section with lineage visualization
    """
    try:
        from powerbi_import.html_template import (
            html_open, html_close, section_open, section_close,
            data_table, esc, badge,
        )
    except ImportError:
        from html_template import (
            html_open, html_close, section_open, section_close,
            data_table, esc, badge,
        )

    html = f'{get_lineage_css()}\n{get_lineage_javascript()}\n'
    html += generate_lineage_embed_html(lineage, f"Data Lineage — {app_name}")
    
    # Add edges table
    html += section_open('Transformation Edges', f'{lineage.edge_count} data flow connections')
    rows = []
    for edge in lineage.edges[:100]:
        src_node = lineage.nodes.get(edge.source, None)
        tgt_node = lineage.nodes.get(edge.target, None)
        rows.append([
            esc(edge.source[:40]),
            esc(src_node.kind if src_node else '?'),
            edge.relation,
            esc(edge.target[:40]),
            esc(tgt_node.kind if tgt_node else '?'),
        ])
    html += data_table(
        ['Source ID', 'Source Type', 'Relation', 'Target ID', 'Target Type'],
        rows
    )
    if lineage.edge_count > 100:
        html += f'<p><em>Showing 100 of {lineage.edge_count} edges</em></p>'
    html += section_close()
    
    return html


__all__ = [
    'get_lineage_css',
    'get_lineage_javascript',
    'generate_lineage_embed_html',
    'inject_lineage_into_comparison_report',
    'add_lineage_section_to_report',
    'create_lineage_report_section',
]
