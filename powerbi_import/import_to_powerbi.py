"""
Import orchestrator for Power BI project generation.

Loads extracted Qlik JSON files, transforms them via the format adapter
into the generation-compatible ``converted_objects`` dict, then drives the
.pbip project generation pipeline (TMDL model + PBIR report).
"""

import os
import sys
import json
from datetime import datetime

try:
    from powerbi_import.pbip_generator import PowerBIProjectGenerator
except ImportError:
    from pbip_generator import PowerBIProjectGenerator


class PowerBIImporter:
    """Power BI object importer — Qlik edition.

    Reads Qlik intermediate JSON files, transforms them into the
    ``converted_objects`` format expected by the shared generation layer,
    and invokes ``PowerBIProjectGenerator``.
    """

    def __init__(self, source_dir=None):
        self.source_dir = source_dir or 'qlik_export/'

    def import_all(self, generate_pbip=True, report_name=None, output_dir=None,
                   calendar_start=None, calendar_end=None, culture=None,
                   model_mode='import', output_format='pbip', paginated=False,
                   validate=True, sample_data=None):
        """Import all extracted objects and generate Power BI project.

        Args:
            generate_pbip: If True, generates Power BI Projects (.pbip)
            report_name: Override report name (defaults to first sheet name or 'Report')
            output_dir: Custom output directory for .pbip projects
            calendar_start: Start year for Calendar table (default: 2020)
            calendar_end: End year for Calendar table (default: 2030)
            culture: Override culture/locale for semantic model
            paginated: If True, generate paginated report layout
            validate: If True, run post-generation artifact validation
            sample_data: Path to directory with sample data files to bundle
        """

        print("=" * 80)
        print("IMPORT POWER BI")
        print("=" * 80)
        print()

        # Load Qlik JSON files and transform to generation-compatible format
        converted_objects = self._load_converted_objects()

        if not converted_objects.get('datasources'):
            print(f"  [ERROR] No datasources found in {os.path.join(self.source_dir, 'datasources.json')}")
            print("     Run extraction first: python migrate.py <file>")
            return

        # Determine report name
        if not report_name:
            dashboards = converted_objects.get('dashboards', [])
            if dashboards:
                report_name = dashboards[0].get('name', 'Report')
            else:
                report_name = 'Report'

        print(f"  Report: {report_name}")
        print(f"  Datasources: {len(converted_objects.get('datasources', []))}")
        print(f"  Worksheets: {len(converted_objects.get('worksheets', []))}")
        print(f"  Calculations: {len(converted_objects.get('calculations', []))}")

        # Inject sample data directory for file bundling
        if sample_data:
            converted_objects['_sample_data_dir'] = sample_data

        # Generate Power BI Project (.pbip) directly from converted objects
        if generate_pbip:
            project_path = self.generate_powerbi_project(
                report_name, converted_objects, output_dir=output_dir,
                calendar_start=calendar_start, calendar_end=calendar_end,
                culture=culture, model_mode=model_mode,
                output_format=output_format, paginated=paginated)

            # Post-generation validation
            if validate and project_path:
                self._run_validation(project_path)

        print()
        print("=" * 80)
        print("IMPORT COMPLETE")
        print("=" * 80)
        print()
        if generate_pbip:
            print("[OK] Power BI Projects (.pbip) generated automatically")
            print("   Open the .pbip files in Power BI Desktop")
            print()

    def _load_converted_objects(self):
        """Load Qlik JSON files and transform to generation-compatible format.

        Reads the 11 Qlik intermediate files, then runs the format adapter
        to produce the ``converted_objects`` dict expected by the generation
        layer.
        """
        # Ensure project root is importable
        _project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        if _project_root not in sys.path:
            sys.path.insert(0, _project_root)

        # Load raw Qlik data
        qlik_data = self._load_qlik_json_files()

        # Transform via format adapter
        try:
            from qlik_export.format_adapter import adapt_qlik_for_generation
            return adapt_qlik_for_generation(qlik_data)
        except ImportError:
            # Fallback: try loading pre-converted files directly
            # (supports pre-converted data or manual JSON placement)
            return self._load_legacy_format_files()

    def _load_qlik_json_files(self):
        """Load all 11 Qlik intermediate JSON files."""
        src = self.source_dir
        qlik_files = {
            'app_metadata':  'app_metadata.json',
            'datasources':   'datasources.json',
            'dimensions':    'dimensions.json',
            'measures':      'measures.json',
            'visualizations': 'visualizations.json',
            'sheets':        'sheets.json',
            'variables':     'variables.json',
            'loadscript':    'loadscript.json',
            'associations':  'associations.json',
            'bookmarks':     'bookmarks.json',
            'master_items':  'master_items.json',
        }
        data = {}
        for key, filename in qlik_files.items():
            filepath = os.path.join(src, filename)
            try:
                if os.path.exists(filepath):
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data[key] = json.load(f)
                else:
                    data[key] = {} if key in ('app_metadata', 'loadscript') else []
            except Exception:
                data[key] = {} if key in ('app_metadata', 'loadscript') else []
        return data

    def _load_legacy_format_files(self):
        """Fallback: load pre-converted JSON files directly."""
        data = {}
        src = self.source_dir
        files_map = {
            'datasources': 'datasources.json',
            'worksheets': 'worksheets.json',
            'dashboards': 'dashboards.json',
            'calculations': 'calculations.json',
            'parameters': 'parameters.json',
            'filters': 'filters.json',
            'stories': 'stories.json',
            'actions': 'actions.json',
            'sets': 'sets.json',
            'groups': 'groups.json',
            'bins': 'bins.json',
            'hierarchies': 'hierarchies.json',
            'sort_orders': 'sort_orders.json',
            'aliases': 'aliases.json',
            'custom_sql': 'custom_sql.json',
            'user_filters': 'user_filters.json',
        }
        for key, filename in files_map.items():
            filepath = os.path.join(src, filename)
            try:
                if os.path.exists(filepath):
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data[key] = json.load(f)
                else:
                    data[key] = [] if key != 'aliases' else {}
            except Exception:
                data[key] = [] if key != 'aliases' else {}
        return data
    
    def generate_powerbi_project(self, report_name, converted_objects, output_dir=None,
                                 calendar_start=None, calendar_end=None, culture=None,
                                 model_mode='import', output_format='pbip', paginated=False):
        """Generate a Power BI Project (.pbip)

        Args:
            report_name: Name of the report
            converted_objects: Dict of extracted source objects
            output_dir: Custom output directory for .pbip project
            calendar_start: Start year for Calendar table
            calendar_end: End year for Calendar table
            culture: Override culture/locale
        """
        
        print(f"\n  Generating Power BI Project (.pbip)...")
        
        try:
            # Determine absolute path to powerbi_projects
            if output_dir:
                projects_dir = os.path.abspath(output_dir)
            else:
                artifacts_dir = os.path.abspath('artifacts')
                projects_dir = os.path.join(artifacts_dir, 'powerbi_projects', 'migrated')
            
            artifacts_dir = os.path.abspath('artifacts')
            generator = PowerBIProjectGenerator(
                output_dir=projects_dir
            )
            
            project_path = generator.generate_project(report_name, converted_objects,
                                                       calendar_start=calendar_start,
                                                       calendar_end=calendar_end,
                                                       culture=culture,
                                                       model_mode=model_mode,
                                                       output_format=output_format,
                                                       paginated=paginated)
            print(f"  [OK] Power BI Project created: {project_path}")
            return project_path
            
        except Exception as e:
            print(f"  [WARN] Error generating Power BI Project: {str(e)}")
            return None

    def _run_validation(self, project_path):
        """Run post-generation artifact validation."""
        try:
            from powerbi_import.validator import ArtifactValidator
            result = ArtifactValidator.validate_project(project_path)
            if isinstance(result, dict):
                errors = result.get('errors', [])
                warnings = result.get('warnings', [])
                files_checked = result.get('files_checked', 0)
                if errors:
                    print(f"  [WARN] Validation: {len(errors)} errors, {len(warnings)} warnings")
                    for err in errors[:5]:
                        print(f"    - {err}")
                else:
                    print(f"  [OK] Validation passed ({files_checked} files, {len(warnings)} warnings)")
            else:
                # Legacy list-of-dicts format
                errors = [r for r in result if isinstance(r, dict) and r.get('level') == 'error']
                warnings = [r for r in result if isinstance(r, dict) and r.get('level') == 'warning']
                if errors:
                    print(f"  [WARN] Validation: {len(errors)} errors, {len(warnings)} warnings")
                else:
                    print(f"  [OK] Validation passed ({len(warnings)} warnings)")
        except Exception as e:
            print(f"  [INFO] Validation skipped: {e}")


def main():
    """Main entry point"""
    
    import sys
    
    # Option to disable .pbip generation
    generate_pbip = '--no-pbip' not in sys.argv
    
    importer = PowerBIImporter()
    importer.import_all(generate_pbip=generate_pbip)


if __name__ == '__main__':
    main()
