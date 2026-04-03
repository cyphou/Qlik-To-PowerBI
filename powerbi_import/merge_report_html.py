"""
Shared Semantic Model — HTML Merge Report Generator.

Produces a visual HTML report showing:
- Qlik source inventory (per-app tables, measures, relationships)
- Power BI merged output (unified model structure)
- Merge details (how tables were matched, column overlap, conflicts resolved)
- Measure/relationship mapping (Qlik → Power BI, dedup/namespace)

Usage::

    from powerbi_import.merge_report_html import generate_merge_html_report

    html_path = generate_merge_html_report(
        assessment=assessment,
        all_extracted=all_extracted,
        app_names=app_names,
        merged=merged_objects,
        model_name="SharedModel",
        output_path="merge_report.html",
    )
"""

from __future__ import annotations

import datetime
import json
import logging
import os
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    from powerbi_import.shared_model import MergeAssessment
except ImportError:
    from shared_model import MergeAssessment

try:
    from powerbi_import.html_template import (
        get_report_css, get_report_js, esc as _esc,
        PBI_BLUE, PBI_DARK, PBI_GRAY, PBI_LIGHT_GRAY, PBI_BG,
        SUCCESS, FAIL, badge as _shared_badge, fidelity_bar,
    )
    WARN = "#797600"
except ImportError:
    from html_template import (
        get_report_css, get_report_js, esc as _esc,
        PBI_BLUE, PBI_DARK, PBI_GRAY, PBI_LIGHT_GRAY, PBI_BG,
        SUCCESS, FAIL, badge as _shared_badge, fidelity_bar,
    )
    WARN = "#797600"


def _safe_id(text: str) -> str:
    """Create a safe HTML id from arbitrary text (alphanumeric + underscore only)."""
    import re
    return re.sub(r'[^a-zA-Z0-9_]', '', text.replace(' ', '_'))


def _score_color(score: int) -> str:
    if score >= 60:
        return SUCCESS
    if score >= 30:
        return WARN
    return FAIL


def _overlap_bar(pct: float) -> str:
    """Render a % bar for column overlap using shared template classes."""
    width = max(int(pct * 100), 0)
    color = "var(--success)" if pct >= 0.7 else "#c19c00" if pct >= 0.4 else "var(--fail)"
    return (
        f'<span class="fidelity-bar">'
        f'<span class="fidelity-track"><span class="fidelity-fill" '
        f'style="width:{width}%;background:{color}"></span></span>'
        f'<span class="fidelity-label">{width}%</span></span>'
    )


def _rec_badge(rec: str) -> str:
    """Render recommendation as styled badge using shared template."""
    labels = {
        "merge": ("MERGE", "green"),
        "partial": ("PARTIAL", "yellow"),
        "separate": ("SEPARATE", "red"),
    }
    text, level = labels.get(rec, (rec.upper(), "gray"))
    return _shared_badge(text, level)


# ═══════════════════════════════════════════════════════════════════
#  Source inventory helpers
# ═══════════════════════════════════════════════════════════════════

def _count_tables(extracted: dict) -> int:
    count = 0
    for ds in extracted.get('datasources', []):
        count += sum(1 for t in ds.get('tables', []) if t.get('type', 'table') == 'table')
    return count


def _count_columns(extracted: dict) -> int:
    count = 0
    for ds in extracted.get('datasources', []):
        for t in ds.get('tables', []):
            count += len(t.get('columns', []))
    return count


def _count_measures(extracted: dict) -> int:
    count = 0
    for ds in extracted.get('datasources', []):
        for c in ds.get('calculations', []):
            if c.get('role', 'measure') == 'measure':
                count += 1
    for c in extracted.get('calculations', []):
        if c.get('role', 'measure') == 'measure':
            count += 1
    return count


def _count_calc_columns(extracted: dict) -> int:
    count = 0
    for ds in extracted.get('datasources', []):
        for c in ds.get('calculations', []):
            if c.get('role') == 'dimension':
                count += 1
    for c in extracted.get('calculations', []):
        if c.get('role') == 'dimension':
            count += 1
    return count


def _count_relationships(extracted: dict) -> int:
    count = 0
    for ds in extracted.get('datasources', []):
        count += len(ds.get('relationships', []))
    return count


def _get_connection_types(extracted: dict) -> list:
    types = set()
    for ds in extracted.get('datasources', []):
        conn = ds.get('connection', {})
        ct = conn.get('type', '')
        if ct:
            types.add(ct)
    return sorted(types)


def _get_table_names(extracted: dict) -> list:
    names = []
    for ds in extracted.get('datasources', []):
        for t in ds.get('tables', []):
            if t.get('type', 'table') == 'table':
                names.append(t.get('name', ''))
    return names


def _get_measures_list(extracted: dict) -> list:
    """Return list of (caption, formula) tuples for measures."""
    measures = []
    seen = set()
    for ds in extracted.get('datasources', []):
        for c in ds.get('calculations', []):
            if c.get('role', 'measure') == 'measure':
                caption = c.get('caption', c.get('name', ''))
                if caption not in seen:
                    seen.add(caption)
                    measures.append((caption, c.get('formula', '')))
    for c in extracted.get('calculations', []):
        if c.get('role', 'measure') == 'measure':
            caption = c.get('caption', c.get('name', ''))
            if caption not in seen:
                seen.add(caption)
                measures.append((caption, c.get('formula', '')))
    return measures


# ═══════════════════════════════════════════════════════════════════
#  Merged model helpers
# ═══════════════════════════════════════════════════════════════════

def _merged_table_count(merged: dict) -> int:
    for ds in merged.get('datasources', []):
        return sum(1 for t in ds.get('tables', []) if t.get('type', 'table') == 'table')
    return 0


def _merged_column_count(merged: dict) -> int:
    count = 0
    for ds in merged.get('datasources', []):
        for t in ds.get('tables', []):
            count += len(t.get('columns', []))
    return count


def _merged_relationship_count(merged: dict) -> int:
    for ds in merged.get('datasources', []):
        return len(ds.get('relationships', []))
    return 0


def _merged_measure_count(merged: dict) -> int:
    count = len([c for c in merged.get('calculations', [])
                 if c.get('role', 'measure') == 'measure'])
    for ds in merged.get('datasources', []):
        count += len([c for c in ds.get('calculations', [])
                      if c.get('role', 'measure') == 'measure'])
    return count


def _merged_tables_list(merged: dict) -> list:
    """Return list of (name, col_count) for merged tables."""
    tables = []
    for ds in merged.get('datasources', []):
        for t in ds.get('tables', []):
            if t.get('type', 'table') == 'table':
                tables.append((t.get('name', ''), len(t.get('columns', []))))
    return tables


def _merged_measures_list(merged: dict) -> list:
    """Return list of (caption, formula, source_wb_or_None) for merged measures."""
    measures = []
    for c in merged.get('calculations', []):
        if c.get('role', 'measure') == 'measure':
            caption = c.get('caption', c.get('name', ''))
            formula = c.get('formula', '')
            src = c.get('_source_app', None)
            original = c.get('_original_caption', None)
            measures.append((caption, formula, src, original))
    for ds in merged.get('datasources', []):
        for c in ds.get('calculations', []):
            if c.get('role', 'measure') == 'measure':
                caption = c.get('caption', c.get('name', ''))
                formula = c.get('formula', '')
                measures.append((caption, formula, None, None))
    return measures


# ═══════════════════════════════════════════════════════════════════
#  Main HTML generator
# ═══════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════
#  Lineage section builder
# ═══════════════════════════════════════════════════════════════════

_ACTION_STYLE = {
    'deduplicated': ('success-tag', '&#10003; Deduplicated'),
    'namespaced': ('warn-tag', '&#9888; Namespaced'),
    'unioned': ('connector-tag', '&#8644; Unioned'),
    'unique': ('connector-tag', '&#8226; Unique'),
    'first-wins': ('connector-tag', '1st wins'),
}


def _build_lineage_section(merged: dict, app_names: List[str]) -> str:
    """Build the Lineage HTML section for the merge report."""
    try:
        from powerbi_import.shared_model import extract_lineage
    except ImportError:
        from shared_model import extract_lineage

    records = extract_lineage(merged)
    if not records:
        return ''

    html = '<div class="section-header" onclick="toggleSection(this)"><span class="section-icon">&#128279;</span>'
    html += 'Lineage<span class="toggle-arrow">&#9660;</span></div>'
    html += '<div class="section-body">'

    # --- Sankey-style flow diagram ---
    # Group by type and action
    type_counts: Dict[str, Dict[str, int]] = {}
    for r in records:
        rtype = r.get('type', 'unknown')
        action = r.get('merge_action', 'unique')
        type_counts.setdefault(rtype, {})
        type_counts[rtype][action] = type_counts[rtype].get(action, 0) + 1

    # app → artifact flow
    wb_artifact_count: Dict[str, int] = {}
    for r in records:
        for wb in r.get('source_apps', []):
            wb_artifact_count[wb] = wb_artifact_count.get(wb, 0) + 1

    html += '<div class="card">'
    html += '<h3>Artifact Flow</h3>'
    html += '<div style="display:flex;justify-content:space-around;align-items:center;flex-wrap:wrap;gap:10px;padding:20px;">'

    # Left side: apps
    html += '<div style="display:flex;flex-direction:column;gap:8px;">'
    for wb_name in app_names:
        count = wb_artifact_count.get(wb_name, 0)
        html += f'<div class="flow-box" style="background:#e8f0fe;color:#1a73e8;min-width:160px;">'
        html += f'{_esc(wb_name)}<br/><small>{count} artifacts</small></div>'
    html += '</div>'

    html += '<div class="flow-arrow">&#8594;</div>'

    # Middle: merge actions
    action_totals: Dict[str, int] = {}
    for r in records:
        action = r.get('merge_action', 'unique')
        action_totals[action] = action_totals.get(action, 0) + 1

    html += '<div style="display:flex;flex-direction:column;gap:8px;">'
    for action, count in sorted(action_totals.items(), key=lambda x: -x[1]):
        style_cls, label = _ACTION_STYLE.get(action, ('connector-tag', action))
        html += f'<div class="flow-box" style="background:#fff;border:2px solid {PBI_BLUE};min-width:140px;">'
        html += f'<span class="{style_cls}">{label}</span><br/><small>{count} items</small></div>'
    html += '</div>'

    html += '<div class="flow-arrow">&#8594;</div>'

    # Right: artifact types
    html += '<div style="display:flex;flex-direction:column;gap:8px;">'
    for rtype, actions in sorted(type_counts.items()):
        total = sum(actions.values())
        html += f'<div class="flow-box" style="background:#d4edda;color:#155724;min-width:140px;">'
        html += f'{_esc(rtype)}<br/><small>{total} items</small></div>'
    html += '</div>'

    html += '</div></div>'

    # --- Sortable detail table ---
    html += '<div class="card">'
    html += '<h3>Artifact Lineage Detail</h3>'
    html += '<table class="detail-table"><tr>'
    html += '<th>Artifact Name</th><th>Type</th><th>Source app(s)</th><th>Merge Action</th>'
    html += '</tr>'

    for r in records:
        name = r.get('name', '')
        rtype = r.get('type', '')
        sources = r.get('source_apps', [])
        action = r.get('merge_action', '')

        source_html = ', '.join(
            f'<span class="connector-tag">{_esc(s)}</span>' for s in sources
        ) if sources else '<span style="color:#a19f9d">—</span>'

        style_cls, label = _ACTION_STYLE.get(action, ('connector-tag', action or '—'))
        action_html = f'<span class="{style_cls}">{label}</span>'

        html += f'<tr><td><strong>{_esc(name)}</strong></td>'
        html += f'<td>{_esc(rtype)}</td>'
        html += f'<td>{source_html}</td>'
        html += f'<td>{action_html}</td></tr>'

    html += '</table></div></div>'

    return html


def generate_merge_html_report(
    assessment: MergeAssessment,
    all_extracted: List[dict],
    app_names: List[str],
    merged: dict,
    model_name: str = "SharedModel",
    output_path: Optional[str] = None,
) -> str:
    """Generate the HTML merge report.

    Args:
        assessment: The MergeAssessment from assess_merge().
        all_extracted: Original extracted data per app.
        app_names: app names (parallel with all_extracted).
        merged: The merged converted_objects from merge_semantic_models().
        model_name: Name of the shared semantic model.
        output_path: File path for the HTML output.

    Returns:
        The output file path.
    """
    try:
        from powerbi_import import __version__ as tool_version
    except Exception:
        tool_version = "13.0.0"

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    score = assessment.merge_score
    score_color = _score_color(score)

    # ── Compute per-app stats ──
    wb_stats = []
    for wb_name, extracted in zip(app_names, all_extracted):
        wb_stats.append({
            'name': wb_name,
            'tables': _count_tables(extracted),
            'columns': _count_columns(extracted),
            'measures': _count_measures(extracted),
            'calc_columns': _count_calc_columns(extracted),
            'relationships': _count_relationships(extracted),
            'connectors': _get_connection_types(extracted),
            'table_names': _get_table_names(extracted),
            'worksheets': len(extracted.get('worksheets', [])),
            'dashboards': len(extracted.get('dashboards', [])),
            'parameters': len(extracted.get('parameters', [])),
        })

    # ── Merged model stats ──
    merged_stats = {
        'tables': _merged_table_count(merged),
        'columns': _merged_column_count(merged),
        'measures': _merged_measure_count(merged),
        'relationships': _merged_relationship_count(merged),
        'parameters': len(merged.get('parameters', [])),
    }

    # Total source stats
    total_src_tables = sum(s['tables'] for s in wb_stats)
    total_src_measures = sum(s['measures'] for s in wb_stats)
    total_src_rels = sum(s['relationships'] for s in wb_stats)
    tables_saved = total_src_tables - merged_stats['tables']

    # ══════════════════════════════════════════════════════════════
    #  Build HTML
    # ══════════════════════════════════════════════════════════════

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Shared Semantic Model — Merge Report</title>
<style>{get_report_css()}
/* merge-report extras */
.merge-arrow {{ color: var(--pbi-blue); font-weight: bold; font-size: 1.2em; padding: 0 8px; }}
.mono {{ font-family: 'Cascadia Code', 'Consolas', monospace; font-size: 0.82em; }}
.section-icon {{ font-size: 1.2em; margin-right: 4px; }}
.flow-box {{ display: inline-block; padding: 12px 20px; border-radius: 8px; text-align: center; font-weight: bold; font-size: 0.95em; }}
.flow-arrow {{ display: inline-block; font-size: 1.8em; color: var(--pbi-blue); vertical-align: middle; padding: 0 10px; }}
.detail-table th {{ background: var(--pbi-gray); }}
</style>
</head>
<body>
<div class="report-header">
<h1>&#128279; Shared Semantic Model — Merge Report</h1>
<p>Model: <strong>{_esc(model_name)}</strong> &nbsp;|&nbsp; apps: {len(app_names)} &nbsp;|&nbsp; Generated: {now} &nbsp;|&nbsp; Tool: v{tool_version}</p>
</div>
<div class="container">
"""

    # ══════════════════════════════════════════════════════════════
    # 1. EXECUTIVE SUMMARY
    # ══════════════════════════════════════════════════════════════
    html += f"""
<div class="section-header" onclick="toggleSection(this)">
<span class="section-icon">&#128200;</span> Executive Summary <span class="toggle-arrow">&#9660;</span></div>
<div class="section-body">
<div class="stat-grid">
    <div class="stat-card"><div class="stat-value">{len(app_names)}</div><div class="stat-label">apps</div></div>
    <div class="stat-card accent-teal"><div class="stat-value" style="color:{score_color}">{score}/100</div><div class="stat-label">Merge Score</div></div>
    <div class="stat-card"><div class="stat-value">{total_src_tables}</div><div class="stat-label">Source Tables</div></div>
    <div class="stat-card accent-green"><div class="stat-value">{merged_stats['tables']}</div><div class="stat-label">Merged Tables</div></div>
    <div class="stat-card accent-green"><div class="stat-value">{tables_saved}</div><div class="stat-label">Tables Saved</div></div>
    <div class="stat-card"><div class="stat-value">{assessment.measure_duplicates_removed}</div><div class="stat-label">Measures Deduped</div></div>
    <div class="stat-card"><div class="stat-value">{assessment.relationship_duplicates_removed}</div><div class="stat-label">Rels Deduped</div></div>
    <div class="stat"><div class="number" style="color:{WARN if assessment.measure_conflicts else SUCCESS}">{len(assessment.measure_conflicts)}</div><div class="label">Conflicts</div></div>
</div>

<div class="card" style="margin-top:15px;text-align:center">
    <div class="flow-box" style="background:#e8f0fe;color:#1a73e8">
        {len(app_names)} Qlik apps<br>
        <span style="font-size:0.8em;font-weight:normal">{total_src_tables} tables &bull; {total_src_measures} measures</span>
    </div>
    <span class="flow-arrow">&#10132;</span>
    <div class="flow-box" style="background:#fff3cd;color:#856404">
        Merge Engine<br>
        <span style="font-size:0.8em;font-weight:normal">Score: {score}/100 &bull; {_rec_badge(assessment.recommendation)}</span>
    </div>
    <span class="flow-arrow">&#10132;</span>
    <div class="flow-box" style="background:#d4edda;color:#155724">
        1 Shared Semantic Model<br>
        <span style="font-size:0.8em;font-weight:normal">{merged_stats['tables']} tables &bull; {merged_stats['measures']} measures &bull; {merged_stats['relationships']} rels</span>
    </div>
    <span class="flow-arrow">+</span>
    <div class="flow-box" style="background:#d4edda;color:#155724">
        {len(app_names)} Thin Reports<br>
        <span style="font-size:0.8em;font-weight:normal">byPath &#8594; {_esc(model_name)}.SemanticModel</span>
    </div>
</div>
</div>
"""

    # ══════════════════════════════════════════════════════════════
    # 2. Qlik SOURCE INVENTORY
    # ══════════════════════════════════════════════════════════════
    html += f"""
<div class="section-header" onclick="toggleSection(this)">
<span class="section-icon">&#128214;</span> Qlik Source Inventory <span class="toggle-arrow">&#9660;</span></div>
<div class="section-body">
<div class="card">
<table>
<tr>
    <th>app</th><th>Connectors</th><th>Tables</th><th>Columns</th>
    <th>Measures</th><th>Calc Columns</th><th>Relationships</th>
    <th>Worksheets</th><th>Parameters</th>
</tr>
"""
    for ws in wb_stats:
        conn_html = " ".join(
            f'<span class="connector-tag">{_esc(c)}</span>' for c in ws['connectors']
        ) or "—"
        html += f"""<tr>
    <td><strong>{_esc(ws['name'])}</strong></td>
    <td>{conn_html}</td>
    <td>{ws['tables']}</td><td>{ws['columns']}</td>
    <td>{ws['measures']}</td><td>{ws['calc_columns']}</td>
    <td>{ws['relationships']}</td>
    <td>{ws['worksheets']}</td><td>{ws['parameters']}</td>
</tr>"""

    # Totals row
    html += f"""<tr style="background:#e8f0fe;font-weight:bold">
    <td>TOTAL</td><td></td>
    <td>{total_src_tables}</td><td>{sum(s['columns'] for s in wb_stats)}</td>
    <td>{total_src_measures}</td><td>{sum(s['calc_columns'] for s in wb_stats)}</td>
    <td>{total_src_rels}</td>
    <td>{sum(s['worksheets'] for s in wb_stats)}</td>
    <td>{sum(s['parameters'] for s in wb_stats)}</td>
</tr>"""
    html += "</table></div></div>"

    # ══════════════════════════════════════════════════════════════
    # 3. POWER BI MERGED OUTPUT
    # ══════════════════════════════════════════════════════════════
    html += f"""
<div class="section-header" onclick="toggleSection(this)">
<span class="section-icon">&#9889;</span> Power BI Merged Output <span class="toggle-arrow">&#9660;</span></div>
<div class="section-body">
<div class="stats">
    <div class="stat"><div class="number" style="color:{PBI_BLUE}">{merged_stats['tables']}</div><div class="label">Tables</div></div>
    <div class="stat"><div class="number">{merged_stats['columns']}</div><div class="label">Columns</div></div>
    <div class="stat"><div class="number">{merged_stats['measures']}</div><div class="label">Measures</div></div>
    <div class="stat"><div class="number">{merged_stats['relationships']}</div><div class="label">Relationships</div></div>
    <div class="stat"><div class="number">{merged_stats['parameters']}</div><div class="label">Parameters</div></div>
    <div class="stat"><div class="number">{len(app_names)}</div><div class="label">Thin Reports</div></div>
</div>

<div class="card">
<h3>Merged Tables</h3>
<table class="detail-table">
<tr><th>Table Name</th><th>Columns</th><th>Source apps</th><th>Merge Action</th></tr>
"""
    # Build table → source apps mapping from merge candidates
    table_sources = {}
    for mc in assessment.merge_candidates:
        table_sources[mc.table_name] = [s[0] for s in mc.sources]

    for tname, col_count in _merged_tables_list(merged):
        sources = table_sources.get(tname, [])
        if sources:
            src_html = ", ".join(f'<span class="connector-tag">{_esc(s)}</span>' for s in sources)
            action = '<span class="success-tag">Merged</span>'
        else:
            # Unique table — find which app it came from
            owner = "—"
            for wb_name, ws in zip(app_names, wb_stats):
                if tname in ws['table_names']:
                    owner = wb_name
                    break
            src_html = f'<span class="connector-tag">{_esc(owner)}</span>'
            action = '<span class="warn-tag">Unique (kept as-is)</span>'
        html += f"""<tr>
    <td><strong>{_esc(tname)}</strong></td>
    <td>{col_count}</td>
    <td>{src_html}</td>
    <td>{action}</td>
</tr>"""

    html += "</table></div></div>"

    # ══════════════════════════════════════════════════════════════
    # 4. MERGE DETAILS — TABLE MATCHING
    # ══════════════════════════════════════════════════════════════
    html += f"""
<div class="section-header" onclick="toggleSection(this)">
<span class="section-icon">&#128269;</span> Merge Details — Table Matching <span class="toggle-arrow">&#9660;</span></div>
<div class="section-body">
"""

    if assessment.merge_candidates:
        html += """<div class="card">
<table>
<tr>
    <th>Table</th><th>Fingerprint</th><th>apps</th>
    <th>Column Overlap</th><th>Conflicts</th>
</tr>
"""
        for mc in assessment.merge_candidates:
            fp = mc.fingerprint
            fp_parts = f"{_esc(fp.connection_type)} | {_esc(fp.server)} | {_esc(fp.database)} | {_esc(fp.table_name)}"
            wb_list = ", ".join(s[0] for s in mc.sources)
            conflict_html = ""
            if mc.conflicts:
                conflict_html = "<br>".join(
                    f'<span class="danger-tag">{_esc(c)}</span>' for c in mc.conflicts[:5]
                )
            else:
                conflict_html = '<span class="success-tag">None</span>'

            html += f"""<tr>
    <td><strong>{_esc(mc.table_name)}</strong></td>
    <td class="mono" style="max-width:300px;word-break:break-all">{fp_parts}</td>
    <td>{_esc(wb_list)}</td>
    <td>{_overlap_bar(mc.column_overlap)}</td>
    <td>{conflict_html}</td>
</tr>"""
        html += "</table></div>"
    else:
        html += '<div class="card"><p style="color:#a19f9d">No merge candidates found — tables are all unique across apps.</p></div>'

    # Unique tables section
    if assessment.unique_tables:
        html += """<div class="card">
<h3>Unique Tables (no matching across apps)</h3>
<table class="detail-table">
<tr><th>Table</th><th>app</th></tr>
"""
        for wb, tables in assessment.unique_tables.items():
            for t in tables:
                html += f'<tr><td>{_esc(t)}</td><td><span class="connector-tag">{_esc(wb)}</span></td></tr>'
        html += "</table></div>"

    html += "</div>"  # end details section

    # ══════════════════════════════════════════════════════════════
    # 5. MEASURE MAPPING
    # ══════════════════════════════════════════════════════════════
    html += f"""
<div class="section-header" onclick="toggleSection(this)">
<span class="section-icon">&#128202;</span> Measure Mapping — Qlik to Power BI <span class="toggle-arrow">&#9660;</span></div>
<div class="section-body">
"""

    # Build source measures per app
    all_source_measures = {}
    for wb_name, extracted in zip(app_names, all_extracted):
        all_source_measures[wb_name] = _get_measures_list(extracted)

    # Tabs: one per app + "Conflicts" tab
    has_conflicts = bool(assessment.measure_conflicts)
    html += '<div class="tab-bar">'
    html += '<div class="tab active" onclick="switchTab(\'meas\', \'all\')">All Measures</div>'
    for wb_name in app_names:
        safe = _safe_id(wb_name)
        html += f'<div class="tab" onclick="switchTab(\'meas\', \'{safe}\')">{_esc(wb_name)}</div>'
    if has_conflicts:
        html += '<div class="tab" onclick="switchTab(\'meas\', \'conflicts\')" style="color:#dc3545">&#9888; Conflicts</div>'
    html += '</div>'

    # All measures tab — merged output
    merged_measures = _merged_measures_list(merged)
    html += '<div class="tab-content active" id="meas-all"><div class="card">'
    html += '<table class="detail-table"><tr><th>Power BI Measure</th><th>DAX Formula</th><th>Action</th><th>Source</th></tr>'
    for caption, formula, src_wb, original in merged_measures:
        short_formula = _esc(formula[:80] + '...' if len(formula) > 80 else formula)
        if src_wb:
            action = f'<span class="warn-tag">Namespaced from [{_esc(original or caption)}]</span>'
            src = f'<span class="connector-tag">{_esc(src_wb)}</span>'
        else:
            action = '<span class="success-tag">Kept / Deduped</span>'
            src = '<span class="connector-tag">Shared</span>'
        html += f"""<tr>
    <td><strong>{_esc(caption)}</strong></td>
    <td class="mono" style="max-width:400px;word-break:break-all">{short_formula}</td>
    <td>{action}</td><td>{src}</td>
</tr>"""
    if not merged_measures:
        html += '<tr><td colspan="4" style="color:#a19f9d;text-align:center">No measures</td></tr>'
    html += '</table></div></div>'

    # Per-app tabs
    for wb_name in app_names:
        safe = _safe_id(wb_name)
        measures = all_source_measures.get(wb_name, [])
        html += f'<div class="tab-content" id="meas-{safe}"><div class="card">'
        html += f'<table class="detail-table"><tr><th>Qlik Measure</th><th>Qlik Formula</th><th>&#10132; Power BI</th></tr>'
        for caption, formula in measures:
            # Find what it became in merged model
            pbi_name = caption
            action_label = "Kept"
            for mc in assessment.measure_conflicts:
                if mc.name == caption and wb_name in mc.variants:
                    pbi_name = f"{caption} ({wb_name})"
                    action_label = "Namespaced"
                    break
            short_formula = _esc(formula[:80] + '...' if len(formula) > 80 else formula)
            html += f"""<tr>
    <td><strong>{_esc(caption)}</strong></td>
    <td class="mono" style="max-width:350px;word-break:break-all">{short_formula}</td>
    <td><span class="merge-arrow">&#10132;</span> <strong>{_esc(pbi_name)}</strong>
        <br><span class="{'warn-tag' if action_label == 'Namespaced' else 'success-tag'}">{action_label}</span></td>
</tr>"""
        if not measures:
            html += '<tr><td colspan="3" style="color:#a19f9d;text-align:center">No measures in this app</td></tr>'
        html += '</table></div></div>'

    # Conflicts tab
    if has_conflicts:
        html += '<div class="tab-content" id="meas-conflicts"><div class="card">'
        html += '<table class="detail-table"><tr><th>Measure Name</th><th>app</th><th>Qlik Formula</th><th>&#10132; Power BI Name</th></tr>'
        for mc in assessment.measure_conflicts:
            first = True
            for wb, formula in mc.variants.items():
                short = _esc(formula[:80] + '...' if len(formula) > 80 else formula)
                name_cell = f'<td rowspan="{len(mc.variants)}"><strong>{_esc(mc.name)}</strong><br><span class="danger-tag">CONFLICT</span></td>' if first else ''
                pbi_name = f"{mc.name} ({wb})"
                html += f"""<tr>
    {name_cell}
    <td><span class="connector-tag">{_esc(wb)}</span></td>
    <td class="mono" style="max-width:350px;word-break:break-all">{short}</td>
    <td><strong>{_esc(pbi_name)}</strong></td>
</tr>"""
                first = False
        html += '</table></div></div>'

    html += "</div>"

    # ══════════════════════════════════════════════════════════════
    # 6. RELATIONSHIP MAPPING
    # ══════════════════════════════════════════════════════════════
    html += f"""
<div class="section-header" onclick="toggleSection(this)">
<span class="section-icon">&#128279;</span> Relationship Mapping <span class="toggle-arrow">&#9660;</span></div>
<div class="section-body">
<div class="card">
"""

    # Collect all source relationships
    all_src_rels = []
    for wb_name, extracted in zip(app_names, all_extracted):
        for ds in extracted.get('datasources', []):
            for rel in ds.get('relationships', []):
                all_src_rels.append((wb_name, rel))

    # Merged relationships
    merged_rels = []
    for ds in merged.get('datasources', []):
        merged_rels = ds.get('relationships', [])
        break

    html += f"""<p>Source relationships: <strong>{len(all_src_rels)}</strong> &nbsp;&#10132;&nbsp;
Merged (deduplicated): <strong>{len(merged_rels)}</strong> &nbsp;
(<span class="success-tag">{assessment.relationship_duplicates_removed} duplicates removed</span>)</p>
<table class="detail-table">
<tr><th>From Table</th><th>From Column</th><th>&#10132;</th><th>To Table</th><th>To Column</th><th>Cardinality</th></tr>
"""
    for rel in merged_rels:
        if 'left' in rel:
            ft, fc = rel['left'].get('table', ''), rel['left'].get('column', '')
            tt, tc = rel['right'].get('table', ''), rel['right'].get('column', '')
        else:
            ft, fc = rel.get('from_table', ''), rel.get('from_column', '')
            tt, tc = rel.get('to_table', ''), rel.get('to_column', '')
        card = rel.get('cardinality', rel.get('join_type', '—'))
        html += f"""<tr>
    <td><strong>{_esc(ft)}</strong></td>
    <td class="mono">{_esc(fc)}</td>
    <td style="text-align:center;color:{PBI_BLUE};font-weight:bold">&#10132;</td>
    <td><strong>{_esc(tt)}</strong></td>
    <td class="mono">{_esc(tc)}</td>
    <td><span class="connector-tag">{_esc(card)}</span></td>
</tr>"""
    if not merged_rels:
        html += '<tr><td colspan="6" style="color:#a19f9d;text-align:center">No relationships</td></tr>'

    html += "</table></div></div>"

    # ══════════════════════════════════════════════════════════════
    # 7. PARAMETER & CONFLICT SUMMARY
    # ══════════════════════════════════════════════════════════════
    if assessment.parameter_conflicts or assessment.parameter_duplicates_removed > 0:
        html += f"""
<div class="section-header" onclick="toggleSection(this)">
<span class="section-icon">&#9881;</span> Parameters <span class="toggle-arrow">&#9660;</span></div>
<div class="section-body">
<div class="card">
<p>Duplicates removed: <strong>{assessment.parameter_duplicates_removed}</strong> &nbsp;|&nbsp;
Conflicts: <strong>{len(assessment.parameter_conflicts)}</strong></p>
"""
        if assessment.parameter_conflicts:
            html += '<table class="detail-table"><tr><th>Parameter</th><th>app</th><th>Type</th><th>Value</th></tr>'
            for pc in assessment.parameter_conflicts:
                pname = pc.get('name', '')
                first = True
                for wb, details in pc.get('variants', {}).items():
                    name_cell = f'<td rowspan="{len(pc["variants"])}"><strong>{_esc(pname)}</strong><br><span class="warn-tag">CONFLICT</span></td>' if first else ''
                    html += f"""<tr>
    {name_cell}
    <td><span class="connector-tag">{_esc(wb)}</span></td>
    <td>{_esc(details.get('datatype', ''))}</td>
    <td class="mono">{_esc(str(details.get('current_value', '')))}</td>
</tr>"""
                    first = False
            html += '</table>'
        html += "</div></div>"

    # ══════════════════════════════════════════════════════════════
    # 8. SECURITY — RLS ROLES
    # ══════════════════════════════════════════════════════════════
    rls_roles = merged.get('user_filters', [])
    if rls_roles:
        # Import validation helpers
        try:
            from powerbi_import.shared_model import (
                validate_rls_propagation,
                validate_rls_principals,
            )
            propagation = {r['role']: r for r in validate_rls_propagation(merged)}
            principals = {r['role']: r for r in validate_rls_principals(merged)}
        except Exception:
            propagation = {}
            principals = {}

        html += f"""
<div class="section-header" onclick="toggleSection(this)">
<span class="section-icon">&#128274;</span> Security &mdash; RLS Roles ({len(rls_roles)}) <span class="toggle-arrow">&#9660;</span></div>
<div class="section-body">
<div class="card">
<table class="detail-table">
<tr><th>Role</th><th>Table</th><th>Expression</th><th>Propagation</th><th>Principal Format</th><th>Source</th></tr>"""
        for uf in rls_roles:
            role_name = uf.get('name', uf.get('field', ''))
            table = uf.get('table', '')
            expr = uf.get('filter_expression', uf.get('formula', ''))[:120]
            source_wbs = ', '.join(uf.get('_source_apps', []))
            # Propagation status
            prop = propagation.get(role_name, {})
            prop_status = prop.get('status', '')
            if prop_status == 'ok':
                prop_html = '<span style="color:#107c10">&#10003; Connected</span>'
            elif prop_status == 'warning':
                prop_html = f'<span style="color:#ca5010">&#9888; {_esc(prop.get("reason", ""))}</span>'
            elif prop_status == 'error':
                prop_html = f'<span style="color:#d13438">&#10007; {_esc(prop.get("reason", ""))}</span>'
            else:
                prop_html = '<span style="color:#a19f9d">N/A</span>'
            # Principal format
            princ = principals.get(role_name, {})
            princ_fmt = _esc(princ.get('format_detected', ''))
            html += f"""<tr>
    <td><strong>{_esc(role_name)}</strong></td>
    <td>{_esc(table)}</td>
    <td class="mono" style="max-width:300px;word-break:break-all">{_esc(expr)}</td>
    <td>{prop_html}</td>
    <td>{princ_fmt}</td>
    <td>{_esc(source_wbs)}</td>
</tr>"""
        html += "</table></div></div>"

    # ══════════════════════════════════════════════════════════════
    # SECTION 9: LINEAGE
    # ══════════════════════════════════════════════════════════════
    html += _build_lineage_section(merged, app_names)

    # ══════════════════════════════════════════════════════════════
    # FOOTER
    # ══════════════════════════════════════════════════════════════
    html += f"""
<div class="report-footer">
    Qlik &#8594; Power BI Migration Tool v{tool_version} &nbsp;|&nbsp;
    Report generated: {now} &nbsp;|&nbsp;
    Model: {_esc(model_name)}
</div>

</div><!-- /.container -->

<script>{get_report_js()}</script>
</body>
</html>"""

    # ── Write output ──
    if not output_path:
        output_path = 'merge_report.html'

    os.makedirs(os.path.dirname(os.path.abspath(output_path)) or '.', exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    logger.info("Merge HTML report saved to %s", output_path)
    return output_path
