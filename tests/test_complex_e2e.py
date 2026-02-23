"""
COMPLEX END-TO-END TESTS — Level 3

Full pipeline simulations: QVF→BIM→TMDL→PBIR with realistic multi-table
models, RLS, hierarchies, themes, drill-through, multi-page reports,
and complete TMDL validation.
"""
import json
import tempfile
import zipfile
from pathlib import Path

import pytest

from fabric_api.dax_converter import (
    convert_qlik_expression_to_dax,
    convert_measures_to_dax,
    convert_dimensions_to_dax,
)
from fabric_api.m_query_generator import generate_all_m_queries
from fabric_api.m_query_builder import (
    inject_m_steps, build_m_query_with_transforms,
    rename_columns, filter_values, group_by, upper_case,
    add_custom_column, join_tables, unpivot, sort_rows,
)
from fabric_api.qlik_script_converter import QlikScriptToPowerQueryConverter
from fabric_api.tmdl_generator import TMDLGenerator, create_pbi_project_from_migration
from fabric_api.visual_generator import create_visual_container, generate_visual_containers


# ══════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════
def _make_synthetic_qvf(tmp_path: Path, qlik_data: dict) -> Path:
    """Build a synthetic QVF zip for extraction tests."""
    qvf_path = tmp_path / "test_app.qvf"
    with zipfile.ZipFile(qvf_path, "w") as zf:
        zf.writestr("qlik-app.json", json.dumps(qlik_data, ensure_ascii=False))
    return qvf_path


# ══════════════════════════════════════════════════════════════════
# 1. Full Retail Data Model — Star Schema
# ══════════════════════════════════════════════════════════════════
class TestRetailStarSchema:
    """Simulates a full retail analytics model conversion:
    - 5 tables (Sales, Products, Customers, Calendar, Stores)
    - Relationships (star schema)
    - RLS roles
    - Hierarchies
    - Measures with set analysis + TOTAL + variables
    - Multiple pages with diverse visual types
    - Theme + bookmarks
    """

    @staticmethod
    def _retail_model():
        return {
            "compatibilityLevel": 1600,
            "model": {
                "culture": "en-US",
                "defaultPowerBIDataSourceVersion": "powerBI_V3",
                "tables": [
                    {
                        "name": "Sales",
                        "description": "Fact table — all transactions",
                        "columns": [
                            {"name": "SaleID", "dataType": "int64", "sourceColumn": "SaleID"},
                            {"name": "ProductID", "dataType": "int64", "sourceColumn": "ProductID"},
                            {"name": "CustomerID", "dataType": "int64", "sourceColumn": "CustomerID"},
                            {"name": "StoreID", "dataType": "int64", "sourceColumn": "StoreID"},
                            {"name": "Date", "dataType": "dateTime", "sourceColumn": "Date"},
                            {"name": "Quantity", "dataType": "int64", "sourceColumn": "Quantity",
                             "displayFolder": "Financials"},
                            {"name": "Amount", "dataType": "double", "sourceColumn": "Amount",
                             "displayFolder": "Financials", "formatString": "#,0.00"},
                            {"name": "Discount", "dataType": "double", "sourceColumn": "Discount",
                             "displayFolder": "Financials", "formatString": "0.00%"},
                        ],
                        "measures": [
                            {"name": "Total Revenue", "expression": "SUM('Sales'[Amount])",
                             "displayFolder": "KPIs", "description": "Sum of all sale amounts",
                             "formatString": "#,0.00"},
                            {"name": "YTD Revenue",
                             "expression": "TOTALYTD(SUM('Sales'[Amount]), 'Calendar'[Date])",
                             "displayFolder": "KPIs"},
                            {"name": "Avg Basket",
                             "expression": "DIVIDE(SUM('Sales'[Amount]), DISTINCTCOUNT('Sales'[SaleID]))",
                             "displayFolder": "KPIs"},
                            {"name": "Customer Count",
                             "expression": "DISTINCTCOUNT('Sales'[CustomerID])",
                             "displayFolder": "KPIs"},
                        ],
                    },
                    {
                        "name": "Products",
                        "description": "Product dimension",
                        "columns": [
                            {"name": "ProductID", "dataType": "int64", "sourceColumn": "ProductID"},
                            {"name": "ProductName", "dataType": "string", "sourceColumn": "ProductName"},
                            {"name": "Category", "dataType": "string", "sourceColumn": "Category",
                             "displayFolder": "Classification"},
                            {"name": "SubCategory", "dataType": "string", "sourceColumn": "SubCategory",
                             "displayFolder": "Classification"},
                            {"name": "UnitPrice", "dataType": "double", "sourceColumn": "UnitPrice",
                             "formatString": "#,0.00"},
                        ],
                        "hierarchies": [
                            {
                                "name": "Product Hierarchy",
                                "levels": [
                                    {"name": "Category", "column": "Category"},
                                    {"name": "SubCategory", "column": "SubCategory"},
                                    {"name": "ProductName", "column": "ProductName"},
                                ],
                            },
                        ],
                    },
                    {
                        "name": "Customers",
                        "description": "Customer dimension",
                        "columns": [
                            {"name": "CustomerID", "dataType": "int64", "sourceColumn": "CustomerID"},
                            {"name": "Name", "dataType": "string", "sourceColumn": "Name"},
                            {"name": "City", "dataType": "string", "sourceColumn": "City",
                             "dataCategory": "City"},
                            {"name": "Country", "dataType": "string", "sourceColumn": "Country",
                             "dataCategory": "Country"},
                            {"name": "Segment", "dataType": "string", "sourceColumn": "Segment"},
                        ],
                        "hierarchies": [
                            {
                                "name": "Geography",
                                "levels": [
                                    {"name": "Country", "column": "Country"},
                                    {"name": "City", "column": "City"},
                                ],
                            },
                        ],
                    },
                    {
                        "name": "Stores",
                        "columns": [
                            {"name": "StoreID", "dataType": "int64", "sourceColumn": "StoreID"},
                            {"name": "StoreName", "dataType": "string", "sourceColumn": "StoreName"},
                            {"name": "Region", "dataType": "string", "sourceColumn": "Region",
                             "dataCategory": "StateOrProvince"},
                        ],
                    },
                    {
                        "name": "Calendar",
                        "dataCategory": "Time",
                        "columns": [
                            {"name": "Date", "dataType": "dateTime", "sourceColumn": "Date"},
                            {"name": "Year", "dataType": "int64", "sourceColumn": "Year"},
                            {"name": "Quarter", "dataType": "int64", "sourceColumn": "Quarter"},
                            {"name": "Month", "dataType": "int64", "sourceColumn": "Month"},
                            {"name": "MonthName", "dataType": "string", "sourceColumn": "MonthName"},
                        ],
                    },
                ],
                "relationships": [
                    {"name": "Sales_Products", "fromTable": "Sales", "fromColumn": "ProductID",
                     "toTable": "Products", "toColumn": "ProductID"},
                    {"name": "Sales_Customers", "fromTable": "Sales", "fromColumn": "CustomerID",
                     "toTable": "Customers", "toColumn": "CustomerID"},
                    {"name": "Sales_Stores", "fromTable": "Sales", "fromColumn": "StoreID",
                     "toTable": "Stores", "toColumn": "StoreID"},
                    {"name": "Sales_Calendar", "fromTable": "Sales", "fromColumn": "Date",
                     "toTable": "Calendar", "toColumn": "Date"},
                ],
                "roles": [
                    {
                        "name": "RegionalManager",
                        "modelPermission": "read",
                        "description": "Restrict to user's region",
                        "tablePermissions": [
                            {"name": "Stores",
                             "filterExpression": "'Stores'[Region] = USERPRINCIPALNAME()"},
                        ],
                        "members": [{"memberName": "user@company.com"}],
                    },
                ],
                "perspectives": [
                    {"name": "SalesView", "tables": ["Sales", "Products", "Calendar"]},
                    {"name": "CustomerView", "tables": ["Sales", "Customers", "Calendar"]},
                ],
                "cultures": [
                    {
                        "name": "fr-FR",
                        "translations": [
                            {"name": "Sales", "translatedCaption": "Ventes"},
                            {"name": "Products", "translatedCaption": "Produits"},
                        ],
                    },
                ],
                "annotations": [],
            },
        }

    def test_full_project_structure(self):
        gen = TMDLGenerator()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "retail"
            gen.create_pbi_project(out, "RetailDashboard", bim_model=self._retail_model())

            sm_dir = out / "RetailDashboard.SemanticModel" / "definition"
            rpt_dir = out / "RetailDashboard.Report" / "definition"

            # Semantic model files
            assert (sm_dir / "model.tmdl").exists()
            assert (sm_dir / "database.tmdl").exists()
            assert (sm_dir / "relationships.tmdl").exists()

            # 5 tables
            assert len(list((sm_dir / "tables").glob("*.tmdl"))) == 5

            # RLS roles
            assert (sm_dir / "roles.tmdl").exists()
            roles_content = (sm_dir / "roles.tmdl").read_text("utf-8")
            assert "RegionalManager" in roles_content
            assert "USERPRINCIPALNAME" in roles_content

            # Perspectives
            assert (sm_dir / "perspectives.tmdl").exists()
            persp_content = (sm_dir / "perspectives.tmdl").read_text("utf-8")
            assert "SalesView" in persp_content
            assert "CustomerView" in persp_content

            # Cultures
            assert (sm_dir / "cultures" / "fr-FR.tmdl").exists()

            # Report
            assert (rpt_dir / "report.json").exists()
            assert (out / "RetailDashboard.pbip").exists()

    def test_table_tmdl_content(self):
        gen = TMDLGenerator()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "retail"
            gen.create_pbi_project(out, "Retail", bim_model=self._retail_model())

            sales_tmdl = (out / "Retail.SemanticModel" / "definition"
                          / "tables" / "Sales.tmdl").read_text("utf-8")

            # Measures present
            assert "Total Revenue" in sales_tmdl
            assert "YTD Revenue" in sales_tmdl
            assert "displayFolder: KPIs" in sales_tmdl

            # Columns present
            assert "Amount" in sales_tmdl
            assert "displayFolder: Financials" in sales_tmdl

            # Products table has hierarchy
            products_tmdl = (out / "Retail.SemanticModel" / "definition"
                             / "tables" / "Products.tmdl").read_text("utf-8")
            assert "hierarchy" in products_tmdl
            assert "Category" in products_tmdl

    def test_multi_page_retail_dashboard(self):
        gen = TMDLGenerator()
        sheets = [
            {
                "id": "overview", "title": "Executive Overview",
                "visualizations": [
                    {"type": "kpi", "title": "Total Revenue"},
                    {"type": "kpi", "title": "Customer Count"},
                    {"type": "barchart", "title": "Revenue by Category"},
                    {"type": "linechart", "title": "Monthly Trend"},
                ],
            },
            {
                "id": "products", "title": "Product Analysis",
                "visualizations": [
                    {"type": "treemap", "title": "Revenue Treemap"},
                    {"type": "table", "title": "Product Details"},
                ],
            },
            {
                "id": "geo", "title": "Geographic Analysis",
                "visualizations": [
                    {"type": "map", "title": "Sales by Country"},
                    {"type": "barchart", "title": "Top Cities"},
                ],
            },
            {
                "id": "detail", "title": "Transaction Detail",
                "pageType": "DrillThrough",
                "visualizations": [
                    {"type": "table", "title": "Transactions"},
                ],
            },
        ]
        bookmarks = [
            {"name": "KPI View", "selections": []},
            {"name": "Map Focus", "selections": [{"field": "Country", "values": ["USA"]}]},
        ]
        theme = {
            "name": "RetailTheme",
            "colors": ["#0078D4", "#50E6FF", "#FFB900", "#E74856"],
            "fontFamily": "Segoe UI",
            "backgroundColor": "#FFFFFF",
        }
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "retail"
            gen.create_pbi_project(
                out, "RetailDashboard",
                bim_model=self._retail_model(),
                sheets=sheets,
                bookmarks=bookmarks,
                theme=theme,
            )

            # Check 4 pages
            pages_json = json.loads(
                (out / "RetailDashboard.Report" / "definition" / "pages" / "pages.json")
                .read_text("utf-8")
            )
            assert len(pages_json["pageOrder"]) == 4

            # Check bookmarks in report
            report = json.loads(
                (out / "RetailDashboard.Report" / "definition" / "report.json")
                .read_text("utf-8")
            )
            assert len(report["bookmarks"]) == 2

            # Check theme file exists
            theme_dir = (out / "RetailDashboard.Report" / "definition"
                         / "StaticResources" / "SharedResources" / "BaseThemes")
            assert theme_dir.exists()
            theme_files = list(theme_dir.glob("*.json"))
            assert len(theme_files) >= 1
            theme_content = json.loads(theme_files[0].read_text("utf-8"))
            assert theme_content["dataColors"][0] == "#0078D4"


# ══════════════════════════════════════════════════════════════════
# 2. DAX — Complex Real-World Expression Suite
# ══════════════════════════════════════════════════════════════════
class TestDAXComplexExpressions:
    """Complex multi-feature Qlik expressions from real migration projects."""

    def test_set_analysis_ignore_current(self):
        """Sum({1} Sales) with ignore-current-selection pattern."""
        dax = convert_qlik_expression_to_dax(
            "Sum({1} Sales)", table_name="Orders"
        )
        assert "CALCULATE" in dax
        assert "ALL" in dax

    def test_set_analysis_clear_field(self):
        """Count({<Year=>} Distinct CustomerID) → CALCULATE(DISTINCTCOUNT(...), REMOVEFILTERS(...))"""
        dax = convert_qlik_expression_to_dax(
            "Count({<Year=>} Distinct CustomerID)", table_name="Orders"
        )
        assert "CALCULATE" in dax
        assert "REMOVEFILTERS" in dax

    def test_total_with_dimensions(self):
        """Sum(TOTAL <Region> Sales) → CALCULATE(SUM(...), ALLEXCEPT(..., Region))"""
        dax = convert_qlik_expression_to_dax(
            "Sum(TOTAL <Region> Sales)", table_name="Orders"
        )
        assert "ALLEXCEPT" in dax
        assert "Region" in dax

    def test_multi_variable_chain(self):
        """Multiple variable references in one expression."""
        dax = convert_qlik_expression_to_dax(
            "If($(vThreshold) > 0, Sum($(vField)), 0)",
            variables={"vThreshold": "100", "vField": "Amount"},
        )
        assert "100" in dax
        assert "Amount" in dax

    def test_rank_expression(self):
        dax = convert_qlik_expression_to_dax("Rank(Sum(Sales))")
        assert "RANKX" in dax

    def test_previous_value(self):
        dax = convert_qlik_expression_to_dax("Previous(Amount)")
        assert "EARLIER" in dax

    def test_fieldvaluecount(self):
        dax = convert_qlik_expression_to_dax("FieldValueCount(Region)")
        assert "DISTINCTCOUNT" in dax


# ══════════════════════════════════════════════════════════════════
# 3. M Query — Complex ETL Pipeline via build_m_query_with_transforms
# ══════════════════════════════════════════════════════════════════
class TestComplexETLPipeline:
    """Simulates a realistic ETL transformation pipeline."""

    BASE = 'let\n    Source = Sql.Database("srv", "sales_db")\nin\n    Source'

    def test_full_etl_pipeline(self):
        """8-step transformation pipeline."""
        result = build_m_query_with_transforms(
            self.BASE,
            [
                {"type": "rename", "mapping": {"cust_id": "CustomerID", "amt": "Amount"}},
                {"type": "upper", "columns": ["Region"]},
                {"type": "filter_values", "column": "Status", "values": ["Active", "Pending"]},
                {"type": "add_custom_column", "name": "Margin",
                 "expression": "[Revenue] - [Cost]"},
                {"type": "group_by", "group_cols": ["Region", "CustomerID"],
                 "agg_specs": [
                     {"column": "Amount", "agg": "sum", "alias": "TotalAmount"},
                     {"column": "Margin", "agg": "avg", "alias": "AvgMargin"},
                 ]},
                {"type": "sort", "columns": [
                    {"column": "TotalAmount", "ascending": False},
                ]},
                {"type": "remove", "columns": ["AvgMargin"]},
                {"type": "add_index", "name": "Rank", "start": 1},
            ],
        )
        # Verify all transforms are in the output
        assert "Table.RenameColumns" in result
        assert "Text.Upper" in result
        assert "Table.SelectRows" in result
        assert "Table.AddColumn" in result
        assert "Table.Group" in result
        assert "Table.Sort" in result
        assert "Table.RemoveColumns" in result
        assert "Table.AddIndexColumn" in result
        # Final step should be the last transform
        lines = result.strip().split("\n")
        last_line = lines[-1].strip()
        assert "AddedIndex" in last_line or "Index" in last_line

    def test_pivot_unpivot_roundtrip(self):
        """Unpivot quarterly columns, then group by year."""
        result = build_m_query_with_transforms(
            self.BASE,
            [
                {"type": "unpivot", "columns": ["Q1", "Q2", "Q3", "Q4"],
                 "attribute": "Quarter", "value": "Revenue"},
                {"type": "group_by", "group_cols": ["Year"],
                 "agg_specs": [{"column": "Revenue", "agg": "sum", "alias": "AnnualRevenue"}]},
            ],
        )
        assert "Table.UnpivotColumns" in result
        assert "Table.Group" in result


# ══════════════════════════════════════════════════════════════════
# 4. Script — Complex Multi-Section Qlik Script
# ══════════════════════════════════════════════════════════════════
class TestComplexQlikScript:
    RETAIL_SCRIPT = """
SET DateFormat='YYYY-MM-DD';
SET vDataDir = 'C:\\RetailData';
LET vCurrentYear = Year(Today());

// === Mapping tables ===
CountryMap:
MAPPING LOAD Code, Name FROM [$(vDataDir)\\ref\\countries.csv] (txt, utf8, embedded labels, delimiter is ',');

StatusMap:
LOAD * INLINE [
Code, Description
A, Active
I, Inactive
P, Pending
];

// === Dimension tables ===
Products:
LOAD
    ProductID,
    ProductName,
    Upper(Category) as Category,
    SubCategory
FROM [$(vDataDir)\\products.xlsx] (ooxml, embedded labels);

Customers:
LOAD
    CustomerID,
    Name,
    City,
    Country
FROM [$(vDataDir)\\customers.csv] (txt, utf8, embedded labels, delimiter is ',');

// === Fact table ===
Sales:
LOAD
    TransactionID,
    ProductID,
    CustomerID,
    Date#(SaleDate, 'YYYY-MM-DD') as SaleDate,
    Quantity,
    Amount
FROM [$(vDataDir)\\sales_$(vCurrentYear).csv] (txt, utf8, embedded labels, delimiter is ',');

CONCATENATE(Sales)
LOAD
    TransactionID,
    ProductID,
    CustomerID,
    Date#(SaleDate, 'YYYY-MM-DD') as SaleDate,
    Quantity,
    Amount
FROM [$(vDataDir)\\sales_archive.csv] (txt, utf8, embedded labels, delimiter is ',');
"""

    def test_full_script_conversion(self):
        converter = QlikScriptToPowerQueryConverter()
        result = converter.convert_qlik_script_to_powerquery(self.RETAIL_SCRIPT)
        assert isinstance(result, str)
        assert len(result) > 50

    def test_variables_expanded(self):
        converter = QlikScriptToPowerQueryConverter()
        result = converter.convert_qlik_script_to_powerquery(self.RETAIL_SCRIPT)
        # $(vDataDir) should be expanded to C:\RetailData
        assert "C:\\RetailData" in result

    def test_inline_table_present(self):
        converter = QlikScriptToPowerQueryConverter()
        result = converter.convert_qlik_script_to_powerquery(self.RETAIL_SCRIPT)
        assert "Active" in result or "#table" in result


# ══════════════════════════════════════════════════════════════════
# 5. Visuals — Full Dashboard Visual Suite
# ══════════════════════════════════════════════════════════════════
class TestFullDashboardVisuals:
    """Test generation of a complete set of dashboard visuals."""

    COL_MAP = {
        "Region": "Sales", "Amount": "Sales", "Date": "Calendar",
        "Category": "Products", "Country": "Customers",
    }
    MEASURE_MAP = {
        "Total Revenue": ("Sales", "SUM('Sales'[Amount])"),
        "Customer Count": ("Sales", "DISTINCTCOUNT('Sales'[CustomerID])"),
    }

    def test_diverse_visual_types(self):
        """Generate 8 different visual types and validate all produce valid containers."""
        visual_defs = [
            {"type": "barchart", "title": "Revenue by Region"},
            {"type": "linechart", "title": "Monthly Trend"},
            {"type": "piechart", "title": "Category Split"},
            {"type": "kpi", "title": "Total Revenue"},
            {"type": "table", "title": "Transaction Detail"},
            {"type": "map", "title": "Sales Map"},
            {"type": "treemap", "title": "Product Treemap"},
            {"type": "gauge", "title": "Target"},
        ]
        for i, viz in enumerate(visual_defs):
            container = create_visual_container(
                f"v{i}", viz, i, [], [], self.COL_MAP, self.MEASURE_MAP,
            )
            assert "visual" in container
            assert "position" in container
            assert container["position"]["x"] >= 0
            assert container["position"]["y"] >= 0

    def test_visual_with_conditional_formatting(self):
        viz = {
            "type": "table",
            "title": "Status Table",
            "colorBy": {"mode": "byMeasure"},
            "conditionalFormatting": [
                {"color": "#FF0000", "operator": "lessThan", "value": 0},
                {"color": "#00FF00", "operator": "greaterThan", "value": 1000},
            ],
        }
        container = create_visual_container(
            "v_cf", viz, 0, [], [], self.COL_MAP, self.MEASURE_MAP,
        )
        assert "objects" in container["visual"]

    def test_visual_with_reference_lines(self):
        viz = {
            "type": "barchart",
            "title": "Sales with Target",
            "referenceLines": [
                {"label": "Target", "value": 10000, "color": "#FF0000"},
                {"label": "Minimum", "value": 2000, "color": "#FFAA00"},
            ],
        }
        container = create_visual_container(
            "v_rl", viz, 0, [], [], self.COL_MAP, self.MEASURE_MAP,
        )
        assert "constantLine" in container["visual"].get("objects", {})

    def test_visual_with_topn_filter(self):
        viz = {
            "type": "barchart",
            "title": "Top 10 Products",
            "filters": [
                {"field": "Category", "type": "topN", "count": 10},
            ],
        }
        container = create_visual_container(
            "v_tn", viz, 0, [], [], self.COL_MAP, self.MEASURE_MAP,
        )
        filters = container["visual"].get("filters", [])
        assert len(filters) >= 1
        assert filters[0]["type"] == "TopN"

    def test_action_button_page_nav(self):
        viz = {
            "type": "actionbutton",
            "title": "Go to Details",
            "navigation": {"sheet": "TransactionDetail"},
        }
        container = create_visual_container(
            "v_nav", viz, 0, [], [], {}, {},
        )
        action_objs = container["visual"].get("objects", {}).get("action", [])
        assert len(action_objs) >= 1
        props = action_objs[0]["properties"]
        assert "PageNavigation" in json.dumps(props)

    def test_action_button_web_url(self):
        viz = {
            "type": "actionbutton",
            "title": "Open Wiki",
            "navigation": {"url": "https://wiki.example.com"},
        }
        container = create_visual_container(
            "v_web", viz, 0, [], [], {}, {},
        )
        action_objs = container["visual"].get("objects", {}).get("action", [])
        assert len(action_objs) >= 1
        props = action_objs[0]["properties"]
        assert "WebUrl" in json.dumps(props)


# ══════════════════════════════════════════════════════════════════
# 6. M Query — All Datasources Batch Generation
# ══════════════════════════════════════════════════════════════════
class TestAllDatasourcesBatch:
    """Generate M queries for a realistic set of mixed datasources."""

    def test_mixed_datasource_batch(self):
        datasources = [
            {"connectionType": "sqlserver", "tableName": "Orders",
             "connection": {"server": "sql-prod", "database": "RetailDB"}},
            {"connectionType": "postgresql", "tableName": "Inventory",
             "connection": {"server": "pg-prod", "database": "warehouse"}},
            {"connectionType": "excel", "tableName": "Budget",
             "connection": {"path": "C:\\Finance\\budget_2024.xlsx"}},
            {"connectionType": "csv", "tableName": "Rates",
             "connection": {"path": "C:\\FX\\exchange_rates.csv"}},
            {"connectionType": "snowflake", "tableName": "Events",
             "connection": {"server": "acme.snowflakecomputing.com", "warehouse": "ANALYTICS"}},
        ]
        queries = generate_all_m_queries(datasources)
        assert len(queries) == 5
        assert "Sql.Database" in queries["Orders"]
        assert "PostgreSQL.Database" in queries["Inventory"]
        assert "Excel.Workbook" in queries["Budget"]
        assert "Csv.Document" in queries["Rates"]
        assert "Snowflake.Databases" in queries["Events"]


# ══════════════════════════════════════════════════════════════════
# 7. create_pbi_project_from_migration — From BIM + PQ files
# ══════════════════════════════════════════════════════════════════
class TestCreateFromMigration:
    """Test the convenience function that reads BIM + PQ + report files."""

    def test_from_bim_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            mig_dir = Path(tmp) / "migration_output"
            mig_dir.mkdir()
            (mig_dir / "powerbi_models").mkdir()
            (mig_dir / "powerbi_reports").mkdir()
            (mig_dir / "powerquery_scripts").mkdir()

            # Write a minimal BIM model
            bim = {
                "compatibilityLevel": 1600,
                "model": {
                    "culture": "en-US",
                    "defaultPowerBIDataSourceVersion": "powerBI_V3",
                    "tables": [{"name": "T1", "columns": [
                        {"name": "C1", "dataType": "string", "sourceColumn": "C1"},
                    ]}],
                    "relationships": [],
                    "annotations": [],
                },
            }
            (mig_dir / "powerbi_models" / "model.bim").write_text(
                json.dumps(bim), encoding="utf-8"
            )

            # Write a PQ script
            (mig_dir / "powerquery_scripts" / "queries.pq").write_text(
                'let\n    Source = #table({"C1"}, {{"val"}})\nin\n    Source',
                encoding="utf-8",
            )

            proj_dir = Path(tmp) / "pbi_output"
            pbip = create_pbi_project_from_migration(mig_dir, proj_dir, "TestReport")
            assert pbip.exists()
            assert (proj_dir / "TestReport.SemanticModel").exists()


# ══════════════════════════════════════════════════════════════════
# 8. TMDL — RLS Role Validation
# ══════════════════════════════════════════════════════════════════
class TestRLSRoles:
    def test_rls_role_content(self):
        gen = TMDLGenerator()
        model = {
            "compatibilityLevel": 1600,
            "model": {
                "culture": "en-US",
                "defaultPowerBIDataSourceVersion": "powerBI_V3",
                "tables": [
                    {"name": "Sales", "columns": [
                        {"name": "Region", "dataType": "string", "sourceColumn": "Region"},
                    ]},
                ],
                "relationships": [],
                "annotations": [],
                "roles": [
                    {
                        "name": "EuropeManager",
                        "modelPermission": "read",
                        "description": "Europe region only",
                        "tablePermissions": [
                            {"name": "Sales",
                             "filterExpression": "'Sales'[Region] = \"Europe\""},
                        ],
                        "members": [
                            {"memberName": "alice@corp.com"},
                            {"memberName": "bob@corp.com"},
                        ],
                    },
                    {
                        "name": "DynamicRLS",
                        "modelPermission": "read",
                        "tablePermissions": [
                            {"name": "Sales",
                             "filterExpression": "'Sales'[UserEmail] = USERPRINCIPALNAME()"},
                        ],
                    },
                ],
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "rls"
            gen.create_pbi_project(out, "RLS_Test", bim_model=model)

            roles_file = out / "RLS_Test.SemanticModel" / "definition" / "roles.tmdl"
            assert roles_file.exists()
            content = roles_file.read_text("utf-8")
            assert "EuropeManager" in content
            assert "DynamicRLS" in content
            assert "USERPRINCIPALNAME" in content
            assert "Europe" in content
            assert "alice@corp.com" in content


# ══════════════════════════════════════════════════════════════════
# 9. TMDL Validation — Syntax Checks on Generated Files
# ══════════════════════════════════════════════════════════════════
class TestTMDLSyntaxValidation:
    """Validate that generated TMDL files have correct structure."""

    @staticmethod
    def _build_and_generate():
        gen = TMDLGenerator()
        model = {
            "compatibilityLevel": 1600,
            "model": {
                "culture": "en-US",
                "defaultPowerBIDataSourceVersion": "powerBI_V3",
                "tables": [
                    {
                        "name": "Sales",
                        "columns": [
                            {"name": "ID", "dataType": "int64", "sourceColumn": "ID"},
                            {"name": "Amount", "dataType": "double", "sourceColumn": "Amount",
                             "formatString": "#,0.00"},
                        ],
                        "measures": [
                            {"name": "Total", "expression": "SUM('Sales'[Amount])"},
                        ],
                    },
                ],
                "relationships": [],
                "annotations": [],
            },
        }
        tmp = tempfile.mkdtemp()
        out = Path(tmp) / "syntax_check"
        gen.create_pbi_project(out, "SyntaxTest", bim_model=model)
        return out

    def test_model_tmdl_has_culture(self):
        out = self._build_and_generate()
        content = (out / "SyntaxTest.SemanticModel" / "definition" / "model.tmdl").read_text("utf-8")
        assert "culture:" in content

    def test_table_tmdl_starts_with_table(self):
        out = self._build_and_generate()
        content = (out / "SyntaxTest.SemanticModel" / "definition" / "tables" / "Sales.tmdl").read_text("utf-8")
        assert content.strip().startswith("table")

    def test_pbip_json_valid(self):
        out = self._build_and_generate()
        pbip = json.loads((out / "SyntaxTest.pbip").read_text("utf-8"))
        assert "version" in pbip

    def test_pbir_json_valid(self):
        out = self._build_and_generate()
        pbir = json.loads(
            (out / "SyntaxTest.Report" / "definition.pbir").read_text("utf-8")
        )
        assert "version" in pbir or "datasetReference" in pbir

    def test_report_json_valid(self):
        out = self._build_and_generate()
        report = json.loads(
            (out / "SyntaxTest.Report" / "definition" / "report.json").read_text("utf-8")
        )
        assert isinstance(report, dict)

    def test_balanced_parentheses_in_measures(self):
        out = self._build_and_generate()
        content = (out / "SyntaxTest.SemanticModel" / "definition" / "tables" / "Sales.tmdl").read_text("utf-8")
        # Check that all DAX expressions have balanced parens
        for line in content.split("\n"):
            if "expression:" in line or "SUM(" in line or "CALCULATE(" in line:
                expr = line.split(":", 1)[-1] if ":" in line else line
                assert expr.count("(") == expr.count(")"), f"Unbalanced parens: {line}"
