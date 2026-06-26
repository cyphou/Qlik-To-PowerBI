"""
TMDL (Tabular Model Definition Language) Generator

Converts extracted Qlik data directly into TMDL files
for the Power BI SemanticModel.

Handles:
- Physical tables with M query partitions
- DAX measures and calculated columns
- Relationships (manyToOne, manyToMany)
- Hierarchies, sets, groups, bins
- Parameter tables (What-If)
- Date table with time intelligence
- Geographic data categories
- RLS roles from source user filters

Generated structure:
  definition/
    database.tmdl
    model.tmdl
    relationships.tmdl
    expressions.tmdl
    roles.tmdl (if RLS)
    tables/
      {TableName}.tmdl
"""

import sys
import os
import re
import uuid
import json

# Add project root to sys.path for package imports
_project_root = os.path.join(os.path.dirname(__file__), '..')
if os.path.abspath(_project_root) not in [os.path.abspath(p) for p in sys.path]:
    sys.path.insert(0, os.path.abspath(_project_root))

from qlik_export.datasource_extractor import (
    generate_power_query_m,
    convert_formula_to_dax,
    map_to_powerbi_type
)
from qlik_export.qlik_model_converter import (
    RelationshipCardinality,
    CrossFilterDirection,
)
from qlik_export.m_query_builder import (
    inject_m_steps,
    m_transform_rename,
    m_transform_remove_columns,
    m_transform_filter_values,
    m_transform_filter_nulls,
    m_transform_add_column,
)


# ════════════════════════════════════════════════════════════════════
#  SOURCE DERIVATION PREFIX CLEANING
#  Secondary defense against source internal field names leaking
# ════════════════════════════════════════════════════════════════════

_RE_TMDL_DERIVATION_PREFIX = re.compile(
    r'^(none|sum|avg|count|min|max|usr|yr|mn|dy|qr|wk|attr|md|mdy|hms|hr|mt|sc|thr|trunc|tyr|tqr|tmn|tdy|twk):'
)
_RE_TMDL_TYPE_SUFFIX = re.compile(r':(nk|qk|ok|fn|tn)$')


def _clean_field_ref(raw):
    """Strip source derivation prefixes and type suffixes from a field name.

    Defensive secondary filter applied in the TMDL generator to catch any
    source-internal names that leaked through extraction.
    """
    clean = _RE_TMDL_DERIVATION_PREFIX.sub('', raw)
    return _RE_TMDL_TYPE_SUFFIX.sub('', clean)


# ════════════════════════════════════════════════════════════════════
#  DAX → POWER QUERY M EXPRESSION CONVERTER
#  Eliminates DAX calculated columns in favour of M Table.AddColumn
# ════════════════════════════════════════════════════════════════════

# M type strings matching DAX/BIM dataType values
_DAX_TO_M_TYPE = {
    'Boolean': 'type logical', 'boolean': 'type logical',
    'String': 'type text', 'string': 'type text',
    'Double': 'type number', 'double': 'type number',
    'Int64': 'Int64.Type', 'int64': 'Int64.Type',
    'DateTime': 'type datetime', 'dateTime': 'type datetime',
    'Decimal': 'type number', 'decimal': 'type number',
}


def _inject_column_types_step(m_query: str, columns: list) -> str:
    """Inject a Table.TransformColumnTypes step into the M query.

    CSV sources load all columns as text.  This adds an explicit type
    conversion step so that numeric / date columns are properly typed
    before the DAX engine evaluates measures like ``SUM()``.
    """
    if not columns or not m_query:
        return m_query

    # Build type pairs for non-string columns
    type_pairs = []
    for col in columns:
        col_name = col.get('name', '')
        col_type = col.get('datatype', 'string')
        m_type = _DAX_TO_M_TYPE.get(col_type)
        if m_type and m_type != 'type text' and col_name:
            type_pairs.append(f'{{"{col_name}", {m_type}}}')

    if not type_pairs:
        return m_query  # all columns are text, nothing to do

    # Find the last step name and the 'in' clause to inject before it
    lines = m_query.strip().split('\n')
    in_index = None
    for i, line in enumerate(lines):
        stripped = line.strip().lower()
        if stripped == 'in' or stripped.startswith('in '):
            in_index = i
            break

    if in_index is None:
        return m_query  # malformed query, skip

    # Determine the previous step name (what the 'in' references)
    pre_in = lines[:in_index]
    prev_step = 'Source'
    for line in reversed(pre_in):
        stripped = line.strip().rstrip(',')
        if '=' in stripped and not stripped.startswith('//'):
            prev_step = stripped.split('=')[0].strip()
            break

    # Ensure last line before 'in' ends with comma
    if pre_in and not pre_in[-1].rstrip().endswith(','):
        pre_in[-1] = pre_in[-1].rstrip() + ','

    # Build the step
    pairs_str = ', '.join(type_pairs)
    type_step = f'    #"Changed Type" = Table.TransformColumnTypes({prev_step}, {{{pairs_str}}})'
    pre_in.append(type_step)

    # Update 'in' to reference the new last step
    rest = lines[in_index:]
    rest[0] = 'in'
    if len(rest) > 1:
        rest[1] = '    #"Changed Type"'
    else:
        rest.append('    #"Changed Type"')

    return '\n'.join(pre_in + rest)


def _split_dax_args(s):
    """Split a string at top-level commas, respecting parentheses and quotes."""
    parts, depth, current, in_str = [], 0, [], False
    for ch in s:
        if in_str:
            current.append(ch)
            if ch == '"':
                in_str = False
        elif ch == '"':
            current.append(ch)
            in_str = True
        elif ch == '(':
            depth += 1
            current.append(ch)
        elif ch == ')':
            depth -= 1
            current.append(ch)
        elif ch == ',' and depth == 0:
            parts.append(''.join(current).strip())
            current = []
        else:
            current.append(ch)
    parts.append(''.join(current).strip())
    return parts


def _extract_function_body(expr, func_name):
    """Extract the content between balanced parens for a named DAX function.

    Only matches if the function call spans the entire expression.
    Returns the inner content string, or None.
    """
    pattern = re.compile(r'^' + re.escape(func_name) + r'\s*\(', re.IGNORECASE)
    m = pattern.match(expr)
    if not m:
        return None
    start = m.end() - 1  # opening '('
    depth, in_str = 0, False
    for i in range(start, len(expr)):
        ch = expr[i]
        if in_str:
            if ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
            if depth == 0:
                if expr[i + 1:].strip() == '':
                    return expr[start + 1:i]
                return None  # function doesn't span full expression
    return None


def _dax_to_m_expression(dax_expr, table_name=''):
    """Convert a DAX calculated-column expression to Power Query M.

    Handles IF, SWITCH, FLOOR, ISBLANK, IN {}, string/date/math functions,
    simple arithmetic, column references, and boolean operators.

    Returns the M expression string on success, or *None* if the expression
    contains cross-table references or DAX constructs with no M equivalent
    (RELATED, LOOKUPVALUE, CALCULATE, etc.).
    """
    if not dax_expr:
        return dax_expr
    expr = dax_expr.strip()
    if not expr:
        return expr

    # ── Reject unconvertible patterns ───────────────────────────────
    upper = expr.upper()
    if 'RELATED(' in upper or 'LOOKUPVALUE(' in upper:
        return None

    # Remove self-table qualifications: 'TableName'[Col] → [Col]
    if table_name:
        expr = re.sub(r"'" + re.escape(table_name) + r"'\[", '[', expr)
    # Any remaining cross-table refs → bail
    if re.search(r"'[^']+'\[", expr):
        return None

    # ── IF(cond, true_val [, false_val]) ────────────────────────────
    body = _extract_function_body(expr, 'IF')
    if body is not None:
        args = _split_dax_args(body)
        if len(args) >= 2:
            cond = _dax_to_m_expression(args[0], table_name)
            true_v = _dax_to_m_expression(args[1], table_name)
            false_v = _dax_to_m_expression(args[2], table_name) if len(args) >= 3 else 'null'
            if cond is not None and true_v is not None and false_v is not None:
                return f'if {cond} then {true_v} else {false_v}'
        return None

    # ── SWITCH(expr, v1, r1, …, default) ────────────────────────────
    body = _extract_function_body(expr, 'SWITCH')
    if body is not None:
        args = _split_dax_args(body)
        if len(args) >= 3:
            sw = _dax_to_m_expression(args[0], table_name)
            if sw is None:
                return None
            parts = []
            i = 1
            while i + 1 < len(args):
                v = _dax_to_m_expression(args[i], table_name)
                r = _dax_to_m_expression(args[i + 1], table_name)
                if v is None or r is None:
                    return None
                parts.append(f'if {sw} = {v} then {r}')
                i += 2
            default_v = (_dax_to_m_expression(args[-1], table_name)
                         if len(args) % 2 == 0 else '"Other"')
            if default_v is None:
                return None
            return ' else '.join(parts) + f' else {default_v}'
        return None

    # ── FLOOR(x, n) → Number.RoundDown(x / n) * n ──────────────────
    body = _extract_function_body(expr, 'FLOOR')
    if body is not None:
        args = _split_dax_args(body)
        if len(args) == 2:
            x = _dax_to_m_expression(args[0], table_name)
            if x is None:
                return None
            n = args[1].strip()
            return f'Number.RoundDown({x} / {n}) * {n}'
        return None

    # ── ISBLANK(x) → (x = null) ────────────────────────────────────
    body = _extract_function_body(expr, 'ISBLANK')
    if body is not None:
        inner = _dax_to_m_expression(body, table_name)
        return f'({inner} = null)' if inner is not None else None

    # ── NOT(x) → not x ─────────────────────────────────────────────
    body = _extract_function_body(expr, 'NOT')
    if body is not None:
        inner = _dax_to_m_expression(body, table_name)
        return f'not ({inner})' if inner is not None else None

    # ── Single-argument DAX → M function map ────────────────────────
    _SINGLE = [
        ('UPPER', 'Text.Upper'), ('LOWER', 'Text.Lower'),
        ('TRIM', 'Text.Trim'), ('LEN', 'Text.Length'),
        ('YEAR', 'Date.Year'), ('MONTH', 'Date.Month'),
        ('DAY', 'Date.Day'), ('QUARTER', 'Date.QuarterOfYear'),
        ('ABS', 'Number.Abs'), ('INT', 'Number.RoundDown'),
        ('SQRT', 'Number.Sqrt'),
    ]
    for dax_fn, m_fn in _SINGLE:
        body = _extract_function_body(expr, dax_fn)
        if body is not None:
            inner = _dax_to_m_expression(body, table_name)
            return f'{m_fn}({inner})' if inner is not None else None

    # ── Multi-argument DAX → M function map ─────────────────────────
    _MULTI = [
        ('LEFT', 'Text.Start'), ('RIGHT', 'Text.End'),
        ('MID', 'Text.Middle'), ('ROUND', 'Number.Round'),
        ('CONTAINSSTRING', 'Text.Contains'),
        ('SUBSTITUTE', 'Text.Replace'),
    ]
    for dax_fn, m_fn in _MULTI:
        body = _extract_function_body(expr, dax_fn)
        if body is not None:
            args = _split_dax_args(body)
            converted = [_dax_to_m_expression(a, table_name) for a in args]
            if any(c is None for c in converted):
                return None
            return f'{m_fn}({", ".join(converted)})'

    # ── [expr] IN {val1, val2, …} → List.Contains({…}, expr) ───────
    in_match = re.match(r'^(.+?)\s+IN\s+(\{.+\})\s*$', expr, re.IGNORECASE)
    if in_match:
        col_m = _dax_to_m_expression(in_match.group(1), table_name)
        if col_m is not None:
            return f'List.Contains({in_match.group(2)}, {col_m})'
        return None

    # ── Leaf expression (literals, column refs, operators) ──────────
    result = expr
    result = result.replace('&&', ' and ').replace('||', ' or ')
    result = re.sub(r'\bTRUE\s*\(\s*\)', 'true', result, flags=re.IGNORECASE)
    result = re.sub(r'\bFALSE\s*\(\s*\)', 'false', result, flags=re.IGNORECASE)
    result = re.sub(r'\bBLANK\s*\(\s*\)', 'null', result, flags=re.IGNORECASE)

    # Remaining DAX function calls → not convertible
    if re.search(r'\b[A-Z_]{2,}\s*\(', result):
        return None
    return result


def _inject_m_steps_into_partition(table, steps):
    """Inject M transformation steps into a table's M partition."""
    if not steps:
        return False
    for partition in table.get('partitions', []):
        source = partition.get('source', {})
        if source.get('type') == 'm' and source.get('expression'):
            source['expression'] = inject_m_steps(source['expression'], steps)
            return True
    return False


def resolve_table_for_column(column_name, datasource_name=None, dax_context=None):
    """Resolve which table a column belongs to, with optional datasource scoping.

    When a worksheet uses multiple datasources, ``datasource_name`` narrows
    the lookup to the tables that belong to that particular datasource.
    Falls back to the global ``column_table_map`` if no datasource-specific
    match is found.

    Args:
        column_name: Column name to resolve.
        datasource_name: Optional datasource name to scope the lookup.
        dax_context: DAX context dict containing ``column_table_map`` and
            ``ds_column_table_map``.

    Returns:
        str or None: Resolved table name, or *None* if unresolved.
    """
    if not dax_context:
        return None
    # Try datasource-specific lookup first
    if datasource_name:
        ds_map = dax_context.get('ds_column_table_map', {}).get(datasource_name, {})
        if column_name in ds_map:
            return ds_map[column_name]
    # Fallback to global map
    return dax_context.get('column_table_map', {}).get(column_name)


# ════════════════════════════════════════════════════════════════════
#  PUBLIC ENTRY POINT
# ════════════════════════════════════════════════════════════════════

def generate_tmdl(datasources, report_name, extra_objects, output_dir,
                  calendar_start=None, calendar_end=None, culture=None,
                  model_mode='import'):
    """
    Main entry point: directly convert extracted source data to TMDL files.

    Args:
        datasources: List of datasources with connections, tables, calculations
        report_name: Name of the report
        extra_objects: Dict with hierarchies, sets, groups, bins, aliases,
                       parameters, user_filters, _datasources
        output_dir: Path to the SemanticModel folder
        calendar_start: Start year for Calendar table (default: 2020)
        calendar_end: End year for Calendar table (default: 2030)
        culture: Override culture/locale (default: en-US)
        model_mode: 'import', 'directquery', or 'composite'
                    Controls partition mode for all tables

    Returns:
        dict: Statistics about the generated model
    """
    if extra_objects is None:
        extra_objects = {}

    # Step 1: Build the semantic model
    model = _build_semantic_model(datasources, report_name, extra_objects,
                                  calendar_start=calendar_start,
                                  calendar_end=calendar_end,
                                  culture=culture,
                                  model_mode=model_mode)

    # Step 2: Write TMDL files
    _write_tmdl_files(model, output_dir)

    # Step 3: Compute and return stats
    tables = model.get('model', {}).get('tables', [])
    rels = model.get('model', {}).get('relationships', [])
    stats = {
        'tables': len(tables),
        'columns': sum(len(t.get('columns', [])) for t in tables),
        'measures': sum(len(t.get('measures', [])) for t in tables),
        'relationships': len(rels),
        'hierarchies': sum(len(t.get('hierarchies', [])) for t in tables),
        'roles': len(model.get('model', {}).get('roles', [])),
        'relationship_report': model.get('_relationship_report', {}),
        'measure_renames': model.get('_measure_renames', {}),
    }
    return stats


# ════════════════════════════════════════════════════════════════════
#  SEMANTIC MODEL BUILDING
# ════════════════════════════════════════════════════════════════════

def _build_semantic_model(datasources, report_name="Report", extra_objects=None,
                          calendar_start=None, calendar_end=None, culture=None,
                          model_mode='import'):
    """
    Build a complete semantic model from extracted datasources.

    Produces tables, partitions with M queries, DAX measures, calculated
    columns, relationships, hierarchies, sets/groups/bins, parameters,
    date table, geographic data categories, hidden columns, and RLS roles.

    Args:
        datasources: List of datasources with connections, tables, calculations
        report_name: Report name
        extra_objects: Optional dict with hierarchies, sets, groups, bins, aliases
        calendar_start: Start year for Calendar table (default: 2020)
        calendar_end: End year for Calendar table (default: 2030)
        culture: Override culture/locale (default: en-US)
        model_mode: 'import', 'directquery', or 'composite'
        culture: Override culture/locale (default: en-US)

    Returns:
        dict: Complete semantic model
    """
    if extra_objects is None:
        extra_objects = {}

    effective_culture = culture or "en-US"

    model = {
        "name": report_name,
        "compatibilityLevel": 1550,
        "model": {
            "culture": effective_culture,
            "defaultPowerBIDataSourceVersion": "powerBI_V3",
            "tables": [],
            "relationships": [],
            "roles": []
        }
    }

    # Store calendar options for _add_date_table
    model['_calendar_start'] = calendar_start
    model['_calendar_end'] = calendar_end

    # Store model mode for partition generation
    model['_model_mode'] = model_mode or 'import'

    # Store raw datasources for M parameter generation (server/database)
    model['_datasources'] = datasources

    # Phase 1: Collect all physical tables and deduplicate
    best_tables = {}  # name -> (table_dict, connection_details)
    m_query_overrides = {}  # table_name -> complete M query (from Prep flows)
    all_calculations = []
    all_columns_metadata = []
    all_hierarchies = []
    all_sets = []
    all_groups = []
    all_bins = []

    for ds in datasources:
        ds_connection = ds.get('connection', {})
        connection_map = ds.get('connection_map', {})
        calculations = ds.get('calculations', [])
        all_calculations.extend(calculations)

        # Collect column metadata
        ds_columns = ds.get('columns', [])
        all_columns_metadata.extend(ds_columns)

        # Extract physical columns from datasource-level list (excluding calculations)
        ds_physical_cols = [c for c in ds_columns if not c.get('calculation')]

        tables = ds.get('tables', [])
        for table in tables:
            table_name = table.get('name', 'Table1')

            # Skip tables without a name
            if not table_name or table_name == 'Unknown':
                continue

            # Inherit datasource-level columns into tables that have none
            # (common for Extracts: single table with columns at DS level)
            if not table.get('columns') and ds_physical_cols and len(tables) == 1:
                # Clean DS-level columns: strip bracket notation and skip special columns
                cleaned_cols = []
                for c in ds_physical_cols:
                    raw = c.get('name', '')
                    if raw.startswith('[:') or not raw:
                        continue  # Skip special columns (e.g. [:Measure Names])
                    clean = dict(c)
                    clean['name'] = raw.strip('[]')
                    cleaned_cols.append(clean)
                table['columns'] = cleaned_cols

            col_count = len(table.get('columns', []))

            # Resolve per-table connection
            table_conn = table.get('connection_details', {})
            if not table_conn:
                conn_ref = table.get('connection', '')
                table_conn = connection_map.get(conn_ref, ds_connection)

            # Deduplicate: keep the version with the most columns
            if table_name not in best_tables or col_count > len(best_tables[table_name][0].get('columns', [])):
                best_tables[table_name] = (table, table_conn)

        # Collect Prep flow M query overrides
        ds_m_overrides = ds.get('m_query_overrides', {})
        for tname, mq in ds_m_overrides.items():
            m_query_overrides[tname] = mq
        # Single-table override (from prep_flow_parser output)
        single_override = ds.get('m_query_override', '')
        if single_override:
            for table in ds.get('tables', []):
                m_query_overrides[table.get('name', '')] = single_override

    # Phase 2: Identify the main table (the one with the most columns = fact table)
    main_table_name = None
    max_cols = -1
    for tname, (table, conn) in best_tables.items():
        ncols = len(table.get('columns', []))
        if ncols > max_cols:
            max_cols = ncols
            main_table_name = tname

    # Phase 2a: Build column metadata mapping
    col_metadata_map = {}
    for cm in all_columns_metadata:
        raw = cm.get('name', '').replace('[', '').replace(']', '')
        caption = cm.get('caption', raw)
        key = caption if caption else raw
        col_metadata_map[key] = cm
        col_metadata_map[raw] = cm

    # Phase 2b: Build context mappings for DAX conversion
    calc_map = {}
    for calc in all_calculations:
        raw = calc.get('name', '').replace('[', '').replace(']', '')
        caption = calc.get('caption', raw)
        if raw and raw != caption:
            calc_map[raw] = caption

    # param_map: "Parameter X" -> parameter caption
    param_map = {}
    # Source 1: From "Parameters" datasource calculations (old format)
    for ds in datasources:
        if ds.get('name', '') == 'Parameters':
            for calc in ds.get('calculations', []):
                raw = calc.get('name', '').replace('[', '').replace(']', '')
                caption = calc.get('caption', raw)
                if raw:
                    param_map[raw] = caption
    # Source 2: From extracted parameters (new format)
    for param in extra_objects.get('parameters', []):
        raw_name = param.get('name', '')
        caption = param.get('caption', '')
        if raw_name and caption:
            match = re.match(r'\[Parameters\]\.\[([^\]]+)\]', raw_name)
            if match:
                param_map[match.group(1)] = caption
            else:
                clean = raw_name.replace('[', '').replace(']', '')
                if clean and clean not in param_map:
                    param_map[clean] = caption

    # column_table_map: column_name -> table_name
    column_table_map = {}
    for tname, (table, conn) in best_tables.items():
        for col in table.get('columns', []):
            cname = col.get('name', '')
            if cname and cname not in column_table_map:
                column_table_map[cname] = tname

    # measure_names: set of all measure names (captions)
    measure_names = set()
    for calc in all_calculations:
        caption = calc.get('caption', calc.get('name', '').replace('[', '').replace(']', ''))
        if caption:
            measure_names.add(caption)
    measure_names.update(param_map.values())

    # param_values: {caption: literal_value} for inlining in calculated columns
    param_values = {}
    for calc in all_calculations:
        caption = calc.get('caption', calc.get('name', '').replace('[', '').replace(']', ''))
        formula = calc.get('formula', '').strip()
        if caption and formula and '[' not in formula:
            param_values[caption] = formula
    for param in extra_objects.get('parameters', []):
        caption = param.get('caption', '')
        value = param.get('value', '').strip('"')
        if caption and value and caption not in param_values:
            datatype = param.get('datatype', 'string')
            if datatype == 'string':
                param_values[caption] = f'"{value}"'
            elif datatype in ('date', 'datetime'):
                # Convert #YYYY-MM-DD# date literal to DAX DATE()
                date_m = re.match(r'#(\d{4})-(\d{2})-(\d{2})#', value)
                if date_m:
                    param_values[caption] = f'DATE({int(date_m.group(1))}, {int(date_m.group(2))}, {int(date_m.group(3))})'
                else:
                    param_values[caption] = value
            else:
                param_values[caption] = value

    # Also add parameter measure names
    for param in extra_objects.get('parameters', []):
        caption = param.get('caption', '')
        if caption:
            measure_names.add(caption)

    # Phase 2c: Build per-datasource column → table map for multi-source routing
    # Maps datasource_name → {column_name → table_name}
    ds_column_table_map = {}
    datasource_table_map = {}  # table_name → datasource_name
    for ds in datasources:
        ds_name = ds.get('name', '')
        ds_col_map = {}
        for table in ds.get('tables', []):
            tname = table.get('name', 'Table1')
            if tname in best_tables:
                datasource_table_map[tname] = ds_name
                for col in table.get('columns', []):
                    cname = col.get('name', '')
                    if cname:
                        ds_col_map[cname] = tname
        if ds_name:
            ds_column_table_map[ds_name] = ds_col_map

    dax_context = {
        'calc_map': calc_map,
        'param_map': param_map,
        'column_table_map': column_table_map,
        'measure_names': measure_names,
        'param_values': param_values,
        'ds_column_table_map': ds_column_table_map,
        'datasource_table_map': datasource_table_map,
    }

    # Phase 3: Create tables
    # Build reverse map: datasource_name → best table name within that datasource
    ds_main_table = {}  # datasource_name → table_name (the table with the most columns in that DS)
    for tname, ds_name in datasource_table_map.items():
        if ds_name not in ds_main_table:
            ds_main_table[ds_name] = tname
        else:
            # Pick the table with more columns within the same datasource
            existing = ds_main_table[ds_name]
            existing_cols = len(best_tables.get(existing, ({}, {}))[0].get('columns', []))
            current_cols = len(best_tables.get(tname, ({}, {}))[0].get('columns', []))
            if current_cols > existing_cols:
                ds_main_table[ds_name] = tname

    for table_name, (table, table_conn) in best_tables.items():
        # Route calculations to their source datasource's main table
        ds_for_table = datasource_table_map.get(table_name)
        if ds_for_table and ds_main_table.get(ds_for_table) == table_name:
            # This table is the main table for its datasource — give it that DS's calcs
            table_calculations = [
                c for c in all_calculations
                if c.get('datasource_name', '') == ds_for_table
            ]
            # Also add calcs with no datasource_name (legacy) if this is the global main table
            if table_name == main_table_name:
                table_calculations += [
                    c for c in all_calculations
                    if not c.get('datasource_name')
                ]
        elif table_name == main_table_name:
            # Fallback: calcs with no datasource match go to the global main table
            routed_ds_names = set(ds_main_table.values())
            table_calculations = [
                c for c in all_calculations
                if c.get('datasource_name', '') not in datasource_table_map.values()
                or not c.get('datasource_name')
            ]
        else:
            table_calculations = []

        tbl = _build_table(
            table=table,
            connection=table_conn,
            calculations=table_calculations,
            columns_metadata=[],
            dax_context=dax_context,
            col_metadata_map=col_metadata_map,
            extra_objects=extra_objects,
            m_query_override=m_query_overrides.get(table_name, ''),
            model_mode=model.get('_model_mode', 'import'),
        )
        model["model"]["tables"].append(tbl)

    # Phase 4: Create relationships (with cross-datasource deduplication)
    seen_rels = set()
    for ds in datasources:
        relationships = ds.get('relationships', [])
        rels = _build_relationships(relationships)
        for rel in rels:
            key = (rel.get('fromTable'), rel.get('fromColumn'),
                   rel.get('toTable'), rel.get('toColumn'))
            if key not in seen_rels:
                seen_rels.add(key)
                model["model"]["relationships"].append(rel)
            else:
                print(f"  ⚠ Skipped duplicate relationship: {key[0]}.{key[1]} → {key[2]}.{key[3]}")

    # Validate relationships: keep only those pointing to existing tables/columns
    valid_relationships = []
    table_columns = {}
    for table in model["model"]["tables"]:
        tname = table.get("name", "")
        table_columns[tname] = {col.get("name", "") for col in table.get("columns", [])}

    for rel in model["model"]["relationships"]:
        from_table = rel.get("fromTable", "")
        to_table = rel.get("toTable", "")
        from_col = rel.get("fromColumn", "")
        to_col = rel.get("toColumn", "")

        if (from_table in table_columns and to_table in table_columns
                and from_col in table_columns[from_table]
                and to_col in table_columns[to_table]
                and from_table != to_table):
            valid_relationships.append(rel)
        else:
            reasons = []
            if from_table not in table_columns:
                reasons.append(f"fromTable '{from_table}' not found")
            elif from_col not in table_columns.get(from_table, set()):
                reasons.append(f"fromColumn '{from_col}' not in '{from_table}'")
            if to_table not in table_columns:
                reasons.append(f"toTable '{to_table}' not found")
            elif to_col not in table_columns.get(to_table, set()):
                reasons.append(f"toColumn '{to_col}' not in '{to_table}'")
            if from_table == to_table:
                reasons.append("self-join")
            print(f"  ⚠ Dropped relationship: {from_table}.{from_col} → {to_table}.{to_col} ({'; '.join(reasons)})")

    model["model"]["relationships"] = valid_relationships

    # Phase 4b: Fix type mismatches in relationship keys
    _fix_relationship_type_mismatches(model)

    # Phase 5: Add sets, groups, bins as calculated columns
    _process_sets_groups_bins(model, extra_objects, main_table_name, column_table_map)

    # Phase 6: Automatic date table if date columns detected
    has_date_columns = False
    for table in model["model"]["tables"]:
        for col in table.get("columns", []):
            if col.get("dataType") == "DateTime" or col.get("dataCategory") == "DateTime":
                has_date_columns = True
                break
        if has_date_columns:
            break
    if has_date_columns:
        _add_date_table(model)

    # Phase 7: Hierarchies from drill-paths
    _apply_hierarchies(model, extra_objects.get('hierarchies', []), column_table_map)

    # Phase 7b: Auto-generate date hierarchies for DateTime columns without one
    _auto_date_hierarchies(model)

    # Phase 8: Parameter tables (What-If parameters)
    _create_parameter_tables(model, extra_objects.get('parameters', []), main_table_name)

    # Phase 8b: Calculation groups (measure-switching parameters)
    _create_calculation_groups(model, extra_objects.get('parameters', []), main_table_name)

    # Phase 8c: Field parameters (dimension-switching parameters with NAMEOF)
    _create_field_parameters(model, extra_objects.get('parameters', []),
                             main_table_name, column_table_map)

    # Phase 9: RLS roles from user filters / security
    _create_rls_roles(model, extra_objects.get('user_filters', []),
                      main_table_name, column_table_map)

    # Phase 9b: Auto-generate measures for quick table calculations (% of total, running sum, etc.)
    _create_quick_table_calc_measures(model, extra_objects.get('worksheets', []),
                                      main_table_name, column_table_map)

    # Phase 10: Infer missing relationships from cross-table DAX references
    _infer_cross_table_relationships(model)

    # Phase 10b: Detect cardinality (runs AFTER Phase 10 so inferred rels are included)
    _detect_many_to_many(model, datasources)

    # Phase 10d: Generate bridge tables for manyToMany relationships (opt-in)
    bridge_mode = extra_objects.get('_bridge_tables', 'none')
    if bridge_mode == 'auto':
        n_bridges = _generate_bridge_tables(model)
        if n_bridges:
            print(f"  ✓ Generated {n_bridges} bridge table(s) to replace manyToMany")
            # Validate bridge tables
            bridge_issues = _validate_bridge_tables(model)
            if bridge_issues:
                for issue in bridge_issues:
                    print(f"  ⚠ Bridge validation: {issue}")
            else:
                print(f"  ✓ Bridge table validation passed")

    # Phase 10c: Replace RELATED() with LOOKUPVALUE() for manyToMany
    _fix_related_for_many_to_many(model)

    # Phase 10e: Optimize cross-filter direction (Phase 3)
    n_downgraded = _optimize_cross_filter_direction(model)
    if n_downgraded:
        print(f"  ✓ Optimized {n_downgraded} relationship(s): "
              f"bothDirections → oneDirection")

    # Phase 11: Deactivate relationships that create ambiguous paths
    _deactivate_ambiguous_paths(model)

    # Phase 11b: Validate relationships and produce health report (Phase 4)
    rel_report = _validate_relationships(model)
    model['_relationship_report'] = rel_report

    # Deduplicate measures globally
    global_measure_names = set()
    for table in model["model"]["tables"]:
        unique_measures = []
        for measure in table.get("measures", []):
            mname = measure.get("name", "")
            if mname not in global_measure_names:
                global_measure_names.add(mname)
                unique_measures.append(measure)
        table["measures"] = unique_measures

    # Phase 11c: Resolve measure/column name collisions
    # Power BI forbids a measure and a column sharing a name in the model.
    n_renamed = _resolve_measure_column_collisions(model)
    if n_renamed:
        print(f"  ✓ Renamed {n_renamed} measure(s) to avoid column-name collisions")

    # Phase 12: Auto-generate perspectives from table list
    all_table_names = [t.get('name', '') for t in model["model"]["tables"]]
    model["model"]["perspectives"] = [{
        "name": "Full Model",
        "tables": all_table_names
    }]

    return model


def _resolve_measure_column_collisions(model):
    """Rename measures that collide with a column name anywhere in the model.

    Power BI forbids a measure and a column sharing the same name. When a
    master measure (e.g. ``Sales = SUM('Orders'[Sales])``) duplicates a
    physical column name, the project fails to load with
    "The '<name>' measure cannot be created because a column with the same
    name already exists." This pass renames the offending measure and rewrites
    every unqualified ``[OldName]`` reference across all measure expressions.

    Returns:
        int: number of measures renamed.
    """
    tables = model.get("model", {}).get("tables", [])

    # Column names across the whole model (case-insensitive — Power BI is
    # case-insensitive for identifier collisions).
    all_columns_ci = set()
    for t in tables:
        for c in t.get("columns", []):
            cn = c.get("name", "")
            if cn:
                all_columns_ci.add(cn.lower())

    # Measure names across the whole model (case-insensitive).
    all_measures_ci = set()
    for t in tables:
        for m in t.get("measures", []):
            mn = m.get("name", "")
            if mn:
                all_measures_ci.add(mn.lower())

    rename_map = {}  # old_name -> new_name
    for t in tables:
        for m in t.get("measures", []):
            mname = m.get("name", "")
            if not mname or mname.lower() not in all_columns_ci:
                continue
            # Pick a non-colliding alternative name.
            new_name = None
            for cand in (f"Total {mname}", f"{mname} Measure",
                         f"{mname} Value", f"{mname} (Measure)"):
                if (cand.lower() not in all_columns_ci
                        and cand.lower() not in all_measures_ci):
                    new_name = cand
                    break
            if new_name is None:
                new_name = f"{mname} Measure"
                i = 2
                while (new_name.lower() in all_columns_ci
                       or new_name.lower() in all_measures_ci):
                    new_name = f"{mname} Measure {i}"
                    i += 1
            rename_map[mname] = new_name
            all_measures_ci.discard(mname.lower())
            all_measures_ci.add(new_name.lower())
            m["name"] = new_name

    # Expose the rename map so the report generator can update visual
    # bindings that still reference the original (pre-rename) measure names.
    model['_measure_renames'] = dict(rename_map)

    if not rename_map:
        return 0

    # Rewrite unqualified [OldName] measure references in all measure
    # expressions. Qualified column refs like 'Orders'[Sales] are preceded by
    # a quote and therefore excluded by the negative lookbehind.
    def _rewrite(expr):
        for old, new in rename_map.items():
            pattern = r"(?<![\w'])\[" + re.escape(old) + r"\]"
            expr = re.sub(pattern, f"[{new}]", expr)
        return expr

    for t in tables:
        for m in t.get("measures", []):
            if m.get("expression"):
                m["expression"] = _rewrite(m["expression"])

    return len(rename_map)


def _build_m_transform_steps(columns, col_metadata_map):
    """
    Build M transformation steps from TWB-embedded column metadata.

    Detects:
    - Column renames: caption ≠ raw name → Table.RenameColumns
    - Hidden columns: hidden=true → Table.RemoveColumns (at query level)

    Args:
        columns: list of column dicts from the table
        col_metadata_map: dict {col_name: {caption, hidden, ...}}

    Returns:
        list of (step_name, step_expression) tuples for inject_m_steps()
    """
    steps = []

    # 1. Collect column renames from caption metadata
    renames = {}
    for col in columns:
        col_name = col.get('name', '')
        meta = col_metadata_map.get(col_name, {})
        caption = meta.get('caption', '')
        # Clean bracket notation: [col_name] → col_name
        clean_name = col_name.strip('[]')
        if caption and caption != clean_name and caption != col_name:
            renames[clean_name] = caption

    if renames:
        steps.append(m_transform_rename(renames))

    return steps


def _build_table(table, connection, calculations, columns_metadata, dax_context=None,
                 col_metadata_map=None, extra_objects=None, m_query_override='',
                 model_mode='import'):
    """
    Create a semantic model table with columns, partitions and measures.

    Args:
        table: Dict with name, columns
        connection: Dict with type and connection details
        calculations: List of calculations
        columns_metadata: List of column metadata
        dax_context: Dict with calc_map, param_map, column_table_map, measure_names
        col_metadata_map: Dict {col_name: {hidden, semantic_role, description, ...}}
        extra_objects: Dict with sets, groups, bins, aliases
        model_mode: 'import', 'directquery', or 'composite'

    Returns:
        dict: Complete table definition
    """
    if dax_context is None:
        dax_context = {}
    if col_metadata_map is None:
        col_metadata_map = {}
    if extra_objects is None:
        extra_objects = {}

    table_name = table.get('name', 'Table1')
    columns = table.get('columns', [])

    # Generate M query: use Prep flow override if available, else generate from connection
    if m_query_override:
        m_query = m_query_override
    else:
        m_query = generate_power_query_m(connection, table)

    # Inject TWB-embedded transformation steps from column metadata
    m_steps = _build_m_transform_steps(columns, col_metadata_map)
    if m_steps:
        m_query = inject_m_steps(m_query, m_steps)

    # Inject Table.TransformColumnTypes for non-string columns
    # CSV/text sources load everything as text; explicit typing is required
    m_query = _inject_column_types_step(m_query, columns)

    # Determine partition mode based on model_mode
    # For composite: large tables use directQuery, small/lookup use import
    partition_mode = model_mode if model_mode in ('import', 'directQuery') else 'import'
    if model_mode == 'composite':
        # Heuristic: tables with many columns are likely fact tables → directQuery
        # Small tables with few columns are likely dimension/lookup → import
        col_count = len(columns)
        if col_count > 10:
            partition_mode = 'directQuery'
        else:
            partition_mode = 'import'

    result_table = {
        "name": table_name,
        "columns": [],
        "partitions": [
            {
                "name": f"Partition-{table_name}",
                "mode": partition_mode,
                "source": {
                    "type": "m",
                    "expression": m_query
                }
            }
        ],
        "measures": []
    }

    # Track column names (avoid duplicates within the table)
    column_name_counts = {}

    # Add columns
    for col in columns:
        original_col_name = col.get('name', 'Column')

        # Handle duplicate column names by adding a suffix
        if original_col_name in column_name_counts:
            column_name_counts[original_col_name] += 1
            unique_col_name = f"{original_col_name}_{column_name_counts[original_col_name]}"
        else:
            column_name_counts[original_col_name] = 0
            unique_col_name = original_col_name

        bim_column = {
            "name": unique_col_name,
            "dataType": map_to_powerbi_type(col.get('datatype', 'string')),
            "sourceColumn": col.get('name', 'Column'),
            "summarizeBy": "none"
        }

        # Apply metadata (hidden, semantic_role, description)
        col_meta = col_metadata_map.get(unique_col_name, col_metadata_map.get(col.get('name', ''), {}))
        if col_meta.get('hidden', False):
            bim_column["isHidden"] = True
        if col_meta.get('description', ''):
            bim_column["description"] = col_meta['description']

        # Geographic data categories from semantic-role
        semantic_role = col_meta.get('semantic_role', '')
        geo_category = _map_semantic_role_to_category(semantic_role, unique_col_name)
        if geo_category:
            bim_column["dataCategory"] = geo_category

        # Add the appropriate data type
        if col.get('datatype') == 'date' or col.get('datatype') == 'datetime':
            bim_column["dataCategory"] = "DateTime"
            bim_column["formatString"] = "General Date"
        elif col.get('datatype') in ['integer', 'real']:
            bim_column["summarizeBy"] = "sum"
            if col.get('datatype') == 'real':
                bim_column["formatString"] = "#,0.00"

        # Apply source number format if available (overrides default)
        source_fmt = col_meta.get('default_format', '') or col.get('default_format', '')
        if source_fmt:
            pbi_fmt = _convert_source_format_to_pbi(source_fmt)
            if pbi_fmt:
                bim_column["formatString"] = pbi_fmt

        result_table["columns"].append(bim_column)

    # Separate calculations into calculated columns vs measures
    column_table_map = dax_context.get('column_table_map', {})
    calc_map_ctx = dax_context.get('calc_map', {})
    param_values = dax_context.get('param_values', {})
    measure_names_ctx = dax_context.get('measure_names', set())

    # Pre-compiled aggregation pattern (reused in pre-classification and main loop)
    _agg_pattern = re.compile(
        r'\b(SUM|COUNT|COUNTA|COUNTD|COUNTROWS|AVERAGE|AVG|MIN|MAX|MEDIAN|'
        r'STDEV|STDEVP|VAR|VARP|PERCENTILE|DISTINCTCOUNT|CALCULATE|'
        r'TOTALYTD|SAMEPERIODLASTYEAR|RANKX|SUMX|AVERAGEX|MINX|MAXX|COUNTX|'
        r'CORR|COVAR|COVARP|'
        r'OFFSET|WINDOW|INDEX|'
        r'RANK|RANK_PERCENTILE)\s*\(',
        re.IGNORECASE
    )

    # --- Pre-classification pass ---
    # Identify which calculations will be calculated columns so that when
    # a calc references another calc-column, we correctly treat it as a
    # column reference (not a measure reference).  Without this, a
    # dimension-role calc that concatenates other calc-columns (e.g.
    # Filière = Nucléaire_vrai & Réseaux_vrai & NSE_vrai) is incorrectly
    # demoted to a measure because the refs appear in calc_map/measure_names.
    prelim_calc_col_captions = set()
    prelim_calc_col_raws = set()
    for _pc in calculations:
        _pc_name = _pc.get('name', '').replace('[', '').replace(']', '')
        _pc_caption = _pc.get('caption', _pc_name)
        _pc_formula = _pc.get('formula', '').strip()
        _pc_role = _pc.get('role', 'measure')
        _pc_is_literal = _pc_formula and '[' not in _pc_formula
        _pc_has_agg = bool(_agg_pattern.search(_pc_formula))
        # Check for physical column refs (refs not in calc_map/measure_names)
        _pc_refs = re.findall(r'\[([^\]]+)\]', _pc_formula)
        _pc_has_col = False
        for _r in _pc_refs:
            if _r == _pc_caption or _r.startswith('Parameters'):
                continue
            if not (_r in measure_names_ctx or _r in calc_map_ctx.values() or _r in calc_map_ctx):
                _pc_has_col = True
                break
        # Dimension-role calcs without aggregation → pre-classify as calc columns.
        # The "references only measures" override is NOT applied here; it will
        # be applied in the main pass with the knowledge of which calcs are
        # truly calc-columns.
        _pc_is_cc = (not _pc_is_literal) and (
            _pc_role == 'dimension' or
            (_pc_role == 'measure' and not _pc_has_agg and _pc_has_col)
        )
        if _pc_is_cc:
            prelim_calc_col_captions.add(_pc_caption)
            prelim_calc_col_raws.add(_pc_name)

    m_calc_steps = []  # Accumulated M Table.AddColumn steps (replaces DAX calc cols)

    for calc in calculations:
        calc_name = calc.get('name', '').replace('[', '').replace(']', '')
        caption = calc.get('caption', calc_name)
        formula = calc.get('formula', '').strip()
        role = calc.get('role', 'measure')
        datatype = calc.get('datatype', 'string')

        # Skip calculations with no formula (e.g. categorical-bin groups)
        # to avoid generating measures with empty expressions.
        if not formula:
            continue

        # Determine if it's a simple literal (parameter) -> measure
        is_literal = formula and '[' not in formula

        # Classify: calculated column or measure
        has_aggregation = bool(_agg_pattern.search(formula))
        refs_in_formula = re.findall(r'\[([^\]]+)\]', formula)
        has_column_refs = False
        references_only_measures = True
        for ref in refs_in_formula:
            if ref == caption:
                continue
            if ref.startswith('Parameters'):
                continue
            # A ref is a "measure/calc ref" ONLY if it's a known calc/param
            # AND it was NOT pre-classified as a calculated column.
            is_known_calc = (ref in measure_names_ctx or
                             ref in calc_map_ctx.values() or
                             ref in calc_map_ctx)
            is_calc_col_ref = (ref in prelim_calc_col_captions or
                               ref in prelim_calc_col_raws)
            is_measure_ref = is_known_calc and not is_calc_col_ref
            if not is_measure_ref:
                has_column_refs = True
                references_only_measures = False
                break

        is_calc_col = (not is_literal) and (
            role == 'dimension' or
            (role == 'measure' and not has_aggregation and has_column_refs)
        )

        # If a dimension-role calc references ONLY other measures/calcs
        # (no physical columns), it must be a measure — calc columns
        # cannot reference measures in DAX.
        if is_calc_col and not has_column_refs and references_only_measures:
            is_calc_col = False

        # Security functions must be measures, never calculated columns
        has_security_func = bool(re.search(
            r'\b(USERPRINCIPALNAME|USERNAME|CUSTOMDATA|USERCULTURE)\s*\(',
            dax_context.get('_preview_dax', formula), re.IGNORECASE
        )) or bool(re.search(
            r'\b(USERNAME|FULLNAME|USERDOMAIN|ISMEMBEROF)\s*\(',
            formula, re.IGNORECASE
        ))
        if has_security_func:
            is_calc_col = False

        # Ignore MAKEPOINT (no DAX equivalent)
        if re.search(r'\bMAKEPOINT\b', formula, re.IGNORECASE):
            continue

        dax_formula = convert_formula_to_dax(
            formula,
            column_name=calc_name,
            table_name=table_name,
            calc_map=dax_context.get('calc_map'),
            param_map=dax_context.get('param_map'),
            column_table_map=column_table_map,
            measure_names=dax_context.get('measure_names'),
            is_calc_column=is_calc_col,
            param_values=param_values,
            calc_datatype=datatype,
            partition_fields=calc.get('table_calc_partitioning')
        )

        if is_calc_col:
            # Post-process: inline literal-value measure references
            for ms in result_table.get("measures", []):
                ms_name = ms.get("name", "")
                ms_expr = ms.get("expression", "").strip()
                if ms_expr and re.match(r'^[\d.]+$|^"[^"]*"$|^true$|^false$', ms_expr, re.IGNORECASE):
                    dax_formula = re.sub(
                        r'\[' + re.escape(ms_name) + r'\]',
                        ms_expr,
                        dax_formula
                    )

            # ── Try to push the calculated column into Power Query M ──
            m_expr = _dax_to_m_expression(dax_formula, table_name)
            if m_expr is not None:
                m_type = _DAX_TO_M_TYPE.get(
                    map_to_powerbi_type(datatype), 'type text')
                m_calc_steps.append(
                    m_transform_add_column(caption, f'each {m_expr}', m_type))
                bim_calc_col = {
                    "name": caption,
                    "dataType": map_to_powerbi_type(datatype),
                    "sourceColumn": caption,
                    "summarizeBy": "none",
                }
            else:
                # Fallback: keep as DAX calculated column
                bim_calc_col = {
                    "name": caption,
                    "dataType": map_to_powerbi_type(datatype),
                    "expression": dax_formula,
                    "summarizeBy": "none",
                    "isCalculated": True,
                }
            if datatype == 'real':
                bim_calc_col["formatString"] = "#,0.00"

            calc_meta = col_metadata_map.get(caption, col_metadata_map.get(calc_name, {}))
            if calc_meta.get('hidden', False):
                bim_calc_col["isHidden"] = True
            if calc_meta.get('description', ''):
                bim_calc_col["description"] = calc_meta['description']
            sr = calc_meta.get('semantic_role', '')
            geo_cat = _map_semantic_role_to_category(sr, caption)
            if geo_cat:
                bim_calc_col["dataCategory"] = geo_cat

            result_table["columns"].append(bim_calc_col)
        else:
            # DAX Measure
            bim_measure = {
                "name": caption,
                "expression": dax_formula,
                "formatString": _get_format_string(datatype),
                "displayFolder": _get_display_folder(datatype, role)
            }
            result_table["measures"].append(bim_measure)

    # Inject accumulated M steps into the partition (replaces DAX calc cols)
    if m_calc_steps:
        _inject_m_steps_into_partition(result_table, m_calc_steps)

    return result_table


def _build_relationships(relationships):
    """
    Create relationships from source joins.

    Args:
        relationships: List of extracted relations with left/right {table, column}

    Returns:
        list: Relationship definitions
    """
    result = []

    for rel in relationships:
        left = rel.get('left', {})
        right = rel.get('right', {})

        from_table = left.get('table', '')
        from_column = left.get('column', '')
        to_table = right.get('table', '')
        to_column = right.get('column', '')

        if not from_table or not to_table or not from_column or not to_column:
            continue

        join_type = rel.get('type', 'left')
        result.append({
            "name": f"Relationship-{len(result)+1}",
            "fromTable": from_table,
            "fromColumn": from_column,
            "toTable": to_table,
            "toColumn": to_column,
            "joinType": join_type,
            "crossFilteringBehavior": "bothDirections" if join_type == 'full' else "oneDirection"
        })

    return result


def _infer_cross_table_relationships(model):
    """
    Infer relationships between tables when DAX expressions reference
    columns from another table but no explicit relationship exists.

    Algorithm:
    1. Scan all DAX expressions (measures, calc columns, RLS roles)
    2. Find 'TableName'[ColumnName] cross-table references
    3. For each unconnected table pair, find the best column-name match
    4. Create a manyToOne relationship (fact->dimension)
    """
    tables = model["model"]["tables"]
    relationships = model["model"]["relationships"]

    # Build existing relationship pairs (bidirectional)
    connected_pairs = set()
    for rel in relationships:
        ft = rel.get("fromTable", "")
        tt = rel.get("toTable", "")
        connected_pairs.add((ft, tt))
        connected_pairs.add((tt, ft))

    # Build table->columns map
    table_columns = {}
    for table in tables:
        tname = table.get("name", "")
        table_columns[tname] = {col.get("name", "") for col in table.get("columns", [])}

    cross_ref_pattern = re.compile(r"'([^']+)'\[([^\]]+)\]")

    # Collect needed table pairs from DAX cross-table references
    needed_pairs = set()

    for table in tables:
        tname = table.get("name", "")
        for measure in table.get("measures", []):
            expr = measure.get("expression", "")
            for match in cross_ref_pattern.finditer(expr):
                ref_table = match.group(1)
                if ref_table != tname and ref_table in table_columns:
                    needed_pairs.add((tname, ref_table))
        for col in table.get("columns", []):
            if col.get("isCalculated"):
                expr = col.get("expression", "")
                for match in cross_ref_pattern.finditer(expr):
                    ref_table = match.group(1)
                    if ref_table != tname and ref_table in table_columns:
                        needed_pairs.add((tname, ref_table))

    # Scan RLS roles
    for role in model["model"].get("roles", []):
        for tp in role.get("tablePermissions", []):
            perm_table = tp.get("name", "")
            expr = tp.get("filterExpression", "")
            for match in cross_ref_pattern.finditer(expr):
                ref_table = match.group(1)
                if ref_table != perm_table and ref_table in table_columns:
                    needed_pairs.add((perm_table, ref_table))

    # For each needed pair, find a matching column for the relationship
    for (source_table, ref_table) in needed_pairs:
        if (source_table, ref_table) in connected_pairs:
            continue

        source_cols = table_columns.get(source_table, set())
        ref_cols = table_columns.get(ref_table, set())

        best_match = None
        best_score = 0

        for sc in source_cols:
            for rc in ref_cols:
                sc_lower = sc.lower()
                rc_lower = rc.lower()
                score = 0

                if sc_lower == rc_lower:
                    score = 100
                elif sc_lower in rc_lower and len(sc_lower) >= 3:
                    score = 50 - (len(rc) - len(sc))
                elif rc_lower in sc_lower and len(rc_lower) >= 3:
                    score = 50 - (len(sc) - len(rc))
                elif len(sc_lower) >= 3 and len(rc_lower) >= 3:
                    common = 0
                    for a, b in zip(sc_lower, rc_lower):
                        if a == b:
                            common += 1
                        else:
                            break
                    if common >= 3:
                        score = common * 5

                if score > best_score:
                    best_score = score
                    best_match = (sc, rc)

        if best_match and best_score >= 15:
            from_col, to_col = best_match

            if len(source_cols) >= len(ref_cols):
                fact_table, dim_table = source_table, ref_table
                fk_col, pk_col = from_col, to_col
            else:
                fact_table, dim_table = ref_table, source_table
                fk_col, pk_col = to_col, from_col

            relationships.append({
                "name": f"inferred_{fact_table}_{dim_table}",
                "fromTable": fact_table,
                "fromColumn": fk_col,
                "toTable": dim_table,
                "toColumn": pk_col,
                "crossFilteringBehavior": "oneDirection"
            })

            connected_pairs.add((source_table, ref_table))
            connected_pairs.add((ref_table, source_table))

    # Pass 2: Proactive key-column matching for unconnected tables
    # Looks for columns with identical names that look like keys (ID, Key, Code, etc.)
    _KEY_SUFFIXES = {'id', 'key', 'code', 'no', 'number', 'num', 'pk', 'fk', 'sk'}
    all_table_names = list(table_columns.keys())

    for i, t1 in enumerate(all_table_names):
        for t2 in all_table_names[i + 1:]:
            if (t1, t2) in connected_pairs:
                continue
            # Skip auto-generated tables (Calendar, parameters)
            if t1 == 'Calendar' or t2 == 'Calendar':
                continue

            t1_cols = table_columns.get(t1, set())
            t2_cols = table_columns.get(t2, set())

            best_col = None
            best_score = 0

            common_cols = t1_cols & t2_cols
            for col in common_cols:
                col_lower = col.lower().rstrip('_')
                # Score: exact ID/key column names get highest priority
                # Split on underscores/spaces AND CamelCase boundaries
                parts = re.split(r'[_\s]', col_lower)
                # Also split CamelCase: "customerid" → check endswith
                has_key_suffix = (
                    any(p in _KEY_SUFFIXES for p in parts)
                    or any(col_lower.endswith(s) for s in _KEY_SUFFIXES)
                )
                if has_key_suffix:
                    score = 90
                elif col_lower.endswith('name'):
                    score = 40
                else:
                    score = 20  # Any common column
                if score > best_score:
                    best_score = score
                    best_col = col

            if best_col and best_score >= 40:
                # Fact = table with more columns, dim = fewer
                if len(t1_cols) >= len(t2_cols):
                    fact_table, dim_table = t1, t2
                else:
                    fact_table, dim_table = t2, t1

                relationships.append({
                    "name": f"inferred_{fact_table}_{dim_table}",
                    "fromTable": fact_table,
                    "fromColumn": best_col,
                    "toTable": dim_table,
                    "toColumn": best_col,
                    "crossFilteringBehavior": "oneDirection"
                })
                connected_pairs.add((t1, t2))
                connected_pairs.add((t2, t1))


def _detect_many_to_many(model, datasources):
    """Determine cardinality for each relationship using multi-signal analysis.

    Signals (in priority order):
    0. Synthetic key table: tables named ``$Syn*`` are Qlik synthetic keys
       created when multiple fields link two tables → manyToMany
    1. Explicit joinType='full' → manyToMany
    2. Column uniqueness from model metadata (primary-key flags)
    3. ID-suffix heuristic: columns ending in ID/Id/_id are likely unique keys
    4. Fact-table tiebreaker: when the same ID column appears on both sides,
       the table with more columns is likely the fact table (FK, not unique)

    Cardinality outcomes:
    - oneToOne  : both sides are unique key columns
    - manyToOne : 'to' side is a unique key, 'from' side is not
    - manyToMany: neither side is a unique key (or explicit full join)
    """
    # Build column-uniqueness map from model tables and datasource metadata
    unique_columns = _build_unique_column_set(model, datasources)

    # Detect synthetic key tables ($Syn, $SyntheticKey, etc.)
    syn_tables = set()
    for table in model.get('model', {}).get('tables', []):
        tname = table.get('name', '')
        if tname.startswith('$Syn') or tname.startswith('$syn'):
            syn_tables.add(tname)

    # Build table-column-count map for fact-table tiebreaker
    table_col_count = {}
    for table in model.get('model', {}).get('tables', []):
        table_col_count[table.get('name', '')] = len(table.get('columns', []))

    for rel in model['model']['relationships']:
        from_table = rel.get('fromTable', '')
        from_col = rel.get('fromColumn', '')
        to_table = rel.get('toTable', '')
        to_col = rel.get('toColumn', '')
        join_type = rel.get('joinType', 'inner')

        # Signal 0: synthetic key table → manyToMany
        if from_table in syn_tables or to_table in syn_tables:
            _set_cardinality(rel, 'many', 'many')
            print(f"  ⚠️  {from_table}.{from_col} ↔ {to_table}.{to_col}: "
                  f"manyToMany (synthetic key table)")
            continue

        # Signal 1: explicit full join → manyToMany
        if join_type == 'full':
            _set_cardinality(rel, 'many', 'many')
            print(f"  ⚠️  {from_table}.{from_col} ↔ {to_table}.{to_col}: "
                  f"manyToMany (full join)")
            continue

        from_unique = (from_table, from_col) in unique_columns
        to_unique = (to_table, to_col) in unique_columns

        # Fact-table tiebreaker: when both sides have ID-suffixed columns
        # (both detected as "unique"), the table with MORE columns is likely
        # the fact table where the column is a foreign key (not truly unique).
        if from_unique and to_unique:
            from_count = table_col_count.get(from_table, 0)
            to_count = table_col_count.get(to_table, 0)
            if from_count > to_count:
                # from-side is the fact table → FK, not unique
                from_unique = False
            elif to_count > from_count:
                # to-side is the fact table → FK, not unique
                to_unique = False
            # If equal column count, keep as oneToOne (can't distinguish)

        if from_unique and to_unique:
            # oneToOne — both sides are keys
            _set_cardinality(rel, 'one', 'one')
            print(f"  ✓  {from_table}.{from_col} → {to_table}.{to_col}: "
                  f"oneToOne (both unique)")
        elif to_unique:
            # manyToOne — standard star-schema pattern (optimal)
            _set_cardinality(rel, 'many', 'one')
            print(f"  ✓  {from_table}.{from_col} → {to_table}.{to_col}: "
                  f"manyToOne (lookup table)")
        elif from_unique:
            # oneToMany — reverse direction
            _set_cardinality(rel, 'one', 'many')
            print(f"  ⚠️  {from_table}.{from_col} → {to_table}.{to_col}: "
                  f"oneToMany (from-side is key)")
        else:
            # manyToMany — neither side detected as unique
            _set_cardinality(rel, 'many', 'many')
            print(f"  ⚠️  {from_table}.{from_col} ↔ {to_table}.{to_col}: "
                  f"manyToMany (no unique key detected)")


def _set_cardinality(rel, from_card, to_card):
    """Set cardinality and crossFilteringBehavior on a relationship.

    Uses ``RelationshipCardinality`` and ``CrossFilterDirection`` enums
    from ``qlik_model_converter`` to ensure consistency across code paths.

    Args:
        rel: Relationship dict to mutate.
        from_card: 'one' or 'many'.
        to_card: 'one' or 'many'.
    """
    # Map string tokens to canonical enum values
    _CARD_MAP = {
        ('one', 'one'): RelationshipCardinality.ONE_TO_ONE,
        ('one', 'many'): RelationshipCardinality.ONE_TO_MANY,
        ('many', 'one'): RelationshipCardinality.MANY_TO_ONE,
        ('many', 'many'): RelationshipCardinality.MANY_TO_MANY,
    }
    cardinality = _CARD_MAP.get((from_card, to_card),
                                 RelationshipCardinality.MANY_TO_ONE)

    rel['fromCardinality'] = from_card
    rel['toCardinality'] = to_card
    rel['_cardinality_enum'] = cardinality.value

    # manyToMany requires bothDirections; everything else uses oneDirection
    if cardinality == RelationshipCardinality.MANY_TO_MANY:
        rel['crossFilteringBehavior'] = CrossFilterDirection.BOTH.value.lower() + 'Directions'
    else:
        rel['crossFilteringBehavior'] = CrossFilterDirection.SINGLE.value.lower() + 'Direction'

    # Normalize to the string values TMDL expects
    # CrossFilterDirection.BOTH → "bothDirections", SINGLE → "oneDirection"
    # (already correct from above, but be explicit for readability)
    if rel['crossFilteringBehavior'] not in ('oneDirection', 'bothDirections'):
        rel['crossFilteringBehavior'] = 'oneDirection'


# ── ID-suffix patterns for unique-key detection ─────────────────────

_ID_SUFFIXES = ('id', '_id', 'key', '_key', 'code', '_code', 'pk', '_pk')

_ID_RE = re.compile(
    r'(?:^|_)(?:id|key|code|pk)$|'   # ends with _id, _key, _code, _pk
    r'(?<=[a-z])(?:ID|Id|Key|Code)$',  # camelCase: CustomerID, ProductId
    re.IGNORECASE,
)


def _build_unique_column_set(model, datasources):
    """Build a set of (table, column) tuples that are likely unique keys.

    Uses three signals:
    1. Primary-key / isKey metadata from the model
    2. ID-suffix heuristic on column names
    3. Relationship target analysis: if the 'to' side of a manyToOne is
       always the same column, it is probably a key
    """
    unique_cols = set()

    # ── Signal 1: Model metadata (isKey, isPrimaryKey) ───────────────
    for table in model.get('model', {}).get('tables', []):
        tname = table.get('name', '')
        for col in table.get('columns', []):
            cname = col.get('name', '')
            if col.get('isKey') or col.get('isPrimaryKey'):
                unique_cols.add((tname, cname))

    # ── Signal 2: ID-suffix heuristic ────────────────────────────────
    for table in model.get('model', {}).get('tables', []):
        tname = table.get('name', '')
        for col in table.get('columns', []):
            cname = col.get('name', '')
            if _ID_RE.search(cname):
                unique_cols.add((tname, cname))

    # ── Signal 3: Datasource column metadata ─────────────────────────
    for ds in datasources:
        for table in ds.get('tables', []):
            tname = table.get('name', '')
            for col in table.get('columns', []):
                cname = col.get('name', '')
                if col.get('isKey') or col.get('isPrimaryKey'):
                    unique_cols.add((tname, cname))
                elif _ID_RE.search(cname):
                    unique_cols.add((tname, cname))

    return unique_cols


def _generate_bridge_tables(model):
    """Replace manyToMany relationships with bridge (junction) tables.

    For each manyToMany relationship between TableA.ColA ↔ TableB.ColB:
    1. Create a calculated bridge table ``Bridge_TableA_TableB`` with two
       columns: ColA and ColB populated via
       ``DISTINCT(SELECTCOLUMNS(CROSSJOIN(VALUES(...), VALUES(...)), ...))``
    2. Replace the single M2M relationship with two manyToOne relationships:
       - TableA.ColA → Bridge.ColA  (manyToOne)
       - TableB.ColB → Bridge.ColB  (manyToOne)
    3. The bridge table is hidden by default.

    Also handles **composite key** M2M relationships (multiple M2M rels
    between the same table pair) by merging them into a single bridge
    table with multiple column pairs.

    This eliminates symmetric cross-filter ambiguity and improves
    Power BI performance compared to native manyToMany relationships.

    Returns:
        int: Number of bridge tables generated.
    """
    rels = model['model']['relationships']
    tables = model['model']['tables']

    m2m_rels = [r for r in rels if
                r.get('fromCardinality') == 'many' and
                r.get('toCardinality') == 'many']

    if not m2m_rels:
        return 0

    # Group M2M rels by table pair for composite key detection
    pair_groups: dict[tuple, list] = {}
    for rel in m2m_rels:
        from_table = rel.get('fromTable', '')
        to_table = rel.get('toTable', '')
        pair_key = (min(from_table, to_table), max(from_table, to_table))
        pair_groups.setdefault(pair_key, []).append(rel)

    existing_table_names = {t.get('name', '') for t in tables}
    new_tables = []
    new_rels = []
    removed_rels = set()

    # Build a quick lookup for column data types
    col_type_map: dict[tuple, str] = {}
    for t in tables:
        tname = t.get('name', '')
        for c in t.get('columns', []):
            col_type_map[(tname, c.get('name', ''))] = c.get('dataType', 'string')

    for (tbl_a, tbl_b), group_rels in pair_groups.items():
        # Collect all column pairs for this table pair
        col_pairs = []
        for rel in group_rels:
            from_table = rel.get('fromTable', '')
            from_col = rel.get('fromColumn', '')
            to_table = rel.get('toTable', '')
            to_col = rel.get('toColumn', '')
            if not from_table or not to_table or not from_col or not to_col:
                continue
            col_pairs.append((from_table, from_col, to_table, to_col))

        if not col_pairs:
            continue

        # Normalize direction: first table is always tbl_a
        normalized = []
        for ft, fc, tt, tc in col_pairs:
            if ft == tbl_a:
                normalized.append((ft, fc, tt, tc))
            else:
                normalized.append((tt, tc, ft, fc))
        col_pairs = normalized

        # Generate unique bridge table name
        bridge_name = f"Bridge_{tbl_a}_{tbl_b}"
        suffix = 2
        while bridge_name in existing_table_names:
            bridge_name = f"Bridge_{tbl_a}_{tbl_b}_{suffix}"
            suffix += 1
        existing_table_names.add(bridge_name)

        # Build bridge table columns and DAX expression
        bridge_cols = []
        values_a = []
        values_b = []
        select_cols = []
        seen_col_names = set()

        for ft, fc, tt, tc in col_pairs:
            ft_type = col_type_map.get((ft, fc), 'string')
            tt_type = col_type_map.get((tt, tc), 'string')

            # Ensure unique column names in bridge table
            a_col_name = fc
            b_col_name = tc
            if a_col_name == b_col_name:
                a_col_name = f"{ft}_{fc}"
                b_col_name = f"{tt}_{tc}"

            # Deduplicate column names
            base_a, base_b = a_col_name, b_col_name
            idx = 2
            while a_col_name in seen_col_names:
                a_col_name = f"{base_a}_{idx}"
                idx += 1
            seen_col_names.add(a_col_name)
            idx = 2
            while b_col_name in seen_col_names:
                b_col_name = f"{base_b}_{idx}"
                idx += 1
            seen_col_names.add(b_col_name)

            bridge_cols.extend([
                {'name': a_col_name, 'dataType': ft_type,
                 'sourceColumn': a_col_name, 'isHidden': False},
                {'name': b_col_name, 'dataType': tt_type,
                 'sourceColumn': b_col_name, 'isHidden': False},
            ])
            values_a.append(f"VALUES('{ft}'[{fc}])")
            values_b.append(f"VALUES('{tt}'[{tc}])")
            select_cols.append(f'        \"{a_col_name}\", \'{ft}\'[{fc}]')
            select_cols.append(f'        \"{b_col_name}\", \'{tt}\'[{tc}]')

        # Build DAX expression
        if len(col_pairs) == 1:
            # Single column pair: simple CROSSJOIN
            dax_expr = (
                f"DISTINCT(\n"
                f"    SELECTCOLUMNS(\n"
                f"        CROSSJOIN(\n"
                f"            {values_a[0]},\n"
                f"            {values_b[0]}\n"
                f"        ),\n"
                + ',\n'.join(select_cols) + '\n'
                f"    )\n"
                f")"
            )
        else:
            # Composite key: CROSSJOIN multiple VALUES
            all_values = []
            for va, vb in zip(values_a, values_b):
                all_values.extend([va, vb])
            crossjoin_inner = ',\n            '.join(all_values)
            dax_expr = (
                f"DISTINCT(\n"
                f"    SELECTCOLUMNS(\n"
                f"        CROSSJOIN(\n"
                f"            {crossjoin_inner}\n"
                f"        ),\n"
                + ',\n'.join(select_cols) + '\n'
                f"    )\n"
                f")"
            )

        bridge_table = {
            'name': bridge_name,
            'columns': bridge_cols,
            'measures': [],
            'hierarchies': [],
            'partitions': [{
                'name': bridge_name,
                'mode': 'import',
                'source': {
                    'type': 'calculated',
                    'expression': dax_expr,
                },
            }],
            'isHidden': True,
        }
        new_tables.append(bridge_table)

        # Create manyToOne relationships from each source table to bridge
        col_idx = 0
        for ft, fc, tt, tc in col_pairs:
            a_col_name = bridge_cols[col_idx]['name']
            b_col_name = bridge_cols[col_idx + 1]['name']
            col_idx += 2

            new_rels.append({
                'name': f"Bridge-{ft}-{bridge_name}-{a_col_name}",
                'fromTable': ft,
                'fromColumn': fc,
                'toTable': bridge_name,
                'toColumn': a_col_name,
                'fromCardinality': 'many',
                'toCardinality': 'one',
                'crossFilteringBehavior': 'oneDirection',
            })
            new_rels.append({
                'name': f"Bridge-{tt}-{bridge_name}-{b_col_name}",
                'fromTable': tt,
                'fromColumn': tc,
                'toTable': bridge_name,
                'toColumn': b_col_name,
                'fromCardinality': 'many',
                'toCardinality': 'one',
                'crossFilteringBehavior': 'oneDirection',
            })

        # Mark all original M2M relationships for removal
        for rel in group_rels:
            removed_rels.add(id(rel))

        is_composite = len(col_pairs) > 1
        kind = f"composite ({len(col_pairs)} keys)" if is_composite else "single key"
        print(f"  🔗 Bridge table '{bridge_name}' ({kind}) for "
              f"{tbl_a} ↔ {tbl_b}")

    # Remove original M2M relationships and add bridge relationships
    model['model']['relationships'] = [
        r for r in rels if id(r) not in removed_rels
    ] + new_rels

    # Add bridge tables to the model
    model['model']['tables'].extend(new_tables)

    return len(new_tables)


# ── Phase 3: Cross-Filter Direction Optimization ────────────────────

def _optimize_cross_filter_direction(model):
    """Minimize use of bothDirections cross-filtering.

    Power BI best practice: use ``oneDirection`` (single) whenever possible.
    ``bothDirections`` should only be used for manyToMany relationships or
    when visual bindings explicitly require reverse filtering.

    This function scans all active relationships and downgrades
    ``bothDirections`` to ``oneDirection`` except for manyToMany
    relationships, which require bidirectional filtering to work.

    Returns:
        int: Number of relationships changed from bothDirections to oneDirection.
    """
    changed = 0
    for rel in model['model']['relationships']:
        if rel.get('isActive') is False:
            continue
        cfb = rel.get('crossFilteringBehavior', 'oneDirection')
        from_card = rel.get('fromCardinality', 'many')
        to_card = rel.get('toCardinality', 'one')

        is_m2m = from_card == 'many' and to_card == 'many'

        if cfb == 'bothDirections' and not is_m2m:
            rel['crossFilteringBehavior'] = 'oneDirection'
            changed += 1

    return changed


# ── Phase 4: Relationship Validation & Reporting ────────────────────

def _validate_relationships(model):
    """Validate all relationships and produce a health report.

    Checks performed:
    1. Orphan relationships — references to tables/columns that don't exist
    2. Duplicate relationships — same (fromTable, fromColumn, toTable, toColumn)
    3. Self-referencing — fromTable == toTable
    4. ManyToMany count — flagged as warnings (performance risk)
    5. Inactive relationship count
    6. BothDirections count — flagged if excessive
    7. Type mismatches — fromColumn and toColumn have different data types

    Returns:
        dict: Relationship health report with errors, warnings, and stats.
    """
    tables = {t.get('name', ''): t for t in model['model']['tables']}
    rels = model['model']['relationships']

    errors = []
    warnings = []
    info = []

    # Build column lookup: {(table, col): dataType}
    col_types = {}
    for tname, tbl in tables.items():
        for col in tbl.get('columns', []):
            cname = col.get('name', '')
            col_types[(tname, cname)] = col.get('dataType', 'string')

    seen_pairs = set()
    m2m_count = 0
    inactive_count = 0
    both_dir_count = 0
    bridge_count = 0

    for rel in rels:
        ft = rel.get('fromTable', '')
        fc = rel.get('fromColumn', '')
        tt = rel.get('toTable', '')
        tc = rel.get('toColumn', '')
        name = rel.get('name', '')

        # Check for bridge tables
        if ft.startswith('Bridge_') or tt.startswith('Bridge_'):
            bridge_count += 1

        # 1. Orphan check
        if ft and ft not in tables:
            errors.append(f"Orphan: relationship '{name}' references "
                          f"non-existent table '{ft}'")
        if tt and tt not in tables:
            errors.append(f"Orphan: relationship '{name}' references "
                          f"non-existent table '{tt}'")
        if ft in tables and fc:
            t_cols = {c.get('name', '') for c in tables[ft].get('columns', [])}
            if fc not in t_cols:
                errors.append(f"Orphan: '{ft}.{fc}' column not found")
        if tt in tables and tc:
            t_cols = {c.get('name', '') for c in tables[tt].get('columns', [])}
            if tc not in t_cols:
                errors.append(f"Orphan: '{tt}.{tc}' column not found")

        # 2. Duplicate check
        pair = (ft, fc, tt, tc)
        if pair in seen_pairs:
            warnings.append(f"Duplicate relationship: {ft}.{fc} → {tt}.{tc}")
        seen_pairs.add(pair)

        # 3. Self-referencing
        if ft and ft == tt:
            warnings.append(f"Self-referencing: '{name}' on table '{ft}'")

        # 4. ManyToMany
        if (rel.get('fromCardinality') == 'many' and
                rel.get('toCardinality') == 'many'):
            m2m_count += 1

        # 5. Inactive
        if rel.get('isActive') is False:
            inactive_count += 1

        # 6. BothDirections
        if rel.get('crossFilteringBehavior') == 'bothDirections':
            both_dir_count += 1

        # 7. Type mismatch
        from_type = col_types.get((ft, fc), '')
        to_type = col_types.get((tt, tc), '')
        if from_type and to_type and from_type.lower() != to_type.lower():
            warnings.append(
                f"Type mismatch: {ft}.{fc} ({from_type}) ↔ "
                f"{tt}.{tc} ({to_type})")

    # Summary warnings
    if m2m_count > 0:
        warnings.append(f"{m2m_count} manyToMany relationship(s) — "
                        f"consider using --bridge-tables auto")
    if both_dir_count > 2:
        warnings.append(f"{both_dir_count} bothDirections relationships — "
                        f"may cause ambiguous filter propagation")

    if not errors and not warnings:
        info.append("All relationships are healthy")

    report = {
        'total': len(rels),
        'active': len(rels) - inactive_count,
        'inactive': inactive_count,
        'manyToMany': m2m_count,
        'bothDirections': both_dir_count,
        'bridgeTables': bridge_count,
        'errors': errors,
        'warnings': warnings,
        'info': info,
        'healthy': len(errors) == 0,
    }

    # Print summary
    if errors:
        for e in errors:
            print(f"  ✗ {e}")
    if warnings:
        for w in warnings:
            print(f"  ⚠ {w}")

    return report


def _validate_bridge_tables(model):
    """Validate generated bridge tables for structural correctness.

    Checks:
    1. Bridge table DAX expression has balanced parentheses
    2. Referenced tables/columns exist in the model
    3. Replacement relationships connect to valid bridge table columns
    4. Each bridge table has at least 2 columns

    Returns:
        list[str]: List of validation issue descriptions (empty = all good).
    """
    issues: list[str] = []
    table_map = {t.get('name', ''): t for t in model['model'].get('tables', [])}
    rels = model['model'].get('relationships', [])

    for table in model['model'].get('tables', []):
        tname = table.get('name', '')
        if not tname.startswith('Bridge_'):
            continue

        # Check: at least 2 columns
        cols = table.get('columns', [])
        if len(cols) < 2:
            issues.append(f"'{tname}' has {len(cols)} columns (expected ≥ 2)")

        # Check: DAX expression exists and has balanced parens
        for part in table.get('partitions', []):
            src = part.get('source', {})
            if src.get('type') != 'calculated':
                continue
            expr = src.get('expression', '')
            if not expr:
                issues.append(f"'{tname}' has empty DAX expression")
                continue
            if expr.count('(') != expr.count(')'):
                issues.append(
                    f"'{tname}' DAX has unbalanced parentheses "
                    f"({expr.count('(')} open vs {expr.count(')')} close)")

            # Check: referenced tables exist in VALUES() calls
            import re as _re
            for m in _re.finditer(r"VALUES\('([^']+)'\[", expr):
                ref_table = m.group(1)
                if ref_table not in table_map:
                    issues.append(
                        f"'{tname}' DAX references non-existent "
                        f"table '{ref_table}'")

        # Check: bridge table has incoming relationships
        bridge_rels = [r for r in rels
                       if r.get('toTable') == tname]
        if len(bridge_rels) < 2:
            issues.append(
                f"'{tname}' has {len(bridge_rels)} incoming "
                f"relationship(s) (expected ≥ 2)")

        # Check: relationship columns exist in bridge table
        col_names = {c.get('name', '') for c in cols}
        for r in bridge_rels:
            to_col = r.get('toColumn', '')
            if to_col and to_col not in col_names:
                issues.append(
                    f"'{tname}' relationship references column "
                    f"'{to_col}' which doesn't exist in bridge table")

    return issues


def _fix_related_for_many_to_many(model):
    """
    Replace RELATED('table'[col]) with LOOKUPVALUE() for manyToMany relationships.
    """
    m2m_tables = {}  # {to_table: [(to_col, from_table, from_col), ...]}
    for rel in model['model']['relationships']:
        if rel.get('fromCardinality') == 'many' and rel.get('toCardinality') == 'many':
            to_table = rel.get('toTable', '')
            to_col = rel.get('toColumn', '')
            from_table = rel.get('fromTable', '')
            from_col = rel.get('fromColumn', '')
            if to_table:
                if to_table not in m2m_tables:
                    m2m_tables[to_table] = (to_col, from_table, from_col)
                # keep first match only (most specific) — avoid overwriting

    if not m2m_tables:
        return

    for table in model['model']['tables']:
        for col in table.get('columns', []):
            expr = col.get('expression', '')
            if expr and 'RELATED(' in expr:
                col['expression'] = _replace_related_with_lookupvalue(expr, m2m_tables)
        for measure in table.get('measures', []):
            expr = measure.get('expression', '')
            if expr and 'RELATED(' in expr:
                measure['expression'] = _replace_related_with_lookupvalue(expr, m2m_tables)


def _replace_related_with_lookupvalue(expr, m2m_tables):
    """Replace RELATED('table'[col]) with LOOKUPVALUE() for m2m tables."""
    pattern = r"RELATED\(('([^']+)'|([A-Za-z0-9_][A-Za-z0-9_ .-]*))\[([^\]]*(?:\]\][^\]]*)*)\]\)"

    def replacer(match):
        table_name = match.group(2) if match.group(2) else match.group(3)
        col_name = match.group(4)

        if table_name not in m2m_tables:
            return match.group(0)

        join_to_col, from_table, from_col = m2m_tables[table_name]

        t_ref = f"'{table_name}'" if not table_name.isidentifier() else table_name
        ft_ref = f"'{from_table}'" if not from_table.isidentifier() else from_table

        return f"LOOKUPVALUE({t_ref}[{col_name}], {t_ref}[{join_to_col}], {ft_ref}[{from_col}])"

    return re.sub(pattern, replacer, expr)


def _fix_relationship_type_mismatches(model):
    """
    Fix type mismatches between relationship key columns.
    Aligns the toColumn ('one' side) to the fromColumn ('many' side) type.
    """
    tables = {t.get('name', ''): t for t in model['model']['tables']}

    pbi_to_m = {
        'String': 'type text',
        'string': 'type text',
        'Int64': 'Int64.Type',
        'int64': 'Int64.Type',
        'Double': 'type number',
        'double': 'type number',
        'Boolean': 'type logical',
        'boolean': 'type logical',
        'DateTime': 'type datetime',
        'dateTime': 'type datetime',
    }

    for rel in model['model']['relationships']:
        from_table = tables.get(rel.get('fromTable', ''))
        to_table = tables.get(rel.get('toTable', ''))
        if not from_table or not to_table:
            continue

        from_col_name = rel.get('fromColumn', '')
        to_col_name = rel.get('toColumn', '')

        from_col = next((c for c in from_table.get('columns', []) if c.get('name') == from_col_name), None)
        to_col = next((c for c in to_table.get('columns', []) if c.get('name') == to_col_name), None)
        if not from_col or not to_col:
            continue

        from_type = from_col.get('dataType', 'string')
        to_type = to_col.get('dataType', 'string')

        if from_type == to_type:
            continue

        print(f"  \u26a0\ufe0f  Type mismatch: {rel.get('fromTable')}.{from_col_name} ({from_type}) "
              f"-> {rel.get('toTable')}.{to_col_name} ({to_type}). Aligning to {from_type}.")

        old_type = to_type
        to_col['dataType'] = from_type

        if from_type.lower() == 'string':
            to_col['summarizeBy'] = 'none'
            if 'formatString' in to_col:
                del to_col['formatString']

        old_m_type = pbi_to_m.get(old_type, '')
        new_m_type = pbi_to_m.get(from_type, '')
        if old_m_type and new_m_type:
            for partition in to_table.get('partitions', []):
                source = partition.get('source', {})
                if isinstance(source, dict) and 'expression' in source:
                    expr = source['expression']
                    old_pattern = f'"{to_col_name}", {old_m_type}'
                    new_pattern = f'"{to_col_name}", {new_m_type}'
                    if old_pattern in expr:
                        source['expression'] = expr.replace(old_pattern, new_pattern)
        else:
            print(f"    \u26a0\ufe0f  Cannot map M types for {to_col_name}: {repr(old_type)} / {repr(from_type)}")


def _map_semantic_role_to_category(semantic_role, col_name=''):
    """Map a semantic-role to a Power BI dataCategory."""
    role_map = {
        '[Country].[Name]': 'Country',
        '[Country].[ISO3166_2]': 'Country',
        '[State].[Name]': 'StateOrProvince',
        '[State].[Abbreviation]': 'StateOrProvince',
        '[County].[Name]': 'County',
        '[City].[Name]': 'City',
        '[ZipCode].[Name]': 'PostalCode',
        '[Latitude]': 'Latitude',
        '[Longitude]': 'Longitude',
        '[Geographical].[Latitude]': 'Latitude',
        '[Geographical].[Longitude]': 'Longitude',
        '[Address]': 'Address',
        '[Continent].[Name]': 'Continent',
    }
    if semantic_role in role_map:
        return role_map[semantic_role]

    if not semantic_role:
        name_lower = col_name.lower()
        if 'latitude' in name_lower or name_lower in ('lat', 'lat_upgrade'):
            return 'Latitude'
        if 'longitude' in name_lower or name_lower in ('lon', 'lng', 'long', 'long_upgrade'):
            return 'Longitude'
        if name_lower in ('city', 'ville', 'commune', 'label') and 'code' not in name_lower:
            return 'City'
        if name_lower in ('country', 'pays'):
            return 'Country'
        if any(x in name_lower for x in ['region', '\u00e9tat', 'state', 'province', 'd\u00e9partement']):
            return 'StateOrProvince'
        if 'postal' in name_lower or 'zip' in name_lower or 'code_postal' in name_lower:
            return 'PostalCode'

    return None


def _get_display_folder(datatype, role):
    """Determine the display folder based on type and role."""
    if role == 'dimension':
        return 'Dimensions'
    if datatype in ('real', 'integer', 'number'):
        return 'Measures'
    if datatype in ('date', 'datetime'):
        return 'Time Intelligence'
    if datatype == 'boolean':
        return 'Flags'
    return 'Calculations'


def _process_sets_groups_bins(model, extra_objects, main_table_name, column_table_map):
    """Add sets, groups and bins as Power Query M columns (fallback: DAX calc cols)."""
    if not main_table_name:
        return

    main_table = None
    for table in model["model"]["tables"]:
        if table.get("name") == main_table_name:
            main_table = table
            break
    if not main_table:
        return

    existing_cols = {col.get("name", "") for col in main_table.get("columns", [])}
    m_steps = []  # Accumulated M steps

    # Sets -> boolean column
    for s in extra_objects.get('sets', []):
        set_name = s.get('name', '')
        if not set_name or set_name in existing_cols:
            continue

        members = s.get('members', [])
        formula = s.get('formula', '')

        if formula:
            dax_expr = formula
        elif members:
            escaped = [f'"{m}"' for m in members[:50]]
            dax_expr = f"'{main_table_name}'[{set_name}] IN {{{', '.join(escaped)}}}"
        else:
            dax_expr = 'TRUE()'

        m_expr = _dax_to_m_expression(dax_expr, main_table_name)
        if m_expr is not None:
            m_steps.append(m_transform_add_column(set_name, f'each {m_expr}', 'type logical'))
            main_table["columns"].append({
                "name": set_name,
                "dataType": "Boolean",
                "sourceColumn": set_name,
                "summarizeBy": "none",
                "displayFolder": "Sets"
            })
        else:
            main_table["columns"].append({
                "name": set_name,
                "dataType": "Boolean",
                "expression": dax_expr,
                "summarizeBy": "none",
                "isCalculated": True,
                "displayFolder": "Sets"
            })
        existing_cols.add(set_name)

    # Groups -> SWITCH / concatenation column
    for g in extra_objects.get('groups', []):
        group_name = g.get('name', '')
        if not group_name or group_name in existing_cols:
            continue

        group_type = g.get('group_type', 'values')
        members = g.get('members', {})
        source_field = g.get('source_field', '').replace('[', '').replace(']', '')
        source_fields = g.get('source_fields', [])

        if group_type == 'combined' and source_fields:
            calc_map_lookup = {}
            for ds in extra_objects.get('_datasources', []):
                for calc in ds.get('calculations', []):
                    raw = calc.get('name', '').replace('[', '').replace(']', '')
                    cap = calc.get('caption', raw)
                    calc_map_lookup[raw] = cap
            for table_obj in model.get('model', {}).get('tables', []):
                for col in table_obj.get('columns', []):
                    if col.get('isCalculated'):
                        col_name = col.get('name', '')
                        if col_name and col_name not in column_table_map:
                            column_table_map[col_name] = table_obj.get('name', main_table_name)
                for meas in table_obj.get('measures', []):
                    meas_name = meas.get('name', '')
                    if meas_name and meas_name not in column_table_map:
                        column_table_map[meas_name] = table_obj.get('name', main_table_name)

            parts = []
            for sf in source_fields:
                # Clean any derivation prefixes (yr:, tyr:, etc.)
                sf = _clean_field_ref(sf)
                resolved = calc_map_lookup.get(sf, sf)
                resolved = _clean_field_ref(resolved)
                table_ref = column_table_map.get(resolved, column_table_map.get(sf, main_table_name))
                escaped_col = resolved.replace(']', ']]')
                ref = f"'{table_ref}'[{escaped_col}]"
                if table_ref != main_table_name:
                    ref = f"RELATED({ref})"
                parts.append(ref)

            if len(parts) == 1:
                dax_expr = parts[0]
            else:
                dax_expr = ' & " | " & '.join(parts)

        elif members and source_field:
            table_ref = column_table_map.get(source_field, main_table_name)
            cases = []
            for label, values in members.items():
                for val in values:
                    cases.append(f'"{val}", "{label}"')

            if cases:
                dax_expr = f"SWITCH('{table_ref}'[{source_field}], {', '.join(cases)}, \"Other\")"
            else:
                dax_expr = f"'{table_ref}'[{source_field}]"
        else:
            dax_expr = '""'

        m_expr = _dax_to_m_expression(dax_expr, main_table_name)
        if m_expr is not None:
            m_steps.append(m_transform_add_column(group_name, f'each {m_expr}', 'type text'))
            main_table["columns"].append({
                "name": group_name,
                "dataType": "String",
                "sourceColumn": group_name,
                "summarizeBy": "none",
                "displayFolder": "Groups"
            })
        else:
            main_table["columns"].append({
                "name": group_name,
                "dataType": "String",
                "expression": dax_expr,
                "summarizeBy": "none",
                "isCalculated": True,
                "displayFolder": "Groups"
            })
        existing_cols.add(group_name)

    # Bins -> FLOOR column
    for b in extra_objects.get('bins', []):
        bin_name = b.get('name', '')
        if not bin_name or bin_name in existing_cols:
            continue

        source_field = b.get('source_field', '').replace('[', '').replace(']', '')
        bin_size = b.get('size', '10')

        if source_field:
            table_ref = column_table_map.get(source_field, main_table_name)
            dax_expr = f"FLOOR('{table_ref}'[{source_field}], {bin_size})"
        else:
            dax_expr = '0'

        m_expr = _dax_to_m_expression(dax_expr, main_table_name)
        if m_expr is not None:
            m_steps.append(m_transform_add_column(bin_name, f'each {m_expr}', 'type number'))
            main_table["columns"].append({
                "name": bin_name,
                "dataType": "Double",
                "sourceColumn": bin_name,
                "summarizeBy": "none",
                "displayFolder": "Bins"
            })
        else:
            main_table["columns"].append({
                "name": bin_name,
                "dataType": "Double",
                "expression": dax_expr,
                "summarizeBy": "none",
                "isCalculated": True,
                "displayFolder": "Bins"
            })
        existing_cols.add(bin_name)

    # Inject accumulated M steps into the partition
    if m_steps:
        _inject_m_steps_into_partition(main_table, m_steps)


def _apply_hierarchies(model, hierarchies, column_table_map):
    """Apply hierarchies (drill-paths) to the model."""
    if not hierarchies:
        return

    for h in hierarchies:
        h_name = h.get('name', '')
        levels = h.get('levels', [])
        if not h_name or not levels:
            continue

        first_level = levels[0]
        target_table_name = column_table_map.get(first_level, '')
        if not target_table_name:
            continue

        for table in model["model"]["tables"]:
            if table.get("name") == target_table_name:
                table_col_names = {col.get("name", "") for col in table.get("columns", [])}
                valid_levels = [l for l in levels if l in table_col_names]

                if valid_levels:
                    if "hierarchies" not in table:
                        table["hierarchies"] = []

                    hierarchy = {
                        "name": h_name,
                        "levels": [
                            {"name": lvl, "ordinal": idx, "column": lvl}
                            for idx, lvl in enumerate(valid_levels)
                        ]
                    }
                    table["hierarchies"].append(hierarchy)
                break


def _auto_date_hierarchies(model):
    """Auto-generate Year > Quarter > Month > Day hierarchies for date columns.

    For every date/dateTime column that does not already belong to a
    user-defined hierarchy, we create Power Query M columns
    (Date.Year, Date.QuarterOfYear, Date.Month, Date.Day)
    and a hierarchy definition on the same table.
    """
    DATE_TYPES = {'dateTime', 'date'}
    # (label, M function, BIM dataType, ordinal)
    PARTS = [
        ('Year', 'Date.Year', 'int64', 0),
        ('Quarter', 'Date.QuarterOfYear', 'int64', 1),
        ('Month', 'Date.Month', 'int64', 2),
        ('Day', 'Date.Day', 'int64', 3),
    ]

    for table in model.get('model', {}).get('tables', []):
        columns = table.get('columns', [])
        existing_hierarchies = table.get('hierarchies', [])

        # Collect columns already used in a hierarchy
        hier_cols = set()
        for h in existing_hierarchies:
            for lvl in h.get('levels', []):
                hier_cols.add(lvl.get('column', ''))

        existing_col_names = {c.get('name', '') for c in columns}

        m_steps = []  # M steps for this table

        for col in list(columns):  # iterate copy — we may append
            col_type = col.get('dataType', '')
            col_name = col.get('name', '')
            if col_type not in DATE_TYPES:
                continue
            if col_name in hier_cols:
                continue  # already in a user-defined hierarchy

            # Build hierarchy name scoped to the column
            hier_name = f"{col_name} Hierarchy"

            # Skip if we already auto-generated this one (idempotency)
            if any(h.get('name') == hier_name for h in existing_hierarchies):
                continue

            # Add M-based columns for the parts (skip if name clashes)
            calc_col_names = []
            for part_label, m_fn, dt, _ in PARTS:
                calc_name = f"{col_name} {part_label}"
                if calc_name in existing_col_names:
                    calc_col_names.append(calc_name)
                    continue  # already exists (e.g. from source extraction)

                m_steps.append(m_transform_add_column(
                    calc_name,
                    f'each {m_fn}([{col_name}])',
                    'Int64.Type'
                ))
                columns.append({
                    'name': calc_name,
                    'dataType': dt,
                    'sourceColumn': calc_name,
                    'isHidden': True,
                })
                existing_col_names.add(calc_name)
                calc_col_names.append(calc_name)

            # Create the hierarchy
            hierarchy = {
                'name': hier_name,
                'levels': [
                    {'name': PARTS[i][0], 'ordinal': i, 'column': calc_col_names[i]}
                    for i in range(len(calc_col_names))
                ],
            }
            if 'hierarchies' not in table:
                table['hierarchies'] = []
            table['hierarchies'].append(hierarchy)

        # Inject accumulated M steps into the table's partition
        if m_steps:
            _inject_m_steps_into_partition(table, m_steps)


def _create_parameter_tables(model, parameters, main_table_name):
    """Create What-If parameter tables for source parameters.

    - Range parameters (integer/real): GENERATESERIES(min, max, step) table
    - List parameters (string/boolean): DATATABLE with domain values
    - Any parameters (no domain): measure with default value on main table
    """
    if not parameters:
        return

    type_map = {
        'integer': ('int64', 'INTEGER'),
        'real': ('double', 'DOUBLE'),
        'date': ('dateTime', 'DATETIME'),
        'datetime': ('dateTime', 'DATETIME'),
        'boolean': ('boolean', 'BOOLEAN'),
        'string': ('string', 'STRING'),
    }

    for param in parameters:
        caption = param.get('caption', '')
        if not caption:
            continue

        datatype = param.get('datatype', 'string')
        default_value = param.get('value', '').strip('"')
        domain_type = param.get('domain_type', 'any')
        allowable_values = param.get('allowable_values', [])

        pbi_type, dax_type = type_map.get(datatype, ('string', 'STRING'))

        if datatype == 'string':
            default_expr = f'"{default_value}"'
        elif datatype == 'boolean':
            default_expr = default_value.upper() if default_value else 'TRUE'
        elif datatype in ('date', 'datetime'):
            # Convert #YYYY-MM-DD# date literal to DAX DATE()
            date_m = re.match(r'#(\d{4})-(\d{2})-(\d{2})#', default_value)
            if date_m:
                default_expr = f'DATE({int(date_m.group(1))}, {int(date_m.group(2))}, {int(date_m.group(3))})'
            else:
                default_expr = default_value if default_value else 'DATE(2024, 1, 1)'
        else:
            default_expr = default_value if default_value else '0'

        if domain_type == 'any' or not allowable_values:
            for table in model["model"]["tables"]:
                if table.get("name") == main_table_name:
                    if "measures" not in table:
                        table["measures"] = []
                    table["measures"].append({
                        "name": caption,
                        "expression": default_expr,
                        "annotations": [
                            {"name": "displayFolder", "value": "Parameters"}
                        ]
                    })
                    break
            continue

        table_expr = None
        col_name = caption

        if domain_type == 'range':
            range_info = next((v for v in allowable_values if v.get('type') == 'range'), None)
            if range_info:
                min_val = range_info.get('min', '0')
                max_val = range_info.get('max', '100')
                step = range_info.get('step', '') or '1'
                table_expr = f"GENERATESERIES({min_val}, {max_val}, {step})"
                col_name = "Value"

        elif domain_type == 'list':
            list_values = [v for v in allowable_values if v.get('type') != 'range']
            if list_values:
                if datatype == 'string':
                    rows = ', '.join(f'{{"{v.get("value", "")}"}}' for v in list_values)
                elif datatype == 'boolean':
                    rows = ', '.join(f'{{{v.get("value", "TRUE").upper()}}}' for v in list_values)
                else:
                    rows = ', '.join(f'{{{v.get("value", "0")}}}' for v in list_values)
                col_name = "Value"
                table_expr = f'DATATABLE("Value", {dax_type}, {{{rows}}})'

        if not table_expr:
            continue

        param_table = {
            "name": caption,
            "columns": [{
                "name": col_name,
                "dataType": pbi_type,
                "sourceColumn": col_name,
                "annotations": [
                    {"name": "displayFolder", "value": "Parameters"}
                ]
            }],
            "measures": [{
                "name": caption,
                "expression": f"SELECTEDVALUE('{caption}'[{col_name}], {default_expr})",
                "annotations": [
                    {"name": "displayFolder", "value": "Parameters"}
                ]
            }],
            "partitions": [{
                "name": caption,
                "mode": "import",
                "source": {
                    "type": "calculated",
                    "expression": table_expr
                }
            }]
        }

        model["model"]["tables"].append(param_table)

    # Deduplicate: remove parameter measures from other tables
    param_table_names = set()
    for param in parameters:
        caption = param.get('caption', '')
        domain_type = param.get('domain_type', 'any')
        if caption and domain_type in ('range', 'list') and param.get('allowable_values'):
            param_table_names.add(caption)

    if param_table_names:
        for table in model["model"]["tables"]:
            table_name = table.get("name", "")
            if table_name in param_table_names:
                continue
            if "measures" in table:
                table["measures"] = [
                    m for m in table["measures"]
                    if m.get("name", "") not in param_table_names
                ]


def _create_calculation_groups(model, parameters, main_table_name):
    """Create calculation group tables from parameters that switch between measures.

    A source parameter that selects from a list of known measure names maps to
    a Power BI calculation group: each selectable measure becomes a calculation
    item that runs ``CALCULATE(SELECTEDMEASURE())``.
    """
    if not parameters:
        return

    existing_tables = {t.get('name', '') for t in model['model']['tables']}

    # Collect all measure names across the model
    measure_names = set()
    for table in model['model']['tables']:
        for m in table.get('measures', []):
            measure_names.add(m.get('name', ''))

    for param in parameters:
        caption = param.get('caption', '')
        domain_type = param.get('domain_type', '')
        datatype = param.get('datatype', 'string')
        allowable_values = param.get('allowable_values', [])

        # Only string list parameters are candidates
        if datatype != 'string' or domain_type != 'list' or not allowable_values:
            continue

        matching_values = [
            v for v in allowable_values
            if v.get('type') != 'range' and v.get('value', '') in measure_names
        ]
        if len(matching_values) < 2:
            continue

        cg_name = f"{caption} CalcGroup"
        if cg_name in existing_tables:
            continue

        calc_items = []
        for idx, val in enumerate(matching_values):
            measure_ref = val.get('value', '')
            calc_items.append({
                "name": measure_ref,
                "expression": "CALCULATE(SELECTEDMEASURE())",
                "ordinal": idx,
            })

        cg_table = {
            "name": cg_name,
            "calculationGroup": {
                "columns": [{"name": caption, "dataType": "string",
                             "sourceColumn": caption}],
                "calculationItems": calc_items,
            },
            "columns": [{"name": caption, "dataType": "string",
                         "sourceColumn": caption}],
            "partitions": [{
                "name": cg_name,
                "mode": "import",
                "source": {"type": "calculationGroup"},
            }],
            "annotations": [
                {"name": "displayFolder", "value": "Calculation Groups"},
            ],
        }
        model['model']['tables'].append(cg_table)
        existing_tables.add(cg_name)


def _create_field_parameters(model, parameters, main_table_name, column_table_map):
    """Create field parameter tables from parameters that switch between columns.

    Field parameters in Power BI allow users to dynamically choose which column
    appears on a visual axis or slicer. This converts parameters whose
    allowable values match existing column names into PBI field parameter tables
    with ``NAMEOF()`` references.
    """
    if not parameters:
        return

    existing_tables = {t.get('name', '') for t in model['model']['tables']}

    # Collect all known column names and measure names
    all_columns = set()
    measure_names = set()
    for table in model['model']['tables']:
        for col in table.get('columns', []):
            all_columns.add(col.get('name', ''))
        for m in table.get('measures', []):
            measure_names.add(m.get('name', ''))

    for param in parameters:
        caption = param.get('caption', '')
        domain_type = param.get('domain_type', '')
        datatype = param.get('datatype', 'string')
        allowable_values = param.get('allowable_values', [])

        # Only string list parameters with column-like values
        if datatype != 'string' or domain_type != 'list' or not allowable_values:
            continue

        matching_cols = [
            v for v in allowable_values
            if v.get('type') != 'range' and v.get('value', '') in all_columns
        ]

        if len(matching_cols) < 2:
            continue
        # Skip if all values are measures (those become calc groups instead)
        if all(v.get('value', '') in measure_names for v in matching_cols):
            continue

        fp_name = f"{caption} FieldParam"
        if fp_name in existing_tables:
            continue

        # Build NAMEOF references for the field parameter DAX expression
        rows = []
        for idx, val in enumerate(matching_cols):
            col_name = val.get('value', '')
            col_table = column_table_map.get(col_name, main_table_name)
            rows.append(
                f"(NAMEOF('{col_table}'[{col_name}]), {idx}, \"{col_name}\")"
            )

        fp_expr = "{\n" + ",\n".join(rows) + "\n}"

        fp_table = {
            "name": fp_name,
            "columns": [
                {"name": caption, "dataType": "string",
                 "sourceColumn": caption,
                 "annotations": [{"name": "displayFolder",
                                  "value": "Field Parameters"}]},
                {"name": f"{caption}_Order", "dataType": "int64",
                 "sourceColumn": f"{caption}_Order", "isHidden": True},
                {"name": f"{caption}_Fields", "dataType": "string",
                 "sourceColumn": f"{caption}_Fields", "isHidden": True},
            ],
            "partitions": [{
                "name": fp_name,
                "mode": "import",
                "source": {
                    "type": "calculated",
                    "expression": fp_expr,
                },
            }],
            "annotations": [
                {"name": "displayFolder", "value": "Field Parameters"},
                {"name": "PBI_NavigationStepName", "value": "Navigation"},
                {"name": "ParameterMetadata",
                 "value": json.dumps({"version": 3, "kind": 2})},
            ],
        }
        model['model']['tables'].append(fp_table)
        existing_tables.add(fp_name)


def _create_rls_roles(model, user_filters, main_table_name, column_table_map):
    """Create Row-Level Security (RLS) roles from source user filters.

    Converts source security patterns to Power BI RLS roles:
    - User filter (explicit user->row mappings) -> RLS role with USERPRINCIPALNAME()
    - Calculated security (USERNAME/FULLNAME formulas) -> RLS role with DAX filter
    - ISMEMBEROF group patterns -> separate RLS role per group
    """
    if not user_filters:
        return

    if not main_table_name:
        tables = model.get('model', {}).get('tables', [])
        if tables:
            main_table_name = tables[0].get('name', 'Table')
        else:
            main_table_name = 'Table'

    roles = []
    role_names = set()

    for uf in user_filters:
        uf_type = uf.get('type', '')

        if uf_type == 'user_filter':
            filter_name = uf.get('name', 'UserFilter')
            column = uf.get('column', '')
            user_mappings = uf.get('user_mappings', [])
            filter_expression = uf.get('filter_expression', '')
            omit_fields = uf.get('omit_fields', [])
            reduce_values = uf.get('reduce_values', [])

            table_name = column_table_map.get(column, main_table_name)

            col_clean = column
            if ':' in col_clean:
                col_clean = col_clean.split(':')[-1]

            # If filter_expression is already provided (from _parse_section_access)
            if filter_expression and not user_mappings and not column:
                role_name = _unique_role_name(filter_name, role_names)
                role_names.add(role_name)

                role_entry = {
                    "name": role_name,
                    "modelPermission": "read",
                    "tablePermissions": [
                        {
                            "name": main_table_name,
                            "filterExpression": filter_expression
                        }
                    ]
                }

                # Add OMIT fields as migration note (Power BI OLS)
                if omit_fields:
                    role_entry["_omit_fields"] = omit_fields
                    role_entry["_migration_note"] = (
                        f"OMIT fields from Section Access: {', '.join(omit_fields)}. "
                        f"Implement as Object-Level Security (OLS) in Power BI."
                    )

                # Add reduce values as additional filter
                if reduce_values:
                    role_entry["_reduce_values"] = reduce_values

                roles.append(role_entry)
                continue

            if user_mappings:
                user_values = {}
                for mapping in user_mappings:
                    user = mapping.get('user', '')
                    val = mapping.get('value', '')
                    if user and val:
                        user_values.setdefault(user, []).append(val)

                or_clauses = []
                for user_email, values in user_values.items():
                    if len(values) == 1:
                        val_expr = f'[{col_clean}] = "{values[0]}"'
                    else:
                        val_list = ', '.join(f'"{v}"' for v in values)
                        val_expr = f'[{col_clean}] IN {{{val_list}}}'
                    or_clauses.append(
                        f'(USERPRINCIPALNAME() = "{user_email}" && {val_expr})'
                    )

                if or_clauses:
                    filter_dax = ' || '.join(or_clauses)
                else:
                    filter_dax = 'FALSE()'

                role_name = _unique_role_name(filter_name, role_names)
                role_names.add(role_name)

                role_entry = {
                    "name": role_name,
                    "modelPermission": "read",
                    "tablePermissions": [
                        {
                            "name": table_name,
                            "filterExpression": filter_dax
                        }
                    ],
                    "_migration_note": (
                        f"Migrated from source user filter '{filter_name}'. "
                        f"Each user is mapped to their allowed {col_clean} values inline. "
                        f"Consider creating a security table for dynamic RLS."
                    ),
                    "_user_mappings": user_mappings
                }

                if omit_fields:
                    role_entry["_omit_fields"] = omit_fields

                roles.append(role_entry)

            elif column:
                filter_dax = f"[{col_clean}] = USERPRINCIPALNAME()"
                role_name = _unique_role_name(filter_name, role_names)
                role_names.add(role_name)

                roles.append({
                    "name": role_name,
                    "modelPermission": "read",
                    "tablePermissions": [
                        {
                            "name": table_name,
                            "filterExpression": filter_dax
                        }
                    ]
                })

        elif uf_type == 'calculated_security':
            calc_name = uf.get('name', 'SecurityCalc')
            formula = uf.get('formula', '')
            functions_used = uf.get('functions_used', [])
            ismemberof_groups = uf.get('ismemberof_groups', [])

            if ismemberof_groups:
                for group in ismemberof_groups:
                    role_name = _unique_role_name(group, role_names)
                    role_names.add(role_name)

                    filter_dax = f"TRUE()  /* Members of role '{group}' have access */"

                    roles.append({
                        "name": role_name,
                        "modelPermission": "read",
                        "tablePermissions": [
                            {
                                "name": main_table_name,
                                "filterExpression": filter_dax
                            }
                        ],
                        "_migration_note": (
                            f"Migrated from ISMEMBEROF(\"{group}\"). "
                            f"Assign Azure AD group members to this RLS role."
                        )
                    })

            elif 'USERNAME' in functions_used or 'FULLNAME' in functions_used:
                dax_filter = convert_formula_to_dax(
                    formula,
                    table_name=main_table_name,
                    column_table_map=column_table_map
                )

                role_name = _unique_role_name(calc_name, role_names)
                role_names.add(role_name)

                # Determine which table the filter applies to
                cross_ref = re.search(r"'([^']+)'\[", dax_filter)
                perm_table = main_table_name
                if cross_ref:
                    ref_table = cross_ref.group(1)
                    model_table_names = {t.get("name", "") for t in model["model"]["tables"]}
                    if ref_table in model_table_names and ref_table != main_table_name:
                        perm_table = ref_table
                        dax_filter = dax_filter.replace(f"'{ref_table}'[", "[")

                roles.append({
                    "name": role_name,
                    "modelPermission": "read",
                    "tablePermissions": [
                        {
                            "name": perm_table,
                            "filterExpression": dax_filter
                        }
                    ],
                    "_migration_note": (
                        f"Migrated from source calculated security '{calc_name}'. "
                        f"Original formula: {formula}"
                    )
                })

    if roles:
        model["model"]["roles"] = roles
        print(f"    \u2713 {len(roles)} RLS role(s) created")


def _unique_role_name(base_name, existing_names):
    """Generate a unique role name, appending _N if needed."""
    clean = re.sub(r'[^\w\s-]', '', base_name).strip()
    if not clean:
        clean = 'Role'

    if clean not in existing_names:
        return clean

    counter = 2
    while f"{clean}_{counter}" in existing_names:
        counter += 1
    return f"{clean}_{counter}"


def _get_format_string(datatype):
    """Return the Power BI format string for a given type."""
    format_map = {
        'integer': '0',
        'real': '#,0.00',
        'currency': '$#,0.00',
        'percentage': '0.00%',
        'date': 'Short Date',
        'datetime': 'General Date',
        'boolean': 'True/False'
    }
    return format_map.get(datatype.lower(), '0')


def _convert_source_format_to_pbi(source_format):
    """Convert a source number format string to Power BI format string.

    Source formats:   #,##0.00  |  0.0%  |  $#,##0  |  0.000  |  #,##0
    PBI formats:      #,0.00   |  0.0%  |  $#,0    |  0.000  |  #,0

    Args:
        source_format: Source format string (from default-format attribute)

    Returns:
        str: Power BI format string, or empty string if no conversion needed
    """
    if not source_format:
        return ''

    fmt = source_format.strip()

    # Already a PBI-compatible format
    if fmt in ('0', '#,0', '#,0.00', '0.00%', '$#,0.00', 'General Date', 'Short Date'):
        return fmt

    # Percentage formats
    if '%' in fmt:
        # Normalize: source uses 0.0% or 0.00% etc.
        return fmt

    # Currency with symbol
    for symbol in ('$', '€', '£', '¥'):
        if symbol in fmt:
            # Convert ##0 pattern to PBI #,0 pattern
            cleaned = fmt.replace('##0', '#0').replace('###', '#').replace(',,', ',')
            # Ensure at least one digit placeholder
            if '0' not in cleaned:
                cleaned = cleaned + '0'
            return cleaned

    # Numeric formats
    # Source uses #,##0.00 → PBI uses #,0.00
    result = fmt
    # Convert #,##0 → #,0 pattern
    result = result.replace('#,##0', '#,0')
    result = result.replace('#,###', '#,#')
    # Handle plain 0 patterns
    if result and result[0] == '0':
        return result  # Already numeric

    return result if result != fmt else fmt


def _deactivate_ambiguous_paths(model):
    """
    Detect and deactivate relationships that create ambiguous paths.

    Power BI requires that the graph of active relationships forms a forest
    (tree per connected component) — i.e., no cycles when treated as undirected.
    If a cycle is detected, the least-important relationship is deactivated.

    Priority for deactivation (first deactivated):
      1. Auto-generated Calendar relationships (name starts with 'Calendar_')
      2. Inferred cross-table relationships (name starts with 'inferred_')
      3. Original source-extracted relationships (last resort)
    """
    relationships = model["model"]["relationships"]
    if not relationships:
        return

    # --- Union-Find -------------------------------------------------------
    parent = {}

    def find(x):
        while parent.get(x, x) != x:
            parent[x] = parent.get(parent[x], parent[x])  # path compression
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra == rb:
            return False          # cycle detected
        parent[ra] = rb
        return True

    # --- Sort relationships so the most important are added first ----------
    def _deactivation_priority(rel):
        """Lower value = more important = added to tree first."""
        name = rel.get('name', '')
        if name.startswith('Calendar_'):
            return 2   # auto-generated → deactivate first
        if name.startswith('inferred_'):
            return 1   # inferred → deactivate second
        return 0       # original source relationships → keep

    sorted_rels = sorted(relationships, key=_deactivation_priority)

    deactivated = []
    for rel in sorted_rels:
        if rel.get('isActive') == False:
            continue  # already inactive, skip
        from_t = rel.get('fromTable', '')
        to_t = rel.get('toTable', '')
        if not from_t or not to_t:
            continue
        if not union(from_t, to_t):
            # This edge creates a cycle → deactivate it
            rel['isActive'] = False
            deactivated.append(f"{from_t}.{rel.get('fromColumn','')} → "
                               f"{to_t}.{rel.get('toColumn','')}")

    for d in deactivated:
        print(f"  ⚠ Deactivated relationship (ambiguous path): {d}")


def _create_quick_table_calc_measures(model, worksheets, main_table_name, column_table_map):
    """Auto-generate DAX measures for quick table calculations.
    
    Detects fields with table_calc metadata (pcto, pctd, running_sum, rank, etc.)
    and creates corresponding DAX measures:
    - pcto (% of Total): DIVIDE(SUM([Field]), CALCULATE(SUM([Field]), ALL('Table')))
    - pctd (% Difference): DIVIDE(SUM([Field]) - CALCULATE(SUM([Field]), PREVIOUSDAY(...)), ...)
    - running_sum: CALCULATE(SUM([Field]), FILTER(ALL('Calendar'[Date]), ...))
    - running_avg, running_count, running_min, running_max: similar pattern
    - rank / rank_unique / rank_dense: RANKX(ALL('Table'), SUM([Field]))
    """
    if not worksheets:
        return
    
    # Find the main table to add measures to
    target_table = None
    for t in model["model"]["tables"]:
        if t.get("name") == main_table_name:
            target_table = t
            break
    if not target_table:
        return
    
    existing_measures = {m.get("name", "") for m in target_table.get("measures", [])}
    added = 0
    
    _AGG_MAP = {
        'sum': 'SUM', 'avg': 'AVERAGE', 'count': 'COUNT',
        'min': 'MIN', 'max': 'MAX', 'countd': 'DISTINCTCOUNT',
    }
    
    for ws in worksheets:
        for field in ws.get('fields', []):
            tc_type = field.get('table_calc')
            if not tc_type:
                continue
            
            field_name = field.get('name', '')
            tc_agg = field.get('table_calc_agg', 'sum')
            agg_func = _AGG_MAP.get(tc_agg, 'SUM')
            tbl = column_table_map.get(field_name, main_table_name)
            
            if tc_type == 'pcto':
                measure_name = f"% of Total {field_name}"
                if measure_name not in existing_measures:
                    expr = f"DIVIDE({agg_func}('{tbl}'[{field_name}]), CALCULATE({agg_func}('{tbl}'[{field_name}]), ALL('{tbl}')))"
                    target_table.setdefault("measures", []).append({
                        "name": measure_name,
                        "expression": expr,
                        "formatString": "0.00%",
                        "displayFolder": "Table Calculations"
                    })
                    existing_measures.add(measure_name)
                    added += 1
            
            elif tc_type == 'pctd':
                measure_name = f"% Difference {field_name}"
                if measure_name not in existing_measures:
                    base = f"{agg_func}('{tbl}'[{field_name}])"
                    prev = f"CALCULATE({base}, PREVIOUSDAY('Calendar'[Date]))"
                    expr = f"VAR _Current = {base} VAR _Previous = {prev} RETURN DIVIDE(_Current - _Previous, _Previous)"
                    target_table.setdefault("measures", []).append({
                        "name": measure_name,
                        "expression": expr,
                        "formatString": "0.00%",
                        "displayFolder": "Table Calculations"
                    })
                    existing_measures.add(measure_name)
                    added += 1
            
            elif tc_type.startswith('running_'):
                running_agg = tc_type.replace('running_', '')
                running_func = _AGG_MAP.get(running_agg, 'SUM')
                measure_name = f"Running {running_agg.title()} {field_name}"
                if measure_name not in existing_measures:
                    expr = (f"CALCULATE({running_func}('{tbl}'[{field_name}]), "
                            f"FILTER(ALL('Calendar'[Date]), 'Calendar'[Date] <= MAX('Calendar'[Date])))")
                    target_table.setdefault("measures", []).append({
                        "name": measure_name,
                        "expression": expr,
                        "formatString": "#,0.00",
                        "displayFolder": "Table Calculations"
                    })
                    existing_measures.add(measure_name)
                    added += 1
            
            elif tc_type in ('rank', 'rank_unique', 'rank_dense'):
                dense = ", DENSE" if tc_type == 'rank_dense' else ""
                measure_name = f"Rank {field_name}"
                if measure_name not in existing_measures:
                    expr = f"RANKX(ALL('{tbl}'), {agg_func}('{tbl}'[{field_name}]){dense})"
                    target_table.setdefault("measures", []).append({
                        "name": measure_name,
                        "expression": expr,
                        "formatString": "#,0",
                        "displayFolder": "Table Calculations"
                    })
                    existing_measures.add(measure_name)
                    added += 1
            
            elif tc_type == 'diff':
                measure_name = f"Difference {field_name}"
                if measure_name not in existing_measures:
                    base = f"{agg_func}('{tbl}'[{field_name}])"
                    prev = f"CALCULATE({base}, PREVIOUSDAY('Calendar'[Date]))"
                    expr = f"{base} - {prev}"
                    target_table.setdefault("measures", []).append({
                        "name": measure_name,
                        "expression": expr,
                        "formatString": "#,0.00",
                        "displayFolder": "Table Calculations"
                    })
                    existing_measures.add(measure_name)
                    added += 1
    
    if added:
        print(f"  ✓ {added} quick table calc measures generated")


def _add_date_table(model):
    """
    Add an automatic date table using Power Query M.

    Uses an M partition (not DAX calculated) to avoid "invalid column ID"
    errors when TMDL relationships reference columns inside
    calculated-table partitions.

    Links Calendar to ALL fact tables that have date columns
    (not just the first one).

    Supports customizable date range via model['_calendar_start'] and
    model['_calendar_end'] (default: 2020–2030).
    """
    cal_start = model.get('_calendar_start') or 2020
    cal_end = model.get('_calendar_end') or 2030

    calendar_m = (
        'let\n'
        f'    StartDate = #date({cal_start}, 1, 1),\n'
        f'    EndDate = #date({cal_end}, 12, 31),\n'
        '    DayCount = Duration.Days(EndDate - StartDate) + 1,\n'
        '    DateList = List.Dates(StartDate, DayCount, #duration(1, 0, 0, 0)),\n'
        '    #"Date Table" = Table.FromList(DateList, Splitter.SplitByNothing(), {"Date"}, null, ExtraValues.Error),\n'
        '    #"Changed Type" = Table.TransformColumnTypes(#"Date Table", {{"Date", type date}}),\n'
        '    #"Added Year" = Table.AddColumn(#"Changed Type", "Year", each Date.Year([Date]), Int64.Type),\n'
        '    #"Added Quarter" = Table.AddColumn(#"Added Year", "Quarter", each "Q" & Text.From(Date.QuarterOfYear([Date]))),\n'
        '    #"Added Month" = Table.AddColumn(#"Added Quarter", "Month", each Date.Month([Date]), Int64.Type),\n'
        '    #"Added MonthName" = Table.AddColumn(#"Added Month", "MonthName", each Date.MonthName([Date])),\n'
        '    #"Added Day" = Table.AddColumn(#"Added MonthName", "Day", each Date.Day([Date]), Int64.Type),\n'
        '    #"Added DayOfWeek" = Table.AddColumn(#"Added Day", "DayOfWeek", each Date.DayOfWeek([Date], Day.Monday) + 1, Int64.Type),\n'
        '    #"Added DayName" = Table.AddColumn(#"Added DayOfWeek", "DayName", each Date.DayOfWeekName([Date]))\n'
        'in\n'
        '    #"Added DayName"'
    )

    date_table = {
        "name": "Calendar",
        "isHidden": False,
        "columns": [
            {
                "name": "Date",
                "dataType": "DateTime",
                "isKey": True,
                "dataCategory": "DateTime",
                "formatString": "dd/mm/yyyy",
                "sourceColumn": "Date",
                "summarizeBy": "none"
            },
            {
                "name": "Year",
                "dataType": "int64",
                "dataCategory": "Years",
                "sourceColumn": "Year",
                "summarizeBy": "none"
            },
            {
                "name": "Quarter",
                "dataType": "string",
                "sourceColumn": "Quarter",
                "summarizeBy": "none"
            },
            {
                "name": "Month",
                "dataType": "int64",
                "dataCategory": "Months",
                "sourceColumn": "Month",
                "summarizeBy": "none"
            },
            {
                "name": "MonthName",
                "dataType": "string",
                "sourceColumn": "MonthName",
                "sortByColumn": "Month",
                "summarizeBy": "none"
            },
            {
                "name": "Day",
                "dataType": "int64",
                "dataCategory": "Days",
                "sourceColumn": "Day",
                "summarizeBy": "none"
            },
            {
                "name": "DayOfWeek",
                "dataType": "int64",
                "sourceColumn": "DayOfWeek",
                "summarizeBy": "none"
            },
            {
                "name": "DayName",
                "dataType": "string",
                "sourceColumn": "DayName",
                "sortByColumn": "DayOfWeek",
                "summarizeBy": "none"
            }
        ],
        "partitions": [
            {
                "name": "Calendar-Partition",
                "mode": "import",
                "source": {
                    "type": "m",
                    "expression": calendar_m
                }
            }
        ],
        "measures": []
    }

    value_expr = None
    # Find a SUM-based measure in any table for time intelligence
    for t in model["model"]["tables"]:
        if t["name"] == "Calendar":
            continue
        for ms in t.get("measures", []):
            expr = ms.get("expression", "")
            if re.match(r'^SUM\b', expr, re.IGNORECASE):
                value_expr = f'[{ms["name"]}]'
                break
        if value_expr:
            break

    time_intelligence_measures = []
    if value_expr:
        time_intelligence_measures = [
            {
                "name": "Year To Date",
                "expression": f"TOTALYTD({value_expr}, 'Calendar'[Date])",
                "formatString": "#,0.00",
                "displayFolder": "Time Intelligence"
            },
            {
                "name": "Previous Year",
                "expression": f"CALCULATE({value_expr}, SAMEPERIODLASTYEAR('Calendar'[Date]))",
                "formatString": "#,0.00",
                "displayFolder": "Time Intelligence"
            },
            {
                "name": "Year Over Year %",
                "expression": "DIVIDE([Year To Date] - [Previous Year], [Previous Year], 0)",
                "formatString": "0.00%",
                "displayFolder": "Time Intelligence"
            }
        ]

    date_table["measures"].extend(time_intelligence_measures)

    # Add Date hierarchy (Year → Quarter → Month → Day)
    date_table["hierarchies"] = [
        {
            "name": "Date Hierarchy",
            "levels": [
                {"name": "Year", "column": "Year", "ordinal": 0},
                {"name": "Quarter", "column": "Quarter", "ordinal": 1},
                {"name": "Month", "column": "MonthName", "ordinal": 2},
                {"name": "Day", "column": "Day", "ordinal": 3},
            ]
        }
    ]

    model["model"]["tables"].append(date_table)

    # Add relationships: Calendar[Date] -> each table's first date column
    for t in model["model"]["tables"]:
        tname = t.get("name", "")
        if tname == "Calendar":
            continue
        for col in t.get("columns", []):
            if col.get("dataType") == "DateTime" or col.get("dataCategory") == "DateTime":
                date_col_name = col.get("name", "")
                if date_col_name and not col.get("isCalculated", False):
                    model["model"]["relationships"].append({
                        "name": f"Calendar_{tname}_{date_col_name}",
                        "fromTable": tname,
                        "fromColumn": date_col_name,
                        "toTable": "Calendar",
                        "toColumn": "Date",
                        "crossFilteringBehavior": "oneDirection"
                    })
                    break  # one date column per table is enough


# ════════════════════════════════════════════════════════════════════
#  TMDL FILE WRITERS
# ════════════════════════════════════════════════════════════════════

def _quote_name(name):
    """Quote a TMDL name if needed (spaces, special characters).
    Internal apostrophes are escaped by doubling them ('')."""
    if re.search(r'[^a-zA-Z0-9_]', name):
        escaped = name.replace("'", "''")
        return f"'{escaped}'"
    return name


def _tmdl_datatype(bim_type):
    """Convert a type to TMDL type."""
    mapping = {
        'int64': 'int64', 'string': 'string', 'double': 'double',
        'decimal': 'decimal', 'boolean': 'boolean', 'datetime': 'dateTime',
        'binary': 'binary',
    }
    return mapping.get(bim_type.lower() if bim_type else '', 'string')


def _tmdl_summarize(summarize_by):
    """Convert summarizeBy to TMDL."""
    mapping = {
        'sum': 'sum',
        'none': 'none',
        'count': 'count',
        'average': 'average',
        'min': 'min',
        'max': 'max',
    }
    return mapping.get(str(summarize_by).lower(), 'none')


def _safe_filename(name):
    """Create a safe filename for a table."""
    safe = re.sub(r'[<>:"/\\|?*]', '_', name)
    return safe


# ════════════════════════════════════════════════════════════════════
#  THEME GENERATION
# ════════════════════════════════════════════════════════════════════

# Default Power BI color palette (used when source has no theme)
_DEFAULT_PBI_COLORS = [
    "#4E79A7", "#F28E2B", "#E15759", "#76B7B2",
    "#59A14F", "#EDC948", "#B07AA1", "#FF9DA7",
    "#9C755F", "#BAB0AC", "#86BCB6", "#8CD17D"
]


def generate_theme_json(theme_data=None):
    """
    Generate a Power BI theme.json from extracted dashboard theme data.

    Args:
        theme_data: dict with 'colors' (list of hex), 'font_family', 'styles'
                    from theme extraction

    Returns:
        dict: Power BI theme definition
    """
    colors = _DEFAULT_PBI_COLORS
    font_family = "Segoe UI"

    if theme_data:
        t_colors = theme_data.get('colors', [])
        if t_colors:
            # Filter valid hex colors
            valid = [c for c in t_colors if isinstance(c, str) and c.startswith('#')]
            if valid:
                colors = valid[:12]
                # Pad to 12 if fewer
                while len(colors) < 12:
                    colors.append(_DEFAULT_PBI_COLORS[len(colors) % len(_DEFAULT_PBI_COLORS)])
        t_font = theme_data.get('font_family', '')
        if t_font:
            font_family = t_font

    theme = {
        "name": "Qlik Migration Theme",
        "dataColors": colors,
        "background": "#FFFFFF",
        "foreground": "#252423",
        "tableAccent": colors[0] if colors else "#4E79A7",
        "textClasses": {
            "callout": {
                "fontSize": 28,
                "fontFace": font_family,
                "color": "#252423"
            },
            "title": {
                "fontSize": 12,
                "fontFace": font_family,
                "color": "#252423"
            },
            "header": {
                "fontSize": 12,
                "fontFace": font_family,
                "color": "#252423"
            },
            "label": {
                "fontSize": 10,
                "fontFace": font_family,
                "color": "#666666"
            }
        },
        "visualStyles": {
            "*": {
                "*": {
                    "*": [{
                        "fontFamily": font_family,
                        "wordWrap": True
                    }]
                }
            }
        }
    }

    return theme


def _write_tmdl_files(model_data, output_dir):
    """
    Write the complete TMDL file structure from a semantic model.

    Args:
        model_data: dict -- the full model (with 'model' key)
        output_dir: str -- path to the SemanticModel folder

    Returns:
        str -- path to the created definition/ folder
    """
    model = model_data.get('model', model_data)

    def_dir = os.path.join(output_dir, 'definition')
    os.makedirs(def_dir, exist_ok=True)

    tables = model.get('tables', [])
    relationships = model.get('relationships', [])
    roles = model.get('roles', [])
    culture = model.get('culture', 'en-US')

    # 1. database.tmdl
    _write_database_tmdl(def_dir, model)

    # 2. model.tmdl
    _write_model_tmdl(def_dir, model, tables, roles)

    # 3. relationships.tmdl
    _write_relationships_tmdl(def_dir, relationships)

    # 4. expressions.tmdl (with datasource parameters)
    _write_expressions_tmdl(def_dir, tables, datasources=model.get('_datasources'),
                            output_dir=output_dir)

    # 5. roles.tmdl
    if roles:
        _write_roles_tmdl(def_dir, roles)

    # 6. tables/*.tmdl
    tables_dir = os.path.join(def_dir, 'tables')
    os.makedirs(tables_dir, exist_ok=True)

    # Clean stale table files from previous runs
    expected_files = set()
    for table in tables:
        tname = table.get('name', 'Table')
        expected_files.add(tname + '.tmdl')
    for existing in os.listdir(tables_dir):
        if existing.endswith('.tmdl') and existing not in expected_files:
            os.remove(os.path.join(tables_dir, existing))

    for table in tables:
        _write_table_tmdl(tables_dir, table)

    # 7. diagramLayout.json (empty — Power BI Desktop fills it on first open)
    diagram_path = os.path.join(def_dir, 'diagramLayout.json')
    with open(diagram_path, 'w', encoding='utf-8') as f:
        json.dump({}, f)

    # 8. perspectives.tmdl (auto-generated from table groupings)
    perspectives = model.get('perspectives', [])
    if not perspectives and len(tables) > 2:
        # Auto-generate a "Full Model" perspective referencing all tables
        perspectives = [{
            "name": "Full Model",
            "tables": [t.get('name', '') for t in tables]
        }]
    if perspectives:
        _write_perspectives_tmdl(def_dir, perspectives)

    # 9. cultures/*.tmdl (model culture)
    if culture and culture != 'en-US':
        cultures_dir = os.path.join(def_dir, 'cultures')
        os.makedirs(cultures_dir, exist_ok=True)
        _write_culture_tmdl(cultures_dir, culture, tables)

    # 10. expressions/*.pq (Power Query M files — one per table)
    _write_power_query_files(def_dir, tables, output_dir=output_dir)

    return def_dir


def _write_perspectives_tmdl(def_dir, perspectives):
    """
    Write perspectives.tmdl for multi-audience model views.

    Each perspective lists the tables visible from that viewpoint,
    allowing different user groups to see relevant subsets.

    Args:
        def_dir: Path to the definition/ folder
        perspectives: List of dicts with 'name' and 'tables' keys
    """
    lines = []
    for persp in perspectives:
        p_name = persp.get('name', 'Default')
        lines.append(f"perspective {_quote_name(p_name)}")
        for table_ref in persp.get('tables', []):
            tbl_name = table_ref if isinstance(table_ref, str) else table_ref.get('name', '')
            if tbl_name:
                lines.append(f"\tperspectiveTable {_quote_name(tbl_name)}")
        lines.append("")

    filepath = os.path.join(def_dir, 'perspectives.tmdl')
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))


def _write_culture_tmdl(cultures_dir, culture_name, tables):
    """
    Write a culture TMDL file with linguistic metadata.

    Generates translation entries for all table and column names
    in the model for the specified culture/locale.

    Args:
        cultures_dir: Path to the cultures/ folder
        culture_name: Locale string (e.g. 'fr-FR')
        tables: List of table definitions (for generating metadata entries)
    """
    lines = [f"culture {_quote_name(culture_name)}"]

    # Generate linguistic metadata entries for tables and columns
    lines.append("\tlinguisticMetadata =")
    lines.append('\t\t```')
    metadata = {
        "Version": "1.0.0",
        "Language": culture_name,
        "DynamicImprovement": "HighConfidence"
    }
    lines.append(f'\t\t\t{json.dumps(metadata, ensure_ascii=False)}')
    lines.append('\t\t\t```')
    lines.append("")

    filepath = os.path.join(cultures_dir, f'{culture_name}.tmdl')
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))


def _write_database_tmdl(def_dir, model):
    """Generate database.tmdl."""
    compat = model.get('compatibilityLevel', 1567)
    if compat < 1600:
        compat = 1600

    content = f"database\n\tcompatibilityLevel: {compat}\n\n"

    filepath = os.path.join(def_dir, 'database.tmdl')
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)


def _write_model_tmdl(def_dir, model, tables, roles=None):
    """Generate model.tmdl."""
    culture = model.get('culture', 'en-US')
    perspectives = model.get('perspectives', [])

    lines = []
    lines.append("model Model")
    lines.append(f"\tculture: {culture}")
    lines.append("\tdefaultPowerBIDataSourceVersion: powerBI_V3")
    lines.append("\tsourceQueryCulture: en-US")
    lines.append("\tdataAccessOptions")
    lines.append("\t\tlegacyRedirects")
    lines.append("\t\treturnErrorValuesAsNull")
    lines.append("")

    # Table order annotation
    table_names = [t.get('name', '') for t in tables]
    table_names_json = '["' + '","'.join(table_names) + '"]'
    lines.append(f"annotation PBI_QueryOrder = {table_names_json}")
    lines.append("")

    # Ref tables
    for table in tables:
        tname = _quote_name(table.get('name', ''))
        lines.append(f"ref table {tname}")

    lines.append("")

    # Ref expression for the DataFolder parameter
    lines.append("ref expression DataFolder")
    lines.append("")

    # Ref roles (RLS)
    if roles:
        for role in roles:
            rname = _quote_name(role.get('name', ''))
            lines.append(f"ref role {rname}")
        lines.append("")

    # Ref perspectives
    if perspectives:
        for persp in perspectives:
            pname = _quote_name(persp.get('name', 'Default'))
            lines.append(f"ref perspective {pname}")
        lines.append("")

    # Ref culture
    if culture and culture != 'en-US':
        lines.append(f"ref culture {_quote_name(culture)}")
        lines.append("")

    content = '\n'.join(lines) + '\n'

    filepath = os.path.join(def_dir, 'model.tmdl')
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)


def _write_expressions_tmdl(def_dir, tables, datasources=None, output_dir=None):
    """Generate expressions.tmdl with M parameters.

    Creates parameterized data source expressions:
    - DataFolder: for file-based data sources
    - ServerName: for server-based connections (SQL, Oracle, PostgreSQL, etc.)
    - DatabaseName: for database-based connections

    These M parameters allow easy switching between dev/staging/prod environments.
    """
    file_paths = []
    server_names = set()
    database_names = set()

    for table in tables:
        for partition in table.get('partitions', []):
            source = partition.get('source', {})
            if isinstance(source, dict):
                expr = source.get('expression', '')
            elif isinstance(source, str):
                expr = source
            else:
                continue

            for m in re.finditer(r'DataFolder\s*&\s*"\\([^"]+)"', expr):
                file_paths.append(m.group(1))
            for m in re.finditer(r'File\.Contents\("([^"]+)"\)', expr):
                file_paths.append(m.group(1))

            # Detect server/database references from M queries
            for m in re.finditer(r'(?:Sql\.Database|PostgreSQL\.Database|Oracle\.Database|Mysql\.Database)\s*\(\s*"([^"]+)"\s*,\s*"([^"]+)"', expr):
                server_names.add(m.group(1))
                database_names.add(m.group(2))
            for m in re.finditer(r'(?:Snowflake\.Databases|AmazonRedshift\.Database|GoogleBigQuery\.Database)\s*\(\s*"([^"]+)"', expr):
                server_names.add(m.group(1))

    # Also extract from datasource connection metadata
    if datasources:
        for ds in (datasources if isinstance(datasources, list) else [datasources]):
            conn = ds.get('connection', {})
            server = conn.get('server', conn.get('host', ''))
            db = conn.get('dbname', conn.get('database', ''))
            if server:
                server_names.add(server)
            if db:
                database_names.add(db)

    default_folder = "C:\\\\Data"

    if file_paths:
        normalized = [p.replace('\\', '/') for p in file_paths]

        if len(normalized) == 1:
            parts = normalized[0].rsplit('/', 1)
            common_dir = parts[0] if len(parts) > 1 else ''
        else:
            common = os.path.commonprefix(normalized)
            if '/' in common:
                common_dir = common[:common.rfind('/')]
            else:
                common_dir = ''

        if common_dir:
            default_folder = "C:\\\\" + common_dir.replace('/', '\\\\')

    # If output_dir is provided, set DataFolder to the data/ subdirectory
    # next to the .pbip file (two levels up from definition/)
    if output_dir:
        project_dir = os.path.dirname(os.path.dirname(def_dir))
        data_dir = os.path.join(project_dir, 'data')
        default_folder = data_dir.replace('\\', '\\\\')

    lines = []
    lines.append(f'expression DataFolder = "{default_folder}" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]')
    lines.append("")

    # Add server/database M parameters for easy environment switching
    if server_names:
        default_server = sorted(server_names)[0]
        lines.append(f'expression ServerName = "{default_server}" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]')
        lines.append("")

    if database_names:
        default_db = sorted(database_names)[0]
        lines.append(f'expression DatabaseName = "{default_db}" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]')
        lines.append("")

    content = '\n'.join(lines) + '\n'

    filepath = os.path.join(def_dir, 'expressions.tmdl')
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)


def _write_power_query_files(def_dir, tables, output_dir=None):
    """Write Power Query M expressions to dedicated .pq files.

    Creates an ``expressions/`` folder under ``definition/`` and writes
    each table's M query as a separate ``.pq`` file.  This allows
    editing M queries independently in VS Code or other editors while
    the TMDL partition still holds the canonical copy.

    Args:
        def_dir: Path to the ``definition/`` folder.
        tables: List of table dicts from the semantic model.
        output_dir: Optional path to the semantic model output folder.
            When provided, files are also mirrored to
            ``<project_root>/power_query/*.pq``.
    """
    expressions_dir = os.path.join(def_dir, 'expressions')
    project_power_query_dir = None
    if output_dir:
        project_root = os.path.dirname(output_dir)
        project_power_query_dir = os.path.join(project_root, 'power_query')
    written = 0

    for table in tables:
        table_name = table.get('name', '')
        if not table_name:
            continue

        for partition in table.get('partitions', []):
            source = partition.get('source', {})
            source_type = source.get('type', 'm')
            expression = source.get('expression', '')

            if not expression or source_type == 'calculated':
                continue

            # Lazily create the expressions directory
            if written == 0:
                os.makedirs(expressions_dir, exist_ok=True)
                if project_power_query_dir:
                    os.makedirs(project_power_query_dir, exist_ok=True)

            safe_name = _safe_filename(table_name)
            pq_path = os.path.join(expressions_dir, f'{safe_name}.pq')
            with open(pq_path, 'w', encoding='utf-8') as f:
                f.write(f'// Power Query M expression for table: {table_name}\n')
                f.write(f'// Auto-generated by Qlik-to-Power BI migration\n\n')
                f.write(expression)
                if not expression.endswith('\n'):
                    f.write('\n')

            if project_power_query_dir:
                mirror_path = os.path.join(project_power_query_dir, f'{safe_name}.pq')
                with open(mirror_path, 'w', encoding='utf-8') as f:
                    f.write(f'// Power Query M expression for table: {table_name}\n')
                    f.write(f'// Auto-generated by Qlik-to-Power BI migration\n\n')
                    f.write(expression)
                    if not expression.endswith('\n'):
                        f.write('\n')
            written += 1
            break  # One .pq file per table (first partition)


def _write_roles_tmdl(def_dir, roles):
    """Generate roles.tmdl with RLS role definitions."""
    if not roles:
        return

    lines = []

    for role in roles:
        role_name = _quote_name(role.get('name', 'DefaultRole'))
        model_permission = role.get('modelPermission', 'read')

        lines.append(f"role {role_name}")
        lines.append(f"\tmodelPermission: {model_permission}")

        migration_note = role.get('_migration_note', '')
        if migration_note:
            note_escaped = migration_note.replace('"', '\\"')
            lines.append(f'\tannotation MigrationNote = "{note_escaped}"')

        lines.append("")

        for tp in role.get('tablePermissions', []):
            tp_name = tp.get('name', '') or ''
            if not tp_name:
                continue
            table_name = _quote_name(tp_name)
            filter_expr = tp.get('filterExpression', '')

            lines.append(f"\ttablePermission {table_name}")

            if filter_expr:
                filter_clean = filter_expr.replace('\n', ' ').replace('\r', ' ').strip()
                lines.append(f"\t\tfilterExpression = {filter_clean}")

            lines.append("")

    content = '\n'.join(lines) + '\n'

    filepath = os.path.join(def_dir, 'roles.tmdl')
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)


def _write_relationships_tmdl(def_dir, relationships):
    """Generate relationships.tmdl."""
    if not relationships:
        filepath = os.path.join(def_dir, 'relationships.tmdl')
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("")
        return

    lines = []

    for rel in relationships:
        rel_id = rel.get('name', str(uuid.uuid4()))
        try:
            uuid.UUID(rel_id)
        except ValueError:
            rel_id = str(uuid.uuid4())

        from_table = _quote_name(rel.get('fromTable', ''))
        from_col = _quote_name(rel.get('fromColumn', ''))
        to_table = _quote_name(rel.get('toTable', ''))
        to_col = _quote_name(rel.get('toColumn', ''))

        lines.append(f"relationship {rel_id}")
        lines.append(f"\tfromColumn: {from_table}.{from_col}")
        lines.append(f"\ttoColumn: {to_table}.{to_col}")

        from_card = rel.get('fromCardinality', '')
        to_card = rel.get('toCardinality', '')
        if from_card == 'many' and to_card == 'many':
            lines.append("\tfromCardinality: many")
            lines.append("\ttoCardinality: many")
        elif from_card == 'one' and to_card == 'one':
            lines.append("\tfromCardinality: one")
            lines.append("\ttoCardinality: one")
        elif from_card == 'one' and to_card == 'many':
            lines.append("\tfromCardinality: one")
            lines.append("\ttoCardinality: many")
        elif from_card == 'many' and to_card == 'one':
            pass  # default in TMDL — omit for brevity

        cfb = rel.get('crossFilteringBehavior', 'oneDirection')
        lines.append(f"\tcrossFilteringBehavior: {cfb}")

        # Security filtering — default oneDirection (safe)
        sfb = rel.get('securityFilteringBehavior', '')
        if sfb and sfb != 'oneDirection':
            lines.append(f"\tsecurityFilteringBehavior: {sfb}")

        if rel.get('isActive') == False:
            lines.append("\tisActive: false")

        lines.append("")

    content = '\n'.join(lines) + '\n'

    filepath = os.path.join(def_dir, 'relationships.tmdl')
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)


def _write_table_tmdl(tables_dir, table):
    """Generate a {table_name}.tmdl file."""
    table_name = table.get('name', 'Table')
    tname_quoted = _quote_name(table_name)

    lines = []
    lines.append(f"table {tname_quoted}")
    lines.append(f"\tlineageTag: {uuid.uuid4()}")

    if table.get('isHidden', False):
        lines.append("\tisHidden")

    lines.append("")

    # Measures (before columns, as in PBI Hero reference)
    for measure in table.get('measures', []):
        _write_measure(lines, measure)

    # Columns
    for column in table.get('columns', []):
        _write_column(lines, column)

    # Hierarchies
    for hierarchy in table.get('hierarchies', []):
        _write_hierarchy(lines, hierarchy)

    # Partition
    for partition in table.get('partitions', []):
        _write_partition(lines, table_name, partition)

    # Incremental refresh policy (if configured)
    refresh_policy = table.get('refreshPolicy')
    if refresh_policy:
        _write_refresh_policy(lines, refresh_policy)

    # Annotations
    lines.append("\tannotation PBI_ResultType = Table")
    lines.append("")

    content = '\n'.join(lines) + '\n'

    filename = _safe_filename(table_name) + '.tmdl'
    filepath = os.path.join(tables_dir, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)


def _write_measure(lines, measure):
    """Write a measure in TMDL."""
    mname = _quote_name(measure.get('name', 'Measure'))
    expression = measure.get('expression') or '0'

    if '\n' in expression:
        lines.append(f"\tmeasure {mname} = ```")
        for expr_line in expression.split('\n'):
            lines.append(f"\t\t\t{expr_line}")
        lines.append("\t\t\t```")
    else:
        lines.append(f"\tmeasure {mname} = {expression}")

    fmt = measure.get('formatString', '')
    if fmt and fmt != '0':
        lines.append(f"\t\tformatString: {fmt}")

    folder = measure.get('displayFolder', '')
    if folder:
        lines.append(f"\t\tdisplayFolder: {folder}")

    desc = measure.get('description', '')
    if desc:
        lines.append(f"\t\tdescription: {desc}")

    if measure.get('isHidden', False):
        lines.append("\t\tisHidden")

    lines.append(f"\t\tlineageTag: {uuid.uuid4()}")
    lines.append("")


def _write_column_properties(lines, column):
    """Write shared column properties (formatString, lineageTag, summarizeBy, etc.)."""
    fmt = column.get('formatString', '')
    if fmt:
        lines.append(f"\t\tformatString: {fmt}")

    lines.append(f"\t\tlineageTag: {uuid.uuid4()}")

    summarize = _tmdl_summarize(column.get('summarizeBy', 'none'))
    lines.append(f"\t\tsummarizeBy: {summarize}")


def _write_column_flags(lines, column):
    """Write optional column flags (isHidden, isKey, dataCategory, etc.)."""
    if column.get('isHidden', False):
        lines.append("\t\tisHidden")
    if column.get('isKey', False):
        lines.append("\t\tisKey")
    data_category = column.get('dataCategory', '')
    if data_category:
        lines.append(f"\t\tdataCategory: {data_category}")
    description = column.get('description', '')
    if description:
        lines.append(f"\t\tdescription: {description}")
    display_folder = column.get('displayFolder', '')
    if display_folder:
        lines.append(f"\t\tdisplayFolder: {display_folder}")
    sort_by = column.get('sortByColumn', '')
    if sort_by:
        lines.append(f"\t\tsortByColumn: {_quote_name(sort_by)}")

    lines.append("")
    lines.append("\t\tannotation SummarizationSetBy = Automatic")
    lines.append("")


def _write_column(lines, column):
    """Write a column in TMDL (physical or calculated)."""
    col_name = column.get('name', 'Column')
    cname_quoted = _quote_name(col_name)
    data_type = _tmdl_datatype(column.get('dataType', 'string'))
    expression = column.get('expression', '')
    is_calculated = column.get('isCalculated', False)

    if is_calculated and expression:
        if '\n' in expression:
            lines.append(f"\tcolumn {cname_quoted} = ```")
            for expr_line in expression.split('\n'):
                lines.append(f"\t\t\t{expr_line}")
            lines.append("\t\t\t```")
        else:
            lines.append(f"\tcolumn {cname_quoted} = {expression}")
        lines.append(f"\t\tdataType: {data_type}")
        _write_column_properties(lines, column)
        _write_column_flags(lines, column)
    else:
        lines.append(f"\tcolumn {cname_quoted}")
        lines.append(f"\t\tdataType: {data_type}")
        _write_column_properties(lines, column)

        source_col = column.get('sourceColumn', col_name)
        source_col_quoted = _quote_name(source_col) if re.search(r'[^a-zA-Z0-9_]', source_col) else source_col
        lines.append(f"\t\tsourceColumn: {source_col_quoted}")
        _write_column_flags(lines, column)


def _write_hierarchy(lines, hierarchy):
    """Write a hierarchy in TMDL."""
    h_name = _quote_name(hierarchy.get('name', 'Hierarchy'))
    levels = hierarchy.get('levels', [])

    lines.append(f"\thierarchy {h_name}")
    lines.append(f"\t\tlineageTag: {uuid.uuid4()}")
    lines.append("")

    for level in levels:
        level_name = _quote_name(level.get('name', 'Level'))
        col_name = _quote_name(level.get('column', level.get('name', '')))
        ordinal = level.get('ordinal', 0)

        lines.append(f"\t\tlevel {level_name}")
        lines.append(f"\t\t\tordinal: {ordinal}")
        lines.append(f"\t\t\tcolumn: {col_name}")
        lines.append(f"\t\t\tlineageTag: {uuid.uuid4()}")
        lines.append("")

    lines.append("")


def _write_refresh_policy(lines, policy):
    """Write an incremental refresh policy in TMDL format.

    The policy dict should contain:
      - incrementalGranularity: 'Day' | 'Month' | 'Quarter' | 'Year'
      - incrementalPeriods: int (number of periods to refresh)
      - rollingWindowGranularity: 'Day' | 'Month' | 'Quarter' | 'Year'
      - rollingWindowPeriods: int (total window size)
      - pollingExpression: M expression for the date column (optional)
      - sourceExpression: M source expression (optional)
    """
    lines.append("\trefreshPolicy")
    gran = policy.get('incrementalGranularity', 'Day')
    inc_periods = policy.get('incrementalPeriods', 1)
    rw_gran = policy.get('rollingWindowGranularity', 'Month')
    rw_periods = policy.get('rollingWindowPeriods', 12)

    lines.append(f"\t\tincrementalGranularity: {gran}")
    lines.append(f"\t\tincrementalPeriods: {inc_periods}")
    lines.append(f"\t\trollingWindowGranularity: {rw_gran}")
    lines.append(f"\t\trollingWindowPeriods: {rw_periods}")

    # Polling expression (the date column to filter on)
    polling = policy.get('pollingExpression', '')
    if polling:
        lines.append(f"\t\tpollingExpression =")
        for pl in polling.split('\n'):
            lines.append(f"\t\t\t\t{pl}")

    # Source expression (the M query with RangeStart/RangeEnd parameters)
    source_expr = policy.get('sourceExpression', '')
    if source_expr:
        lines.append(f"\t\tsourceExpression =")
        for sl in source_expr.split('\n'):
            lines.append(f"\t\t\t\t{sl}")

    lines.append("")


def detect_refresh_policy(table, datasources=None):
    """Auto-detect an incremental refresh policy for a table.

    If the table has a DateTime column and comes from a relational data source,
    generate default policy settings. Users should refine these.

    Args:
        table: Table dict with 'columns' list.
        datasources: Optional list of datasource dicts for connection type detection.

    Returns:
        dict with policy settings, or None if not applicable.
    """
    date_cols = []
    for col in table.get('columns', []):
        dt = (col.get('dataType') or col.get('type') or '').lower()
        name = (col.get('name') or '').lower()
        if 'date' in dt or 'datetime' in dt or 'timestamp' in dt:
            date_cols.append(col)
        elif any(kw in name for kw in ('date', 'datetime', 'timestamp', 'created_at', 'updated_at')):
            date_cols.append(col)

    if not date_cols:
        return None

    # Pick the best candidate date column
    best = date_cols[0]
    for c in date_cols:
        cn = (c.get('name') or '').lower()
        if any(kw in cn for kw in ('updated', 'modified', 'last_')):
            best = c
            break

    col_name = best.get('name', 'Date')

    # Build M polling expression
    polling = f'let\n    currentDate = DateTime.LocalNow(),\n    #"MaxDate" = Sql.Database("server", "db"){{[Schema="dbo",Item="{table.get("name", "Table")}"]}}[{col_name}],\n    maxVal = List.Max(#"MaxDate")\nin\n    maxVal'

    return {
        'incrementalGranularity': 'Day',
        'incrementalPeriods': 3,
        'rollingWindowGranularity': 'Month',
        'rollingWindowPeriods': 12,
        'pollingExpression': polling,
        'sourceExpression': '',
        'dateColumn': col_name,
    }


def _write_partition(lines, table_name, partition):
    """Write a partition in TMDL."""
    part_name = f"{table_name}-{uuid.uuid4()}"
    mode = partition.get('mode', 'import')
    source = partition.get('source', {})
    source_type = source.get('type', 'm')
    expression = source.get('expression', '')

    lines.append(f"\tpartition {_quote_name(part_name)} = {source_type}")
    lines.append(f"\t\tmode: {mode}")

    if expression:
        if source_type == 'calculated':
            expr_clean = expression.replace('\r\n', '\n').replace('\r', '\n')
            if '\n' in expr_clean:
                lines.append("\t\tsource = ```")
                for expr_line in expr_clean.split('\n'):
                    lines.append(f"\t\t\t\t{expr_line}")
                lines.append("\t\t\t\t```")
            else:
                lines.append(f"\t\tsource = {expr_clean}")
        else:
            lines.append(f"\t\tsource =")
            for expr_line in expression.split('\n'):
                lines.append(f"\t\t\t\t{expr_line}")
    else:
        lines.append(f"\t\tsource =")
        lines.append("\t\t\t\tlet")
        lines.append("\t\t\t\t\tSource = #table(type table [], {})")
        lines.append("\t\t\t\t\t// TODO: Configure data source — replace with actual connection")
        lines.append("\t\t\t\tin")
        lines.append("\t\t\t\t\tSource")

    lines.append("")
