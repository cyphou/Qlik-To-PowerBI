"""
Power BI Project (.pbip) generator from converted Qlik objects

This module automatically creates the complete structure of a Power BI Project,
including all the files needed to open the project in Power BI Desktop.
"""

import os
import json
import logging
from datetime import datetime
import uuid
import re
import sys
import shutil

logger = logging.getLogger(__name__)

# Add project root to sys.path for package imports
_project_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
if os.path.abspath(_project_root) not in [os.path.abspath(p) for p in sys.path]:
    sys.path.insert(0, os.path.abspath(_project_root))

# Generator imports
from powerbi_import import m_query_generator
from powerbi_import import tmdl_generator


def _write_json(filepath, data, ensure_ascii=True):
    """Write a JSON file, creating parent directories as needed."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=ensure_ascii)


def _L(v):
    """PBIR expression literal wrapper."""
    return {"expr": {"Literal": {"Value": v}}}


class PowerBIProjectGenerator:
    """Generates Power BI Project (.pbip) files"""
    
    def __init__(self, output_dir='artifacts/powerbi_projects/'):
        self.output_dir = os.path.abspath(output_dir)
        
        os.makedirs(self.output_dir, exist_ok=True)
    
    def generate_project(self, report_name, converted_objects, calendar_start=None,
                         calendar_end=None, culture=None, model_mode='import',
                         output_format='pbip', paginated=False):
        """
        Generates a complete Power BI Project
        
        Args:
            report_name: Report name
            converted_objects: Dict containing all converted objects
            calendar_start: Start year for Calendar table (default: 2020)
            calendar_end: End year for Calendar table (default: 2030)
            culture: Override culture/locale for semantic model
            paginated: If True, generate a paginated report layout alongside interactive report
        
        Returns:
            str: Path to the generated project
        """
        
        print(f"\n🔨 Generating Power BI Project: {report_name}")
        
        # Store options for downstream use
        self._calendar_start = calendar_start
        self._calendar_end = calendar_end
        self._culture = culture
        self._model_mode = model_mode or 'import'
        self._output_format = output_format or 'pbip'
        self._paginated = paginated
        
        # Create project structure
        project_dir = os.path.join(self.output_dir, report_name)
        os.makedirs(project_dir, exist_ok=True)
        
        # 1. Create the .pbip file
        pbip_file = self.create_pbip_file(project_dir, report_name)
        print(f"  ✓ .pbip file created: {pbip_file}")
        
        # 2. Create the SemanticModel structure
        if self._output_format in ('pbip', 'tmdl'):
            sm_dir = self.create_semantic_model_structure(project_dir, report_name, converted_objects)
            print(f"  ✓ SemanticModel created: {sm_dir}")
        
        # 3. Create the Report structure
        if self._output_format in ('pbip', 'pbir'):
            report_dir = self.create_report_structure(project_dir, report_name, converted_objects)
            print(f"  ✓ Report created: {report_dir}")
        
        # 4. Create metadata
        self.create_metadata(project_dir, report_name, converted_objects)
        print(f"  ✓ Metadata created")
        
        # 5. Copy sample data files if provided
        sample_data_dir = converted_objects.get('_sample_data_dir')
        if sample_data_dir and os.path.isdir(sample_data_dir):
            data_dest = os.path.join(project_dir, 'data')
            os.makedirs(data_dest, exist_ok=True)
            import shutil
            copied = 0
            for f in os.listdir(sample_data_dir):
                src = os.path.join(sample_data_dir, f)
                if os.path.isfile(src):
                    shutil.copy2(src, os.path.join(data_dest, f))
                    copied += 1
            if copied:
                print(f"  ✓ Sample data copied: {copied} files → {data_dest}")
        
        # 6. GeoJSON passthrough for shape map visuals
        try:
            from powerbi_import.geo_passthrough import (
                detect_geo_sources, copy_geo_resources, build_shape_map_config,
            )
            visualizations = converted_objects.get('worksheets', [])
            geo_sources = detect_geo_sources(visualizations)
            if geo_sources:
                created = copy_geo_resources(geo_sources, project_dir, report_name)
                if created:
                    print(f"  ✓ GeoJSON resources: {len(created)} files → RegisteredResources/")
        except Exception as exc:
            logger.debug("GeoJSON passthrough skipped: %s", exc)

        # 7. Create paginated report layout (if requested)
        if self._paginated:
            pag_dir = self._create_paginated_report(project_dir, report_name, converted_objects)
            print(f"  ✓ Paginated report layout created: {pag_dir}")
        
        print(f"\n✅ Power BI Project generated: {project_dir}")
        print(f"   📂 Open in Power BI Desktop: {pbip_file}")
        
        return project_dir
    
    def create_pbip_file(self, project_dir, report_name):
        """Creates the main .pbip file — format identical to PBI Hero reference"""
        
        pbip_content = {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json",
            "version": "1.0",
            "artifacts": [
                {
                    "report": {
                        "path": f"{report_name}.Report"
                    }
                }
            ],
            "settings": {
                "enableAutoRecovery": True
            }
        }
        
        pbip_file = os.path.join(project_dir, f"{report_name}.pbip")
        
        _write_json(pbip_file, pbip_content)
        
        # Also create the .gitignore
        gitignore = os.path.join(project_dir, '.gitignore')
        with open(gitignore, 'w', encoding='utf-8') as f:
            f.write(".pbi/\n")
        
        return pbip_file
    
    def create_semantic_model_structure(self, project_dir, report_name, converted_objects):
        """Creates the SemanticModel structure (format identical to PBI Hero reference)"""
        
        import time as _time
        sm_dir = os.path.join(project_dir, f"{report_name}.SemanticModel")
        if os.path.exists(sm_dir):
            for attempt in range(5):
                try:
                    shutil.rmtree(sm_dir)
                    break
                except (OSError, PermissionError):
                    if attempt < 4:
                        _time.sleep(0.5 * (attempt + 1))
                    else:
                        for root, dirs, files in os.walk(sm_dir, topdown=False):
                            for name in files:
                                try:
                                    os.remove(os.path.join(root, name))
                                except OSError:
                                    pass
                            for name in dirs:
                                try:
                                    os.rmdir(os.path.join(root, name))
                                except OSError:
                                    pass
        os.makedirs(sm_dir, exist_ok=True)
        
        # 1. Create .platform
        platform = {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
            "metadata": {
                "type": "SemanticModel",
                "displayName": report_name
            },
            "config": {
                "version": "2.0",
                "logicalId": str(uuid.uuid4())
            }
        }
        _write_json(os.path.join(sm_dir, '.platform'), platform)
        
        # 2. Create definition.pbism
        pbism_definition = {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
            "version": "4.2",
            "settings": {
                "qnaEnabled": True
            }
        }
        pbism_file = os.path.join(sm_dir, 'definition.pbism')
        _write_json(pbism_file, pbism_definition)
        
        # 3. Create SemanticModel in TMDL (format identical to PBI Hero reference)
        self.create_tmdl_model(sm_dir, report_name, converted_objects)
        
        return sm_dir
    
    def create_tmdl_model(self, sm_dir, report_name, converted_objects):
        """Creates the semantic model in TMDL format (Tabular Model Definition Language)
        
        Directly converts extracted source data to TMDL files.
        """
        
        datasources = converted_objects.get('datasources', [])
        
        # Collect additional objects
        extra_objects = {
            'hierarchies': converted_objects.get('hierarchies', []),
            'sets': converted_objects.get('sets', []),
            'groups': converted_objects.get('groups', []),
            'bins': converted_objects.get('bins', []),
            'aliases': converted_objects.get('aliases', {}),
            'parameters': converted_objects.get('parameters', []),
            'user_filters': converted_objects.get('user_filters', []),
            '_datasources': converted_objects.get('datasources', []),
            '_bridge_tables': converted_objects.get('_bridge_tables', 'none'),
        }
        
        try:
            # Direct source -> TMDL generation (no intermediate BIM layer)
            stats = tmdl_generator.generate_tmdl(
                datasources=datasources,
                report_name=report_name,
                extra_objects=extra_objects,
                output_dir=sm_dir,
                calendar_start=getattr(self, '_calendar_start', None),
                calendar_end=getattr(self, '_calendar_end', None),
                culture=getattr(self, '_culture', None),
                model_mode=getattr(self, '_model_mode', 'import'),
            )

            # Capture measure renames (measure/column collision fix) so the
            # report generator can update stale visual bindings.
            self._measure_renames = stats.get('measure_renames', {}) or {}

            print(f"  \u2713 TMDL model created with:")
            print(f"    - {stats['tables']} tables")
            print(f"    - {stats['columns']} columns")
            print(f"    - {stats['measures']} DAX measures")
            print(f"    - {stats['relationships']} relationships")
            if stats['hierarchies']:
                print(f"    - {stats['hierarchies']} hierarchies")
            if stats['roles']:
                print(f"    - {stats['roles']} RLS roles")

            # Relationship health report (Phase 4)
            rel_report = stats.get('relationship_report', {})
            if rel_report.get('manyToMany', 0):
                print(f"    - {rel_report['manyToMany']} manyToMany relationship(s)")
            if rel_report.get('inactive', 0):
                print(f"    - {rel_report['inactive']} inactive relationship(s)")
            if rel_report.get('bridgeTables', 0):
                print(f"    - {rel_report['bridgeTables']} bridge table relationship(s)")
            
        except Exception as e:
            print(f"  \u26a0 Error during TMDL generation: {e}")
            import traceback
            traceback.print_exc()
    
    def _create_basic_model_bim(self, report_name, datasources):
        """Basic BIM generation in case of error (fallback)"""
        
        tables = []
        
        # Create a simple sample table
        m_expression = m_query_generator.generate_sample_data_query('SampleData', None)
        
        tables.append({
            "name": "SampleData",
            "columns": [
                {"name": "ID", "dataType": "int64", "sourceColumn": "ID"},
                {"name": "Name", "dataType": "string", "sourceColumn": "Name"},
                {"name": "Value", "dataType": "int64", "sourceColumn": "Value"}
            ],
            "partitions": [{
                "name": "SampleData",
                "mode": "import",
                "source": {
                    "type": "m",
                    "expression": m_expression
                }
            }]
        })
        
        return {
            "name": report_name,
            "compatibilityLevel": 1567,
            "model": {
                "culture": "en-US",
                "defaultPowerBIDataSourceVersion": "powerBI_V3",
                "tables": tables
            }
        }
    
    # ── Visual creation helpers (extracted from create_report_structure) ─────

    def _make_visual_position(self, pos, scale_x, scale_y, z_index):
        """Create a standard PBIR position dict from source coordinates."""
        return {
            "x": round(pos.get('x', 0) * scale_x),
            "y": round(pos.get('y', 0) * scale_y),
            "z": z_index * 1000,
            "height": round(pos.get('h', 200) * scale_y),
            "width": round(pos.get('w', 300) * scale_x),
            "tabOrder": z_index * 1000
        }

    def _create_visual_worksheet(self, visuals_dir, ws_data, obj, scale_x, scale_y,
                                  visual_count, worksheets, converted_objects,
                                  tooltip_page_map=None):
        """Create a worksheet-type visual (chart, table, etc.)."""
        visual_id = uuid.uuid4().hex[:20]
        visual_dir = os.path.join(visuals_dir, visual_id)

        pos = obj.get('position', {})
        visual_type = ws_data.get('chart_type', 'clusteredBarChart') if ws_data else 'clusteredBarChart'
        ws_name = obj.get('worksheetName', '')

        # Validate scatter chart: needs at least one measure for X/Y axes.
        # Circle/Shape marks sometimes produce scatterChart but lack measures.
        if visual_type == 'scatterChart' and ws_data:
            skip_names = {'Measure Names', 'Measure Values', 'Multiple Values',
                          ':Measure Names', ':Measure Values'}
            fields = ws_data.get('fields', [])
            has_measure = any(
                self._is_measure_field(self._clean_field_name(f.get('name', '')))
                for f in fields
                if self._clean_field_name(f.get('name', '')) not in skip_names
            )
            if not has_measure:
                visual_type = 'table'

        visual_json = {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.5.0/schema.json",
            "name": visual_id,
            "position": self._make_visual_position(pos, scale_x, scale_y, visual_count),
            "visual": {
                "visualType": visual_type,
                "drillFilterOtherVisuals": True
            }
        }

        # Add query if fields are available
        if ws_data and ws_data.get('fields'):
            query = self._build_visual_query(ws_data)
            if query:
                visual_json["visual"]["query"] = query
                # Apply sort state from extraction
                sort_orders = ws_data.get('sort_orders', [])
                if sort_orders and isinstance(sort_orders, list) and len(sort_orders) > 0:
                    sort_def = sort_orders[0]
                    sort_field = sort_def.get('field', '')
                    sort_dir = sort_def.get('direction', 'ASC')
                    sort_by = sort_def.get('sort_by', '')

                    # Clean source notation: strip "DatasourceName." prefix
                    if '.' in sort_field:
                        sort_field = sort_field.split('.', 1)[1]
                    if '.' in sort_by:
                        sort_by = sort_by.split('.', 1)[1]
                    # Strip aggregation prefixes (sum:, avg:, etc.) and type suffixes (:qk, :nk)
                    sort_field = self._clean_field_name(sort_field)
                    sort_by = self._clean_field_name(sort_by)
                    if sort_field:
                        # Resolve sort field and sort_by through _field_map for correct Entity/Property
                        sort_entity = self._main_table
                        sort_prop = sort_field
                        if hasattr(self, '_field_map') and sort_field in self._field_map:
                            sort_entity, sort_prop = self._field_map[sort_field]

                        sort_entry = {
                            "direction": "Descending" if sort_dir.upper() == 'DESC' else "Ascending"
                        }
                        if sort_by:
                            # Resolve sort_by measure through _field_map
                            by_entity = self._main_table
                            by_prop = sort_by
                            if hasattr(self, '_field_map') and sort_by in self._field_map:
                                by_entity, by_prop = self._field_map[sort_by]
                            # Computed sort: sort category by a measure
                            sort_entry["field"] = {
                                "Aggregation": {
                                    "Expression": {"Column": {"Expression": {"SourceRef": {"Entity": by_entity}}, "Property": by_prop}},
                                    "Function": 0
                                }
                            }
                        else:
                            sort_entry["field"] = {
                                "Column": {"Expression": {"SourceRef": {"Entity": sort_entity}}, "Property": sort_prop}
                            }
                        query["queryState"] = query.get("queryState", {})
                        query["sortDefinition"] = {"sort": [sort_entry]}

        # Visual objects: title + encodings
        visual_objects = self._build_visual_objects(ws_name, ws_data, visual_type)
        visual_json["visual"]["objects"] = visual_objects

        # Visual filters
        if ws_data and ws_data.get('filters'):
            visual_filters = self._create_visual_filters(ws_data['filters'])
            if visual_filters:
                visual_json["filterConfig"] = {"filters": visual_filters}

        # Tooltip page binding (viz-in-tooltip → Power BI Report Page tooltip)
        if tooltip_page_map and ws_data:
            # Check if this worksheet has a viz-in-tooltip reference
            tooltips = ws_data.get('tooltips', [])
            if isinstance(tooltips, list):
                for tip in tooltips:
                    if isinstance(tip, dict) and tip.get('type') == 'viz_in_tooltip':
                        tip_ws_name = tip.get('worksheet', '')
                        tip_page_name = tooltip_page_map.get(tip_ws_name)
                        if tip_page_name:
                            visual_json["visual"].setdefault("objects", {})
                            visual_json["visual"]["objects"]["tooltips"] = [{
                                "properties": {
                                    "type": _L("'ReportPage'"),
                                    "page": _L(f"'{tip_page_name}'")
                                }
                            }]
                            break

        # Apply padding from dashboard zone
        obj_padding = obj.get('padding', {})
        if obj_padding:
            pad_props = {}
            for side in ('left', 'right', 'top', 'bottom'):
                pad_key = f'padding-{side}'
                if pad_key in obj_padding:
                    pad_props[side] = _L(f"{obj_padding[pad_key]}D")
            if pad_props:
                visual_json["visual"].setdefault("objects", {})
                visual_json["visual"]["objects"]["padding"] = [{"properties": pad_props}]
            # Apply border if extracted
            if obj_padding.get('border_style') and obj_padding['border_style'] != 'none':
                border_props = {
                    "show": _L("true")
                }
                if obj_padding.get('border_color'):
                    border_props["color"] = {
                        "solid": {"color": _L(f"'{obj_padding['border_color']}'")}
                    }
                visual_json["visual"].setdefault("objects", {})
                visual_json["visual"]["objects"]["border"] = [{"properties": border_props}]

        _write_json(os.path.join(visual_dir, 'visual.json'), visual_json, ensure_ascii=False)

    @staticmethod
    def _parse_rich_text_runs(obj):
        """Parse source text runs into PBI paragraphs with formatting.

        Converts <formatted-text><run> elements (bold, italic, color,
        font_size, url) into PBI textRuns with textStyle properties.

        Args:
            obj: Dashboard text object with 'text_runs' and 'content' fields

        Returns:
            list: PBI paragraphs array for textbox visual
        """
        text_runs = obj.get('text_runs', [])
        if not text_runs:
            # Fallback: single plain run from content
            return [{"textRuns": [{"value": obj.get('content', '')}]}]

        # Group runs into paragraphs by newline characters
        paragraphs = []
        current_runs = []
        for run in text_runs:
            text = run.get('text', '')
            # Split on newlines to create separate paragraphs
            lines = text.split('\n')
            for i, line in enumerate(lines):
                if i > 0:
                    # Newline = new paragraph
                    paragraphs.append({"textRuns": current_runs if current_runs else [{"value": ""}]})
                    current_runs = []
                if line or i == 0:
                    pbi_run = {"value": line}
                    # Build textStyle from source run formatting
                    style = {}
                    if run.get('bold'):
                        style['fontWeight'] = 'bold'
                    if run.get('italic'):
                        style['fontStyle'] = 'italic'
                    if run.get('color'):
                        color = run['color']
                        if color.startswith('#') and len(color) == 7:
                            style['color'] = color
                        elif color.startswith('#') and len(color) == 9:
                            # Source uses #AARRGGBB, PBI uses #RRGGBB
                            style['color'] = '#' + color[3:]
                    if run.get('font_size'):
                        try:
                            pts = float(run['font_size'])
                            style['fontSize'] = f"{pts}pt"
                        except (ValueError, TypeError):
                            logger.debug("Could not parse font_size: %s", run.get('font_size'))
                    if style:
                        pbi_run['textStyle'] = style
                    # URL → hyperlink
                    if run.get('url'):
                        pbi_run['url'] = run['url']
                    current_runs.append(pbi_run)

        # Flush last paragraph
        if current_runs:
            paragraphs.append({"textRuns": current_runs})

        return paragraphs if paragraphs else [{"textRuns": [{"value": ""}]}]

    def _create_visual_textbox(self, visuals_dir, obj, scale_x, scale_y, visual_count):
        """Create a textbox visual from a source text object.

        Supports rich text with bold, italic, color, font_size, and URLs
        from <formatted-text><run> elements.
        """
        visual_id = uuid.uuid4().hex[:20]
        visual_dir = os.path.join(visuals_dir, visual_id)

        pos = obj.get('position', {})
        paragraphs = self._parse_rich_text_runs(obj)

        visual_json = {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.5.0/schema.json",
            "name": visual_id,
            "position": self._make_visual_position(pos, scale_x, scale_y, visual_count),
            "visual": {
                "visualType": "textbox",
                "objects": {
                    "general": [{
                        "properties": {
                            "paragraphs": _L(json.dumps(paragraphs))
                        }
                    }]
                }
            }
        }
        _write_json(os.path.join(visual_dir, 'visual.json'), visual_json, ensure_ascii=False)

    def _create_visual_image(self, visuals_dir, obj, scale_x, scale_y, visual_count):
        """Create an image visual from a source image object."""
        visual_id = uuid.uuid4().hex[:20]
        visual_dir = os.path.join(visuals_dir, visual_id)

        pos = obj.get('position', {})

        visual_json = {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.5.0/schema.json",
            "name": visual_id,
            "position": self._make_visual_position(pos, scale_x, scale_y, visual_count),
            "visual": {
                "visualType": "image",
                "objects": {
                    "general": [{
                        "properties": {
                            "imageUrl": _L(f"'{obj.get('source', '')}'")
                        }
                    }]
                }
            }
        }
        _write_json(os.path.join(visual_dir, 'visual.json'), visual_json, ensure_ascii=False)

    def _create_visual_filter_control(self, visuals_dir, obj, scale_x, scale_y,
                                       visual_count, calc_id_to_caption, converted_objects):
        """Create a slicer visual from a source filter control."""
        visual_id = uuid.uuid4().hex[:20]
        visual_dir = os.path.join(visuals_dir, visual_id)

        pos = obj.get('position', {})
        calc_col_id = obj.get('calc_column_id', '')
        column_name = calc_id_to_caption.get(calc_col_id, '')
        if not column_name:
            # Try the raw calc_column_id as a physical column name
            column_name = calc_col_id if calc_col_id else obj.get('field', obj.get('name', ''))

        # Resolve table via _field_map first (more reliable), then _find_column_table
        table_name = ''
        if hasattr(self, '_field_map') and column_name in self._field_map:
            table_name, column_name = self._field_map[column_name]
        if not table_name:
            table_name = self._find_column_table(column_name, converted_objects)

        vx = round(pos.get('x', 0) * scale_x)
        vy = round(pos.get('y', 0) * scale_y)
        vw = round(pos.get('w', 200) * scale_x)
        vh = round(pos.get('h', 60) * scale_y)

        # Determine slicer mode from parameter/field data type
        slicer_mode = self._detect_slicer_mode(obj, column_name, converted_objects)

        slicer_json = self._create_slicer_visual(visual_id, vx, vy, vw, vh,
                                                  column_name, table_name, visual_count,
                                                  slicer_mode=slicer_mode)
        _write_json(os.path.join(visual_dir, 'visual.json'), slicer_json, ensure_ascii=False)

    def _create_action_visuals(self, visuals_dir, actions, scale_x, scale_y,
                                visual_count, page_display_name):
        """Create action button visuals from source actions.
        
        Generates:
        - URL actions → actionButton visuals with WebUrl type
        - sheet-navigate actions → actionButton visuals with PageNavigation type
        
        Returns the number of visuals created.
        """
        created = 0
        for action in actions:
            action_type = action.get('type', '')
            
            if action_type == 'url':
                visual_id = uuid.uuid4().hex[:20]
                visual_dir = os.path.join(visuals_dir, visual_id)
                
                url = action.get('url', '')
                action_name = action.get('name', 'URL Action')
                
                btn_json = {
                    "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.5.0/schema.json",
                    "name": visual_id,
                    "position": {
                        "x": 10, "y": 10 + created * 50,
                        "z": (visual_count + created) * 1000,
                        "height": 40, "width": 200,
                        "tabOrder": (visual_count + created) * 1000
                    },
                    "visual": {
                        "visualType": "actionButton",
                        "objects": {
                            "icon": [{"properties": {"shapeType": _L("'ArrowRight'")}}],
                            "outline": [{"properties": {"show": _L("false")}}],
                            "text": [{"properties": {
                                "show": _L("true"),
                                "text": _L(f"'{action_name}'")
                            }}],
                            "action": [{"properties": {
                                "type": _L("'WebUrl'"),
                                "webUrl": _L(f"'{url}'")
                            }}]
                        }
                    }
                }
                _write_json(os.path.join(visual_dir, 'visual.json'), btn_json, ensure_ascii=False)
                created += 1
            
            elif action_type == 'sheet-navigate':
                visual_id = uuid.uuid4().hex[:20]
                visual_dir = os.path.join(visuals_dir, visual_id)
                
                target_ws = action.get('target_worksheet', '')
                action_name = action.get('name', target_ws or 'Navigate')
                
                btn_json = {
                    "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.5.0/schema.json",
                    "name": visual_id,
                    "position": {
                        "x": 10, "y": 10 + created * 50,
                        "z": (visual_count + created) * 1000,
                        "height": 40, "width": 200,
                        "tabOrder": (visual_count + created) * 1000
                    },
                    "visual": {
                        "visualType": "actionButton",
                        "objects": {
                            "icon": [{"properties": {"shapeType": _L("'ArrowRight'")}}],
                            "outline": [{"properties": {"show": _L("false")}}],
                            "text": [{"properties": {
                                "show": _L("true"),
                                "text": _L(f"'{action_name}'")
                            }}],
                            "action": [{"properties": {
                                "type": _L("'PageNavigation'")
                            }}]
                        }
                    }
                }
                _write_json(os.path.join(visual_dir, 'visual.json'), btn_json, ensure_ascii=False)
                created += 1
        
        return created

    def create_report_structure(self, project_dir, report_name, converted_objects):
        """Creates the Report structure in PBIR v4.0 format (identical to PBI Hero reference)
        
        Structure:
          Report/
            .platform
            definition.pbir
            definition/
              version.json
              report.json
              pages/
                pages.json
                {pageName}/
                  page.json
                  visuals/
                    {visualId}/
                      visual.json
        """
        import shutil
        import time
        
        # Build field mapping from source to Power BI model
        self._build_field_mapping(converted_objects)
        
        report_dir = os.path.join(project_dir, f"{report_name}.Report")
        
        # Clean previous content (with retries for OneDrive sync locks)
        if os.path.exists(report_dir):
            for attempt in range(5):
                try:
                    shutil.rmtree(report_dir)
                    break
                except PermissionError:
                    if attempt < 4:
                        time.sleep(0.5 * (attempt + 1))
                    else:
                        # Last resort: remove files individually, skip locked ones
                        for root, dirs, files in os.walk(report_dir, topdown=False):
                            for name in files:
                                try:
                                    os.remove(os.path.join(root, name))
                                except PermissionError:
                                    pass
                            for name in dirs:
                                try:
                                    os.rmdir(os.path.join(root, name))
                                except (PermissionError, OSError):
                                    pass
        os.makedirs(report_dir, exist_ok=True)
        
        # 1. .platform
        platform = {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
            "metadata": {
                "type": "Report",
                "displayName": report_name
            },
            "config": {
                "version": "2.0",
                "logicalId": str(uuid.uuid4())
            }
        }
        _write_json(os.path.join(report_dir, '.platform'), platform)
        
        # 2. definition.pbir (PBIR v4.0, schema 2.0.0, points to SemanticModel)
        report_definition = {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
            "version": "4.0",
            "datasetReference": {
                "byPath": {
                    "path": f"../{report_name}.SemanticModel"
                }
            }
        }
        _write_json(os.path.join(report_dir, 'definition.pbir'), report_definition)
        
        # 3. definition/ folder
        def_dir = os.path.join(report_dir, 'definition')
        os.makedirs(def_dir, exist_ok=True)
        
        # 3a. version.json
        version_json = {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/versionMetadata/1.0.0/schema.json",
            "version": "2.0.0"
        }
        _write_json(os.path.join(def_dir, 'version.json'), version_json)
        
        # 3b. report.json (schema 3.1.0 — format PBI Hero)
        #     Generate custom theme from extracted dashboard colors
        theme_data = None
        dashboards = converted_objects.get('dashboards', [])
        for db in dashboards:
            t = db.get('theme')
            if t and t.get('colors'):
                theme_data = t
                break

        custom_theme = tmdl_generator.generate_theme_json(theme_data)

        report_json = {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/3.1.0/schema.json",
            "themeCollection": {
                "baseTheme": {
                    "name": "CY24SU06",
                    "reportVersionAtImport": {
                        "visual": "1.8.50",
                        "report": "2.0.50",
                        "page": "1.3.50"
                    },
                    "type": "SharedResources"
                }
            },
            "resourcePackages": [
                {
                    "name": "SharedResources",
                    "type": "SharedResources",
                    "items": [
                        {
                            "name": "CY24SU06",
                            "path": "BaseThemes/CY24SU06.json",
                            "type": "BaseTheme"
                        }
                    ]
                }
            ],
            "settings": {
                "hideVisualContainerHeader": True,
                "useStylableVisualContainerHeader": True,
                "exportDataMode": "None",
                "defaultDrillFilterOtherVisuals": True,
                "allowChangeFilterTypes": True,
                "useEnhancedTooltips": True
            }
        }

        # Add custom theme reference if theme data was found
        if theme_data:
            report_json["resourcePackages"].append({
                "name": "MigrationTheme",
                "type": "CustomTheme",
                "items": [
                    {
                        "name": "QlikMigrationTheme",
                        "path": "RegisteredResources/QlikMigrationTheme.json",
                        "type": "CustomTheme"
                    }
                ]
            })
            report_json["themeCollection"]["customTheme"] = {
                "name": "QlikMigrationTheme",
                "reportVersionAtImport": {
                    "visual": "1.8.50",
                    "report": "2.0.50",
                    "page": "1.3.50"
                },
                "type": "CustomTheme"
            }
        
        # Source parameters are inlined as constant values in DAX
        # calculated measures/columns. No report filters are generated because
        # parameters do not correspond to filterable data columns.

        # Wire bookmarks from stories into report.json
        stories = converted_objects.get('stories', [])
        all_bookmarks = []
        if stories:
            story_bookmarks = self._create_bookmarks(stories)
            all_bookmarks.extend(story_bookmarks)

        # Wire dynamic zone visibility bookmarks from worksheets
        dz_bookmarks = self._create_dynamic_zone_bookmarks(
            converted_objects.get('worksheets', [])
        )
        all_bookmarks.extend(dz_bookmarks)

        if all_bookmarks:
            # PBIR report schema 3.1.0 rejects a root-level "bookmarks" property.
            # Persist generated bookmarks in a sidecar file for migration traceability.
            _write_json(
                os.path.join(def_dir, 'bookmarks.generated.json'),
                {"bookmarks": all_bookmarks}
            )
        
        _write_json(os.path.join(def_dir, 'report.json'), report_json)
        
        # Write custom theme file if theme data was found
        if theme_data:
            res_dir = os.path.join(def_dir, 'RegisteredResources')
            _write_json(os.path.join(res_dir, 'QlikMigrationTheme.json'), custom_theme)
        
        # 4. Create pages with visuals
        pages_dir = os.path.join(def_dir, 'pages')
        os.makedirs(pages_dir, exist_ok=True)
        
        worksheets = converted_objects.get('worksheets', [])
        
        page_names = []
        
        # Pre-build tooltip page mapping for viz-in-tooltip binding
        # tooltip_page_map: worksheet_name → tooltip_page_name
        tooltip_page_map = {}
        
        if dashboards:
            for db_idx, db in enumerate(dashboards):
                page_name = f"ReportSection{uuid.uuid4().hex[:20]}" if db_idx > 0 else "ReportSection"
                page_display_name = db.get('name', f'Page {db_idx + 1}')
                page_names.append(page_name)
                
                # Create the page folder
                page_dir = os.path.join(pages_dir, page_name)
                os.makedirs(page_dir, exist_ok=True)
                
                # Get the size
                size = db.get('size', {})
                page_width = size.get('width', 1280)
                page_height = size.get('height', 720)
                
                page_json = {
                    "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.0.0/schema.json",
                    "name": page_name,
                    "displayName": page_display_name,
                    "displayOption": "FitToPage",
                    "height": page_height,
                    "width": page_width
                }
                
                # Add page-level filters from dashboard filters
                db_filters = list(db.get('filters', []))
                # Also promote context filters from worksheets to page level
                for ws in worksheets:
                    for f in ws.get('filters', []):
                        if f.get('is_context', False):
                            db_filters.append(f)
                if db_filters:
                    page_filters = self._create_visual_filters(db_filters)
                    if page_filters:
                        page_json["filterConfig"] = {"filters": page_filters}

                # Add background image from dashboard metadata
                bg_img = db.get('backgroundImage', {})
                if bg_img and isinstance(bg_img, dict) and bg_img.get('url'):
                    page_json["background"] = {
                        "image": {
                            "url": bg_img['url'],
                            "name": "BackgroundImage",
                        },
                        "transparency": bg_img.get('transparency', 0),
                    }
                
                _write_json(os.path.join(page_dir, 'page.json'), page_json)
                
                # Create visuals
                visuals_dir = os.path.join(page_dir, 'visuals')
                os.makedirs(visuals_dir, exist_ok=True)
                
                db_objects = db.get('objects', [])
                visual_count = 0
                
                # Build a calc_id → caption lookup for slicers
                calcs = converted_objects.get('calculations', [])
                calc_id_to_caption = {}
                for c in calcs:
                    cname = c.get('name', '').strip('[]')
                    ccaption = c.get('caption', '')
                    if cname and ccaption:
                        calc_id_to_caption[cname] = ccaption
                
                # Compute scale factor from source to Power BI pixels
                max_x = max((o.get('position', {}).get('x', 0) + o.get('position', {}).get('w', 0) for o in db_objects), default=page_width)
                max_y = max((o.get('position', {}).get('y', 0) + o.get('position', {}).get('h', 0) for o in db_objects), default=page_height)
                scale_x = page_width / max(max_x, 1)
                scale_y = page_height / max(max_y, 1)
                
                for obj in db_objects:
                    if obj.get('type') == 'worksheetReference':
                        ws_name = obj.get('worksheetName', '')
                        ws_data = self._find_worksheet(worksheets, ws_name)
                        self._create_visual_worksheet(visuals_dir, ws_data, obj,
                                                       scale_x, scale_y, visual_count,
                                                       worksheets, converted_objects,
                                                       tooltip_page_map=tooltip_page_map)
                        visual_count += 1
                    
                    elif obj.get('type') == 'text':
                        self._create_visual_textbox(visuals_dir, obj, scale_x, scale_y, visual_count)
                        visual_count += 1
                    
                    elif obj.get('type') == 'image':
                        self._create_visual_image(visuals_dir, obj, scale_x, scale_y, visual_count)
                        visual_count += 1
                    
                    elif obj.get('type') == 'filter_control':
                        self._create_visual_filter_control(visuals_dir, obj, scale_x, scale_y,
                                                            visual_count, calc_id_to_caption,
                                                            converted_objects)
                        visual_count += 1
                
                # Create action buttons for URL and sheet-navigate actions
                actions = converted_objects.get('actions', [])
                if actions:
                    # Filter actions relevant to this dashboard
                    db_name = db.get('name', '')
                    db_actions = [a for a in actions if a.get('type') in ('url', 'sheet-navigate')
                                  and (not a.get('source_worksheet') or a.get('source_worksheet') == db_name
                                       or any(o.get('worksheetName') == a.get('source_worksheet') for o in db_objects))]
                    if db_actions:
                        created = self._create_action_visuals(visuals_dir, db_actions,
                                                               scale_x, scale_y, visual_count,
                                                               page_display_name)
                        visual_count += created

                # Create slicer for Pages shelf (play-axis animation)
                pages_shelf = db.get('pages_shelf', {})
                if pages_shelf:
                    self._create_pages_shelf_slicer(
                        visuals_dir, pages_shelf, scale_x, scale_y,
                        visual_count, converted_objects)
                    visual_count += 1
                
                print(f"  📊 Page '{page_display_name}': {visual_count} visuals created")
        
        # Fallback: default page
        if not page_names or (dashboards and all(len(d.get('objects', [])) == 0 for d in dashboards)):
            page_name = "ReportSection"
            page_names = [page_name]
            
            page_dir = os.path.join(pages_dir, page_name)
            os.makedirs(page_dir, exist_ok=True)
            
            page_json = {
                "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.0.0/schema.json",
                "name": page_name,
                "displayName": "Qlik Migration",
                "displayOption": "FitToPage",
                "height": 720,
                "width": 1280
            }
            _write_json(os.path.join(page_dir, 'page.json'), page_json)
            
            visuals_dir = os.path.join(page_dir, 'visuals')
            os.makedirs(visuals_dir, exist_ok=True)
            
            x, y = 10, 10
            for idx, ws in enumerate(worksheets):
                visual_id = uuid.uuid4().hex[:20]
                visual_dir = os.path.join(visuals_dir, visual_id)
                
                visual_type = ws.get('chart_type', 'clusteredBarChart')
                ws_name = ws.get('name', f'Visual {idx+1}')

                # Validate scatter chart has measures for X/Y
                if visual_type == 'scatterChart':
                    skip_names = {'Measure Names', 'Measure Values', 'Multiple Values',
                                  ':Measure Names', ':Measure Values'}
                    fields = ws.get('fields', [])
                    has_measure = any(
                        self._is_measure_field(self._clean_field_name(f.get('name', '')))
                        for f in fields
                        if self._clean_field_name(f.get('name', '')) not in skip_names
                    )
                    if not has_measure:
                        visual_type = 'table'
                
                visual_json = {
                    "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.5.0/schema.json",
                    "name": visual_id,
                    "position": {
                        "x": x,
                        "y": y,
                        "z": idx * 1000,
                        "height": 200,
                        "width": 300,
                        "tabOrder": idx * 1000
                    },
                    "visual": {
                        "visualType": visual_type,
                        "drillFilterOtherVisuals": True
                    }
                }
                
                if ws.get('fields'):
                    query = self._build_visual_query(ws)
                    if query:
                        visual_json["visual"]["query"] = query
                
                _write_json(os.path.join(visual_dir, 'visual.json'), visual_json, ensure_ascii=False)
                
                x += 320
                if x > 1000:
                    x = 10
                    y += 220
            
            print(f"  📊 Default page: {len(worksheets)} visuals created")
        
        # 5b. Tooltip pages — worksheets with viz_in_tooltip data
        # Build a mapping: worksheet_name → tooltip_page_name for binding
        tooltip_page_map = {}  # viz_in_tooltip source worksheet → tooltip page name
        tooltip_worksheets = [ws for ws in worksheets if ws.get('tooltip', {}).get('viz_in_tooltip')]
        # Also check tooltips list for viz_in_tooltip entries
        if not tooltip_worksheets:
            tooltip_worksheets = []
            for ws in worksheets:
                tooltips = ws.get('tooltips', [])
                if isinstance(tooltips, list):
                    for tip in tooltips:
                        if isinstance(tip, dict) and tip.get('type') == 'viz_in_tooltip':
                            tooltip_worksheets.append(ws)
                            break
        
        for tip_ws in tooltip_worksheets:
            tip_name = f"Tooltip_{uuid.uuid4().hex[:12]}"
            tip_display = f"Tooltip - {tip_ws.get('name', 'Tooltip')}"
            page_names.append(tip_name)
            # Track tooltip page for visual binding
            tooltip_page_map[tip_ws.get('name', '')] = tip_name
            # Also map from viz_in_tooltip references
            tooltips = tip_ws.get('tooltips', [])
            if isinstance(tooltips, list):
                for tip in tooltips:
                    if isinstance(tip, dict) and tip.get('type') == 'viz_in_tooltip':
                        tooltip_page_map[tip.get('worksheet', '')] = tip_name

            tip_dir = os.path.join(pages_dir, tip_name)
            os.makedirs(tip_dir, exist_ok=True)

            tip_page = {
                "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.0.0/schema.json",
                "name": tip_name,
                "displayName": tip_display,
                "displayOption": "FitToPage",
                "height": 320,
                "width": 480,
                "pageType": "Tooltip"
            }
            _write_json(os.path.join(tip_dir, 'page.json'), tip_page)

            # Create a visual for the tooltip
            tip_visuals_dir = os.path.join(tip_dir, 'visuals')
            os.makedirs(tip_visuals_dir, exist_ok=True)
            self._create_visual_worksheet(
                tip_visuals_dir, tip_ws,
                {'type': 'worksheetReference', 'worksheetName': tip_ws.get('name', ''),
                 'position': {'x': 0, 'y': 0, 'w': 480, 'h': 320}},
                1.0, 1.0, 0, worksheets, converted_objects
            )
            print(f"  💡 Tooltip page '{tip_display}' created")

        # 5c. Mobile layout pages — from device layouts (phone/tablet)
        if dashboards:
            for db_idx, db in enumerate(dashboards):
                device_layouts = db.get('device_layouts', [])
                for dl in device_layouts:
                    device_type = dl.get('device_type', '')
                    if device_type == 'phone' and not dl.get('auto_generated', False):
                        mobile_page_name = f"MobileLayout_{uuid.uuid4().hex[:12]}"
                        mobile_display = f"{db.get('name', 'Dashboard')} (Phone)"
                        page_names.append(mobile_page_name)
                        
                        mobile_dir = os.path.join(pages_dir, mobile_page_name)
                        os.makedirs(mobile_dir, exist_ok=True)
                        
                        mobile_page = {
                            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.0.0/schema.json",
                            "name": mobile_page_name,
                            "displayName": mobile_display,
                            "displayOption": "FitToPage",
                            "height": 568,
                            "width": 320,
                        }
                        _write_json(os.path.join(mobile_dir, 'page.json'), mobile_page)
                        
                        # Create visuals for visible zones
                        mobile_visuals_dir = os.path.join(mobile_dir, 'visuals')
                        os.makedirs(mobile_visuals_dir, exist_ok=True)
                        
                        vis_count = 0
                        for zone in dl.get('zones', []):
                            zone_name = zone.get('name', '')
                            ws_data = self._find_worksheet(worksheets, zone_name)
                            if ws_data:
                                self._create_visual_worksheet(
                                    mobile_visuals_dir, ws_data,
                                    {'type': 'worksheetReference', 'worksheetName': zone_name,
                                     'position': zone.get('position', {'x': 0, 'y': vis_count * 200, 'w': 320, 'h': 200})},
                                    1.0, 1.0, vis_count, worksheets, converted_objects
                                )
                                vis_count += 1
                        
                        print(f"  📱 Mobile layout page '{mobile_display}': {vis_count} visuals")

        # 5d. Drill-through pages — from filter actions targeting specific worksheets
        self._create_drillthrough_pages(pages_dir, page_names, worksheets,
                                        converted_objects)
        pages_metadata = {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.0.0/schema.json",
            "pageOrder": page_names,
            "activePageName": page_names[0] if page_names else ""
        }
        _write_json(os.path.join(pages_dir, 'pages.json'), pages_metadata)
        
        # Post-generation cleanup: remove stale visual directories (OneDrive lock leftovers)
        for page_name in page_names:
            visuals_dir = os.path.join(pages_dir, page_name, 'visuals')
            if os.path.isdir(visuals_dir):
                for vdir in os.listdir(visuals_dir):
                    vpath = os.path.join(visuals_dir, vdir)
                    if os.path.isdir(vpath) and not os.path.exists(os.path.join(vpath, 'visual.json')):
                        try:
                            shutil.rmtree(vpath)
                        except (PermissionError, OSError):
                            pass  # Skip if still locked
        
        return report_dir
    
    def _build_field_mapping(self, converted_objects):
        """Builds the mapping from source fields to the Power BI model.
        
        Solves 2 problems:
        1. Visuals reference the source internal ID (e.g. federated.xxx) instead
           of the Power BI table name (e.g. CORN, cities.csv)
        2. Visuals reference source calculation IDs (e.g. Calculation_114...)
           instead of the Power BI measure name (e.g. Filiere, Lat_upgrade)
        
        Tables are now all real physical tables.
        Measures are on the main table (the one with the most columns).
        
        Creates self._field_map: {raw_field_name: (table_name, property_name)}
        """
        self._field_map = {}
        
        datasources = converted_objects.get('datasources', [])
        
        # Phase 1: Collect deduplicated physical tables
        best_tables = {}
        for ds in datasources:
            tables = ds.get('tables', [])
            # Extract physical columns from datasource-level list (excluding calculations)
            ds_cols = [c for c in ds.get('columns', []) if not c.get('calculation')]
            for table in tables:
                tname = table.get('name', '?')
                if not tname or tname == 'Unknown':
                    continue
                # Inherit datasource-level columns into tables that have none
                # (common for Extracts: single table with columns at DS level)
                if not table.get('columns') and ds_cols and len(tables) == 1:
                    # Clean DS-level columns: strip bracket notation and skip special columns
                    cleaned_cols = []
                    for c in ds_cols:
                        raw = c.get('name', '')
                        if raw.startswith('[:') or not raw:
                            continue  # Skip special columns (e.g. [:Measure Names])
                        clean = dict(c)
                        clean['name'] = raw.strip('[]')
                        cleaned_cols.append(clean)
                    table['columns'] = cleaned_cols
                if tname not in best_tables or len(table.get('columns', [])) > len(best_tables[tname].get('columns', [])):
                    best_tables[tname] = table
        
        # Phase 2: Identify the main table (the one with the most columns)
        main_table = None
        max_cols = 0
        for tname, t in best_tables.items():
            ncols = len(t.get('columns', []))
            if ncols > max_cols:
                max_cols = ncols
                main_table = tname
        
        # Phase 3: Map columns of each physical table
        #   Also track physical measure columns (role='measure' from source)
        for tname, t in best_tables.items():
            for col in t.get('columns', []):
                cname = col.get('name', '?')
                self._field_map[cname] = (tname, cname)
                # Also index by caption for visual references using display name
                caption = col.get('caption', '')
                if caption and caption not in self._field_map:
                    self._field_map[caption] = (tname, cname)
        
        # Phase 4: Map source calculations (rawID -> caption/friendly name)
        # Measures are on the main table
        measures_table = main_table or 'Table'
        self._measure_names = set()  # Track which fields are measures (not dimensions) — for bucket assignment
        self._bim_measure_names = set()  # Track only named BIM measures — for Measure vs Column wrapper

        # Phase 4a: Physical columns with role='measure' (from source data)
        #   These go into _measure_names for visual bucket classification (Y not Category)
        #   but NOT into _bim_measure_names (they're physical columns, not DAX measures)
        for tname, t in best_tables.items():
            for col in t.get('columns', []):
                if col.get('role', '') == 'measure':
                    cname = col.get('name', '?')
                    self._measure_names.add(cname)

        # Phase 4b: Calculated measures — these are both visual measures AND BIM measures
        for ds in datasources:
            for calc in ds.get('calculations', []):
                raw_name = calc.get('name', '').replace('[', '').replace(']', '')
                caption = calc.get('caption', raw_name)
                if raw_name not in self._field_map:
                    self._field_map[raw_name] = (measures_table, caption)
                # Also index by caption for filters using the readable name
                if caption and caption not in self._field_map:
                    self._field_map[caption] = (measures_table, caption)
                # Track measure names for Category vs Y assignment
                if calc.get('role', '') == 'measure':
                    self._measure_names.add(raw_name)
                    self._bim_measure_names.add(raw_name)
                    if caption:
                        self._measure_names.add(caption)
                        self._bim_measure_names.add(caption)
        
        # Also gather measure names from top-level calculations
        for calc in converted_objects.get('calculations', []):
            if calc.get('role', '') == 'measure':
                raw_name = calc.get('name', '').replace('[', '').replace(']', '')
                caption = calc.get('caption', raw_name)
                self._measure_names.add(raw_name)
                self._bim_measure_names.add(raw_name)
                if caption:
                    self._measure_names.add(caption)
                    self._bim_measure_names.add(caption)
        
        # Phase 5: Map extracted groups (BIM-generated calculated columns)
        groups = converted_objects.get('groups', [])
        for g in groups:
            group_name = g.get('name', '').replace('[', '').replace(']', '')
            if group_name and group_name not in self._field_map:
                self._field_map[group_name] = (measures_table, group_name)
        
        # Save the main table for fallback
        self._main_table = measures_table
    
    def _is_measure_field(self, field_name):
        """Check if a field is a measure (aggregate) vs a dimension"""
        clean = field_name.replace('[', '').replace(']', '')
        if hasattr(self, '_measure_names') and clean in self._measure_names:
            return True
        # Resolve via field_map and check the resolved name
        if hasattr(self, '_field_map') and clean in self._field_map:
            _, prop = self._field_map[clean]
            if hasattr(self, '_measure_names') and prop in self._measure_names:
                return True
        return False

    def _pick_fallback_column(self):
        """Pick a meaningful fallback column from the model field map.

        Prefers date or ID columns over arbitrary first-inserted columns
        so the visual shows something useful rather than a random field.
        """
        if not hasattr(self, '_field_map') or not self._field_map:
            return 'Column'
        candidates = list(self._field_map.keys())
        # Prefer date columns
        for c in candidates:
            cl = c.lower()
            if 'date' in cl or 'year' in cl or 'month' in cl:
                return c
        # Then ID columns
        for c in candidates:
            cl = c.lower()
            if cl.endswith('id') or cl.endswith('_id') or cl.startswith('id_'):
                return c
        # Then name columns
        for c in candidates:
            if 'name' in c.lower() or 'nom' in c.lower():
                return c
        return candidates[0]
    
    def _clean_field_name(self, name):
        """Strip all known source derivation prefixes from a field name"""
        # Coerce non-string names (some Qlik exports embed dicts/lists)
        if not isinstance(name, str):
            if isinstance(name, dict):
                name = name.get('name') or name.get('field') or name.get('qName') or ''
            elif isinstance(name, (list, tuple)) and name:
                name = name[0]
            name = str(name) if name is not None else ''
        # Remove derivation prefixes (none:, usr:, yr:, tmn:, etc.)
        clean = re.sub(r'^(none|sum|avg|count|min|max|usr|yr|mn|dy|qr|wk|attr|md|mdy|hms|hr|mt|sc|thr|trunc|tmn):',
                        '', name)
        # Remove type suffixes (:nk, :qk, :ok, :fn, :tn)
        clean = re.sub(r':(nk|qk|ok|fn|tn)$', '', clean)
        return clean

    def _build_visual_query(self, ws_data):
        """Builds a query with queryState for a visual (PBIR v4.0 format)"""
        fields = ws_data.get('fields', [])
        if not fields:
            return None
        
        # Clean field names and filter out meta-fields and generated geo fields
        skip_names = {'Measure Names', 'Measure Values', 'Multiple Values',
                      ':Measure Names', ':Measure Values',
                      'Longitude (generated)', 'Latitude (generated)'}
        cleaned_fields = []
        seen_names = set()
        for f in fields:
            raw_name = f.get('name', '')
            clean = self._clean_field_name(raw_name)
            raw_str = raw_name if isinstance(raw_name, str) else clean
            if clean in skip_names or raw_str in skip_names:
                continue
            # Deduplicate: same field from different shelves
            if clean in seen_names:
                continue
            seen_names.add(clean)
            cleaned_fields.append({**f, 'name': clean})
        
        if not cleaned_fields:
            return None

        # Filter out fields that don't resolve to any table in the model.
        # This prevents Missing_References errors for Qlik runtime-only fields
        # (e.g. fields created by the load script at reload but absent from
        # the static metadata extracted from the binary export).
        if hasattr(self, '_field_map'):
            validated_fields = []
            for f in cleaned_fields:
                clean = f['name']
                if clean in self._field_map:
                    validated_fields.append(f)
                elif hasattr(self, '_bim_measure_names') and clean in self._bim_measure_names:
                    validated_fields.append(f)
                elif hasattr(self, '_measure_names') and clean in self._measure_names:
                    validated_fields.append(f)
                else:
                    logger.debug("Visual field '%s' not in model — skipping binding", clean)
            cleaned_fields = validated_fields
            if not cleaned_fields:
                # All original fields are unresolvable — bind to a meaningful
                # column from the model (prefer date or ID columns over arbitrary first).
                if self._field_map:
                    fallback_col = self._pick_fallback_column()
                    cleaned_fields = [{'name': fallback_col, 'role': 'dimension'}]
                else:
                    return None
        
        query_state = {}
        
        # Separate dimensions (→ Category) from measures (→ Y/Size)
        # Use _measure_names set for accurate classification
        dim_fields = []
        mea_fields = []
        for f in cleaned_fields:
            if self._is_measure_field(f['name']):
                mea_fields.append(f)
            else:
                dim_fields.append(f)
        
        visual_type = ws_data.get('chart_type', 'clusteredBarChart')
        
        if visual_type in ('filledMap', 'map'):
            if dim_fields:
                query_state["Category"] = self._make_projection(dim_fields[0])
            if mea_fields:
                query_state["Size"] = self._make_projection(mea_fields[0])
        elif visual_type in ('tableEx', 'table'):
            all_fields = dim_fields + mea_fields
            if all_fields:
                query_state["Values"] = {
                    "projections": [self._make_projection_entry(f) for f in all_fields]
                }
        elif visual_type in ('pivotTable', 'matrix'):
            # Power BI's matrix visual (visualType "pivotTable") uses the
            # Rows / Columns / Values data roles. Emitting Category/Y here
            # leaves every well empty and PBI rejects the visual with
            # DataViewMappingError_ConditionRangeTooSmall ("too few columns
            # in the Values bucket"). First dim → Rows, second dim → Columns,
            # measures → Values.
            if dim_fields:
                query_state["Rows"] = self._make_projection(dim_fields[0])
            if len(dim_fields) >= 2:
                query_state["Columns"] = self._make_projection(dim_fields[1])
            if mea_fields:
                query_state["Values"] = {
                    "projections": [self._make_projection_entry(m) for m in mea_fields[:6]]
                }
            elif len(dim_fields) >= 2:
                # No measures: keep Rows as the grouping and place the
                # remaining dimensions in Values so the matrix still renders.
                query_state["Values"] = {
                    "projections": [self._make_projection_entry(d) for d in dim_fields[1:]]
                }
        elif visual_type == 'scatterChart':
            # Scatter chart: dims → Category (Details), measures → X/Y (aggregated)
            if dim_fields:
                query_state["Category"] = self._make_projection(dim_fields[0])
            if len(mea_fields) >= 2:
                query_state["X"] = self._make_scatter_axis_projection(mea_fields[0])
                query_state["Y"] = self._make_scatter_axis_projection(mea_fields[1])
            elif len(mea_fields) == 1:
                query_state["Y"] = self._make_scatter_axis_projection(mea_fields[0])
            # If 3+ measures, third becomes Size (bubble)
            if len(mea_fields) >= 3:
                query_state["Size"] = self._make_scatter_axis_projection(mea_fields[2])
        elif visual_type in ('gauge', 'kpi'):
            # Gauge/KPI: first measure → Value, second → Target
            if mea_fields:
                query_state["Y"] = self._make_projection(mea_fields[0])
            if len(mea_fields) >= 2:
                query_state["TargetValue"] = self._make_projection(mea_fields[1])
            if dim_fields:
                query_state["Category"] = self._make_projection(dim_fields[0])
        elif visual_type in ('card', 'multiRowCard'):
            # Card: measures → Values
            all_fields = mea_fields if mea_fields else dim_fields
            if all_fields:
                query_state["Values"] = {
                    "projections": [self._make_projection_entry(f) for f in all_fields[:6]]
                }
        elif visual_type in ('pieChart', 'donutChart', 'funnel', 'treemap'):
            # Pie/Donut/Funnel/Treemap: dim → Category, measure → Values
            if dim_fields:
                query_state["Category"] = self._make_projection(dim_fields[0])
            if mea_fields:
                query_state["Y"] = self._make_projection(mea_fields[0])
        elif visual_type in ('lineClusteredColumnComboChart', 'lineStackedColumnComboChart'):
            # Combo: dim → Category, first measure → ColumnY, second → LineY
            if dim_fields:
                query_state["Category"] = self._make_projection(dim_fields[0])
            if mea_fields:
                query_state["ColumnY"] = self._make_projection(mea_fields[0])
            if len(mea_fields) >= 2:
                query_state["LineY"] = self._make_projection(mea_fields[1])
        elif visual_type == 'waterfallChart':
            # Waterfall: dim → Category, measure → Y, optional breakdown
            if dim_fields:
                query_state["Category"] = self._make_projection(dim_fields[0])
            if mea_fields:
                query_state["Y"] = self._make_projection(mea_fields[0])
            if len(dim_fields) >= 2:
                query_state["Breakdown"] = self._make_projection(dim_fields[1])
        elif visual_type == 'boxAndWhisker':
            # Box plot: dim → Category, measure → Value
            if dim_fields:
                query_state["Category"] = self._make_projection(dim_fields[0])
            if mea_fields:
                query_state["Value"] = self._make_projection(mea_fields[0])
        else:
            # Standard charts: dimensions → Category, measures → Y
            if dim_fields:
                query_state["Category"] = self._make_projection(dim_fields[0])
            if mea_fields:
                query_state["Y"] = self._make_projection(mea_fields[0])
            # If no measures found but we have multiple dims, use last as Y
            elif len(dim_fields) > 1:
                query_state["Y"] = self._make_projection(dim_fields[-1])
        
        return {"queryState": query_state} if query_state else None
    
    def _make_projection(self, field):
        """Creates a simple projection for a field"""
        return {
            "projections": [self._make_projection_entry(field)]
        }

    def _make_scatter_axis_projection(self, field):
        """Creates a projection for scatter chart X/Y/Size axes.
        BIM measures use Measure wrapper; physical columns use Aggregation
        wrapper (Sum) since scatter axes require explicit aggregation."""
        return {
            "projections": [self._make_scatter_axis_entry(field)]
        }

    def _make_scatter_axis_entry(self, field):
        """Creates projection entry for scatter chart axes.
        Named DAX measures → Measure wrapper.
        Physical columns → Aggregation wrapper with Function 0 (Sum)."""
        raw_name = field.get('name', 'Field')
        clean_name = self._clean_field_name(raw_name)

        if hasattr(self, '_field_map') and clean_name in self._field_map:
            entity, prop = self._field_map[clean_name]
        else:
            entity = field.get('datasource', 'Table')
            prop = clean_name

        is_bim_measure = hasattr(self, '_bim_measure_names') and (
            clean_name in self._bim_measure_names or prop in self._bim_measure_names
        )

        if is_bim_measure:
            # A measure may have been renamed to avoid a measure/column name
            # collision (e.g. Profit -> Total Profit). Bind to the new name.
            renames = getattr(self, '_measure_renames', None)
            if renames and prop in renames:
                prop = renames[prop]
            field_ref = {
                "Measure": {
                    "Expression": {"SourceRef": {"Entity": entity}},
                    "Property": prop
                }
            }
        else:
            # Physical column: wrap as Aggregation (Sum) for scatter axes
            field_ref = {
                "Aggregation": {
                    "Expression": {
                        "Column": {
                            "Expression": {"SourceRef": {"Entity": entity}},
                            "Property": prop
                        }
                    },
                    "Function": 0
                }
            }

        return {
            "field": field_ref,
            "queryRef": f"{entity}.{prop}",
            "active": True
        }
    
    def _make_projection_entry(self, field):
        """Creates a projection entry for a field, resolved to the Power BI model.
        Uses 'Measure' wrapper for named BIM measures, 'Column' wrapper for
        physical columns (PBI Desktop auto-aggregates numeric columns in value buckets)."""
        raw_name = field.get('name', 'Field')
        
        # Clean all known source prefixes
        clean_name = self._clean_field_name(raw_name)
        
        # Resolve via mapping
        if hasattr(self, '_field_map') and clean_name in self._field_map:
            entity, prop = self._field_map[clean_name]
        else:
            # Fallback: use field name as property
            # and search across all tables
            entity = field.get('datasource', 'Table')
            prop = clean_name
        
        # Use Measure wrapper ONLY for named BIM measures (DAX definitions),
        # Column wrapper for everything else (PBI auto-aggregates numeric columns)
        is_bim_measure = hasattr(self, '_bim_measure_names') and (
            clean_name in self._bim_measure_names or prop in self._bim_measure_names
        )
        if is_bim_measure:
            # Honor measure/column collision renames (e.g. Profit -> Total Profit).
            renames = getattr(self, '_measure_renames', None)
            if renames and prop in renames:
                prop = renames[prop]
        field_type = "Measure" if is_bim_measure else "Column"
        
        return {
            "field": {
                field_type: {
                    "Expression": {
                        "SourceRef": {
                            "Entity": entity
                        }
                    },
                    "Property": prop
                }
            },
            "queryRef": f"{entity}.{prop}",
            "active": True
        }
    
    def _create_bookmarks(self, stories):
        """Converts source stories/bookmarks to Power BI bookmarks.

        Generates bookmark entries with filter state from Qlik selections.
        """
        bookmarks = []
        for story in stories:
            story_name = story.get('name', 'Story')
            for sp_idx, sp in enumerate(story.get('story_points', [])):
                caption = sp.get('caption', f'{story_name} - Point {sp_idx + 1}')
                bookmark = {
                    "name": f"Bookmark_{uuid.uuid4().hex[:12]}",
                    "displayName": caption,
                    "explorationState": {
                        "version": "1.0"
                    }
                }
                # Add captured filters if available
                if sp.get('filters_state'):
                    bookmark["explorationState"]["activeSection"] = sp.get('captured_sheet', '')
                    # Build filter expressions from selection state
                    filters = []
                    for fs in sp['filters_state']:
                        field = fs.get('field', '')
                        values = fs.get('values', [])
                        if field and values:
                            entity, prop = self._resolve_field_entity(field)
                            filter_entry = {
                                "type": "Categorical",
                                "field": {
                                    "Column": {
                                        "Expression": {"SourceRef": {"Entity": entity}},
                                        "Property": prop
                                    }
                                },
                                "filter": {
                                    "Version": 2,
                                    "From": [{"Name": "b", "Entity": entity, "Type": 0}],
                                    "Where": [{
                                        "Condition": {
                                            "In": {
                                                "Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "b"}}, "Property": prop}}],
                                                "Values": [[{"Literal": {"Value": f"'{v}'"}}] for v in values]
                                            }
                                        }
                                    }]
                                }
                            }
                            filters.append(filter_entry)
                    if filters:
                        bookmark["explorationState"]["filters"] = filters
                bookmarks.append(bookmark)
        return bookmarks

    def _create_dynamic_zone_bookmarks(self, worksheets):
        """Create bookmarks for Qlik dynamic zone visibility conditions.

        In Qlik, dynamic zones show/hide visuals based on expression conditions.
        In Power BI, this maps to bookmark toggle groups where each bookmark
        controls which visuals are visible.

        Returns:
            List of bookmark dicts for report.json.
        """
        bookmarks = []
        for ws in worksheets:
            dz = ws.get('dynamicZone', ws.get('dynamic_zone', {}))
            if not isinstance(dz, dict) or not dz.get('condition'):
                continue
            ws_name = ws.get('name', 'Visual')
            condition = dz.get('condition', '')
            show = dz.get('show', True)
            bookmark = {
                "name": f"bm_{uuid.uuid4().hex[:12]}",
                "displayName": f"Toggle: {ws_name}",
                "explorationState": {
                    "version": "1.0",
                },
                "options": {
                    "targetVisualType": "toggleVisibility",
                },
            }
            # Store condition as annotation for documentation
            bookmark["explorationState"]["annotation"] = (
                f"Qlik dynamic zone condition: {condition} "
                f"(show={show})"
            )
            bookmarks.append(bookmark)
        return bookmarks
    
    def _create_report_filters(self, converted_objects):
        """Creates report-level filters from parameters"""
        report_filters = []
        
        params = converted_objects.get('parameters', [])
        for param in params:
            # Support both extracted (caption/value) and converted (displayName/currentValue) format
            param_name = param.get('displayName', param.get('caption', param.get('name', '')))
            if not param_name:
                continue
            param_name = param_name.replace('[', '').replace(']', '')
            
            current_value = param.get('currentValue', param.get('value', ''))
            if not current_value:
                continue
            
            # Clean quotes
            if isinstance(current_value, str):
                current_value = current_value.strip('"')
            
            # Resolve Entity via _field_map (parameters = measures on main table)
            entity, prop = self._resolve_field_entity(param_name)
            
            filter_obj = {
                "name": f"Filter_{uuid.uuid4().hex[:12]}",
                "type": "Categorical",
                "field": {
                    "Column": {
                        "Expression": {"SourceRef": {"Entity": entity}},
                        "Property": prop
                    }
                },
                "filter": {
                    "Version": 2,
                    "From": [{"Name": "p", "Entity": entity, "Type": 0}],
                    "Where": [{
                        "Condition": {
                            "In": {
                                "Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "p"}}, "Property": prop}}],
                                "Values": [[{"Literal": {"Value": f"'{current_value}'"}}]]
                            }
                        }
                    }]
                }
            }
            report_filters.append(filter_obj)
        
        return report_filters
    
    def _resolve_field_entity(self, field_name):
        """Resolves a field name to (entity_table, property_name) via _field_map"""
        clean = field_name.replace('[', '').replace(']', '')
        if hasattr(self, '_field_map'):
            # Direct match
            if clean in self._field_map:
                return self._field_map[clean]
            # Try without attr:/ prefix
            for prefix in ('attr:', ':'):
                if clean.startswith(prefix) and clean[len(prefix):] in self._field_map:
                    return self._field_map[clean[len(prefix):]]
            # Partial match (calc ID may contain Calculation_xxx)
            for key, val in self._field_map.items():
                if key == clean or val[1] == clean:
                    return val
        # Fallback: use main table (all calc columns are there)
        main = getattr(self, '_main_table', clean)
        return (main, clean)

    def _create_visual_filters(self, filters):
        """Creates visual-level filters from worksheet filters"""
        visual_filters = []
        
        # Source virtual fields that have no PBI equivalent
        skip_fields = {'Measure Names', 'Measure Values', 'Multiple Values',
                       ':Measure Names', ':Measure Values'}
        
        for f in filters:
            field = f.get('field', '')
            if not field:
                continue
            
            # Clean field name (remove brackets)
            clean_field = field.replace('[', '').replace(']', '')
            
            # Skip virtual fields (no PBI column exists)
            if clean_field in skip_fields or field.replace('[', '').replace(']', '') in skip_fields:
                continue
            
            # Resolve Entity (table) and Property (column) via mapping
            entity, prop = self._resolve_field_entity(clean_field)
            
            filter_type = f.get('type', 'categorical')
            
            if filter_type == 'range' or f.get('min') is not None:
                # Range filter (dates, numbers)
                pbi_filter = {
                    "name": f"Filter_{uuid.uuid4().hex[:12]}",
                    "type": "Advanced",
                    "field": {
                        "Column": {
                            "Expression": {"SourceRef": {"Entity": entity}},
                            "Property": prop
                        }
                    },
                    "filter": {
                        "Version": 2,
                        "From": [{"Name": "t", "Entity": entity, "Type": 0}],
                        "Where": []
                    }
                }
                conditions = []
                if f.get('min') is not None:
                    conditions.append({
                        "Comparison": {
                            "ComparisonKind": 2,  # >=
                            "Left": {"Column": {"Expression": {"SourceRef": {"Source": "t"}}, "Property": prop}},
                            "Right": {"Literal": {"Value": f"'{f['min']}'"}} 
                        }
                    })
                if f.get('max') is not None:
                    conditions.append({
                        "Comparison": {
                            "ComparisonKind": 3,  # <=
                            "Left": {"Column": {"Expression": {"SourceRef": {"Source": "t"}}, "Property": prop}},
                            "Right": {"Literal": {"Value": f"'{f['max']}'"}} 
                        }
                    })
                if conditions:
                    pbi_filter["filter"]["Where"] = [{"Condition": c} for c in conditions]
                    visual_filters.append(pbi_filter)
            else:
                # Categorical filter
                values = f.get('values', [])
                is_exclude = f.get('exclude', False)
                
                # Skip categorical filters with no values (empty Where breaks PBI)
                if not values:
                    continue
                
                pbi_filter = {
                    "name": f"Filter_{uuid.uuid4().hex[:12]}",
                    "type": "Categorical",
                    "field": {
                        "Column": {
                            "Expression": {"SourceRef": {"Entity": entity}},
                            "Property": prop
                        }
                    },
                    "filter": {
                        "Version": 2,
                        "From": [{"Name": "t", "Entity": entity, "Type": 0}],
                        "Where": []
                    }
                }
                
                condition = {
                    "In": {
                        "Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "t"}}, "Property": prop}}],
                        "Values": [[{"Literal": {"Value": f"'{v}'"}}] for v in values[:100]]
                    }
                }
                if is_exclude:
                    condition = {"Not": {"Expression": condition}}
                pbi_filter["filter"]["Where"].append({"Condition": condition})
                
                visual_filters.append(pbi_filter)
        
        return visual_filters
    
    def _build_visual_objects(self, ws_name, ws_data, visual_type):
        """Builds visual objects (title, colors, labels, legend, axes)"""
        objects = {}
        
        # Title
        objects["title"] = [{
            "properties": {
                "text": _L(f"'{ws_name}'")
            }
        }]
        
        if not ws_data:
            return objects
        
        formatting = ws_data.get('formatting', {})
        mark_encoding = ws_data.get('mark_encoding', {})
        
        # Data labels — from formatting.mark.mark-labels-show OR mark_encoding.label
        show_labels = False
        mark_fmt = formatting.get('mark', {})
        if isinstance(mark_fmt, dict):
            show_labels = mark_fmt.get('mark-labels-show', '').lower() == 'true'
        if mark_encoding.get('label', {}).get('show'):
            show_labels = True
        
        if show_labels:
            label_props = {
                "show": _L("true")
            }
            # Apply label font size
            label_info = mark_encoding.get('label', {})
            if label_info.get('font_size'):
                label_props["fontSize"] = _L(f"{label_info['font_size']}D")
            if label_info.get('font_color'):
                label_props["color"] = {
                    "solid": {"color": _L(f"'{label_info['font_color']}'")}
                }
            # Map label position (source → PBI)
            pos_map = {'top': "'OutsideEnd'", 'center': "'InsideCenter'", 
                       'bottom': "'InsideBase'", 'left': "'Left'", 'right': "'Right'"}
            if label_info.get('position') and label_info['position'] in pos_map:
                label_props["labelPosition"] = _L(pos_map[label_info['position']])
            objects["labels"] = [{"properties": label_props}]
        
        # Legend (if color encoded on a field)
        color_field = mark_encoding.get('color', {}).get('field', '')
        if color_field and color_field != 'Multiple Values':
            legend_props = {
                "show": _L("true"),
            }
            # Extract legend position from formatting
            legend_fmt = formatting.get('legend', formatting.get('color-legend', {}))
            if isinstance(legend_fmt, dict):
                legend_pos = legend_fmt.get('position', legend_fmt.get('legend-position', ''))
                legend_pos_map = {
                    'right': "'Right'", 'left': "'Left'",
                    'top': "'Top'", 'bottom': "'Bottom'",
                    'top-right': "'TopRight'", 'bottom-right': "'BottomRight'",
                    'top-left': "'TopLeft'", 'bottom-left': "'BottomLeft'",
                }
                if legend_pos.lower() in legend_pos_map:
                    legend_props["position"] = _L(legend_pos_map[legend_pos.lower()])
                else:
                    legend_props["position"] = _L("'Right'")
                # Legend title
                legend_title = legend_fmt.get('title', '')
                if legend_title:
                    legend_props["titleText"] = _L(f"'{legend_title}'")
                    legend_props["showTitle"] = _L("true")
                # Legend font size
                legend_font_size = legend_fmt.get('font-size', '')
                if legend_font_size:
                    legend_props["fontSize"] = _L(f"{legend_font_size}D")
            else:
                legend_props["position"] = _L("'Right'")
            objects["legend"] = [{"properties": legend_props}]
        
        # Label color (from formatting.label.color)
        label_fmt = formatting.get('label', {})
        if isinstance(label_fmt, dict) and label_fmt.get('color'):
            if "labels" not in objects:
                objects["labels"] = [{"properties": {}}]
            objects["labels"][0]["properties"]["color"] = {
                "solid": {"color": _L(f"'{label_fmt['color']}'")}
            }
        
        # Axis display (formatting.axis.display)
        axis_fmt = formatting.get('axis', {})
        if isinstance(axis_fmt, dict):
            axis_display = axis_fmt.get('display', 'true')
            show_axis = axis_display.lower() != 'none' if axis_display else True
            if show_axis:
                objects["categoryAxis"] = [{
                    "properties": {
                        "show": _L("true")
                    }
                }]
                objects["valueAxis"] = [{
                    "properties": {
                        "show": _L("true")
                    }
                }]
        
        # Explicit axes (if extracted)
        axes_data = ws_data.get('axes', {})
        if axes_data:
            x_axis = axes_data.get('x', {})
            if x_axis:
                cat_props = {
                    "show": _L("true")
                }
                if x_axis.get('title'):
                    cat_props["titleText"] = _L(f"'{x_axis['title']}'")
                    cat_props["showAxisTitle"] = _L("true")
                if x_axis.get('reversed'):
                    cat_props["reverseOrder"] = _L("true")
                objects["categoryAxis"] = [{"properties": cat_props}]
                
            y_axis = axes_data.get('y', {})
            if y_axis:
                val_props = {
                    "show": _L("true")
                }
                if y_axis.get('title'):
                    val_props["titleText"] = _L(f"'{y_axis['title']}'")
                    val_props["showAxisTitle"] = _L("true")
                # Apply axis range (min/max)
                if not y_axis.get('auto_range', True):
                    if y_axis.get('range_min') is not None:
                        val_props["start"] = _L(f"{y_axis['range_min']}D")
                    if y_axis.get('range_max') is not None:
                        val_props["end"] = _L(f"{y_axis['range_max']}D")
                # Apply log scale
                if y_axis.get('scale') == 'log':
                    val_props["axisScale"] = _L("'Log'")
                # Apply reversed axis
                if y_axis.get('reversed'):
                    val_props["reverseOrder"] = _L("true")
                objects["valueAxis"] = [{"properties": val_props}]
            
            # Dual-axis / combo-chart secondary axis
            if axes_data.get('dual_axis') and visual_type in ('lineClusteredColumnComboChart', 'lineStackedColumnComboChart'):
                y2_props = {
                    "show": _L("true")
                }
                # If synced, set same scale properties
                if axes_data.get('dual_axis_sync'):
                    if not y_axis.get('auto_range', True):
                        if y_axis.get('range_min') is not None:
                            y2_props["start"] = val_props.get("start", {})
                        if y_axis.get('range_max') is not None:
                            y2_props["end"] = val_props.get("end", {})
                    if y_axis.get('scale') == 'log':
                        y2_props["axisScale"] = _L("'Log'")
                objects["y1AxisReferenceLine"] = [{"properties": {}}]  # Marker for combo secondary axis
        
        # Background color
        bg_color = formatting.get('background_color', '')
        if not bg_color and isinstance(formatting.get('pane', {}), dict):
            bg_color = formatting.get('pane', {}).get('background-color', '')
        if bg_color:
            objects["visualContainerStyle"] = [{
                "properties": {
                    "background": {
                        "solid": {"color": _L(f"'{bg_color}'")}
                    }
                }
            }]
        
        # Table/matrix-specific formatting (header font, row banding, grid)
        if visual_type in ('tableEx', 'table', 'matrix'):
            header_style = formatting.get('header_style', formatting.get('column-header_style', {}))
            if isinstance(header_style, dict):
                col_headers_props = {}
                if header_style.get('font-size'):
                    col_headers_props["fontSize"] = _L(f"{header_style['font-size']}D")
                if header_style.get('font-weight') == 'bold':
                    col_headers_props["bold"] = _L("true")
                if header_style.get('font-color'):
                    col_headers_props["fontColor"] = {
                        "solid": {"color": _L(f"'{header_style['font-color']}'")}
                    }
                if col_headers_props:
                    objects["columnHeaders"] = [{"properties": col_headers_props}]
            
            # Row banding (alternating row colors)
            row_style = formatting.get('worksheet_style', {})
            if isinstance(row_style, dict) and row_style.get('band-color'):
                objects["values"] = [{
                    "properties": {
                        "backColor": {
                            "solid": {"color": _L(f"'{row_style['band-color']}'")}
                        }
                    }
                }]
            
            # Grid/border
            if isinstance(header_style, dict) and header_style.get('border-style', 'none') != 'none':
                grid_props = {"show": _L("true")}
                if header_style.get('border-color'):
                    grid_props["color"] = {
                        "solid": {"color": _L(f"'{header_style['border-color']}'")}
                    }
                objects["gridlines"] = [{"properties": grid_props}]
        
        # Conditional formatting (color encoding)
        color_enc = mark_encoding.get('color', {})
        color_mode = color_enc.get('type', '')  # 'quantitative' → gradient, 'categorical' → distinct
        if color_mode == 'quantitative' or color_enc.get('palette', ''):
            # Data-driven color scale
            palette_colors = color_enc.get('palette_colors', [])
            if len(palette_colors) >= 2:
                # Generate proper PBI gradient rule with min/max/mid colors
                gradient_rule = {
                    "properties": {
                        "fill": {
                            "solid": {"color": _L(f"'{palette_colors[0]}'")}
                        }
                    },
                    "rules": [{
                        "inputRole": "Y",
                        "gradient": {
                            "min": {
                                "color": _L(f"'{palette_colors[0]}'")
                            },
                            "max": {
                                "color": _L(f"'{palette_colors[-1]}'")
                            }
                        }
                    }]
                }
                # Add midpoint color if 3+ colors
                if len(palette_colors) >= 3:
                    mid_color = palette_colors[len(palette_colors) // 2]
                    gradient_rule["rules"][0]["gradient"]["mid"] = {
                        "color": _L(f"'{mid_color}'")
                    }
                objects["dataPoint"] = [gradient_rule]
            elif len(palette_colors) == 1:
                objects["dataPoint"] = [{
                    "properties": {
                        "fill": {
                            "solid": {"color": _L(f"'{palette_colors[0]}'")}
                        }
                    }
                }]
        
        # Reference lines (source reference lines/bands → PBI constant lines)
        ref_lines = ws_data.get('reference_lines', [])
        if ref_lines:
            y_ref_lines = []
            for ref in ref_lines:
                ref_value = ref.get('value', 0)
                ref_label = ref.get('label', '')
                ref_color = ref.get('color', '#666666')
                line_def = {
                    "type": "Constant",
                    "value": str(ref_value),
                    "show": _L("true"),
                    "displayName": _L(f"'{ref_label}'"),
                    "color": {"solid": {"color": _L(f"'{ref_color}'")}},
                    "style": _L("'dashed'")
                }
                y_ref_lines.append(line_def)
            if y_ref_lines:
                if "valueAxis" not in objects:
                    objects["valueAxis"] = [{"properties": {"show": _L("true")}}]
                objects["valueAxis"][0]["properties"]["referenceLine"] = y_ref_lines

        # ── Extended visual config (ported from Fabric) ──────────────

        # Trend lines (analytics pane)
        trend_lines = ws_data.get('trend_lines', [])
        if trend_lines:
            trend_objs = []
            for tl in trend_lines:
                trend_type = tl.get('type', 'linear').capitalize()
                if trend_type not in ('Linear', 'Exponential', 'Logarithmic',
                                      'Polynomial', 'Power', 'MovingAverage'):
                    trend_type = 'Linear'
                trend_obj = {
                    "show": _L("true"),
                    "lineColor": {"solid": {"color": _L(f"'{tl.get('color', '#666666')}'")}}
                }
                if tl.get('show_equation'):
                    trend_obj["displayEquation"] = _L("true")
                if tl.get('show_r_squared'):
                    trend_obj["displayRSquared"] = _L("true")
                trend_objs.append({"properties": trend_obj})
            objects["trend"] = trend_objs

        # Annotations → subtitle text
        annotations = ws_data.get('annotations', [])
        if annotations:
            anno_texts = [a.get('text', '') for a in annotations if a.get('text')]
            if anno_texts:
                subtitle_text = "; ".join(anno_texts[:3])
                objects.setdefault("subTitle", [{"properties": {}}])
                objects["subTitle"][0]["properties"]["show"] = _L("true")
                objects["subTitle"][0]["properties"]["text"] = _L(json.dumps(subtitle_text))

        # Font formatting (family + size from extracted formatting)
        font_props = formatting.get('font', {})
        if isinstance(font_props, dict):
            font_family = font_props.get('family', '')
            font_size = font_props.get('size', '')
            if font_family or font_size:
                if "labels" not in objects:
                    objects["labels"] = [{"properties": {}}]
                if font_family:
                    objects["labels"][0]["properties"]["fontFamily"] = _L(f"'{font_family}'")
                if font_size:
                    try:
                        fs_val = int(float(str(font_size).replace('pt', '').replace('px', '').strip()))
                        objects["labels"][0]["properties"]["fontSize"] = _L(f"{fs_val}D")
                    except (ValueError, TypeError):
                        logger.debug("Could not parse label fontSize: %s", font_size)

        # Enhanced axis config (label rotation, show toggles)
        axes_detail = ws_data.get('axes', {})
        if axes_detail:
            for axis_key, axis_obj_key in [('x', 'categoryAxis'), ('y', 'valueAxis')]:
                ax = axes_detail.get(axis_key, {})
                if not ax:
                    continue
                if axis_obj_key in objects:
                    props = objects[axis_obj_key][0].get("properties", {})
                else:
                    props = {"show": _L("true")}
                if ax.get('show_title') is False:
                    props["showAxisTitle"] = _L("false")
                if ax.get('show_label') is False:
                    props["show"] = _L("false")
                if ax.get('label_rotation'):
                    try:
                        rot = int(float(ax['label_rotation']))
                        if rot != 0:
                            props["labelAngle"] = _L(f"{rot}L")
                    except (ValueError, TypeError):
                        logger.debug("Could not parse axis label_rotation: %s", ax.get('label_rotation'))
                if ax.get('format'):
                    props["labelDisplayUnits"] = _L("'0L'")
                objects[axis_obj_key] = [{"properties": props}]

        # Forecast config (analytics pane)
        forecasts = ws_data.get('forecasting', [])
        if forecasts:
            fc = forecasts[0]
            forecast_obj = {
                "show": _L("true"),
                "forecastLength": _L(f"{fc.get('periods', 5)}L"),
                "confidenceBandStyle": _L("'fill'"),
            }
            ci = fc.get('prediction_interval', '95')
            forecast_obj["confidenceLevel"] = _L(f"'{ci}'")
            if fc.get('ignore_last', '0') != '0':
                forecast_obj["ignoreLast"] = _L(f"{fc['ignore_last']}L")
            objects["forecast"] = [{"properties": forecast_obj}]

        # Map options (washout/transparency + style)
        map_opts = ws_data.get('map_options', {})
        if map_opts and visual_type in ('map', 'filledMap'):
            map_props = {}
            washout = map_opts.get('washout', '0.0')
            try:
                wo_val = float(washout)
                if wo_val > 0:
                    map_props["transparency"] = _L(f"{int(wo_val * 100)}L")
            except (ValueError, TypeError):
                logger.debug("Could not parse map washout: %s", washout)
            style = map_opts.get('style', 'road')
            style_map = {'normal': "'road'", 'light': "'grayscale'",
                         'dark': "'darkGrayscale'", 'satellite': "'aerial'",
                         'streets': "'road'"}
            pbi_style = style_map.get(style.lower(), "'road'")
            map_props["mapStyle"] = _L(pbi_style)
            if map_props:
                objects["mapControl"] = [{"properties": map_props}]

        # Per-value color assignments (categorical color map)
        if not objects.get("dataPoint"):
            color_values = color_enc.get('color_values', {})
            if color_values:
                dp_rules = []
                for val, clr in list(color_values.items())[:20]:
                    dp_rules.append({
                        "properties": {
                            "fill": {"solid": {"color": _L(f"'{clr}'")}}
                        }
                    })
                if dp_rules:
                    objects["dataPoint"] = dp_rules

        # Stepped color thresholds (discrete conditional formatting)
        if not objects.get("dataPoint"):
            color_thresholds = color_enc.get('thresholds', [])
            if color_thresholds and len(color_thresholds) >= 2:
                rules = []
                for thresh in color_thresholds:
                    rule = {"properties": {
                        "fill": {"solid": {"color": _L(
                            f"'{thresh.get('color', '#cccccc')}'")}}
                    }}
                    if thresh.get('value') is not None:
                        rule["properties"]["inputValue"] = _L(f"{thresh['value']}D")
                    rules.append(rule)
                objects["dataPoint"] = rules

        # Data bars for table/matrix columns
        if visual_type in ('tableEx', 'matrix', 'pivotTable', 'table'):
            value_fields = [f for f in ws_data.get('fields', [])
                            if f.get('role') == 'measure']
            if value_fields and color_enc.get('type') == 'quantitative':
                data_bar_props = {
                    "show": _L("true"),
                    "positiveColor": {"solid": {"color": _L("'#4472C4'")}},
                    "negativeColor": {"solid": {"color": _L("'#ED7D31'")}},
                }
                objects["dataBar"] = [{"properties": data_bar_props}]

            # Default row banding fallback
            if "values" not in objects:
                objects["values"] = [{
                    "properties": {
                        "backColor": {"solid": {"color": _L("'#F2F2F2'")}}
                    }
                }]

            # Totals and subtotals
            totals = ws_data.get('totals', {})
            if totals and (totals.get('grand_totals') or totals.get('subtotals')):
                objects.setdefault("total", [{"properties": {}}])
                objects["total"][0]["properties"]["totals"] = _L("true")
                if totals.get('subtotals'):
                    objects.setdefault("subTotals", [{"properties": {}}])
                    objects["subTotals"][0]["properties"]["rowSubtotals"] = _L("true")

        # Continuous vs discrete axis scale
        for axis_key, axis_obj_key in [('x', 'categoryAxis'), ('y', 'valueAxis')]:
            ax = axes_detail.get(axis_key, {})
            if ax.get('is_continuous') is True:
                if axis_obj_key in objects:
                    objects[axis_obj_key][0]["properties"]["axisType"] = _L("'Continuous'")
            elif ax.get('is_continuous') is False and axis_obj_key in objects:
                objects[axis_obj_key][0]["properties"]["axisType"] = _L("'Categorical'")

        # Dual-axis synchronization (secShow / secAxisLabel)
        dual_axis = ws_data.get('dual_axis', {})
        if isinstance(dual_axis, dict) and dual_axis.get('enabled'):
            if "valueAxis" not in objects:
                objects["valueAxis"] = [{"properties": {"show": _L("true")}}]
            if dual_axis.get('synchronized'):
                objects["valueAxis"][0]["properties"]["secShow"] = _L("true")
                objects["valueAxis"][0]["properties"]["secAxisLabel"] = _L("true")

        # Per-object padding
        padding = ws_data.get('padding', {})
        if isinstance(padding, dict) and padding:
            pad_props = {}
            for side in ('top', 'bottom', 'left', 'right'):
                val = padding.get(f'padding_{side}', padding.get(f'margin_{side}', 0))
                if val:
                    pad_props[side] = _L(f"{val}L")
            if pad_props:
                objects["visualContainerPadding"] = [{"properties": pad_props}]

        # Reference bands and statistical reference lines (analytics_stats)
        analytics_stats = ws_data.get('analytics_stats', [])
        for stat in analytics_stats:
            if stat.get('type') == 'distribution_band':
                band_from = stat.get('value_from', '')
                band_to = stat.get('value_to', '')
                if band_from and band_to:
                    if "valueAxis" not in objects:
                        objects["valueAxis"] = [{"properties": {"show": _L("true")}}]
                    objects["valueAxis"][0]["properties"].setdefault("referenceLine", [])
                    objects["valueAxis"][0]["properties"]["referenceLine"].append({
                        "type": "Band",
                        "lowerBound": str(band_from),
                        "upperBound": str(band_to),
                        "transparency": _L("50L"),
                        "show": _L("true"),
                    })
            elif stat.get('type') in ('stat_line', 'stat_reference'):
                comp = stat.get('computation', stat.get('stat', ''))
                stat_map = {'mean': 'Average', 'median': 'Median',
                            'constant': 'Constant', 'percentile': 'Percentile',
                            'mode': 'Average'}
                stat_type = stat_map.get(comp.lower(), 'Average')
                if "valueAxis" not in objects:
                    objects["valueAxis"] = [{"properties": {"show": _L("true")}}]
                objects["valueAxis"][0]["properties"].setdefault("referenceLine", [])
                objects["valueAxis"][0]["properties"]["referenceLine"].append({
                    "type": stat_type,
                    "show": _L("true"),
                    "style": _L("'dashed'"),
                })

        # Small multiples formatting
        sm_field = ws_data.get('small_multiples', '')
        if not sm_field:
            pages_shelf = ws_data.get('pages_shelf', {})
            if isinstance(pages_shelf, dict):
                sm_field = pages_shelf.get('field', '')
        if sm_field:
            objects["smallMultiple"] = [{"properties": {
                "layoutMode": _L("'Flow'"),
                "showChartTitle": _L("true"),
            }}]

        # Number format mapping on labels
        fmt_info = formatting.get('number_format', formatting.get('format_string', ''))
        if fmt_info:
            pbi_fmt = self._convert_number_format(fmt_info)
            if pbi_fmt and "labels" in objects:
                objects["labels"][0]["properties"]["labelDisplayUnits"] = _L(f"'{pbi_fmt}'")

        return objects
    
    def _create_slicer_visual(self, visual_id, x, y, w, h, field_name, table_name, z_order,
                               slicer_mode='Dropdown'):
        """Creates a slicer visual for a filter/parameter control with field binding.

        Args:
            slicer_mode: PBI slicer mode string — ``'Dropdown'``, ``'List'``,
                ``'Between'`` (range/slider), or ``'Basic'`` (relative date).
        """
        clean_field = field_name.replace('[', '').replace(']', '')
        clean_table = table_name.replace("'", "''") if table_name else getattr(self, '_main_table', 'Table')
        
        # Build objects with the correct mode
        slicer_objects = {
            "data": [{
                "properties": {
                    "mode": _L(f"'{slicer_mode}'")
                }
            }],
            "header": [{
                "properties": {
                    "show": _L("true")
                }
            }]
        }

        # For slider / range mode, add numericInputStyle
        if slicer_mode == 'Between':
            slicer_objects["numericInputStyle"] = [{
                "properties": {
                    "show": _L("true")
                }
            }]

        slicer = {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.5.0/schema.json",
            "name": visual_id,
            "position": {
                "x": x, "y": y, "z": z_order * 1000,
                "height": h, "width": w,
                "tabOrder": z_order * 1000
            },
            "visual": {
                "visualType": "slicer",
                "objects": slicer_objects,
                "drillFilterOtherVisuals": True
            }
        }
        
        # Add query binding (PBIR queryState format with RoleProjection)
        if clean_field and clean_table:
            slicer["visual"]["query"] = {
                "queryState": {
                    "Values": {
                        "projections": [{
                            "field": {
                                "Column": {
                                    "Expression": {"SourceRef": {"Entity": clean_table}},
                                    "Property": clean_field
                                }
                            },
                            "queryRef": f"{clean_table}.{clean_field}"
                        }]
                    }
                }
            }
        
        return slicer
    
    def _detect_slicer_mode(self, obj, column_name, converted_objects):
        """Detect the best PBI slicer mode for a source filter control.

        Returns one of: ``'Dropdown'``, ``'List'``, ``'Between'``, ``'Basic'``.
        """
        param_ref = obj.get('param', '')

        # Check if this is a range parameter → slider (Between)
        for param in converted_objects.get('parameters', []):
            p_name = param.get('name', '').replace('[', '').replace(']', '')
            if p_name and (p_name in param_ref or p_name == column_name):
                if param.get('domain_type') == 'range':
                    return 'Between'
                if param.get('domain_type') == 'list':
                    return 'List'

        # Check column data type across datasources
        col_lower = column_name.lower()
        for ds in converted_objects.get('datasources', []):
            for table in ds.get('tables', []):
                for col in table.get('columns', []):
                    name = (col.get('caption', '') or col.get('name', '')).lower()
                    if name == col_lower:
                        dtype = col.get('datatype', '').lower()
                        if dtype in ('date', 'datetime'):
                            return 'Basic'  # relative date slicer
                        if dtype in ('integer', 'real', 'float', 'number'):
                            return 'Between'  # numeric range slider

        # Default to Dropdown for categorical text fields
        return 'Dropdown'

    def _create_pages_shelf_slicer(self, visuals_dir, pages_shelf, scale_x, scale_y,
                                    visual_count, converted_objects):
        """Create an animation-hint slicer from source Pages shelf.

        In Qlik the Pages shelf allows playback through dimension values;
        Power BI has no direct equivalent.  We create a standard slicer bound
        to the same field and annotate it with a comment so that the user
        knows it originated from a Pages shelf.
        """
        field = pages_shelf.get('field', '')
        if not field:
            return
        table_name = self._find_column_table(field, converted_objects)
        visual_id = uuid.uuid4().hex[:20]
        visual_dir = os.path.join(visuals_dir, visual_id)
        os.makedirs(visual_dir, exist_ok=True)
        slicer = self._create_slicer_visual(
            visual_id, 10, 10, 400, 50, field, table_name, visual_count)
        slicer.setdefault('visual', {}).setdefault('objects', {})
        slicer['visual']['objects']['general'] = [{
            'properties': {
                'comments': _L("'Pages Shelf / Play Axis: animate through values'")
            }
        }]
        _write_json(os.path.join(visual_dir, 'visual.json'), slicer)

    @staticmethod
    def _convert_number_format(source_format):
        """Convert source number format string to PBI display units / format.

        Common patterns::

            ###,###    → #,0
            $#,#00.00  → $#,0.00
            0.0%       → 0.0%
            0.00       → 0.00
        """
        if not source_format or not isinstance(source_format, str):
            return ''
        fmt = source_format.strip()
        # Already a PBI-compatible format
        if fmt in ('0', '0.0', '0.00', '#,0', '#,0.0', '#,0.00',
                   '0%', '0.0%', '0.00%'):
            return fmt
        # Currency
        if '$' in fmt:
            return fmt.replace('#,#', '#,0').replace('##', '#0')
        # Percentage
        if '%' in fmt:
            return fmt
        # Thousands separator
        if ',' in fmt:
            return fmt.replace('#,#', '#,0')
        return fmt

    def _create_drillthrough_pages(self, pages_dir, page_names, worksheets,
                                    converted_objects):
        """Create drill-through pages from source filter/set actions.

        Inspects actions for ``filter`` or ``set-value`` types that target
        specific worksheets.  Each unique target becomes a PBI drill-through
        page with ``pageType: "Drillthrough"`` and a drillthrough filter on
        the source field.
        """
        actions = converted_objects.get('actions', [])
        if not actions:
            return

        # Collect unique target worksheets from filter/set actions
        drillthrough_targets = {}  # target_ws_name → source_field
        for action in actions:
            a_type = action.get('type', '')
            if a_type not in ('filter', 'set-value'):
                continue
            target_sheets = action.get('target_worksheets', [])
            if not target_sheets:
                target = action.get('target_worksheet', '')
                if target:
                    target_sheets = [target]
            source_field = action.get('field', action.get('source_field', ''))

            for ts in target_sheets:
                # Skip if the target is already a dashboard page (not drill-through)
                if ts not in drillthrough_targets:
                    drillthrough_targets[ts] = source_field

        if not drillthrough_targets:
            return

        for target_ws, source_field in drillthrough_targets.items():
            ws_data = self._find_worksheet(worksheets, target_ws)
            if not ws_data:
                continue

            dt_page_name = f"Drillthrough_{uuid.uuid4().hex[:12]}"
            dt_display = f"Drillthrough - {target_ws}"
            page_names.append(dt_page_name)

            dt_dir = os.path.join(pages_dir, dt_page_name)
            os.makedirs(dt_dir, exist_ok=True)

            dt_page = {
                "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.0.0/schema.json",
                "name": dt_page_name,
                "displayName": dt_display,
                "displayOption": "FitToPage",
                "height": 720,
                "width": 1280,
                "pageType": "Drillthrough"
            }

            # Add drill-through filter if source field is known
            if source_field:
                clean_field = source_field.replace('[', '').replace(']', '')
                table_name = self._find_column_table(clean_field, converted_objects)
                if table_name:
                    dt_page["drillthrough"] = {
                        "filters": [{
                            "name": f"Filter_{clean_field}",
                            "field": {
                                "Column": {
                                    "Expression": {"SourceRef": {"Entity": table_name}},
                                    "Property": clean_field
                                }
                            },
                            "type": "Categorical"
                        }]
                    }

            _write_json(os.path.join(dt_dir, 'page.json'), dt_page)

            # Create visuals on the drill-through page
            dt_visuals_dir = os.path.join(dt_dir, 'visuals')
            os.makedirs(dt_visuals_dir, exist_ok=True)
            self._create_visual_worksheet(
                dt_visuals_dir, ws_data,
                {'type': 'worksheetReference', 'worksheetName': target_ws,
                 'position': {'x': 0, 'y': 0, 'w': 1280, 'h': 720}},
                1.0, 1.0, 0, worksheets, converted_objects
            )
            print(f"  [Drillthrough] page '{dt_display}' created")

    def _find_column_table(self, column_name, converted_objects):
        """Finds the table containing a given column"""
        datasources = converted_objects.get('datasources', [])
        for ds in datasources:
            for table in ds.get('tables', []):
                for col in table.get('columns', []):
                    col_caption = col.get('caption', col.get('name', ''))
                    if col_caption == column_name or col.get('name', '') == column_name:
                        return table.get('name', '')
                # Also search in calculations
                for calc in ds.get('calculations', []):
                    calc_caption = calc.get('caption', '')
                    if calc_caption == column_name:
                        # The calculation is in the main table of this datasource
                        tables = ds.get('tables', [])
                        if tables:
                            return tables[0].get('name', '')
        return ''
    
    def _find_worksheet(self, worksheets, name):
        """Finds a worksheet by name"""
        for ws in worksheets:
            if ws.get('name') == name:
                return ws
        return None
    
    def create_metadata(self, project_dir, report_name, converted_objects):
        """Creates migration metadata file for documentation."""
        # Count visuals and pages from the generated report
        pages_count = 0
        visuals_count = 0
        report_def = os.path.join(project_dir, f"{report_name}.Report", "definition", "pages")
        if os.path.isdir(report_def):
            for entry in os.listdir(report_def):
                entry_path = os.path.join(report_def, entry)
                if os.path.isdir(entry_path) and entry.startswith('ReportSection'):
                    pages_count += 1
                    vis_dir = os.path.join(entry_path, 'visuals')
                    if os.path.isdir(vis_dir):
                        visuals_count += len([d for d in os.listdir(vis_dir)
                                              if os.path.isdir(os.path.join(vis_dir, d))])

        # Check for theme
        theme_applied = os.path.exists(os.path.join(
            project_dir, f"{report_name}.Report", "definition",
            "RegisteredResources", "QlikMigrationTheme.json"
        ))

        # Read TMDL stats
        tmdl_stats = {}
        tables_dir = os.path.join(project_dir, f"{report_name}.SemanticModel",
                                  "definition", "tables")
        if os.path.isdir(tables_dir):
            tmdl_stats['tables'] = len([f for f in os.listdir(tables_dir) if f.endswith('.tmdl')])

        # Count measures and relationships from TMDL files
        measures_count = 0
        columns_count = 0
        if os.path.isdir(tables_dir):
            for tmdl_file in os.listdir(tables_dir):
                if tmdl_file.endswith('.tmdl'):
                    try:
                        with open(os.path.join(tables_dir, tmdl_file), 'r', encoding='utf-8') as f:
                            content = f.read()
                        measures_count += content.count('\n\tmeasure ')
                        columns_count += content.count('\n\tcolumn ')
                    except (IOError, OSError):
                        pass
        tmdl_stats['measures'] = measures_count
        tmdl_stats['columns'] = columns_count

        relationships_count = 0
        rels_path = os.path.join(project_dir, f"{report_name}.SemanticModel",
                                 "definition", "relationships.tmdl")
        if os.path.isfile(rels_path):
            try:
                with open(rels_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                relationships_count = content.count('\nrelationship ')
            except (IOError, OSError):
                pass
        tmdl_stats['relationships'] = relationships_count

        # Collect visual type mappings used
        visual_types_used = {}
        for ws in converted_objects.get('worksheets', []):
            ws_name = ws.get('name', 'Unknown')
            mark = ws.get('mark_type', 'Automatic')
            visual_types_used[ws_name] = mark

        # Collect approximation warnings from visual generation
        from powerbi_import.visual_generator import get_approximation_note
        approximations = []
        for ws_name, mark in visual_types_used.items():
            note = get_approximation_note(mark)
            if note:
                approximations.append({"worksheet": ws_name, "source_type": mark, "note": note})

        # Theme detail
        theme_detail = {}
        if theme_applied:
            theme_detail['status'] = 'applied'
        else:
            has_colors = any(
                d.get('formatting', {}).get('background_color')
                for d in converted_objects.get('dashboards', [])
            )
            theme_detail['status'] = 'skipped'
            theme_detail['reason'] = 'no dashboard colors detected' if not has_colors else 'generation error'

        metadata = {
            "generated_at": datetime.now().isoformat(),
            "source": "Qlik Migration",
            "report_name": report_name,
            "objects_converted": {
                "worksheets": len(converted_objects.get('worksheets', [])),
                "dashboards": len(converted_objects.get('dashboards', [])),
                "datasources": len(converted_objects.get('datasources', [])),
                "calculations": len(converted_objects.get('calculations', [])),
                "parameters": len(converted_objects.get('parameters', [])),
                "filters": len(converted_objects.get('filters', [])),
                "stories": len(converted_objects.get('stories', [])),
                "sets": len(converted_objects.get('sets', [])),
                "groups": len(converted_objects.get('groups', [])),
                "bins": len(converted_objects.get('bins', [])),
                "hierarchies": len(converted_objects.get('hierarchies', [])),
                "user_filters": len(converted_objects.get('user_filters', [])),
                "actions": len(converted_objects.get('actions', [])),
                "custom_sql": len(converted_objects.get('custom_sql', []))
            },
            "generated_output": {
                "pages": pages_count,
                "visuals": visuals_count,
                "theme_applied": theme_applied,
                "theme_detail": theme_detail
            },
            "tmdl_stats": tmdl_stats,
            "measure_renames": getattr(self, '_measure_renames', {}) or {},
            "visual_type_mappings": visual_types_used,
            "approximations": approximations,
        }
        metadata_file = os.path.join(project_dir, 'migration_metadata.json')
        _write_json(metadata_file, metadata)

    # ═══════════════════════════════════════════════════════════════════
    # Paginated Report Generation
    # ═══════════════════════════════════════════════════════════════════

    def _create_paginated_report(self, project_dir, report_name, converted_objects):
        """Generate a paginated report layout (RDL-style) for print-oriented output.

        Creates a ``PaginatedReport/`` directory inside the project with:
        - ``report.json``: Paginated report definition with fixed page dimensions
        - ``pages/``: One ``pageN.json`` per worksheet with tabular layout
        - ``header.json`` / ``footer.json``: Placeholder header/footer definitions

        Paginated reports use fixed positioning (inches/cm) rather than
        responsive layout.  This is a starting point that users can refine
        in Power BI Report Builder.
        """
        pag_dir = os.path.join(project_dir, 'PaginatedReport')
        pages_dir = os.path.join(pag_dir, 'pages')
        os.makedirs(pages_dir, exist_ok=True)

        # --- Report-level definition ---
        report_def = {
            "$schema": "paginated-report/1.0.0",
            "name": f"{report_name}_Paginated",
            "description": f"Paginated report generated from Qlik app '{report_name}'",
            "pageWidth": "8.5in",
            "pageHeight": "11in",
            "marginTop": "0.5in",
            "marginBottom": "0.5in",
            "marginLeft": "0.75in",
            "marginRight": "0.75in",
            "orientation": "Portrait",
            "pageCount": 0,
            "dataSource": report_name,
        }

        # --- Header / Footer ---
        header_def = {
            "height": "0.75in",
            "items": [
                {
                    "type": "textbox",
                    "value": report_name,
                    "style": {"fontSize": "14pt", "fontWeight": "bold"},
                    "position": {"left": "0in", "top": "0.1in", "width": "5in", "height": "0.4in"},
                },
                {
                    "type": "textbox",
                    "value": "=Globals!ExecutionTime",
                    "style": {"fontSize": "8pt", "textAlign": "right"},
                    "position": {"left": "5in", "top": "0.1in", "width": "2in", "height": "0.3in"},
                },
            ],
        }
        footer_def = {
            "height": "0.5in",
            "items": [
                {
                    "type": "textbox",
                    "value": "=Globals!PageNumber & \" of \" & Globals!TotalPages",
                    "style": {"fontSize": "8pt", "textAlign": "center"},
                    "position": {"left": "2.5in", "top": "0.05in", "width": "2in", "height": "0.3in"},
                },
            ],
        }

        _write_json(os.path.join(pag_dir, 'header.json'), header_def)
        _write_json(os.path.join(pag_dir, 'footer.json'), footer_def)

        # --- One page per worksheet showing a table of the worksheet's fields ---
        worksheets = converted_objects.get('worksheets', [])
        page_num = 0
        for ws in worksheets:
            ws_name = ws.get('name', f'Sheet{page_num + 1}')
            fields = ws.get('fields', [])
            if not fields:
                continue
            page_num += 1

            # Build column definitions from fields
            col_width = min(2.0, 7.0 / max(len(fields), 1))
            columns = []
            for idx, field in enumerate(fields):
                fname = field if isinstance(field, str) else field.get('name', f'Column{idx}')
                columns.append({
                    "name": fname,
                    "width": f"{col_width:.2f}in",
                    "header": fname,
                    "style": {"fontSize": "9pt"},
                })

            page_def = {
                "pageNumber": page_num,
                "name": ws_name,
                "body": {
                    "height": "9in",
                    "items": [
                        {
                            "type": "tablix",
                            "name": f"Table_{ws_name}",
                            "position": {"left": "0in", "top": "0in",
                                         "width": f"{min(col_width * len(fields), 7.0):.2f}in",
                                         "height": "2in"},
                            "columns": columns,
                            "dataSetName": ws_name,
                            "headerRow": True,
                            "repeatHeaderOnNewPage": True,
                        }
                    ],
                },
            }
            _write_json(os.path.join(pages_dir, f'page{page_num}.json'), page_def)

        report_def['pageCount'] = page_num
        _write_json(os.path.join(pag_dir, 'report.json'), report_def)

        return pag_dir
