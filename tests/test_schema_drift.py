"""Tests for powerbi_import.schema_drift — column, table, measure change detection."""

import unittest

from powerbi_import.schema_drift import (
    detect_schema_drift,
    SchemaDriftReport,
    SchemaDriftEntry,
)


class TestDetectSchemaDriftColumns(unittest.TestCase):
    """Test column-level drift detection."""

    def _ds(self, tables):
        """Helper to build a datasources list around table dicts."""
        return [{"tables": tables, "relationships": []}]

    def test_added_column(self):
        prev = {"datasources": self._ds([{"name": "T", "columns": [{"name": "A"}]}])}
        curr = {"datasources": self._ds([
            {"name": "T", "columns": [{"name": "A"}, {"name": "B"}]}
        ])}
        report = detect_schema_drift(curr, prev)
        self.assertTrue(report.has_drift)
        added = [e for e in report.entries
                 if e.category == "column" and e.change_type == "added"]
        self.assertEqual(len(added), 1)
        self.assertEqual(added[0].name, "B")

    def test_removed_column(self):
        prev = {"datasources": self._ds([
            {"name": "T", "columns": [{"name": "A"}, {"name": "B"}]}
        ])}
        curr = {"datasources": self._ds([{"name": "T", "columns": [{"name": "A"}]}])}
        report = detect_schema_drift(curr, prev)
        removed = [e for e in report.entries
                   if e.category == "column" and e.change_type == "removed"]
        self.assertEqual(len(removed), 1)
        self.assertEqual(removed[0].name, "B")

    def test_no_drift(self):
        ds = self._ds([{"name": "T", "columns": [{"name": "A"}, {"name": "B"}]}])
        report = detect_schema_drift({"datasources": ds}, {"datasources": ds})
        col_entries = [e for e in report.entries if e.category == "column"]
        self.assertEqual(len(col_entries), 0)

    def test_column_type_change(self):
        prev = {"datasources": self._ds([
            {"name": "T", "columns": [{"name": "X", "datatype": "string"}]}
        ])}
        curr = {"datasources": self._ds([
            {"name": "T", "columns": [{"name": "X", "datatype": "integer"}]}
        ])}
        report = detect_schema_drift(curr, prev)
        modified = [e for e in report.entries
                    if e.category == "column" and e.change_type == "modified"]
        self.assertEqual(len(modified), 1)
        self.assertIn("type changed", modified[0].detail)


class TestDetectSchemaDriftTables(unittest.TestCase):
    """Test table-level drift."""

    def _ds(self, table_names):
        return [{"tables": [{"name": n, "columns": []} for n in table_names],
                 "relationships": []}]

    def test_added_table(self):
        prev = {"datasources": self._ds(["Orders"])}
        curr = {"datasources": self._ds(["Orders", "Products"])}
        report = detect_schema_drift(curr, prev)
        added = [e for e in report.entries
                 if e.category == "table" and e.change_type == "added"]
        self.assertEqual(len(added), 1)
        self.assertEqual(added[0].name, "Products")

    def test_removed_table(self):
        prev = {"datasources": self._ds(["Orders", "Products"])}
        curr = {"datasources": self._ds(["Orders"])}
        report = detect_schema_drift(curr, prev)
        removed = [e for e in report.entries
                   if e.category == "table" and e.change_type == "removed"]
        self.assertEqual(len(removed), 1)
        self.assertEqual(removed[0].name, "Products")


class TestDetectSchemaDriftCalculations(unittest.TestCase):
    """Test calculation/formula drift."""

    def test_added_calculation(self):
        prev = {"calculations": []}
        curr = {"calculations": [{"name": "TotalSales", "formula": "SUM(Sales)"}]}
        report = detect_schema_drift(curr, prev)
        added = [e for e in report.entries
                 if e.category == "calculation" and e.change_type == "added"]
        self.assertEqual(len(added), 1)

    def test_modified_calculation(self):
        prev = {"calculations": [{"name": "Total", "formula": "SUM(A)"}]}
        curr = {"calculations": [{"name": "Total", "formula": "SUM(B)"}]}
        report = detect_schema_drift(curr, prev)
        modified = [e for e in report.entries
                    if e.category == "calculation" and e.change_type == "modified"]
        self.assertEqual(len(modified), 1)

    def test_removed_calculation(self):
        prev = {"calculations": [{"name": "Old", "formula": "SUM(X)"}]}
        curr = {"calculations": []}
        report = detect_schema_drift(curr, prev)
        removed = [e for e in report.entries
                   if e.category == "calculation" and e.change_type == "removed"]
        self.assertEqual(len(removed), 1)


class TestSchemaDriftReport(unittest.TestCase):
    """Test report data class."""

    def test_no_drift_summary(self):
        report = SchemaDriftReport()
        self.assertFalse(report.has_drift)
        self.assertIn("No schema drift", report.summary())

    def test_drift_summary_with_entries(self):
        entries = [
            SchemaDriftEntry("column", "added", "NewCol", table="T"),
            SchemaDriftEntry("column", "removed", "OldCol", table="T"),
        ]
        report = SchemaDriftReport(entries=entries)
        self.assertTrue(report.has_drift)
        summary = report.summary()
        self.assertIn("column", summary)
        self.assertIn("+1", summary)
        self.assertIn("-1", summary)

    def test_to_dict(self):
        entries = [SchemaDriftEntry("table", "added", "Sales")]
        report = SchemaDriftReport(entries=entries, source_name="TestApp")
        d = report.to_dict()
        self.assertEqual(d["source_name"], "TestApp")
        self.assertEqual(d["total_changes"], 1)
        self.assertEqual(d["summary"]["added"], 1)

    def test_filter_by_category(self):
        entries = [
            SchemaDriftEntry("column", "added", "A"),
            SchemaDriftEntry("table", "added", "B"),
        ]
        report = SchemaDriftReport(entries=entries)
        self.assertEqual(len(report.by_category("column")), 1)
        self.assertEqual(len(report.by_category("table")), 1)


if __name__ == "__main__":
    unittest.main()
