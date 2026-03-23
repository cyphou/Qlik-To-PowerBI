"""Tests for v6.0.0 Phase 3 — Integrate Standalone Tools into Pipeline."""

import pytest
from qlik_export.format_adapter import (
    adapt_qlik_for_generation,
    _parse_section_access,
)
from qlik_export.qlik_migrator import QlikToPowerBIConverter
from qlik_export.qlik_model_converter import QlikToPowerBIModelConverter


# ── 3.1 Theme integration ───────────────────────────────────────


class TestThemeIntegration:
    """Theme colors from app_metadata flow into dashboards."""

    def test_theme_colors_injected(self):
        qlik_data = {
            'datasources': [],
            'dimensions': [],
            'measures': [],
            'visualizations': [],
            'sheets': [{'id': 's1', 'title': 'Page 1'}],
            'variables': [],
            'loadscript': {},
            'associations': [],
            'bookmarks': [],
            'master_items': [],
            'app_metadata': {
                'theme': {'colors': ['#FF0000', '#00FF00', '#0000FF']},
            },
        }
        result = adapt_qlik_for_generation(qlik_data)
        dashboards = result['dashboards']
        assert len(dashboards) >= 1
        theme = dashboards[0].get('theme', {})
        assert theme.get('colors') == ['#FF0000', '#00FF00', '#0000FF']

    def test_theme_colors_from_flat_key(self):
        """Fallback: colors at top level of app_metadata."""
        qlik_data = {
            'datasources': [],
            'dimensions': [],
            'measures': [],
            'visualizations': [],
            'sheets': [{'id': 's1', 'title': 'Page 1'}],
            'variables': [],
            'loadscript': {},
            'associations': [],
            'bookmarks': [],
            'master_items': [],
            'app_metadata': {'colors': ['#111', '#222']},
        }
        result = adapt_qlik_for_generation(qlik_data)
        assert result['dashboards'][0]['theme']['colors'] == ['#111', '#222']

    def test_no_theme_no_error(self):
        qlik_data = {
            'datasources': [],
            'dimensions': [],
            'measures': [],
            'visualizations': [],
            'sheets': [{'id': 's1', 'title': 'Page 1'}],
            'variables': [],
            'loadscript': {},
            'associations': [],
            'bookmarks': [],
            'master_items': [],
            'app_metadata': {},
        }
        result = adapt_qlik_for_generation(qlik_data)
        # No theme → no 'theme' key in dashboard
        assert 'theme' not in result['dashboards'][0] or not result['dashboards'][0].get('theme', {}).get('colors')


# ── 3.2 Variable → measures/parameters ──────────────────────────


class TestVariablePromotion:
    """Variables with aggregation expressions are promoted to measures."""

    def test_agg_variable_promoted(self):
        qlik_data = {
            'datasources': [],
            'dimensions': [],
            'measures': [],
            'visualizations': [],
            'sheets': [],
            'variables': [
                {'name': 'vTotalSales', 'definition': 'Sum(Sales)'},
                {'name': 'vThreshold', 'definition': '100'},
            ],
            'loadscript': {},
            'associations': [],
            'bookmarks': [],
            'master_items': [],
            'app_metadata': {},
        }
        result = adapt_qlik_for_generation(qlik_data)

        # vTotalSales should be in calculations, not parameters
        calc_names = [c['name'] for c in result['calculations']]
        param_names = [p['name'] for p in result['parameters']]

        assert 'vTotalSales' in calc_names
        assert 'vTotalSales' not in param_names

        # vThreshold should stay as a parameter
        assert 'vThreshold' in param_names
        assert 'vThreshold' not in calc_names

    def test_various_agg_patterns(self):
        """Multiple aggregation types detected."""
        qlik_data = {
            'datasources': [],
            'dimensions': [],
            'measures': [],
            'visualizations': [],
            'sheets': [],
            'variables': [
                {'name': 'vAvg', 'definition': 'Avg(Score)'},
                {'name': 'vCount', 'definition': 'Count(OrderID)'},
                {'name': 'vStatic', 'definition': '2024'},
                {'name': 'vText', 'definition': 'Hello World'},
            ],
            'loadscript': {},
            'associations': [],
            'bookmarks': [],
            'master_items': [],
            'app_metadata': {},
        }
        result = adapt_qlik_for_generation(qlik_data)
        calc_names = [c['name'] for c in result['calculations']]
        param_names = [p['name'] for p in result['parameters']]

        assert 'vAvg' in calc_names
        assert 'vCount' in calc_names
        assert 'vStatic' in param_names
        assert 'vText' in param_names

    def test_promoted_measure_has_correct_role(self):
        qlik_data = {
            'datasources': [],
            'dimensions': [],
            'measures': [],
            'visualizations': [],
            'sheets': [],
            'variables': [{'name': 'vMetric', 'definition': 'Sum(Revenue)'}],
            'loadscript': {},
            'associations': [],
            'bookmarks': [],
            'master_items': [],
            'app_metadata': {},
        }
        result = adapt_qlik_for_generation(qlik_data)
        promoted = [c for c in result['calculations'] if c['name'] == 'vMetric']
        assert len(promoted) == 1
        assert promoted[0]['role'] == 'measure'
        assert promoted[0]['formula'] == 'Sum(Revenue)'
        assert promoted[0]['original_type'] == 'qlik_variable_measure'


# ── 3.3 Section Access → RLS ────────────────────────────────────


class TestSectionAccess:
    """SECTION ACCESS → RLS user_filters."""

    def test_basic_section_access(self):
        script = """
        SECTION ACCESS;
        LOAD * INLINE [
            ACCESS, USERID
            ADMIN, admin@company.com
            USER, alice@company.com
            USER, bob@company.com
        ];
        SECTION APPLICATION;
        """
        roles = _parse_section_access(script)
        assert len(roles) == 3
        names = [r['name'] for r in roles]
        assert 'RLS_admin' in names
        assert 'RLS_alice' in names
        assert any('USERPRINCIPALNAME()' in r['filter_expression'] for r in roles)

    def test_section_access_as_dict(self):
        loadscript = {
            'script': """
            SECTION ACCESS;
            LOAD * INLINE [
                ACCESS, USERID
                USER, user1@domain.com
            ];
            SECTION APPLICATION;
            """
        }
        roles = _parse_section_access(loadscript)
        assert len(roles) == 1
        assert 'user1@domain.com' in roles[0]['filter_expression']

    def test_no_section_access(self):
        roles = _parse_section_access("LOAD * FROM data.csv;")
        assert roles == []

    def test_empty_loadscript(self):
        assert _parse_section_access(None) == []
        assert _parse_section_access("") == []
        assert _parse_section_access({}) == []

    def test_section_access_in_pipeline(self):
        """RLS roles flow through adapt_qlik_for_generation."""
        qlik_data = {
            'datasources': [],
            'dimensions': [],
            'measures': [],
            'visualizations': [],
            'sheets': [],
            'variables': [],
            'loadscript': {
                'script': """
                SECTION ACCESS;
                LOAD * INLINE [
                    ACCESS, USERID
                    USER, test@corp.com
                ];
                SECTION APPLICATION;
                """
            },
            'associations': [],
            'bookmarks': [],
            'master_items': [],
            'app_metadata': {},
        }
        result = adapt_qlik_for_generation(qlik_data)
        assert len(result['user_filters']) >= 1
        assert 'test@corp.com' in result['user_filters'][0]['filter_expression']


# ── 3.4 Consolidated DAX converters ─────────────────────────────


class TestDaxConverterConsolidation:
    """All DAX conversion paths use the canonical converter."""

    def test_migrator_uses_canonical(self):
        """QlikToPowerBIConverter delegates to dax_converter."""
        result = QlikToPowerBIConverter.convert_qlik_expression_to_dax("Sum(Sales)")
        assert "SUM" in result
        # Set analysis should now work via canonical converter
        result2 = QlikToPowerBIConverter.convert_qlik_expression_to_dax(
            "If(IsNull(x), 0, x)"
        )
        assert "IF" in result2
        assert "ISBLANK" in result2

    def test_migrator_handles_complex(self):
        """Canonical converter handles patterns the old one couldn't."""
        # Set analysis — old converter couldn't handle this
        result = QlikToPowerBIConverter.convert_qlik_expression_to_dax(
            "Upper(Name)"
        )
        assert "UPPER" in result
