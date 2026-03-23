"""Tests for generate_report.py — HTML migration dashboard."""

import json
import os
import pytest
import tempfile

from generate_report import generate_html, generate_dashboard, generate_batch_dashboard


# ── Fixtures ─────────────────────────────────────────────────────

def _sample_assessment(name="SalesApp"):
    return {
        "app_name": name,
        "timestamp": "2025-01-15T10:00:00",
        "overall_score": "GREEN",
        "summary": f"Assessment for {name}",
        "totals": {"checks": 20, "pass": 16, "warn": 3, "fail": 1},
        "categories": [
            {
                "name": "Data Sources",
                "worst_severity": "warn",
                "checks": [
                    {"name": "Connector: SQL Server", "severity": "pass", "detail": "Supported", "recommendation": ""},
                    {"name": "Connector: Excel", "severity": "warn", "detail": "Excel detected", "recommendation": "Use dataflow"},
                    {"name": "Complexity", "severity": "pass", "detail": "Complexity score: 2.5", "recommendation": ""},
                ],
            },
            {
                "name": "Calculations",
                "worst_severity": "fail",
                "checks": [
                    {"name": "Unsupported function", "severity": "fail", "detail": "KeepChar used", "recommendation": "Manual fix needed"},
                ],
            },
        ],
    }


def _sample_report(name="SalesApp"):
    return {
        "report_name": name,
        "created_at": "2025-01-15T10:01:00",
        "summary": {
            "total_items": 50,
            "exact": 40,
            "approximate": 7,
            "placeholder": 1,
            "unsupported": 2,
            "skipped": 0,
            "fidelity_score": 85.0,
            "by_category": {
                "calculation": {"total": 20, "exact": 15, "approximate": 5},
                "datasource": {"total": 5, "exact": 5, "approximate": 0},
                "visual": {"total": 15, "exact": 12, "approximate": 3},
                "parameter": {"total": 3, "exact": 3, "approximate": 0},
                "relationship": {"total": 7, "exact": 5, "approximate": 2},
            },
        },
        "items": [
            {"category": "calculation", "name": "Total Sales", "status": "exact",
             "source_formula": "Sum(Sales)", "dax": "SUM('Sales'[Amount])"},
            {"category": "calculation", "name": "YTD Revenue", "status": "approximate",
             "source_formula": "RangeSum(Above(Sum(Revenue),0,RowNo()))",
             "dax": "CALCULATE(SUM('Revenue'[Amount]), DATESYTD('Calendar'[Date]))"},
            {"category": "datasource", "name": "Orders", "status": "exact",
             "note": "SQL Server, Orders table"},
            {"category": "visual", "name": "SalesBarChart", "status": "exact",
             "note": "barchart → clusteredBarChart"},
            {"category": "visual", "name": "KPI Card", "status": "approximate",
             "note": "kpi → card"},
            {"category": "calculation", "name": "ComplexCalc", "status": "unsupported",
             "source_formula": "Aggr(Count(Distinct ID), Region)", "dax": "// UNSUPPORTED"},
        ],
    }


def _sample_metadata(name="SalesApp"):
    return {
        "tmdl_stats": {"tables": 5, "columns": 30, "measures": 10, "relationships": 3},
        "generated_output": {"pages": 3, "visuals": 12},
        "objects_converted": {
            "calculations": 20, "worksheets": 3, "filters": 5,
            "datasources": 2, "sheets": 3,
        },
        "visual_type_mappings": {"barchart": "clusteredBarChart", "kpi": "card"},
    }


# ── generate_html() ──────────────────────────────────────────────

class TestGenerateHtml:
    def test_empty_data(self):
        html = generate_html({}, {}, {})
        assert "<!DOCTYPE html>" in html or "<!doctype" in html.lower()
        assert "</html>" in html

    def test_with_assessment_only(self):
        html = generate_html({"App1": _sample_assessment("App1")}, {}, {})
        assert "App1" in html
        assert "GREEN" in html

    def test_with_report_only(self):
        html = generate_html({}, {"App1": _sample_report("App1")}, {})
        assert "App1" in html
        assert "85" in html  # fidelity

    def test_with_metadata_only(self):
        html = generate_html({}, {}, {"App1": _sample_metadata()})
        assert "<!DOCTYPE html>" in html or "<!doctype" in html.lower()
        assert "</html>" in html

    def test_full_data(self):
        assessments = {"App1": _sample_assessment("App1")}
        reports = {"App1": _sample_report("App1")}
        metadata = {"App1": _sample_metadata("App1")}
        html = generate_html(assessments, reports, metadata)
        assert "<!DOCTYPE html>" in html
        assert "App1" in html
        assert "Executive Summary" in html
        assert "Assessment Results" in html
        assert "Migration Results" in html

    def test_multiple_apps(self):
        assessments = {
            "App1": _sample_assessment("App1"),
            "App2": _sample_assessment("App2"),
        }
        reports = {
            "App1": _sample_report("App1"),
            "App2": _sample_report("App2"),
        }
        html = generate_html(assessments, reports, {})
        assert "App1" in html
        assert "App2" in html

    def test_contains_stat_cards(self):
        html = generate_html({}, {"A": _sample_report("A")}, {})
        assert "Qlik Apps" in html
        assert "Fidelity" in html

    def test_contains_converted_items(self):
        html = generate_html({}, {"A": _sample_report("A")}, {})
        assert "Total Sales" in html
        assert "SUM" in html

    def test_assessment_badges(self):
        html = generate_html({"A": _sample_assessment("A")}, {}, {})
        assert "GREEN" in html

    def test_fidelity_bar_present(self):
        html = generate_html({}, {"A": _sample_report("A")}, {})
        assert "85" in html

    def test_category_breakdown(self):
        html = generate_html({}, {"A": _sample_report("A")}, {})
        assert "Calculation" in html
        assert "Datasource" in html

    def test_assessment_warnings_section(self):
        html = generate_html({"A": _sample_assessment("A")}, {"A": _sample_report("A")}, {})
        assert "KeepChar" in html  # from the fail check

    def test_visual_type_mappings(self):
        html = generate_html({}, {"A": _sample_report("A")}, {"A": _sample_metadata()})
        assert "clusteredBarChart" in html

    def test_xss_safe(self):
        evil_assess = _sample_assessment("<script>xss</script>")
        evil_assess["app_name"] = "<script>alert(1)</script>"
        html = generate_html({"evil": evil_assess}, {}, {})
        assert "<script>alert" not in html
        assert "<script>xss" not in html


# ── generate_dashboard() ─────────────────────────────────────────

class TestGenerateDashboard:
    def test_no_artifacts_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = generate_dashboard("NoApp", tmp)
            assert result is None

    def test_with_migration_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = _sample_report("TestApp")
            report_path = os.path.join(tmp, "migration_report_TestApp_20250115.json")
            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(report, f)

            result = generate_dashboard(
                "TestApp", tmp,
                migration_report_path=report_path,
            )
            assert result is not None
            assert result.endswith(".html")
            assert os.path.isfile(result)

            with open(result, encoding="utf-8") as f:
                html = f.read()
            assert "TestApp" in html
            assert "<!DOCTYPE html>" in html

    def test_with_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = _sample_report("App2")
            report_path = os.path.join(tmp, "report.json")
            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(report, f)

            meta_dir = os.path.join(tmp, "App2")
            os.makedirs(meta_dir, exist_ok=True)
            meta_path = os.path.join(meta_dir, "migration_metadata.json")
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(_sample_metadata("App2"), f)

            result = generate_dashboard(
                "App2", tmp,
                migration_report_path=report_path,
                metadata_path=meta_path,
            )
            assert result is not None
            assert os.path.isfile(result)

    def test_auto_discover_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = _sample_report("Auto")
            fname = os.path.join(tmp, "migration_report_Auto_20250115.json")
            with open(fname, "w", encoding="utf-8") as f:
                json.dump(report, f)

            result = generate_dashboard("Auto", tmp)
            assert result is not None
            assert os.path.isfile(result)


# ── generate_batch_dashboard() ────────────────────────────────────

class TestBatchDashboard:
    def test_no_results_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = generate_batch_dashboard(tmp, {})
            assert result is None

    def test_batch_with_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            report1 = _sample_report("App1")
            report2 = _sample_report("App2")
            rp1 = os.path.join(tmp, "r1.json")
            rp2 = os.path.join(tmp, "r2.json")
            with open(rp1, "w", encoding="utf-8") as f:
                json.dump(report1, f)
            with open(rp2, "w", encoding="utf-8") as f:
                json.dump(report2, f)

            result = generate_batch_dashboard(tmp, {
                "App1": {"migration_report_path": rp1},
                "App2": {"migration_report_path": rp2},
            })
            assert result is not None
            assert result.endswith(".html")
            assert os.path.isfile(result)

            with open(result, encoding="utf-8") as f:
                html = f.read()
            assert "App1" in html
            assert "App2" in html


# ── HTML structure validation ─────────────────────────────────────

class TestHtmlStructure:
    def test_has_css_style(self):
        html = generate_html({}, {"A": _sample_report("A")}, {})
        assert "<style>" in html

    def test_has_javascript(self):
        html = generate_html({}, {"A": _sample_report("A")}, {})
        assert "<script>" in html

    def test_sections_present(self):
        html = generate_html(
            {"A": _sample_assessment("A")},
            {"A": _sample_report("A")},
            {"A": _sample_metadata()},
        )
        for section in ["Executive Summary", "Generated Artifacts",
                        "Assessment Results", "Migration Results",
                        "Converted Items", "Per-App Details"]:
            assert section in html, f"Section '{section}' not found"

    def test_no_unclosed_divs(self):
        """Rough check that div count is balanced."""
        html = generate_html({}, {"A": _sample_report("A")}, {})
        opens = html.count("<div")
        closes = html.count("</div>")
        assert abs(opens - closes) <= 2, f"Unbalanced divs: {opens} opens, {closes} closes"

    def test_no_python_objects_leaked(self):
        """Ensure no raw Python repr leaks into HTML."""
        html = generate_html(
            {"A": _sample_assessment("A")},
            {"A": _sample_report("A")},
            {"A": _sample_metadata()},
        )
        assert "{''" not in html
        assert "<class " not in html
        assert "None" not in html or "NoneType" not in html
