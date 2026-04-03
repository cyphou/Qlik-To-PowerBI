"""Tests for powerbi_import.sla_tracker — per-app SLA compliance tracking."""

import time
import unittest

from powerbi_import.sla_tracker import (
    SLATracker,
    SLAResult,
    SLAReport,
    DEFAULT_SLA_CONFIG,
)


class TestSLAResult(unittest.TestCase):
    """Test SLAResult data class."""

    def test_compliant_when_all_pass(self):
        r = SLAResult(app="test", time_compliant=True,
                      fidelity_compliant=True, validation_compliant=True)
        self.assertTrue(r.compliant)

    def test_non_compliant_on_time_breach(self):
        r = SLAResult(app="test", time_compliant=False)
        self.assertFalse(r.compliant)

    def test_non_compliant_on_fidelity_breach(self):
        r = SLAResult(app="test", fidelity_compliant=False)
        self.assertFalse(r.compliant)

    def test_to_dict(self):
        r = SLAResult(app="demo", migration_seconds=5.0, fidelity_score=90.0)
        d = r.to_dict()
        self.assertEqual(d["app"], "demo")
        self.assertEqual(d["migration_seconds"], 5.0)
        self.assertIn("compliant", d)


class TestSLATracker(unittest.TestCase):
    """Test SLA tracking workflow."""

    def test_compliant_migration(self):
        tracker = SLATracker({"max_migration_seconds": 60, "min_fidelity_score": 80.0,
                              "require_validation_pass": True, "alert_on_breach": False})
        tracker.start("app1")
        result = tracker.record_result("app1", fidelity=95.0, validation_passed=True)
        self.assertTrue(result.compliant)
        self.assertEqual(result.breaches, [])

    def test_fidelity_breach(self):
        tracker = SLATracker({"max_migration_seconds": 60, "min_fidelity_score": 80.0,
                              "require_validation_pass": False, "alert_on_breach": False})
        tracker.start("app1")
        result = tracker.record_result("app1", fidelity=50.0)
        self.assertFalse(result.fidelity_compliant)
        self.assertTrue(any("Fidelity" in b for b in result.breaches))

    def test_validation_breach(self):
        tracker = SLATracker({"max_migration_seconds": 600, "min_fidelity_score": 0,
                              "require_validation_pass": True, "alert_on_breach": False})
        tracker.start("app1")
        result = tracker.record_result("app1", fidelity=100.0, validation_passed=False)
        self.assertFalse(result.validation_compliant)
        self.assertTrue(any("validation" in b.lower() for b in result.breaches))

    def test_report_aggregation(self):
        tracker = SLATracker({"max_migration_seconds": 600, "min_fidelity_score": 80.0,
                              "require_validation_pass": False, "alert_on_breach": False})
        tracker.start("app1")
        tracker.record_result("app1", fidelity=95.0)
        tracker.start("app2")
        tracker.record_result("app2", fidelity=50.0)
        report = tracker.get_report()
        self.assertEqual(report.total_apps, 2)
        self.assertEqual(report.compliant_count, 1)
        self.assertEqual(report.breach_count, 1)
        self.assertEqual(report.compliance_rate, 50.0)

    def test_report_to_dict(self):
        tracker = SLATracker({"alert_on_breach": False})
        tracker.start("app1")
        tracker.record_result("app1", fidelity=100.0, validation_passed=True)
        report = tracker.get_report()
        d = report.to_dict()
        self.assertIn("timestamp", d)
        self.assertIn("compliance_rate", d)
        self.assertIn("results", d)
        self.assertEqual(len(d["results"]), 1)

    def test_reset_clears_state(self):
        tracker = SLATracker({"alert_on_breach": False})
        tracker.start("app1")
        tracker.record_result("app1", fidelity=90.0)
        tracker.reset()
        report = tracker.get_report()
        self.assertEqual(report.total_apps, 0)

    def test_no_start_gives_zero_time(self):
        tracker = SLATracker({"max_migration_seconds": 60, "alert_on_breach": False})
        result = tracker.record_result("unstarted", fidelity=90.0, validation_passed=True)
        self.assertEqual(result.migration_seconds, 0.0)
        self.assertTrue(result.time_compliant)


class TestSLAReport(unittest.TestCase):
    def test_empty_compliance_rate(self):
        report = SLAReport()
        self.assertEqual(report.compliance_rate, 100.0)


if __name__ == "__main__":
    unittest.main()
