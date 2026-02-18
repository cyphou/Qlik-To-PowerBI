"""
Comprehensive test suite for TMDLGenerator (PBI Project / TMDL output).
Run with: pytest tests/test_tmdl_generator.py -v
"""
import json
import tempfile
from pathlib import Path

import pytest

from fabric_api.tmdl_generator import TMDLGenerator


# ------------------------------------------------------------------
# 1. Basic project structure
# ------------------------------------------------------------------
def test_basic_project():
    gen = TMDLGenerator()
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "proj"
        model = {
            "name": "M1",
            "compatibilityLevel": 1567,
            "model": {
                "culture": "fr-FR",
                "defaultPowerBIDataSourceVersion": "powerBI_V3",
                "tables": [
                    {
                        "name": "T1",
                        "columns": [
                            {"name": "C1", "dataType": "string", "sourceColumn": "C1"}
                        ],
                    }
                ],
                "relationships": [],
                "annotations": [],
            },
        }
        pbip = gen.create_pbi_project(output_dir=out, report_name="Test1", bim_model=model)
        assert pbip.exists(), ".pbip file missing"
        assert pbip.suffix == ".pbip"
        assert (out / "Test1.SemanticModel" / "definition.pbism").exists()
        assert (out / "Test1.SemanticModel" / "definition" / "database.tmdl").exists()
        assert (out / "Test1.SemanticModel" / "definition" / "model.tmdl").exists()
        assert (out / "Test1.SemanticModel" / "definition" / "tables" / "T1.tmdl").exists()
        assert (out / "Test1.Report" / "definition.pbir").exists()
        assert (out / "Test1.Report" / "definition" / "report.json").exists()




# ------------------------------------------------------------------
# 2. No BIM model (empty default)
# ------------------------------------------------------------------
def test_no_bim():
    gen = TMDLGenerator()
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "proj"
        pbip = gen.create_pbi_project(output_dir=out, report_name="NoBim")
        assert pbip.exists()
        db = (out / "NoBim.SemanticModel" / "definition" / "database.tmdl").read_text("utf-8")
        assert "compatibilityLevel" in db
        tables = list((out / "NoBim.SemanticModel" / "definition" / "tables").iterdir())
        assert len(tables) == 0, "Should have no table files without BIM or PQ script"




# ------------------------------------------------------------------
# 3. Power Query script only (no BIM)
# ------------------------------------------------------------------
def test_pq_script_only():
    gen = TMDLGenerator()
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "proj"
        pq = 'let\n    Source = Sql.Database("srv", "db")\nin\n    Source'
        pbip = gen.create_pbi_project(output_dir=out, report_name="PQOnly", power_query_script=pq)
        assert pbip.exists()
        tmdl = (
            out / "PQOnly.SemanticModel" / "definition" / "tables" / "SampleData.tmdl"
        ).read_text("utf-8")
        assert "table SampleData" in tmdl
        assert "partition" in tmdl
        assert "Source" in tmdl




# ------------------------------------------------------------------
# 4. Relationships file generation
# ------------------------------------------------------------------
def test_relationships():
    gen = TMDLGenerator()
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "proj"
        model = {
            "name": "RelModel",
            "compatibilityLevel": 1567,
            "model": {
                "culture": "en-US",
                "defaultPowerBIDataSourceVersion": "powerBI_V3",
                "tables": [
                    {"name": "Fact", "columns": [{"name": "DimKey", "dataType": "int64", "sourceColumn": "DimKey"}]},
                    {"name": "Dim", "columns": [{"name": "DimKey", "dataType": "int64", "sourceColumn": "DimKey"}]},
                ],
                "relationships": [
                    {
                        "name": "Fact_Dim",
                        "fromTable": "Fact",
                        "fromColumn": "DimKey",
                        "toTable": "Dim",
                        "toColumn": "DimKey",
                        "crossFilteringBehavior": "bothDirections",
                        "isActive": True,
                    }
                ],
            },
        }
        gen.create_pbi_project(output_dir=out, report_name="Rel", bim_model=model)
        content = (out / "Rel.SemanticModel" / "definition" / "relationships.tmdl").read_text("utf-8")
        assert "Fact_Dim" in content
        assert "Fact.DimKey" in content
        assert "Dim.DimKey" in content
        assert "bothDirections" in content




# ------------------------------------------------------------------
# 5. Measures and format strings
# ------------------------------------------------------------------
def test_measures():
    gen = TMDLGenerator()
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "proj"
        model = {
            "name": "MeasureModel",
            "compatibilityLevel": 1567,
            "model": {
                "culture": "en-US",
                "defaultPowerBIDataSourceVersion": "powerBI_V3",
                "tables": [
                    {
                        "name": "Sales",
                        "columns": [{"name": "Amount", "dataType": "double", "sourceColumn": "Amount"}],
                        "measures": [
                            {"name": "Total", "expression": "SUM(Sales[Amount])", "formatString": "#,0.00"},
                            {"name": "Count", "expression": "COUNTROWS(Sales)"},
                        ],
                    }
                ],
            },
        }
        gen.create_pbi_project(output_dir=out, report_name="Meas", bim_model=model)
        tmdl = (out / "Meas.SemanticModel" / "definition" / "tables" / "Sales.tmdl").read_text("utf-8")
        assert "measure Total = SUM(Sales[Amount])" in tmdl
        assert "formatString: #,0.00" in tmdl
        assert "measure Count = COUNTROWS(Sales)" in tmdl




# ------------------------------------------------------------------
# 6. Hierarchies in table TMDL
# ------------------------------------------------------------------
def test_hierarchies():
    gen = TMDLGenerator()
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "proj"
        model = {
            "name": "HierModel",
            "compatibilityLevel": 1567,
            "model": {
                "culture": "en-US",
                "defaultPowerBIDataSourceVersion": "powerBI_V3",
                "tables": [
                    {
                        "name": "Date",
                        "columns": [
                            {"name": "Year", "dataType": "int64", "sourceColumn": "Year"},
                            {"name": "Month", "dataType": "string", "sourceColumn": "Month"},
                        ],
                        "hierarchies": [
                            {
                                "name": "Date Hierarchy",
                                "levels": [
                                    {"name": "Year", "column": "Year"},
                                    {"name": "Month", "column": "Month"},
                                ],
                            }
                        ],
                    }
                ],
            },
        }
        gen.create_pbi_project(output_dir=out, report_name="Hier", bim_model=model)
        tmdl = (out / "Hier.SemanticModel" / "definition" / "tables" / "Date.tmdl").read_text("utf-8")
        assert "hierarchy 'Date Hierarchy'" in tmdl
        assert "level Year" in tmdl
        assert "level Month" in tmdl




# ------------------------------------------------------------------
# 7. Visualizations in report.json
# ------------------------------------------------------------------
def test_visualizations():
    gen = TMDLGenerator()
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "proj"
        gen.create_pbi_project(
            output_dir=out,
            report_name="Viz",
            visualizations=[
                {"type": "barchart", "name": "V1"},
                {"type": "kpi", "name": "V2"},
                {"type": "table", "name": "V3"},
            ],
            dimensions=[{"name": "Dim1"}],
            measures=[{"name": "M1"}, {"name": "M2"}],
        )
        # PBIR format: visuals are individual files under pages/<section>/visuals/<id>/visual.json
        visuals_dir = out / "Viz.Report" / "definition" / "pages" / "ReportSection" / "visuals"
        assert visuals_dir.exists(), "visuals directory missing"
        visual_dirs = list(visuals_dir.iterdir())
        assert len(visual_dirs) == 3, f"Expected 3 visual folders, got {len(visual_dirs)}"
        types = []
        for vd in sorted(visual_dirs):
            vj = json.loads((vd / "visual.json").read_text("utf-8"))
            types.append(vj["visual"]["visualType"])
        assert sorted(types) == sorted(["clusteredBarChart", "card", "tableEx"]), f"Wrong types: {types}"




# ------------------------------------------------------------------
# 8. .pbip JSON structure
# ------------------------------------------------------------------
def test_pbip_json():
    gen = TMDLGenerator()
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "proj"
        pbip = gen.create_pbi_project(output_dir=out, report_name="JsonTest")
        data = json.loads(pbip.read_text("utf-8"))
        assert data["version"] == "1.0"
        assert "artifacts" in data
        assert data["artifacts"][0]["report"]["path"] == "JsonTest.Report"




# ------------------------------------------------------------------
# 9. .pbir dataset reference
# ------------------------------------------------------------------
def test_pbir_reference():
    gen = TMDLGenerator()
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "proj"
        gen.create_pbi_project(output_dir=out, report_name="RefTest")
        pbir = json.loads((out / "RefTest.Report" / "definition.pbir").read_text("utf-8"))
        assert pbir["datasetReference"]["byPath"]["path"] == "../RefTest.SemanticModel"




# ------------------------------------------------------------------
# 10. Table names with spaces (quoting)
# ------------------------------------------------------------------
def test_quoted_names():
    gen = TMDLGenerator()
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "proj"
        model = {
            "name": "QuoteModel",
            "compatibilityLevel": 1567,
            "model": {
                "culture": "en-US",
                "defaultPowerBIDataSourceVersion": "powerBI_V3",
                "tables": [
                    {
                        "name": "Sales Data",
                        "columns": [{"name": "First Name", "dataType": "string", "sourceColumn": "First Name"}],
                        "measures": [{"name": "Total Amount", "expression": "SUM([Amount])"}],
                    }
                ],
            },
        }
        gen.create_pbi_project(output_dir=out, report_name="Quote", bim_model=model)
        tmdl = (out / "Quote.SemanticModel" / "definition" / "tables" / "Sales Data.tmdl").read_text("utf-8")
        assert "table 'Sales Data'" in tmdl
        assert "column 'First Name'" in tmdl
        assert "measure 'Total Amount'" in tmdl




# ------------------------------------------------------------------
# 11. Multiple tables
# ------------------------------------------------------------------
def test_multiple_tables():
    gen = TMDLGenerator()
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "proj"
        tables = [
            {"name": f"Table{i}", "columns": [{"name": "Id", "dataType": "int64", "sourceColumn": "Id"}]}
            for i in range(5)
        ]
        model = {
            "name": "Multi",
            "compatibilityLevel": 1567,
            "model": {"culture": "en-US", "defaultPowerBIDataSourceVersion": "powerBI_V3", "tables": tables},
        }
        gen.create_pbi_project(output_dir=out, report_name="Multi", bim_model=model)
        tmdl_files = list((out / "Multi.SemanticModel" / "definition" / "tables").glob("*.tmdl"))
        assert len(tmdl_files) == 5, f"Expected 5 table files, got {len(tmdl_files)}"




# ------------------------------------------------------------------
# 12. Expressions TMDL
# ------------------------------------------------------------------
def test_expressions():
    gen = TMDLGenerator()
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "proj"
        model = {
            "name": "ExprModel",
            "compatibilityLevel": 1567,
            "model": {
                "culture": "en-US",
                "defaultPowerBIDataSourceVersion": "powerBI_V3",
                "tables": [],
                "expressions": [
                    {
                        "name": "ServerParam",
                        "expression": '"myserver" meta [IsParameterQuery=true]',
                        "lineageTag": "abc-123",
                    }
                ],
            },
        }
        gen.create_pbi_project(output_dir=out, report_name="Expr", bim_model=model)
        expr_file = out / "Expr.SemanticModel" / "definition" / "expressions.tmdl"
        assert expr_file.exists(), "expressions.tmdl missing"
        content = expr_file.read_text("utf-8")
        assert "ServerParam" in content
        assert "abc-123" in content




# ------------------------------------------------------------------
# 13. Inactive relationship
# ------------------------------------------------------------------
def test_inactive_relationship():
    gen = TMDLGenerator()
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "proj"
        model = {
            "name": "InactiveRel",
            "compatibilityLevel": 1567,
            "model": {
                "culture": "en-US",
                "defaultPowerBIDataSourceVersion": "powerBI_V3",
                "tables": [
                    {"name": "A", "columns": [{"name": "K", "dataType": "int64", "sourceColumn": "K"}]},
                    {"name": "B", "columns": [{"name": "K", "dataType": "int64", "sourceColumn": "K"}]},
                ],
                "relationships": [
                    {
                        "name": "A_B",
                        "fromTable": "A",
                        "fromColumn": "K",
                        "toTable": "B",
                        "toColumn": "K",
                        "crossFilteringBehavior": "oneDirection",
                        "isActive": False,
                    }
                ],
            },
        }
        gen.create_pbi_project(output_dir=out, report_name="InactRel", bim_model=model)
        content = (out / "InactRel.SemanticModel" / "definition" / "relationships.tmdl").read_text("utf-8")
        assert "isActive: false" in content




# ------------------------------------------------------------------
# 14. Partition with M expression (fenced code block)
# ------------------------------------------------------------------
def test_partition_expression():
    gen = TMDLGenerator()
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "proj"
        model = {
            "name": "PartModel",
            "compatibilityLevel": 1567,
            "model": {
                "culture": "en-US",
                "defaultPowerBIDataSourceVersion": "powerBI_V3",
                "tables": [
                    {
                        "name": "Data",
                        "columns": [{"name": "Val", "dataType": "double", "sourceColumn": "Val"}],
                        "partitions": [
                            {
                                "name": "DataPartition",
                                "mode": "import",
                                "source": {
                                    "type": "m",
                                    "expression": 'let\n    Source = Excel.Workbook(File.Contents("data.xlsx"))\nin\n    Source',
                                },
                            }
                        ],
                    }
                ],
            },
        }
        gen.create_pbi_project(output_dir=out, report_name="Part", bim_model=model)
        tmdl = (out / "Part.SemanticModel" / "definition" / "tables" / "Data.tmdl").read_text("utf-8")
        assert "partition DataPartition = m" in tmdl
        assert "mode: import" in tmdl
        assert "Excel.Workbook" in tmdl
        assert "source =" in tmdl
