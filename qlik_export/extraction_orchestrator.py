"""
Extraction Orchestrator — QVF/JSON → 11 intermediate JSON files

Two-step pipeline:
  1. Parse QVF or JSON export → produce 11 structured JSON files
  2. Load intermediate JSON for the generation step (TMDL + visuals)

Intermediate JSON contract:
  app_metadata.json      App name, description, author, dates
  datasources.json       Connection strings, tables, columns, types
  dimensions.json        Master dimensions (fields, labels, groupings)
  measures.json          Master measures (expressions, labels, formats)
  visualizations.json    Chart types, dimension/measure bindings
  sheets.json            Sheet layouts, cell positions
  variables.json         Variables (name, definition, comment)
  loadscript.json        Full Qlik load script
  associations.json      Table associations / relationships
  bookmarks.json         Bookmarks and selections
  master_items.json      Master items (combined dim/measure refs)
"""

import json
import logging
import os
import re
import tempfile
import zipfile
import zlib
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)

# The 11 intermediate file names
INTERMEDIATE_FILES = [
    "app_metadata.json",
    "datasources.json",
    "dimensions.json",
    "measures.json",
    "visualizations.json",
    "sheets.json",
    "variables.json",
    "loadscript.json",
    "associations.json",
    "bookmarks.json",
    "master_items.json",
]


class ExtractionOrchestrator:
    """
    Orchestrate the extraction of Qlik content into 11 intermediate JSON files.

    Supports two input modes:
      1. QVF file (.qvf) — uses QVFExtractor internally
      2. JSON export (.json) — parses Qlik Sense JSON export
    """

    def __init__(self, output_dir: str = "output"):
        self.output_dir = Path(output_dir)
        self._data: Dict[str, Any] = {}

    # ─────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────

    def extract(
        self,
        input_path: str,
        resolve_binary: bool = True,
        binary_source: Optional[str] = None,
        binary_source_dirs: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Run extraction from a QVF or JSON file.

        Args:
            input_path: Path to .qvf or .json file

        Returns:
            Dict with all 11 intermediate data structures
        """
        path = Path(input_path)
        if not path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")

        ext = path.suffix.lower()
        if ext == ".qvf":
            self._extract_from_qvf(path)
        elif ext == ".json":
            self._extract_from_json(path)
        else:
            raise ValueError(f"Unsupported file format: {ext}. Use .qvf or .json")

        # Post-extraction: parse load script → enrich datasources with M queries
        self._enrich_from_loadscript(
            resolve_binary=resolve_binary,
            binary_source=binary_source,
            binary_source_dirs=binary_source_dirs,
        )

        logger.info(f"Extraction completed from {path.name}")
        return self._data

    def write_intermediate_json(self, output_dir: Optional[str] = None) -> str:
        """
        Write all 11 intermediate JSON files to the output directory.

        Returns:
            Path to the output directory
        """
        out = Path(output_dir) if output_dir else self.output_dir
        out.mkdir(parents=True, exist_ok=True)

        for filename in INTERMEDIATE_FILES:
            key = filename.replace(".json", "")
            data = self._data.get(key, {})
            filepath = out / filename
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
            logger.info(f"  Wrote {filepath}")

        logger.info(f"All 11 intermediate files written to {out}")
        return str(out)

    def extract_and_write(self, input_path: str,
                          output_dir: Optional[str] = None) -> str:
        """
        Extract from input and write all 11 JSON files. Convenience method.

        Returns:
            Path to the output directory
        """
        self.extract(input_path)
        return self.write_intermediate_json(output_dir)

    @staticmethod
    def load_intermediate_json(json_dir: str) -> Dict[str, Any]:
        """
        Load all 11 intermediate JSON files for the generation step.

        Args:
            json_dir: Directory containing the 11 JSON files

        Returns:
            Dict keyed by file stem (e.g., 'datasources', 'measures', ...)
        """
        result = {}
        json_path = Path(json_dir)

        for filename in INTERMEDIATE_FILES:
            filepath = json_path / filename
            key = filename.replace(".json", "")
            if filepath.exists():
                with open(filepath, "r", encoding="utf-8") as f:
                    result[key] = json.load(f)
                logger.debug(f"  Loaded {filename}")
            else:
                logger.warning(f"  Missing {filename} — using empty default")
                result[key] = {} if key in ("app_metadata", "loadscript") else []

        return result

    # ─────────────────────────────────────────────────────────────
    # QVF Extraction
    # ─────────────────────────────────────────────────────────────

    def _extract_from_qvf(self, qvf_path: Path) -> None:
        """Extract from a .qvf file using QVFExtractor."""
        try:
            # Support both package and script execution contexts.
            from qlik_export.qvf_extractor import QVFExtractor
        except ImportError:
            try:
                from qvf_extractor import QVFExtractor
            except ImportError:
                logger.error("QVFExtractor not available — install qvf_extractor module")
                raise

        extractor = QVFExtractor(str(qvf_path))
        try:
            if hasattr(extractor, "extract"):
                qvf_data = extractor.extract()
            elif hasattr(extractor, "extract_all"):
                qvf_data = extractor.extract_all()
            else:
                raise AttributeError("QVFExtractor has neither 'extract' nor 'extract_all'")
        except zipfile.BadZipFile as exc:
            # Some samples are mislabeled as .qvf but contain JSON payloads.
            # Only use JSON fallback when the content actually looks like JSON.
            if self._looks_like_json_payload(qvf_path):
                logger.warning("QVF is not a ZIP archive (%s) — trying JSON fallback", exc)
                self._extract_from_json(qvf_path)
                return

            try:
                qvf_data = self._extract_from_binary_qvf_export(qvf_path)
                logger.warning(
                    "QVF is not a ZIP archive (%s) — decoded as a binary Qlik export",
                    exc,
                )
            except ValueError:
                raise ValueError(
                    f"Invalid QVF file '{qvf_path}': file is not a ZIP archive and does not contain JSON. "
                    "Provide a valid .qvf export or a .json Qlik export file."
                ) from exc

        # Normalize known QVFExtractor key variants to orchestrator schema.
        if isinstance(qvf_data, dict):
            if "loadScript" in qvf_data and "loadscript" not in qvf_data:
                qvf_data["loadscript"] = qvf_data.get("loadScript", "")
            if "dataModel" in qvf_data and "data_model" not in qvf_data:
                qvf_data["data_model"] = qvf_data.get("dataModel", {})

        # Map QVFExtractor output to intermediate schema
        self._data = {
            "app_metadata": self._build_app_metadata(qvf_data, qvf_path),
            "datasources": self._build_datasources(qvf_data),
            "dimensions": self._build_dimensions(qvf_data),
            "measures": self._build_measures(qvf_data),
            "visualizations": self._build_visualizations(qvf_data),
            "sheets": self._build_sheets(qvf_data),
            "variables": self._build_variables(qvf_data),
            "loadscript": self._build_loadscript(qvf_data),
            "associations": self._build_associations(qvf_data),
            "bookmarks": self._build_bookmarks(qvf_data),
            "master_items": self._build_master_items(qvf_data),
        }

    def _extract_from_binary_qvf_export(self, qvf_path: Path) -> Dict[str, Any]:
        """Decode Qlik binary app exports that embed compressed JSON records."""
        raw_bytes = qvf_path.read_bytes()
        if b"qvapp_" not in raw_bytes:
            raise ValueError("Not a recognized Qlik binary export")

        payloads = self._collect_embedded_json_payloads(raw_bytes)
        if not payloads:
            raise ValueError("No embedded JSON payloads found in Qlik binary export")

        qvf_data: Dict[str, Any] = {
            "metadata": {},
            "loadScript": "",
            "dimensions": [],
            "measures": [],
            "sheets": [],
            "visualizations": [],
            "dataModel": {},
            "variables": [],
        }
        qvf_types_found = set()
        master_measures: List[Dict[str, Any]] = []
        master_dimensions: List[Dict[str, Any]] = []

        for payload in payloads:
            if not isinstance(payload, dict):
                continue

            if "qTitle" in payload and not payload.get("qMetaData"):
                qvf_data["metadata"] = {
                    "qTitle": payload.get("qTitle", ""),
                    "qDescription": payload.get("description", ""),
                    "modifiedDate": payload.get("qLastReloadTime", ""),
                    "qSavedInProductVersion": payload.get("qSavedInProductVersion", ""),
                }
                qvf_types_found.add("metadata")
                continue

            if "qScript" in payload:
                qvf_data["loadScript"] = payload.get("qScript", "")
                qvf_types_found.add("script")
                continue

            q_type = (
                payload.get("qMetaData", {}).get("qType")
                or payload.get("qRoot", {}).get("qProperty", {}).get("qInfo", {}).get("qType")
                or payload.get("qInfo", {}).get("qType")
                or payload.get("qId")
            )
            if q_type == "LoadModel":
                qvf_data["dataModel"] = self._normalize_binary_load_model(payload)
                qvf_types_found.add("loadmodel")
                continue

            if q_type == "sheet":
                sheet, visuals = self._normalize_binary_sheet(payload)
                qvf_data["sheets"].append(sheet)
                qvf_data["visualizations"].extend(visuals)
                qvf_types_found.add("sheet")
                continue

            # Master measure (library item) — carries a reusable DAX-convertible
            # expression that would otherwise be lost.
            if q_type == "measure" and "qMeasure" in payload:
                m = self._normalize_binary_master_measure(payload)
                if m:
                    master_measures.append(m)
                    qvf_types_found.add("master_measure")
                continue

            # Master dimension (library item)
            if q_type == "dimension" and "qDim" in payload:
                d = self._normalize_binary_master_dimension(payload)
                if d:
                    master_dimensions.append(d)
                    qvf_types_found.add("master_dimension")
                continue

            if q_type and str(q_type).endswith("variablelist"):
                qvf_data["variables"].extend(self._normalize_binary_variable_list(payload))
                qvf_types_found.add("variables")

        if not qvf_types_found.intersection(
            {"metadata", "script", "sheet", "loadmodel", "variables",
             "master_measure", "master_dimension"}
        ):
            raise ValueError("No recognized Qlik objects found in binary export")

        # Merge master items with those inferred from visualizations
        # (master items take precedence — they carry real expressions/labels).
        self._resolve_binary_visual_library_items(
            qvf_data["visualizations"],
            master_dimensions,
            master_measures,
        )
        inferred_dims = self._collect_binary_dimensions(qvf_data["visualizations"])
        inferred_meas = self._collect_binary_measures(qvf_data["visualizations"])
        qvf_data["dimensions"] = self._merge_binary_items(master_dimensions, inferred_dims, key="field")
        qvf_data["measures"] = self._merge_binary_items(master_measures, inferred_meas, key="name")
        return qvf_data

    @staticmethod
    def _normalize_binary_master_measure(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract a master measure from a decoded binary payload."""
        q_meas = payload.get("qMeasure", {})
        meta = payload.get("qMetaDef", {})
        info = payload.get("qInfo", {})
        title = meta.get("title") or q_meas.get("qLabel") or ""
        expr = q_meas.get("qDef", "")
        if not title and not expr:
            return None
        return {
            "id": info.get("qId", ""),
            "name": str(title) if title else str(expr),
            "expression": str(expr),
            "label": str(q_meas.get("qLabel") or title),
            "description": meta.get("description", ""),
            "formatString": q_meas.get("qNumFormat", {}).get("qFmt", ""),
        }

    @staticmethod
    def _normalize_binary_master_dimension(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract a master dimension from a decoded binary payload."""
        q_dim = payload.get("qDim", {})
        meta = payload.get("qMetaDef", {})
        info = payload.get("qInfo", {})
        field_defs = q_dim.get("qFieldDefs", []) or []
        field_labels = q_dim.get("qFieldLabels", []) or []
        field = field_defs[0] if field_defs else ""
        if not isinstance(field, str):
            field = str(field)
        title = meta.get("title") or q_dim.get("qAlias") or (field_labels[0] if field_labels else field)
        if not field and not title:
            return None
        return {
            "id": info.get("qId", ""),
            "name": str(title) if title else field,
            "field": field,
            "label": str(field_labels[0]) if field_labels else str(title),
            "description": meta.get("description", ""),
            "grouping": q_dim.get("qGrouping", "N"),
            "fields": [str(f) for f in field_defs],
        }

    @staticmethod
    def _merge_binary_items(primary: List[Dict[str, Any]],
                            secondary: List[Dict[str, Any]],
                            key: str) -> List[Dict[str, Any]]:
        """Merge primary (master) items with secondary (inferred), dedup by key."""
        merged: List[Dict[str, Any]] = []
        seen = set()
        for item in list(primary) + list(secondary):
            k = str(item.get(key, "")).lower()
            if not k or k in seen:
                continue
            seen.add(k)
            merged.append(item)
        return merged

    @staticmethod
    def _resolve_binary_visual_library_items(
        visualizations: List[Dict[str, Any]],
        master_dimensions: List[Dict[str, Any]],
        master_measures: List[Dict[str, Any]],
    ) -> None:
        """Hydrate empty hypercube slots that reference Qlik library items."""
        dimensions_by_id = {
            item.get("id"): item for item in master_dimensions if item.get("id")
        }
        measures_by_id = {
            item.get("id"): item for item in master_measures if item.get("id")
        }

        for visual in visualizations:
            for dimension in visual.get("dimensions", []):
                master = dimensions_by_id.get(dimension.get("libraryId"))
                if master and not dimension.get("field"):
                    field = master.get("field", "")
                    if isinstance(field, str) and field.lstrip().startswith("="):
                        expression = field.lstrip()[1:].strip()
                        field = (
                            expression
                            if re.fullmatch(r"(?:\[[^\]]+\]|[^\W\d]\w*)", expression)
                            else master.get("name") or master.get("label", "")
                        )
                        field = field.strip("[]")
                    dimension.update({
                        "field": field,
                        "name": field,
                        "label": master.get("label") or master.get("name", ""),
                    })

            for measure in visual.get("measures", []):
                master = measures_by_id.get(measure.get("libraryId"))
                if master and not measure.get("expression"):
                    measure.update({
                        "name": master.get("name", ""),
                        "label": master.get("label") or master.get("name", ""),
                        "expression": master.get("expression", ""),
                    })

    @staticmethod
    def _collect_embedded_json_payloads(raw_bytes: bytes) -> List[Any]:
        """Extract decompressible JSON payloads from a binary Qlik export."""
        payloads: List[Any] = []
        seen_offsets = set()
        signatures = (b"\x78\x9c", b"\x78\x01", b"\x78\xda", b"\x1f\x8b")

        for sig in signatures:
            start = 0
            while True:
                idx = raw_bytes.find(sig, start)
                if idx < 0:
                    break
                start = idx + 1
                if idx in seen_offsets:
                    continue
                seen_offsets.add(idx)

                try:
                    if sig == b"\x1f\x8b":
                        data = zlib.decompress(raw_bytes[idx:], 31)
                    else:
                        data = zlib.decompress(raw_bytes[idx:])
                except (zlib.error, OverflowError, MemoryError):
                    continue

                # Guard against decompression bombs (max 256 MB)
                if len(data) > 256 * 1024 * 1024:
                    continue

                text = data.decode("utf-8", errors="ignore").rstrip("\x00").strip()
                if not text.startswith(("{", "[")):
                    continue
                try:
                    payloads.append(json.loads(text))
                except json.JSONDecodeError:
                    continue

        return payloads

    @staticmethod
    def _normalize_binary_load_model(payload: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize a decoded LoadModel payload into extractor-friendly data."""
        qprop = payload.get("qRoot", {}).get("qProperty", {})
        tables = []
        for table in qprop.get("tables", []):
            fields = []
            for field in table.get("fields", []):
                fields.append({
                    "qName": field.get("name", field.get("qName", "")),
                    "qType": field.get("type", field.get("qType", "text")),
                })
            tables.append({
                "qName": table.get("name", table.get("qName", "")),
                "qFields": fields,
                "type": table.get("type", table.get("connectionType", "unknown")),
            })

        associations = qprop.get("associations", [])
        if isinstance(associations, dict):
            associations = associations.get("qAssociations", []) or []

        return {
            "tables": tables,
            "associations": associations,
        }

    def _normalize_binary_sheet(self, payload: Dict[str, Any]):
        """Normalize a decoded sheet payload into sheet + visual objects."""
        qroot = payload.get("qRoot", {})
        qprop = qroot.get("qProperty", {})
        children = qroot.get("qChildren", [])
        child_map = {}
        for child in children:
            child_prop = child.get("qProperty", {})
            child_id = child_prop.get("qInfo", {}).get("qId")
            if child_id:
                child_map[child_id] = child

        sheet_id = qprop.get("qInfo", {}).get("qId", "")
        sheet = {
            "id": sheet_id,
            "title": qprop.get("qMetaDef", {}).get("title", ""),
            "description": qprop.get("qMetaDef", {}).get("description", ""),
            "rank": qprop.get("rank", 0),
            "cells": [],
            "layout": {
                "columns": qprop.get("columns"),
                "rows": qprop.get("rows"),
                "gridResolution": qprop.get("gridResolution"),
            },
        }
        visuals = []

        for idx, cell in enumerate(qprop.get("cells", [])):
            vis_id = cell.get("name", cell.get("id", f"{sheet_id}_vis_{idx}"))
            child_node = child_map.get(vis_id, {})
            child_prop = child_node.get("qProperty", {})
            dimensions = self._extract_binary_hypercube_dimensions(child_prop)
            if not dimensions:
                dimensions = self._extract_binary_list_dimensions(child_node)
            measures = self._extract_binary_hypercube_measures(child_prop)
            title = (
                child_prop.get("title")
                or child_prop.get("qMetaDef", {}).get("title")
                or child_prop.get("qHyperCubeDef", {}).get("qTitle", {}).get("qv", "")
                or cell.get("title", "")
            )
            settings = child_prop if child_prop else cell.get("properties", {})
            position = cell.get("position", cell.get("bounds", {}))
            normalized_cell = {
                "name": vis_id,
                "id": vis_id,
                "type": cell.get("type", child_prop.get("qInfo", {}).get("qType", "unknown")),
                "title": title,
                "bounds": cell.get("bounds", {}),
                "position": position,
                "dimensions": dimensions,
                "measures": measures,
                "properties": settings,
            }
            sheet["cells"].append(normalized_cell)
            visuals.append({
                "id": vis_id,
                "type": normalized_cell["type"],
                "title": title,
                "sheetId": sheet_id,
                "dimensions": dimensions,
                "measures": measures,
                "settings": settings,
                "position": position,
            })

        return sheet, visuals

    @staticmethod
    def _extract_binary_hypercube_dimensions(child_prop: Dict[str, Any]) -> List[Dict[str, Any]]:
        dims = []
        hypercube = child_prop.get("qHyperCubeDef", {})
        for dim in hypercube.get("qDimensions", []):
            qdef = dim.get("qDef", {})
            fields = qdef.get("qFieldDefs", [])
            labels = qdef.get("qFieldLabels", [])
            field = fields[0] if fields else ""
            label = labels[0] if labels else field
            dims.append({
                "field": field,
                "name": field,
                "label": label,
                "libraryId": dim.get("qLibraryId", ""),
            })
        return dims

    @staticmethod
    def _extract_binary_list_dimensions(child_node: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Collect listbox fields nested under a filterpane object."""
        dimensions = []
        for nested in child_node.get("qChildren", []):
            prop = nested.get("qProperty", {})
            qdef = prop.get("qListObjectDef", {}).get("qDef", {})
            fields = qdef.get("qFieldDefs", []) or []
            labels = qdef.get("qFieldLabels", []) or []
            for index, field in enumerate(fields):
                if not field:
                    continue
                label = labels[index] if index < len(labels) else field
                dimensions.append({
                    "field": field,
                    "name": field,
                    "label": label,
                    "libraryId": "",
                })
            dimensions.extend(
                ExtractionOrchestrator._extract_binary_list_dimensions(nested)
            )
        return dimensions

    @staticmethod
    def _extract_binary_hypercube_measures(child_prop: Dict[str, Any]) -> List[Dict[str, Any]]:
        measures = []
        hypercube = child_prop.get("qHyperCubeDef", {})
        for idx, measure in enumerate(hypercube.get("qMeasures", [])):
            qdef = measure.get("qDef", {})
            expression = qdef.get("qDef", "")
            label = qdef.get("qLabel") or qdef.get("qLabelExpression") or child_prop.get("title") or f"Measure {idx + 1}"
            measures.append({
                "name": label,
                "label": label,
                "expression": expression,
                "libraryId": measure.get("qLibraryId", ""),
            })
        return measures

    @staticmethod
    def _normalize_binary_variable_list(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        variables = []
        for entry in payload.get("qEntryList", []):
            props = entry.get("qProperties", {})
            variables.append({
                "qName": props.get("qName", ""),
                "qDefinition": props.get("qDefinition", ""),
                "qComment": props.get("qComment", ""),
                "qIsScriptCreated": props.get("qIsScriptCreated", False),
            })
        return variables

    @staticmethod
    def _collect_binary_dimensions(visualizations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        dims = []
        seen = set()
        for vis in visualizations:
            for dim in vis.get("dimensions", []):
                field = dim.get("field", "")
                if not isinstance(field, str):
                    field = str(field)
                if not field or field in seen:
                    continue
                seen.add(field)
                label = dim.get("label", field)
                if not isinstance(label, str):
                    label = field
                dims.append({
                    "id": field,
                    "name": label or field,
                    "field": field,
                    "label": label or field,
                    "fields": [field],
                })
        return dims

    @staticmethod
    def _collect_binary_measures(visualizations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        measures = []
        seen = set()
        for vis in visualizations:
            for measure in vis.get("measures", []):
                raw_name = measure.get("name", "")
                raw_expr = measure.get("expression", "")
                # Coerce to string — some Qlik exports embed dicts/lists here
                name = str(raw_name) if not isinstance(raw_name, str) else raw_name
                expr = str(raw_expr) if not isinstance(raw_expr, str) else raw_expr
                key = (name, expr)
                if not key[0] and not key[1]:
                    continue
                if key in seen:
                    continue
                seen.add(key)
                label = measure.get("label", "")
                if not isinstance(label, str):
                    label = name
                measures.append({
                    "id": name,
                    "name": name,
                    "expression": expr,
                    "label": label or name,
                })
        return measures

    def _extract_from_json(self, json_path: Path) -> None:
        """Extract from a Qlik Sense JSON export."""
        try:
            with open(json_path, "rb") as f:
                raw_bytes = f.read()

            text = self._decode_json_text(raw_bytes, json_path)
            raw = json.loads(text)
        except UnicodeDecodeError as exc:
            raise ValueError(
                f"Invalid JSON export '{json_path}': file is not valid UTF-8/UTF-16/UTF-32 JSON text. "
                "Use a proper JSON export or a valid .qvf file."
            ) from exc
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Invalid JSON export '{json_path}': {exc.msg} at line {exc.lineno}, column {exc.colno}."
            ) from exc

        # Handle various JSON export formats
        if isinstance(raw, dict):
            self._extract_from_json_dict(raw, json_path)
        elif isinstance(raw, list):
            # List of objects — try to detect format
            self._data = self._default_intermediate()
            self._data["app_metadata"] = {
                "name": json_path.stem,
                "source_file": str(json_path),
                "extracted_at": datetime.now().isoformat(),
            }
            logger.warning("JSON appears to be a list; partial extraction only")
        else:
            raise ValueError("Unexpected JSON structure")

    def _extract_from_json_dict(self, raw: Dict, json_path: Path) -> None:
        """Parse a dict-formatted Qlik JSON export."""
        # Direct intermediate format (all 11 keys present)
        if any(k in raw for k in ("datasources", "measures", "dimensions", "sheets")):
            self._data = self._default_intermediate()
            for key in self._data:
                if key in raw:
                    self._data[key] = raw[key]
            if "app_metadata" not in raw:
                self._data["app_metadata"] = {
                    "name": raw.get("name", raw.get("qTitle", json_path.stem)),
                    "description": raw.get("description", raw.get("qDescription", "")),
                    "source_file": str(json_path),
                    "extracted_at": datetime.now().isoformat(),
                }
            else:
                # Preserve explicit metadata but ensure resolver-critical fields
                # are available for relative-path handling (e.g., Binary source).
                if not isinstance(self._data["app_metadata"], dict):
                    self._data["app_metadata"] = {}
                self._data["app_metadata"].setdefault("source_file", str(json_path))
                self._data["app_metadata"].setdefault("extracted_at", datetime.now().isoformat())
            # Fallback: if no datasources but 'tables' key exists, use it
            if not self._data.get("datasources") and "tables" in raw:
                tables = raw["tables"]
                # Filter out placeholder entries with no fields
                useful = [t for t in tables
                          if t.get("name", "Unknown") != "Unknown" or t.get("fields")]
                if useful:
                    self._data["datasources"] = useful
            # Handle camelCase loadScript → loadscript dict
            if not self._data.get("loadscript", {}).get("script") and "loadScript" in raw:
                ls = raw["loadScript"]
                if isinstance(ls, str):
                    self._data["loadscript"] = {"script": ls}
                elif isinstance(ls, dict):
                    self._data["loadscript"] = ls
            # Pull master dimensions/measures from Qlik 'properties' lists
            # (qDimensionList / qMeasureList) when not already provided as
            # top-level keys. Without this the visual binding inference has
            # no catalog to match against and every visual is rendered empty.
            self._merge_property_master_items(raw)
            # Auto-extract visualizations from sheet cells when not explicitly provided
            if not self._data.get("visualizations"):
                self._data["visualizations"] = self._extract_visuals_from_sheets(
                    self._data.get("sheets", [])
                )
            return

        # Qlik Sense Engine API export format
        if "qHyperCubeDef" in raw or "qAppLayout" in raw:
            self._data = self._parse_engine_api_export(raw, json_path)
            return

        # Flat metadata format
        self._data = self._default_intermediate()
        self._data["app_metadata"] = {
            "name": raw.get("name", raw.get("qTitle", json_path.stem)),
            "description": raw.get("description", raw.get("qDescription", "")),
            "author": raw.get("author", raw.get("modifiedByUserName", "")),
            "source_file": str(json_path),
            "extracted_at": datetime.now().isoformat(),
        }

        # Try extracting tables from properties
        if "tables" in raw:
            self._data["datasources"] = raw["tables"]
        if "fields" in raw:
            self._data["dimensions"] = [
                {"name": f.get("name", f.get("qName", "")),
                 "field": f.get("name", f.get("qName", "")),
                 "label": f.get("label", f.get("qName", ""))}
                for f in raw["fields"]
            ]

    @staticmethod
    def _looks_like_json_payload(path: Path, sample_size: int = 2048) -> bool:
        """Return True when the file starts like a JSON object/array payload."""
        try:
            with open(path, "rb") as f:
                sample = f.read(sample_size)
        except OSError:
            return False

        if not sample:
            return False

        # Fast-path for UTF-8 (+ BOM) payloads.
        probe = sample
        if probe.startswith(b"\xef\xbb\xbf"):
            probe = probe[3:]
        probe = probe.lstrip()
        if probe.startswith(b"{") or probe.startswith(b"["):
            return True

        # Also accept UTF-16/UTF-32 BOM-encoded JSON payloads.
        for bom, encoding in (
            (b"\xff\xfe\x00\x00", "utf-32"),
            (b"\x00\x00\xfe\xff", "utf-32"),
            (b"\xff\xfe", "utf-16"),
            (b"\xfe\xff", "utf-16"),
        ):
            if sample.startswith(bom):
                try:
                    text = sample.decode(encoding)
                except UnicodeDecodeError:
                    return False
                text = text.lstrip()
                return text.startswith("{") or text.startswith("[")

        return False

    @staticmethod
    def _decode_json_text(raw_bytes: bytes, json_path: Path) -> str:
        """Decode JSON text with BOM-aware UTF-8/16/32 handling."""
        if not raw_bytes:
            raise ValueError(f"Invalid JSON export '{json_path}': file is empty.")

        if raw_bytes.startswith((b"\xff\xfe\x00\x00", b"\x00\x00\xfe\xff")):
            return raw_bytes.decode("utf-32")
        if raw_bytes.startswith((b"\xff\xfe", b"\xfe\xff")):
            return raw_bytes.decode("utf-16")
        if raw_bytes.startswith(b"\xef\xbb\xbf"):
            return raw_bytes.decode("utf-8-sig")
        return raw_bytes.decode("utf-8")

    # ─────────────────────────────────────────────────────────────
    # Builders — QVF data → intermediate schema
    # ─────────────────────────────────────────────────────────────

    def _build_app_metadata(self, qvf: Dict, path: Path) -> Dict:
        meta = qvf.get("metadata", qvf.get("app_metadata", {}))
        return {
            "name": meta.get("name", meta.get("qTitle", path.stem)),
            "description": meta.get("description", meta.get("qDescription", "")),
            "author": meta.get("author", meta.get("modifiedByUserName", "")),
            "created_date": meta.get("createdDate", ""),
            "modified_date": meta.get("modifiedDate", ""),
            "source_file": str(path),
            "extracted_at": datetime.now().isoformat(),
            "qlik_app_id": meta.get("qAppId", meta.get("id", "")),
        }

    def _build_datasources(self, qvf: Dict) -> List[Dict]:
        sources = qvf.get("datasources", qvf.get("data_model", {}).get("tables", []))
        if isinstance(sources, dict):
            sources = sources.get("tables", [])
        result = []
        for src in sources:
            ds = {
                "tableName": src.get("tableName", src.get("qName", src.get("name", ""))),
                "connectionType": src.get("connectionType", src.get("type", "unknown")),
                "connection": src.get("connection", {}),
                "columns": [],
            }
            columns = src.get("columns", src.get("fields", src.get("qFields", [])))
            for col in columns:
                ds["columns"].append({
                    "name": col.get("name", col.get("qName", "")),
                    "dataType": col.get("dataType", col.get("qType", "text")),
                    "label": col.get("label", col.get("qName", "")),
                })
            result.append(ds)
        return result

    def _build_dimensions(self, qvf: Dict) -> List[Dict]:
        dims = qvf.get("dimensions", [])
        result = []
        for dim in dims:
            d = {
                "id": dim.get("id", dim.get("qInfo", {}).get("qId", "")),
                "name": dim.get("name", dim.get("qMetaDef", {}).get("title", "")),
                "field": dim.get("field", ""),
                "label": dim.get("label", dim.get("qMetaDef", {}).get("title", "")),
                "description": dim.get("description", dim.get("qMetaDef", {}).get("description", "")),
                "grouping": dim.get("grouping", "single"),
                "fields": dim.get("fields", []),
            }
            # Extract field from expression if not explicit
            if not d["field"] and "expression" in dim:
                d["field"] = dim["expression"]
            if not d["field"]:
                fd = dim.get("qDim", {}).get("qFieldDefs", [])
                if fd:
                    d["field"] = fd[0] if isinstance(fd[0], str) else fd[0].get("qDef", "")
            result.append(d)
        return result

    def _build_measures(self, qvf: Dict) -> List[Dict]:
        measures = qvf.get("measures", [])
        result = []
        for meas in measures:
            m = {
                "id": meas.get("id", meas.get("qInfo", {}).get("qId", "")),
                "name": meas.get("name", meas.get("qMetaDef", {}).get("title", "")),
                "expression": meas.get("expression", ""),
                "label": meas.get("label", meas.get("qMetaDef", {}).get("title", "")),
                "description": meas.get("description", meas.get("qMetaDef", {}).get("description", "")),
                "formatString": meas.get("formatString", meas.get("qNumFormat", {}).get("qFmt", "")),
            }
            if not m["expression"]:
                m["expression"] = meas.get("qMeasure", {}).get("qDef", "")
            result.append(m)
        return result

    def _build_visualizations(self, qvf: Dict) -> List[Dict]:
        visuals = qvf.get("visualizations", [])
        result = []
        for vis in visuals:
            v = {
                "id": vis.get("id", ""),
                "type": vis.get("type", vis.get("qType", "unknown")),
                "title": vis.get("title", ""),
                "sheetId": vis.get("sheetId", ""),
                "dimensions": vis.get("dimensions", []),
                "measures": vis.get("measures", []),
                "settings": vis.get("settings", {}),
                "position": vis.get("position", {}),
            }
            result.append(v)
        return result

    # ─────────────────────────────────────────────────────────────
    # Master-item extraction + visual binding inference
    # ─────────────────────────────────────────────────────────────

    def _merge_property_master_items(self, raw: Dict) -> None:
        """Populate dimensions/measures from Qlik ``properties`` lists.

        Qlik Sense exports keep master dimensions and measures under
        ``properties.qDimensionList.qItems`` and
        ``properties.qMeasureList.qItems``.  The direct-format branch only
        copies top-level keys, so these catalogs would otherwise be lost,
        leaving visuals with nothing to bind to.
        """
        props = raw.get("properties", {})
        if not isinstance(props, dict):
            return

        if not self._data.get("dimensions"):
            dim_items = props.get("qDimensionList", {}).get("qItems", [])
            dims: List[Dict] = []
            for it in dim_items:
                q_dim = it.get("qDim", {})
                field_defs = q_dim.get("qFieldDefs", [])
                field_labels = q_dim.get("qFieldLabels", [])
                meta = it.get("qMeta", {})
                dims.append({
                    "id": it.get("qInfo", {}).get("qId", ""),
                    "name": meta.get("title", field_defs[0] if field_defs else ""),
                    "field": field_defs[0] if field_defs else "",
                    "label": meta.get("title", field_labels[0] if field_labels else ""),
                    "description": meta.get("description", ""),
                    "grouping": q_dim.get("qGrouping", "N"),
                    "fields": list(field_defs),
                })
            if dims:
                self._data["dimensions"] = dims

        if not self._data.get("measures"):
            meas_items = props.get("qMeasureList", {}).get("qItems", [])
            meas: List[Dict] = []
            for it in meas_items:
                q_meas = it.get("qMeasure", {})
                meta = it.get("qMeta", {})
                title = meta.get("title", "")
                meas.append({
                    "id": it.get("qInfo", {}).get("qId", ""),
                    "name": title,
                    "expression": q_meas.get("qDef", ""),
                    "label": title,
                    "description": meta.get("description", ""),
                    "formatString": q_meas.get("qNumFormat", {}).get("qFmt", ""),
                })
            if meas:
                self._data["measures"] = meas

    def _build_measure_catalog(self) -> List[Dict]:
        """Return measures available for binding inference (title + expression)."""
        catalog: List[Dict] = []
        seen = set()
        for src in (self._data.get("measures", []),
                    self._data.get("master_items", [])):
            for item in src:
                if item.get("type") and item.get("type") != "measure":
                    continue
                title = item.get("name") or item.get("title") or ""
                expr = item.get("expression", "")
                if not title or title.lower() in seen:
                    continue
                seen.add(title.lower())
                catalog.append({"name": title, "expression": expr})
        return catalog

    def _build_dimension_catalog(self) -> List[Dict]:
        """Return dimensions available for binding inference (title + field)."""
        catalog: List[Dict] = []
        seen = set()
        for src in (self._data.get("dimensions", []),
                    self._data.get("master_items", [])):
            for item in src:
                if item.get("type") and item.get("type") != "dimension":
                    continue
                title = item.get("name") or item.get("title") or ""
                field = item.get("field") or ""
                if not field and item.get("fields"):
                    field = item["fields"][0]
                if not field:
                    continue
                key = (title.lower(), field.lower())
                if key in seen:
                    continue
                seen.add(key)
                catalog.append({"name": title or field, "field": field})
        return catalog

    @staticmethod
    def _infer_visual_bindings(title: str, vtype: str,
                               measure_catalog: List[Dict],
                               dim_catalog: List[Dict]):
        """Infer dimension/measure bindings for a visual from its title.

        Heuristics:
          * Match measure / dimension catalog names that appear in the title.
          * Honour an explicit ``X by Y`` pattern (Y = dimension).
          * Apply sensible per-visual-type defaults so every visual is bound
            to at least one field and renders populated in Power BI.
        Returns ``(dimensions, measures)`` lists in the cell-binding shape.
        """
        title_l = (title or "").lower()
        vtype_l = (vtype or "").lower()

        # ── Measure matches (longest catalog name first) ──────────
        matched_measures: List[Dict] = []
        for m in sorted(measure_catalog, key=lambda x: -len(x["name"])):
            if m["name"] and m["name"].lower() in title_l:
                if all(m["name"] != mm["name"] for mm in matched_measures):
                    matched_measures.append(m)

        # ── Dimension matches, preferring the "... by <dim>" tail ──
        matched_dims: List[Dict] = []
        by_tail = ""
        for sep in (" by ", " per ", " across "):
            if sep in title_l:
                by_tail = title_l.split(sep, 1)[1]
                break
        ordered_dims = sorted(dim_catalog, key=lambda x: -len(x["name"]))
        if by_tail:
            for d in ordered_dims:
                if d["name"].lower() in by_tail or d["field"].lower() in by_tail:
                    matched_dims.append(d)
                    break
        if not matched_dims:
            for d in ordered_dims:
                if d["name"].lower() in title_l or d["field"].lower() in title_l:
                    matched_dims.append(d)
                    break

        # ── Per-type role requirements ────────────────────────────
        value_only = vtype_l in ("kpi", "card", "gauge", "text-image", "textbox")
        needs_two_measures = vtype_l in ("scatter", "scatterplot") or \
            any(s in title_l for s in (" vs ", " versus ", " & "))
        is_table = vtype_l in ("table", "pivot-table", "pivottable", "tableex")

        def _default_measure():
            return measure_catalog[0] if measure_catalog else None

        def _default_dimension():
            # Prefer a date dimension for trend/line visuals.
            if vtype_l in ("linechart", "line", "combo", "area") or "trend" in title_l:
                for d in dim_catalog:
                    if "date" in d["field"].lower() or "date" in d["name"].lower():
                        return d
            return dim_catalog[0] if dim_catalog else None

        out_measures: List[Dict] = []
        out_dims: List[Dict] = []

        # Measures
        chosen_measures = matched_measures[:]
        if not chosen_measures and _default_measure():
            chosen_measures = [_default_measure()]
        if needs_two_measures and len(chosen_measures) < 2:
            for m in measure_catalog:
                if all(m["name"] != cm["name"] for cm in chosen_measures):
                    chosen_measures.append(m)
                    if len(chosen_measures) >= 2:
                        break
        for m in chosen_measures:
            out_measures.append({
                "name": m["name"],
                "label": m["name"],
                "expression": m.get("expression", ""),
            })

        # Dimensions (skip for value-only visuals like cards/KPIs)
        if not value_only:
            chosen_dims = matched_dims[:]
            if not chosen_dims and _default_dimension():
                chosen_dims = [_default_dimension()]
            if is_table:
                # Tables benefit from a couple of extra dimensions.
                for d in dim_catalog:
                    if len(chosen_dims) >= 3:
                        break
                    if all(d["field"] != cd["field"] for cd in chosen_dims):
                        chosen_dims.append(d)
            for d in chosen_dims:
                out_dims.append({
                    "field": d["field"],
                    "name": d["field"],
                    "label": d["name"],
                })

        return out_dims, out_measures

    def _build_sheets(self, qvf: Dict) -> List[Dict]:
        sheets = qvf.get("sheets", [])
        result = []
        for sheet in sheets:
            s = {
                "id": sheet.get("id", sheet.get("qInfo", {}).get("qId", "")),
                "title": sheet.get("title", sheet.get("qMeta", {}).get("title", "")),
                "description": sheet.get("description", ""),
                "rank": sheet.get("rank", 0),
                "cells": sheet.get("cells", []),
                "layout": sheet.get("layout", {}),
            }
            result.append(s)
        return result

    def _extract_visuals_from_sheets(self, sheets: List[Dict]) -> List[Dict]:
        """Extract visualization objects from sheet cells.

        When the JSON export has no top-level 'visualizations' key, each
        sheet may carry its visuals inline as 'cells'.  This method walks
        through every sheet, pulls the cells out, and returns a flat list
        of visualization dicts compatible with the downstream pipeline.
        """
        visuals: List[Dict] = []
        # Build catalogs for binding inference (title → field / expression).
        measure_catalog = self._build_measure_catalog()
        dim_catalog = self._build_dimension_catalog()
        for idx, sheet in enumerate(sheets):
            # Resolve sheet id from multiple possible locations
            sheet_id = (
                sheet.get("id")
                or sheet.get("qProperty", {}).get("qInfo", {}).get("qId")
                or sheet.get("qInfo", {}).get("qId")
                or f"sheet_{idx}"
            )
            # Resolve sheet title for fallback naming
            sheet_title = (
                sheet.get("title")
                or sheet.get("qProperty", {}).get("qMetaDef", {}).get("title")
                or sheet.get("qMeta", {}).get("title")
                or f"Sheet {idx + 1}"
            )
            # Normalize the sheet dict so downstream code can use .get("id")
            if "id" not in sheet:
                sheet["id"] = sheet_id
            if "title" not in sheet:
                sheet["title"] = sheet_title

            cells = sheet.get("cells", [])
            for cell_idx, cell in enumerate(cells):
                vis_id = cell.get("name", cell.get("id", f"{sheet_id}_vis_{cell_idx}"))
                dimensions = cell.get("dimensions", [])
                measures = cell.get("measures", [])
                # Infer field bindings from the visual title when the cell
                # carries none, so the generated Power BI visual is populated
                # instead of showing "Select or add data to populate".
                if not dimensions and not measures:
                    dimensions, measures = self._infer_visual_bindings(
                        cell.get("title", ""),
                        cell.get("type", "unknown"),
                        measure_catalog,
                        dim_catalog,
                    )
                vis = {
                    "id": vis_id,
                    "type": cell.get("type", "unknown"),
                    "title": cell.get("title", ""),
                    "sheetId": sheet_id,
                    "dimensions": dimensions,
                    "measures": measures,
                    "settings": cell.get("properties", cell.get("settings", {})),
                    "position": cell.get("position", cell.get("bounds", {})),
                }
                visuals.append(vis)
        return visuals

    def _build_variables(self, qvf: Dict) -> List[Dict]:
        variables = qvf.get("variables", [])
        result = []
        for var in variables:
            v = {
                "name": var.get("name", var.get("qName", "")),
                "definition": var.get("definition", var.get("qDefinition", "")),
                "comment": var.get("comment", var.get("qComment", "")),
                "isScript": var.get("isScript", var.get("qIsScriptCreated", False)),
            }
            result.append(v)
        return result

    def _build_loadscript(self, qvf: Dict) -> Dict:
        script = qvf.get("loadscript", qvf.get("script", ""))
        if isinstance(script, str):
            return {"script": script}
        return script if isinstance(script, dict) else {"script": str(script)}

    def _build_associations(self, qvf: Dict) -> List[Dict]:
        assocs = qvf.get("associations", qvf.get("data_model", {}).get("associations", []))
        if isinstance(assocs, dict):
            assocs = assocs.get("associations", [])
        result = []
        for assoc in assocs:
            a = {
                "table1": assoc.get("table1", assoc.get("qTable1", "")),
                "field1": assoc.get("field1", assoc.get("qField1", "")),
                "table2": assoc.get("table2", assoc.get("qTable2", "")),
                "field2": assoc.get("field2", assoc.get("qField2", "")),
            }
            result.append(a)
        return result

    def _build_bookmarks(self, qvf: Dict) -> List[Dict]:
        bookmarks = qvf.get("bookmarks", [])
        result = []
        for bm in bookmarks:
            b = {
                "id": bm.get("id", bm.get("qInfo", {}).get("qId", "")),
                "name": bm.get("name", bm.get("qMetaDef", {}).get("title", "")),
                "description": bm.get("description", ""),
                "selections": bm.get("selections", bm.get("qBookmark", {}).get("qStateData", [])),
            }
            result.append(b)
        return result

    def _build_master_items(self, qvf: Dict) -> List[Dict]:
        items = qvf.get("master_items", [])
        if not items:
            # Combine dimensions and measures as master items
            dims = qvf.get("dimensions", [])
            measures = qvf.get("measures", [])
            for d in dims:
                items.append({
                    "id": d.get("id", ""),
                    "name": d.get("name", ""),
                    "type": "dimension",
                    "definition": d.get("field", d.get("expression", "")),
                })
            for m in measures:
                items.append({
                    "id": m.get("id", ""),
                    "name": m.get("name", ""),
                    "type": "measure",
                    "definition": m.get("expression", ""),
                })
        return items

    # ─────────────────────────────────────────────────────────────
    # Engine API format parser
    # ─────────────────────────────────────────────────────────────

    def _parse_engine_api_export(self, raw: Dict, path: Path) -> Dict[str, Any]:
        """Parse Qlik Sense Engine API export format."""
        data = self._default_intermediate()
        layout = raw.get("qAppLayout", {})
        data["app_metadata"] = {
            "name": layout.get("qTitle", path.stem),
            "description": layout.get("qDescription", ""),
            "author": layout.get("qLastReloadTime", ""),
            "source_file": str(path),
            "extracted_at": datetime.now().isoformat(),
        }

        # Extract hypercube if present
        hc = raw.get("qHyperCubeDef", {})
        if hc:
            dims = hc.get("qDimensions", [])
            data["dimensions"] = [
                {
                    "id": d.get("qLibraryId", ""),
                    "name": d.get("qDef", {}).get("qFieldDefs", [""])[0],
                    "field": d.get("qDef", {}).get("qFieldDefs", [""])[0],
                    "label": d.get("qDef", {}).get("qFieldLabels", [""])[0] if d.get("qDef", {}).get("qFieldLabels") else "",
                }
                for d in dims
            ]
            meas = hc.get("qMeasures", [])
            data["measures"] = [
                {
                    "id": m.get("qLibraryId", ""),
                    "name": m.get("qDef", {}).get("qLabel", ""),
                    "expression": m.get("qDef", {}).get("qDef", ""),
                    "label": m.get("qDef", {}).get("qLabel", ""),
                }
                for m in meas
            ]

        return data

    # ─────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    def _default_intermediate() -> Dict[str, Any]:
        """Return empty default intermediate structure."""
        return {
            "app_metadata": {},
            "datasources": [],
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

    # ─────────────────────────────────────────────────────────────
    # Load script → datasource enrichment
    # ─────────────────────────────────────────────────────────────

    def _enrich_from_loadscript(
        self,
        resolve_binary: bool = True,
        binary_source: Optional[str] = None,
        binary_source_dirs: Optional[List[str]] = None,
    ) -> None:
        """Parse the Qlik load script and enrich datasources with M queries.

        Uses ``QlikScriptToPowerQueryConverter`` to convert LOAD statements
        into Power Query M, then attaches M queries to matching datasource
        entries (by table name).  New tables discovered in the script that
        don't already have a datasource entry are appended.
        """
        script = self._data.get("loadscript", {}).get("script", "")
        if not script or not script.strip():
            return

        # Restitution-only apps often use `Binary` to import the data model
        # from another app. If local datasources are empty, try to resolve the
        # referenced source file and hydrate datasources from it.
        if resolve_binary and not self._data.get("datasources"):
            self._hydrate_datasources_from_binary_source(
                script,
                binary_source=binary_source,
                binary_source_dirs=binary_source_dirs,
            )

        try:
            from qlik_export.qlik_script_converter import (
                QlikScriptToPowerQueryConverter,
            )
        except ImportError:
            try:
                from qlik_script_converter import QlikScriptToPowerQueryConverter
            except ImportError:
                logger.debug("qlik_script_converter not available — skipping load script enrichment")
                return

        try:
            pq_output = QlikScriptToPowerQueryConverter.convert_qlik_script_to_powerquery(script)
        except Exception as exc:
            logger.warning("Load script conversion failed: %s", exc)
            return

        if not pq_output or not pq_output.strip():
            return

        # Parse the converter output into named query blocks.
        # The output follows the pattern:
        #   // Query: TableName
        #   let ... in ... FinalStep
        #
        # We split on "// Query:" lines to extract per-table M queries.
        query_blocks: Dict[str, str] = {}
        current_name: Optional[str] = None
        current_lines: List[str] = []

        for line in pq_output.split("\n"):
            if line.startswith("// Query: "):
                # Flush previous block
                if current_name and current_lines:
                    query_blocks[current_name] = "\n".join(current_lines).strip()
                current_name = line[len("// Query: "):].strip()
                current_lines = []
            elif line.startswith("// ") and not current_name:
                # Skip comment lines before any query block
                continue
            else:
                current_lines.append(line)

        # Flush last block
        if current_name and current_lines:
            query_blocks[current_name] = "\n".join(current_lines).strip()

        if not query_blocks:
            logger.debug("No named query blocks extracted from load script")
            return

        # Build a lookup of existing datasources by table name
        ds_list: List[Dict] = self._data.get("datasources", [])
        ds_by_name: Dict[str, Dict] = {}
        for ds in ds_list:
            name = ds.get("tableName", ds.get("name", ""))
            if name:
                ds_by_name[name] = ds

        enriched = 0
        added = 0
        for table_name, m_query in query_blocks.items():
            if not m_query:
                continue
            if table_name in ds_by_name:
                # Enrich existing datasource with M query
                ds_by_name[table_name]["m_query"] = m_query
                enriched += 1
            else:
                # New table discovered from load script — add minimal entry
                # Try to extract column names from M query SelectColumns patterns
                columns = self._extract_columns_from_m_query(m_query)
                new_ds = {
                    "tableName": table_name,
                    "connectionType": "loadscript",
                    "connection": {"type": "loadscript"},
                    "columns": columns,
                    "m_query": m_query,
                }
                ds_list.append(new_ds)
                added += 1

        if enriched or added:
            logger.info(
                "Load script enrichment: %d datasources enriched, %d new tables added",
                enriched, added,
            )

    @staticmethod
    def _extract_binary_load_target(script: str) -> Optional[str]:
        """Return the first `Binary ...;` target path found in a load script."""
        import re as _re

        if not script:
            return None

        # Keep first Binary statement only; this mirrors the load order.
        match = _re.search(r"(?im)^\s*binary\s+(.+?)\s*;", script)
        if not match:
            return None

        token = match.group(1).strip()
        if (token.startswith('"') and token.endswith('"')) or (
            token.startswith("'") and token.endswith("'")
        ):
            token = token[1:-1].strip()
        return token or None

    @staticmethod
    def _resolve_binary_source_candidates(
        binary_target: str,
        source_file: Optional[str],
        preferred_source: Optional[str] = None,
        search_dirs: Optional[List[str]] = None,
    ) -> List[Path]:
        """Resolve likely filesystem candidates for a Binary source reference."""
        candidates: List[Path] = []
        if not binary_target:
            return candidates

        target = binary_target.strip()
        source_dir = Path(source_file).resolve().parent if source_file else Path.cwd()

        def _push(path_obj: Path):
            try:
                resolved = path_obj.resolve()
            except Exception:
                return
            if resolved not in candidates:
                candidates.append(resolved)

        if preferred_source:
            _push(Path(preferred_source))

        for extra_dir in (search_dirs or []):
            if not extra_dir:
                continue
            try:
                extra_path = Path(extra_dir).resolve()
            except Exception:
                continue
            if extra_path.is_dir():
                _push(extra_path / Path(target).name)

        # Qlik lib:// references cannot be resolved directly without connection
        # metadata. Probe the UUID/name first, then sibling QVF applications so
        # Binary-backed presentation apps work with a single migration command.
        if target.lower().startswith("lib://"):
            probe_name = Path(target.replace("\\", "/")).name
            if probe_name:
                for extra_dir in (search_dirs or []):
                    try:
                        extra_path = Path(extra_dir).resolve()
                    except Exception:
                        continue
                    if extra_path.is_dir():
                        for found in extra_path.rglob(probe_name):
                            _push(found)
                        for found in extra_path.rglob(f"{probe_name}.qvf"):
                            _push(found)
                        for found in sorted(extra_path.glob("*.qvf")):
                            _push(found)
                for found in source_dir.rglob(probe_name):
                    _push(found)
                for found in source_dir.rglob(f"{probe_name}.qvf"):
                    _push(found)
                for found in sorted(source_dir.glob("*.qvf")):
                    _push(found)
            return candidates

        path_target = Path(target)
        if path_target.is_absolute():
            _push(path_target)
            return candidates

        _push(source_dir / path_target)
        _push(Path.cwd() / path_target)
        return candidates

    @staticmethod
    def _score_binary_source_data(
        target_data: Dict[str, Any],
        source_data: Dict[str, Any],
    ) -> tuple[int, int]:
        """Score a Binary source by referenced-field overlap and model size."""
        import re as _re

        target_payload = {
            key: target_data.get(key, [])
            for key in ("dimensions", "measures", "visualizations", "master_items")
        }
        target_text = json.dumps(target_payload, ensure_ascii=False, default=str)
        target_fields = {
            name.strip().casefold()
            for name in _re.findall(r"\[([^]]+)\]", target_text)
            if name.strip()
        }

        def _collect_explicit_fields(value: Any) -> None:
            if isinstance(value, dict):
                for key, item in value.items():
                    if (
                        key.casefold() in {"field", "fieldname", "sourcecolumn"}
                        and isinstance(item, str)
                        and item.strip()
                    ):
                        target_fields.add(item.strip().casefold())
                    _collect_explicit_fields(item)
            elif isinstance(value, list):
                for item in value:
                    _collect_explicit_fields(item)

        _collect_explicit_fields(target_payload)

        source_fields = set()
        datasources = source_data.get("datasources", []) or []
        for datasource in datasources:
            if not isinstance(datasource, dict):
                continue
            for column in datasource.get("columns", []) or []:
                if isinstance(column, dict):
                    name = (
                        column.get("name")
                        or column.get("field")
                        or column.get("sourceColumn")
                    )
                else:
                    name = column
                if name:
                    source_fields.add(str(name).strip().casefold())

        return len(target_fields & source_fields), len(datasources)

    def _hydrate_datasources_from_binary_source(
        self,
        script: str,
        binary_source: Optional[str] = None,
        binary_source_dirs: Optional[List[str]] = None,
    ) -> bool:
        """Hydrate datasources from the app referenced by a Qlik Binary load."""
        binary_target = self._extract_binary_load_target(script)
        if not binary_target:
            return False

        source_file = self._data.get("app_metadata", {}).get("source_file")
        candidates = self._resolve_binary_source_candidates(
            binary_target,
            source_file,
            preferred_source=binary_source,
            search_dirs=binary_source_dirs,
        )
        if not candidates:
            logger.warning(
                "Binary load detected (%s) but no local source file could be resolved. "
                "Use --binary-source <file> or --binary-source-dir <dir>.",
                binary_target,
            )
            return False

        source_path = Path(source_file).resolve() if source_file else None
        preferred_path = Path(binary_source).resolve() if binary_source else None
        resolved_sources = []
        for candidate in candidates:
            if source_path and candidate == source_path:
                continue
            if not candidate.exists() or not candidate.is_file():
                continue

            try:
                with tempfile.TemporaryDirectory(prefix="qlik_binary_") as temp_dir:
                    nested = ExtractionOrchestrator(output_dir=temp_dir)
                    # Avoid infinite loops for cyclic Binary references.
                    nested.extract(str(candidate), resolve_binary=False)
            except Exception as exc:
                logger.warning("Binary source extraction failed for %s: %s", candidate, exc)
                continue

            nested_ds = nested._data.get("datasources", [])
            if not nested_ds:
                continue

            overlap, datasource_count = self._score_binary_source_data(
                self._data,
                nested._data,
            )
            resolved_sources.append((
                candidate == preferred_path,
                overlap,
                datasource_count,
                candidate,
                nested_ds,
                nested._data.get("associations", []),
            ))

        if resolved_sources:
            (
                _, overlap, datasource_count, candidate, nested_ds,
                nested_associations,
            ) = max(resolved_sources, key=lambda item: item[:3])
            self._data["datasources"] = nested_ds
            if not self._data.get("associations") and nested_associations:
                self._data["associations"] = nested_associations

            logger.warning(
                "Binary load source resolved automatically (%s): imported %d "
                "datasources with %d referenced-field matches",
                candidate,
                datasource_count,
                overlap,
            )
            return True

        logger.warning(
            "Binary load detected (%s) but no datasource-bearing source app was found. "
            "Use --binary-source <file> or --binary-source-dir <dir>.",
            binary_target,
        )
        return False

    @staticmethod
    def _extract_columns_from_m_query(m_query: str) -> List[Dict]:
        """Extract column names from a Power Query M snippet.

        Looks for Table.SelectColumns(..., {"Col1", "Col2"}) or
        #table({"Col1", "Col2"}, ...) patterns.
        """
        import re as _re
        columns: List[Dict] = []
        seen: set = set()

        def _clean_column_name(name: str) -> str:
            text = (name or "").strip()
            if not text:
                return ""
            # Drop accidental table-label fragments leaked from statement splits,
            # e.g. `ID_CHGT_TECH;\n\n[QUAL_QUESTPAT_CLOT_GENERIQUE]:`.
            text = _re.sub(r';\s*\[.*?\]:\s*$', '', text, flags=_re.DOTALL)
            text = _re.sub(r'\s*\[.*?\]:\s*$', '', text, flags=_re.DOTALL)
            text = text.split(';', 1)[0].strip()
            return text

        # Prefer Table.SelectColumns(..., {"Col1", "Col2"}) pattern first
        sc_match = _re.search(
            r'Table\.SelectColumns\s*\([^,]+,\s*\{([^{}]+)\}', m_query
        )
        if sc_match:
            names = _re.findall(r'"([^"]+)"', sc_match.group(1))
            for name in names:
                name = _clean_column_name(name)
                if not name:
                    continue
                if name not in seen:
                    seen.add(name)
                    columns.append({"name": name, "dataType": "string"})
            if columns:
                return columns

        # Fallback: find the last {..."Col1", "Col2"...} list that looks
        # like a column list (only quoted strings separated by commas).
        best_names: List[str] = []
        for m in _re.finditer(r'\{([^{}]+)\}', m_query):
            inner = m.group(1)
            names = _re.findall(r'"([^"]+)"', inner)
            # Ensure this is a pure quoted-string list (no brackets/equals)
            if len(names) >= 2 and '[' not in inner and '=' not in inner:
                best_names = names
        for name in best_names:
            name = _clean_column_name(name)
            if not name:
                continue
            if name not in seen:
                seen.add(name)
                columns.append({"name": name, "dataType": "string"})
        return columns

    def get_extraction_summary(self) -> Dict[str, Any]:
        """Return a summary of what was extracted."""
        return {
            "app_name": self._data.get("app_metadata", {}).get("name", "Unknown"),
            "datasources_count": len(self._data.get("datasources", [])),
            "dimensions_count": len(self._data.get("dimensions", [])),
            "measures_count": len(self._data.get("measures", [])),
            "visualizations_count": len(self._data.get("visualizations", [])),
            "sheets_count": len(self._data.get("sheets", [])),
            "variables_count": len(self._data.get("variables", [])),
            "associations_count": len(self._data.get("associations", [])),
            "bookmarks_count": len(self._data.get("bookmarks", [])),
            "master_items_count": len(self._data.get("master_items", [])),
            "has_loadscript": bool(self._data.get("loadscript", {}).get("script", "")),
        }
