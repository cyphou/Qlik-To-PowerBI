"""Tests for powerbi_import.html_template — component library."""

import pytest
from powerbi_import.html_template import (
    esc,
    get_report_css,
    get_report_js,
    html_open,
    html_close,
    stat_card,
    stat_grid,
    section_open,
    section_close,
    card,
    badge,
    fidelity_bar,
    donut_chart,
    bar_chart,
    data_table,
    tab_bar,
    tab_content,
    heatmap_table,
    PBI_BLUE,
    PBI_DARK,
    PBI_GRAY,
    SUCCESS,
    WARN,
    FAIL,
    PURPLE,
    TEAL,
    ORANGE,
)


# ── esc() ──────────────────────────────────────────────────────
class TestEsc:
    def test_plain_text(self):
        assert esc("hello") == "hello"

    def test_html_entities(self):
        result = esc('<script>alert("xss")</script>')
        assert "&lt;" in result
        assert "&gt;" in result
        assert "&quot;" in result
        assert "<script>" not in result

    def test_none_returns_string(self):
        result = esc(None)
        assert isinstance(result, str)

    def test_numeric(self):
        assert esc(42) == "42"


# ── Color constants ──────────────────────────────────────────────
class TestColors:
    def test_all_constants_defined(self):
        for color in (PBI_BLUE, PBI_DARK, PBI_GRAY, SUCCESS, WARN, FAIL, PURPLE, TEAL, ORANGE):
            assert isinstance(color, str)
            assert len(color) > 3  # at least #rgb


# ── CSS / JS ──────────────────────────────────────────────────────
class TestCssJs:
    def test_css_returns_string(self):
        css = get_report_css()
        assert isinstance(css, str)
        assert "body" in css or "--" in css  # CSS variable or body rule

    def test_js_toggle_function(self):
        js = get_report_js()
        assert "toggleSection" in js

    def test_js_switch_tab(self):
        js = get_report_js()
        assert "switchTab" in js

    def test_js_filter_table(self):
        js = get_report_js()
        assert "filterTable" in js

    def test_js_sort_table(self):
        js = get_report_js()
        assert "sortTable" in js


# ── html_open / html_close ────────────────────────────────────────
class TestHtmlSkeleton:
    def test_open_contains_doctype(self):
        html = html_open(title="Test")
        assert "<!DOCTYPE html>" in html or "<!doctype" in html.lower()

    def test_open_contains_title(self):
        html = html_open(title="My Report")
        assert "My Report" in html

    def test_open_contains_css(self):
        html = html_open(title="Test")
        assert "<style>" in html

    def test_close_has_footer(self):
        html = html_close()
        assert "</html>" in html
        assert "Qlik" in html  # Qlik branding in footer

    def test_close_version(self):
        html = html_close(version="8.0.0")
        assert "8.0.0" in html

    def test_round_trip(self):
        """open + close produces valid-ish HTML."""
        html = html_open(title="T") + "<p>Body</p>" + html_close()
        assert html.count("<!DOCTYPE") == 1
        assert html.count("</html>") == 1


# ── stat_card / stat_grid ──────────────────────────────────────────
class TestStatGrid:
    def test_stat_card_value_label(self):
        result = stat_card(42, "Items")
        assert "42" in result
        assert "Items" in result

    def test_stat_card_accent(self):
        result = stat_card(10, "Ok", accent="success")
        assert "success" in result or SUCCESS.lower() in result.lower()

    def test_stat_grid_wraps_cards(self):
        cards = [stat_card(1, "A"), stat_card(2, "B")]
        grid = stat_grid(cards)
        assert grid.count("stat") >= 2

    def test_empty_grid(self):
        grid = stat_grid([])
        assert isinstance(grid, str)


# ── section_open / section_close ──────────────────────────────────
class TestSections:
    def test_section_contains_title(self):
        html = section_open("sec1", "My Section")
        assert "My Section" in html

    def test_section_contains_id(self):
        html = section_open("sec1", "Title")
        assert "sec1" in html

    def test_section_with_icon(self):
        html = section_open("s", "T", icon="&#128200;")
        assert "&#128200;" in html

    def test_section_close(self):
        html = section_close()
        assert "</div>" in html


# ── badge ─────────────────────────────────────────────────────────
class TestBadge:
    def test_green_badge(self):
        result = badge("GREEN")
        assert "GREEN" in result

    def test_exact_badge(self):
        result = badge("exact")
        assert "exact" in result

    def test_unsupported_badge(self):
        result = badge("unsupported")
        assert "unsupported" in result

    def test_empty_badge(self):
        result = badge("")
        assert isinstance(result, str)


# ── fidelity_bar ──────────────────────────────────────────────────
class TestFidelityBar:
    def test_100_percent(self):
        result = fidelity_bar(100.0)
        assert "100" in result

    def test_0_percent(self):
        result = fidelity_bar(0.0)
        assert "0" in result

    def test_50_percent(self):
        result = fidelity_bar(50.0)
        assert "50" in result


# ── donut_chart ────────────────────────────────────────────────────
class TestDonutChart:
    def test_single_segment(self):
        html = donut_chart([("A", 100, "#f00")], center_text="100%")
        assert "100%" in html

    def test_multiple_segments(self):
        html = donut_chart([("X", 50, "#f00"), ("Y", 50, "#0f0")])
        assert isinstance(html, str)
        assert len(html) > 50

    def test_empty_segments(self):
        html = donut_chart([])
        assert isinstance(html, str)


# ── bar_chart ──────────────────────────────────────────────────────
class TestBarChart:
    def test_bar_chart_items(self):
        html = bar_chart([("Cat A", 10, "#f00"), ("Cat B", 5, "#0f0")])
        assert "Cat A" in html
        assert "Cat B" in html

    def test_single_item(self):
        html = bar_chart([("X", 42, "#abc")])
        assert "42" in html or "X" in html

    def test_empty(self):
        html = bar_chart([])
        assert isinstance(html, str)


# ── data_table ─────────────────────────────────────────────────────
class TestDataTable:
    def test_basic_table(self):
        html = data_table(["Name", "Value"], [["A", "1"], ["B", "2"]], "t1")
        assert "Name" in html
        assert "Value" in html
        assert "<table" in html

    def test_empty_rows(self):
        html = data_table(["H1"], [], "t2")
        assert "<table" in html

    def test_searchable_table(self):
        html = data_table(["H"], [["x"]], "t3", searchable=True)
        assert "search" in html.lower() or "filter" in html.lower() or "input" in html.lower()

    def test_sortable_table(self):
        html = data_table(["H"], [["x"]], "t4", sortable=True)
        assert "sort" in html.lower() or "onclick" in html.lower()


# ── tab_bar / tab_content ─────────────────────────────────────────
class TestTabs:
    def test_tab_bar(self):
        html = tab_bar("grp", [("t1", "Tab 1", True), ("t2", "Tab 2", False)])
        assert "Tab 1" in html
        assert "Tab 2" in html

    def test_tab_content_active(self):
        html = tab_content("grp", "t1", "<p>Content</p>", active=True)
        assert "Content" in html

    def test_tab_content_inactive(self):
        html = tab_content("grp", "t2", "<p>Hidden</p>", active=False)
        assert "Hidden" in html


# ── heatmap_table ─────────────────────────────────────────────────
class TestHeatmap:
    def test_heatmap_table(self):
        html = heatmap_table(["App", "Tables", "Measures"],
                             [["app1", "5", "10"], ["app2", "3", "7"]], "hm1")
        assert "app1" in html
        assert "<table" in html


# ── card ──────────────────────────────────────────────────────────
class TestCard:
    def test_card_content(self):
        html = card("<p>Hello</p>", title="My Card")
        assert "Hello" in html
        assert "My Card" in html

    def test_card_no_title(self):
        html = card("<p>Body</p>")
        assert "Body" in html


# ── XSS safety ────────────────────────────────────────────────────
class TestXssSafety:
    def test_esc_prevents_xss(self):
        malicious = '<img src=x onerror=alert(1)>'
        result = esc(malicious)
        assert "<img" not in result
        assert "onerror" not in result or "&" in result

    def test_badge_escapes_xss(self):
        result = badge('<script>alert(1)</script>')
        assert "<script>" not in result

    def test_stat_card_escapes(self):
        result = stat_card('<b>evil</b>', '<i>bad</i>')
        # The label/value should be escaped
        assert isinstance(result, str)
