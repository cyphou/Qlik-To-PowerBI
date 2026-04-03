"""
Merge Assessment Reporter — JSON + console output for shared semantic model merging.

Generates a detailed assessment report showing:
- Merge candidates (shared tables) with column overlap
- Measure conflicts and deduplication stats
- Relationship and parameter deduplication
- Merge score and recommendation

Usage::

    from powerbi_import.merge_assessment import generate_merge_report, print_merge_summary
    from powerbi_import.shared_model import assess_merge

    assessment = assess_merge(all_extracted, app_names)
    print_merge_summary(assessment)
    generate_merge_report(assessment, output_path="merge_assessment.json")
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

try:
    from powerbi_import.shared_model import MergeAssessment
except ImportError:
    from shared_model import MergeAssessment

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

# HTML report colors
_PBI_BLUE = "#0078d4"
_PBI_DARK = "#323130"
_PBI_BG = "#f5f5f5"
_GREEN = "#107c10"
_YELLOW = "#ffb900"
_RED = "#d13438"


def generate_merge_report(assessment: MergeAssessment,
                          output_path: str = None) -> dict:
    """Generate a detailed merge assessment report.

    Args:
        assessment: The MergeAssessment from assess_merge().
        output_path: Optional file path to write merge_assessment.json.

    Returns:
        The report dict.
    """
    report = assessment.to_dict()
    report['timestamp'] = datetime.now(timezone.utc).isoformat()

    if output_path:
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        logger.info("Merge assessment saved to %s", output_path)

    return report


def print_merge_summary(assessment: MergeAssessment):
    """Print a formatted console summary of the merge assessment."""
    w = 64  # Box width

    print()
    print("=" * w)
    print("  Shared Semantic Model — Merge Assessment".center(w))
    print("=" * w)

    # Overview
    tables_saved = assessment.total_tables - assessment.unique_table_count
    pct = int(tables_saved / max(assessment.total_tables, 1) * 100)
    print(f"  apps analyzed:           {len(assessment.apps)}")
    print(f"  Total tables found:           {assessment.total_tables}")
    print(f"  Unique tables (after merge):  {assessment.unique_table_count}")
    print(f"  Tables saved by merging:      {tables_saved} ({pct}%)")
    print("-" * w)

    # Merge candidates
    if assessment.merge_candidates:
        print("  MERGE CANDIDATES (same connection + table name):")
        print()
        for mc in assessment.merge_candidates:
            wb_count = len(mc.sources)
            wb_total = len(assessment.apps)
            overlap_pct = int(mc.column_overlap * 100)
            marker = "OK" if overlap_pct >= 70 else "WARN"
            print(f"    [{marker}] {mc.table_name:<20} — "
                  f"found in {wb_count}/{wb_total} apps "
                  f"({overlap_pct}% col match)")
            if mc.conflicts:
                for c in mc.conflicts[:3]:
                    print(f"         ! {c}")
        print()

    # Measure conflicts
    if assessment.measure_conflicts:
        print("  MEASURE CONFLICTS:")
        print()
        for mc in assessment.measure_conflicts:
            print(f"    ! [{mc.name}] — different DAX in "
                  f"{', '.join(mc.variants.keys())}")
            for wb, formula in mc.variants.items():
                short = formula[:60] + '...' if len(formula) > 60 else formula
                print(f"      {wb}: {short}")
            print(f"      -> Will create [{mc.name} (app)] per variant")
        print()

    # Unique tables — split into linked and isolated
    if assessment.unique_tables:
        # Show linked unique tables (will be included in merged model)
        if assessment.linked_unique_tables:
            print("  LINKED UNIQUE TABLES (included in shared model):")
            for wb, tables in assessment.linked_unique_tables.items():
                for t in tables:
                    print(f"    ✓ {t:<25} — only in {wb}, but linked to shared tables")
            print()

        # Show isolated tables (will NOT be included in merged model)
        if assessment.isolated_tables:
            print("  ISOLATED TABLES (excluded from shared model — no links):")
            for wb, tables in assessment.isolated_tables.items():
                for t in tables:
                    print(f"    ✗ {t:<25} — only in {wb}, no relationships to other tables")
            print()

    # Stats
    print("-" * w)
    total_measures = (
        assessment.measure_duplicates_removed + len(assessment.measure_conflicts)
    )
    print(f"  MEASURES:       {total_measures} shared, "
          f"{assessment.measure_duplicates_removed} duplicates removed, "
          f"{len(assessment.measure_conflicts)} conflicts")
    print(f"  RELATIONSHIPS:  {assessment.relationship_duplicates_removed} "
          f"duplicates removed")
    print(f"  PARAMETERS:     {assessment.parameter_duplicates_removed} "
          f"duplicates removed, "
          f"{len(assessment.parameter_conflicts)} conflicts")

    # Recommendation
    print("-" * w)
    rec_labels = {
        "merge": "MERGE RECOMMENDED",
        "partial": "PARTIAL MERGE (review conflicts)",
        "separate": "KEEP SEPARATE (low overlap)",
    }
    rec = rec_labels.get(assessment.recommendation, assessment.recommendation)
    print(f"  Merge score:      {assessment.merge_score}/100")
    print(f"  Recommendation:   {rec}")
    print("=" * w)
    print()


def generate_merge_html_report(
    assessment: MergeAssessment,
    output_path: str = "merge_assessment.html",
    rls_conflicts: list = None,
    relationship_suggestions: list = None,
) -> str:
    """Generate an HTML merge assessment report.

    Args:
        assessment: MergeAssessment result.
        output_path: Path to write the HTML file.
        rls_conflicts: Optional list of RLS conflicts from detect_rls_conflicts().
        relationship_suggestions: Optional list from suggest_cross_app_relationships().

    Returns:
        Path to the generated HTML file.
    """
    rls_conflicts = rls_conflicts or []
    relationship_suggestions = relationship_suggestions or []

    score = assessment.merge_score
    tables_saved = assessment.total_tables - assessment.unique_table_count
    rec_labels = {
        "merge": "MERGE RECOMMENDED",
        "partial": "PARTIAL MERGE (review conflicts)",
        "separate": "KEEP SEPARATE (low overlap)",
    }
    rec = rec_labels.get(assessment.recommendation, assessment.recommendation)

    html = html_open('Shared Semantic Model — Merge Assessment',
                     f'apps: {", ".join(assessment.apps)}')

    # Summary stats
    score_level = 'green' if score >= 60 else ('yellow' if score >= 30 else 'red')
    html += stat_grid([
        stat_card('Merge Score', f'{score}/100', accent=score_level),
        stat_card('Total Tables', str(assessment.total_tables)),
        stat_card('Tables Saved', str(tables_saved), accent='green'),
        stat_card('Measure Conflicts', str(len(assessment.measure_conflicts)),
                  accent='orange' if assessment.measure_conflicts else None),
        stat_card('Recommendation', rec),
    ])

    # Merge Candidates
    html += section_open('candidates', 'Merge Candidates')
    if assessment.merge_candidates:
        rows = []
        for mc in assessment.merge_candidates:
            overlap_pct = int(mc.column_overlap * 100)
            color_cls = 'green' if overlap_pct >= 70 else ('yellow' if overlap_pct >= 40 else 'red')
            sources = esc(", ".join(s[0] for s in mc.sources))
            conflicts_html = "<br>".join(esc(c) for c in mc.conflicts[:3]) if mc.conflicts else "None"
            rows.append([
                esc(mc.table_name), sources,
                badge(f'{overlap_pct}%', color_cls),
                conflicts_html,
            ])
        html += data_table(['Table', 'apps', 'Column Overlap', 'Conflicts'],
                           rows, sortable=True)
    else:
        html += '<p>No merge candidates found</p>\n'
    html += section_close()

    # Measure Conflicts
    html += section_open('measure-conflicts', 'Measure Conflicts')
    if assessment.measure_conflicts:
        rows = []
        for mc in assessment.measure_conflicts:
            for wb, formula in mc.variants.items():
                short = formula[:80] + '...' if len(formula) > 80 else formula
                rows.append([esc(mc.name), esc(wb), f'<code>{esc(short)}</code>'])
        html += data_table(['Measure', 'app', 'Formula'], rows, sortable=True)
    else:
        html += '<p>No measure conflicts</p>\n'
    html += section_close()

    # RLS Conflicts
    html += section_open('rls-conflicts', 'RLS Conflicts')
    if rls_conflicts:
        rows = []
        for rc in rls_conflicts:
            for wb, expr in rc.get('variants', {}).items():
                short = str(expr)[:80] + '...' if len(str(expr)) > 80 else str(expr)
                rows.append([
                    esc(rc.get('role_name', 'N/A')),
                    esc(rc.get('table', 'N/A')),
                    esc(wb),
                    f'<code>{esc(short)}</code>',
                ])
        html += data_table(['Role', 'Table', 'app', 'Expression'], rows, sortable=True)
    else:
        html += '<p>No RLS conflicts detected</p>\n'
    html += section_close()

    # Suggested Relationships
    html += section_open('rel-suggestions', 'Suggested Relationships')
    if relationship_suggestions:
        rows = []
        for rs in relationship_suggestions:
            conf_level = 'green' if rs.get('confidence') == 'high' else 'yellow'
            rows.append([
                esc(rs.get('from_table', '')),
                esc(rs.get('from_column', '')),
                esc(rs.get('to_table', '')),
                esc(rs.get('to_column', '')),
                badge(rs.get('confidence', 'medium'), conf_level),
            ])
        html += data_table(['From Table', 'From Column', 'To Table', 'To Column', 'Confidence'],
                           rows, sortable=True)
    else:
        html += '<p>No relationship suggestions</p>\n'
    html += section_close()

    html += html_close()

    os.makedirs(os.path.dirname(os.path.abspath(output_path)) or '.', exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    logger.info("Merge HTML report saved to %s", output_path)
    return output_path


# ═══════════════════════════════════════════════════════════════════
#  Manifest diff — compare two merge manifests
# ═══════════════════════════════════════════════════════════════════

def diff_manifests(old: dict, new: dict) -> dict:
    """Compare two merge manifests and return a structured diff.

    Both *old* and *new* can be either ``MergeManifest.to_dict()`` dicts
    or ``MergeManifest`` instances (with a ``.to_dict()`` method).

    Returns:
        Dict with keys: ``added_tables``, ``removed_tables``,
        ``added_measures``, ``removed_measures``,
        ``added_apps``, ``removed_apps``,
        ``changed_relationships``, ``config_changes``.
    """
    if hasattr(old, 'to_dict'):
        old = old.to_dict()
    if hasattr(new, 'to_dict'):
        new = new.to_dict()

    old_tables = set(old.get('table_fingerprints', {}).keys())
    new_tables = set(new.get('table_fingerprints', {}).keys())

    old_wb_names = {wb.get('name', '') for wb in old.get('apps', [])}
    new_wb_names = {wb.get('name', '') for wb in new.get('apps', [])}

    # Collect all measures across apps
    old_measures = set()
    for wb in old.get('apps', []):
        old_measures.update(wb.get('measures', []))
    new_measures = set()
    for wb in new.get('apps', []):
        new_measures.update(wb.get('measures', []))

    # Relationship count change
    old_rels = old.get('artifact_counts', {}).get('relationships', 0)
    new_rels = new.get('artifact_counts', {}).get('relationships', 0)

    # Config changes
    old_config = old.get('merge_config_snapshot', {})
    new_config = new.get('merge_config_snapshot', {})
    config_changes = {}
    all_keys = set(list(old_config.keys()) + list(new_config.keys()))
    for key in all_keys:
        ov = old_config.get(key)
        nv = new_config.get(key)
        if ov != nv:
            config_changes[key] = {'old': ov, 'new': nv}

    return {
        'added_tables': sorted(new_tables - old_tables),
        'removed_tables': sorted(old_tables - new_tables),
        'added_measures': sorted(new_measures - old_measures),
        'removed_measures': sorted(old_measures - new_measures),
        'added_apps': sorted(new_wb_names - old_wb_names),
        'removed_apps': sorted(old_wb_names - new_wb_names),
        'relationship_count_change': new_rels - old_rels,
        'config_changes': config_changes,
        'old_score': old.get('merge_score', 0),
        'new_score': new.get('merge_score', 0),
    }
