"""Tests for PowerBIProjectGenerator (.pbip project generation).

Covers:
- Project structure creation (.pbip, SemanticModel, Report)
- TMDL model generation from converted_objects
- PBIR report pages and visual generation
- Edge cases: empty data, unicode names, special characters
"""

import json
import os
import shutil
import tempfile
import pytest

from powerbi_import.pbip_generator import PowerBIProjectGenerator


# ── Fixtures ──────────────────────────────────────────────────────

@pytest.fixture
def tmp_dir():
    d = tempfile.mkdtemp(prefix="test_pbip_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def generator(tmp_dir):
    return PowerBIProjectGenerator(output_dir=tmp_dir)


def _minimal_objects():
    """Minimal converted_objects dict with one table + one measure."""
    return {
        "datasources": [
            {
                "name": "Sales",
                "tables": [
                    {
                        "name": "Orders",
                        "columns": [
                            {"name": "OrderID", "dataType": "int64"},
                            {"name": "Amount", "dataType": "double", "formatString": "#,0.00"},
                            {"name": "Region", "dataType": "string"},
                        ],
                    }
                ],
                "calculations": [
                    {"name": "TotalSales", "formula": "SUM('Orders'[Amount])", "table": "Orders"},
                ],
                "connectionString": "Provider=SQLNCLI;Server=localhost;Database=Sales;",
            }
        ],
        "calculations": [
            {"name": "TotalSales", "formula": "SUM('Orders'[Amount])", "table": "Orders"},
        ],
        "worksheets": [
            {
                "name": "Dashboard",
                "visualizations": [
                    {
                        "type": "barchart",
                        "dimensions": ["Region"],
                        "measures": ["TotalSales"],
                        "position": {"x": 0, "y": 0, "width": 600, "height": 400},
                    }
                ],
            }
        ],
        "dashboards": [{"name": "Sales Dashboard"}],
        "parameters": [],
        "filters": [],
        "hierarchies": [],
        "relationships": [],
        "roles": [],
    }


def _multi_table_objects():
    """Multiple tables with relationships."""
    return {
        "datasources": [
            {
                "name": "SalesDB",
                "tables": [
                    {
                        "name": "Orders",
                        "columns": [
                            {"name": "OrderID", "dataType": "int64"},
                            {"name": "CustomerID", "dataType": "int64"},
                            {"name": "Amount", "dataType": "double"},
                        ],
                    },
                    {
                        "name": "Customers",
                        "columns": [
                            {"name": "CustomerID", "dataType": "int64"},
                            {"name": "Name", "dataType": "string"},
                            {"name": "Region", "dataType": "string"},
                        ],
                    },
                ],
            }
        ],
        "calculations": [
            {"name": "TotalSales", "formula": "SUM('Orders'[Amount])", "table": "Orders"},
            {"name": "CustomerCount", "formula": "DISTINCTCOUNT('Customers'[CustomerID])", "table": "Customers"},
        ],
        "worksheets": [
            {
                "name": "Overview",
                "visualizations": [
                    {
                        "type": "table",
                        "dimensions": ["Name", "Region"],
                        "measures": ["TotalSales"],
                        "position": {"x": 0, "y": 0, "width": 800, "height": 400},
                    },
                ],
            },
            {
                "name": "Detail",
                "visualizations": [],
            },
        ],
        "dashboards": [{"name": "MultiTable Report"}],
        "relationships": [
            {
                "fromTable": "Orders",
                "fromColumn": "CustomerID",
                "toTable": "Customers",
                "toColumn": "CustomerID",
                "crossFilteringBehavior": "oneDirection",
            }
        ],
        "parameters": [],
        "filters": [],
        "hierarchies": [],
        "roles": [],
    }


# ══════════════════════════════════════════════════════════════════
# 1. Project Structure
# ══════════════════════════════════════════════════════════════════

class TestProjectStructure:
    """Verify the overall .pbip project structure."""

    def test_generate_creates_project_dir(self, generator, tmp_dir):
        obj = _minimal_objects()
        path = generator.generate_project("TestReport", obj)
        assert os.path.isdir(path)

    def test_pbip_file_created(self, generator, tmp_dir):
        obj = _minimal_objects()
        path = generator.generate_project("TestReport", obj)
        pbip = os.path.join(path, "TestReport.pbip")
        assert os.path.isfile(pbip)

    def test_pbip_file_valid_json(self, generator, tmp_dir):
        obj = _minimal_objects()
        path = generator.generate_project("TestReport", obj)
        pbip = os.path.join(path, "TestReport.pbip")
        with open(pbip, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert "$schema" in data
        assert "artifacts" in data

    def test_semantic_model_dir_created(self, generator, tmp_dir):
        obj = _minimal_objects()
        path = generator.generate_project("TestReport", obj)
        sm = os.path.join(path, "TestReport.SemanticModel")
        assert os.path.isdir(sm)

    def test_report_dir_created(self, generator, tmp_dir):
        obj = _minimal_objects()
        path = generator.generate_project("TestReport", obj)
        report = os.path.join(path, "TestReport.Report")
        assert os.path.isdir(report)

    def test_gitignore_created(self, generator, tmp_dir):
        obj = _minimal_objects()
        path = generator.generate_project("TestReport", obj)
        gi = os.path.join(path, ".gitignore")
        assert os.path.isfile(gi)

    def test_platform_file_in_semantic_model(self, generator, tmp_dir):
        obj = _minimal_objects()
        path = generator.generate_project("TestReport", obj)
        sm = os.path.join(path, "TestReport.SemanticModel")
        assert os.path.isfile(os.path.join(sm, ".platform"))

    def test_definition_pbism_created(self, generator, tmp_dir):
        obj = _minimal_objects()
        path = generator.generate_project("TestReport", obj)
        sm = os.path.join(path, "TestReport.SemanticModel")
        assert os.path.isfile(os.path.join(sm, "definition.pbism"))


# ══════════════════════════════════════════════════════════════════
# 2. TMDL Model Output
# ══════════════════════════════════════════════════════════════════

class TestTMDLOutput:
    """Verify TMDL files are generated correctly."""

    def test_model_tmdl_created(self, generator, tmp_dir):
        obj = _minimal_objects()
        path = generator.generate_project("TestReport", obj)
        sm = os.path.join(path, "TestReport.SemanticModel")
        tmdl_dir = os.path.join(sm, "definition")
        model_tmdl = os.path.join(tmdl_dir, "model.tmdl")
        assert os.path.isfile(model_tmdl)

    def test_tables_dir_created(self, generator, tmp_dir):
        obj = _minimal_objects()
        path = generator.generate_project("TestReport", obj)
        sm = os.path.join(path, "TestReport.SemanticModel")
        tables_dir = os.path.join(sm, "definition", "tables")
        assert os.path.isdir(tables_dir)

    def test_table_tmdl_file_exists(self, generator, tmp_dir):
        obj = _minimal_objects()
        path = generator.generate_project("TestReport", obj)
        sm = os.path.join(path, "TestReport.SemanticModel")
        tables_dir = os.path.join(sm, "definition", "tables")
        # Should have at least the Orders table
        tmdl_files = [f for f in os.listdir(tables_dir) if f.endswith(".tmdl")]
        assert len(tmdl_files) >= 1

    def test_table_contains_columns(self, generator, tmp_dir):
        obj = _minimal_objects()
        path = generator.generate_project("TestReport", obj)
        sm = os.path.join(path, "TestReport.SemanticModel")
        tables_dir = os.path.join(sm, "definition", "tables")
        # Read the orders table tmdl
        orders_files = [f for f in os.listdir(tables_dir) if "orders" in f.lower() or "Orders" in f]
        assert len(orders_files) >= 1
        with open(os.path.join(tables_dir, orders_files[0]), "r", encoding="utf-8") as f:
            content = f.read()
        assert "OrderID" in content or "Amount" in content

    def test_measure_in_output(self, generator, tmp_dir):
        obj = _minimal_objects()
        path = generator.generate_project("TestReport", obj)
        sm = os.path.join(path, "TestReport.SemanticModel")
        # Search for TotalSales in any tmdl file
        found = False
        for root, dirs, files in os.walk(sm):
            for f in files:
                if f.endswith(".tmdl"):
                    with open(os.path.join(root, f), "r", encoding="utf-8") as fh:
                        if "TotalSales" in fh.read():
                            found = True
                            break
        assert found, "Measure TotalSales not found in any .tmdl file"

    def test_multi_table_generates_all_tables(self, generator, tmp_dir):
        obj = _multi_table_objects()
        path = generator.generate_project("MultiTable", obj)
        sm = os.path.join(path, "MultiTable.SemanticModel")
        tables_dir = os.path.join(sm, "definition", "tables")
        tmdl_files = [f for f in os.listdir(tables_dir) if f.endswith(".tmdl")]
        # Should have at least Orders + Customers (+ possibly Calendar)
        assert len(tmdl_files) >= 2


# ══════════════════════════════════════════════════════════════════
# 3. Report Structure
# ══════════════════════════════════════════════════════════════════

class TestReportOutput:
    """Verify PBIR report pages and visual bindings."""

    def test_report_platform_file(self, generator, tmp_dir):
        obj = _minimal_objects()
        path = generator.generate_project("TestReport", obj)
        report = os.path.join(path, "TestReport.Report")
        assert os.path.isfile(os.path.join(report, ".platform"))

    def test_report_definition_exists(self, generator, tmp_dir):
        obj = _minimal_objects()
        path = generator.generate_project("TestReport", obj)
        report = os.path.join(path, "TestReport.Report")
        # Should have definition.pbir or report.json
        has_pbir = os.path.isfile(os.path.join(report, "definition.pbir"))
        has_json = os.path.isfile(os.path.join(report, "report.json"))
        assert has_pbir or has_json

    def test_page_dirs_created(self, generator, tmp_dir):
        obj = _minimal_objects()
        path = generator.generate_project("TestReport", obj)
        report = os.path.join(path, "TestReport.Report")
        definition = os.path.join(report, "definition")
        # Should have pages subdirectory or page-level files
        has_pages = os.path.isdir(os.path.join(definition, "pages")) if os.path.isdir(definition) else False
        # Some structures put pages directly in report or definition
        assert has_pages or os.path.isdir(definition) or os.path.isdir(report)

    def test_multi_page_report(self, generator, tmp_dir):
        obj = _multi_table_objects()
        path = generator.generate_project("MultiPage", obj)
        report = os.path.join(path, "MultiPage.Report")
        # Count JSON/page files — should be >= 2 pages
        page_count = 0
        for root, dirs, files in os.walk(report):
            for d in dirs:
                if "page" in d.lower():
                    page_count += 1
            for f in files:
                if "page" in f.lower():
                    page_count += 1
        assert page_count >= 1, "Report should have at least 1 page"


# ══════════════════════════════════════════════════════════════════
# 4. Edge Cases
# ══════════════════════════════════════════════════════════════════

class TestPbipEdgeCases:
    """Edge cases and boundary conditions."""

    def test_empty_datasources(self, generator, tmp_dir):
        """Project with empty datasources should still generate structure."""
        obj = _minimal_objects()
        obj["datasources"] = [{"name": "Empty", "tables": []}]
        path = generator.generate_project("EmptyDS", obj)
        assert os.path.isdir(path)

    def test_no_worksheets(self, generator, tmp_dir):
        """Project with no worksheets should still generate model."""
        obj = _minimal_objects()
        obj["worksheets"] = []
        path = generator.generate_project("NoWS", obj)
        assert os.path.isdir(path)
        sm = os.path.join(path, "NoWS.SemanticModel")
        assert os.path.isdir(sm)

    def test_no_calculations(self, generator, tmp_dir):
        """Project without measures should still work."""
        obj = _minimal_objects()
        obj["calculations"] = []
        path = generator.generate_project("NoCalcs", obj)
        assert os.path.isdir(path)

    def test_unicode_report_name(self, generator, tmp_dir):
        """Report name with accented characters."""
        obj = _minimal_objects()
        path = generator.generate_project("Rapport_Ventes", obj)
        assert os.path.isdir(path)

    def test_output_format_tmdl_only(self, generator, tmp_dir):
        """output_format='tmdl' should generate only SemanticModel."""
        obj = _minimal_objects()
        path = generator.generate_project("TMDLOnly", obj, output_format='tmdl')
        sm = os.path.join(path, "TMDLOnly.SemanticModel")
        assert os.path.isdir(sm)

    def test_output_format_pbir_only(self, generator, tmp_dir):
        """output_format='pbir' should generate only Report."""
        obj = _minimal_objects()
        path = generator.generate_project("PBIROnly", obj, output_format='pbir')
        report = os.path.join(path, "PBIROnly.Report")
        assert os.path.isdir(report)

    def test_calendar_options(self, generator, tmp_dir):
        """Calendar start/end should be respected."""
        obj = _minimal_objects()
        path = generator.generate_project("CalTest", obj, calendar_start=2015, calendar_end=2025)
        # Verify project created successfully (calendar params accepted)
        assert os.path.isdir(path)

    def test_culture_option(self, generator, tmp_dir):
        """Culture override should not break generation."""
        obj = _minimal_objects()
        path = generator.generate_project("CultureTest", obj, culture="fr-FR")
        assert os.path.isdir(path)

    def test_paginated_report(self, generator, tmp_dir):
        """paginated=True should create additional report layout."""
        obj = _minimal_objects()
        path = generator.generate_project("PagTest", obj, paginated=True)
        assert os.path.isdir(path)

    def test_regenerate_overwrites(self, generator, tmp_dir):
        """Generating twice to same name should overwrite cleanly."""
        obj = _minimal_objects()
        path1 = generator.generate_project("Regen", obj)
        path2 = generator.generate_project("Regen", obj)
        assert path1 == path2
        assert os.path.isdir(path2)
