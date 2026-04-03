#!/usr/bin/env python3
"""Post-migration field verification: Qlik worksheets vs Power BI visuals.

Compares field bindings between the original Qlik workbook and the
generated Power BI project to verify migration fidelity.

Usage:
    python scripts/verify_fields.py <twb_path> <pbip_output_dir>
    python scripts/verify_fields.py examples/real_world/vishnu_dashboard.qvf C:\\temp\\vishnu_fix6\\vishnu_dashboard
"""
import argparse
import json
import glob
import os
import re
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile


# ── Qlik field parsing helpers ─────────────────────────────────────────────

_RE_FIELD = re.compile(
    r'\[(?P<ds>[^\]]*)\]\.\[(?:(?P<agg>\w+):)?(?P<name>[^\]:]+)(?::(?P<kind>\w+))?\]'
)

_AGG_MAP = {
    'sum': 'Sum', 'avg': 'Average', 'cnt': 'Count', 'countd': 'DistinctCount',
    'ctd': 'DistinctCount', 'min': 'Min', 'max': 'Max', 'median': 'Median',
    'attr': 'Attr', 'none': None,
}

_DATE_PREFIXES = {
    'yr': 'YEAR', 'qr': 'QUARTER', 'mn': 'MONTH', 'dy': 'DAY',
    'wk': 'WEEK', 'tyr': 'YEAR', 'tqr': 'QUARTER', 'tmn': 'MONTH',
    'tdy': 'DAY', 'twk': 'WEEK',
}


# Fields that are Qlik-specific and have no direct PBI equivalent
_GENERATED_FIELDS = {
    'Latitude (generated)', 'Longitude (generated)',
    'Number of Records', 'Multiple Values',
}


def _parse_shelf_fields(text, shelf_name):
    """Parse Qlik shelf text (rows/cols) into structured fields."""
    if not text:
        return []
    fields = []
    for m in _RE_FIELD.finditer(text):
        agg_raw = m.group('agg') or ''
        name = m.group('name')
        date_part = _DATE_PREFIXES.get(agg_raw)
        agg = _AGG_MAP.get(agg_raw, agg_raw if agg_raw else None)
        is_measure = agg is not None and agg_raw not in ('none', '')
        fields.append({
            'name': name,
            'agg': agg,
            'date_part': date_part,
            'shelf': shelf_name,
            'is_measure': is_measure,
        })
    return fields


def _parse_mark_encodings(ws_elem):
    """Parse mark-level encodings (color, size, label, tooltip, detail)."""
    fields = []
    for pane in ws_elem.findall('.//pane'):
        for enc in pane.findall('.//encoding'):
            enc_type = enc.get('type', '')
            col = enc.get('column', '')
            if not col:
                continue
            m = _RE_FIELD.search(f'[_].[{col}]') or _RE_FIELD.search(col)
            if m:
                name = m.group('name')
            else:
                name = re.sub(r'[\[\]]', '', col).split('.')[-1]
                name = re.sub(r'^(sum|avg|cnt|none|attr|min|max|countd|ctd):', '', name)
                name = name.rstrip(':qk').rstrip(':ok').rstrip(':nk')
            fields.append({
                'name': name,
                'shelf': f'encoding:{enc_type}',
                'is_measure': False,
                'agg': None,
                'date_part': None,
            })
    return fields


def extract_Qlik_worksheets(twb_path):
    """Extract field information from each Qlik worksheet."""
    # Handle TWBX (ZIP containing TWB)
    if twb_path.lower().endswith('.qvf'):
        with zipfile.ZipFile(twb_path, 'r') as zf:
            twb_name = next((n for n in zf.namelist() if n.endswith('.qvf')), None)
            if not twb_name:
                return []
            with zf.open(twb_name) as fh:
                tree = ET.parse(fh)
    else:
        tree = ET.parse(twb_path)
    root = tree.getroot()

    # Build calculation ID → caption map for resolving internal calc names
    calc_caption_map = {}
    for ds in root.findall('.//datasource'):
        for col in ds.findall('.//column'):
            col_name = col.get('name', '')
            caption = col.get('caption', '')
            calc = col.find('calculation')
            if caption and col_name:
                # Strip brackets if present
                clean = col_name.strip('[]')
                calc_caption_map[clean] = caption
                # Also map with agg prefix removed
                if ':' in clean:
                    parts = clean.split(':')
                    if len(parts) >= 2:
                        calc_caption_map[parts[-1]] = caption

    worksheets = []
    for ws in root.findall('.//worksheet'):
        name = ws.get('name', '')
        rows_el = ws.find('.//rows')
        cols_el = ws.find('.//cols')
        rows_text = rows_el.text.strip() if rows_el is not None and rows_el.text else ''
        cols_text = cols_el.text.strip() if cols_el is not None and cols_el.text else ''

        row_fields = _parse_shelf_fields(rows_text, 'rows')
        col_fields = _parse_shelf_fields(cols_text, 'cols')
        enc_fields = _parse_mark_encodings(ws)

        all_fields = row_fields + col_fields + enc_fields

        # Resolve Qlik internal calc IDs to their display captions
        resolved = []
        for f in all_fields:
            name = f['name']
            # Only resolve calculation IDs (e.g. Calculation_1234567890)
            if name.startswith('Calculation_') and name in calc_caption_map:
                f['original_name'] = name
                f['name'] = calc_caption_map[name]
            # Skip Qlik-specific generated fields
            if f['name'] in _GENERATED_FIELDS:
                continue
            resolved.append(f)

        # Deduplicate by name
        seen = set()
        unique = []
        for f in resolved:
            if f['name'] not in seen:
                seen.add(f['name'])
                unique.append(f)

        worksheets.append({
            'name': name,
            'fields': unique,
            'row_fields': row_fields,
            'col_fields': col_fields,
            'enc_fields': enc_fields,
            'is_empty': not rows_text and not cols_text,
        })
    return worksheets


# ── PBI visual parsing ────────────────────────────────────────────────────────

def extract_pbi_visuals(pbip_dir):
    """Extract field information from each PBI visual.json."""
    pattern = os.path.join(pbip_dir, '**', 'visual.json')
    files = sorted(glob.glob(pattern, recursive=True))

    visuals = []
    for filepath in files:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        vid = os.path.basename(os.path.dirname(filepath))
        vis = data.get('visual', {})
        vtype = vis.get('visualType', 'unknown')

        # Extract title
        title = ''
        vc_objs = vis.get('visualContainerObjects', vis.get('vcObjects', {}))
        for t_item in vc_objs.get('title', []):
            txt = t_item.get('properties', {}).get('text', {})
            if isinstance(txt, dict):
                val = txt.get('expr', {}).get('Literal', {}).get('Value', '')
                title = val.strip("'").strip('"')

        # Extract fields from queryState
        qs = vis.get('query', {}).get('queryState', {})
        fields = []
        for role, role_data in qs.items():
            for proj in role_data.get('projections', []):
                field_info = proj.get('field', {})
                qref = proj.get('queryRef', '')

                # Parse field name and aggregation
                agg_node = field_info.get('Aggregation', {})
                if agg_node:
                    prop = agg_node.get('Expression', {}).get('Column', {}).get('Property', '')
                    func_id = agg_node.get('Function', 0)
                    agg_names = {0: 'Sum', 1: 'Average', 2: 'Count', 3: 'Min',
                                 4: 'Max', 5: 'CountNonNull', 6: 'DistinctCount'}
                    agg = agg_names.get(func_id, str(func_id))
                    table = agg_node.get('Expression', {}).get('Column', {}).get(
                        'Expression', {}).get('SourceRef', {}).get('Entity', '')
                else:
                    col_node = field_info.get('Column', {})
                    prop = col_node.get('Property', '')
                    table = col_node.get('Expression', {}).get('SourceRef', {}).get('Entity', '')
                    agg = None

                if prop:
                    fields.append({
                        'name': prop,
                        'role': role,
                        'agg': agg,
                        'table': table,
                        'queryRef': qref,
                    })

        # Position
        pos = data.get('position', {})

        visuals.append({
            'id': vid,
            'type': vtype,
            'title': title,
            'fields': fields,
            'position': pos,
            'is_empty': len(fields) == 0,
        })
    return visuals


# ── Comparison logic ──────────────────────────────────────────────────────────

def _match_ws_to_visual(ws, pbi_visuals, used_ids):
    """Find the best-matching PBI visual for a Qlik worksheet by field overlap."""
    ws_names = {f['name'] for f in ws['fields']}
    if not ws_names:
        # Empty worksheet — match to empty visual
        for v in pbi_visuals:
            if v['id'] not in used_ids and v['is_empty']:
                return v
        return None

    best, best_score = None, -1
    for v in pbi_visuals:
        if v['id'] in used_ids:
            continue
        pbi_names = {f['name'] for f in v['fields']}
        overlap = len(ws_names & pbi_names)
        union = len(ws_names | pbi_names)
        score = overlap / union if union else 0
        if score > best_score:
            best_score = score
            best = v
    return best


def compare_fields(Qlik_ws, pbi_visuals):
    """Compare Qlik worksheet fields against PBI visual fields.
    
    Returns a list of comparison results with match status.
    """
    results = []
    used_ids = set()

    for ws in Qlik_ws:
        pbi = _match_ws_to_visual(ws, pbi_visuals, used_ids)
        if pbi:
            used_ids.add(pbi['id'])

        ws_field_names = {f['name'] for f in ws['fields']}
        pbi_field_names = {f['name'] for f in pbi['fields']} if pbi else set()

        matched = ws_field_names & pbi_field_names
        missing_in_pbi = ws_field_names - pbi_field_names
        extra_in_pbi = pbi_field_names - ws_field_names

        # Check aggregation consistency
        agg_mismatches = []
        if pbi:
            ws_agg_map = {f['name']: f.get('agg') for f in ws['fields']}
            pbi_agg_map = {f['name']: f.get('agg') for f in pbi['fields']}
            for name in matched:
                ws_agg = ws_agg_map.get(name)
                pbi_agg = pbi_agg_map.get(name)
                if ws_agg and pbi_agg and ws_agg != pbi_agg:
                    agg_mismatches.append({
                        'field': name,
                        'Qlik_agg': ws_agg,
                        'pbi_agg': pbi_agg,
                    })

        if ws['is_empty']:
            status = 'EMPTY'  # Intentionally empty worksheet
        elif not pbi:
            status = 'NO_VISUAL'
        elif missing_in_pbi and not extra_in_pbi:
            status = 'MISSING'
        elif missing_in_pbi and extra_in_pbi:
            status = 'PARTIAL'
        elif extra_in_pbi and not missing_in_pbi:
            status = 'EXTRA'
        else:
            status = 'OK'

        results.append({
            'worksheet': ws['name'],
            'visual_id': pbi['id'][:12] if pbi else None,
            'visual_type': pbi['type'] if pbi else None,
            'status': status,
            'Qlik_fields': sorted(ws_field_names),
            'pbi_fields': sorted(pbi_field_names),
            'matched': sorted(matched),
            'missing_in_pbi': sorted(missing_in_pbi),
            'extra_in_pbi': sorted(extra_in_pbi),
            'agg_mismatches': agg_mismatches,
        })

    return results


# ── Report output ─────────────────────────────────────────────────────────────

def print_report(results, Qlik_ws, pbi_visuals, workbook_name=''):
    """Print side-by-side comparison report."""
    header = f'  POST-MIGRATION FIELD VERIFICATION — {workbook_name}' if workbook_name else '  POST-MIGRATION FIELD VERIFICATION'
    print('=' * 80)
    print(header)
    print('=' * 80)
    print()

    total = len(results)
    ok_count = sum(1 for r in results if r['status'] in ('OK', 'EMPTY', 'EXTRA'))
    issue_count = total - ok_count

    for r in results:
        status_icon = {
            'OK': '\u2705', 'EMPTY': '\u2b1c', 'MISSING': '\u274c',
            'PARTIAL': '\u26a0\ufe0f', 'EXTRA': '\u2139\ufe0f', 'NO_VISUAL': '\u274c',
        }.get(r['status'], '?')

        print(f'  {status_icon} {r["worksheet"]:<30} [{r["status"]}]')
        print(f'     Visual: {r["visual_type"] or "n/a":<20} ID: {r["visual_id"] or "n/a"}')

        # Qlik fields
        print(f'     Qlik ({len(r["Qlik_fields"])}):')
        for idx_ws, ws in enumerate(Qlik_ws):
            if ws['name'] == r['worksheet']:
                for f in ws['fields']:
                    agg_str = f' ({f["agg"]})' if f.get('agg') else ''
                    dp_str = f' [{f["date_part"]}]' if f.get('date_part') else ''
                    shelf_str = f'  @{f["shelf"]}'
                    in_pbi = '\u2705' if f['name'] in r['matched'] else '\u274c'
                    print(f'       {in_pbi} {f["name"]}{agg_str}{dp_str}{shelf_str}')
                break

        # PBI fields
        pbi_vis = None
        for v in pbi_visuals:
            if v['id'][:12] == r.get('visual_id'):
                pbi_vis = v
                break
        if pbi_vis:
            print(f'     PBI ({len(r["pbi_fields"])}):')
            for f in pbi_vis['fields']:
                agg_str = f' ({f["agg"]})' if f.get('agg') else ''
                role_str = f'  @{f["role"]}'
                in_tab = '\u2705' if f['name'] in r['matched'] else '\u2795'
                print(f'       {in_tab} {f["table"]}.{f["name"]}{agg_str}{role_str}')

        # Aggregation mismatches
        for am in r['agg_mismatches']:
            print(f'     \u26a0\ufe0f Agg mismatch: {am["field"]}: '
                  f'Qlik={am["Qlik_agg"]} vs PBI={am["pbi_agg"]}')

        if r['missing_in_pbi']:
            print(f'     \u274c Missing in PBI: {", ".join(r["missing_in_pbi"])}')
        if r['extra_in_pbi']:
            print(f'     \u2795 Extra in PBI:   {", ".join(r["extra_in_pbi"])}')

        print()

    # Summary
    print('=' * 80)
    print(f'  SUMMARY: {ok_count}/{total} worksheets OK'
          f'  |  {issue_count} with issues')
    print('=' * 80)

    return issue_count


def verify_single(twb_path, pbip_dir, workbook_name='', summary_only=False):
    """Verify a single TWB against its PBI output. Returns (issue_count, ws_count)."""
    Qlik_ws = extract_Qlik_worksheets(twb_path)
    pbi_visuals = extract_pbi_visuals(pbip_dir)
    results = compare_fields(Qlik_ws, pbi_visuals)
    if summary_only:
        total = len(results)
        ok = sum(1 for r in results if r['status'] in ('OK', 'EMPTY', 'EXTRA'))
        issues = total - ok
        name_str = f' {workbook_name}' if workbook_name else ''
        print(f'  {name_str:<35} {ok}/{total} OK  |  {issues} issues')
        return issues, total
    issues = print_report(results, Qlik_ws, pbi_visuals, workbook_name=workbook_name)
    return issues, len(results)


def main():
    parser = argparse.ArgumentParser(
        description='Post-migration field verification: Qlik vs Power BI')
    parser.add_argument('twb_path', nargs='?', help='Path to Qlik .qvf/.qvf file')
    parser.add_argument('pbip_dir', nargs='?', help='Path to generated PBI project directory')
    parser.add_argument('--batch', nargs=2, metavar=('Qlik_DIR', 'OUTPUT_DIR'),
                        help='Batch verify all TWB/TWBX in Qlik_DIR against OUTPUT_DIR')
    parser.add_argument('--summary-only', action='store_true',
                        help='Print only per-workbook summary (no field details)')
    args = parser.parse_args()

    if args.batch:
        tab_dir, out_dir = args.batch
        twb_files = sorted(
            glob.glob(os.path.join(tab_dir, '*.qvf'))
            + glob.glob(os.path.join(tab_dir, '*.qvf'))
        )
        total_ws, total_issues, total_ok = 0, 0, 0
        skipped = []
        for twb_path in twb_files:
            name = os.path.splitext(os.path.basename(twb_path))[0]
            pbip_dir = os.path.join(out_dir, name)
            if not os.path.isdir(pbip_dir):
                skipped.append(name)
                continue
            issues, ws_count = verify_single(twb_path, pbip_dir, workbook_name=name,
                                             summary_only=args.summary_only)
            total_ws += ws_count
            total_issues += issues
            total_ok += ws_count - issues
            print()

        print('=' * 80)
        print(f'  BATCH SUMMARY: {total_ok}/{total_ws} worksheets OK across '
              f'{len(twb_files) - len(skipped)} workbooks')
        if skipped:
            print(f'  Skipped (no PBI output): {", ".join(skipped)}')
        print('=' * 80)
        return 1 if total_issues > 0 else 0

    if not args.qvf_path or not args.pbip_dir:
        parser.error('Provide TWB_PATH and PBIP_DIR, or use --batch')

    if not os.path.exists(args.qvf_path):
        print(f'Error: TWB file not found: {args.qvf_path}')
        return 1
    if not os.path.isdir(args.pbip_dir):
        print(f'Error: PBI directory not found: {args.pbip_dir}')
        return 1

    print(f'Qlik: {args.qvf_path}')
    print(f'PBI:     {args.pbip_dir}')
    print()

    issues, _ = verify_single(args.qvf_path, args.pbip_dir,
                              summary_only=args.summary_only)
    return 1 if issues > 0 else 0


if __name__ == '__main__':
    sys.exit(main())
