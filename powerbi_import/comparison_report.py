"""Side-by-side comparison report — Source vs. Power BI.

Generates an HTML report that shows each source worksheet alongside
the corresponding Power BI visual definition, highlighting:

* Visual type mapping
* DAX formula conversions
* Filter mapping
* Data model differences (columns, measures, relationships)

Usage::

    python -m powerbi_import.comparison_report \\
        qlik_export/ artifacts/powerbi_projects/MyProject/ \\
        --output comparison.html
"""

import json
import os
import html as html_mod
import argparse
import glob
import logging


# ────────────────────────────────────────────────────────
# CSS Theme
# ────────────────────────────────────────────────────────

_CSS = """
* { box-sizing: border-box; }
body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
       margin: 0; padding: 0; background: #f0f2f5; color: #333; }
header { background: linear-gradient(135deg, #1a237e 0%, #283593 100%);
         color: #fff; padding: 1.5rem 2rem; position: relative; }
header h1 { margin: 0; font-size: 1.5rem; }
header p { margin: 0.3rem 0 0; opacity: 0.85; font-size: 0.9rem; }
.container { max-width: 1400px; margin: 1rem auto; padding: 0 1rem; }
.summary { display: flex; gap: 1rem; margin-bottom: 1.5rem; flex-wrap: wrap; }
.card { background: #fff; border-radius: 8px; padding: 1rem 1.5rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.12); flex: 1; min-width: 200px; }
.card h3 { margin-top: 0; font-size: 0.85rem; color: #666; text-transform: uppercase; }
.card .val { font-size: 2rem; font-weight: 700; }
.comparison { background: #fff; border-radius: 8px; margin-bottom: 1rem;
              box-shadow: 0 1px 3px rgba(0,0,0,0.12); overflow: hidden; }
.comparison .row-header { background: #e8eaf6; padding: 0.75rem 1rem;
                          font-weight: 600; display: flex; justify-content: space-between; }
.comparison .row-header .badge { background: #4caf50; color: #fff; padding: 2px 8px;
                                  border-radius: 4px; font-size: 0.75rem; }
.comparison .row-header .badge.warn { background: #ff9800; }
.comparison .row-header .badge.fail { background: #f44336; }
.cols { display: grid; grid-template-columns: 1fr 1fr; }
.col { padding: 1rem; border-top: 1px solid #e0e0e0; }
.col:first-child { border-right: 1px solid #e0e0e0; }
.col h4 { margin: 0 0 0.5rem; color: #1a237e; font-size: 0.8rem; text-transform: uppercase; }
pre { background: #f5f5f5; padding: 0.5rem; border-radius: 4px; overflow-x: auto;
      font-size: 0.82rem; margin: 0.3rem 0; white-space: pre-wrap; }
.label { font-weight: 600; color: #555; font-size: 0.8rem; }
table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
th, td { border: 1px solid #e0e0e0; padding: 4px 8px; text-align: left; }
th { background: #fafafa; }
.pass { color: #4caf50; } .warn { color: #ff9800; } .fail { color: #f44336; }
.theme-toggle {
    position: absolute; top: 50%; right: 24px; transform: translateY(-50%);
    background: rgba(255,255,255,0.15); border: 1px solid rgba(255,255,255,0.25);
    color: #fff; border-radius: 20px; padding: 6px 14px; cursor: pointer;
    font-size: 0.82em; font-family: inherit; font-weight: 500;
    display: inline-flex; align-items: center; gap: 6px;
    transition: background 0.2s; backdrop-filter: blur(4px);
}
.theme-toggle:hover { background: rgba(255,255,255,0.25); }
.theme-toggle .theme-icon { font-size: 1.1em; line-height: 1; }
[data-theme="dark"] body { background: #1b1a19; color: #f3f2f1; }
[data-theme="dark"] header { background: linear-gradient(135deg, #0d1440 0%, #1a237e 100%); }
[data-theme="dark"] .card { background: #252423; box-shadow: 0 1px 3px rgba(0,0,0,0.4); }
[data-theme="dark"] .card h3 { color: #8a8886; }
[data-theme="dark"] .comparison { background: #252423; }
[data-theme="dark"] .comparison .row-header { background: #2d2d2d; }
[data-theme="dark"] .col { border-color: #3b3a39; }
[data-theme="dark"] .col h4 { color: #8ea0e0; }
[data-theme="dark"] pre { background: #2d2d2d; color: #d4d4d4; }
[data-theme="dark"] .label { color: #b3b0ad; }
[data-theme="dark"] table { background: #252423; }
[data-theme="dark"] th { background: #3b3a39; color: #f3f2f1; }
[data-theme="dark"] th, [data-theme="dark"] td { border-color: #3b3a39; color: #f3f2f1; }
[data-theme="dark"] h2 { color: #f3f2f1; }
@media print { .theme-toggle { display: none; } }
"""

_THEME_JS = """
<script>
(function() {
    var stored = localStorage.getItem('pbi-report-theme');
    if (stored) { document.documentElement.setAttribute('data-theme', stored); }
    else if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
        document.documentElement.setAttribute('data-theme', 'dark');
    }
})();
function toggleTheme() {
    var html = document.documentElement;
    var next = html.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
    html.setAttribute('data-theme', next);
    localStorage.setItem('pbi-report-theme', next);
    var btn = document.querySelector('.theme-toggle');
    if (btn) {
        btn.querySelector('.theme-icon').textContent = next === 'dark' ? '\\u2600' : '\\u263E';
        btn.querySelector('.theme-label').textContent = next === 'dark' ? 'Light' : 'Dark';
    }
}
document.addEventListener('DOMContentLoaded', function() {
    var theme = document.documentElement.getAttribute('data-theme') || 'light';
    var btn = document.querySelector('.theme-toggle');
    if (btn) {
        btn.querySelector('.theme-icon').textContent = theme === 'dark' ? '\\u2600' : '\\u263E';
        btn.querySelector('.theme-label').textContent = theme === 'dark' ? 'Light' : 'Dark';
    }
});
</script>
"""


# ────────────────────────────────────────────────────────
# Data loaders
# ────────────────────────────────────────────────────────

def _load_json(path):
    """Load a JSON file, returning empty dict/list on failure."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def _load_extracted(extract_dir):
    """Load all 16 extracted JSON files from the extraction directory."""
    data = {}
    names = [
        'worksheets', 'dashboards', 'datasources', 'calculations',
        'parameters', 'filters', 'stories', 'actions', 'sets', 'groups',
        'bins', 'hierarchies', 'sort_orders', 'aliases', 'custom_sql',
        'user_filters',
    ]
    for name in names:
        path = os.path.join(extract_dir, f'{name}.json')
        data[name] = _load_json(path)
    return data


def _load_pbip(pbip_dir):
    """Load Power BI project artifacts from a .pbip directory."""
    result = {'pages': [], 'model': {}, 'report': {}}
    # Find report.json
    for root, dirs, files in os.walk(pbip_dir):
        for f in files:
            full = os.path.join(root, f)
            if f == 'report.json':
                result['report'] = _load_json(full)
            elif f.endswith('.json') and 'page' in root.lower():
                result['pages'].append({'path': full, 'data': _load_json(full)})
            elif f.endswith('.json') and 'visual' in f.lower():
                result.setdefault('visuals', []).append(
                    {'path': full, 'data': _load_json(full)}
                )
    # Load migration report if present
    reports = glob.glob(os.path.join(pbip_dir, '..', 'migration_report_*.json'))
    if not reports:
        # Check new layout: reports/ sibling directory of migrated/
        reports = glob.glob(os.path.join(pbip_dir, '..', '..', 'reports', 'migration_report_*.json'))
    if reports:
        result['migration_report'] = _load_json(sorted(reports)[-1])
    return result


# ────────────────────────────────────────────────────────
# Comparison logic
# ────────────────────────────────────────────────────────

def _compare_worksheets(extracted, pbip_data):
    """Compare source worksheets to PBI pages/visuals."""
    comparisons = []
    worksheets = extracted.get('worksheets', [])
    if isinstance(worksheets, dict):
        worksheets = worksheets.get('worksheets', [])

    pbi_pages = pbip_data.get('pages', [])
    pbi_visuals = pbip_data.get('visuals', [])

    for ws in worksheets:
        name = ws.get('name', 'Unknown')
        tab_type = ws.get('mark_type', ws.get('mark_encoding', {}).get('type', 'auto'))
        tab_fields = ws.get('fields', [])
        tab_filters = ws.get('filters', [])

        # Try to find matching PBI visual
        pbi_match = None
        for v in (pbi_visuals or []):
            vdata = v.get('data', {})
            title = vdata.get('title', {}).get('text', '')
            if title and (name.lower() in title.lower() or title.lower() in name.lower()):
                pbi_match = vdata
                break

        comparisons.append({
            'name': name,
            'source': {
                'mark_type': tab_type,
                'field_count': len(tab_fields),
                'fields': tab_fields[:10],
                'filter_count': len(tab_filters),
            },
            'powerbi': {
                'visual_type': pbi_match.get('visualType', 'N/A') if pbi_match else 'N/A',
                'matched': pbi_match is not None,
            },
            'status': 'pass' if pbi_match else 'warn',
        })
    return comparisons


def _compare_calculations(extracted, pbip_data):
    """Compare source calculations to PBI DAX measures/columns."""
    calcs = extracted.get('calculations', [])
    if isinstance(calcs, dict):
        calcs = calcs.get('calculations', [])

    results = []
    for calc in calcs[:50]:  # Limit for report size
        name = calc.get('name', calc.get('caption', ''))
        formula = calc.get('formula', '')
        role = calc.get('role', '')
        results.append({
            'name': name,
            'source_formula': formula,
            'role': role,
        })
    return results


def _compare_datasources(extracted):
    """Summarize datasource comparison."""
    ds = extracted.get('datasources', [])
    if isinstance(ds, dict):
        ds = ds.get('datasources', [])
    summary = []
    for d in ds:
        name = d.get('name', d.get('caption', ''))
        conn = d.get('connection', {})
        tables = d.get('tables', [])
        summary.append({
            'name': name,
            'type': conn.get('class', conn.get('type', 'unknown')),
            'table_count': len(tables),
            'column_count': sum(len(t.get('columns', [])) for t in tables),
        })
    return summary


# ────────────────────────────────────────────────────────
# HTML generation
# ────────────────────────────────────────────────────────

def _esc(text):
    """HTML-escape text."""
    return html_mod.escape(str(text)) if text else ''


def generate_comparison_report(
    extract_dir,
    pbip_dir,
    output_path=None,
    include_lineage=True,
    source_app_path=None,
):
    """Generate an HTML comparison report.

    Args:
        extract_dir: Path to the qlik_export/ directory with JSON files.
        pbip_dir: Path to the generated .pbip project directory.
        output_path: Output HTML file path (default: comparison_report.html
                     in the pbip directory's parent).
        include_lineage: Whether to include lineage visualization (default: True).
        source_app_path: Optional path to the source app file (.json/.qvf/.qlik)
            to recover script lineage when extract_dir does not contain loadscript.json.

    Returns:
        str: Path to the generated HTML file.
    """
    extracted = _load_extracted(extract_dir)
    pbip_data = _load_pbip(pbip_dir)

    ws_compare = _compare_worksheets(extracted, pbip_data)
    calc_compare = _compare_calculations(extracted, pbip_data)
    ds_compare = _compare_datasources(extracted)
    migration_report = pbip_data.get('migration_report', {})

    # Counts
    ws_total = len(ws_compare)
    ws_matched = sum(1 for w in ws_compare if w['status'] == 'pass')
    calc_total = len(calc_compare)
    ds_total = len(ds_compare)

    if output_path is None:
        output_path = os.path.join(os.path.dirname(pbip_dir), 'comparison_report.html')

    parts = [f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Migration Comparison Report</title>
<style>{_CSS}</style>
"""]

    # Add lineage CSS if enabled
    if include_lineage:
        try:
            from powerbi_import.lineage_html_embed import get_lineage_css, get_lineage_javascript
        except ImportError:
            from lineage_html_embed import get_lineage_css, get_lineage_javascript
        parts.append(f'<style>\n{get_lineage_css()}\n</style>')
        parts.append('</head>')
    else:
        parts.append('</head>')

    parts.append("""
<body>
<header>
<h1>Qlik → Power BI — Side-by-Side Comparison</h1>
<p>Extract: """ + _esc(extract_dir) + """ | Project: """ + _esc(pbip_dir) + """</p>
<button class="theme-toggle" onclick="toggleTheme()" title="Toggle dark/light mode">
    <span class="theme-icon">&#9790;</span>
    <span class="theme-label">Dark</span>
</button>
</header>
<div class="container">
""")

    # Summary cards
    fidelity = migration_report.get('overall_fidelity', 'N/A')
    parts.append(f"""
<div class="summary">
  <div class="card"><h3>Worksheets</h3><div class="val">{ws_total}</div></div>
  <div class="card"><h3>Matched Visuals</h3><div class="val">{ws_matched}/{ws_total}</div></div>
  <div class="card"><h3>Calculations</h3><div class="val">{calc_total}</div></div>
  <div class="card"><h3>Datasources</h3><div class="val">{ds_total}</div></div>
  <div class="card"><h3>Fidelity</h3><div class="val">{_esc(str(fidelity))}</div></div>
</div>
""")

    # Add lineage visualization if enabled
    if include_lineage:
        try:
            from powerbi_import.lineage_html_embed import generate_lineage_embed_html, FullLineageMap
        except ImportError:
            from lineage_html_embed import generate_lineage_embed_html, FullLineageMap
        
        try:
            # Try to load existing lineage_map.json from the project output
            lineage_path = None
            lineage_data = None
            
            # Search for lineage_map.json in various locations
            import glob as glob_module
            
            # Priority 1: Direct sibling in pbip_dir
            candidate = os.path.join(pbip_dir, 'lineage_map.json')
            if os.path.exists(candidate):
                lineage_path = candidate
            
            # Priority 2: In pbip_dir parent
            if not lineage_path:
                for f in glob_module.glob(os.path.join(os.path.dirname(pbip_dir), '*.json')):
                    if 'lineage' in os.path.basename(f):
                        lineage_path = f
                        break
            
            # Priority 3: Recursive search in output directory
            if not lineage_path:
                for root, dirs, files in os.walk(os.path.dirname(os.path.dirname(pbip_dir))):
                    if 'lineage_map.json' in files:
                        lineage_path = os.path.join(root, 'lineage_map.json')
                        break
            
            if lineage_path and os.path.exists(lineage_path):
                try:
                    lineage_data = _load_json(lineage_path)
                except Exception as e:
                    lineage_data = None
            
            if lineage_data:
                # Build a FullLineageMap from the saved data
                lineage = FullLineageMap(app_name=lineage_data.get('app_name', 'Unknown'))
                
                # Handle both formats: full_lineage format (nodes/edges) and lineage_map format (entries)
                if 'nodes' in lineage_data and 'edges' in lineage_data:
                    # Full lineage format
                    for node in lineage_data.get('nodes', []):
                        lineage.add_node(
                            node.get('id', ''),
                            node.get('kind', ''),
                            node.get('label', ''),
                        )
                    
                    for edge in lineage_data.get('edges', []):
                        lineage.add_edge(
                            edge.get('source', ''),
                            edge.get('target', ''),
                            edge.get('relation', 'transforms_to')
                        )
                elif 'entries' in lineage_data:
                    # lineage_map format - convert entries to nodes/edges
                    seen_sources = set()
                    seen_targets = set()
                    
                    for entry in lineage_data.get('entries', []):
                        source_type = entry.get('source_type', '')
                        source_name = entry.get('source_name', '')
                        target_type = entry.get('target_type', '')
                        target_name = entry.get('target_name', '')
                        
                        # Create source node if not seen
                        source_id = f"{source_type}_{source_name}"
                        if source_id not in seen_sources and source_name:
                            lineage.add_node(source_id, f'qlik_{source_type}', source_name)
                            seen_sources.add(source_id)
                        
                        # Create target node if not seen
                        target_id = f"{target_type}_{target_name}"
                        if target_id not in seen_targets and target_name:
                            lineage.add_node(target_id, f'pbi_{target_type}', target_name)
                            seen_targets.add(target_id)
                        
                        # Create edge
                        if source_name and target_name:
                            lineage.add_edge(source_id, target_id, 'migrated_to')
                
                # Generate and add lineage section
                if lineage.node_count > 0:
                    lineage_html = generate_lineage_embed_html(lineage, "End-to-End Data Lineage")
                    parts.append(lineage_html)
        except Exception as e:
            # Silently skip lineage on error
            import traceback
            pass        
        # Add data prep lineage if enabled
        try:
            from powerbi_import.data_prep_lineage import (
                build_data_prep_lineage, generate_data_prep_lineage_html,
                parse_qlik_script_lineage, parse_m_query_lineage
            )
        except ImportError:
            from data_prep_lineage import (
                build_data_prep_lineage, generate_data_prep_lineage_html,
                parse_qlik_script_lineage, parse_m_query_lineage
            )
        
        try:
            data_prep_lineage = None
            
            # Try to build data prep lineage from extracted Qlik script
            loadscript_path = os.path.join(extract_dir, 'loadscript.json')
            if os.path.exists(loadscript_path):
                try:
                    loadscript_data = _load_json(loadscript_path)
                    script_content = loadscript_data.get('script', '')
                    if script_content:
                        data_prep_lineage = parse_qlik_script_lineage(script_content)
                except Exception as e:
                    logger.warning(f'Could not parse Qlik script lineage: {e}')

            # Fallback for JSON-input migrations where qlik_export/ does not
            # contain the current app's loadscript.json.
            if (not data_prep_lineage or data_prep_lineage.node_count == 0) and source_app_path:
                try:
                    src_ext = os.path.splitext(source_app_path)[1].lower()
                    if src_ext == '.json' and os.path.exists(source_app_path):
                        source_data = _load_json(source_app_path)
                        script_content = source_data.get('script', '')
                        if script_content:
                            data_prep_lineage = parse_qlik_script_lineage(script_content)
                except Exception as e:
                    logger.warning(f'Could not parse source app script lineage: {e}')
            
            # If no script lineage, try to build from M queries in PBIP
            if not data_prep_lineage or data_prep_lineage.node_count == 0:
                try:
                    data_prep_lineage = build_data_prep_lineage(extract_dir, pbip_dir)
                except Exception as e:
                    logger.warning(f'Could not build data prep lineage: {e}')
            
            # Add data prep lineage section if we have data
            if data_prep_lineage and data_prep_lineage.node_count > 0:
                data_prep_html = generate_data_prep_lineage_html(
                    data_prep_lineage,
                    title='Data Preparation Lineage'
                )
                parts.append(data_prep_html)
        except Exception as e:
            # Silently skip data prep lineage on error
            pass

    # ── Worksheet comparison ──
    parts.append('<h2>Worksheet → Visual Mapping</h2>')
    for ws in ws_compare:
        badge_cls = ws['status']
        badge_txt = 'Matched' if badge_cls == 'pass' else 'Unmatched'
        parts.append(f"""
<div class="comparison">
  <div class="row-header">
    <span>{_esc(ws['name'])}</span>
    <span class="badge {badge_cls}">{badge_txt}</span>
  </div>
  <div class="cols">
    <div class="col">
      <h4>Source</h4>
      <p><span class="label">Mark type:</span> {_esc(ws['source']['mark_type'])}</p>
      <p><span class="label">Fields:</span> {ws['source']['field_count']}</p>
      <p><span class="label">Filters:</span> {ws['source']['filter_count']}</p>
    </div>
    <div class="col">
      <h4>Power BI</h4>
      <p><span class="label">Visual type:</span> {_esc(ws['powerbi']['visual_type'])}</p>
    </div>
  </div>
</div>""")

    # ── Calculation comparison ──
    if calc_compare:
        parts.append('<h2>Calculation Conversions</h2>')
        parts.append('<table><tr><th>Name</th><th>Source Formula</th><th>Role</th></tr>')
        for c in calc_compare:
            parts.append(
                f"<tr><td>{_esc(c['name'])}</td>"
                f"<td><pre>{_esc(c['source_formula'])}</pre></td>"
                f"<td>{_esc(c['role'])}</td></tr>"
            )
        parts.append('</table>')

    # ── Datasource comparison ──
    if ds_compare:
        parts.append('<h2>Datasource Summary</h2>')
        parts.append('<table><tr><th>Name</th><th>Type</th><th>Tables</th><th>Columns</th></tr>')
        for d in ds_compare:
            parts.append(
                f"<tr><td>{_esc(d['name'])}</td><td>{_esc(d['type'])}</td>"
                f"<td>{d['table_count']}</td><td>{d['column_count']}</td></tr>"
            )
        parts.append('</table>')

    # ── Migration report items ──
    items = migration_report.get('items', [])
    if items:
        parts.append('<h2>Migration Item Status</h2>')
        parts.append('<table><tr><th>Item</th><th>Type</th><th>Status</th><th>Notes</th></tr>')
        for item in items[:100]:
            status = item.get('status', '')
            cls = 'pass' if status in ('migrated', 'converted') else 'warn' if status == 'partial' else 'fail'
            parts.append(
                f"<tr><td>{_esc(item.get('name', ''))}</td>"
                f"<td>{_esc(item.get('type', ''))}</td>"
                f"<td class=\"{cls}\">{_esc(status)}</td>"
                f"<td>{_esc(item.get('notes', ''))}</td></tr>"
            )
        parts.append('</table>')

    parts.append(_THEME_JS)
    
    # Add lineage JavaScript if enabled
    if include_lineage:
        try:
            from powerbi_import.lineage_html_embed import get_lineage_javascript
        except ImportError:
            from lineage_html_embed import get_lineage_javascript
        parts.append(get_lineage_javascript())
    
    parts.append('</div></body></html>')

    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(parts))
    print(f"  ✓ Comparison report: {output_path}")
    return output_path


# ────────────────────────────────────────────────────────
# CLI
# ────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='Generate a side-by-side Qlik vs Power BI comparison report'
    )
    parser.add_argument('extract_dir', help='Path to qlik_export/ directory')
    parser.add_argument('pbip_dir', help='Path to generated .pbip project directory')
    parser.add_argument(
        '--output', '-o', default=None,
        help='Output HTML file path (default: comparison_report.html in pbip parent)'
    )
    parser.add_argument(
        '--include-lineage', action='store_true', default=True,
        help='Include lineage visualization (default: True)'
    )
    parser.add_argument(
        '--no-lineage', action='store_false', dest='include_lineage',
        help='Exclude lineage visualization'
    )
    args = parser.parse_args()
    generate_comparison_report(args.extract_dir, args.pbip_dir, args.output, args.include_lineage)


if __name__ == '__main__':
    main()
