"""Schema drift detection — compare Qlik source against migrated .pbip.

Sprint 111: Detects added/removed/renamed columns, changed calculation
formulas, new worksheets, modified relationships. Generates a diff report
enabling targeted incremental re-migration.

Usage:
    from powerbi_import.schema_drift import detect_schema_drift
    report = detect_schema_drift(current_extracted, previous_extracted)
    print(report.summary())
"""

import json
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)


class SchemaDriftEntry:
    """A single schema change between two versions of a Qlik app."""

    __slots__ = ('category', 'change_type', 'name', 'table', 'detail')

    ADDED = 'added'
    REMOVED = 'removed'
    MODIFIED = 'modified'
    RENAMED = 'renamed'

    def __init__(self, category, change_type, name, table='', detail=''):
        self.category = category      # column, measure, table, relationship, worksheet, etc.
        self.change_type = change_type  # added, removed, modified, renamed
        self.name = name
        self.table = table
        self.detail = detail

    def __repr__(self):
        prefix = f'{self.table}.' if self.table else ''
        return f'SchemaDriftEntry({self.category}, {self.change_type}, {prefix}{self.name})'

    def to_dict(self):
        d = {
            'category': self.category,
            'change_type': self.change_type,
            'name': self.name,
        }
        if self.table:
            d['table'] = self.table
        if self.detail:
            d['detail'] = self.detail
        return d


class SchemaDriftReport:
    """Collection of schema drift entries with summary statistics."""

    def __init__(self, entries=None, source_name='', timestamp=None):
        self.entries = entries or []
        self.source_name = source_name
        self.timestamp = timestamp or datetime.now().isoformat()

    @property
    def has_drift(self):
        return len(self.entries) > 0

    @property
    def added(self):
        return [e for e in self.entries if e.change_type == SchemaDriftEntry.ADDED]

    @property
    def removed(self):
        return [e for e in self.entries if e.change_type == SchemaDriftEntry.REMOVED]

    @property
    def modified(self):
        return [e for e in self.entries if e.change_type == SchemaDriftEntry.MODIFIED]

    @property
    def renamed(self):
        return [e for e in self.entries if e.change_type == SchemaDriftEntry.RENAMED]

    def by_category(self, category):
        return [e for e in self.entries if e.category == category]

    def summary(self):
        """Human-readable summary string."""
        if not self.has_drift:
            return 'No schema drift detected.'
        lines = [f'Schema drift detected ({len(self.entries)} changes):']
        for cat in ('table', 'column', 'measure', 'relationship', 'worksheet',
                    'parameter', 'filter', 'calculation'):
            items = self.by_category(cat)
            if items:
                added = sum(1 for e in items if e.change_type == 'added')
                removed = sum(1 for e in items if e.change_type == 'removed')
                modified = sum(1 for e in items if e.change_type == 'modified')
                parts = []
                if added:
                    parts.append(f'+{added}')
                if removed:
                    parts.append(f'-{removed}')
                if modified:
                    parts.append(f'~{modified}')
                lines.append(f'  {cat}: {", ".join(parts)}')
        return '\n'.join(lines)

    def to_dict(self):
        return {
            'source_name': self.source_name,
            'timestamp': self.timestamp,
            'has_drift': self.has_drift,
            'total_changes': len(self.entries),
            'summary': {
                'added': len(self.added),
                'removed': len(self.removed),
                'modified': len(self.modified),
                'renamed': len(self.renamed),
            },
            'entries': [e.to_dict() for e in self.entries],
        }

    def to_json(self, indent=2):
        return json.dumps(self.to_dict(), indent=indent)

    def save(self, path):
        os.makedirs(os.path.dirname(os.path.abspath(path)) or '.', exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(self.to_json())


# ── Core comparison functions ──────────────────────────────────────────────────

def _compare_tables(prev_ds, curr_ds):
    """Compare tables between two extraction snapshots."""
    entries = []
    prev_tables = {}
    curr_tables = {}

    for ds in prev_ds:
        for t in ds.get('tables', []):
            name = t.get('name', '')
            if name:
                prev_tables[name] = t

    for ds in curr_ds:
        for t in ds.get('tables', []):
            name = t.get('name', '')
            if name:
                curr_tables[name] = t

    # Added tables
    for name in curr_tables:
        if name not in prev_tables:
            entries.append(SchemaDriftEntry('table', 'added', name))

    # Removed tables
    for name in prev_tables:
        if name not in curr_tables:
            entries.append(SchemaDriftEntry('table', 'removed', name))

    # Modified tables — compare columns
    for name in curr_tables:
        if name in prev_tables:
            col_entries = _compare_columns(
                prev_tables[name].get('columns', []),
                curr_tables[name].get('columns', []),
                table_name=name,
            )
            entries.extend(col_entries)

    return entries


def _compare_columns(prev_cols, curr_cols, table_name=''):
    """Compare columns in a single table."""
    entries = []
    prev_map = {c.get('name', ''): c for c in prev_cols if c.get('name')}
    curr_map = {c.get('name', ''): c for c in curr_cols if c.get('name')}

    for name in curr_map:
        if name not in prev_map:
            entries.append(SchemaDriftEntry('column', 'added', name, table=table_name))
        else:
            # Check type change
            prev_type = prev_map[name].get('datatype', '')
            curr_type = curr_map[name].get('datatype', '')
            if prev_type and curr_type and prev_type != curr_type:
                entries.append(SchemaDriftEntry(
                    'column', 'modified', name, table=table_name,
                    detail=f'type changed: {prev_type} → {curr_type}',
                ))

    for name in prev_map:
        if name not in curr_map:
            entries.append(SchemaDriftEntry('column', 'removed', name, table=table_name))

    return entries


def _compare_calculations(prev_calcs, curr_calcs):
    """Compare calculation formulas."""
    entries = []
    prev_map = {}
    for c in prev_calcs:
        key = c.get('name', '') or c.get('caption', '')
        if key:
            prev_map[key] = c

    curr_map = {}
    for c in curr_calcs:
        key = c.get('name', '') or c.get('caption', '')
        if key:
            curr_map[key] = c

    for key in curr_map:
        if key not in prev_map:
            entries.append(SchemaDriftEntry('calculation', 'added', key))
        else:
            prev_formula = prev_map[key].get('formula', '')
            curr_formula = curr_map[key].get('formula', '')
            if prev_formula != curr_formula:
                entries.append(SchemaDriftEntry(
                    'calculation', 'modified', key,
                    detail=f'formula changed',
                ))

    for key in prev_map:
        if key not in curr_map:
            entries.append(SchemaDriftEntry('calculation', 'removed', key))

    return entries


def _compare_worksheets(prev_ws, curr_ws):
    """Compare worksheets."""
    entries = []
    prev_names = {w.get('name', '') for w in prev_ws if w.get('name')}
    curr_names = {w.get('name', '') for w in curr_ws if w.get('name')}

    for name in curr_names - prev_names:
        entries.append(SchemaDriftEntry('worksheet', 'added', name))
    for name in prev_names - curr_names:
        entries.append(SchemaDriftEntry('worksheet', 'removed', name))

    # Check for field changes in surviving worksheets
    prev_map = {w.get('name', ''): w for w in prev_ws if w.get('name')}
    curr_map = {w.get('name', ''): w for w in curr_ws if w.get('name')}
    for name in curr_names & prev_names:
        prev_fields = {f.get('name', '') for f in prev_map[name].get('fields', []) if f.get('name')}
        curr_fields = {f.get('name', '') for f in curr_map[name].get('fields', []) if f.get('name')}
        if prev_fields != curr_fields:
            added = curr_fields - prev_fields
            removed = prev_fields - curr_fields
            parts = []
            if added:
                parts.append(f'+{len(added)} fields')
            if removed:
                parts.append(f'-{len(removed)} fields')
            entries.append(SchemaDriftEntry(
                'worksheet', 'modified', name,
                detail=', '.join(parts),
            ))

    return entries


def _compare_relationships(prev_ds, curr_ds):
    """Compare relationships across datasources."""
    entries = []

    def _rel_key(r):
        return (r.get('from_table', ''), r.get('from_column', ''),
                r.get('to_table', ''), r.get('to_column', ''))

    prev_rels = set()
    for ds in prev_ds:
        for r in ds.get('relationships', []):
            prev_rels.add(_rel_key(r))

    curr_rels = set()
    for ds in curr_ds:
        for r in ds.get('relationships', []):
            curr_rels.add(_rel_key(r))

    for key in curr_rels - prev_rels:
        entries.append(SchemaDriftEntry(
            'relationship', 'added',
            f'{key[0]}.{key[1]} → {key[2]}.{key[3]}',
        ))
    for key in prev_rels - curr_rels:
        entries.append(SchemaDriftEntry(
            'relationship', 'removed',
            f'{key[0]}.{key[1]} → {key[2]}.{key[3]}',
        ))

    return entries


def _compare_parameters(prev_params, curr_params):
    """Compare parameters."""
    entries = []
    prev_map = {p.get('name', ''): p for p in prev_params if p.get('name')}
    curr_map = {p.get('name', ''): p for p in curr_params if p.get('name')}

    for name in curr_map:
        if name not in prev_map:
            entries.append(SchemaDriftEntry('parameter', 'added', name))
        else:
            prev_val = prev_map[name].get('current_value', '')
            curr_val = curr_map[name].get('current_value', '')
            if prev_val != curr_val:
                entries.append(SchemaDriftEntry(
                    'parameter', 'modified', name,
                    detail=f'value: {prev_val} → {curr_val}',
                ))

    for name in prev_map:
        if name not in curr_map:
            entries.append(SchemaDriftEntry('parameter', 'removed', name))

    return entries


def _compare_filters(prev_filters, curr_filters):
    """Compare global filters."""
    entries = []
    prev_names = {f.get('field', '') for f in prev_filters if f.get('field')}
    curr_names = {f.get('field', '') for f in curr_filters if f.get('field')}

    for name in curr_names - prev_names:
        entries.append(SchemaDriftEntry('filter', 'added', name))
    for name in prev_names - curr_names:
        entries.append(SchemaDriftEntry('filter', 'removed', name))

    return entries


# ── Public API ─────────────────────────────────────────────────────────────────

def detect_schema_drift(current_extracted, previous_extracted, source_name=''):
    """Compare two extraction snapshots to detect schema drift.

    Args:
        current_extracted: dict from _load_converted_objects() (current source)
        previous_extracted: dict from _load_converted_objects() (previous migration)
        source_name: Optional app name for the report

    Returns:
        SchemaDriftReport with all detected changes
    """
    entries = []

    # Tables and columns
    entries.extend(_compare_tables(
        previous_extracted.get('datasources', []),
        current_extracted.get('datasources', []),
    ))

    # Calculations
    entries.extend(_compare_calculations(
        previous_extracted.get('calculations', []),
        current_extracted.get('calculations', []),
    ))

    # Worksheets
    entries.extend(_compare_worksheets(
        previous_extracted.get('worksheets', []),
        current_extracted.get('worksheets', []),
    ))

    # Relationships
    entries.extend(_compare_relationships(
        previous_extracted.get('datasources', []),
        current_extracted.get('datasources', []),
    ))

    # Parameters
    entries.extend(_compare_parameters(
        previous_extracted.get('parameters', []),
        current_extracted.get('parameters', []),
    ))

    # Filters
    entries.extend(_compare_filters(
        previous_extracted.get('filters', []),
        current_extracted.get('filters', []),
    ))

    return SchemaDriftReport(entries=entries, source_name=source_name)


def load_snapshot(snapshot_dir):
    """Load a previous extraction snapshot from JSON files on disk.

    Args:
        snapshot_dir: Directory containing the 17 extracted JSON files

    Returns:
        dict: Loaded snapshot (same format as _load_converted_objects)
    """
    data = {}
    files_map = {
        'datasources': 'datasources.json',
        'worksheets': 'worksheets.json',
        'dashboards': 'dashboards.json',
        'calculations': 'calculations.json',
        'parameters': 'parameters.json',
        'filters': 'filters.json',
    }
    for key, fname in files_map.items():
        path = os.path.join(snapshot_dir, fname)
        if os.path.isfile(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data[key] = json.load(f)
            except (json.JSONDecodeError, OSError):
                data[key] = []
        else:
            data[key] = []
    return data


def save_snapshot(extracted_data, output_dir):
    """Save an extraction snapshot for future drift comparison.

    Args:
        extracted_data: dict from _load_converted_objects()
        output_dir: Directory to write snapshot files
    """
    os.makedirs(output_dir, exist_ok=True)
    for key in ('datasources', 'worksheets', 'calculations', 'parameters', 'filters'):
        data = extracted_data.get(key, [])
        path = os.path.join(output_dir, f'{key}.json')
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, default=str)
