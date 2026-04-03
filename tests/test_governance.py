"""Tests for powerbi_import.governance — naming conventions, PII, audit trail."""

import json
import os
import tempfile
import unittest

from powerbi_import.governance import (
    GovernanceEngine,
    GovernanceReport,
    AuditTrail,
    _is_snake_case,
    _is_camel_case,
    _is_pascal_case,
    _to_snake_case,
    _to_pascal_case,
    DEFAULT_GOVERNANCE_CONFIG,
)


class TestNamingHelpers(unittest.TestCase):
    """Test naming convention helpers."""

    def test_snake_case_valid(self):
        self.assertTrue(_is_snake_case("order_id"))
        self.assertTrue(_is_snake_case("total"))

    def test_snake_case_invalid(self):
        self.assertFalse(_is_snake_case("OrderId"))
        self.assertFalse(_is_snake_case("order-id"))

    def test_camel_case_valid(self):
        self.assertTrue(_is_camel_case("orderId"))
        self.assertTrue(_is_camel_case("total"))

    def test_camel_case_invalid(self):
        self.assertFalse(_is_camel_case("OrderId"))
        self.assertFalse(_is_camel_case("order_id"))

    def test_pascal_case_valid(self):
        self.assertTrue(_is_pascal_case("OrderId"))
        self.assertTrue(_is_pascal_case("Total"))

    def test_pascal_case_invalid(self):
        self.assertFalse(_is_pascal_case("orderId"))
        self.assertFalse(_is_pascal_case("order_id"))

    def test_to_snake_case_conversion(self):
        self.assertEqual(_to_snake_case("OrderId"), "order_id")
        self.assertEqual(_to_snake_case("MyTableName"), "my_table_name")

    def test_to_pascal_case_conversion(self):
        self.assertEqual(_to_pascal_case("order_id"), "OrderId")


class TestGovernanceEnginePII(unittest.TestCase):
    """Test PII detection."""

    def test_email_detected(self):
        engine = GovernanceEngine({"pii_detection": True})
        tables = [{"name": "Users", "columns": [{"name": "EmailAddress"}], "measures": []}]
        report = engine.check(tables)
        pii_issues = [i for i in report.issues if i.category == "pii"]
        self.assertGreater(len(pii_issues), 0)
        self.assertIn("email", report.classifications.get("Users.EmailAddress", ""))

    def test_ssn_detected(self):
        engine = GovernanceEngine({"pii_detection": True})
        tables = [{"name": "Employees", "columns": [{"name": "SSN"}], "measures": []}]
        report = engine.check(tables)
        pii_issues = [i for i in report.issues if i.category == "pii"]
        self.assertGreater(len(pii_issues), 0)

    def test_phone_detected(self):
        engine = GovernanceEngine({"pii_detection": True})
        tables = [{"name": "Contacts", "columns": [{"name": "PhoneNumber"}], "measures": []}]
        report = engine.check(tables)
        pii_issues = [i for i in report.issues if i.category == "pii"]
        self.assertGreater(len(pii_issues), 0)

    def test_dob_detected(self):
        engine = GovernanceEngine({"pii_detection": True})
        tables = [{"name": "Patients", "columns": [{"name": "DateOfBirth"}], "measures": []}]
        report = engine.check(tables)
        pii_issues = [i for i in report.issues if i.category == "pii"]
        self.assertGreater(len(pii_issues), 0)

    def test_no_pii_when_disabled(self):
        engine = GovernanceEngine({"pii_detection": False})
        tables = [{"name": "Users", "columns": [{"name": "Email"}], "measures": []}]
        report = engine.check(tables)
        pii_issues = [i for i in report.issues if i.category == "pii"]
        self.assertEqual(len(pii_issues), 0)

    def test_non_pii_column_clean(self):
        engine = GovernanceEngine({"pii_detection": True})
        tables = [{"name": "Sales", "columns": [{"name": "Revenue"}], "measures": []}]
        report = engine.check(tables)
        pii_issues = [i for i in report.issues if i.category == "pii"]
        self.assertEqual(len(pii_issues), 0)


class TestGovernanceEngineNaming(unittest.TestCase):
    """Test naming convention enforcement."""

    def test_table_naming_pascal_case(self):
        engine = GovernanceEngine({"naming": {"table_style": "PascalCase"}})
        tables = [{"name": "my_table", "columns": [], "measures": []}]
        report = engine.check(tables)
        naming_issues = [i for i in report.issues if i.category == "naming"]
        self.assertGreater(len(naming_issues), 0)

    def test_table_naming_passes_when_correct(self):
        engine = GovernanceEngine({"naming": {"table_style": "PascalCase"}})
        tables = [{"name": "MyTable", "columns": [], "measures": []}]
        report = engine.check(tables)
        table_issues = [i for i in report.issues
                        if i.category == "naming" and i.artifact_type == "table"]
        self.assertEqual(len(table_issues), 0)

    def test_column_naming_snake_case(self):
        engine = GovernanceEngine({"naming": {"column_style": "snake_case"}})
        tables = [{"name": "T", "columns": [{"name": "OrderId"}], "measures": []}]
        report = engine.check(tables)
        col_issues = [i for i in report.issues if i.artifact_type == "column"]
        self.assertGreater(len(col_issues), 0)

    def test_measure_prefix_enforcement(self):
        engine = GovernanceEngine({"naming": {"measure_prefix": "m_"}})
        tables = [{"name": "T", "columns": [], "measures": [{"name": "TotalSales"}]}]
        report = engine.check(tables)
        meas_issues = [i for i in report.issues if i.artifact_type == "measure"]
        self.assertGreater(len(meas_issues), 0)

    def test_measure_with_correct_prefix_passes(self):
        engine = GovernanceEngine({"naming": {"measure_prefix": "m_"}})
        tables = [{"name": "T", "columns": [], "measures": [{"name": "m_TotalSales"}]}]
        report = engine.check(tables)
        meas_issues = [i for i in report.issues if i.artifact_type == "measure"]
        self.assertEqual(len(meas_issues), 0)

    def test_enforce_mode_severity(self):
        engine = GovernanceEngine({"mode": "enforce", "naming": {"table_style": "PascalCase"}})
        tables = [{"name": "bad_table", "columns": [], "measures": []}]
        report = engine.check(tables)
        self.assertEqual(report.mode, "enforce")
        table_issues = [i for i in report.issues if i.artifact_type == "table"]
        self.assertTrue(all(i.severity == "fail" for i in table_issues))


class TestGovernanceReport(unittest.TestCase):
    """Test GovernanceReport data class."""

    def test_empty_report(self):
        report = GovernanceReport()
        self.assertEqual(report.issue_count, 0)
        self.assertEqual(report.warn_count, 0)
        self.assertEqual(report.fail_count, 0)

    def test_to_dict(self):
        engine = GovernanceEngine({"pii_detection": True})
        tables = [{"name": "T", "columns": [{"name": "Email"}], "measures": []}]
        report = engine.check(tables)
        d = report.to_dict()
        self.assertIn("issue_count", d)
        self.assertIn("issues", d)
        self.assertIsInstance(d["issues"], list)


class TestAuditTrail(unittest.TestCase):
    """Test append-only audit log."""

    def test_record_creates_entry(self):
        trail = AuditTrail()
        entry = trail.record(app_name="TestApp", source_file="app.qvf")
        self.assertIn("id", entry)
        self.assertIn("timestamp", entry)
        self.assertEqual(entry["app"], "TestApp")

    def test_save_and_read(self):
        with tempfile.TemporaryDirectory() as td:
            log_path = os.path.join(td, "audit.jsonl")
            trail = AuditTrail(log_path=log_path)
            trail.record(app_name="App1")
            trail.record(app_name="App2")
            saved = trail.save()
            self.assertEqual(saved, 2)
            entries = trail.read()
            self.assertEqual(len(entries), 2)
            self.assertEqual(entries[0]["app"], "App1")

    def test_save_clears_buffer(self):
        with tempfile.TemporaryDirectory() as td:
            log_path = os.path.join(td, "audit.jsonl")
            trail = AuditTrail(log_path=log_path)
            trail.record(app_name="A")
            trail.save()
            # Second save should write 0
            second = trail.save()
            self.assertEqual(second, 0)

    def test_read_empty_nonexistent(self):
        trail = AuditTrail(log_path="/nonexistent/audit.jsonl")
        entries = trail.read()
        self.assertEqual(entries, [])


if __name__ == "__main__":
    unittest.main()
