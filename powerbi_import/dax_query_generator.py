"""DAX Query View Generator — Sprint 124.

Auto-generates DAX queries for every measure in the semantic model.
Users can paste these into DAX Studio to verify results match Qlik.

Usage::

    from dax_query_generator import generate_dax_queries, export_dax_queries

    queries = generate_dax_queries(model_tables)
    export_dax_queries(queries, output_dir)
"""

import json
import logging
import os
import re

logger = logging.getLogger(__name__)


def generate_dax_queries(tables):
    """Generate DAX validation queries for every measure in the model.

    For each measure, produces a SUMMARIZECOLUMNS query that evaluates
    the measure against its most relevant dimension column.

    Args:
        tables: list of table dicts from the semantic model

    Returns:
        list of dicts: [{'name': str, 'table': str, 'measure': str,
                          'dax': str, 'description': str}]
    """
    queries = []

    for table in (tables or []):
        table_name = table.get('name', '')
        if not table_name or table_name == 'Calendar':
            continue

        measures = table.get('measures', [])
        columns = table.get('columns', [])

        # Find best dimension column (prefer string/text, avoid hidden/key)
        dim_col = _find_best_dimension(columns, table_name)

        for measure in measures:
            meas_name = measure.get('name', '')
            if not meas_name:
                continue

            # Skip internal/system measures
            folder = measure.get('displayFolder', '')
            if folder in ('Time Intelligence', 'Formatted', 'Analytics'):
                continue

            escaped_table = table_name.replace("'", "''")
            escaped_meas = meas_name.replace('"', '""')

            if dim_col:
                escaped_dim = dim_col.replace('"', '""')
                dax = (
                    f'EVALUATE\n'
                    f'SUMMARIZECOLUMNS(\n'
                    f'    \'{escaped_table}\'[{escaped_dim}],\n'
                    f'    "{escaped_meas}", [{meas_name}]\n'
                    f')\n'
                    f'ORDER BY \'{escaped_table}\'[{escaped_dim}]'
                )
            else:
                dax = (
                    f'EVALUATE\n'
                    f'ROW("{escaped_meas}", [{meas_name}])'
                )

            queries.append({
                'name': f'{table_name}_{meas_name}',
                'table': table_name,
                'measure': meas_name,
                'dax': dax,
                'description': f'Validation query for [{meas_name}] on {table_name}',
            })

    return queries


def _find_best_dimension(columns, table_name):
    """Find the best dimension column for a validation query.

    Prefers: string columns > date columns > other non-hidden columns.
    Avoids: key columns, hidden columns, calculated columns.
    """
    string_cols = []
    date_cols = []
    other_cols = []

    for col in (columns or []):
        if isinstance(col, str):
            other_cols.append(col)
            continue
        col_name = col.get('name', '')
        if not col_name:
            continue
        # Skip technical columns
        if col.get('isHidden'):
            continue
        if col.get('isKey'):
            continue
        if col_name.lower().endswith(('_id', '_key', '_sk', '_fk', '_pk')):
            continue

        dtype = col.get('dataType', '').lower()
        if dtype == 'string':
            string_cols.append(col_name)
        elif dtype in ('datetime', 'date'):
            date_cols.append(col_name)
        else:
            other_cols.append(col_name)

    # Prefer string, then date, then any
    if string_cols:
        return string_cols[0]
    if date_cols:
        return date_cols[0]
    if other_cols:
        return other_cols[0]
    return None


def export_dax_queries(queries, output_dir):
    """Export DAX queries as .dax files.

    Args:
        queries: list of query dicts from generate_dax_queries()
        output_dir: path to write .dax files

    Returns:
        int: number of files written
    """
    os.makedirs(output_dir, exist_ok=True)
    count = 0

    for q in queries:
        # Sanitize filename
        safe_name = re.sub(r'[<>:"/\\|?*]', '_', q['name'])
        filepath = os.path.join(output_dir, f'{safe_name}.dax')
        header = (
            f'// Validation Query: {q["measure"]}\n'
            f'// Table: {q["table"]}\n'
            f'// {q["description"]}\n'
            f'// Paste into DAX Studio to compare with Qlik values\n\n'
        )
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(header + q['dax'] + '\n')
        count += 1

    logger.info("Exported %d DAX query files to %s", count, output_dir)
    return count


def generate_query_summary(queries):
    """Generate a summary of all validation queries.

    Returns:
        dict with counts, table breakdown, and query list
    """
    tables = {}
    for q in queries:
        tbl = q.get('table', 'Unknown')
        tables.setdefault(tbl, []).append(q['measure'])

    return {
        'total_queries': len(queries),
        'tables': {k: len(v) for k, v in tables.items()},
        'measures_by_table': tables,
    }
