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
    ):
        """Write the PBIR definition folder (version.json, report.json, pages/)."""

        # version.json
        _write_json(def_dir / "version.json", {
            "$schema": _SCHEMA_VERSION,
            "version": "2.0.0",
        })

        # report.json (PBIR report-level metadata)
        _write_json(def_dir / "report.json", {
            "$schema": _SCHEMA_REPORT,
            "themeCollection": {
                "baseTheme": {
                    "name": "CY24SU06",
                    "reportVersionAtImport": {
                        "visual": "1.8.50",
                        "report": "2.0.50",
                        "page": "1.3.50",
                    },
                    "type": "SharedResources",
                },
            },
            "settings": {
                "hideVisualContainerHeader": True,
                "useStylableVisualContainerHeader": True,
                "defaultDrillFilterOtherVisuals": True,
                "allowChangeFilterTypes": True,
                "useEnhancedTooltips": True,
            },
        })

        # ── Build pages ──────────────────────────────────────
        page_name = "ReportSection"
        page_display = "Page 1"
        page_dir = pages_dir / page_name
        page_dir.mkdir(parents=True, exist_ok=True)

        # pages.json
        _write_json(pages_dir / "pages.json", {
            "$schema": _SCHEMA_PAGES,
            "pageOrder": [page_name],
            "activePageName": page_name,
        })

        # page.json
        _write_json(page_dir / "page.json", {
            "$schema": _SCHEMA_PAGE,
            "name": page_name,
            "displayName": page_display,
            "displayOption": "FitToPage",
            "height": 720,
            "width": 1280,
        })

        # ── Visuals ──────────────────────────────────────────
        if visualizations:
            visuals_dir = page_dir / "visuals"
            visuals_dir.mkdir(exist_ok=True)
            for i, viz in enumerate(visualizations[:10]):
                visual_id = _short_id(f"viz_{i}_{report_name}")
                v_dir = visuals_dir / visual_id
                v_dir.mkdir(exist_ok=True)
                self._write_visual_json(
                    v_dir / "visual.json",
                    visual_id, viz, i,
                    dimensions or [], measures or [],
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

        # Columns
        for col in table_def.get("columns", []):
            lines.append("")
            col_name = col.get("name", "Col")
            data_type = col.get("dataType", "string")
            col_tag = col.get("lineageTag", _new_guid())
            source_col = col.get("sourceColumn", col_name)
            summarize = col.get("summarizeBy", "none")

            lines.append(f"\tcolumn {_quote_tmdl(col_name)}")
            lines.append(f"\t\tdataType: {data_type}")
            fmt_str = col.get("formatString", "")
            if fmt_str:
                lines.append(f"\t\tformatString: {fmt_str}")
            lines.append(f"\t\tlineageTag: {col_tag}")
            lines.append(f"\t\tsummarizeBy: {summarize}")
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

        # Hierarchies
        for hierarchy in table_def.get("hierarchies", []):
            h_name = hierarchy.get("name", "Hierarchy")
            lines.append("")
            lines.append(f"\thierarchy {_quote_tmdl(h_name)}")
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
