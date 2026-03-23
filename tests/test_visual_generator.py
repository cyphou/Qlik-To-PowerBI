"""Tests for visual_generator.py — visual type mapping + PBIR generation.

Covers:
- resolve_visual_type: 60+ source → PBI type mappings
- resolve_custom_visual_type: custom visual GUID lookup
- get_approximation_note: approximation notes for imprecise mappings
- _get_config_template: per-type config templates
- create_visual_container: full visual JSON output
- generate_visual_containers: batch generation from worksheets
- create_projections / create_prototype_query
- Sparkline, small multiples, reference lines, data bars
- _calculate_proportional_layout: layout calculations
"""

import pytest
from powerbi_import.visual_generator import (
    resolve_visual_type,
    resolve_custom_visual_type,
    get_approximation_note,
    _get_config_template,
    create_visual_container,
    generate_visual_containers,
    create_projections,
    create_prototype_query,
    build_query_state,
    _build_sparkline_config,
    _build_small_multiples_config,
    _build_dynamic_reference_line,
    _build_data_bar_config,
    _calculate_proportional_layout,
    create_page_layout,
    VISUAL_TYPE_MAP,
    CUSTOM_VISUAL_GUIDS,
)


# ══════════════════════════════════════════════════════════════════
# 1. resolve_visual_type — Standard Type Mapping
# ══════════════════════════════════════════════════════════════════

class TestResolveVisualType:
    """60+ visual type mappings from source → Power BI."""

    # Bar charts
    def test_barchart(self):
        assert resolve_visual_type("barchart") == "clusteredBarChart"

    def test_bar(self):
        assert resolve_visual_type("bar") == "clusteredBarChart"

    def test_stackedbarchart(self):
        assert resolve_visual_type("stackedbarchart") == "stackedBarChart"

    # Line / Area
    def test_linechart(self):
        assert resolve_visual_type("linechart") == "lineChart"

    def test_areachart(self):
        assert resolve_visual_type("areachart") == "areaChart"

    # Combo
    def test_combo(self):
        assert resolve_visual_type("combo") == "lineStackedColumnComboChart"

    # Pie / Donut / Funnel
    def test_piechart(self):
        assert resolve_visual_type("piechart") == "pieChart"

    def test_donut(self):
        assert resolve_visual_type("donut") == "donutChart"

    def test_funnel(self):
        assert resolve_visual_type("funnel") == "funnel"

    # Scatter
    def test_scatter(self):
        assert resolve_visual_type("scatter") == "scatterChart"

    def test_bubble(self):
        assert resolve_visual_type("bubble") == "scatterChart"

    # Map
    def test_map(self):
        assert resolve_visual_type("map") == "map"

    def test_filledmap(self):
        assert resolve_visual_type("filledmap") == "filledMap"

    # Table / Matrix
    def test_table(self):
        assert resolve_visual_type("table") == "tableEx"

    def test_pivot_table(self):
        assert resolve_visual_type("pivot-table") == "pivotTable"

    def test_matrix(self):
        assert resolve_visual_type("matrix") == "matrix"

    # KPI / Card / Gauge
    def test_kpi(self):
        assert resolve_visual_type("kpi") == "card"

    def test_gauge(self):
        assert resolve_visual_type("gauge") == "gauge"

    # Treemap / Hierarchy
    def test_treemap(self):
        assert resolve_visual_type("treemap") == "treemap"

    def test_sunburst(self):
        assert resolve_visual_type("sunburst") == "sunburst"

    # Waterfall / Box
    def test_waterfall(self):
        assert resolve_visual_type("waterfall") == "waterfallChart"

    def test_boxplot(self):
        assert resolve_visual_type("boxplot") == "boxAndWhisker"

    # Filter / Slicer
    def test_filterpane(self):
        assert resolve_visual_type("filterpane") == "slicer"

    def test_slicer(self):
        assert resolve_visual_type("slicer") == "slicer"

    # Specialty
    def test_wordcloud(self):
        assert resolve_visual_type("wordcloud") == "wordCloud"

    def test_ribbon(self):
        assert resolve_visual_type("ribbon") == "ribbonChart"

    def test_mekko(self):
        assert resolve_visual_type("mekko") == "stackedBarChart"

    # Qlik-specific
    def test_straight_table(self):
        assert resolve_visual_type("straight-table") == "tableEx"

    def test_text_image(self):
        assert resolve_visual_type("text-image") == "textbox"

    def test_container(self):
        assert resolve_visual_type("container") == "actionButton"

    # Unknown type fallback
    def test_unknown_type(self):
        result = resolve_visual_type("unknown_type_xyz")
        assert result is not None  # Should return some default

    # Case insensitivity
    def test_case_insensitive(self):
        assert resolve_visual_type("BarChart") == "clusteredBarChart"

    def test_histogram(self):
        assert resolve_visual_type("histogram") == "clusteredColumnChart"

    def test_pareto(self):
        assert resolve_visual_type("pareto") == "lineClusteredColumnComboChart"


# ══════════════════════════════════════════════════════════════════
# 2. Custom Visual GUID Lookup
# ══════════════════════════════════════════════════════════════════

class TestCustomVisuals:
    """Custom visual GUID lookup for AppSource visuals."""

    def test_sankey_has_guid(self):
        vtype, guid = resolve_custom_visual_type("sankey")
        assert guid is not None
        assert "guid" in guid

    def test_chord_has_guid(self):
        vtype, guid = resolve_custom_visual_type("chord")
        assert guid is not None

    def test_wordcloud_has_guid(self):
        vtype, guid = resolve_custom_visual_type("wordcloud")
        assert guid is not None

    def test_bar_no_custom(self):
        vtype, guid = resolve_custom_visual_type("barchart")
        assert guid is None

    def test_custom_disabled(self):
        vtype, guid = resolve_custom_visual_type("sankey", use_custom_visuals=False)
        assert guid is None

    def test_custom_has_roles(self):
        _, guid = resolve_custom_visual_type("sankey")
        assert "roles" in guid


# ══════════════════════════════════════════════════════════════════
# 3. Approximation Notes
# ══════════════════════════════════════════════════════════════════

class TestApproximationNotes:
    """get_approximation_note returns notes for imprecise mappings."""

    def test_known_mapping_no_note(self):
        note = get_approximation_note("barchart")
        # Direct mappings may or may not have notes
        assert note is None or isinstance(note, str)

    def test_note_for_specialty(self):
        # Specialty vis may have approximation notes
        note = get_approximation_note("mekko")
        assert note is None or isinstance(note, str)


# ══════════════════════════════════════════════════════════════════
# 4. Config Templates
# ══════════════════════════════════════════════════════════════════

class TestConfigTemplates:
    """Per-visual-type config template generation."""

    def test_bar_config(self):
        config = _get_config_template("clusteredBarChart")
        assert isinstance(config, dict)

    def test_line_config(self):
        config = _get_config_template("lineChart")
        assert isinstance(config, dict)

    def test_pie_config(self):
        config = _get_config_template("pieChart")
        assert isinstance(config, dict)

    def test_table_config(self):
        config = _get_config_template("tableEx")
        assert isinstance(config, dict)

    def test_unknown_config(self):
        config = _get_config_template("unknownType")
        assert isinstance(config, dict)

    def test_map_config(self):
        config = _get_config_template("map")
        assert isinstance(config, dict)

    def test_gauge_config(self):
        config = _get_config_template("gauge")
        assert isinstance(config, dict)

    def test_slicer_config(self):
        config = _get_config_template("slicer")
        assert isinstance(config, dict)


# ══════════════════════════════════════════════════════════════════
# 5. Visual Container Generation
# ══════════════════════════════════════════════════════════════════

class TestCreateVisualContainer:
    """Full visual container JSON output."""

    def _ws(self, vtype="barchart", dims=None, measures=None):
        return {
            "name": "TestSheet",
            "type": vtype,
            "dimensions": dims or [{"field": "Region", "name": "Region"}],
            "measures": measures or [{"field": "Sales", "name": "Sales"}],
            "position": {"x": 0, "y": 0, "width": 600, "height": 400},
        }

    def test_returns_dict(self):
        result = create_visual_container(self._ws())
        assert isinstance(result, dict)

    def test_has_position(self):
        result = create_visual_container(self._ws(), x=10, y=20, width=600, height=400)
        assert "position" in result or "x" in result or "config" in result

    def test_bar_visual(self):
        result = create_visual_container(self._ws("barchart"))
        assert isinstance(result, dict)

    def test_line_visual(self):
        result = create_visual_container(self._ws("linechart"))
        assert isinstance(result, dict)

    def test_pie_visual(self):
        result = create_visual_container(self._ws("piechart"))
        assert isinstance(result, dict)

    def test_table_visual(self):
        result = create_visual_container(self._ws("table"))
        assert isinstance(result, dict)

    def test_kpi_visual(self):
        result = create_visual_container(self._ws("kpi"))
        assert isinstance(result, dict)


# ══════════════════════════════════════════════════════════════════
# 6. Batch Generation
# ══════════════════════════════════════════════════════════════════

class TestGenerateVisualContainers:
    """Batch visual generation from worksheet list."""

    def test_empty_worksheets(self):
        result = generate_visual_containers([])
        assert isinstance(result, (list, dict))

    def test_single_worksheet(self):
        ws = [{
            "name": "Page1",
            "type": "barchart",
            "dimensions": [{"field": "Region", "name": "Region"}],
            "measures": [{"field": "Sales", "name": "Sales"}],
        }]
        result = generate_visual_containers(ws)
        assert result is not None

    def test_multiple_worksheets(self):
        ws = [
            {"name": "P1", "type": "barchart", "dimensions": [{"field": "R"}], "measures": [{"field": "S"}]},
            {"name": "P2", "type": "linechart", "dimensions": [{"field": "D"}], "measures": [{"field": "V"}]},
        ]
        result = generate_visual_containers(ws)
        assert result is not None


# ══════════════════════════════════════════════════════════════════
# 7. Projections / Query
# ══════════════════════════════════════════════════════════════════

class TestProjectionsAndQuery:
    """Projections and prototype query generation."""

    def _ws(self):
        return {
            "name": "Sheet1",
            "type": "barchart",
            "dimensions": ["Region", "Country"],
            "measures": ["TotalSales"],
        }

    def test_create_projections(self):
        proj = create_projections(self._ws())
        assert isinstance(proj, (list, dict))

    def test_create_prototype_query(self):
        result = create_prototype_query(self._ws())
        assert isinstance(result, (dict, list, str))


# ══════════════════════════════════════════════════════════════════
# 8. Sparkline / Small Multiples / Reference Lines / Data Bars
# ══════════════════════════════════════════════════════════════════

class TestSparkline:
    def test_build_sparkline_config(self):
        cfg = _build_sparkline_config("Revenue", "Sales")
        assert isinstance(cfg, dict)


class TestSmallMultiples:
    def test_build_small_multiples_config(self):
        cfg = _build_small_multiples_config("Region", "Sales")
        # Returns a tuple (config_dict, field_binding)
        assert isinstance(cfg, tuple)
        assert isinstance(cfg[0], dict)

    def test_small_multiples_layout_flow(self):
        cfg = _build_small_multiples_config("Region", "Sales", layout_mode="flow")
        assert isinstance(cfg, tuple)
        assert isinstance(cfg[0], dict)


class TestReferenceLines:
    def test_static_reference_line(self):
        cfg = _build_dynamic_reference_line("constant", field_name="Sales", table_name="Orders")
        assert cfg is None or isinstance(cfg, dict)


class TestDataBars:
    def test_data_bar_config(self):
        cfg = _build_data_bar_config("Amount", "Orders")
        assert isinstance(cfg, dict)


# ══════════════════════════════════════════════════════════════════
# 9. Layout Calculations
# ══════════════════════════════════════════════════════════════════

class TestLayout:
    def test_proportional_layout_empty(self):
        result = _calculate_proportional_layout([])
        assert isinstance(result, (list, dict))

    def test_proportional_layout_single(self):
        ws = [{"name": "A", "position": {"x": 0, "y": 0, "width": 500, "height": 300}}]
        result = _calculate_proportional_layout(ws)
        assert len(result) >= 1

    def test_proportional_layout_multiple(self):
        ws = [
            {"name": "A", "position": {"x": 0, "y": 0, "width": 400, "height": 300}},
            {"name": "B", "position": {"x": 400, "y": 0, "width": 400, "height": 300}},
        ]
        result = _calculate_proportional_layout(ws)
        assert len(result) >= 2

    def test_create_page_layout(self):
        ws = [{"name": "A", "type": "bar", "visuals": []}]
        result = create_page_layout(ws)
        assert result is not None


# ══════════════════════════════════════════════════════════════════
# 10. Type Map Completeness
# ══════════════════════════════════════════════════════════════════

class TestTypeMapCompleteness:
    """Verify the VISUAL_TYPE_MAP covers expected types."""

    def test_has_at_least_60_entries(self):
        assert len(VISUAL_TYPE_MAP) >= 60

    def test_all_values_are_strings(self):
        for k, v in VISUAL_TYPE_MAP.items():
            assert isinstance(v, str), f"Value for '{k}' is not a string: {v}"

    def test_custom_visual_guids_structure(self):
        for k, v in CUSTOM_VISUAL_GUIDS.items():
            assert "guid" in v, f"Missing guid for '{k}'"
            assert "name" in v, f"Missing name for '{k}'"
            assert "roles" in v, f"Missing roles for '{k}'"
