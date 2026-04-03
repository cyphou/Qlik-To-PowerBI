"""
Notebook-based interactive migration API for Jupyter environments.

Provides a stateful ``MigrationSession`` class for cell-by-cell migration
control, inline DAX/M editing, visual preview, and notebook generation.

Usage in a Jupyter notebook::

    from powerbi_import.notebook_api import MigrationSession

    session = MigrationSession()
    session.load('path/to/app.twbx')
    session.assess()
    session.preview_dax()
    session.edit_dax('Total Sales', 'SUM(Sales[Amount])')
    session.generate(output_dir='/tmp/pbi_output')
    session.validate()
"""

import copy
import json
import logging
import os
import sys

logger = logging.getLogger(__name__)


class MigrationSession:
    """Stateful migration session for interactive notebook use.

    Maintains extraction results, DAX/visual overrides, and configuration
    across Jupyter cells.  Methods return plain dicts/lists so that
    ``pandas.DataFrame(result)`` works seamlessly when pandas is available.
    """

    def __init__(self):
        self._app_path = None
        self._extracted = None          # dict of 16 JSON object types
        self._converted_objects = None  # post-conversion model dict
        self._assessment = None
        self._dax_overrides = {}        # measure_name → new_formula
        self._visual_overrides = {}     # visual_name → new_visual_type
        self._config = {
            'calendar_start': 2020,
            'calendar_end': 2030,
            'culture': 'en-US',
            'mode': 'import',
            'languages': [],
            'goals': False,
        }
        self._generated_path = None
        self._validation_result = None

    # ── Loading ───────────────────────────────────────────────

    def load(self, app_path):
        """Extract a Qlik app into the session.

        Args:
            app_path: Path to ``.twb`` or ``.twbx`` file.

        Returns:
            dict: Summary of extracted objects (counts per type).
        """
        # Add extraction module to path if needed
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        extract_dir = os.path.join(base, 'Qlik_export')
        if extract_dir not in sys.path:
            sys.path.insert(0, extract_dir)

        from Qlik_export.extract_Qlik_data import QlikExtractor

        self._app_path = os.path.abspath(app_path)
        extractor = QlikExtractor(self._app_path)
        self._extracted = extractor.extract_all()

        summary = {}
        for key, value in self._extracted.items():
            if isinstance(value, list):
                summary[key] = len(value)
            elif isinstance(value, dict):
                summary[key] = len(value)
            else:
                summary[key] = 1
        logger.info("Loaded %s — %d object types extracted", app_path,
                     len(summary))
        return summary

    # ── Assessment ────────────────────────────────────────────

    def assess(self):
        """Run pre-migration assessment on extracted data.

        Returns:
            dict: Assessment report with per-category scores.
        """
        self._require_loaded()

        from powerbi_import.assessment import AssessmentReport

        report = AssessmentReport(self._extracted)
        self._assessment = report.to_dict()
        return self._assessment

    # ── DAX Preview & Editing ─────────────────────────────────

    def preview_dax(self):
        """Preview DAX conversions for all calculations.

        Returns:
            list[dict]: Per-calculation Qlik→DAX mapping with accuracy.
        """
        self._require_loaded()

        from Qlik_export.dax_converter import convert_Qlik_formula_to_dax

        calculations = self._extracted.get('calculations', [])
        datasources = self._extracted.get('datasources', [])
        # Build column_table_map from datasources
        col_table_map = {}
        for ds in datasources:
            for tbl in ds.get('tables', []):
                tname = tbl.get('name', '')
                for col in tbl.get('columns', []):
                    cname = col.get('name', '')
                    if cname:
                        col_table_map[cname] = tname

        results = []
        for calc in calculations:
            name = calc.get('name', calc.get('caption', ''))
            formula = calc.get('formula', '')
            if not formula:
                continue
            dax = convert_Qlik_formula_to_dax(
                formula, column_table_map=col_table_map
            )
            # Check for overrides
            if name in self._dax_overrides:
                dax = self._dax_overrides[name]
                status = 'overridden'
            elif any(kw in dax.lower() for kw in ('blank(', '0 /* ', 'todo', '/* no dax')):
                status = 'approximated'
            else:
                status = 'exact'

            results.append({
                'name': name,
                'Qlik_formula': formula,
                'dax_formula': dax,
                'status': status,
            })
        return results

    def list_approximated(self):
        """List all calculations with approximated or placeholder DAX.

        Returns:
            list[dict]: Measures/columns needing manual review.
        """
        previews = self.preview_dax()
        return [p for p in previews if p['status'] == 'approximated']

    def edit_dax(self, measure_name, new_formula):
        """Override a DAX formula for a specific measure or calculation.

        Args:
            measure_name: Name of the measure/calculation to override.
            new_formula: New DAX expression.
        """
        self._dax_overrides[measure_name] = new_formula
        logger.info("DAX override set: %s", measure_name)

    def clear_dax_override(self, measure_name):
        """Remove a DAX override, reverting to auto-converted formula.

        Args:
            measure_name: Name of the measure/calculation.
        """
        self._dax_overrides.pop(measure_name, None)

    def get_dax_overrides(self):
        """Return all active DAX overrides.

        Returns:
            dict: measure_name → formula.
        """
        return dict(self._dax_overrides)

    # ── M Query Preview ───────────────────────────────────────

    def preview_m(self):
        """Preview Power Query M expressions for all datasources.

        Returns:
            list[dict]: Per-table M query preview.
        """
        self._require_loaded()

        from Qlik_export.m_query_builder import generate_power_query_m

        datasources = self._extracted.get('datasources', [])
        results = []
        for ds in datasources:
            conn = ds.get('connection', ds.get('connection_map', {}))
            for tbl in ds.get('tables', []):
                tname = tbl.get('name', '')
                try:
                    m_expr = generate_power_query_m(conn, tbl)
                except Exception:
                    m_expr = f'// Failed to generate M for {tname}'
                results.append({
                    'table': tname,
                    'datasource': ds.get('name', ''),
                    'connection_type': conn.get('class', conn.get('type', 'unknown')),
                    'm_expression': m_expr,
                })
        return results

    # ── Visual Preview & Overrides ────────────────────────────

    def preview_visuals(self):
        """Preview Qlik→PBI visual type mappings.

        Returns:
            list[dict]: Per-visual mapping with data role coverage.
        """
        self._require_loaded()

        from powerbi_import.visual_generator import resolve_visual_type

        worksheets = self._extracted.get('worksheets', [])
        results = []
        for ws in worksheets:
            ws_name = ws.get('name', '')
            mark = ws.get('mark_type', ws.get('type', 'automatic'))

            # Check override
            if ws_name in self._visual_overrides:
                pbi_type = self._visual_overrides[ws_name]
                override = True
            else:
                pbi_type = resolve_visual_type(mark)
                override = False

            fields = ws.get('fields', [])
            results.append({
                'worksheet': ws_name,
                'Qlik_mark': mark,
                'pbi_visual_type': pbi_type,
                'field_count': len(fields),
                'overridden': override,
            })
        return results

    def override_visual_type(self, visual_name, new_type):
        """Override the PBI visual type for a specific worksheet.

        Args:
            visual_name: Qlik worksheet name.
            new_type: PBI visual type string (e.g., 'lineChart').
        """
        self._visual_overrides[visual_name] = new_type
        logger.info("Visual override set: %s → %s", visual_name, new_type)

    # ── Configuration ─────────────────────────────────────────

    def configure(self, **options):
        """Update migration configuration options.

        Args:
            **options: Any of calendar_start, calendar_end, culture,
                       mode, languages, goals.

        Returns:
            dict: Updated configuration.
        """
        for key, value in options.items():
            if key in self._config:
                self._config[key] = value
            else:
                logger.warning("Unknown config option: %s", key)
        return dict(self._config)

    def get_config(self):
        """Return current migration configuration."""
        return dict(self._config)

    # ── Generation ────────────────────────────────────────────

    def generate(self, output_dir=None):
        """Generate the .pbip project from extracted + overridden data.

        Args:
            output_dir: Output directory (default: temp dir).

        Returns:
            dict: Generation summary (path, table count, measure count).
        """
        self._require_loaded()

        from powerbi_import.import_to_powerbi import PowerBIImporter

        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        source_dir = os.path.join(base, 'Qlik_export')

        importer = PowerBIImporter(source_dir=source_dir)

        # Apply DAX overrides to extracted calculations
        if self._dax_overrides:
            calcs = self._extracted.get('calculations', [])
            for calc in calcs:
                name = calc.get('name', calc.get('caption', ''))
                if name in self._dax_overrides:
                    calc['_dax_override'] = self._dax_overrides[name]

        if output_dir is None:
            import tempfile
            output_dir = os.path.join(tempfile.gettempdir(), 'pbi_notebook_output')

        result = importer.import_all(
            generate_pbip=True,
            output_dir=output_dir,
            calendar_start=self._config.get('calendar_start', 2020),
            calendar_end=self._config.get('calendar_end', 2030),
            culture=self._config.get('culture', 'en-US'),
            model_mode=self._config.get('mode', 'import'),
            languages=self._config.get('languages'),
        )
        self._generated_path = output_dir

        summary = {
            'output_dir': output_dir,
            'tables': result.get('tables', 0) if isinstance(result, dict) else 0,
            'measures': result.get('measures', 0) if isinstance(result, dict) else 0,
            'pages': result.get('pages', 0) if isinstance(result, dict) else 0,
        }
        logger.info("Generated .pbip project at %s", output_dir)
        return summary

    # ── Validation ────────────────────────────────────────────

    def validate(self):
        """Validate the generated .pbip project.

        Returns:
            dict: Validation results with error/warning counts.
        """
        if not self._generated_path:
            raise RuntimeError("No project generated yet — call generate() first")

        from powerbi_import.validator import ArtifactValidator

        validator = ArtifactValidator()
        result = validator.validate_project(self._generated_path)
        self._validation_result = result
        return result

    # ── Deployment ────────────────────────────────────────────

    def deploy(self, workspace_id, refresh=False):
        """Deploy the generated project to Power BI Service.

        Args:
            workspace_id: Target PBI workspace ID.
            refresh: Trigger dataset refresh after deploy.

        Returns:
            dict: Deployment result.
        """
        if not self._generated_path:
            raise RuntimeError("No project generated yet — call generate() first")

        from powerbi_import.deploy.pbi_deployer import PBIWorkspaceDeployer

        deployer = PBIWorkspaceDeployer(workspace_id=workspace_id)
        result = deployer.deploy_project(
            self._generated_path, refresh=refresh
        )
        return result.to_dict()

    # ── Notebook Generation ───────────────────────────────────

    def generate_notebook(self, app_path, output_path=None):
        """Auto-generate a Jupyter notebook for the given app.

        Creates a pre-filled .ipynb with extraction results, assessment,
        and conversion previews.

        Args:
            app_path: Path to .twb / .twbx file.
            output_path: Output .ipynb path (default: same dir as app).

        Returns:
            str: Path to the generated notebook file.
        """
        wb_name = os.path.splitext(os.path.basename(app_path))[0]
        if output_path is None:
            output_path = os.path.join(
                os.path.dirname(os.path.abspath(app_path)),
                f'{wb_name}_migration.ipynb'
            )

        # Escape the app path for embedding in Python code
        safe_path = app_path.replace('\\', '\\\\').replace("'", "\\'")

        cells = [
            _make_markdown_cell(
                f"# Migration Notebook: {wb_name}\n\n"
                "This notebook guides you through migrating a Qlik app "
                "to Power BI using the interactive `MigrationSession` API."
            ),
            _make_code_cell(
                "from powerbi_import.notebook_api import MigrationSession\n\n"
                "session = MigrationSession()\n"
                f"summary = session.load(r'{safe_path}')\n"
                "summary"
            ),
            _make_markdown_cell("## Step 2 — Pre-Migration Assessment"),
            _make_code_cell(
                "assessment = session.assess()\n"
                "assessment"
            ),
            _make_markdown_cell(
                "## Step 3 — DAX Conversion Preview\n\n"
                "Review approximated formulas and override if needed."
            ),
            _make_code_cell(
                "dax_preview = session.preview_dax()\n"
                "# Show approximated formulas:\n"
                "approx = session.list_approximated()\n"
                "approx"
            ),
            _make_markdown_cell(
                "## Step 4 — M Query Preview\n\n"
                "Check generated Power Query M expressions."
            ),
            _make_code_cell(
                "m_preview = session.preview_m()\n"
                "m_preview"
            ),
            _make_markdown_cell(
                "## Step 5 — Visual Mapping Preview\n\n"
                "Review Qlik→PBI visual type mappings."
            ),
            _make_code_cell(
                "visuals = session.preview_visuals()\n"
                "visuals"
            ),
            _make_markdown_cell(
                "## Step 6 — Configure & Generate\n\n"
                "Adjust settings and generate the .pbip project."
            ),
            _make_code_cell(
                "session.configure(calendar_start=2020, calendar_end=2030)\n"
                "result = session.generate()\n"
                "result"
            ),
            _make_markdown_cell("## Step 7 — Validate"),
            _make_code_cell(
                "validation = session.validate()\n"
                "validation"
            ),
            _make_markdown_cell(
                "## Step 8 — Deploy (Optional)\n\n"
                "Uncomment and set your workspace ID to deploy."
            ),
            _make_code_cell(
                "# result = session.deploy(workspace_id='YOUR_WORKSPACE_ID', refresh=True)\n"
                "# result"
            ),
        ]

        notebook = {
            'nbformat': 4,
            'nbformat_minor': 5,
            'metadata': {
                'kernelspec': {
                    'display_name': 'Python 3',
                    'language': 'python',
                    'name': 'python3',
                },
                'language_info': {
                    'name': 'python',
                    'version': '3.11.0',
                },
            },
            'cells': cells,
        }

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(notebook, f, indent=1, ensure_ascii=False)

        logger.info("Generated migration notebook: %s", output_path)
        return output_path

    # ── Internals ─────────────────────────────────────────────

    def _require_loaded(self):
        """Raise if no app has been loaded."""
        if self._extracted is None:
            raise RuntimeError(
                "No app loaded — call load('path.twbx') first"
            )


# ── Notebook cell helpers ─────────────────────────────────────

def _make_markdown_cell(source):
    """Create a Jupyter markdown cell dict."""
    return {
        'cell_type': 'markdown',
        'metadata': {},
        'source': [source],
    }


def _make_code_cell(source):
    """Create a Jupyter code cell dict."""
    return {
        'cell_type': 'code',
        'metadata': {},
        'source': [source],
        'outputs': [],
        'execution_count': None,
    }
