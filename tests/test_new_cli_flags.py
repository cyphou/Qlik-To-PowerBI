"""Tests for new migrate.py CLI flags and helper functions."""

import os
import subprocess
import sys
import tempfile
import unittest

# Ensure project root is on sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from migrate import _build_calc_map_from_tmdl, _build_lineage_calc_map


class TestBuildCalcMapFromTmdl(unittest.TestCase):
    """Tests for _build_lineage_calc_map helper."""

    def test_empty_directory(self):
        with tempfile.TemporaryDirectory() as td:
            result = _build_lineage_calc_map("NoApp", td)
            self.assertEqual(result, {})

    def test_reads_measures(self):
        with tempfile.TemporaryDirectory() as td:
            app = "TestApp"
            tables_dir = os.path.join(td, app, f"{app}.SemanticModel",
                                      "definition", "tables")
            os.makedirs(tables_dir)
            with open(os.path.join(tables_dir, "Sales.tmdl"), "w") as f:
                f.write("table Sales\n")
                f.write("\tmeasure Revenue = SUM([Amount])\n")
                f.write("\tmeasure 'Total Count' = COUNT([ID])\n")

            result = _build_lineage_calc_map(app, td)
            self.assertIn("Revenue", result)
            self.assertEqual(result["Revenue"]["table"], "Sales")
            self.assertEqual(result["Revenue"]["type"], "measure")

    def test_reads_calculated_columns(self):
        with tempfile.TemporaryDirectory() as td:
            app = "TestApp"
            tables_dir = os.path.join(td, app, f"{app}.SemanticModel",
                                      "definition", "tables")
            os.makedirs(tables_dir)
            with open(os.path.join(tables_dir, "Products.tmdl"), "w") as f:
                f.write("table Products\n")
                f.write("\tcolumn Category = RELATED('Dim'[Cat])\n")

            result = _build_lineage_calc_map(app, td)
            self.assertIn("Category", result)
            self.assertEqual(result["Category"]["type"], "calculated_column")
            self.assertEqual(result["Category"]["table"], "Products")

    def test_multiple_tables(self):
        with tempfile.TemporaryDirectory() as td:
            app = "MultiTable"
            tables_dir = os.path.join(td, app, f"{app}.SemanticModel",
                                      "definition", "tables")
            os.makedirs(tables_dir)
            with open(os.path.join(tables_dir, "A.tmdl"), "w") as f:
                f.write("table A\n\tmeasure M1 = SUM([X])\n")
            with open(os.path.join(tables_dir, "B.tmdl"), "w") as f:
                f.write("table B\n\tmeasure M2 = COUNT([Y])\n")

            result = _build_lineage_calc_map(app, td)
            self.assertEqual(result["M1"]["table"], "A")
            self.assertEqual(result["M2"]["table"], "B")

    def test_ignores_non_tmdl_files(self):
        with tempfile.TemporaryDirectory() as td:
            app = "TestApp"
            tables_dir = os.path.join(td, app, f"{app}.SemanticModel",
                                      "definition", "tables")
            os.makedirs(tables_dir)
            with open(os.path.join(tables_dir, "readme.txt"), "w") as f:
                f.write("measure Fake = 1\n")

            result = _build_lineage_calc_map(app, td)
            self.assertEqual(result, {})

    def test_measure_rename_aliases_original_name(self):
        with tempfile.TemporaryDirectory() as td:
            app = "TestApp"
            tables_dir = os.path.join(td, app, f"{app}.SemanticModel",
                                      "definition", "tables")
            os.makedirs(tables_dir)
            with open(os.path.join(tables_dir, "Sales.tmdl"), "w", encoding="utf-8") as f:
                f.write("table Sales\n")
                f.write("\tmeasure 'Total Revenue' = SUM('Sales'[Revenue])\n")

            result = _build_calc_map_from_tmdl(
                app,
                td,
                {"Revenue": "Total Revenue"},
            )
            self.assertEqual(result["Total Revenue"], "SUM('Sales'[Revenue])")
            self.assertEqual(result["Revenue"], "SUM('Sales'[Revenue])")


class TestNewCLIFlags(unittest.TestCase):
    """Test that all new argparse arguments are accepted by migrate.py --help."""

    @classmethod
    def setUpClass(cls):
        """Get migrate.py --help output once."""
        project_root = os.path.join(os.path.dirname(__file__), "..")
        python = os.path.join(project_root, "venv", "Scripts", "python.exe")
        if not os.path.isfile(python):
            python = sys.executable
        result = subprocess.run(
            [python, os.path.join(project_root, "migrate.py"), "--help"],
            capture_output=True, text=True, cwd=project_root,
        )
        cls.help_text = result.stdout + result.stderr

    def _assert_flag(self, flag_name):
        self.assertIn(flag_name, self.help_text,
                      f"Flag {flag_name} not found in --help output")

    def test_qa_flag(self):
        self._assert_flag("--qa")

    def test_governance_flag(self):
        self._assert_flag("--governance")

    def test_compare_flag(self):
        self._assert_flag("--compare")

    def test_no_compare_flag(self):
        self._assert_flag("--no-compare")

    def test_dashboard_flag(self):
        self._assert_flag("--dashboard")

    def test_optimize_dax_flag(self):
        self._assert_flag("--optimize-dax")

    def test_time_intelligence_flag(self):
        self._assert_flag("--time-intelligence")

    def test_monitor_flag(self):
        self._assert_flag("--monitor")

    def test_deploy_flag(self):
        self._assert_flag("--deploy")

    def test_deploy_refresh_flag(self):
        self._assert_flag("--deploy-refresh")

    def test_deploy_bundle_flag(self):
        self._assert_flag("--deploy-bundle")

    def test_shared_model_flag(self):
        self._assert_flag("--shared-model")

    def test_model_name_flag(self):
        self._assert_flag("--model-name")

    def test_assess_merge_flag(self):
        self._assert_flag("--assess-merge")

    def test_global_assess_flag(self):
        self._assert_flag("--global-assess")

    def test_check_drift_flag(self):
        self._assert_flag("--check-drift")

    def test_sla_config_flag(self):
        self._assert_flag("--sla-config")

    def test_llm_refine_flag(self):
        self._assert_flag("--llm-refine")

    def test_llm_provider_flag(self):
        self._assert_flag("--llm-provider")

    def test_llm_model_flag(self):
        self._assert_flag("--llm-model")

    def test_llm_dry_run_flag(self):
        self._assert_flag("--llm-dry-run")

    def test_workers_flag(self):
        self._assert_flag("--workers")

    def test_parallel_flag(self):
        self._assert_flag("--parallel")

    def test_resume_flag(self):
        self._assert_flag("--resume")

    def test_jsonl_log_flag(self):
        self._assert_flag("--jsonl-log")

    def test_web_ui_flag(self):
        self._assert_flag("--web-ui")

    def test_web_port_flag(self):
        self._assert_flag("--web-port")

    def test_endorse_flag(self):
        self._assert_flag("--endorse")

    def test_manifest_flag(self):
        self._assert_flag("--manifest")

    def test_validate_data_flag(self):
        self._assert_flag("--validate-data")

    def test_sync_flag(self):
        self._assert_flag("--sync")

    def test_multi_tenant_flag(self):
        self._assert_flag("--multi-tenant")

    def test_rolling_flag(self):
        self._assert_flag("--rolling")

    def test_consolidate_flag(self):
        self._assert_flag("--consolidate")

    def test_server_url_flag(self):
        self._assert_flag("--server-url")

    def test_server_api_key_flag(self):
        self._assert_flag("--server-api-key")

    def test_server_cert_flag(self):
        self._assert_flag("--server-cert")

    def test_server_app_id_flag(self):
        self._assert_flag("--server-app-id")

    def test_refresh_schedule_flag(self):
        self._assert_flag("--refresh-schedule")

    def test_refresh_timezone_flag(self):
        self._assert_flag("--refresh-timezone")

    def test_binary_source_flag(self):
        self._assert_flag("--binary-source")

    def test_binary_source_dir_flag(self):
        self._assert_flag("--binary-source-dir")

    def test_verify_open_flag(self):
        self._assert_flag("--verify-open")

    def test_autoheal_flag(self):
        self._assert_flag("--autoheal")

    def test_autoheal_iterations_flag(self):
        self._assert_flag("--autoheal-iterations")

    def test_rewrite_policy_flag(self):
        self._assert_flag("--rewrite-policy")

    def test_ensure_open_flag(self):
        self._assert_flag("--ensure-open")

    def test_no_ensure_open_flag(self):
        self._assert_flag("--no-ensure-open")

    def test_ensure_open_strict_flag(self):
        self._assert_flag("--ensure-open-strict")

    def test_no_ensure_open_strict_flag(self):
        self._assert_flag("--no-ensure-open-strict")

    def test_simple_mode_flag(self):
        self._assert_flag("--simple-mode")

    def test_help_simple_flag(self):
        self._assert_flag("--help-simple")

    def test_simple_command_flag(self):
        self._assert_flag("--simple-command")

    def test_target_flag(self):
        self._assert_flag("--target")

    def test_workspace_id_flag(self):
        self._assert_flag("--workspace-id")

if __name__ == "__main__":
    unittest.main()
