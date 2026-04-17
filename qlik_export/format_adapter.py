"""
Format adapter: Qlik extraction → generation-layer converted_objects.

Transforms the 11 Qlik intermediate JSON files into the dict structure
expected by the shared ``powerbi_import/`` generation layer (TMDL + PBIP).

Mapping overview
================
Qlik intermediate file      →  ``converted_objects`` key
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

from qlik_export.qlik_model_converter import _infer_column_datatype

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
    # 3.1 — Inject theme colors from app_metadata into the first dashboard
    theme_colors = qlik_app_meta.get('theme', {}).get('colors', [])
    if not theme_colors:
        theme_colors = qlik_app_meta.get('colors', [])
    if theme_colors and dashboards:
        dashboards[0].setdefault('theme', {})['colors'] = theme_colors

    # 3.2 — Promote variables that contain aggregation expressions to measures
    _AGG_PATTERN = re.compile(
        r'\b(Sum|Avg|Count|Min|Max|Median|Stdev|Only|CountDistinct)\s*\(',
        re.IGNORECASE,
    )
    promoted: list[Dict] = []
    remaining_params: list[Dict] = []
    for p in parameters:
        val = p.get('value', '')
        if val and _AGG_PATTERN.search(val):
            promoted.append({
                'name': p['name'],
                'caption': p.get('caption', p['name']),
                'formula': val,
                'role': 'measure',
                'datatype': 'double',
                'original_type': 'qlik_variable_measure',
            })
        else:
            remaining_params.append(p)
    calculations.extend(promoted)
    parameters = remaining_params

    # 3.3 — Parse Section Access from load script → user_filters (RLS)
    user_filters = _parse_section_access(qlik_loadscript)
    # Inject calculations into datasources (Tableau format nests them)
    _inject_calculations_into_datasources(datasources, calculations)

    # 3.4 — Extract navigation actions (drillTo, goToSheet) from visuals
    actions = _extract_navigation_actions(qlik_visuals)

    result = {
        'datasources':  datasources,
        'worksheets':   worksheets,
        'dashboards':   dashboards,
        'calculations': calculations,
        'parameters':   parameters,
        'filters':      [],
        'stories':      stories,
        'actions':      actions,
        'sets':         [],
        'groups':       [],
        'bins':         [],
        'hierarchies':  [],
        'sort_orders':  [],
        'aliases':      {},
        'custom_sql':   custom_sql,
        'user_filters': user_filters,
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
            # Infer type from column name when source has no explicit type
            if col_type in ('string', 'text'):
                col_type = _infer_column_datatype(col_name)
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
            'filters': _extract_visual_filters(viz),
            'sort_orders': _extract_sort_orders(viz),
            'subtitle': viz.get('subtitle', ''),
        }

        # Slicer-specific configuration from Qlik filter panes
        if qlik_type in ('filterpane', 'listbox'):
            worksheet['slicer_config'] = _extract_slicer_config(viz)

        # 3a — Tooltip page references (viz-in-tooltip)
        tooltip_viz = viz.get('tooltip', {})
        if isinstance(tooltip_viz, dict) and tooltip_viz.get('type') == 'visualization':
            worksheet.setdefault('tooltips', []).append({
                'type': 'viz_in_tooltip',
                'worksheet': tooltip_viz.get('visualization', tooltip_viz.get('id', '')),
            })

        # 3b — Alternate state (qStateName)
        state_name = viz.get('qStateName', viz.get('stateName', ''))
        if state_name and state_name != '$':
            worksheet['alternate_state'] = state_name

        # 3c — Conditional formatting icon rules
        cond_fmt = viz.get('conditionalFormatting', viz.get('conditional_formatting', []))
        icon_rules = []
        for rule in (cond_fmt if isinstance(cond_fmt, list) else []):
            if isinstance(rule, dict) and rule.get('type') in ('icon', 'iconSet', 'icon_set'):
                icon_rules.append(rule)
        if icon_rules:
            worksheet['icon_rules'] = icon_rules

        # Carry layout info (used by dashboard objects)
        if bounds:
            worksheet['_bounds'] = bounds
        worksheet['_col'] = col
        worksheet['_row'] = row
        worksheet['_colspan'] = colspan
        worksheet['_rowspan'] = rowspan

        worksheets.append(worksheet)

    return worksheets


# ── Per-visual filters ────────────────────────────────────────────────

def _extract_visual_filters(viz: Dict) -> List[Dict]:
    """Extract visual-level dimension limits / filters from a Qlik visualization.

    Qlik visuals may have:
      - ``qHyperCubeDef.qDimensions[].qOtherLimit`` (limit values shown)
      - ``qHyperCubeDef.qStateCounts`` (for limit enforcement)
      - ``qFilters`` or ``filters`` nested lists
    """
    filters: List[Dict] = []

    # Explicit filter definitions on the visual
    for f in viz.get('filters', []):
        field = f if isinstance(f, str) else f.get('field', f.get('name', ''))
        values = [] if isinstance(f, str) else f.get('values', [])
        exclude = False if isinstance(f, str) else f.get('exclude', False)
        ftype = 'categorical' if isinstance(f, str) else f.get('type', 'categorical')
        if field:
            entry: Dict = {'field': field, 'type': ftype, 'exclude': exclude}
            if values:
                entry['values'] = values
            if not isinstance(f, str):
                if f.get('min') is not None:
                    entry['min'] = f['min']
                if f.get('max') is not None:
                    entry['max'] = f['max']
            filters.append(entry)

    # Qlik dimension "other" limits → top-N filters
    for dim in viz.get('dimensions', []):
        if isinstance(dim, dict):
            other_limit = dim.get('qOtherLimit', dim.get('otherLimit', {}))
            if isinstance(other_limit, dict) and other_limit.get('qOtherMode', 0) != 0:
                limit_n = other_limit.get('qOtherLimitNo', 10)
                dim_field = dim.get('field', dim.get('name', ''))
                if dim_field:
                    filters.append({
                        'field': dim_field,
                        'type': 'topN',
                        'topN': limit_n,
                    })

    return filters


def _extract_sort_orders(viz: Dict) -> List[Dict]:
    """Extract sort orders from a Qlik visualization definition.

    Qlik sort criteria can appear as:
      - ``qHyperCubeDef.qInterColumnSortOrder`` (column indices)
      - ``qSortCriterias`` on individual dimensions
      - ``sortOrder`` / ``sort`` explicit property
    """
    sort_orders: List[Dict] = []

    # Direct sort specification
    for s in viz.get('sort_orders', viz.get('sort', [])):
        if isinstance(s, dict):
            sort_orders.append({
                'field': s.get('field', s.get('column', '')),
                'direction': s.get('direction', s.get('order', 'ascending')),
            })
        elif isinstance(s, str):
            sort_orders.append({'field': s, 'direction': 'ascending'})

    # Fallback: infer from dimension sort criteria
    if not sort_orders:
        for dim in viz.get('dimensions', []):
            if isinstance(dim, dict):
                sort_crit = dim.get('qSortCriterias', dim.get('sortCriteria', []))
                if sort_crit:
                    direction = 'ascending'
                    if isinstance(sort_crit, list) and sort_crit:
                        first = sort_crit[0] if isinstance(sort_crit[0], dict) else {}
                        if first.get('qSortByNumeric', 0) == -1 or first.get('qSortByLoadOrder', 0) == -1:
                            direction = 'descending'
                    dim_field = dim.get('field', dim.get('name', ''))
                    if dim_field:
                        sort_orders.append({'field': dim_field, 'direction': direction})

    return sort_orders


def _extract_slicer_config(viz: Dict) -> Dict:
    """Extract slicer configuration from a Qlik filter pane / listbox.

    Returns a dict with Power BI slicer properties:
      - mode: 'Basic' or 'Dropdown'
      - singleSelect: bool
      - search_enabled: bool
      - orientation: 'Vertical' or 'Horizontal'
    """
    props = viz.get('properties', viz.get('props', {}))
    qlik_type = (viz.get('type', '') or '').lower()

    # Detect dropdown vs list
    show_mode = props.get('listLayout', props.get('showMode', ''))
    is_dropdown = (show_mode == 'dropdown' or qlik_type == 'dropdown')

    # Single select
    single_select = props.get('singleSelect', props.get('qListObjectDef', {}).get('qSingleSelect', False))

    # Search
    search_enabled = props.get('searchEnabled', True)

    # Date range detection
    is_date_range = False
    for dim in viz.get('dimensions', []):
        if isinstance(dim, dict):
            field_name = (dim.get('field', '') or '').lower()
            if any(kw in field_name for kw in ('date', 'time', 'year', 'month')):
                is_date_range = True
                break

    return {
        'mode': 'Dropdown' if is_dropdown else 'Basic',
        'singleSelect': bool(single_select),
        'search_enabled': bool(search_enabled),
        'is_date_range': is_date_range,
    }


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

        # 3d — Background image from sheet metadata
        bg_image = sheet.get('backgroundImage', sheet.get('background_image', {}))
        if not bg_image:
            bg_image = sheet.get('properties', {}).get('backgroundImage', {})

        db_entry = {
            'name': sheet_name,
            'size': {'width': width, 'height': height},
            'objects': objects,
        }
        if bg_image and isinstance(bg_image, dict) and bg_image.get('url'):
            db_entry['backgroundImage'] = {
                'url': bg_image['url'],
                'transparency': bg_image.get('transparency', 0),
            }

        dashboards.append(db_entry)

    return dashboards


# ── Navigation actions (drillTo, goToSheet, URL) ───────────────────

def _extract_navigation_actions(qlik_visuals: List[Dict]) -> List[Dict]:
    """Extract navigation actions from Qlik visualizations.

    Qlik buttons and visuals can have navigation actions:
      - ``navigation.action = "goToSheet"`` → sheet-navigate
      - ``navigation.action = "goToSheetById"`` → sheet-navigate
      - ``navigation.action = "goToURL"`` → url
      - ``actions`` list with ``actionType: "drillTo"`` or ``"nextSheet"``
    """
    actions: List[Dict] = []

    for viz in qlik_visuals:
        viz_name = viz.get('title', viz.get('name', viz.get('id', '')))

        # 1. Qlik navigation property (buttons, containers)
        nav = viz.get('navigation', {})
        if isinstance(nav, dict) and nav.get('action'):
            nav_action = nav['action']
            if nav_action in ('goToSheet', 'goToSheetById'):
                target_sheet = nav.get('sheet', nav.get('sheetId', ''))
                if target_sheet:
                    actions.append({
                        'type': 'sheet-navigate',
                        'target_worksheet': target_sheet,
                        'source_worksheet': viz_name,
                    })
            elif nav_action == 'goToURL':
                url = nav.get('url', '')
                if url:
                    actions.append({
                        'type': 'url',
                        'url': url,
                        'source_worksheet': viz_name,
                    })

        # 2. Qlik actions list (newer format)
        for act in viz.get('actions', []):
            if not isinstance(act, dict):
                continue
            act_type = act.get('actionType', act.get('type', ''))
            if act_type == 'drillTo':
                target = act.get('sheet', act.get('target', ''))
                field = act.get('field', act.get('bookmark', ''))
                if target:
                    actions.append({
                        'type': 'filter',
                        'target_worksheet': target,
                        'field': field,
                        'source_worksheet': viz_name,
                    })
            elif act_type in ('nextSheet', 'prevSheet', 'goToSheet'):
                target = act.get('sheet', act.get('target', ''))
                if target:
                    actions.append({
                        'type': 'sheet-navigate',
                        'target_worksheet': target,
                        'source_worksheet': viz_name,
                    })

    return actions


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
    """Convert Qlik bookmarks → Tableau story format with selection state."""
    stories = []
    for bm in qlik_bookmarks:
        name = bm.get('name', bm.get('title', ''))
        if not name:
            continue

        # Extract selection state from bookmark
        selections = bm.get('selections', bm.get('qBookmark', {}).get('qStateData', []))
        filters_state = []
        for sel in (selections if isinstance(selections, list) else []):
            field = sel.get('fieldName', sel.get('field', ''))
            values = sel.get('selectedValues', sel.get('values', []))
            if field:
                filters_state.append({
                    'field': field,
                    'values': values,
                })

        story_point = {
            'caption': name,
            'worksheet': '',
            'filters_state': filters_state if filters_state else None,
            'captured_sheet': bm.get('sheetId', bm.get('sheet', '')),
        }

        stories.append({
            'name': name,
            'caption': bm.get('description', name),
            'story_points': [story_point],
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


# ── Section Access → RLS user_filters ────────────────────────────────

def _parse_section_access(qlik_loadscript: Any) -> List[Dict]:
    """Parse Qlik SECTION ACCESS block into RLS user_filter dicts.

    Returns a list of dicts, each with:
      - name: role name
      - filter_expression: DAX filter (e.g., USERPRINCIPALNAME() = "user@domain")
      - tables: list of table names this role applies to (empty = all)
      - type: 'user_filter' or 'calculated_security'
      - omit_fields: list of fields hidden from this user (OMIT column)
      - reduce_field: field name that restricts visible rows
      - reduce_values: values for the reduce field
    """
    if not qlik_loadscript:
        return []

    script_text = ''
    if isinstance(qlik_loadscript, dict):
        script_text = qlik_loadscript.get('script', qlik_loadscript.get('content', ''))
    elif isinstance(qlik_loadscript, str):
        script_text = qlik_loadscript

    if not script_text:
        return []

    # Find SECTION ACCESS block
    sa_match = re.search(
        r'SECTION\s+ACCESS\s*;(.*?)(?:SECTION\s+APPLICATION\s*;|\Z)',
        script_text,
        re.IGNORECASE | re.DOTALL,
    )
    if not sa_match:
        return []

    sa_block = sa_match.group(1)
    roles: List[Dict] = []

    # Parse LOAD ... INLINE [...] inside section access
    inline_match = re.search(
        r'LOAD\s+.*?INLINE\s*\[(.*?)\]',
        sa_block,
        re.IGNORECASE | re.DOTALL,
    )
    if not inline_match:
        return []

    lines = inline_match.group(1).strip().split('\n')
    if len(lines) < 2:
        return []

    # First line is header
    headers = [h.strip().upper() for h in lines[0].split(',')]
    userid_idx = None
    ntname_idx = None
    omit_idx = None
    reduce_idx = None
    for i, h in enumerate(headers):
        if h in ('USERID', 'USER'):
            userid_idx = i
        elif h in ('NTNAME',):
            ntname_idx = i
        elif h == 'OMIT':
            omit_idx = i
        elif h == 'REDUCTION':
            reduce_idx = i

    user_col_idx = userid_idx if userid_idx is not None else ntname_idx
    if user_col_idx is None:
        return []

    for line in lines[1:]:
        parts = [p.strip() for p in line.split(',')]
        if len(parts) <= user_col_idx:
            continue
        user_val = parts[user_col_idx].strip().strip('"').strip("'")
        if not user_val:
            continue

        # Wildcard * means "all users" → TRUE() filter
        if user_val == '*':
            filter_expr = 'TRUE()'
            role_name = 'RLS_AllUsers'
        else:
            filter_expr = f'USERPRINCIPALNAME() = "{user_val}"'
            role_name = f'RLS_{user_val.split("@")[0]}'

        role = {
            'name': role_name,
            'filter_expression': filter_expr,
            'tables': [],
            'type': 'user_filter',
        }

        # Parse OMIT field — columns to hide from this user
        if omit_idx is not None and len(parts) > omit_idx:
            omit_val = parts[omit_idx].strip().strip('"').strip("'")
            if omit_val:
                role['omit_fields'] = [f.strip() for f in omit_val.split(';') if f.strip()]

        # Parse REDUCTION field — rows to restrict
        if reduce_idx is not None and len(parts) > reduce_idx:
            reduce_val = parts[reduce_idx].strip().strip('"').strip("'")
            if reduce_val:
                role['reduce_values'] = [v.strip() for v in reduce_val.split(';') if v.strip()]

        roles.append(role)

    if roles:
        logger.info("Parsed %d RLS roles from Section Access", len(roles))
    return roles
