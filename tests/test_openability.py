"""Tests for powerbi_import.openability."""

import json
import os
import tempfile
import unittest

from powerbi_import.openability import check_openability, extract_m_partitions


def _write_min_project(root: str, m_expr: str) -> str:
    app = "Demo"
    proj = os.path.join(root, app)
    sm_def = os.path.join(proj, f"{app}.SemanticModel", "definition")
    rep = os.path.join(proj, f"{app}.Report")
    os.makedirs(sm_def, exist_ok=True)
    os.makedirs(rep, exist_ok=True)

    with open(os.path.join(rep, "definition.pbir"), "w", encoding="utf-8") as f:
        json.dump({"$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/3.1.0/schema.json"}, f)

    tmdl = (
        "model Model\n"
        "\ttable 'T'\n"
        "\tpartition P = m\n"
        "\t\tsource =\n"
        + "\n".join("\t\t\t\t" + ln for ln in m_expr.splitlines()) + "\n"
        "\t\tmeasure M = 1\n"
    )
    with open(os.path.join(sm_def, "model.tmdl"), "w", encoding="utf-8") as f:
        f.write(tmdl)
    return proj


def _write_relationship(proj: str, direction: str, include_columns: bool = True) -> None:
    app = os.path.basename(proj)
    definition = os.path.join(proj, f"{app}.SemanticModel", "definition")
    path = os.path.join(definition, "relationships.tmdl")
    with open(path, "w", encoding="utf-8") as f:
        f.write(
            "relationship R1\n"
            "\tfromColumn: A.ID\n"
            "\ttoColumn: B.ID\n"
            "\tfromCardinality: one\n"
            "\ttoCardinality: one\n"
            f"\tcrossFilteringBehavior: {direction}\n"
        )
    if include_columns:
        with open(os.path.join(definition, "endpoints.tmdl"), "w", encoding="utf-8") as f:
            f.write(
                "table A\n"
                "\tcolumn ID\n"
                "table B\n"
                "\tcolumn ID\n"
            )


class TestExtractMPartitions(unittest.TestCase):
    def test_extract_single_partition(self):
        text = (
            "\tpartition P = m\n"
            "\t\tsource =\n"
            "\t\t\t\tlet\n"
            "\t\t\t\t    Source = #table(type table [A=number], {{1}})\n"
            "\t\t\t\tin\n"
            "\t\t\t\t    Source\n"
        )
        parts = extract_m_partitions(text)
        self.assertEqual(len(parts), 1)
        self.assertEqual(parts[0][0], "P")
        self.assertIn("let", parts[0][1])


class TestCheckOpenability(unittest.TestCase):
    def test_missing_project(self):
        report = check_openability("does-not-exist")
        self.assertFalse(report.openable)
        self.assertGreater(len(report.blocking_issues), 0)

    def test_valid_project_is_openable(self):
        with tempfile.TemporaryDirectory() as td:
            m_expr = "\n".join([
                "let",
                "    Source = #table(type table [A=number], {{1}})",
                "in",
                "    Source",
            ])
            proj = _write_min_project(td, m_expr)
            report = check_openability(proj)
            self.assertTrue(report.openable)

    def test_invalid_m_partition_blocks_openability(self):
        with tempfile.TemporaryDirectory() as td:
            m_expr = "\n".join([
                "let",
                "    Source = #table(type table [A=number], {{1}})",
            ])
            proj = _write_min_project(td, m_expr)
            report = check_openability(proj)
            self.assertFalse(report.openable)
            self.assertTrue(any("power_query" in i for i in report.blocking_issues))

    def test_one_to_one_one_direction_blocks_openability(self):
        with tempfile.TemporaryDirectory() as td:
            proj = _write_min_project(td, "let\n    Source = #table({}, {})\nin\n    Source")
            _write_relationship(proj, "oneDirection")
            report = check_openability(proj)
            self.assertFalse(report.openable)
            self.assertTrue(any("relationships" in i for i in report.blocking_issues))

    def test_one_to_one_both_directions_is_openable(self):
        with tempfile.TemporaryDirectory() as td:
            proj = _write_min_project(td, "let\n    Source = #table({}, {})\nin\n    Source")
            _write_relationship(proj, "bothDirections")
            report = check_openability(proj)
            self.assertTrue(report.openable)

    def test_relationship_missing_column_blocks_openability(self):
        with tempfile.TemporaryDirectory() as td:
            proj = _write_min_project(td, "let\n    Source = #table({}, {})\nin\n    Source")
            _write_relationship(proj, "bothDirections", include_columns=False)
            report = check_openability(proj)
            self.assertFalse(report.openable)
            self.assertTrue(any(
                "relationships" in issue and "missing column" in issue
                for issue in report.blocking_issues
            ))

    def test_relationship_to_calculated_table_blocks_openability(self):
        with tempfile.TemporaryDirectory() as td:
            proj = _write_min_project(td, "let\n    Source = #table({}, {})\nin\n    Source")
            _write_relationship(proj, "bothDirections")
            app = os.path.basename(proj)
            path = os.path.join(proj, f"{app}.SemanticModel", "definition", "endpoints.tmdl")
            with open(path, "a", encoding="utf-8") as f:
                f.write(
                    "\tpartition P = calculated\n"
                    "\t\tsource = DISTINCT(A)\n"
                )
            report = check_openability(proj)
            self.assertFalse(report.openable)
            self.assertTrue(any(
                "relationships" in issue and "calculated table" in issue
                for issue in report.blocking_issues
            ))

    def test_measure_column_name_collision_blocks_openability(self):
        with tempfile.TemporaryDirectory() as td:
            proj = _write_min_project(td, "let\n    Source = #table({}, {})\nin\n    Source")
            app = os.path.basename(proj)
            path = os.path.join(proj, f"{app}.SemanticModel", "definition", "collision.tmdl")
            with open(path, "w", encoding="utf-8") as f:
                f.write(
                    "table A\n"
                    "\tcolumn 'EIG P'\n"
                    "table B\n"
                    "\tmeasure 'eig p' = 1\n"
                )
            report = check_openability(proj)
            self.assertFalse(report.openable)
            self.assertTrue(any("model_names" in issue for issue in report.blocking_issues))


if __name__ == "__main__":
    unittest.main()
