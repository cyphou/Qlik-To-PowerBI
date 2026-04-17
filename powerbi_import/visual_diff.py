"""
Visual diff report generator.

Produces a side-by-side HTML report comparing Qlik visuals
(worksheets) against the generated Power BI visuals, highlighting:

* Visual type mappings and approximations
* Field assignment coverage (mapped vs. unmapped)
* Encoding gaps (color, size, tooltip, label, detail)
* Filter mapping completeness

Usage::

    from powerbi_import.visual_diff import generate_visual_diff
    path = generate_visual_diff(extracted_data, pbip_dir, output_path='diff.html')
"""

from __future__ import annotations

import glob
import json
import logging
import os
import html as html_mod
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    from powerbi_import.html_template import get_report_css, get_report_js
except ImportError:
    from html_template import get_report_css, get_report_js


# ── Visual type mapping (subset for display — full map in visual_generator) ──

_MARK_TO_PBI = {
    'bar': 'clusteredBarChart', 'stacked-bar': 'stackedBarChart',
    'line': 'lineChart', 'area': 'areaChart',
    'pie': 'pieChart', 'donut': 'donutChart',
    'circle': 'scatterChart', 'shape': 'scatterChart',
    'square': 'treemap', 'treemap': 'treemap',
    'text': 'tableEx', 'automatic': 'table',
    'map': 'map', 'polygon': 'filledMap',
    'gantt': 'clusteredBarChart', 'histogram': 'clusteredColumnChart',
    'scatter': 'scatterChart', 'bubble': 'scatterChart',
    'funnel': 'funnel', 'waterfall': 'waterfallChart',
    'heatmap': 'matrix', 'highlight-table': 'matrix',
    'box-and-whisker': 'boxAndWhisker', 'gauge': 'gauge',
    'kpi': 'card', 'card': 'card',
    'combo': 'lineClusteredColumnComboChart',
    'wordcloud': 'wordCloud',
}


# ── CSS Theme (matches comparison_report.py style) ──────────────

_CSS_EXTRA = """
/* visual-diff extras */
.diff { background: var(--surface); border-radius: 8px; margin-bottom: 1rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.12); overflow: hidden; }
.diff .row-header { background: var(--pbi-light-blue); padding: 0.75rem 1rem;
                    font-weight: 600; display: flex; justify-content: space-between;
                    align-items: center; }
.diff .row-header .badge { padding: 2px 8px; border-radius: 4px;
                           font-size: 0.75rem; color: #fff; }
.badge.exact { background: var(--success); }
.badge.approx { background: #ca5010; }
.badge.unmapped { background: var(--fail); }
.cols { display: grid; grid-template-columns: 1fr 1fr; }
.col { padding: 1rem; border-top: 1px solid #e0e0e0; }
.col:first-child { border-right: 1px solid #e0e0e0; }
.col h4 { margin: 0 0 0.5rem; color: var(--pbi-blue); font-size: 0.8rem; text-transform: uppercase; }
.field-list { list-style: none; padding: 0; margin: 0.3rem 0; }
.field-list li { padding: 2px 0; font-size: 0.85rem; }
.field-list li.mapped { color: var(--success); }
.field-list li.unmapped { color: var(--fail); }
.field-list li.approx { color: #ca5010; }
.label { font-weight: 600; color: #555; font-size: 0.8rem; }
.encoding-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
                 gap: 0.3rem; margin: 0.3rem 0; }
.enc-item { background: var(--pbi-bg); border-radius: 4px; padding: 4px 8px;
            font-size: 0.8rem; text-align: center; }
.enc-item.present { background: #dff6dd; color: var(--success); }
.enc-item.missing { background: #fde7e9; color: var(--fail); }
.summary { display: flex; gap: 1rem; margin-bottom: 1.5rem; flex-wrap: wrap; }
.summary .card { flex: 1; min-width: 180px; }
.card .val.pass { color: var(--success); }
.card .val.warn { color: #ca5010; }
.card .val.fail { color: var(--fail); }
/* dark mode overrides for visual-diff extras */
[data-theme="dark"] .diff { background: var(--pbi-surface); box-shadow: 0 1px 3px rgba(0,0,0,0.4); }
[data-theme="dark"] .diff .row-header { background: #1a3a5c; }
[data-theme="dark"] .col { border-color: #3b3a39; }
[data-theme="dark"] .label { color: #b3b0ad; }
[data-theme="dark"] .enc-item { background: #323130; color: #b3b0ad; }
[data-theme="dark"] .enc-item.present { background: #1a3a1a; color: #6ccb5f; }
[data-theme="dark"] .enc-item.missing { background: #4a1a1d; color: #f5707a; }
"""


def _esc(text):
    """HTML-escape text."""
    return html_mod.escape(str(text)) if text else ''


# ── Data loaders ────────────────────────────────────────────────

def _load_json(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def _load_pbi_visuals(pbip_dir: str) -> List[Dict]:
    """Load all visual.json files from a .pbip project."""
    visuals = []
    for root, dirs, files in os.walk(pbip_dir):
        for f in files:
            if f == 'visual.json':
                full = os.path.join(root, f)
                data = _load_json(full)
                if data:
                    visuals.append(data)
    return visuals


def _extract_pbi_visual_info(visual_json: Dict) -> Dict:
    """Extract key info from a PBI visual.json."""
    visual = visual_json.get('visual', visual_json.get('singleVisual', {}))
    visual_type = visual.get('visualType', 'unknown')
    title = ''

    # Try to get title
    title_obj = visual_json.get('title', {})
    if isinstance(title_obj, dict):
        title = title_obj.get('text', '')

    # Extract field references
    fields = []
    query = visual_json.get('query', visual.get('query', {}))
    if isinstance(query, dict):
        commands = query.get('Commands', [])
        for cmd in commands:
            if not isinstance(cmd, dict):
                continue
            sem_query = cmd.get('SemanticQueryDataShapeCommand', {})
            q = sem_query.get('Query', {})
            for section in ('Select', 'GroupBy', 'OrderBy'):
                items = q.get(section, [])
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    for ref_type in ('Column', 'Measure', 'Aggregation'):
                        ref = item.get(ref_type, {})
                        if isinstance(ref, dict):
                            expr = ref.get('Expression', {})
                            src = expr.get('SourceRef', {})
                            entity = src.get('Entity', '')
                            prop = ref.get('Property', '')
                            if entity and prop:
                                fields.append(f'{entity}[{prop}]')
                            # Aggregation wraps another expression
                            inner = ref.get('Expression', {})
                            if 'Column' in inner:
                                inner_col = inner['Column']
                                inner_src = inner_col.get('Expression', {}).get('SourceRef', {})
                                ie = inner_src.get('Entity', '')
                                ip = inner_col.get('Property', '')
                                if ie and ip:
                                    fields.append(f'{ie}[{ip}]')

    return {
        'visualType': visual_type,
        'title': title,
        'fields': fields,
    }


# ── Diff logic ──────────────────────────────────────────────────

_ENCODING_TYPES = ['color', 'size', 'shape', 'label', 'tooltip', 'detail', 'path']


def _diff_worksheet(ws: Dict, pbi_visuals: List[Dict]) -> Dict:
    """Compare a single Qlik worksheet against PBI visuals."""
    ws_name = ws.get('name', 'Unknown')
    mark_type = ws.get('mark_type', '')
    if isinstance(mark_type, dict):
        mark_type = mark_type.get('type', '')
    mark_type = str(mark_type).lower()

    # Qlik fields
    tab_fields = []
    for f in ws.get('fields', []):
        if isinstance(f, dict):
            tab_fields.append(f.get('name') or f.get('caption', ''))
        elif isinstance(f, str):
            tab_fields.append(f)
    tab_fields = [f for f in tab_fields if f]

    # Qlik encodings
    mark_enc = ws.get('mark_encoding', {})
    tab_encodings = {}
    for enc_type in _ENCODING_TYPES:
        val = mark_enc.get(enc_type)
        tab_encodings[enc_type] = val is not None and val != ''

    # Qlik filters
    tab_filters = ws.get('filters', [])

    # Expected PBI type
    expected_pbi = _MARK_TO_PBI.get(mark_type, 'tableEx')

    # Try to match with PBI visual
    pbi_match = None
    for v in pbi_visuals:
        info = _extract_pbi_visual_info(v)
        if info['title'] and ws_name.lower() in info['title'].lower():
            pbi_match = info
            break
        if info['visualType'] == expected_pbi:
            # Weak match by type
            if pbi_match is None:
                pbi_match = info

    # Classification
    if pbi_match:
        if pbi_match['visualType'] == expected_pbi:
            status = 'exact'
        else:
            status = 'approx'
    else:
        status = 'unmapped'

    # Field coverage
    pbi_fields = pbi_match['fields'] if pbi_match else []
    mapped_fields = []
    unmapped_fields = []
    for tf in tab_fields:
        clean = tf.strip('[]')
        found = any(clean.lower() in pf.lower() for pf in pbi_fields)
        if found:
            mapped_fields.append(tf)
        else:
            unmapped_fields.append(tf)

    return {
        'name': ws_name,
        'mark_type': mark_type,
        'expected_pbi_type': expected_pbi,
        'actual_pbi_type': pbi_match['visualType'] if pbi_match else None,
        'status': status,
        'Qlik_fields': tab_fields,
        'pbi_fields': pbi_fields,
        'mapped_fields': mapped_fields,
        'unmapped_fields': unmapped_fields,
        'field_coverage': (
            round(len(mapped_fields) / len(tab_fields) * 100)
            if tab_fields else 100
        ),
        'Qlik_encodings': tab_encodings,
        'Qlik_filter_count': len(tab_filters),
        'pbi_matched': pbi_match is not None,
    }


def generate_visual_diff(
    extracted_data: Dict,
    pbip_dir: str,
    output_path: Optional[str] = None,
) -> str:
    """Generate a visual diff HTML report.

    Args:
        extracted_data: Dict of extracted JSON objects from Qlik.
        pbip_dir: Path to the generated .pbip project directory.
        output_path: Output HTML file path (default: visual_diff.html
                     in the pbip directory's parent).

    Returns:
        Path to the generated HTML file.
    """
    worksheets = extracted_data.get('worksheets', [])
    if isinstance(worksheets, dict):
        worksheets = worksheets.get('worksheets', [])

    pbi_visuals = _load_pbi_visuals(pbip_dir)

    diffs = [_diff_worksheet(ws, pbi_visuals) for ws in worksheets]

    # Summary stats
    total = len(diffs)
    exact_count = sum(1 for d in diffs if d['status'] == 'exact')
    approx_count = sum(1 for d in diffs if d['status'] == 'approx')
    unmapped_count = sum(1 for d in diffs if d['status'] == 'unmapped')
    avg_coverage = (
        round(sum(d['field_coverage'] for d in diffs) / total)
        if total else 100
    )

    if output_path is None:
        output_path = os.path.join(
            os.path.dirname(pbip_dir), 'visual_diff.html'
        )

    # Build HTML
    parts = [f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Visual Diff Report</title>
<style>{get_report_css()}{_CSS_EXTRA}</style>
</head>
<body>
<div class="report-header">
<h1>Qlik &rarr; Power BI &mdash; Visual Diff Report</h1>
<p>Project: {_esc(pbip_dir)}</p>
<button class="theme-toggle" onclick="toggleTheme()" title="Toggle dark/light mode">
    <span class="theme-icon">&#9790;</span>
    <span class="theme-label">Dark</span>
</button>
</div>
<div class="container">
"""]

    # Summary cards
    cov_cls = 'pass' if avg_coverage >= 80 else ('warn' if avg_coverage >= 50 else 'fail')
    parts.append(f"""
<div class="summary">
  <div class="card"><h3>Total Visuals</h3><div class="val">{total}</div></div>
  <div class="card"><h3>Exact Match</h3><div class="val pass">{exact_count}</div></div>
  <div class="card"><h3>Approximate</h3><div class="val warn">{approx_count}</div></div>
  <div class="card"><h3>Unmapped</h3><div class="val fail">{unmapped_count}</div></div>
  <div class="card"><h3>Avg Field Coverage</h3><div class="val {cov_cls}">{avg_coverage}%</div></div>
</div>
""")

    # Per-visual diff cards
    for d in diffs:
        badge_cls = d['status']
        badge_map = {'exact': 'Exact Match', 'approx': 'Approximate', 'unmapped': 'Unmapped'}
        badge_txt = badge_map.get(badge_cls, badge_cls)

        # Encoding status
        enc_html = '<div class="encoding-grid">'
        for enc_type, present in d['Qlik_encodings'].items():
            cls = 'present' if present else 'missing'
            enc_html += f'<div class="enc-item {cls}">{_esc(enc_type)}</div>'
        enc_html += '</div>'

        # Field lists
        mapped_html = ''.join(
            f'<li class="mapped">✓ {_esc(f)}</li>' for f in d['mapped_fields']
        )
        unmapped_html = ''.join(
            f'<li class="unmapped">✗ {_esc(f)}</li>' for f in d['unmapped_fields']
        )
        pbi_fields_html = ''.join(
            f'<li>{_esc(f)}</li>' for f in d['pbi_fields'][:15]
        )

        parts.append(f"""
<div class="diff">
  <div class="row-header">
    <span>{_esc(d['name'])}</span>
    <span class="badge {badge_cls}">{badge_txt} — {d['field_coverage']}% field coverage</span>
  </div>
  <div class="cols">
    <div class="col">
      <h4>Qlik</h4>
      <p><span class="label">Mark type:</span> {_esc(d['mark_type']) or 'auto'}</p>
      <p><span class="label">Expected PBI type:</span> {_esc(d['expected_pbi_type'])}</p>
      <p><span class="label">Fields ({len(d['Qlik_fields'])}):</span></p>
      <ul class="field-list">{mapped_html}{unmapped_html}</ul>
      <p><span class="label">Encodings:</span></p>
      {enc_html}
      <p><span class="label">Filters:</span> {d['Qlik_filter_count']}</p>
    </div>
    <div class="col">
      <h4>Power BI</h4>
      <p><span class="label">Visual type:</span> {_esc(d['actual_pbi_type'] or 'N/A')}</p>
      <p><span class="label">Fields ({len(d['pbi_fields'])}):</span></p>
      <ul class="field-list">{pbi_fields_html}</ul>
    </div>
  </div>
</div>""")

    # Summary table
    parts.append('<h2>Summary Table</h2>')
    parts.append(
        '<table><tr><th>Worksheet</th><th>Qlik Mark</th>'
        '<th>Expected PBI</th><th>Actual PBI</th>'
        '<th>Status</th><th>Field Coverage</th></tr>'
    )
    for d in diffs:
        st_cls = d['status']
        parts.append(
            f"<tr><td>{_esc(d['name'])}</td>"
            f"<td>{_esc(d['mark_type'])}</td>"
            f"<td>{_esc(d['expected_pbi_type'])}</td>"
            f"<td>{_esc(d['actual_pbi_type'] or 'N/A')}</td>"
            f'<td class="{st_cls}">{_esc(d["status"])}</td>'
            f"<td>{d['field_coverage']}%</td></tr>"
        )
    parts.append('</table>')

    parts.append(f"""</div><script>{get_report_js()}
(function() {{
    var theme = document.documentElement.getAttribute('data-theme') || 'light';
    var btn = document.querySelector('.theme-toggle');
    if (btn) {{
        btn.querySelector('.theme-icon').textContent = theme === 'dark' ? '\\u2600' : '\\u263E';
        btn.querySelector('.theme-label').textContent = theme === 'dark' ? 'Light' : 'Dark';
    }}
}})();
</script></body></html>""")

    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(parts))
    logger.info("Visual diff report: %s", output_path)
    print(f"  ✓ Visual diff report: {output_path}")
    return output_path


def generate_visual_diff_json(
    extracted_data: Dict,
    pbip_dir: str,
) -> Dict:
    """Generate visual diff data as a dict (for programmatic use).

    Args:
        extracted_data: Dict of extracted JSON objects from Qlik.
        pbip_dir: Path to the generated .pbip project directory.

    Returns:
        Dict with diff results and summary.
    """
    worksheets = extracted_data.get('worksheets', [])
    if isinstance(worksheets, dict):
        worksheets = worksheets.get('worksheets', [])

    pbi_visuals = _load_pbi_visuals(pbip_dir)
    diffs = [_diff_worksheet(ws, pbi_visuals) for ws in worksheets]

    total = len(diffs)
    return {
        'total': total,
        'exact': sum(1 for d in diffs if d['status'] == 'exact'),
        'approximate': sum(1 for d in diffs if d['status'] == 'approx'),
        'unmapped': sum(1 for d in diffs if d['status'] == 'unmapped'),
        'avg_field_coverage': (
            round(sum(d['field_coverage'] for d in diffs) / total)
            if total else 100
        ),
        'visuals': diffs,
    }
