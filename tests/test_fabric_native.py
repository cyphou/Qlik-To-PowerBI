"""Tests for Fabric-native modules — constants, naming, lakehouse, calc_column_utils."""

import os
import tempfile
import unittest

from powerbi_import.fabric_constants import (
    FABRIC_ARTIFACTS,
    SPARK_TYPE_MAP,
    PYSPARK_TYPE_MAP,
    AGG_PATTERN,
    map_to_spark_type,
)
from powerbi_import.fabric_naming import (
    sanitize_table_name,
    sanitize_column_name,
    sanitize_query_name,
    sanitize_pipeline_name,
    make_python_var,
    sanitize_filesystem_name,
)
from powerbi_import.calc_column_utils import (
    classify_calculations,
    sanitize_calc_col_name,
)
from powerbi_import.lakehouse_generator import LakehouseGenerator


# ── fabric_constants ──────────────────────────────────────────────────────────

class TestFabricConstants(unittest.TestCase):
    """Test fabric_constants module."""

    def test_fabric_artifacts_list(self):
        self.assertIn("lakehouse", FABRIC_ARTIFACTS)
        self.assertIn("dataflow", FABRIC_ARTIFACTS)
        self.assertIn("notebook", FABRIC_ARTIFACTS)
        self.assertIn("semanticmodel", FABRIC_ARTIFACTS)
        self.assertIn("pipeline", FABRIC_ARTIFACTS)

    def test_spark_type_map_has_common_types(self):
        self.assertEqual(SPARK_TYPE_MAP["string"], "STRING")
        self.assertEqual(SPARK_TYPE_MAP["integer"], "INT")
        self.assertEqual(SPARK_TYPE_MAP["double"], "DOUBLE")
        self.assertEqual(SPARK_TYPE_MAP["boolean"], "BOOLEAN")
        self.assertEqual(SPARK_TYPE_MAP["datetime"], "TIMESTAMP")

    def test_map_to_spark_type_known(self):
        self.assertEqual(map_to_spark_type("string"), "STRING")
        self.assertEqual(map_to_spark_type("int64"), "BIGINT")

    def test_map_to_spark_type_unknown_defaults_string(self):
        self.assertEqual(map_to_spark_type("unknown_type"), "STRING")

    def test_map_to_spark_type_case_insensitive(self):
        self.assertEqual(map_to_spark_type("STRING"), "STRING")
        self.assertEqual(map_to_spark_type("DateTime"), "TIMESTAMP")

    def test_pyspark_type_map(self):
        self.assertEqual(PYSPARK_TYPE_MAP["string"], "StringType()")
        self.assertEqual(PYSPARK_TYPE_MAP["boolean"], "BooleanType()")

    def test_agg_pattern_matches(self):
        self.assertTrue(AGG_PATTERN.search("SUM('T'[X])"))
        self.assertTrue(AGG_PATTERN.search("AVERAGE('T'[Y])"))
        self.assertTrue(AGG_PATTERN.search("DISTINCTCOUNT('T'[Z])"))
        self.assertFalse(AGG_PATTERN.search("'T'[Column]"))


# ── fabric_naming ─────────────────────────────────────────────────────────────

class TestSanitizeTableName(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(sanitize_table_name("Sales"), "sales")

    def test_schema_prefix_stripped(self):
        self.assertEqual(sanitize_table_name("dbo.Sales"), "sales")

    def test_special_chars_replaced(self):
        result = sanitize_table_name("My Table!")
        self.assertNotIn("!", result)
        self.assertNotIn(" ", result)

    def test_leading_digits_stripped(self):
        result = sanitize_table_name("123table")
        self.assertFalse(result[0].isdigit())

    def test_brackets_removed(self):
        result = sanitize_table_name("[Sales]")
        self.assertNotIn("[", result)
        self.assertNotIn("]", result)

    def test_empty_fallback(self):
        self.assertEqual(sanitize_table_name(""), "table")


class TestSanitizeColumnName(unittest.TestCase):
    def test_basic(self):
        result = sanitize_column_name("Revenue")
        self.assertEqual(result, "Revenue")

    def test_special_chars(self):
        result = sanitize_column_name("Grand Total $")
        self.assertNotIn("$", result)

    def test_leading_digits(self):
        result = sanitize_column_name("1stColumn")
        self.assertFalse(result[0].isdigit())

    def test_empty_fallback(self):
        self.assertEqual(sanitize_column_name(""), "column")


class TestSanitizeQueryName(unittest.TestCase):
    def test_spaces_allowed(self):
        result = sanitize_query_name("My Query")
        self.assertIn(" ", result)

    def test_empty_fallback(self):
        self.assertEqual(sanitize_query_name(""), "Query")


class TestSanitizePipelineName(unittest.TestCase):
    def test_basic(self):
        result = sanitize_pipeline_name("Load Sales")
        self.assertNotIn(" ", result)

    def test_empty_fallback(self):
        self.assertEqual(sanitize_pipeline_name(""), "activity")


class TestMakePythonVar(unittest.TestCase):
    def test_basic(self):
        result = make_python_var("MyTable")
        self.assertTrue(result.islower())
        self.assertTrue(result.isidentifier())

    def test_leading_digits(self):
        result = make_python_var("123Sales")
        self.assertTrue(result.isidentifier())


class TestSanitizeFilesystemName(unittest.TestCase):
    def test_removes_invalid_chars(self):
        result = sanitize_filesystem_name('file<>:"/\\|?*.txt')
        self.assertNotIn("<", result)
        self.assertNotIn(">", result)
        self.assertNotIn(":", result)


# ── calc_column_utils ────────────────────────────────────────────────────────

class TestClassifyCalculations(unittest.TestCase):
    """Test row-level vs aggregate classification."""

    def test_aggregate_is_measure(self):
        calcs = [{"formula": "SUM('T'[Revenue])", "role": "measure", "datatype": "double"}]
        cc, meas = classify_calculations(calcs)
        self.assertEqual(len(meas), 1)
        self.assertEqual(len(cc), 0)

    def test_row_level_is_calc_column(self):
        calcs = [{"formula": "[Price] * [Qty]", "role": "dimension", "datatype": "double"}]
        cc, meas = classify_calculations(calcs)
        self.assertEqual(len(cc), 1)
        self.assertEqual(len(meas), 0)
        self.assertIn("spark_type", cc[0])

    def test_empty_formula_skipped(self):
        calcs = [{"formula": "", "role": "measure", "datatype": "string"}]
        cc, meas = classify_calculations(calcs)
        self.assertEqual(len(cc), 0)
        self.assertEqual(len(meas), 0)


class TestSanitizeCalcColName(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(sanitize_calc_col_name("Total Revenue"), "total_revenue")

    def test_brackets_removed(self):
        result = sanitize_calc_col_name("[Order Count]")
        self.assertNotIn("[", result)
        self.assertNotIn("]", result)

    def test_empty_fallback(self):
        self.assertEqual(sanitize_calc_col_name(""), "calc_col")


# ── lakehouse_generator ──────────────────────────────────────────────────────

class TestLakehouseGenerator(unittest.TestCase):
    """Test LakehouseGenerator schema generation."""

    def test_generate_basic_schema(self):
        with tempfile.TemporaryDirectory() as td:
            gen = LakehouseGenerator(td, "TestProject")
            extracted = {
                "datasources": [{
                    "connection": {"type": "sqlserver"},
                    "tables": [{
                        "name": "Orders",
                        "columns": [
                            {"name": "OrderID", "datatype": "string"},
                            {"name": "Amount", "datatype": "double"},
                        ],
                    }],
                }],
                "calculations": [],
            }
            stats = gen.generate(extracted)
            self.assertIn("tables", stats)
            self.assertGreaterEqual(stats["tables"], 1)

    def test_lakehouse_dir_created(self):
        with tempfile.TemporaryDirectory() as td:
            gen = LakehouseGenerator(td, "LH")
            self.assertTrue(os.path.isdir(gen.lakehouse_dir))

    def test_deduplicates_tables(self):
        with tempfile.TemporaryDirectory() as td:
            gen = LakehouseGenerator(td, "Dedup")
            extracted = {
                "datasources": [
                    {"connection": {}, "tables": [{"name": "T", "columns": []}]},
                    {"connection": {}, "tables": [{"name": "T", "columns": []}]},
                ],
                "calculations": [],
            }
            stats = gen.generate(extracted)
            self.assertEqual(stats["tables"], 1)


if __name__ == "__main__":
    unittest.main()
