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

    def extract(self, input_path: str) -> Dict[str, Any]:
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
            from .qvf_extractor import QVFExtractor
        except ImportError:
            logger.error("QVFExtractor not available — install qvf_extractor module")
            raise

        extractor = QVFExtractor(str(qvf_path))
        qvf_data = extractor.extract()

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

    def _extract_from_json(self, json_path: Path) -> None:
        """Extract from a Qlik Sense JSON export."""
        with open(json_path, "r", encoding="utf-8") as f:
            raw = json.load(f)

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
                vis = {
                    "id": vis_id,
                    "type": cell.get("type", "unknown"),
                    "title": cell.get("title", ""),
                    "sheetId": sheet_id,
                    "dimensions": cell.get("dimensions", []),
                    "measures": cell.get("measures", []),
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
