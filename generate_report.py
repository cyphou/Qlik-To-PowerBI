"""
Generate consolidated HTML Migration & Assessment Dashboard for Qlik → Power BI.

Reads assessment JSON, migration report JSON, and metadata JSON artifacts
to produce a self-contained, interactive HTML dashboard with:

- Executive summary (stat cards, donut chart, bar charts)
- Generated artifacts overview (tables, columns, measures, visuals)
- Assessment results table (per-app readiness scores)
- Migration results table (per-app fidelity bars)
- Converted items detail (tabbed per-app, searchable, sortable)
- Per-app detail cards (visual mappings, table mappings, warnings)

Usage (standalone)::

    python generate_report.py

Usage (programmatic)::

    from generate_report import generate_dashboard
    html_path = generate_dashboard("MyApp", "output/migrated")

Called automatically at the end of each migration from migrate.py.
"""

import json
import os
import glob
import datetime

from powerbi_import.html_template import (
    html_open, html_close, stat_card, stat_grid, section_open, section_close,
    badge, fidelity_bar, donut_chart, bar_chart, data_table, tab_bar,
    tab_content, card, esc,
    PBI_BLUE, PBI_DARK, PBI_GRAY,
    SUCCESS, WARN, FAIL, PURPLE, TEAL, ORANGE,
)

BASE = "artifacts/powerbi_projects"
ASSESSMENTS_DIR = os.path.join(BASE, "assessments")
REPORTS_DIR = os.path.join(BASE, "reports")
MIGRATED_DIR = os.path.join(BASE, "migrated")
OUTPUT = os.path.join(BASE, "MIGRATION_ASSESSMENT_REPORT.html")


def load_assessments():
    """Load all assessment JSON files."""
    assessments = {}
    for f in sorted(glob.glob(os.path.join(ASSESSMENTS_DIR, "assessment_*.json"))):
        if os.path.isfile(f):
            try:
                with open(f, encoding="utf-8") as fh:
                    data = json.load(fh)
                name = data.get("app_name", os.path.basename(f).replace("assessment_", "").replace(".json", ""))
                assessments[name] = data
            except (json.JSONDecodeError, OSError):
                pass
    return assessments


def load_migration_reports():
    """Load latest migration report per app."""
    reports = {}
    for f in sorted(glob.glob(os.path.join(REPORTS_DIR, "migration_report_*.json"))):
        if os.path.isfile(f):
            try:
                with open(f, encoding="utf-8") as fh:
                    data = json.load(fh)
                name = data.get("report_name", "")
                if name not in reports or data.get("created_at", "") > reports[name].get("created_at", ""):
                    reports[name] = data
            except (json.JSONDecodeError, OSError):
                pass
    return reports


def load_metadata():
    """Load migration_metadata.json from each project directory."""
    metadata = {}
    for d in sorted(glob.glob(os.path.join(MIGRATED_DIR, "*"))):
        if os.path.isdir(d):
            meta_file = os.path.join(d, "migration_metadata.json")
            if os.path.isfile(meta_file):
                try:
                    with open(meta_file, encoding="utf-8") as fh:
                        metadata[os.path.basename(d)] = json.load(fh)
                except (json.JSONDecodeError, OSError):
                    pass
    return metadata


def generate_html(assessments, reports, metadata):
    """Generate consolidated HTML report."""
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    try:
        from powerbi_import import __version__ as tool_version
    except Exception:
        tool_version = "8.0.0"

    # ── Aggregate stats ──────────────────────────────────────────
    total_apps = len(set(list(assessments.keys()) + list(reports.keys())))
    green = sum(1 for a in assessments.values() if a.get("overall_score") == "GREEN")
    yellow = sum(1 for a in assessments.values() if a.get("overall_score") == "YELLOW")
    red = sum(1 for a in assessments.values() if a.get("overall_score") == "RED")

    fidelity_scores = [r.get("summary", {}).get("fidelity_score", 0) for r in reports.values()]
    avg_fidelity = sum(fidelity_scores) / len(fidelity_scores) if fidelity_scores else 0

    total_items = sum(r.get("summary", {}).get("total_items", 0) for r in reports.values())
    total_exact = sum(r.get("summary", {}).get("exact", 0) for r in reports.values())
    total_approx = sum(r.get("summary", {}).get("approximate", 0) for r in reports.values())
    total_unsupported = sum(r.get("summary", {}).get("unsupported", 0) for r in reports.values())
    total_placeholder = sum(r.get("summary", {}).get("placeholder", 0) for r in reports.values())
    total_skipped = sum(r.get("summary", {}).get("skipped", 0) for r in reports.values())

    total_tables = sum(m.get("tmdl_stats", {}).get("tables", 0) for m in metadata.values())
    total_measures = sum(m.get("tmdl_stats", {}).get("measures", 0) for m in metadata.values())
    total_columns = sum(m.get("tmdl_stats", {}).get("columns", 0) for m in metadata.values())
    total_relationships = sum(m.get("tmdl_stats", {}).get("relationships", 0) for m in metadata.values())
    total_pages = sum(m.get("generated_output", {}).get("pages", 0) for m in metadata.values())
    total_visuals = sum(m.get("generated_output", {}).get("visuals", 0) for m in metadata.values())

    # By-category breakdown
    cat_totals = {}
    for r in reports.values():
        by_cat = r.get("summary", {}).get("by_category", {})
        for cat_name, vals in by_cat.items():
            if cat_name not in cat_totals:
                cat_totals[cat_name] = {"total": 0, "exact": 0, "approx": 0}
            cat_totals[cat_name]["total"] += vals.get("total", 0)
            cat_totals[cat_name]["exact"] += vals.get("exact", 0)
            cat_totals[cat_name]["approx"] += vals.get("approximate", 0)

    # Connector distribution
    connector_counts = {}
    for r in reports.values():
        for item in r.get("items", []):
            if item.get("category") == "datasource":
                note = item.get("note", "")
                conn_type = note.split(",")[0].strip() if "," in note else "Unknown"
                connector_counts[conn_type] = connector_counts.get(conn_type, 0) + 1

    # Per-app complexity
    all_names = sorted(set(list(assessments.keys()) + list(reports.keys())))
    app_complexity = {}
    for name in all_names:
        m = metadata.get(name, {})
        tmdl = m.get("tmdl_stats", {})
        gen = m.get("generated_output", {})
        obj = m.get("objects_converted", {})
        app_complexity[name] = {
            "tables": tmdl.get("tables", 0),
            "measures": tmdl.get("measures", 0),
            "columns": tmdl.get("columns", 0),
            "relationships": tmdl.get("relationships", 0),
            "pages": gen.get("pages", 0),
            "visuals": gen.get("visuals", 0),
            "calculations": obj.get("calculations", 0),
            "filters": obj.get("filters", 0),
            "sheets": obj.get("worksheets", obj.get("sheets", 0)),
        }

    cat_colors = {
        "datasource": PBI_BLUE, "calculation": PURPLE, "visual": TEAL,
        "parameter": "#c19c00", "filter": FAIL, "relationship": SUCCESS,
        "set": PBI_GRAY, "group": ORANGE, "hierarchy": "#4f6bed",
        "bookmark": "#e97627", "rls_role": "#5c2d91",
    }
    conn_colors = {
        "Excel": "#217346", "SQL Server": "#cc2927", "PostgreSQL": "#336791",
        "Oracle": "#f80000", "MySQL": "#4479a1", "CSV": "#ff6d00",
        "Snowflake": "#29b5e8", "BigQuery": "#4285f4", "QVD": "#4dc9f6",
        "ODBC": "#888", "Unknown": PBI_GRAY,
    }

    # ═══════════════════════════════════════════════════════════════
    #  Build HTML
    # ═══════════════════════════════════════════════════════════════
    html = html_open(
        title="Qlik \u2192 Power BI \u2014 Migration Dashboard",
        subtitle=f"{total_apps} app{'s' if total_apps != 1 else ''} migrated",
        timestamp=now,
        version=tool_version,
    )

    # ── Executive Summary ───────────────────────────────────────
    html += section_open("exec", "Executive Summary", "&#128200;")
    html += stat_grid([
        stat_card(total_apps, "Qlik Apps", accent="blue"),
        stat_card(f"{avg_fidelity:.1f}%", "Avg. Fidelity", accent="success"),
        stat_card(total_items, "Items Converted"),
        stat_card(total_exact, "Exact", accent="success"),
        stat_card(total_approx, "Approximate", accent="warn"),
        stat_card(total_unsupported, "Unsupported", accent="fail"),
    ])

    html += '<div class="chart-row">'

    # Donut: Conversion Status
    html += '<div class="chart-card"><h4>&#127919; Conversion Status</h4>'
    donut_segments = [
        ("Exact", total_exact, SUCCESS),
        ("Approximate", total_approx, "#c19c00"),
        ("Unsupported", total_unsupported, FAIL),
    ]
    # Surface skipped/placeholder items so legend percentages match the true
    # total (otherwise Exact reads 100% even when fidelity is below 100%).
    if total_placeholder:
        donut_segments.append(("Placeholder", total_placeholder, ORANGE))
    if total_skipped:
        donut_segments.append(("Skipped", total_skipped, PBI_GRAY))
    html += donut_chart(donut_segments, center_text=f"{avg_fidelity:.0f}%")
    html += '</div>'

    # Bar: By Category
    cat_items = [(cat.title(), vals["total"], cat_colors.get(cat, PBI_BLUE))
                 for cat, vals in sorted(cat_totals.items(), key=lambda x: -x[1]["total"])]
    if cat_items:
        html += '<div class="chart-card"><h4>&#128202; Items by Category</h4>'
        html += bar_chart(cat_items)
        html += '</div>'

    # Bar: Connectors
    conn_items = [(conn, count, conn_colors.get(conn, PBI_BLUE))
                  for conn, count in sorted(connector_counts.items(), key=lambda x: -x[1])]
    if conn_items:
        html += '<div class="chart-card"><h4>&#128268; Data Connectors</h4>'
        html += bar_chart(conn_items)
        html += '</div>'

    html += '</div>'
    html += section_close()

    # ── Generated Artifacts ─────────────────────────────────────
    html += section_open("artifacts", "Generated Artifacts", "&#128736;")
    html += stat_grid([
        stat_card(total_tables, "TMDL Tables", accent="blue"),
        stat_card(total_columns, "Columns", accent="blue"),
        stat_card(total_measures, "DAX Measures", accent="purple"),
        stat_card(total_relationships, "Relationships", accent="teal"),
        stat_card(total_pages, "Report Pages"),
        stat_card(total_visuals, "Visuals"),
    ])

    # App Complexity Heatmap
    if app_complexity:
        dims = ("tables", "columns", "measures", "relationships", "sheets",
                "calculations", "filters", "pages", "visuals")
        maxima = {}
        for dim in dims:
            maxima[dim] = max((v.get(dim, 0) for v in app_complexity.values()), default=1) or 1

        heat_headers = ["Qlik App"] + [d.title() for d in dims]
        heat_rows = []
        for app_name, vals in app_complexity.items():
            row = [f'<strong>{esc(app_name)}</strong>']
            for dim in dims:
                v = vals.get(dim, 0)
                intensity = v / maxima[dim] if maxima[dim] else 0
                bg = f"rgba(0,120,212,{0.08 + intensity * 0.65:.2f})"
                fg = "#fff" if intensity > 0.5 else PBI_DARK
                row.append(f'<span style="display:block;padding:4px;border-radius:3px;background:{bg};color:{fg};text-align:center;font-weight:600">{v}</span>')
            heat_rows.append(row)
        html += '<div class="card"><h4>&#127919; App Complexity Heatmap</h4>'
        html += data_table(heat_headers, heat_rows, "heatmap-tbl", sortable=True)
        html += '</div>'

    html += section_close()

    # ── Assessment Results ─────────────────────────────────────────
    if assessments:
        html += section_open("assess", "Assessment Results", "&#9989;")
        assess_rows = []
        for name in all_names:
            a = assessments.get(name, {})
            if not a:
                continue
            score = a.get("overall_score", "N/A")
            totals = a.get("totals", {})

            connectors = []
            complexity = ""
            for cat_data in a.get("categories", []):
                for check in cat_data.get("checks", []):
                    if "Connector:" in check.get("name", ""):
                        connectors.append(check["name"].replace("Connector: ", ""))
                    if "Complexity score" in check.get("detail", ""):
                        complexity = check["detail"].replace("Complexity score: ", "")

            conn_html = " ".join(f'<span class="tag tag-connector">{esc(c)}</span>' for c in connectors) if connectors else "\u2014"
            warn_val = totals.get('warn', 0)
            warn_html = f'<span class="tag tag-warn">{warn_val}</span>' if warn_val > 0 else str(warn_val or '\u2014')
            assess_rows.append([
                f'<strong>{esc(name)}</strong>',
                badge(score),
                str(totals.get('checks', '\u2014')),
                str(totals.get('pass', '\u2014')),
                warn_html,
                str(totals.get('fail', '\u2014')),
                complexity or "\u2014",
                conn_html,
            ])
        html += '<div class="card">'
        html += data_table(
            ["Qlik App", "Readiness", "Checks", "Passed", "Warnings", "Failures", "Complexity", "Connectors"],
            assess_rows, "assess-tbl", sortable=True, searchable=True,
        )
        html += '</div>'
        html += section_close()

    # ── Migration Results Table ────────────────────────────────────
    html += section_open("migration", "Migration Results", "&#128640;")
    mig_rows = []
    for name in all_names:
        r = reports.get(name, {})
        m = metadata.get(name, {})
        s = r.get("summary", {})
        fid = s.get("fidelity_score", 0)
        tmdl = m.get("tmdl_stats", {})
        gen = m.get("generated_output", {})

        mig_rows.append([
            f'<strong>{esc(name)}</strong>',
            fidelity_bar(fid),
            str(s.get('total_items', '\u2014')),
            f'<span class="text-success fw-bold">{s.get("exact", "\u2014")}</span>',
            str(s.get('approximate', 0) or '\u2014'),
            str(s.get('unsupported', 0) or '\u2014'),
            str(tmdl.get('tables', '\u2014')),
            str(tmdl.get('measures', '\u2014')),
            str(gen.get('pages', '\u2014')),
            str(gen.get('visuals', '\u2014')),
        ])
    html += '<div class="card">'
    html += data_table(
        ["Qlik App", "Fidelity", "Total", "Exact", "Approx.", "Unsupported",
         "Tables", "Measures", "Pages", "Visuals"],
        mig_rows, "mig-tbl", sortable=True, searchable=True,
    )
    html += '</div>'
    html += section_close()

    # ── Converted Items (tabbed by app) ───────────────────────────
    all_items_by_app = []
    for name in all_names:
        r = reports.get(name, {})
        for item in r.get("items", []):
            all_items_by_app.append((name, item))

    if all_items_by_app:
        html += section_open("converted", "Converted Items by App", "&#128221;")

        def _conv_rows(item_tuples, show_app=True):
            rows = []
            for app_name, item in item_tuples:
                status = item.get("status", "")
                src = esc(item.get("source_formula") or item.get("note") or "")
                dax = esc(item.get("dax") or "")
                row = []
                if show_app:
                    row.append(f'<strong class="nowrap">{esc(app_name)}</strong>')
                row += [
                    f'<span class="tag tag-connector">{esc(item.get("category", ""))}</span>',
                    f'<strong>{esc(item.get("name", ""))}</strong>',
                    badge(status),
                    f'<span class="mono fs-sm" style="max-width:350px;word-break:break-all;display:inline-block">{src}</span>',
                    f'<span class="mono fs-sm" style="max-width:350px;word-break:break-all;display:inline-block">{dax}</span>',
                ]
                rows.append(row)
            return rows

        app_tabs = {}
        for name in all_names:
            r = reports.get(name, {})
            items = r.get("items", [])
            if items:
                app_tabs[name] = items

        conv_group = "conv-app"
        tabs = [("all", f"All ({len(all_items_by_app)})", True)]
        for app_name, items in app_tabs.items():
            safe_name = app_name.replace(" ", "_").replace("'", "")
            tabs.append((safe_name, f"{app_name} ({len(items)})", False))
        html += tab_bar(conv_group, tabs)

        all_headers = ["App", "Category", "Name", "Status", "Qlik Expression", "DAX / Target"]
        html += tab_content(conv_group, "all",
            data_table(all_headers, _conv_rows(all_items_by_app, True),
                       "conv-all-tbl", searchable=True, detail=True),
            active=True)

        per_headers = ["Category", "Name", "Status", "Qlik Expression", "DAX / Target"]
        for app_name, items in app_tabs.items():
            safe_name = app_name.replace(" ", "_").replace("'", "")
            html += tab_content(conv_group, safe_name,
                data_table(per_headers,
                           _conv_rows([(app_name, i) for i in items], False),
                           f"conv-{safe_name}-tbl", searchable=True, detail=True))

        html += section_close()

    # ── Per-App Detail Sections ──────────────────────────────────
    html += section_open("details", "Per-App Details", "&#128221;")

    for name in all_names:
        r = reports.get(name, {})
        a = assessments.get(name, {})
        m = metadata.get(name, {})

        items = r.get("items", [])
        if not items and not a:
            continue

        score = a.get("overall_score", "N/A")
        s = r.get("summary", {})
        fid = s.get("fidelity_score", 0)
        by_cat = s.get("by_category", {})
        safe_name = name.replace(" ", "_").replace("'", "")

        badge_html = badge(score) if score != "N/A" else ""
        fid_html = fidelity_bar(fid) if fid else ""
        html += f"""
<div class="card">
<div class="section-header" onclick="toggleSection('app-{safe_name}')" style="margin-top:0;border-bottom:none">
    <h2 style="font-size:1em">{esc(name)} &nbsp; {badge_html} &nbsp; {fid_html}</h2>
    <span class="toggle-arrow" id="app-{safe_name}-arrow">&#9660;</span>
</div>
<div class="section-body" id="app-{safe_name}">"""

        # Objects converted summary
        obj = m.get("objects_converted", {})
        if obj:
            non_zero = {k: v for k, v in obj.items() if v > 0}
            if non_zero:
                tags = " &nbsp;|&nbsp; ".join(f"<strong>{esc(k)}</strong>:&nbsp;{v}" for k, v in non_zero.items())
                html += f'<p class="text-gray fs-sm">&#128230; {tags}</p>'

        # By-category mini bar chart
        if by_cat:
            cat_bar_items = [(cat_name.title(), vals.get("total", 0), cat_colors.get(cat_name, PBI_BLUE))
                             for cat_name, vals in sorted(by_cat.items(), key=lambda x: -x[1].get("total", 0))]
            html += bar_chart(cat_bar_items)

        # Visual type mappings
        visual_details = m.get("visual_details", [])
        vtm = m.get("visual_type_mappings", {})
        if visual_details:
            vis_rows = []
            for vd in visual_details:
                dims = vd.get('dimensions', [])
                meas = vd.get('measures', [])
                dims_html = ', '.join(f'<span class="tag tag-dim">{esc(d)}</span>' for d in dims) if dims else '<span class="text-muted">\u2014</span>'
                meas_html = ', '.join(f'<span class="tag tag-measure">{esc(me)}</span>' for me in meas) if meas else '<span class="text-muted">\u2014</span>'
                vis_rows.append([
                    f'<strong>{esc(vd.get("sheet", vd.get("worksheet", "")))}</strong>',
                    f'<span class="tag tag-connector">{esc(vd.get("qlik_type", "?"))}</span>',
                    '&#8594;',
                    f'<span class="tag tag-success">{esc(vd.get("pbi_visual", "?"))}</span>',
                    dims_html,
                    meas_html,
                    str(vd.get('field_count', 0)),
                ])
            html += '<h4>&#127912; Qlik Visual &#8594; Power BI Visual</h4>'
            html += data_table(
                ["Sheet", "Qlik Type", "", "Power BI Visual", "Dimensions", "Measures", "Fields"],
                vis_rows, detail=True)
        elif vtm:
            vtm_rows = []
            for vis_name, pbi_vis in vtm.items():
                vtm_rows.append([
                    esc(vis_name),
                    '&#8594;',
                    f'<span class="tag tag-success">{esc(pbi_vis)}</span>',
                ])
            html += '<h4>&#127912; Visual Mappings</h4>'
            html += data_table(["Qlik Visual", "", "Power BI Visual"], vtm_rows, detail=True)

        # Table mapping (from migration report)
        table_mapping = r.get("table_mapping", [])
        if table_mapping:
            tm_rows = []
            for tm_item in table_mapping:
                tm_rows.append([
                    esc(tm_item.get('source_datasource', '')),
                    f'<strong>{esc(tm_item.get("source_table", ""))}</strong>',
                    f'<strong>{esc(tm_item.get("target_table", ""))}</strong>',
                    f'<span class="tag tag-connector">{esc(tm_item.get("connection_type", "?"))}</span>',
                    str(tm_item.get('columns', 0)),
                ])
            html += '<h4>&#128203; Table Mapping</h4>'
            html += data_table(
                ["Source Datasource", "Source Table", "Target Table (PBI)", "Connection", "Columns"],
                tm_rows, detail=True)

        # Assessment warnings
        warnings = []
        for cat_data in a.get("categories", []):
            for check in cat_data.get("checks", []):
                if check.get("severity") in ("warn", "fail"):
                    warnings.append(check)
        if warnings:
            html += '<h4 class="text-warn">&#9888; Assessment Warnings</h4><ul class="fs-sm">'
            for w in warnings:
                cls = "text-warn" if w["severity"] == "warn" else "text-fail"
                html += f'<li class="{cls}">[{w["severity"].upper()}] {esc(w["name"])}: {esc(w["detail"])}'
                if w.get("recommendation"):
                    html += f' &rarr; <em>{esc(w["recommendation"])}</em>'
                html += '</li>'
            html += '</ul>'

        # Converted Items (tabbed by category)
        if items:
            calc_items = [i for i in items if i.get("category") == "calculation"]
            ds_items = [i for i in items if i.get("category") == "datasource"]
            vis_items = [i for i in items if i.get("category") == "visual"]
            other_items = [i for i in items if i.get("category") not in ("calculation", "datasource", "visual")]

            app_tab_group = f"app-tab-{safe_name}"
            app_tabs_list = [
                ("all", f"All ({len(items)})", True),
                ("calc", f"Calculations ({len(calc_items)})", False),
                ("ds", f"Datasources ({len(ds_items)})", False),
                ("vis", f"Visuals ({len(vis_items)})", False),
            ]
            if other_items:
                app_tabs_list.append(("other", f"Other ({len(other_items)})", False))

            html += '<h4>&#128221; Converted Items</h4>'
            html += tab_bar(app_tab_group, app_tabs_list)

            def _render_items(item_list, tid, active=False):
                if not item_list:
                    return tab_content(app_tab_group, tid,
                                       '<p class="text-muted" style="font-style:italic">No items in this category.</p>',
                                       active)
                rows = []
                for item in item_list:
                    status = item.get("status", "")
                    src = esc(item.get("source_formula") or item.get("note") or "")
                    dax = esc(item.get("dax") or "")
                    rows.append([
                        f'<span class="tag tag-connector">{esc(item.get("category", ""))}</span>',
                        f'<strong>{esc(item.get("name", ""))}</strong>',
                        badge(status),
                        f'<span class="mono fs-sm" style="max-width:350px;word-break:break-all;display:inline-block">{src}</span>',
                        f'<span class="mono fs-sm" style="max-width:350px;word-break:break-all;display:inline-block">{dax}</span>',
                    ])
                return tab_content(app_tab_group, tid,
                    data_table(["Category", "Name", "Status", "Qlik Expression", "DAX / Target"],
                               rows, detail=True), active)

            html += _render_items(items, "all", active=True)
            html += _render_items(calc_items, "calc")
            html += _render_items(ds_items, "ds")
            html += _render_items(vis_items, "vis")
            if other_items:
                html += _render_items(other_items, "other")

        html += "</div></div>"

    html += section_close()

    html += html_close(version=tool_version, timestamp=now)
    return html


def generate_dashboard(report_name, output_dir, migration_report_path=None, metadata_path=None):
    """Generate an HTML migration dashboard for a single migration run.

    Called automatically at the end of each migration.

    Args:
        report_name: Name of the migrated Qlik app.
        output_dir: Directory containing the generated .pbip project.
        migration_report_path: Explicit path to the migration report JSON.
        metadata_path: Explicit path to migration_metadata.json.

    Returns:
        str or None: Path to the generated HTML file, or None on failure.
    """
    reports = {}
    if migration_report_path and os.path.isfile(migration_report_path):
        try:
            with open(migration_report_path, encoding="utf-8") as fh:
                data = json.load(fh)
            reports[data.get("report_name", report_name)] = data
        except (json.JSONDecodeError, OSError):
            pass
    else:
        pattern = os.path.join(output_dir, f"migration_report_{report_name}_*.json")
        candidates = sorted(glob.glob(pattern))
        if candidates:
            try:
                with open(candidates[-1], encoding="utf-8") as fh:
                    data = json.load(fh)
                reports[data.get("report_name", report_name)] = data
            except (json.JSONDecodeError, OSError):
                pass

    metadata = {}
    if metadata_path and os.path.isfile(metadata_path):
        try:
            with open(metadata_path, encoding="utf-8") as fh:
                metadata[report_name] = json.load(fh)
        except (json.JSONDecodeError, OSError):
            pass
    else:
        candidate = os.path.join(output_dir, report_name, "migration_metadata.json")
        if os.path.isfile(candidate):
            try:
                with open(candidate, encoding="utf-8") as fh:
                    metadata[report_name] = json.load(fh)
            except (json.JSONDecodeError, OSError):
                pass

    if not reports and not metadata:
        return None

    html = generate_html({}, reports, metadata)
    html_path = os.path.join(output_dir, f"MIGRATION_DASHBOARD_{report_name}.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    return html_path


def generate_batch_dashboard(output_dir, app_results):
    """Generate a consolidated HTML dashboard for a batch migration.

    Args:
        output_dir: Root output directory.
        app_results: dict mapping app names to dicts with keys
            ``migration_report_path`` and ``metadata_path``.

    Returns:
        str or None: Path to the generated HTML file.
    """
    reports = {}
    metadata = {}
    for name, paths in app_results.items():
        rp = paths.get("migration_report_path")
        if rp and os.path.isfile(rp):
            try:
                with open(rp, encoding="utf-8") as fh:
                    reports[name] = json.load(fh)
            except (json.JSONDecodeError, OSError):
                pass
        mp = paths.get("metadata_path")
        if mp and os.path.isfile(mp):
            try:
                with open(mp, encoding="utf-8") as fh:
                    metadata[name] = json.load(fh)
            except (json.JSONDecodeError, OSError):
                pass

    if not reports and not metadata:
        return None

    html = generate_html({}, reports, metadata)
    html_path = os.path.join(output_dir, "MIGRATION_DASHBOARD.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    return html_path


def main():
    assessments = load_assessments()
    reports = load_migration_reports()
    metadata = load_metadata()
    print(f"Loaded: {len(assessments)} assessments, {len(reports)} migration reports, {len(metadata)} metadata files")
    html = generate_html(assessments, reports, metadata)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Report generated: {OUTPUT}")
    print(f"  Size: {len(html):,} bytes")


if __name__ == "__main__":
    main()
