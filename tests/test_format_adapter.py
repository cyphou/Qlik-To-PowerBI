"""
Tests for qlik_export.format_adapter — the Qlik→generation bridge layer.

Validates input handling, chart-type mapping, data transformation,
and edge-case resilience for the critical path between Qlik extraction
and Power BI project generation.
"""

import pytest
import warnings

from qlik_export.format_adapter import (
    adapt_qlik_for_generation,
    adapt_qlik_to_tableau_format,
    _QLIK_CHART_TYPE_MAP,
)


# ── Fixtures ────────────────────────────────────────────────────────

@pytest.fixture
def empty_qlik_data():
    """Minimal valid Qlik data with all keys empty."""
    return {
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


@pytest.fixture
def minimal_qlik_data():
    """One datasource, one table, one column."""
    return {
        'datasources': [{
            'tableName': 'Sales',
            'connectionType': 'sql',
            'connection': {'server': 'db.example.com', 'database': 'analytics'},
            'columns': [
                {'name': 'Amount', 'dataType': 'numeric'},
                {'name': 'Region', 'dataType': 'string', 'label': 'Sales Region'},
            ],
        }],
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


@pytest.fixture
def full_qlik_data():
    """Realistic Qlik data with all object types populated."""
    return {
        'datasources': [
            {
                'tableName': 'Sales',
                'connectionType': 'PostgreSQL',
                'connection': {'server': 'db.co', 'database': 'dw'},
                'columns': [
                    {'name': 'SalesAmount', 'dataType': 'numeric', 'label': 'Sales Amount'},
                    {'name': 'ProductId', 'dataType': 'integer'},
                    {'name': 'OrderDate', 'dataType': 'date'},
                ],
            },
            {
                'tableName': 'Product',
                'connectionType': 'PostgreSQL',
                'connection': {'server': 'db.co', 'database': 'dw'},
                'columns': [
                    {'name': 'ProductId', 'dataType': 'integer'},
                    {'name': 'ProductName', 'dataType': 'string'},
                ],
            },
        ],
        'dimensions': [
            {'name': 'ProductCategory', 'label': 'Product Category', 'field': 'Category'},
            {'name': 'YearMonth', 'label': 'Year-Month',
             'field': "Year(OrderDate) & '-' & Month(OrderDate)", 'is_calculated': True},
        ],
        'measures': [
            {'name': 'Total Sales', 'label': 'Total Sales', 'expression': 'Sum(SalesAmount)'},
            {'name': 'Avg Sales', 'label': 'Average Sales', 'expression': 'Avg(SalesAmount)'},
        ],
        'visualizations': [
            {
                'type': 'barchart',
                'title': 'Sales by Region',
                'dimensions': [{'field': 'Region', 'label': 'Region'}],
                'measures': [{'name': 'Total Sales', 'expression': 'Sum(SalesAmount)'}],
            },
            {
                'type': 'kpi',
                'title': 'Revenue KPI',
                'dimensions': [],
                'measures': [{'name': 'Total Sales'}],
            },
            {
                'type': 'linechart',
                'title': 'Trend',
                'dimensions': [{'field': 'OrderDate'}],
                'measures': [{'name': 'Total Sales'}],
            },
        ],
        'sheets': [
            {'id': 'sheet1', 'title': 'Overview', 'width': 1280, 'height': 720},
        ],
        'variables': [
            {'name': 'vCurrentYear', 'definition': '2024', 'label': 'Current Year'},
            {'name': '$hidden', 'definition': 'x'},
            {'name': '_internal', 'definition': 'y'},
        ],
        'loadscript': {'script': 'LOAD * FROM Sales.qvd (qvd);'},
        'associations': [
            {'table1': 'Sales', 'table2': 'Product',
             'field1': 'ProductId', 'field2': 'ProductId'},
        ],
        'bookmarks': [
            {'name': 'Q1 Filter', 'description': 'First quarter filter'},
        ],
        'master_items': [
            {'name': 'Profit', 'type': 'measure', 'expression': 'Sum(Revenue) - Sum(Cost)'},
        ],
        'app_metadata': {'name': 'SalesApp', 'author': 'analyst'},
    }


# ── Input validation tests ──────────────────────────────────────────

class TestInputValidation:
    """Guard against invalid inputs at the API boundary."""

    def test_none_input_raises_value_error(self):
        with pytest.raises(ValueError, match="must not be None"):
            adapt_qlik_for_generation(None)

    def test_non_dict_input_raises_value_error(self):
        with pytest.raises(ValueError, match="must be a dict"):
            adapt_qlik_for_generation([1, 2, 3])

    def test_string_input_raises_value_error(self):
        with pytest.raises(ValueError, match="must be a dict"):
            adapt_qlik_for_generation("not a dict")

    def test_empty_dict_returns_valid_structure(self):
        result = adapt_qlik_for_generation({})
        assert isinstance(result, dict)
        # All 16 expected keys must be present
        expected_keys = {
            'datasources', 'worksheets', 'dashboards', 'calculations',
            'parameters', 'filters', 'stories', 'actions', 'sets',
            'groups', 'bins', 'hierarchies', 'sort_orders', 'aliases',
            'custom_sql', 'user_filters',
        }
        assert set(result.keys()) == expected_keys

    def test_empty_dict_all_lists_empty(self):
        result = adapt_qlik_for_generation({})
        for key in ('datasources', 'worksheets', 'dashboards', 'calculations',
                     'parameters', 'filters', 'stories', 'custom_sql'):
            assert result[key] == [], f"Expected '{key}' to be empty list"
        assert result['aliases'] == {}


# ── Output structure tests ───────────────────────────────────────────

class TestOutputStructure:
    """Verify the 16-key output contract."""

    def test_full_data_returns_all_keys(self, full_qlik_data):
        result = adapt_qlik_for_generation(full_qlik_data)
        expected_keys = {
            'datasources', 'worksheets', 'dashboards', 'calculations',
            'parameters', 'filters', 'stories', 'actions', 'sets',
            'groups', 'bins', 'hierarchies', 'sort_orders', 'aliases',
            'custom_sql', 'user_filters',
        }
        assert set(result.keys()) == expected_keys

    def test_empty_qlik_data_returns_valid_structure(self, empty_qlik_data):
        result = adapt_qlik_for_generation(empty_qlik_data)
        assert isinstance(result['datasources'], list)
        assert isinstance(result['worksheets'], list)
        assert isinstance(result['dashboards'], list)
        assert isinstance(result['aliases'], dict)


# ── Datasource adaptation tests ──────────────────────────────────────

class TestDatasourceAdaptation:

    def test_minimal_datasource(self, minimal_qlik_data):
        result = adapt_qlik_for_generation(minimal_qlik_data)
        assert len(result['datasources']) == 1
        ds = result['datasources'][0]
        assert ds['name'] == 'Sales'
        assert ds['connection']['type'] == 'sql'
        assert len(ds['columns']) == 2

    def test_datasource_column_fields(self, minimal_qlik_data):
        result = adapt_qlik_for_generation(minimal_qlik_data)
        col = result['datasources'][0]['columns'][1]
        assert col['name'] == 'Region'
        assert col['datatype'] == 'string'
        assert col['caption'] == 'Sales Region'
        assert col['role'] == 'dimension'

    def test_multiple_datasources(self, full_qlik_data):
        result = adapt_qlik_for_generation(full_qlik_data)
        assert len(result['datasources']) == 2
        names = [ds['name'] for ds in result['datasources']]
        assert 'Sales' in names
        assert 'Product' in names

    def test_empty_columns_fallback(self):
        """Datasource with no columns should not crash."""
        data = {
            'datasources': [{'tableName': 'Empty', 'columns': []}],
            'dimensions': [], 'measures': [], 'visualizations': [],
            'sheets': [], 'variables': [], 'loadscript': {},
            'associations': [], 'bookmarks': [], 'master_items': [],
            'app_metadata': {},
        }
        result = adapt_qlik_for_generation(data)
        assert len(result['datasources']) == 1
        assert result['datasources'][0]['columns'] == []

    def test_missing_columns_key(self):
        """Datasource dict without 'columns' key at all."""
        data = {
            'datasources': [{'tableName': 'NoColKey'}],
            'dimensions': [], 'measures': [], 'visualizations': [],
            'sheets': [], 'variables': [], 'loadscript': {},
            'associations': [], 'bookmarks': [], 'master_items': [],
            'app_metadata': {},
        }
        result = adapt_qlik_for_generation(data)
        assert len(result['datasources']) == 1
        assert result['datasources'][0]['columns'] == []

    def test_datasource_connection_string_fallback(self):
        """Connection given as a plain string instead of a dict."""
        data = {
            'datasources': [{
                'tableName': 'StrConn',
                'columns': [{'name': 'A'}],
                'connection': 'Server=db;Database=test',
            }],
            'dimensions': [], 'measures': [], 'visualizations': [],
            'sheets': [], 'variables': [], 'loadscript': {},
            'associations': [], 'bookmarks': [], 'master_items': [],
            'app_metadata': {},
        }
        result = adapt_qlik_for_generation(data)
        ds = result['datasources'][0]
        assert ds['connection']['connectionString'] == 'Server=db;Database=test'

    def test_m_query_override_passthrough(self):
        """Pre-built M query should pass through to m_query_overrides."""
        data = {
            'datasources': [{
                'tableName': 'WithM',
                'columns': [{'name': 'A'}],
                'm_query': 'let Source = Sql.Database("server", "db") in Source',
            }],
            'dimensions': [], 'measures': [], 'visualizations': [],
            'sheets': [], 'variables': [], 'loadscript': {},
            'associations': [], 'bookmarks': [], 'master_items': [],
            'app_metadata': {},
        }
        result = adapt_qlik_for_generation(data)
        ds = result['datasources'][0]
        assert 'WithM' in ds.get('m_query_overrides', {})

    def test_datasource_name_fallback_chain(self):
        """Table name resolution: tableName > name > table > default."""
        data = {
            'datasources': [
                {'name': 'ByName', 'columns': []},
                {'table': 'ByTable', 'columns': []},
                {'columns': []},  # no name at all — should get fallback
            ],
            'dimensions': [], 'measures': [], 'visualizations': [],
            'sheets': [], 'variables': [], 'loadscript': {},
            'associations': [], 'bookmarks': [], 'master_items': [],
            'app_metadata': {},
        }
        result = adapt_qlik_for_generation(data)
        names = [ds['name'] for ds in result['datasources']]
        assert 'ByName' in names
        assert 'ByTable' in names


# ── Relationship / association tests ─────────────────────────────────

class TestRelationshipAdaptation:

    def test_associations_become_relationships(self, full_qlik_data):
        result = adapt_qlik_for_generation(full_qlik_data)
        # Relationship should be injected into one of the datasources
        all_rels = []
        for ds in result['datasources']:
            all_rels.extend(ds.get('relationships', []))
        assert len(all_rels) >= 1
        rel = all_rels[0]
        assert rel['left']['table'] == 'Sales'
        assert rel['right']['table'] == 'Product'
        assert rel['left']['column'] == 'ProductId'

    def test_no_associations_no_relationships(self, minimal_qlik_data):
        result = adapt_qlik_for_generation(minimal_qlik_data)
        for ds in result['datasources']:
            assert ds.get('relationships', []) == []


# ── Calculation (measures + dimensions) tests ────────────────────────

class TestCalculationAdaptation:

    def test_measures_become_calculations(self, full_qlik_data):
        result = adapt_qlik_for_generation(full_qlik_data)
        measure_calcs = [c for c in result['calculations'] if c['role'] == 'measure']
        assert len(measure_calcs) >= 2
        names = {c['name'] for c in measure_calcs}
        assert 'Total Sales' in names
        assert 'Avg Sales' in names

    def test_measure_formula_preserved(self, full_qlik_data):
        result = adapt_qlik_for_generation(full_qlik_data)
        total = next(c for c in result['calculations'] if c['name'] == 'Total Sales')
        assert total['formula'] == 'Sum(SalesAmount)'

    def test_calculated_dimension_included(self, full_qlik_data):
        result = adapt_qlik_for_generation(full_qlik_data)
        dim_calcs = [c for c in result['calculations'] if c['role'] == 'dimension']
        names = {c['name'] for c in dim_calcs}
        assert 'YearMonth' in names

    def test_plain_dimension_excluded(self, full_qlik_data):
        """Plain field-reference dimensions should NOT become calculations."""
        result = adapt_qlik_for_generation(full_qlik_data)
        names = {c['name'] for c in result['calculations']}
        assert 'ProductCategory' not in names

    def test_duplicate_names_deduplicated(self):
        """Same measure name appearing twice should only produce one calc."""
        data = {
            'datasources': [],
            'dimensions': [],
            'measures': [
                {'name': 'Revenue', 'expression': 'Sum(Amt)'},
                {'name': 'Revenue', 'expression': 'Sum(Amt)'},
            ],
            'visualizations': [], 'sheets': [], 'variables': [],
            'loadscript': {}, 'associations': [], 'bookmarks': [],
            'master_items': [], 'app_metadata': {},
        }
        result = adapt_qlik_for_generation(data)
        revenue_calcs = [c for c in result['calculations'] if c['name'] == 'Revenue']
        assert len(revenue_calcs) == 1

    def test_master_item_measure(self, full_qlik_data):
        result = adapt_qlik_for_generation(full_qlik_data)
        names = {c['name'] for c in result['calculations']}
        assert 'Profit' in names

    def test_calculations_injected_into_datasource(self, full_qlik_data):
        result = adapt_qlik_for_generation(full_qlik_data)
        # Calculations should be nested inside the first datasource
        if result['datasources']:
            ds_calcs = result['datasources'][0].get('calculations', [])
            assert len(ds_calcs) > 0

    def test_no_measures_no_calculations(self, empty_qlik_data):
        result = adapt_qlik_for_generation(empty_qlik_data)
        assert result['calculations'] == []


# ── Visual / worksheet tests ────────────────────────────────────────

class TestWorksheetAdaptation:

    def test_visualizations_become_worksheets(self, full_qlik_data):
        result = adapt_qlik_for_generation(full_qlik_data)
        assert len(result['worksheets']) == 3

    def test_chart_type_mapped(self, full_qlik_data):
        result = adapt_qlik_for_generation(full_qlik_data)
        bar_ws = next(w for w in result['worksheets'] if w['name'] == 'Sales by Region')
        assert bar_ws['chart_type'] == 'clusteredBarChart'

    def test_kpi_type_mapped(self, full_qlik_data):
        result = adapt_qlik_for_generation(full_qlik_data)
        kpi_ws = next(w for w in result['worksheets'] if w['name'] == 'Revenue KPI')
        assert kpi_ws['chart_type'] == 'card'

    def test_worksheet_dimensions_and_measures(self, full_qlik_data):
        result = adapt_qlik_for_generation(full_qlik_data)
        bar_ws = next(w for w in result['worksheets'] if w['name'] == 'Sales by Region')
        assert len(bar_ws['dimensions']) >= 1
        assert len(bar_ws['measures']) >= 1

    def test_worksheet_fields_combined(self, full_qlik_data):
        result = adapt_qlik_for_generation(full_qlik_data)
        bar_ws = next(w for w in result['worksheets'] if w['name'] == 'Sales by Region')
        assert len(bar_ws['fields']) >= 2
        roles = {f['role'] for f in bar_ws['fields']}
        assert 'dimension' in roles
        assert 'measure' in roles

    def test_unknown_chart_type_defaults_to_bar(self):
        """Unknown Qlik chart type should default with a warning."""
        data = {
            'datasources': [], 'dimensions': [], 'measures': [],
            'visualizations': [{'type': 'unknownWidget', 'title': 'Mystery'}],
            'sheets': [], 'variables': [], 'loadscript': {},
            'associations': [], 'bookmarks': [], 'master_items': [],
            'app_metadata': {},
        }
        result = adapt_qlik_for_generation(data)
        assert result['worksheets'][0]['chart_type'] == 'clusteredBarChart'

    def test_visual_with_string_dimensions(self):
        """Dimensions given as plain strings (not dicts)."""
        data = {
            'datasources': [], 'dimensions': [], 'measures': [],
            'visualizations': [{
                'type': 'barchart', 'title': 'Plain',
                'dimensions': ['Region', 'Category'],
                'measures': ['Sales'],
            }],
            'sheets': [], 'variables': [], 'loadscript': {},
            'associations': [], 'bookmarks': [], 'master_items': [],
            'app_metadata': {},
        }
        result = adapt_qlik_for_generation(data)
        ws = result['worksheets'][0]
        assert len(ws['dimensions']) == 2
        assert ws['dimensions'][0]['field'] == 'Region'
        assert len(ws['measures']) == 1

    def test_no_visuals_no_worksheets(self, empty_qlik_data):
        result = adapt_qlik_for_generation(empty_qlik_data)
        assert result['worksheets'] == []


# ── Chart type mapping coverage ──────────────────────────────────────

class TestChartTypeMapping:
    """Verify all entries in _QLIK_CHART_TYPE_MAP produce valid PBI types."""

    KNOWN_PBI_TYPES = {
        'clusteredBarChart', 'lineStackedColumnComboChart', 'lineChart',
        'pieChart', 'scatterChart', 'tableEx', 'pivotTable', 'card',
        'gauge', 'map', 'treemap', 'waterfallChart', 'boxAndWhisker',
        'clusteredColumnChart', 'slicer', 'textbox', 'actionButton',
        'stackedBarChart', 'bulletChart', 'wordCloud', 'funnel',
        'donutChart', 'areaChart', 'stackedColumnChart', 'decompositionTree',
        'kpi',
    }

    def test_all_mapped_types_are_valid(self):
        for qlik_type, pbi_type in _QLIK_CHART_TYPE_MAP.items():
            assert pbi_type in self.KNOWN_PBI_TYPES, (
                f"Qlik type '{qlik_type}' maps to unknown PBI type '{pbi_type}'"
            )

    def test_map_has_reasonable_coverage(self):
        assert len(_QLIK_CHART_TYPE_MAP) >= 35


# ── Dashboard (sheet) tests ──────────────────────────────────────────

class TestDashboardAdaptation:

    def test_sheets_become_dashboards(self, full_qlik_data):
        result = adapt_qlik_for_generation(full_qlik_data)
        assert len(result['dashboards']) >= 1
        assert result['dashboards'][0]['name'] == 'Overview'

    def test_dashboard_has_size(self, full_qlik_data):
        result = adapt_qlik_for_generation(full_qlik_data)
        dash = result['dashboards'][0]
        assert 'size' in dash
        assert dash['size']['width'] == 1280
        assert dash['size']['height'] == 720

    def test_no_sheets_creates_fallback_dashboard(self):
        """If no sheets but visuals exist, a fallback dashboard is created."""
        data = {
            'datasources': [], 'dimensions': [], 'measures': [],
            'visualizations': [
                {'type': 'kpi', 'title': 'Rev KPI'},
                {'type': 'barchart', 'title': 'Top Sales'},
            ],
            'sheets': [],
            'variables': [], 'loadscript': {}, 'associations': [],
            'bookmarks': [], 'master_items': [], 'app_metadata': {},
        }
        result = adapt_qlik_for_generation(data)
        assert len(result['dashboards']) == 1
        assert result['dashboards'][0]['name'] == 'Dashboard'
        assert len(result['dashboards'][0]['objects']) == 2

    def test_no_sheets_no_visuals_no_dashboards(self, empty_qlik_data):
        result = adapt_qlik_for_generation(empty_qlik_data)
        assert result['dashboards'] == []


# ── Parameter (variable) tests ──────────────────────────────────────

class TestParameterAdaptation:

    def test_variables_become_parameters(self, full_qlik_data):
        result = adapt_qlik_for_generation(full_qlik_data)
        assert len(result['parameters']) >= 1
        names = {p['name'] for p in result['parameters']}
        assert 'vCurrentYear' in names

    def test_system_variables_excluded(self, full_qlik_data):
        result = adapt_qlik_for_generation(full_qlik_data)
        names = {p['name'] for p in result['parameters']}
        assert '$hidden' not in names
        assert '_internal' not in names

    def test_parameter_value_preserved(self, full_qlik_data):
        result = adapt_qlik_for_generation(full_qlik_data)
        param = next(p for p in result['parameters'] if p['name'] == 'vCurrentYear')
        assert param['value'] == '2024'
        assert param['currentValue'] == '2024'


# ── Story (bookmark) tests ──────────────────────────────────────────

class TestStoryAdaptation:

    def test_bookmarks_become_stories(self, full_qlik_data):
        result = adapt_qlik_for_generation(full_qlik_data)
        assert len(result['stories']) >= 1
        assert result['stories'][0]['name'] == 'Q1 Filter'

    def test_story_has_story_points(self, full_qlik_data):
        result = adapt_qlik_for_generation(full_qlik_data)
        story = result['stories'][0]
        assert 'story_points' in story
        assert len(story['story_points']) >= 1


# ── Custom SQL (loadscript) tests ────────────────────────────────────

class TestCustomSqlAdaptation:

    def test_loadscript_dict_becomes_custom_sql(self, full_qlik_data):
        result = adapt_qlik_for_generation(full_qlik_data)
        assert len(result['custom_sql']) >= 1
        assert 'LOAD' in result['custom_sql'][0]['query']

    def test_loadscript_string_becomes_custom_sql(self):
        data = {
            'datasources': [], 'dimensions': [], 'measures': [],
            'visualizations': [], 'sheets': [], 'variables': [],
            'loadscript': 'LOAD * FROM data.csv',
            'associations': [], 'bookmarks': [], 'master_items': [],
            'app_metadata': {},
        }
        result = adapt_qlik_for_generation(data)
        assert len(result['custom_sql']) == 1
        assert result['custom_sql'][0]['query'] == 'LOAD * FROM data.csv'

    def test_empty_loadscript_no_custom_sql(self, empty_qlik_data):
        result = adapt_qlik_for_generation(empty_qlik_data)
        assert result['custom_sql'] == []


# ── Deprecated alias test ────────────────────────────────────────────

class TestDeprecatedAlias:

    def test_old_name_emits_deprecation_warning(self, empty_qlik_data):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            adapt_qlik_to_tableau_format(empty_qlik_data)
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "adapt_qlik_for_generation" in str(w[0].message)

    def test_old_name_still_works(self, full_qlik_data):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            result = adapt_qlik_to_tableau_format(full_qlik_data)
            assert len(result['datasources']) == 2


# ── Expression passthrough tests ─────────────────────────────────────

class TestExpressionPassthrough:

    def test_complex_expression_preserved(self):
        expr = "Sum({<Year={$(vCurrentYear)}>} SalesAmount) / Count(DISTINCT CustomerId)"
        data = {
            'datasources': [], 'dimensions': [],
            'measures': [{'name': 'Complex', 'expression': expr}],
            'visualizations': [], 'sheets': [], 'variables': [],
            'loadscript': {}, 'associations': [], 'bookmarks': [],
            'master_items': [], 'app_metadata': {},
        }
        result = adapt_qlik_for_generation(data)
        calc = next(c for c in result['calculations'] if c['name'] == 'Complex')
        assert calc['formula'] == expr
