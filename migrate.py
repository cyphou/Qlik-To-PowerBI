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
- QA pipeline:                 python migrate.py app.qvf --qa
- Deploy to PBI Service:       python migrate.py app.qvf --deploy WORKSPACE_ID
- Shared semantic model:       python migrate.py --shared-model a.json b.json
- Fabric-native output:        python migrate.py app.qvf --output-format fabric
"""

import os
import sys
import glob
import json
import logging
import argparse
import time
import shutil
import concurrent.futures
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
                   output_format='pbip', paginated=False, sample_data=None,
                   bridge_tables='none'):
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
        sample_data: Path to directory with sample data files to bundle
    """
    global _stats
    print_step(2, 2, "POWER BI PROJECT GENERATION")
    t0 = time.monotonic()

    if output_format == 'fabric':
        try:
            from powerbi_import.fabric_project_generator import generate_fabric_project
            from qlik_export.format_adapter import adapt_qlik_for_generation
            from qlik_export.extraction_orchestrator import ExtractionOrchestrator

            qlik_dir = os.path.join(os.path.dirname(__file__), 'qlik_export')
            extracted = ExtractionOrchestrator.load_intermediate_json(qlik_dir)
            adapted = adapt_qlik_for_generation(extracted)

            fabric_out = output_dir or os.path.join('artifacts', 'fabric_projects')
            name = report_name or 'FabricProject'
            result = generate_fabric_project(adapted, name, fabric_out)

            print(f"\n\u2713 Fabric project generated: {result.get('output_dir', fabric_out)}")
            for artifact_type, count in result.get('artifacts', {}).items():
                print(f"    {artifact_type}: {count}")
            _stats.pbip_path = result.get('output_dir', fabric_out)
            return True
        except Exception as e:
            logger.error(f"Fabric generation failed: {e}", exc_info=True)
            print(f"\n\u2717 Fabric generation failed: {e}")
            return False

    try:
        from powerbi_import.import_to_powerbi import PowerBIImporter

        importer = PowerBIImporter()
        importer.import_all(generate_pbip=True, report_name=report_name, output_dir=output_dir,
                            calendar_start=calendar_start, calendar_end=calendar_end,
                            culture=culture, model_mode=model_mode,
                            output_format=output_format, sample_data=sample_data,
                            bridge_tables=bridge_tables)

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


def _build_lineage_calc_map(source_basename, output_dir):
    """Build a calc_map dict from generated TMDL files for lineage tracking."""
    import re as _re
    calc_map = {}
    out_base = output_dir or os.path.join('artifacts', 'powerbi_projects', 'migrated')
    tables_dir = os.path.join(out_base, source_basename,
                              f'{source_basename}.SemanticModel',
                              'definition', 'tables')
    if not os.path.isdir(tables_dir):
        return calc_map
    for tmdl_file in os.listdir(tables_dir):
        if not tmdl_file.endswith('.tmdl'):
            continue
        fpath = os.path.join(tables_dir, tmdl_file)
        try:
            content = open(fpath, 'r', encoding='utf-8').read()
            table_name = tmdl_file.replace('.tmdl', '')
            for m in _re.finditer(r'measure\s+[\'"]?(.+?)[\'"]?\s*=', content):
                measure_name = m.group(1).strip()
                calc_map[measure_name] = {'table': table_name, 'type': 'measure'}
            for m in _re.finditer(r'column\s+[\'"]?(.+?)[\'"]?\s*=', content):
                col_name = m.group(1).strip()
                calc_map[col_name] = {'table': table_name, 'type': 'calculated_column'}
        except Exception:
            continue
    return calc_map


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
        choices=['pbip', 'tmdl', 'pbir', 'fabric'],
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

    parser.add_argument(
        '--merge',
        metavar='DIR',
        nargs='+',
        default=None,
        help='Merge multiple Qlik app exports into a shared semantic model. Provide paths to .json exports.'
    )

    parser.add_argument(
        '--assess-server',
        metavar='DIR',
        default=None,
        help='Run portfolio-level assessment on a directory of Qlik app exports (RED/YELLOW/GREEN scoring)'
    )

    # ── New CLI flags (v10 parity) ────────────────────────────

    parser.add_argument(
        '--compare',
        action='store_true',
        default=False,
        help='Generate comparison report (HTML) after migration'
    )

    parser.add_argument(
        '--no-compare',
        action='store_true',
        default=False,
        help='Disable auto-generated comparison report'
    )

    parser.add_argument(
        '--dashboard',
        action='store_true',
        default=False,
        help='Generate interactive telemetry dashboard (HTML)'
    )

    parser.add_argument(
        '--optimize-dax',
        action='store_true',
        default=False,
        help='Run DAX optimizer pass (IF→SWITCH, COALESCE, constant folding, VAR extraction)'
    )

    parser.add_argument(
        '--no-optimize-dax',
        action='store_true',
        default=False,
        help='Disable DAX optimizer (enabled by default)'
    )

    parser.add_argument(
        '--time-intelligence',
        metavar='MODE',
        choices=['auto', 'none'],
        default=None,
        help='Auto-inject Time Intelligence measures: auto (YTD, PY, YoY%%) or none'
    )

    parser.add_argument(
        '--qa',
        action='store_true',
        default=False,
        help='Run full QA pipeline: validate → auto-fix → governance → compare → qa_report.json'
    )

    parser.add_argument(
        '--governance',
        action='store_true',
        default=False,
        help='Run governance checks (naming conventions, PII detection, audit trail)'
    )

    parser.add_argument(
        '--governance-config',
        metavar='FILE',
        default=None,
        help='Path to governance rules configuration file'
    )

    parser.add_argument(
        '--monitor',
        action='store_true',
        default=False,
        help='Export metrics to monitoring systems (Azure Monitor, Prometheus, JSON)'
    )

    parser.add_argument(
        '--deploy',
        metavar='WORKSPACE_ID',
        default=None,
        help='Deploy generated .pbip to Power BI Service workspace'
    )

    parser.add_argument(
        '--deploy-refresh',
        action='store_true',
        default=False,
        help='Trigger dataset refresh after deployment'
    )

    parser.add_argument(
        '--deploy-bundle',
        metavar='WORKSPACE_ID',
        default=None,
        help='Deploy shared semantic model + thin reports as an atomic Fabric bundle'
    )

    parser.add_argument(
        '--bundle-refresh',
        action='store_true',
        default=False,
        help='Trigger dataset refresh after bundle deployment'
    )

    parser.add_argument(
        '--shared-model',
        metavar='FILE',
        nargs='+',
        default=None,
        help='Merge multiple Qlik apps into one shared semantic model with thin reports'
    )

    parser.add_argument(
        '--model-name',
        metavar='NAME',
        default='SharedModel',
        help='Name for the shared semantic model (default: SharedModel)'
    )

    parser.add_argument(
        '--assess-merge',
        action='store_true',
        default=False,
        help='Only assess merge feasibility for --shared-model (no generation)'
    )

    parser.add_argument(
        '--force-merge',
        action='store_true',
        default=False,
        help='Force merge even if merge score is below threshold'
    )

    parser.add_argument(
        '--strict-merge',
        action='store_true',
        default=False,
        help='Block generation on merge validation failures (cycles, type errors)'
    )

    parser.add_argument(
        '--merge-preview',
        action='store_true',
        default=False,
        help='Preview merge results without generating output files'
    )

    parser.add_argument(
        '--save-merge-config',
        metavar='FILE',
        default=None,
        help='Save merge decisions to a JSON config for reproducibility'
    )

    parser.add_argument(
        '--merge-config',
        metavar='FILE',
        default=None,
        help='Load previously saved merge decisions from a JSON config'
    )

    parser.add_argument(
        '--global-assess',
        action='store_true',
        default=False,
        help='Cross-app pairwise merge scoring and clustering analysis'
    )

    parser.add_argument(
        '--check-drift',
        metavar='DIR',
        default=None,
        help='Compare current extraction against a saved snapshot for schema drift detection'
    )

    parser.add_argument(
        '--sla-config',
        metavar='FILE',
        default=None,
        help='SLA compliance configuration file (max time, min fidelity thresholds)'
    )

    parser.add_argument(
        '--multi-tenant',
        metavar='FILE',
        default=None,
        help='Multi-tenant deployment template file with variable substitution'
    )

    parser.add_argument(
        '--llm-refine',
        action='store_true',
        default=False,
        help='Use LLM-assisted DAX refinement for complex conversions'
    )

    parser.add_argument(
        '--llm-provider',
        metavar='PROVIDER',
        choices=['openai', 'anthropic', 'azure'],
        default=None,
        help='LLM provider for DAX refinement: openai, anthropic, or azure'
    )

    parser.add_argument(
        '--llm-model',
        metavar='MODEL',
        default=None,
        help='LLM model name (e.g., gpt-4, claude-3-opus)'
    )

    parser.add_argument(
        '--llm-key',
        metavar='KEY',
        default=None,
        help='API key for LLM provider (or set via environment variable)'
    )

    parser.add_argument(
        '--llm-endpoint',
        metavar='URL',
        default=None,
        help='Custom LLM endpoint URL (for Azure OpenAI or self-hosted)'
    )

    parser.add_argument(
        '--llm-max-calls',
        metavar='N',
        type=int,
        default=None,
        help='Maximum number of LLM API calls per migration'
    )

    parser.add_argument(
        '--llm-dry-run',
        action='store_true',
        default=False,
        help='Preview LLM refinement suggestions without applying them'
    )

    parser.add_argument(
        '--sample-data',
        metavar='DIR',
        default=None,
        help='Directory containing sample data files (CSV) to copy into the generated project'
    )

    parser.add_argument(
        '--workers',
        metavar='N',
        type=int,
        default=None,
        help='Number of parallel workers for batch migration (default: sequential)'
    )

    parser.add_argument(
        '--parallel',
        metavar='N',
        type=int,
        default=None,
        help='Alias for --workers: number of parallel workers for batch migration'
    )

    parser.add_argument(
        '--resume',
        action='store_true',
        default=False,
        help='Resume a previously interrupted batch migration from the last checkpoint'
    )

    parser.add_argument(
        '--jsonl-log',
        metavar='FILE',
        default=None,
        help='Write structured JSONL logs to the specified file'
    )

    parser.add_argument(
        '--web-ui',
        action='store_true',
        default=False,
        help='Launch the Streamlit web migration wizard'
    )

    parser.add_argument(
        '--web-port',
        metavar='PORT',
        type=int,
        default=8501,
        help='Port for the web UI (default: 8501)'
    )

    parser.add_argument(
        '--endorse',
        metavar='LEVEL',
        choices=['promoted', 'certified'],
        default=None,
        help='Endorsement level for deployed artifacts: promoted or certified'
    )

    parser.add_argument(
        '--manifest',
        metavar='FILE',
        default=None,
        help='Write a migration manifest file listing all generated artifacts'
    )

    parser.add_argument(
        '--languages',
        metavar='LOCALES',
        default=None,
        help='Generate multi-language culture TMDL files (e.g., fr-FR,de-DE,es-ES)'
    )

    parser.add_argument(
        '--rolling',
        action='store_true',
        default=False,
        help='Enable rolling deployment (incremental update without downtime)'
    )

    parser.add_argument(
        '--consolidate',
        action='store_true',
        default=False,
        help='Auto-consolidate duplicate datasources across apps'
    )

    parser.add_argument(
        '--skip-conversion',
        action='store_true',
        default=False,
        help='Skip DAX/M conversion, reuse existing converted JSON files'
    )

    parser.add_argument(
        '--validate-data',
        action='store_true',
        default=False,
        help='Post-migration data validation (query equivalence testing)'
    )

    parser.add_argument(
        '--bridge-tables',
        metavar='MODE',
        choices=['auto', 'none'],
        default='none',
        help='Bridge table strategy for many-to-many relationships: '
             'auto (generate junction tables), none (keep native M2M). Default: none'
    )

    parser.add_argument(
        '--sync',
        action='store_true',
        default=False,
        help='Auto-deploy after incremental change detection'
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

    # ── Web UI mode ───────────────────────────────────────────
    if getattr(args, 'web_ui', False):
        try:
            from web.app import launch_app
            port = getattr(args, 'web_port', 8501)
            launch_app(port=port)
            return ExitCode.SUCCESS
        except ImportError:
            print("Web UI requires: pip install streamlit")
            return ExitCode.GENERAL_ERROR

    # ── Shared-model merge mode (superset of --merge) ─────────
    if getattr(args, 'shared_model', None):
        try:
            from powerbi_import.shared_model import SharedModelBuilder
            from powerbi_import.thin_report_generator import generate_thin_reports
            from powerbi_import.merge_assessment import generate_merge_assessment
            from qlik_export.format_adapter import adapt_qlik_for_generation
            from qlik_export.extraction_orchestrator import ExtractionOrchestrator

            print_header("SHARED SEMANTIC MODEL")
            model_name = getattr(args, 'model_name', 'SharedModel')
            apps = []
            for app_path in args.shared_model:
                if not os.path.isfile(app_path):
                    print(f"  ⚠ File not found: {app_path}")
                    continue
                qlik_dir = os.path.join(os.path.dirname(__file__), 'qlik_export')
                orchestrator = ExtractionOrchestrator(output_dir=qlik_dir)
                orchestrator.extract(app_path)
                extracted = orchestrator.get_extraction_summary_data()
                adapted = adapt_qlik_for_generation(extracted)
                app_name = os.path.splitext(os.path.basename(app_path))[0]
                apps.append({'name': app_name, 'data': adapted})
                print(f"  ✓ Loaded: {app_name}")

            if len(apps) < 2:
                print("  ✗ At least 2 apps required for shared model")
                return ExitCode.GENERAL_ERROR

            builder = SharedModelBuilder()
            # Load merge config if specified
            merge_config_file = getattr(args, 'merge_config', None)
            if merge_config_file:
                try:
                    from powerbi_import.merge_config import load_merge_config
                    mc = load_merge_config(merge_config_file)
                    builder.apply_config(mc)
                    print(f"  ✓ Merge config loaded: {merge_config_file}")
                except Exception as e:
                    print(f"  ⚠ Merge config load failed: {e}")

            for app in apps:
                builder.add_app(app['name'], app['data'])

            merge_out = args.output_dir or os.path.join('output', 'shared', model_name)

            # Assess-merge only mode
            if getattr(args, 'assess_merge', False) or getattr(args, 'merge_preview', False):
                result = builder.assess()
                assessment = generate_merge_assessment(result)
                print(f"\n  Merge Score:    {assessment.get('merge_score', 0)}/100")
                print(f"  Shared tables:  {assessment.get('shared_tables', 0)}")
                print(f"  Unique tables:  {assessment.get('unique_tables', 0)}")
                print(f"  Conflicts:      {assessment.get('conflicts', 0)}")
                return ExitCode.SUCCESS

            result = builder.build(merge_out, model_name=model_name)
            assessment = generate_merge_assessment(result)

            # Save merge config if requested
            save_config = getattr(args, 'save_merge_config', None)
            if save_config:
                try:
                    from powerbi_import.merge_config import save_merge_config
                    save_merge_config(result.get('decisions', {}), save_config)
                    print(f"  ✓ Merge config saved: {save_config}")
                except Exception as e:
                    print(f"  ⚠ Save merge config failed: {e}")

            # Generate thin reports
            thin_reports = generate_thin_reports(result, merge_out, model_name)

            print(f"\n  Model name:     {model_name}")
            print(f"  Shared tables:  {assessment.get('shared_tables', 0)}")
            print(f"  Unique tables:  {assessment.get('unique_tables', 0)}")
            print(f"  Thin reports:   {len(thin_reports)}")
            print(f"\n✓ Shared model: {merge_out}")

            # Deploy bundle if requested
            deploy_bundle_ws = getattr(args, 'deploy_bundle', None)
            if deploy_bundle_ws:
                try:
                    from powerbi_import.deploy.bundle_deployer import BundleDeployer
                    deployer = BundleDeployer(workspace_id=deploy_bundle_ws)
                    dep_result = deployer.deploy(merge_out, refresh=getattr(args, 'bundle_refresh', False))
                    print(f"  ✓ Bundle deployed to workspace: {deploy_bundle_ws}")
                except Exception as e:
                    print(f"  ✗ Bundle deployment failed: {e}")

            return ExitCode.SUCCESS
        except Exception as e:
            logger.error(f"Shared model failed: {e}", exc_info=True)
            print(f"\n✗ Shared model failed: {e}")
            return ExitCode.GENERAL_ERROR

    # ── Multi-app merge mode (legacy --merge) ─────────────────
    if args.merge:
        try:
            from powerbi_import.shared_model import SharedModelBuilder
            from powerbi_import.thin_report_generator import generate_thin_reports
            from powerbi_import.merge_assessment import generate_merge_assessment
            from qlik_export.format_adapter import adapt_qlik_for_generation
            from qlik_export.extraction_orchestrator import ExtractionOrchestrator

            print_header("MULTI-APP MERGE")
            apps = []
            for app_path in args.merge:
                if not os.path.isfile(app_path):
                    print(f"  \u26a0 File not found: {app_path}")
                    continue
                qlik_dir = os.path.join(os.path.dirname(__file__), 'qlik_export')
                orchestrator = ExtractionOrchestrator(output_dir=qlik_dir)
                orchestrator.extract(app_path)
                extracted = orchestrator.get_extraction_summary_data()
                adapted = adapt_qlik_for_generation(extracted)
                app_name = os.path.splitext(os.path.basename(app_path))[0]
                apps.append({'name': app_name, 'data': adapted})
                print(f"  \u2713 Loaded: {app_name}")

            if len(apps) < 2:
                print("  \u2717 At least 2 apps required for merge")
                return ExitCode.GENERAL_ERROR

            builder = SharedModelBuilder()
            for app in apps:
                builder.add_app(app['name'], app['data'])

            merge_out = args.output_dir or os.path.join('output', 'merged')
            result = builder.build(merge_out)
            assessment = generate_merge_assessment(result)

            print(f"\n  Shared tables:  {assessment.get('shared_tables', 0)}")
            print(f"  Unique tables:  {assessment.get('unique_tables', 0)}")
            print(f"  Thin reports:   {len(apps)}")
            print(f"\n\u2713 Merged project: {merge_out}")
            return ExitCode.SUCCESS
        except Exception as e:
            logger.error(f"Merge failed: {e}", exc_info=True)
            print(f"\n\u2717 Merge failed: {e}")
            return ExitCode.GENERAL_ERROR

    # ── Server/portfolio assessment mode ──────────────────────
    if args.assess_server:
        try:
            from powerbi_import.server_assessment import assess_portfolio

            print_header("PORTFOLIO ASSESSMENT")
            result = assess_portfolio(args.assess_server)

            print(f"  Apps analyzed:  {result.get('total_apps', 0)}")
            print(f"  GREEN:          {result.get('green', 0)}")
            print(f"  YELLOW:         {result.get('yellow', 0)}")
            print(f"  RED:            {result.get('red', 0)}")

            out_dir = args.output_dir or os.path.join('output', 'assessments')
            os.makedirs(out_dir, exist_ok=True)
            report_path = os.path.join(out_dir, 'portfolio_assessment.json')
            with open(report_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            print(f"\n\u2713 Portfolio assessment: {report_path}")

            if json_mode:
                print(json.dumps(result, indent=2, ensure_ascii=False))

            return ExitCode.SUCCESS
        except Exception as e:
            logger.error(f"Portfolio assessment failed: {e}", exc_info=True)
            print(f"\n\u2717 Assessment failed: {e}")
            return ExitCode.ASSESSMENT_FAILED

    # ── Global assessment mode (cross-app merge analysis) ─────
    if getattr(args, 'global_assess', False):
        try:
            from powerbi_import.global_assessment import run_global_assessment
            from qlik_export.format_adapter import adapt_qlik_for_generation
            from qlik_export.extraction_orchestrator import ExtractionOrchestrator

            print_header("GLOBAL ASSESSMENT \u2014 CROSS-APP MERGE ANALYSIS")

            batch_dir = getattr(args, 'batch', None)
            app_files = []
            if batch_dir and os.path.isdir(batch_dir):
                for pattern in ['*.qvf', '*.json']:
                    app_files.extend(glob.glob(os.path.join(batch_dir, pattern)))
            elif args.qlik_file:
                app_files = [args.qlik_file]

            if len(app_files) < 2:
                print("  \u2717 At least 2 apps required for global assessment")
                return ExitCode.GENERAL_ERROR

            apps = []
            for app_path in sorted(app_files):
                qlik_dir = os.path.join(os.path.dirname(__file__), 'qlik_export')
                orchestrator = ExtractionOrchestrator(output_dir=qlik_dir)
                orchestrator.extract(app_path)
                extracted = orchestrator.get_extraction_summary_data()
                adapted = adapt_qlik_for_generation(extracted)
                app_name = os.path.splitext(os.path.basename(app_path))[0]
                apps.append({'name': app_name, 'data': adapted})
                print(f"  \u2713 Analyzed: {app_name}")

            result = run_global_assessment(apps)

            out_dir = args.output_dir or os.path.join('output', 'assessments')
            os.makedirs(out_dir, exist_ok=True)
            report_path = os.path.join(out_dir, 'global_assessment.json')
            with open(report_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)

            print(f"\n  Merge clusters: {result.get('cluster_count', 0)}")
            print(f"  Total pairs:    {result.get('total_pairs', 0)}")
            print(f"\n\u2713 Global assessment: {report_path}")
            return ExitCode.SUCCESS
        except Exception as e:
            logger.error(f"Global assessment failed: {e}", exc_info=True)
            print(f"\n\u2717 Global assessment failed: {e}")
            return ExitCode.ASSESSMENT_FAILED

    # ── Schema drift detection mode ───────────────────────────
    if getattr(args, 'check_drift', None):
        try:
            from powerbi_import.schema_drift import detect_schema_drift

            print_header("SCHEMA DRIFT DETECTION")
            result = detect_schema_drift(args.check_drift)

            added = len(result.get('added_columns', []))
            removed = len(result.get('removed_columns', []))
            renamed = len(result.get('renamed_columns', []))
            print(f"  Added columns:   {added}")
            print(f"  Removed columns: {removed}")
            print(f"  Renamed columns: {renamed}")

            if added + removed + renamed == 0:
                print("\n\u2713 No schema drift detected")
            else:
                print(f"\n\u26a0 Schema drift detected: {added + removed + renamed} changes")

            return ExitCode.SUCCESS
        except Exception as e:
            logger.error(f"Schema drift detection failed: {e}", exc_info=True)
            print(f"\n\u2717 Schema drift failed: {e}")
            return ExitCode.GENERAL_ERROR

    # ── Batch migration mode ──────────────────────────────────
    if args.batch:
        workers = getattr(args, 'workers', None) or getattr(args, 'parallel', None)
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
            sample_data=getattr(args, 'sample_data', None),
            bridge_tables=getattr(args, 'bridge_tables', 'none'),
        )
        if results['generation']:
            progress.complete(f"{_stats.pages_generated} pages, {_stats.visuals_generated} visuals")
        else:
            progress.fail("Generation failed")

        # DAX optimization pass
        if results.get('generation') and not args.dry_run:
            try:
                from powerbi_import.dax_optimizer import optimize_dax
                out_base = args.output_dir or os.path.join('artifacts', 'powerbi_projects', 'migrated')
                tables_dir = os.path.join(out_base, source_basename,
                                          f'{source_basename}.SemanticModel',
                                          'definition', 'tables')
                if os.path.isdir(tables_dir):
                    import re as _re
                    optimized_count = 0
                    for tmdl_file in os.listdir(tables_dir):
                        if not tmdl_file.endswith('.tmdl'):
                            continue
                        fpath = os.path.join(tables_dir, tmdl_file)
                        content = open(fpath, 'r', encoding='utf-8').read()
                        new_content = content
                        # Find DAX expressions in measures (inline and multiline)
                        for m in _re.finditer(r'(measure\s+.+?=\s*)(.+?)(?=\n\t|\n\s*\n|\Z)', content, _re.DOTALL):
                            original = m.group(2).strip()
                            if original.startswith('```') or original.startswith('let'):
                                continue
                            opt, rules = optimize_dax(original)
                            if rules:
                                new_content = new_content.replace(original, opt, 1)
                                optimized_count += 1
                        if new_content != content:
                            with open(fpath, 'w', encoding='utf-8') as f:
                                f.write(new_content)
                    if optimized_count and not json_mode:
                        print(f"  \u2713 DAX optimizer: {optimized_count} measures optimized")
            except Exception as exc:
                logger.debug("DAX optimization skipped: %s", exc)

        # Plugin hook: post_generation
        if results.get('generation'):
            plugin_manager.call_hook('post_generation', project_dir=_stats.pbip_path)

    # ── Lineage map generation ────────────────────────────────
    if results.get('generation') and not args.dry_run:
        try:
            from powerbi_import.lineage_map import build_lineage_map
            from qlik_export.extraction_orchestrator import ExtractionOrchestrator

            qlik_dir = os.path.join(os.path.dirname(__file__), 'qlik_export')
            qlik_data = ExtractionOrchestrator.load_intermediate_json(qlik_dir)
            calc_map = _build_lineage_calc_map(source_basename, args.output_dir)
            lineage = build_lineage_map(source_basename, qlik_data, calc_map)
            out_base = args.output_dir or os.path.join('artifacts', 'powerbi_projects', 'migrated')
            lineage_path = lineage.save(os.path.join(out_base, source_basename))
            if not json_mode:
                print(f"  \u2713 Lineage map: {lineage_path} ({lineage.to_dict()['total_entries']} entries)")
        except Exception as exc:
            logger.debug("Lineage map generation skipped: %s", exc)

    # ── LLM-assisted DAX refinement ───────────────────────────
    if getattr(args, 'llm_refine', False) and results.get('generation') and not args.dry_run:
        try:
            from powerbi_import.llm_client import refine_dax_with_llm
            import re as _re

            out_base = args.output_dir or os.path.join('artifacts', 'powerbi_projects', 'migrated')
            tables_dir = os.path.join(out_base, source_basename,
                                      f'{source_basename}.SemanticModel',
                                      'definition', 'tables')
            llm_config = {
                'provider': getattr(args, 'llm_provider', None),
                'model': getattr(args, 'llm_model', None),
                'api_key': getattr(args, 'llm_key', None),
                'endpoint': getattr(args, 'llm_endpoint', None),
                'max_calls': getattr(args, 'llm_max_calls', None),
                'dry_run': getattr(args, 'llm_dry_run', False),
            }

            if os.path.isdir(tables_dir):
                refined_count = 0
                for tmdl_file in os.listdir(tables_dir):
                    if not tmdl_file.endswith('.tmdl'):
                        continue
                    fpath = os.path.join(tables_dir, tmdl_file)
                    content = open(fpath, 'r', encoding='utf-8').read()
                    new_content = content
                    for m in _re.finditer(r'(measure\s+.+?=\s*)(.+?)(?=\n\t|\n\s*\n|\Z)', content, _re.DOTALL):
                        original = m.group(2).strip()
                        if original.startswith('```') or original.startswith('let'):
                            continue
                        refined = refine_dax_with_llm(original, config=llm_config)
                        if refined and refined != original:
                            new_content = new_content.replace(original, refined, 1)
                            refined_count += 1
                    if new_content != content and not llm_config.get('dry_run'):
                        with open(fpath, 'w', encoding='utf-8') as f:
                            f.write(new_content)
                if refined_count and not json_mode:
                    mode = "preview" if llm_config.get('dry_run') else "applied"
                    print(f"  \u2713 LLM refinement: {refined_count} measures {mode}")
        except Exception as exc:
            logger.debug("LLM refinement skipped: %s", exc)

    # ── Governance checks ─────────────────────────────────────
    if getattr(args, 'governance', False) and results.get('generation') and not args.dry_run:
        try:
            from powerbi_import.governance import GovernanceAuditor
            out_base = args.output_dir or os.path.join('artifacts', 'powerbi_projects', 'migrated')
            project_dir = os.path.join(out_base, source_basename)
            auditor = GovernanceAuditor()
            gov_result = auditor.audit_project(project_dir)
            findings = gov_result.get('findings', [])
            if findings and not json_mode:
                print(f"  \u26a0 Governance: {len(findings)} finding(s)")
                for f_item in findings[:5]:
                    print(f"    \u2022 {f_item.get('message', f_item)}")
            elif not json_mode:
                print(f"  \u2713 Governance: all checks passed")
        except Exception as exc:
            logger.debug("Governance checks skipped: %s", exc)

    # ── Comparison report ─────────────────────────────────────
    if (getattr(args, 'compare', False) or not getattr(args, 'no_compare', False)) and \
       results.get('generation') and not args.dry_run:
        try:
            from powerbi_import.comparison_report import generate_comparison_report
            out_base = args.output_dir or os.path.join('artifacts', 'powerbi_projects', 'migrated')
            project_dir = os.path.join(out_base, source_basename)
            extract_dir = os.path.join(os.path.dirname(__file__), 'qlik_export')
            comp_path = generate_comparison_report(extract_dir, project_dir)
            if comp_path and not json_mode:
                print(f"  \u2713 Comparison report: {comp_path}")
        except Exception as exc:
            logger.debug("Comparison report skipped: %s", exc)

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

    # ── QA pipeline (validate → auto-fix → governance → report) ───
    qa_result = None
    if getattr(args, 'qa', False) and results.get('generation') and not args.dry_run:
        try:
            from powerbi_import.qa_pipeline import run_qa_pipeline
            out_base = args.output_dir or os.path.join('artifacts', 'powerbi_projects', 'migrated')
            project_dir = os.path.join(out_base, source_basename)
            qa_result = run_qa_pipeline(project_dir, out_base, verbose=args.verbose)
            if not json_mode:
                fixes = qa_result.get('auto_fixes', 0)
                findings = qa_result.get('governance_findings', 0)
                print(f"  \u2713 QA pipeline: {fixes} auto-fixes, {findings} governance findings")
        except Exception as exc:
            logger.debug("QA pipeline skipped: %s", exc)

    # ── Telemetry dashboard ───────────────────────────────────
    if getattr(args, 'dashboard', False) and results.get('generation') and not args.dry_run:
        try:
            from powerbi_import.telemetry_dashboard import generate_telemetry_dashboard
            out_base = args.output_dir or os.path.join('artifacts', 'powerbi_projects', 'migrated')
            dash_path = generate_telemetry_dashboard(out_base)
            if dash_path and not json_mode:
                print(f"  \u2713 Telemetry dashboard: {dash_path}")
        except Exception as exc:
            logger.debug("Telemetry dashboard skipped: %s", exc)

    # ── Monitoring export ─────────────────────────────────────
    if getattr(args, 'monitor', None) and results.get('generation') and not args.dry_run:
        try:
            from powerbi_import.monitoring import export_metrics
            out_base = args.output_dir or os.path.join('artifacts', 'powerbi_projects', 'migrated')
            export_metrics(
                format_type=args.monitor,
                output_dir=out_base,
                migration_stats={
                    'tables': _stats.tmdl_tables,
                    'measures': _stats.tmdl_measures,
                    'visuals': _stats.visuals_generated,
                    'pages': _stats.pages_generated,
                },
            )
            if not json_mode:
                print(f"  \u2713 Metrics exported: {args.monitor}")
        except Exception as exc:
            logger.debug("Monitoring export skipped: %s", exc)

    # ── Data validation (equivalence testing) ─────────────────
    if getattr(args, 'validate_data', None) and results.get('generation') and not args.dry_run:
        try:
            from powerbi_import.equivalence_tester import EquivalenceTester
            tester = EquivalenceTester()
            eq_result = tester.compare(args.validate_data)
            match_pct = eq_result.get('match_percentage', 0)
            if not json_mode:
                print(f"  \u2713 Data validation: {match_pct}% match")
        except Exception as exc:
            logger.debug("Data validation skipped: %s", exc)

    # ── Deploy to Power BI Service ────────────────────────────
    if getattr(args, 'deploy', None) and results.get('generation') and not args.dry_run:
        try:
            from powerbi_import.deploy.pbi_deployer import PBIWorkspaceDeployer
            out_base = args.output_dir or os.path.join('artifacts', 'powerbi_projects', 'migrated')
            project_dir = os.path.join(out_base, source_basename)
            deployer = PBIWorkspaceDeployer(workspace_id=args.deploy)
            deploy_result = deployer.deploy(
                project_dir,
                refresh=getattr(args, 'deploy_refresh', False),
                endorse=getattr(args, 'endorse', None),
            )
            if not json_mode:
                print(f"  \u2713 Deployed to workspace: {args.deploy}")
        except Exception as exc:
            logger.warning("Deployment failed: %s", exc)

    # ── Manifest generation ───────────────────────────────────
    if getattr(args, 'manifest', False) and results.get('generation') and not args.dry_run:
        try:
            out_base = args.output_dir or os.path.join('artifacts', 'powerbi_projects', 'migrated')
            project_dir = os.path.join(out_base, source_basename)
            manifest = {
                'version': '10.0.0',
                'app_name': source_basename,
                'generated': datetime.now().isoformat(),
                'tables': _stats.tmdl_tables,
                'measures': _stats.tmdl_measures,
                'visuals': _stats.visuals_generated,
                'pages': _stats.pages_generated,
                'artifacts': [],
            }
            # Walk project dir to list artifacts
            for root, _dirs, files in os.walk(project_dir):
                for fname in files:
                    rel = os.path.relpath(os.path.join(root, fname), project_dir)
                    manifest['artifacts'].append(rel.replace('\\', '/'))
            manifest_path = os.path.join(project_dir, 'manifest.json')
            with open(manifest_path, 'w', encoding='utf-8') as f:
                json.dump(manifest, f, indent=2, ensure_ascii=False)
            if not json_mode:
                print(f"  \u2713 Manifest: {manifest_path} ({len(manifest['artifacts'])} artifacts)")
        except Exception as exc:
            logger.debug("Manifest generation skipped: %s", exc)

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
