"""Tests for powerbi_import.openability_guard."""

import json
import os
import tempfile
import unittest

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


if __name__ == "__main__":
    unittest.main()
