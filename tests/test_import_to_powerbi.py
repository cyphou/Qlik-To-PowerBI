"""
Tests for powerbi_import.import_to_powerbi — the generation orchestrator.

Validates JSON loading, format adapter integration, and error handling
for the module that sits between the Qlik JSON files and the .pbip generation.
"""

import os
import sys
import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

# Ensure project root is importable
_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root))

from powerbi_import.import_to_powerbi import PowerBIImporter


# ── Fixtures ────────────────────────────────────────────────────────

@pytest.fixture
def qlik_json_dir(tmp_path):
    """Create a temp directory with the 11 Qlik intermediate JSON files."""
    files = {
        'app_metadata.json': {'name': 'TestApp', 'author': 'Tester'},
        'datasources.json': [
            {
                'tableName': 'Sales',
                'connectionType': 'PostgreSQL',
                'connection': {'server': 'localhost', 'database': 'test'},
                'columns': [
                    {'name': 'Amount', 'dataType': 'numeric'},
                    {'name': 'Region', 'dataType': 'string'},
                ],
            }
        ],
        'dimensions.json': [
            {'name': 'Region', 'field': 'Region'},
        ],
        'measures.json': [
            {'name': 'Total Sales', 'expression': 'Sum(Amount)'},
        ],
        'visualizations.json': [
            {
                'type': 'barchart',
                'title': 'Sales Chart',
                'dimensions': [{'field': 'Region'}],
                'measures': [{'name': 'Total Sales'}],
            },
        ],
        'sheets.json': [
            {'id': 'sheet1', 'title': 'Overview'},
        ],
        'variables.json': [
            {'name': 'vYear', 'definition': '2024'},
        ],
        'loadscript.json': {'script': 'LOAD * FROM Sales.qvd'},
        'associations.json': [],
        'bookmarks.json': [],
        'master_items.json': [],
    }
    for name, content in files.items():
        (tmp_path / name).write_text(json.dumps(content), encoding='utf-8')
    return str(tmp_path)


@pytest.fixture
def partial_json_dir(tmp_path):
    """Create a directory with only some JSON files (missing datasources)."""
    files = {
        'app_metadata.json': {'name': 'Partial'},
        'measures.json': [{'name': 'M1', 'expression': 'Sum(X)'}],
        'dimensions.json': [],
        'visualizations.json': [],
        'sheets.json': [],
        'variables.json': [],
        'loadscript.json': {},
        'associations.json': [],
        'bookmarks.json': [],
        'master_items.json': [],
    }
    for name, content in files.items():
        (tmp_path / name).write_text(json.dumps(content), encoding='utf-8')
    return str(tmp_path)


@pytest.fixture
def empty_json_dir(tmp_path):
    """Create a directory with all empty JSON files."""
    files = {
        'app_metadata.json': {},
        'datasources.json': [],
        'dimensions.json': [],
        'measures.json': [],
        'visualizations.json': [],
        'sheets.json': [],
        'variables.json': [],
        'loadscript.json': {},
        'associations.json': [],
        'bookmarks.json': [],
        'master_items.json': [],
    }
    for name, content in files.items():
        (tmp_path / name).write_text(json.dumps(content), encoding='utf-8')
    return str(tmp_path)


# ── Initialization tests ────────────────────────────────────────────

class TestPowerBIImporterInit:

    def test_default_source_dir(self):
        importer = PowerBIImporter()
        assert importer.source_dir == 'qlik_export/'

    def test_custom_source_dir(self, qlik_json_dir):
        importer = PowerBIImporter(source_dir=qlik_json_dir)
        assert importer.source_dir == qlik_json_dir


# ── JSON loading tests ──────────────────────────────────────────────

class TestQlikJsonLoading:

    def test_load_all_11_files(self, qlik_json_dir):
        importer = PowerBIImporter(source_dir=qlik_json_dir)
        data = importer._load_qlik_json_files()
        assert set(data.keys()) == {
            'app_metadata', 'datasources', 'dimensions', 'measures',
            'visualizations', 'sheets', 'variables', 'loadscript',
            'associations', 'bookmarks', 'master_items',
        }
        assert len(data['datasources']) == 1
        assert data['app_metadata']['name'] == 'TestApp'

    def test_missing_file_returns_defaults(self, partial_json_dir):
        """Missing datasources.json should default to []."""
        importer = PowerBIImporter(source_dir=partial_json_dir)
        data = importer._load_qlik_json_files()
        assert data['datasources'] == []

    def test_empty_files_load_ok(self, empty_json_dir):
        importer = PowerBIImporter(source_dir=empty_json_dir)
        data = importer._load_qlik_json_files()
        assert data['datasources'] == []
        assert data['app_metadata'] == {}

    def test_corrupt_json_file_returns_default(self, tmp_path):
        """Corrupt JSON file should not crash loading."""
        (tmp_path / "datasources.json").write_text("NOT JSON", encoding="utf-8")
        (tmp_path / "app_metadata.json").write_text("{}", encoding="utf-8")
        # Write other necessary files as valid
        for name in ['dimensions', 'measures', 'visualizations', 'sheets',
                      'variables', 'associations', 'bookmarks', 'master_items']:
            (tmp_path / f"{name}.json").write_text("[]", encoding="utf-8")
        (tmp_path / "loadscript.json").write_text("{}", encoding="utf-8")

        importer = PowerBIImporter(source_dir=str(tmp_path))
        data = importer._load_qlik_json_files()
        # Should default to [] for corrupt datasources
        assert data['datasources'] == []


# ── Format adapter integration tests ─────────────────────────────────

class TestConvertedObjectsLoading:

    def test_load_converted_objects_via_adapter(self, qlik_json_dir):
        """Full path: JSON files → format adapter → converted_objects."""
        importer = PowerBIImporter(source_dir=qlik_json_dir)
        result = importer._load_converted_objects()
        assert isinstance(result, dict)
        assert 'datasources' in result
        assert 'worksheets' in result
        assert len(result['datasources']) >= 1

    def test_empty_datasources_returns_valid_structure(self, empty_json_dir):
        """Empty datasources should still return valid structure."""
        importer = PowerBIImporter(source_dir=empty_json_dir)
        result = importer._load_converted_objects()
        assert isinstance(result, dict)
        assert result['datasources'] == []


# ── import_all tests (with mocked generation) ───────────────────────

class TestImportAll:

    def test_import_all_no_datasources_prints_error(self, empty_json_dir, capsys):
        """import_all with empty datasources should print error and return."""
        importer = PowerBIImporter(source_dir=empty_json_dir)
        importer.import_all(generate_pbip=False)
        captured = capsys.readouterr()
        assert "ERROR" in captured.out or "No datasources" in captured.out

    def test_import_all_with_data(self, qlik_json_dir, capsys):
        """import_all with valid data should proceed (generation may fail without full deps)."""
        importer = PowerBIImporter(source_dir=qlik_json_dir)
        # Disable actual generation so test focuses on loading/adapter
        importer.import_all(generate_pbip=False)
        captured = capsys.readouterr()
        assert "IMPORT POWER BI" in captured.out
        assert "Sales Chart" in captured.out or "Report" in captured.out

    def test_import_all_custom_report_name(self, qlik_json_dir, capsys):
        """Custom report_name should be used."""
        importer = PowerBIImporter(source_dir=qlik_json_dir)
        importer.import_all(generate_pbip=False, report_name='CustomReport')
        captured = capsys.readouterr()
        assert "CustomReport" in captured.out


# ── Legacy fallback tests ───────────────────────────────────────────

class TestLegacyFallback:

    def test_legacy_format_loading(self, tmp_path):
        """If format_adapter import fails, legacy files should be loaded."""
        # Create pre-converted legacy files
        (tmp_path / "datasources.json").write_text(json.dumps([
            {"name": "LegacyDS", "tables": []}
        ]), encoding="utf-8")
        (tmp_path / "worksheets.json").write_text("[]", encoding="utf-8")
        (tmp_path / "dashboards.json").write_text("[]", encoding="utf-8")
        (tmp_path / "calculations.json").write_text("[]", encoding="utf-8")
        (tmp_path / "parameters.json").write_text("[]", encoding="utf-8")
        (tmp_path / "filters.json").write_text("[]", encoding="utf-8")
        (tmp_path / "stories.json").write_text("[]", encoding="utf-8")
        (tmp_path / "actions.json").write_text("[]", encoding="utf-8")
        (tmp_path / "sets.json").write_text("[]", encoding="utf-8")
        (tmp_path / "groups.json").write_text("[]", encoding="utf-8")
        (tmp_path / "bins.json").write_text("[]", encoding="utf-8")
        (tmp_path / "hierarchies.json").write_text("[]", encoding="utf-8")
        (tmp_path / "sort_orders.json").write_text("[]", encoding="utf-8")
        (tmp_path / "aliases.json").write_text("{}", encoding="utf-8")
        (tmp_path / "custom_sql.json").write_text("[]", encoding="utf-8")
        (tmp_path / "user_filters.json").write_text("[]", encoding="utf-8")

        importer = PowerBIImporter(source_dir=str(tmp_path))
        result = importer._load_legacy_format_files()
        assert len(result['datasources']) == 1
        assert result['datasources'][0]['name'] == 'LegacyDS'
        assert result['aliases'] == {}
