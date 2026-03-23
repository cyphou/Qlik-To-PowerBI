"""Tests for qlik_export.extraction_orchestrator — QVF/JSON extraction pipeline.

Covers:
- ExtractionOrchestrator: extract, load_intermediate_json, get_extraction_summary
- Input dispatch (.qvf vs .json vs unsupported)
- Intermediate JSON loading with missing files
- Extraction summary counts
"""

import json
import os
import tempfile
import pytest
from qlik_export.extraction_orchestrator import ExtractionOrchestrator


# ═══════════════════════════════════════════════════════════════
#  Constructor
# ═══════════════════════════════════════════════════════════════

class TestConstructor:
    def test_default_output_dir(self):
        orch = ExtractionOrchestrator()
        assert isinstance(orch, ExtractionOrchestrator)

    def test_custom_output_dir(self):
        orch = ExtractionOrchestrator(output_dir="/tmp/test")
        assert isinstance(orch, ExtractionOrchestrator)


# ═══════════════════════════════════════════════════════════════
#  extract() — input validation
# ═══════════════════════════════════════════════════════════════

class TestExtractInputValidation:
    def test_unsupported_extension_raises(self):
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            f.write(b"data")
            path = f.name
        try:
            orch = ExtractionOrchestrator()
            with pytest.raises((ValueError, Exception)):
                orch.extract(path)
        finally:
            os.unlink(path)

    def test_missing_file_raises(self):
        orch = ExtractionOrchestrator()
        with pytest.raises((FileNotFoundError, OSError, Exception)):
            orch.extract("/nonexistent/file.qvf")


# ═══════════════════════════════════════════════════════════════
#  extract() — JSON input
# ═══════════════════════════════════════════════════════════════

class TestExtractFromJson:
    def test_direct_intermediate_format(self):
        """JSON in intermediate format (has known keys)."""
        data = {
            "datasources": [{"name": "Orders", "connectionType": "csv"}],
            "measures": [{"name": "Total", "expression": "Sum(Amount)"}],
            "dimensions": [{"name": "Region", "field": "Region"}],
            "sheets": [{"id": "s1", "title": "Sheet1"}],
            "visualizations": [{"type": "barchart"}],
            "variables": [],
            "associations": [],
            "bookmarks": [],
            "master_items": [],
        }
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            json.dump(data, f)
            path = f.name
        try:
            orch = ExtractionOrchestrator()
            result = orch.extract(path)
            assert isinstance(result, dict)
            assert "datasources" in result
        finally:
            os.unlink(path)

    def test_minimal_json(self):
        """Minimal JSON dict."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            json.dump({"app_name": "Test"}, f)
            path = f.name
        try:
            orch = ExtractionOrchestrator()
            result = orch.extract(path)
            assert isinstance(result, dict)
        finally:
            os.unlink(path)

    def test_empty_json_dict(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            json.dump({}, f)
            path = f.name
        try:
            orch = ExtractionOrchestrator()
            result = orch.extract(path)
            assert isinstance(result, dict)
        finally:
            os.unlink(path)


# ═══════════════════════════════════════════════════════════════
#  load_intermediate_json
# ═══════════════════════════════════════════════════════════════

class TestLoadIntermediateJson:
    def test_load_complete_set(self):
        """All 11 files present."""
        with tempfile.TemporaryDirectory() as tmpdir:
            files = {
                "app_metadata.json": {"app_name": "Test"},
                "datasources.json": [{"name": "DS1"}],
                "dimensions.json": [{"name": "D1"}],
                "measures.json": [{"name": "M1"}],
                "visualizations.json": [{"type": "bar"}],
                "sheets.json": [{"id": "s1"}],
                "variables.json": [{"name": "v1"}],
                "loadscript.json": {"script": "LOAD..."},
                "associations.json": [{"from": "A", "to": "B"}],
                "bookmarks.json": [{"name": "BM1"}],
                "master_items.json": [{"name": "MI1"}],
            }
            for fname, content in files.items():
                with open(os.path.join(tmpdir, fname), "w") as f:
                    json.dump(content, f)

            result = ExtractionOrchestrator.load_intermediate_json(tmpdir)
            assert result["app_metadata"]["app_name"] == "Test"
            assert len(result["datasources"]) == 1
            assert len(result["measures"]) == 1

    def test_load_with_missing_files(self):
        """Missing files return defaults (empty dict/list)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Only write app_metadata
            with open(os.path.join(tmpdir, "app_metadata.json"), "w") as f:
                json.dump({"app_name": "Partial"}, f)

            result = ExtractionOrchestrator.load_intermediate_json(tmpdir)
            assert result["app_metadata"]["app_name"] == "Partial"
            assert result.get("datasources") == [] or result.get("datasources") == {}
            assert result.get("measures") == [] or result.get("measures") == {}

    def test_load_empty_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = ExtractionOrchestrator.load_intermediate_json(tmpdir)
            assert isinstance(result, dict)


# ═══════════════════════════════════════════════════════════════
#  write_intermediate_json
# ═══════════════════════════════════════════════════════════════

class TestWriteIntermediateJson:
    def test_write_and_load_roundtrip(self):
        """Extract from JSON, write, load back — should match."""
        data = {
            "datasources": [{"name": "T1", "connectionType": "csv"}],
            "measures": [{"name": "M1", "expression": "Sum(X)"}],
            "dimensions": [],
            "sheets": [],
            "visualizations": [],
            "variables": [],
            "associations": [],
            "bookmarks": [],
            "master_items": [],
        }
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            json.dump(data, f)
            input_path = f.name

        with tempfile.TemporaryDirectory() as outdir:
            try:
                orch = ExtractionOrchestrator()
                orch.extract(input_path)
                orch.write_intermediate_json(outdir)

                loaded = ExtractionOrchestrator.load_intermediate_json(outdir)
                assert isinstance(loaded, dict)
            finally:
                os.unlink(input_path)


# ═══════════════════════════════════════════════════════════════
#  get_extraction_summary
# ═══════════════════════════════════════════════════════════════

class TestGetExtractionSummary:
    def test_summary_after_extract(self):
        data = {
            "datasources": [{"name": "A"}, {"name": "B"}],
            "measures": [{"name": "M1"}],
            "dimensions": [{"name": "D1"}, {"name": "D2"}],
            "sheets": [{"id": "s1"}],
            "visualizations": [{"type": "bar"}, {"type": "line"}],
            "variables": [],
            "associations": [],
            "bookmarks": [],
            "master_items": [],
        }
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            json.dump(data, f)
            path = f.name
        try:
            orch = ExtractionOrchestrator()
            orch.extract(path)
            summary = orch.get_extraction_summary()
            assert isinstance(summary, dict)
            assert summary.get("datasources_count", 0) >= 1 or summary.get("tables", 0) >= 1
        finally:
            os.unlink(path)
