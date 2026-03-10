"""
Format adapter: Qlik extraction → Tableau-compatible converted_objects.

Transforms the 11 Qlik intermediate JSON files into the dict structure
expected by the shared ``powerbi_import/`` generation layer (TMDL + PBIP).

Mapping overview
================
Qlik intermediate file      →  Tableau ``converted_objects`` key
─────────────────────────   ────────────────────────────────────
datasources.json             →  datasources (restructured)
visualizations.json          →  worksheets
sheets.json                  →  dashboards
measures.json                →  calculations (role=measure) + datasources[].calculations
dimensions.json              →  calculations (role=dimension) + datasources[].calculations
variables.json               →  parameters
associations.json            →  datasources[].relationships
bookmarks.json               →  stories
loadscript.json              →  custom_sql (+ m_query_overrides)
master_items.json            →  (merged into calculations)
app_metadata.json            →  (metadata only)
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Visual type mapping (Qlik → PBI chart_type) ────────────────────

_QLIK_CHART_TYPE_MAP = {
    'barchart': 'clusteredBarChart',
    'bar': 'clusteredBarChart',
    'combochart': 'lineStackedColumnComboChart',
    'combo': 'lineStackedColumnComboChart',
    'linechart': 'lineChart',
    'line': 'lineChart',
    'piechart': 'pieChart',
    'pie': 'pieChart',
    'scatterplot': 'scatterChart',
    'scatter': 'scatterChart',
    'table': 'tableEx',
    'straight table': 'tableEx',
    'pivot-table': 'pivotTable',
    'pivot table': 'pivotTable',
    'pivottable': 'pivotTable',
    'kpi': 'card',
    'gauge': 'gauge',
    'map': 'map',
    'treemap': 'treemap',
    'waterfallchart': 'waterfallChart',
    'waterfall': 'waterfallChart',
    'boxplot': 'boxAndWhisker',
    'distributionplot': 'scatterChart',
    'histogram': 'clusteredColumnChart',
    'filterpane': 'slicer',
    'listbox': 'slicer',
    'text-image': 'textbox',
    'container': 'actionButton',
    'mekko': 'stackedBarChart',
    'mekkochart': 'stackedBarChart',
    'bullet': 'bulletChart',
    'bulletchart': 'bulletChart',
    'wordcloud': 'wordCloud',
    'qlik-word-cloud': 'wordCloud',
    'funnelchart': 'funnel',
    'funnel': 'funnel',
    'donut': 'donutChart',
    'donutchart': 'donutChart',
    'areachart': 'areaChart',
    'area': 'areaChart',
    'stackedbarchart': 'stackedBarChart',
    'columnchart': 'clusteredColumnChart',
    'column': 'clusteredColumnChart',
    'stackedcolumnchart': 'stackedColumnChart',
    'sankey': 'decompositionTree',
    'networkgraph': 'decompositionTree',
    'heatmap': 'tableEx',
}


def adapt_qlik_for_generation(qlik_data: Dict[str, Any]) -> Dict[str, Any]:
    """Transform Qlik extraction output to generation-layer format.

    Args:
        qlik_data: Dict with 11 Qlik intermediate keys
                   (datasources, dimensions, measures, visualizations,
                    sheets, variables, loadscript, associations,
                    bookmarks, master_items, app_metadata)

    Returns:
        Dict matching the ``converted_objects`` contract expected by
        ``powerbi_import/pbip_generator.py`` and ``powerbi_import/tmdl_generator.py``.

    Raises:
        ValueError: If *qlik_data* is ``None`` or not a ``dict``.
    """
    # ── Input validation ────────────────────────────────────
    if qlik_data is None:
        raise ValueError("qlik_data must not be None")
    if not isinstance(qlik_data, dict):
        raise ValueError(f"qlik_data must be a dict, got {type(qlik_data).__name__}")

    # ── Source data ──────────────────────────────────────────
    qlik_datasources  = qlik_data.get('datasources', [])
    qlik_dimensions   = qlik_data.get('dimensions', [])
    qlik_measures     = qlik_data.get('measures', [])
    qlik_visuals      = qlik_data.get('visualizations', [])
    qlik_sheets       = qlik_data.get('sheets', [])
    qlik_variables    = qlik_data.get('variables', [])
    qlik_loadscript   = qlik_data.get('loadscript', {})
    qlik_associations = qlik_data.get('associations', [])
    qlik_bookmarks    = qlik_data.get('bookmarks', [])
    qlik_master_items = qlik_data.get('master_items', [])
    qlik_app_meta     = qlik_data.get('app_metadata', {})

    # ── Build adapted structures ────────────────────────────
    datasources   = _adapt_datasources(qlik_datasources, qlik_associations, qlik_loadscript)
    calculations  = _adapt_calculations(qlik_measures, qlik_dimensions, qlik_master_items)
    worksheets    = _adapt_worksheets(qlik_visuals)
    dashboards    = _adapt_dashboards(qlik_sheets, qlik_visuals)
    parameters    = _adapt_parameters(qlik_variables)
    stories       = _adapt_stories(qlik_bookmarks)
    custom_sql    = _adapt_custom_sql(qlik_loadscript)

    # Inject calculations into datasources (Tableau format nests them)
    _inject_calculations_into_datasources(datasources, calculations)

    result = {
        'datasources':  datasources,
        'worksheets':   worksheets,
        'dashboards':   dashboards,
        'calculations': calculations,
        'parameters':   parameters,
        'filters':      [],
        'stories':      stories,
        'actions':      [],
        'sets':         [],
        'groups':       [],
        'bins':         [],
        'hierarchies':  [],
        'sort_orders':  [],
        'aliases':      {},
        'custom_sql':   custom_sql,
        'user_filters': [],
    }

    logger.info(
        "Qlik→PBI format adapted: %d datasources, %d worksheets, "
        "%d dashboards, %d calculations, %d parameters",
        len(datasources), len(worksheets), len(dashboards),
        len(calculations), len(parameters),
    )

    return result


# Backward-compat alias (deprecated — use adapt_qlik_for_generation)
def adapt_qlik_to_tableau_format(qlik_data: Dict[str, Any]) -> Dict[str, Any]:
    """Deprecated — use :func:`adapt_qlik_for_generation`."""
    import warnings
    warnings.warn(
        "adapt_qlik_to_tableau_format is deprecated, "
        "use adapt_qlik_for_generation instead",
        DeprecationWarning,
        stacklevel=2,
    )
    return adapt_qlik_for_generation(qlik_data)


# ── Datasources ─────────────────────────────────────────────────────

def _adapt_datasources(
    qlik_ds: List[Dict],
    qlik_assoc: List[Dict],
    qlik_loadscript: Any,
) -> List[Dict]:
    """Convert Qlik datasources → generation-layer datasource format."""
    if not qlik_ds:
        logger.warning("No datasources found in Qlik data")
        return []

    datasources = []
    for ds in qlik_ds:
        table_name = ds.get('tableName', ds.get('name', ds.get('table', 'Table')))
        if not table_name:
            table_name = f'Table_{len(datasources) + 1}'
            logger.warning("Datasource missing name — defaulting to '%s'", table_name)
        conn_type  = (ds.get('connectionType', '')
                      or ds.get('type', '')
                      or ds.get('sourceType', '')).lower()

        # Build connection dict
        raw_conn = ds.get('connection', {})
        if isinstance(raw_conn, str):
            raw_conn = {'connectionString': raw_conn}

        connection = {
            'type': conn_type,
        }
        # Forward standard keys
        for key in ('server', 'database', 'schema', 'path', 'filename',
                     'host', 'port', 'connectionString', 'url'):
            if raw_conn.get(key):
                connection[key] = raw_conn[key]

        # Build columns
        raw_columns = ds.get('columns', [])
        if not raw_columns:
            logger.warning("Empty columns in datasource '%s' — using fallback", table_name)
        columns = []
        for col in raw_columns:
            col_name = col.get('name', '')
            col_type = (col.get('dataType', '')
                        or col.get('type', '')
                        or 'string').lower()
            columns.append({
                'name': col_name,
                'datatype': col_type,
                'caption': col.get('label', col.get('caption', col_name)),
                'role': 'dimension',
                'hidden': col.get('hidden', False),
                'description': col.get('comment', col.get('description', '')),
                'default_format': col.get('formatString', col.get('format', '')),
            })

        # Table entry
        table_entry = {
            'name': table_name,
            'columns': columns,
        }

        # M query override from load script or pre-built M
        m_overrides = {}
        m_query = ds.get('m_query', ds.get('mQuery', ''))
        if m_query:
            m_overrides[table_name] = m_query

        adapted_ds = {
            'name': table_name,
            'connection': connection,
            'tables': [table_entry],
            'columns': columns,            # DS-level columns (inherited)
            'calculations': [],            # Populated later
            'relationships': [],           # Populated from associations
        }
        if m_overrides:
            adapted_ds['m_query_overrides'] = m_overrides

        datasources.append(adapted_ds)

    # ── Inject relationships from associations ──────────────
    _inject_relationships(datasources, qlik_assoc)

    return datasources


def _inject_relationships(datasources: List[Dict], associations: List[Dict]):
    """Convert Qlik associations → Tableau relationship format inside datasources."""
    if not associations:
        return

    ds_map = {ds['name']: ds for ds in datasources}

    for assoc in associations:
        table1 = assoc.get('table1', assoc.get('fromTable', ''))
        table2 = assoc.get('table2', assoc.get('toTable', ''))
        field1 = assoc.get('field1', assoc.get('fromField', assoc.get('fromColumn', '')))
        field2 = assoc.get('field2', assoc.get('toField', assoc.get('toColumn', '')))

        rel = {
            'left': {'table': table1, 'column': field1},
            'right': {'table': table2, 'column': field2},
            'type': 'left',
        }

        # Add to the first matching datasource
        target_ds = ds_map.get(table1) or ds_map.get(table2)
        if target_ds:
            target_ds.setdefault('relationships', []).append(rel)
            # Ensure both tables exist in this datasource
            existing = {t['name'] for t in target_ds.get('tables', [])}
            other = table2 if table1 in existing else table1
            if other and other not in existing:
                # Add the other table as a stub
                other_ds = ds_map.get(other)
                if other_ds and other_ds.get('tables'):
                    target_ds['tables'].append(other_ds['tables'][0])
        else:
            # No matching datasource — attach to first
            if datasources:
                datasources[0].setdefault('relationships', []).append(rel)


# ── Calculations ────────────────────────────────────────────────────

def _adapt_calculations(
    qlik_measures: List[Dict],
    qlik_dimensions: List[Dict],
    qlik_master_items: List[Dict],
) -> List[Dict]:
    """Convert Qlik measures + calculated dimensions → Tableau calculations."""
    calculations = []
    seen_names = set()

    # Measures → calculations (role=measure)
    for m in qlik_measures:
        name = m.get('name', m.get('label', ''))
        if not name or name in seen_names:
            continue
        seen_names.add(name)
        calculations.append({
            'name': name,
            'caption': m.get('label', m.get('name', name)),
            'formula': m.get('expression', m.get('definition', '')),
            'role': 'measure',
            'datatype': m.get('dataType', 'real'),
            'original_type': 'qlik_measure',
        })

    # Dimensions → calculations (only calculated ones with expressions)
    for d in qlik_dimensions:
        name = d.get('name', d.get('label', ''))
        field = d.get('field', d.get('definition', ''))

        # Only include as a calculation if it has an expression
        # (not just a plain field reference)
        is_calculated = d.get('is_calculated', False)
        if not is_calculated and field:
            # Heuristic: if the field contains function calls, it's calculated
            is_calculated = bool(re.search(r'[A-Za-z]+\s*\(', field))

        if not name or name in seen_names:
            continue

        if is_calculated:
            seen_names.add(name)
            calculations.append({
                'name': name,
                'caption': d.get('label', name),
                'formula': field,
                'role': 'dimension',
                'datatype': d.get('dataType', 'string'),
                'original_type': 'qlik_dimension_calculated',
            })

    # Master items (any that weren't already captured)
    for mi in qlik_master_items:
        mi_type = mi.get('type', 'measure')
        name = mi.get('name', mi.get('label', ''))
        if not name or name in seen_names:
            continue
        expr = mi.get('expression', mi.get('definition', mi.get('field', '')))
        if not expr:
            continue
        seen_names.add(name)
        calculations.append({
            'name': name,
            'caption': mi.get('label', name),
            'formula': expr,
            'role': 'measure' if mi_type == 'measure' else 'dimension',
            'datatype': mi.get('dataType', 'string'),
            'original_type': f'qlik_master_{mi_type}',
        })

    return calculations


def _inject_calculations_into_datasources(
    datasources: List[Dict],
    calculations: List[Dict],
):
    """Inject calculations into datasource dicts (Tableau nests them inside DS)."""
    if not datasources or not calculations:
        return

    # All calculations go into the first datasource (main datasource)
    # matching how Tableau routes unrouted calcs to the global main DS
    main_ds = datasources[0]
    for calc in calculations:
        main_ds.setdefault('calculations', []).append({
            'name': calc['name'],
            'caption': calc.get('caption', calc['name']),
            'formula': calc.get('formula', ''),
            'role': calc.get('role', 'measure'),
            'datatype': calc.get('datatype', 'string'),
        })


# ── Worksheets (from Qlik visualizations) ───────────────────────────

def _adapt_worksheets(qlik_visuals: List[Dict]) -> List[Dict]:
    """Convert Qlik visualizations → Tableau worksheet format."""
    worksheets = []

    for viz in qlik_visuals:
        qlik_type = (viz.get('type', '')
                     or viz.get('visualType', '')
                     or viz.get('chart_type', '')).lower()
        pbi_type = _QLIK_CHART_TYPE_MAP.get(qlik_type)
        if pbi_type is None:
            pbi_type = 'clusteredBarChart'
            if qlik_type:
                logger.warning("Unmapped Qlik chart type '%s' → defaulting to clusteredBarChart", qlik_type)

        name = viz.get('title', viz.get('name', viz.get('id', f'Visual_{len(worksheets)}')))

        # Build dimensions list
        dimensions = []
        for dim in viz.get('dimensions', []):
            dim_field = dim if isinstance(dim, str) else dim.get('field', dim.get('name', dim.get('label', '')))
            dim_label = dim if isinstance(dim, str) else dim.get('label', dim.get('name', dim_field))
            if dim_field:
                dimensions.append({
                    'field': dim_field,
                    'name': dim_field,
                    'label': dim_label,
                })

        # Build measures list
        measures = []
        for meas in viz.get('measures', []):
            m_name = meas if isinstance(meas, str) else meas.get('name', meas.get('label', ''))
            m_expr = '' if isinstance(meas, str) else meas.get('expression', meas.get('definition', ''))
            m_label = meas if isinstance(meas, str) else meas.get('label', meas.get('name', m_name))
            if m_name:
                measures.append({
                    'name': m_name,
                    'label': m_label,
                    'expression': m_expr,
                })

        # Build fields list (combined dims + measures for the legacy path)
        fields = []
        for d in dimensions:
            fields.append({
                'name': d.get('field', d.get('name', '')),
                'role': 'dimension',
                'shelf': 'rows',
            })
        for m in measures:
            fields.append({
                'name': m.get('name', ''),
                'role': 'measure',
                'shelf': 'columns',
            })

        # Bounds / position (passed through for layout)
        bounds = viz.get('bounds', {})
        col = viz.get('col', 0)
        row = viz.get('row', 0)
        colspan = viz.get('colspan', 6)
        rowspan = viz.get('rowspan', 4)

        worksheet = {
            'name': name,
            'chart_type': pbi_type,
            'mark_type': qlik_type,
            'visualType': pbi_type,
            'fields': fields,
            'dimensions': dimensions,
            'measures': measures,
            'dataFields': [],
            'filters': [],
            'sort_orders': [],
            'subtitle': viz.get('subtitle', ''),
        }

        # Carry layout info (used by dashboard objects)
        if bounds:
            worksheet['_bounds'] = bounds
        worksheet['_col'] = col
        worksheet['_row'] = row
        worksheet['_colspan'] = colspan
        worksheet['_rowspan'] = rowspan

        worksheets.append(worksheet)

    return worksheets


# ── Dashboards (from Qlik sheets) ──────────────────────────────────

def _adapt_dashboards(
    qlik_sheets: List[Dict],
    qlik_visuals: List[Dict],
) -> List[Dict]:
    """Convert Qlik sheets → Tableau dashboard format."""
    if not qlik_sheets:
        # If no explicit sheets, create a single dashboard from all visuals
        if qlik_visuals:
            objects = []
            for i, viz in enumerate(qlik_visuals):
                name = viz.get('title', viz.get('name', viz.get('id', f'Visual_{i}')))
                bounds = viz.get('bounds', {})
                objects.append({
                    'type': 'worksheetReference',
                    'worksheetName': name,
                    'position': {
                        'x': bounds.get('x', (i % 3) * 400),
                        'y': bounds.get('y', (i // 3) * 300),
                        'w': bounds.get('width', bounds.get('w', 400)),
                        'h': bounds.get('height', bounds.get('h', 300)),
                    },
                })
            return [{
                'name': 'Dashboard',
                'size': {'width': 1280, 'height': 720},
                'objects': objects,
            }]
        return []

    # Build visual lookup by sheet
    visual_by_sheet: Dict[str, List[Dict]] = {}
    for viz in qlik_visuals:
        sheet_id = viz.get('sheetId', viz.get('sheet', ''))
        if sheet_id:
            visual_by_sheet.setdefault(sheet_id, []).append(viz)

    dashboards = []
    for sheet in qlik_sheets:
        sheet_id = sheet.get('id', sheet.get('qInfo', {}).get('qId', ''))
        sheet_name = sheet.get('title', sheet.get('name', f'Sheet_{len(dashboards)}'))

        # Size
        width = sheet.get('width', 1280)
        height = sheet.get('height', 720)

        # Visuals on this sheet
        sheet_visuals = visual_by_sheet.get(sheet_id, [])

        # If no visuals matched by sheetId, try matching all visuals
        # for the first sheet (common in exports)
        if not sheet_visuals and len(qlik_sheets) == 1:
            sheet_visuals = qlik_visuals

        # Build dashboard objects (worksheet references)
        objects = []
        for i, viz in enumerate(sheet_visuals):
            viz_name = viz.get('title', viz.get('name', viz.get('id', f'Visual_{i}')))
            bounds = viz.get('bounds', {})

            # Compute position from bounds or grid
            x = bounds.get('x', viz.get('col', (i % 3)) * 400)
            y = bounds.get('y', viz.get('row', (i // 3)) * 300)
            w = bounds.get('width', bounds.get('w', viz.get('colspan', 6) * 130))
            h = bounds.get('height', bounds.get('h', viz.get('rowspan', 4) * 100))

            objects.append({
                'type': 'worksheetReference',
                'worksheetName': viz_name,
                'position': {'x': x, 'y': y, 'w': w, 'h': h},
            })

        dashboards.append({
            'name': sheet_name,
            'size': {'width': width, 'height': height},
            'objects': objects,
        })

    return dashboards


# ── Parameters (from Qlik variables) ───────────────────────────────

def _adapt_parameters(qlik_variables: List[Dict]) -> List[Dict]:
    """Convert Qlik variables → Tableau parameter format."""
    parameters = []
    for v in qlik_variables:
        name = v.get('name', '')
        definition = v.get('definition', v.get('value', ''))
        if not name:
            continue

        # Skip system variables (start with special chars)
        if name.startswith('$') or name.startswith('_'):
            continue

        parameters.append({
            'name': name,
            'caption': v.get('label', v.get('comment', name)),
            'displayName': v.get('label', name),
            'value': definition,
            'currentValue': definition,
            'datatype': 'string',   # Qlik variables are untyped
        })

    return parameters


# ── Stories (from Qlik bookmarks) ───────────────────────────────────

def _adapt_stories(qlik_bookmarks: List[Dict]) -> List[Dict]:
    """Convert Qlik bookmarks → Tableau story format."""
    stories = []
    for bm in qlik_bookmarks:
        name = bm.get('name', bm.get('title', ''))
        if not name:
            continue
        stories.append({
            'name': name,
            'caption': bm.get('description', name),
            'story_points': [{
                'caption': name,
                'worksheet': '',
            }],
        })
    return stories


# ── Custom SQL (from Qlik load script) ──────────────────────────────

def _adapt_custom_sql(qlik_loadscript: Any) -> List[Dict]:
    """Convert Qlik load script → custom_sql entries."""
    if not qlik_loadscript:
        return []

    script_text = ''
    if isinstance(qlik_loadscript, dict):
        script_text = qlik_loadscript.get('script', '')
    elif isinstance(qlik_loadscript, str):
        script_text = qlik_loadscript

    if not script_text:
        return []

    return [{
        'name': 'QlikLoadScript',
        'query': script_text,
        'tables': [],
    }]
