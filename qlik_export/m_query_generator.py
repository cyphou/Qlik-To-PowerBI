"""
Power Query M Generator — 42 connector types

Generates Power Query M queries from Qlik datasource metadata.
Dispatches by connection type to produce complete `let ... in Result` M queries.

Supported connectors:
  Excel, CSV, SQL Server, PostgreSQL, BigQuery, Oracle, MySQL, Snowflake,
  Teradata, SAP HANA, SAP BW, Redshift, Databricks, Spark, Azure SQL,
  Azure Synapse, Google Sheets, Google Analytics, SharePoint, JSON, XML, PDF,
  Salesforce, Web, QVD, ODBC, OLE DB, OData, Azure Blob/ADLS, Vertica,
  Impala, Hadoop Hive/HDInsight, Presto/Trino, Fabric Lakehouse, Dataverse,
  MongoDB, Cosmos DB, Amazon Athena, IBM DB2, GeoJSON, Custom SQL
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
    """Generate M query for QVD source.

    QVD files are Qlik's proprietary columnar format.  Power BI cannot read
    them natively, so we offer three strategies the user can choose from:
      1) Pre-converted CSV/Parquet (default — fast to iterate)
      2) QVD Reader custom connector (if installed)
      3) ODBC via Qlik's ODBC driver
    """
    path = ds.get("connection", {}).get("path", ds.get("path", "C:\\Data\\file.qvd"))
    table = ds.get("tableName", ds.get("table", "QvdTable"))
    columns = ds.get("columns", [])

    # Determine conversion path (prefer Parquet → CSV → ODBC)
    parquet_path = path.rsplit(".", 1)[0] + ".parquet" if "." in path else path + ".parquet"
    csv_path = path.rsplit(".", 1)[0] + ".csv" if "." in path else path + ".csv"

    lines = [
        "let",
        f'    // Original QVD: {path}',
        f'    // Strategy 1 — Pre-converted Parquet (recommended):',
        f'    //   Source = Parquet.Document(File.Contents("{parquet_path}")),',
        f'    // Strategy 2 — QVD Reader custom connector:',
        f'    //   Source = QvdFile.Content("{path}"),',
        f'    // Strategy 3 — CSV export (default):',
        f'    Source = Csv.Document(File.Contents("{csv_path}"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.None]),',
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


def _gen_m_odata(ds: Dict) -> str:
    """Generate M query for OData source."""
    conn = ds.get("connection", {})
    url = conn.get("url", conn.get("server", "https://services.odata.org/V4/Northwind/Northwind.svc"))
    table = ds.get("tableName", "Table1")
    return "\n".join([
        "let",
        f'    Source = OData.Feed("{url}"),',
        f'    Table = Source{{[Name="{table}"]}}[Data]',
        "in",
        "    Table",
    ])


def _gen_m_google_analytics(ds: Dict) -> str:
    """Generate M query for Google Analytics source."""
    conn = ds.get("connection", {})
    view_id = conn.get("viewId", conn.get("view_id", "123456789"))
    return "\n".join([
        "let",
        f'    // Google Analytics View: {view_id}',
        f'    Source = GoogleAnalytics.Accounts(),',
        f'    // TODO: Navigate to the correct property and view',
        f'    Data = Source{{0}}[Data]',
        "in",
        "    Data",
    ])


def _gen_m_azure_blob(ds: Dict) -> str:
    """Generate M query for Azure Blob Storage / ADLS source."""
    conn = ds.get("connection", {})
    account = conn.get("account", conn.get("server", "mystorageaccount"))
    container = conn.get("container", conn.get("database", "data"))
    path = conn.get("path", "")
    return "\n".join([
        "let",
        f'    Source = AzureStorage.Blobs("https://{account}.blob.core.windows.net/{container}"),',
        f'    // TODO: Filter to specific path: {path}' if path else '    // TODO: Filter to specific file',
        f'    Data = Source{{0}}[Content]',
        "in",
        "    Data",
    ])


def _gen_m_vertica(ds: Dict) -> str:
    """Generate M query for Vertica source."""
    conn = ds.get("connection", {})
    server = conn.get("server", conn.get("host", "vertica-server"))
    database = conn.get("database", "analytics")
    table = ds.get("tableName", "table1")
    schema = conn.get("schema", "public")
    return "\n".join([
        "let",
        f'    Source = Odbc.DataSource("Driver={{Vertica}};Server={server};Database={database}"),',
        f'    Table = Source{{[Schema="{schema}", Name="{table}"]}}[Data]',
        "in",
        "    Table",
    ])


def _gen_m_impala(ds: Dict) -> str:
    """Generate M query for Apache Impala source."""
    conn = ds.get("connection", {})
    server = conn.get("server", conn.get("host", "impala-server"))
    port = conn.get("port", "21050")
    table = ds.get("tableName", "table1")
    database = conn.get("database", "default")
    return "\n".join([
        "let",
        f'    Source = Odbc.DataSource("Driver={{Cloudera ODBC Driver for Impala}};Host={server};Port={port}"),',
        f'    DB = Source{{[Name="{database}"]}}[Data],',
        f'    Table = DB{{[Name="{table}"]}}[Data]',
        "in",
        "    Table",
    ])


def _gen_m_hadoop_hive(ds: Dict) -> str:
    """Generate M query for Hadoop Hive / HDInsight source."""
    conn = ds.get("connection", {})
    server = conn.get("server", conn.get("host", "hive-server"))
    database = conn.get("database", "default")
    table = ds.get("tableName", "table1")
    return "\n".join([
        "let",
        f'    Source = Odbc.DataSource("Driver={{Microsoft Hive ODBC Driver}};Host={server};Database={database}"),',
        f'    Table = Source{{[Name="{table}"]}}[Data]',
        "in",
        "    Table",
    ])


def _gen_m_presto(ds: Dict) -> str:
    """Generate M query for Presto / Trino source."""
    conn = ds.get("connection", {})
    server = conn.get("server", conn.get("host", "presto-server"))
    port = conn.get("port", "8080")
    catalog = conn.get("catalog", conn.get("database", "hive"))
    schema = conn.get("schema", "default")
    table = ds.get("tableName", "table1")
    return "\n".join([
        "let",
        f'    Source = Odbc.DataSource("Driver={{Presto ODBC Driver}};Host={server};Port={port};Catalog={catalog};Schema={schema}"),',
        f'    Table = Source{{[Name="{table}"]}}[Data]',
        "in",
        "    Table",
    ])


def _gen_m_fabric_lakehouse(ds: Dict) -> str:
    """Generate M query for Microsoft Fabric Lakehouse source."""
    conn = ds.get("connection", {})
    workspace = conn.get("workspace", conn.get("workspaceId", "workspace-guid"))
    lakehouse = conn.get("lakehouse", conn.get("database", "MyLakehouse"))
    table = ds.get("tableName", "table1")
    return "\n".join([
        "let",
        f'    Source = Lakehouse.Contents(null, "{workspace}", "{lakehouse}"),',
        f'    Table = Source{{[Name="{table}"]}}[Data]',
        "in",
        "    Table",
    ])


def _gen_m_dataverse(ds: Dict) -> str:
    """Generate M query for Dataverse / Common Data Service source."""
    conn = ds.get("connection", {})
    org_url = conn.get("url", conn.get("server", "https://org.crm.dynamics.com"))
    table = ds.get("tableName", "account")
    return "\n".join([
        "let",
        f'    Source = CommonDataService.Database("{org_url}"),',
        f'    Table = Source{{[Name="{table}"]}}[Data]',
        "in",
        "    Table",
    ])


def _gen_m_mongodb(ds: Dict) -> str:
    """Generate M query for MongoDB / MongoDB Atlas source."""
    conn = ds.get("connection", {})
    server = conn.get("server", conn.get("host", "mongodb-server"))
    database = conn.get("database", "mydb")
    collection = ds.get("tableName", conn.get("collection", "collection1"))
    return "\n".join([
        "let",
        f'    Source = MongoDB.Database("{server}", "{database}"),',
        f'    Collection = Source{{[Name="{collection}"]}}[Data]',
        "in",
        "    Collection",
    ])


def _gen_m_cosmosdb(ds: Dict) -> str:
    """Generate M query for Azure Cosmos DB source."""
    conn = ds.get("connection", {})
    endpoint = conn.get("url", conn.get("server", "https://myaccount.documents.azure.com:443/"))
    database = conn.get("database", "mydb")
    container = ds.get("tableName", conn.get("container", "container1"))
    return "\n".join([
        "let",
        f'    Source = DocumentDB.Contents("{endpoint}"),',
        f'    DB = Source{{[Name="{database}"]}}[Data],',
        f'    Container = DB{{[Name="{container}"]}}[Data]',
        "in",
        "    Container",
    ])


def _gen_m_athena(ds: Dict) -> str:
    """Generate M query for Amazon Athena source."""
    conn = ds.get("connection", {})
    region = conn.get("region", "us-east-1")
    catalog = conn.get("catalog", conn.get("database", "AwsDataCatalog"))
    schema = conn.get("schema", "default")
    table = ds.get("tableName", "table1")
    s3_output = conn.get("s3OutputLocation", "s3://athena-results/")
    return "\n".join([
        "let",
        f'    Source = Odbc.DataSource("Driver={{Simba Athena ODBC Driver}};AwsRegion={region};S3OutputLocation={s3_output};AuthenticationType=IAM Credentials"),',
        f'    Table = Source{{[Schema="{schema}", Name="{table}"]}}[Data]',
        "in",
        "    Table",
    ])


def _gen_m_db2(ds: Dict) -> str:
    """Generate M query for IBM DB2 source."""
    conn = ds.get("connection", {})
    server = conn.get("server", conn.get("host", "db2-server"))
    database = conn.get("database", "SAMPLE")
    table = ds.get("tableName", "table1")
    schema = conn.get("schema", "DB2INST1")
    return "\n".join([
        "let",
        f'    Source = DB2.Database("{server}", "{database}"),',
        f'    Table = Source{{[Schema="{schema}", Name="{table}"]}}[Data]',
        "in",
        "    Table",
    ])


def _gen_m_geojson(ds: Dict) -> str:
    """Generate M query for GeoJSON source."""
    conn = ds.get("connection", {})
    path = conn.get("path", conn.get("url", "data.geojson"))
    return "\n".join([
        "let",
        f'    Source = Json.Document(File.Contents("{path}")),',
        f'    Features = Source[features],',
        f'    Table = Table.FromList(Features, Splitter.SplitByNothing())',
        "in",
        "    Table",
    ])


def _gen_m_sap_bw(ds: Dict) -> str:
    """Generate M query for SAP BW source."""
    conn = ds.get("connection", {})
    server = conn.get("server", conn.get("host", "sap-bw-server"))
    system_id = conn.get("systemId", conn.get("sid", "BWP"))
    cube = ds.get("tableName", conn.get("cube", "ZCUBE_SALES"))
    return "\n".join([
        "let",
        f'    Source = SapBusinessWarehouse.Cubes("{server}", "{system_id}"),',
        f'    Cube = Source{{[Name="{cube}"]}}[Data]',
        "in",
        "    Cube",
    ])


def _gen_m_custom_sql(ds: Dict) -> str:
    """Generate M query from custom SQL statement."""
    conn = ds.get("connection", {})
    server = conn.get("server", conn.get("host", "sql-server"))
    database = conn.get("database", "mydb")
    sql = ds.get("customSql", ds.get("query", conn.get("query", "SELECT * FROM table1")))
    return "\n".join([
        "let",
        f'    Source = Sql.Database("{server}", "{database}", [Query="',
        f'        {sql}',
        '    "])',
        "in",
        "    Source",
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
    # ── Additional connectors (v10) ───────────────────────────
    "odata": _gen_m_odata,
    "google_analytics": _gen_m_google_analytics,
    "googleanalytics": _gen_m_google_analytics,
    "azure_blob": _gen_m_azure_blob,
    "azureblob": _gen_m_azure_blob,
    "adls": _gen_m_azure_blob,
    "azure_data_lake": _gen_m_azure_blob,
    "vertica": _gen_m_vertica,
    "impala": _gen_m_impala,
    "hive": _gen_m_hadoop_hive,
    "hadoop_hive": _gen_m_hadoop_hive,
    "hdinsight": _gen_m_hadoop_hive,
    "presto": _gen_m_presto,
    "trino": _gen_m_presto,
    "fabric_lakehouse": _gen_m_fabric_lakehouse,
    "lakehouse": _gen_m_fabric_lakehouse,
    "dataverse": _gen_m_dataverse,
    "cds": _gen_m_dataverse,
    "common_data_service": _gen_m_dataverse,
    "mongodb": _gen_m_mongodb,
    "mongodb_atlas": _gen_m_mongodb,
    "cosmosdb": _gen_m_cosmosdb,
    "cosmos_db": _gen_m_cosmosdb,
    "azure_cosmos_db": _gen_m_cosmosdb,
    "documentdb": _gen_m_cosmosdb,
    "athena": _gen_m_athena,
    "amazon_athena": _gen_m_athena,
    "db2": _gen_m_db2,
    "ibm_db2": _gen_m_db2,
    "geojson": _gen_m_geojson,
    "sap_bw": _gen_m_sap_bw,
    "sapbw": _gen_m_sap_bw,
    "custom_sql": _gen_m_custom_sql,
    "customsql": _gen_m_custom_sql,
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
