"""Tests for portfolio-level server assessment (powerbi_import/server_assessment.py).

Covers the previously-missing ``assess_portfolio`` entry point used by the
``--assess-server`` CLI flag, plus app-export discovery filtering.
"""

import os

import pytest

from powerbi_import.server_assessment import (
    assess_portfolio,
    run_server_assessment,
    _discover_app_exports,
)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QLIK_EXPORTS = os.path.join(REPO_ROOT, "examples", "qlik", "qlik_exports")


# ─────────────────────────────────────────────────────────────
#  _discover_app_exports
# ─────────────────────────────────────────────────────────────

class TestDiscoverAppExports:
    def test_finds_json_and_qvf(self, tmp_path):
        (tmp_path / "app_a.json").write_text("{}", encoding="utf-8")
        (tmp_path / "app_b.qvf").write_bytes(b"PK")
        found = _discover_app_exports(str(tmp_path))
        names = sorted(os.path.basename(p) for p in found)
        assert names == ["app_a.json", "app_b.qvf"]

    def test_skips_generated_json(self, tmp_path):
        (tmp_path / "real_app.json").write_text("{}", encoding="utf-8")
        (tmp_path / "migration_report_x.json").write_text("{}", encoding="utf-8")
        (tmp_path / "portfolio_assessment.json").write_text("{}", encoding="utf-8")
        (tmp_path / "lineage_map.json").write_text("{}", encoding="utf-8")
        found = [os.path.basename(p) for p in _discover_app_exports(str(tmp_path))]
        assert found == ["real_app.json"]

    def test_finds_one_level_deep(self, tmp_path):
        sub = tmp_path / "nested"
        sub.mkdir()
        (sub / "deep_app.json").write_text("{}", encoding="utf-8")
        found = [os.path.basename(p) for p in _discover_app_exports(str(tmp_path))]
        assert "deep_app.json" in found

    def test_recursive_finds_deeply_nested(self, tmp_path):
        deep = tmp_path / "space" / "stream" / "apps"
        deep.mkdir(parents=True)
        (deep / "buried.qvf").write_bytes(b"binary")
        # flat scan misses it (3 levels deep)
        flat = [os.path.basename(p) for p in _discover_app_exports(str(tmp_path))]
        assert "buried.qvf" not in flat
        # recursive finds it
        rec = [os.path.basename(p) for p in _discover_app_exports(str(tmp_path), recursive=True)]
        assert "buried.qvf" in rec

    def test_recursive_excludes_generated_project_dirs(self, tmp_path):
        (tmp_path / "real.qvf").write_bytes(b"binary")
        gen = tmp_path / "MyApp.SemanticModel" / "definition"
        gen.mkdir(parents=True)
        (gen / "model.json").write_text("{}", encoding="utf-8")
        rec = [os.path.basename(p) for p in _discover_app_exports(str(tmp_path), recursive=True)]
        assert "real.qvf" in rec
        assert "model.json" not in rec


# ─────────────────────────────────────────────────────────────
#  run_server_assessment (synthetic adapted data)
# ─────────────────────────────────────────────────────────────

class TestRunServerAssessment:
    def test_classifies_and_aggregates(self):
        apps = [
            {"datasources": [], "worksheets": [{"title": "s1"}], "calculations": []},
            {"datasources": [], "worksheets": [], "calculations": []},
        ]
        result = run_server_assessment(apps, ["AppOne", "AppTwo"])
        assert result.total_apps == 2
        assert result.green_count + result.yellow_count + result.red_count == 2
        assert len(result.app_results) == 2
        assert 0 <= result.readiness_pct <= 100


# ─────────────────────────────────────────────────────────────
#  assess_portfolio
# ─────────────────────────────────────────────────────────────

class TestAssessPortfolio:
    def test_rejects_non_directory(self):
        with pytest.raises(ValueError):
            assess_portfolio("does_not_exist_dir_xyz")

    def test_empty_directory_raises(self, tmp_path):
        with pytest.raises(ValueError):
            assess_portfolio(str(tmp_path))

    @pytest.mark.skipif(
        not os.path.isdir(QLIK_EXPORTS),
        reason="example qlik exports not present",
    )
    def test_real_folder_assessment(self, tmp_path):
        result = assess_portfolio(QLIK_EXPORTS, output_dir=str(tmp_path))
        # Aggregate keys consumed by the CLI summary block.
        assert result["total_apps"] >= 1
        assert result["green"] + result["yellow"] + result["red"] == result["total_apps"]
        assert "readiness_pct" in result
        assert "total_effort_hours" in result
        assert result["apps"]
        assert "connector_census" in result
        # HTML report is generated when output_dir is given.
        assert os.path.isfile(result["html_report"])
