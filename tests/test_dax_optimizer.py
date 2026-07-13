"""Tests for powerbi_import.dax_optimizer — AST-based DAX rewriter."""

import json
import os
import tempfile
import unittest

from powerbi_import.dax_optimizer import (
    optimize_dax,
    generate_time_intelligence_measures,
    build_measure_dependency_dag,
    generate_optimization_report,
)


class TestOptimizeDaxRules(unittest.TestCase):
    """Test individual optimization rules."""

    # ── isblank_coalesce ──

    def test_isblank_to_coalesce_standard(self):
        formula = "IF(ISBLANK([Sales]), 0, [Sales])"
        result, rules = optimize_dax(formula)
        self.assertIn("isblank_coalesce", rules)
        self.assertIn("COALESCE", result)
        self.assertNotIn("ISBLANK", result)

    def test_isblank_to_coalesce_reversed_branches(self):
        formula = "IF(ISBLANK([X]), [X], 99)"
        result, rules = optimize_dax(formula)
        self.assertIn("isblank_coalesce", rules)
        self.assertIn("COALESCE", result)

    def test_isblank_no_match(self):
        formula = "IF(ISBLANK([A]), [B], [C])"
        result, rules = optimize_dax(formula)
        self.assertNotIn("isblank_coalesce", rules)

    # ── nested_if_to_switch ──

    def test_nested_if_to_switch(self):
        formula = 'IF([Status] = "A", 1, IF([Status] = "B", 2, IF([Status] = "C", 3, 0)))'
        result, rules = optimize_dax(formula)
        self.assertIn("nested_if_to_switch", rules)
        self.assertIn("SWITCH", result)

    def test_single_if_not_switched(self):
        formula = 'IF([Status] = "A", 1, 0)'
        result, rules = optimize_dax(formula)
        self.assertNotIn("nested_if_to_switch", rules)

    # ── redundant_calculate ──

    def test_redundant_calculate_removed(self):
        formula = "CALCULATE(SUM([Sales]))"
        result, rules = optimize_dax(formula)
        self.assertIn("redundant_calculate", rules)
        self.assertEqual(result, "SUM([Sales])")

    def test_calculate_with_filter_kept(self):
        formula = "CALCULATE(SUM([Sales]), 'Table'[Year] = 2024)"
        result, rules = optimize_dax(formula)
        # Should not simplify because there's a filter argument
        self.assertIn("CALCULATE", result)

    def test_calculate_with_nested_expr_and_filter_kept(self):
        formula = "CALCULATE(SUM(SUM('Sales'[Amount])), ALLSELECTED('Sales'))"
        result, rules = optimize_dax(formula)
        self.assertIn("CALCULATE", result)
        self.assertNotIn("redundant_calculate", rules)

    # ── constant_fold ──

    def test_constant_fold_addition(self):
        formula = "SUM([X]) + 1 + 2"
        result, rules = optimize_dax(formula)
        self.assertIn("constant_fold", rules)
        self.assertIn("3", result)

    def test_constant_fold_multiplication(self):
        formula = "10 * 5"
        result, rules = optimize_dax(formula)
        self.assertIn("constant_fold", rules)
        self.assertEqual(result, "50")

    def test_constant_fold_subtraction(self):
        formula = "100 - 30"
        result, rules = optimize_dax(formula)
        self.assertIn("constant_fold", rules)
        self.assertEqual(result, "70")

    def test_constant_fold_division_exact(self):
        formula = "100 / 5"
        result, rules = optimize_dax(formula)
        self.assertIn("constant_fold", rules)
        self.assertEqual(result, "20")

    # ── simplify_sumx ──

    def test_simplify_sumx(self):
        formula = "SUMX('Sales', 'Sales'[Revenue])"
        result, rules = optimize_dax(formula)
        self.assertIn("simplify_sumx", rules)
        self.assertEqual(result, "SUM('Sales'[Revenue])")

    def test_sumx_different_tables_kept(self):
        formula = "SUMX('Sales', 'Products'[Price])"
        result, rules = optimize_dax(formula)
        self.assertNotIn("simplify_sumx", rules)
        self.assertIn("SUMX", result)

    # ── trim_whitespace ──

    def test_trim_whitespace(self):
        formula = "  SUM(  [Sales]  )  "
        result, rules = optimize_dax(formula)
        self.assertIn("trim_whitespace", rules)
        self.assertNotIn("  ", result)
        self.assertEqual(result, result.strip())


class TestOptimizeDaxRuleSet(unittest.TestCase):
    """Test rule_set filtering."""

    def test_only_specified_rules_applied(self):
        formula = "IF(ISBLANK([X]), 0, [X])"
        result, rules = optimize_dax(formula, rule_set=["isblank_coalesce"])
        self.assertEqual(rules, ["isblank_coalesce"])

    def test_empty_rule_set_applies_all(self):
        # Empty list is falsy → rule_set filter not applied → all rules run
        formula = "IF(ISBLANK([X]), 0, [X])"
        result, rules = optimize_dax(formula, rule_set=[])
        self.assertGreater(len(rules), 0)

    def test_unknown_rule_ignored(self):
        formula = "SUM([X])"
        result, rules = optimize_dax(formula, rule_set=["nonexistent_rule"])
        self.assertEqual(rules, [])


class TestOptimizeDaxEdgeCases(unittest.TestCase):
    """Test edge-case inputs."""

    def test_none_input(self):
        result, rules = optimize_dax(None)
        self.assertIsNone(result)
        self.assertEqual(rules, [])

    def test_empty_string(self):
        result, rules = optimize_dax("")
        self.assertEqual(result, "")
        self.assertEqual(rules, [])

    def test_non_string_input(self):
        result, rules = optimize_dax(42)
        self.assertEqual(result, 42)
        self.assertEqual(rules, [])

    def test_already_optimal(self):
        formula = "SUM([Sales])"
        result, rules = optimize_dax(formula)
        self.assertEqual(result, formula)
        self.assertEqual(rules, [])


class TestTimeIntelligenceMeasures(unittest.TestCase):
    """Test generate_time_intelligence_measures()."""

    def test_generates_ytd_py_yoy_for_agg_measure(self):
        measures = [{"name": "Total Sales", "expression": "SUM('Sales'[Revenue])"}]
        ti = generate_time_intelligence_measures(measures)
        self.assertEqual(len(ti), 3)
        names = [m["name"] for m in ti]
        self.assertIn("Total Sales YTD", names)
        self.assertIn("Total Sales PY", names)
        self.assertIn("Total Sales YoY %", names)

    def test_ytd_uses_totalytd(self):
        measures = [{"name": "Count", "expression": "COUNTROWS('Orders')"}]
        ti = generate_time_intelligence_measures(measures)
        ytd = [m for m in ti if m["name"] == "Count YTD"][0]
        self.assertIn("TOTALYTD", ytd["expression"])

    def test_py_uses_sameperiodlastyear(self):
        measures = [{"name": "Rev", "expression": "SUM('T'[X])"}]
        ti = generate_time_intelligence_measures(measures)
        py = [m for m in ti if m["name"] == "Rev PY"][0]
        self.assertIn("SAMEPERIODLASTYEAR", py["expression"])

    def test_display_folder_set(self):
        measures = [{"name": "M", "expression": "AVERAGE('T'[V])"}]
        ti = generate_time_intelligence_measures(measures)
        for m in ti:
            self.assertEqual(m["displayFolder"], "Time Intelligence")

    def test_skips_non_aggregation_measures(self):
        measures = [{"name": "Label", "expression": "'Table'[Column]"}]
        ti = generate_time_intelligence_measures(measures)
        self.assertEqual(len(ti), 0)

    def test_custom_date_column(self):
        measures = [{"name": "Rev", "expression": "SUM('T'[X])"}]
        ti = generate_time_intelligence_measures(measures, date_column="'DateDim'[CalDate]")
        ytd = [m for m in ti if m["name"] == "Rev YTD"][0]
        self.assertIn("'DateDim'[CalDate]", ytd["expression"])

    def test_empty_measures_list(self):
        ti = generate_time_intelligence_measures([])
        self.assertEqual(ti, [])

    def test_measure_missing_name(self):
        measures = [{"expression": "SUM('T'[X])"}]
        ti = generate_time_intelligence_measures(measures)
        self.assertEqual(len(ti), 0)


class TestBuildMeasureDependencyDag(unittest.TestCase):
    """Test build_measure_dependency_dag()."""

    def test_basic_edges(self):
        measures = [
            {"name": "Base", "expression": "SUM('T'[X])"},
            {"name": "Derived", "expression": "[Base] * 2"},
        ]
        dag = build_measure_dependency_dag(measures)
        self.assertIn(("Derived", "Base"), dag["edges"])

    def test_roots_have_no_deps(self):
        measures = [
            {"name": "A", "expression": "SUM('T'[X])"},
            {"name": "B", "expression": "[A] + 1"},
        ]
        dag = build_measure_dependency_dag(measures)
        self.assertIn("A", dag["roots"])
        self.assertNotIn("B", dag["roots"])

    def test_unused_measures(self):
        measures = [
            {"name": "Used", "expression": "SUM('T'[X])"},
            {"name": "Unused", "expression": "SUM('T'[Y])"},
            {"name": "Derived", "expression": "[Used] + 1"},
        ]
        dag = build_measure_dependency_dag(measures)
        self.assertIn("Unused", dag["unused"])
        self.assertIn("Derived", dag["unused"])

    def test_circular_detection(self):
        measures = [
            {"name": "A", "expression": "[B] + 1"},
            {"name": "B", "expression": "[A] + 1"},
        ]
        dag = build_measure_dependency_dag(measures)
        self.assertTrue(len(dag["circular"]) > 0)

    def test_empty_measures(self):
        dag = build_measure_dependency_dag([])
        self.assertEqual(dag["edges"], [])
        self.assertEqual(dag["circular"], [])
        self.assertEqual(dag["unused"], [])
        self.assertEqual(dag["roots"], [])


class TestGenerateOptimizationReport(unittest.TestCase):
    """Test generate_optimization_report()."""

    def test_report_counts(self):
        measures = [
            {"name": "M1", "expression": "IF(ISBLANK([X]), 0, [X])"},
            {"name": "M2", "expression": "SUM([Y])"},
        ]
        report = generate_optimization_report(measures)
        self.assertEqual(report["total_measures"], 2)
        self.assertGreaterEqual(report["optimized_count"], 1)
        m1 = [m for m in report["measures"] if m["name"] == "M1"][0]
        self.assertTrue(m1["changed"])

    def test_report_unchanged_measure(self):
        measures = [{"name": "Simple", "expression": "SUM([X])"}]
        report = generate_optimization_report(measures)
        self.assertEqual(report["optimized_count"], 0)
        self.assertFalse(report["measures"][0]["changed"])

    def test_report_writes_to_file(self):
        measures = [{"name": "M", "expression": "  SUM([X])  "}]
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "opt_report.json")
            report = generate_optimization_report(measures, output_path=path)
            self.assertTrue(os.path.isfile(path))
            with open(path, "r") as f:
                loaded = json.load(f)
            self.assertEqual(loaded["total_measures"], 1)


if __name__ == "__main__":
    unittest.main()
