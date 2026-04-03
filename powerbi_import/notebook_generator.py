"""
PySpark Notebook Generator for Microsoft Fabric.

Generates Jupyter notebooks (.ipynb) with PySpark code for:
1. Data ingestion from original sources into Lakehouse Delta tables
2. Data transformations (calculated columns materialised via withColumn)
3. Schema validation and data quality checks
"""

import os
import json
import re
from datetime import datetime

from .calc_column_utils import (
    classify_calculations,
    sanitize_calc_col_name,
    Qlik_formula_to_pyspark,
)
from .fabric_naming import make_python_var as _make_var_name

# Connection type → PySpark read snippet
_SPARK_READ_TEMPLATES = {
    'SQL Server': (
        '# Read from SQL Server\n'
        'jdbc_url = "jdbc:sqlserver://{server};databaseName={database}"\n'
        'df_{table_var} = spark.read \\\n'
        '    .format("jdbc") \\\n'
        '    .option("url", jdbc_url) \\\n'
        '    .option("dbtable", "{table_name}") \\\n'
        '    .option("user", "<username>") \\\n'
        '    .option("password", "<password>") \\\n'
        '    .load()\n'
    ),
    'PostgreSQL': (
        '# Read from PostgreSQL\n'
        'jdbc_url = "jdbc:postgresql://{server}:{port}/{database}"\n'
        'df_{table_var} = spark.read \\\n'
        '    .format("jdbc") \\\n'
        '    .option("url", jdbc_url) \\\n'
        '    .option("dbtable", "{table_name}") \\\n'
        '    .option("user", "<username>") \\\n'
        '    .option("password", "<password>") \\\n'
        '    .option("driver", "org.postgresql.Driver") \\\n'
        '    .load()\n'
    ),
    'Oracle': (
        '# Read from Oracle\n'
        'jdbc_url = "jdbc:oracle:thin:@{server}:{port}/{service}"\n'
        'df_{table_var} = spark.read \\\n'
        '    .format("jdbc") \\\n'
        '    .option("url", jdbc_url) \\\n'
        '    .option("dbtable", "{table_name}") \\\n'
        '    .option("user", "<username>") \\\n'
        '    .option("password", "<password>") \\\n'
        '    .option("driver", "oracle.jdbc.driver.OracleDriver") \\\n'
        '    .load()\n'
    ),
    'MySQL': (
        '# Read from MySQL\n'
        'jdbc_url = "jdbc:mysql://{server}:{port}/{database}"\n'
        'df_{table_var} = spark.read \\\n'
        '    .format("jdbc") \\\n'
        '    .option("url", jdbc_url) \\\n'
        '    .option("dbtable", "{table_name}") \\\n'
        '    .option("user", "<username>") \\\n'
        '    .option("password", "<password>") \\\n'
        '    .load()\n'
    ),
    'Snowflake': (
        '# Read from Snowflake\n'
        'df_{table_var} = spark.read \\\n'
        '    .format("snowflake") \\\n'
        '    .option("sfURL", "{server}") \\\n'
        '    .option("sfDatabase", "{database}") \\\n'
        '    .option("sfSchema", "{schema}") \\\n'
        '    .option("sfWarehouse", "{warehouse}") \\\n'
        '    .option("dbtable", "{table_name}") \\\n'
        '    .option("sfUser", "<username>") \\\n'
        '    .option("sfPassword", "<password>") \\\n'
        '    .load()\n'
    ),
    'BigQuery': (
        '# Read from BigQuery\n'
        'df_{table_var} = spark.read \\\n'
        '    .format("bigquery") \\\n'
        '    .option("table", "{project}.{dataset}.{table_name}") \\\n'
        '    .load()\n'
    ),
    'CSV': (
        '# Read CSV file\n'
        'df_{table_var} = spark.read \\\n'
        '    .format("csv") \\\n'
        '    .option("header", "true") \\\n'
        '    .option("inferSchema", "true") \\\n'
        '    .option("delimiter", "{delimiter}") \\\n'
        '    .load("Files/{filename}")\n'
    ),
    'Excel': (
        '# Read Excel file (requires com.crealytics:spark-excel)\n'
        'df_{table_var} = spark.read \\\n'
        '    .format("com.crealytics.spark.excel") \\\n'
        '    .option("header", "true") \\\n'
        '    .option("inferSchema", "true") \\\n'
        "    .option(\"dataAddress\", \"\\'{table_name}\\'!A1\") \\\n"
        '    .load("Files/{filename}")\n'
    ),
    'Custom SQL': (
        '# Read via Custom SQL\n'
        'jdbc_url = "jdbc:sqlserver://{server};databaseName={database}"\n'
        'custom_query = """{custom_sql}"""\n'
        'df_{table_var} = spark.read \\\n'
        '    .format("jdbc") \\\n'
        '    .option("url", jdbc_url) \\\n'
        '    .option("query", custom_query) \\\n'
        '    .option("user", "<username>") \\\n'
        '    .option("password", "<password>") \\\n'
        '    .load()\n'
    ),
}


def _make_notebook(cells, metadata=None):
    """Create a Jupyter notebook JSON structure."""
    if metadata is None:
        metadata = {}
    return {
        'nbformat': 4,
        'nbformat_minor': 5,
        'metadata': {
            'kernel_info': {'name': 'synapse_pyspark'},
            'kernelspec': {
                'name': 'synapse_pyspark',
                'display_name': 'Synapse PySpark',
                'language': 'Python',
            },
            'language_info': {
                'name': 'python',
                'version': '3.10',
                'mimetype': 'text/x-python',
                'file_extension': '.py',
                'pygments_lexer': 'ipython3',
                'codemirror_mode': {'name': 'ipython', 'version': 3},
            },
            'microsoft': {
                'language': 'python',
                'ms_spell_check': {'ms_spell_check_language': 'en'},
            },
            'trident': {
                'lakehouse': {
                    'default_lakehouse_name': metadata.get('lakehouse_name', ''),
                    'known_lakehouses': [],
                },
            },
            **metadata,
        },
        'cells': cells,
    }


def _markdown_cell(source, cell_id=None):
    """Create a markdown cell."""
    return {
        'cell_type': 'markdown',
        'metadata': {'nteract': {'transient': {'deleting': False}}},
        'source': source if isinstance(source, list) else [source],
        'id': cell_id or '',
    }


def _code_cell(source, cell_id=None):
    """Create a code cell."""
    return {
        'cell_type': 'code',
        'metadata': {
            'jupyter': {'outputs_hidden': False, 'source_hidden': False},
            'nteract': {'transient': {'deleting': False}},
            'microsoft': {'language': 'python'},
        },
        'source': source if isinstance(source, list) else [source],
        'outputs': [],
        'execution_count': None,
        'id': cell_id or '',
    }


class NotebookGenerator:
    """Generates PySpark notebooks for Fabric ETL pipelines."""

    def __init__(self, project_dir, project_name):
        self.project_dir = project_dir
        self.project_name = project_name
        self.notebook_dir = os.path.join(project_dir, f'{project_name}.Notebook')
        os.makedirs(self.notebook_dir, exist_ok=True)

    def generate(self, extracted_data):
        """Generate PySpark notebooks from extracted Qlik data.

        Args:
            extracted_data: Dict with 'datasources', 'custom_sql', etc.

        Returns:
            Dict with generation stats
            {'cells': int, 'notebooks': int, 'calc_columns': int}
        """
        datasources = extracted_data.get('datasources', [])
        custom_sql = extracted_data.get('custom_sql', [])
        calculations = extracted_data.get('calculations', [])

        calc_columns, measures = classify_calculations(calculations)

        etl_cells = self._generate_etl_cells(datasources, custom_sql)
        etl_nb = _make_notebook(etl_cells, {
            'lakehouse_name': f'{self.project_name}_Lakehouse',
            'description': f'ETL pipeline for {self.project_name}',
        })

        etl_path = os.path.join(self.notebook_dir, 'etl_pipeline.ipynb')
        with open(etl_path, 'w', encoding='utf-8') as f:
            json.dump(etl_nb, f, indent=2, ensure_ascii=False)

        total_cells = len(etl_cells)
        notebooks = 1

        if calculations:
            transform_cells = self._generate_transformation_cells(
                datasources, calc_columns, measures,
            )
            transform_nb = _make_notebook(transform_cells, {
                'lakehouse_name': f'{self.project_name}_Lakehouse',
                'description': f'Data transformations for {self.project_name}',
            })

            transform_path = os.path.join(self.notebook_dir, 'transformations.ipynb')
            with open(transform_path, 'w', encoding='utf-8') as f:
                json.dump(transform_nb, f, indent=2, ensure_ascii=False)

            total_cells += len(transform_cells)
            notebooks += 1

        return {
            'cells': total_cells,
            'notebooks': notebooks,
            'calc_columns': len(calc_columns),
        }

    def _generate_etl_cells(self, datasources, custom_sql):
        """Generate cells for the ETL pipeline notebook."""
        cells = []

        cells.append(_markdown_cell([
            f'# ETL Pipeline — {self.project_name}\n',
            '\n',
            'This notebook ingests data from the original Qlik data sources\n',
            'into Fabric Lakehouse Delta tables.\n',
            '\n',
            f'**Generated:** {datetime.now().strftime("%Y-%m-%d %H:%M")}\n',
        ]))

        cells.append(_code_cell([
            '# Setup\n',
            'from pyspark.sql import SparkSession\n',
            'from pyspark.sql.types import *\n',
            'from pyspark.sql.functions import *\n',
            'from datetime import datetime\n',
            '\n',
            f'LAKEHOUSE_NAME = "{self.project_name}_Lakehouse"\n',
            'print(f"ETL Pipeline started: {datetime.now()}")\n',
        ]))

        tables_info = []
        seen_tables = set()

        for ds in datasources:
            connection = ds.get('connection', {})
            if not connection and ds.get('connections'):
                connection = ds['connections'][0]
            connection_map = ds.get('connection_map', {})

            for table in ds.get('tables', []):
                table_name = table.get('name', '')
                if not table_name or table_name in seen_tables:
                    continue
                seen_tables.add(table_name)

                table_conn = table.get('connection_details', {})
                if table_conn and table_conn.get('type'):
                    conn = table_conn
                elif table.get('connection') and table.get('connection') in connection_map:
                    conn = connection_map[table['connection']]
                else:
                    conn = connection

                tables_info.append({
                    'name': table_name,
                    'connection': conn,
                    'columns': table.get('columns', []),
                })

        cells.append(_markdown_cell([
            '## Data Ingestion\n',
            '\n',
            f'Loading {len(tables_info)} table(s) from source systems.\n',
        ]))

        for table_info in tables_info:
            table_name = table_info['name']
            conn = table_info['connection']
            conn_type = conn.get('type', 'Unknown')
            details = conn.get('details', {})
            table_var = _make_var_name(table_name)
            lh_table = re.sub(r'[^a-zA-Z0-9_]', '_', table_name).lower()

            cells.append(_markdown_cell(f'### Table: `{table_name}` ({conn_type})'))

            template = _SPARK_READ_TEMPLATES.get(conn_type, '')
            if template:
                code = template.format(
                    table_var=table_var,
                    table_name=table_name,
                    server=details.get('server', 'localhost'),
                    port=details.get('port', ''),
                    database=details.get('database', ''),
                    schema=details.get('schema', 'public'),
                    warehouse=details.get('warehouse', ''),
                    project=details.get('project', ''),
                    dataset=details.get('dataset', ''),
                    filename=details.get('filename', ''),
                    delimiter=details.get('delimiter', ','),
                    service=details.get('service', ''),
                    custom_sql='',
                )
            else:
                code = (
                    f'# TODO: Configure data source for {conn_type}\n'
                    f'df_{table_var} = spark.createDataFrame([], schema=StructType([]))\n'
                )

            code += f'\n# Preview\ndf_{table_var}.printSchema()\n'
            code += f'print(f"Rows: {{df_{table_var}.count()}}")\n'
            code += f'\n# Write to Lakehouse Delta table\n'
            code += f'df_{table_var}.write \\\n'
            code += f'    .format("delta") \\\n'
            code += f'    .mode("overwrite") \\\n'
            code += f'    .saveAsTable("{lh_table}")\n'
            code += f'print(f"Written to Lakehouse: {lh_table}")\n'

            cells.append(_code_cell(code))

        if custom_sql:
            cells.append(_markdown_cell('## Custom SQL Queries'))
            for sql_entry in custom_sql:
                sql_name = sql_entry.get('name', 'Custom Query')
                sql_query = sql_entry.get('query', '')
                table_var = _make_var_name(sql_name)
                lh_table = re.sub(r'[^a-zA-Z0-9_]', '_', sql_name).lower()

                cells.append(_markdown_cell(f'### {sql_name}'))
                code = (
                    f'# Custom SQL: {sql_name}\n'
                    f'custom_query = """\n{sql_query}\n"""\n\n'
                    f'# TODO: Configure JDBC connection\n'
                    f'# df_{table_var} = spark.read.format("jdbc").option("query", custom_query).load()\n'
                    f'# df_{table_var}.write.format("delta").mode("overwrite").saveAsTable("{lh_table}")\n'
                )
                cells.append(_code_cell(code))

        cells.append(_markdown_cell('## Summary'))
        cells.append(_code_cell([
            'print("\\n" + "=" * 60)\n',
            'print("ETL Pipeline Complete")\n',
            'print("=" * 60)\n',
            f'print(f"Tables loaded: {len(tables_info)}")\n',
            'print(f"Completed: {datetime.now()}")\n',
            '\n',
            'print("\\nLakehouse tables:")\n',
            'for t in spark.catalog.listTables():\n',
            '    print(f"  - {t.name} ({t.tableType})")\n',
        ]))

        return cells

    def _generate_transformation_cells(self, datasources, calc_columns, measures):
        """Generate cells for data transformations."""
        cells = []

        cells.append(_markdown_cell([
            f'# Data Transformations — {self.project_name}\n',
            '\n',
            'Materialises calculated columns as physical columns\n',
            'in the Lakehouse Delta table via PySpark withColumn().\n',
            '\n',
            f'**Generated:** {datetime.now().strftime("%Y-%m-%d %H:%M")}\n',
        ]))

        cells.append(_code_cell([
            'from pyspark.sql import SparkSession\n',
            'import pyspark.sql.functions as F\n',
            'from pyspark.sql.types import *\n',
            'from pyspark.sql.window import Window\n',
            'from datetime import datetime\n',
            '\n',
            'print(f"Transformations started: {datetime.now()}")\n',
        ]))

        main_table_name = None
        for ds in datasources:
            for table in ds.get('tables', []):
                t_name = table.get('name', '')
                if t_name:
                    lh_name = re.sub(r'[^a-zA-Z0-9_]', '_', t_name).lower()
                    if main_table_name is None:
                        main_table_name = lh_name
                    elif len(table.get('columns', [])) > 0:
                        main_table_name = lh_name

        main_table_name = main_table_name or 'main_table'

        if calc_columns:
            cells.append(_markdown_cell([
                '## Calculated Columns (materialised)\n',
                '\n',
                f'{len(calc_columns)} calculated column(s) will be added\n',
                f'to the `{main_table_name}` Delta table.\n',
            ]))

            cells.append(_code_cell([
                f'# Read the main table from Lakehouse\n',
                f'df = spark.read.format("delta").table("{main_table_name}")\n',
                f'print(f"Rows: {{df.count()}}, Columns: {{len(df.columns)}}")\n',
            ]))

            for cc in calc_columns:
                col_name = cc.get('caption', cc.get('name', ''))
                formula = cc.get('formula', '')

                cells.append(_markdown_cell(
                    f'### `{col_name}` ({cc.get("datatype", "string")})\n\n'
                    f'**Qlik formula:** `{formula}`'
                ))

                pyspark_line = Qlik_formula_to_pyspark(formula, col_name)
                cells.append(_code_cell(pyspark_line + '\n'))

            cells.append(_code_cell([
                f'# Overwrite the Delta table with the new columns\n',
                f'df.write.format("delta").mode("overwrite")'
                f'.option("overwriteSchema", "true")'
                f'.saveAsTable("{main_table_name}")\n',
                f'print(f"Written {{len(df.columns)}} columns to '
                f'{main_table_name}")\n',
            ]))

        if measures:
            cells.append(_markdown_cell([
                '## Measures (DAX — informational only)\n',
                '\n',
                'The following calculations use aggregation functions\n',
                'and will remain as DAX measures in the Semantic Model.\n',
            ]))
            for m in measures:
                m_name = m.get('caption', m.get('name', 'Unnamed'))
                m_formula = m.get('formula', '')
                cells.append(_markdown_cell(
                    f'- **`{m_name}`**: `{m_formula}`'
                ))

        cells.append(_markdown_cell('## Summary'))
        cells.append(_code_cell([
            'print("\\n" + "=" * 60)\n',
            'print("Transformations Complete")\n',
            'print("=" * 60)\n',
            f'print("Calculated columns materialised: {len(calc_columns)}")\n',
            f'print("Measures kept as DAX:            {len(measures)}")\n',
            'print(f"Completed: {datetime.now()}")\n',
        ]))

        return cells
