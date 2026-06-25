"""
Datasource extraction bridge — Qlik-to-Power BI type/formula/M adapters.

The powerbi_import/ generation layer (tmdl_generator.py) imports three
functions from ``datasource_extractor``:

    generate_power_query_m(connection, table)
    convert_formula_to_dax(formula, ...)
    map_to_powerbi_type(datatype)

Backward-compatible aliases (``convert_tableau_formula_to_dax``,
``map_tableau_to_powerbi_type``) are kept for existing call-sites.
"""

import os
import sys

# Add project root to sys.path for package imports
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from qlik_export.dax_converter import (
    convert_qlik_expression_to_dax as _convert_qlik_expression_to_dax,
    QLIK_TO_DAX_TYPE,
    convert_qlik_type_to_dax,
)
from qlik_export.m_query_generator import generate_m_query
from qlik_export.m_query_builder import inject_m_steps


# ── Type mapping ─────────────────────────────────────────────────

# Power BI TMDL data types keyed by Qlik type names
_QLIK_TO_PBI_TYPE = {
    'text': 'String',
    'string': 'String',
    'num': 'Double',
    'number': 'Double',
    'numeric': 'Double',
    'real': 'Double',
    'double': 'Double',
    'integer': 'Int64',
    'int': 'Int64',
    'int64': 'Int64',
    'money': 'Decimal',
    'currency': 'Decimal',
    'decimal': 'Decimal',
    'date': 'DateTime',
    'timestamp': 'DateTime',
    'datetime': 'DateTime',
    'datetype': 'DateTime',
    'time': 'DateTime',
    'boolean': 'Boolean',
    'dual': 'String',
}


def map_to_powerbi_type(datatype):
    """Map a Qlik data type string to the corresponding Power BI TMDL type."""
    if not datatype:
        return 'String'
    return _QLIK_TO_PBI_TYPE.get(datatype.lower(), 'String')


# Backward-compatible aliases
map_qlik_to_powerbi_type = map_to_powerbi_type


def map_tableau_to_powerbi_type(*args, **kwargs):
    """Deprecated — use ``map_to_powerbi_type`` instead."""
    import warnings
    warnings.warn(
        "map_tableau_to_powerbi_type is deprecated; use map_to_powerbi_type.",
        DeprecationWarning, stacklevel=2,
    )
    return map_to_powerbi_type(*args, **kwargs)


# ── DAX conversion ──────────────────────────────────────────────

def convert_formula_to_dax(
    formula,
    column_name='Measure',
    table_name='Table',
    calc_map=None,
    param_map=None,
    column_table_map=None,
    measure_names=None,
    is_calc_column=False,
    param_values=None,
    calc_datatype=None,
    partition_fields=None,
    compute_using=None,
    evaluate_policy=None,
):
    """Convert a Qlik expression to DAX.

    Accepts extra keyword arguments for API compatibility;
    only the parameters understood by the Qlik converter are forwarded.
    """
    if not formula or not formula.strip():
        return ''

    # Build variables dict from calc_map (Qlik variables ≈ calculated-field references)
    variables = {}
    if calc_map and isinstance(calc_map, dict):
        variables.update(calc_map)

    return _convert_qlik_expression_to_dax(
        qlik_expr=formula,
        table_name=table_name,
        col_table_map=column_table_map,
        is_calculated_column=is_calc_column,
        variables=variables,
        evaluate_policy=evaluate_policy,
    )


# Backward-compatible aliases
convert_qlik_expression_to_dax = convert_formula_to_dax


def convert_tableau_formula_to_dax(*args, **kwargs):
    """Deprecated — use ``convert_formula_to_dax`` instead."""
    import warnings
    warnings.warn(
        "convert_tableau_formula_to_dax is deprecated; use convert_formula_to_dax.",
        DeprecationWarning, stacklevel=2,
    )
    return convert_formula_to_dax(*args, **kwargs)


# ── M query generation ──────────────────────────────────────────

def generate_power_query_m(connection, table):
    """Generate a Power Query M query from Qlik connection + table metadata.

    Args:
        connection: dict with connection details (connectionType, connectionDetails, etc.)
        table: dict with table info (name, columns)

    Returns:
        str: Complete M query
    """
    conn_type = ''
    if isinstance(connection, dict):
        conn_type = connection.get('type', connection.get('connectionType', '')).lower()

    table_name = ''
    columns = []
    if isinstance(table, dict):
        table_name = table.get('name', table.get('tableName', 'Table'))
        columns = table.get('columns', [])
    elif isinstance(table, str):
        table_name = table

    datasource = {
        'tableName': table_name,
        'connectionType': conn_type,
        'connection': connection if isinstance(connection, dict) else {},
        'columns': columns,
    }

    return generate_m_query(datasource)
