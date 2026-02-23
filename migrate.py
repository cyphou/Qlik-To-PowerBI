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


def run_extraction(qlik_file, output_dir):
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

        print(f"\n✓ Extraction completed — intermediate JSON in {json_dir}")
        return True

    except Exception as e:
        print(f"\nError during extraction: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def run_conversion(json_dir):
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
        print(f"  Measures converted: {len(measures_dax)}")

        # ── Dimensions → DAX (calculated dims) ──────────────
        dimensions = data.get("dimensions", [])
        for d in dimensions:
            d["field"] = expand_variables(d.get("field", ""))
        dimensions_dax = convert_dimensions_to_dax(dimensions)
        calc_dims = [d for d in dimensions_dax if d.get("is_calculated")]
        print(f"  Dimensions: {len(dimensions_dax)} ({len(calc_dims)} calculated)")

        # ── Datasources → M queries ─────────────────────────
        datasources = data.get("datasources", [])
        m_queries = generate_all_m_queries(datasources)
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
        print(f"  Relationships: {len(relationships)}")

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

        bim_model = {
            "compatibilityLevel": 1600,
            "model": {
                "culture": "en-US",
                "defaultPowerBIDataSourceVersion": "powerBI_V3",
                "tables": tables,
                "relationships": relationships,
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


def run_generation(json_dir, output_dir, report_name):
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

        print(f"\n✓ Power BI project generated: {pbip_path}")
        return True

    except Exception as e:
        print(f"\nError during generation: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


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

    # Determine report name from source file
    source_basename = os.path.splitext(os.path.basename(args.qlik_file))[0]
    json_dir = os.path.join(args.output_dir, source_basename, "_extracted")

    # Step 1: Extraction
    if not args.skip_extraction:
        results["extraction"] = run_extraction(args.qlik_file, json_dir)
        if not results["extraction"]:
            print("\nMigration aborted due to extraction failure")
            return 1
    else:
        print("\nExtraction skipped (using existing intermediate JSON)")
        results["extraction"] = True

    # Step 2: Conversion (expressions → DAX, scripts → M, build model)
    if not args.skip_conversion:
        results["conversion"] = run_conversion(json_dir)
        if not results["conversion"]:
            print("\nMigration aborted due to conversion failure")
            return 1
    else:
        print("\nConversion skipped (using existing _converted.json)")
        results["conversion"] = True

    # Step 3: Generate .pbip project
    results["generation"] = run_generation(json_dir, args.output_dir, source_basename)

    # Final report
    duration = datetime.now() - start_time
    print_header("MIGRATION RESULT")
    print(f"Duration: {duration}")
    print()

    for step_name, success in [
        ("Qlik Extraction", results.get("extraction", False)),
        ("Expression Conversion", results.get("conversion", False)),
        ("Power BI Generation", results.get("generation", False)),
    ]:
        status = "✓ Success" if success else "✗ Failed"
        print(f"  {step_name:<30} {status}")

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
