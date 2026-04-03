"""
Dataflow Gen2 Generator for Microsoft Fabric.

Generates Dataflow Gen2 definitions from extracted Qlik datasources.
Dataflow Gen2 uses Power Query M language to define data transformations.

Output:
- dataflow_definition.json: Dataflow Gen2 mashup document
- Individual .m files for each query (for readability)
- mashup.pq: Combined Power Query M document
"""

import os
import json
import re
import sys
from datetime import datetime

from .calc_column_utils import (
    classify_calculations,
    make_m_add_column_step,
    sanitize_calc_col_name,
)
from .fabric_naming import sanitize_query_name as _sanitize_query_name

# Import m_query_builder from qlik_export (sibling package)
_parent = os.path.join(os.path.dirname(os.path.dirname(__file__)))
if _parent not in sys.path:
    sys.path.insert(0, _parent)


def _get_m_query_builder():
    """Lazy import of m_query_builder to avoid circular imports."""
    from qlik_export.m_query_builder import generate_power_query_m
    return generate_power_query_m


class DataflowGenerator:
    """Generates Dataflow Gen2 definitions from Qlik datasources."""

    def __init__(self, project_dir, project_name):
        self.project_dir = project_dir
        self.project_name = project_name
        self.dataflow_dir = os.path.join(project_dir, f'{project_name}.Dataflow')
        os.makedirs(self.dataflow_dir, exist_ok=True)

    def generate(self, extracted_data):
        """Generate Dataflow Gen2 definition from extracted Qlik data.

        Args:
            extracted_data: Dict with 'datasources', 'custom_sql',
                            'calculations', etc.

        Returns:
            Dict with generation stats {'queries': int, 'calc_columns': int}
        """
        datasources = extracted_data.get('datasources', [])
        custom_sql = extracted_data.get('custom_sql', [])
        calculations = extracted_data.get('calculations', [])

        calc_columns, _measures = classify_calculations(calculations)

        generate_power_query_m = _get_m_query_builder()

        queries = []
        seen_queries = set()

        for ds in datasources:
            connection = ds.get('connection', {})
            if not connection and ds.get('connections'):
                connection = ds['connections'][0]
            connection_map = ds.get('connection_map', {})

            for table in ds.get('tables', []):
                table_name = table.get('name', '')
                query_name = _sanitize_query_name(table_name)

                if query_name in seen_queries:
                    continue
                seen_queries.add(query_name)

                # Use per-table connection if available
                table_conn = table.get('connection_details', {})
                if table_conn and table_conn.get('type'):
                    conn = table_conn
                elif table.get('connection') and table.get('connection') in connection_map:
                    conn = connection_map[table['connection']]
                else:
                    conn = connection

                # Check for M query override
                m_query_overrides = ds.get('m_query_overrides', {})
                m_override = ds.get('m_query_override', '')

                if table_name in m_query_overrides:
                    m_query = m_query_overrides[table_name]
                elif m_override:
                    m_query = m_override
                else:
                    m_query = generate_power_query_m(conn, table)

                lh_table = re.sub(r'[^a-zA-Z0-9_]', '_', table_name).lower()

                queries.append({
                    'name': query_name,
                    'description': f'Ingests data from {table_name}',
                    'm_query': m_query,
                    'lakehouse_table': lh_table,
                    'source_type': conn.get('type', 'Unknown'),
                    'source_details': conn.get('details', {}),
                    'result_type': 'Table',
                    'load_enabled': True,
                })

        # Custom SQL queries
        for sql_entry in custom_sql:
            sql_name = _sanitize_query_name(sql_entry.get('name', 'Custom_SQL'))
            if sql_name not in seen_queries:
                seen_queries.add(sql_name)

                ds_name = sql_entry.get('datasource', '')
                conn = {'type': 'SQL Server', 'details': {'server': 'localhost', 'database': 'MyDB'}}
                for ds in datasources:
                    if ds.get('name', '') == ds_name:
                        conn = ds.get('connection', conn)
                        break

                sql_query = sql_entry.get('query', '')
                server = conn.get('details', {}).get('server', 'localhost')
                database = conn.get('details', {}).get('database', 'MyDB')
                sql_escaped = sql_query.replace('"', '""')

                m_query = (
                    'let\n'
                    '    // Custom SQL Query\n'
                    f'    Source = Sql.Database("{server}", "{database}", '
                    f'[Query="{sql_escaped}"]),\n'
                    '    Result = Source\n'
                    'in\n'
                    '    Result'
                )

                lh_table = re.sub(r'[^a-zA-Z0-9_]', '_', sql_name).lower()
                queries.append({
                    'name': sql_name,
                    'description': f'Custom SQL: {sql_name}',
                    'm_query': m_query,
                    'lakehouse_table': lh_table,
                    'source_type': 'Custom SQL',
                    'result_type': 'Table',
                    'load_enabled': True,
                })

        # Inject calculated columns into the main table query
        if calc_columns and queries:
            main_q = queries[0]
            main_q['m_query'] = self._inject_calc_column_steps(
                main_q['m_query'], calc_columns,
            )
            main_q['description'] += (
                f' + {len(calc_columns)} calculated column(s)'
            )

        dataflow_def = self._build_dataflow_definition(queries)

        def_path = os.path.join(self.dataflow_dir, 'dataflow_definition.json')
        with open(def_path, 'w', encoding='utf-8') as f:
            json.dump(dataflow_def, f, indent=2, ensure_ascii=False)

        self._write_m_query_files(queries)
        self._write_mashup_document(queries)

        return {'queries': len(queries), 'calc_columns': len(calc_columns)}

    def _inject_calc_column_steps(self, m_query, calc_columns):
        """Inject Table.AddColumn steps for calculated columns into an M query."""
        in_match = re.search(r'\bin\s*\n\s*(\w+)\s*$', m_query, re.MULTILINE)
        if not in_match:
            comment = '\n// Calculated columns (manual conversion needed):\n'
            for cc in calc_columns:
                name = cc.get('caption', cc.get('name', ''))
                comment += f'// - {name}: {cc.get("formula", "")}\n'
            return m_query + comment

        final_step = in_match.group(1)
        before_in = m_query[:in_match.start()]

        prev_step = final_step
        extra_lines = []
        for cc in calc_columns:
            col_name = cc.get('caption', cc.get('name', ''))
            formula = cc.get('formula', '')
            line, prev_step = make_m_add_column_step(formula, col_name, prev_step)
            extra_lines.append(line)

        steps_block = ',\n'.join(extra_lines)
        return f'{before_in},\n{steps_block}\nin\n    {prev_step}'

    def _build_dataflow_definition(self, queries):
        """Build the Dataflow Gen2 JSON definition."""
        mashup_sections = []
        for q in queries:
            mashup_sections.append(f'shared {q["name"]} = {q["m_query"]};')

        mashup_document = '\nsection Section1;\n\n' + '\n\n'.join(mashup_sections)

        query_groups = []
        for q in queries:
            query_groups.append({
                'name': q['name'],
                'description': q.get('description', ''),
                'queryId': q['name'].lower().replace(' ', '_'),
                'resultType': q.get('result_type', 'Table'),
                'loadEnabled': q.get('load_enabled', True),
                'destination': {
                    'type': 'Lakehouse',
                    'tableName': q.get('lakehouse_table', q['name'].lower()),
                    'updateMethod': 'Replace',
                    'schemaMapping': 'Auto',
                },
            })

        return {
            '$schema': 'https://developer.microsoft.com/json-schemas/fabric/item/dataflow/definition/dataflowGen2/1.0.0/schema.json',
            'properties': {
                'displayName': f'{self.project_name}_Dataflow',
                'description': f'Dataflow Gen2 generated from Qlik app: {self.project_name}',
                'type': 'DataflowGen2',
                'created': datetime.now().isoformat(),
            },
            'mashupDocument': mashup_document,
            'queries': query_groups,
        }

    def _write_m_query_files(self, queries):
        """Write individual .m files for each query."""
        queries_dir = os.path.join(self.dataflow_dir, 'queries')
        os.makedirs(queries_dir, exist_ok=True)

        for q in queries:
            safe_name = re.sub(r'[^a-zA-Z0-9_]', '_', q['name'])
            q_path = os.path.join(queries_dir, f'{safe_name}.m')
            with open(q_path, 'w', encoding='utf-8') as f:
                f.write(f'// Query: {q["name"]}\n')
                f.write(f'// Description: {q.get("description", "")}\n')
                f.write(f'// Destination: {q.get("lakehouse_table", "")}\n\n')
                f.write(q['m_query'])
                f.write('\n')

    def _write_mashup_document(self, queries):
        """Write the combined Power Query M mashup document."""
        mashup_path = os.path.join(self.dataflow_dir, 'mashup.pq')
        with open(mashup_path, 'w', encoding='utf-8') as f:
            f.write('// Dataflow Gen2 Mashup Document\n')
            f.write(f'// Generated: {datetime.now().isoformat()}\n\n')
            f.write('section Section1;\n\n')
            for q in queries:
                f.write(f'shared {q["name"]} = {q["m_query"]};\n\n')

    # ════════════════════════════════════════════════════════════════
    #  PREP FLOW → DATAFLOW GEN2 DIRECT CONVERSION
    # ════════════════════════════════════════════════════════════════

    def generate_from_prep_flow(self, prep_flow_data, extracted_data=None):
        """Generate Dataflow Gen2 directly from a parsed Qlik Prep flow.

        This bypasses the standard datasource→M→Dataflow pipeline and
        instead converts the Prep flow DAG steps directly into Dataflow
        Gen2 Power Query M queries, preserving the Prep transformation
        order and logic.

        Args:
            prep_flow_data: Parsed Prep flow dict from prep_flow_parser.
                Keys: 'datasources' (list with m_query entries),
                      'nodes' (optional), 'flow_name' (optional)
            extracted_data: Optional extracted app data for enrichment

        Returns:
            dict: {queries: int, prep_steps: int}
        """
        prep_datasources = prep_flow_data.get('datasources', [])
        flow_name = prep_flow_data.get('flow_name', self.project_name)

        queries = []
        seen = set()

        for ds in prep_datasources:
            # Prep datasources already have m_query from parse_prep_flow()
            m_query = ds.get('m_query', '')
            if not m_query:
                continue

            table_name = ds.get('name', ds.get('caption', ''))
            query_name = _sanitize_query_name(table_name) if table_name else f'PrepQuery_{len(queries) + 1}'

            if query_name in seen:
                query_name = f'{query_name}_{len(queries) + 1}'
            seen.add(query_name)

            # Detect if this is a prep-sourced query
            is_prep = ds.get('is_prep_source', False)
            conn_type = ds.get('connection', {}).get('type', 'Unknown')

            lh_table = re.sub(r'[^a-zA-Z0-9_]', '_', query_name).lower()

            queries.append({
                'name': query_name,
                'description': f'Prep flow step: {table_name}' + (' (prep source)' if is_prep else ''),
                'm_query': m_query,
                'lakehouse_table': lh_table,
                'source_type': conn_type,
                'result_type': 'Table',
                'load_enabled': True,
                'prep_source': is_prep,
            })

        # If extracted_data also has datasources not in prep, add them
        if extracted_data:
            generate_m = _get_m_query_builder()
            for ds in extracted_data.get('datasources', []):
                conn = ds.get('connection', {})
                for t in ds.get('tables', []):
                    tname = t.get('name', '')
                    qname = _sanitize_query_name(tname)
                    if qname not in seen:
                        seen.add(qname)
                        m_query = generate_m(conn, t)
                        lh_table = re.sub(r'[^a-zA-Z0-9_]', '_', tname).lower()
                        queries.append({
                            'name': qname,
                            'description': f'app datasource: {tname}',
                            'm_query': m_query,
                            'lakehouse_table': lh_table,
                            'source_type': conn.get('type', 'Unknown'),
                            'result_type': 'Table',
                            'load_enabled': True,
                            'prep_source': False,
                        })

        # Build and write Dataflow definition
        dataflow_def = self._build_dataflow_definition(queries)
        def_path = os.path.join(self.dataflow_dir, 'dataflow_definition.json')
        with open(def_path, 'w', encoding='utf-8') as f:
            json.dump(dataflow_def, f, indent=2, ensure_ascii=False)

        self._write_m_query_files(queries)
        self._write_mashup_document(queries)

        prep_count = sum(1 for q in queries if q.get('prep_source'))
        return {'queries': len(queries), 'prep_steps': prep_count}
