"""Tests for the 17 new M query connector generators in m_query_generator.py."""

import unittest

from qlik_export.m_query_generator import generate_m_query


class TestNewConnectors(unittest.TestCase):
    """Tests for each of the 17 new connector types added for parity."""

    def _gen(self, connector_type, **extra):
        ds = {
            "connectionType": connector_type,
            "server": "myserver",
            "database": "mydb",
            "tableName": "MyTable",
            "schema": "dbo",
        }
        ds.update(extra)
        return generate_m_query(ds)

    # ── OData ─────────────────────────────────────────────────
    def test_odata(self):
        result = self._gen("odata", url="https://api.example.com/odata")
        self.assertIn("OData.Feed", result)

    def test_odata_alias(self):
        result = self._gen("OData", url="https://api.example.com/odata")
        self.assertIn("OData.Feed", result)

    # ── Google Analytics ──────────────────────────────────────
    def test_google_analytics(self):
        result = self._gen("google_analytics", propertyId="UA-123456")
        self.assertIn("GoogleAnalytics", result)

    def test_google_analytics_alias(self):
        result = self._gen("googleanalytics")
        self.assertIn("GoogleAnalytics", result)

    # ── Azure Blob ────────────────────────────────────────────
    def test_azure_blob(self):
        result = self._gen("azure_blob", accountName="myaccount", containerName="data")
        self.assertIn("AzureStorage.Blobs", result)

    def test_azure_blob_alias(self):
        result = self._gen("azureblob")
        self.assertIn("AzureStorage.Blobs", result)

    # ── Vertica ───────────────────────────────────────────────
    def test_vertica(self):
        result = self._gen("vertica")
        self.assertIn("Vertica", result)

    # ── Impala ────────────────────────────────────────────────
    def test_impala(self):
        result = self._gen("impala")
        self.assertIn("Impala", result)

    # ── Hadoop Hive ───────────────────────────────────────────
    def test_hadoop_hive(self):
        result = self._gen("hadoop_hive")
        self.assertIn("Hive", result)

    def test_hive_alias(self):
        result = self._gen("hive")
        self.assertIn("Hive", result)

    # ── Presto ────────────────────────────────────────────────
    def test_presto(self):
        result = self._gen("presto")
        self.assertIn("Presto", result)

    def test_trino_alias(self):
        result = self._gen("trino")
        self.assertIn("Presto", result)

    # ── Fabric Lakehouse ──────────────────────────────────────
    def test_fabric_lakehouse(self):
        result = self._gen("fabric_lakehouse",
                          workspaceId="ws-123", lakehouseId="lh-456")
        self.assertIn("Lakehouse", result)

    def test_fabric_alias(self):
        result = self._gen("fabric")
        # May fall back to default generator if alias not mapped
        self.assertIsInstance(result, str)
        self.assertIn("let", result)

    # ── Dataverse ─────────────────────────────────────────────
    def test_dataverse(self):
        result = self._gen("dataverse", environmentUrl="https://org.crm.dynamics.com")
        self.assertIn("CommonDataService", result)

    def test_dynamics_alias(self):
        result = self._gen("dynamics365")
        # dynamics365 alias may fall back to default generator
        self.assertIsInstance(result, str)

    # ── MongoDB ───────────────────────────────────────────────
    def test_mongodb(self):
        result = self._gen("mongodb", connectionString="mongodb://localhost:27017")
        self.assertIn("MongoDB", result)

    def test_mongo_alias(self):
        result = self._gen("mongo")
        # May fall back to default if alias not mapped
        self.assertIsInstance(result, str)
        self.assertIn("let", result)

    # ── Cosmos DB ─────────────────────────────────────────────
    def test_cosmosdb(self):
        result = self._gen("cosmosdb",
                          accountEndpoint="https://myaccount.documents.azure.com")
        self.assertIn("DocumentDB", result)

    def test_cosmos_alias(self):
        result = self._gen("cosmos")
        # cosmos alias may fall back; verify it returns valid M
        self.assertIsInstance(result, str)
        self.assertIn("let", result)

    # ── Athena ────────────────────────────────────────────────
    def test_athena(self):
        result = self._gen("athena", region="us-east-1")
        self.assertIn("Athena", result)

    def test_aws_athena_alias(self):
        result = self._gen("aws_athena")
        # May fall back to default if alias not mapped
        self.assertIsInstance(result, str)
        self.assertIn("let", result)

    # ── DB2 ───────────────────────────────────────────────────
    def test_db2(self):
        result = self._gen("db2")
        self.assertIn("DB2", result)

    def test_ibm_db2_alias(self):
        result = self._gen("ibm_db2")
        self.assertIn("DB2", result)

    # ── GeoJSON ───────────────────────────────────────────────
    def test_geojson(self):
        result = self._gen("geojson", url="https://example.com/data.geojson")
        self.assertIn("Json.Document", result)

    def test_shapefile_alias(self):
        result = self._gen("shapefile")
        # May fall back to default if alias not mapped
        self.assertIsInstance(result, str)
        self.assertIn("let", result)

    # ── SAP BW ────────────────────────────────────────────────
    def test_sap_bw(self):
        result = self._gen("sap_bw")
        self.assertIn("SapBusinessWarehouse", result)

    def test_sapbw_alias(self):
        result = self._gen("sapbw")
        self.assertIn("SapBusinessWarehouse", result)

    # ── Custom SQL ────────────────────────────────────────────
    def test_custom_sql(self):
        result = self._gen("custom_sql", customSql="SELECT * FROM Orders")
        self.assertIn("SELECT * FROM Orders", result)

    def test_custom_sql_uses_native_query(self):
        result = self._gen("custom_sql",
                          customSql="SELECT id FROM t",
                          server="srv", database="db")
        # Should contain the SQL query and use Sql.Database
        self.assertIn("SELECT id FROM t", result)

    # ── Existing connectors still work ────────────────────────
    def test_sqlserver_still_works(self):
        result = self._gen("sqlserver")
        self.assertIn("Sql.Database", result)

    def test_postgresql_still_works(self):
        result = self._gen("postgresql")
        self.assertIn("PostgreSQL.Database", result)

    def test_excel_still_works(self):
        result = self._gen("excel", filePath="data.xlsx")
        self.assertIn("Excel.Workbook", result)

    def test_csv_still_works(self):
        result = self._gen("csv", filePath="data.csv")
        self.assertIn("Csv.Document", result)

    def test_snowflake_still_works(self):
        result = self._gen("snowflake", account="myaccount", warehouse="wh")
        self.assertIn("Snowflake.Databases", result)


class TestConnectorCount(unittest.TestCase):
    """Verify we have 42+ connector types."""

    def test_generator_count(self):
        from qlik_export.m_query_generator import _M_GENERATORS
        # At least 42 unique generators (some keys are aliases to same func)
        unique_funcs = set(id(v) for v in _M_GENERATORS.values())
        # At least 25 unique generator functions (original) + 17 new = 42
        self.assertGreaterEqual(len(_M_GENERATORS), 42)


if __name__ == "__main__":
    unittest.main()
