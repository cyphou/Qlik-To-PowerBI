"""Tests for powerbi_import.qa_pipeline — post-migration QA suite."""

import json
import os
import tempfile
import unittest

from powerbi_import.qa_pipeline import _autofix_tmdl_file, run_qa_pipeline, _AUTOFIX_PATTERNS


class TestAutofixPatterns(unittest.TestCase):
    """Tests for the auto-fix Qlik→DAX leak patterns."""

    def test_patterns_list_not_empty(self):
        self.assertGreater(len(_AUTOFIX_PATTERNS), 10)

    def test_all_patterns_have_required_keys(self):
        for p in _AUTOFIX_PATTERNS:
            self.assertIn("pattern", p)
            self.assertIn("replacement", p)
            self.assertIn("description", p)

    def test_autofix_isnull_to_isblank(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tmdl", delete=False,
                                         encoding="utf-8") as f:
            f.write('measure Revenue = IF(IsNull([Amount]), 0, [Amount])\n')
            path = f.name
        try:
            fixes = _autofix_tmdl_file(path)
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("ISBLANK", content)
            self.assertNotIn("IsNull", content)
            self.assertTrue(any("IsNull" in fix["pattern"] for fix in fixes))
        finally:
            os.unlink(path)

    def test_autofix_null_to_blank(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tmdl", delete=False,
                                         encoding="utf-8") as f:
            f.write('measure M = IF([X] = Null(), 0, [X])\n')
            path = f.name
        try:
            fixes = _autofix_tmdl_file(path)
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("BLANK()", content)
        finally:
            os.unlink(path)

    def test_autofix_alt_to_coalesce(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tmdl", delete=False,
                                         encoding="utf-8") as f:
            f.write('measure M = Alt([X], 0)\n')
            path = f.name
        try:
            _autofix_tmdl_file(path)
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("COALESCE(", content)
        finally:
            os.unlink(path)

    def test_autofix_osuser_to_userprincipalname(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tmdl", delete=False,
                                         encoding="utf-8") as f:
            f.write('measure M = IF(OSUser() = "admin", 1, 0)\n')
            path = f.name
        try:
            _autofix_tmdl_file(path)
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("USERPRINCIPALNAME()", content)
        finally:
            os.unlink(path)

    def test_autofix_upper_lower_len(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tmdl", delete=False,
                                         encoding="utf-8") as f:
            f.write('measure M = Upper(Lower(Len([Name])))\n')
            path = f.name
        try:
            _autofix_tmdl_file(path)
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("UPPER(", content)
            self.assertIn("LOWER(", content)
            self.assertIn("LEN(", content)
        finally:
            os.unlink(path)

    def test_autofix_no_changes(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tmdl", delete=False,
                                         encoding="utf-8") as f:
            f.write('measure Revenue = SUM([Amount])\n')
            path = f.name
        try:
            fixes = _autofix_tmdl_file(path)
            self.assertEqual(len(fixes), 0)
        finally:
            os.unlink(path)

    def test_autofix_multiple_patterns(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tmdl", delete=False,
                                         encoding="utf-8") as f:
            f.write('measure M = IF(IsNull(Upper(Trim([Name]))), Null(), [Name])\n')
            path = f.name
        try:
            fixes = _autofix_tmdl_file(path)
            self.assertGreater(len(fixes), 2)
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("ISBLANK", content)
            self.assertIn("UPPER(", content)
            self.assertIn("TRIM(", content)
        finally:
            os.unlink(path)

    def test_autofix_nonexistent_file(self):
        fixes = _autofix_tmdl_file("/nonexistent/file.tmdl")
        self.assertEqual(fixes, [])

    def test_autofix_ceil_floor(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tmdl", delete=False,
                                         encoding="utf-8") as f:
            f.write('measure M = Ceil(Floor([Value]))\n')
            path = f.name
        try:
            _autofix_tmdl_file(path)
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("CEILING(", content)
            self.assertIn("FLOOR(", content)
        finally:
            os.unlink(path)


class TestRunQAPipeline(unittest.TestCase):
    """Integration tests for the full QA pipeline."""

    def _make_project(self, tmpdir, tmdl_content=None):
        """Create a minimal .pbip project structure."""
        app_name = "TestApp"
        project = os.path.join(tmpdir, app_name)
        sem_model = os.path.join(project, f"{app_name}.SemanticModel",
                                 "definition", "tables")
        os.makedirs(sem_model, exist_ok=True)

        if tmdl_content:
            with open(os.path.join(sem_model, "Sales.tmdl"), "w", encoding="utf-8") as f:
                f.write(tmdl_content)

        # Report structure
        report_dir = os.path.join(project, f"{app_name}.Report", "definition")
        os.makedirs(report_dir, exist_ok=True)
        with open(os.path.join(report_dir, "report.json"), "w", encoding="utf-8") as f:
            json.dump({"version": "4.0"}, f)

        return project

    def test_clean_project(self):
        with tempfile.TemporaryDirectory() as td:
            project = self._make_project(td, tmdl_content=(
                'table Sales\n'
                '\tmeasure Revenue = SUM([Amount])\n'
            ))
            result = run_qa_pipeline(project, td)
            self.assertIn("overall_status", result)
            self.assertIn("steps", result)
            self.assertIn("autofix", result["steps"])
            self.assertEqual(result["steps"]["autofix"]["total_fixes"], 0)

    def test_project_with_leaks(self):
        with tempfile.TemporaryDirectory() as td:
            project = self._make_project(td, tmdl_content=(
                'table Sales\n'
                '\tmeasure M = IF(IsNull([X]), Null(), Upper([X]))\n'
            ))
            result = run_qa_pipeline(project, td)
            total_fixes = result["steps"]["autofix"]["total_fixes"]
            self.assertGreater(total_fixes, 0)

    def test_qa_report_saved(self):
        with tempfile.TemporaryDirectory() as td:
            project = self._make_project(td, tmdl_content='table T\n')
            run_qa_pipeline(project, td)
            qa_path = os.path.join(td, "qa_report.json")
            self.assertTrue(os.path.isfile(qa_path))
            with open(qa_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.assertIn("timestamp", data)
            self.assertIn("duration_seconds", data)

    def test_qa_report_has_all_steps(self):
        with tempfile.TemporaryDirectory() as td:
            project = self._make_project(td, tmdl_content='table T\n')
            result = run_qa_pipeline(project, td)
            expected_steps = ["validation", "autofix", "governance", "comparison"]
            for step in expected_steps:
                self.assertIn(step, result["steps"], f"Missing step: {step}")

    def test_verbose_mode(self):
        with tempfile.TemporaryDirectory() as td:
            project = self._make_project(td, tmdl_content='table T\n')
            result = run_qa_pipeline(project, td, verbose=True)
            self.assertIn("overall_status", result)

    def test_nonexistent_project(self):
        with tempfile.TemporaryDirectory() as td:
            result = run_qa_pipeline(os.path.join(td, "nonexistent"), td)
            self.assertIn("overall_status", result)


if __name__ == "__main__":
    unittest.main()
