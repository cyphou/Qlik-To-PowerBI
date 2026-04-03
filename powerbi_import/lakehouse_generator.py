"""
Lakehouse Definition Generator for Microsoft Fabric.

Generates Lakehouse table schema definitions from extracted
Qlik datasource metadata. Creates:
- lakehouse_definition.json: Lakehouse metadata + table schemas
- Table DDL scripts for Delta Lake tables
- Table metadata JSON for other generators
"""

import os
import json
from datetime import datetime

from .calc_column_utils import classify_calculations, sanitize_calc_col_name
from .fabric_constants import map_to_spark_type as _map_to_spark_type
from .fabric_naming import sanitize_table_name as _sanitize_table_name
from .fabric_naming import sanitize_column_name as _sanitize_column_name


class LakehouseGenerator:
    """Generates Lakehouse definitions from Qlik datasources."""

    def __init__(self, project_dir, project_name):
        self.project_dir = project_dir
        self.project_name = project_name
        self.lakehouse_dir = os.path.join(project_dir, f'{project_name}.Lakehouse')
        os.makedirs(self.lakehouse_dir, exist_ok=True)

    def generate(self, extracted_data):
        """Generate Lakehouse definition from extracted Qlik data.

        Args:
            extracted_data: Dict with 'datasources', 'calculations', etc.

        Returns:
            Dict with generation stats {'tables': int, 'columns': int,
                                         'calc_columns': int}
        """
        datasources = extracted_data.get('datasources', [])
        custom_sql = extracted_data.get('custom_sql', [])
        calculations = extracted_data.get('calculations', [])

        calc_columns, _measures = classify_calculations(calculations)

        tables = []
        seen_tables = set()

        for ds in datasources:
            for table in ds.get('tables', []):
                table_name = _sanitize_table_name(table.get('name', ''))
                if not table_name or table_name in seen_tables:
                    continue
                seen_tables.add(table_name)

                columns = []
                for col in table.get('columns', []):
                    col_name = _sanitize_column_name(col.get('name', ''))
                    spark_type = _map_to_spark_type(col.get('datatype', 'string'))
                    nullable = col.get('nullable', True)
                    columns.append({
                        'name': col_name,
                        'datatype': spark_type,
                        'nullable': nullable,
                        'original_name': col.get('name', ''),
                        'original_type': col.get('datatype', 'string'),
                    })

                conn_details = table.get('connection_details', {})
                ds_conn = ds.get('connection', {})
                if not ds_conn and ds.get('connections'):
                    ds_conn = ds['connections'][0]
                source_type = conn_details.get('type', ds_conn.get('type', 'Unknown'))

                tables.append({
                    'name': table_name,
                    'original_name': table.get('name', ''),
                    'columns': columns,
                    'source_type': source_type,
                    'source_connection': conn_details.get('details', {}),
                    'format': 'delta',
                })

        # Custom SQL tables
        for sql_entry in custom_sql:
            sql_name = _sanitize_table_name(sql_entry.get('name', 'custom_query'))
            if sql_name not in seen_tables:
                seen_tables.add(sql_name)
                tables.append({
                    'name': sql_name,
                    'original_name': sql_entry.get('name', ''),
                    'columns': [],
                    'source_type': 'Custom SQL',
                    'custom_sql': sql_entry.get('query', ''),
                    'format': 'delta',
                })

        # Add calculated columns to the main (fact) table
        num_calc_cols = 0
        if calc_columns and tables:
            main_table = max(tables, key=lambda t: len(t.get('columns', [])))
            existing_names = {c['name'] for c in main_table['columns']}

            for cc in calc_columns:
                cc_name = sanitize_calc_col_name(
                    cc.get('caption', cc.get('name', 'calc'))
                )
                if cc_name in existing_names:
                    continue
                existing_names.add(cc_name)

                main_table['columns'].append({
                    'name': cc_name,
                    'datatype': cc['spark_type'],
                    'nullable': True,
                    'original_name': cc.get('caption', cc.get('name', '')),
                    'original_type': cc.get('datatype', 'string'),
                    'is_calculated': True,
                    'formula': cc.get('formula', ''),
                })
                num_calc_cols += 1

        lakehouse_def = {
            '$schema': 'https://developer.microsoft.com/json-schemas/fabric/item/lakehouse/definition/lakehouse/1.0.0/schema.json',
            'properties': {
                'displayName': f'{self.project_name}_Lakehouse',
                'description': f'Lakehouse generated from Qlik app: {self.project_name}',
                'created': datetime.now().isoformat(),
                'defaultSchema': 'dbo',
            },
            'tables': tables,
        }

        def_path = os.path.join(self.lakehouse_dir, 'lakehouse_definition.json')
        with open(def_path, 'w', encoding='utf-8') as f:
            json.dump(lakehouse_def, f, indent=2, ensure_ascii=False)

        self._generate_ddl(tables)
        self._generate_table_metadata(tables)

        total_columns = sum(len(t.get('columns', [])) for t in tables)
        return {'tables': len(tables), 'columns': total_columns,
                'calc_columns': num_calc_cols}

    def _generate_ddl(self, tables):
        """Generate Spark SQL DDL scripts for creating Delta tables."""
        ddl_dir = os.path.join(self.lakehouse_dir, 'ddl')
        os.makedirs(ddl_dir, exist_ok=True)

        all_ddl = []
        for table in tables:
            if not table.get('columns'):
                continue

            ddl = f"-- Create table: {table['name']}\n"
            ddl += f"-- Source: {table.get('original_name', '')} ({table.get('source_type', '')})\n"
            ddl += f"CREATE TABLE IF NOT EXISTS {table['name']} (\n"

            col_defs = []
            for col in table['columns']:
                nullable = '' if col.get('nullable', True) else ' NOT NULL'
                comment = ''
                if col.get('is_calculated'):
                    comment = f'  -- calc: {col.get("formula", "")}'
                col_defs.append(f"    {col['name']} {col['datatype']}{nullable}{comment}")

            ddl += ',\n'.join(col_defs)
            ddl += '\n)\nUSING DELTA;\n'
            all_ddl.append(ddl)

            ddl_path = os.path.join(ddl_dir, f'{table["name"]}.sql')
            with open(ddl_path, 'w', encoding='utf-8') as f:
                f.write(ddl)

        if all_ddl:
            combined_path = os.path.join(ddl_dir, '_all_tables.sql')
            with open(combined_path, 'w', encoding='utf-8') as f:
                f.write('-- Lakehouse DDL — Generated by Qlik to Power BI Migration\n')
                f.write('-- Run in a Fabric Notebook or Spark SQL editor\n\n')
                f.write('\n\n'.join(all_ddl))

    def _generate_table_metadata(self, tables):
        """Generate table metadata JSON for other generators to consume."""
        meta = {
            'lakehouse_name': f'{self.project_name}_Lakehouse',
            'tables': [
                {
                    'name': t['name'],
                    'original_name': t.get('original_name', ''),
                    'column_count': len(t.get('columns', [])),
                    'source_type': t.get('source_type', 'Unknown'),
                    'format': t.get('format', 'delta'),
                }
                for t in tables
            ],
        }
        meta_path = os.path.join(self.lakehouse_dir, 'table_metadata.json')
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)
