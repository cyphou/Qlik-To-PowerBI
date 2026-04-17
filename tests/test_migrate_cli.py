"""
Tests for migrate.py CLI — the user-facing entry point.

Uses subprocess to test the actual CLI argument parsing and exit codes,
plus direct-import tests for helper functions.
"""

import os
import sys
import json
import subprocess
import tempfile
import shutil
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

# Ensure project root is importable
_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root))

import migrate
from migrate import (
    ExitCode,
    MigrationStats,
    _load_json,
    main,
    setup_logging,
)


# ── Fixtures ────────────────────────────────────────────────────────

@pytest.fixture
def tmp_dir(tmp_path):
    """Provide a temporary directory that gets cleaned up."""
    return tmp_path


@pytest.fixture
def fake_qvf(tmp_dir):
    """Create a fake .qvf file (just needs to exist)."""
    p = tmp_dir / "test_app.qvf"
    p.write_bytes(b"PK\x03\x04fake_qvf_content")
    return str(p)


@pytest.fixture
def fake_json_export(tmp_dir):
    """Create a fake .json export file."""
    p = tmp_dir / "test_export.json"
    p.write_text(json.dumps({"app_metadata": {"name": "Test"}}), encoding="utf-8")
    return str(p)


@pytest.fixture
def valid_json_file(tmp_dir):
    """Create a valid JSON intermediate file."""
    p = tmp_dir / "datasources.json"
    p.write_text(json.dumps([{"tableName": "T1", "columns": []}]), encoding="utf-8")
    return str(p)


@pytest.fixture
def corrupt_json_file(tmp_dir):
    """Create a corrupt JSON file."""
    p = tmp_dir / "corrupt.json"
    p.write_text("{ not valid json }", encoding="utf-8")
    return str(p)


# ── ExitCode enum tests ─────────────────────────────────────────────

class TestExitCodes:

    def test_success_is_zero(self):
        assert ExitCode.SUCCESS == 0

    def test_all_codes_are_integers(self):
        for code in ExitCode:
            assert isinstance(int(code), int)

    def test_distinct_values(self):
        values = [int(c) for c in ExitCode]
        assert len(values) == len(set(values)), "Exit codes must be unique"


# ── MigrationStats tests ────────────────────────────────────────────

class TestMigrationStats:

    def test_default_values(self):
        stats = MigrationStats()
        assert stats.datasources == 0
        assert stats.app_name == ""
        assert stats.warnings == []

    def test_to_dict(self):
        stats = MigrationStats()
        stats.app_name = "TestApp"
        stats.datasources = 5
        d = stats.to_dict()
        assert d['app_name'] == "TestApp"
        assert d['datasources'] == 5


# ── _load_json tests ────────────────────────────────────────────────

class TestLoadJson:

    def test_load_valid_json(self, valid_json_file):
        result = _load_json(valid_json_file)
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]['tableName'] == 'T1'

    def test_load_nonexistent_returns_empty(self, tmp_dir):
        result = _load_json(str(tmp_dir / "does_not_exist.json"))
        assert result == []

    def test_load_corrupt_json_returns_empty(self, corrupt_json_file):
        """Corrupt JSON should log error and return empty list (not crash)."""
        result = _load_json(corrupt_json_file)
        assert result == []


# ── setup_logging tests ─────────────────────────────────────────────

class TestSetupLogging:

    def test_verbose_sets_debug(self):
        """setup_logging(verbose=True) should not crash."""
        setup_logging(verbose=True)

    def test_quiet_sets_error(self):
        setup_logging(quiet=True)

    def test_default_sets_info(self):
        setup_logging()


# ── CLI argument parsing (via subprocess) ────────────────────────────

class TestCLIParsing:
    """Test CLI flag parsing via argparse."""

    def _run_cli(self, *args, timeout=30):
        """Run migrate.py as subprocess and return (returncode, stdout, stderr)."""
        cmd = [sys.executable, str(_project_root / "migrate.py")] + list(args)
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            cwd=str(_project_root),
        )
        return result.returncode, result.stdout, result.stderr

    def test_help_flag_exits_zero(self):
        rc, stdout, stderr = self._run_cli("--help")
        assert rc == 0
        assert "migrate" in stdout.lower() or "qlik" in stdout.lower()

    def test_no_args_exits_error(self):
        """Running without arguments should error (qlik_file required)."""
        rc, stdout, stderr = self._run_cli()
        assert rc != 0

    def test_missing_file_exits_error(self):
        rc, stdout, stderr = self._run_cli("nonexistent_file.qvf")
        # Should fail during extraction (file not found)
        assert rc != 0

    def test_invalid_extension_is_accepted(self, tmp_dir):
        """Any file extension is accepted by the parser (extraction may fail)."""
        p = tmp_dir / "test.xlsx"
        p.write_text("fake")
        rc, stdout, stderr = self._run_cli(str(p))
        # Parser accepts it; extraction will fail
        assert rc != 0

    def test_validate_flag_accepted(self):
        """--validate flag should be accepted by argparse."""
        rc, stdout, stderr = self._run_cli("--help")
        assert "--validate" in stdout

    def test_batch_config_flag_accepted(self):
        rc, stdout, stderr = self._run_cli("--help")
        assert "--batch-config" in stdout

    def test_dry_run_flag_accepted(self):
        rc, stdout, stderr = self._run_cli("--help")
        assert "--dry-run" in stdout

    def test_assess_flag_accepted(self):
        rc, stdout, stderr = self._run_cli("--help")
        assert "--assess" in stdout


# ── Argument handling via main() with mocks ──────────────────────────

class TestMainWithMocks:
    """Test main() logic paths with mocked extraction/generation."""

    def test_dry_run_skips_generation(self, fake_qvf):
        """--dry-run should skip actual generation."""
        with patch('migrate.run_extraction', return_value=True) as mock_ext, \
             patch('migrate.run_generation') as mock_gen, \
             patch('migrate.run_migration_report', return_value=None):
            test_args = ['migrate.py', fake_qvf, '--dry-run']
            with patch('sys.argv', test_args):
                result = main()
            mock_ext.assert_called_once()
            mock_gen.assert_not_called()
            assert result == ExitCode.SUCCESS

    def test_skip_extraction_flag(self, fake_qvf):
        """--skip-extraction should bypass extraction step."""
        with patch('migrate.run_generation', return_value=True) as mock_gen, \
             patch('migrate.run_extraction') as mock_ext, \
             patch('migrate.run_migration_report', return_value=None):
            test_args = ['migrate.py', fake_qvf, '--skip-extraction']
            with patch('sys.argv', test_args):
                result = main()
            mock_ext.assert_not_called()
            mock_gen.assert_called_once()

    def test_extraction_failure_aborts(self, fake_qvf):
        """If extraction fails, generation should not run."""
        with patch('migrate.run_extraction', return_value=False), \
             patch('migrate.run_generation') as mock_gen:
            test_args = ['migrate.py', fake_qvf]
            with patch('sys.argv', test_args):
                result = main()
            mock_gen.assert_not_called()
            assert result == ExitCode.EXTRACTION_FAILED

    def test_quiet_mode(self, fake_qvf):
        """--quiet should not crash."""
        with patch('migrate.run_extraction', return_value=True), \
             patch('migrate.run_generation', return_value=True), \
             patch('migrate.run_migration_report', return_value=None):
            test_args = ['migrate.py', fake_qvf, '--quiet']
            with patch('sys.argv', test_args):
                result = main()
            assert result == ExitCode.SUCCESS

    def test_output_dir_forwarded(self, fake_qvf, tmp_dir):
        """--output-dir should be forwarded to run_generation."""
        out = str(tmp_dir / "custom_out")
        with patch('migrate.run_extraction', return_value=True), \
             patch('migrate.run_generation', return_value=True) as mock_gen, \
             patch('migrate.run_migration_report', return_value=None):
            test_args = ['migrate.py', fake_qvf, '--output-dir', out]
            with patch('sys.argv', test_args):
                main()
            # Check output_dir was passed to run_generation
            call_kwargs = mock_gen.call_args
            assert call_kwargs[1].get('output_dir') == out or call_kwargs.kwargs.get('output_dir') == out


# ── Batch migration tests ───────────────────────────────────────────

class TestBatchMigration:

    def test_batch_empty_dir(self, tmp_dir):
        """Batch with no .qvf/.json files should error."""
        from migrate import run_batch_migration
        result = run_batch_migration(str(tmp_dir))
        assert result == ExitCode.GENERAL_ERROR

    def test_batch_nonexistent_dir(self, tmp_dir):
        from migrate import run_batch_migration
        result = run_batch_migration(str(tmp_dir / "nope"))
        assert result == ExitCode.GENERAL_ERROR

    def test_batch_config_invalid_json(self, tmp_dir):
        """Batch config with invalid JSON should error."""
        p = tmp_dir / "bad_config.json"
        p.write_text("not json", encoding="utf-8")
        from migrate import _run_batch_config
        import argparse
        args = argparse.Namespace(
            batch_config=str(p),
            skip_extraction=False,
            output_dir=None,
            calendar_start=None,
            calendar_end=None,
            culture=None,
        )
        result = _run_batch_config(args)
        assert result == ExitCode.GENERAL_ERROR


# ── DAX optimizer default / opt-out tests ────────────────────────────

class TestDaxOptimizerFlags:
    """Test that --optimize-dax / --no-optimize-dax are parsed correctly."""

    def _get_help_text(self):
        result = subprocess.run(
            [sys.executable, str(_project_root / 'migrate.py'), '--help'],
            capture_output=True, text=True, timeout=30,
        )
        return result.stdout

    def test_optimize_dax_in_help(self):
        """--optimize-dax should appear in help output."""
        assert '--optimize-dax' in self._get_help_text()

    def test_no_optimize_dax_in_help(self):
        """--no-optimize-dax should appear in help output."""
        assert '--no-optimize-dax' in self._get_help_text()

    def test_optimize_dax_enabled_by_default(self):
        """DAX optimizer runs by default — enabled by default help text."""
        help_text = self._get_help_text()
        # The flag description mentions 'enabled by default'
        assert 'enabled by default' in help_text


class TestNewCLIFlags:
    """Test that new CLI flags are accepted and parsed correctly."""

    def _get_help_text(self):
        result = subprocess.run(
            [sys.executable, str(_project_root / 'migrate.py'), '--help'],
            capture_output=True, text=True, timeout=30,
        )
        return result.stdout

    def test_post_check_in_help(self):
        assert '--post-check' in self._get_help_text()

    def test_time_intelligence_in_help(self):
        assert '--time-intelligence' in self._get_help_text()

    def test_sla_config_in_help(self):
        assert '--sla-config' in self._get_help_text()

    def test_jsonl_log_in_help(self):
        assert '--jsonl-log' in self._get_help_text()

    def test_post_check_description(self):
        """Post-check help should mention comprehensive."""
        help_text = self._get_help_text()
        assert 'comprehensive' in help_text.lower() or 'post-migration' in help_text.lower()
