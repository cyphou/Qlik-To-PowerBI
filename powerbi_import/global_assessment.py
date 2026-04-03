"""
Global Assessment — Cross-app Merge Analysis & HTML Report.

Analyzes ALL apps in a batch to identify merge clusters,
pairwise overlap, and produces a visual HTML report showing:
- app inventory (per-app stats)
- Pairwise merge score matrix (N×N heatmap)
- Merge clusters (groups of apps that share tables)
- Isolated apps (no overlap with any other)
- Per-cluster detailed breakdown

Usage (CLI)::

    python migrate.py --batch examples/Qlik_samples/ --global-assess
    python migrate.py --global-assess wb1.qvf wb2.qvf wb3.qvf wb4.qvf

Usage (programmatic)::

    from powerbi_import.global_assessment import (
        run_global_assessment,
        generate_global_html_report,
    )

    result = run_global_assessment(all_extracted_list, app_names)
    generate_global_html_report(result, output_path="global_assessment.html")
"""

from __future__ import annotations

import datetime
import json
import logging
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

try:
    from powerbi_import.shared_model import (
        MergeAssessment,
        assess_merge,
        build_table_fingerprints,
    )
except ImportError:
    from shared_model import (
        MergeAssessment,
        assess_merge,
        build_table_fingerprints,
    )


# ═══════════════════════════════════════════════════════════════════
#  Color palette (matches merge_report_html.py)
# ═══════════════════════════════════════════════════════════════════
PBI_BLUE = "#0078d4"
PBI_DARK = "#323130"
PBI_GRAY = "#605e5c"
PBI_LIGHT_GRAY = "#a19f9d"
PBI_BG = "#f5f5f5"
SUCCESS = "#28a745"
WARN = "#ffc107"
FAIL = "#dc3545"


# ═══════════════════════════════════════════════════════════════════
#  Data classes
# ═══════════════════════════════════════════════════════════════════

@dataclass
class WorkbookProfile:
    """Stats for a single app."""
    name: str
    tables: int = 0
    columns: int = 0
    measures: int = 0
    calc_columns: int = 0
    relationships: int = 0
    worksheets: int = 0
    dashboards: int = 0
    parameters: int = 0
    connection_types: List[str] = field(default_factory=list)
    table_names: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "tables": self.tables,
            "columns": self.columns,
            "measures": self.measures,
            "calc_columns": self.calc_columns,
            "relationships": self.relationships,
            "worksheets": self.worksheets,
            "dashboards": self.dashboards,
            "parameters": self.parameters,
            "connection_types": self.connection_types,
            "table_names": self.table_names,
        }


@dataclass
class PairwiseScore:
    """Merge score between two apps."""
    wb_a: str
    wb_b: str
    merge_score: int = 0
    shared_tables: int = 0
    recommendation: str = "separate"

    def to_dict(self) -> dict:
        return {
            "app_a": self.wb_a,
            "app_b": self.wb_b,
            "merge_score": self.merge_score,
            "shared_tables": self.shared_tables,
            "recommendation": self.recommendation,
        }


@dataclass
class MergeCluster:
    """A group of apps recommended for merging."""
    cluster_id: int
    apps: List[str] = field(default_factory=list)
    shared_tables: List[str] = field(default_factory=list)
    avg_score: int = 0
    recommendation: str = "merge"
    assessment: Optional[MergeAssessment] = None

    def to_dict(self) -> dict:
        d = {
            "cluster_id": self.cluster_id,
            "apps": self.apps,
            "shared_tables": self.shared_tables,
            "avg_score": self.avg_score,
            "recommendation": self.recommendation,
        }
        if self.assessment:
            d["merge_details"] = self.assessment.to_dict()
        return d


@dataclass
class GlobalAssessment:
    """Full cross-app assessment."""
    app_profiles: List[WorkbookProfile] = field(default_factory=list)
    pairwise_scores: List[PairwiseScore] = field(default_factory=list)
    merge_clusters: List[MergeCluster] = field(default_factory=list)
    isolated_apps: List[str] = field(default_factory=list)
    total_apps: int = 0
    total_tables: int = 0
    total_measures: int = 0

    def to_dict(self) -> dict:
        return {
            "total_apps": self.total_apps,
            "total_tables": self.total_tables,
            "total_measures": self.total_measures,
            "merge_clusters": [c.to_dict() for c in self.merge_clusters],
            "isolated_apps": self.isolated_apps,
            "pairwise_scores": [p.to_dict() for p in self.pairwise_scores],
            "app_profiles": [w.to_dict() for w in self.app_profiles],
        }


# ═══════════════════════════════════════════════════════════════════
#  Profiling helpers
# ═══════════════════════════════════════════════════════════════════

def _build_profile(name: str, extracted: dict) -> WorkbookProfile:
    """Build a WorkbookProfile from extracted data."""
    p = WorkbookProfile(name=name)
    conn_types = set()
    for ds in extracted.get('datasources', []):
        conn = ds.get('connection', {})
        ct = conn.get('type', '')
        if ct:
            conn_types.add(ct)
        for t in ds.get('tables', []):
            if t.get('type', 'table') == 'table':
                p.tables += 1
                p.table_names.append(t.get('name', ''))
            p.columns += len(t.get('columns', []))
        for c in ds.get('calculations', []):
            if c.get('role', 'measure') == 'measure':
                p.measures += 1
            elif c.get('role') == 'dimension':
                p.calc_columns += 1
        p.relationships += len(ds.get('relationships', []))
    for c in extracted.get('calculations', []):
        if c.get('role', 'measure') == 'measure':
            p.measures += 1
        elif c.get('role') == 'dimension':
            p.calc_columns += 1
    p.worksheets = len(extracted.get('worksheets', []))
    p.dashboards = len(extracted.get('dashboards', []))
    p.parameters = len(extracted.get('parameters', []))
    p.connection_types = sorted(conn_types)
    return p


def _find_shared_table_names(ext_a: dict, ext_b: dict) -> List[str]:
    """Find table names shared between two apps via fingerprint matching."""
    fp_a = build_table_fingerprints(ext_a.get('datasources', []))
    fp_b = build_table_fingerprints(ext_b.get('datasources', []))
    return _find_shared_table_names_cached(fp_a, fp_b)


def _find_shared_table_names_cached(fp_a: dict, fp_b: dict) -> List[str]:
    """Find shared table names from pre-computed fingerprint dicts."""
    hashes_a = {fp.fingerprint(): name for name, (fp, _, _) in fp_a.items()}
    hashes_b = {fp.fingerprint(): name for name, (fp, _, _) in fp_b.items()}
    shared_hashes = set(hashes_a.keys()) & set(hashes_b.keys())
    return [hashes_a[h] for h in shared_hashes]


# ═══════════════════════════════════════════════════════════════════
#  Core assessment
# ═══════════════════════════════════════════════════════════════════

def run_global_assessment(
    all_extracted: List[dict],
    app_names: List[str],
) -> GlobalAssessment:
    """Analyze all apps pairwise and identify merge clusters.

    Args:
        all_extracted: List of converted_objects dicts (one per app).
        app_names: Names for each app (parallel with all_extracted).

    Returns:
        GlobalAssessment with profiles, pairwise scores, and clusters.
    """
    n = len(app_names)
    result = GlobalAssessment(total_apps=n)

    # 1. Build per-app profiles
    for name, ext in zip(app_names, all_extracted):
        result.app_profiles.append(_build_profile(name, ext))
    result.total_tables = sum(p.tables for p in result.app_profiles)
    result.total_measures = sum(p.measures for p in result.app_profiles)

    # 2. Pairwise merge scores
    # adjacency: wb_index → set of wb_indices with score >= 30
    adjacency: Dict[int, set] = {i: set() for i in range(n)}

    # Pre-compute fingerprints once per app (O(n) instead of O(n²))
    _fingerprint_cache: Dict[int, dict] = {}
    for i in range(n):
        _fingerprint_cache[i] = build_table_fingerprints(
            all_extracted[i].get('datasources', [])
        )

    for i in range(n):
        for j in range(i + 1, n):
            pair_assessment = assess_merge(
                [all_extracted[i], all_extracted[j]],
                [app_names[i], app_names[j]],
            )
            shared = _find_shared_table_names_cached(
                _fingerprint_cache[i], _fingerprint_cache[j]
            )
            ps = PairwiseScore(
                wb_a=app_names[i],
                wb_b=app_names[j],
                merge_score=pair_assessment.merge_score,
                shared_tables=len(shared),
                recommendation=pair_assessment.recommendation,
            )
            result.pairwise_scores.append(ps)
            if pair_assessment.merge_score >= 30:
                adjacency[i].add(j)
                adjacency[j].add(i)

    # 3. Find connected components (merge clusters) via BFS
    visited = set()
    cluster_id = 0
    for start in range(n):
        if start in visited:
            continue
        if not adjacency[start]:
            # Isolated app
            result.isolated_apps.append(app_names[start])
            visited.add(start)
            continue

        # BFS
        cluster_indices = []
        queue = [start]
        while queue:
            node = queue.pop(0)
            if node in visited:
                continue
            visited.add(node)
            cluster_indices.append(node)
            for neighbor in adjacency[node]:
                if neighbor not in visited:
                    queue.append(neighbor)

        if len(cluster_indices) < 2:
            result.isolated_apps.append(app_names[cluster_indices[0]])
            continue

        # Build cluster assessment
        cluster_wb_names = [app_names[i] for i in cluster_indices]
        cluster_extracted = [all_extracted[i] for i in cluster_indices]
        cluster_assessment = assess_merge(cluster_extracted, cluster_wb_names)

        # Collect shared table names
        shared_names = sorted({
            mc.table_name for mc in cluster_assessment.merge_candidates
        })

        # Average pairwise score within cluster
        pair_scores = []
        for ps in result.pairwise_scores:
            if ps.wb_a in cluster_wb_names and ps.wb_b in cluster_wb_names:
                pair_scores.append(ps.merge_score)
        avg = int(sum(pair_scores) / len(pair_scores)) if pair_scores else 0

        cluster = MergeCluster(
            cluster_id=cluster_id,
            apps=cluster_wb_names,
            shared_tables=shared_names,
            avg_score=avg,
            recommendation=cluster_assessment.recommendation,
            assessment=cluster_assessment,
        )
        result.merge_clusters.append(cluster)
        cluster_id += 1

    return result


# ═══════════════════════════════════════════════════════════════════
#  Console output
# ═══════════════════════════════════════════════════════════════════

def print_global_summary(result: GlobalAssessment):
    """Print a formatted console summary."""
    w = 68
    print()
    print("=" * w)
    print("  Global Cross-app Assessment".center(w))
    print("=" * w)
    print(f"  apps analyzed:     {result.total_apps}")
    print(f"  Total tables:           {result.total_tables}")
    print(f"  Total measures:         {result.total_measures}")
    print(f"  Merge clusters found:   {len(result.merge_clusters)}")
    print(f"  Isolated apps:     {len(result.isolated_apps)}")
    print("-" * w)

    if result.merge_clusters:
        print()
        print("  MERGE CLUSTERS:")
        for cluster in result.merge_clusters:
            rec_label = {
                "merge": "MERGE",
                "partial": "PARTIAL",
                "separate": "SEPARATE",
            }.get(cluster.recommendation, cluster.recommendation.upper())
            print(f"    Cluster #{cluster.cluster_id + 1} "
                  f"[{rec_label}] (avg score: {cluster.avg_score}/100)")
            for wb in cluster.apps:
                print(f"      - {wb}")
            if cluster.shared_tables:
                print(f"      Shared tables: {', '.join(cluster.shared_tables)}")
            print()

    if result.isolated_apps:
        print("  ISOLATED apps (no merge candidates):")
        for wb in result.isolated_apps:
            print(f"    - {wb}")
        print()

    if result.pairwise_scores:
        print("  PAIRWISE SCORES:")
        for ps in result.pairwise_scores:
            marker = {
                "merge": "OK",
                "partial": "~~",
                "separate": "--",
            }.get(ps.recommendation, "--")
            print(f"    [{marker}] {ps.wb_a} <-> {ps.wb_b}: "
                  f"{ps.merge_score}/100 "
                  f"({ps.shared_tables} shared tables)")
        print()

    print("=" * w)
    print()


# ═══════════════════════════════════════════════════════════════════
#  HTML helpers
# ═══════════════════════════════════════════════════════════════════

def _esc(text: str) -> str:
    """HTML-escape a string."""
    return (str(text)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;"))


def _score_bg(score: int) -> str:
    """Return background color for a merge score cell."""
    if score >= 60:
        return "#d4edda"  # green tint
    if score >= 30:
        return "#fff3cd"  # yellow tint
    if score > 0:
        return "#f8d7da"  # red tint
    return "#f5f5f5"      # neutral


def _score_color(score: int) -> str:
    if score >= 60:
        return SUCCESS
    if score >= 30:
        return WARN
    return FAIL


def _rec_badge(rec: str) -> str:
    labels = {
        "merge": ("MERGE", "badge-green"),
        "partial": ("PARTIAL", "badge-yellow"),
        "separate": ("SEPARATE", "badge-red"),
    }
    text, cls = labels.get(rec, (rec.upper(), "badge-gray"))
    return f'<span class="badge {cls}">{text}</span>'


def _overlap_bar(pct: float) -> str:
    width = max(int(pct * 100), 0)
    color = SUCCESS if pct >= 0.7 else WARN if pct >= 0.4 else FAIL
    return (
        f'<span class="fidelity-bar">'
        f'<span class="fidelity-track" style="width:120px">'
        f'<span class="fidelity-fill" style="width:{width}%;background:{color}"></span></span>'
        f'<span class="fidelity-label" style="color:{color}">{width}%</span></span>'
    )


# ═══════════════════════════════════════════════════════════════════
#  HTML report generator
# ═══════════════════════════════════════════════════════════════════

def generate_global_html_report(
    result: GlobalAssessment,
    output_path: Optional[str] = None,
) -> str:
    """Generate a comprehensive HTML report for the global assessment.

    Args:
        result: GlobalAssessment from run_global_assessment().
        output_path: File path for HTML output (default: global_assessment.html).

    Returns:
        The output file path.
    """
    try:
        from powerbi_import import __version__ as tool_version
    except Exception:
        tool_version = "14.0.0"

    try:
        from powerbi_import.html_template import (
            get_report_css, get_report_js, esc as _template_esc,
        )
    except ImportError:
        from html_template import (
            get_report_css, get_report_js, esc as _template_esc,
        )

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    n = result.total_apps
    profiles = result.app_profiles
    wb_names = [p.name for p in profiles]

    # Build pairwise lookup: (a, b) → PairwiseScore
    pair_lookup: Dict[Tuple[str, str], PairwiseScore] = {}
    for ps in result.pairwise_scores:
        pair_lookup[(ps.wb_a, ps.wb_b)] = ps
        pair_lookup[(ps.wb_b, ps.wb_a)] = ps

    # ══════════════════════════════════════════════════════════
    #  HTML head — uses shared template CSS
    # ══════════════════════════════════════════════════════════
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Global Assessment — Merge Analysis</title>
<style>{get_report_css()}</style>
</head>
<body>
<div class="report-header">
    <h1>Global Assessment — Cross-app Merge Analysis</h1>
    <div class="subtitle">{n} apps analyzed</div>
    <div class="meta">
        <span>&#128197; {now}</span>
        <span>&#9881; v{_esc(tool_version)}</span>
    </div>
</div>
<div class="container">
"""

    # ══════════════════════════════════════════════════════════
    # 1. EXECUTIVE SUMMARY
    # ══════════════════════════════════════════════════════════
    merge_count = len(result.merge_clusters)
    iso_count = len(result.isolated_apps)
    clustered_count = sum(len(c.apps) for c in result.merge_clusters)

    html += """
<div class="section-header" onclick="toggleSection('exec')">
    <span class="section-icon">&#128200;</span>
    <h2>Executive Summary</h2>
    <span class="toggle-arrow" id="exec-arrow">&#9660;</span>
</div>
<div class="section-body" id="exec">
"""
    html += '<div class="stat-grid">'
    html += f'<div class="stat-card accent-blue"><div class="stat-value">{n}</div><div class="stat-label">apps</div></div>'
    html += f'<div class="stat-card accent-blue"><div class="stat-value">{result.total_tables}</div><div class="stat-label">Total Tables</div></div>'
    html += f'<div class="stat-card accent-purple"><div class="stat-value">{result.total_measures}</div><div class="stat-label">Total Measures</div></div>'
    html += f'<div class="stat-card accent-success"><div class="stat-value">{merge_count}</div><div class="stat-label">Merge Clusters</div></div>'
    html += f'<div class="stat-card accent-success"><div class="stat-value">{clustered_count}</div><div class="stat-label">apps in Clusters</div></div>'
    html += f'<div class="stat-card"><div class="stat-value">{iso_count}</div><div class="stat-label">Isolated apps</div></div>'
    html += '</div>'
    # Recommendation summary
    if merge_count:
        html += '<div class="card" style="margin-top:15px">'
        html += '<h3>Recommended Actions</h3><ul>'
        for cluster in result.merge_clusters:
            wbs = ", ".join(f"<strong>{_esc(w)}</strong>" for w in cluster.apps)
            html += (f'<li>{_rec_badge(cluster.recommendation)} &nbsp; '
                     f'{wbs} &nbsp; '
                     f'(score: {cluster.avg_score}/100, '
                     f'{len(cluster.shared_tables)} shared tables)</li>')
        if result.isolated_apps:
            iso_list = ", ".join(
                f"<strong>{_esc(w)}</strong>" for w in result.isolated_apps
            )
            html += (f'<li><span class="isolated-tag">STANDALONE</span> &nbsp; '
                     f'{iso_list} &nbsp; (migrate individually)</li>')
        html += '</ul></div>'
    else:
        html += ('<div class="card" style="margin-top:15px"><p>'
                 'No merge clusters detected — all apps should be '
                 'migrated individually.</p></div>')
    html += '</div>'

    # ══════════════════════════════════════════════════════════
    # 2. app INVENTORY
    # ══════════════════════════════════════════════════════════
    html += f"""
<div class="section-header" onclick="toggleSection('inv')">
    <span class="section-icon">&#128214;</span>
    <h2>app Inventory</h2>
    <span class="toggle-arrow" id="inv-arrow">&#9660;</span>
</div>
<div class="section-body" id="inv">
<div class="card">
<table>
<tr>
    <th>app</th><th>Connectors</th><th>Tables</th><th>Columns</th>
    <th>Measures</th><th>Calc Columns</th><th>Relationships</th>
    <th>Worksheets</th><th>Dashboards</th><th>Status</th>
</tr>
"""
    # Pre-compute which apps are clustered
    clustered_set = set()
    wb_cluster_map: Dict[str, int] = {}
    for cluster in result.merge_clusters:
        for wb in cluster.apps:
            clustered_set.add(wb)
            wb_cluster_map[wb] = cluster.cluster_id

    for p in profiles:
        conn_html = " ".join(
            f'<span class="connector-tag">{_esc(c)}</span>'
            for c in p.connection_types
        ) or "—"
        if p.name in clustered_set:
            cid = wb_cluster_map[p.name] + 1
            status = f'<span class="success-tag">Cluster #{cid}</span>'
        else:
            status = '<span class="isolated-tag">Standalone</span>'
        html += f"""<tr>
    <td><strong>{_esc(p.name)}</strong></td>
    <td>{conn_html}</td>
    <td>{p.tables}</td><td>{p.columns}</td>
    <td>{p.measures}</td><td>{p.calc_columns}</td>
    <td>{p.relationships}</td>
    <td>{p.worksheets}</td><td>{p.dashboards}</td>
    <td>{status}</td>
</tr>"""

    # Totals
    html += f"""<tr style="background:#e8f0fe;font-weight:bold">
    <td>TOTAL</td><td></td>
    <td>{sum(p.tables for p in profiles)}</td>
    <td>{sum(p.columns for p in profiles)}</td>
    <td>{sum(p.measures for p in profiles)}</td>
    <td>{sum(p.calc_columns for p in profiles)}</td>
    <td>{sum(p.relationships for p in profiles)}</td>
    <td>{sum(p.worksheets for p in profiles)}</td>
    <td>{sum(p.dashboards for p in profiles)}</td>
    <td></td>
</tr>"""
    html += '</table></div></div>'

    # ══════════════════════════════════════════════════════════
    # 3. PAIRWISE MERGE SCORE MATRIX
    # ══════════════════════════════════════════════════════════
    if n >= 2:
        html += f"""
<div class="section-header" onclick="toggleSection('matrix')">
    <span class="section-icon">&#127922;</span>
    <h2>Pairwise Merge Score Matrix</h2>
    <span class="toggle-arrow" id="matrix-arrow">&#9660;</span>
</div>
<div class="section-body" id="matrix">
<div class="card" style="overflow-x:auto">
<table>
<tr><th style="min-width:150px"></th>"""
        for name in wb_names:
            short = _esc(name[:18] + '..' if len(name) > 20 else name)
            html += f'<th class="matrix-cell">{short}</th>'
        html += '</tr>'

        for i, name_a in enumerate(wb_names):
            short_a = _esc(name_a[:18] + '..' if len(name_a) > 20 else name_a)
            html += f'<tr><td><strong>{short_a}</strong></td>'
            for j, name_b in enumerate(wb_names):
                if i == j:
                    html += ('<td class="matrix-cell" '
                             f'style="background:#e8f0fe;color:{PBI_BLUE}">'
                             '—</td>')
                else:
                    ps = pair_lookup.get((name_a, name_b))
                    if ps:
                        bg = _score_bg(ps.merge_score)
                        html += (f'<td class="matrix-cell" '
                                 f'style="background:{bg}" '
                                 f'title="{_esc(name_a)} &lt;-&gt; '
                                 f'{_esc(name_b)}: '
                                 f'{ps.shared_tables} shared tables">'
                                 f'{ps.merge_score}</td>')
                    else:
                        html += '<td class="matrix-cell">—</td>'
            html += '</tr>'
        html += '</table>'
        html += ('<p style="font-size:0.8em;color:#a19f9d;margin-top:8px">'
                 'Green = merge recommended (60+) &nbsp;|&nbsp; '
                 'Yellow = partial merge (30-59) &nbsp;|&nbsp; '
                 'Red = keep separate (&lt;30) &nbsp;|&nbsp; '
                 'Hover for details</p>')
        html += '</div></div>'

    # ══════════════════════════════════════════════════════════
    # 4. MERGE CLUSTERS
    # ══════════════════════════════════════════════════════════
    if result.merge_clusters:
        html += f"""
<div class="section-header" onclick="toggleSection('clusters')">
    <span class="section-icon">&#128279;</span>
    <h2>Merge Clusters</h2>
    <span class="toggle-arrow" id="clusters-arrow">&#9660;</span>
</div>
<div class="section-body" id="clusters">
"""
        for cluster in result.merge_clusters:
            border_class = cluster.recommendation
            html += f'<div class="cluster-card {border_class}">'
            html += (f'<h3 style="margin-top:0">Cluster #{cluster.cluster_id + 1} '
                     f'— {_rec_badge(cluster.recommendation)} '
                     f'&nbsp; avg score: '
                     f'<span style="color:{_score_color(cluster.avg_score)}">'
                     f'{cluster.avg_score}/100</span></h3>')

            # apps in cluster
            html += '<p><strong>apps:</strong> '
            html += " ".join(
                f'<span class="connector-tag">{_esc(w)}</span>'
                for w in cluster.apps
            )
            html += '</p>'

            # Shared tables
            if cluster.shared_tables:
                html += '<p><strong>Shared tables:</strong> '
                html += ", ".join(
                    f'<span class="success-tag">{_esc(t)}</span>'
                    for t in cluster.shared_tables
                )
                html += '</p>'

            # Command to run merge
            wbs_arg = " ".join(
                f'"{w}.qvf"' if " " in w else f"{w}.qvf"
                for w in cluster.apps
            )
            cmd = (f'python migrate.py --shared-model {wbs_arg} '
                   f'--model-name "Cluster{cluster.cluster_id + 1}Model"')
            html += f'<p style="margin-top:10px"><strong>Run:</strong></p>'
            html += f'<div class="cmd-box">{_esc(cmd)}</div>'

            # Cluster merge details (if assessment available)
            if cluster.assessment:
                a = cluster.assessment
                html += '<div style="margin-top:15px">'
                # Merge candidates table
                if a.merge_candidates:
                    html += ('<table class="detail-table">'
                             '<tr><th>Table</th><th>apps</th>'
                             '<th>Column Overlap</th>'
                             '<th>Conflicts</th></tr>')
                    for mc in a.merge_candidates:
                        wb_list = ", ".join(s[0] for s in mc.sources)
                        conflict_html = ""
                        if mc.conflicts:
                            conflict_html = "<br>".join(
                                f'<span class="danger-tag">{_esc(c)}</span>'
                                for c in mc.conflicts[:3]
                            )
                        else:
                            conflict_html = ('<span class="success-tag">'
                                             'None</span>')
                        html += (f'<tr><td><strong>{_esc(mc.table_name)}'
                                 f'</strong></td>'
                                 f'<td>{_esc(wb_list)}</td>'
                                 f'<td>{_overlap_bar(mc.column_overlap)}</td>'
                                 f'<td>{conflict_html}</td></tr>')
                    html += '</table>'

                # Measure conflicts
                if a.measure_conflicts:
                    html += '<h4 style="margin-top:12px">Measure Conflicts</h4>'
                    html += ('<table class="detail-table">'
                             '<tr><th>Measure</th><th>app</th>'
                             '<th>Formula</th></tr>')
                    for mc in a.measure_conflicts:
                        first = True
                        for wb, formula in mc.variants.items():
                            short = _esc(
                                formula[:60] + '...'
                                if len(formula) > 60 else formula
                            )
                            name_cell = (
                                f'<td rowspan="{len(mc.variants)}">'
                                f'<strong>{_esc(mc.name)}</strong><br>'
                                f'<span class="danger-tag">CONFLICT</span>'
                                f'</td>'
                            ) if first else ''
                            html += (f'<tr>{name_cell}'
                                     f'<td><span class="connector-tag">'
                                     f'{_esc(wb)}</span></td>'
                                     f'<td class="mono">{short}</td></tr>')
                            first = False
                    html += '</table>'

                # Stats line
                html += (f'<p style="font-size:0.85em;color:{PBI_GRAY};'
                         f'margin-top:10px">'
                         f'Measures deduped: {a.measure_duplicates_removed} '
                         f'&nbsp;|&nbsp; '
                         f'Relationships deduped: '
                         f'{a.relationship_duplicates_removed} '
                         f'&nbsp;|&nbsp; '
                         f'Parameters deduped: '
                         f'{a.parameter_duplicates_removed}</p>')
                html += '</div>'

            html += '</div>'  # end cluster-card

        html += '</div>'  # end clusters collapsible

    # ══════════════════════════════════════════════════════════
    # 5. ISOLATED apps
    # ══════════════════════════════════════════════════════════
    if result.isolated_apps:
        html += f"""
<div class="section-header" onclick="toggleSection('isolated')">
    <span class="section-icon">&#128683;</span>
    <h2>Isolated apps</h2>
    <span class="toggle-arrow" id="isolated-arrow">&#9660;</span>
</div>
<div class="section-body" id="isolated">
<div class="card">
<p>These apps share no tables with others and should be migrated
individually.</p>
<table class="detail-table">
<tr><th>app</th><th>Tables</th><th>Measures</th><th>Worksheets</th>
    <th>Connectors</th><th>Command</th></tr>
"""
        for wb_name in result.isolated_apps:
            p = next(
                (x for x in profiles if x.name == wb_name), None
            )
            if not p:
                continue
            conn_html = " ".join(
                f'<span class="connector-tag">{_esc(c)}</span>'
                for c in p.connection_types
            ) or "—"
            cmd = f'python migrate.py {_esc(wb_name)}.qvf'
            html += f"""<tr>
    <td><strong>{_esc(wb_name)}</strong></td>
    <td>{p.tables}</td><td>{p.measures}</td><td>{p.worksheets}</td>
    <td>{conn_html}</td>
    <td class="mono">{cmd}</td>
</tr>"""
        html += '</table></div></div>'

    # ══════════════════════════════════════════════════════════
    # 6. PAIRWISE DETAIL TABLE
    # ══════════════════════════════════════════════════════════
    if result.pairwise_scores:
        html += f"""
<div class="section-header" onclick="toggleSection('pairs')">
    <span class="section-icon">&#128295;</span>
    <h2>Pairwise Detail</h2>
    <span class="toggle-arrow" id="pairs-arrow">&#9660;</span>
</div>
<div class="section-body" id="pairs">
<div class="card">
<table>
<tr><th>app A</th><th>app B</th><th>Score</th>
    <th>Shared Tables</th><th>Recommendation</th></tr>
"""
        for ps in sorted(result.pairwise_scores,
                         key=lambda x: x.merge_score, reverse=True):
            bg = _score_bg(ps.merge_score)
            html += f"""<tr>
    <td><strong>{_esc(ps.wb_a)}</strong></td>
    <td><strong>{_esc(ps.wb_b)}</strong></td>
    <td class="matrix-cell" style="background:{bg}">{ps.merge_score}</td>
    <td>{ps.shared_tables}</td>
    <td>{_rec_badge(ps.recommendation)}</td>
</tr>"""
        html += '</table></div></div>'

    # ══════════════════════════════════════════════════════════
    # FOOTER
    # ══════════════════════════════════════════════════════════
    html += f"""
<div class="report-footer">
    Qlik &#8594; Power BI Migration Tool v{_esc(tool_version)} &nbsp;|&nbsp;
    Global Assessment generated: {now} &nbsp;|&nbsp;
    {n} apps analyzed
</div>

</div><!-- /.container -->

<script>
{get_report_js()}
</script>
</body>
</html>"""

    # ── Write output ──
    if not output_path:
        output_path = 'global_assessment.html'

    os.makedirs(os.path.dirname(os.path.abspath(output_path)) or '.', exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    logger.info("Global assessment HTML saved to %s", output_path)
    return output_path


def save_global_assessment_json(
    result: GlobalAssessment,
    output_path: str,
) -> str:
    """Save the global assessment as JSON.

    Args:
        result: GlobalAssessment to serialize.
        output_path: File path for JSON output.

    Returns:
        The output file path.
    """
    data = result.to_dict()
    data['timestamp'] = datetime.datetime.now(
        datetime.timezone.utc
    ).isoformat()

    os.makedirs(os.path.dirname(os.path.abspath(output_path)) or '.', exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    logger.info("Global assessment JSON saved to %s", output_path)
    return output_path


# ══════════════════════════════════════════════════════════════════════════════
# Sprint 88 — Enterprise Portfolio Intelligence
# ══════════════════════════════════════════════════════════════════════════════

def build_data_lineage(
    all_extracted: List[dict],
    app_names: List[str],
) -> Dict:
    """Build a cross-app data lineage graph.

    Traces: datasource → tables → calculations → visuals for each app,
    and identifies shared datasources/tables across apps.

    Returns:
        dict with 'nodes' (list) and 'edges' (list) for a directed graph.
    """
    nodes = []
    edges = []
    node_id = 0
    node_map = {}  # (type, name) -> id

    def _get_or_create(ntype, name, wb=None):
        nonlocal node_id
        key = (ntype, name)
        if key not in node_map:
            node_map[key] = node_id
            nodes.append({
                'id': node_id,
                'type': ntype,
                'name': name,
                'apps': [],
            })
            node_id += 1
        nid = node_map[key]
        if wb and wb not in nodes[nid]['apps']:
            nodes[nid]['apps'].append(wb)
        return nid

    for wb_name, ext in zip(app_names, all_extracted):
        # Datasources → tables
        for ds in ext.get('datasources', []):
            ds_name = ds.get('caption', ds.get('name', ''))
            ds_id = _get_or_create('datasource', ds_name, wb_name)
            for tbl in ds.get('tables', []):
                tbl_name = tbl.get('name', '')
                if not tbl_name:
                    continue
                tbl_id = _get_or_create('table', tbl_name, wb_name)
                edges.append({'source': ds_id, 'target': tbl_id, 'type': 'contains'})

            # Calculations
            for calc in ds.get('calculations', []):
                calc_name = calc.get('name', '')
                if not calc_name:
                    continue
                calc_id = _get_or_create('calculation', calc_name, wb_name)
                # Link to parent table if known
                for tbl in ds.get('tables', []):
                    tbl_id = node_map.get(('table', tbl.get('name', '')))
                    if tbl_id is not None:
                        edges.append({'source': tbl_id, 'target': calc_id, 'type': 'computes'})
                        break

        # Worksheets → visuals (use fields to link to tables/calculations)
        for ws in ext.get('worksheets', []):
            ws_name = ws.get('name', '')
            if not ws_name:
                continue
            vis_id = _get_or_create('visual', ws_name, wb_name)
            for fld in ws.get('fields', []):
                fld_name = fld if isinstance(fld, str) else fld.get('name', '')
                for ntype in ('calculation', 'table'):
                    src_id = node_map.get((ntype, fld_name))
                    if src_id is not None:
                        edges.append({'source': src_id, 'target': vis_id, 'type': 'displays'})
                        break

    return {'nodes': nodes, 'edges': edges}


def recommend_consolidation(
    global_result: GlobalAssessment,
) -> List[Dict]:
    """Recommend whether each app cluster should share a model or stay standalone.

    Enhances merge cluster analysis with actionable recommendations based on
    data overlap, update frequency patterns, and audience segmentation.

    Returns:
        list of recommendation dicts per cluster/isolated app.
    """
    recommendations = []

    for cluster in global_result.merge_clusters:
        score = cluster.avg_score
        wbs = cluster.apps
        shared = cluster.shared_tables

        if score >= 70:
            action = 'shared_model'
            reason = (f"High overlap ({score:.0f}%) with {len(shared)} shared tables. "
                      f"Consolidate into a single shared semantic model.")
        elif score >= 45:
            action = 'partial_merge'
            reason = (f"Moderate overlap ({score:.0f}%). Merge shared tables into "
                      f"a base model; keep app-specific tables as thin reports.")
        else:
            action = 'review'
            reason = (f"Low overlap ({score:.0f}%). Consider keeping separate "
                      f"but standardizing connection strings and naming.")

        recommendations.append({
            'apps': wbs,
            'action': action,
            'score': score,
            'shared_tables': shared,
            'reason': reason,
        })

    for wb_name in global_result.isolated_apps:
        recommendations.append({
            'apps': [wb_name],
            'action': 'standalone',
            'score': 0,
            'shared_tables': [],
            'reason': 'No overlap with other apps. Migrate independently.',
        })

    return recommendations


def plan_resource_allocation(
    server_assessment,
    team_size: int = 3,
) -> Dict:
    """Plan team allocation based on complexity and wave structure.

    Args:
        server_assessment: ServerAssessment result from server_assessment module.
        team_size: Available team members (default: 3).

    Returns:
        dict with per-wave resource allocation and timeline.
    """
    waves = server_assessment.waves if hasattr(server_assessment, 'waves') else []
    total_effort = server_assessment.total_effort_hours if hasattr(server_assessment, 'total_effort_hours') else 0

    allocation = {
        'team_size': team_size,
        'total_effort_hours': total_effort,
        'waves': [],
    }

    for wave in waves:
        w_effort = wave.total_effort if hasattr(wave, 'total_effort') else 0
        w_count = len(wave.apps) if hasattr(wave, 'apps') else 0
        # Skill mix recommendation based on wave label
        label = wave.label if hasattr(wave, 'label') else ''
        if 'complex' in label.lower():
            skills = {'dax_expert': 1, 'm_expert': 1, 'visual_designer': max(1, team_size - 2)}
        elif 'easy' in label.lower():
            skills = {'dax_expert': 0, 'm_expert': 0, 'visual_designer': team_size}
        else:
            skills = {'dax_expert': 1, 'm_expert': 0, 'visual_designer': max(1, team_size - 1)}

        # Parallel weeks: effort / (team_size * 40h/week), minimum 1 week
        weeks = max(1, round(w_effort / (team_size * 40), 1)) if team_size > 0 else 0

        allocation['waves'].append({
            'wave': wave.wave_number if hasattr(wave, 'wave_number') else 0,
            'label': label,
            'apps': w_count,
            'effort_hours': w_effort,
            'estimated_weeks': weeks,
            'skill_mix': skills,
        })

    return allocation


def generate_governance_report(
    global_result: GlobalAssessment,
    server_assessment=None,
    output_path: str = 'governance_report.html',
) -> str:
    """Generate an executive governance report (HTML).

    Combines global assessment (merge clusters, overlap) with server assessment
    (complexity, effort, waves) into a single executive summary.

    Returns:
        Path to the generated HTML file.
    """
    try:
        from powerbi_import.html_template import (
            html_open, html_close, stat_grid, stat_card, section_open,
            section_close, data_table, badge, esc,
        )
    except ImportError:
        from html_template import (
            html_open, html_close, stat_grid, stat_card, section_open,
            section_close, data_table, badge, esc,
        )

    total = global_result.total_apps
    clusters = global_result.merge_clusters
    isolated = global_result.isolated_apps

    # Build wave summary from server assessment
    total_effort = 0
    wave_data = []
    if server_assessment:
        for wave in getattr(server_assessment, 'waves', []):
            label = getattr(wave, 'label', '')
            count = len(getattr(wave, 'apps', []))
            effort = getattr(wave, 'total_effort', 0)
            total_effort += effort
            wave_data.append([
                f'Wave {getattr(wave, "wave_number", "?")}',
                esc(label), str(count), f'{effort:.1f}h',
            ])

    # Risk matrix
    green = getattr(server_assessment, 'green_count', 0) if server_assessment else 0
    yellow = getattr(server_assessment, 'yellow_count', 0) if server_assessment else 0
    red = getattr(server_assessment, 'red_count', 0) if server_assessment else 0

    now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    html = html_open('Migration Governance Report',
                     f'{total} apps analyzed', now_str)

    # Executive Summary
    html += section_open('exec-summary', 'Executive Summary')
    html += stat_grid([
        stat_card('Total apps', str(total)),
        stat_card('Merge Clusters', str(len(clusters)), accent='teal'),
        stat_card('Standalone', str(len(isolated)), accent='purple'),
        stat_card('Estimated Effort', f'{total_effort:.0f}h', accent='orange'),
    ])
    html += section_close()

    # Risk Matrix
    html += section_open('risk-matrix', 'Risk Matrix')
    risk_rows = [
        [badge('GREEN (ready)', 'green'), str(green),
         f'{green / max(total, 1) * 100:.0f}%'],
        [badge('YELLOW (review)', 'yellow'), str(yellow),
         f'{yellow / max(total, 1) * 100:.0f}%'],
        [badge('RED (complex)', 'red'), str(red),
         f'{red / max(total, 1) * 100:.0f}%'],
    ]
    html += data_table(['Status', 'Count', 'Percentage'], risk_rows)
    html += section_close()

    # Migration Waves
    html += section_open('migration-waves', 'Migration Waves')
    if wave_data:
        html += data_table(['Wave', 'Label', 'apps', 'Effort'], wave_data,
                           sortable=True)
    else:
        html += '<p>No wave data available</p>\n'
    html += section_close()

    # Model Consolidation
    html += section_open('consolidation', 'Model Consolidation')
    cluster_rows = []
    for c in clusters:
        cluster_rows.append([
            f'Cluster {c.cluster_id}',
            esc(', '.join(c.apps)),
            str(len(c.shared_tables)),
            f'{c.avg_score:.0f}',
            esc(c.recommendation),
        ])
    if cluster_rows:
        html += data_table(
            ['Cluster', 'apps', 'Shared Tables', 'Avg Score', 'Recommendation'],
            cluster_rows, sortable=True)
    else:
        html += '<p>No merge clusters detected</p>\n'
    html += section_close()

    html += html_close()

    os.makedirs(os.path.dirname(os.path.abspath(output_path)) or '.', exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    logger.info("Governance report saved to %s", output_path)
    return output_path
