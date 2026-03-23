"""Tests for v6.0.0 Phase 2 — DAX Accuracy & Expression Depth."""

import pytest
from qlik_export.dax_converter import (
    convert_qlik_expression_to_dax,
    _expand_variables,
    _convert_total_qualifier,
    _convert_set_analysis,
    _convert_aggr,
    _convert_concat,
    _convert_sum_if,
    _split_top_level_args,
)


# ── 2.1 Dollar-sign variable expansion ─────────────────────────


class TestVariableExpansion:
    """Tests for $(vName) and $(=expr) expansion."""

    def test_simple_variable(self):
        result = _expand_variables("Sum($(vSalesField))", {"vSalesField": "Sales"})
        assert result == "Sum(Sales)"

    def test_multiple_variables(self):
        variables = {"vYear": "2024", "vRegion": "North"}
        result = _expand_variables("$(vYear) and $(vRegion)", variables)
        assert result == "2024 and North"

    def test_nested_variables(self):
        variables = {"vInner": "Sales", "vOuter": "Sum($(vInner))"}
        result = _expand_variables("$(vOuter)", variables)
        assert result == "Sum(Sales)"

    def test_expression_variable(self):
        """$(=expression) should inline the expression, stripping the '='."""
        result = _expand_variables("Sum($(=Year(Today())))", {})
        assert result == "Sum(Year(Today()))"

    def test_expression_variable_with_vars(self):
        variables = {"vThreshold": "100"}
        result = _expand_variables("If(Sales > $(vThreshold), $(=1+1))", variables)
        assert result == "If(Sales > 100, 1+1)"

    def test_unknown_variable_kept(self):
        result = _expand_variables("$(vUnknown)", {"vOther": "X"})
        assert result == "$(vUnknown)"

    def test_no_variables_passthrough(self):
        result = _expand_variables("Sum(Sales)", None)
        assert result == "Sum(Sales)"

    def test_no_dollar_sign_passthrough(self):
        result = _expand_variables("Sum(Sales)", {"vX": "Y"})
        assert result == "Sum(Sales)"

    def test_max_depth_prevents_infinite_loop(self):
        """Self-referencing variable should not loop forever."""
        variables = {"vLoop": "$(vLoop)"}
        result = _expand_variables("$(vLoop)", variables)
        # After 10 iterations it should stop; the result is still $(vLoop)
        assert "vLoop" in result

    def test_variable_in_full_pipeline(self):
        """$() expansion integrated into convert_qlik_expression_to_dax."""
        result = convert_qlik_expression_to_dax(
            "Sum($(vField))",
            variables={"vField": "Sales"},
        )
        assert "SUM" in result
        assert "Sales" in result


# ── 2.2 TOTAL qualifier ─────────────────────────────────────────


class TestTotalQualifier:
    """Tests for TOTAL → CALCULATE + ALL/ALLEXCEPT."""

    def test_simple_total(self):
        result = _convert_total_qualifier("Sum(TOTAL Sales)", "Orders")
        assert "CALCULATE" in result
        assert "ALL('Orders')" in result
        assert "SUM" in result

    def test_total_with_dimension(self):
        result = _convert_total_qualifier("Sum(TOTAL <Region> Sales)", "Orders")
        assert "CALCULATE" in result
        assert "ALLEXCEPT" in result
        assert "'Orders'[Region]" in result

    def test_total_multiple_dimensions(self):
        result = _convert_total_qualifier("Sum(TOTAL <Region, Year> Sales)", "Orders")
        assert "ALLEXCEPT" in result
        assert "'Orders'[Region]" in result
        assert "'Orders'[Year]" in result

    def test_total_count_distinct(self):
        result = _convert_total_qualifier("Count(TOTAL CustomerID)", "Sales")
        assert "CALCULATE" in result
        assert "ALL('Sales')" in result

    def test_no_total_passthrough(self):
        result = _convert_total_qualifier("Sum(Sales)", "Orders")
        assert result == "Sum(Sales)"


# ── 2.3 Sum(If(...)) → CALCULATE/SUMX ───────────────────────────


class TestSumIf:
    """Tests for Sum(If(cond, val)) → CALCULATE or SUMX."""

    def test_sum_if_equality(self):
        """Sum(If(Region='North', Sales)) → CALCULATE(SUM(...), filter)."""
        result = _convert_sum_if('Sum(If(Region="North", Sales))', "Orders")
        assert "CALCULATE" in result
        assert "SUM" in result
        assert "Region" in result

    def test_sum_if_complex_condition(self):
        """Sum(If(Year>2020, Amount, 0)) → SUMX(FILTER(...), ...)."""
        result = _convert_sum_if("Sum(If(Year>2020, Amount, 0))", "Orders")
        assert "SUMX" in result or "CALCULATE" in result
        assert "FILTER" in result or "Amount" in result

    def test_avg_if(self):
        """Avg(If(Status='Active', Score)) → CALCULATE or AVERAGEX."""
        result = _convert_sum_if('Avg(If(Status="Active", Score))', "Data")
        assert "AVERAGE" in result or "AVERAGEX" in result

    def test_no_sum_if_passthrough(self):
        result = _convert_sum_if("Sum(Sales)", "Orders")
        assert result == "Sum(Sales)"

    def test_sum_if_full_pipeline(self):
        result = convert_qlik_expression_to_dax(
            'Sum(If(Region="North", Sales))', table_name="Orders"
        )
        assert "CALCULATE" in result or "SUMX" in result


# ── 2.4 Concat → CONCATENATEX ───────────────────────────────────


class TestConcat:
    """Tests for Concat() → CONCATENATEX()."""

    def test_simple_concat(self):
        result = _convert_concat("Concat(ProductName, ', ')", "Products")
        assert "CONCATENATEX" in result
        assert "VALUES" in result
        assert "'Products'[ProductName]" in result

    def test_concat_with_distinct(self):
        result = _convert_concat("Concat(DISTINCT Region, '; ')", "Sales")
        assert "CONCATENATEX" in result
        assert "'Sales'[Region]" in result

    def test_concat_with_sort(self):
        result = _convert_concat("Concat(Region, ', ', Region)", "Sales")
        assert "CONCATENATEX" in result
        assert "ASC" in result

    def test_no_concat_passthrough(self):
        result = _convert_concat("Sum(Sales)", "T")
        assert result == "Sum(Sales)"

    def test_concat_full_pipeline(self):
        result = convert_qlik_expression_to_dax(
            "Concat(ProductName, ', ')", table_name="Products"
        )
        assert "CONCATENATEX" in result


# ── 2.5 Nested Aggr ─────────────────────────────────────────────


class TestAggrBracketMatching:
    """Tests for Aggr() → ADDCOLUMNS(SUMMARIZE(...))."""

    def test_simple_aggr(self):
        result = _convert_aggr("Aggr(Sum(Sales), Customer)", "Orders")
        # Single dim with Sum → SUMX iterator pattern
        assert "SUMX" in result
        assert "VALUES('Orders'[Customer])" in result

    def test_aggr_multiple_dims(self):
        result = _convert_aggr("Aggr(Count(OrderID), Year, Month)", "Orders")
        assert "ADDCOLUMNS" in result
        assert "'Orders'[Year]" in result
        assert "'Orders'[Month]" in result

    def test_aggr_nested_expression(self):
        """Aggr with nested function calls should be parsed correctly."""
        result = _convert_aggr("Aggr(Sum(If(x>1, Sales)), Region)", "Data")
        # Single dim with Sum → SUMX iterator pattern
        assert "SUMX" in result
        assert "VALUES('Data'[Region])" in result
        # The inner expression should be preserved
        assert "Sum(If(x>1, Sales))" in result

    def test_no_aggr_passthrough(self):
        result = _convert_aggr("Sum(Sales)", "T")
        assert result == "Sum(Sales)"

    def test_aggr_full_pipeline(self):
        result = convert_qlik_expression_to_dax(
            "Aggr(Sum(Sales), Customer)", table_name="Orders"
        )
        # Single dim with Sum → SUMX iterator via full pipeline
        assert "SUMX" in result or "SUM" in result


# ── 2.6 Set Analysis operators ───────────────────────────────────


class TestSetAnalysisExtended:
    """Tests for extended set analysis: {1<>}, {$<>}, subtraction, union."""

    def test_basic_set(self):
        result = _convert_set_analysis("Sum({<Year={2024}>} Sales)", "Orders")
        assert "CALCULATE" in result
        assert "2024" in result

    def test_set_with_all(self):
        """Sum({1<Year={2024}>} Sales) → CALCULATE(…, ALL(…), Year=2024)."""
        result = _convert_set_analysis("Sum({1<Year={2024}>} Sales)", "Orders")
        assert "CALCULATE" in result
        assert "ALL" in result

    def test_set_with_dollar(self):
        """Sum({$<Year={2024}>} Sales) → CALCULATE(…, Year=2024)."""
        result = _convert_set_analysis("Sum({$<Year={2024}>} Sales)", "Orders")
        assert "CALCULATE" in result
        assert "2024" in result

    def test_set_clear_field(self):
        """Sum({<Year=>} Sales) → CALCULATE(…, REMOVEFILTERS(Year))."""
        result = _convert_set_analysis("Sum({<Year=>} Sales)", "Orders")
        assert "REMOVEFILTERS" in result

    def test_set_multiple_values(self):
        result = _convert_set_analysis(
            'Sum({<Region={"North","South"}>} Sales)', "Orders"
        )
        assert "CALCULATE" in result
        assert "North" in result
        assert "South" in result

    def test_set_subtraction(self):
        """Sum({<Region=Region-{'Alaska'}>} Sales) → exclude Alaska."""
        result = _convert_set_analysis(
            "Sum({<Region=Region-{'Alaska'}>} Sales)", "Orders"
        )
        assert "CALCULATE" in result
        assert "Alaska" in result

    def test_set_union(self):
        """Sum({<Year=Year+{2024}>} Sales) → include 2024 in addition."""
        result = _convert_set_analysis(
            "Sum({<Year=Year+{2024}>} Sales)", "Orders"
        )
        assert "CALCULATE" in result
        assert "2024" in result


# ── Split top-level args helper ──────────────────────────────────


class TestSplitTopLevelArgs:
    """Tests for the bracket-aware argument splitter."""

    def test_simple_args(self):
        assert _split_top_level_args("a, b, c") == ["a", " b", " c"]

    def test_nested_parens(self):
        args = _split_top_level_args("Sum(a, b), c")
        assert len(args) == 2
        assert "Sum(a, b)" in args[0]

    def test_quoted_comma(self):
        args = _split_top_level_args('a, "hello, world", b')
        assert len(args) == 3

    def test_empty(self):
        assert _split_top_level_args("") == []

    def test_deeply_nested(self):
        # Inner content of Aggr(...): "Sum(If(x>1, Sales)), Region, Year"
        args = _split_top_level_args("Sum(If(x>1, Sales)), Region, Year")
        assert len(args) == 3


# ── Variable-as-measure in pipeline ──────────────────────────────


class TestVariableAsMeasure:
    """Test that variables with aggregation expressions are correctly handled."""

    def test_variable_expansion_then_dax(self):
        """A variable containing Sum() should expand then convert."""
        result = convert_qlik_expression_to_dax(
            "$(vTotalSales)",
            variables={"vTotalSales": "Sum(Revenue)"},
        )
        assert "SUM" in result
        assert "Revenue" in result

    def test_nested_variable_expansion(self):
        """Nested variable: $(vOuter) references $(vInner)."""
        result = convert_qlik_expression_to_dax(
            "$(vOuter)",
            variables={"vOuter": "Sum($(vField))", "vField": "Sales"},
        )
        assert "SUM" in result
        assert "Sales" in result
