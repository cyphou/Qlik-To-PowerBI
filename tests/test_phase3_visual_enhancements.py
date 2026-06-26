"""Tests for Phase 3 — Visual & Reporting Enhancements.

Covers:
- 3a: Drillthrough pages — navigation action extraction + drillthrough page generation
- 3b: Tooltip pages — viz-in-tooltip extraction
- 3c: Icon set conditional formatting — build_icon_set_config()
- 3d: Alternate states → bookmarks — extraction + bookmark wiring in report.json
- 3e: Background image support — extraction + page background generation
"""

import json
import os
import uuid
import pytest

from qlik_export.format_adapter import adapt_qlik_for_generation
from powerbi_import.visual_generator import (
    build_icon_set_config,
    ICON_SET_PRESETS,
)
from powerbi_import.pbip_generator import PowerBIProjectGenerator


# ═══════════════════════════════════════════════════════════════
#  Helper: build minimal qlik_data for adapt_qlik_for_generation
# ═══════════════════════════════════════════════════════════════

def _qlik_data(**overrides):
    """Return a minimal Qlik intermediate data dict."""
    base = {
        'datasources': [],
        'dimensions': [],
        'measures': [],
        'visualizations': [],
        'sheets': [],
        'variables': [],
        'loadscript': {},
        'associations': [],
        'bookmarks': [],
        'master_items': [],
        'app_metadata': {},
    }
    base.update(overrides)
    return base


# ═══════════════════════════════════════════════════════════════
#  3a — Drillthrough (Navigation Action Extraction)
# ═══════════════════════════════════════════════════════════════

class TestDrillthroughExtraction:
    def test_goto_sheet_action(self):
        viz = [{
            'name': 'Sales Button',
            'type': 'button',
            'navigation': {'action': 'goToSheet', 'sheet': 'Details'},
        }]
        result = adapt_qlik_for_generation(_qlik_data(visualizations=viz))
        actions = result['actions']
        assert len(actions) == 1
        assert actions[0]['type'] == 'sheet-navigate'
        assert actions[0]['target_worksheet'] == 'Details'

    def test_goto_sheet_by_id(self):
        viz = [{
            'name': 'Nav',
            'type': 'button',
            'navigation': {'action': 'goToSheetById', 'sheetId': 'sheet123'},
        }]
        result = adapt_qlik_for_generation(_qlik_data(visualizations=viz))
        assert result['actions'][0]['target_worksheet'] == 'sheet123'

    def test_goto_url_action(self):
        viz = [{
            'name': 'Link',
            'type': 'button',
            'navigation': {'action': 'goToURL', 'url': 'https://example.com'},
        }]
        result = adapt_qlik_for_generation(_qlik_data(visualizations=viz))
        assert result['actions'][0]['type'] == 'url'
        assert result['actions'][0]['url'] == 'https://example.com'

    def test_drill_to_action_list(self):
        viz = [{
            'name': 'Chart',
            'type': 'barchart',
            'actions': [{'actionType': 'drillTo', 'sheet': 'DetailSheet', 'field': 'Category'}],
        }]
        result = adapt_qlik_for_generation(_qlik_data(visualizations=viz))
        assert result['actions'][0]['type'] == 'filter'
        assert result['actions'][0]['target_worksheet'] == 'DetailSheet'
        assert result['actions'][0]['field'] == 'Category'

    def test_no_navigation_no_actions(self):
        viz = [{'name': 'Chart', 'type': 'barchart'}]
        result = adapt_qlik_for_generation(_qlik_data(visualizations=viz))
        assert result['actions'] == []

    def test_multiple_visuals_multiple_actions(self):
        viz = [
            {'name': 'Btn1', 'type': 'button',
             'navigation': {'action': 'goToSheet', 'sheet': 'Page1'}},
            {'name': 'Btn2', 'type': 'button',
             'navigation': {'action': 'goToSheet', 'sheet': 'Page2'}},
        ]
        result = adapt_qlik_for_generation(_qlik_data(visualizations=viz))
        assert len(result['actions']) == 2

    def test_next_sheet_action(self):
        viz = [{
            'name': 'Nav',
            'type': 'button',
            'actions': [{'actionType': 'nextSheet', 'sheet': 'Sheet2'}],
        }]
        result = adapt_qlik_for_generation(_qlik_data(visualizations=viz))
        assert result['actions'][0]['type'] == 'sheet-navigate'


class TestDrillthroughPageGeneration:
    def test_filter_action_creates_drillthrough_page(self, tmp_path):
        gen = PowerBIProjectGenerator(str(tmp_path))
        co = {
            'datasources': [{'name': 'DS', 'tables': [
                {'name': 'Sales', 'columns': [{'name': 'Category'}]}
            ], 'connection': {'type': 'CSV'}}],
            'worksheets': [{'name': 'DetailView', 'chart_type': 'tableEx', 'fields': []}],
            'dashboards': [],
            'calculations': [],
            'parameters': [],
            'filters': [],
            'stories': [],
            'actions': [{'type': 'filter', 'target_worksheet': 'DetailView',
                         'field': 'Category'}],
            'sets': [], 'groups': [], 'bins': [], 'hierarchies': [],
            'sort_orders': [], 'aliases': {}, 'custom_sql': [],
            'user_filters': [],
        }
        report_dir = gen.create_report_structure(str(tmp_path), 'Test', co)
        # Find drillthrough page
        pages_dir = os.path.join(report_dir, 'definition', 'pages')
        dt_pages = [d for d in os.listdir(pages_dir) if d.startswith('Drillthrough_')]
        assert len(dt_pages) >= 1
        with open(os.path.join(pages_dir, dt_pages[0], 'page.json'), encoding='utf-8') as f:
            page = json.load(f)
        assert page.get('pageType') == 'Drillthrough'


# ═══════════════════════════════════════════════════════════════
#  3b — Tooltip Pages (viz-in-tooltip extraction)
# ═══════════════════════════════════════════════════════════════

class TestTooltipExtraction:
    def test_tooltip_viz_reference_extracted(self):
        viz = [{
            'name': 'Chart',
            'type': 'barchart',
            'tooltip': {'type': 'visualization', 'visualization': 'TooltipViz'},
        }]
        result = adapt_qlik_for_generation(_qlik_data(visualizations=viz))
        ws = result['worksheets'][0]
        assert 'tooltips' in ws
        assert ws['tooltips'][0]['type'] == 'viz_in_tooltip'
        assert ws['tooltips'][0]['worksheet'] == 'TooltipViz'

    def test_no_tooltip_no_key(self):
        viz = [{'name': 'Chart', 'type': 'barchart'}]
        result = adapt_qlik_for_generation(_qlik_data(visualizations=viz))
        ws = result['worksheets'][0]
        assert 'tooltips' not in ws or ws.get('tooltips') == []

    def test_non_viz_tooltip_ignored(self):
        viz = [{
            'name': 'Chart',
            'type': 'barchart',
            'tooltip': {'type': 'default'},
        }]
        result = adapt_qlik_for_generation(_qlik_data(visualizations=viz))
        ws = result['worksheets'][0]
        assert ws.get('tooltips') is None or len(ws.get('tooltips', [])) == 0


# ═══════════════════════════════════════════════════════════════
#  3c — Icon Set Conditional Formatting
# ═══════════════════════════════════════════════════════════════

class TestIconSetConfig:
    def test_traffic_light_preset(self):
        cfg = build_icon_set_config('Score', 'Metrics', 'traffic_light')
        assert cfg['id'] == 'iconSet_Score'
        assert cfg['iconSetType'] == 'traffic_light'
        assert len(cfg['rules']) == 3

    def test_arrows_preset(self):
        cfg = build_icon_set_config('Growth', 'Sales', 'arrows')
        assert cfg['iconSetType'] == 'arrows'
        assert any(r['shape'] == 'ArrowUp' for r in cfg['rules'])

    def test_flags_preset(self):
        cfg = build_icon_set_config('Status', 'T', 'flags')
        assert cfg['iconSetType'] == 'flags'

    def test_shapes_preset(self):
        cfg = build_icon_set_config('Risk', 'T', 'shapes')
        assert cfg['iconSetType'] == 'shapes'

    def test_custom_thresholds(self):
        cfg = build_icon_set_config('Score', 'T', thresholds=[25, 75])
        assert cfg['rules'][0]['threshold'] == 25

    def test_reverse_order(self):
        cfg_normal = build_icon_set_config('X', 'T', 'traffic_light', reverse=False)
        cfg_reversed = build_icon_set_config('X', 'T', 'traffic_light', reverse=True)
        # Reversed: first icon should have green color (originally last)
        assert cfg_normal['rules'][0]['color'] != cfg_reversed['rules'][0]['color']
        assert cfg_reversed['reverseIconOrder'] is True

    def test_custom_icon_set(self):
        custom = {
            'icons': [
                {'color': '#000', 'shape': 'Square'},
                {'color': '#FFF', 'shape': 'Circle'},
                {'color': '#888', 'shape': 'Diamond'},
            ],
            'thresholds': [30, 70],
        }
        cfg = build_icon_set_config('Col', 'T', icon_set=custom)
        assert cfg['iconSetType'] == 'custom'
        assert cfg['rules'][0]['color'] == '#000'

    def test_field_reference(self):
        cfg = build_icon_set_config('Revenue', 'Sales')
        field = cfg['field']['Column']
        assert field['Expression']['SourceRef']['Entity'] == 'Sales'
        assert field['Property'] == 'Revenue'

    def test_all_presets_exist(self):
        for name in ('traffic_light', 'arrows', 'flags', 'shapes'):
            assert name in ICON_SET_PRESETS
            cfg = build_icon_set_config('X', 'T', name)
            assert len(cfg['rules']) == 3

    def test_show_icon_only_default(self):
        cfg = build_icon_set_config('X', 'T')
        assert cfg['showIconOnly'] is False


class TestIconRuleExtraction:
    def test_icon_rules_extracted(self):
        viz = [{
            'name': 'Table',
            'type': 'table',
            'conditionalFormatting': [
                {'type': 'icon', 'field': 'Score', 'iconSet': 'traffic_light'},
            ],
        }]
        result = adapt_qlik_for_generation(_qlik_data(visualizations=viz))
        ws = result['worksheets'][0]
        assert 'icon_rules' in ws
        assert len(ws['icon_rules']) == 1

    def test_non_icon_rules_not_extracted(self):
        viz = [{
            'name': 'Table',
            'type': 'table',
            'conditionalFormatting': [
                {'type': 'color', 'field': 'Score'},
            ],
        }]
        result = adapt_qlik_for_generation(_qlik_data(visualizations=viz))
        ws = result['worksheets'][0]
        assert ws.get('icon_rules') is None or len(ws.get('icon_rules', [])) == 0


# ═══════════════════════════════════════════════════════════════
#  3d — Alternate States → Bookmarks
# ═══════════════════════════════════════════════════════════════

class TestAlternateStateExtraction:
    def test_alternate_state_extracted(self):
        viz = [{
            'name': 'Chart',
            'type': 'barchart',
            'qStateName': 'CompareState',
        }]
        result = adapt_qlik_for_generation(_qlik_data(visualizations=viz))
        ws = result['worksheets'][0]
        assert ws['alternate_state'] == 'CompareState'

    def test_default_state_not_extracted(self):
        viz = [{'name': 'Chart', 'type': 'barchart', 'qStateName': '$'}]
        result = adapt_qlik_for_generation(_qlik_data(visualizations=viz))
        ws = result['worksheets'][0]
        assert 'alternate_state' not in ws

    def test_no_state_no_key(self):
        viz = [{'name': 'Chart', 'type': 'barchart'}]
        result = adapt_qlik_for_generation(_qlik_data(visualizations=viz))
        ws = result['worksheets'][0]
        assert 'alternate_state' not in ws

    def test_statename_alternative_key(self):
        viz = [{'name': 'Chart', 'type': 'barchart', 'stateName': 'Alt1'}]
        result = adapt_qlik_for_generation(_qlik_data(visualizations=viz))
        ws = result['worksheets'][0]
        assert ws['alternate_state'] == 'Alt1'


class TestBookmarkWiring:
    def test_bookmarks_written_to_report_json(self, tmp_path):
        gen = PowerBIProjectGenerator(str(tmp_path))
        co = {
            'datasources': [{'name': 'DS', 'tables': [
                {'name': 'T', 'columns': [{'name': 'X'}]}
            ], 'connection': {'type': 'CSV'}}],
            'worksheets': [{'name': 'Sheet1', 'chart_type': 'table', 'fields': []}],
            'dashboards': [],
            'calculations': [],
            'parameters': [],
            'filters': [],
            'stories': [{
                'name': 'Q1 Review',
                'story_points': [
                    {'caption': 'January', 'filters_state': [
                        {'field': 'Month', 'values': ['Jan']}
                    ], 'captured_sheet': 'Sheet1'},
                    {'caption': 'February'},
                ],
            }],
            'actions': [],
            'sets': [], 'groups': [], 'bins': [], 'hierarchies': [],
            'sort_orders': [], 'aliases': {}, 'custom_sql': [],
            'user_filters': [],
        }
        report_dir = gen.create_report_structure(str(tmp_path), 'BmTest', co)
        with open(os.path.join(report_dir, 'definition', 'report.json'), encoding='utf-8') as f:
            report = json.load(f)
        assert 'bookmarks' not in report

        with open(os.path.join(report_dir, 'definition', 'bookmarks.generated.json'), encoding='utf-8') as f:
            generated = json.load(f)
        assert len(generated['bookmarks']) == 2
        assert generated['bookmarks'][0]['displayName'] == 'January'
        # First bookmark has filter state
        assert 'filters' in generated['bookmarks'][0]['explorationState']

    def test_no_stories_no_bookmarks(self, tmp_path):
        gen = PowerBIProjectGenerator(str(tmp_path))
        co = {
            'datasources': [], 'worksheets': [], 'dashboards': [],
            'calculations': [], 'parameters': [], 'filters': [],
            'stories': [], 'actions': [],
            'sets': [], 'groups': [], 'bins': [], 'hierarchies': [],
            'sort_orders': [], 'aliases': {}, 'custom_sql': [],
            'user_filters': [],
        }
        report_dir = gen.create_report_structure(str(tmp_path), 'NoBm', co)
        with open(os.path.join(report_dir, 'definition', 'report.json'), encoding='utf-8') as f:
            report = json.load(f)
        assert 'bookmarks' not in report
        assert not os.path.exists(os.path.join(report_dir, 'definition', 'bookmarks.generated.json'))


# ═══════════════════════════════════════════════════════════════
#  3e — Background Image Support
# ═══════════════════════════════════════════════════════════════

class TestBackgroundImageExtraction:
    def test_background_image_extracted(self):
        sheets = [{
            'id': 's1',
            'title': 'Dashboard',
            'backgroundImage': {'url': 'https://example.com/bg.png', 'transparency': 20},
        }]
        viz = [{'name': 'Chart', 'type': 'barchart', 'sheetId': 's1'}]
        result = adapt_qlik_for_generation(_qlik_data(sheets=sheets, visualizations=viz))
        db = result['dashboards'][0]
        assert 'backgroundImage' in db
        assert db['backgroundImage']['url'] == 'https://example.com/bg.png'
        assert db['backgroundImage']['transparency'] == 20

    def test_no_background_no_key(self):
        sheets = [{'id': 's1', 'title': 'Sheet'}]
        result = adapt_qlik_for_generation(_qlik_data(sheets=sheets))
        db = result['dashboards'][0]
        assert 'backgroundImage' not in db

    def test_background_from_properties(self):
        sheets = [{
            'id': 's1',
            'title': 'Sheet',
            'properties': {'backgroundImage': {'url': 'https://example.com/bg2.jpg'}},
        }]
        result = adapt_qlik_for_generation(_qlik_data(sheets=sheets))
        db = result['dashboards'][0]
        assert db['backgroundImage']['url'] == 'https://example.com/bg2.jpg'


class TestBackgroundImageGeneration:
    def test_page_has_background(self, tmp_path):
        gen = PowerBIProjectGenerator(str(tmp_path))
        co = {
            'datasources': [],
            'worksheets': [{'name': 'Chart1', 'chart_type': 'table', 'fields': []}],
            'dashboards': [{
                'name': 'Main',
                'size': {'width': 1280, 'height': 720},
                'objects': [{'type': 'worksheetReference', 'worksheetName': 'Chart1',
                             'position': {'x': 0, 'y': 0, 'w': 400, 'h': 300}}],
                'backgroundImage': {'url': 'https://example.com/bg.png', 'transparency': 10},
            }],
            'calculations': [], 'parameters': [], 'filters': [],
            'stories': [], 'actions': [],
            'sets': [], 'groups': [], 'bins': [], 'hierarchies': [],
            'sort_orders': [], 'aliases': {}, 'custom_sql': [],
            'user_filters': [],
        }
        report_dir = gen.create_report_structure(str(tmp_path), 'BgTest', co)
        pages_dir = os.path.join(report_dir, 'definition', 'pages')
        page_dirs = [d for d in os.listdir(pages_dir) if os.path.isdir(os.path.join(pages_dir, d))]
        found_bg = False
        for pd in page_dirs:
            pj = os.path.join(pages_dir, pd, 'page.json')
            if os.path.exists(pj):
                with open(pj, encoding='utf-8') as f:
                    page = json.load(f)
                if 'background' in page:
                    assert page['background']['image']['url'] == 'https://example.com/bg.png'
                    found_bg = True
        assert found_bg

    def test_no_background_no_property(self, tmp_path):
        gen = PowerBIProjectGenerator(str(tmp_path))
        co = {
            'datasources': [],
            'worksheets': [{'name': 'Chart1', 'chart_type': 'table', 'fields': []}],
            'dashboards': [{
                'name': 'Main',
                'size': {'width': 1280, 'height': 720},
                'objects': [{'type': 'worksheetReference', 'worksheetName': 'Chart1',
                             'position': {'x': 0, 'y': 0, 'w': 400, 'h': 300}}],
            }],
            'calculations': [], 'parameters': [], 'filters': [],
            'stories': [], 'actions': [],
            'sets': [], 'groups': [], 'bins': [], 'hierarchies': [],
            'sort_orders': [], 'aliases': {}, 'custom_sql': [],
            'user_filters': [],
        }
        report_dir = gen.create_report_structure(str(tmp_path), 'NoBg', co)
        pages_dir = os.path.join(report_dir, 'definition', 'pages')
        for pd in os.listdir(pages_dir):
            pj = os.path.join(pages_dir, pd, 'page.json')
            if os.path.exists(pj):
                with open(pj, encoding='utf-8') as f:
                    page = json.load(f)
                assert 'background' not in page
