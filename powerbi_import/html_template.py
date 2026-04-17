"""
Shared HTML template module for Qlik → Power BI migration reports.

Provides a unified CSS framework (Fluent / Power BI design language),
JavaScript helpers, and reusable HTML component builders for consistent,
professional HTML reports.

Usage::

    from powerbi_import.html_template import (
        html_open, html_close, stat_card, stat_grid, section_open,
        section_close, badge, fidelity_bar, donut_chart, bar_chart,
        data_table, tab_bar, tab_content, card, heatmap_table, esc,
    )
"""

from __future__ import annotations

import datetime
from typing import Any, Dict, List, Optional, Tuple

# ═══════════════════════════════════════════════════════════════════════
#  Design tokens — Fluent / Power BI design language
# ═══════════════════════════════════════════════════════════════════════

PBI_BLUE = "#0078d4"
PBI_DARK_BLUE = "#004578"
PBI_LIGHT_BLUE = "#deecf9"
PBI_DARK = "#323130"
PBI_GRAY = "#605e5c"
PBI_LIGHT_GRAY = "#a19f9d"
PBI_BG = "#faf9f8"
PBI_SURFACE = "#ffffff"
SUCCESS = "#107c10"
SUCCESS_BG = "#dff6dd"
WARN = "#797600"
WARN_BG = "#fff4ce"
FAIL = "#a4262c"
FAIL_BG = "#fde7e9"
PURPLE = "#8764b8"
TEAL = "#038387"
ORANGE = "#ca5010"


def esc(text: Any) -> str:
    """HTML-escape a string."""
    return (str(text)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))


# ═══════════════════════════════════════════════════════════════════════
#  CSS Framework
# ═══════════════════════════════════════════════════════════════════════

def get_report_css() -> str:
    """Return the complete shared CSS for all reports."""
    return """
    :root {
        --pbi-blue: #0078d4;
        --pbi-dark-blue: #004578;
        --pbi-light-blue: #deecf9;
        --pbi-dark: #323130;
        --pbi-gray: #605e5c;
        --pbi-light-gray: #a19f9d;
        --pbi-bg: #faf9f8;
        --pbi-surface: #ffffff;
        --success: #107c10;
        --success-bg: #dff6dd;
        --warn: #797600;
        --warn-bg: #fff4ce;
        --fail: #a4262c;
        --fail-bg: #fde7e9;
        --purple: #8764b8;
        --teal: #038387;
        --orange: #ca5010;
        --shadow-sm: 0 1.6px 3.6px rgba(0,0,0,0.13), 0 0.3px 0.9px rgba(0,0,0,0.11);
        --shadow-md: 0 3.2px 7.2px rgba(0,0,0,0.13), 0 0.6px 1.8px rgba(0,0,0,0.11);
        --shadow-lg: 0 6.4px 14.4px rgba(0,0,0,0.13), 0 1.2px 3.6px rgba(0,0,0,0.11);
        --radius: 8px;
        --radius-sm: 4px;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
        font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, 'Helvetica Neue', sans-serif;
        background: var(--pbi-bg); color: var(--pbi-dark); line-height: 1.5;
        -webkit-font-smoothing: antialiased;
    }
    .report-header {
        background: linear-gradient(135deg, #0078d4 0%, #004578 100%);
        color: #fff; padding: 32px 40px 28px; margin-bottom: 24px;
    }
    .report-header h1 { font-size: 1.75em; font-weight: 600; letter-spacing: -0.02em; margin-bottom: 6px; }
    .report-header .subtitle { font-size: 0.9em; opacity: 0.85; font-weight: 400; }
    .report-header .meta { display: flex; gap: 16px; margin-top: 12px; font-size: 0.82em; opacity: 0.7; }
    .report-header .meta span { display: flex; align-items: center; gap: 4px; }
    .container { max-width: 1440px; margin: 0 auto; padding: 0 24px 40px; }
    .section-header {
        display: flex; align-items: center; gap: 10px; padding: 14px 0 10px;
        margin-top: 28px; border-bottom: 2px solid #edebe9; cursor: pointer;
        user-select: none; transition: border-color 0.2s;
    }
    .section-header:hover { border-bottom-color: var(--pbi-blue); }
    .section-header h2 { font-size: 1.15em; font-weight: 600; color: var(--pbi-dark); flex: 1; }
    .section-header .section-icon { font-size: 1.2em; width: 28px; text-align: center; }
    .section-header .toggle-arrow { font-size: 0.7em; color: var(--pbi-light-gray); transition: transform 0.3s ease; }
    .section-header .toggle-arrow.collapsed { transform: rotate(-90deg); }
    .section-body { overflow: hidden; transition: max-height 0.35s ease, opacity 0.25s ease; max-height: 8000px; opacity: 1; }
    .section-body.collapsed { max-height: 0 !important; opacity: 0; }
    .stat-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(155px, 1fr)); gap: 14px; margin: 16px 0; }
    .stat-card {
        background: var(--pbi-surface); border-radius: var(--radius); padding: 20px 16px;
        text-align: center; box-shadow: var(--shadow-sm); transition: transform 0.15s ease, box-shadow 0.15s ease;
        border-top: 3px solid transparent;
    }
    .stat-card:hover { transform: translateY(-2px); box-shadow: var(--shadow-md); }
    .stat-card .stat-value { font-size: 2em; font-weight: 700; line-height: 1.1; color: var(--pbi-blue); }
    .stat-card .stat-label { font-size: 0.8em; color: var(--pbi-gray); margin-top: 6px; font-weight: 500; text-transform: uppercase; letter-spacing: 0.04em; }
    .stat-card.accent-success { border-top-color: var(--success); }
    .stat-card.accent-success .stat-value { color: var(--success); }
    .stat-card.accent-warn { border-top-color: #c19c00; }
    .stat-card.accent-warn .stat-value { color: #c19c00; }
    .stat-card.accent-fail { border-top-color: var(--fail); }
    .stat-card.accent-fail .stat-value { color: var(--fail); }
    .stat-card.accent-purple { border-top-color: var(--purple); }
    .stat-card.accent-purple .stat-value { color: var(--purple); }
    .stat-card.accent-teal { border-top-color: var(--teal); }
    .stat-card.accent-teal .stat-value { color: var(--teal); }
    .stat-card.accent-blue { border-top-color: var(--pbi-blue); }
    .card { background: var(--pbi-surface); border-radius: var(--radius); padding: 20px 24px; margin: 14px 0; box-shadow: var(--shadow-sm); }
    .card h3 { font-size: 1em; font-weight: 600; color: var(--pbi-dark); margin-bottom: 14px; }
    .card h4 { font-size: 0.92em; font-weight: 600; color: var(--pbi-gray); margin: 18px 0 10px; }
    .table-container { overflow-x: auto; border-radius: var(--radius); box-shadow: var(--shadow-sm); margin: 14px 0; }
    table { border-collapse: collapse; width: 100%; font-size: 0.85em; background: var(--pbi-surface); }
    thead th {
        background: var(--pbi-blue); color: #fff; padding: 11px 14px; text-align: left;
        font-weight: 600; font-size: 0.82em; text-transform: uppercase; letter-spacing: 0.04em;
        position: sticky; top: 0; z-index: 2; white-space: nowrap;
    }
    thead th.sortable { cursor: pointer; user-select: none; }
    thead th.sortable:hover { background: #106ebe; }
    thead th .sort-icon { display: inline-block; margin-left: 4px; opacity: 0.5; font-size: 0.9em; }
    .detail-table thead th { background: var(--pbi-gray); }
    tbody td { padding: 9px 14px; border-bottom: 1px solid #edebe9; vertical-align: middle; }
    tbody tr:hover { background: #f3f2f1; }
    tbody tr:last-child td { border-bottom: none; }
    .table-search { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; }
    .table-search input {
        font-family: inherit; font-size: 0.85em; padding: 7px 12px;
        border: 1px solid #d2d0ce; border-radius: var(--radius-sm); width: 260px;
        outline: none; transition: border-color 0.2s;
    }
    .table-search input:focus { border-color: var(--pbi-blue); box-shadow: 0 0 0 2px rgba(0,120,212,0.2); }
    .table-search label { font-size: 0.82em; color: var(--pbi-gray); }
    .badge { display: inline-block; padding: 2px 10px; border-radius: 12px; font-weight: 600; font-size: 0.78em; letter-spacing: 0.02em; text-transform: uppercase; }
    .badge-green  { background: var(--success-bg); color: var(--success); }
    .badge-yellow { background: var(--warn-bg); color: var(--warn); }
    .badge-red    { background: var(--fail-bg); color: var(--fail); }
    .badge-blue   { background: var(--pbi-light-blue); color: var(--pbi-dark-blue); }
    .badge-gray   { background: #edebe9; color: var(--pbi-gray); }
    .badge-purple { background: #f3e8fd; color: #5c2d91; }
    .badge-teal   { background: #d4f4f4; color: #005b5e; }
    .tag { display: inline-block; padding: 2px 8px; border-radius: var(--radius-sm); font-size: 0.78em; font-weight: 500; white-space: nowrap; }
    .tag-connector { background: #e8f0fe; color: #1a73e8; }
    .tag-success   { background: var(--success-bg); color: var(--success); }
    .tag-warn      { background: var(--warn-bg); color: #856404; }
    .tag-danger    { background: var(--fail-bg); color: var(--fail); }
    .tag-dim       { background: #e8eaf6; color: #283593; }
    .tag-measure   { background: #fce4ec; color: #b71c1c; }
    .fidelity-bar { display: inline-flex; align-items: center; gap: 8px; vertical-align: middle; }
    .fidelity-track { width: 120px; height: 8px; background: #edebe9; border-radius: 4px; overflow: hidden; }
    .fidelity-fill { height: 100%; border-radius: 4px; transition: width 0.5s ease; }
    .fidelity-label { font-size: 0.82em; font-weight: 600; min-width: 46px; }
    .chart-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px; margin: 16px 0; }
    .chart-card { background: var(--pbi-surface); border-radius: var(--radius); padding: 20px 24px; box-shadow: var(--shadow-sm); }
    .chart-card h4 { font-size: 0.9em; font-weight: 600; color: var(--pbi-dark); margin-bottom: 14px; }
    .donut-container { display: flex; align-items: center; justify-content: center; gap: 28px; }
    .donut { width: 150px; height: 150px; }
    .donut circle { transition: stroke-dasharray 0.8s ease; }
    .donut-legend { font-size: 0.85em; line-height: 2; }
    .legend-dot { display: inline-block; width: 12px; height: 12px; border-radius: 3px; margin-right: 8px; vertical-align: middle; }
    .bar-chart { display: flex; flex-direction: column; gap: 8px; }
    .bar-row { display: flex; align-items: center; gap: 10px; }
    .bar-label { width: 110px; text-align: right; font-size: 0.82em; color: var(--pbi-gray); flex-shrink: 0; font-weight: 500; }
    .bar-track { flex: 1; height: 24px; background: #edebe9; border-radius: var(--radius-sm); overflow: hidden; position: relative; }
    .bar-fill {
        height: 100%; border-radius: var(--radius-sm); display: flex; align-items: center;
        justify-content: flex-end; padding-right: 8px; color: #fff; font-size: 0.75em;
        font-weight: 600; transition: width 0.5s ease; min-width: 0;
    }
    .bar-value { font-size: 0.82em; color: var(--pbi-gray); width: 36px; text-align: right; font-weight: 600; }
    .tab-bar { display: flex; gap: 4px; border-bottom: 2px solid #edebe9; margin-bottom: 14px; overflow-x: auto; }
    .tab {
        padding: 8px 18px; cursor: pointer; font-size: 0.85em; font-weight: 500;
        border-radius: var(--radius-sm) var(--radius-sm) 0 0; transition: all 0.2s;
        color: var(--pbi-gray); white-space: nowrap; border-bottom: 2px solid transparent; margin-bottom: -2px;
    }
    .tab:hover { background: var(--pbi-light-blue); color: var(--pbi-blue); }
    .tab.active { color: var(--pbi-blue); font-weight: 600; border-bottom-color: var(--pbi-blue); background: transparent; }
    .tab-content { display: none; }
    .tab-content.active { display: block; }
    .heatmap td { text-align: center; font-weight: 600; font-size: 0.82em; transition: background 0.2s; }
    .heatmap td.heat-label { text-align: left; font-weight: 600; color: var(--pbi-dark); background: transparent !important; }
    .mono { font-family: 'Cascadia Code', 'Consolas', 'Monaco', monospace; font-size: 0.85em; }
    code { background: #f3f2f1; padding: 2px 6px; border-radius: 3px; font-family: 'Cascadia Code', 'Consolas', 'Monaco', monospace; font-size: 0.88em; }
    .text-success { color: var(--success); }
    .text-warn    { color: #c19c00; }
    .text-fail    { color: var(--fail); }
    .text-blue    { color: var(--pbi-blue); }
    .text-gray    { color: var(--pbi-gray); }
    .text-muted   { color: var(--pbi-light-gray); }
    .fw-bold      { font-weight: 600; }
    .fs-sm        { font-size: 0.85em; }
    .mt-0         { margin-top: 0; }
    .mb-0         { margin-bottom: 0; }
    .nowrap       { white-space: nowrap; }
    .report-footer { text-align: center; padding: 28px 20px; margin-top: 40px; border-top: 1px solid #edebe9; color: var(--pbi-light-gray); font-size: 0.82em; }
    .report-footer a { color: var(--pbi-blue); text-decoration: none; }
    @media print {
        .report-header { background: #0078d4 !important; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
        .section-body { max-height: none !important; opacity: 1 !important; }
        .section-header { cursor: default; } .toggle-arrow { display: none; }
        .stat-card, .card { break-inside: avoid; } .table-search { display: none; } body { background: #fff; }
    }
    @media (max-width: 768px) {
        .report-header { padding: 20px; } .report-header h1 { font-size: 1.3em; }
        .container { padding: 0 12px 20px; }
        .stat-grid { grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); }
        .chart-row { grid-template-columns: 1fr; } .bar-label { width: 80px; }
        .donut-container { flex-direction: column; }
    }
    /* ── Dark theme (toggle or system preference) ──────────── */
    [data-theme="dark"] {
        --pbi-bg: #1b1a19; --pbi-surface: #252423; --pbi-dark: #f3f2f1;
        --pbi-gray: #b3b0ad; --pbi-light-gray: #8a8886;
        --shadow-sm: 0 1.6px 3.6px rgba(0,0,0,0.4), 0 0.3px 0.9px rgba(0,0,0,0.3);
        --shadow-md: 0 3.2px 7.2px rgba(0,0,0,0.4), 0 0.6px 1.8px rgba(0,0,0,0.3);
    }
    [data-theme="dark"] body { background: var(--pbi-bg); color: var(--pbi-dark); }
    [data-theme="dark"] .report-header { background: linear-gradient(135deg, #004578 0%, #001d33 100%); }
    [data-theme="dark"] .stat-card,
    [data-theme="dark"] .card,
    [data-theme="dark"] .chart-card { background: var(--pbi-surface); }
    [data-theme="dark"] table { background: var(--pbi-surface); }
    [data-theme="dark"] thead th { background: #004578; }
    [data-theme="dark"] thead th.sortable:hover { background: #005a9e; }
    [data-theme="dark"] .detail-table thead th { background: #3b3a39; }
    [data-theme="dark"] tbody td { border-bottom-color: #3b3a39; }
    [data-theme="dark"] tbody tr:hover { background: #323130; }
    [data-theme="dark"] .section-header { border-bottom-color: #3b3a39; }
    [data-theme="dark"] .section-header:hover { border-bottom-color: #2b88d8; }
    [data-theme="dark"] .tab-bar { border-bottom-color: #3b3a39; }
    [data-theme="dark"] .tab:hover { background: rgba(0,120,212,0.15); }
    [data-theme="dark"] .fidelity-track,
    [data-theme="dark"] .bar-track { background: #3b3a39; }
    [data-theme="dark"] .badge-gray { background: #3b3a39; color: #b3b0ad; }
    [data-theme="dark"] .badge-green { background: #1a3a1a; color: #6ccb5f; }
    [data-theme="dark"] .badge-yellow { background: #3a3500; color: #d4c75f; }
    [data-theme="dark"] .badge-red { background: #4a1a1d; color: #f5707a; }
    [data-theme="dark"] .badge-blue { background: #1a3a5c; color: #6cb8f6; }
    [data-theme="dark"] .badge-purple { background: #2d1a4e; color: #c4a5f0; }
    [data-theme="dark"] .badge-teal { background: #1a3a3a; color: #5fd4d4; }
    [data-theme="dark"] .tag-connector { background: #1a3a5c; color: #6cb8f6; }
    [data-theme="dark"] .tag-success { background: #1a3a1a; color: #6ccb5f; }
    [data-theme="dark"] .tag-warn { background: #3a3500; color: #d4c75f; }
    [data-theme="dark"] .tag-danger { background: #4a1a1d; color: #f5707a; }
    [data-theme="dark"] .tag-dim { background: #1a2040; color: #8ea0e0; }
    [data-theme="dark"] .tag-measure { background: #3a1a2a; color: #e08090; }
    [data-theme="dark"] code { background: #3b3a39; }
    [data-theme="dark"] .report-footer { border-top-color: #3b3a39; }
    [data-theme="dark"] .table-search input { background: #323130; border-color: #3b3a39; color: var(--pbi-dark); }
    [data-theme="dark"] .table-search input:focus { border-color: #2b88d8; }
    [data-theme="dark"] .comparison { background: var(--pbi-surface); }
    [data-theme="dark"] .comparison .row-header { background: #2d2d2d; }
    [data-theme="dark"] .col { border-color: #3b3a39; }
    [data-theme="dark"] pre { background: #2d2d2d; color: #d4d4d4; }
    /* ── Theme toggle button ─────────────────────────────────── */
    .theme-toggle {
        position: absolute; top: 50%; right: 24px; transform: translateY(-50%);
        background: rgba(255,255,255,0.15); border: 1px solid rgba(255,255,255,0.25);
        color: #fff; border-radius: 20px; padding: 6px 14px; cursor: pointer;
        font-size: 0.82em; font-family: inherit; font-weight: 500;
        display: inline-flex; align-items: center; gap: 6px;
        transition: background 0.2s, border-color 0.2s;
        backdrop-filter: blur(4px); -webkit-backdrop-filter: blur(4px);
    }
    .theme-toggle:hover { background: rgba(255,255,255,0.25); border-color: rgba(255,255,255,0.4); }
    .theme-toggle .theme-icon { font-size: 1.1em; line-height: 1; }
    .report-header { position: relative; }
    @media print and (prefers-color-scheme: dark) {
        :root { --pbi-bg: #fff; --pbi-surface: #fff; --pbi-dark: #323130; --pbi-gray: #605e5c; --pbi-light-gray: #a19f9d; }
        body { background: #fff; color: #323130; } .report-header { background: #0078d4 !important; }
    }
    @media print { .theme-toggle { display: none; } }
"""


# ═══════════════════════════════════════════════════════════════════════
#  JavaScript
# ═══════════════════════════════════════════════════════════════════════

def get_report_js() -> str:
    """Return the shared JavaScript for interactive features."""
    return """
/* ── Theme toggle ─────────────────────────────────────── */
(function() {
    var stored = localStorage.getItem('pbi-report-theme');
    if (stored) {
        document.documentElement.setAttribute('data-theme', stored);
    } else if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
        document.documentElement.setAttribute('data-theme', 'dark');
    }
})();
function toggleTheme() {
    var html = document.documentElement;
    var current = html.getAttribute('data-theme');
    var next = current === 'dark' ? 'light' : 'dark';
    html.setAttribute('data-theme', next);
    localStorage.setItem('pbi-report-theme', next);
    var btn = document.querySelector('.theme-toggle');
    if (btn) {
        btn.querySelector('.theme-icon').textContent = next === 'dark' ? '\\u2600' : '\\u263E';
        btn.querySelector('.theme-label').textContent = next === 'dark' ? 'Light' : 'Dark';
    }
}
window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function(e) {
    if (!localStorage.getItem('pbi-report-theme')) {
        document.documentElement.setAttribute('data-theme', e.matches ? 'dark' : 'light');
        var btn = document.querySelector('.theme-toggle');
        if (btn) {
            btn.querySelector('.theme-icon').textContent = e.matches ? '\\u2600' : '\\u263E';
            btn.querySelector('.theme-label').textContent = e.matches ? 'Light' : 'Dark';
        }
    }
});
function toggleSection(id) {
    var body = document.getElementById(id);
    var arrow = document.getElementById(id + '-arrow');
    if (!body) return;
    body.classList.toggle('collapsed');
    if (arrow) arrow.classList.toggle('collapsed');
}
function switchTab(groupId, tabName) {
    var allTabs = document.querySelectorAll('[data-tab-group="' + groupId + '"]');
    allTabs.forEach(function(t) { t.classList.remove('active'); });
    var allContents = document.querySelectorAll('[data-tab-content-group="' + groupId + '"]');
    allContents.forEach(function(c) { c.classList.remove('active'); });
    var targetTab = document.querySelector('[data-tab-group="' + groupId + '"][data-tab-name="' + tabName + '"]');
    if (targetTab) targetTab.classList.add('active');
    var targetContent = document.getElementById(groupId + '-' + tabName);
    if (targetContent) targetContent.classList.add('active');
}
function filterTable(inputId, tableId) {
    var input = document.getElementById(inputId);
    var table = document.getElementById(tableId);
    if (!input || !table) return;
    var filter = input.value.toLowerCase();
    var rows = table.querySelectorAll('tbody tr');
    rows.forEach(function(row) {
        var text = row.textContent.toLowerCase();
        row.style.display = text.indexOf(filter) > -1 ? '' : 'none';
    });
}
function sortTable(tableId, colIndex) {
    var table = document.getElementById(tableId);
    if (!table) return;
    var th = table.querySelectorAll('thead th')[colIndex];
    var tbody = table.querySelector('tbody');
    var rows = Array.from(tbody.querySelectorAll('tr'));
    var isAsc = th.classList.contains('sort-asc');
    table.querySelectorAll('thead th').forEach(function(h) { h.classList.remove('sort-asc', 'sort-desc'); });
    th.classList.add(isAsc ? 'sort-desc' : 'sort-asc');
    var direction = isAsc ? -1 : 1;
    rows.sort(function(a, b) {
        var aVal = a.cells[colIndex].getAttribute('data-sort') || a.cells[colIndex].textContent.trim();
        var bVal = b.cells[colIndex].getAttribute('data-sort') || b.cells[colIndex].textContent.trim();
        var aNum = parseFloat(aVal.replace(/[^0-9.-]/g, ''));
        var bNum = parseFloat(bVal.replace(/[^0-9.-]/g, ''));
        if (!isNaN(aNum) && !isNaN(bNum)) return (aNum - bNum) * direction;
        return aVal.localeCompare(bVal) * direction;
    });
    rows.forEach(function(row) { tbody.appendChild(row); });
}
"""


# ═══════════════════════════════════════════════════════════════════════
#  HTML structure helpers
# ═══════════════════════════════════════════════════════════════════════

def html_open(
    title: str,
    subtitle: str = "",
    timestamp: str = "",
    version: str = "",
) -> str:
    """Return the opening HTML (doctype, header, container start)."""
    if not timestamp:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    meta_parts = []
    if timestamp:
        meta_parts.append(f'<span>&#128197; {esc(timestamp)}</span>')
    if version:
        meta_parts.append(f'<span>&#9881; v{esc(version)}</span>')
    meta_html = "\n        ".join(meta_parts)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(title)}</title>
<style>{get_report_css()}</style>
</head>
<body>
<div class="report-header">
    <h1>{esc(title)}</h1>
    {"<div class='subtitle'>" + esc(subtitle) + "</div>" if subtitle else ""}
    <div class="meta">
        {meta_html}
    </div>
    <button class="theme-toggle" onclick="toggleTheme()" title="Toggle dark/light mode">
        <span class="theme-icon">&#9790;</span>
        <span class="theme-label">Dark</span>
    </button>
</div>
<div class="container">
"""


def html_close(version: str = "", timestamp: str = "") -> str:
    """Return the closing HTML (footer, scripts, closing tags)."""
    if not timestamp:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    footer_parts = ["Qlik &#8594; Power BI Migration Tool"]
    if version:
        footer_parts[0] += f" v{esc(version)}"
    footer_parts.append(f"Report generated {esc(timestamp)}")
    return f"""
</div>
<div class="report-footer">
    <p>{" &nbsp;|&nbsp; ".join(footer_parts)}</p>
    <p>Open .pbip files in Power BI Desktop (Developer Mode) to validate</p>
</div>
<script>
{get_report_js()}
// Sync toggle button label on load
(function() {{
    var theme = document.documentElement.getAttribute('data-theme') || 'light';
    var btn = document.querySelector('.theme-toggle');
    if (btn) {{
        btn.querySelector('.theme-icon').textContent = theme === 'dark' ? '\\u2600' : '\\u263E';
        btn.querySelector('.theme-label').textContent = theme === 'dark' ? 'Light' : 'Dark';
    }}
}})();
</script>
</body>
</html>"""


# ═══════════════════════════════════════════════════════════════════════
#  Components
# ═══════════════════════════════════════════════════════════════════════

def stat_card(value: Any, label: str, color: str = "", accent: str = "") -> str:
    """Return HTML for a single stat card."""
    accent_cls = f" accent-{accent}" if accent else ""
    style = f' style="color:{color}"' if color else ""
    return f"""<div class="stat-card{accent_cls}">
    <div class="stat-value"{style}>{esc(str(value))}</div>
    <div class="stat-label">{esc(label)}</div>
</div>"""


def stat_grid(cards: List[str]) -> str:
    """Wrap stat cards in a grid container."""
    return '<div class="stat-grid">\n' + "\n".join(cards) + "\n</div>"


def section_open(section_id: str, title: str, icon: str = "", collapsed: bool = False) -> str:
    """Open a collapsible section."""
    arrow_cls = " collapsed" if collapsed else ""
    body_cls = " collapsed" if collapsed else ""
    return f"""
<div class="section-header" onclick="toggleSection('{section_id}')">
    <span class="section-icon">{icon}</span>
    <h2>{title}</h2>
    <span class="toggle-arrow{arrow_cls}" id="{section_id}-arrow">&#9660;</span>
</div>
<div class="section-body{body_cls}" id="{section_id}">
"""


def section_close() -> str:
    """Close a collapsible section."""
    return "\n</div>\n"


def card(content: str = "", title: str = "") -> str:
    """Return a card wrapper with optional title."""
    h = f"<h3>{esc(title)}</h3>" if title else ""
    return f'<div class="card">{h}\n{content}\n</div>'


def badge(score: str, level: str = "") -> str:
    """Return a colored badge for GREEN/YELLOW/RED/pass/warn/fail scores."""
    mapping = {
        "GREEN": "green", "YELLOW": "yellow", "RED": "red",
        "PASS": "green", "WARN": "yellow", "FAIL": "red",
        "INFO": "blue", "EXACT": "green", "APPROXIMATE": "yellow",
        "UNSUPPORTED": "red",
    }
    if level:
        cls = level
    else:
        cls = mapping.get(score.upper() if hasattr(score, 'upper') else score, "gray")
    return f'<span class="badge badge-{cls}">{esc(str(score))}</span>'


def fidelity_bar(pct: float) -> str:
    """Return an inline fidelity progress bar."""
    color = "var(--success)" if pct >= 95 else "#c19c00" if pct >= 80 else "var(--fail)"
    return f"""<span class="fidelity-bar">
    <span class="fidelity-track"><span class="fidelity-fill" style="width:{pct:.0f}%;background:{color}"></span></span>
    <span class="fidelity-label" style="color:{color}">{pct:.1f}%</span>
</span>"""


def donut_chart(segments: List[Tuple[str, float, str]], center_text: str = "") -> str:
    """Return SVG donut chart. segments: [(label, value, color), ...]."""
    total = sum(s[1] for s in segments) or 1
    svg = '<div class="donut-container">\n<svg class="donut" viewBox="0 0 42 42">\n'
    svg += '<circle cx="21" cy="21" r="15.91549431" fill="transparent" stroke="#edebe9" stroke-width="5.5"></circle>\n'
    offset = 25
    for _, value, color in segments:
        pct = value / total * 100
        svg += f'<circle cx="21" cy="21" r="15.91549431" fill="transparent" stroke="{color}" stroke-width="5.5" '
        svg += f'stroke-dasharray="{pct:.2f} {100-pct:.2f}" stroke-dashoffset="{offset:.2f}"></circle>\n'
        offset -= pct
    if center_text:
        svg += f'<text x="21" y="22.5" text-anchor="middle" font-size="6" font-weight="bold" fill="{PBI_DARK}">{esc(center_text)}</text>\n'
    svg += '</svg>\n<div class="donut-legend">\n'
    for label, value, color in segments:
        pct = value / total * 100
        svg += f'<div><span class="legend-dot" style="background:{color}"></span>{esc(label)}: {int(value)} ({pct:.0f}%)</div>\n'
    svg += '</div>\n</div>'
    return svg


def bar_chart(items: List[Tuple[str, float, str]], max_value: float = 0) -> str:
    """Return a horizontal bar chart. items: [(label, value, color), ...]."""
    if not max_value:
        max_value = max((v for _, v, _ in items), default=1) or 1
    html = '<div class="bar-chart">\n'
    for label, value, color in items:
        pct = value / max_value * 100
        display = int(value) if value == int(value) else f"{value:.1f}"
        html += f"""<div class="bar-row">
    <div class="bar-label">{esc(label)}</div>
    <div class="bar-track"><div class="bar-fill" style="width:{pct:.1f}%;background:{color}">{display if pct > 12 else ''}</div></div>
    <div class="bar-value">{display}</div>
</div>\n"""
    html += '</div>'
    return html


def data_table(
    headers: List[str],
    rows: List[List[str]],
    table_id: str = "",
    sortable: bool = False,
    searchable: bool = False,
    detail: bool = False,
) -> str:
    """Return a data table with optional sort and search."""
    tid = table_id or f"tbl-{id(headers)}"
    html = ""
    if searchable:
        search_id = f"search-{tid}"
        html += f"""<div class="table-search">
    <label>&#128269;</label>
    <input type="text" id="{search_id}" placeholder="Filter rows..." oninput="filterTable('{search_id}', '{tid}')">
</div>\n"""
    detail_cls = ' class="detail-table"' if detail else ''
    html += f'<div class="table-container"><table id="{tid}"{detail_cls}>\n<thead><tr>\n'
    for i, h in enumerate(headers):
        if sortable:
            html += f'<th class="sortable" onclick="sortTable(\'{tid}\', {i})">{esc(h)} <span class="sort-icon">&#8693;</span></th>\n'
        else:
            html += f'<th>{esc(h)}</th>\n'
    html += '</tr></thead>\n<tbody>\n'
    for row in rows:
        html += '<tr>' + ''.join(f'<td>{cell}</td>' for cell in row) + '</tr>\n'
    html += '</tbody></table></div>'
    return html


def tab_bar(group_id: str, tabs: List[Tuple[str, str, bool]]) -> str:
    """Return a tab bar. tabs: [(tab_id, label, is_active), ...]."""
    html = '<div class="tab-bar">\n'
    for tab_id, label, active in tabs:
        cls = " active" if active else ""
        html += f'<div class="tab{cls}" data-tab-group="{group_id}" data-tab-name="{tab_id}" onclick="switchTab(\'{group_id}\', \'{tab_id}\')">{label}</div>\n'
    html += '</div>'
    return html


def tab_content(group_id: str, tab_id: str, content: str, active: bool = False) -> str:
    """Return a tab content panel."""
    cls = " active" if active else ""
    return f'<div class="tab-content{cls}" id="{group_id}-{tab_id}" data-tab-content-group="{group_id}">\n{content}\n</div>'


def heatmap_table(headers: List[str], rows: List[List[str]], table_id: str = "") -> str:
    """Return a heatmap-style table (cells pre-styled by caller)."""
    tid = table_id or f"heat-{id(headers)}"
    html = f'<div class="table-container"><table id="{tid}" class="heatmap">\n<thead><tr>\n'
    for h in headers:
        html += f'<th>{esc(h)}</th>\n'
    html += '</tr></thead>\n<tbody>\n'
    for row in rows:
        html += '<tr>' + ''.join(f'<td>{cell}</td>' for cell in row) + '</tr>\n'
    html += '</tbody></table></div>'
    return html
