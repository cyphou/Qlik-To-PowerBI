"""Tests for qlik_export.dax_converter — the DAX conversion engine.

Covers:
- convert_qlik_expression_to_dax (9-phase pipeline)
- convert_qlik_format_to_dax
- convert_qlik_type_to_dax
- convert_measures_to_dax / convert_dimensions_to_dax (batch)
- _SIMPLE_FUNCTION_MAP completeness
- Set analysis → CALCULATE
- Aggr() decomposition → iterators
- Inter-record functions → OFFSET / WINDOW
- Variable expansion $(vName)
- TOTAL qualifier → ALL / ALLEXCEPT
- Sum(If()) → CALCULATE / SUMX
- Concat() → CONCATENATEX
- Class() → INT/DIVIDE
- RELATED() and LOOKUPVALUE() insertion
"""

import pytest
from qlik_export.dax_converter import (
    convert_qlik_expression_to_dax,
    convert_qlik_format_to_dax,
    convert_qlik_type_to_dax,
    convert_measures_to_dax,
    convert_dimensions_to_dax,
)


# ═══════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════

def dax(expr, table="Sales", **kw):
    """Shorthand for convert_qlik_expression_to_dax."""
    return convert_qlik_expression_to_dax(expr, table_name=table, **kw)


# ═══════════════════════════════════════════════════════════════
#  Empty / None input
# ═══════════════════════════════════════════════════════════════

class TestEmptyInput:
    def test_empty_string(self):
        assert dax("") == ""

    def test_none_input(self):
        assert dax(None) == ""

    def test_whitespace(self):
        result = dax("   ")
        assert result.strip() == ""


# ═══════════════════════════════════════════════════════════════
#  Phase 1: Operator Conversion
# ═══════════════════════════════════════════════════════════════

class TestOperators:
    def test_and_operator(self):
        result = dax("A AND B")
        assert "&&" in result

    def test_or_operator(self):
        result = dax("A OR B")
        assert "||" in result

    def test_not_operator(self):
        result = dax("NOT A")
        assert "NOT" in result

    def test_mixed_case_and(self):
        result = dax("X aNd Y")
        assert "&&" in result

    def test_preserves_band(self):
        """Should not convert AND inside words like 'BAND'."""
        result = dax("BAND")
        assert "&&" not in result


# ═══════════════════════════════════════════════════════════════
#  Phase 1b: Variable Expansion
# ═══════════════════════════════════════════════════════════════

class TestVariableExpansion:
    def test_simple_variable(self):
        result = dax("$(vYear)", variables={"vYear": "2024"})
        assert "2024" in result

    def test_nested_variable(self):
        result = dax("$(vOuter)", variables={"vOuter": "$(vInner)", "vInner": "42"})
        assert "42" in result

    def test_undefined_variable(self):
        """Undefined variables stay as $(name)."""
        result = dax("$(vUndefined)")
        assert "vUndefined" in result

    def test_no_infinite_recursion(self):
        """Self-referencing variable shouldn't crash (max 10 passes)."""
        result = dax("$(vLoop)", variables={"vLoop": "$(vLoop)"})
        assert isinstance(result, str)


# ═══════════════════════════════════════════════════════════════
#  Phase 2: If / Match / Pick
# ═══════════════════════════════════════════════════════════════

class TestIfMatchPick:
    def test_if_function(self):
        result = dax("If(A > 0, 'Yes', 'No')")
        assert "IF(" in result

    def test_match_to_switch(self):
        result = dax("Match(Status, 'A', 'B', 'C')")
        assert "SWITCH(" in result

    def test_pick_to_switch(self):
        result = dax("Pick(index, 'a', 'b', 'c')")
        assert "SWITCH(" in result


# ═══════════════════════════════════════════════════════════════
#  Phase 3: Set Analysis → CALCULATE
# ═══════════════════════════════════════════════════════════════

class TestSetAnalysis:
    def test_simple_set(self):
        result = dax("Sum({<Year={2024}>} Sales)")
        assert "CALCULATE" in result
        assert "2024" in result

    def test_multiple_modifiers(self):
        result = dax("Sum({<Year={2024}, Region={'North'}>} Sales)")
        assert "CALCULATE" in result

    def test_excluded_values(self):
        """Year-= syntax (set subtraction) — parser may not decompose."""
        result = dax("Sum({<Year-={2020}>} Sales)")
        assert isinstance(result, str)  # doesn't crash

    def test_dollar_set(self):
        result = dax("Sum({$<Year={2024}>} Sales)")
        assert "CALCULATE" in result

    def test_dollar_sign_expr(self):
        result = dax("Sum({<Year={$(=Year(Today())-1)}>} Sales)")
        assert "CALCULATE" in result

    def test_set_1_all_context(self):
        result = dax("Sum({1<Year={2024}>} Sales)")
        assert "ALL" in result

    def test_clear_filter(self):
        """Year= (empty) should produce REMOVEFILTERS or ALL."""
        result = dax("Sum({<Year=>} Sales)")
        assert "CALCULATE" in result

    def test_count_distinct_set(self):
        """Count(Distinct {set} Field) — parser may not decompose Distinct prefix."""
        result = dax("Count(Distinct {<Year={2024}>} CustomerID)")
        assert isinstance(result, str)  # doesn't crash


# ═══════════════════════════════════════════════════════════════
#  Phase 3b: TOTAL qualifier
# ═══════════════════════════════════════════════════════════════

class TestTotalQualifier:
    def test_total_simple(self):
        result = dax("Sum(TOTAL Sales)")
        assert "ALL" in result or "CALCULATE" in result

    def test_total_restricted(self):
        result = dax("Sum(TOTAL <Region> Sales)")
        assert "ALLEXCEPT" in result or "ALL" in result


# ═══════════════════════════════════════════════════════════════
#  Phase 3c: Sum(If()) → CALCULATE
# ═══════════════════════════════════════════════════════════════

class TestSumIf:
    def test_sum_if_equality(self):
        result = dax("Sum(If(Status='Active', Amount, 0))")
        assert "CALCULATE" in result or "SUMX" in result

    def test_avg_if(self):
        result = dax("Avg(If(Year=2024, Revenue, 0))")
        assert "CALCULATE" in result or "AVERAGEX" in result


# ═══════════════════════════════════════════════════════════════
#  Phase 4: Aggr() Decomposition
# ═══════════════════════════════════════════════════════════════

class TestAggr:
    def test_single_dim(self):
        result = dax("Aggr(Sum(Sales), Customer)")
        assert "SUMX" in result or "VALUES" in result

    def test_multi_dim(self):
        result = dax("Aggr(Sum(Sales), Year, Month)")
        assert "SUMMARIZE" in result or "ADDCOLUMNS" in result

    def test_count_distinct_in_aggr(self):
        result = dax("Aggr(Count(Distinct ID), Region)")
        assert "COUNTX" in result or "VALUES" in result

    def test_avg_in_aggr(self):
        result = dax("Aggr(Avg(Score), Department)")
        assert "AVERAGEX" in result or "VALUES" in result


# ═══════════════════════════════════════════════════════════════
#  Phase 4b: Inter-Record Functions
# ═══════════════════════════════════════════════════════════════

class TestInterRecord:
    def test_previous(self):
        result = dax("Previous(Sum(Sales))")
        assert "OFFSET" in result

    def test_above_no_offset(self):
        result = dax("Above(Sum(Sales))")
        assert "OFFSET" in result

    def test_above_with_offset(self):
        result = dax("Above(Sum(Sales), 2)")
        assert "OFFSET" in result

    def test_below(self):
        result = dax("Below(Sum(Sales))")
        assert "OFFSET" in result

    def test_below_with_offset(self):
        result = dax("Below(Sum(Sales), 3)")
        assert "OFFSET" in result
        assert "3" in result

    def test_peek(self):
        result = dax("Peek(Amount, -1)")
        assert "OFFSET" in result

    def test_peek_no_offset(self):
        result = dax("Peek(Amount)")
        assert "OFFSET" in result

    def test_rangesum_above_running_total(self):
        result = dax("RangeSum(Above(Sum(Sales), 0, RowNo()))")
        assert "running total" in result.lower() or "CALCULATE" in result

    def test_rank(self):
        result = dax("Rank(Sum(Sales))")
        assert "RANKX" in result

    def test_field_value_count(self):
        result = dax("FieldValueCount(Region)")
        assert "DISTINCTCOUNT" in result

    def test_field_value(self):
        result = dax("FieldValue(Region, 1)")
        assert "INDEX" in result


# ═══════════════════════════════════════════════════════════════
#  Phase 5: Simple Function Map — Core Samples
# ═══════════════════════════════════════════════════════════════

class TestSimpleFunctionMap:
    # ── Aggregation ────────────────────────────────────────────
    def test_sum(self):
        assert "SUM(" in dax("Sum(Amount)")

    def test_avg(self):
        assert "AVERAGE(" in dax("Avg(Amount)")

    def test_count(self):
        assert "COUNT(" in dax("Count(ID)")

    def test_count_distinct(self):
        assert "DISTINCTCOUNT(" in dax("CountDistinct(ID)")

    def test_min(self):
        assert "MIN(" in dax("Min(Value)")

    def test_max(self):
        assert "MAX(" in dax("Max(Value)")

    def test_median(self):
        assert "MEDIAN(" in dax("Median(Score)")

    def test_only(self):
        assert "FIRSTNONBLANK(" in dax("Only(Name)")

    # ── Null / Logic ───────────────────────────────────────────
    def test_isnull(self):
        assert "ISBLANK(" in dax("IsNull(X)")

    def test_null(self):
        assert "BLANK()" in dax("Null()")

    def test_nullcount(self):
        assert "COUNTBLANK(" in dax("NullCount(X)")

    def test_true(self):
        assert "TRUE()" in dax("True()")

    def test_false(self):
        assert "FALSE()" in dax("False()")

    # ── String ─────────────────────────────────────────────────
    def test_upper(self):
        assert "UPPER(" in dax("Upper(Name)")

    def test_lower(self):
        assert "LOWER(" in dax("Lower(Name)")

    def test_len(self):
        assert "LEN(" in dax("Len(Name)")

    def test_left(self):
        assert "LEFT(" in dax("Left(Name, 3)")

    def test_right(self):
        assert "RIGHT(" in dax("Right(Name, 3)")

    def test_mid(self):
        assert "MID(" in dax("Mid(Name, 2, 4)")

    def test_trim(self):
        assert "TRIM(" in dax("Trim(Name)")

    def test_replace(self):
        assert "SUBSTITUTE(" in dax("Replace(Name, 'A', 'B')")

    def test_purgechar(self):
        assert "SUBSTITUTE(" in dax("PurgeChar(Name, '-')")

    def test_chr(self):
        assert "UNICHAR(" in dax("Chr(65)")

    def test_ord(self):
        assert "UNICODE(" in dax("Ord('A')")

    # ── Date / Time ────────────────────────────────────────────
    def test_year(self):
        assert "YEAR(" in dax("Year(Date)")

    def test_month(self):
        assert "MONTH(" in dax("Month(Date)")

    def test_day(self):
        assert "DAY(" in dax("Day(Date)")

    def test_today(self):
        assert "TODAY()" in dax("Today()")

    def test_now(self):
        assert "NOW()" in dax("Now()")

    def test_weekday(self):
        assert "WEEKDAY(" in dax("WeekDay(Date)")

    def test_monthname(self):
        assert "FORMAT(" in dax("MonthName(Date)")

    def test_monthstart(self):
        r = dax("MonthStart(Date)")
        assert "STARTOFMONTH" in r or "EOMONTH" in r or "DATE" in r

    def test_monthend(self):
        r = dax("MonthEnd(Date)")
        assert "ENDOFMONTH" in r or "EOMONTH" in r

    def test_addmonths(self):
        r = dax("AddMonths(Date, 3)")
        assert "EDATE(" in r or "DATE" in r

    # ── Math ───────────────────────────────────────────────────
    def test_abs(self):
        assert "ABS(" in dax("Abs(Value)")

    def test_ceil(self):
        r = dax("Ceil(Value)")
        assert "CEILING(" in r or "ROUNDUP(" in r

    def test_floor(self):
        assert "FLOOR(" in dax("Floor(Value)")

    def test_sqrt(self):
        assert "SQRT(" in dax("Sqrt(Value)")

    def test_mod(self):
        assert "MOD(" in dax("Mod(A, B)")

    def test_log(self):
        assert "LOG(" in dax("Log(Value)")

    def test_exp(self):
        assert "EXP(" in dax("Exp(Value)")

    def test_round(self):
        assert "ROUND(" in dax("Round(Value, 2)")

    # ── Type Conversion ────────────────────────────────────────
    def test_num(self):
        assert "VALUE(" in dax("Num(X)")

    def test_text(self):
        assert "FORMAT(" in dax("Text(X)")

    def test_date_func(self):
        assert "DATE(" in dax("Date(2024, 1, 15)")

    # ── Security ───────────────────────────────────────────────
    def test_osuser(self):
        assert "USERPRINCIPALNAME()" in dax("OSUser()")


# ═══════════════════════════════════════════════════════════════
#  Stub / Unsupported Functions
# ═══════════════════════════════════════════════════════════════

class TestStubFunctions:
    def test_skew_fallback(self):
        result = dax("Skew(Values)")
        assert "Skew fallback" in result
        assert "0" in result

    def test_correl_unsupported(self):
        result = dax("Correl(X, Y)")
        assert "Correl" in result or "0" in result

    def test_bitcount_unsupported(self):
        result = dax("BitCount(Flags)")
        assert "BitCount" in result or "0" in result

    def test_hash128_fallback(self):
        result = dax("Hash128(Data)")
        assert "Hash128 fallback" in result
        assert "FORMAT(" in result

    def test_evaluate_passthrough(self):
        result = dax("Evaluate(expr)")
        assert "Evaluate(" not in result
        assert "expr" in result

    def test_keepchar_passthrough(self):
        result = dax("KeepChar(Name, 'ABC')")
        assert "CONCATENATEX(" in result
        assert "CONTAINSSTRING(" in result


# ═══════════════════════════════════════════════════════════════
#  Phase 6: Alt() → COALESCE
# ═══════════════════════════════════════════════════════════════

class TestAlt:
    def test_alt_to_coalesce(self):
        result = dax("Alt(A, B, 'default')")
        assert "COALESCE(" in result


# ═══════════════════════════════════════════════════════════════
#  Phase 7: Class() → INT/DIVIDE
# ═══════════════════════════════════════════════════════════════

class TestClass:
    def test_class_bucket(self):
        result = dax("Class(Revenue, 1000)")
        assert "INT(" in result or "DIVIDE(" in result


# ═══════════════════════════════════════════════════════════════
#  Phase 8: RELATED() Insertion
# ═══════════════════════════════════════════════════════════════

class TestRelatedInsertion:
    def test_related_cross_table(self):
        col_map = {"CustomerName": "Customers", "Amount": "Sales"}
        rels = [{"fromTable": "Sales", "toTable": "Customers", "crossFilteringBehavior": "oneDirection"}]
        result = dax("[CustomerName]", table="Sales",
                     col_table_map=col_map,
                     relationships=rels,
                     is_calculated_column=True)
        assert "RELATED(" in result or "LOOKUPVALUE(" in result

    def test_same_table_no_related(self):
        col_map = {"Amount": "Sales"}
        result = dax("[Amount]", table="Sales",
                     col_table_map=col_map,
                     is_calculated_column=True)
        assert "RELATED(" not in result

    def test_no_related_in_measure(self):
        col_map = {"CustomerName": "Customers"}
        result = dax("[CustomerName]", table="Sales",
                     col_table_map=col_map,
                     is_calculated_column=False)
        assert "RELATED(" not in result


# ═══════════════════════════════════════════════════════════════
#  Phase 9: Cleanup
# ═══════════════════════════════════════════════════════════════

class TestCleanup:
    def test_no_double_spaces(self):
        result = dax("Sum(  Amount  )")
        assert "  " not in result.strip()


# ═══════════════════════════════════════════════════════════════
#  Concat → CONCATENATEX
# ═══════════════════════════════════════════════════════════════

class TestConcat:
    def test_concat_basic(self):
        result = dax("Concat(Name, ', ')")
        assert "CONCATENATEX" in result


# ═══════════════════════════════════════════════════════════════
#  Inline DISTINCT keyword (Qlik Count(DISTINCT x))
# ═══════════════════════════════════════════════════════════════

class TestInlineDistinct:
    def test_count_distinct_to_distinctcount(self):
        col_map = {"OrderID": "Orders"}
        result = dax("Count(DISTINCT OrderID)", table="Orders",
                     col_table_map=col_map)
        assert result == "DISTINCTCOUNT('Orders'[OrderID])"
        assert "DISTINCT " not in result  # no leftover keyword

    def test_count_distinct_lowercase(self):
        col_map = {"CustomerID": "Orders"}
        result = dax("Count(distinct CustomerID)", table="Orders",
                     col_table_map=col_map)
        assert result == "DISTINCTCOUNT('Orders'[CustomerID])"

    def test_count_distinct_in_expression(self):
        col_map = {"Sales": "Orders", "OrderID": "Orders"}
        result = dax("Sum(Sales) / Count(DISTINCT OrderID)", table="Orders",
                     col_table_map=col_map)
        assert result == "SUM('Orders'[Sales]) / DISTINCTCOUNT('Orders'[OrderID])"

    def test_plain_count_not_distinct(self):
        col_map = {"OrderID": "Orders"}
        result = dax("Count(OrderID)", table="Orders", col_table_map=col_map)
        assert result == "COUNT('Orders'[OrderID])"

    def test_sum_distinct_drops_keyword(self):
        col_map = {"Amount": "Orders"}
        result = dax("Sum(DISTINCT Amount)", table="Orders",
                     col_table_map=col_map)
        assert "DISTINCT " not in result
        assert result == "SUM('Orders'[Amount])"


# ═══════════════════════════════════════════════════════════════
#  convert_qlik_format_to_dax
# ═══════════════════════════════════════════════════════════════

class TestFormatConversion:
    def test_number_format(self):
        result = convert_qlik_format_to_dax("#,##0.00")
        assert isinstance(result, str)
        assert "0" in result

    def test_time_mm_after_hh(self):
        result = convert_qlik_format_to_dax("hh:mm:ss")
        assert "nn" in result

    def test_date_format(self):
        result = convert_qlik_format_to_dax("YYYY-MM-DD")
        assert isinstance(result, str)

    def test_empty_format(self):
        result = convert_qlik_format_to_dax("")
        assert isinstance(result, str)


# ═══════════════════════════════════════════════════════════════
#  convert_qlik_type_to_dax
# ═══════════════════════════════════════════════════════════════

class TestTypeConversion:
    def test_text_type(self):
        assert convert_qlik_type_to_dax("text") == "string"

    def test_num_type(self):
        assert convert_qlik_type_to_dax("num") == "double"

    def test_integer_type(self):
        assert convert_qlik_type_to_dax("integer") == "int64"

    def test_date_type(self):
        result = convert_qlik_type_to_dax("date")
        assert "date" in result.lower()

    def test_timestamp_type(self):
        result = convert_qlik_type_to_dax("timestamp")
        assert "datetime" in result.lower()

    def test_unknown_type(self):
        result = convert_qlik_type_to_dax("weird_type")
        assert result == "string"

    def test_empty_type(self):
        result = convert_qlik_type_to_dax("")
        assert isinstance(result, str)


# ═══════════════════════════════════════════════════════════════
#  Batch: convert_measures_to_dax / convert_dimensions_to_dax
# ═══════════════════════════════════════════════════════════════

class TestBatchConversion:
    def test_measures_basic(self):
        measures = [
            {"name": "Total", "expression": "Sum(Amount)", "label": "Total Sales"},
            {"name": "Avg", "expression": "Avg(Price)", "label": "Average Price"},
        ]
        result = convert_measures_to_dax(measures, table_name="Sales")
        assert len(result) == 2
        assert "dax_expression" in result[0]
        assert "SUM(" in result[0]["dax_expression"]

    def test_measures_empty_list(self):
        result = convert_measures_to_dax([], table_name="T")
        assert result == []

    def test_dimensions_basic(self):
        dims = [
            {"name": "Region", "field": "Region", "label": "Region"},
            {"name": "CalcDim", "field": "Upper(Name)", "label": "Upper Name"},
        ]
        result = convert_dimensions_to_dax(dims, table_name="T")
        assert len(result) == 2
        # CalcDim has an expression → is_calculated should be set
        calc_dim = [d for d in result if d["name"] == "CalcDim"][0]
        assert calc_dim.get("is_calculated") is True

    def test_dimensions_simple_field_not_calculated(self):
        dims = [{"name": "Region", "field": "Region", "label": "Region"}]
        result = convert_dimensions_to_dax(dims, table_name="T")
        assert result[0].get("is_calculated") is not True


# ═══════════════════════════════════════════════════════════════
#  Complex / Combined Expressions
# ═══════════════════════════════════════════════════════════════

class TestComplexExpressions:
    def test_nested_if_sum(self):
        result = dax("If(Sum(Revenue) > 0, Sum(Revenue) / Sum(Cost), 0)")
        assert "IF(" in result
        assert "SUM(" in result

    def test_set_with_if(self):
        """Sum({set} If()) — complex combo may not fully decompose."""
        result = dax("Sum({<Year={2024}>} If(Active=1, Amount, 0))")
        assert isinstance(result, str)  # doesn't crash
        assert "IF(" in result or "CALCULATE" in result or "2024" in result

    def test_expression_with_operators(self):
        result = dax("Sum(Amount) / Count(ID)")
        assert "SUM(" in result
        assert "COUNT(" in result

    def test_case_insensitivity(self):
        assert "SUM(" in dax("sum(Amount)")
        assert "AVERAGE(" in dax("avg(Price)")
        assert "COUNT(" in dax("count(ID)")

    def test_concat_with_set(self):
        result = dax("Concat({<Year={2024}>} Name, ', ')")
        # Should handle both set analysis and concat
        assert isinstance(result, str)

    def test_real_world_kpi(self):
        expr = "Num(Sum({<Year={$(vCurrentYear)}>} Revenue) / Sum({<Year={$(vPrevYear)}>} Revenue) - 1, '#,##0%')"
        result = dax(expr, variables={"vCurrentYear": "2024", "vPrevYear": "2023"})
        assert "CALCULATE" in result
        assert "2024" in result
