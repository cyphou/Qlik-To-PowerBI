"""
Générateur de projets Power BI (PBI Project / TMDL) – format 4.0

Produit une structure de dossiers .pbip entièrement compatible avec
Power BI Desktop (Developer Mode), Fabric Git Integration et CI/CD.

Structure PBI Project 4.0
=========================
  .gitignore
  <Nom>.pbip
  <Nom>.SemanticModel/
      .platform
      definition.pbism               # version 4.0+
      diagramLayout.json
      definition/
          database.tmdl
          model.tmdl                  # inclut « ref table » pour chaque table
          tables/
              <Table>.tmdl
          relationships.tmdl
          expressions.tmdl
  <Nom>.Report/
      .platform
      definition.pbir                 # version 4.0
      definition/                     # PBIR format (pas PBIR-Legacy)
          version.json
          report.json
          pages/
              pages.json
              <PageName>/
                  page.json
                  visuals/
                      <visualId>/
                          visual.json
"""

import json
import logging
import re
import uuid
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# ── JSON Schema URLs (Microsoft published schemas) ────────────────
_SCHEMA_PBIP = "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json"
_SCHEMA_PBISM = "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json"
_SCHEMA_PBIR = "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json"
_SCHEMA_PLATFORM = "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json"
_SCHEMA_VERSION = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/versionMetadata/1.0.0/schema.json"
_SCHEMA_REPORT = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/3.1.0/schema.json"
_SCHEMA_PAGES = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.0.0/schema.json"
_SCHEMA_PAGE = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.0.0/schema.json"
_SCHEMA_VISUAL = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.5.0/schema.json"


def _new_guid() -> str:
    """Generate a new GUID string."""
    return str(uuid.uuid4())


def _short_id(seed: str = "") -> str:
    """Generate a 20-char hex id (matches PBI Desktop convention)."""
    return hashlib.sha1((seed or _new_guid()).encode()).hexdigest()[:20]


def _sanitize_name(name: str) -> str:
    """Sanitize a name for use as a filename."""
    return "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in name).strip()


# ── Visual type mapping ───────────────────────────────────────────
_VISUAL_TYPE_MAP = {
    # Qlik → PBI mapping
    "barchart": "clusteredBarChart",
    "linechart": "lineChart",
    "piechart": "pieChart",
    "kpi": "card",
    "table": "tableEx",
    "scatter": "scatterChart",
    "treemap": "treemap",
    "gauge": "gauge",
    "pivot": "pivotTable",
    # PBI pass-through (already correct types)
    "clusteredbarchart": "clusteredBarChart",
    "linechart": "lineChart",
    "piechart": "pieChart",
    "card": "card",
    "tableex": "tableEx",
    "scatterchart": "scatterChart",
    "pivottable": "pivotTable",
    "columnchart": "columnChart",
    "clusteredcolumnchart": "clusteredColumnChart",
    "donutchart": "donutChart",
    "funnel": "funnel",
    "map": "map",
    "slicer": "slicer",
    "multirowcard": "multiRowCard",
}


# ── Data role definitions per visual type ─────────────────────────
# Each key maps to (dimension_roles, measure_roles) where:
#   dimension_roles = list of role names that accept columns/dimensions
#   measure_roles   = list of role names that accept measures/aggregations
_VISUAL_DATA_ROLES: Dict[str, tuple] = {
    "card":                       ([], ["Fields"]),
    "multiRowCard":               ([], ["Values"]),
    "clusteredBarChart":          (["Category"], ["Y"]),
    "clusteredColumnChart":       (["Category"], ["Y"]),
    "lineChart":                  (["Category"], ["Y"]),
    "pieChart":                   (["Category"], ["Y"]),
    "donutChart":                 (["Category"], ["Y"]),
    "waterfallChart":             (["Category"], ["Y"]),
    "funnel":                     (["Category"], ["Y"]),
    "gauge":                      ([], ["Y"]),
    "treemap":                    (["Group"], ["Values"]),
    "scatterChart":               (["Category"], ["X", "Y"]),
    "tableEx":                    (["Values"], ["Values"]),   # tableEx uses one role
    "pivotTable":                 (["Rows"], ["Values"]),
    "slicer":                     (["Values"], []),
    "lineStackedColumnComboChart": (["Category"], ["Y", "Y2"]),
    "map":                        (["Category"], ["Size"]),
}


# ── Aggregation function mapping (Qlik expression → PBI function ID) ─

_AGG_FUNC_MAP = {
    "sum": 1,
    "min": 2,
    "max": 3,
    "count": 4,
    "countnonnull": 5,
    "avg": 6,
    "average": 6,
}


def _build_column_table_map(bim_model: Optional[Dict]) -> Dict[str, str]:
    """Build {column_name: table_name} lookup from a BIM model dict."""
    col_map: Dict[str, str] = {}
    if not bim_model:
        return col_map
    model = bim_model.get("model", bim_model)
    for table_def in model.get("tables", []):
        tname = table_def.get("name", "")
        for col in table_def.get("columns", []):
            cname = col.get("name", "")
            if cname and tname:
                col_map[cname] = tname
        for meas in table_def.get("measures", []):
            mname = meas.get("name", "")
            if mname and tname:
                col_map[mname] = tname
    return col_map


def _parse_qlik_expression(expr: str) -> tuple:
    """Parse a Qlik expression like 'Sum(Amount)' → ('sum', 'Amount')."""
    m = re.match(r'(\w+)\((\w+)\)', expr.strip()) if expr else None
    if m:
        return m.group(1).lower(), m.group(2)
    return "", expr.strip() if expr else ""


def _make_column_projection(
    entity: str, prop: str, query_ref: str, active: bool = False,
    display_name: Optional[str] = None,
) -> Dict:
    """Create a PBIR column field projection."""
    proj: Dict[str, Any] = {
        "field": {
            "Column": {
                "Expression": {"SourceRef": {"Entity": entity}},
                "Property": prop,
            },
        },
        "queryRef": query_ref,
        "nativeQueryRef": prop,
    }
    if active:
        proj["active"] = True
    if display_name:
        proj["displayName"] = display_name
    return proj


def _make_aggregation_projection(
    entity: str, prop: str, func_id: int,
    query_ref: str, display_name: Optional[str] = None,
) -> Dict:
    """Create a PBIR aggregation field projection."""
    proj: Dict[str, Any] = {
        "field": {
            "Aggregation": {
                "Expression": {
                    "Column": {
                        "Expression": {"SourceRef": {"Entity": entity}},
                        "Property": prop,
                    },
                },
                "Function": func_id,
            },
        },
        "queryRef": query_ref,
        "nativeQueryRef": prop,
    }
    if display_name:
        proj["displayName"] = display_name
    return proj


def _make_measure_projection(
    entity: str, measure_name: str,
    query_ref: str, display_name: Optional[str] = None,
) -> Dict:
    """Create a PBIR named-measure field projection."""
    proj: Dict[str, Any] = {
        "field": {
            "Measure": {
                "Expression": {"SourceRef": {"Entity": entity}},
                "Property": measure_name,
            },
        },
        "queryRef": query_ref,
        "nativeQueryRef": measure_name,
    }
    if display_name:
        proj["displayName"] = display_name
    return proj


def _build_measure_lookup(bim_model: Optional[Dict]) -> Dict[str, tuple]:
    """Build {measure_name: (table_name, dax_expression)} from BIM model."""
    lookup: Dict[str, tuple] = {}
    if not bim_model:
        return lookup
    model = bim_model.get("model", bim_model)
    for table_def in model.get("tables", []):
        tname = table_def.get("name", "")
        for meas in table_def.get("measures", []):
            mname = meas.get("name", "")
            if mname and tname:
                lookup[mname] = (tname, meas.get("expression", ""))
    return lookup


class TMDLGenerator:
    """
    Génère un projet Power BI au format PBI Project 4.0 / TMDL.

    Produit une structure de dossiers compatible avec Power BI Desktop
    (Developer Mode), Fabric Git Integration et les pipelines CI/CD.
    """

    def __init__(self):
        """Initialiser le générateur TMDL."""
        self.report_logical_id = _new_guid()
        self.semantic_model_logical_id = _new_guid()

    # ==================================================================
    # Public entry point
    # ==================================================================
    def create_pbi_project(
        self,
        output_dir: Path,
        report_name: str,
        bim_model: Optional[Dict] = None,
        power_query_script: Optional[str] = None,
        visualizations: Optional[List[Dict]] = None,
        dimensions: Optional[List[Dict]] = None,
        measures: Optional[List[Dict]] = None,
        sheets: Optional[List[Dict]] = None,
        bookmarks: Optional[List[Dict]] = None,
        theme: Optional[Dict] = None,
    ) -> Path:
        """
        Créer un projet Power BI complet au format 4.0.

        Returns:
            Chemin du fichier .pbip créé
        """
        logger.info(f"Création du projet PBI 4.0: {output_dir / report_name}")

        output_dir = Path(output_dir)
        safe_name = _sanitize_name(report_name)

        # ── Root paths ────────────────────────────────────────────
        project_root = output_dir
        project_root.mkdir(parents=True, exist_ok=True)

        sm_dir = project_root / f"{safe_name}.SemanticModel"
        sm_def_dir = sm_dir / "definition"
        sm_tables_dir = sm_def_dir / "tables"
        rpt_dir = project_root / f"{safe_name}.Report"
        rpt_def_dir = rpt_dir / "definition"
        rpt_pages_dir = rpt_def_dir / "pages"

        for d in [sm_dir, sm_def_dir, sm_tables_dir,
                  rpt_dir, rpt_def_dir, rpt_pages_dir]:
            d.mkdir(parents=True, exist_ok=True)

        # ── .gitignore ────────────────────────────────────────────
        self._write_gitignore(project_root / ".gitignore")

        # ── .pbip root file ───────────────────────────────────────
        pbip_path = project_root / f"{safe_name}.pbip"
        self._write_pbip(pbip_path, safe_name)

        # ── Semantic Model ────────────────────────────────────────
        self._write_pbism(sm_dir / "definition.pbism")
        self._write_platform(sm_dir / ".platform", "SemanticModel", report_name)
        self._write_diagram_layout(sm_dir / "diagramLayout.json")

        # Collect table names for model.tmdl ref table entries
        table_names: List[str] = []

        if bim_model:
            table_names = self._write_tmdl_from_bim(sm_def_dir, sm_tables_dir, bim_model)
        else:
            table_names = self._write_default_tmdl(sm_def_dir, sm_tables_dir, power_query_script)

        # ── Report (PBIR format) ──────────────────────────────────
        self._write_pbir(rpt_dir / "definition.pbir", safe_name)
        self._write_platform(rpt_dir / ".platform", "Report", report_name)

        # Build column→table lookup for visual data bindings
        col_table_map = _build_column_table_map(bim_model)
        measure_lookup = _build_measure_lookup(bim_model)

        self._write_pbir_definition(
            rpt_def_dir, rpt_pages_dir,
            report_name, visualizations, dimensions, measures,
            col_table_map, measure_lookup,
            sheets=sheets,
            bookmarks=bookmarks,
            theme=theme,
        )

        logger.info(f"✓ Projet PBI 4.0 créé: {pbip_path}")
        return pbip_path

    # ==================================================================
    # .gitignore
    # ==================================================================
    @staticmethod
    def _write_gitignore(path: Path):
        if not path.exists():
            path.write_text(
                "**/.pbi/localSettings.json\n**/.pbi/cache.abf\n",
                encoding="utf-8",
            )

    # ==================================================================
    # .pbip root file
    # ==================================================================
    def _write_pbip(self, path: Path, name: str):
        content = {
            "$schema": _SCHEMA_PBIP,
            "version": "1.0",
            "artifacts": [
                {"report": {"path": f"{name}.Report"}}
            ],
            "settings": {
                "enableAutoRecovery": True,
            },
        }
        _write_json(path, content)

    # ==================================================================
    # Semantic Model – definition.pbism  (version 4.0)
    # ==================================================================
    @staticmethod
    def _write_pbism(path: Path):
        content = {
            "$schema": _SCHEMA_PBISM,
            "version": "4.0",
            "settings": {},
        }
        _write_json(path, content)

    # ==================================================================
    # .platform (Fabric Git Integration metadata)
    # ==================================================================
    def _write_platform(self, path: Path, item_type: str, display_name: str):
        logical_id = (self.report_logical_id
                      if item_type == "Report"
                      else self.semantic_model_logical_id)
        content = {
            "$schema": _SCHEMA_PLATFORM,
            "metadata": {
                "type": item_type,
                "displayName": display_name,
            },
            "config": {
                "version": "2.0",
                "logicalId": logical_id,
            },
        }
        _write_json(path, content)

    # ==================================================================
    # diagramLayout.json (minimal, Power BI Desktop fills it in)
    # ==================================================================
    @staticmethod
    def _write_diagram_layout(path: Path):
        content = {
            "version": "1.1.0",
            "diagrams": [],
        }
        _write_json(path, content)

    # ==================================================================
    # Report – definition.pbir  (version 4.0)
    # ==================================================================
    @staticmethod
    def _write_pbir(path: Path, name: str):
        content = {
            "$schema": _SCHEMA_PBIR,
            "version": "4.0",
            "datasetReference": {
                "byPath": {
                    "path": f"../{name}.SemanticModel",
                },
            },
        }
        _write_json(path, content)

    # ==================================================================
    # Report PBIR definition/ folder
    # ==================================================================
    def _write_pbir_definition(
        self,
        def_dir: Path,
        pages_dir: Path,
        report_name: str,
        visualizations: Optional[List[Dict]],
        dimensions: Optional[List[Dict]],
        measures: Optional[List[Dict]],
        col_table_map: Optional[Dict[str, str]] = None,
        measure_lookup: Optional[Dict[str, tuple]] = None,
        sheets: Optional[List[Dict]] = None,
        bookmarks: Optional[List[Dict]] = None,
        theme: Optional[Dict] = None,
    ):
        """Write the PBIR definition folder (version.json, report.json, pages/)."""

        # version.json
        _write_json(def_dir / "version.json", {
            "$schema": _SCHEMA_VERSION,
            "version": "2.0.0",
        })

        # ── Theme ─────────────────────────────────────────────
        theme_config = {
            "baseTheme": {
                "name": "CY24SU06",
                "reportVersionAtImport": {
                    "visual": "1.8.50",
                    "report": "2.0.50",
                    "page": "1.3.50",
                },
                "type": "SharedResources",
            },
        }
        if theme and theme.get("name"):
            theme_config["baseTheme"]["name"] = theme["name"]

        # report.json
        report_settings: Dict[str, Any] = {
            "hideVisualContainerHeader": True,
            "useStylableVisualContainerHeader": True,
            "defaultDrillFilterOtherVisuals": True,
            "allowChangeFilterTypes": True,
            "useEnhancedTooltips": True,
            "useCrossReportDrillthrough": False,
            "isPersistentUserStateDisabled": False,
        }

        report_json: Dict[str, Any] = {
            "$schema": _SCHEMA_REPORT,
            "themeCollection": theme_config,
            "settings": report_settings,
        }

        # ── Bookmarks ─────────────────────────────────────────
        if bookmarks:
            bm_list = []
            for bm in bookmarks:
                bm_entry: Dict[str, Any] = {
                    "name": _short_id(bm.get("name", "")),
                    "displayName": bm.get("name", bm.get("title", "Bookmark")),
                    "explorationState": {},
                }
                bm_list.append(bm_entry)
            if bm_list:
                report_json["bookmarks"] = bm_list

        _write_json(def_dir / "report.json", report_json)

        # ── Write custom theme if provided ─────────────────────
        if theme:
            theme_json = TMDLGenerator.generate_theme_json(theme)
            themes_dir = def_dir / "StaticResources" / "SharedResources" / "BaseThemes"
            themes_dir.mkdir(parents=True, exist_ok=True)
            _write_json(themes_dir / f"{theme.get('name', 'MigratedQlikTheme')}.json", theme_json)

        # ──────────────────────────────────────────────────────
        # Build pages: one PBI page per Qlik sheet
        # ──────────────────────────────────────────────────────
        page_infos = []
        viz_list = visualizations or []

        if sheets and len(sheets) > 0:
            # Multi-sheet: create one PBI page per Qlik sheet
            for idx, sheet in enumerate(sheets):
                sheet_id = sheet.get("id", f"sheet_{idx}")
                sheet_title = sheet.get("title", f"Page {idx + 1}")
                page_name = _sanitize_name(sheet_title).replace(" ", "") or f"Page{idx + 1}"
                # Collect visuals belonging to this sheet
                sheet_vizs = [
                    v for v in viz_list
                    if v.get("sheetId") == sheet_id
                ]
                # If no sheetId matching, distribute visuals across sheets
                if not sheet_vizs and idx == 0 and viz_list:
                    # Fallback: put all visuals on first page when IDs don't match
                    sheet_vizs = viz_list
                page_infos.append({
                    "page_name": page_name,
                    "display_name": sheet_title,
                    "visualizations": sheet_vizs,
                    "sheet_raw": sheet,
                })
        else:
            # Single page fallback
            page_infos.append({
                "page_name": "ReportSection",
                "display_name": "Page 1",
                "visualizations": viz_list,
            })

        # pages.json
        page_order = [p["page_name"] for p in page_infos]
        _write_json(pages_dir / "pages.json", {
            "$schema": _SCHEMA_PAGES,
            "pageOrder": page_order,
            "activePageName": page_order[0] if page_order else "ReportSection",
        })

        # ── Write each page ──────────────────────────────────
        for page_info in page_infos:
            page_name = page_info["page_name"]
            page_display = page_info["display_name"]
            page_vizs = page_info["visualizations"]

            page_dir = pages_dir / page_name
            page_dir.mkdir(parents=True, exist_ok=True)

            # page.json
            page_json: Dict[str, Any] = {
                "$schema": _SCHEMA_PAGE,
                "name": page_name,
                "displayName": page_display,
                "displayOption": "FitToPage",
                "height": 720,
                "width": 1280,
            }

            # Drill-through page support (Qlik navigation actions)
            sheet_raw = page_info.get("sheet_raw", {})
            if sheet_raw.get("isDrillThrough") or sheet_raw.get("drillThrough"):
                page_json["pageType"] = "DrillThrough"
                page_json["drillThrough"] = {
                    "enabled": True,
                }

            # Tooltip page support
            if sheet_raw.get("isTooltip") or sheet_raw.get("tooltip"):
                page_json["pageType"] = "Tooltip"
                page_json["tooltipEnabled"] = True
                page_json["height"] = 320
                page_json["width"] = 480

            # Background color
            bg_color = sheet_raw.get("backgroundColor", "")
            if bg_color:
                page_json["background"] = {
                    "color": {"solid": {"color": bg_color}},
                    "transparency": 0,
                }

            _write_json(page_dir / "page.json", page_json)

            # ── Visuals (no arbitrary limit) ─────────────────
            if page_vizs:
                visuals_dir = page_dir / "visuals"
                visuals_dir.mkdir(exist_ok=True)
                for i, viz in enumerate(page_vizs):
                    visual_id = _short_id(f"viz_{i}_{page_name}_{report_name}")
                    v_dir = visuals_dir / visual_id
                    v_dir.mkdir(exist_ok=True)

                    # Use per-visual dims/measures if available, else fallback
                    viz_dims = viz.get("dimensions", dimensions or [])
                    viz_meas = viz.get("measures", measures or [])

                    self._write_visual_json(
                        v_dir / "visual.json",
                        visual_id, viz, i,
                        viz_dims, viz_meas,
                        col_table_map or {},
                        measure_lookup or {},
                    )

    # ==================================================================
    # Individual visual.json (PBIR format)
    # ==================================================================
    def _write_visual_json(
        self,
        path: Path,
        visual_id: str,
        visualization: Dict,
        index: int,
        dimensions: List[Dict],
        measures: List[Dict],
        col_table_map: Dict[str, str],
        measure_lookup: Dict[str, tuple],
    ):
        col = index % 2
        row = index // 2
        x = 10 + col * 640
        y = 10 + row * 350
        width = 620
        height = 340

        raw_type = visualization.get("type", "tableEx")
        pbi_type = _VISUAL_TYPE_MAP.get(raw_type.lower(), "tableEx")

        visual_obj: Dict[str, Any] = {
            "visualType": pbi_type,
            "drillFilterOtherVisuals": True,
        }

        # tableEx / pivotTable benefit from autoSelectVisualType
        if pbi_type in ("tableEx", "pivotTable"):
            visual_obj["autoSelectVisualType"] = True

        # ── Build query.queryState projections ────────────────
        query_state = self._build_query_state(
            pbi_type, dimensions, measures, col_table_map, measure_lookup,
        )
        if query_state:
            visual_obj["query"] = {"queryState": query_state}

        content: Dict[str, Any] = {
            "$schema": _SCHEMA_VISUAL,
            "name": visual_id,
            "position": {
                "x": x, "y": y,
                "z": 1000 + index,
                "height": height, "width": width,
                "tabOrder": 1000 + index,
            },
            "visual": visual_obj,
        }

        _write_json(path, content)

    # ==================================================================
    # Build query.queryState per visual type
    # ==================================================================
    @staticmethod
    def _build_query_state(
        pbi_type: str,
        dimensions: List[Dict],
        measures: List[Dict],
        col_table_map: Dict[str, str],
        measure_lookup: Dict[str, tuple],
    ) -> Optional[Dict]:
        """Build PBIR queryState with role-based projections."""
        roles = _VISUAL_DATA_ROLES.get(pbi_type)
        if not roles:
            return None

        dim_roles, meas_roles = roles

        # ── Resolve dimension projections ─────────────────────
        dim_projections: List[Dict] = []
        for dim in dimensions:
            field_name = dim.get("field", "")
            table_name = col_table_map.get(field_name, "")
            if not table_name:
                # Try dimension name as fallback
                table_name = col_table_map.get(dim.get("name", ""), "")
            if not table_name and col_table_map:
                # Use the first available table as fallback
                table_name = next(iter(col_table_map.values()), "Table")
            if table_name and field_name:
                proj = _make_column_projection(
                    entity=table_name,
                    prop=field_name,
                    query_ref=f"{table_name}.{field_name}",
                    active=True,
                    display_name=dim.get("label") or dim.get("name"),
                )
                dim_projections.append(proj)

        # ── Resolve measure projections ───────────────────────
        meas_projections: List[Dict] = []
        for meas in measures:
            measure_label = meas.get("label") or meas.get("name", "Measure")

            # Try to find a named measure in the BIM model
            bim_info = measure_lookup.get(measure_label)
            if bim_info:
                tbl_name, _dax_expr = bim_info
                proj = _make_measure_projection(
                    entity=tbl_name,
                    measure_name=measure_label,
                    query_ref=f"{tbl_name}.{measure_label}",
                    display_name=measure_label,
                )
                meas_projections.append(proj)
                continue

            # Fallback: inline aggregation from Qlik expression
            expr = meas.get("expression", "")
            func_name, col_name = _parse_qlik_expression(expr)
            func_id = _AGG_FUNC_MAP.get(func_name, 1)  # default Sum
            table_name = col_table_map.get(col_name, "")
            if not table_name and col_table_map:
                table_name = next(iter(col_table_map.values()), "Table")
            if table_name and col_name:
                agg_name = func_name.capitalize() if func_name else "Sum"
                proj = _make_aggregation_projection(
                    entity=table_name,
                    prop=col_name,
                    func_id=func_id,
                    query_ref=f"{agg_name}({table_name}.{col_name})",
                    display_name=measure_label,
                )
                meas_projections.append(proj)

        # ── Nothing to bind? ──────────────────────────────────
        if not dim_projections and not meas_projections:
            return None

        query_state: Dict[str, Any] = {}

        # ── Special case: tableEx shares a single "Values" role ──
        if pbi_type == "tableEx":
            all_projs = dim_projections + meas_projections
            if all_projs:
                query_state["Values"] = {"projections": all_projs}
            return query_state if query_state else None

        # ── Assign dimensions to dimension roles ──────────────
        for role_name in dim_roles:
            if dim_projections:
                query_state[role_name] = {"projections": list(dim_projections)}

        # ── Assign measures to measure roles ──────────────────
        for i, role_name in enumerate(meas_roles):
            if i < len(meas_projections):
                # Distribute measures across roles (e.g., X and Y for scatter)
                query_state[role_name] = {"projections": [meas_projections[i]]}
            elif meas_projections:
                # If fewer measures than roles, use the first one
                query_state[role_name] = {"projections": [meas_projections[0]]}

        return query_state if query_state else None

    # ==================================================================
    # TMDL generation from a BIM dict
    # ==================================================================
    def _write_tmdl_from_bim(
        self,
        definition_dir: Path,
        tables_dir: Path,
        bim_model: Dict,
    ) -> List[str]:
        """Generate TMDL files from a BIM model dictionary. Returns table names."""
        model = bim_model.get("model", bim_model)

        # database.tmdl
        compat = bim_model.get("compatibilityLevel", 1600)
        self._write_database_tmdl(definition_dir / "database.tmdl", compat)

        # Collect table names first
        table_names: List[str] = []
        for table_def in model.get("tables", []):
            table_names.append(table_def.get("name", "UnknownTable"))

        # model.tmdl (with ref table entries)
        culture = model.get("culture", "en-US")
        ds_version = model.get("defaultPowerBIDataSourceVersion", "powerBI_V3")
        annotations = model.get("annotations", [])
        self._write_model_tmdl(
            definition_dir / "model.tmdl",
            culture, ds_version, annotations, table_names,
        )

        # tables/*.tmdl
        for table_def in model.get("tables", []):
            table_name = table_def.get("name", "UnknownTable")
            safe_table = _sanitize_name(table_name)
            self._write_table_tmdl(tables_dir / f"{safe_table}.tmdl", table_def)

        # relationships.tmdl
        relationships = model.get("relationships", [])
        if relationships:
            self._write_relationships_tmdl(definition_dir / "relationships.tmdl", relationships)

        # expressions.tmdl
        expressions = model.get("expressions", [])
        if expressions:
            self._write_expressions_tmdl(definition_dir / "expressions.tmdl", expressions)

        # roles.tmdl (RLS - Row-Level Security)
        roles = model.get("roles", [])
        if roles:
            self._write_roles_tmdl(definition_dir / "roles.tmdl", roles)

        # perspectives.tmdl
        perspectives = model.get("perspectives", [])
        if perspectives:
            self._write_perspectives_tmdl(definition_dir / "perspectives.tmdl", perspectives)

        # cultures/*.tmdl (translations)
        cultures = model.get("cultures", [])
        if cultures:
            cultures_dir = definition_dir / "cultures"
            cultures_dir.mkdir(parents=True, exist_ok=True)
            for culture_def in cultures:
                culture_name = culture_def.get("name", "en-US")
                self._write_culture_tmdl(
                    cultures_dir / f"{culture_name}.tmdl", culture_def
                )

        return table_names

    # ==================================================================
    # Default TMDL (no BIM provided)
    # ==================================================================
    def _write_default_tmdl(
        self,
        definition_dir: Path,
        tables_dir: Path,
        power_query_script: Optional[str],
    ) -> List[str]:
        """Generate minimal TMDL when no BIM model is supplied. Returns table names."""
        self._write_database_tmdl(definition_dir / "database.tmdl", 1600)

        table_names: List[str] = []

        if power_query_script:
            table_names.append("SampleData")
            tag = _new_guid()
            table_def = {
                "name": "SampleData",
                "lineageTag": tag,
                "columns": [
                    {
                        "name": "Column1",
                        "dataType": "string",
                        "sourceColumn": "Column1",
                        "lineageTag": _new_guid(),
                        "summarizeBy": "none",
                    }
                ],
                "partitions": [
                    {
                        "name": "Partition",
                        "mode": "import",
                        "source": {
                            "type": "m",
                            "expression": power_query_script,
                        },
                    }
                ],
            }
            self._write_table_tmdl(tables_dir / "SampleData.tmdl", table_def)

        self._write_model_tmdl(
            definition_dir / "model.tmdl",
            "en-US", "powerBI_V3", [], table_names,
        )

        return table_names

    # ==================================================================
    # Individual TMDL file writers
    # ==================================================================
    @staticmethod
    def _write_database_tmdl(path: Path, compat_level: int = 1600):
        lines = [
            "database",
            f"\tcompatibilityLevel: {compat_level}",
            "",
        ]
        path.write_text("\n".join(lines), encoding="utf-8")
        logger.debug(f"  Écrit: {path.name}")

    @staticmethod
    def _write_model_tmdl(
        path: Path,
        culture: str,
        ds_version: str,
        annotations: List[Dict],
        table_names: Optional[List[str]] = None,
    ):
        lines = [
            "model Model",
            f"\tculture: {culture}",
            f"\tdefaultPowerBIDataSourceVersion: {ds_version}",
            "\tdiscourageImplicitMeasures",
        ]

        # Annotations (root-level, no tab indent)
        for ann in annotations:
            ann_name = ann.get("name", "")
            ann_value = ann.get("value", "")
            lines.append("")
            lines.append(f"annotation {_quote_tmdl(ann_name)} = {ann_value}")

        # ref table entries (root-level, no tab indent)
        if table_names:
            lines.append("")
            for tname in table_names:
                lines.append(f"ref table {_quote_tmdl(tname)}")

        lines.append("")
        path.write_text("\n".join(lines), encoding="utf-8")
        logger.debug(f"  Écrit: {path.name}")

    @staticmethod
    def _write_table_tmdl(path: Path, table_def: Dict):
        """Write a single table TMDL file."""
        name = table_def.get("name", "UnknownTable")
        lineage_tag = table_def.get("lineageTag", _new_guid())

        lines: List[str] = []
        lines.append(f"table {_quote_tmdl(name)}")
        lines.append(f"\tlineageTag: {lineage_tag}")

        # Table-level description
        description = table_def.get("description", "")
        if description:
            lines.append(f"\tdescription: {description}")

        # Table-level dataCategory (e.g., Time for calendar tables)
        if table_def.get("dataCategory"):
            lines.append(f"\tdataCategory: {table_def['dataCategory']}")

        # Table-level isHidden
        if table_def.get("isHidden"):
            lines.append("\tisHidden")

        # Columns
        for col in table_def.get("columns", []):
            lines.append("")
            col_name = col.get("name", "Col")
            data_type = col.get("dataType", "string")
            col_tag = col.get("lineageTag", _new_guid())
            source_col = col.get("sourceColumn", col_name)
            summarize = col.get("summarizeBy", "none")
            col_type = col.get("type", "")  # "calculated" for calc columns

            if col_type == "calculated":
                # Calculated column with DAX expression
                expr = col.get("expression", col_name)
                lines.append(f"\tcolumn {_quote_tmdl(col_name)} = {expr}")
            else:
                lines.append(f"\tcolumn {_quote_tmdl(col_name)}")

            lines.append(f"\t\tdataType: {data_type}")
            fmt_str = col.get("formatString", "")
            if fmt_str:
                lines.append(f"\t\tformatString: {fmt_str}")
            lines.append(f"\t\tlineageTag: {col_tag}")
            lines.append(f"\t\tsummarizeBy: {summarize}")

            # Display folder
            display_folder = col.get("displayFolder", "")
            if display_folder:
                lines.append(f"\t\tdisplayFolder: {display_folder}")

            # Description
            col_desc = col.get("description", "")
            if col_desc:
                lines.append(f"\t\tdescription: {col_desc}")

            # dataCategory for geographic columns
            data_cat = col.get("dataCategory", "")
            if data_cat:
                lines.append(f"\t\tdataCategory: {data_cat}")

            # isHidden flag
            if col.get("isHidden"):
                lines.append("\t\tisHidden")

            # sortByColumn
            sort_by = col.get("sortByColumn", "")
            if sort_by:
                lines.append(f"\t\tsortByColumn: {_quote_tmdl(sort_by)}")

            if col_type != "calculated":
                lines.append(f"\t\tsourceColumn: {source_col}")

            for ann in col.get("annotations", []):
                lines.append(f"\t\tannotation {ann.get('name', '')} = {ann.get('value', '')}")

        # Measures
        for measure in table_def.get("measures", []):
            m_name = measure.get("name", "Measure")
            m_expr = measure.get("expression", "")
            m_tag = measure.get("lineageTag", _new_guid())
            fmt = measure.get("formatString", "")

            lines.append("")
            lines.append(f"\tmeasure {_quote_tmdl(m_name)} = {m_expr}")
            lines.append(f"\t\tlineageTag: {m_tag}")
            if fmt:
                lines.append(f"\t\tformatString: {fmt}")
            # Measure display folder
            m_folder = measure.get("displayFolder", "")
            if m_folder:
                lines.append(f"\t\tdisplayFolder: {m_folder}")
            # Measure description
            m_desc = measure.get("description", "")
            if m_desc:
                lines.append(f"\t\tdescription: {m_desc}")

        # Calculation groups
        for calc_group in table_def.get("calculationGroups", []):
            cg_name = calc_group.get("name", "CalculationGroup")
            lines.append("")
            lines.append(f"\tcalculationGroup {_quote_tmdl(cg_name)}")
            for item in calc_group.get("calculationItems", []):
                item_name = item.get("name", "Item")
                item_expr = item.get("expression", "SELECTEDMEASURE()")
                lines.append(f"\t\tcalculationItem {_quote_tmdl(item_name)}")
                lines.append(f"\t\t\texpression: {item_expr}")
                if item.get("formatStringExpression"):
                    lines.append(f"\t\t\tformatStringExpression: {item['formatStringExpression']}")

        # Hierarchies
        for hierarchy in table_def.get("hierarchies", []):
            h_name = hierarchy.get("name", "Hierarchy")
            lines.append("")
            lines.append(f"\thierarchy {_quote_tmdl(h_name)}")
            # Hierarchy display folder
            if hierarchy.get("displayFolder"):
                lines.append(f"\t\tdisplayFolder: {hierarchy['displayFolder']}")
            for level in hierarchy.get("levels", []):
                l_name = level.get("name", "Level")
                l_col = level.get("column", l_name)
                # Strip any Table.Column prefix — TMDL expects just the column name
                if "." in l_col:
                    l_col = l_col.rsplit(".", 1)[-1]
                lines.append(f"\t\tlevel {_quote_tmdl(l_name)}")
                lines.append(f"\t\t\tcolumn: {_quote_tmdl(l_col)}")

        # Partitions (Power Query M expressions)
        for partition in table_def.get("partitions", []):
            p_name = partition.get("name", name)
            p_mode = partition.get("mode", "import")
            source = partition.get("source", {})

            lines.append("")
            lines.append(f"\tpartition {_quote_tmdl(p_name)} = m")
            lines.append(f"\t\tmode: {p_mode}")

            expr = source.get("expression", "")
            if expr:
                # Normalise escaped newlines to real newlines, then unescape quotes
                expr = expr.replace("\\n", "\n").replace('\\"', '"')
                lines.append("\t\tsource =")
                for expr_line in expr.split("\n"):
                    lines.append(f"\t\t\t{expr_line}")

        # Annotations at table level
        for ann in table_def.get("annotations", []):
            lines.append("")
            lines.append(f"\tannotation {_quote_tmdl(ann.get('name', ''))} = {ann.get('value', '')}")

        lines.append("")
        path.write_text("\n".join(lines), encoding="utf-8")
        logger.debug(f"  Écrit: {path.name}")

    @staticmethod
    def _write_relationships_tmdl(path: Path, relationships: List[Dict]):
        """Write relationships.tmdl."""
        # Map BIM enum values → TMDL enum values
        _CROSS_FILTER_MAP = {
            "single": "oneDirection",
            "onedirection": "oneDirection",
            "both": "bothDirections",
            "bothdirections": "bothDirections",
            "automatic": "automatic",
        }

        lines: List[str] = []
        for rel in relationships:
            rel_name = rel.get("name", _new_guid())
            from_table = rel.get("fromTable", "")
            from_col = rel.get("fromColumn", "")
            to_table = rel.get("toTable", "")
            to_col = rel.get("toColumn", "")
            raw_cross = rel.get("crossFilteringBehavior", "")
            cross_filter = _CROSS_FILTER_MAP.get(raw_cross.lower(), raw_cross) if raw_cross else ""
            is_active = rel.get("isActive", True)

            lines.append(f"relationship {_quote_tmdl(rel_name)}")
            lines.append(f"\tfromColumn: {_quote_tmdl(from_table)}.{_quote_tmdl(from_col)}")
            lines.append(f"\ttoColumn: {_quote_tmdl(to_table)}.{_quote_tmdl(to_col)}")
            if cross_filter and cross_filter != "oneDirection":
                lines.append(f"\tcrossFilteringBehavior: {cross_filter}")
            if not is_active:
                lines.append("\tisActive: false")
            lines.append("")

        path.write_text("\n".join(lines), encoding="utf-8")
        logger.debug(f"  Écrit: {path.name}")

    @staticmethod
    def _write_expressions_tmdl(path: Path, expressions: List[Dict]):
        """Write expressions.tmdl (shared M expressions)."""
        lines: List[str] = []
        for expr_def in expressions:
            expr_name = expr_def.get("name", "Expression")
            expr_text = expr_def.get("expression", "")
            tag = expr_def.get("lineageTag", _new_guid())
            query_group = expr_def.get("queryGroup", "")

            lines.append(f"expression {_quote_tmdl(expr_name)} =")
            lines.append("\t\t```")
            for expr_line in expr_text.split("\n"):
                lines.append(f"\t\t{expr_line}")
            lines.append("\t\t```")
            lines.append(f"\tlineageTag: {tag}")
            if query_group:
                lines.append(f"\tqueryGroup: {_quote_tmdl(query_group)}")
            lines.append("")

        path.write_text("\n".join(lines), encoding="utf-8")
        logger.debug(f"  Écrit: {path.name}")

    @staticmethod
    def _write_roles_tmdl(path: Path, roles: List[Dict]):
        """Write roles.tmdl (Row-Level Security roles from Qlik Section Access)."""
        lines: List[str] = []
        for role in roles:
            role_name = role.get("name", "DefaultRole")
            description = role.get("description", "")
            model_perm = role.get("modelPermission", "read")

            lines.append(f"role {_quote_tmdl(role_name)}")
            lines.append(f"\tmodelPermission: {model_perm}")
            if description:
                lines.append(f"\tdescription: {description}")

            # Table permissions with filter expressions
            for tp in role.get("tablePermissions", []):
                tp_table = tp.get("name", tp.get("table", ""))
                tp_filter = tp.get("filterExpression", "")
                if tp_table and tp_filter:
                    lines.append("")
                    lines.append(f"\ttablePermission {_quote_tmdl(tp_table)}")
                    lines.append(f"\t\tfilterExpression: {tp_filter}")

            # RLS members (informational — PBI handles via AAD)
            for member in role.get("members", []):
                member_name = member.get("memberName", "")
                if member_name:
                    lines.append("")
                    lines.append(f"\t/// Member: {member_name}")

            lines.append("")

        path.write_text("\n".join(lines), encoding="utf-8")
        logger.debug(f"  Écrit: {path.name}")

    # ==================================================================
    # Perspectives (optional — for multi-audience models)
    # ==================================================================
    @staticmethod
    def _write_perspectives_tmdl(path: Path, perspectives: List[Dict]):
        """Write perspectives.tmdl."""
        lines: List[str] = []
        for persp in perspectives:
            p_name = persp.get("name", "Default")
            lines.append(f"perspective {_quote_tmdl(p_name)}")
            for table_ref in persp.get("tables", []):
                tbl_name = table_ref if isinstance(table_ref, str) else table_ref.get("name", "")
                if tbl_name:
                    lines.append(f"\tperspectiveTable {_quote_tmdl(tbl_name)}")
            lines.append("")
        path.write_text("\n".join(lines), encoding="utf-8")
        logger.debug(f"  Écrit: {path.name}")

    # ==================================================================
    # Cultures / Translations
    # ==================================================================
    @staticmethod
    def _write_culture_tmdl(path: Path, culture_def: Dict):
        """Write a single culture TMDL file (translations)."""
        culture_name = culture_def.get("name", "en-US")
        lines: List[str] = [
            f"culture {_quote_tmdl(culture_name)}",
        ]
        for translation in culture_def.get("translations", []):
            obj_type = translation.get("objectType", "table")
            obj_name = translation.get("name", "")
            translated = translation.get("translatedCaption", "")
            if obj_name and translated:
                lines.append(f"\tlinguisticMetadata {_quote_tmdl(obj_name)} = {translated}")
        lines.append("")
        path.write_text("\n".join(lines), encoding="utf-8")
        logger.debug(f"  Écrit: {path.name}")

    # ==================================================================
    # Calendar table generator (auto time-intelligence)
    # ==================================================================
    @staticmethod
    def generate_calendar_table() -> Dict:
        """
        Generate a Calendar/Date table definition for time intelligence.

        Returns a table_def dict suitable for _write_table_tmdl().
        """
        tag = _new_guid()
        return {
            "name": "Calendar",
            "lineageTag": tag,
            "dataCategory": "Time",
            "columns": [
                {"name": "Date", "dataType": "dateTime", "sourceColumn": "Date",
                 "lineageTag": _new_guid(), "summarizeBy": "none",
                 "formatString": "yyyy-MM-dd", "isKey": True},
                {"name": "Year", "dataType": "int64", "sourceColumn": "Year",
                 "lineageTag": _new_guid(), "summarizeBy": "none"},
                {"name": "Month", "dataType": "int64", "sourceColumn": "Month",
                 "lineageTag": _new_guid(), "summarizeBy": "none"},
                {"name": "MonthName", "dataType": "string", "sourceColumn": "MonthName",
                 "lineageTag": _new_guid(), "summarizeBy": "none",
                 "sortByColumn": "Month"},
                {"name": "Quarter", "dataType": "int64", "sourceColumn": "Quarter",
                 "lineageTag": _new_guid(), "summarizeBy": "none"},
                {"name": "QuarterLabel", "dataType": "string", "sourceColumn": "QuarterLabel",
                 "lineageTag": _new_guid(), "summarizeBy": "none",
                 "sortByColumn": "Quarter"},
                {"name": "DayOfWeek", "dataType": "int64", "sourceColumn": "DayOfWeek",
                 "lineageTag": _new_guid(), "summarizeBy": "none"},
                {"name": "DayName", "dataType": "string", "sourceColumn": "DayName",
                 "lineageTag": _new_guid(), "summarizeBy": "none",
                 "sortByColumn": "DayOfWeek"},
                {"name": "WeekNumber", "dataType": "int64", "sourceColumn": "WeekNumber",
                 "lineageTag": _new_guid(), "summarizeBy": "none"},
                {"name": "IsWeekend", "dataType": "boolean", "sourceColumn": "IsWeekend",
                 "lineageTag": _new_guid(), "summarizeBy": "none"},
            ],
            "partitions": [
                {
                    "name": "Calendar",
                    "mode": "import",
                    "source": {
                        "type": "m",
                        "expression": (
                            "let\n"
                            '    StartDate = #date(2020, 1, 1),\n'
                            '    EndDate = #date(2030, 12, 31),\n'
                            '    DayCount = Duration.Days(EndDate - StartDate) + 1,\n'
                            '    Source = List.Dates(StartDate, DayCount, #duration(1, 0, 0, 0)),\n'
                            '    Table = Table.FromList(Source, Splitter.SplitByNothing(), {"Date"}, null, ExtraValues.Error),\n'
                            '    ChangedType = Table.TransformColumnTypes(Table, {{"Date", type date}}),\n'
                            '    AddYear = Table.AddColumn(ChangedType, "Year", each Date.Year([Date]), Int64.Type),\n'
                            '    AddMonth = Table.AddColumn(AddYear, "Month", each Date.Month([Date]), Int64.Type),\n'
                            '    AddMonthName = Table.AddColumn(AddMonth, "MonthName", each Date.MonthName([Date]), type text),\n'
                            '    AddQuarter = Table.AddColumn(AddMonthName, "Quarter", each Date.QuarterOfYear([Date]), Int64.Type),\n'
                            '    AddQuarterLabel = Table.AddColumn(AddQuarter, "QuarterLabel", each "Q" & Text.From(Date.QuarterOfYear([Date])), type text),\n'
                            '    AddDayOfWeek = Table.AddColumn(AddQuarterLabel, "DayOfWeek", each Date.DayOfWeek([Date], Day.Monday) + 1, Int64.Type),\n'
                            '    AddDayName = Table.AddColumn(AddDayOfWeek, "DayName", each Date.DayOfWeekName([Date]), type text),\n'
                            '    AddWeekNumber = Table.AddColumn(AddDayName, "WeekNumber", each Date.WeekOfYear([Date]), Int64.Type),\n'
                            '    AddIsWeekend = Table.AddColumn(AddWeekNumber, "IsWeekend", each Date.DayOfWeek([Date], Day.Monday) >= 5, type logical)\n'
                            "in\n"
                            "    AddIsWeekend"
                        ),
                    },
                }
            ],
            "measures": [
                {"name": "Today", "expression": "TODAY()",
                 "lineageTag": _new_guid(), "formatString": "yyyy-MM-dd"},
            ],
        }

    # ==================================================================
    # Parameter / What-If table generator
    # ==================================================================
    @staticmethod
    def generate_parameter_table(
        param_name: str,
        min_val: float = 0,
        max_val: float = 100,
        step: float = 1,
        default_val: Optional[float] = None,
    ) -> Dict:
        """
        Generate a parameter (What-If) table using GENERATESERIES.

        Returns a table_def dict suitable for _write_table_tmdl().
        """
        tag = _new_guid()
        default = default_val if default_val is not None else min_val
        safe_name = param_name.replace(" ", "")

        return {
            "name": param_name,
            "lineageTag": tag,
            "isHidden": False,
            "columns": [
                {
                    "name": f"{param_name} Value",
                    "dataType": "double",
                    "sourceColumn": f"{param_name} Value",
                    "lineageTag": _new_guid(),
                    "summarizeBy": "none",
                    "type": "calculated",
                    "expression": f"GENERATESERIES({min_val}, {max_val}, {step})",
                },
            ],
            "measures": [
                {
                    "name": f"{safe_name}Value",
                    "expression": f'SELECTEDVALUE(\'{param_name}\'[{param_name} Value], {default})',
                    "lineageTag": _new_guid(),
                },
            ],
        }

    # ==================================================================
    # Geographic data categories mapping
    # ==================================================================
    GEOGRAPHIC_CATEGORIES: Dict[str, str] = {
        "country": "Country",
        "state": "StateOrProvince",
        "province": "StateOrProvince",
        "city": "City",
        "postalcode": "PostalCode",
        "zipcode": "PostalCode",
        "zip": "PostalCode",
        "address": "Address",
        "county": "County",
        "continent": "Continent",
        "latitude": "Latitude",
        "longitude": "Longitude",
        "lat": "Latitude",
        "lon": "Longitude",
        "lng": "Longitude",
        "place": "Place",
        "region": "StateOrProvince",
        "countryregion": "Country",
    }

    @classmethod
    def infer_data_category(cls, column_name: str) -> str:
        """Infer geographic dataCategory from column name."""
        lower = column_name.lower().strip()
        return cls.GEOGRAPHIC_CATEGORIES.get(lower, "")

    # ==================================================================
    # Theme JSON generator (Qlik themes → PBI report themes)
    # ==================================================================
    @staticmethod
    def generate_theme_json(
        theme_def: Optional[Dict] = None,
        qlik_colors: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Generate a Power BI report theme JSON from Qlik theme data.

        Args:
            theme_def: Qlik theme definition dict (name, colors, font, etc.)
            qlik_colors: Explicit color palette (overrides theme_def colors)

        Returns:
            PBI theme JSON dict ready to write to theme.json
        """
        theme = theme_def or {}

        default_palette = [
            "#118DFF", "#12239E", "#E66C37", "#6B007B",
            "#E044A7", "#744EC2", "#D9B300", "#D64550",
            "#197278", "#1AAB40", "#15C6F4", "#4092FF",
        ]

        palette = qlik_colors or theme.get("colors", theme.get("palette", default_palette))
        if not palette:
            palette = default_palette

        font = theme.get("fontFamily", theme.get("font", "Segoe UI"))

        pbi_theme: Dict[str, Any] = {
            "name": theme.get("name", "MigratedQlikTheme"),
            "dataColors": palette[:12],
            "background": theme.get("backgroundColor", "#FFFFFF"),
            "foreground": theme.get("foregroundColor", "#252423"),
            "tableAccent": palette[0] if palette else "#118DFF",
            "textClasses": {
                "callout": {"fontSize": 45, "fontFace": font, "color": palette[0] if palette else "#118DFF"},
                "title": {"fontSize": 12, "fontFace": font, "color": "#252423"},
                "header": {"fontSize": 12, "fontFace": font, "color": "#252423"},
                "label": {"fontSize": 10, "fontFace": font, "color": "#666666"},
            },
            "visualStyles": {
                "*": {
                    "*": {
                        "*": [{"wordWrap": True, "fontFamily": font}],
                    },
                },
            },
        }

        if theme.get("conditionalColors"):
            pbi_theme["conditionalFormatting"] = {
                "divergent": {
                    "min": {"color": theme["conditionalColors"].get("min", "#FF0000")},
                    "mid": {"color": theme["conditionalColors"].get("mid", "#FFFF00")},
                    "max": {"color": theme["conditionalColors"].get("max", "#00FF00")},
                }
            }

        return pbi_theme

    # ==================================================================
    # Incremental refresh policy generator
    # ==================================================================
    @staticmethod
    def generate_incremental_refresh_policy(
        table_name: str,
        date_column: str = "Date",
        incremental_days: int = 30,
        archive_days: int = 365,
    ) -> Dict[str, Any]:
        """Generate incremental refresh policy metadata for a table."""
        return {
            "refreshPolicy": {
                "policyType": "basic",
                "rollingWindowGranularity": "day",
                "rollingWindowPeriods": archive_days,
                "incrementalGranularity": "day",
                "incrementalPeriods": incremental_days,
                "pollingExpression": f"let MaxDate = List.Max(Source[{date_column}]) in MaxDate",
            },
        }

    # ==================================================================
    # Sensitivity label helper
    # ==================================================================
    @staticmethod
    def generate_sensitivity_label(
        label_id: str = "",
        label_name: str = "General",
    ) -> Dict[str, Any]:
        """Generate sensitivity label metadata for the .pbip project."""
        return {
            "sensitivityLabel": {
                "labelId": label_id or _new_guid(),
                "displayName": label_name,
            },
        }

    # ==================================================================
    # Deployment pipeline config generator
    # ==================================================================
    @staticmethod
    def generate_deployment_config(
        workspace_dev: str = "",
        workspace_test: str = "",
        workspace_prod: str = "",
    ) -> Dict[str, Any]:
        """Generate deployment pipeline configuration."""
        return {
            "deploymentPipeline": {
                "stages": [
                    {"name": "Development", "workspaceId": workspace_dev or _new_guid()},
                    {"name": "Test", "workspaceId": workspace_test or _new_guid()},
                    {"name": "Production", "workspaceId": workspace_prod or _new_guid()},
                ],
                "rules": {
                    "parameterRules": [],
                    "datasourceRules": [],
                },
            },
        }

    # ==================================================================
    # Scheduled refresh config
    # ==================================================================
    @staticmethod
    def generate_refresh_schedule(
        frequency: str = "Daily",
        times: Optional[List[str]] = None,
        timezone: str = "UTC",
    ) -> Dict[str, Any]:
        """Generate scheduled refresh configuration."""
        return {
            "refreshSchedule": {
                "frequency": frequency,
                "times": times or ["07:00", "19:00"],
                "timeZone": timezone,
                "enabled": True,
                "notifyOption": "MailOnFailure",
            },
        }


# ==================================================================
# Quoting helper
# ==================================================================
def _quote_tmdl(name: str) -> str:
    """Quote a TMDL identifier if it contains spaces or special chars."""
    if not name:
        return "''"
    if " " in name or any(c in name for c in ".-+/\\(){}[]"):
        return f"'{name}'"
    return name


# ==================================================================
# JSON writer helper
# ==================================================================
def _write_json(path: Path, content: dict):
    """Write a dict as pretty-printed JSON (UTF-8 without BOM)."""
    path.write_text(json.dumps(content, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.debug(f"  Écrit: {path.name}")


# ==================================================================
# Convenience function (mirrors the old create_pbix_from_migration)
# ==================================================================
def create_pbi_project_from_migration(
    migration_output_dir: Path,
    project_output_dir: Path,
    report_name: str,
) -> Path:
    """
    Créer un projet PBI (.pbip / TMDL) à partir des fichiers de migration.

    Args:
        migration_output_dir: Dossier contenant les fichiers de migration
        project_output_dir: Dossier où créer le projet PBI
        report_name: Nom du rapport

    Returns:
        Chemin du fichier .pbip créé
    """
    logger.info(f"Création du projet PBI depuis: {migration_output_dir}")

    # Charger le modèle BIM si disponible
    bim_model = None
    bim_files = list(migration_output_dir.glob("powerbi_models/*.bim"))
    if bim_files:
        with open(bim_files[0], "r", encoding="utf-8") as f:
            bim_model = json.load(f)
        logger.info(f"✓ Modèle BIM chargé: {bim_files[0].name}")

    # Charger le script Power Query si disponible
    power_query_script = None
    pq_files = list(migration_output_dir.glob("powerquery_scripts/*.pq"))
    if pq_files:
        with open(pq_files[0], "r", encoding="utf-8") as f:
            power_query_script = f.read()
        logger.info(f"✓ Script Power Query chargé: {pq_files[0].name}")

    # Charger les visualisations si disponibles
    visualizations = None
    dimensions = None
    measures = None

    report_files = list(migration_output_dir.glob("powerbi_reports/*.json"))
    if report_files:
        with open(report_files[0], "r", encoding="utf-8") as f:
            report_data = json.load(f)
            visualizations = report_data.get("visualizations", [])
            dimensions = report_data.get("dimensions", [])
            measures = report_data.get("measures", [])
        logger.info(f"✓ Rapport chargé: {report_files[0].name}")

    generator = TMDLGenerator()
    pbip_path = generator.create_pbi_project(
        output_dir=project_output_dir,
        report_name=report_name,
        bim_model=bim_model,
        power_query_script=power_query_script,
        visualizations=visualizations,
        dimensions=dimensions,
        measures=measures,
    )

    return pbip_path
