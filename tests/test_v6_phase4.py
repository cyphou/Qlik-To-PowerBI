"""Tests for v6.0.0 Phase 4 — Visual Report Fidelity."""

import pytest
from qlik_export.format_adapter import (
    adapt_qlik_for_generation,
    _extract_visual_filters,
    _extract_sort_orders,
    _extract_slicer_config,
    _adapt_stories,
)


def _base_qlik_data(**overrides):
    """Minimal Qlik data dict for testing."""
    data = {
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
    data.update(overrides)
    return data


# ── 4.1 Per-visual dimension/measure bindings ───────────────────


class TestPerVisualBindings:
    """Dimensions and measures are carried per-worksheet, not global."""

    def test_dims_measures_per_visual(self):
        qlik_data = _base_qlik_data(visualizations=[
            {
                'type': 'barchart',
                'title': 'Chart1',
                'dimensions': [{'field': 'Region', 'name': 'Region', 'label': 'Region'}],
                'measures': [{'name': 'Sales', 'label': 'Sales', 'expression': 'Sum(Sales)'}],
            },
            {
                'type': 'linechart',
                'title': 'Chart2',
                'dimensions': [{'field': 'Year', 'name': 'Year', 'label': 'Year'}],
                'measures': [{'name': 'Profit', 'label': 'Profit', 'expression': 'Sum(Profit)'}],
            },
        ])
        result = adapt_qlik_for_generation(qlik_data)
        ws = result['worksheets']
        assert len(ws) == 2

        chart1 = ws[0]
        assert chart1['dimensions'][0]['field'] == 'Region'
        assert chart1['measures'][0]['name'] == 'Sales'

        chart2 = ws[1]
        assert chart2['dimensions'][0]['field'] == 'Year'
        assert chart2['measures'][0]['name'] == 'Profit'

    def test_fields_contain_both_dims_and_measures(self):
        qlik_data = _base_qlik_data(visualizations=[
            {
                'type': 'table',
                'title': 'Table1',
                'dimensions': [{'field': 'Name', 'name': 'Name', 'label': 'Name'}],
                'measures': [{'name': 'Score', 'label': 'Score', 'expression': 'Sum(Score)'}],
            },
        ])
        result = adapt_qlik_for_generation(qlik_data)
        fields = result['worksheets'][0]['fields']
        names = [f['name'] for f in fields]
        assert 'Name' in names
        assert 'Score' in names


# ── 4.2 Visual-level filters ────────────────────────────────────


class TestVisualFilters:
    """Per-visual filters are extracted from Qlik visualization data."""

    def test_explicit_filters(self):
        viz = {
            'filters': [
                {'field': 'Region', 'type': 'categorical', 'values': ['North', 'South']},
            ],
        }
        filters = _extract_visual_filters(viz)
        assert len(filters) == 1
        assert filters[0]['field'] == 'Region'
        assert filters[0]['values'] == ['North', 'South']

    def test_topn_from_dimension_limit(self):
        viz = {
            'dimensions': [
                {
                    'field': 'Customer',
                    'name': 'Customer',
                    'qOtherLimit': {'qOtherMode': 1, 'qOtherLimitNo': 5},
                },
            ],
        }
        filters = _extract_visual_filters(viz)
        assert len(filters) == 1
        assert filters[0]['type'] == 'topN'
        assert filters[0]['topN'] == 5

    def test_no_filters(self):
        assert _extract_visual_filters({}) == []

    def test_range_filter(self):
        viz = {
            'filters': [
                {'field': 'Date', 'type': 'range', 'min': '2020-01-01', 'max': '2024-12-31'},
            ],
        }
        filters = _extract_visual_filters(viz)
        assert len(filters) == 1
        assert filters[0]['min'] == '2020-01-01'
        assert filters[0]['max'] == '2024-12-31'

    def test_filters_flow_through_pipeline(self):
        qlik_data = _base_qlik_data(visualizations=[
            {
                'type': 'barchart',
                'title': 'Filtered Chart',
                'dimensions': [],
                'measures': [],
                'filters': [{'field': 'Status', 'values': ['Active']}],
            },
        ])
        result = adapt_qlik_for_generation(qlik_data)
        ws_filters = result['worksheets'][0]['filters']
        assert len(ws_filters) == 1
        assert ws_filters[0]['field'] == 'Status'


# ── 4.3 Sort order preservation ──────────────────────────────────


class TestSortOrders:
    """Sort orders from Qlik are preserved in worksheets."""

    def test_explicit_sort(self):
        viz = {
            'sort': [
                {'field': 'Sales', 'direction': 'descending'},
            ],
        }
        sorts = _extract_sort_orders(viz)
        assert len(sorts) == 1
        assert sorts[0]['field'] == 'Sales'
        assert sorts[0]['direction'] == 'descending'

    def test_sort_from_dimension_criteria(self):
        viz = {
            'dimensions': [
                {
                    'field': 'Year',
                    'name': 'Year',
                    'qSortCriterias': [{'qSortByNumeric': -1}],
                },
            ],
        }
        sorts = _extract_sort_orders(viz)
        assert len(sorts) == 1
        assert sorts[0]['field'] == 'Year'
        assert sorts[0]['direction'] == 'descending'

    def test_ascending_default(self):
        viz = {
            'dimensions': [
                {
                    'field': 'Name',
                    'name': 'Name',
                    'qSortCriterias': [{'qSortByAlphabetical': 1}],
                },
            ],
        }
        sorts = _extract_sort_orders(viz)
        assert sorts[0]['direction'] == 'ascending'

    def test_no_sort(self):
        assert _extract_sort_orders({}) == []


# ── 4.4 Slicer configuration ────────────────────────────────────


class TestSlicerConfig:
    """Filter pane → slicer configuration."""

    def test_dropdown_mode(self):
        viz = {
            'type': 'filterpane',
            'properties': {'listLayout': 'dropdown'},
            'dimensions': [],
        }
        config = _extract_slicer_config(viz)
        assert config['mode'] == 'Dropdown'

    def test_list_mode_default(self):
        viz = {
            'type': 'filterpane',
            'properties': {},
            'dimensions': [],
        }
        config = _extract_slicer_config(viz)
        assert config['mode'] == 'Basic'

    def test_single_select(self):
        viz = {
            'type': 'listbox',
            'properties': {'singleSelect': True},
            'dimensions': [],
        }
        config = _extract_slicer_config(viz)
        assert config['singleSelect'] is True

    def test_date_range_detection(self):
        viz = {
            'type': 'filterpane',
            'properties': {},
            'dimensions': [{'field': 'OrderDate', 'name': 'OrderDate'}],
        }
        config = _extract_slicer_config(viz)
        assert config['is_date_range'] is True

    def test_non_date_slicer(self):
        viz = {
            'type': 'filterpane',
            'properties': {},
            'dimensions': [{'field': 'Country', 'name': 'Country'}],
        }
        config = _extract_slicer_config(viz)
        assert config['is_date_range'] is False

    def test_slicer_config_in_pipeline(self):
        qlik_data = _base_qlik_data(visualizations=[
            {
                'type': 'filterpane',
                'title': 'Region Filter',
                'dimensions': [{'field': 'Region', 'name': 'Region'}],
                'measures': [],
                'properties': {'listLayout': 'dropdown', 'singleSelect': True},
            },
        ])
        result = adapt_qlik_for_generation(qlik_data)
        ws = result['worksheets'][0]
        assert 'slicer_config' in ws
        assert ws['slicer_config']['mode'] == 'Dropdown'
        assert ws['slicer_config']['singleSelect'] is True


# ── 4.5 Bookmark generation ─────────────────────────────────────


class TestBookmarkGeneration:
    """Bookmarks with selections flow through as stories."""

    def test_bookmark_with_selections(self):
        bookmarks = [
            {
                'name': 'Q1 View',
                'description': 'Quarter 1 filter state',
                'selections': [
                    {'fieldName': 'Quarter', 'selectedValues': ['Q1']},
                    {'fieldName': 'Year', 'selectedValues': ['2024']},
                ],
                'sheetId': 'sheet1',
            },
        ]
        stories = _adapt_stories(bookmarks)
        assert len(stories) == 1
        assert stories[0]['name'] == 'Q1 View'
        sp = stories[0]['story_points'][0]
        assert sp['captured_sheet'] == 'sheet1'
        assert sp['filters_state'] is not None
        assert len(sp['filters_state']) == 2
        assert sp['filters_state'][0]['field'] == 'Quarter'
        assert sp['filters_state'][0]['values'] == ['Q1']

    def test_bookmark_no_selections(self):
        bookmarks = [{'name': 'Simple Bookmark'}]
        stories = _adapt_stories(bookmarks)
        assert len(stories) == 1
        sp = stories[0]['story_points'][0]
        assert sp['filters_state'] is None

    def test_empty_bookmarks(self):
        assert _adapt_stories([]) == []

    def test_bookmarks_in_pipeline(self):
        qlik_data = _base_qlik_data(bookmarks=[
            {
                'name': 'My Bookmark',
                'selections': [{'fieldName': 'Region', 'selectedValues': ['EMEA']}],
            },
        ])
        result = adapt_qlik_for_generation(qlik_data)
        assert len(result['stories']) == 1
        sp = result['stories'][0]['story_points'][0]
        assert sp['filters_state'][0]['field'] == 'Region'
