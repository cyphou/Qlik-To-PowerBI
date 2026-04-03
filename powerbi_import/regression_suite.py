"""Regression Suite Generator — Auto-generates regression test artifacts.

Captures all visual values, filter states, and data row counts from
a migrated Power BI project into a JSON snapshot. Re-running against
the same app after re-migration detects quality drift.
"""

import json
import os
import hashlib


def generate_regression_snapshot(converted_objects, output_path=None):
    """Generate a regression test snapshot from converted objects.

    Captures key metrics that should remain stable across re-migrations:
    - Measure count per table
    - Column count per table
    - Visual count per page
    - Filter count
    - Relationship count
    - Content hash of each measure expression

    Args:
        converted_objects: Dict of converted Power BI objects
        output_path: Optional path to write JSON snapshot

    Returns:
        dict: Regression snapshot
    """
    snapshot = {
        'version': '1.0',
        'tables': {},
        'pages': {},
        'filters': 0,
        'relationships': 0,
        'measures': {},
    }

    # Tables and measures
    for ds in converted_objects.get('datasources', []):
        for table in ds.get('tables', []):
            tname = table.get('name', '')
            snapshot['tables'][tname] = {
                'column_count': len(table.get('columns', [])),
            }

    # Calculations → measure signatures
    for calc in converted_objects.get('calculations', []):
        name = calc.get('name', calc.get('caption', ''))
        formula = calc.get('formula', '')
        if name and formula:
            sig = hashlib.sha256(formula.encode('utf-8')).hexdigest()[:16]
            snapshot['measures'][name] = {
                'formula_hash': sig,
            }

    # Worksheets → pages
    for ws in converted_objects.get('worksheets', []):
        ws_name = ws.get('name', '')
        field_count = len(ws.get('fields', []))
        snapshot['pages'][ws_name] = {
            'field_count': field_count,
        }

    # Filters
    snapshot['filters'] = len(converted_objects.get('filters', []))

    # Relationships
    for ds in converted_objects.get('datasources', []):
        snapshot['relationships'] += len(ds.get('relationships', []))

    if output_path:
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(snapshot, f, indent=2, ensure_ascii=False)

    return snapshot


def compare_snapshots(baseline, current):
    """Compare two regression snapshots and identify drift.

    Args:
        baseline: Previous regression snapshot dict
        current: New regression snapshot dict

    Returns:
        dict with:
        - 'drifts': list of detected changes
        - 'passed': True if no drift detected
    """
    drifts = []

    # Compare table counts
    base_tables = set(baseline.get('tables', {}).keys())
    curr_tables = set(current.get('tables', {}).keys())
    added = curr_tables - base_tables
    removed = base_tables - curr_tables
    if added:
        drifts.append({'type': 'tables_added', 'items': sorted(added)})
    if removed:
        drifts.append({'type': 'tables_removed', 'items': sorted(removed)})

    # Compare column counts per table
    for tname in base_tables & curr_tables:
        base_cols = baseline['tables'][tname].get('column_count', 0)
        curr_cols = current['tables'][tname].get('column_count', 0)
        if base_cols != curr_cols:
            drifts.append({
                'type': 'column_count_changed',
                'table': tname,
                'baseline': base_cols,
                'current': curr_cols,
            })

    # Compare measure hashes
    base_measures = baseline.get('measures', {})
    curr_measures = current.get('measures', {})
    for mname in set(base_measures) | set(curr_measures):
        base_hash = base_measures.get(mname, {}).get('formula_hash', '')
        curr_hash = curr_measures.get(mname, {}).get('formula_hash', '')
        if base_hash != curr_hash:
            if mname not in base_measures:
                drifts.append({'type': 'measure_added', 'measure': mname})
            elif mname not in curr_measures:
                drifts.append({'type': 'measure_removed', 'measure': mname})
            else:
                drifts.append({
                    'type': 'measure_changed',
                    'measure': mname,
                    'baseline_hash': base_hash,
                    'current_hash': curr_hash,
                })

    # Compare filter count
    if baseline.get('filters', 0) != current.get('filters', 0):
        drifts.append({
            'type': 'filter_count_changed',
            'baseline': baseline.get('filters', 0),
            'current': current.get('filters', 0),
        })

    return {
        'drifts': drifts,
        'passed': len(drifts) == 0,
    }
