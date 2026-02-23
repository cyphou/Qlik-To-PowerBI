"""
Power Query M Generator — 25 connector types

Generates Power Query M queries from Qlik datasource metadata.
Dispatches by connection type to produce complete `let ... in Result` M queries.

Supported connectors:
  Excel, CSV, SQL Server, PostgreSQL, BigQuery, Oracle, MySQL, Snowflake,
  Teradata, SAP HANA, Redshift, Databricks, Spark, Azure SQL, Azure Synapse,
  Google Sheets, SharePoint, JSON, XML, PDF, Salesforce, Web, QVD, ODBC, OLE DB
"""

import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


# ── Qlik data type → Power Query M type mapping ──────────────────

_M_TYPE_MAP: Dict[str, str] = {
    "integer": "Int64.Type",
    "int": "Int64.Type",
    "num": "type number",
    "number": "type number",
    "numeric": "type number",
    "real": "type number",
    "money": "Currency.Type",
    "currency": "Currency.Type",
    "decimal": "type number",
    "text": "type text",
    "string": "type text",
    "date": "type date",
    "timestamp": "type datetime",
    "datetime": "type datetime",
    "time": "type time",
    "boolean": "type logical",
    "dual": "type text",
}


def map_qlik_to_m_type(qlik_type: str) -> str:
    """Map a Qlik data type to a Power Query M type."""
    return _M_TYPE_MAP.get(qlik_type.lower(), "type text") if qlik_type else "type text"


def _m_escape(name: str) -> str:
    """Escape a column/table name for use in M code."""
    if any(c in name for c in ' .-+/\\(){}[]#@!'):
        return f'"{name}"'
    return f'"{name}"'


def _build_type_step(columns: List[Dict], prev_step: str = "Source") -> str:
    """Generate a Table.TransformColumnTypes step from column metadata."""
    if not columns:
        return ""
    type_pairs = []
    for col in columns:
        col_name = col.get("name", "")
        col_type = col.get("dataType", col.get("type", "text"))
        m_type = map_qlik_to_m_type(col_type)
        type_pairs.append(f'{{{_m_escape(col_name)}, {m_type}}}')
    joined = ", ".join(type_pairs)
    return f'    ChangedTypes = Table.TransformColumnTypes({prev_step}, {{{joined}}})'


# ═══════════════════════════════════════════════════════════════════
# Per-Connector M Query Generators
# ═══════════════════════════════════════════════════════════════════

def _gen_m_excel(ds: Dict) -> str:
    """Generate M query for Excel source."""
    path = ds.get("connection", {}).get("path", ds.get("path", "C:\\Data\\file.xlsx"))
    table = ds.get("tableName", ds.get("table", "Sheet1"))
    columns = ds.get("columns", [])

    lines = [
        "let",
        f'    Source = Excel.Workbook(File.Contents("{path}"), null, true),',
        f'    Sheet = Source{{[Item="{table}",Kind="Sheet"]}}[Data],',
        '    PromotedHeaders = Table.PromoteHeaders(Sheet, [PromoteAllScalars=true]),',
    ]
    type_step = _build_type_step(columns, "PromotedHeaders")
    if type_step:
        lines.append(type_step)
        lines.append("in")
        lines.append("    ChangedTypes")
    else:
        lines.append("in")
        lines.append("    PromotedHeaders")
    return "\n".join(lines)


def _gen_m_csv(ds: Dict) -> str:
    """Generate M query for CSV/text source."""
    path = ds.get("connection", {}).get("path", ds.get("path", "C:\\Data\\file.csv"))
    delimiter = ds.get("connection", {}).get("delimiter", ",")
    columns = ds.get("columns", [])

    lines = [
        "let",
        f'    Source = Csv.Document(File.Contents("{path}"), [Delimiter="{delimiter}", Encoding=65001, QuoteStyle=QuoteStyle.None]),',
        '    PromotedHeaders = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),',
    ]
    type_step = _build_type_step(columns, "PromotedHeaders")
    if type_step:
        lines.append(type_step)
        lines.append("in")
        lines.append("    ChangedTypes")
    else:
        lines.append("in")
        lines.append("    PromotedHeaders")
    return "\n".join(lines)


def _gen_m_sql_server(ds: Dict) -> str:
    """Generate M query for SQL Server source."""
    conn = ds.get("connection", {})
    server = conn.get("server", conn.get("host", "localhost"))
    database = conn.get("database", conn.get("db", "master"))
    table = ds.get("tableName", ds.get("table", "dbo.Table1"))
    schema, tbl = ("dbo", table) if "." not in table else table.split(".", 1)

    return "\n".join([
        "let",
        f'    Source = Sql.Database("{server}", "{database}"),',
        f'    Table = Source{{[Schema="{schema}",Item="{tbl}"]}}[Data]',
        "in",
        "    Table",
    ])


def _gen_m_postgresql(ds: Dict) -> str:
    """Generate M query for PostgreSQL source."""
    conn = ds.get("connection", {})
    server = conn.get("server", conn.get("host", "localhost"))
    database = conn.get("database", conn.get("db", "postgres"))
    table = ds.get("tableName", ds.get("table", "public.table1"))
    schema, tbl = ("public", table) if "." not in table else table.split(".", 1)

    return "\n".join([
        "let",
        f'    Source = PostgreSQL.Database("{server}", "{database}"),',
        f'    Table = Source{{[Schema="{schema}",Item="{tbl}"]}}[Data]',
        "in",
        "    Table",
    ])


def _gen_m_oracle(ds: Dict) -> str:
    """Generate M query for Oracle source."""
    conn = ds.get("connection", {})
    server = conn.get("server", conn.get("host", "localhost"))
    table = ds.get("tableName", ds.get("table", "SCHEMA.TABLE1"))

    return "\n".join([
        "let",
        f'    Source = Oracle.Database("{server}"),',
        f'    Table = Source{{[Schema="{table.split(".")[0] if "." in table else "SCHEMA"}",Item="{table.split(".")[-1]}"]}}[Data]',
        "in",
        "    Table",
    ])


def _gen_m_mysql(ds: Dict) -> str:
    """Generate M query for MySQL source."""
    conn = ds.get("connection", {})
    server = conn.get("server", conn.get("host", "localhost"))
    database = conn.get("database", conn.get("db", "mydb"))
    table = ds.get("tableName", ds.get("table", "table1"))

    return "\n".join([
        "let",
        f'    Source = MySQL.Database("{server}", "{database}"),',
        f'    Table = Source{{[Schema="{database}",Item="{table}"]}}[Data]',
        "in",
        "    Table",
    ])


def _gen_m_bigquery(ds: Dict) -> str:
    """Generate M query for BigQuery source."""
    conn = ds.get("connection", {})
    project = conn.get("project", conn.get("server", "my-project"))
    dataset = conn.get("dataset", conn.get("database", "my_dataset"))
    table = ds.get("tableName", ds.get("table", "table1"))

    return "\n".join([
        "let",
        f'    Source = GoogleBigQuery.Database([BillingProject="{project}"]),',
        f'    Dataset = Source{{[Name="{dataset}"]}}[Data],',
        f'    Table = Dataset{{[Name="{table}"]}}[Data]',
        "in",
        "    Table",
    ])


def _gen_m_snowflake(ds: Dict) -> str:
    """Generate M query for Snowflake source."""
    conn = ds.get("connection", {})
    server = conn.get("server", conn.get("host", "account.snowflakecomputing.com"))
    warehouse = conn.get("warehouse", "COMPUTE_WH")
    database = conn.get("database", conn.get("db", "MY_DB"))
    schema = conn.get("schema", "PUBLIC")
    table = ds.get("tableName", ds.get("table", "TABLE1"))

    return "\n".join([
        "let",
        f'    Source = Snowflake.Databases("{server}", "{warehouse}"),',
        f'    DB = Source{{[Name="{database}"]}}[Data],',
        f'    Schema = DB{{[Name="{schema}"]}}[Data],',
        f'    Table = Schema{{[Name="{table}"]}}[Data]',
        "in",
        "    Table",
    ])


def _gen_m_teradata(ds: Dict) -> str:
    """Generate M query for Teradata source."""
    conn = ds.get("connection", {})
    server = conn.get("server", conn.get("host", "teradata-server"))
    database = conn.get("database", "DBC")
    table = ds.get("tableName", "TABLE1")

    return "\n".join([
        "let",
        f'    Source = Teradata.Database("{server}", [Database="{database}"]),',
        f'    Table = Source{{[Name="{table}"]}}[Data]',
        "in",
        "    Table",
    ])


def _gen_m_sap_hana(ds: Dict) -> str:
    """Generate M query for SAP HANA source."""
    conn = ds.get("connection", {})
    server = conn.get("server", conn.get("host", "hana-server:30015"))
    table = ds.get("tableName", "SCHEMA.TABLE1")

    return "\n".join([
        "let",
        f'    Source = SapHana.Database("{server}"),',
        f'    Table = Source{{[Schema="{table.split(".")[0] if "." in table else "_SYS_BIC"}",Name="{table.split(".")[-1]}"]}}[Data]',
        "in",
        "    Table",
    ])


def _gen_m_redshift(ds: Dict) -> str:
    """Generate M query for Amazon Redshift source."""
    conn = ds.get("connection", {})
    server = conn.get("server", conn.get("host", "cluster.redshift.amazonaws.com"))
    database = conn.get("database", "dev")
    table = ds.get("tableName", "public.table1")
    schema, tbl = ("public", table) if "." not in table else table.split(".", 1)

    return "\n".join([
        "let",
        f'    Source = AmazonRedshift.Database("{server}", "{database}"),',
        f'    Table = Source{{[Schema="{schema}",Item="{tbl}"]}}[Data]',
        "in",
        "    Table",
    ])


def _gen_m_databricks(ds: Dict) -> str:
    """Generate M query for Databricks source."""
    conn = ds.get("connection", {})
    server = conn.get("server", conn.get("host", "adb-xxx.azuredatabricks.net"))
    http_path = conn.get("httpPath", "/sql/1.0/warehouses/xxx")
    catalog = conn.get("catalog", conn.get("database", "main"))
    table = ds.get("tableName", "default.table1")

    return "\n".join([
        "let",
        f'    Source = Databricks.Catalogs("{server}", "{http_path}"),',
        f'    Catalog = Source{{[Name="{catalog}"]}}[Data],',
        f'    Table = Catalog{{[Name="{table}"]}}[Data]',
        "in",
        "    Table",
    ])


def _gen_m_spark(ds: Dict) -> str:
    """Generate M query for Spark source."""
    conn = ds.get("connection", {})
    server = conn.get("server", conn.get("host", "spark-server"))
    table = ds.get("tableName", "default.table1")

    return "\n".join([
        "let",
        f'    Source = SparkHive.Database("{server}"),',
        f'    Table = Source{{[Name="{table}"]}}[Data]',
        "in",
        "    Table",
    ])


def _gen_m_azure_sql(ds: Dict) -> str:
    """Generate M query for Azure SQL source."""
    conn = ds.get("connection", {})
    server = conn.get("server", conn.get("host", "server.database.windows.net"))
    database = conn.get("database", "mydb")
    table = ds.get("tableName", "dbo.Table1")
    schema, tbl = ("dbo", table) if "." not in table else table.split(".", 1)

    return "\n".join([
        "let",
        f'    Source = AzureSQL.Database("{server}", "{database}"),',
        f'    Table = Source{{[Schema="{schema}",Item="{tbl}"]}}[Data]',
        "in",
        "    Table",
    ])


def _gen_m_azure_synapse(ds: Dict) -> str:
    """Generate M query for Azure Synapse source."""
    conn = ds.get("connection", {})
    server = conn.get("server", conn.get("host", "workspace.sql.azuresynapse.net"))
    database = conn.get("database", "pool")
    table = ds.get("tableName", "dbo.Table1")
    schema, tbl = ("dbo", table) if "." not in table else table.split(".", 1)

    return "\n".join([
        "let",
        f'    Source = AzureSynapse.Database("{server}", "{database}"),',
        f'    Table = Source{{[Schema="{schema}",Item="{tbl}"]}}[Data]',
        "in",
        "    Table",
    ])


def _gen_m_google_sheets(ds: Dict) -> str:
    """Generate M query for Google Sheets source."""
    conn = ds.get("connection", {})
    url = conn.get("url", conn.get("path", "https://docs.google.com/spreadsheets/d/SHEET_ID"))

    return "\n".join([
        "let",
        f'    Source = Web.BrowserContents("{url}"),',
        '    Table = Html.Table(Source, {{{"Column1", "Column1"}}}, [RowSelector=".waffle"])',
        "    // Note: Google Sheets requires Web connector — configure auth in Power BI",
        "in",
        "    Table",
    ])


def _gen_m_sharepoint(ds: Dict) -> str:
    """Generate M query for SharePoint source."""
    conn = ds.get("connection", {})
    site_url = conn.get("url", conn.get("path", "https://company.sharepoint.com/sites/data"))
    file_path = conn.get("filePath", "Shared Documents/data.xlsx")

    return "\n".join([
        "let",
        f'    Source = SharePoint.Files("{site_url}", [ApiVersion = 15]),',
        f'    File = Source{{[Name="{file_path.split("/")[-1]}"]}}[Content],',
        '    Workbook = Excel.Workbook(File, true),',
        '    Sheet = Workbook{{[Item="Sheet1",Kind="Sheet"]}}[Data]',
        "in",
        "    Sheet",
    ])


def _gen_m_json(ds: Dict) -> str:
    """Generate M query for JSON source."""
    path = ds.get("connection", {}).get("path", ds.get("path", "C:\\Data\\data.json"))

    return "\n".join([
        "let",
        f'    Source = Json.Document(File.Contents("{path}")),',
        '    Table = Table.FromRecords(Source)',
        "in",
        "    Table",
    ])


def _gen_m_xml(ds: Dict) -> str:
    """Generate M query for XML source."""
    path = ds.get("connection", {}).get("path", ds.get("path", "C:\\Data\\data.xml"))

    return "\n".join([
        "let",
        f'    Source = Xml.Tables(File.Contents("{path}")),',
        '    Table = Source{{0}}',
        "in",
        "    Table",
    ])


def _gen_m_pdf(ds: Dict) -> str:
    """Generate M query for PDF source."""
    path = ds.get("connection", {}).get("path", ds.get("path", "C:\\Data\\report.pdf"))

    return "\n".join([
        "let",
        f'    Source = Pdf.Tables(File.Contents("{path}")),',
        '    Table = Source{{[Id="Table001"]}}[Data]',
        "in",
        "    Table",
    ])


def _gen_m_salesforce(ds: Dict) -> str:
    """Generate M query for Salesforce source."""
    table = ds.get("tableName", ds.get("table", "Account"))

    return "\n".join([
        "let",
        '    Source = Salesforce.Data(),',
        f'    Table = Source{{[Name="{table}"]}}[Data]',
        "in",
        "    Table",
    ])


def _gen_m_web(ds: Dict) -> str:
    """Generate M query for Web source."""
    url = ds.get("connection", {}).get("url", ds.get("path", "https://example.com/data"))

    return "\n".join([
        "let",
        f'    Source = Web.BrowserContents("{url}"),',
        '    Table = Html.Table(Source, {{{"Column1", "TABLE > TR > TD:nth-child(1)"}}})',
        "in",
        "    Table",
    ])


def _gen_m_qvd(ds: Dict) -> str:
    """Generate M query for QVD source (requires custom connector)."""
    path = ds.get("connection", {}).get("path", ds.get("path", "C:\\Data\\file.qvd"))

    return "\n".join([
        "let",
        f'    // QVD source: {path}',
        '    // QVD files require the Qlik QVD connector or conversion to CSV/Parquet',
        f'    Source = Csv.Document(File.Contents("{path.replace(".qvd", ".csv")}"), [Delimiter=",", Encoding=65001]),',
        '    PromotedHeaders = Table.PromoteHeaders(Source, [PromoteAllScalars=true])',
        "in",
        "    PromotedHeaders",
    ])


def _gen_m_odbc(ds: Dict) -> str:
    """Generate M query for ODBC source."""
    conn = ds.get("connection", {})
    dsn = conn.get("dsn", conn.get("connectionString", "DSN=MyDSN"))
    table = ds.get("tableName", "table1")

    return "\n".join([
        "let",
        f'    Source = Odbc.DataSource("{dsn}"),',
        f'    Table = Source{{[Name="{table}"]}}[Data]',
        "in",
        "    Table",
    ])


def _gen_m_oledb(ds: Dict) -> str:
    """Generate M query for OLE DB source."""
    conn = ds.get("connection", {})
    conn_str = conn.get("connectionString", "Provider=SQLOLEDB;Data Source=server;Initial Catalog=db")
    table = ds.get("tableName", "table1")

    return "\n".join([
        "let",
        f'    Source = OleDb.DataSource("{conn_str}"),',
        f'    Table = Source{{[Name="{table}"]}}[Data]',
        "in",
        "    Table",
    ])


def _gen_m_sample(ds: Dict) -> str:
    """Generate sample/fallback M query with inline data."""
    table = ds.get("tableName", ds.get("table", "SampleData"))
    columns = ds.get("columns", [])

    if columns:
        col_defs = ", ".join([f'{_m_escape(c.get("name", f"Col{i}"))}'
                              for i, c in enumerate(columns)])
        return "\n".join([
            "let",
            f'    // TODO: Configure data source for table "{table}"',
            f'    Source = #table({{{col_defs}}}, {{}})',
            "in",
            "    Source",
        ])
    else:
        return "\n".join([
            "let",
            f'    // TODO: Configure data source for table "{table}"',
            '    Source = #table({"Column1"}, {{}})',
            "in",
            "    Source",
        ])


# ═══════════════════════════════════════════════════════════════════
# Connector Dispatch
# ═══════════════════════════════════════════════════════════════════

_M_GENERATORS: Dict[str, Any] = {
    "excel": _gen_m_excel,
    "xlsx": _gen_m_excel,
    "xls": _gen_m_excel,
    "csv": _gen_m_csv,
    "txt": _gen_m_csv,
    "text": _gen_m_csv,
    "sqlserver": _gen_m_sql_server,
    "sql": _gen_m_sql_server,
    "mssql": _gen_m_sql_server,
    "postgresql": _gen_m_postgresql,
    "postgres": _gen_m_postgresql,
    "oracle": _gen_m_oracle,
    "mysql": _gen_m_mysql,
    "bigquery": _gen_m_bigquery,
    "snowflake": _gen_m_snowflake,
    "teradata": _gen_m_teradata,
    "saphana": _gen_m_sap_hana,
    "sap_hana": _gen_m_sap_hana,
    "hana": _gen_m_sap_hana,
    "redshift": _gen_m_redshift,
    "databricks": _gen_m_databricks,
    "spark": _gen_m_spark,
    "azuresql": _gen_m_azure_sql,
    "azure_sql": _gen_m_azure_sql,
    "synapse": _gen_m_azure_synapse,
    "azure_synapse": _gen_m_azure_synapse,
    "google_sheets": _gen_m_google_sheets,
    "googlesheets": _gen_m_google_sheets,
    "sharepoint": _gen_m_sharepoint,
    "json": _gen_m_json,
    "xml": _gen_m_xml,
    "pdf": _gen_m_pdf,
    "salesforce": _gen_m_salesforce,
    "web": _gen_m_web,
    "qvd": _gen_m_qvd,
    "odbc": _gen_m_odbc,
    "oledb": _gen_m_oledb,
    "ole_db": _gen_m_oledb,
}


def generate_m_query(datasource: Dict) -> str:
    """
    Generate a Power Query M query from a Qlik datasource definition.

    Args:
        datasource: Dict with at least 'connectionType' (or 'type', 'sourceType')
                     and optionally 'connection', 'tableName', 'columns', 'path'.

    Returns:
        Complete M query string (let ... in Result)
    """
    # Resolve connection type from multiple possible keys
    conn_type = (
        datasource.get("connectionType", "")
        or datasource.get("type", "")
        or datasource.get("sourceType", "")
        or ""
    ).lower().replace(" ", "").replace("-", "")

    # Also try to infer from file extension in path
    if not conn_type:
        path = datasource.get("connection", {}).get("path", datasource.get("path", ""))
        if path:
            ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
            conn_type = ext

    generator = _M_GENERATORS.get(conn_type, _gen_m_sample)

    try:
        return generator(datasource)
    except Exception as e:
        logger.warning(f"M query generation failed for {conn_type}: {e}")
        return _gen_m_sample(datasource)


def generate_all_m_queries(datasources: List[Dict]) -> Dict[str, str]:
    """
    Generate M queries for all datasources.

    Args:
        datasources: List of datasource dicts

    Returns:
        {table_name: m_query} mapping
    """
    queries = {}
    for ds in datasources:
        table_name = ds.get("tableName", ds.get("table", ds.get("name", "Table")))
        queries[table_name] = generate_m_query(ds)
    return queries
