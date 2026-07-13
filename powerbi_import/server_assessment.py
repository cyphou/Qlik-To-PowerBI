"""
Server-Level Assessment Pipeline — Portfolio Assessment for Qlik Sense
or local folder of apps.

Produces enterprise-grade readiness reports including:
- Per-app RED/YELLOW/GREEN classification
- Connector census (histogram of datasource types)
- Complexity heatmap (5 axes)
- Migration wave planning (grouping by shared data + complexity)
- Effort estimation (hours per app)
- Executive HTML dashboard report

Usage (CLI)::

    python migrate.py --bulk-assess folder_of_twbx/
    python migrate.py --server https://Qlik.company.com --server-assess

Usage (programmatic)::

    from powerbi_import.server_assessment import (
        ServerAssessment, run_server_assessment, generate_server_html_report
    )

    result = run_server_assessment(all_extracted_list, app_names)
    generate_server_html_report(result, "server_assessment.html")
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

try:
    from powerbi_import.assessment import run_assessment, AssessmentReport
except ImportError:
    from assessment import run_assessment, AssessmentReport


# ═══════════════════════════════════════════════════════════════════
#  Constants
# ═══════════════════════════════════════════════════════════════════

PBI_BLUE = "#0078d4"
PBI_DARK = "#323130"
PBI_GRAY = "#605e5c"
PBI_BG = "#f5f5f5"
GREEN = "#107c10"
YELLOW = "#ffb900"
RED = "#d13438"

# Effort estimation weights (hours per unit)
_EFFORT_PER_VISUAL = 0.15
_EFFORT_PER_CALC = 0.2
_EFFORT_PER_LOD = 0.5
_EFFORT_PER_TABLE_CALC = 0.4
_EFFORT_PER_DATASOURCE = 0.3
_EFFORT_PER_TABLE = 0.1
_EFFORT_BASE_HOURS = 1.0  # Base overhead per app


# ═══════════════════════════════════════════════════════════════════
#  Data classes
# ═══════════════════════════════════════════════════════════════════

@dataclass
class WorkbookReadiness:
    """Per-app readiness result."""
    name: str
    status: str  # "GREEN", "YELLOW", "RED"
    pass_count: int = 0
    warn_count: int = 0
    fail_count: int = 0
    info_count: int = 0
    complexity: Dict[str, int] = field(default_factory=dict)
    effort_hours: float = 0.0
    connector_types: List[str] = field(default_factory=list)
    visual_count: int = 0
    calc_count: int = 0
    table_count: int = 0
    assessment_report: Optional[object] = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "status": self.status,
            "pass_count": self.pass_count,
            "warn_count": self.warn_count,
            "fail_count": self.fail_count,
            "info_count": self.info_count,
            "complexity": self.complexity,
            "effort_hours": round(self.effort_hours, 1),
            "connector_types": self.connector_types,
            "visual_count": self.visual_count,
            "calc_count": self.calc_count,
            "table_count": self.table_count,
        }


@dataclass
class MigrationWave:
    """A group of apps to migrate together."""
    wave_number: int
    label: str  # "Easy", "Medium", "Complex"
    apps: List[str] = field(default_factory=list)
    total_effort: float = 0.0

    def to_dict(self) -> dict:
        return {
            "wave_number": self.wave_number,
            "label": self.label,
            "apps": self.apps,
            "total_effort": round(self.total_effort, 1),
        }


@dataclass
class ServerAssessment:
    """Complete server-level assessment result."""
    app_results: List[WorkbookReadiness] = field(default_factory=list)
    connector_census: Dict[str, int] = field(default_factory=dict)
    waves: List[MigrationWave] = field(default_factory=list)
    total_apps: int = 0
    green_count: int = 0
    yellow_count: int = 0
    red_count: int = 0
    total_effort_hours: float = 0.0
    timestamp: str = ""

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "total_apps": self.total_apps,
            "green_count": self.green_count,
            "yellow_count": self.yellow_count,
            "red_count": self.red_count,
            "total_effort_hours": round(self.total_effort_hours, 1),
            "app_results": [r.to_dict() for r in self.app_results],
            "connector_census": self.connector_census,
            "waves": [w.to_dict() for w in self.waves],
        }

    @property
    def readiness_pct(self) -> int:
        if self.total_apps == 0:
            return 0
        return int(self.green_count / self.total_apps * 100)


# ═══════════════════════════════════════════════════════════════════
#  Core pipeline
# ═══════════════════════════════════════════════════════════════════

def run_server_assessment(
    all_extracted: List[dict],
    app_names: List[str],
) -> ServerAssessment:
    """Run portfolio-level assessment across multiple apps.

    Args:
        all_extracted: List of extracted app dicts.
        app_names: Parallel list of app names.

    Returns:
        ServerAssessment with per-app scoring and aggregated analysis.
    """
    result = ServerAssessment(
        total_apps=len(app_names),
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

    connector_counter: Dict[str, int] = {}

    for wb_name, extracted in zip(app_names, all_extracted):
        readiness = _assess_single_app(wb_name, extracted)
        result.app_results.append(readiness)

        # Accumulate connector census
        for conn in readiness.connector_types:
            connector_counter[conn] = connector_counter.get(conn, 0) + 1

        # Accumulate totals
        if readiness.status == "GREEN":
            result.green_count += 1
        elif readiness.status == "YELLOW":
            result.yellow_count += 1
        else:
            result.red_count += 1
        result.total_effort_hours += readiness.effort_hours

    result.connector_census = dict(
        sorted(connector_counter.items(), key=lambda x: x[1], reverse=True)
    )

    # Build migration waves
    result.waves = _build_migration_waves(result.app_results)

    return result


# File-name substrings that indicate generated/intermediate JSON, not app exports
_NON_APP_JSON_MARKERS = (
    'migration_report', 'portfolio_assessment', 'assessment_',
    'lineage_map', 'migration_metadata', 'batch_report', 'merge_assessment',
    'diagramlayout', 'definition', 'version', 'page', 'visual', 'report.json',
    'pages.json', 'bookmarks', 'config.example',
)


def _discover_app_exports(directory: str, recursive: bool = False) -> List[str]:
    """Find Qlik app exports (*.json / *.qvf) in a directory.

    By default scans the directory and one sub-level. With ``recursive=True``
    it walks the entire tree — useful for enterprise Qlik-server dumps where
    binary QVF exports are nested in per-stream / per-space folders.

    Skips generated/intermediate JSON files so a folder that also contains
    migration output is still assessable.
    """
    import glob

    candidates: List[str] = []
    if recursive:
        for pattern in ('*.json', '*.qvf'):
            candidates.extend(
                glob.glob(os.path.join(directory, '**', pattern), recursive=True)
            )
    else:
        for pattern in ('*.json', '*.qvf'):
            candidates.extend(glob.glob(os.path.join(directory, pattern)))
            candidates.extend(glob.glob(os.path.join(directory, '*', pattern)))

    # Directory segments that mark generated migration output (skip in recursive)
    _GEN_DIR_MARKERS = (
        os.sep + 'definition' + os.sep,
        '.semanticmodel' + os.sep,
        '.report' + os.sep,
        os.sep + 'power_query' + os.sep,
    )

    app_files: List[str] = []
    for path in sorted(set(candidates)):
        base = os.path.basename(path).lower()
        low = path.lower()
        if path.lower().endswith('.json') and any(
            marker in base for marker in _NON_APP_JSON_MARKERS
        ):
            continue
        # In recursive mode, exclude files inside generated project folders.
        if recursive and any(m in low for m in _GEN_DIR_MARKERS):
            continue
        app_files.append(path)
    return app_files


def assess_portfolio(
    directory: str,
    output_dir: Optional[str] = None,
    recursive: bool = False,
) -> dict:
    """Run a portfolio-level assessment over a folder of Qlik app exports.

    Discovers every ``*.json`` / ``*.qvf`` app export in ``directory`` (and one
    sub-level, or the whole tree when ``recursive=True``), extracts and adapts
    each, runs :func:`run_server_assessment`, and — when ``output_dir`` is
    given — writes an executive HTML report.

    Args:
        directory: Folder containing Qlik app exports.
        output_dir: Optional folder to write ``portfolio_assessment.html``.
        recursive: Walk the entire directory tree (enterprise server dumps).

    Returns:
        ``ServerAssessment.to_dict()`` augmented with short CLI aliases
        (``green``/``yellow``/``red``/``readiness_pct``) and, when generated,
        an ``html_report`` path plus the list of ``apps`` / ``skipped`` files.
    """
    if not os.path.isdir(directory):
        raise ValueError(f"Not a directory: {directory}")

    try:
        from qlik_export.extraction_orchestrator import ExtractionOrchestrator
        from qlik_export.format_adapter import adapt_qlik_for_generation
    except ImportError:  # pragma: no cover - script execution context
        from extraction_orchestrator import ExtractionOrchestrator  # type: ignore
        from format_adapter import adapt_qlik_for_generation  # type: ignore

    app_files = _discover_app_exports(directory, recursive=recursive)
    if not app_files:
        raise ValueError(
            f"No Qlik app exports (*.json / *.qvf) found in {directory}"
        )

    # Extraction writes 11 intermediate JSONs; isolate them in qlik_export/.
    qlik_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'qlik_export')

    all_adapted: List[dict] = []
    app_names: List[str] = []
    skipped: List[str] = []
    for path in app_files:
        try:
            orchestrator = ExtractionOrchestrator(output_dir=qlik_dir)
            extracted = orchestrator.extract(path)
            adapted = adapt_qlik_for_generation(extracted)
            all_adapted.append(adapted)
            app_names.append(os.path.splitext(os.path.basename(path))[0])
        except Exception as exc:  # noqa: BLE001 - skip unparseable apps
            logger.warning("Skipping %s: %s", path, exc)
            skipped.append(path)

    if not all_adapted:
        raise ValueError("No apps could be extracted for assessment")

    result = run_server_assessment(all_adapted, app_names)
    data = result.to_dict()
    # Short aliases consumed by the CLI summary block.
    data['green'] = result.green_count
    data['yellow'] = result.yellow_count
    data['red'] = result.red_count
    data['readiness_pct'] = result.readiness_pct
    data['apps'] = app_names
    if skipped:
        data['skipped'] = skipped

    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        html_path = os.path.join(output_dir, 'portfolio_assessment.html')
        try:
            generate_server_html_report(result, html_path)
            data['html_report'] = html_path
        except Exception as exc:  # noqa: BLE001 - HTML is best-effort
            logger.warning("Portfolio HTML report generation failed: %s", exc)

    return data


def _assess_single_app(wb_name: str, extracted: dict) -> WorkbookReadiness:
    """Run assessment on a single app and produce readiness result."""
    report = run_assessment(extracted)

    pass_c = warn_c = fail_c = info_c = 0
    for cat in report.categories:
        for check in cat.checks:
            if check.severity == "pass":
                pass_c += 1
            elif check.severity == "warn":
                warn_c += 1
            elif check.severity == "fail":
                fail_c += 1
            else:
                info_c += 1

    # Classify status
    if fail_c == 0 and warn_c <= 2:
        status = "GREEN"
    elif fail_c <= 2:
        status = "YELLOW"
    else:
        status = "RED"

    # Extract complexity metrics
    complexity = _compute_complexity(extracted)

    # Extract connector types
    connectors = []
    for ds in extracted.get('datasources', []):
        conn = ds.get('connection', {})
        ctype = conn.get('type', 'unknown')
        if ctype and ctype not in connectors:
            connectors.append(ctype)

    # Estimate effort
    effort = _estimate_effort(extracted, complexity)

    return WorkbookReadiness(
        name=wb_name,
        status=status,
        pass_count=pass_c,
        warn_count=warn_c,
        fail_count=fail_c,
        info_count=info_c,
        complexity=complexity,
        effort_hours=effort,
        connector_types=connectors,
        visual_count=complexity.get('visuals', 0),
        calc_count=complexity.get('calculations', 0),
        table_count=complexity.get('tables', 0),
        assessment_report=report,
    )


def _compute_complexity(extracted: dict) -> Dict[str, int]:
    """Compute complexity metrics for a app."""
    visuals = len(extracted.get('worksheets', []))
    dashboards = len(extracted.get('dashboards', []))

    calc_count = len(extracted.get('calculations', []))
    for ds in extracted.get('datasources', []):
        calc_count += len(ds.get('calculations', []))

    table_count = 0
    for ds in extracted.get('datasources', []):
        table_count += sum(
            1 for t in ds.get('tables', [])
            if t.get('type', 'table') == 'table'
        )

    lod_count = 0
    table_calc_count = 0
    all_calcs = list(extracted.get('calculations', []))
    for ds in extracted.get('datasources', []):
        all_calcs.extend(ds.get('calculations', []))
    for calc in all_calcs:
        formula = calc.get('formula', '')
        if '{' in formula and any(
            kw in formula.upper() for kw in ('FIXED', 'INCLUDE', 'EXCLUDE')
        ):
            lod_count += 1
        if any(kw in formula.upper() for kw in (
            'RUNNING_', 'WINDOW_', 'RANK(', 'RANK_', 'INDEX(', 'FIRST(', 'LAST(',
        )):
            table_calc_count += 1

    filters = len(extracted.get('filters', []))
    actions = len(extracted.get('actions', []))

    return {
        'visuals': visuals,
        'dashboards': dashboards,
        'calculations': calc_count,
        'tables': table_count,
        'lod_expressions': lod_count,
        'table_calcs': table_calc_count,
        'filters': filters,
        'actions': actions,
        'parameters': len(extracted.get('parameters', [])),
        'rls_rules': len(extracted.get('user_filters', [])),
        'custom_sql': len(extracted.get('custom_sql', [])),
    }


def _estimate_effort(extracted: dict, complexity: Dict[str, int]) -> float:
    """Estimate migration effort in hours."""
    hours = _EFFORT_BASE_HOURS
    hours += complexity.get('visuals', 0) * _EFFORT_PER_VISUAL
    hours += complexity.get('calculations', 0) * _EFFORT_PER_CALC
    hours += complexity.get('lod_expressions', 0) * _EFFORT_PER_LOD
    hours += complexity.get('table_calcs', 0) * _EFFORT_PER_TABLE_CALC
    hours += complexity.get('tables', 0) * _EFFORT_PER_TABLE

    ds_count = len(extracted.get('datasources', []))
    hours += ds_count * _EFFORT_PER_DATASOURCE

    return round(hours, 1)


def _build_migration_waves(
    app_results: List[WorkbookReadiness],
) -> List[MigrationWave]:
    """Group apps into migration waves based on complexity."""
    easy = []
    medium = []
    hard = []

    for r in app_results:
        score = (
            r.complexity.get('calculations', 0) +
            r.complexity.get('lod_expressions', 0) * 3 +
            r.complexity.get('table_calcs', 0) * 2
        )
        if r.status == "GREEN" and score <= 5:
            easy.append(r)
        elif r.status == "RED" or score > 20:
            hard.append(r)
        else:
            medium.append(r)

    waves = []
    wave_num = 1
    if easy:
        waves.append(MigrationWave(
            wave_number=wave_num,
            label="Easy (quick wins)",
            apps=[r.name for r in easy],
            total_effort=sum(r.effort_hours for r in easy),
        ))
        wave_num += 1
    if medium:
        waves.append(MigrationWave(
            wave_number=wave_num,
            label="Medium (standard migration)",
            apps=[r.name for r in medium],
            total_effort=sum(r.effort_hours for r in medium),
        ))
        wave_num += 1
    if hard:
        waves.append(MigrationWave(
            wave_number=wave_num,
            label="Complex (manual review recommended)",
            apps=[r.name for r in hard],
            total_effort=sum(r.effort_hours for r in hard),
        ))

    return waves


# ═══════════════════════════════════════════════════════════════════
#  JSON output
# ═══════════════════════════════════════════════════════════════════

def save_server_assessment_json(
    assessment: ServerAssessment, output_path: str
) -> dict:
    """Save server assessment to JSON file."""
    report = assessment.to_dict()
    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    logger.info("Server assessment saved to %s", output_path)
    return report


# ═══════════════════════════════════════════════════════════════════
#  Console summary
# ═══════════════════════════════════════════════════════════════════

def print_server_summary(assessment: ServerAssessment):
    """Print a formatted console summary of the server assessment."""
    w = 70
    print()
    print("=" * w)
    print("  Qlik Sense — Portfolio Assessment".center(w))
    print("=" * w)

    print(f"  Total apps:    {assessment.total_apps}")
    print(f"  GREEN (ready):      {assessment.green_count}")
    print(f"  YELLOW (review):    {assessment.yellow_count}")
    print(f"  RED (complex):      {assessment.red_count}")
    print(f"  Readiness:          {assessment.readiness_pct}%")
    print(f"  Est. total effort:  {assessment.total_effort_hours:.1f} hours")
    print("-" * w)

    # Connector census
    if assessment.connector_census:
        print("  CONNECTOR CENSUS:")
        for conn, count in assessment.connector_census.items():
            bar = "#" * min(count, 30)
            print(f"    {conn:<20} {bar} ({count})")
        print()

    # Waves
    for wave in assessment.waves:
        print(f"  WAVE {wave.wave_number}: {wave.label}")
        for wb in wave.apps:
            print(f"    - {wb}")
        print(f"    Est. effort: {wave.total_effort:.1f} hours")
        print()

    print("=" * w)


# ═══════════════════════════════════════════════════════════════════
#  HTML report generator
# ═══════════════════════════════════════════════════════════════════

def generate_server_html_report(
    assessment: ServerAssessment,
    output_path: str = "server_assessment.html",
) -> str:
    """Generate an executive HTML dashboard report for the server assessment."""
    try:
        from powerbi_import.html_template import (
            html_open, html_close, stat_card, stat_grid, section_open,
            section_close, badge, fidelity_bar, donut_chart, bar_chart,
            data_table, esc, SUCCESS, FAIL,
        )
    except ImportError:
        from html_template import (
            html_open, html_close, stat_card, stat_grid, section_open,
            section_close, badge, fidelity_bar, donut_chart, bar_chart,
            data_table, esc, SUCCESS, FAIL,
        )

    html = html_open(
        title="Qlik Sense \u2014 Portfolio Assessment",
        subtitle=f"{assessment.total_apps} apps analyzed",
        timestamp=assessment.timestamp,
    )

    # ── Executive Summary ──────────────────────────────────────
    html += section_open("summary", "Executive Summary", "&#128200;")
    html += stat_grid([
        stat_card(assessment.total_apps, "Total apps", accent="blue"),
        stat_card(assessment.green_count, "GREEN (Ready)", accent="success"),
        stat_card(assessment.yellow_count, "YELLOW (Review)", accent="warn"),
        stat_card(assessment.red_count, "RED (Complex)", accent="fail"),
        stat_card(f"{assessment.readiness_pct}%", "Readiness", accent="blue"),
        stat_card(f"{assessment.total_effort_hours:.1f}h", "Est. Total Effort", accent="purple"),
    ])

    # Readiness donut
    html += '<div class="chart-row">'
    html += '<div class="chart-card"><h4>&#127919; Readiness Distribution</h4>'
    html += donut_chart([
        ("GREEN", assessment.green_count, SUCCESS),
        ("YELLOW", assessment.yellow_count, "#c19c00"),
        ("RED", assessment.red_count, FAIL),
    ], center_text=f"{assessment.readiness_pct}%")
    html += '</div>'

    # Connector distribution
    if assessment.connector_census:
        conn_items = [(conn, count, "#0078d4")
                      for conn, count in assessment.connector_census.items()]
        html += '<div class="chart-card"><h4>&#128268; Connector Census</h4>'
        html += bar_chart(conn_items)
        html += '</div>'

    html += '</div>'  # chart-row
    html += section_close()

    # ── Migration Waves ──────────────────────────────────────────
    if assessment.waves:
        html += section_open("waves", "Migration Waves", "&#128640;")
        wave_rows = []
        for wave in assessment.waves:
            members = ', '.join(wave.apps[:5])
            if len(wave.apps) > 5:
                members += '...'
            wave_rows.append([
                f'<strong>Wave {wave.wave_number}</strong>',
                esc(wave.label),
                str(len(wave.apps)),
                f'{wave.total_effort:.1f}h',
                esc(members),
            ])
        html += '<div class="card">'
        html += data_table(
            ["Wave", "Classification", "apps", "Effort", "Members"],
            wave_rows, "wave-tbl", sortable=True)
        html += '</div>'
        html += section_close()

    # ── app Detail ──────────────────────────────────────────
    html += section_open("detail", "app Detail", "&#128221;")
    wb_rows = []
    for r in sorted(assessment.app_results, key=lambda x: x.effort_hours, reverse=True):
        wb_rows.append([
            badge(r.status),
            f'<strong>{esc(r.name)}</strong>',
            str(r.visual_count),
            str(r.calc_count),
            str(r.table_count),
            str(r.complexity.get('lod_expressions', 0)),
            f'{r.effort_hours:.1f}h',
            ', '.join(esc(c) for c in r.connector_types) or 'N/A',
        ])
    html += '<div class="card">'
    html += data_table(
        ["Status", "app", "Visuals", "Calcs", "Tables", "LOD", "Effort", "Connectors"],
        wb_rows, "wb-detail-tbl", sortable=True, searchable=True)
    html += '</div>'
    html += section_close()

    html += html_close()

    os.makedirs(os.path.dirname(os.path.abspath(output_path)) or '.', exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    logger.info("Server assessment HTML report saved to %s", output_path)
    return output_path
