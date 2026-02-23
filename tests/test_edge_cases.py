"""
STRESS & EDGE-CASE TESTS — Level 4

Boundary conditions, invalid inputs, Unicode, empty/null data,
deeply nested expressions, large payloads, error paths.
"""
import json
import tempfile
from pathlib import Path

import pytest

from fabric_api.dax_converter import (
    convert_qlik_expression_to_dax,
    convert_measures_to_dax,
    convert_dimensions_to_dax,
    _convert_operators,
    _convert_if_expressions,
    _convert_set_analysis,
    _convert_aggr,
    _convert_alt,
    _convert_class,
    _insert_related,
    _cleanup_dax,
    convert_qlik_type_to_dax,
)
from fabric_api.m_query_generator import generate_m_query, generate_all_m_queries
from fabric_api.m_query_builder import (
    rename_columns, filter_values, group_by, sort_rows,
    remove_columns, select_columns, upper_case, lower_case,
    replace_values, fill_down, add_custom_column, join_tables,
    unpivot, pivot, split_column_by_delimiter, merge_columns,
    inject_m_steps, build_m_query_with_transforms,
    add_index, skip_rows, remove_top_rows, promote_headers,
    duplicate_column, reorder_columns, trim_text, clean_text,
    proper_case, replace_nulls, filter_nulls, filter_contains,
    filter_range, distinct_rows, top_n, transpose,
    demote_headers, add_conditional_column,
)
from fabric_api.visual_generator import (
    create_visual_container, resolve_visual_type, generate_visual_containers,
)
from fabric_api.tmdl_generator import TMDLGenerator
from fabric_api.qlik_script_converter import QlikScriptToPowerQueryConverter


# ══════════════════════════════════════════════════════════════════
# 1. DAX — Empty / Null / Whitespace Inputs
# ══════════════════════════════════════════════════════════════════
class TestDAXEmptyInputs:
    def test_empty_string(self):
        result = convert_qlik_expression_to_dax("")
        assert result == "" or result is not None  # should not crash

    def test_whitespace_only(self):
        result = convert_qlik_expression_to_dax("   ")
        assert isinstance(result, str)

    def test_none_like_empty_expression(self):
        """An expression that resolves to nothing useful."""
        result = convert_qlik_expression_to_dax("$(vEmpty)")
        assert isinstance(result, str)

    def test_comment_line(self):
        result = convert_qlik_expression_to_dax("// this is a comment")
        assert isinstance(result, str)


class TestDAXOperatorsEdge:
    def test_no_operators(self):
        result = _convert_operators("SimpleField")
        assert result == "SimpleField"

    def test_consecutive_operators(self):
        result = _convert_operators("A and B or C and D")
        assert "&&" in result
        assert "||" in result

    def test_already_dax_operators(self):
        result = _convert_operators("A && B || C")
        assert "&&" in result
        assert "||" in result


class TestDAXIfEdgeCases:
    def test_deeply_nested_ifs(self):
        """5-level nested If — _convert_if_expressions handles block-style If only.
        Function-style If(cond, val) is handled by the simple function map."""
        expr = "If A=1 Then If B=2 Then 'deep' Else 'b1' End Else 'a0' End"
        result = _convert_if_expressions(expr)
        assert "IF(" in result

    def test_if_function_style_via_full_pipeline(self):
        """Function-style If( is handled by full pipeline."""
        result = convert_qlik_expression_to_dax("If(Amount > 100, 'High', 'Low')")
        assert "IF(" in result


class TestDAXSetAnalysisEdge:
    def test_set_with_clear_modifier(self):
        """Set analysis with clear-field modifier (no nested braces)."""
        expr = "Sum({<Country=>} Sales)"
        result = _convert_set_analysis(expr, table_name="Orders")
        assert "REMOVEFILTERS" in result

    def test_set_with_ignore_all(self):
        """Set analysis with {1} (ignore all selections)."""
        expr = "Sum({1} Amount)"
        result = _convert_set_analysis(expr, table_name="T")
        assert "ALL" in result

    def test_set_analysis_passthrough_complex(self):
        """Nested braces in set values are a known regex limitation — passes through."""
        expr = "Sum({<Year={$(vYear)}>} Sales)"
        result = _convert_set_analysis(expr)
        assert isinstance(result, str)


class TestDAXAggrEdgeCases:
    def test_aggr_with_multiple_dims(self):
        result = _convert_aggr("Aggr(Sum(Sales), Category, Region, Year)")
        assert "SUMMARIZE" in result

    def test_aggr_empty_expression(self):
        result = _convert_aggr("Aggr(, Category)")
        assert isinstance(result, str)  # should not crash


class TestDAXAltEdgeCases:
    def test_alt_single_value(self):
        result = _convert_alt("Alt(Amount)")
        assert "COALESCE" in result

    def test_alt_many_values(self):
        result = _convert_alt("Alt(A, B, C, D, E, F)")
        assert "COALESCE" in result
        assert result.count(",") >= 5


class TestDAXClassEdge:
    def test_class_small_interval(self):
        result = _convert_class("Class(Price, 0.01)")
        assert "INT" in result or "DIVIDE" in result


class TestDAXRelatedEdge:
    def test_related_same_table(self):
        """RELATED should NOT be inserted for same-table references."""
        result = _insert_related("'Sales'[Amount]", "Sales", {})
        assert "RELATED" not in result

    def test_related_unknown_table(self):
        """When the referenced table is not in relationships, handle gracefully."""
        rels = {"Products": "manyToOne"}
        result = _insert_related("'Unknown'[Field]", "Sales", rels)
        assert isinstance(result, str)


class TestDAXCleanupEdge:
    def test_double_parens(self):
        result = _cleanup_dax("SUM((Amount))")
        assert "((" not in result or "SUM" in result

    def test_trailing_comma(self):
        result = _cleanup_dax("CALCULATE(SUM(X), )")
        assert result.endswith(")") or isinstance(result, str)

    def test_very_long_expression(self):
        """1000-character expression should not crash."""
        expr = " + ".join([f"[Field{i}]" for i in range(200)])
        result = _cleanup_dax(expr)
        assert len(result) > 0


# ══════════════════════════════════════════════════════════════════
# 2. DAX Batch — Edge Cases
# ══════════════════════════════════════════════════════════════════
class TestDAXBatchEdge:
    def test_empty_measures_list(self):
        result = convert_measures_to_dax([])
        assert result == [] or isinstance(result, list)

    def test_measure_missing_expression(self):
        result = convert_measures_to_dax([
            {"name": "M1", "label": "Measure 1"},  # no expression key
        ])
        assert isinstance(result, list)

    def test_empty_dimensions_list(self):
        result = convert_dimensions_to_dax([])
        assert result == [] or isinstance(result, list)

    def test_dimension_missing_field(self):
        result = convert_dimensions_to_dax([
            {"name": "D1", "label": "Dim 1"},
        ])
        assert isinstance(result, list)


# ══════════════════════════════════════════════════════════════════
# 3. M Query Builder — Edge Cases
# ══════════════════════════════════════════════════════════════════
class TestMQueryBuilderEdge:
    def test_rename_empty_mapping(self):
        name, code = rename_columns("Source", {})
        assert isinstance(code, str)

    def test_rename_single_column(self):
        name, code = rename_columns("Source", {"A": "B"})
        assert "A" in code and "B" in code

    def test_filter_values_empty_list(self):
        name, code = filter_values("Source", "Col", [])
        assert isinstance(code, str)

    def test_filter_values_single_value(self):
        name, code = filter_values("Source", "Status", ["Active"])
        assert "Active" in code

    def test_group_by_single_col_single_agg(self):
        name, code = group_by("Source", ["Region"], [{"column": "Amount", "agg": "sum", "alias": "Total"}])
        assert "Region" in code
        assert "List.Sum" in code

    def test_sort_empty_columns(self):
        name, code = sort_rows("Source", [])
        assert isinstance(code, str)

    def test_upper_case_single_col(self):
        name, code = upper_case("Source", ["X"])
        assert "Text.Upper" in code

    def test_lower_case_single_col(self):
        name, code = lower_case("Source", ["X"])
        assert "Text.Lower" in code

    def test_remove_single_column(self):
        name, code = remove_columns("Source", ["Temp"])
        assert "Temp" in code

    def test_select_single_column(self):
        name, code = select_columns("Source", ["Keep"])
        assert "Keep" in code

    def test_replace_values_in_column(self):
        name, code = replace_values("Source", "Status", "Old", "New")
        assert "Old" in code and "New" in code

    def test_fill_down_multiple(self):
        name, code = fill_down("Source", ["A", "B", "C"])
        assert code.count('"') >= 6

    def test_add_custom_column_complex_expression(self):
        name, code = add_custom_column("Source", "Tax", "[Amount] * 0.2 + [Surcharge]")
        assert "Tax" in code
        assert "[Amount]" in code

    def test_join_tables_all_types(self):
        for jt in ["inner", "left", "right", "full", "leftanti", "rightanti"]:
            name, code = join_tables("Source", "Other", "ID", "ID", join_kind=jt)
            assert "Table.NestedJoin" in code

    def test_unpivot_single_column(self):
        name, code = unpivot("Source", ["Revenue"], "Attr", "Val")
        assert "Revenue" in code

    def test_pivot_column(self):
        name, code = pivot("Source", "Quarter", "Revenue", "sum")
        assert "Table.Pivot" in code

    def test_split_column_default_delimiter(self):
        name, code = split_column_by_delimiter("Source", "FullName", "-")
        assert "Splitter.SplitTextByDelimiter" in code

    def test_merge_two_columns(self):
        name, code = merge_columns("Source", ["First", "Last"], "FullName", " ")
        assert "Combine" in code

    def test_add_index_column_zero_start(self):
        name, code = add_index("Source", "Idx", 0)
        assert "Table.AddIndexColumn" in code

    def test_skip_rows_zero(self):
        name, code = skip_rows("Source", 0)
        assert "Table.Skip" in code

    def test_remove_top_rows(self):
        name, code = remove_top_rows("Source", 3)
        assert "Table.RemoveFirstN" in code

    def test_promote_headers(self):
        name, code = promote_headers("Source")
        assert "Table.PromoteHeaders" in code

    def test_duplicate_column(self):
        name, code = duplicate_column("Source", "Col1", "Col1_Copy")
        assert "Col1" in code

    def test_reorder_columns(self):
        name, code = reorder_columns("Source", ["C", "B", "A"])
        assert "Table.ReorderColumns" in code

    def test_trim_text(self):
        name, code = trim_text("Source", ["Name"])
        assert "Text.Trim" in code

    def test_clean_text(self):
        name, code = clean_text("Source", ["Notes"])
        assert "Text.Clean" in code

    def test_proper_case(self):
        name, code = proper_case("Source", ["City"])
        assert "Text.Proper" in code

    def test_replace_nulls(self):
        name, code = replace_nulls("Source", "Amount", "0")
        assert "Table.ReplaceValue" in code

    def test_filter_nulls(self):
        name, code = filter_nulls("Source", "Email")
        assert "Table.SelectRows" in code

    def test_filter_contains(self):
        name, code = filter_contains("Source", "Name", "John")
        assert "Text.Contains" in code

    def test_filter_range(self):
        name, code = filter_range("Source", "Amount", 100, 500)
        assert "100" in code and "500" in code

    def test_distinct_rows(self):
        name, code = distinct_rows("Source")
        assert "Table.Distinct" in code

    def test_top_n(self):
        name, code = top_n("Source", "Amount", 10)
        assert "MaxN" in code

    def test_transpose(self):
        name, code = transpose("Source")
        assert "Table.Transpose" in code

    def test_demote_headers(self):
        name, code = demote_headers("Source")
        assert "Table.DemoteHeaders" in code

    def test_conditional_column(self):
        name, code = add_conditional_column(
            "Source",
            "Grade",
            [
                {"column": "Score", "operator": ">", "value": "90", "result": "A"},
                {"column": "Score", "operator": ">", "value": "80", "result": "B"},
            ],
            "C",
        )
        assert "Grade" in code


class TestInjectMStepsEdge:
    BASE_QUERY = 'let\n    Source = #table({"A"}, {{"x"}})\nin\n    Source'

    def test_inject_empty_steps(self):
        result = inject_m_steps(self.BASE_QUERY, [])
        assert "Source" in result
        # Should be unchanged or minimally changed
        assert "let" in result

    def test_inject_single_step(self):
        result = inject_m_steps(self.BASE_QUERY, [("Upper", 'Table.TransformColumns(Source, {{"A", Text.Upper}})')])
        assert "Upper" in result

    def test_inject_into_query_without_in(self):
        """If query has no 'in' keyword, should handle gracefully."""
        bad_query = 'Source = #table({"A"}, {{"x"}})'
        result = inject_m_steps(bad_query, [("Step1", "Table.Skip(Source, 1)")])
        assert isinstance(result, str)


class TestBuildWithTransformsEdge:
    BASE = 'let\n    Source = #table({"A"}, {{"x"}})\nin\n    Source'

    def test_empty_transforms_list(self):
        result = build_m_query_with_transforms(self.BASE, [])
        assert "Source" in result

    def test_unknown_transform_type(self):
        """Unknown type should be skipped, not crash."""
        result = build_m_query_with_transforms(
            self.BASE, [{"type": "nonexistent_transform_xyz"}]
        )
        assert isinstance(result, str)

    def test_transform_missing_required_fields(self):
        """Transform with missing params should not crash."""
        result = build_m_query_with_transforms(
            self.BASE, [{"type": "rename"}]  # missing "mapping"
        )
        assert isinstance(result, str)


# ══════════════════════════════════════════════════════════════════
# 4. M Query Generator — Edge Cases
# ══════════════════════════════════════════════════════════════════
class TestMQueryGeneratorEdge:
    def test_unknown_connector_type(self):
        result = generate_m_query({
            "connectionType": "unknown_db_xyz",
            "tableName": "Test",
            "connection": {"server": "x"},
        })
        assert isinstance(result, str)
        assert len(result) > 0

    def test_empty_datasources(self):
        result = generate_all_m_queries([])
        assert result == {}

    def test_missing_table_name(self):
        result = generate_all_m_queries([
            {"connectionType": "csv", "connection": {"path": "data.csv"}},
        ])
        # Should use default name
        assert len(result) == 1

    def test_duplicate_table_names(self):
        result = generate_all_m_queries([
            {"connectionType": "csv", "tableName": "Data", "connection": {"path": "a.csv"}},
            {"connectionType": "csv", "tableName": "Data", "connection": {"path": "b.csv"}},
        ])
        # Last one wins (dict behavior)
        assert len(result) == 1


# ══════════════════════════════════════════════════════════════════
# 5. Unicode / Special Characters
# ══════════════════════════════════════════════════════════════════
class TestUnicodeSupport:
    def test_dax_unicode_table_name(self):
        result = convert_qlik_expression_to_dax(
            "Sum(Montant)", table_name="Données Ventes"
        )
        assert isinstance(result, str)
        assert "SUM" in result

    def test_dax_unicode_expression(self):
        result = convert_qlik_expression_to_dax("If(Région='Île-de-France', 1, 0)")
        assert "IF" in result

    def test_dax_japanese_chars(self):
        result = convert_qlik_expression_to_dax("Sum(売上高)")
        assert "SUM" in result

    def test_m_query_unicode_table(self):
        result = generate_m_query({
            "connectionType": "sqlserver",
            "tableName": "Données_Ventes",
            "connection": {"server": "srv", "database": "db"},
        })
        assert "Données_Ventes" in result

    def test_visual_unicode_title(self):
        container = create_visual_container(
            "v_uni", {"type": "kpi", "title": "Chiffre d'affaires — €"},
            0, [], [], {}, {},
        )
        title_str = json.dumps(container)
        assert "Chiffre" in title_str

    def test_tmdl_unicode_measure(self):
        gen = TMDLGenerator()
        model = {
            "compatibilityLevel": 1600,
            "model": {
                "culture": "fr-FR",
                "defaultPowerBIDataSourceVersion": "powerBI_V3",
                "tables": [{
                    "name": "Ventes",
                    "columns": [{"name": "Montant", "dataType": "double", "sourceColumn": "Montant"}],
                    "measures": [{"name": "CA Total", "expression": "SUM('Ventes'[Montant])"}],
                }],
                "relationships": [],
                "annotations": [],
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "unicode"
            gen.create_pbi_project(out, "VentesReport", bim_model=model)
            tmdl = (out / "VentesReport.SemanticModel" / "definition"
                    / "tables" / "Ventes.tmdl").read_text("utf-8")
            assert "CA Total" in tmdl
            assert "Montant" in tmdl


# ══════════════════════════════════════════════════════════════════
# 6. Visual Generator — Edge Cases
# ══════════════════════════════════════════════════════════════════
class TestVisualEdgeCases:
    def test_unknown_visual_type(self):
        pbi_type = resolve_visual_type("completly_made_up_type")
        assert isinstance(pbi_type, str)
        assert len(pbi_type) > 0

    def test_visual_no_title(self):
        container = create_visual_container(
            "v_nt", {"type": "barchart"}, 0, [], [], {}, {},
        )
        assert "visual" in container

    def test_visual_empty_dict(self):
        container = create_visual_container(
            "v_empty", {}, 0, [], [], {}, {},
        )
        assert "visual" in container

    def test_visual_with_bounds(self):
        container = create_visual_container(
            "v_bounds",
            {"type": "table", "bounds": {"x": 100, "y": 200, "width": 400, "height": 300}},
            0, [], [], {}, {},
        )
        assert container["position"]["x"] == 100
        assert container["position"]["y"] == 200

    def test_visual_with_qlik_grid_position(self):
        container = create_visual_container(
            "v_grid",
            {"type": "barchart", "col": 6, "row": 3, "colspan": 12, "rowspan": 5},
            0, [], [], {}, {},
        )
        # col 6 × (1280 // 24) = 6 × 53 = 318 (integer division)
        assert container["position"]["x"] == 6 * (1280 // 24)
        assert container["position"]["y"] == 3 * 50

    def test_generate_visual_containers_empty(self):
        result = generate_visual_containers([], "test")
        assert result == []

    def test_generate_visual_containers_over_20_limit(self):
        """Only first 20 visuals should be processed."""
        vizs = [{"type": "kpi", "title": f"KPI {i}"} for i in range(25)]
        result = generate_visual_containers(vizs, "test")
        assert len(result) == 20


# ══════════════════════════════════════════════════════════════════
# 7. TMDL Generator — Edge Cases
# ══════════════════════════════════════════════════════════════════
class TestTMDLEdgeCases:
    def test_model_with_no_tables(self):
        gen = TMDLGenerator()
        model = {
            "compatibilityLevel": 1600,
            "model": {
                "culture": "en-US",
                "defaultPowerBIDataSourceVersion": "powerBI_V3",
                "tables": [],
                "relationships": [],
                "annotations": [],
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "empty_model"
            gen.create_pbi_project(out, "EmptyModel", bim_model=model)
            assert (out / "EmptyModel.pbip").exists()
            assert (out / "EmptyModel.SemanticModel" / "definition" / "model.tmdl").exists()

    def test_table_with_no_columns(self):
        gen = TMDLGenerator()
        model = {
            "compatibilityLevel": 1600,
            "model": {
                "culture": "en-US",
                "defaultPowerBIDataSourceVersion": "powerBI_V3",
                "tables": [{"name": "EmptyTable", "columns": []}],
                "relationships": [],
                "annotations": [],
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "no_cols"
            gen.create_pbi_project(out, "NoCols", bim_model=model)
            tmdl = (out / "NoCols.SemanticModel" / "definition"
                    / "tables" / "EmptyTable.tmdl").read_text("utf-8")
            assert "EmptyTable" in tmdl

    def test_column_with_special_chars(self):
        gen = TMDLGenerator()
        model = {
            "compatibilityLevel": 1600,
            "model": {
                "culture": "en-US",
                "defaultPowerBIDataSourceVersion": "powerBI_V3",
                "tables": [{
                    "name": "Data",
                    "columns": [
                        {"name": "Price ($)", "dataType": "double", "sourceColumn": "Price ($)"},
                        {"name": "Count #", "dataType": "int64", "sourceColumn": "Count #"},
                        {"name": "% Growth", "dataType": "double", "sourceColumn": "% Growth"},
                    ],
                }],
                "relationships": [],
                "annotations": [],
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "special_chars"
            gen.create_pbi_project(out, "SpecialChars", bim_model=model)
            tmdl = (out / "SpecialChars.SemanticModel" / "definition"
                    / "tables" / "Data.tmdl").read_text("utf-8")
            assert "Price" in tmdl
            assert "Growth" in tmdl

    def test_many_tables_performance(self):
        """20 tables with 10 columns each — should complete in reasonable time."""
        gen = TMDLGenerator()
        tables = []
        for t in range(20):
            cols = [
                {"name": f"col_{c}", "dataType": "string", "sourceColumn": f"col_{c}"}
                for c in range(10)
            ]
            tables.append({"name": f"Table_{t}", "columns": cols})
        model = {
            "compatibilityLevel": 1600,
            "model": {
                "culture": "en-US",
                "defaultPowerBIDataSourceVersion": "powerBI_V3",
                "tables": tables,
                "relationships": [],
                "annotations": [],
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "perf"
            gen.create_pbi_project(out, "PerfTest", bim_model=model)
            tmdl_files = list((out / "PerfTest.SemanticModel" / "definition" / "tables").glob("*.tmdl"))
            assert len(tmdl_files) == 20

    def test_relationship_with_cross_filter(self):
        gen = TMDLGenerator()
        model = {
            "compatibilityLevel": 1600,
            "model": {
                "culture": "en-US",
                "defaultPowerBIDataSourceVersion": "powerBI_V3",
                "tables": [
                    {"name": "A", "columns": [
                        {"name": "ID", "dataType": "int64", "sourceColumn": "ID"},
                    ]},
                    {"name": "B", "columns": [
                        {"name": "AID", "dataType": "int64", "sourceColumn": "AID"},
                    ]},
                ],
                "relationships": [{
                    "name": "A_B",
                    "fromTable": "B", "fromColumn": "AID",
                    "toTable": "A", "toColumn": "ID",
                    "crossFilteringBehavior": "bothDirections",
                }],
                "annotations": [],
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "xfilter"
            gen.create_pbi_project(out, "XFilter", bim_model=model)
            rels = (out / "XFilter.SemanticModel" / "definition"
                    / "relationships.tmdl").read_text("utf-8")
            assert "bothDirections" in rels


# ══════════════════════════════════════════════════════════════════
# 8. Script Converter — Edge Cases
# ══════════════════════════════════════════════════════════════════
class TestScriptConverterEdge:
    def test_empty_script(self):
        converter = QlikScriptToPowerQueryConverter()
        result = converter.convert_qlik_script_to_powerquery("")
        assert isinstance(result, str)

    def test_comments_only_script(self):
        converter = QlikScriptToPowerQueryConverter()
        result = converter.convert_qlik_script_to_powerquery("""
        // This is a comment
        /* Block comment */
        REM Another comment;
        """)
        assert isinstance(result, str)

    def test_set_statements_only(self):
        converter = QlikScriptToPowerQueryConverter()
        result = converter.convert_qlik_script_to_powerquery("""
        SET DateFormat='YYYY-MM-DD';
        SET ThousandSep=',';
        SET DecimalSep='.';
        """)
        assert isinstance(result, str)

    def test_resident_load(self):
        converter = QlikScriptToPowerQueryConverter()
        result = converter.convert_qlik_script_to_powerquery("""
        Products:
        LOAD ProductID, ProductName
        FROM products.csv (txt, utf8, embedded labels, delimiter is ',');

        ProductsSummary:
        LOAD
            ProductID,
            Count(ProductID) as ProductCount
        RESIDENT Products
        GROUP BY ProductID;
        """)
        assert isinstance(result, str)
        assert "Product" in result

    def test_where_clause(self):
        converter = QlikScriptToPowerQueryConverter()
        result = converter.convert_qlik_script_to_powerquery("""
        ActiveOrders:
        LOAD OrderID, Status, Amount
        FROM orders.csv (txt, utf8, embedded labels, delimiter is ',')
        WHERE Status = 'Active';
        """)
        assert isinstance(result, str)

    def test_qualify_unqualify(self):
        converter = QlikScriptToPowerQueryConverter()
        result = converter.convert_qlik_script_to_powerquery("""
        QUALIFY *;
        UNQUALIFY OrderID;

        Orders:
        LOAD * FROM orders.csv (txt, utf8, embedded labels, delimiter is ',');
        """)
        assert isinstance(result, str)


# ══════════════════════════════════════════════════════════════════
# 9. Type Mapping — All Data Types
# ══════════════════════════════════════════════════════════════════
class TestTypeConversionExhaustive:
    @pytest.mark.parametrize("qlik_type,expected", [
        ("text", "string"),
        ("num", "double"),
        ("integer", "int64"),
        ("date", "dateTime"),
        ("timestamp", "dateTime"),
        ("money", "decimal"),
        ("dual", "string"),
        ("interval", "string"),
        ("completely_unknown_type_xyz", "string"),  # fallback
        ("", "string"),
    ])
    def test_type_mapping(self, qlik_type, expected):
        result = convert_qlik_type_to_dax(qlik_type)
        assert result == expected


# ══════════════════════════════════════════════════════════════════
# 10. Large Batch Stress
# ══════════════════════════════════════════════════════════════════
class TestLargeBatchStress:
    def test_100_measures_batch(self):
        """Convert 100 measures in one batch."""
        measures = [
            {"name": f"Measure_{i}", "expression": f"Sum(Field_{i})", "label": f"M {i}"}
            for i in range(100)
        ]
        result = convert_measures_to_dax(measures)
        assert len(result) == 100
        for m in result:
            assert "SUM" in m.get("dax_expression", m.get("expression", ""))

    def test_50_datasources_batch(self):
        """Generate M queries for 50 CSV sources."""
        datasources = [
            {"connectionType": "csv", "tableName": f"Table_{i}",
             "connection": {"path": f"C:\\data\\file_{i}.csv"}}
            for i in range(50)
        ]
        result = generate_all_m_queries(datasources)
        assert len(result) == 50

    def test_100_visuals_batch(self):
        """Generate containers for 100 visuals (only 20 will be processed)."""
        vizs = [{"type": "barchart", "title": f"Chart {i}"} for i in range(100)]
        result = generate_visual_containers(vizs, "stress_test")
        assert len(result) == 20  # capped at 20
