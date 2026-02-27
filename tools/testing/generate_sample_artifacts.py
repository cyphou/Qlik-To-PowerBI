#!/usr/bin/env python3
"""
Generate sample .pbip artifacts from test JSON exports.

Usage:
    python tools/testing/generate_sample_artifacts.py

Generates .pbip projects in artifacts/powerbi_projects/ from each
test sample in examples/qlik/test_samples/ and examples/qlik/qlik_exports/.
"""

import json
import os
import sys
from pathlib import Path

# Ensure src/ is on the path
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))


def generate_from_json_export(json_path: Path, output_dir: Path) -> bool:
    """Generate a .pbip project from a Qlik JSON export."""
    from fabric_api.extraction_orchestrator import ExtractionOrchestrator
    from fabric_api.dax_converter import (
        convert_measures_to_dax,
        convert_dimensions_to_dax,
        convert_qlik_type_to_dax,
    )
    from fabric_api.m_query_generator import generate_all_m_queries
    from fabric_api.qlik_script_converter import QlikScriptToPowerQueryConverter
    from fabric_api.tmdl_generator import TMDLGenerator

    report_name = json_path.stem
    print(f"\n{'='*60}")
    print(f"Generating: {report_name}")
    print(f"Source:     {json_path}")
    print(f"Output:     {output_dir / report_name}")
    print(f"{'='*60}")

    # ── Step 1: Extract ──────────────────────────────────────
    orchestrator = ExtractionOrchestrator(output_dir=str(output_dir))
    orchestrator.extract(str(json_path))
    temp_json_dir = str(output_dir / report_name / "_temp_extracted")
    orchestrator.write_intermediate_json(temp_json_dir)

    # ── Step 2: Convert ──────────────────────────────────────
    data = ExtractionOrchestrator.load_intermediate_json(temp_json_dir)

    # Variables
    variables = data.get("variables", [])
    var_map = {}
    for v in variables:
        vname = v.get("name", "")
        vdef = v.get("definition", "")
        if vname:
            var_map[vname] = vdef

    import re
    def expand_variables(expr):
        if not expr or "$(" not in expr:
            return expr
        for _ in range(5):
            new_expr = re.sub(
                r'\$\((\w+)\)',
                lambda m: var_map.get(m.group(1), m.group(0)),
                expr,
            )
            if new_expr == expr:
                break
            expr = new_expr
        return expr

    # Measures → DAX
    measures = data.get("measures", [])
    for m in measures:
        m["expression"] = expand_variables(m.get("expression", ""))
    measures_dax = convert_measures_to_dax(measures)

    # Dimensions → DAX
    dimensions = data.get("dimensions", [])
    for d in dimensions:
        d["field"] = expand_variables(d.get("field", ""))
    dimensions_dax = convert_dimensions_to_dax(dimensions)

    # Datasources → M queries
    datasources = data.get("datasources", [])
    m_queries = generate_all_m_queries(datasources)

    # Load script → M
    loadscript = data.get("loadscript", {})
    script_text = loadscript.get("script", "") if isinstance(loadscript, dict) else ""
    script_text = expand_variables(script_text)
    script_m_queries = {}
    if script_text:
        converter = QlikScriptToPowerQueryConverter()
        pq_script = converter.convert_qlik_script_to_powerquery(script_text)
        if pq_script:
            script_m_queries["LoadScript"] = pq_script

    # Associations → relationships
    associations = data.get("associations", [])
    relationships = []
    for assoc in associations:
        relationships.append({
            "name": f"{assoc.get('table1', '')}_{assoc.get('table2', '')}",
            "fromTable": assoc.get("table1", ""),
            "fromColumn": assoc.get("field1", ""),
            "toTable": assoc.get("table2", ""),
            "toColumn": assoc.get("field2", ""),
            "crossFilteringBehavior": "oneDirection",
            "isActive": True,
        })

    # Build tables
    tables = []
    for ds in datasources:
        table_name = ds.get("tableName", "Table")
        columns = []
        for col in ds.get("columns", []):
            columns.append({
                "name": col.get("name", ""),
                "dataType": convert_qlik_type_to_dax(col.get("dataType", "text")),
                "sourceColumn": col.get("name", ""),
                "summarizeBy": "none",
            })

        table_measures = []
        if not tables:  # only first table
            for m in measures_dax:
                table_measures.append({
                    "name": m.get("name", ""),
                    "expression": m.get("dax_expression", m.get("expression", "")),
                    "formatString": m.get("formatString", ""),
                    "description": m.get("description", m.get("comment", "")),
                })

        for d in dimensions_dax:
            if d.get("is_calculated"):
                columns.append({
                    "name": d.get("name", ""),
                    "dataType": "string",
                    "type": "calculated",
                    "expression": d.get("dax_expression", ""),
                })

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
            "measures": table_measures,
            "partitions": partitions,
        })

    # Shared expressions
    expressions_list = []
    all_m = {**m_queries, **script_m_queries}
    for expr_name, expr_text in all_m.items():
        expressions_list.append({
            "name": expr_name,
            "expression": expr_text,
        })

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

    # ── Step 3: Generate .pbip ───────────────────────────────
    generator = TMDLGenerator()
    project_dir = output_dir / report_name
    project_dir.mkdir(parents=True, exist_ok=True)

    pbip_path = generator.create_pbi_project(
        output_dir=project_dir,
        report_name=report_name,
        bim_model=bim_model,
        visualizations=data.get("visualizations", []),
        dimensions=dimensions_dax,
        measures=measures_dax,
        sheets=data.get("sheets", []),
        bookmarks=data.get("bookmarks", []),
    )

    # Cleanup temp extracted dir
    import shutil
    temp_dir = output_dir / report_name / "_temp_extracted"
    if temp_dir.exists():
        shutil.rmtree(temp_dir)

    print(f"  ✓ Generated: {pbip_path}")

    # Count artifacts
    sm_tables = project_dir / f"{report_name}.SemanticModel" / "definition" / "tables"
    table_count = len(list(sm_tables.glob("*.tmdl"))) if sm_tables.exists() else 0
    exprs = project_dir / f"{report_name}.SemanticModel" / "definition" / "expressions.tmdl"
    has_exprs = exprs.exists()
    rpt_pages = project_dir / f"{report_name}.Report" / "definition" / "pages"
    page_count = 0
    visual_count = 0
    if rpt_pages.exists():
        for p in rpt_pages.iterdir():
            if p.is_dir():
                page_count += 1
                vis_dir = p / "visuals"
                if vis_dir.exists():
                    visual_count += sum(1 for v in vis_dir.iterdir() if v.is_dir())

    print(f"  Tables: {table_count}, Pages: {page_count}, Visuals: {visual_count}, Expressions: {'Yes' if has_exprs else 'No'}")
    return True


def main():
    artifacts_dir = ROOT / "artifacts" / "powerbi_projects"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    # Collect all JSON samples
    sources = []

    # From test_samples
    for size_dir in ["small", "medium", "large"]:
        sample_dir = ROOT / "examples" / "qlik" / "test_samples" / size_dir
        if sample_dir.exists():
            for f in sorted(sample_dir.glob("*.json")):
                sources.append(f)

    # From qlik_exports
    exports_dir = ROOT / "examples" / "qlik" / "qlik_exports"
    if exports_dir.exists():
        for f in sorted(exports_dir.glob("*.json")):
            sources.append(f)

    if not sources:
        print("No JSON source files found!")
        return 1

    print(f"Found {len(sources)} source file(s) to process")
    successes = 0
    failures = 0

    for src in sources:
        try:
            ok = generate_from_json_export(src, artifacts_dir)
            if ok:
                successes += 1
            else:
                failures += 1
        except Exception as e:
            print(f"  ✗ Failed: {src.name} — {e}")
            import traceback
            traceback.print_exc()
            failures += 1

    print(f"\n{'='*60}")
    print(f"RESULTS: {successes} succeeded, {failures} failed")
    print(f"Output:  {artifacts_dir}")
    print(f"{'='*60}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
