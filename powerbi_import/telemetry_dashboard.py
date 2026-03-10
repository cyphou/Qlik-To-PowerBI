"""Telemetry dashboard — generates an HTML summary of migration runs.

Reads migration report JSON files from the artifacts directory and
builds a single-page dashboard with charts and tables summarizing
migration history, fidelity trends, and common issues.

Usage::

    python -m powerbi_import.telemetry_dashboard [artifacts_dir] [-o dashboard.html]
"""

import json
import os
import glob
import argparse
import html as html_mod
from datetime import datetime


_CSS = """
* { box-sizing: border-box; }
body { font-family: 'Segoe UI', Tahoma, sans-serif; margin: 0; padding: 0;
       background: #f0f2f5; color: #333; }
header { background: linear-gradient(135deg, #0d47a1, #1565c0);
         color: #fff; padding: 1.5rem 2rem; }
header h1 { margin: 0; font-size: 1.4rem; }
.container { max-width: 1200px; margin: 1rem auto; padding: 0 1rem; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
        gap: 1rem; margin-bottom: 1.5rem; }
.card { background: #fff; border-radius: 8px; padding: 1rem 1.5rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.12); }
.card h3 { margin-top: 0; font-size: 0.8rem; color: #888; text-transform: uppercase; }
.card .val { font-size: 2rem; font-weight: 700; }
.card .sub { font-size: 0.85rem; color: #666; }
table { width: 100%; border-collapse: collapse; font-size: 0.85rem; margin-bottom: 1rem; }
th, td { border: 1px solid #e0e0e0; padding: 6px 10px; text-align: left; }
th { background: #fafafa; }
.pass { color: #4caf50; font-weight: 600; }
.warn { color: #ff9800; font-weight: 600; }
.fail { color: #f44336; font-weight: 600; }
.chart-bar { height: 24px; background: #42a5f5; border-radius: 3px;
             display: inline-block; min-width: 2px; }
.footer { text-align: center; padding: 2rem; font-size: 0.8rem; color: #999; }
"""


def _load_reports(artifacts_dir):
    """Load all migration report JSONs from the artifacts directory."""
    pattern = os.path.join(artifacts_dir, '**', 'migration_report_*.json')
    files = sorted(glob.glob(pattern, recursive=True))
    reports = []
    for f in files:
        try:
            with open(f, 'r', encoding='utf-8') as fh:
                data = json.load(fh)
            data['_file'] = f
            reports.append(data)
        except (OSError, json.JSONDecodeError):
            pass
    return reports


def _esc(text):
    return html_mod.escape(str(text)) if text else ''


def generate_dashboard(artifacts_dir, output_path=None):
    """Generate an HTML telemetry dashboard.

    Args:
        artifacts_dir: Path to the artifacts directory.
        output_path: Output file (default: artifacts/telemetry_dashboard.html).

    Returns:
        str: Path to the generated HTML file.
    """
    reports = _load_reports(artifacts_dir)

    if output_path is None:
        output_path = os.path.join(artifacts_dir, 'telemetry_dashboard.html')

    # Aggregate stats
    total_runs = len(reports)
    fidelities = [r.get('fidelity_score', r.get('overall_fidelity', 0))
                  for r in reports if r.get('fidelity_score') or r.get('overall_fidelity')]
    avg_fidelity = round(sum(fidelities) / len(fidelities), 1) if fidelities else 0
    max_fidelity = max(fidelities) if fidelities else 0
    min_fidelity = min(fidelities) if fidelities else 0

    # Items aggregation
    all_items = []
    status_counts = {}
    for r in reports:
        for item in r.get('items', []):
            all_items.append(item)
            st = item.get('status', 'unknown')
            status_counts[st] = status_counts.get(st, 0) + 1

    # Workbook names
    wbs = sorted(set(r.get('workbook_name', r.get('report_name', 'Unknown')) for r in reports))

    # Issue categories
    issue_counts = {}
    for item in all_items:
        notes = item.get('notes', '')
        if 'unsupported' in notes.lower() or 'not supported' in notes.lower():
            issue_counts['Unsupported feature'] = issue_counts.get('Unsupported feature', 0) + 1
        elif 'fallback' in notes.lower():
            issue_counts['Fallback applied'] = issue_counts.get('Fallback applied', 0) + 1
        elif 'manual' in notes.lower():
            issue_counts['Manual review needed'] = issue_counts.get('Manual review needed', 0) + 1

    # Build HTML
    parts = [f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Migration Telemetry Dashboard</title>
<style>{_CSS}</style>
</head>
<body>
<header>
<h1>Migration Telemetry Dashboard</h1>
</header>
<div class="container">
"""]

    # Summary cards
    parts.append('<div class="grid">')
    parts.append(f'<div class="card"><h3>Total Migrations</h3><div class="val">{total_runs}</div>'
                 f'<div class="sub">{len(wbs)} unique workbooks</div></div>')
    parts.append(f'<div class="card"><h3>Avg Fidelity</h3><div class="val">{avg_fidelity}%</div>'
                 f'<div class="sub">min {min_fidelity}% / max {max_fidelity}%</div></div>')
    migrated = status_counts.get('migrated', 0) + status_counts.get('converted', 0)
    partial = status_counts.get('partial', 0)
    skipped = status_counts.get('skipped', 0) + status_counts.get('failed', 0)
    parts.append(f'<div class="card"><h3>Items Migrated</h3><div class="val">{migrated}</div>'
                 f'<div class="sub">{partial} partial, {skipped} skipped/failed</div></div>')
    total_items = len(all_items)
    parts.append(f'<div class="card"><h3>Total Items</h3><div class="val">{total_items}</div></div>')
    parts.append('</div>')

    # Fidelity history
    if fidelities:
        parts.append('<h2>Fidelity History</h2>')
        parts.append('<div class="card">')
        max_bar = max(fidelities) or 1
        for i, f in enumerate(fidelities[-30:]):  # Last 30 runs
            w = int(f / max_bar * 300)
            color = '#4caf50' if f >= 80 else '#ff9800' if f >= 50 else '#f44336'
            parts.append(f'<div style="margin:2px 0"><span class="chart-bar" '
                         f'style="width:{w}px;background:{color}"></span> {f}%</div>')
        parts.append('</div>')

    # Per-workbook table
    if reports:
        parts.append('<h2>Migration Runs</h2>')
        parts.append('<table><tr><th>Workbook</th><th>Fidelity</th><th>Items</th>'
                     '<th>Timestamp</th></tr>')
        for r in reports[-50:]:
            name = r.get('workbook_name', r.get('report_name', ''))
            fid = r.get('fidelity_score', r.get('overall_fidelity', ''))
            items_count = len(r.get('items', []))
            ts = r.get('timestamp', r.get('generated_at', ''))
            cls = 'pass' if fid and float(fid) >= 80 else 'warn' if fid else 'fail'
            parts.append(f'<tr><td>{_esc(name)}</td>'
                         f'<td class="{cls}">{_esc(str(fid))}%</td>'
                         f'<td>{items_count}</td>'
                         f'<td>{_esc(ts)}</td></tr>')
        parts.append('</table>')

    # Status distribution
    if status_counts:
        parts.append('<h2>Status Distribution</h2>')
        parts.append('<table><tr><th>Status</th><th>Count</th></tr>')
        for st, cnt in sorted(status_counts.items(), key=lambda x: -x[1]):
            parts.append(f'<tr><td>{_esc(st)}</td><td>{cnt}</td></tr>')
        parts.append('</table>')

    # Common issues
    if issue_counts:
        parts.append('<h2>Common Issues</h2>')
        parts.append('<table><tr><th>Issue</th><th>Occurrences</th></tr>')
        for issue, cnt in sorted(issue_counts.items(), key=lambda x: -x[1]):
            parts.append(f'<tr><td>{_esc(issue)}</td><td>{cnt}</td></tr>')
        parts.append('</table>')

    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    parts.append(f'<div class="footer">Generated: {now} | '
                 f'Qlik → Power BI Migration Tool</div>')
    parts.append('</div></body></html>')

    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(parts))
    print(f"  ✓ Telemetry dashboard: {output_path}")
    return output_path


def main():
    parser = argparse.ArgumentParser(description='Generate migration telemetry dashboard')
    parser.add_argument('artifacts_dir', nargs='?', default='artifacts/powerbi_projects',
                        help='Path to artifacts directory with migration reports')
    parser.add_argument('-o', '--output', default=None, help='Output HTML file path')
    args = parser.parse_args()
    generate_dashboard(args.artifacts_dir, args.output)


if __name__ == '__main__':
    main()
