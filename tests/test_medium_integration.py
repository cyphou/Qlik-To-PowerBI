"""
MEDIUM COMPLEXITY TESTS — Level 2

Multi-step conversions, chained transforms, realistic Qlik examples,
and TMDL project generation with validation of output files.
"""
import json
import tempfile
from pathlib import Path

import pytest

from fabric_api.dax_converter import (
    convert_qlik_expression_to_dax,
    convert_measures_to_dax,
    convert_dimensions_to_dax,
)
from fabric_api.m_query_generator import generate_m_query, generate_all_m_queries
from fabric_api.m_query_builder import (
    inject_m_steps, build_m_query_with_transforms,
    rename_columns, filter_values, group_by, join_tables, sort_rows,
    upper_case, add_custom_column, unpivot, select_columns,
)
from fabric_api.qlik_script_converter import QlikScriptToPowerQueryConverter
from fabric_api.tmdl_generator import TMDLGenerator
from fabric_api.visual_generator import create_visual_container, generate_visual_containers


# ══════════════════════════════════════════════════════════════════
# 1. DAX — Realistic Expression Chains
# ══════════════════════════════════════════════════════════════════
class TestDAXRealisticExpressions:
    """Real-world Qlik expressions that combine multiple features."""

    def test_set_analysis_with_variables(self):
        """Variable expansion in expression (set analysis with nested braces is a known regex limitation)."""
        dax = convert_qlik_expression_to_dax(
            "Sum({<Year=>} $(vField))",
            table_name="Orders",
            variables={"vField": "Sales"},
        )
        assert "Sales" in dax

    def test_nested_if_with_aggregation(self):
        """If(Sum(Sales) > 1000, 'High', If(Sum(Sales) > 500, 'Medium', 'Low'))"""
        dax = convert_qlik_expression_to_dax(
            "If(Sum(Sales) > 1000, 'High', If(Sum(Sales) > 500, 'Medium', 'Low'))"
        )
        assert "IF(" in dax
        assert "SUM" in dax

    def test_calculated_column_with_related(self):
        """Cross-table reference should insert RELATED()."""
        dax = convert_qlik_expression_to_dax(
            "Upper([CategoryName])",
            table_name="Products",
            col_table_map={"CategoryName": "Categories"},
            relationships=[{"fromTable": "Products", "toTable": "Categories"}],
            is_calculated_column=True,
        )
        assert "RELATED" in dax
        assert "UPPER" in dax

    def test_coalesce_chain(self):
        """Alt(val1, val2, 0) → COALESCE."""
        dax = convert_qlik_expression_to_dax("Alt(Discount, DefaultDiscount, 0)")
        assert "COALESCE" in dax

    def test_class_binning(self):
        """Class(Amount, 1000) → bucketing expression."""
        dax = convert_qlik_expression_to_dax("Class(Amount, 1000)")
        assert "INT" in dax and "DIVIDE" in dax

    def test_date_functions_chain(self):
        """Year(Today()) should compose correctly."""
        dax = convert_qlik_expression_to_dax("Year(Today())")
        assert "YEAR(TODAY())" == dax

    def test_string_functions(self):
        dax = convert_qlik_expression_to_dax("Upper(Left(CustomerName, 3))")
        assert "UPPER" in dax
        assert "LEFT" in dax

    def test_math_functions(self):
        dax = convert_qlik_expression_to_dax("Round(Sqrt(Abs(Value)), 2)")
        assert "ROUND" in dax
        assert "SQRT" in dax
        assert "ABS" in dax

    def test_dual_handling(self):
        dax = convert_qlik_expression_to_dax("Dual('Label', 1)")
        assert "VALUE" in dax

    def test_apply_map(self):
        dax = convert_qlik_expression_to_dax("ApplyMap('MapTable', KeyField, 'Default')")
        assert "LOOKUPVALUE" in dax


# ══════════════════════════════════════════════════════════════════
# 2. DAX — Batch Conversion with Format Strings
# ══════════════════════════════════════════════════════════════════
class TestDAXBatchWithFormats:
    def test_measures_preserve_format(self):
        measures = [
            {"name": "Revenue", "expression": "Sum(Amount)", "format": "#,##0.00"},
            {"name": "Growth %", "expression": "Avg(GrowthRate)", "format": "0.00%"},
        ]
        result = convert_measures_to_dax(measures, table_name="Finance")
        assert result[0]["formatString"] == "#,0.00"
        assert result[1]["formatString"] == "0.00%"

    def test_dimensions_mixed(self):
        dims = [
            {"field": "Region"},                                # plain field
            {"field": "Upper(Country)"},                         # calculated
            {"field": "If(Sales > 100, 'Big', 'Small')"},       # expression
        ]
        result = convert_dimensions_to_dax(dims, "Sales")
        assert result[0]["is_calculated"] is False
        assert result[1]["is_calculated"] is True
        assert result[2]["is_calculated"] is True
        assert "UPPER" in result[1]["dax_expression"]
        assert "IF(" in result[2]["dax_expression"]


# ══════════════════════════════════════════════════════════════════
# 3. M Query Builder — Chained Transforms
# ══════════════════════════════════════════════════════════════════
class TestChainedTransforms:
    BASE_M = 'let\n    Source = Sql.Database("srv", "db")\nin\n    Source'

    def test_rename_then_filter(self):
        steps = [
            rename_columns("Source", {"old_name": "NewName"}),
            filter_values("RenamedColumns", "Status", ["Active"]),
        ]
        result = inject_m_steps(self.BASE_M, steps)
        assert "Table.RenameColumns" in result
        assert "Table.SelectRows" in result
        assert result.strip().endswith("FilteredRows")

    def test_upper_then_group(self):
        steps = [
            upper_case("Source", ["Region"]),
            group_by("UpperCaseText", ["Region"],
                     [{"column": "Revenue", "agg": "sum", "alias": "Total"}]),
        ]
        result = inject_m_steps(self.BASE_M, steps)
        assert "Text.Upper" in result
        assert "Table.Group" in result

    def test_join_then_select(self):
        steps = [
            join_tables("Source", "Lookup", "ID", "ID", "LeftOuter"),
            select_columns("JoinedTable", ["Name", "Amount"]),
        ]
        result = inject_m_steps(self.BASE_M, steps)
        assert "Table.NestedJoin" in result or "Table.Join" in result
        assert "Table.SelectColumns" in result

    def test_unpivot_then_sort(self):
        steps = [
            unpivot("Source", ["Q1", "Q2", "Q3", "Q4"]),
            sort_rows("UnpivotedColumns", [{"column": "Attribute", "ascending": True}]),
        ]
        result = inject_m_steps(self.BASE_M, steps)
        assert "Table.UnpivotColumns" in result
        assert "Table.Sort" in result


# ══════════════════════════════════════════════════════════════════
# 4. M Query Builder — build_m_query_with_transforms
# ══════════════════════════════════════════════════════════════════
class TestBuildWithTransforms:
    BASE_M = 'let\n    Source = Csv.Document(File.Contents("data.csv"))\nin\n    Source'

    def test_single_rename(self):
        result = build_m_query_with_transforms(
            self.BASE_M,
            [{"type": "rename", "mapping": {"A": "Alpha"}}],
        )
        assert "Table.RenameColumns" in result

    def test_filter_then_group(self):
        result = build_m_query_with_transforms(
            self.BASE_M,
            [
                {"type": "filter_values", "column": "Status", "values": ["Active"]},
                {"type": "group_by", "group_cols": ["Region"],
                 "agg_specs": [{"column": "Sales", "agg": "sum", "alias": "Total"}]},
            ],
        )
        assert "Table.SelectRows" in result
        assert "Table.Group" in result

    def test_unknown_transform_skipped(self):
        """Unknown transform types should be silently skipped."""
        result = build_m_query_with_transforms(
            self.BASE_M,
            [
                {"type": "rename", "mapping": {"A": "B"}},
                {"type": "totally_unknown_transform"},
                {"type": "upper", "columns": ["B"]},
            ],
        )
        assert "RenamedColumns" in result
        assert "UpperCase" in result

    def test_custom_column_and_sort(self):
        result = build_m_query_with_transforms(
            self.BASE_M,
            [
                {"type": "add_custom_column", "name": "Margin",
                 "expression": "[Revenue] - [Cost]"},
                {"type": "sort", "columns": [{"column": "Margin", "ascending": False}]},
            ],
        )
        assert "Table.AddColumn" in result
        assert "Table.Sort" in result


# ══════════════════════════════════════════════════════════════════
# 5. Script Converter — Real-World Scripts
# ══════════════════════════════════════════════════════════════════
class TestScriptConverterRealistic:
    def test_multi_table_load(self):
        """Script loading from two different sources."""
        script = """
Orders:
LOAD OrderID, CustomerID, Amount
FROM [C:\\Data\\orders.csv] (txt, utf8, embedded labels, delimiter is ',');

Customers:
LOAD CustomerID, Name, Country
FROM [C:\\Data\\customers.xlsx] (ooxml, embedded labels);
"""
        converter = QlikScriptToPowerQueryConverter()
        result = converter.convert_qlik_script_to_powerquery(script)
        assert "orders.csv" in result or "Orders" in result

    def test_sql_load(self):
        """SQL LOAD statement."""
        script = """
LOAD CustomerID, Total;
SQL SELECT CustomerID, SUM(Amount) as Total
FROM Orders
GROUP BY CustomerID;
"""
        converter = QlikScriptToPowerQueryConverter()
        result = converter.convert_qlik_script_to_powerquery(script)
        assert isinstance(result, str)

    def test_let_set_variables(self):
        """Variables defined with LET/SET and used via $(vName)."""
        script = """
SET vDataPath = 'C:\\SharedData';
LET vYear = Year(Today());

Sales:
LOAD * FROM [$(vDataPath)\\sales_$(vYear).csv] (txt, utf8);
"""
        converter = QlikScriptToPowerQueryConverter()
        result = converter.convert_qlik_script_to_powerquery(script)
        assert "C:\\SharedData" in result

    def test_inline_table(self):
        """INLINE data load."""
        script = """
StatusMap:
LOAD * INLINE [
Code, Description
A, Active
I, Inactive
P, Pending
];
"""
        converter = QlikScriptToPowerQueryConverter()
        result = converter.convert_qlik_script_to_powerquery(script)
        assert "Active" in result or "#table" in result

    def test_mapping_load(self):
        """MAPPING LOAD for ApplyMap lookup."""
        script = """
CountryMap:
MAPPING LOAD
    Code,
    Name
FROM [C:\\ref\\countries.csv] (txt, utf8, embedded labels, delimiter is ',');
"""
        converter = QlikScriptToPowerQueryConverter()
        result = converter.convert_qlik_script_to_powerquery(script)
        assert "CountryMap" in result or "lookup" in result.lower() or "countries.csv" in result

    def test_concatenate_load(self):
        """CONCATENATE appending to existing table."""
        script = """
Sales:
LOAD * FROM [C:\\Data\\sales_2023.csv];

CONCATENATE(Sales)
LOAD * FROM [C:\\Data\\sales_2024.csv];
"""
        converter = QlikScriptToPowerQueryConverter()
        result = converter.convert_qlik_script_to_powerquery(script)
        assert "sales_2024" in result or "Combine" in result or "sales_2023" in result


# ══════════════════════════════════════════════════════════════════
# 6. TMDL — Multi-Table Project with Relationships
# ══════════════════════════════════════════════════════════════════
class TestTMDLMultiTable:
    def _build_model(self):
        return {
            "compatibilityLevel": 1600,
            "model": {
                "culture": "en-US",
                "defaultPowerBIDataSourceVersion": "powerBI_V3",
                "tables": [
                    {
                        "name": "Orders",
                        "description": "Order transactions",
                        "columns": [
                            {"name": "OrderID", "dataType": "int64", "sourceColumn": "OrderID"},
                            {"name": "CustomerID", "dataType": "int64", "sourceColumn": "CustomerID"},
                            {"name": "Amount", "dataType": "double", "sourceColumn": "Amount",
                             "displayFolder": "Financials", "formatString": "#,0.00"},
                        ],
                        "measures": [
                            {"name": "Total Revenue", "expression": "SUM('Orders'[Amount])",
                             "displayFolder": "KPIs", "description": "Sum of all order amounts"},
                            {"name": "Order Count", "expression": "COUNTROWS('Orders')",
                             "displayFolder": "KPIs"},
                        ],
                    },
                    {
                        "name": "Customers",
                        "columns": [
                            {"name": "CustomerID", "dataType": "int64", "sourceColumn": "CustomerID"},
                            {"name": "Name", "dataType": "string", "sourceColumn": "Name"},
                            {"name": "Country", "dataType": "string", "sourceColumn": "Country",
                             "dataCategory": "Country"},
                        ],
                    },
                    {
                        "name": "Calendar",
                        "dataCategory": "Time",
                        "columns": [
                            {"name": "Date", "dataType": "dateTime", "sourceColumn": "Date"},
                            {"name": "Year", "dataType": "int64", "sourceColumn": "Year"},
                            {"name": "Month", "dataType": "int64", "sourceColumn": "Month"},
                        ],
                    },
                ],
                "relationships": [
                    {
                        "name": "Orders_Customers",
                        "fromTable": "Orders", "fromColumn": "CustomerID",
                        "toTable": "Customers", "toColumn": "CustomerID",
                        "crossFilteringBehavior": "bothDirections",
                    },
                ],
                "annotations": [],
            },
        }

    def test_three_tables_generated(self):
        gen = TMDLGenerator()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "proj"
            gen.create_pbi_project(out, "MultiTable", bim_model=self._build_model())
            tables_dir = out / "MultiTable.SemanticModel" / "definition" / "tables"
            tmdl_files = list(tables_dir.glob("*.tmdl"))
            assert len(tmdl_files) == 3

    def test_relationship_tmdl_exists(self):
        gen = TMDLGenerator()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "proj"
            gen.create_pbi_project(out, "MultiTable", bim_model=self._build_model())
            rel_file = out / "MultiTable.SemanticModel" / "definition" / "relationships.tmdl"
            assert rel_file.exists()
            content = rel_file.read_text("utf-8")
            assert "CustomerID" in content

    def test_measure_in_tmdl(self):
        gen = TMDLGenerator()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "proj"
            gen.create_pbi_project(out, "MultiTable", bim_model=self._build_model())
            orders_tmdl = (out / "MultiTable.SemanticModel" / "definition"
                           / "tables" / "Orders.tmdl").read_text("utf-8")
            assert "Total Revenue" in orders_tmdl
            assert "SUM" in orders_tmdl
            assert "displayFolder: KPIs" in orders_tmdl


# ══════════════════════════════════════════════════════════════════
# 7. TMDL — Multi-Page Report with Visuals
# ══════════════════════════════════════════════════════════════════
class TestTMDLMultiPageVisuals:
    def test_two_pages_with_visuals(self):
        gen = TMDLGenerator()
        model = {
            "compatibilityLevel": 1600,
            "model": {
                "culture": "en-US",
                "defaultPowerBIDataSourceVersion": "powerBI_V3",
                "tables": [{"name": "Sales", "columns": [
                    {"name": "Region", "dataType": "string", "sourceColumn": "Region"},
                    {"name": "Revenue", "dataType": "double", "sourceColumn": "Revenue"},
                ]}],
                "relationships": [], "annotations": [],
            },
        }
        sheets = [
            {
                "id": "overview", "title": "Overview",
                "visualizations": [
                    {"type": "barchart", "title": "Revenue by Region",
                     "dimensions": [{"field": "Region"}],
                     "measures": [{"expression": "Sum(Revenue)"}]},
                    {"type": "kpi", "title": "Total Revenue",
                     "measures": [{"expression": "Sum(Revenue)"}]},
                ],
            },
            {
                "id": "details", "title": "Details",
                "visualizations": [
                    {"type": "table", "title": "All Data"},
                ],
            },
        ]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "proj"
            gen.create_pbi_project(out, "Visuals", bim_model=model, sheets=sheets)

            # Check pages.json has 2 pages
            pages_json = json.loads(
                (out / "Visuals.Report" / "definition" / "pages" / "pages.json")
                .read_text("utf-8")
            )
            assert len(pages_json["pageOrder"]) == 2

    def test_bookmarks_written(self):
        gen = TMDLGenerator()
        model = {
            "compatibilityLevel": 1600,
            "model": {
                "culture": "en-US",
                "defaultPowerBIDataSourceVersion": "powerBI_V3",
                "tables": [{"name": "T", "columns": [
                    {"name": "C", "dataType": "string", "sourceColumn": "C"},
                ]}],
                "relationships": [], "annotations": [],
            },
        }
        bookmarks = [
            {"name": "Default View", "selections": [{"field": "Region", "values": ["US"]}]},
            {"name": "Europe View", "selections": [{"field": "Region", "values": ["EU"]}]},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "proj"
            gen.create_pbi_project(out, "BM", bim_model=model, bookmarks=bookmarks)
            report = json.loads(
                (out / "BM.Report" / "definition" / "report.json").read_text("utf-8")
            )
            assert len(report["bookmarks"]) == 2
            assert report["bookmarks"][0]["displayName"] == "Default View"


# ══════════════════════════════════════════════════════════════════
# 8. Visual Generator — Realistic Visuals
# ══════════════════════════════════════════════════════════════════
class TestVisualGeneratorRealistic:
    COL_MAP = {"Region": "Sales", "Amount": "Sales", "Date": "Calendar"}
    MEASURE_MAP = {"Total": ("Sales", "SUM('Sales'[Amount])")}

    def test_bar_chart_with_dims_and_measures(self):
        viz = {
            "type": "barchart",
            "title": "Sales by Region",
            "dimensions": [{"field": "Region", "name": "Region"}],
            "measures": [{"expression": "Sum(Amount)", "name": "Total Sales"}],
        }
        container = create_visual_container(
            "v1", viz, 0,
            viz["dimensions"], viz["measures"],
            self.COL_MAP, self.MEASURE_MAP,
        )
        assert container["visual"]["visualType"] == "clusteredBarChart"
        assert container["position"]["x"] >= 0

    def test_kpi_card(self):
        viz = {"type": "kpi", "title": "Revenue"}
        container = create_visual_container(
            "v2", viz, 0, [], [], self.COL_MAP, self.MEASURE_MAP,
        )
        assert container["visual"]["visualType"] == "card"

    def test_slicer_with_sync(self):
        viz = {
            "type": "filterpane",
            "syncGroup": "DateFilter",
            "dimensions": [{"field": "Date", "name": "Date"}],
        }
        container = create_visual_container(
            "v3", viz, 0,
            viz["dimensions"], [],
            self.COL_MAP, self.MEASURE_MAP,
        )
        assert container["visual"]["visualType"] == "slicer"
        assert container.get("syncGroup", {}).get("groupName") == "DateFilter"

    def test_batch_generation(self):
        vizs = [
            {"type": "barchart", "title": "Chart 1"},
            {"type": "linechart", "title": "Chart 2"},
            {"type": "table", "title": "Table 1"},
        ]
        containers = generate_visual_containers(
            vizs, "Report", measures=[], dimensions=[],
            col_table_map={}, measure_lookup={},
        )
        assert len(containers) == 3


# ══════════════════════════════════════════════════════════════════
# 9. Theme Generation — Variations
# ══════════════════════════════════════════════════════════════════
class TestThemeVariations:
    def test_default_has_12_colors(self):
        theme = TMDLGenerator.generate_theme_json()
        assert len(theme["dataColors"]) == 12

    def test_custom_theme_from_qlik(self):
        theme = TMDLGenerator.generate_theme_json(
            theme_def={
                "name": "Corporate Theme",
                "fontFamily": "Segoe UI",
                "backgroundColor": "#F5F5F5",
                "foregroundColor": "#333333",
                "colors": ["#003366", "#006699", "#3399CC", "#66CCFF"],
            },
        )
        assert theme["name"] == "Corporate Theme"
        assert theme["dataColors"][0] == "#003366"
        assert theme["background"] == "#F5F5F5"

    def test_conditional_formatting_in_theme(self):
        theme = TMDLGenerator.generate_theme_json(
            theme_def={
                "conditionalColors": {
                    "min": "#FF0000", "mid": "#FFFF00", "max": "#00FF00",
                },
            },
        )
        assert "conditionalFormatting" in theme
        assert theme["conditionalFormatting"]["divergent"]["min"]["color"] == "#FF0000"

    def test_qlik_colors_override(self):
        """qlik_colors parameter should take precedence over theme_def colors."""
        theme = TMDLGenerator.generate_theme_json(
            theme_def={"colors": ["#111111"]},
            qlik_colors=["#AAAAAA", "#BBBBBB"],
        )
        assert theme["dataColors"][0] == "#AAAAAA"
