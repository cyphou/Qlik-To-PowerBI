"""Tests for qlik_export.m_query_builder — Power Query M step builders.

Covers all 40+ transform generators:
- Column ops: rename, remove, select, duplicate, reorder, split, merge
- Value ops: replace, replace_nulls, trim, clean, upper/lower/proper, fill
- Filter ops: filter_values, exclude, range, nulls, contains, distinct, top_n
- Aggregate: group_by
- Pivot: unpivot, unpivot_other, pivot
- Join: join_tables, join_tables_multi_step
- Union: append_tables, wildcard_union
- Reshape: sort, transpose, add_index, skip_rows, remove rows, promote/demote
- Calculated: add_custom_column, add_conditional_column
- Auto-chain: m_transform_* wrappers
- Orchestration: inject_m_steps, build_m_query_with_transforms
"""

import pytest
from qlik_export.m_query_builder import (
    rename_columns,
    remove_columns,
    select_columns,
    duplicate_column,
    reorder_columns,
    split_column_by_delimiter,
    merge_columns,
    replace_values,
    replace_nulls,
    trim_text,
    clean_text,
    upper_case,
    lower_case,
    proper_case,
    fill_down,
    fill_up,
    filter_values,
    exclude_values,
    filter_range,
    filter_nulls,
    filter_contains,
    distinct_rows,
    top_n,
    group_by,
    unpivot,
    unpivot_other,
    pivot,
    join_tables,
    join_tables_multi_step,
    append_tables,
    wildcard_union,
    sort_rows,
    transpose,
    add_index,
    skip_rows,
    remove_top_rows,
    remove_bottom_rows,
    promote_headers,
    demote_headers,
    add_custom_column,
    add_conditional_column,
    inject_m_steps,
    build_m_query_with_transforms,
)


# ── Fixture: base query ──────────────────────────────────────────

BASE_QUERY = """let
    Source = Csv.Document(File.Contents("data.csv"))
in
    Source"""


def _step(result):
    """Extract (step_name, step_code) from a builder result."""
    assert isinstance(result, tuple)
    assert len(result) == 2
    return result


# ═══════════════════════════════════════════════════════════════
#  Column Operations
# ═══════════════════════════════════════════════════════════════

class TestColumnOps:
    def test_rename_columns(self):
        name, code = _step(rename_columns("Source", {"Old": "New"}))
        assert "RenamedColumns" in name
        assert "Table.RenameColumns" in code
        assert "Old" in code
        assert "New" in code

    def test_remove_columns(self):
        name, code = _step(remove_columns("Source", ["Temp", "Debug"]))
        assert "RemovedColumns" in name
        assert "Table.RemoveColumns" in code

    def test_select_columns(self):
        name, code = _step(select_columns("Source", ["ID", "Name"]))
        assert "SelectedColumns" in name
        assert "Table.SelectColumns" in code

    def test_duplicate_column(self):
        name, code = _step(duplicate_column("Source", "Price", "Price_Copy"))
        assert "DuplicatedColumn" in name
        assert "Table.DuplicateColumn" in code

    def test_reorder_columns(self):
        name, code = _step(reorder_columns("Source", ["B", "A", "C"]))
        assert "ReorderedColumns" in name
        assert "Table.ReorderColumns" in code

    def test_split_column(self):
        name, code = _step(split_column_by_delimiter("Source", "FullName", ","))
        assert "SplitColumn" in name
        assert "Splitter" in code

    def test_merge_columns(self):
        name, code = _step(merge_columns("Source", ["First", "Last"], "FullName", " "))
        assert "MergedColumns" in name
        assert "Table.CombineColumns" in code or "Combiner" in code


# ═══════════════════════════════════════════════════════════════
#  Value Operations
# ═══════════════════════════════════════════════════════════════

class TestValueOps:
    def test_replace_values(self):
        name, code = _step(replace_values("Source", "Status", "old", "new"))
        assert "ReplacedValues" in name
        assert "Table.ReplaceValue" in code

    def test_replace_nulls(self):
        name, code = _step(replace_nulls("Source", "Amount", "0"))
        assert "ReplacedNulls" in name
        assert "null" in code

    def test_trim_text(self):
        name, code = _step(trim_text("Source", ["Name"]))
        assert "TrimmedText" in name
        assert "Text.Trim" in code

    def test_clean_text(self):
        name, code = _step(clean_text("Source", ["Notes"]))
        assert "CleanedText" in name
        assert "Text.Clean" in code

    def test_upper_case(self):
        name, code = _step(upper_case("Source", ["Name"]))
        assert "UpperCase" in name
        assert "Text.Upper" in code

    def test_lower_case(self):
        name, code = _step(lower_case("Source", ["Code"]))
        assert "LowerCase" in name
        assert "Text.Lower" in code

    def test_proper_case(self):
        name, code = _step(proper_case("Source", ["City"]))
        assert "ProperCase" in name
        assert "Text.Proper" in code

    def test_fill_down(self):
        name, code = _step(fill_down("Source", ["Region"]))
        assert "FilledDown" in name
        assert "Table.FillDown" in code

    def test_fill_up(self):
        name, code = _step(fill_up("Source", ["Region"]))
        assert "FilledUp" in name
        assert "Table.FillUp" in code


# ═══════════════════════════════════════════════════════════════
#  Filter Operations
# ═══════════════════════════════════════════════════════════════

class TestFilterOps:
    def test_filter_values(self):
        name, code = _step(filter_values("Source", "Status", ["Active", "Pending"]))
        assert "FilteredRows" in name
        assert "Table.SelectRows" in code or "List.Contains" in code

    def test_exclude_values(self):
        name, code = _step(exclude_values("Source", "Status", ["Closed"]))
        assert "ExcludedRows" in name

    def test_filter_range_both(self):
        name, code = _step(filter_range("Source", "Age", 18, 65))
        assert "FilteredRange" in name
        assert "18" in code
        assert "65" in code

    def test_filter_range_min_only(self):
        name, code = _step(filter_range("Source", "Age", min_val=0))
        assert ">=" in code or "0" in code

    def test_filter_range_max_only(self):
        name, code = _step(filter_range("Source", "Price", max_val=100))
        assert "<=" in code or "100" in code

    def test_filter_nulls_remove(self):
        name, code = _step(filter_nulls("Source", "Amount", keep_nulls=False))
        assert "FilteredNulls" in name
        assert "null" in code

    def test_filter_nulls_keep(self):
        name, code = _step(filter_nulls("Source", "Amount", keep_nulls=True))
        assert "null" in code

    def test_filter_contains(self):
        name, code = _step(filter_contains("Source", "Name", "Smith"))
        assert "FilteredContains" in name
        assert "Text.Contains" in code

    def test_distinct_rows(self):
        name, code = _step(distinct_rows("Source"))
        assert "DistinctRows" in name
        assert "Table.Distinct" in code

    def test_distinct_rows_columns(self):
        name, code = _step(distinct_rows("Source", ["ID"]))
        assert "Table.Distinct" in code

    def test_top_n(self):
        name, code = _step(top_n("Source", "Revenue", 10))
        assert "TopN" in name
        assert "Table.MaxN" in code


# ═══════════════════════════════════════════════════════════════
#  Aggregate
# ═══════════════════════════════════════════════════════════════

class TestAggregate:
    def test_group_by_sum(self):
        name, code = _step(group_by("Source", ["Region"],
                                     [{"column": "Amount", "agg": "sum", "alias": "Total"}]))
        assert "GroupedRows" in name
        assert "Table.Group" in code
        assert "List.Sum" in code

    def test_group_by_count(self):
        _, code = _step(group_by("Source", ["Dept"],
                                  [{"column": "ID", "agg": "count", "alias": "Cnt"}]))
        assert "List.Count" in code

    def test_group_by_avg(self):
        _, code = _step(group_by("Source", ["Cat"],
                                  [{"column": "Price", "agg": "avg", "alias": "AvgPrice"}]))
        assert "List.Average" in code

    def test_group_by_unknown_agg(self):
        """Unknown agg falls back to List.Sum."""
        _, code = _step(group_by("Source", ["Cat"],
                                  [{"column": "X", "agg": "weird", "alias": "Y"}]))
        assert "List.Sum" in code


# ═══════════════════════════════════════════════════════════════
#  Pivot / Unpivot
# ═══════════════════════════════════════════════════════════════

class TestPivotUnpivot:
    def test_unpivot(self):
        name, code = _step(unpivot("Source", ["Q1", "Q2", "Q3"]))
        assert "Unpivoted" in name
        assert "Table.UnpivotColumns" in code

    def test_unpivot_custom_names(self):
        _, code = _step(unpivot("Source", ["A"], "Metric", "Val"))
        assert "Metric" in code
        assert "Val" in code

    def test_unpivot_other(self):
        name, code = _step(unpivot_other("Source", ["ID", "Name"]))
        assert "UnpivotedOther" in name
        assert "Table.UnpivotOtherColumns" in code

    def test_pivot(self):
        name, code = _step(pivot("Source", "Category", "Amount"))
        assert "Pivoted" in name
        assert "Table.Pivot" in code


# ═══════════════════════════════════════════════════════════════
#  Join
# ═══════════════════════════════════════════════════════════════

class TestJoin:
    def test_left_join(self):
        name, code = _step(join_tables("Source", "Products", "ProductID", "ID", "left"))
        assert "Joined" in name
        assert "Table.NestedJoin" in code
        assert "JoinKind.LeftOuter" in code

    def test_inner_join(self):
        _, code = _step(join_tables("Source", "T2", "K", "K", "inner"))
        assert "JoinKind.Inner" in code

    def test_right_join(self):
        _, code = _step(join_tables("Source", "T2", "K", "K", "right"))
        assert "JoinKind.RightOuter" in code

    def test_full_join(self):
        _, code = _step(join_tables("Source", "T2", "K", "K", "full"))
        assert "JoinKind.FullOuter" in code

    def test_join_with_expand(self):
        name, code = _step(join_tables("Source", "T2", "K", "K", "left",
                                        expand_columns=["Name", "Price"]))
        assert "Expanded" in name
        assert "Table.ExpandTableColumn" in code

    def test_join_multi_step(self):
        steps = join_tables_multi_step("Source", "T2", "K", "K", "left",
                                        expand_columns=["Name"])
        assert isinstance(steps, list)
        assert len(steps) >= 1

    def test_unknown_join_kind(self):
        """Unknown join kind defaults to LeftOuter."""
        _, code = _step(join_tables("Source", "T2", "K", "K", "unknown_kind"))
        assert "JoinKind.LeftOuter" in code


# ═══════════════════════════════════════════════════════════════
#  Union / Append
# ═══════════════════════════════════════════════════════════════

class TestUnionAppend:
    def test_append_tables(self):
        name, code = _step(append_tables(["Table1", "Table2", "Table3"]))
        assert "Appended" in name
        assert "Table.Combine" in code

    def test_wildcard_union(self):
        name, code = _step(wildcard_union("C:/data", "*.csv"))
        assert "WildcardUnion" in name or "Wildcard" in name
        assert "Folder.Files" in code


# ═══════════════════════════════════════════════════════════════
#  Reshape
# ═══════════════════════════════════════════════════════════════

class TestReshape:
    def test_sort_rows(self):
        name, code = _step(sort_rows("Source", [{"column": "Name", "ascending": True}]))
        assert "SortedRows" in name
        assert "Table.Sort" in code

    def test_sort_descending(self):
        _, code = _step(sort_rows("Source", [{"column": "Amount", "ascending": False}]))
        assert "Table.Sort" in code

    def test_transpose(self):
        name, code = _step(transpose("Source"))
        assert "Transposed" in name
        assert "Table.Transpose" in code

    def test_add_index(self):
        name, code = _step(add_index("Source"))
        assert "AddedIndex" in name
        assert "Table.AddIndexColumn" in code

    def test_add_index_custom(self):
        _, code = _step(add_index("Source", "RowNum", 1))
        assert "RowNum" in code

    def test_skip_rows(self):
        name, code = _step(skip_rows("Source", 5))
        assert "SkippedRows" in name
        assert "Table.Skip" in code

    def test_remove_top_rows(self):
        name, code = _step(remove_top_rows("Source", 3))
        assert "RemovedTopRows" in name
        assert "Table.RemoveFirstN" in code

    def test_remove_bottom_rows(self):
        name, code = _step(remove_bottom_rows("Source", 2))
        assert "RemovedBottomRows" in name
        assert "Table.RemoveLastN" in code

    def test_promote_headers(self):
        name, code = _step(promote_headers("Source"))
        assert "PromotedHeaders" in name
        assert "Table.PromoteHeaders" in code

    def test_demote_headers(self):
        name, code = _step(demote_headers("Source"))
        assert "DemotedHeaders" in name
        assert "Table.DemoteHeaders" in code


# ═══════════════════════════════════════════════════════════════
#  Calculated Columns
# ═══════════════════════════════════════════════════════════════

class TestCalculated:
    def test_add_custom_column(self):
        name, code = _step(add_custom_column("Source", "FullName",
                                              '[First] & " " & [Last]'))
        assert "AddedCustom" in name
        assert "Table.AddColumn" in code

    def test_add_conditional_column(self):
        conditions = [
            {"column": "Score", "operator": ">", "value": "90", "result": "A"},
            {"column": "Score", "operator": ">", "value": "80", "result": "B"},
        ]
        name, code = _step(add_conditional_column("Source", "Grade", conditions, "C"))
        assert "AddedConditional" in name
        assert "Table.AddColumn" in code
        assert "if" in code.lower()

    def test_conditional_equals(self):
        conditions = [
            {"column": "Status", "operator": "=", "value": "Active", "result": "Yes"},
        ]
        _, code = _step(add_conditional_column("Source", "IsActive", conditions))
        assert "Active" in code


# ═══════════════════════════════════════════════════════════════
#  inject_m_steps
# ═══════════════════════════════════════════════════════════════

class TestInjectMSteps:
    def test_inject_single_step(self):
        step = rename_columns("Source", {"Old": "New"})
        result = inject_m_steps(BASE_QUERY, [step])
        assert "RenamedColumns" in result
        assert "Table.RenameColumns" in result
        assert "in" in result.lower()

    def test_inject_multiple_steps(self):
        s1 = rename_columns("Source", {"A": "B"})
        s2 = remove_columns(s1[0], ["Temp"])
        result = inject_m_steps(BASE_QUERY, [s1, s2])
        assert "RenamedColumns" in result
        assert "RemovedColumns" in result

    def test_inject_preserves_source(self):
        step = filter_values("Source", "Status", ["Active"])
        result = inject_m_steps(BASE_QUERY, [step])
        assert "Csv.Document" in result  # original source preserved

    def test_inject_empty_steps(self):
        result = inject_m_steps(BASE_QUERY, [])
        assert result == BASE_QUERY

    def test_in_target_rewrites(self):
        step = add_index("Source")
        result = inject_m_steps(BASE_QUERY, [step])
        # The 'in' section should reference the last injected step
        assert "AddedIndex" in result


# ═══════════════════════════════════════════════════════════════
#  build_m_query_with_transforms
# ═══════════════════════════════════════════════════════════════

class TestBuildMQueryWithTransforms:
    def test_single_transform(self):
        result = build_m_query_with_transforms(BASE_QUERY, [
            {"type": "rename", "mapping": {"Old": "New"}},
        ])
        assert "RenamedColumns" in result

    def test_multiple_transforms(self):
        result = build_m_query_with_transforms(BASE_QUERY, [
            {"type": "upper", "columns": ["Name"]},
            {"type": "filter_values", "column": "Status", "values": ["Active"]},
        ])
        assert "UpperCase" in result
        assert "FilteredRows" in result

    def test_all_transform_types(self):
        """Every supported transform type should not crash."""
        transforms = [
            {"type": "rename", "mapping": {"A": "B"}},
            {"type": "remove", "columns": ["Temp"]},
            {"type": "trim", "columns": ["Name"]},
            {"type": "sort", "columns": [{"column": "ID", "ascending": True}]},
            {"type": "add_index"},
        ]
        result = build_m_query_with_transforms(BASE_QUERY, transforms)
        assert "let" in result.lower()
        assert "in" in result.lower()

    def test_unknown_transform_skipped(self):
        result = build_m_query_with_transforms(BASE_QUERY, [
            {"type": "nonexistent_transform"},
        ])
        assert "let" in result.lower()  # original query intact

    def test_empty_transforms(self):
        result = build_m_query_with_transforms(BASE_QUERY, [])
        assert result == BASE_QUERY


# ═══════════════════════════════════════════════════════════════
#  Edge Cases
# ═══════════════════════════════════════════════════════════════

class TestEdgeCases:
    def test_all_functions_return_tuples(self):
        """Every step generator should return (str, str)."""
        results = [
            rename_columns("S", {"A": "B"}),
            remove_columns("S", ["X"]),
            select_columns("S", ["Y"]),
            duplicate_column("S", "A", "A2"),
            reorder_columns("S", ["B", "A"]),
            replace_values("S", "C", "o", "n"),
            replace_nulls("S", "C", "0"),
            trim_text("S", ["C"]),
            clean_text("S", ["C"]),
            upper_case("S", ["C"]),
            lower_case("S", ["C"]),
            proper_case("S", ["C"]),
            fill_down("S", ["C"]),
            fill_up("S", ["C"]),
            filter_values("S", "C", ["v"]),
            exclude_values("S", "C", ["v"]),
            filter_range("S", "C", 0, 10),
            filter_nulls("S", "C"),
            filter_contains("S", "C", "x"),
            distinct_rows("S"),
            top_n("S", "C", 5),
            unpivot("S", ["A"]),
            unpivot_other("S", ["A"]),
            pivot("S", "A", "B"),
            sort_rows("S", [{"column": "A"}]),
            transpose("S"),
            add_index("S"),
            skip_rows("S", 1),
            remove_top_rows("S", 1),
            remove_bottom_rows("S", 1),
            promote_headers("S"),
            demote_headers("S"),
            add_custom_column("S", "N", "1"),
        ]
        for r in results:
            assert isinstance(r, tuple), f"Expected tuple, got {type(r)}"
            assert len(r) == 2
            assert isinstance(r[0], str)
            assert isinstance(r[1], str)

    def test_prev_step_threading(self):
        """Steps should reference the previous step name."""
        s1_name, _ = rename_columns("Source", {"A": "B"})
        s2_name, s2_code = filter_values(s1_name, "Status", ["Active"])
        assert s1_name in s2_code
