"""
Main script for Qlik to Power BI migration

Pipeline:
1. Extract objects from the Qlik file (.qvf or .json export) → intermediate JSON
2. Generate the Power BI project (.pbip) with TMDL model + PBIR report
3. Generate migration report with per-item fidelity tracking

Supports:
- Single file migration:      python migrate.py app.qvf
- JSON export migration:      python migrate.py export.json
- Batch migration:             python migrate.py --batch folder/
- Custom output directory:     python migrate.py app.qvf --output-dir out/
- Skip extraction:             python migrate.py app.qvf --skip-extraction
- Verbose logging:             python migrate.py app.qvf --verbose
"""

import os
import sys
import glob
import json
import logging
import argparse
import time
from datetime import datetime
from enum import IntEnum


# ── Structured exit codes ────────────────────────────────────────────

class ExitCode(IntEnum):
    """Structured exit codes for CI/CD integration."""
    SUCCESS = 0
    GENERAL_ERROR = 1
    FILE_NOT_FOUND = 2
    EXTRACTION_FAILED = 3
    GENERATION_FAILED = 4
    VALIDATION_FAILED = 5
    ASSESSMENT_FAILED = 6
    BATCH_PARTIAL_FAIL = 7
    KEYBOARD_INTERRUPT = 130


# Ensure Unicode output on Windows consoles (✓, →, ✗, etc.)
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass


# ── Structured logging setup ────────────────────────────────────────

logger = logging.getLogger('qlik_to_powerbi')


def setup_logging(verbose=False, log_file=None, quiet=False):
    """Configure structured logging.

    Args:
        verbose: If True, set DEBUG level; otherwise INFO.
        log_file: Optional path to a log file.
        quiet: If True, suppress all output except ERROR level.
    """
    if quiet:
        level = logging.ERROR
    elif verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO
    fmt = '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    datefmt = '%Y-%m-%d %H:%M:%S'

    handlers = [logging.StreamHandler(sys.stdout)]
    if log_file:
        os.makedirs(os.path.dirname(log_file) or '.', exist_ok=True)
        handlers.append(logging.FileHandler(log_file, encoding='utf-8'))

    logging.basicConfig(level=level, format=fmt, datefmt=datefmt, handlers=handlers)
    if not verbose:
        logging.getLogger('qlik_to_powerbi').setLevel(logging.INFO)


# ── Migration statistics tracker ────────────────────────────────────

class MigrationStats:
    """Tracks statistics across all pipeline steps."""

    def __init__(self):
        # Extraction
        self.app_name = ""
        self.datasources = 0
        self.dimensions = 0
        self.measures = 0
        self.visualizations = 0
        self.sheets = 0
        self.variables = 0
        self.associations = 0
        self.bookmarks = 0
        self.has_loadscript = False
        self.master_items = 0
        # Generation
        self.tmdl_tables = 0
        self.tmdl_columns = 0
        self.tmdl_measures = 0
        self.tmdl_relationships = 0
        self.tmdl_hierarchies = 0
        self.tmdl_roles = 0
        self.visuals_generated = 0
        self.pages_generated = 0
        self.theme_applied = False
        self.pbip_path = ""
        # Diagnostics
        self.warnings = []
        self.skipped = []

    def to_dict(self):
        return {k: v for k, v in self.__dict__.items()}


_stats = MigrationStats()


def print_header(text):
    """Print a formatted header."""
    print()
    print("=" * 80)
    print(text.center(80))
    print("=" * 80)
    print()


def print_step(step_num, total_steps, text):
    """Print a step indicator."""
    print(f"\n[Step {step_num}/{total_steps}] {text}")
    print("-" * 80)


# ── Step 1: Qlik Extraction ─────────────────────────────────────────

def run_extraction(qlik_file):
    """Extract objects from a .qvf or JSON export → intermediate JSON files.

    Writes the 11 Qlik intermediate JSON files to ``qlik_export/``.

    Args:
        qlik_file: Path to .qvf or .json Qlik file.

    Returns:
        bool: True if extraction succeeded.
    """
    global _stats
    print_step(1, 2, "QLIK OBJECTS EXTRACTION")
    t0 = time.monotonic()

    if not os.path.exists(qlik_file):
        logger.error(f"Qlik file not found: {qlik_file}")
        print(f"Error: Qlik file not found: {qlik_file}")
        return False

    print(f"Source file: {qlik_file}")
    _stats.app_name = os.path.splitext(os.path.basename(qlik_file))[0]

    try:
        from qlik_export.extraction_orchestrator import ExtractionOrchestrator

        # Output JSON files to qlik_export/ directory
        output_dir = os.path.join(os.path.dirname(__file__), 'qlik_export')
        orchestrator = ExtractionOrchestrator(output_dir=output_dir)
        orchestrator.extract(qlik_file)
        json_dir = orchestrator.write_intermediate_json(output_dir)

        # Collect extraction counts
        summary = orchestrator.get_extraction_summary()
        _stats.datasources = summary.get('datasources_count', 0)
        _stats.dimensions = summary.get('dimensions_count', 0)
        _stats.measures = summary.get('measures_count', 0)
        _stats.visualizations = summary.get('visualizations_count', 0)
        _stats.sheets = summary.get('sheets_count', 0)
        _stats.variables = summary.get('variables_count', 0)
        _stats.associations = summary.get('associations_count', 0)
        _stats.bookmarks = summary.get('bookmarks_count', 0)
        _stats.has_loadscript = summary.get('has_loadscript', False)
        _stats.master_items = summary.get('master_items_count', 0)

        print(f"\n  App name:       {summary.get('app_name', 'Unknown')}")
        print(f"  Datasources:    {_stats.datasources}")
        print(f"  Dimensions:     {_stats.dimensions}")
        print(f"  Measures:       {_stats.measures}")
        print(f"  Visualizations: {_stats.visualizations}")
        print(f"  Sheets:         {_stats.sheets}")
        print(f"  Variables:      {_stats.variables}")
        print(f"  Associations:   {_stats.associations}")
        print(f"  Bookmarks:      {_stats.bookmarks}")
        print(f"  Master Items:   {_stats.master_items}")
        print(f"  Load Script:    {'Yes' if _stats.has_loadscript else 'No'}")

        print(f"\n✓ Extraction completed in {time.monotonic() - t0:.1f}s — intermediate JSON in {json_dir}")
        return True

    except Exception as e:
        logger.error(f"Extraction failed: {e}", exc_info=True)
        print(f"\nError during extraction: {str(e)}")
        return False


# ── Step 2: Power BI Generation ──────────────────────────────────────

def run_generation(report_name=None, output_dir=None, calendar_start=None,
                   calendar_end=None, culture=None, model_mode='import',
                   output_format='pbip', paginated=False):
    """Generate Power BI project (.pbip) from extracted Qlik data.

    Loads the intermediate JSON from ``qlik_export/``, transforms to
    generation-layer format via the adapter, then generates .pbip.

    Args:
        report_name: Override report name (defaults to app name or 'Report')
        output_dir: Custom output directory for .pbip projects
        calendar_start: Start year for Calendar table (default: 2020)
        calendar_end: End year for Calendar table (default: 2030)
        culture: Override culture/locale for semantic model
        paginated: If True, generate paginated report layout
    """
    global _stats
    print_step(2, 2, "POWER BI PROJECT GENERATION")
    t0 = time.monotonic()

    try:
        from powerbi_import.import_to_powerbi import PowerBIImporter

        importer = PowerBIImporter()
        importer.import_all(generate_pbip=True, report_name=report_name, output_dir=output_dir,
                            calendar_start=calendar_start, calendar_end=calendar_end,
                            culture=culture, model_mode=model_mode,
                            output_format=output_format)

        # Collect generation stats from the output
        base_dir = output_dir or os.path.join('artifacts', 'powerbi_projects', 'migrated')
        project_dir = os.path.join(base_dir, report_name or 'Report')
        if not os.path.exists(project_dir):
            print(f"\n✗ No project generated (no datasources or data model)")
            return False
        if os.path.exists(project_dir):
            _stats.pbip_path = project_dir
            # Count TMDL tables, pages, visuals
            for root, dirs, files in os.walk(project_dir):
                if os.path.basename(root) == 'tables':
                    _stats.tmdl_tables = len([f for f in files if f.endswith('.tmdl')])
                if os.path.basename(root) == 'pages':
                    _stats.pages_generated = len([d for d in dirs if d.startswith('ReportSection')])
                if os.path.basename(root) == 'visuals':
                    _stats.visuals_generated += len(dirs)
                if 'QlikMigrationTheme.json' in files:
                    _stats.theme_applied = True

            # Read TMDL stats from metadata if available
            meta_path = os.path.join(project_dir, 'migration_metadata.json')
            if os.path.exists(meta_path):
                try:
                    with open(meta_path, 'r', encoding='utf-8') as f:
                        meta = json.load(f)
                    tmdl = meta.get('tmdl_stats', {})
                    _stats.tmdl_columns = tmdl.get('columns', 0)
                    _stats.tmdl_measures = tmdl.get('measures', 0)
                    _stats.tmdl_relationships = tmdl.get('relationships', 0)
                    _stats.tmdl_hierarchies = tmdl.get('hierarchies', 0)
                    _stats.tmdl_roles = tmdl.get('roles', 0)
                except Exception:
                    pass

        pages = _stats.pages_generated
        visuals = _stats.visuals_generated
        elapsed = time.monotonic() - t0
        summary_parts = []
        if pages:
            summary_parts.append(f"{pages} pages")
        if visuals:
            summary_parts.append(f"{visuals} visuals")
        detail = f" ({', '.join(summary_parts)})" if summary_parts else ""
        print(f"\n✓ Power BI project generated in {elapsed:.1f}s{detail}")
        return True

    except Exception as e:
        logger.error(f"Generation failed: {e}", exc_info=True)
        print(f"\nError during generation: {str(e)}")
        return False


# ── Step 3: Migration Report ────────────────────────────────────────

def run_migration_report(report_name, output_dir=None):
    """Generate a structured migration report with per-item fidelity tracking.

    Args:
        report_name: Name of the report
        output_dir: Custom output directory

    Returns:
        dict or None: Report summary dict, or None on failure
    """
    try:
        from powerbi_import.migration_report import MigrationReport

        report = MigrationReport(report_name)

        # Load Qlik JSON files from qlik_export/
        json_dir = os.path.join(os.path.dirname(__file__), 'qlik_export')
        _load = lambda fname: _load_json(os.path.join(json_dir, fname))

        datasources = _load('datasources.json')
        measures = _load('measures.json')
        dimensions = _load('dimensions.json')
        visualizations = _load('visualizations.json')
        variables = _load('variables.json')
        bookmarks = _load('bookmarks.json')

        # Add datasources
        if datasources:
            report.add_datasources(datasources)

        # Build calc_map from generated TMDL files
        calc_map = _build_calc_map_from_tmdl(report_name, output_dir)

        # Create calculations list from measures + dimensions
        calculations = []
        for m in measures:
            calculations.append({
                'name': m.get('name', m.get('label', '')),
                'caption': m.get('label', m.get('name', '')),
                'formula': m.get('expression', ''),
                'role': 'measure',
            })
        for d in dimensions:
            if d.get('is_calculated') or (d.get('field', '') and '(' in d.get('field', '')):
                calculations.append({
                    'name': d.get('name', d.get('label', '')),
                    'caption': d.get('label', d.get('name', '')),
                    'formula': d.get('field', ''),
                    'role': 'dimension',
                })

        if calculations:
            report.add_calculations(calculations, calc_map)

        # Add visuals as worksheets
        if visualizations:
            worksheets = []
            for viz in visualizations:
                worksheets.append({
                    'name': viz.get('title', viz.get('name', '')),
                    'chart_type': viz.get('type', ''),
                })
            report.add_visuals(worksheets)

        # Add variables as parameters
        if variables:
            params = [{'name': v.get('name', ''), 'caption': v.get('name', '')} for v in variables
                      if not v.get('name', '').startswith('$')]
            if params:
                report.add_parameters(params)

        # Save report
        reports_dir = output_dir or os.path.join('artifacts', 'powerbi_projects', 'reports')
        saved_path = report.save(reports_dir)
        logger.info(f"Migration report saved: {saved_path}")

        report.print_summary()

        return report.get_summary()

    except Exception as e:
        logger.warning(f"Migration report generation failed: {e}")
        return None


def _load_json(filepath):
    """Load a JSON file, returning empty list on failure."""
    try:
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            logger.debug("Optional JSON file not found: %s", filepath)
    except json.JSONDecodeError as e:
        logger.error("Corrupt JSON file '%s': %s", filepath, e)
    except OSError as e:
        logger.error("Cannot read JSON file '%s': %s", filepath, e)
    return []


def _build_calc_map_from_tmdl(report_name, output_dir=None):
    """Scan generated TMDL table files to build a calculation→DAX map.

    Returns:
        dict: mapping calculation name → DAX expression
    """
    import re as _re

    calc_map = {}
    base_dir = output_dir or os.path.join('artifacts', 'powerbi_projects', 'migrated')
    tables_dir = os.path.join(base_dir, report_name,
                              f'{report_name}.SemanticModel',
                              'definition', 'tables')

    if not os.path.isdir(tables_dir):
        return calc_map

    inline_pattern = _re.compile(r'(?:measure|column)\s+(.+?)\s*=\s*(.*)')
    multiline_start = _re.compile(r'(?:measure|column)\s+(.+?)\s*=\s*```\s*$')

    def _strip_quotes(name):
        name = name.strip()
        if name.startswith("'") and name.endswith("'"):
            name = name[1:-1]
        return name

    for tmdl_file in os.listdir(tables_dir):
        if not tmdl_file.endswith('.tmdl'):
            continue
        filepath = os.path.join(tables_dir, tmdl_file)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            i = 0
            while i < len(lines):
                stripped = lines[i].strip()

                m = multiline_start.match(stripped)
                if m:
                    name = _strip_quotes(m.group(1))
                    expr_lines = []
                    i += 1
                    while i < len(lines):
                        l = lines[i].strip()
                        if l == '```':
                            break
                        expr_lines.append(l)
                        i += 1
                    expression = ' '.join(expr_lines).strip()
                    if expression and not expression.startswith('let'):
                        calc_map[name] = expression
                    i += 1
                    continue

                m = inline_pattern.match(stripped)
                if m:
                    name = _strip_quotes(m.group(1))
                    expression = m.group(2).strip()
                    if expression and not expression.startswith('let'):
                        calc_map[name] = expression
                    i += 1
                    continue

                i += 1

        except Exception:
            continue

    return calc_map


# ── Batch migration ─────────────────────────────────────────────────

def run_batch_migration(batch_dir, output_dir=None, skip_extraction=False,
                        calendar_start=None, calendar_end=None, culture=None):
    """Batch migrate all .qvf/.json files in a directory.

    Args:
        batch_dir: Directory containing Qlik files
        output_dir: Custom output directory for .pbip projects
        skip_extraction: Skip extraction step
        calendar_start: Start year for Calendar table
        calendar_end: End year for Calendar table
        culture: Override culture/locale
    """
    if not os.path.isdir(batch_dir):
        print(f"Error: Batch directory not found: {batch_dir}")
        return ExitCode.GENERAL_ERROR

    # Find all Qlik files
    patterns = ['*.qvf', '*.json']
    qlik_files = []
    for pattern in patterns:
        qlik_files.extend(glob.glob(os.path.join(batch_dir, pattern)))

    if not qlik_files:
        print(f"Error: No .qvf/.json files found in {batch_dir}")
        return ExitCode.GENERAL_ERROR

    qlik_files.sort()

    print_header("QLIK TO POWER BI BATCH MIGRATION")
    print(f"  Directory:   {batch_dir}")
    print(f"  Files found: {len(qlik_files)}")
    if output_dir:
        print(f"  Output dir:  {output_dir}")
    print()

    batch_start = datetime.now()
    batch_results = {}

    for i, qlik_file in enumerate(qlik_files, 1):
        basename = os.path.splitext(os.path.basename(qlik_file))[0]
        print(f"\n{'=' * 80}")
        print(f"  [{i}/{len(qlik_files)}] Migrating: {basename}")
        print(f"{'=' * 80}")

        global _stats
        _stats = MigrationStats()

        file_results = {}

        # Step 1: Extract
        if not skip_extraction:
            file_results['extraction'] = run_extraction(qlik_file)
            if not file_results['extraction']:
                logger.warning(f"Extraction failed for {basename}, skipping")
                batch_results[basename] = {'success': False, 'error': 'extraction'}
                continue
        else:
            file_results['extraction'] = True

        # Step 2: Generate
        file_results['generation'] = run_generation(
            report_name=basename,
            output_dir=output_dir,
            calendar_start=calendar_start,
            calendar_end=calendar_end,
            culture=culture,
        )

        # Step 3: Migration report
        report_summary = None
        if file_results.get('generation'):
            report_summary = run_migration_report(
                report_name=basename,
                output_dir=output_dir,
            )

        all_ok = all(v for v in file_results.values() if v is not None)
        batch_results[basename] = {
            'success': all_ok,
            'stats': _stats.to_dict(),
            'fidelity': report_summary.get('fidelity_score') if report_summary else None,
        }

    # Batch summary
    batch_duration = datetime.now() - batch_start
    succeeded = sum(1 for r in batch_results.values() if r['success'])
    failed = len(batch_results) - succeeded

    print_header("BATCH MIGRATION SUMMARY")
    print(f"  Total files: {len(batch_results)}")
    print(f"  Succeeded:   {succeeded}")
    print(f"  Failed:      {failed}")
    print(f"  Duration:    {batch_duration}")
    print()

    for name, result in batch_results.items():
        status = "[OK]" if result['success'] else "[FAIL]"
        fidelity = result.get('fidelity')
        fid_str = f"  (fidelity: {fidelity}%)" if fidelity is not None else ""
        print(f"  {status} {name}{fid_str}")

    return ExitCode.SUCCESS if failed == 0 else ExitCode.BATCH_PARTIAL_FAIL


def _run_batch_config(args):
    """Run migrations using a JSON batch configuration file.

    The config file is a JSON array of objects::

        [
          {"file": "sales.qvf", "culture": "fr-FR"},
          {"file": "finance.json", "calendar_start": 2018}
        ]
    """
    config_path = args.batch_config
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            entries = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Error: Cannot load batch config: {exc}")
        return ExitCode.GENERAL_ERROR

    if not isinstance(entries, list):
        print("Error: Batch config must be a JSON array of objects")
        return ExitCode.GENERAL_ERROR

    config_dir = os.path.dirname(os.path.abspath(config_path))

    print_header("QLIK TO POWER BI BATCH-CONFIG MIGRATION")
    print(f"  Config file:  {config_path}")
    print(f"  Entries:      {len(entries)}")
    print()

    global _stats
    batch_start = datetime.now()
    results = {}

    for i, entry in enumerate(entries, 1):
        raw_file = entry.get('file', '')
        if not raw_file:
            print(f"  [{i}/{len(entries)}] SKIP — missing 'file' key")
            continue

        qlik_file = raw_file if os.path.isabs(raw_file) else os.path.join(config_dir, raw_file)
        if not os.path.isfile(qlik_file):
            print(f"  [{i}/{len(entries)}] SKIP — file not found: {raw_file}")
            results[raw_file] = {'success': False, 'error': 'file_not_found'}
            continue

        basename = os.path.splitext(os.path.basename(qlik_file))[0]
        print(f"\n{'=' * 80}")
        print(f"  [{i}/{len(entries)}] Migrating: {basename}")
        print(f"{'=' * 80}")

        _stats = MigrationStats()

        skip = entry.get('skip_extraction', args.skip_extraction)
        out_dir = entry.get('output_dir', args.output_dir)
        cal_start = entry.get('calendar_start', args.calendar_start)
        cal_end = entry.get('calendar_end', args.calendar_end)
        culture = entry.get('culture', args.culture)
        paginated = entry.get('paginated', getattr(args, 'paginated', False))

        file_results = {}

        if not skip:
            file_results['extraction'] = run_extraction(qlik_file)
            if not file_results['extraction']:
                results[basename] = {'success': False, 'error': 'extraction'}
                continue
        else:
            file_results['extraction'] = True

        file_results['generation'] = run_generation(
            report_name=basename,
            output_dir=out_dir,
            calendar_start=cal_start,
            calendar_end=cal_end,
            culture=culture,
            paginated=paginated,
        )

        report_summary = None
        if file_results.get('generation'):
            report_summary = run_migration_report(report_name=basename, output_dir=out_dir)

        all_ok = all(v for v in file_results.values() if v is not None)
        results[basename] = {
            'success': all_ok,
            'stats': _stats.to_dict(),
            'fidelity': report_summary.get('fidelity_score') if report_summary else None,
        }

    batch_duration = datetime.now() - batch_start
    succeeded = sum(1 for r in results.values() if r.get('success'))
    failed = len(results) - succeeded

    print_header("BATCH-CONFIG MIGRATION SUMMARY")
    print(f"  Total entries: {len(results)}")
    print(f"  Succeeded:     {succeeded}")
    print(f"  Failed:        {failed}")
    print(f"  Duration:      {batch_duration}")
    print()
    for name, res in results.items():
        status = "[OK]" if res.get('success') else "[FAIL]"
        fid = res.get('fidelity')
        fid_str = f"  (fidelity: {fid}%)" if fid is not None else ""
        print(f"  {status} {name}{fid_str}")

    return ExitCode.SUCCESS if failed == 0 else ExitCode.BATCH_PARTIAL_FAIL


# ── Main entry point ────────────────────────────────────────────────

def main():
    """Main entry point."""

    parser = argparse.ArgumentParser(
        description='Migrate a Qlik Sense application to a Power BI project (.pbip)'
    )

    parser.add_argument(
        'qlik_file',
        nargs='?',
        default=None,
        help='Path to the Qlik file (.qvf or .json export)'
    )

    parser.add_argument(
        '--skip-extraction',
        action='store_true',
        help='Skip extraction (use existing intermediate JSON in qlik_export/)'
    )

    parser.add_argument(
        '--wizard',
        action='store_true',
        default=False,
        help='Launch the interactive migration wizard'
    )

    parser.add_argument(
        '--output-dir',
        metavar='DIR',
        default=None,
        help='Custom output directory for generated .pbip projects (default: artifacts/powerbi_projects/)'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose (DEBUG) logging'
    )

    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Suppress all output except errors (useful for scripted/CI usage)'
    )

    parser.add_argument(
        '--log-file',
        metavar='FILE',
        default=None,
        help='Write logs to a file in addition to console'
    )

    parser.add_argument(
        '--batch',
        metavar='DIR',
        default=None,
        help='Batch migrate all .qvf/.json files in the specified directory'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview migration without writing any files (extraction + analysis only)'
    )

    parser.add_argument(
        '--calendar-start',
        metavar='YEAR',
        type=int,
        default=None,
        help='Start year for the auto-generated Calendar table (default: 2020)'
    )

    parser.add_argument(
        '--calendar-end',
        metavar='YEAR',
        type=int,
        default=None,
        help='End year for the auto-generated Calendar table (default: 2030)'
    )

    parser.add_argument(
        '--culture',
        metavar='LOCALE',
        default=None,
        help='Override culture/locale for the semantic model (e.g., fr-FR, de-DE). Default: en-US'
    )

    parser.add_argument(
        '--assess',
        action='store_true',
        help='Run pre-migration assessment after extraction (no generation)'
    )

    parser.add_argument(
        '--mode',
        choices=['import', 'directquery', 'composite'],
        default='import',
        help='Semantic model mode: import (default), directquery, or composite'
    )

    parser.add_argument(
        '--rollback',
        action='store_true',
        help='Backup existing .pbip project before overwriting'
    )

    parser.add_argument(
        '--output-format',
        choices=['pbip', 'tmdl', 'pbir'],
        default='pbip',
        help='Output format: pbip (default, full project), tmdl (semantic model only), pbir (report only)'
    )

    parser.add_argument(
        '--config',
        metavar='FILE',
        default=None,
        help='Path to a JSON configuration file (CLI args override config file values)'
    )

    parser.add_argument(
        '--incremental',
        metavar='DIR',
        default=None,
        help='Path to an existing .pbip project — merge changes incrementally, preserving manual edits'
    )

    parser.add_argument(
        '--telemetry',
        action='store_true',
        default=False,
        help='Enable anonymous usage telemetry (opt-in, no PII collected)'
    )

    parser.add_argument(
        '--paginated',
        action='store_true',
        default=False,
        help='Generate a paginated report layout alongside the interactive report'
    )

    parser.add_argument(
        '--batch-config',
        metavar='FILE',
        default=None,
        help=(
            'Path to a JSON batch configuration file. '
            'Example: [{"file": "sales.qvf", "culture": "fr-FR"}]'
        )
    )

    parser.add_argument(
        '--validate',
        action='store_true',
        default=False,
        help='Run post-generation TMDL/schema validation on the output .pbip project'
    )

    parser.add_argument(
        '--json',
        action='store_true',
        default=False,
        help='Output machine-parseable JSON result to stdout (suppresses human-readable output)'
    )

    parser.add_argument(
        '--plugins',
        metavar='SPEC',
        nargs='*',
        default=None,
        help='Plugin module paths to load (e.g., my_module.MyPlugin)'
    )

    args = parser.parse_args()

    # Load configuration file if specified (CLI args take precedence)
    if args.config:
        try:
            from powerbi_import.config.migration_config import load_config
            config = load_config(filepath=args.config, args=args)
            if not args.qlik_file and getattr(config, 'source_file', None):
                args.qlik_file = config.source_file
            if not args.output_dir and config.output_dir:
                args.output_dir = config.output_dir
            if args.mode == 'import' and config.model_mode != 'import':
                args.mode = config.model_mode
            if not args.culture and config.culture != 'en-US':
                args.culture = config.culture
            if args.calendar_start is None and config.calendar_start != 2020:
                args.calendar_start = config.calendar_start
            if args.calendar_end is None and config.calendar_end != 2030:
                args.calendar_end = config.calendar_end
            if args.output_format == 'pbip' and config.output_format != 'pbip':
                args.output_format = config.output_format
            if not args.rollback and config.rollback:
                args.rollback = True
            if not args.verbose and config.verbose:
                args.verbose = True
            if not args.log_file and config.log_file:
                args.log_file = config.log_file
            logger.info(f"Configuration loaded from: {args.config}")
        except Exception as e:
            print(f"Warning: Failed to load config file: {e}")

    # ── Interactive wizard mode ───────────────────────────────
    if getattr(args, 'wizard', False):
        from powerbi_import.wizard import run_wizard, wizard_to_args
        config = run_wizard()
        if config is None:
            return ExitCode.SUCCESS
        args = wizard_to_args(config)

    # Setup structured logging
    json_mode = getattr(args, 'json', False)
    setup_logging(verbose=args.verbose, log_file=args.log_file,
                  quiet=getattr(args, 'quiet', False) or json_mode)

    # ── Plugin system initialization ──────────────────────────
    from powerbi_import.plugins import get_plugin_manager, reset_plugin_manager
    plugin_manager = reset_plugin_manager()
    plugin_specs = getattr(args, 'plugins', None)
    if plugin_specs:
        plugin_manager.load_from_config(plugin_specs)
        if not json_mode:
            count = len(plugin_manager.plugins)
            if count:
                print(f"  Plugins loaded: {count}")

    # ── Batch-config migration mode ───────────────────────────
    if args.batch_config:
        return _run_batch_config(args)

    # ── Batch migration mode ──────────────────────────────────
    if args.batch:
        return run_batch_migration(
            batch_dir=args.batch,
            output_dir=args.output_dir,
            skip_extraction=args.skip_extraction,
            calendar_start=args.calendar_start,
            calendar_end=args.calendar_end,
            culture=args.culture,
        )

    # ── Single file migration ─────────────────────────────────
    if not args.qlik_file:
        parser.error('qlik_file is required (or use --batch DIR)')

    if not json_mode:
        print_header("QLIK TO POWER BI MIGRATION")
        print(f"Source file: {args.qlik_file}")
        if args.output_dir:
            print(f"Output dir:  {args.output_dir}")
        if args.dry_run:
            print(f"Mode:        DRY RUN (no files will be written)")
        if args.calendar_start or args.calendar_end:
            cal_start = args.calendar_start or 2020
            cal_end = args.calendar_end or 2030
            print(f"Calendar:    {cal_start}-{cal_end}")
        if args.culture:
            print(f"Culture:     {args.culture}")
        if args.mode and args.mode != 'import':
            print(f"Mode:        {args.mode}")
        if args.output_format and args.output_format != 'pbip':
            print(f"Format:      {args.output_format}")
        if args.rollback:
            print(f"Rollback:    enabled")
        if getattr(args, 'telemetry', False):
            print(f"Telemetry:   enabled")
        print()

    start_time = datetime.now()
    results = {}

    # Initialize progress tracker
    from powerbi_import.progress import MigrationProgress, NullProgress
    step_count = 2 + (1 if getattr(args, 'validate', False) else 0)
    progress = MigrationProgress(total_steps=step_count, show_bar=not json_mode) if not json_mode else NullProgress()

    # Initialize telemetry (opt-in)
    telemetry = None
    if getattr(args, 'telemetry', False):
        try:
            from powerbi_import.telemetry import TelemetryCollector
            telemetry = TelemetryCollector(enabled=True)
            telemetry.start()
        except Exception:
            pass

    # Plugin hook: pre_extraction
    plugin_manager.call_hook('pre_extraction', source_file=args.qlik_file)

    # Step 1: Extraction
    if not args.skip_extraction:
        progress.start("Extracting Qlik objects")
        results['extraction'] = run_extraction(args.qlik_file)
        if not results['extraction']:
            progress.fail("Extraction failed")
            if not json_mode:
                print("\nMigration aborted due to extraction failure")
            return ExitCode.EXTRACTION_FAILED
        progress.complete(f"{_stats.datasources} datasources, {_stats.visualizations} visuals")
    else:
        progress.skip("Extraction", "Using existing intermediate JSON")
        if not json_mode:
            print("\nExtraction skipped (using existing intermediate JSON)")
        results['extraction'] = True

    # Plugin hook: post_extraction
    plugin_manager.call_hook('post_extraction', extracted_data={})

    # Step 1b: Assessment (optional)
    if args.assess and results.get('extraction'):
        try:
            from powerbi_import.assessment import run_assessment, print_assessment_report, save_assessment_report
            from powerbi_import.strategy_advisor import recommend_strategy, print_recommendation

            # Load Qlik data for assessment
            qlik_dir = os.path.join(os.path.dirname(__file__), 'qlik_export')
            from qlik_export.format_adapter import adapt_qlik_for_generation
            from qlik_export.extraction_orchestrator import ExtractionOrchestrator

            extracted = ExtractionOrchestrator.load_intermediate_json(qlik_dir)
            adapted = adapt_qlik_for_generation(extracted)

            source_basename = os.path.splitext(os.path.basename(args.qlik_file))[0]
            report = run_assessment(adapted, app_name=source_basename)
            print_assessment_report(report)

            out_dir = args.output_dir or os.path.join('artifacts', 'powerbi_projects', 'assessments')
            os.makedirs(out_dir, exist_ok=True)
            source_basename = os.path.splitext(os.path.basename(args.qlik_file))[0]
            assess_path = os.path.join(out_dir, f'assessment_{source_basename}.json')
            save_assessment_report(report, assess_path)
            print(f"\n  Assessment saved to: {assess_path}")

            rec = recommend_strategy(adapted, prep_flow=False)
            print_recommendation(rec)

            print("\n✓ Assessment complete (no generation performed)")
            return ExitCode.SUCCESS
        except Exception as e:
            logger.error(f"Assessment failed: {e}")
            print(f"\n✗ Assessment failed: {e}")
            return ExitCode.ASSESSMENT_FAILED

    # Step 2: Generate .pbip project
    source_basename = os.path.splitext(os.path.basename(args.qlik_file))[0]

    # Rollback: backup existing output if requested
    if args.rollback and not args.dry_run:
        out_base = args.output_dir or os.path.join('artifacts', 'powerbi_projects', 'migrated')
        existing_dir = os.path.join(out_base, source_basename)
        if os.path.exists(existing_dir):
            import shutil
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_dir = existing_dir + f'.backup_{ts}'
            shutil.copytree(existing_dir, backup_dir)
            logger.info(f"Rollback backup created: {backup_dir}")
            print(f"  Rollback backup: {backup_dir}")

    if args.dry_run:
        if not json_mode:
            print("\n[DRY RUN] Skipping generation — would produce:")
            print(f"  Report:  {source_basename}")
            out_dir = args.output_dir or os.path.join('artifacts', 'powerbi_projects', 'migrated')
            print(f"  Output:  {os.path.join(out_dir, source_basename)}")
        results['generation'] = True
    else:
        # Plugin hook: pre_generation
        plugin_manager.call_hook('pre_generation', converted_objects={})

        progress.start("Generating Power BI project")
        results['generation'] = run_generation(
            report_name=source_basename,
            output_dir=args.output_dir,
            calendar_start=args.calendar_start,
            calendar_end=args.calendar_end,
            culture=args.culture,
            model_mode=args.mode,
            output_format=args.output_format,
            paginated=getattr(args, 'paginated', False),
        )
        if results['generation']:
            progress.complete(f"{_stats.pages_generated} pages, {_stats.visuals_generated} visuals")
            # Plugin hook: post_generation
            plugin_manager.call_hook('post_generation', project_dir=_stats.pbip_path)
        else:
            progress.fail("Generation failed")

    # Step 3: Incremental merge (optional)
    if getattr(args, 'incremental', None) and results.get('generation'):
        try:
            from powerbi_import.incremental import IncrementalMerger
            out_dir = args.output_dir or os.path.join('artifacts', 'powerbi_projects', 'migrated')
            generated_dir = os.path.join(out_dir, source_basename)
            existing_dir = args.incremental
            if os.path.isdir(existing_dir) and os.path.isdir(generated_dir):
                print_header("INCREMENTAL MERGE")
                merge_stats = IncrementalMerger.merge(
                    existing_dir=existing_dir,
                    incoming_dir=generated_dir,
                    output_dir=generated_dir,
                )
                print(f"  Added: {merge_stats['added']}")
                print(f"  Merged: {merge_stats['merged']}")
                print(f"  Removed: {merge_stats['removed']}")
                print(f"  Preserved: {merge_stats['preserved']}")
                if merge_stats['conflicts']:
                    print(f"  Conflicts: {len(merge_stats['conflicts'])}")
                    for c in merge_stats['conflicts']:
                        print(f"    ⚠ {c}")
            else:
                print(f"  ⚠ Incremental merge skipped: directory not found")
        except Exception as exc:
            print(f"  ⚠ Incremental merge failed: {exc}")

    # Step 4: Post-generation validation (optional)
    if getattr(args, 'validate', False) and results.get('generation') and not args.dry_run:
        try:
            from powerbi_import.validator import ArtifactValidator
            out_base = args.output_dir or os.path.join('artifacts', 'powerbi_projects', 'migrated')
            project_dir = os.path.join(out_base, source_basename)
            print_step(3, 3, "POST-GENERATION VALIDATION")
            vresult = ArtifactValidator.validate_project(project_dir)
            results['validation'] = vresult.get('valid', False)
            if vresult.get('errors'):
                for err in vresult['errors']:
                    print(f"    ✗ {err}")
            if vresult.get('warnings'):
                for w in vresult['warnings'][:10]:
                    print(f"    ⚠ {w}")
                remaining = len(vresult['warnings']) - 10
                if remaining > 0:
                    print(f"    ... and {remaining} more warnings")
            if vresult.get('valid'):
                print(f"    ✓ Validation passed ({vresult.get('files_checked', 0)} files checked)")
            else:
                print(f"    ✗ Validation failed — {len(vresult.get('errors', []))} error(s)")
        except Exception as exc:
            logger.warning("Validation failed: %s", exc)
            results['validation'] = False

    # Step 5: Migration report
    report_summary = None
    if results.get('generation'):
        report_summary = run_migration_report(
            report_name=source_basename,
            output_dir=args.output_dir,
        )

    # Step 6: HTML Dashboard
    html_dashboard_path = None
    if results.get('generation') and not args.dry_run:
        try:
            from generate_report import generate_dashboard
            out_base = args.output_dir or os.path.join('artifacts', 'powerbi_projects', 'migrated')
            html_dashboard_path = generate_dashboard(
                report_name=source_basename,
                output_dir=out_base,
                migration_report_path=None,
                metadata_path=None,
            )
            if html_dashboard_path and not json_mode:
                print(f"  Dashboard: {html_dashboard_path}")
        except Exception as exc:
            logger.warning("HTML dashboard generation failed: %s", exc)

    # ── Final summary ────────────────────────────────────────
    duration = datetime.now() - start_time
    all_success = all(v for v in results.values() if v is not None)

    # ── JSON output mode ──────────────────────────────────────
    if json_mode:
        json_result = {
            "status": "success" if all_success else "error",
            "input": args.qlik_file,
            "output_dir": _stats.pbip_path or "",
            "tables": _stats.tmdl_tables,
            "measures": _stats.tmdl_measures,
            "visuals": _stats.visuals_generated,
            "pages": _stats.pages_generated,
            "warnings": _stats.warnings,
            "duration_seconds": round(duration.total_seconds(), 2),
        }
        if report_summary:
            json_result["fidelity_score"] = report_summary.get('fidelity_score', 0)
            json_result["exact"] = report_summary.get('exact', 0)
            json_result["approximate"] = report_summary.get('approximate', 0)
            json_result["unsupported"] = report_summary.get('unsupported', 0)
        print(json.dumps(json_result, indent=2, ensure_ascii=False))

        # Finalize telemetry
        if telemetry:
            try:
                telemetry.record_stats(
                    success=all_success,
                    extraction=bool(results.get('extraction')),
                    generation=bool(results.get('generation')),
                )
                telemetry.finish()
                telemetry.save()
                telemetry.send()
            except Exception:
                pass

        return ExitCode.SUCCESS if all_success else ExitCode.GENERAL_ERROR

    # ── Human-readable summary ────────────────────────────────
    print_header("MIGRATION SUMMARY")

    # Step results
    print("  Step Results:")
    for step_name, success in [
        ("Qlik Extraction", results.get('extraction', False)),
        ("Power BI Generation", results.get('generation', False)),
        ("Validation", results.get('validation', None)),
        ("Migration Report", report_summary is not None if results.get('generation') else None),
    ]:
        if success is None:
            continue
        status = "✓ Success" if success else "✗ Failed"
        print(f"    {step_name:<30} {status}")

    # Extraction summary
    if results.get('extraction'):
        print(f"\n  Extraction Summary ({_stats.app_name}):")
        extraction_items = [
            ("Datasources", _stats.datasources),
            ("Dimensions", _stats.dimensions),
            ("Measures", _stats.measures),
            ("Visualizations", _stats.visualizations),
            ("Sheets", _stats.sheets),
            ("Variables", _stats.variables),
            ("Associations", _stats.associations),
            ("Bookmarks", _stats.bookmarks),
            ("Master Items", _stats.master_items),
        ]
        for label, count in extraction_items:
            if count > 0:
                print(f"    {label:<30} {count}")
        if _stats.has_loadscript:
            print(f"    {'Load Script':<30} Yes")

    # Generation summary
    if results.get('generation'):
        print(f"\n  Generation Summary:")
        gen_items = [
            ("TMDL Tables", _stats.tmdl_tables),
            ("TMDL Columns", _stats.tmdl_columns),
            ("DAX Measures", _stats.tmdl_measures),
            ("Relationships", _stats.tmdl_relationships),
            ("Hierarchies", _stats.tmdl_hierarchies),
            ("RLS Roles", _stats.tmdl_roles),
            ("Report Pages", _stats.pages_generated),
            ("Visuals", _stats.visuals_generated),
        ]
        for label, count in gen_items:
            if count > 0:
                print(f"    {label:<30} {count}")
        if _stats.theme_applied:
            print(f"    {'Custom Theme':<30} ✓ Applied")

    # Fidelity score from migration report
    if report_summary:
        fidelity = report_summary.get('fidelity_score', 0)
        total = report_summary.get('total_items', 0)
        exact = report_summary.get('exact', 0)
        approx = report_summary.get('approximate', 0)
        unsup = report_summary.get('unsupported', 0)
        print(f"\n  Migration Fidelity:")
        print(f"    {'Fidelity Score':<30} {fidelity}%")
        print(f"    {'Exact Conversions':<30} {exact}/{total}")
        if approx:
            print(f"    {'Approximate':<30} {approx}")
        if unsup:
            print(f"    {'Unsupported':<30} {unsup}")

    # Warnings
    if _stats.warnings:
        print(f"\n  Warnings ({len(_stats.warnings)}):")
        for w in _stats.warnings[:10]:
            print(f"    ⚠ {w}")
        if len(_stats.warnings) > 10:
            print(f"    ... and {len(_stats.warnings) - 10} more")

    # Skipped items
    if _stats.skipped:
        print(f"\n  Skipped ({len(_stats.skipped)}):")
        for s in _stats.skipped[:5]:
            print(f"    → {s}")

    print(f"\n  Duration: {duration.total_seconds():.1f}s")

    all_success = all(v for v in results.values() if v is not None)

    if all_success:
        if _stats.pbip_path:
            print(f"\n✓ Migration complete in {duration.total_seconds():.1f}s → {_stats.pbip_path}")
        else:
            print(f"\n✓ Migration complete in {duration.total_seconds():.1f}s")
        if html_dashboard_path:
            print(f"\n  HTML Dashboard: {html_dashboard_path}")
        print("\n  Next steps:")
        print("    1. Open the .pbip file in Power BI Desktop (Developer Mode)")
        print("    2. Configure data sources in Power Query Editor")
        print("    3. Verify DAX measures and calculated columns")
        print("    4. Check relationships in the Model view")
        print("    5. Compare visuals with the original Qlik application")
    else:
        print("\n✗ Migration completed with errors")

    # Finalize telemetry
    if telemetry:
        try:
            telemetry.record_stats(
                success=all_success,
                extraction=bool(results.get('extraction')),
                generation=bool(results.get('generation')),
            )
            telemetry.finish()
            telemetry.save()
            telemetry.send()
        except Exception:
            pass

    return ExitCode.SUCCESS if all_success else ExitCode.GENERAL_ERROR


if __name__ == '__main__':
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\nMigration interrupted by user")
        sys.exit(ExitCode.KEYBOARD_INTERRUPT)
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
        print(f"\n\nFatal error: {str(e)}")
        sys.exit(ExitCode.GENERAL_ERROR)
