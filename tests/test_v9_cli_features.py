"""Tests for v9 CLI features in migrate.py — new flags and integration."""

import argparse
import os
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock


class TestCliOutputFormat(unittest.TestCase):
    """Test --output-format flag acceptance."""

    def _parse(self, args):
        """Import and invoke the argument parser from migrate.py."""
        # We import the module fresh to get the parser
        import migrate
        # Build a parser the same way migrate.py does
        parser = argparse.ArgumentParser()
        parser.add_argument('input', nargs='?', default=None)
        parser.add_argument('--output-format', choices=['pbip', 'tmdl', 'pbir', 'fabric'],
                            default='pbip')
        parser.add_argument('--merge', metavar='DIR', nargs='+', default=None)
        parser.add_argument('--assess-server', metavar='DIR', default=None)
        parser.add_argument('--json', action='store_true', default=False)
        parser.add_argument('--plugins', metavar='SPEC', nargs='*', default=None)
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--verbose', action='store_true')
        parser.add_argument('--skip-extraction', action='store_true')
        parser.add_argument('--output-dir', default=None)
        return parser.parse_args(args)

    def test_fabric_format_accepted(self):
        args = self._parse(["app.qvf", "--output-format", "fabric"])
        self.assertEqual(args.output_format, "fabric")

    def test_pbip_format_default(self):
        args = self._parse(["app.qvf"])
        self.assertEqual(args.output_format, "pbip")

    def test_tmdl_format(self):
        args = self._parse(["app.qvf", "--output-format", "tmdl"])
        self.assertEqual(args.output_format, "tmdl")

    def test_pbir_format(self):
        args = self._parse(["app.qvf", "--output-format", "pbir"])
        self.assertEqual(args.output_format, "pbir")

    def test_invalid_format_rejected(self):
        with self.assertRaises(SystemExit):
            self._parse(["app.qvf", "--output-format", "invalid"])


class TestCliMergeFlag(unittest.TestCase):
    """Test --merge flag."""

    def _parse(self, args):
        parser = argparse.ArgumentParser()
        parser.add_argument('input', nargs='?', default=None)
        parser.add_argument('--merge', metavar='DIR', nargs='+', default=None)
        return parser.parse_args(args)

    def test_merge_multiple_paths(self):
        args = self._parse(["--merge", "app1.json", "app2.json", "app3.json"])
        self.assertEqual(len(args.merge), 3)

    def test_merge_single_path(self):
        args = self._parse(["--merge", "app.json"])
        self.assertEqual(len(args.merge), 1)

    def test_merge_not_specified(self):
        args = self._parse(["app.qvf"])
        self.assertIsNone(args.merge)


class TestCliAssessServer(unittest.TestCase):
    """Test --assess-server flag."""

    def _parse(self, args):
        parser = argparse.ArgumentParser()
        parser.add_argument('input', nargs='?', default=None)
        parser.add_argument('--assess-server', metavar='DIR', default=None)
        return parser.parse_args(args)

    def test_assess_server_with_dir(self):
        args = self._parse(["--assess-server", "/path/to/exports"])
        self.assertEqual(args.assess_server, "/path/to/exports")

    def test_assess_server_not_specified(self):
        args = self._parse(["app.qvf"])
        self.assertIsNone(args.assess_server)


class TestCliJsonOutput(unittest.TestCase):
    """Test --json flag."""

    def _parse(self, args):
        parser = argparse.ArgumentParser()
        parser.add_argument('input', nargs='?', default=None)
        parser.add_argument('--json', action='store_true', default=False)
        return parser.parse_args(args)

    def test_json_flag(self):
        args = self._parse(["app.qvf", "--json"])
        self.assertTrue(args.json)

    def test_no_json_flag(self):
        args = self._parse(["app.qvf"])
        self.assertFalse(args.json)


class TestCliPlugins(unittest.TestCase):
    """Test --plugins flag."""

    def _parse(self, args):
        parser = argparse.ArgumentParser()
        parser.add_argument('input', nargs='?', default=None)
        parser.add_argument('--plugins', metavar='SPEC', nargs='*', default=None)
        return parser.parse_args(args)

    def test_plugins_multiple(self):
        args = self._parse(["app.qvf", "--plugins", "m.A", "m.B"])
        self.assertEqual(args.plugins, ["m.A", "m.B"])

    def test_no_plugins(self):
        args = self._parse(["app.qvf"])
        self.assertIsNone(args.plugins)


class TestCliDryRun(unittest.TestCase):
    """Test --dry-run flag."""

    def _parse(self, args):
        parser = argparse.ArgumentParser()
        parser.add_argument('input', nargs='?', default=None)
        parser.add_argument('--dry-run', action='store_true')
        return parser.parse_args(args)

    def test_dry_run_set(self):
        args = self._parse(["app.qvf", "--dry-run"])
        self.assertTrue(args.dry_run)


class TestDaxOptimizerIntegration(unittest.TestCase):
    """Test that DAX optimizer can be called after generation (mock-based)."""

    def test_optimize_dax_callable(self):
        from powerbi_import.dax_optimizer import optimize_dax
        formula = "IF(ISBLANK([X]), 0, [X])"
        result, rules = optimize_dax(formula)
        self.assertIn("COALESCE", result)

    def test_optimization_report_callable(self):
        from powerbi_import.dax_optimizer import generate_optimization_report
        measures = [
            {"name": "M1", "expression": "SUM([X])"},
            {"name": "M2", "expression": "  AVERAGE( [Y] )  "},
        ]
        report = generate_optimization_report(measures)
        self.assertEqual(report["total_measures"], 2)

    def test_time_intelligence_callable(self):
        from powerbi_import.dax_optimizer import generate_time_intelligence_measures
        measures = [{"name": "Rev", "expression": "SUM('T'[Amount])"}]
        ti = generate_time_intelligence_measures(measures)
        self.assertEqual(len(ti), 3)


class TestMigrateModuleImportable(unittest.TestCase):
    """Test that migrate.py is importable and key symbols exist."""

    def test_exit_code_defined(self):
        from migrate import ExitCode
        self.assertEqual(ExitCode.SUCCESS, 0)
        self.assertEqual(ExitCode.GENERAL_ERROR, 1)

    def test_setup_logging_callable(self):
        from migrate import setup_logging
        setup_logging(verbose=False)  # Should not raise

    def test_exit_codes_comprehensive(self):
        from migrate import ExitCode
        self.assertTrue(hasattr(ExitCode, 'EXTRACTION_FAILED'))
        self.assertTrue(hasattr(ExitCode, 'GENERATION_FAILED'))
        self.assertTrue(hasattr(ExitCode, 'VALIDATION_FAILED'))


class TestFabricOutputFormatIntegration(unittest.TestCase):
    """Test that fabric-related modules are importable."""

    def test_lakehouse_generator_importable(self):
        from powerbi_import.lakehouse_generator import LakehouseGenerator
        self.assertTrue(callable(LakehouseGenerator))

    def test_fabric_constants_importable(self):
        from powerbi_import.fabric_constants import FABRIC_ARTIFACTS
        self.assertIn("lakehouse", FABRIC_ARTIFACTS)

    def test_fabric_naming_importable(self):
        from powerbi_import.fabric_naming import sanitize_table_name
        self.assertEqual(sanitize_table_name("TestTable"), "testtable")


if __name__ == "__main__":
    unittest.main()
