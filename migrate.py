"""
Main script for Qlik to Power BI migration

Pipeline:
1. Extract objects from the Qlik file (.qvf or .json export)
2. Convert Qlik expressions → DAX, load scripts → Power Query M
3. Build BIM model (tables, relationships, measures, RLS)
4. Generate the Power BI project (.pbip) with TMDL model + PBIR report
"""

import os
import sys
import argparse
import json
import logging
from datetime import datetime
from pathlib import Path

# Ensure src/ is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

logger = logging.getLogger(__name__)


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


def run_extraction(qlik_file, output_dir, stats=None):
    """Run Qlik extraction → intermediate JSON files."""
    print_step(1, 3, "QLIK OBJECTS EXTRACTION")

    if not os.path.exists(qlik_file):
        print(f"Error: Qlik file not found: {qlik_file}")
        return False

    print(f"Source file: {qlik_file}")

    try:
        from fabric_api.extraction_orchestrator import ExtractionOrchestrator

        orchestrator = ExtractionOrchestrator(output_dir=output_dir)
        orchestrator.extract(qlik_file)
        json_dir = orchestrator.write_intermediate_json(output_dir)

        summary = orchestrator.get_extraction_summary()
        print(f"  App name:       {summary.get('app_name', 'Unknown')}")
        print(f"  Datasources:    {summary.get('datasources_count', 0)}")
        print(f"  Dimensions:     {summary.get('dimensions_count', 0)}")
        print(f"  Measures:       {summary.get('measures_count', 0)}")
        print(f"  Visualizations: {summary.get('visualizations_count', 0)}")
        print(f"  Sheets:         {summary.get('sheets_count', 0)}")
        print(f"  Variables:      {summary.get('variables_count', 0)}")
        print(f"  Associations:   {summary.get('associations_count', 0)}")
        print(f"  Bookmarks:      {summary.get('bookmarks_count', 0)}")
        print(f"  Has load script:{summary.get('has_loadscript', False)}")

        if stats:
            stats.app_name = summary.get('app_name', 'Unknown')
            stats.datasources = summary.get('datasources_count', 0)
            stats.dimensions = summary.get('dimensions_count', 0)
            stats.measures = summary.get('measures_count', 0)
            stats.visualizations = summary.get('visualizations_count', 0)
            stats.sheets = summary.get('sheets_count', 0)
            stats.variables = summary.get('variables_count', 0)
            stats.associations = summary.get('associations_count', 0)
            stats.bookmarks = summary.get('bookmarks_count', 0)
            stats.has_loadscript = summary.get('has_loadscript', False)

        print(f"\n✓ Extraction completed — intermediate JSON in {json_dir}")
        return True

    except Exception as e:
        print(f"\nError during extraction: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


# ── Migration statistics tracker ─────────────────────────────────────
class MigrationStats:
    """Collect statistics across all migration steps for the final report."""
    def __init__(self):
        self.app_name = "Unknown"
        # Extraction
        self.datasources = 0
        self.dimensions = 0
        self.measures = 0
        self.visualizations = 0
        self.sheets = 0
        self.variables = 0
        self.associations = 0
        self.bookmarks = 0
        self.has_loadscript = False
        # Conversion
        self.dax_measures_converted = 0
        self.dax_dimensions_total = 0
        self.dax_calc_dims = 0
        self.m_queries_generated = 0
        self.loadscript_converted = False
        self.relationships_built = 0
        self.tables_built = 0
        self.variables_expanded = 0
        self.expressions_resolved = 0
        # Generation
        self.tmdl_tables_written = 0
        self.visuals_generated = 0
        self.pages_generated = 0
        self.pbip_path = ""
        # Warnings
        self.warnings: list = []
        self.skipped: list = []

    def add_warning(self, msg: str):
        self.warnings.append(msg)

    def add_skipped(self, msg: str):
        self.skipped.append(msg)


def run_conversion(json_dir, stats=None):
    """Convert Qlik expressions → DAX, load scripts → M, build BIM model."""
    print_step(2, 3, "EXPRESSION & MODEL CONVERSION")

    try:
        from fabric_api.extraction_orchestrator import ExtractionOrchestrator
        from fabric_api.dax_converter import (
            convert_measures_to_dax,
            convert_dimensions_to_dax,
            convert_qlik_expression_to_dax,
            convert_qlik_type_to_dax,
        )
        from fabric_api.m_query_generator import generate_all_m_queries
        from fabric_api.qlik_script_converter import QlikScriptToPowerQueryConverter

        data = ExtractionOrchestrator.load_intermediate_json(json_dir)

        # ── Variables: expand $(vName) references ────────────
        variables = data.get("variables", [])
        var_map = {}
        for v in variables:
            vname = v.get("name", "")
            vdef = v.get("definition", "")
            if vname:
                var_map[vname] = vdef
        if stats:
            stats.variables_expanded = len(var_map)
        print(f"  Variables loaded: {len(var_map)}")

        def expand_variables(expr):
            """Expand $(vName) dollar-sign variable references."""
            if not expr or "$(" not in expr:
                return expr
            import re
            max_passes = 5
            for _ in range(max_passes):
                new_expr = re.sub(
                    r'\$\((\w+)\)',
                    lambda m: var_map.get(m.group(1), m.group(0)),
                    expr,
                )
                if new_expr == expr:
                    break
                expr = new_expr
            return expr

        # ── Measures → DAX ──────────────────────────────────
        measures = data.get("measures", [])
        for m in measures:
            m["expression"] = expand_variables(m.get("expression", ""))
        measures_dax = convert_measures_to_dax(measures)
        if stats:
            stats.dax_measures_converted = len(measures_dax)
        print(f"  Measures converted: {len(measures_dax)}")

        # ── Dimensions → DAX (calculated dims) ──────────────
        dimensions = data.get("dimensions", [])
        for d in dimensions:
            d["field"] = expand_variables(d.get("field", ""))
        dimensions_dax = convert_dimensions_to_dax(dimensions)
        calc_dims = [d for d in dimensions_dax if d.get("is_calculated")]
        if stats:
            stats.dax_dimensions_total = len(dimensions_dax)
            stats.dax_calc_dims = len(calc_dims)
        print(f"  Dimensions: {len(dimensions_dax)} ({len(calc_dims)} calculated)")

        # ── Datasources → M queries ─────────────────────────
        datasources = data.get("datasources", [])
        m_queries = generate_all_m_queries(datasources)
        if stats:
            stats.m_queries_generated = len(m_queries)
        print(f"  M queries generated: {len(m_queries)}")

        # ── Load script → M ─────────────────────────────────
        loadscript = data.get("loadscript", {})
        script_text = loadscript.get("script", "") if isinstance(loadscript, dict) else ""
        script_text = expand_variables(script_text)
        script_m_queries = {}
        if script_text:
            converter = QlikScriptToPowerQueryConverter()
            pq_script = converter.convert_qlik_script_to_powerquery(script_text)
            if pq_script:
                script_m_queries["LoadScript"] = pq_script
                if stats:
                    stats.loadscript_converted = True
                print(f"  Load script converted to M")

        # ── Associations → relationships ─────────────────────
        associations = data.get("associations", [])
        relationships = []
        for assoc in associations:
            relationships.append({
                "name": f"{assoc.get('table1','')}__{assoc.get('table2','')}",
                "fromTable": assoc.get("table1", ""),
                "fromColumn": assoc.get("field1", ""),
                "toTable": assoc.get("table2", ""),
                "toColumn": assoc.get("field2", ""),
                "crossFilteringBehavior": "oneDirection",
                "isActive": True,
            })
        if stats:
            stats.relationships_built = len(relationships)
        print(f"  Relationships: {len(relationships)}")

        # ── Build shared expressions from M queries ──────────
        expressions_list = []
        all_m = {**m_queries, **script_m_queries}
        for expr_name, expr_text in all_m.items():
            expressions_list.append({
                "name": expr_name,
                "expression": expr_text,
            })
        if stats:
            stats.expressions_resolved = len(expressions_list)

        # ── Build BIM model dict ─────────────────────────────
        tables = []
        for ds in datasources:
            table_name = ds.get("tableName", "Table")
            columns = []
            for col in ds.get("columns", []):
                col_entry = {
                    "name": col.get("name", ""),
                    "dataType": convert_qlik_type_to_dax(col.get("dataType", "text")),
                    "sourceColumn": col.get("name", ""),
                    "summarizeBy": "none",
                    "description": col.get("comment", col.get("description", "")),
                }
                # Auto-assign display folder from Qlik field tags or group
                if col.get("group") or col.get("tag"):
                    col_entry["displayFolder"] = col.get("group", col.get("tag", ""))
                columns.append(col_entry)

            # Measures for this table
            table_measures = []
            for m in measures_dax:
                # Assign measures to first table for now
                table_measures.append({
                    "name": m.get("name", ""),
                    "expression": m.get("dax_expression", m.get("expression", "")),
                    "formatString": m.get("formatString", ""),
                    "description": m.get("description", m.get("comment", "")),
                    "displayFolder": m.get("group", m.get("tags", "")),
                })

            # Calculated columns from dimensions
            for d in dimensions_dax:
                if d.get("is_calculated"):
                    columns.append({
                        "name": d.get("name", ""),
                        "dataType": "string",
                        "type": "calculated",
                        "expression": d.get("dax_expression", ""),
                    })

            # M query partition
            m_query = m_queries.get(table_name, "")
            partitions = []
            if m_query:
                partitions.append({
                    "name": table_name,
                    "mode": "import",
                    "source": {"type": "m", "expression": m_query},
                })

            tables.append({
                "name": table_name,
                "columns": columns,
                "measures": table_measures if tables == [] else [],  # measures on first table only
                "partitions": partitions,
            })

            # Only assign measures to the first table
            measures_dax_remaining = []

        # Add script-derived tables
        for sq_name, sq_m in script_m_queries.items():
            tables.append({
                "name": sq_name,
                "columns": [{"name": "Column1", "dataType": "string", "sourceColumn": "Column1", "summarizeBy": "none"}],
                "partitions": [{"name": sq_name, "mode": "import", "source": {"type": "m", "expression": sq_m}}],
            })

        if stats:
            stats.tables_built = len(tables)

        bim_model = {
            "compatibilityLevel": 1600,
            "model": {
                "culture": "en-US",
                "defaultPowerBIDataSourceVersion": "powerBI_V3",
                "tables": tables,
                "relationships": relationships,
                "expressions": expressions_list,
                "annotations": [],
            },
        }

        # ── Write converted data back ────────────────────────
        converted = {
            "bim_model": bim_model,
            "measures_dax": measures_dax,
            "dimensions_dax": dimensions_dax,
            "m_queries": m_queries,
            "variables": var_map,
            "visualizations": data.get("visualizations", []),
            "sheets": data.get("sheets", []),
            "dimensions": dimensions_dax,
            "measures": measures_dax,
            "bookmarks": data.get("bookmarks", []),
            "app_metadata": data.get("app_metadata", {}),
        }

        converted_path = Path(json_dir) / "_converted.json"
        with open(converted_path, "w", encoding="utf-8") as f:
            json.dump(converted, f, indent=2, ensure_ascii=False, default=str)

        print(f"  Model built: {len(tables)} tables, {len(relationships)} relationships")
        print(f"\n✓ Conversion completed — {converted_path}")
        return True

    except Exception as e:
        print(f"\nError during conversion: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def run_generation(json_dir, output_dir, report_name, stats=None):
    """Generate Power BI project (.pbip) from converted data."""
    print_step(3, 3, "POWER BI PROJECT GENERATION")

    try:
        from fabric_api.tmdl_generator import TMDLGenerator

        converted_path = Path(json_dir) / "_converted.json"
        if not converted_path.exists():
            print("Error: Converted data not found. Run conversion step first.")
            return False

        with open(converted_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        generator = TMDLGenerator()

        project_dir = Path(output_dir) / report_name
        project_dir.mkdir(parents=True, exist_ok=True)

        pbip_path = generator.create_pbi_project(
            output_dir=project_dir,
            report_name=report_name,
            bim_model=data.get("bim_model"),
            power_query_script=None,
            visualizations=data.get("visualizations"),
            dimensions=data.get("dimensions"),
            measures=data.get("measures"),
            sheets=data.get("sheets"),
            bookmarks=data.get("bookmarks"),
        )

        if stats:
            stats.pbip_path = str(pbip_path)
            # Count generated artifacts
            proj = Path(output_dir) / report_name
            sm_tables = proj / f"{report_name}.SemanticModel" / "definition" / "tables"
            if sm_tables.exists():
                stats.tmdl_tables_written = len(list(sm_tables.glob("*.tmdl")))
            rpt_pages = proj / f"{report_name}.Report" / "definition" / "pages"
            if rpt_pages.exists():
                stats.pages_generated = sum(1 for p in rpt_pages.iterdir() if p.is_dir())
                for page_dir in rpt_pages.iterdir():
                    visuals_dir = page_dir / "visuals"
                    if visuals_dir.exists():
                        stats.visuals_generated += sum(1 for v in visuals_dir.iterdir() if v.is_dir())

        print(f"\n✓ Power BI project generated: {pbip_path}")
        return True

    except Exception as e:
        print(f"\nError during generation: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def print_migration_summary(stats, duration, results):
    """Print a detailed migration summary report."""
    print_header("MIGRATION SUMMARY REPORT")

    # ── Step results ──────────────────────────────────────────
    print("Pipeline Steps")
    print("-" * 50)
    for step_name, success in [
        ("Qlik Extraction", results.get("extraction", False)),
        ("Expression Conversion", results.get("conversion", False)),
        ("Power BI Generation", results.get("generation", False)),
    ]:
        status = "✓ Success" if success else "✗ Failed"
        print(f"  {step_name:<30} {status}")

    # ── Extraction summary ────────────────────────────────────
    print(f"\nSource Application: {stats.app_name}")
    print("-" * 50)
    print(f"  {'Datasources':<25} {stats.datasources:>5}")
    print(f"  {'Dimensions':<25} {stats.dimensions:>5}")
    print(f"  {'Measures':<25} {stats.measures:>5}")
    print(f"  {'Visualizations':<25} {stats.visualizations:>5}")
    print(f"  {'Sheets':<25} {stats.sheets:>5}")
    print(f"  {'Variables':<25} {stats.variables:>5}")
    print(f"  {'Associations':<25} {stats.associations:>5}")
    print(f"  {'Bookmarks':<25} {stats.bookmarks:>5}")
    print(f"  {'Load Script':<25} {'Yes' if stats.has_loadscript else 'No':>5}")

    # ── Conversion summary ────────────────────────────────────
    print(f"\nConversion Results")
    print("-" * 50)
    print(f"  {'DAX measures converted':<25} {stats.dax_measures_converted:>5}")
    print(f"  {'Dimensions processed':<25} {stats.dax_dimensions_total:>5}")
    print(f"  {'  Calculated columns':<25} {stats.dax_calc_dims:>5}")
    print(f"  {'M queries generated':<25} {stats.m_queries_generated:>5}")
    print(f"  {'Variables expanded':<25} {stats.variables_expanded:>5}")
    print(f"  {'Shared expressions':<25} {stats.expressions_resolved:>5}")
    print(f"  {'Relationships built':<25} {stats.relationships_built:>5}")
    print(f"  {'Tables in model':<25} {stats.tables_built:>5}")
    print(f"  {'Load script → M':<25} {'Yes' if stats.loadscript_converted else 'No':>5}")

    # ── Generation summary ────────────────────────────────────
    print(f"\nGenerated Output")
    print("-" * 50)
    print(f"  {'TMDL table files':<25} {stats.tmdl_tables_written:>5}")
    print(f"  {'Report pages':<25} {stats.pages_generated:>5}")
    print(f"  {'Visual containers':<25} {stats.visuals_generated:>5}")
    if stats.pbip_path:
        print(f"  Project path: {stats.pbip_path}")

    # ── Warnings ──────────────────────────────────────────────
    if stats.warnings:
        print(f"\nWarnings ({len(stats.warnings)})")
        print("-" * 50)
        for w in stats.warnings:
            print(f"  ⚠ {w}")

    if stats.skipped:
        print(f"\nSkipped Items ({len(stats.skipped)})")
        print("-" * 50)
        for s in stats.skipped:
            print(f"  → {s}")

    # ── Duration ──────────────────────────────────────────────
    print(f"\nDuration: {duration}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Migrate a Qlik Sense application to a Power BI project (.pbip)"
    )

    parser.add_argument(
        "qlik_file",
        help="Path to the Qlik file (.qvf or .json export)",
    )

    parser.add_argument(
        "--output-dir",
        default="output/migrated",
        help="Output directory for generated project (default: output/migrated)",
    )

    parser.add_argument(
        "--skip-extraction",
        action="store_true",
        help="Skip extraction step (reuse existing intermediate JSON files)",
    )

    parser.add_argument(
        "--skip-conversion",
        action="store_true",
        help="Skip conversion step (reuse existing _converted.json)",
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)

    print_header("QLIK TO POWER BI MIGRATION")
    print(f"Source file: {args.qlik_file}")
    print(f"Output dir:  {args.output_dir}")
    print()

    start_time = datetime.now()
    results = {}
    stats = MigrationStats()

    # Determine report name from source file
    source_basename = os.path.splitext(os.path.basename(args.qlik_file))[0]
    json_dir = os.path.join(args.output_dir, source_basename, "_extracted")

    # Step 1: Extraction
    if not args.skip_extraction:
        results["extraction"] = run_extraction(args.qlik_file, json_dir, stats=stats)
        if not results["extraction"]:
            print("\nMigration aborted due to extraction failure")
            return 1
    else:
        print("\nExtraction skipped (using existing intermediate JSON)")
        results["extraction"] = True

    # Step 2: Conversion (expressions → DAX, scripts → M, build model)
    if not args.skip_conversion:
        results["conversion"] = run_conversion(json_dir, stats=stats)
        if not results["conversion"]:
            print("\nMigration aborted due to conversion failure")
            return 1
    else:
        print("\nConversion skipped (using existing _converted.json)")
        results["conversion"] = True

    # Step 3: Generate .pbip project
    results["generation"] = run_generation(json_dir, args.output_dir, source_basename, stats=stats)

    # Final summary report
    duration = datetime.now() - start_time
    print_migration_summary(stats, duration, results)

    all_success = all(results.values())

    if all_success:
        print("\nMigration completed successfully!")
        print("\nNext steps:")
        print(f"  1. Open the .pbip file in {args.output_dir}/{source_basename}/")
        print("  2. Enable Developer Mode in Power BI Desktop → Options → Preview features")
        print("  3. Configure data sources in Power Query Editor")
        print("  4. Verify DAX measures and calculated columns")
        print("  5. Review visual data bindings and fix any unresolved references")
    else:
        print("\nMigration completed with errors")

    return 0 if all_success else 1


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\nMigration interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nFatal error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
