"""
Lineage Map Generator — Source-to-target provenance tracking

Generates a ``lineage_map.json`` that traces every object from the Qlik source
to its Power BI target, enabling full migration auditability.

Tracked lineage types:
  - Datasource → Table
  - Measure → DAX Measure
  - Dimension → Column / Hierarchy
  - Variable → Parameter Table / Measure
  - Visualization → Visual
  - Sheet → Report Page
  - Association → Relationship
  - Bookmark → PBI Bookmark
"""

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class LineageEntry:
    """A single lineage record mapping source → target."""

    def __init__(self, source_type: str, source_name: str,
                 target_type: str, target_name: str,
                 source_expression: str = "",
                 target_expression: str = "",
                 status: str = "exact",
                 notes: str = ""):
        self.source_type = source_type
        self.source_name = source_name
        self.target_type = target_type
        self.target_name = target_name
        self.source_expression = source_expression
        self.target_expression = target_expression
        self.status = status  # exact | approximate | unsupported
        self.notes = notes

    def to_dict(self) -> Dict[str, str]:
        d: Dict[str, str] = {
            "source_type": self.source_type,
            "source_name": self.source_name,
            "target_type": self.target_type,
            "target_name": self.target_name,
            "status": self.status,
        }
        if self.source_expression:
            d["source_expression"] = self.source_expression
        if self.target_expression:
            d["target_expression"] = self.target_expression
        if self.notes:
            d["notes"] = self.notes
        return d


class LineageMap:
    """Collects and exports lineage entries for a migration."""

    def __init__(self, app_name: str = ""):
        self.app_name = app_name
        self.entries: List[LineageEntry] = []
        self.created_at = datetime.now().isoformat()

    def add(self, source_type: str, source_name: str,
            target_type: str, target_name: str, **kwargs: Any) -> None:
        self.entries.append(LineageEntry(
            source_type=source_type,
            source_name=source_name,
            target_type=target_type,
            target_name=target_name,
            **kwargs,
        ))

    def add_datasource(self, ds_name: str, table_name: str, **kw: Any) -> None:
        self.add("datasource", ds_name, "table", table_name, **kw)

    def add_measure(self, qlik_name: str, dax_name: str,
                    qlik_expr: str = "", dax_expr: str = "", **kw: Any) -> None:
        self.add("measure", qlik_name, "dax_measure", dax_name,
                 source_expression=qlik_expr, target_expression=dax_expr, **kw)

    def add_dimension(self, dim_name: str, target_name: str,
                      target_type: str = "column", **kw: Any) -> None:
        self.add("dimension", dim_name, target_type, target_name, **kw)

    def add_variable(self, var_name: str, target_name: str,
                     target_type: str = "parameter", **kw: Any) -> None:
        self.add("variable", var_name, target_type, target_name, **kw)

    def add_visual(self, viz_name: str, pbi_visual: str, **kw: Any) -> None:
        self.add("visualization", viz_name, "visual", pbi_visual, **kw)

    def add_sheet(self, sheet_name: str, page_name: str, **kw: Any) -> None:
        self.add("sheet", sheet_name, "report_page", page_name, **kw)

    def add_association(self, assoc_desc: str, rel_desc: str, **kw: Any) -> None:
        self.add("association", assoc_desc, "relationship", rel_desc, **kw)

    def add_bookmark(self, bm_name: str, pbi_bm: str, **kw: Any) -> None:
        self.add("bookmark", bm_name, "pbi_bookmark", pbi_bm, **kw)

    def to_dict(self) -> Dict[str, Any]:
        by_type: Dict[str, List[Dict[str, str]]] = {}
        for e in self.entries:
            by_type.setdefault(e.source_type, []).append(e.to_dict())

        return {
            "app_name": self.app_name,
            "created_at": self.created_at,
            "total_entries": len(self.entries),
            "by_source_type": {
                stype: len(items) for stype, items in by_type.items()
            },
            "entries": [e.to_dict() for e in self.entries],
        }

    def save(self, output_dir: str) -> str:
        os.makedirs(output_dir, exist_ok=True)
        path = os.path.join(output_dir, "lineage_map.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
        logger.info("Lineage map saved: %s (%d entries)", path, len(self.entries))
        return path


def build_lineage_map(app_name: str, qlik_data: Dict[str, Any],
                      calc_map: Optional[Dict[str, str]] = None) -> LineageMap:
    """Build a lineage map from extracted Qlik data and generated DAX.

    Args:
        app_name: Name of the Qlik application.
        qlik_data: Dict with keys like 'datasources', 'measures', 'dimensions',
                   'visualizations', 'sheets', 'associations', 'variables', 'bookmarks'.
        calc_map: Optional mapping of calculation name → DAX expression
                  (from generated TMDL files).

    Returns:
        Populated LineageMap instance.
    """
    lm = LineageMap(app_name=app_name)
    calc_map = calc_map or {}

    # Datasources → Tables
    for ds in qlik_data.get("datasources", []):
        name = ds.get("name", ds.get("tableName", ""))
        if name:
            lm.add_datasource(name, name)

    # Measures → DAX Measures
    for m in qlik_data.get("measures", []):
        name = m.get("name", m.get("label", ""))
        expr = m.get("expression", "")
        dax = calc_map.get(name, "")
        if name:
            lm.add_measure(name, name, qlik_expr=expr, dax_expr=dax)

    # Dimensions → Columns / Hierarchies
    for d in qlik_data.get("dimensions", []):
        name = d.get("name", d.get("label", ""))
        field = d.get("field", "")
        is_drill = d.get("type") == "drill-group" or d.get("isDrillDown", False)
        if name:
            target_type = "hierarchy" if is_drill else "column"
            lm.add_dimension(name, name, target_type=target_type,
                             source_expression=field)

    # Variables → Parameters / Measures
    for v in qlik_data.get("variables", []):
        name = v.get("name", "")
        if name and not name.startswith("$"):
            lm.add_variable(name, name)

    # Visualizations → Visuals
    for viz in qlik_data.get("visualizations", []):
        title = viz.get("title", viz.get("name", ""))
        viz_type = viz.get("type", "")
        if title:
            lm.add_visual(title, f"{viz_type} → visual", source_expression=viz_type)

    # Sheets → Report Pages
    for sheet in qlik_data.get("sheets", []):
        name = sheet.get("title", sheet.get("name", ""))
        if name:
            lm.add_sheet(name, name)

    # Associations → Relationships
    for assoc in qlik_data.get("associations", []):
        table1 = assoc.get("table1", "")
        table2 = assoc.get("table2", "")
        field = assoc.get("field", assoc.get("key", ""))
        if table1 and table2:
            desc = f"{table1}.{field} → {table2}.{field}"
            lm.add_association(desc, desc)

    # Bookmarks → PBI Bookmarks
    for bm in qlik_data.get("bookmarks", []):
        name = bm.get("name", bm.get("title", ""))
        if name:
            lm.add_bookmark(name, name)

    return lm
