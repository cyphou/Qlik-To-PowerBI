"""
Power Query M Builder — 40+ chainable transforms + inject_m_steps

Provides composable transform functions that produce M query steps.
Each function takes a `prev_step` name and returns (step_name, m_code).

The `inject_m_steps()` function inserts transform steps into an existing
`let ... in Result` M query, before the final `in` clause.

Transform categories:
  Column ops:  rename, remove, select, duplicate, reorder, split, merge
  Value ops:   replace, replace_nulls, trim, clean, upper, lower, proper, fill_down, fill_up
  Filter ops:  filter_values, exclude, filter_range, filter_nulls, filter_contains, distinct, top_n
  Aggregate:   group_by (sum/avg/count/countd/min/max/median/stdev)
  Pivot:       unpivot, unpivot_other, pivot
  Join:        join (inner/left/right/full/leftanti/rightanti) with auto-expand
  Union:       append_tables, wildcard_union
  Reshape:     sort, transpose, add_index, skip_rows, remove_rows, promote_headers, demote_headers
  Calculated:  add_custom_column, add_conditional_column
"""

import logging
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger(__name__)


def _m_col(name: str) -> str:
    """Escape column name for M code."""
    return f'"{name}"'


# ═══════════════════════════════════════════════════════════════════
# Column Operations
# ═══════════════════════════════════════════════════════════════════

def rename_columns(prev: str, mapping: Dict[str, str]) -> Tuple[str, str]:
    """Rename columns. mapping: {old_name: new_name}."""
    pairs = ", ".join(f'{{{_m_col(old)}, {_m_col(new)}}}'
                      for old, new in mapping.items())
    return ("RenamedColumns", f'    RenamedColumns = Table.RenameColumns({prev}, {{{pairs}}})')


def remove_columns(prev: str, columns: List[str]) -> Tuple[str, str]:
    """Remove specified columns."""
    cols = ", ".join(_m_col(c) for c in columns)
    return ("RemovedColumns", f'    RemovedColumns = Table.RemoveColumns({prev}, {{{cols}}})')


def select_columns(prev: str, columns: List[str]) -> Tuple[str, str]:
    """Keep only specified columns."""
    cols = ", ".join(_m_col(c) for c in columns)
    return ("SelectedColumns", f'    SelectedColumns = Table.SelectColumns({prev}, {{{cols}}})')


def duplicate_column(prev: str, source: str, new_name: str) -> Tuple[str, str]:
    """Duplicate a column with a new name."""
    return ("DuplicatedColumn",
            f'    DuplicatedColumn = Table.DuplicateColumn({prev}, {_m_col(source)}, {_m_col(new_name)})')


def reorder_columns(prev: str, columns: List[str]) -> Tuple[str, str]:
    """Reorder columns."""
    cols = ", ".join(_m_col(c) for c in columns)
    return ("ReorderedColumns", f'    ReorderedColumns = Table.ReorderColumns({prev}, {{{cols}}})')


def split_column_by_delimiter(prev: str, column: str, delimiter: str = ",") -> Tuple[str, str]:
    """Split a column by delimiter."""
    return ("SplitColumn",
            f'    SplitColumn = Table.SplitColumn({prev}, {_m_col(column)}, '
            f'Splitter.SplitTextByDelimiter("{delimiter}", QuoteStyle.Csv))')


def merge_columns(prev: str, columns: List[str], new_name: str, separator: str = " ") -> Tuple[str, str]:
    """Merge multiple columns into one."""
    cols = ", ".join(_m_col(c) for c in columns)
    return ("MergedColumns",
            f'    MergedColumns = Table.CombineColumns({prev}, {{{cols}}}, '
            f'Combiner.CombineTextByDelimiter("{separator}", QuoteStyle.None), {_m_col(new_name)})')


# ═══════════════════════════════════════════════════════════════════
# Value Operations
# ═══════════════════════════════════════════════════════════════════

def replace_values(prev: str, column: str, old_value: str, new_value: str) -> Tuple[str, str]:
    """Replace values in a column."""
    return ("ReplacedValues",
            f'    ReplacedValues = Table.ReplaceValue({prev}, "{old_value}", "{new_value}", '
            f'Replacer.ReplaceText, {{{_m_col(column)}}})')


def replace_nulls(prev: str, column: str, replacement: str) -> Tuple[str, str]:
    """Replace null values in a column."""
    return ("ReplacedNulls",
            f'    ReplacedNulls = Table.ReplaceValue({prev}, null, "{replacement}", '
            f'Replacer.ReplaceValue, {{{_m_col(column)}}})')


def trim_text(prev: str, columns: List[str]) -> Tuple[str, str]:
    """Trim whitespace from columns."""
    transforms = ", ".join(f'{{{_m_col(c)}, Text.Trim}}' for c in columns)
    return ("TrimmedText", f'    TrimmedText = Table.TransformColumns({prev}, {{{transforms}}})')


def clean_text(prev: str, columns: List[str]) -> Tuple[str, str]:
    """Remove non-printable characters from columns."""
    transforms = ", ".join(f'{{{_m_col(c)}, Text.Clean}}' for c in columns)
    return ("CleanedText", f'    CleanedText = Table.TransformColumns({prev}, {{{transforms}}})')


def upper_case(prev: str, columns: List[str]) -> Tuple[str, str]:
    """Convert columns to uppercase."""
    transforms = ", ".join(f'{{{_m_col(c)}, Text.Upper}}' for c in columns)
    return ("UpperCase", f'    UpperCase = Table.TransformColumns({prev}, {{{transforms}}})')


def lower_case(prev: str, columns: List[str]) -> Tuple[str, str]:
    """Convert columns to lowercase."""
    transforms = ", ".join(f'{{{_m_col(c)}, Text.Lower}}' for c in columns)
    return ("LowerCase", f'    LowerCase = Table.TransformColumns({prev}, {{{transforms}}})')


def proper_case(prev: str, columns: List[str]) -> Tuple[str, str]:
    """Convert columns to proper case."""
    transforms = ", ".join(f'{{{_m_col(c)}, Text.Proper}}' for c in columns)
    return ("ProperCase", f'    ProperCase = Table.TransformColumns({prev}, {{{transforms}}})')


def fill_down(prev: str, columns: List[str]) -> Tuple[str, str]:
    """Fill null values downward."""
    cols = ", ".join(_m_col(c) for c in columns)
    return ("FilledDown", f'    FilledDown = Table.FillDown({prev}, {{{cols}}})')


def fill_up(prev: str, columns: List[str]) -> Tuple[str, str]:
    """Fill null values upward."""
    cols = ", ".join(_m_col(c) for c in columns)
    return ("FilledUp", f'    FilledUp = Table.FillUp({prev}, {{{cols}}})')


# ═══════════════════════════════════════════════════════════════════
# Filter Operations
# ═══════════════════════════════════════════════════════════════════

def filter_values(prev: str, column: str, values: List[str]) -> Tuple[str, str]:
    """Keep rows where column matches one of the given values."""
    val_list = ", ".join(f'"{v}"' for v in values)
    return ("FilteredRows",
            f'    FilteredRows = Table.SelectRows({prev}, each List.Contains({{{val_list}}}, [' + column + ']))')


def exclude_values(prev: str, column: str, values: List[str]) -> Tuple[str, str]:
    """Remove rows where column matches one of the given values."""
    val_list = ", ".join(f'"{v}"' for v in values)
    return ("ExcludedRows",
            f'    ExcludedRows = Table.SelectRows({prev}, each not List.Contains({{{val_list}}}, [' + column + ']))')


def filter_range(prev: str, column: str, min_val: Optional[str] = None,
                 max_val: Optional[str] = None) -> Tuple[str, str]:
    """Filter rows by numeric range."""
    conditions = []
    if min_val is not None:
        conditions.append(f'[{column}] >= {min_val}')
    if max_val is not None:
        conditions.append(f'[{column}] <= {max_val}')
    condition = " and ".join(conditions) if conditions else "true"
    return ("FilteredRange", f'    FilteredRange = Table.SelectRows({prev}, each {condition})')


def filter_nulls(prev: str, column: str, keep_nulls: bool = False) -> Tuple[str, str]:
    """Filter rows based on null values."""
    op = "=" if keep_nulls else "<>"
    return ("FilteredNulls",
            f'    FilteredNulls = Table.SelectRows({prev}, each [{column}] {op} null)')


def filter_contains(prev: str, column: str, text: str) -> Tuple[str, str]:
    """Filter rows where column contains text."""
    return ("FilteredContains",
            f'    FilteredContains = Table.SelectRows({prev}, each Text.Contains([{column}], "{text}"))')


def distinct_rows(prev: str, columns: Optional[List[str]] = None) -> Tuple[str, str]:
    """Remove duplicate rows."""
    if columns:
        cols = ", ".join(_m_col(c) for c in columns)
        return ("DistinctRows", f'    DistinctRows = Table.Distinct({prev}, {{{cols}}})')
    return ("DistinctRows", f'    DistinctRows = Table.Distinct({prev})')


def top_n(prev: str, column: str, n: int, ascending: bool = False) -> Tuple[str, str]:
    """Keep top N rows by column."""
    order = "Order.Ascending" if ascending else "Order.Descending"
    return ("TopN",
            f'    TopN = Table.MaxN({prev}, {{{{{_m_col(column)}, {order}}}}}, {n})')


# ═══════════════════════════════════════════════════════════════════
# Aggregate
# ═══════════════════════════════════════════════════════════════════

_AGG_FUNCTIONS = {
    "sum": ('List.Sum', 'type number'),
    "avg": ('List.Average', 'type number'),
    "average": ('List.Average', 'type number'),
    "count": ('List.Count', 'Int64.Type'),
    "countd": ('List.NonNullCount', 'Int64.Type'),
    "countdistinct": ('List.NonNullCount', 'Int64.Type'),
    "min": ('List.Min', 'type number'),
    "max": ('List.Max', 'type number'),
    "median": ('List.Median', 'type number'),
    "stdev": ('List.StandardDeviation', 'type number'),
}


def group_by(prev: str, group_cols: List[str],
             agg_specs: List[Dict[str, str]]) -> Tuple[str, str]:
    """
    Group by columns and aggregate.

    agg_specs: list of {column, agg, alias} where agg is
    sum/avg/count/countd/min/max/median/stdev
    """
    g_cols = ", ".join(_m_col(c) for c in group_cols)

    agg_parts = []
    for spec in agg_specs:
        alias = spec.get("alias", f'{spec["agg"]}_{spec["column"]}')
        func, m_type = _AGG_FUNCTIONS.get(spec["agg"].lower(), ("List.Sum", "type number"))
        agg_parts.append(
            f'{{{_m_col(alias)}, each {func}([{spec["column"]}]), {m_type}}}'
        )
    aggs = ", ".join(agg_parts)
    return ("GroupedRows",
            f'    GroupedRows = Table.Group({prev}, {{{g_cols}}}, {{{aggs}}})')


# ═══════════════════════════════════════════════════════════════════
# Pivot / Unpivot
# ═══════════════════════════════════════════════════════════════════

def unpivot(prev: str, columns: List[str], attribute_col: str = "Attribute",
            value_col: str = "Value") -> Tuple[str, str]:
    """Unpivot specified columns."""
    cols = ", ".join(_m_col(c) for c in columns)
    return ("Unpivoted",
            f'    Unpivoted = Table.UnpivotColumns({prev}, {{{cols}}}, '
            f'{_m_col(attribute_col)}, {_m_col(value_col)})')


def unpivot_other(prev: str, keep_columns: List[str], attribute_col: str = "Attribute",
                  value_col: str = "Value") -> Tuple[str, str]:
    """Unpivot all columns except the specified ones."""
    cols = ", ".join(_m_col(c) for c in keep_columns)
    return ("UnpivotedOther",
            f'    UnpivotedOther = Table.UnpivotOtherColumns({prev}, {{{cols}}}, '
            f'{_m_col(attribute_col)}, {_m_col(value_col)})')


def pivot(prev: str, attribute_col: str, value_col: str,
          agg: str = "sum") -> Tuple[str, str]:
    """Pivot a column."""
    func = _AGG_FUNCTIONS.get(agg.lower(), ("List.Sum",))[0]
    return ("Pivoted",
            f'    Pivoted = Table.Pivot({prev}, List.Distinct({prev}[{attribute_col}]), '
            f'{_m_col(attribute_col)}, {_m_col(value_col)}, {func})')


# ═══════════════════════════════════════════════════════════════════
# Join
# ═══════════════════════════════════════════════════════════════════

_JOIN_KINDS = {
    "inner": "JoinKind.Inner",
    "left": "JoinKind.LeftOuter",
    "leftouter": "JoinKind.LeftOuter",
    "right": "JoinKind.RightOuter",
    "rightouter": "JoinKind.RightOuter",
    "full": "JoinKind.FullOuter",
    "fullouter": "JoinKind.FullOuter",
    "leftanti": "JoinKind.LeftAnti",
    "rightanti": "JoinKind.RightAnti",
}


def join_tables(prev: str, right_table: str, left_key: str, right_key: str,
                join_kind: str = "left", expand_columns: Optional[List[str]] = None,
                step_suffix: str = "") -> Tuple[str, str]:
    """
    Join with another table and optionally auto-expand.
    Returns two steps if expand_columns is provided, else one step.
    """
    kind = _JOIN_KINDS.get(join_kind.lower().replace(" ", ""), "JoinKind.LeftOuter")
    join_step = (f'Joined{step_suffix}',
                 f'    Joined{step_suffix} = Table.NestedJoin({prev}, '
                 f'{{{_m_col(left_key)}}}, {right_table}, '
                 f'{{{_m_col(right_key)}}}, "Joined", {kind})')

    if expand_columns:
        cols = ", ".join(_m_col(c) for c in expand_columns)
        expand_step = (f'Expanded{step_suffix}',
                       f'    Expanded{step_suffix} = Table.ExpandTableColumn('
                       f'Joined{step_suffix}, "Joined", {{{cols}}})')
        return expand_step  # Return expand step as final
    return join_step


def join_tables_multi_step(prev: str, right_table: str, left_key: str, right_key: str,
                           join_kind: str = "left",
                           expand_columns: Optional[List[str]] = None,
                           step_suffix: str = "") -> List[Tuple[str, str]]:
    """
    Join with another table, returning multiple steps (join + optional expand).
    """
    kind = _JOIN_KINDS.get(join_kind.lower().replace(" ", ""), "JoinKind.LeftOuter")
    steps = []
    steps.append(
        (f'Joined{step_suffix}',
         f'    Joined{step_suffix} = Table.NestedJoin({prev}, '
         f'{{{_m_col(left_key)}}}, {right_table}, '
         f'{{{_m_col(right_key)}}}, "Joined", {kind})')
    )
    if expand_columns:
        cols = ", ".join(_m_col(c) for c in expand_columns)
        steps.append(
            (f'Expanded{step_suffix}',
             f'    Expanded{step_suffix} = Table.ExpandTableColumn('
             f'Joined{step_suffix}, "Joined", {{{cols}}})')
        )
    return steps


# ═══════════════════════════════════════════════════════════════════
# Union / Append
# ═══════════════════════════════════════════════════════════════════

def append_tables(tables: List[str]) -> Tuple[str, str]:
    """Append (union) multiple tables."""
    table_list = ", ".join(tables)
    return ("Appended", f'    Appended = Table.Combine({{{table_list}}})')


def wildcard_union(folder_path: str, file_pattern: str = "*.csv") -> Tuple[str, str]:
    """Union all files from a folder matching a pattern."""
    return ("WildcardUnion", "\n".join([
        f'    Files = Folder.Files("{folder_path}"),',
        f'    Filtered = Table.SelectRows(Files, each Text.EndsWith([Name], ".csv")),',
        f'    WildcardUnion = Table.Combine(Table.TransformRows(Filtered, '
        f'each Csv.Document([Content], [Delimiter=","])))',
    ]))


# ═══════════════════════════════════════════════════════════════════
# Reshape
# ═══════════════════════════════════════════════════════════════════

def sort_rows(prev: str, columns: List[Dict[str, Any]]) -> Tuple[str, str]:
    """Sort rows by columns. columns: [{column, ascending}]."""
    sort_specs = []
    for spec in columns:
        order = "Order.Ascending" if spec.get("ascending", True) else "Order.Descending"
        sort_specs.append(f'{{{_m_col(spec["column"])}, {order}}}')
    specs = ", ".join(sort_specs)
    return ("SortedRows", f'    SortedRows = Table.Sort({prev}, {{{specs}}})')


def transpose(prev: str) -> Tuple[str, str]:
    """Transpose the table."""
    return ("Transposed", f'    Transposed = Table.Transpose({prev})')


def add_index(prev: str, column_name: str = "Index", start: int = 0) -> Tuple[str, str]:
    """Add an index column."""
    return ("AddedIndex",
            f'    AddedIndex = Table.AddIndexColumn({prev}, {_m_col(column_name)}, {start}, 1)')


def skip_rows(prev: str, count: int) -> Tuple[str, str]:
    """Skip first N rows."""
    return ("SkippedRows", f'    SkippedRows = Table.Skip({prev}, {count})')


def remove_top_rows(prev: str, count: int) -> Tuple[str, str]:
    """Remove first N rows."""
    return ("RemovedTopRows", f'    RemovedTopRows = Table.RemoveFirstN({prev}, {count})')


def remove_bottom_rows(prev: str, count: int) -> Tuple[str, str]:
    """Remove last N rows."""
    return ("RemovedBottomRows", f'    RemovedBottomRows = Table.RemoveLastN({prev}, {count})')


def promote_headers(prev: str) -> Tuple[str, str]:
    """Promote first row to headers."""
    return ("PromotedHeaders",
            f'    PromotedHeaders = Table.PromoteHeaders({prev}, [PromoteAllScalars=true])')


def demote_headers(prev: str) -> Tuple[str, str]:
    """Demote headers to first row."""
    return ("DemotedHeaders", f'    DemotedHeaders = Table.DemoteHeaders({prev})')


# ═══════════════════════════════════════════════════════════════════
# Calculated Columns
# ═══════════════════════════════════════════════════════════════════

def add_custom_column(prev: str, name: str, expression: str,
                      m_type: str = "type text") -> Tuple[str, str]:
    """Add a calculated column with a custom M expression."""
    return ("AddedCustom",
            f'    AddedCustom = Table.AddColumn({prev}, {_m_col(name)}, '
            f'each {expression}, {m_type})')


def add_conditional_column(prev: str, name: str,
                           conditions: List[Dict[str, str]],
                           else_value: str = "null") -> Tuple[str, str]:
    """
    Add a conditional column.
    conditions: [{column, operator, value, result}]
    """
    parts = []
    for cond in conditions:
        col = cond["column"]
        op = cond.get("operator", "=")
        val = cond["value"]
        result = cond["result"]
        if op == "=":
            parts.append(f'if [{col}] = "{val}" then "{result}"')
        elif op == ">":
            parts.append(f'if [{col}] > {val} then "{result}"')
        elif op == "<":
            parts.append(f'if [{col}] < {val} then "{result}"')
        elif op == "contains":
            parts.append(f'if Text.Contains([{col}], "{val}") then "{result}"')
        else:
            parts.append(f'if [{col}] {op} "{val}" then "{result}"')

    expr = " else ".join(parts) + f' else "{else_value}"'
    return ("AddedConditional",
            f'    AddedConditional = Table.AddColumn({prev}, {_m_col(name)}, each {expr})')


# ═══════════════════════════════════════════════════════════════════
# Step Injection Engine
# ═══════════════════════════════════════════════════════════════════

def inject_m_steps(m_query: str, steps: List[Tuple[str, str]]) -> str:
    """
    Inject transform steps into an existing M query.

    Takes a `let ... in FinalStep` query and inserts additional steps
    before the `in` clause.

    Args:
        m_query: Existing M query string
        steps: List of (step_name, step_code) tuples from transform functions

    Returns:
        Updated M query with injected steps
    """
    if not steps:
        return m_query

    lines = m_query.strip().split("\n")

    # Find the 'in' line
    in_index = None
    for i, line in enumerate(lines):
        stripped = line.strip().lower()
        if stripped == "in" or stripped.startswith("in "):
            in_index = i
            break

    if in_index is None:
        logger.warning("Could not find 'in' clause in M query; appending steps at end")
        return m_query

    # Build the new query
    pre_in = lines[:in_index]
    post_in = lines[in_index:]

    # Ensure last step before 'in' has a comma
    if pre_in and not pre_in[-1].rstrip().endswith(","):
        pre_in[-1] = pre_in[-1].rstrip() + ","

    # Add new steps
    for i, (step_name, step_code) in enumerate(steps):
        if i < len(steps) - 1:
            pre_in.append(step_code + ",")
        else:
            pre_in.append(step_code)

    # Update the 'in' clause to reference the last injected step
    last_step_name = steps[-1][0]
    post_in = ["in", f"    {last_step_name}"]

    return "\n".join(pre_in + post_in)


def build_m_query_with_transforms(base_query: str,
                                  transforms: List[Dict[str, Any]]) -> str:
    """
    Apply a list of transform definitions to an M query.

    transforms: list of dicts with 'type' and parameters, e.g.:
        {"type": "rename", "mapping": {"OldCol": "NewCol"}}
        {"type": "filter_values", "column": "Status", "values": ["Active"]}
        {"type": "group_by", "group_cols": ["Category"],
         "agg_specs": [{"column": "Amount", "agg": "sum", "alias": "Total"}]}
    """
    # Determine starting step name from query
    lines = base_query.strip().split("\n")
    current_step = "Source"
    for line in reversed(lines):
        stripped = line.strip()
        if stripped.startswith("in"):
            continue
        if "=" in stripped and not stripped.startswith("//"):
            current_step = stripped.split("=")[0].strip()
            break

    steps = []
    _DISPATCH = {
        "rename": lambda t, p: rename_columns(p, t["mapping"]),
        "remove": lambda t, p: remove_columns(p, t["columns"]),
        "select": lambda t, p: select_columns(p, t["columns"]),
        "duplicate": lambda t, p: duplicate_column(p, t["source"], t["new_name"]),
        "reorder": lambda t, p: reorder_columns(p, t["columns"]),
        "split": lambda t, p: split_column_by_delimiter(p, t["column"], t.get("delimiter", ",")),
        "merge": lambda t, p: merge_columns(p, t["columns"], t["new_name"], t.get("separator", " ")),
        "replace": lambda t, p: replace_values(p, t["column"], t["old_value"], t["new_value"]),
        "replace_nulls": lambda t, p: replace_nulls(p, t["column"], t["replacement"]),
        "trim": lambda t, p: trim_text(p, t["columns"]),
        "clean": lambda t, p: clean_text(p, t["columns"]),
        "upper": lambda t, p: upper_case(p, t["columns"]),
        "lower": lambda t, p: lower_case(p, t["columns"]),
        "proper": lambda t, p: proper_case(p, t["columns"]),
        "fill_down": lambda t, p: fill_down(p, t["columns"]),
        "fill_up": lambda t, p: fill_up(p, t["columns"]),
        "filter_values": lambda t, p: filter_values(p, t["column"], t["values"]),
        "exclude": lambda t, p: exclude_values(p, t["column"], t["values"]),
        "filter_range": lambda t, p: filter_range(p, t["column"], t.get("min"), t.get("max")),
        "filter_nulls": lambda t, p: filter_nulls(p, t["column"], t.get("keep_nulls", False)),
        "filter_contains": lambda t, p: filter_contains(p, t["column"], t["text"]),
        "distinct": lambda t, p: distinct_rows(p, t.get("columns")),
        "top_n": lambda t, p: top_n(p, t["column"], t["n"], t.get("ascending", False)),
        "group_by": lambda t, p: group_by(p, t["group_cols"], t["agg_specs"]),
        "unpivot": lambda t, p: unpivot(p, t["columns"], t.get("attribute", "Attribute"), t.get("value", "Value")),
        "unpivot_other": lambda t, p: unpivot_other(p, t["keep_columns"], t.get("attribute", "Attribute"), t.get("value", "Value")),
        "pivot": lambda t, p: pivot(p, t["attribute_col"], t["value_col"], t.get("agg", "sum")),
        "sort": lambda t, p: sort_rows(p, t["columns"]),
        "transpose": lambda t, p: transpose(p),
        "add_index": lambda t, p: add_index(p, t.get("name", "Index"), t.get("start", 0)),
        "skip_rows": lambda t, p: skip_rows(p, t["count"]),
        "remove_top_rows": lambda t, p: remove_top_rows(p, t["count"]),
        "remove_bottom_rows": lambda t, p: remove_bottom_rows(p, t["count"]),
        "promote_headers": lambda t, p: promote_headers(p),
        "demote_headers": lambda t, p: demote_headers(p),
        "add_custom_column": lambda t, p: add_custom_column(p, t["name"], t["expression"], t.get("type", "type text")),
        "add_conditional_column": lambda t, p: add_conditional_column(p, t["name"], t["conditions"], t.get("else_value", "null")),
    }

    for transform in transforms:
        ttype = transform.get("type", "")
        handler = _DISPATCH.get(ttype)
        if handler:
            try:
                step_name, step_code = handler(transform, current_step)
                steps.append((step_name, step_code))
                current_step = step_name
            except (KeyError, TypeError) as e:
                logger.warning(f"Skipping invalid transform '{ttype}': {e}")
        else:
            logger.warning(f"Unknown transform type: {ttype}")

    return inject_m_steps(base_query, steps)
