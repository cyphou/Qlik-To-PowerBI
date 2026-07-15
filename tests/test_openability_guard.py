"""Tests for powerbi_import.openability_guard."""

import json
import os
import tempfile
import unittest
from unittest.mock import patch

from powerbi_import.openability_guard import ensure_openable


def _write_project_with_invalid_m_and_dax(root: str) -> str:
    app = "GuardDemo"
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
    bad_dax = "COUNTD([A])"

    tmdl = (
        "model Model\n"
        "\ttable 'T'\n"
        "\tpartition P = m\n"
        "\t\tsource =\n"
        + "\n".join("\t\t\t\t" + ln for ln in bad_m.splitlines()) + "\n"
        + f"\t\tmeasure Bad = {bad_dax}\n"
    )
    with open(os.path.join(sm_def, "model.tmdl"), "w", encoding="utf-8") as f:
        f.write(tmdl)

    return proj


class TestOpenabilityGuard(unittest.TestCase):
    def test_guard_makes_project_openable(self):
        with tempfile.TemporaryDirectory() as td:
            proj = _write_project_with_invalid_m_and_dax(td)
            result = ensure_openable(proj, max_autoheal_iterations=2)
            self.assertTrue(result.get("openable"), result)
            self.assertIn(result.get("stage"), {"autoheal", "safety_fallback", "initial"})
            self.assertIn("root_cause_taxonomy", result)
            self.assertIn("initial", result["root_cause_taxonomy"])
            self.assertIn("final", result["root_cause_taxonomy"])
            self.assertIn("autoheal_metrics", result)
            self.assertIn("action_count", result["autoheal_metrics"])
            self.assertIn("stage_trace", result)
            self.assertGreaterEqual(len(result["stage_trace"]), 1)

    def test_guard_strict_mode_blocks_when_fallback_touches_critical_objects(self):
        class _Report:
            def __init__(self, openable, issues=None):
                self.openable = bool(openable)
                self._issues = list(issues or [])

            def to_dict(self):
                return {
                    "openable": self.openable,
                    "blocking_count": len(self._issues),
                    "warning_count": 0,
                    "blocking_issues": self._issues,
                    "warnings": [],
                }

        class _Autoheal:
            def to_dict(self):
                return {
                    "project_dir": "X",
                    "iterations": 1,
                    "changed": True,
                    "clean": False,
                    "action_count": 1,
                    "actions": [{"artifact": "dax", "confidence": "high", "source": "deterministic"}],
                    "remaining_errors": [{"artifact": "dax", "message": "still invalid"}],
                }

        with patch("powerbi_import.openability_guard.check_openability") as mock_check, \
                patch("powerbi_import.openability_guard.AutoHealer") as mock_healer, \
                patch("powerbi_import.openability_guard._apply_tmdl_safety_fallback", return_value=(1, 0)):
            mock_check.side_effect = [
                _Report(False, ["[dax] bad expression"]),
                _Report(False, ["[dax] still bad"]),
                _Report(True, []),
            ]
            mock_healer.return_value.heal_project.return_value = _Autoheal()

            result = ensure_openable("X", strict_mode=True)

            self.assertFalse(result.get("openable"))
            self.assertEqual(result.get("stage"), "strict_block")
            self.assertTrue(result.get("strict_mode"))
            self.assertIsNotNone(result.get("strict_violation"))
            self.assertEqual(
                result["strict_violation"]["reason"],
                "safety_fallback_modified_critical_objects",
            )
            self.assertGreaterEqual(len(result.get("stage_trace") or []), 3)


if __name__ == "__main__":
    unittest.main()
