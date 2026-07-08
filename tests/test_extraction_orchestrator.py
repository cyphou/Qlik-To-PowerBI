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
import zlib
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

    def test_qvf_extension_with_json_payload_fallback(self):
        """Some samples are named .qvf but contain JSON content.

        Extraction should gracefully fall back to JSON parsing instead of
        failing with BadZipFile.
        """
        data = {
            "datasources": [{"name": "Orders", "connectionType": "csv"}],
            "sheets": [{"id": "s1", "title": "Sheet1"}],
            "visualizations": [{"id": "v1", "type": "barchart"}],
            "variables": [],
            "associations": [],
            "bookmarks": [],
            "master_items": [],
        }
        with tempfile.NamedTemporaryFile(suffix=".qvf", delete=False, mode="w", encoding="utf-8") as f:
            json.dump(data, f)
            path = f.name
        try:
            orch = ExtractionOrchestrator()
            result = orch.extract(path)
            assert isinstance(result, dict)
            assert "datasources" in result
            assert len(result.get("datasources", [])) == 1
        finally:
            os.unlink(path)

    def test_qvf_extension_with_binary_payload_raises_clear_error(self):
        """Binary non-ZIP .qvf files should not be parsed as JSON fallback."""
        with tempfile.NamedTemporaryFile(suffix=".qvf", delete=False) as f:
            f.write(b"\xff\xfe\x00\x01not-json")
            path = f.name
        try:
            orch = ExtractionOrchestrator()
            with pytest.raises(ValueError, match="Invalid QVF file"):
                orch.extract(path)
        finally:
            os.unlink(path)

    def test_qvf_extension_with_malformed_json_payload_raises_json_error(self):
        """A .qvf that looks like JSON but is invalid should return a JSON parse error."""
        with tempfile.NamedTemporaryFile(suffix=".qvf", delete=False, mode="w", encoding="utf-8") as f:
            f.write('{"datasources": [}')
            path = f.name
        try:
            orch = ExtractionOrchestrator()
            with pytest.raises(ValueError, match="Invalid JSON export"):
                orch.extract(path)
        finally:
            os.unlink(path)

    def test_qvf_extension_with_utf16_json_payload_fallback(self):
        """UTF-16 JSON payloads mislabeled as .qvf should still be parsed."""
        text = '{"datasources": [{"name": "Orders", "connectionType": "csv"}], "sheets": []}'
        with tempfile.NamedTemporaryFile(suffix=".qvf", delete=False) as f:
            f.write(text.encode("utf-16"))
            path = f.name
        try:
            orch = ExtractionOrchestrator()
            result = orch.extract(path)
            assert isinstance(result, dict)
            assert len(result.get("datasources", [])) == 1
        finally:
            os.unlink(path)

    def test_qvf_extension_with_binary_export_payload_fallback(self):
        """Binary Qlik exports with embedded compressed JSON should be decoded."""
        metadata = {
            "qTitle": "Binary Export App",
            "description": "Exported from Qlik",
            "qLastReloadTime": "2026-07-08T06:32:43.836Z",
        }
        sheet = {
            "qMetaData": {"qType": "sheet"},
            "qRoot": {
                "qProperty": {
                    "qInfo": {"qId": "sheet-1", "qType": "sheet"},
                    "qMetaDef": {"title": "Sheet 1", "description": ""},
                    "rank": 0,
                    "cells": [
                        {
                            "name": "viz-1",
                            "type": "table",
                            "bounds": {"x": 0, "y": 0, "width": 100, "height": 100},
                        }
                    ],
                },
                "qChildren": [
                    {
                        "qProperty": {
                            "qInfo": {"qId": "viz-1", "qType": "table"},
                            "qHyperCubeDef": {
                                "qDimensions": [
                                    {"qDef": {"qFieldDefs": ["Region"], "qFieldLabels": ["Region"]}}
                                ],
                                "qMeasures": [
                                    {"qDef": {"qLabel": "Sales", "qDef": "Sum(Sales)"}}
                                ],
                            },
                        }
                    }
                ],
            },
        }
        script = {"qScript": "LOAD * INLINE [Region,Sales\nA,1\n];"}
        variable_list = {
            "qId": "user_variablelist",
            "qEntryList": [
                {
                    "qProperties": {
                        "qInfo": {"qId": "var-1", "qType": "variable"},
                        "qName": "vTest",
                        "qDefinition": "42",
                    }
                }
            ],
        }
        payload = (
            b"qvapp_approperties"
            + zlib.compress(json.dumps(metadata).encode("utf-8"))
            + b"qvapp_allproperties"
            + zlib.compress(json.dumps(sheet).encode("utf-8"))
            + b"qvapp_appscript"
            + zlib.compress(json.dumps(script).encode("utf-8"))
            + b"qvapp_variablelist"
            + zlib.compress(json.dumps(variable_list).encode("utf-8"))
        )
        with tempfile.NamedTemporaryFile(suffix=".qvf", delete=False) as f:
            f.write(payload)
            path = f.name
        try:
            orch = ExtractionOrchestrator()
            result = orch.extract(path)
            assert result["app_metadata"]["name"] == "Binary Export App"
            assert result["loadscript"]["script"].startswith("LOAD * INLINE")
            assert any(dim["field"] == "Region" for dim in result["dimensions"])
            assert any(measure["expression"] == "Sum(Sales)" for measure in result["measures"])
            assert len(result["visualizations"]) == 1
            assert result["variables"][0]["name"] == "vTest"
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


class TestExtractColumnsFromMQuery:
    def test_extract_columns_strips_trailing_table_label_fragment(self):
        m_query = (
            'let\n'
            '    Source = Sql.Database("ServerName", "DatabaseName"),\n'
            '    Table = Source{{[Schema="dbo",Item="TableName"]}}[Data],\n'
            '    SelectedColumns = Table.SelectColumns(Table, {"QCLG_CODE_ENTITE", "ID_CHGT_TECH;\n\n[QUAL_QUESTPAT_CLOT_GENERIQUE]:"})\n'
            'in\n'
            '    SelectedColumns\n'
        )
        columns = ExtractionOrchestrator._extract_columns_from_m_query(m_query)
        assert [c["name"] for c in columns] == ["QCLG_CODE_ENTITE", "ID_CHGT_TECH"]


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
