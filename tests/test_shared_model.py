"""Tests for powerbi_import.shared_model — multi-app merge engine."""

import unittest

from powerbi_import.shared_model import (
    TableFingerprint,
    MergeCandidate,
    MergeAssessment,
    build_table_fingerprints,
    compute_column_overlap,
    assess_merge,
)


class TestTableFingerprint(unittest.TestCase):
    """Test fingerprint consistency and equality."""

    def test_fingerprint_deterministic(self):
        fp = TableFingerprint("sqlserver", "srv", "db", "dbo", "Sales")
        self.assertEqual(fp.fingerprint(), fp.fingerprint())

    def test_equal_fingerprints_match(self):
        fp1 = TableFingerprint("sqlserver", "srv", "db", "dbo", "Sales")
        fp2 = TableFingerprint("sqlserver", "srv", "db", "dbo", "Sales")
        self.assertEqual(fp1, fp2)
        self.assertEqual(hash(fp1), hash(fp2))

    def test_different_table_name_differs(self):
        fp1 = TableFingerprint("sqlserver", "srv", "db", "dbo", "Sales")
        fp2 = TableFingerprint("sqlserver", "srv", "db", "dbo", "Orders")
        self.assertNotEqual(fp1, fp2)

    def test_case_insensitive(self):
        fp1 = TableFingerprint("SqlServer", "SRV", "DB", "DBO", "sales")
        fp2 = TableFingerprint("sqlserver", "srv", "db", "dbo", "Sales")
        self.assertEqual(fp1, fp2)

    def test_fingerprint_hex_length(self):
        fp = TableFingerprint("pg", "localhost", "mydb", "public", "tbl")
        self.assertEqual(len(fp.fingerprint()), 16)


class TestBuildTableFingerprints(unittest.TestCase):
    """Test fingerprint building from datasource dicts."""

    def test_single_table(self):
        ds = [{
            "connection": {"type": "sqlserver", "details": {"server": "srv", "database": "db"}},
            "tables": [{"name": "Sales", "columns": [{"name": "ID"}]}],
        }]
        fps = build_table_fingerprints(ds)
        self.assertIn("Sales", fps)
        fp, table, conn = fps["Sales"]
        self.assertIsInstance(fp, TableFingerprint)

    def test_multiple_tables(self):
        ds = [{
            "connection": {"type": "pg", "details": {"server": "s", "database": "d"}},
            "tables": [
                {"name": "A", "columns": []},
                {"name": "B", "columns": []},
            ],
        }]
        fps = build_table_fingerprints(ds)
        self.assertEqual(len(fps), 2)

    def test_custom_sql_table(self):
        ds = [{
            "connection": {"type": "sqlserver", "details": {"server": "s", "database": "d"}},
            "tables": [{"name": "CustomQuery", "custom_sql": "SELECT 1", "columns": []}],
        }]
        fps = build_table_fingerprints(ds)
        self.assertIn("CustomQuery", fps)


class TestComputeColumnOverlap(unittest.TestCase):
    """Test Jaccard similarity of column names."""

    def test_identical_tables(self):
        t = {"columns": [{"name": "A"}, {"name": "B"}, {"name": "C"}]}
        self.assertEqual(compute_column_overlap(t, t), 1.0)

    def test_disjoint_tables(self):
        t1 = {"columns": [{"name": "A"}]}
        t2 = {"columns": [{"name": "B"}]}
        self.assertEqual(compute_column_overlap(t1, t2), 0.0)

    def test_partial_overlap(self):
        t1 = {"columns": [{"name": "A"}, {"name": "B"}]}
        t2 = {"columns": [{"name": "B"}, {"name": "C"}]}
        overlap = compute_column_overlap(t1, t2)
        # Jaccard: |{B}| / |{A, B, C}| = 1/3
        self.assertAlmostEqual(overlap, 1 / 3, places=4)

    def test_both_empty(self):
        self.assertEqual(compute_column_overlap({"columns": []}, {"columns": []}), 0.0)


class TestAssessMerge(unittest.TestCase):
    """Test merge assessment with multiple apps."""

    def _make_extracted(self, table_names, conn=None):
        conn = conn or {"type": "sqlserver", "details": {"server": "srv", "database": "db"}}
        return {
            "datasources": [{
                "connection": conn,
                "tables": [{"name": n, "columns": [{"name": "ID"}]} for n in table_names],
                "relationships": [],
            }],
            "calculations": [],
            "parameters": [],
            "user_filters": [],
        }

    def test_shared_tables_detected(self):
        e1 = self._make_extracted(["Sales", "Products"])
        e2 = self._make_extracted(["Sales", "Customers"])
        assessment = assess_merge([e1, e2], ["App1", "App2"])
        shared_names = {mc.table_name for mc in assessment.merge_candidates}
        self.assertIn("Sales", shared_names)

    def test_unique_tables_tracked(self):
        e1 = self._make_extracted(["Sales", "Unique1"])
        e2 = self._make_extracted(["Sales"])
        assessment = assess_merge([e1, e2], ["App1", "App2"])
        unique_app1 = assessment.unique_tables.get("App1", [])
        self.assertIn("Unique1", unique_app1)

    def test_merge_score_calculated(self):
        e1 = self._make_extracted(["Sales", "Products"])
        e2 = self._make_extracted(["Sales", "Products"])
        assessment = assess_merge([e1, e2], ["App1", "App2"])
        self.assertIsInstance(assessment.merge_score, int)
        self.assertGreater(assessment.merge_score, 0)

    def test_single_app_no_candidates(self):
        e1 = self._make_extracted(["Sales"])
        assessment = assess_merge([e1], ["App1"])
        self.assertEqual(len(assessment.merge_candidates), 0)

    def test_total_tables_counted(self):
        e1 = self._make_extracted(["A", "B"])
        e2 = self._make_extracted(["B", "C"])
        assessment = assess_merge([e1, e2], ["W1", "W2"])
        self.assertEqual(assessment.total_tables, 4)

    def test_to_dict(self):
        e1 = self._make_extracted(["Sales"])
        e2 = self._make_extracted(["Sales"])
        assessment = assess_merge([e1, e2], ["A", "B"])
        d = assessment.to_dict()
        self.assertIn("apps", d)
        self.assertIn("merge_candidates", d)
        self.assertIn("merge_score", d)


if __name__ == "__main__":
    unittest.main()
