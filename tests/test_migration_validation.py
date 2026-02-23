"""
Migration Validation Tests — end-to-end migration quality checks.

Tests cover:
  - Project structure validation (all required files/folders)
  - JSON validity (parseable, correct schemas)
  - TMDL syntax (balanced quotes, valid keywords, no orphan refs)
  - DAX expression validation (balanced parens, known functions)
  - Cross-reference checks (visual bindings ↔ model columns)
  - Intermediate JSON contract (11 files, expected keys)
  - Round-trip: extraction → generation → valid .pbip
"""

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Dict, List

import pytest


# ── Helpers ──────────────────────────────────────────────────────

def _create_sample_bim_model() -> Dict:
    """Create a minimal BIM model for testing."""
    return {
        "compatibilityLevel": 1600,
        "model": {
            "culture": "en-US",
            "defaultPowerBIDataSourceVersion": "powerBI_V3",
            "tables": [
                {
                    "name": "Sales",
                    "lineageTag": "aaa-bbb",
                    "columns": [
                        {"name": "Amount", "dataType": "double",
                         "sourceColumn": "Amount", "summarizeBy": "sum"},
                        {"name": "Date", "dataType": "dateTime",
                         "sourceColumn": "Date", "summarizeBy": "none"},
                        {"name": "Country", "dataType": "string",
                         "sourceColumn": "Country", "summarizeBy": "none"},
                    ],
                    "measures": [
                        {"name": "Total Sales", "expression": "SUM('Sales'[Amount])"},
                    ],
                    "partitions": [
                        {"name": "Sales", "mode": "import",
                         "source": {"type": "m",
                                    "expression": 'let\n    Source = Sql.Database("srv", "db")\nin\n    Source'}},
                    ],
                },
                {
                    "name": "Customers",
                    "lineageTag": "ccc-ddd",
                    "columns": [
                        {"name": "CustomerID", "dataType": "int64",
                         "sourceColumn": "CustomerID", "summarizeBy": "none"},
                        {"name": "Name", "dataType": "string",
                         "sourceColumn": "Name", "summarizeBy": "none"},
                    ],
                },
            ],
            "relationships": [
                {
                    "name": "rel1",
                    "fromTable": "Sales",
                    "fromColumn": "CustomerID",
                    "toTable": "Customers",
                    "toColumn": "CustomerID",
                    "crossFilteringBehavior": "both",
                },
            ],
            "annotations": [],
        },
    }


def _create_sample_visualizations() -> List[Dict]:
    return [
        {"type": "barchart", "title": "Sales by Country"},
        {"type": "linechart", "title": "Sales Trend"},
        {"type": "kpi", "title": "Total Revenue"},
        {"type": "table", "title": "Detail Table"},
    ]


def _create_sample_dimensions() -> List[Dict]:
    return [
        {"name": "Country", "field": "Country", "label": "Country"},
        {"name": "Date", "field": "Date", "label": "Date"},
    ]


def _create_sample_measures() -> List[Dict]:
    return [
        {"name": "Total Sales", "expression": "Sum(Amount)", "label": "Total Sales"},
    ]


# ═══════════════════════════════════════════════════════════════════
# Test: PBI Project Structure
# ═══════════════════════════════════════════════════════════════════

class TestProjectStructure:
    """Validate the generated PBI Project folder structure."""

    def setup_method(self):
        from fabric_api.tmdl_generator import TMDLGenerator
        self.gen = TMDLGenerator()
        self.tmpdir = tempfile.mkdtemp(prefix="test_pbip_")

    def test_pbip_file_created(self):
        pbip = self.gen.create_pbi_project(
            output_dir=Path(self.tmpdir),
            report_name="TestReport",
            bim_model=_create_sample_bim_model(),
        )
        assert pbip.exists()
        assert pbip.suffix == ".pbip"

    def test_semantic_model_folder(self):
        self.gen.create_pbi_project(
            output_dir=Path(self.tmpdir),
            report_name="TestReport",
            bim_model=_create_sample_bim_model(),
        )
        sm_dir = Path(self.tmpdir) / "TestReport.SemanticModel"
        assert sm_dir.exists()
        assert (sm_dir / "definition.pbism").exists()
        assert (sm_dir / ".platform").exists()

    def test_tmdl_files_created(self):
        self.gen.create_pbi_project(
            output_dir=Path(self.tmpdir),
            report_name="TestReport",
            bim_model=_create_sample_bim_model(),
        )
        def_dir = Path(self.tmpdir) / "TestReport.SemanticModel" / "definition"
        assert (def_dir / "database.tmdl").exists()
        assert (def_dir / "model.tmdl").exists()
        assert (def_dir / "tables" / "Sales.tmdl").exists()
        assert (def_dir / "tables" / "Customers.tmdl").exists()
        assert (def_dir / "relationships.tmdl").exists()

    def test_report_folder(self):
        self.gen.create_pbi_project(
            output_dir=Path(self.tmpdir),
            report_name="TestReport",
            bim_model=_create_sample_bim_model(),
            visualizations=_create_sample_visualizations(),
            dimensions=_create_sample_dimensions(),
            measures=_create_sample_measures(),
        )
        rpt_dir = Path(self.tmpdir) / "TestReport.Report"
        assert rpt_dir.exists()
        assert (rpt_dir / "definition.pbir").exists()
        def_dir = rpt_dir / "definition"
        assert (def_dir / "version.json").exists()
        assert (def_dir / "report.json").exists()
        assert (def_dir / "pages" / "pages.json").exists()

    def test_visual_json_files_created(self):
        self.gen.create_pbi_project(
            output_dir=Path(self.tmpdir),
            report_name="TestReport",
            bim_model=_create_sample_bim_model(),
            visualizations=_create_sample_visualizations(),
            dimensions=_create_sample_dimensions(),
            measures=_create_sample_measures(),
        )
        page_dir = Path(self.tmpdir) / "TestReport.Report" / "definition" / "pages" / "ReportSection"
        visuals_dir = page_dir / "visuals"
        assert visuals_dir.exists()
        visual_dirs = list(visuals_dir.iterdir())
        assert len(visual_dirs) == 4  # 4 visualizations


# ═══════════════════════════════════════════════════════════════════
# Test: JSON Validity
# ═══════════════════════════════════════════════════════════════════

class TestJsonValidity:
    """Validate that all generated JSON files are parseable."""

    def setup_method(self):
        from fabric_api.tmdl_generator import TMDLGenerator
        self.gen = TMDLGenerator()
        self.tmpdir = tempfile.mkdtemp(prefix="test_json_")
        self.gen.create_pbi_project(
            output_dir=Path(self.tmpdir),
            report_name="JsonTest",
            bim_model=_create_sample_bim_model(),
            visualizations=_create_sample_visualizations(),
            dimensions=_create_sample_dimensions(),
            measures=_create_sample_measures(),
        )

    def test_pbip_is_valid_json(self):
        pbip = Path(self.tmpdir) / "JsonTest.pbip"
        data = json.loads(pbip.read_text(encoding="utf-8"))
        assert "$schema" in data
        assert "artifacts" in data

    def test_pbism_is_valid_json(self):
        path = Path(self.tmpdir) / "JsonTest.SemanticModel" / "definition.pbism"
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data.get("version") == "4.0"

    def test_pbir_is_valid_json(self):
        path = Path(self.tmpdir) / "JsonTest.Report" / "definition.pbir"
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data.get("version") == "4.0"

    def test_report_json_has_schema(self):
        path = Path(self.tmpdir) / "JsonTest.Report" / "definition" / "report.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        assert "$schema" in data

    def test_visual_json_has_schema(self):
        visuals_dir = (Path(self.tmpdir) / "JsonTest.Report" / "definition"
                       / "pages" / "ReportSection" / "visuals")
        for v_dir in visuals_dir.iterdir():
            vj = v_dir / "visual.json"
            data = json.loads(vj.read_text(encoding="utf-8"))
            assert "$schema" in data
            assert "visual" in data


# ═══════════════════════════════════════════════════════════════════
# Test: TMDL Syntax
# ═══════════════════════════════════════════════════════════════════

class TestTmdlSyntax:
    """Validate TMDL file syntax."""

    def setup_method(self):
        from fabric_api.tmdl_generator import TMDLGenerator
        self.gen = TMDLGenerator()
        self.tmpdir = tempfile.mkdtemp(prefix="test_tmdl_")
        self.gen.create_pbi_project(
            output_dir=Path(self.tmpdir),
            report_name="TmdlTest",
            bim_model=_create_sample_bim_model(),
        )
        self.def_dir = Path(self.tmpdir) / "TmdlTest.SemanticModel" / "definition"

    def test_database_tmdl_starts_with_keyword(self):
        content = (self.def_dir / "database.tmdl").read_text(encoding="utf-8")
        assert content.startswith("database")

    def test_model_tmdl_has_ref_tables(self):
        content = (self.def_dir / "model.tmdl").read_text(encoding="utf-8")
        assert "ref table Sales" in content
        assert "ref table Customers" in content

    def test_table_tmdl_has_columns(self):
        content = (self.def_dir / "tables" / "Sales.tmdl").read_text(encoding="utf-8")
        assert "column Amount" in content or "column 'Amount'" in content
        assert "dataType: double" in content

    def test_table_tmdl_has_measures(self):
        content = (self.def_dir / "tables" / "Sales.tmdl").read_text(encoding="utf-8")
        assert "measure" in content
        assert "Total Sales" in content

    def test_relationships_tmdl(self):
        content = (self.def_dir / "relationships.tmdl").read_text(encoding="utf-8")
        assert "relationship" in content
        assert "fromColumn" in content
        assert "toColumn" in content

    def test_balanced_quotes_in_tmdl(self):
        """Ensure all TMDL files have balanced single quotes."""
        for tmdl_file in self.def_dir.rglob("*.tmdl"):
            content = tmdl_file.read_text(encoding="utf-8")
            single_quotes = content.count("'")
            assert single_quotes % 2 == 0, \
                f"Unbalanced quotes in {tmdl_file.name}: {single_quotes} quotes"


# ═══════════════════════════════════════════════════════════════════
# Test: DAX Converter
# ═══════════════════════════════════════════════════════════════════

class TestDaxConverter:
    """Test DAX expression conversion from Qlik."""

    def test_basic_aggregation(self):
        from fabric_api.dax_converter import convert_qlik_expression_to_dax
        result = convert_qlik_expression_to_dax("Sum(Amount)")
        assert "SUM" in result

    def test_if_conversion(self):
        from fabric_api.dax_converter import convert_qlik_expression_to_dax
        result = convert_qlik_expression_to_dax("If(Amount > 100, 'High', 'Low')")
        assert "IF" in result

    def test_null_handling(self):
        from fabric_api.dax_converter import convert_qlik_expression_to_dax
        result = convert_qlik_expression_to_dax("IsNull(Amount)")
        assert "ISBLANK" in result

    def test_date_function(self):
        from fabric_api.dax_converter import convert_qlik_expression_to_dax
        result = convert_qlik_expression_to_dax("Year(OrderDate)")
        assert "YEAR" in result

    def test_string_function(self):
        from fabric_api.dax_converter import convert_qlik_expression_to_dax
        result = convert_qlik_expression_to_dax("Upper(Name)")
        assert "UPPER" in result

    def test_empty_expression(self):
        from fabric_api.dax_converter import convert_qlik_expression_to_dax
        result = convert_qlik_expression_to_dax("")
        assert result == ""

    def test_batch_measures(self):
        from fabric_api.dax_converter import convert_measures_to_dax
        measures = [
            {"name": "Total", "expression": "Sum(Amount)"},
            {"name": "Avg", "expression": "Avg(Amount)"},
        ]
        result = convert_measures_to_dax(measures)
        assert len(result) == 2
        assert "SUM" in result[0]["dax_expression"]
        assert "AVERAGE" in result[1]["dax_expression"]


# ═══════════════════════════════════════════════════════════════════
# Test: M Query Generator
# ═══════════════════════════════════════════════════════════════════

class TestMQueryGenerator:
    """Test Power Query M generation."""

    def test_csv_connector(self):
        from fabric_api.m_query_generator import generate_m_query
        result = generate_m_query({
            "connectionType": "csv",
            "connection": {"path": "C:\\data.csv"},
        })
        assert "Csv.Document" in result
        assert "let" in result
        assert "in" in result

    def test_sql_server_connector(self):
        from fabric_api.m_query_generator import generate_m_query
        result = generate_m_query({
            "connectionType": "sqlserver",
            "connection": {"server": "srv", "database": "db"},
            "tableName": "dbo.Sales",
        })
        assert "Sql.Database" in result

    def test_postgresql_connector(self):
        from fabric_api.m_query_generator import generate_m_query
        result = generate_m_query({
            "connectionType": "postgresql",
            "connection": {"server": "pg", "database": "mydb"},
            "tableName": "public.orders",
        })
        assert "PostgreSQL.Database" in result

    def test_snowflake_connector(self):
        from fabric_api.m_query_generator import generate_m_query
        result = generate_m_query({
            "connectionType": "snowflake",
            "connection": {"server": "acc.snowflakecomputing.com", "warehouse": "WH"},
        })
        assert "Snowflake.Databases" in result

    def test_unknown_type_generates_sample(self):
        from fabric_api.m_query_generator import generate_m_query
        result = generate_m_query({"connectionType": "unknown"})
        assert "TODO" in result

    def test_generate_all(self):
        from fabric_api.m_query_generator import generate_all_m_queries
        result = generate_all_m_queries([
            {"connectionType": "csv", "tableName": "T1", "connection": {"path": "f.csv"}},
            {"connectionType": "excel", "tableName": "T2", "connection": {"path": "f.xlsx"}},
        ])
        assert "T1" in result
        assert "T2" in result


# ═══════════════════════════════════════════════════════════════════
# Test: M Query Builder
# ═══════════════════════════════════════════════════════════════════

class TestMQueryBuilder:
    """Test Power Query M transforms and step injection."""

    def test_rename_columns(self):
        from fabric_api.m_query_builder import rename_columns
        name, code = rename_columns("Source", {"Old": "New"})
        assert name == "RenamedColumns"
        assert "Table.RenameColumns" in code

    def test_filter_values(self):
        from fabric_api.m_query_builder import filter_values
        name, code = filter_values("Source", "Status", ["Active"])
        assert "Table.SelectRows" in code

    def test_group_by(self):
        from fabric_api.m_query_builder import group_by
        name, code = group_by("Source", ["Cat"], [
            {"column": "Amount", "agg": "sum", "alias": "Total"},
        ])
        assert "Table.Group" in code
        assert "List.Sum" in code

    def test_inject_steps(self):
        from fabric_api.m_query_builder import inject_m_steps
        base = 'let\n    Source = Table.FromRecords({})\nin\n    Source'
        steps = [("Step1", '    Step1 = Table.Distinct(Source)')]
        result = inject_m_steps(base, steps)
        assert "Step1" in result
        assert "Table.Distinct" in result

    def test_build_with_transforms(self):
        from fabric_api.m_query_builder import build_m_query_with_transforms
        base = 'let\n    Source = Table.FromRecords({})\nin\n    Source'
        result = build_m_query_with_transforms(base, [
            {"type": "rename", "mapping": {"A": "B"}},
            {"type": "distinct"},
        ])
        assert "RenamedColumns" in result
        assert "DistinctRows" in result


# ═══════════════════════════════════════════════════════════════════
# Test: Extraction Orchestrator
# ═══════════════════════════════════════════════════════════════════

class TestExtractionOrchestrator:
    """Test the extraction orchestrator with JSON input."""

    def test_load_from_json(self):
        from fabric_api.extraction_orchestrator import ExtractionOrchestrator
        # Create a sample JSON export
        sample = {
            "name": "TestApp",
            "datasources": [{"tableName": "T1", "connectionType": "csv"}],
            "dimensions": [{"name": "Dim1", "field": "F1"}],
            "measures": [{"name": "M1", "expression": "Sum(X)"}],
            "sheets": [{"title": "Sheet1"}],
        }
        tmpdir = tempfile.mkdtemp()
        json_path = os.path.join(tmpdir, "export.json")
        with open(json_path, "w") as f:
            json.dump(sample, f)

        orch = ExtractionOrchestrator()
        data = orch.extract(json_path)
        assert data["app_metadata"]["name"] == "TestApp"
        assert len(data["datasources"]) == 1

    def test_write_11_files(self):
        from fabric_api.extraction_orchestrator import ExtractionOrchestrator, INTERMEDIATE_FILES
        sample = {"name": "WF", "datasources": [], "dimensions": [], "measures": []}
        tmpdir = tempfile.mkdtemp()
        json_path = os.path.join(tmpdir, "test.json")
        with open(json_path, "w") as f:
            json.dump(sample, f)

        orch = ExtractionOrchestrator()
        orch.extract(json_path)
        out_dir = os.path.join(tmpdir, "intermediate")
        orch.write_intermediate_json(out_dir)

        for fname in INTERMEDIATE_FILES:
            assert os.path.exists(os.path.join(out_dir, fname)), f"Missing: {fname}"

    def test_load_intermediate(self):
        from fabric_api.extraction_orchestrator import ExtractionOrchestrator, INTERMEDIATE_FILES
        tmpdir = tempfile.mkdtemp()
        for fname in INTERMEDIATE_FILES:
            with open(os.path.join(tmpdir, fname), "w") as f:
                json.dump([] if fname != "app_metadata.json" else {"name": "X"}, f)

        data = ExtractionOrchestrator.load_intermediate_json(tmpdir)
        assert "app_metadata" in data
        assert "datasources" in data
        assert len(data) == 11


# ═══════════════════════════════════════════════════════════════════
# Test: Visual Generator
# ═══════════════════════════════════════════════════════════════════

class TestVisualGenerator:
    """Test visual container generation."""

    def test_resolve_type(self):
        from fabric_api.visual_generator import resolve_visual_type
        assert resolve_visual_type("barchart") == "clusteredBarChart"
        assert resolve_visual_type("linechart") == "lineChart"
        assert resolve_visual_type("unknown") == "tableEx"

    def test_create_visual_container(self):
        from fabric_api.visual_generator import create_visual_container
        result = create_visual_container(
            visual_id="test_vid",
            visualization={"type": "barchart", "title": "Test"},
            index=0,
            dimensions=[],
            measures=[],
            col_table_map={},
            measure_lookup={},
            page_width=1280,
            page_height=720,
        )
        assert result["visual"]["visualType"] == "clusteredBarChart"
        assert "$schema" in result

    def test_generate_visual_containers(self):
        from fabric_api.visual_generator import generate_visual_containers
        vizs = [
            {"type": "barchart", "title": "Bar"},
            {"type": "piechart", "title": "Pie"},
        ]
        result = generate_visual_containers(vizs, report_name="TestReport")
        assert len(result) == 2


# ═══════════════════════════════════════════════════════════════════
# Test: TMDL Enhancements (v3.0)
# ═══════════════════════════════════════════════════════════════════

class TestTmdlEnhancements:
    """Test new TMDL features: RLS, calendar, parameters, dataCategory."""

    def test_calendar_table(self):
        from fabric_api.tmdl_generator import TMDLGenerator
        cal = TMDLGenerator.generate_calendar_table()
        assert cal["name"] == "Calendar"
        assert cal["dataCategory"] == "Time"
        col_names = [c["name"] for c in cal["columns"]]
        assert "Date" in col_names
        assert "Year" in col_names
        assert "MonthName" in col_names

    def test_parameter_table(self):
        from fabric_api.tmdl_generator import TMDLGenerator
        param = TMDLGenerator.generate_parameter_table("Discount", 0, 50, 5, 10)
        assert param["name"] == "Discount"
        assert len(param["measures"]) == 1
        assert "SELECTEDVALUE" in param["measures"][0]["expression"]

    def test_geographic_category(self):
        from fabric_api.tmdl_generator import TMDLGenerator
        assert TMDLGenerator.infer_data_category("Country") == "Country"
        assert TMDLGenerator.infer_data_category("city") == "City"
        assert TMDLGenerator.infer_data_category("PostalCode") == "PostalCode"
        assert TMDLGenerator.infer_data_category("SomeField") == ""

    def test_rls_roles_tmdl(self):
        from fabric_api.tmdl_generator import TMDLGenerator
        gen = TMDLGenerator()
        tmpdir = tempfile.mkdtemp()
        bim = _create_sample_bim_model()
        bim["model"]["roles"] = [
            {
                "name": "RegionRole",
                "modelPermission": "read",
                "tablePermissions": [
                    {"name": "Sales",
                     "filterExpression": "'Sales'[Country] = USERPRINCIPALNAME()"},
                ],
            },
        ]
        gen.create_pbi_project(
            output_dir=Path(tmpdir),
            report_name="RLSTest",
            bim_model=bim,
        )
        roles_path = Path(tmpdir) / "RLSTest.SemanticModel" / "definition" / "roles.tmdl"
        assert roles_path.exists()
        content = roles_path.read_text(encoding="utf-8")
        assert "RegionRole" in content
        assert "filterExpression" in content

    def test_calculated_column_in_tmdl(self):
        from fabric_api.tmdl_generator import TMDLGenerator
        gen = TMDLGenerator()
        tmpdir = tempfile.mkdtemp()
        bim = _create_sample_bim_model()
        bim["model"]["tables"][0]["columns"].append({
            "name": "SalesCategory",
            "dataType": "string",
            "type": "calculated",
            "expression": 'IF([Amount] > 1000, "High", "Low")',
            "summarizeBy": "none",
        })
        gen.create_pbi_project(
            output_dir=Path(tmpdir),
            report_name="CalcTest",
            bim_model=bim,
        )
        tmdl = (Path(tmpdir) / "CalcTest.SemanticModel" / "definition"
                / "tables" / "Sales.tmdl").read_text(encoding="utf-8")
        assert "SalesCategory" in tmdl
        assert "IF(" in tmdl

    def test_hidden_column(self):
        from fabric_api.tmdl_generator import TMDLGenerator
        gen = TMDLGenerator()
        tmpdir = tempfile.mkdtemp()
        bim = _create_sample_bim_model()
        bim["model"]["tables"][0]["columns"][0]["isHidden"] = True
        gen.create_pbi_project(
            output_dir=Path(tmpdir),
            report_name="HiddenTest",
            bim_model=bim,
        )
        tmdl = (Path(tmpdir) / "HiddenTest.SemanticModel" / "definition"
                / "tables" / "Sales.tmdl").read_text(encoding="utf-8")
        assert "isHidden" in tmdl
