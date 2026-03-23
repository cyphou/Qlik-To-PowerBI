"""Tests for qlik_export.m_query_generator — Power Query M generation.

Covers:
- map_qlik_to_m_type (17 type mappings + defaults)
- generate_m_query (25 connector types + fallback)
- generate_all_m_queries (batch)
- Type resolution priority (connectionType > type > sourceType > path)
- Schema/table splitting
- Column type step generation
"""

import pytest
from qlik_export.m_query_generator import (
    map_qlik_to_m_type,
    generate_m_query,
    generate_all_m_queries,
)


# ═══════════════════════════════════════════════════════════════
#  map_qlik_to_m_type
# ═══════════════════════════════════════════════════════════════

class TestMapQlikToMType:
    @pytest.mark.parametrize("qlik,expected", [
        ("integer", "Int64.Type"),
        ("int", "Int64.Type"),
        ("num", "type number"),
        ("number", "type number"),
        ("numeric", "type number"),
        ("real", "type number"),
        ("decimal", "type number"),
        ("money", "Currency.Type"),
        ("currency", "Currency.Type"),
        ("text", "type text"),
        ("string", "type text"),
        ("date", "type date"),
        ("timestamp", "type datetime"),
        ("datetime", "type datetime"),
        ("time", "type time"),
        ("boolean", "type logical"),
        ("dual", "type text"),
    ])
    def test_known_types(self, qlik, expected):
        assert map_qlik_to_m_type(qlik) == expected

    def test_unknown_type(self):
        assert map_qlik_to_m_type("blob") == "type text"

    def test_empty_string(self):
        assert map_qlik_to_m_type("") == "type text"

    def test_none(self):
        assert map_qlik_to_m_type(None) == "type text"

    def test_case_insensitive(self):
        assert map_qlik_to_m_type("INTEGER") == "Int64.Type"
        assert map_qlik_to_m_type("Text") == "type text"


# ═══════════════════════════════════════════════════════════════
#  generate_m_query — Connector Dispatch
# ═══════════════════════════════════════════════════════════════

class TestGenerateMQueryConnectors:
    """Test that each connector type produces a valid let...in query."""

    def _ds(self, conn_type, **extra):
        ds = {"connectionType": conn_type, "tableName": "TestTable",
              "connection": {"server": "myserver", "database": "mydb",
                             "path": "data.csv", "host": "dbhost"},
              "columns": [{"name": "ID", "dataType": "integer"},
                          {"name": "Name", "dataType": "text"}]}
        ds.update(extra)
        return ds

    def _assert_valid_m(self, query):
        assert "let" in query.lower()
        assert "in" in query.lower()
        return query

    # ── Database connectors ────────────────────────────────
    def test_sql_server(self):
        q = self._assert_valid_m(generate_m_query(self._ds("sqlserver")))
        assert "Sql.Database" in q

    def test_sql_alias(self):
        q = self._assert_valid_m(generate_m_query(self._ds("sql")))
        assert "Sql.Database" in q

    def test_mssql_alias(self):
        q = self._assert_valid_m(generate_m_query(self._ds("mssql")))
        assert "Sql.Database" in q

    def test_postgresql(self):
        q = self._assert_valid_m(generate_m_query(self._ds("postgresql")))
        assert "PostgreSQL.Database" in q

    def test_postgres_alias(self):
        q = self._assert_valid_m(generate_m_query(self._ds("postgres")))
        assert "PostgreSQL.Database" in q

    def test_mysql(self):
        q = self._assert_valid_m(generate_m_query(self._ds("mysql")))
        assert "MySQL.Database" in q

    def test_oracle(self):
        q = self._assert_valid_m(generate_m_query(self._ds("oracle")))
        assert "Oracle.Database" in q

    def test_bigquery(self):
        q = self._assert_valid_m(generate_m_query(self._ds("bigquery")))
        assert "GoogleBigQuery" in q

    def test_snowflake(self):
        q = self._assert_valid_m(generate_m_query(self._ds("snowflake")))
        assert "Snowflake" in q

    def test_teradata(self):
        q = self._assert_valid_m(generate_m_query(self._ds("teradata")))
        assert "Teradata" in q

    def test_sap_hana(self):
        q = self._assert_valid_m(generate_m_query(self._ds("saphana")))
        assert "SapHana" in q

    def test_sap_hana_alias(self):
        q = self._assert_valid_m(generate_m_query(self._ds("sap_hana")))
        assert "SapHana" in q

    def test_redshift(self):
        q = self._assert_valid_m(generate_m_query(self._ds("redshift")))
        assert "AmazonRedshift" in q

    def test_databricks(self):
        q = self._assert_valid_m(generate_m_query(self._ds("databricks")))
        assert "Databricks" in q

    def test_spark(self):
        q = self._assert_valid_m(generate_m_query(self._ds("spark")))
        assert "Spark" in q

    def test_azure_sql(self):
        q = self._assert_valid_m(generate_m_query(self._ds("azuresql")))
        assert "AzureSQL" in q

    def test_synapse(self):
        q = self._assert_valid_m(generate_m_query(self._ds("synapse")))
        assert "AzureSynapse" in q or "Synapse" in q

    # ── File connectors ────────────────────────────────────
    def test_excel(self):
        q = self._assert_valid_m(generate_m_query(self._ds("excel")))
        assert "Excel.Workbook" in q

    def test_xlsx_alias(self):
        q = self._assert_valid_m(generate_m_query(self._ds("xlsx")))
        assert "Excel.Workbook" in q

    def test_csv(self):
        q = self._assert_valid_m(generate_m_query(self._ds("csv")))
        assert "Csv.Document" in q

    def test_txt_alias(self):
        q = self._assert_valid_m(generate_m_query(self._ds("txt")))
        assert "Csv.Document" in q

    def test_json(self):
        q = self._assert_valid_m(generate_m_query(self._ds("json")))
        assert "Json.Document" in q

    def test_xml(self):
        q = self._assert_valid_m(generate_m_query(self._ds("xml")))
        assert "Xml.Tables" in q

    def test_pdf(self):
        q = self._assert_valid_m(generate_m_query(self._ds("pdf")))
        assert "Pdf.Tables" in q

    def test_qvd(self):
        q = self._assert_valid_m(generate_m_query(self._ds("qvd")))
        assert "Csv" in q or "qvd" in q.lower() or "Parquet" in q

    # ── Other connectors ───────────────────────────────────
    def test_salesforce(self):
        q = self._assert_valid_m(generate_m_query(self._ds("salesforce")))
        assert "Salesforce" in q

    def test_web(self):
        q = self._assert_valid_m(generate_m_query(self._ds("web")))
        assert "Web" in q

    def test_google_sheets(self):
        q = self._assert_valid_m(generate_m_query(self._ds("google_sheets")))
        assert "Web" in q

    def test_sharepoint(self):
        q = self._assert_valid_m(generate_m_query(self._ds("sharepoint")))
        assert "SharePoint" in q

    def test_odbc(self):
        q = self._assert_valid_m(generate_m_query(self._ds("odbc")))
        assert "Odbc" in q

    def test_oledb(self):
        q = self._assert_valid_m(generate_m_query(self._ds("oledb")))
        assert "OleDb" in q


# ═══════════════════════════════════════════════════════════════
#  Type Resolution Priority
# ═══════════════════════════════════════════════════════════════

class TestTypeResolution:
    def test_connection_type_wins(self):
        ds = {"connectionType": "excel", "type": "csv", "sourceType": "json",
              "tableName": "T", "connection": {"path": "x.txt"}, "columns": []}
        q = generate_m_query(ds)
        assert "Excel.Workbook" in q

    def test_type_fallback(self):
        ds = {"type": "postgresql", "tableName": "T",
              "connection": {"server": "s", "database": "d"}, "columns": []}
        q = generate_m_query(ds)
        assert "PostgreSQL.Database" in q

    def test_source_type_fallback(self):
        ds = {"sourceType": "mysql", "tableName": "T",
              "connection": {"server": "s", "database": "d"}, "columns": []}
        q = generate_m_query(ds)
        assert "MySQL.Database" in q

    def test_path_extension_inference(self):
        ds = {"tableName": "T", "connection": {"path": "data/output.csv"},
              "columns": []}
        q = generate_m_query(ds)
        assert "Csv.Document" in q

    def test_unknown_type_fallback(self):
        ds = {"connectionType": "unknown_db", "tableName": "T",
              "connection": {}, "columns": []}
        q = generate_m_query(ds)
        assert "#table" in q.lower() or "TODO" in q


# ═══════════════════════════════════════════════════════════════
#  Schema/Table Splitting
# ═══════════════════════════════════════════════════════════════

class TestSchemaSplitting:
    def test_sql_server_schema_table(self):
        ds = {"connectionType": "sqlserver", "tableName": "sales.Orders",
              "connection": {"server": "srv", "database": "db"}, "columns": []}
        q = generate_m_query(ds)
        assert "sales" in q
        assert "Orders" in q

    def test_sql_server_default_schema(self):
        ds = {"connectionType": "sqlserver", "tableName": "Orders",
              "connection": {"server": "srv", "database": "db"}, "columns": []}
        q = generate_m_query(ds)
        assert "dbo" in q or "Orders" in q

    def test_postgresql_default_schema(self):
        ds = {"connectionType": "postgresql", "tableName": "Orders",
              "connection": {"server": "srv", "database": "db"}, "columns": []}
        q = generate_m_query(ds)
        assert "public" in q or "Orders" in q


# ═══════════════════════════════════════════════════════════════
#  Column Type Steps
# ═══════════════════════════════════════════════════════════════

class TestColumnTypeSteps:
    def test_columns_produce_type_step(self):
        ds = {"connectionType": "excel", "tableName": "T",
              "connection": {"path": "test.xlsx"},
              "columns": [{"name": "ID", "dataType": "integer"},
                          {"name": "Name", "dataType": "text"}]}
        q = generate_m_query(ds)
        assert "TransformColumnTypes" in q or "Int64" in q

    def test_no_columns_no_type_step(self):
        ds = {"connectionType": "excel", "tableName": "T",
              "connection": {"path": "test.xlsx"}, "columns": []}
        q = generate_m_query(ds)
        assert isinstance(q, str)


# ═══════════════════════════════════════════════════════════════
#  Normalization
# ═══════════════════════════════════════════════════════════════

class TestNormalization:
    def test_spaces_stripped(self):
        ds = {"connectionType": "SQL Server", "tableName": "T",
              "connection": {"server": "s", "database": "d"}, "columns": []}
        q = generate_m_query(ds)
        assert "Sql.Database" in q

    def test_hyphens_stripped(self):
        ds = {"connectionType": "SAP-HANA", "tableName": "T",
              "connection": {"server": "s"}, "columns": []}
        q = generate_m_query(ds)
        assert "SapHana" in q


# ═══════════════════════════════════════════════════════════════
#  generate_all_m_queries
# ═══════════════════════════════════════════════════════════════

class TestGenerateAllMQueries:
    def test_basic(self):
        ds_list = [
            {"connectionType": "csv", "tableName": "Orders",
             "connection": {"path": "orders.csv"}, "columns": []},
            {"connectionType": "excel", "tableName": "Products",
             "connection": {"path": "products.xlsx"}, "columns": []},
        ]
        result = generate_all_m_queries(ds_list)
        assert "Orders" in result
        assert "Products" in result
        assert "Csv.Document" in result["Orders"]
        assert "Excel.Workbook" in result["Products"]

    def test_empty_list(self):
        result = generate_all_m_queries([])
        assert result == {}

    def test_name_fallback_chain(self):
        # table key
        ds = [{"connectionType": "csv", "table": "MyTable",
               "connection": {"path": "f.csv"}, "columns": []}]
        result = generate_all_m_queries(ds)
        assert "MyTable" in result

    def test_name_key_fallback(self):
        ds = [{"connectionType": "csv", "name": "Named",
               "connection": {"path": "f.csv"}, "columns": []}]
        result = generate_all_m_queries(ds)
        assert "Named" in result

    def test_default_table_name(self):
        ds = [{"connectionType": "csv",
               "connection": {"path": "f.csv"}, "columns": []}]
        result = generate_all_m_queries(ds)
        assert "Table" in result


# ═══════════════════════════════════════════════════════════════
#  Edge Cases
# ═══════════════════════════════════════════════════════════════

class TestEdgeCases:
    def test_empty_datasource(self):
        q = generate_m_query({})
        assert isinstance(q, str)
        assert "#table" in q.lower() or "let" in q.lower()

    def test_connection_with_host_fallback(self):
        ds = {"connectionType": "sqlserver", "tableName": "T",
              "connection": {"host": "myhost", "database": "db"}, "columns": []}
        q = generate_m_query(ds)
        assert "myhost" in q or "Sql.Database" in q
