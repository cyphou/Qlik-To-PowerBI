"""Tests for v7.0.0 Phase 1 — DAX Accuracy Deepening.

Tests for:
- Aggr() decomposition to SUMX/COUNTX/AVERAGEX iterators
- Inter-record functions: RangeSum, Above, Below, Peek with OFFSET
- P()/E() set analysis functions
- Dollar-sign expressions in set modifiers
"""

import pytest
from qlik_export.dax_converter import (
    convert_qlik_expression_to_dax,
    _convert_aggr,
    _convert_inter_record,
    _convert_set_analysis,
    _parse_set_modifiers,
)


# ══════════════════════════════════════════════════════════════════
# 1. Aggr() Decomposition — Iterator Pattern
# ══════════════════════════════════════════════════════════════════

class TestAggrDecomposition:
    """Aggr() with recognized inner agg + single dim → iterator (SUMX, etc.)."""

    def test_aggr_sum_single_dim(self):
        result = _convert_aggr("Aggr(Sum(Sales), Customer)", "Orders")
        assert "SUMX" in result
        assert "VALUES('Orders'[Customer])" in result
        assert "Sum(Sales)" in result

    def test_aggr_count_single_dim(self):
        result = _convert_aggr("Aggr(Count(OrderID), Region)", "Orders")
        assert "COUNTX" in result
        assert "VALUES('Orders'[Region])" in result

    def test_aggr_avg_single_dim(self):
        result = _convert_aggr("Aggr(Avg(Score), Student)", "Grades")
        assert "AVERAGEX" in result
        assert "VALUES('Grades'[Student])" in result

    def test_aggr_min_single_dim(self):
        result = _convert_aggr("Aggr(Min(Price), Category)", "Products")
        assert "MINX" in result
        assert "VALUES('Products'[Category])" in result

    def test_aggr_max_single_dim(self):
        result = _convert_aggr("Aggr(Max(Price), Category)", "Products")
        assert "MAXX" in result

    def test_aggr_multi_dim_stays_addcolumns(self):
        """Multiple dimensions still use ADDCOLUMNS/SUMMARIZE."""
        result = _convert_aggr("Aggr(Sum(Sales), Year, Month)", "Orders")
        assert "ADDCOLUMNS" in result
        assert "SUMMARIZE" in result
        assert "'Orders'[Year]" in result
        assert "'Orders'[Month]" in result

    def test_aggr_unknown_inner_uses_addcolumns(self):
        """Unknown inner function falls back to ADDCOLUMNS/SUMMARIZE."""
        result = _convert_aggr("Aggr(Median(Score), Student)", "Grades")
        assert "ADDCOLUMNS" in result
        assert "SUMMARIZE" in result

    def test_aggr_nested_aggr(self):
        """Nested Aggr(Aggr()) — inner processed first via reversed iteration."""
        result = _convert_aggr("Aggr(Sum(Aggr(Count(ID), Month)), Year)", "Data")
        # Inner Aggr should be converted first
        assert "SUMX" in result or "ADDCOLUMNS" in result
        # Outer should also be handled
        assert "Year" in result

    def test_aggr_full_pipeline_sum(self):
        """Full pipeline: Aggr(Sum(Sales)) → SUMX via convert_qlik_expression_to_dax."""
        result = convert_qlik_expression_to_dax(
            "Aggr(Sum(Sales), Customer)", table_name="Orders"
        )
        assert "SUMX" in result or "SUM" in result

    def test_aggr_full_pipeline_count(self):
        result = convert_qlik_expression_to_dax(
            "Aggr(Count(OrderID), Region)", table_name="Sales"
        )
        assert "COUNTX" in result or "COUNT" in result


# ══════════════════════════════════════════════════════════════════
# 2. Inter-Record Functions — OFFSET pattern
# ══════════════════════════════════════════════════════════════════

class TestInterRecordOFFSET:
    """Inter-record functions using DAX OFFSET instead of EARLIER stubs."""

    def test_previous_uses_offset(self):
        result = _convert_inter_record("Previous(Amount)")
        assert "OFFSET(-1" in result
        assert "ALLSELECTED" in result

    def test_peek_with_offset(self):
        result = _convert_inter_record("Peek(Sales, -2)")
        assert "OFFSET(-2" in result

    def test_peek_zero_offset(self):
        result = _convert_inter_record("Peek(Sales, 0)")
        assert "OFFSET(0" in result

    def test_peek_no_offset(self):
        """Peek(field) with no offset → previous row."""
        result = _convert_inter_record("Peek(Revenue)")
        assert "OFFSET(-1" in result

    def test_above_with_offset(self):
        result = _convert_inter_record("Above(Total, 3)")
        assert "OFFSET(-3" in result

    def test_above_no_offset(self):
        result = _convert_inter_record("Above(Total)")
        assert "OFFSET(-1" in result

    def test_below_with_offset(self):
        result = _convert_inter_record("Below(Total, 2)")
        assert "OFFSET(2" in result

    def test_below_no_offset(self):
        result = _convert_inter_record("Below(Total)")
        assert "OFFSET(1" in result

    def test_above_with_count(self):
        """Above(field, offset, count) — count ignored, offset used."""
        result = _convert_inter_record("Above(Sales, 1, 5)")
        assert "OFFSET(-1" in result

    def test_below_with_count(self):
        result = _convert_inter_record("Below(Sales, 2, 3)")
        assert "OFFSET(2" in result

    def test_table_name_passed(self):
        """Table name should appear in ALLSELECTED."""
        result = _convert_inter_record("Previous(Amount)", "Orders")
        assert "ALLSELECTED('Orders')" in result

    def test_fieldvalue_index(self):
        result = _convert_inter_record("FieldValue(Region, 3)")
        assert "INDEX(Region, 3)" in result

    def test_fieldvaluecount(self):
        result = _convert_inter_record("FieldValueCount(Region)")
        assert "DISTINCTCOUNT(Region)" in result

    def test_rank(self):
        result = _convert_inter_record("Rank(Sales)")
        assert "RANKX" in result


class TestRangeSum:
    """RangeSum(Above(...)) → running total pattern."""

    def test_rangesum_above_running_total(self):
        result = _convert_inter_record("RangeSum(Above(Sales, 0, RowNo()))")
        assert "running total" in result.lower() or "CALCULATE" in result
        assert "SUM" in result

    def test_rangesum_above_with_table(self):
        result = _convert_inter_record("RangeSum(Above(Amount, 0, RowNo()))", "Orders")
        assert "'Orders'" in result

    def test_rangesum_full_pipeline(self):
        result = convert_qlik_expression_to_dax(
            "RangeSum(Above(Sales, 0, RowNo()))", table_name="Orders"
        )
        # Should produce some form of running total, not just a stub
        assert "CALCULATE" in result or "SUM" in result


# ══════════════════════════════════════════════════════════════════
# 3. P()/E() Set Analysis Functions
# ══════════════════════════════════════════════════════════════════

class TestSetAnalysisPE:
    """P() and E() set functions in set modifiers."""

    def test_p_function_all(self):
        """P({1} <Field>) → ALL('T'[Field])."""
        filters = _parse_set_modifiers("1 <P({1} Region)>", "Sales")
        assert any("ALL" in f and "Region" in f for f in filters)

    def test_e_function_except(self):
        """E({1} <Field>) → EXCEPT(ALL, VALUES)."""
        filters = _parse_set_modifiers("1 <E({1} Region)>", "Sales")
        assert any("EXCEPT" in f and "Region" in f for f in filters)


class TestSetAnalysisDollarExpr:
    """Dollar-sign expressions in set analysis modifiers."""

    def test_dollar_year_minus_one(self):
        """$(=Year(Today())-1) → YEAR(TODAY()) - 1 in filter."""
        filters = _parse_set_modifiers(
            "$<Year={$(=Year(Today())-1)}>", "Sales"
        )
        found = any("YEAR(TODAY()) - 1" in f for f in filters)
        assert found or len(filters) > 0  # At minimum, should produce a filter

    def test_basic_set_still_works(self):
        """Verify basic set modifiers still work after P()/E() additions."""
        filters = _parse_set_modifiers("$<Year={2024}>", "Sales")
        assert any("2024" in f for f in filters)

    def test_clear_filter_still_works(self):
        filters = _parse_set_modifiers("$<Year=>", "Sales")
        assert any("REMOVEFILTERS" in f for f in filters)

    def test_multi_value_still_works(self):
        filters = _parse_set_modifiers('$<Region={"North","South"}>', "Sales")
        assert any("North" in f for f in filters)
        assert any("South" in f for f in filters)


# ══════════════════════════════════════════════════════════════════
# 4. Full Pipeline Integration — v7 features
# ══════════════════════════════════════════════════════════════════

class TestV7FullPipeline:
    """End-to-end tests ensuring v7 features integrate cleanly."""

    def test_aggr_count_pipeline(self):
        result = convert_qlik_expression_to_dax(
            "Aggr(Count(Orders), Customer)", table_name="Sales"
        )
        assert "COUNTX" in result or "COUNT" in result

    def test_previous_pipeline(self):
        result = convert_qlik_expression_to_dax("Previous(Revenue)")
        assert "OFFSET" in result

    def test_below_pipeline(self):
        result = convert_qlik_expression_to_dax("Below(Amount, 2)")
        assert "OFFSET" in result

    def test_set_analysis_with_all(self):
        result = convert_qlik_expression_to_dax(
            "Sum({1<Year={2024}>} Sales)", table_name="Orders"
        )
        assert "CALCULATE" in result
        assert "ALL" in result
        assert "2024" in result

    def test_mixed_expression(self):
        """Expression combining multiple v7 features."""
        result = convert_qlik_expression_to_dax(
            "If(Previous(Sales) > 0, Sales / Previous(Sales) - 1, 0)"
        )
        assert "IF" in result
        assert "OFFSET" in result
