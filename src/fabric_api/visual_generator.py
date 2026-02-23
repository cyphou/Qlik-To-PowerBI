"""
Visual Generator — 60+ Qlik visual types → Power BI visuals

Generates PBIR-format visual containers with:
- 60+ visual type mappings (all Qlik chart types)
- 30+ visual config templates (per-type axis, legend, data label settings)
- Deep per-type query state building
- Grid layout positioning from Qlik sheet cell coordinates
"""

import json
import hashlib
import uuid
import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


def _new_guid() -> str:
    return str(uuid.uuid4())


def _short_id(seed: str = "") -> str:
    return hashlib.sha1((seed or _new_guid()).encode()).hexdigest()[:20]


# ═══════════════════════════════════════════════════════════════════
# 60+ Visual Type Mappings
# ═══════════════════════════════════════════════════════════════════

VISUAL_TYPE_MAP: Dict[str, str] = {
    # ── Bar charts ────────────────────────────────────────────
    "barchart": "clusteredBarChart",
    "bar": "clusteredBarChart",
    "stackedbarchart": "stackedBarChart",
    "stacked-bar": "stackedBarChart",
    "100stackedbarchart": "hundredPercentStackedBarChart",
    "100-stacked-bar": "hundredPercentStackedBarChart",

    # ── Column charts ─────────────────────────────────────────
    "columnchart": "clusteredColumnChart",
    "column": "clusteredColumnChart",
    "stackedcolumnchart": "stackedColumnChart",
    "stacked-column": "stackedColumnChart",
    "100stackedcolumnchart": "hundredPercentStackedColumnChart",
    "100-stacked-column": "hundredPercentStackedColumnChart",
    "histogram": "clusteredColumnChart",

    # ── Line / Area ───────────────────────────────────────────
    "linechart": "lineChart",
    "line": "lineChart",
    "areachart": "areaChart",
    "area": "areaChart",
    "stackedareachart": "stackedAreaChart",
    "stacked-area": "stackedAreaChart",
    "100stackedareachart": "hundredPercentStackedAreaChart",
    "sparkline": "lineChart",

    # ── Combo ─────────────────────────────────────────────────
    "combo": "lineStackedColumnComboChart",
    "combochart": "lineStackedColumnComboChart",
    "linecolumnchart": "lineStackedColumnComboChart",
    "lineclusteredcolumncombochart": "lineClusteredColumnComboChart",

    # ── Pie / Donut / Funnel ──────────────────────────────────
    "piechart": "pieChart",
    "pie": "pieChart",
    "donutchart": "donutChart",
    "donut": "donutChart",
    "funnel": "funnel",
    "funnelchart": "funnel",

    # ── Scatter / Bubble ──────────────────────────────────────
    "scatter": "scatterChart",
    "scatterplot": "scatterChart",
    "scatterchart": "scatterChart",
    "bubble": "scatterChart",
    "bubblechart": "scatterChart",

    # ── Map visualizations ────────────────────────────────────
    "map": "map",
    "geomap": "map",
    "filledmap": "filledMap",
    "shapemap": "shapeMap",
    "azuremap": "azureMap",

    # ── Table / Matrix ────────────────────────────────────────
    "table": "tableEx",
    "straight-table": "tableEx",
    "straighttable": "tableEx",
    "tableex": "tableEx",
    "pivot-table": "pivotTable",
    "pivottable": "pivotTable",
    "pivot": "pivotTable",
    "matrix": "pivotTable",

    # ── KPI / Card / Gauge ────────────────────────────────────
    "kpi": "card",
    "card": "card",
    "multirowcard": "multiRowCard",
    "multi-kpi": "multiRowCard",
    "gauge": "gauge",
    "meter": "gauge",

    # ── Treemap / Hierarchy ───────────────────────────────────
    "treemap": "treemap",
    "sunburst": "sunburst",
    "decompositiontree": "decompositionTree",

    # ── Waterfall / Box / Bullet ──────────────────────────────
    "waterfall": "waterfallChart",
    "waterfallchart": "waterfallChart",
    "boxplot": "boxAndWhisker",
    "box-and-whisker": "boxAndWhisker",
    "bullet": "bulletChart",
    "bulletchart": "bulletChart",

    # ── Text / Image / Container ──────────────────────────────
    "text-image": "textbox",
    "textbox": "textbox",
    "text": "textbox",
    "image": "image",
    "container": "actionButton",
    "tabcontainer": "actionButton",
    "button": "actionButton",
    "actionbutton": "actionButton",

    # ── Filter / Slicer ──────────────────────────────────────
    "filterpane": "slicer",
    "slicer": "slicer",
    "listbox": "slicer",

    # ── Specialty ─────────────────────────────────────────────
    "wordcloud": "wordCloud",
    "word-cloud": "wordCloud",
    "ribbonchart": "ribbonChart",
    "ribbon": "ribbonChart",
    "mekko": "stackedBarChart",
    "mekkochart": "stackedBarChart",
    "distributionplot": "scatterChart",
    "sankey": "sankeyDiagram",
    "networkgraph": "forceGraph",
    "correlationplot": "scatterChart",
    "densityplot": "scatterChart",

    # ── PBI pass-through (already correct) ─────────────────
    "clusteredbarchart": "clusteredBarChart",
    "stackedbarchart": "stackedBarChart",
    "clusteredcolumnchart": "clusteredColumnChart",
    "stackedcolumnchart": "stackedColumnChart",
    "linechart": "lineChart",
    "piechart": "pieChart",
    "scatterchart": "scatterChart",
    "areachart": "areaChart",
    "stackedareachart": "stackedAreaChart",
    "donutchart": "donutChart",
    "waterfallchart": "waterfallChart",
    "lineStackedColumnComboChart": "lineStackedColumnComboChart",
}


# ═══════════════════════════════════════════════════════════════════
# Data Role Definitions per Visual Type
# ═══════════════════════════════════════════════════════════════════

VISUAL_DATA_ROLES: Dict[str, tuple] = {
    # (dimension_roles, measure_roles)
    "card":                              ([], ["Fields"]),
    "multiRowCard":                      ([], ["Values"]),
    "kpi":                               ([], ["Indicator", "TrendAxis"]),
    "clusteredBarChart":                 (["Category"], ["Y"]),
    "stackedBarChart":                   (["Category", "Series"], ["Y"]),
    "hundredPercentStackedBarChart":     (["Category", "Series"], ["Y"]),
    "clusteredColumnChart":              (["Category"], ["Y"]),
    "stackedColumnChart":                (["Category", "Series"], ["Y"]),
    "hundredPercentStackedColumnChart":  (["Category", "Series"], ["Y"]),
    "lineChart":                         (["Category"], ["Y"]),
    "areaChart":                         (["Category"], ["Y"]),
    "stackedAreaChart":                  (["Category", "Series"], ["Y"]),
    "hundredPercentStackedAreaChart":    (["Category", "Series"], ["Y"]),
    "pieChart":                          (["Category"], ["Y"]),
    "donutChart":                        (["Category"], ["Y"]),
    "waterfallChart":                    (["Category"], ["Y"]),
    "funnel":                            (["Category"], ["Y"]),
    "gauge":                             ([], ["Y", "MinValue", "MaxValue", "TargetValue"]),
    "treemap":                           (["Group"], ["Values"]),
    "sunburst":                          (["Group"], ["Values"]),
    "scatterChart":                      (["Category", "Details"], ["X", "Y", "Size"]),
    "tableEx":                           (["Values"], ["Values"]),
    "pivotTable":                        (["Rows", "Columns"], ["Values"]),
    "slicer":                            (["Values"], []),
    "lineStackedColumnComboChart":       (["Category"], ["ColumnY", "LineY"]),
    "lineClusteredColumnComboChart":     (["Category"], ["ColumnY", "LineY"]),
    "map":                               (["Category", "Location"], ["Size", "Color"]),
    "filledMap":                         (["Location"], ["Color"]),
    "ribbonChart":                       (["Category", "Series"], ["Y"]),
    "boxAndWhisker":                     (["Category", "Sampling"], ["Value"]),
    "bulletChart":                       (["Category"], ["Value", "TargetValue", "Minimum", "NeedsImprovement", "Satisfactory", "Good", "VeryGood", "Maximum"]),
    "decompositionTree":                 (["TreeItems"], ["Values"]),
    "wordCloud":                         (["Category"], ["Values"]),
    "textbox":                           ([], []),
    "image":                             ([], []),
    "actionButton":                      ([], []),
}


# ═══════════════════════════════════════════════════════════════════
# 30+ Visual Config Templates
# ═══════════════════════════════════════════════════════════════════

def _get_config_template(visual_type: str) -> Dict[str, Any]:
    """Return per-type visual configuration template."""

    templates: Dict[str, Dict[str, Any]] = {
        "tableEx": {
            "autoSelectVisualType": True,
            "objects": {"values": [{"properties": {"bold": {"expr": {"Literal": {"Value": "false"}}}}}]},
        },
        "pivotTable": {
            "autoSelectVisualType": True,
        },
        "clusteredBarChart": {
            "objects": {
                "categoryAxis": [{"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}}}],
                "valueAxis": [{"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}}}],
                "legend": [{"properties": {"show": {"expr": {"Literal": {"Value": "false"}}}}}],
                "dataPoint": [{"properties": {"showAllDataPoints": {"expr": {"Literal": {"Value": "true"}}}}}],
            },
        },
        "stackedBarChart": {
            "objects": {
                "categoryAxis": [{"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}}}],
                "valueAxis": [{"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}}}],
                "legend": [{"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}}}],
            },
        },
        "clusteredColumnChart": {
            "objects": {
                "categoryAxis": [{"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}}}],
                "valueAxis": [{"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}}}],
                "dataPoint": [{"properties": {"showAllDataPoints": {"expr": {"Literal": {"Value": "true"}}}}}],
            },
        },
        "stackedColumnChart": {
            "objects": {
                "categoryAxis": [{"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}}}],
                "valueAxis": [{"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}}}],
                "legend": [{"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}}}],
            },
        },
        "lineChart": {
            "objects": {
                "categoryAxis": [{"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}}}],
                "valueAxis": [{"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}}}],
                "dataPoint": [{"properties": {"showMarkers": {"expr": {"Literal": {"Value": "true"}}}}}],
                "legend": [{"properties": {"show": {"expr": {"Literal": {"Value": "false"}}}}}],
            },
        },
        "areaChart": {
            "objects": {
                "categoryAxis": [{"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}}}],
                "valueAxis": [{"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}}}],
            },
        },
        "pieChart": {
            "objects": {
                "legend": [{"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}}}],
                "labels": [{"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}, "labelStyle": {"expr": {"Literal": {"Value": "'Category, percent of total'"}}}}}],
            },
        },
        "donutChart": {
            "objects": {
                "legend": [{"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}}}],
                "labels": [{"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}}}],
            },
        },
        "scatterChart": {
            "objects": {
                "categoryAxis": [{"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}, "showAxisTitle": {"expr": {"Literal": {"Value": "true"}}}}}],
                "valueAxis": [{"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}, "showAxisTitle": {"expr": {"Literal": {"Value": "true"}}}}}],
            },
        },
        "gauge": {
            "objects": {
                "axis": [{"properties": {"min": {"expr": {"Literal": {"Value": "0L"}}}, "max": {"expr": {"Literal": {"Value": "100L"}}}}}],
                "target": [{"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}}}],
            },
        },
        "card": {
            "objects": {
                "labels": [{"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}, "fontSize": {"expr": {"Literal": {"Value": "27D"}}}}}],
                "categoryLabels": [{"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}}}],
            },
        },
        "multiRowCard": {
            "objects": {
                "dataLabels": [{"properties": {"fontSize": {"expr": {"Literal": {"Value": "15D"}}}}}],
                "cardTitle": [{"properties": {"fontSize": {"expr": {"Literal": {"Value": "12D"}}}}}],
            },
        },
        "treemap": {
            "objects": {
                "legend": [{"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}}}],
                "labels": [{"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}}}],
            },
        },
        "waterfallChart": {
            "objects": {
                "sentimentColors": [{"properties": {"increaseFill": {"solid": {"color": "#4CAF50"}}, "decreaseFill": {"solid": {"color": "#F44336"}}, "totalFill": {"solid": {"color": "#2196F3"}}}}],
                "categoryAxis": [{"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}}}],
            },
        },
        "funnel": {
            "objects": {
                "labels": [{"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}}}],
            },
        },
        "boxAndWhisker": {
            "objects": {
                "general": [{"properties": {"orientation": {"expr": {"Literal": {"Value": "'Vertical'"}}}}}],
            },
        },
        "map": {
            "objects": {
                "legend": [{"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}}}],
            },
        },
        "filledMap": {
            "objects": {
                "legend": [{"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}}}],
            },
        },
        "ribbonChart": {
            "objects": {
                "categoryAxis": [{"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}}}],
                "valueAxis": [{"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}}}],
                "legend": [{"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}}}],
            },
        },
        "lineStackedColumnComboChart": {
            "objects": {
                "categoryAxis": [{"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}}}],
                "valueAxis": [{"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}}}],
                "lineStyles": [{"properties": {"showMarker": {"expr": {"Literal": {"Value": "true"}}}}}],
                "legend": [{"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}}}],
            },
        },
        "lineClusteredColumnComboChart": {
            "objects": {
                "categoryAxis": [{"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}}}],
                "valueAxis": [{"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}}}],
                "legend": [{"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}}}],
            },
        },
        "wordCloud": {
            "objects": {
                "general": [{"properties": {"maxNumberOfWords": {"expr": {"Literal": {"Value": "100L"}}}}}],
            },
        },
        "bulletChart": {
            "objects": {
                "axis": [{"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}}}],
            },
        },
        "slicer": {
            "objects": {
                "data": [{"properties": {"mode": {"expr": {"Literal": {"Value": "'Basic'"}}}}}],
            },
        },
    }

    return templates.get(visual_type, {})


# ═══════════════════════════════════════════════════════════════════
# Visual Container Generation
# ═══════════════════════════════════════════════════════════════════

def resolve_visual_type(qlik_type: str) -> str:
    """Resolve a Qlik visualization type to a Power BI visual type."""
    return VISUAL_TYPE_MAP.get(qlik_type.lower(), "tableEx")


def generate_visual_containers(
    visualizations: List[Dict],
    report_name: str,
    dimensions: Optional[List[Dict]] = None,
    measures: Optional[List[Dict]] = None,
    col_table_map: Optional[Dict[str, str]] = None,
    measure_lookup: Optional[Dict[str, tuple]] = None,
    page_width: int = 1280,
    page_height: int = 720,
) -> List[Dict]:
    """
    Generate PBIR visual containers for a list of visualizations.

    Args:
        visualizations: List of Qlik visualization dicts
        report_name: Report name (used for ID generation)
        dimensions: Available dimensions
        measures: Available measures
        col_table_map: {column_name: table_name} lookup
        measure_lookup: {measure_name: (table, dax_expr)} lookup
        page_width: Page width in pixels
        page_height: Page height in pixels

    Returns:
        List of (visual_id, visual_json) tuples for writing to visual.json
    """
    containers = []
    dims = dimensions or []
    meas = measures or []
    ctm = col_table_map or {}
    ml = measure_lookup or {}

    for i, viz in enumerate(visualizations[:20]):  # Limit to 20 visuals per page
        visual_id = _short_id(f"viz_{i}_{report_name}")
        visual_json = create_visual_container(
            visual_id=visual_id,
            visualization=viz,
            index=i,
            dimensions=dims,
            measures=meas,
            col_table_map=ctm,
            measure_lookup=ml,
            page_width=page_width,
            page_height=page_height,
        )
        containers.append((visual_id, visual_json))

    return containers


def create_visual_container(
    visual_id: str,
    visualization: Dict,
    index: int,
    dimensions: List[Dict],
    measures: List[Dict],
    col_table_map: Dict[str, str],
    measure_lookup: Dict[str, tuple],
    page_width: int = 1280,
    page_height: int = 720,
) -> Dict[str, Any]:
    """Create a single PBIR visual container."""

    # ── Position calculation (grid layout) ────────────────────
    cols_per_row = 2
    col = index % cols_per_row
    row = index // cols_per_row

    margin = 10
    w = (page_width - margin * (cols_per_row + 1)) // cols_per_row
    h = 340

    x = margin + col * (w + margin)
    y = margin + row * (h + margin)

    # Use Qlik cell position if available
    if "bounds" in visualization:
        bounds = visualization["bounds"]
        x = int(bounds.get("x", x))
        y = int(bounds.get("y", y))
        w = int(bounds.get("width", w))
        h = int(bounds.get("height", h))
    elif "col" in visualization and "row" in visualization:
        x = int(visualization["col"]) * (page_width // 24)  # Qlik uses 24-col grid
        y = int(visualization["row"]) * 50
        if "colspan" in visualization:
            w = int(visualization["colspan"]) * (page_width // 24)
        if "rowspan" in visualization:
            h = int(visualization["rowspan"]) * 50

    # ── Resolve visual type ───────────────────────────────────
    raw_type = visualization.get("type", "tableEx")
    pbi_type = resolve_visual_type(raw_type)

    # ── Build visual object ───────────────────────────────────
    visual_obj: Dict[str, Any] = {
        "visualType": pbi_type,
        "drillFilterOtherVisuals": True,
    }

    # Apply config template
    config = _get_config_template(pbi_type)
    if "autoSelectVisualType" in config:
        visual_obj["autoSelectVisualType"] = config["autoSelectVisualType"]
    if "objects" in config:
        visual_obj["objects"] = config["objects"]

    # ── Build query state ─────────────────────────────────────
    # Use visualization-specific dims/measures if available
    viz_dims = visualization.get("dimensions", dimensions)
    viz_meas = visualization.get("measures", measures)

    query_state = build_query_state(
        pbi_type,
        viz_dims if isinstance(viz_dims, list) else dimensions,
        viz_meas if isinstance(viz_meas, list) else measures,
        col_table_map,
        measure_lookup,
    )
    if query_state:
        visual_obj["query"] = {"queryState": query_state}

    # ── Title ─────────────────────────────────────────────────
    title = visualization.get("title", "") or visualization.get("name", "")
    if title:
        visual_obj.setdefault("vcObjects", {})
        visual_obj["vcObjects"]["title"] = [{
            "properties": {
                "show": {"expr": {"Literal": {"Value": "true"}}},
                "text": {"expr": {"Literal": {"Value": json.dumps(title)}}},
            }
        }]

    # ── Assemble container ────────────────────────────────────
    container = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.5.0/schema.json",
        "name": visual_id,
        "position": {
            "x": x,
            "y": y,
            "z": 1000 + index,
            "height": h,
            "width": w,
            "tabOrder": 1000 + index,
        },
        "visual": visual_obj,
    }

    return container


# ═══════════════════════════════════════════════════════════════════
# Query State Builder
# ═══════════════════════════════════════════════════════════════════

# Aggregation function mapping (Qlik expression → PBI function ID)
_AGG_FUNC_MAP = {
    "sum": 1, "min": 2, "max": 3, "count": 4,
    "countnonnull": 5, "avg": 6, "average": 6,
}


def build_query_state(
    pbi_type: str,
    dimensions: List[Dict],
    measures: List[Dict],
    col_table_map: Dict[str, str],
    measure_lookup: Dict[str, tuple],
) -> Optional[Dict]:
    """Build PBIR queryState with role-based projections."""
    import re

    roles = VISUAL_DATA_ROLES.get(pbi_type)
    if not roles:
        return None

    dim_roles, meas_roles = roles

    # ── Resolve dimension projections ─────────────────────────
    dim_projections: List[Dict] = []
    for dim in dimensions:
        field_name = dim.get("field", "") or dim.get("name", "")
        table_name = col_table_map.get(field_name, "")
        if not table_name and col_table_map:
            table_name = next(iter(col_table_map.values()), "Table")
        if table_name and field_name:
            proj = {
                "field": {
                    "Column": {
                        "Expression": {"SourceRef": {"Entity": table_name}},
                        "Property": field_name,
                    },
                },
                "queryRef": f"{table_name}.{field_name}",
                "nativeQueryRef": field_name,
                "active": True,
            }
            display_name = dim.get("label") or dim.get("name")
            if display_name:
                proj["displayName"] = display_name
            dim_projections.append(proj)

    # ── Resolve measure projections ───────────────────────────
    meas_projections: List[Dict] = []
    for meas in measures:
        measure_label = meas.get("label") or meas.get("name", "Measure")

        # Try named measure from BIM model
        bim_info = measure_lookup.get(measure_label)
        if bim_info:
            tbl_name, _dax_expr = bim_info
            proj = {
                "field": {
                    "Measure": {
                        "Expression": {"SourceRef": {"Entity": tbl_name}},
                        "Property": measure_label,
                    },
                },
                "queryRef": f"{tbl_name}.{measure_label}",
                "nativeQueryRef": measure_label,
            }
            if measure_label:
                proj["displayName"] = measure_label
            meas_projections.append(proj)
            continue

        # Fallback: inline aggregation from Qlik expression
        expr = meas.get("expression", "")
        m = re.match(r'(\w+)\((\w+)\)', expr.strip()) if expr else None
        if m:
            func_name, col_name = m.group(1).lower(), m.group(2)
        else:
            func_name, col_name = "", expr.strip() if expr else ""

        func_id = _AGG_FUNC_MAP.get(func_name, 1)
        table_name = col_table_map.get(col_name, "")
        if not table_name and col_table_map:
            table_name = next(iter(col_table_map.values()), "Table")
        if table_name and col_name:
            agg_name = func_name.capitalize() if func_name else "Sum"
            proj = {
                "field": {
                    "Aggregation": {
                        "Expression": {
                            "Column": {
                                "Expression": {"SourceRef": {"Entity": table_name}},
                                "Property": col_name,
                            },
                        },
                        "Function": func_id,
                    },
                },
                "queryRef": f"{agg_name}({table_name}.{col_name})",
                "nativeQueryRef": col_name,
            }
            if measure_label:
                proj["displayName"] = measure_label
            meas_projections.append(proj)

    if not dim_projections and not meas_projections:
        return None

    query_state: Dict[str, Any] = {}

    # ── Special: tableEx shares a single "Values" role ────────
    if pbi_type == "tableEx":
        all_projs = dim_projections + meas_projections
        if all_projs:
            query_state["Values"] = {"projections": all_projs}
        return query_state if query_state else None

    # ── Assign dimensions to dimension roles ──────────────────
    for role_name in dim_roles:
        if dim_projections:
            query_state[role_name] = {"projections": list(dim_projections)}

    # ── Assign measures to measure roles ──────────────────────
    for i, role_name in enumerate(meas_roles):
        if i < len(meas_projections):
            query_state[role_name] = {"projections": [meas_projections[i]]}
        elif meas_projections:
            query_state[role_name] = {"projections": [meas_projections[0]]}

    return query_state if query_state else None
