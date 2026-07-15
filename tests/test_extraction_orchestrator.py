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
from pathlib import Path

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

    def test_json_restitution_binary_hydrates_datasources_from_source_app(self):
        """When app has Binary load and no local model, import datasources from source app."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source_qvf = os.path.join(tmpdir, "source_model.qvf")
            restitution_json = os.path.join(tmpdir, "restitution.json")

            source_payload = {
                "app_metadata": {"name": "SourceModel"},
                "datasources": [
                    {
                        "tableName": "FactSales",
                        "connectionType": "qvd",
                        "columns": [{"name": "Amount", "dataType": "numeric"}],
                    }
                ],
                "dimensions": [],
                "measures": [],
                "visualizations": [],
                "sheets": [],
                "variables": [],
                "loadscript": {"script": ""},
                "associations": [],
                "bookmarks": [],
                "master_items": [],
            }
            with open(source_qvf, "w", encoding="utf-8") as f:
                json.dump(source_payload, f)

            restitution_payload = {
                "app_metadata": {"name": "RestitutionApp"},
                "datasources": [],
                "dimensions": [{"name": "Region", "field": "Region"}],
                "measures": [{"name": "Total", "expression": "Sum(Amount)"}],
                "visualizations": [
                    {
                        "type": "barchart",
                        "title": "Total by Region",
                        "dimensions": [{"field": "Region"}],
                        "measures": [{"name": "Total"}],
                    }
                ],
                "sheets": [{"id": "s1", "title": "Overview"}],
                "variables": [],
                "loadscript": {"script": 'Binary "source_model.qvf";'},
                "associations": [],
                "bookmarks": [],
                "master_items": [],
            }
            with open(restitution_json, "w", encoding="utf-8") as f:
                json.dump(restitution_payload, f)

            orch = ExtractionOrchestrator()
            result = orch.extract(restitution_json)

            assert result.get("datasources")
            assert result["datasources"][0]["tableName"] == "FactSales"


class TestBinaryLoadResolutionHelpers:
    def test_extract_binary_load_target(self):
        script = """
        // comment
        Binary "lib://DataFiles/source_app.qvf";
        LOAD * INLINE [A\n1\n];
        """
        target = ExtractionOrchestrator._extract_binary_load_target(script)
        assert target == "lib://DataFiles/source_app.qvf"

    def test_resolve_binary_candidates_honors_overrides(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source_file = os.path.join(tmpdir, "restitution.qvf")
            with open(source_file, "w", encoding="utf-8") as f:
                f.write("{}")

            override_dir = os.path.join(tmpdir, "models")
            os.makedirs(override_dir, exist_ok=True)
            source_model = os.path.join(override_dir, "source_model.qvf")
            with open(source_model, "w", encoding="utf-8") as f:
                f.write("{}")

            candidates = ExtractionOrchestrator._resolve_binary_source_candidates(
                binary_target="source_model.qvf",
                source_file=source_file,
                preferred_source=source_model,
                search_dirs=[override_dir],
            )

            assert candidates
            assert any(str(c).endswith("source_model.qvf") for c in candidates)

    def test_lib_binary_discovers_sibling_qvf_candidates(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source_file = os.path.join(tmpdir, "presentation.qvf")
            model_file = os.path.join(tmpdir, "data_model.qvf")
            for path in (source_file, model_file):
                with open(path, "w", encoding="utf-8") as f:
                    f.write("{}")

            candidates = ExtractionOrchestrator._resolve_binary_source_candidates(
                binary_target="lib://APPS_SENSE/model-uuid",
                source_file=source_file,
            )

            assert Path(model_file).resolve() in candidates

    def test_binary_source_score_prefers_referenced_fields(self):
        target = {
            "measures": [{"expression": "Sum([Sales])"}],
            "dimensions": [{"field": "Region"}],
        }
        matching = {
            "datasources": [{
                "tableName": "Facts",
                "columns": [{"name": "Sales"}, {"name": "Region"}],
            }],
        }
        unrelated = {
            "datasources": [{
                "tableName": "Other",
                "columns": [{"name": "Unrelated"}],
            }],
        }

        matching_score = ExtractionOrchestrator._score_binary_source_data(
            target,
            matching,
        )
        unrelated_score = ExtractionOrchestrator._score_binary_source_data(
            target,
            unrelated,
        )

        assert matching_score > unrelated_score


class TestBinaryVisualBindings:
    def test_filterpane_uses_nested_listbox_field(self):
        payload = {
            "qRoot": {
                "qProperty": {
                    "qInfo": {"qId": "sheet-1", "qType": "sheet"},
                    "qMetaDef": {"title": "Overview"},
                    "cells": [{"name": "filter-1", "type": "filterpane"}],
                },
                "qChildren": [{
                    "qProperty": {
                        "qInfo": {"qId": "filter-1", "qType": "filterpane"},
                    },
                    "qChildren": [{
                        "qProperty": {
                            "qInfo": {"qId": "list-1", "qType": "listbox"},
                            "qListObjectDef": {
                                "qDef": {
                                    "qFieldDefs": ["Month"],
                                    "qFieldLabels": ["Month"],
                                },
                            },
                        },
                    }],
                }],
            },
        }

        _, visuals = ExtractionOrchestrator()._normalize_binary_sheet(payload)

        assert visuals[0]["dimensions"] == [{
            "field": "Month",
            "name": "Month",
            "label": "Month",
            "libraryId": "",
        }]

    def test_library_ids_hydrate_visual_dimension_and_measure(self):
        visuals = [{
            "dimensions": [{
                "field": "", "name": "", "label": "", "libraryId": "dim-1",
            }],
            "measures": [{
                "name": "Measure 1", "label": "Measure 1",
                "expression": "", "libraryId": "measure-1",
            }],
        }]
        dimensions = [{
            "id": "dim-1", "field": "Category", "name": "Category",
            "label": "Category",
        }]
        measures = [{
            "id": "measure-1", "name": "Total", "label": "Total",
            "expression": "Sum(Amount)",
        }]

        ExtractionOrchestrator._resolve_binary_visual_library_items(
            visuals, dimensions, measures,
        )

        assert visuals[0]["dimensions"][0]["field"] == "Category"
        assert visuals[0]["measures"][0]["name"] == "Total"
        assert visuals[0]["measures"][0]["expression"] == "Sum(Amount)"

    def test_calculated_library_dimension_uses_generated_column_name(self):
        visuals = [{
            "dimensions": [{
                "field": "", "name": "", "label": "", "libraryId": "dim-1",
            }],
            "measures": [],
        }]
        dimensions = [{
            "id": "dim-1", "field": "=If([Score] > 0, 'Yes', 'No')",
            "name": "Score category", "label": "Score category",
        }]

        ExtractionOrchestrator._resolve_binary_visual_library_items(
            visuals, dimensions, [],
        )

        assert visuals[0]["dimensions"][0]["field"] == "Score category"


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


# ═══════════════════════════════════════════════════════════════
#  _collect_embedded_json_payloads — binary export decode path
# ═══════════════════════════════════════════════════════════════

class TestCollectEmbeddedJsonPayloads:
    def test_zlib_compressed_json_decoded(self):
        """A zlib-compressed JSON object embedded in bytes is decoded."""
        obj = {"hello": "world", "n": 42}
        raw = b"PREFIX\x00\x00" + zlib.compress(json.dumps(obj).encode("utf-8")) + b"TRAIL"
        payloads = ExtractionOrchestrator._collect_embedded_json_payloads(raw)
        assert obj in payloads

    def test_zlib_compressed_json_array_decoded(self):
        """A zlib-compressed JSON array is decoded."""
        obj = [1, 2, {"k": "v"}]
        raw = zlib.compress(json.dumps(obj).encode("utf-8"))
        payloads = ExtractionOrchestrator._collect_embedded_json_payloads(raw)
        assert obj in payloads

    def test_gzip_compressed_json_decoded(self):
        """A gzip-framed (0x1f 0x8b) JSON payload is decoded with wbits=31."""
        obj = {"gzip": True, "value": "compressed"}
        # wbits=31 produces a gzip container (magic 0x1f 0x8b)
        compressor = zlib.compressobj(9, zlib.DEFLATED, 31)
        gz = compressor.compress(json.dumps(obj).encode("utf-8")) + compressor.flush()
        assert gz[:2] == b"\x1f\x8b"
        raw = b"\x00\x00" + gz
        payloads = ExtractionOrchestrator._collect_embedded_json_payloads(raw)
        assert obj in payloads

    def test_decompression_bomb_skipped(self, monkeypatch):
        """A payload that decompresses to >256MB is skipped without allocating."""
        import qlik_export.extraction_orchestrator as eo

        class _FakeHuge:
            def __len__(self):
                return 300 * 1024 * 1024  # > 256 MB guard, no real allocation

        def _fake_decompress(data, *args, **kwargs):
            return _FakeHuge()

        # Real compressed payload so a signature is found and decompress is invoked.
        raw = zlib.compress(json.dumps({"x": 1}).encode("utf-8"))
        monkeypatch.setattr(eo.zlib, "decompress", _fake_decompress)
        payloads = ExtractionOrchestrator._collect_embedded_json_payloads(raw)
        assert payloads == []

    def test_corrupt_bytes_skipped_gracefully(self):
        """Bytes containing a fake signature but non-decompressible data are skipped."""
        # Contains a zlib magic prefix but the rest is garbage → zlib.error.
        raw = b"\x78\x9c" + b"\xff\xff\xff\xffnot-real-zlib-data"
        payloads = ExtractionOrchestrator._collect_embedded_json_payloads(raw)
        assert payloads == []

    def test_no_signatures_returns_empty(self):
        """Bytes with no compression signatures yield no payloads."""
        raw = b"plain text with no compressed data at all"
        payloads = ExtractionOrchestrator._collect_embedded_json_payloads(raw)
        assert payloads == []

    def test_decompressed_non_json_skipped(self):
        """A compressed payload that is not JSON is skipped."""
        raw = zlib.compress(b"just a plain string, not json")
        payloads = ExtractionOrchestrator._collect_embedded_json_payloads(raw)
        assert payloads == []

    def test_multiple_payloads_collected(self):
        """Multiple compressed JSON blobs in one blob are all decoded."""
        a = {"first": 1}
        b = [{"second": 2}]
        raw = (
            b"A" + zlib.compress(json.dumps(a).encode("utf-8"))
            + b"B" + zlib.compress(json.dumps(b).encode("utf-8"))
        )
        payloads = ExtractionOrchestrator._collect_embedded_json_payloads(raw)
        assert a in payloads
        assert b in payloads


# ═══════════════════════════════════════════════════════════════
#  _collect_binary_measures / _collect_binary_dimensions
#  (dict-coercion bug fix — commit 5f760d8)
# ═══════════════════════════════════════════════════════════════

class TestCollectBinaryMeasures:
    def test_normal_string_measures_pass_through(self):
        vis = [{"measures": [{"name": "Sales", "expression": "Sum(Sales)", "label": "Total Sales"}]}]
        result = ExtractionOrchestrator._collect_binary_measures(vis)
        assert len(result) == 1
        assert result[0]["name"] == "Sales"
        assert result[0]["expression"] == "Sum(Sales)"
        assert result[0]["label"] == "Total Sales"

    def test_dict_name_and_expression_coerced_to_string(self):
        """A measure with dict as name/expression must not raise TypeError."""
        vis = [{"measures": [{"name": {"qv": "Sales"}, "expression": {"qDef": "Sum(Sales)"}}]}]
        result = ExtractionOrchestrator._collect_binary_measures(vis)
        assert len(result) == 1
        assert isinstance(result[0]["name"], str)
        assert isinstance(result[0]["expression"], str)

    def test_dict_label_falls_back_to_name(self):
        vis = [{"measures": [{"name": "Sales", "expression": "Sum(Sales)", "label": {"bad": "dict"}}]}]
        result = ExtractionOrchestrator._collect_binary_measures(vis)
        assert result[0]["label"] == "Sales"

    def test_duplicate_measures_deduplicated(self):
        vis = [
            {"measures": [{"name": "Sales", "expression": "Sum(Sales)"}]},
            {"measures": [{"name": "Sales", "expression": "Sum(Sales)"}]},
        ]
        result = ExtractionOrchestrator._collect_binary_measures(vis)
        assert len(result) == 1

    def test_empty_measure_skipped(self):
        vis = [{"measures": [{"name": "", "expression": ""}]}]
        result = ExtractionOrchestrator._collect_binary_measures(vis)
        assert result == []

    def test_no_measures_key_returns_empty(self):
        vis = [{}]
        result = ExtractionOrchestrator._collect_binary_measures(vis)
        assert result == []


class TestCollectBinaryDimensions:
    def test_normal_string_dimensions_pass_through(self):
        vis = [{"dimensions": [{"field": "Region", "label": "Region Name"}]}]
        result = ExtractionOrchestrator._collect_binary_dimensions(vis)
        assert len(result) == 1
        assert result[0]["field"] == "Region"
        assert result[0]["label"] == "Region Name"

    def test_dict_field_coerced_to_string(self):
        """A dimension with dict as field must not crash."""
        vis = [{"dimensions": [{"field": {"qv": "Region"}}]}]
        result = ExtractionOrchestrator._collect_binary_dimensions(vis)
        assert len(result) == 1
        assert isinstance(result[0]["field"], str)

    def test_dict_label_falls_back_to_field(self):
        vis = [{"dimensions": [{"field": "Region", "label": {"bad": "dict"}}]}]
        result = ExtractionOrchestrator._collect_binary_dimensions(vis)
        assert result[0]["label"] == "Region"

    def test_duplicate_dimensions_deduplicated(self):
        vis = [
            {"dimensions": [{"field": "Region"}]},
            {"dimensions": [{"field": "Region"}]},
        ]
        result = ExtractionOrchestrator._collect_binary_dimensions(vis)
        assert len(result) == 1

    def test_empty_field_skipped(self):
        vis = [{"dimensions": [{"field": ""}]}]
        result = ExtractionOrchestrator._collect_binary_dimensions(vis)
        assert result == []

    def test_no_dimensions_key_returns_empty(self):
        vis = [{}]
        result = ExtractionOrchestrator._collect_binary_dimensions(vis)
        assert result == []


# == Binary master measure/dimension extraction (roadmap #2) =========

class TestBinaryMasterItemExtraction:
    def test_master_measure_extracted(self):
        payload = {
            "qInfo": {"qId": "m1", "qType": "measure"},
            "qMeasure": {"qLabel": "Sales", "qDef": "Sum(Sales)",
                         "qNumFormat": {"qFmt": "#,##0"}},
            "qMetaDef": {"title": "Sales", "description": "Total sales"},
        }
        m = ExtractionOrchestrator._normalize_binary_master_measure(payload)
        assert m["name"] == "Sales"
        assert m["expression"] == "Sum(Sales)"
        assert m["label"] == "Sales"
        assert m["formatString"] == "#,##0"

    def test_master_measure_empty_returns_none(self):
        payload = {"qInfo": {"qId": "x"}, "qMeasure": {}, "qMetaDef": {}}
        assert ExtractionOrchestrator._normalize_binary_master_measure(payload) is None

    def test_master_dimension_extracted(self):
        payload = {
            "qInfo": {"qId": "d1", "qType": "dimension"},
            "qDim": {"qFieldDefs": ["Region"], "qFieldLabels": ["Region"],
                     "qGrouping": "N"},
            "qMetaDef": {"title": "Region"},
        }
        d = ExtractionOrchestrator._normalize_binary_master_dimension(payload)
        assert d["name"] == "Region"
        assert d["field"] == "Region"
        assert d["fields"] == ["Region"]

    def test_master_dimension_calculated_field(self):
        payload = {
            "qInfo": {"qId": "d2", "qType": "dimension"},
            "qDim": {"qFieldDefs": ["=Year([Date])"], "qFieldLabels": ["Year"]},
            "qMetaDef": {"title": "Year"},
        }
        d = ExtractionOrchestrator._normalize_binary_master_dimension(payload)
        assert d["name"] == "Year"
        assert d["field"] == "=Year([Date])"

    def test_merge_prefers_master_over_inferred(self):
        master = [{"name": "Sales", "expression": "Sum(Sales)"}]
        inferred = [{"name": "sales", "expression": ""}, {"name": "Cost", "expression": ""}]
        merged = ExtractionOrchestrator._merge_binary_items(master, inferred, key="name")
        # 'Sales' from master wins (case-insensitive dedup), 'Cost' added
        assert len(merged) == 2
        assert merged[0]["expression"] == "Sum(Sales)"
