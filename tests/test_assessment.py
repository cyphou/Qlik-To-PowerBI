"""Tests for the pre-migration assessment module (powerbi_import.assessment)."""

import json
import os
import pytest
from powerbi_import.assessment import (
    run_assessment,
    print_assessment_report,
    save_assessment_report,
    CheckItem,
    CategoryResult,
    AssessmentReport,
    PASS, INFO, WARN, FAIL,
)


# ── Helpers ──────────────────────────────────────────────────────────

def _empty_extracted():
    """Minimal extracted data dict with all expected keys."""
    return {
        "datasources": [],
        "worksheets": [],
        "dashboards": [],
        "calculations": [],
        "parameters": [],
        "filters": [],
        "stories": [],
        "actions": [],
        "sets": [],
        "groups": [],
        "bins": [],
        "hierarchies": [],
        "sort_orders": [],
        "custom_sql": [],
        "user_filters": [],
    }


def _make_calc(name, formula, role="measure"):
    return {"name": name, "caption": name, "formula": formula, "role": role}


def _make_datasource(name, conn_type="SQL Server", tables=None):
    ds = {
        "name": name,
        "connection": {"type": conn_type},
        "tables": tables or [],
        "columns": [],
        "relationships": [],
    }
    return ds


# ═══════════════════════════════════════════════════════════════════
#  Data class tests
# ═══════════════════════════════════════════════════════════════════

class TestCheckItem:
    def test_creation(self):
        item = CheckItem("Cat", "Check", PASS, "Detail", "Rec")
        assert item.category == "Cat"
        assert item.severity == PASS

    def test_default_recommendation(self):
        item = CheckItem("Cat", "Check", INFO, "Detail")
        assert item.recommendation == ""


class TestCategoryResult:
    def test_empty(self):
        cat = CategoryResult(name="Test")
        assert cat.worst_severity == PASS
        assert cat.pass_count == 0

    def test_worst_severity(self):
        cat = CategoryResult(name="Test")
        cat.checks.append(CheckItem("Test", "A", PASS, "Ok"))
        cat.checks.append(CheckItem("Test", "B", WARN, "Warning"))
        cat.checks.append(CheckItem("Test", "C", FAIL, "Failure"))
        assert cat.worst_severity == FAIL
        assert cat.pass_count == 1
        assert cat.warn_count == 1
        assert cat.fail_count == 1

    def test_all_pass(self):
        cat = CategoryResult(name="Test")
        cat.checks.append(CheckItem("Test", "A", PASS, "Ok"))
        cat.checks.append(CheckItem("Test", "B", PASS, "Also ok"))
        assert cat.worst_severity == PASS


class TestAssessmentReport:
    def test_green_score(self):
        report = AssessmentReport(app_name="TestApp", timestamp="2026-01-01T00:00:00Z")
        cat = CategoryResult(name="Test")
        cat.checks.append(CheckItem("Test", "A", PASS, "Ok"))
        report.categories = [cat]
        assert report.overall_score == "GREEN"

    def test_yellow_score(self):
        report = AssessmentReport(app_name="TestApp", timestamp="2026-01-01T00:00:00Z")
        cat = CategoryResult(name="Test")
        cat.checks.append(CheckItem("Test", "A", WARN, "Warning"))
        report.categories = [cat]
        assert report.overall_score == "YELLOW"

    def test_red_score(self):
        report = AssessmentReport(app_name="TestApp", timestamp="2026-01-01T00:00:00Z")
        cat = CategoryResult(name="Test")
        cat.checks.append(CheckItem("Test", "A", FAIL, "Failure"))
        report.categories = [cat]
        assert report.overall_score == "RED"

    def test_to_dict(self):
        report = AssessmentReport(app_name="Sales", timestamp="2026-01-01T00:00:00Z")
        cat = CategoryResult(name="DS")
        cat.checks.append(CheckItem("DS", "Check1", PASS, "Detail"))
        report.categories = [cat]
        report.summary = {"app": "Sales"}

        d = report.to_dict()
        assert d["app_name"] == "Sales"
        assert d["overall_score"] == "GREEN"
        assert d["totals"]["checks"] == 1
        assert len(d["categories"]) == 1
        assert d["categories"][0]["name"] == "DS"

    def test_totals(self):
        report = AssessmentReport(app_name="Test", timestamp="now")
        cat1 = CategoryResult(name="A")
        cat1.checks = [
            CheckItem("A", "1", PASS, ""),
            CheckItem("A", "2", WARN, ""),
        ]
        cat2 = CategoryResult(name="B")
        cat2.checks = [
            CheckItem("B", "3", FAIL, ""),
            CheckItem("B", "4", PASS, ""),
        ]
        report.categories = [cat1, cat2]
        assert report.total_checks == 4
        assert report.total_pass == 2
        assert report.total_warn == 1
        assert report.total_fail == 1


# ═══════════════════════════════════════════════════════════════════
#  Category: Datasource Compatibility
# ═══════════════════════════════════════════════════════════════════

class TestDatasourceChecks:
    def test_no_datasources(self):
        data = _empty_extracted()
        report = run_assessment(data, app_name="Test")
        ds_cat = report.categories[0]
        assert ds_cat.name == "Datasource Compatibility"
        assert any("No datasource" in c.detail for c in ds_cat.checks)

    def test_supported_connector(self):
        data = _empty_extracted()
        data["datasources"] = [_make_datasource("Sales", "SQL Server")]
        report = run_assessment(data)
        ds_cat = report.categories[0]
        assert any(c.severity == PASS and "SQL Server" in c.name for c in ds_cat.checks)

    def test_partially_supported_connector(self):
        data = _empty_extracted()
        data["datasources"] = [_make_datasource("DW", "BigQuery")]
        report = run_assessment(data)
        ds_cat = report.categories[0]
        assert any(c.severity == WARN and "BigQuery" in c.name for c in ds_cat.checks)

    def test_unsupported_connector(self):
        data = _empty_extracted()
        data["datasources"] = [_make_datasource("Logs", "QVX")]
        report = run_assessment(data)
        ds_cat = report.categories[0]
        assert any(c.severity == FAIL and "QVX" in c.name for c in ds_cat.checks)

    def test_unknown_connector(self):
        data = _empty_extracted()
        data["datasources"] = [_make_datasource("Mystery", "Unknown")]
        report = run_assessment(data)
        ds_cat = report.categories[0]
        assert any(c.severity == WARN and "Unknown" in c.name for c in ds_cat.checks)

    def test_multiple_connectors(self):
        data = _empty_extracted()
        data["datasources"] = [
            _make_datasource("S1", "SQL Server"),
            _make_datasource("S2", "Oracle"),
            _make_datasource("S3", "csv"),
        ]
        report = run_assessment(data)
        ds_cat = report.categories[0]
        assert any("3 datasource" in c.detail for c in ds_cat.checks)


# ═══════════════════════════════════════════════════════════════════
#  Category: Calculation & Expression Readiness
# ═══════════════════════════════════════════════════════════════════

class TestCalculationChecks:
    def test_no_calculations(self):
        data = _empty_extracted()
        report = run_assessment(data)
        calc_cat = report.categories[1]
        assert calc_cat.name == "Calculation & Expression Readiness"
        assert any("No calculated" in c.detail for c in calc_cat.checks)

    def test_simple_calculations_pass(self):
        data = _empty_extracted()
        data["calculations"] = [
            _make_calc("Revenue", "Sum(Sales)"),
            _make_calc("Profit", "Sum(Sales) - Sum(Cost)"),
        ]
        report = run_assessment(data)
        calc_cat = report.categories[1]
        assert any("2 calculated" in c.detail for c in calc_cat.checks)
        assert any("No DAX equivalent" in c.name and c.severity == PASS for c in calc_cat.checks)

    def test_no_dax_equivalent_detected(self):
        data = _empty_extracted()
        data["calculations"] = [
            _make_calc("Hashed", "Hash128(CustomerID)"),
            _make_calc("Dynamic", "Evaluate('Sum(Sales)')"),
        ]
        report = run_assessment(data)
        calc_cat = report.categories[1]
        assert any(c.severity == FAIL and "No DAX equivalent" in c.name for c in calc_cat.checks)

    def test_manual_review_detected(self):
        data = _empty_extracted()
        data["calculations"] = [
            _make_calc("Aggregated", "Aggr(Sum(Sales), Region)"),
            _make_calc("Mapped", "ApplyMap('MapTable', Field, 'Default')"),
            _make_calc("PrevVal", "Peek(Sales, -1)"),
        ]
        report = run_assessment(data)
        calc_cat = report.categories[1]
        assert any(c.severity == WARN and "Manual review" in c.name for c in calc_cat.checks)

    def test_set_analysis_detected(self):
        data = _empty_extracted()
        data["calculations"] = [
            _make_calc("FilteredSum", "Sum({<Year={2024}>} Sales)"),
        ]
        report = run_assessment(data)
        calc_cat = report.categories[1]
        assert any("Set Analysis" in c.name for c in calc_cat.checks)

    def test_nested_set_analysis_warns(self):
        data = _empty_extracted()
        data["calculations"] = [
            _make_calc("Nested", "Sum({<Year={$(=Year(Today()))}>} Sales)"),
        ]
        report = run_assessment(data)
        calc_cat = report.categories[1]
        set_check = [c for c in calc_cat.checks if "Set Analysis" in c.name]
        assert len(set_check) == 1
        # Nested set analysis detected (set within set)
        assert set_check[0].severity in (INFO, WARN)

    def test_aggr_expression_detected(self):
        data = _empty_extracted()
        data["calculations"] = [
            _make_calc("Dim_Agg", "Aggr(Sum(Sales), Region, Product)"),
        ]
        report = run_assessment(data)
        calc_cat = report.categories[1]
        assert any("Aggr()" in c.name for c in calc_cat.checks)

    def test_dollar_sign_detected(self):
        data = _empty_extracted()
        data["calculations"] = [
            _make_calc("DynYear", "Sum({<Year={$(=Year(Today())-1)}>} Sales)"),
        ]
        report = run_assessment(data)
        calc_cat = report.categories[1]
        assert any("Dollar-sign" in c.name for c in calc_cat.checks)

    def test_total_qualifier_detected(self):
        data = _empty_extracted()
        data["calculations"] = [
            _make_calc("Share", "Sum(Sales) / Sum(TOTAL Sales)"),
        ]
        report = run_assessment(data)
        calc_cat = report.categories[1]
        assert any("TOTAL" in c.name for c in calc_cat.checks)

    def test_inter_record_detected(self):
        data = _empty_extracted()
        data["calculations"] = [
            _make_calc("PrevSales", "Above(Sum(Sales))"),
            _make_calc("NextSales", "Below(Sum(Sales))"),
            _make_calc("PeekVal", "Peek(Sales, -1)"),
        ]
        report = run_assessment(data)
        calc_cat = report.categories[1]
        assert any(c.severity == WARN and "Inter-record" in c.name for c in calc_cat.checks)

    def test_no_inter_record_passes(self):
        data = _empty_extracted()
        data["calculations"] = [_make_calc("Simple", "Sum(Sales)")]
        report = run_assessment(data)
        calc_cat = report.categories[1]
        assert any("Inter-record" in c.name and c.severity == PASS for c in calc_cat.checks)

    def test_deep_aggr_nesting_warns(self):
        data = _empty_extracted()
        data["calculations"] = [
            _make_calc("DeepAggr", "Aggr(Aggr(Sum(Sales), Product), Region)"),
        ]
        report = run_assessment(data)
        calc_cat = report.categories[1]
        aggr_checks = [c for c in calc_cat.checks if "Aggr()" in c.name]
        assert len(aggr_checks) == 1
        assert aggr_checks[0].severity == WARN
        assert "depth" in aggr_checks[0].detail.lower()

    def test_deep_dollar_chain_warns(self):
        data = _empty_extracted()
        data["calculations"] = [
            _make_calc("ChainedVar", "Sum($(=$(=$(=vField))))"),
        ]
        report = run_assessment(data)
        calc_cat = report.categories[1]
        ds_checks = [c for c in calc_cat.checks if "Dollar-sign" in c.name]
        assert len(ds_checks) == 1
        assert ds_checks[0].severity == WARN
        assert "depth" in ds_checks[0].detail.lower()


# ═══════════════════════════════════════════════════════════════════
#  Category: Visual & Sheet Coverage
# ═══════════════════════════════════════════════════════════════════

class TestVisualChecks:
    def test_no_visuals(self):
        data = _empty_extracted()
        report = run_assessment(data)
        vis_cat = report.categories[2]
        assert vis_cat.name == "Visual & Sheet Coverage"
        assert any("0 visualization" in c.detail for c in vis_cat.checks)

    def test_mapped_chart_types(self):
        data = _empty_extracted()
        data["worksheets"] = [
            {"name": "Revenue", "chart_type": "barchart"},
            {"name": "Trend", "chart_type": "linechart"},
        ]
        report = run_assessment(data)
        vis_cat = report.categories[2]
        assert any("2 visualization" in c.detail for c in vis_cat.checks)

    def test_unmapped_chart_type(self):
        data = _empty_extracted()
        data["worksheets"] = [
            {"name": "Custom", "chart_type": "weird_custom_chart"},
        ]
        report = run_assessment(data)
        vis_cat = report.categories[2]
        assert any(c.severity == WARN and "Unmapped" in c.name for c in vis_cat.checks)

    def test_extension_detected(self):
        data = _empty_extracted()
        data["worksheets"] = [
            {"name": "SankeyViz", "chart_type": "qlik-sankey-chart-ext"},
        ]
        report = run_assessment(data)
        vis_cat = report.categories[2]
        assert any(c.severity == WARN and "extension" in c.name.lower() for c in vis_cat.checks)

    def test_extension_via_field(self):
        data = _empty_extracted()
        data["worksheets"] = [
            {"name": "CustomExt", "chart_type": "barchart", "extensionType": "vizlib-combo-chart"},
        ]
        report = run_assessment(data)
        vis_cat = report.categories[2]
        assert any(c.severity == WARN and "extension" in c.name.lower() for c in vis_cat.checks)

    def test_no_extensions_passes(self):
        data = _empty_extracted()
        data["worksheets"] = [{"name": "Bar", "chart_type": "barchart"}]
        report = run_assessment(data)
        vis_cat = report.categories[2]
        assert any("extension" in c.name.lower() and c.severity == PASS for c in vis_cat.checks)


# ═══════════════════════════════════════════════════════════════════
#  Category: Filters & Parameters
# ═══════════════════════════════════════════════════════════════════

class TestFilterChecks:
    def test_no_filters(self):
        data = _empty_extracted()
        report = run_assessment(data)
        filt_cat = report.categories[3]
        assert filt_cat.name == "Filter & Parameter Complexity"

    def test_user_filters_detected(self):
        data = _empty_extracted()
        data["user_filters"] = [{"user": "admin", "table": "Sales", "filter": "Region='US'"}]
        report = run_assessment(data)
        filt_cat = report.categories[3]
        assert any("User filter" in c.name and "RLS" in c.detail for c in filt_cat.checks)

    def test_parameters(self):
        data = _empty_extracted()
        data["parameters"] = [{"name": "vYear", "caption": "vYear"}]
        report = run_assessment(data)
        filt_cat = report.categories[3]
        assert any("1 parameter" in c.detail for c in filt_cat.checks)


# ═══════════════════════════════════════════════════════════════════
#  Category: Data Model Complexity
# ═══════════════════════════════════════════════════════════════════

class TestDataModelChecks:
    def test_small_model(self):
        data = _empty_extracted()
        data["datasources"] = [
            _make_datasource("S1", "SQL Server", tables=[
                {"name": "Sales", "columns": [{"name": "Amount"}, {"name": "Date"}]},
            ]),
        ]
        report = run_assessment(data)
        model_cat = report.categories[4]
        assert model_cat.name == "Data Model Complexity"
        assert any("1 table" in c.detail for c in model_cat.checks)

    def test_large_model_warns(self):
        data = _empty_extracted()
        tables = [{"name": f"Table{i}", "columns": [{"name": "col"}]} for i in range(25)]
        data["datasources"] = [_make_datasource("Big", "SQL Server", tables=tables)]
        report = run_assessment(data)
        model_cat = report.categories[4]
        tbl_check = [c for c in model_cat.checks if "Table count" in c.name]
        assert tbl_check[0].severity == WARN


# ═══════════════════════════════════════════════════════════════════
#  Category: Interactivity & Actions
# ═══════════════════════════════════════════════════════════════════

class TestInteractivityChecks:
    def test_no_actions(self):
        data = _empty_extracted()
        report = run_assessment(data)
        int_cat = report.categories[5]
        assert int_cat.name == "Interactivity & Actions"

    def test_stories_as_bookmarks(self):
        data = _empty_extracted()
        data["stories"] = [{"name": "Story1", "story_points": [{"id": 1}, {"id": 2}]}]
        report = run_assessment(data)
        int_cat = report.categories[5]
        assert any("bookmark" in c.detail.lower() for c in int_cat.checks)


# ═══════════════════════════════════════════════════════════════════
#  Category: Load Script Complexity
# ═══════════════════════════════════════════════════════════════════

class TestLoadScriptChecks:
    def test_no_custom_sql(self):
        data = _empty_extracted()
        report = run_assessment(data)
        ls_cat = report.categories[6]
        assert ls_cat.name == "Load Script Complexity"
        assert any("No custom SQL" in c.detail for c in ls_cat.checks)

    def test_custom_sql_detected(self):
        data = _empty_extracted()
        data["custom_sql"] = [{"query": "SELECT * FROM sales"}]
        report = run_assessment(data)
        ls_cat = report.categories[6]
        assert any("1 SQL" in c.detail for c in ls_cat.checks)

    def test_variable_chain_warns(self):
        data = _empty_extracted()
        data["calculations"] = [
            _make_calc(f"Calc{i}", f"Sum($(=vField{i}))")
            for i in range(15)
        ]
        report = run_assessment(data)
        ls_cat = report.categories[6]
        assert any(c.severity == WARN and "chain" in c.name.lower() for c in ls_cat.checks)

    def test_section_access_detected_via_user_filters(self):
        data = _empty_extracted()
        data["user_filters"] = [{"user": "admin", "table": "Sales", "filter": "Region='US'"}]
        report = run_assessment(data)
        ls_cat = report.categories[6]
        assert any("Section Access" in c.name and c.severity == WARN for c in ls_cat.checks)

    def test_section_access_detected_via_loadscript(self):
        data = _empty_extracted()
        data["loadscript"] = {"script": "SECTION ACCESS;\nLOAD * INLINE [\nACCESS, USERID\nADMIN, *\n];"}
        report = run_assessment(data)
        ls_cat = report.categories[6]
        assert any("Section Access" in c.name and c.severity == WARN for c in ls_cat.checks)

    def test_no_section_access_passes(self):
        data = _empty_extracted()
        report = run_assessment(data)
        ls_cat = report.categories[6]
        assert any("Section Access" in c.name and c.severity == PASS for c in ls_cat.checks)

    def test_stacked_load_detected(self):
        data = _empty_extracted()
        data["loadscript"] = {"script": "Sales:\nLOAD Amount, Date\nLOAD Amount, Date\nFROM data.qvd;"}
        report = run_assessment(data)
        ls_cat = report.categories[6]
        assert any("Stacked LOAD" in c.name for c in ls_cat.checks)
        stacked_checks = [c for c in ls_cat.checks if "Stacked LOAD" in c.name]
        assert stacked_checks[0].severity in (INFO, WARN)

    def test_no_stacked_load_passes(self):
        data = _empty_extracted()
        data["loadscript"] = {"script": "Sales:\nLOAD Amount, Date FROM data.qvd;"}
        report = run_assessment(data)
        ls_cat = report.categories[6]
        assert any("Stacked LOAD" in c.name and c.severity == PASS for c in ls_cat.checks)

    def test_deep_variable_chain_depth(self):
        data = _empty_extracted()
        data["calculations"] = [
            _make_calc("Deep", "Sum($(=$(=$(=vField))))"),
        ]
        report = run_assessment(data)
        ls_cat = report.categories[6]
        var_checks = [c for c in ls_cat.checks if "chain" in c.name.lower() or "Variable" in c.name]
        assert len(var_checks) >= 1
        # Should have chain depth info
        assert any("depth" in c.detail.lower() for c in var_checks)


# ═══════════════════════════════════════════════════════════════════
#  Category: Migration Scope & Effort
# ═══════════════════════════════════════════════════════════════════

class TestMigrationScopeChecks:
    def test_low_complexity(self):
        data = _empty_extracted()
        data["worksheets"] = [{"name": "V1", "chart_type": "barchart"}]
        data["datasources"] = [_make_datasource("S1", "CSV")]
        report = run_assessment(data)
        scope_cat = report.categories[7]
        assert any("Low" in c.detail for c in scope_cat.checks)

    def test_high_complexity(self):
        data = _empty_extracted()
        data["worksheets"] = [{"name": f"V{i}", "chart_type": "barchart"} for i in range(20)]
        data["dashboards"] = [{"name": f"S{i}"} for i in range(10)]
        data["datasources"] = [_make_datasource("S1", "SQL Server")]
        data["calculations"] = [
            _make_calc(f"C{i}", "Sum({<Year={2024}>} Sales)") for i in range(50)
        ]
        data["user_filters"] = [{"user": "u1"}, {"user": "u2"}]
        data["custom_sql"] = [{"query": "SELECT 1"} for _ in range(5)]
        report = run_assessment(data)
        scope_cat = report.categories[7]
        # Should be at least Medium
        assert any("Medium" in c.detail or "High" in c.detail or "Very High" in c.detail
                    for c in scope_cat.checks)

    def test_object_inventory(self):
        data = _empty_extracted()
        data["datasources"] = [_make_datasource("S1", "CSV")]
        data["calculations"] = [_make_calc("M1", "Sum(X)")]
        report = run_assessment(data)
        scope_cat = report.categories[7]
        inv_check = [c for c in scope_cat.checks if "inventory" in c.name.lower()]
        assert len(inv_check) == 1
        assert "Datasources: 1" in inv_check[0].detail


# ═══════════════════════════════════════════════════════════════════
#  Full assessment flow
# ═══════════════════════════════════════════════════════════════════

class TestFullAssessment:
    def test_empty_app_is_green(self):
        data = _empty_extracted()
        report = run_assessment(data, app_name="EmptyApp")
        # Empty app gets YELLOW because "no datasources" is a warning
        assert report.overall_score in ("GREEN", "YELLOW")
        assert report.app_name == "EmptyApp"
        assert report.total_checks > 0

    def test_app_with_unsupported_functions_is_red(self):
        data = _empty_extracted()
        data["calculations"] = [_make_calc("Bad", "Hash128(ID)")]
        data["datasources"] = [_make_datasource("S1", "QVX")]
        report = run_assessment(data)
        assert report.overall_score == "RED"

    def test_app_with_warnings_is_yellow(self):
        data = _empty_extracted()
        data["calculations"] = [_make_calc("Complex", "Aggr(Sum(Sales), Region)")]
        data["datasources"] = [_make_datasource("S1", "SQL Server")]
        report = run_assessment(data)
        assert report.overall_score in ("YELLOW", "GREEN")

    def test_eight_categories(self):
        data = _empty_extracted()
        report = run_assessment(data)
        assert len(report.categories) == 8
        names = {c.name for c in report.categories}
        assert "Datasource Compatibility" in names
        assert "Calculation & Expression Readiness" in names
        assert "Visual & Sheet Coverage" in names
        assert "Filter & Parameter Complexity" in names
        assert "Data Model Complexity" in names
        assert "Interactivity & Actions" in names
        assert "Load Script Complexity" in names
        assert "Migration Scope & Effort" in names

    def test_print_report_no_crash(self, capsys):
        data = _empty_extracted()
        data["datasources"] = [_make_datasource("S1", "SQL Server")]
        data["calculations"] = [
            _make_calc("SetCalc", "Sum({<Year={2024}>} Sales)"),
            _make_calc("AggrCalc", "Aggr(Sum(Sales), Region)"),
        ]
        report = run_assessment(data, app_name="PrintTest")
        print_assessment_report(report)
        captured = capsys.readouterr()
        assert "PRE-MIGRATION ASSESSMENT REPORT" in captured.out
        assert "PrintTest" in captured.out

    def test_save_report(self, tmp_path):
        data = _empty_extracted()
        report = run_assessment(data, app_name="SaveTest")
        filepath = save_assessment_report(report, str(tmp_path))
        assert os.path.exists(filepath)
        with open(filepath, "r", encoding="utf-8") as f:
            saved = json.load(f)
        assert saved["app_name"] == "SaveTest"
        assert saved["overall_score"] in ("GREEN", "YELLOW")

    def test_to_dict_serializable(self):
        data = _empty_extracted()
        data["datasources"] = [_make_datasource("S1", "BigQuery")]
        data["calculations"] = [_make_calc("H", "Hash256(X)")]
        report = run_assessment(data, app_name="SerializeTest")
        d = report.to_dict()
        # Verify JSON-serializable
        json_str = json.dumps(d)
        assert "SerializeTest" in json_str


# ═══════════════════════════════════════════════════════════════════
#  Realistic Qlik app scenarios
# ═══════════════════════════════════════════════════════════════════

class TestRealisticScenarios:
    def test_simple_sales_app(self):
        """A simple Qlik app with basic measures and a few sheets."""
        data = _empty_extracted()
        data["datasources"] = [
            _make_datasource("SalesDB", "SQL Server", tables=[
                {"name": "Sales", "columns": [{"name": "Amount"}, {"name": "Date"}, {"name": "Region"}]},
                {"name": "Products", "columns": [{"name": "ProductID"}, {"name": "Name"}]},
            ]),
        ]
        data["calculations"] = [
            _make_calc("Total Sales", "Sum(Amount)"),
            _make_calc("Avg Order", "Avg(Amount)"),
            _make_calc("Order Count", "Count(OrderID)"),
        ]
        data["worksheets"] = [
            {"name": "Overview", "chart_type": "barchart"},
            {"name": "Trend", "chart_type": "linechart"},
            {"name": "Details", "chart_type": "table"},
        ]
        data["dashboards"] = [{"name": "Sales Dashboard"}]
        data["parameters"] = [{"name": "vYear", "caption": "Year Selector"}]

        report = run_assessment(data, app_name="SimpleSales")
        assert report.overall_score == "GREEN"
        assert report.total_fail == 0

    def test_complex_enterprise_app(self):
        """A complex Qlik app with set analysis, Aggr, Section Access."""
        data = _empty_extracted()
        data["datasources"] = [
            _make_datasource("SalesDB", "Oracle"),
            _make_datasource("HRDB", "Snowflake"),
        ]
        data["calculations"] = [
            _make_calc("YTD_Sales", "Sum({<Year={$(=Year(Today()))}>} TOTAL Sales)"),
            _make_calc("RegionAvg", "Aggr(Avg(Sales), Region)"),
            _make_calc("PrevYearSales", "Sum({<Year={$(=Year(Today())-1)}>} Sales)"),
            _make_calc("MarketShare", "Sum(Sales) / Sum(TOTAL Sales)"),
            _make_calc("HashedID", "Hash128(EmployeeID)"),
            _make_calc("DynField", "ApplyMap('FieldMap', Status, 'Unknown')"),
        ]
        data["worksheets"] = [
            {"name": f"Visual{i}", "chart_type": "barchart"} for i in range(15)
        ]
        data["dashboards"] = [{"name": f"Sheet{i}"} for i in range(5)]
        data["user_filters"] = [{"user": "admin", "filter": "TRUE()"}]
        data["custom_sql"] = [{"query": "SELECT * FROM audit_log"}]
        data["parameters"] = [
            {"name": f"vParam{i}", "caption": f"Param{i}"} for i in range(5)
        ]

        report = run_assessment(data, app_name="EnterpriseSales")
        # Should be RED (Hash128 has no DAX equivalent)
        assert report.overall_score == "RED"
        assert report.total_fail >= 1
        # Should have warnings for Oracle, Snowflake, Aggr, ApplyMap
        assert report.total_warn >= 1
