"""Tests for powerbi_import.autoheal."""

import json
import os
import tempfile
import unittest

from powerbi_import.autoheal import AutoHealer, StaticValidatorSource, heal_dax_expression


def _write_project_with_invalid_m(root: str) -> str:
    app = "Demo"
    proj = os.path.join(root, app)
    sm_def = os.path.join(proj, f"{app}.SemanticModel", "definition")
    rep = os.path.join(proj, f"{app}.Report")
    os.makedirs(sm_def, exist_ok=True)
    os.makedirs(rep, exist_ok=True)

    with open(os.path.join(rep, "definition.pbir"), "w", encoding="utf-8") as f:
        json.dump({"$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/3.1.0/schema.json"}, f)

    bad_m = "\n".join([
        "let",
        "    Source = #table(type table [A=number], {{1}}),",
        "in",
        "    Source",
    ])
    tmdl = (
        "model Model\n"
        "\ttable 'T'\n"
        "\tpartition P = m\n"
        "\t\tsource =\n"
        + "\n".join("\t\t\t\t" + ln for ln in bad_m.splitlines()) + "\n"
        "\t\tmeasure M = 1\n"
    )
    with open(os.path.join(sm_def, "model.tmdl"), "w", encoding="utf-8") as f:
        f.write(tmdl)
    return proj


def _write_project_with_missing_in_m(root: str) -> str:
    app = "DemoMissingIn"
    proj = os.path.join(root, app)
    sm_def = os.path.join(proj, f"{app}.SemanticModel", "definition")
    rep = os.path.join(proj, f"{app}.Report")
    os.makedirs(sm_def, exist_ok=True)
    os.makedirs(rep, exist_ok=True)

    with open(os.path.join(rep, "definition.pbir"), "w", encoding="utf-8") as f:
        json.dump({"$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/3.1.0/schema.json"}, f)

    bad_m = "\n".join([
        "let",
        "    Source = #table(type table [A=number], {{1}})",
    ])
    tmdl = (
        "model Model\n"
        "\ttable 'T'\n"
        "\tpartition P = m\n"
        "\t\tsource =\n"
        + "\n".join("\t\t\t\t" + ln for ln in bad_m.splitlines()) + "\n"
        "\t\tmeasure M = 1\n"
    )
    with open(os.path.join(sm_def, "model.tmdl"), "w", encoding="utf-8") as f:
        f.write(tmdl)
    return proj


class TestAutoHeal(unittest.TestCase):
    def test_static_validator_finds_m_error(self):
        with tempfile.TemporaryDirectory() as td:
            proj = _write_project_with_invalid_m(td)
            errs = StaticValidatorSource().collect(proj)
            self.assertTrue(any(e.artifact == "m" for e in errs))

    def test_autoheal_repairs_m_partition(self):
        with tempfile.TemporaryDirectory() as td:
            proj = _write_project_with_invalid_m(td)
            healer = AutoHealer(max_iterations=2)
            report = healer.heal_project(proj)
            self.assertGreaterEqual(len(report.actions), 1)
            self.assertFalse(any(e.artifact == "m" for e in report.remaining_errors))

    def test_rewrite_policy_conservative_skips_m_healing(self):
        with tempfile.TemporaryDirectory() as td:
            proj = _write_project_with_invalid_m(td)
            healer = AutoHealer(max_iterations=1, rewrite_policy="conservative")
            report = healer.heal_project(proj)
            self.assertEqual(report.rewrite_policy, "conservative")
            self.assertFalse(any(a.artifact == "m" for a in report.actions))
            self.assertTrue(any(e.artifact == "m" for e in report.remaining_errors))

    def test_rewrite_policy_aggressive_adds_countd_fix(self):
        fixed, changed = heal_dax_expression("CountD([CustomerId])", rewrite_policy="aggressive")
        self.assertTrue(changed)
        self.assertIn("DISTINCTCOUNT(", fixed)

    def test_rewrite_policy_aggressive_adds_ceil_fix(self):
        fixed, changed = heal_dax_expression("Ceil([Value])", rewrite_policy="aggressive")
        self.assertTrue(changed)
        self.assertIn("CEILING(", fixed)

    def test_rewrite_policy_conservative_keeps_countd(self):
        fixed, changed = heal_dax_expression("CountD([CustomerId])", rewrite_policy="conservative")
        self.assertFalse(changed)
        self.assertEqual(fixed, "CountD([CustomerId])")

    def test_rewrite_policy_aggressive_maps_common_qlik_functions(self):
        fixed, changed = heal_dax_expression(
            "If(Year(Date(2024,1,1))=2024, Sum([Amount]), Avg([Amount]))",
            rewrite_policy="aggressive",
        )
        self.assertTrue(changed)
        self.assertIn("IF(", fixed)
        self.assertIn("YEAR(", fixed)
        self.assertIn("DATE(", fixed)
        self.assertIn("SUM(", fixed)
        self.assertIn("AVERAGE(", fixed)

    def test_rewrite_policy_conservative_keeps_common_qlik_functions(self):
        expr = "If(Year(Date(2024,1,1))=2024, Sum([Amount]), Avg([Amount]))"
        fixed, changed = heal_dax_expression(expr, rewrite_policy="conservative")
        self.assertFalse(changed)
        self.assertEqual(fixed, expr)

    def test_rewrite_policy_defaults_to_balanced(self):
        healer = AutoHealer(max_iterations=1, rewrite_policy="unknown")
        self.assertEqual(healer.rewrite_policy, "balanced")

    def test_rewrite_policy_aggressive_repairs_missing_in_m(self):
        with tempfile.TemporaryDirectory() as td:
            proj = _write_project_with_missing_in_m(td)
            conservative = AutoHealer(max_iterations=1, rewrite_policy="conservative").heal_project(proj)
            self.assertTrue(any(e.artifact == "m" for e in conservative.remaining_errors))

            aggressive = AutoHealer(max_iterations=2, rewrite_policy="aggressive").heal_project(proj)
            self.assertFalse(any(e.artifact == "m" for e in aggressive.remaining_errors))
            self.assertTrue(any(a.artifact == "m" for a in aggressive.actions))


if __name__ == "__main__":
    unittest.main()
