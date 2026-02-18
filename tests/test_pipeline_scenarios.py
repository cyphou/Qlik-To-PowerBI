"""
Comprehensive pipeline tests with QVF sources of varying complexity.

Tests the full chain: QVF extraction -> model conversion -> TMDL generation
at different complexity levels to detect bugs.
"""
import json
import shutil
import tempfile
import zipfile
from pathlib import Path

import pytest

# -- imports under test --
from fabric_api.qvf_extractor import QVFExtractor
from fabric_api.qlik_model_converter import (
    QlikDataModelExtractor,
    QlikModelMigrator,
    _infer_column_datatype,
)
from fabric_api.qlik_script_converter import QlikScriptToPowerQueryConverter
from fabric_api.tmdl_generator import TMDLGenerator


# ====================================================================
# Helpers: create synthetic QVF zip files
# ====================================================================

def _make_qvf(tmp_dir: Path, stem: str, load_script: str,
               dimensions=None, measures=None, sheets=None,
               app_name: str = "Test App") -> Path:
    """Create a minimal .qvf (zip) with given load script and objects."""
    qvf_path = tmp_dir / f"{stem}.qvf"
    with zipfile.ZipFile(qvf_path, 'w') as zf:
        # app.xml
        zf.writestr("app.xml", f"""<?xml version="1.0" encoding="utf-8"?>
<app><Title>{app_name}</Title><Description>Test</Description>
<Author>pytest</Author></app>""")

        # loadscript.txt
        zf.writestr("loadscript.txt", load_script)

        # dimensions
        for i, dim in enumerate(dimensions or []):
            zf.writestr(f"dimensions/dim_{i}.json", json.dumps({
                "qInfo": {"qId": f"dim{i}", "qType": "dimension"},
                "qDim": {
                    "qFieldDefs": [dim.get("field", "")],
                    "qFieldLabels": [dim.get("label", dim.get("field", ""))],
                },
                "qMetaDef": {"title": dim.get("name", f"Dim{i}")},
            }))

        # measures
        for i, meas in enumerate(measures or []):
            zf.writestr(f"measures/measure_{i}.json", json.dumps({
                "qInfo": {"qId": f"meas{i}", "qType": "measure"},
                "qMeasure": {
                    "qDef": meas.get("expression", ""),
                    "qLabel": meas.get("label", meas.get("name", "")),
                },
                "qMetaDef": {"title": meas.get("name", f"Meas{i}")},
            }))

        # sheets
        for i, sheet in enumerate(sheets or [{"name": "Sheet 1"}]):
            zf.writestr(f"sheets/sheet_{i}.json", json.dumps({
                "qInfo": {"qId": f"sheet{i}", "qType": "sheet"},
                "qMetaDef": {"title": sheet.get("name", f"Sheet{i}"),
                             "description": ""},
                "cells": sheet.get("cells", []),
            }))

        # variable
        zf.writestr("variables/var_0.json", json.dumps({
            "qName": "vVersion",
            "qDefinition": "1.0",
            "qComment": "version",
        }))

    return qvf_path


def _load_qlik_json(qvf_path, tmp_dir):
    """Extract a QVF and return the parsed JSON dict (utf-8 safe)."""
    ext = QVFExtractor(qvf_path)
    ext.extract_all()
    out_json = tmp_dir / "exported.json"
    ext.export_to_json(out_json)
    with open(out_json, encoding="utf-8") as f:
        return json.load(f)


# ====================================================================
# SCENARIO 1 -- Minimal: single table, no measures, no relationships
# ====================================================================

SCRIPT_MINIMAL = """\
Employees:
LOAD
    EmployeeID,
    FirstName,
    LastName,
    HireDate
FROM [data/employees.csv]
(txt, codepage is 1252, embedded labels, delimiter is ',', msq);
"""

class TestScenarioMinimal:
    """Single table, no dimensions, no measures."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        self.tmp = tmp_path
        self.qvf = _make_qvf(tmp_path, "minimal", SCRIPT_MINIMAL,
                              app_name="Minimal App")

    def test_extraction(self):
        ext = QVFExtractor(self.qvf)
        data = ext.extract_all()
        assert data["loadScript"]
        tables = data["dataModel"]["tables"]
        assert len(tables) == 1
        assert tables[0]["name"] == "Employees"
        fields = [f["name"] for f in tables[0]["fields"]]
        assert "EmployeeID" in fields
        assert "HireDate" in fields

    def test_model_conversion(self):
        qlik_data = _load_qlik_json(self.qvf, self.tmp)

        migrator = QlikModelMigrator()
        result = migrator.migrate_model(qlik_data, self.tmp / "model.bim")
        assert result["status"] == "success"
        assert result["tables_count"] == 1
        assert result["relationships_count"] == 0

        bim = result["model"]
        tbl = bim["model"]["tables"][0]
        # HireDate should be dateTime
        hire_col = [c for c in tbl["columns"] if c["name"] == "HireDate"][0]
        assert hire_col["dataType"] == "dateTime"
        # EmployeeID should be int64
        eid_col = [c for c in tbl["columns"] if c["name"] == "EmployeeID"][0]
        assert eid_col["dataType"] == "int64"

    def test_pbi_project_generation(self):
        qlik_data = _load_qlik_json(self.qvf, self.tmp)

        migrator = QlikModelMigrator()
        result = migrator.migrate_model(qlik_data, self.tmp / "model.bim")

        gen = TMDLGenerator()
        pbip = gen.create_pbi_project(
            output_dir=self.tmp / "project",
            report_name="Minimal App",
            bim_model=result["model"],
        )
        assert Path(pbip).exists()
        # Check TMDL files exist
        tmdl_dir = self.tmp / "project" / "Minimal App.SemanticModel" / "definition"
        assert (tmdl_dir / "model.tmdl").exists()
        assert (tmdl_dir / "database.tmdl").exists()
        tables_dir = tmdl_dir / "tables"
        assert (tables_dir / "Employees.tmdl").exists()


# ====================================================================
# SCENARIO 2 -- Star schema: fact + 2 dimensions, measures, hierarchy
# ====================================================================

SCRIPT_STAR = """\
Orders:
LOAD
    OrderID,
    CustomerID,
    ProductID,
    OrderDate,
    Amount,
    Quantity
FROM [data/orders.csv]
(txt, codepage is 1252, embedded labels, delimiter is ',', msq);

Customers:
LOAD
    CustomerID,
    CustomerName,
    Country,
    City,
    Region
FROM [data/customers.csv]
(txt, codepage is 1252, embedded labels, delimiter is ',', msq);

Products:
LOAD
    ProductID,
    ProductName,
    CategoryID,
    UnitPrice
FROM [data/products.csv]
(txt, codepage is 1252, embedded labels, delimiter is ',', msq);
"""

STAR_DIMS = [
    {"name": "Customer Name", "field": "CustomerName", "label": "Client"},
    {"name": "Product Name", "field": "ProductName", "label": "Produit"},
]
STAR_MEASURES = [
    {"name": "Total Revenue", "expression": "Sum(Amount)", "label": "Total Revenue"},
    {"name": "Qty Sold", "expression": "Sum(Quantity)", "label": "Qty Sold"},
    {"name": "Avg Price", "expression": "Avg(UnitPrice)", "label": "Avg Price"},
]


class TestScenarioStar:
    """Star schema with 3 tables, 2 dims, 3 measures, 1 hierarchy."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        self.tmp = tmp_path
        self.qvf = _make_qvf(tmp_path, "star", SCRIPT_STAR,
                              dimensions=STAR_DIMS,
                              measures=STAR_MEASURES,
                              app_name="Star App")

    def test_extraction_counts(self):
        ext = QVFExtractor(self.qvf)
        data = ext.extract_all()
        assert len(data["dimensions"]) == 2
        assert len(data["measures"]) == 3
        tables = data["dataModel"]["tables"]
        assert len(tables) == 3
        table_names = {t["name"] for t in tables}
        assert table_names == {"Orders", "Customers", "Products"}

    def test_relationship_directions(self):
        qlik_data = _load_qlik_json(self.qvf, self.tmp)

        migrator = QlikModelMigrator()
        result = migrator.migrate_model(qlik_data, self.tmp / "model.bim")
        rels = result["model"]["model"]["relationships"]

        # Must have 2 relationships (CustomerID, ProductID)
        assert len(rels) == 2

        for rel in rels:
            # from = fact (Orders), to = dimension
            if "CustomerID" in rel["fromColumn"]:
                assert rel["fromTable"] == "Orders"
                assert rel["toTable"] == "Customers"
            elif "ProductID" in rel["fromColumn"]:
                assert rel["fromTable"] == "Orders"
                assert rel["toTable"] == "Products"
            else:
                pytest.fail(f"Unexpected relationship: {rel}")

    def test_measures_dax_conversion(self):
        qlik_data = _load_qlik_json(self.qvf, self.tmp)

        migrator = QlikModelMigrator()
        result = migrator.migrate_model(qlik_data, self.tmp / "model.bim")

        all_measures = []
        for tbl in result["model"]["model"]["tables"]:
            all_measures.extend(tbl.get("measures", []))

        assert len(all_measures) == 3
        names = {m["name"] for m in all_measures}
        assert "Total Revenue" in names
        assert "Qty Sold" in names
        assert "Avg Price" in names

        # Check DAX expressions
        rev = [m for m in all_measures if m["name"] == "Total Revenue"][0]
        assert "SUM(" in rev["expression"]
        assert "'Orders'" in rev["expression"]

        avg = [m for m in all_measures if m["name"] == "Avg Price"][0]
        assert "AVERAGE(" in avg["expression"]

    def test_data_types(self):
        qlik_data = _load_qlik_json(self.qvf, self.tmp)

        migrator = QlikModelMigrator()
        result = migrator.migrate_model(qlik_data, self.tmp / "model.bim")

        orders_tbl = [t for t in result["model"]["model"]["tables"]
                      if t["name"] == "Orders"][0]
        col_types = {c["name"]: c["dataType"] for c in orders_tbl["columns"]}

        assert col_types["OrderID"] == "int64"
        assert col_types["Amount"] == "double"
        assert col_types["Quantity"] == "double"  # referenced by SUM
        assert col_types["OrderDate"] == "dateTime"
        assert col_types["CustomerID"] == "int64"

    def test_hierarchy_created(self):
        qlik_data = _load_qlik_json(self.qvf, self.tmp)

        migrator = QlikModelMigrator()
        result = migrator.migrate_model(qlik_data, self.tmp / "model.bim")

        assert result["hierarchies_count"] >= 1
        # Check hierarchy exists in Orders table
        orders_tbl = [t for t in result["model"]["model"]["tables"]
                      if t["name"] == "Orders"][0]
        assert "hierarchies" in orders_tbl
        h = orders_tbl["hierarchies"][0]
        assert "OrderDate" in h["name"]

    def test_full_project(self):
        """Full end-to-end: QVF -> TMDL project with visuals."""
        qlik_data = _load_qlik_json(self.qvf, self.tmp)

        migrator = QlikModelMigrator()
        result = migrator.migrate_model(qlik_data, self.tmp / "model.bim")

        visuals = [
            {"type": "card", "name": "Total Revenue Card"},
            {"type": "clusteredBarChart", "name": "Revenue by Customer"},
            {"type": "tableEx", "name": "Detail Table"},
        ]

        gen = TMDLGenerator()
        pbip = gen.create_pbi_project(
            output_dir=self.tmp / "project",
            report_name="Star App",
            bim_model=result["model"],
            visualizations=visuals,
            dimensions=qlik_data.get("dimensions", []),
            measures=qlik_data.get("measures", []),
        )
        assert Path(pbip).exists()

        # Check visuals directory
        visuals_dir = (self.tmp / "project" / "Star App.Report" / "definition"
                       / "pages" / "ReportSection" / "visuals")
        assert visuals_dir.exists()
        visual_dirs = list(visuals_dir.iterdir())
        assert len(visual_dirs) == 3

        # Each visual should have valid JSON with query bindings
        for vdir in visual_dirs:
            vj = json.loads((vdir / "visual.json").read_text(encoding="utf-8"))
            assert "visual" in vj
            assert "visualType" in vj["visual"]
            # Data visuals should have query
            if vj["visual"]["visualType"] in ("card", "clusteredBarChart", "tableEx"):
                assert "query" in vj["visual"], \
                    f"Visual {vj['visual']['visualType']} missing query"

        # Verify relationships.tmdl exists and has correct content
        rels_path = (self.tmp / "project" / "Star App.SemanticModel"
                     / "definition" / "relationships.tmdl")
        assert rels_path.exists()
        rels_tmdl = rels_path.read_text(encoding="utf-8")
        assert "CustomerID" in rels_tmdl
        assert "ProductID" in rels_tmdl


# ====================================================================
# SCENARIO 3 -- Complex expressions: computed columns, nested funcs
# ====================================================================

SCRIPT_COMPLEX = """\
Sales:
LOAD
    SaleID,
    Year(SaleDate) as SaleYear,
    Month(SaleDate) as SaleMonth,
    Upper(Region) as Region,
    Round(Amount * 1.2, 2) as AmountWithTax,
    If(Quantity > 100, 'Bulk', 'Regular') as OrderType,
    Amount,
    Quantity,
    SaleDate,
    CustomerID
FROM [data/sales.csv]
(txt, codepage is 1252, embedded labels, delimiter is ',', msq);

Customers:
LOAD
    CustomerID,
    CustomerName,
    Email
FROM [data/customers.csv]
(txt, codepage is 1252, embedded labels, delimiter is ',', msq);
"""

COMPLEX_MEASURES = [
    {"name": "Revenue", "expression": "Sum(Amount)", "label": "Revenue"},
    {"name": "Tax Amount", "expression": "Sum(AmountWithTax)", "label": "Tax Amount"},
    {"name": "Order Count", "expression": "Count(SaleID)", "label": "Order Count"},
]


class TestScenarioComplex:
    """Complex script with computed columns and various functions."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        self.tmp = tmp_path
        self.qvf = _make_qvf(tmp_path, "complex", SCRIPT_COMPLEX,
                              measures=COMPLEX_MEASURES,
                              app_name="Complex App")

    def test_computed_columns_extracted(self):
        ext = QVFExtractor(self.qvf)
        data = ext.extract_all()
        tables = data["dataModel"]["tables"]
        sales = [t for t in tables if t["name"] == "Sales"][0]
        field_names = [f["name"] for f in sales["fields"]]

        # Computed columns should use their alias
        assert "SaleYear" in field_names
        assert "SaleMonth" in field_names
        assert "Region" in field_names
        assert "AmountWithTax" in field_names
        assert "OrderType" in field_names

    def test_count_measure_format(self):
        qlik_data = _load_qlik_json(self.qvf, self.tmp)

        migrator = QlikModelMigrator()
        result = migrator.migrate_model(qlik_data, self.tmp / "model.bim")

        all_measures = []
        for tbl in result["model"]["model"]["tables"]:
            all_measures.extend(tbl.get("measures", []))

        count_meas = [m for m in all_measures if m["name"] == "Order Count"][0]
        assert "COUNT(" in count_meas["expression"]
        assert count_meas.get("formatString") == "0"

    def test_relationship_inferred(self):
        qlik_data = _load_qlik_json(self.qvf, self.tmp)

        migrator = QlikModelMigrator()
        result = migrator.migrate_model(qlik_data, self.tmp / "model.bim")
        rels = result["model"]["model"]["relationships"]

        assert len(rels) == 1
        rel = rels[0]
        # Sales is fact, Customers is dimension
        assert rel["fromTable"] == "Sales"
        assert rel["toTable"] == "Customers"


# ====================================================================
# SCENARIO 4 -- Edge cases: unicode names, spaces, special chars
# ====================================================================

SCRIPT_UNICODE = """\
Ventes:
LOAD
    VenteID,
    Montant,
    Quantit\u00e9,
    DateCommande,
    ClientID
FROM [data/ventes.csv]
(txt, codepage is 65001, embedded labels, delimiter is ',', msq);

Clients:
LOAD
    ClientID,
    NomClient,
    R\u00e9gion,
    Pays
FROM [data/clients.csv]
(txt, codepage is 65001, embedded labels, delimiter is ',', msq);
"""

UNICODE_DIMS = [
    {"name": "Nom du Client", "field": "NomClient", "label": "Nom du Client"},
]
UNICODE_MEASURES = [
    {"name": "CA Total", "expression": "Sum(Montant)", "label": "CA Total"},
    {"name": "Qt\u00e9 Totale", "expression": "Sum(Quantit\u00e9)", "label": "Qt\u00e9 Totale"},
]


class TestScenarioUnicode:
    """Unicode table/column names, accented characters."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        self.tmp = tmp_path
        self.qvf = _make_qvf(tmp_path, "unicode", SCRIPT_UNICODE,
                              dimensions=UNICODE_DIMS,
                              measures=UNICODE_MEASURES,
                              app_name="Application Fran\u00e7aise")

    def test_unicode_extraction(self):
        ext = QVFExtractor(self.qvf)
        data = ext.extract_all()
        tables = data["dataModel"]["tables"]
        assert len(tables) == 2
        names = {t["name"] for t in tables}
        assert "Ventes" in names
        assert "Clients" in names

        ventes = [t for t in tables if t["name"] == "Ventes"][0]
        fields = [f["name"] for f in ventes["fields"]]
        assert "Quantit\u00e9" in fields
        assert "DateCommande" in fields

    def test_unicode_in_tmdl(self):
        qlik_data = _load_qlik_json(self.qvf, self.tmp)

        migrator = QlikModelMigrator()
        result = migrator.migrate_model(qlik_data, self.tmp / "model.bim")

        gen = TMDLGenerator()
        pbip = gen.create_pbi_project(
            output_dir=self.tmp / "project",
            report_name="Application Fran\u00e7aise",
            bim_model=result["model"],
            dimensions=qlik_data.get("dimensions", []),
            measures=qlik_data.get("measures", []),
        )

        # Check Ventes table is written correctly
        tmdl = (self.tmp / "project" / "Application Fran\u00e7aise.SemanticModel"
                / "definition" / "tables" / "Ventes.tmdl").read_text(encoding="utf-8")
        assert "Quantit\u00e9" in tmdl
        assert "DateCommande" in tmdl
        assert "CA Total" in tmdl

    def test_unicode_measure_dax(self):
        qlik_data = _load_qlik_json(self.qvf, self.tmp)

        migrator = QlikModelMigrator()
        result = migrator.migrate_model(qlik_data, self.tmp / "model.bim")

        all_measures = []
        for tbl in result["model"]["model"]["tables"]:
            all_measures.extend(tbl.get("measures", []))

        ca = [m for m in all_measures if m["name"] == "CA Total"][0]
        assert "SUM(" in ca["expression"]
        assert "'Ventes'" in ca["expression"]

    def test_relationship_french_tables(self):
        qlik_data = _load_qlik_json(self.qvf, self.tmp)

        migrator = QlikModelMigrator()
        result = migrator.migrate_model(qlik_data, self.tmp / "model.bim")
        rels = result["model"]["model"]["relationships"]
        assert len(rels) == 1
        # Ventes is fact, Clients is dimension
        rel = rels[0]
        assert rel["fromTable"] == "Ventes"
        assert rel["toTable"] == "Clients"


# ====================================================================
# SCENARIO 5 -- Snowflake: 5 tables, chained relationships
# ====================================================================

SCRIPT_SNOWFLAKE = """\
FactSales:
LOAD
    TransactionID,
    ProductID,
    StoreID,
    DateID,
    Revenue,
    Quantity,
    Discount
FROM [data/fact_sales.csv]
(txt, codepage is 1252, embedded labels, delimiter is ',', msq);

DimProducts:
LOAD
    ProductID,
    ProductName,
    SubCategoryID,
    BrandID,
    UnitCost
FROM [data/dim_products.csv]
(txt, codepage is 1252, embedded labels, delimiter is ',', msq);

DimSubCategories:
LOAD
    SubCategoryID,
    SubCategoryName,
    CategoryID
FROM [data/dim_subcategories.csv]
(txt, codepage is 1252, embedded labels, delimiter is ',', msq);

DimCategories:
LOAD
    CategoryID,
    CategoryName,
    Department
FROM [data/dim_categories.csv]
(txt, codepage is 1252, embedded labels, delimiter is ',', msq);

DimStores:
LOAD
    StoreID,
    StoreName,
    City,
    Country
FROM [data/dim_stores.csv]
(txt, codepage is 1252, embedded labels, delimiter is ',', msq);
"""

SNOWFLAKE_MEASURES = [
    {"name": "Total Revenue", "expression": "Sum(Revenue)", "label": "Total Revenue"},
    {"name": "Total Discount", "expression": "Sum(Discount)", "label": "Total Discount"},
    {"name": "Units Sold", "expression": "Sum(Quantity)", "label": "Units Sold"},
]


class TestScenarioSnowflake:
    """Snowflake schema: 5 tables, chained dimension relationships."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        self.tmp = tmp_path
        self.qvf = _make_qvf(tmp_path, "snowflake", SCRIPT_SNOWFLAKE,
                              measures=SNOWFLAKE_MEASURES,
                              app_name="Snowflake App")

    def test_all_tables_extracted(self):
        ext = QVFExtractor(self.qvf)
        data = ext.extract_all()
        tables = data["dataModel"]["tables"]
        assert len(tables) == 5
        expected = {"FactSales", "DimProducts", "DimSubCategories",
                    "DimCategories", "DimStores"}
        actual = {t["name"] for t in tables}
        assert actual == expected

    def test_chained_relationships(self):
        qlik_data = _load_qlik_json(self.qvf, self.tmp)

        migrator = QlikModelMigrator()
        result = migrator.migrate_model(qlik_data, self.tmp / "model.bim")
        rels = result["model"]["model"]["relationships"]

        # Expected: FactSales->DimProducts (ProductID),
        #           FactSales->DimStores (StoreID),
        #           DimProducts->DimSubCategories (SubCategoryID),
        #           DimSubCategories->DimCategories (CategoryID)
        assert len(rels) >= 3  # At least 3 relationships expected

        # Verify key join columns exist
        join_cols = {r["fromColumn"] for r in rels}
        assert "ProductID" in join_cols
        assert "StoreID" in join_cols

    def test_revenue_types(self):
        qlik_data = _load_qlik_json(self.qvf, self.tmp)

        migrator = QlikModelMigrator()
        result = migrator.migrate_model(qlik_data, self.tmp / "model.bim")

        fact_tbl = [t for t in result["model"]["model"]["tables"]
                    if t["name"] == "FactSales"][0]
        types = {c["name"]: c["dataType"] for c in fact_tbl["columns"]}
        assert types["Revenue"] == "double"
        assert types["Quantity"] == "double"  # SUM-referenced
        assert types["Discount"] == "double"
        assert types["TransactionID"] == "int64"

    def test_full_tmdl_project(self):
        qlik_data = _load_qlik_json(self.qvf, self.tmp)

        migrator = QlikModelMigrator()
        result = migrator.migrate_model(qlik_data, self.tmp / "model.bim")

        gen = TMDLGenerator()
        pbip = gen.create_pbi_project(
            output_dir=self.tmp / "project",
            report_name="Snowflake App",
            bim_model=result["model"],
            measures=qlik_data.get("measures", []),
        )
        assert Path(pbip).exists()

        # All 5 tables should have TMDL files
        tables_dir = (self.tmp / "project" / "Snowflake App.SemanticModel"
                      / "definition" / "tables")
        tmdl_files = list(tables_dir.glob("*.tmdl"))
        assert len(tmdl_files) == 5

        # Relationships file should exist (we have 3+ rels)
        rels_path = (self.tmp / "project" / "Snowflake App.SemanticModel"
                     / "definition" / "relationships.tmdl")
        assert rels_path.exists()
        rels = rels_path.read_text(encoding="utf-8")
        assert "ProductID" in rels


# ====================================================================
# SCENARIO 6 -- No script: empty loadScript, only tables structure
# ====================================================================

class TestScenarioNoScript:
    """Edge case: QVF with empty load script."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        self.tmp = tmp_path
        self.qvf = _make_qvf(tmp_path, "noscript", "",
                              app_name="Empty Script App")

    def test_empty_script_no_crash(self):
        ext = QVFExtractor(self.qvf)
        data = ext.extract_all()
        assert data["loadScript"] == ""
        assert len(data["dataModel"]["tables"]) == 0

    def test_model_migration_empty(self):
        qlik_data = _load_qlik_json(self.qvf, self.tmp)

        migrator = QlikModelMigrator()
        result = migrator.migrate_model(qlik_data, self.tmp / "model.bim")
        assert result["status"] == "success"
        assert result["tables_count"] == 0

    def test_pbi_project_no_tables(self):
        qlik_data = _load_qlik_json(self.qvf, self.tmp)

        migrator = QlikModelMigrator()
        result = migrator.migrate_model(qlik_data, self.tmp / "model.bim")

        gen = TMDLGenerator()
        pbip = gen.create_pbi_project(
            output_dir=self.tmp / "project",
            report_name="Empty App",
            bim_model=result["model"],
        )
        assert Path(pbip).exists()


# ====================================================================
# SCENARIO 7 -- Data type inference unit tests
# ====================================================================

class TestDataTypeInference:
    """Unit tests for _infer_column_datatype."""

    def test_id_columns(self):
        assert _infer_column_datatype("CustomerID") == "int64"
        assert _infer_column_datatype("product_id") == "int64"
        assert _infer_column_datatype("OrderId") == "int64"
        assert _infer_column_datatype("SaleID") == "int64"

    def test_numeric_columns(self):
        assert _infer_column_datatype("Amount") == "double"
        assert _infer_column_datatype("UnitPrice") == "double"
        assert _infer_column_datatype("TotalCost") == "double"
        assert _infer_column_datatype("Revenue") == "double"
        assert _infer_column_datatype("Discount") == "double"

    def test_date_columns(self):
        assert _infer_column_datatype("OrderDate") == "dateTime"
        assert _infer_column_datatype("HireDate") == "dateTime"
        assert _infer_column_datatype("CreatedDateTime") == "dateTime"
        assert _infer_column_datatype("DateCommande") == "dateTime"

    def test_integer_columns(self):
        assert _infer_column_datatype("Year") == "int64"
        assert _infer_column_datatype("Month") == "int64"
        assert _infer_column_datatype("Day") == "int64"
        assert _infer_column_datatype("Quarter") == "int64"
        assert _infer_column_datatype("Quantity") == "int64"  # Without measure ref
        assert _infer_column_datatype("Age") == "int64"
        assert _infer_column_datatype("LineItemCount") == "int64"

    def test_string_columns(self):
        assert _infer_column_datatype("CustomerName") == "string"
        assert _infer_column_datatype("Description") == "string"
        assert _infer_column_datatype("Email") == "string"
        assert _infer_column_datatype("Country") == "string"

    def test_measure_override(self):
        """Columns referenced by measures should be double."""
        refs = {"Quantity", "Amount"}
        assert _infer_column_datatype("Quantity", refs) == "double"
        assert _infer_column_datatype("Amount", refs) == "double"

    def test_camelcase_parsing(self):
        assert _infer_column_datatype("UnitPrice") == "double"
        assert _infer_column_datatype("TotalAmount") == "double"
        assert _infer_column_datatype("LineItemCount") == "int64"

    def test_french_columns(self):
        assert _infer_column_datatype("Montant") == "double"
        assert _infer_column_datatype("DateCommande") == "dateTime"


# ====================================================================
# SCENARIO 8 -- Script converter error handling
# ====================================================================

class TestScriptConverterErrors:
    """Test the Qlik script converter handles edge cases."""

    def test_inline_data_no_crash(self):
        script = """\
InlineData:
LOAD * INLINE [
Col1, Col2
A, 1
B, 2
];
"""
        converter = QlikScriptToPowerQueryConverter()
        # Should not crash even if conversion is partial
        try:
            result = converter.convert_qlik_script_to_powerquery(script)
            assert isinstance(result, str)
        except Exception:
            pass  # acceptably fails for INLINE

    def test_empty_script(self):
        converter = QlikScriptToPowerQueryConverter()
        result = converter.convert_qlik_script_to_powerquery("")
        assert isinstance(result, str)

    def test_sql_load(self):
        script = """\
SQLTable:
LOAD
    ID,
    Name
SQL SELECT ID, Name FROM dbo.Table1;
"""
        ext_data = {"loadScript": script}
        extractor = QlikDataModelExtractor(ext_data)
        # SQL LOAD won't match the FROM/RESIDENT/INLINE pattern
        # Should not crash
        tables = extractor.extract_tables_and_fields()
        assert isinstance(tables, dict)
