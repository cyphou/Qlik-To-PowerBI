"""Self-Healing v3 — twelve model healers.

Catches the most common reasons a generated .pbip refuses to open in
Power BI Desktop or fails to refresh data:

  1. Globally duplicate measure names
  2. Self-referencing measures (infinite recursion)
  3. Sort-by-column self-reference / missing target
  4. Hierarchy levels referencing missing columns
  5. Display folder name normalization
  6. Relationship data type mismatch
  7. Invalid identifier characters
  8. Int64 with decimal-precision formatString
  9. dataType case normalization
 10. Duplicate relationships
 11. isHidden + isKey conflict on date-table key
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Set


__all__ = ['run_v3_healers']

_DATATYPE_CANONICAL: Dict[str, str] = {
    'string': 'string',
    'int64': 'int64',
    'integer': 'int64',
    'long': 'int64',
    'double': 'double',
    'decimal': 'decimal',
    'datetime': 'dateTime',
    'date': 'dateTime',
    'time': 'dateTime',
    'boolean': 'boolean',
    'bool': 'boolean',
    'binary': 'binary',
    'variant': 'variant',
}

_DATATYPE_VALID: Set[str] = {
    'string', 'String',
    'int64', 'Int64',
    'double', 'Double',
    'decimal', 'Decimal',
    'dateTime', 'DateTime',
    'boolean', 'Boolean',
    'binary', 'Binary',
    'variant', 'Variant',
}

_INVALID_NAME_CHARS = re.compile(r'[\x00-\x1f\x7f]')
_DECIMAL_FMT = re.compile(r'\.[#0]')
_PERCENT_FMT = re.compile(r'%')

_TYPE_FAMILY: Dict[str, str] = {
    'string': 'text',
    'int64': 'numeric',
    'double': 'numeric',
    'decimal': 'numeric',
    'datetime': 'datetime',
    'date': 'datetime',
    'boolean': 'boolean',
    'binary': 'binary',
}


def _heal_global_measure_dupes(model, recovery=None) -> int:
    repairs = 0
    tables = model.get('model', {}).get('tables', []) or []
    seen: Dict[str, str] = {}
    for tbl in tables:
        tname = tbl.get('name', '') or ''
        for m in tbl.get('measures', []) or []:
            mname = m.get('name', '') or ''
            if not mname:
                continue
            if mname not in seen:
                seen[mname] = tname
                continue
            owning = seen[mname]
            suffix_base = re.sub(r'\W+', '_', tname).strip('_') or 'tbl'
            new_name = f'{mname}_{suffix_base}'
            counter = 2
            while new_name in seen:
                new_name = f'{mname}_{suffix_base}_{counter}'
                counter += 1
            old_name = mname
            m['name'] = new_name
            seen[new_name] = tname
            m.setdefault('annotations', []).append({
                'name': 'MigrationNote',
                'value': (f'Self-heal: renamed from "{old_name}" -- duplicates '
                          f'measure on table "{owning}".'),
            })
            repairs += 1
            if recovery is not None:
                recovery.record(
                    'tmdl', 'duplicate_measure_global',
                    item_name=f'{tname}.{old_name}',
                    description=(f'Measure "{old_name}" duplicated across '
                                 f'tables (also on "{owning}")'),
                    action=f'Renamed to "{new_name}" on "{tname}"',
                    severity='warning',
                    follow_up='Verify visuals using this measure still resolve',
                )
    return repairs


def _heal_self_referencing_measures(model, recovery=None) -> int:
    repairs = 0
    tables = model.get('model', {}).get('tables', []) or []
    for tbl in tables:
        tname = tbl.get('name', '') or ''
        for m in tbl.get('measures', []) or []:
            mname = m.get('name', '') or ''
            expr = m.get('expression', '') or ''
            if not mname or not expr:
                continue
            bare = re.compile(r'\[' + re.escape(mname) + r'\]')
            qualified = re.compile(
                r"'" + re.escape(tname.replace("'", "''")) + r"'\[" +
                re.escape(mname) + r'\]'
            )
            if not (bare.search(expr) or qualified.search(expr)):
                continue
            m['expression'] = 'BLANK()'
            m['isHidden'] = True
            m.setdefault('annotations', []).append({
                'name': 'MigrationNote',
                'value': (f'Self-heal: self-referencing measure. '
                          f'Original: {expr[:200]}'),
            })
            repairs += 1
            if recovery is not None:
                recovery.record(
                    'tmdl', 'self_referencing_measure',
                    item_name=f'{tname}.{mname}',
                    description=f'Measure "{mname}" references itself',
                    action='Replaced body with BLANK() and hid measure',
                    severity='warning',
                    follow_up=f'Rewrite measure "{mname}" without self-reference',
                )
    return repairs


def _heal_sort_by_column(model, recovery=None) -> int:
    repairs = 0
    for tbl in model.get('model', {}).get('tables', []) or []:
        tname = tbl.get('name', '') or ''
        col_names: Set[str] = {
            c.get('name', '') for c in tbl.get('columns', []) or []
            if c.get('name')
        }
        for col in tbl.get('columns', []) or []:
            cname = col.get('name', '') or ''
            target = col.get('sortByColumn', '') or ''
            if not target:
                continue
            if target == cname:
                col.pop('sortByColumn', None)
                repairs += 1
                if recovery is not None:
                    recovery.record(
                        'tmdl', 'sort_by_column_self',
                        item_name=f'{tname}.{cname}',
                        description=f'sortByColumn points at itself',
                        action='Removed sortByColumn',
                        severity='warning',
                    )
                continue
            if target not in col_names:
                col.pop('sortByColumn', None)
                repairs += 1
                if recovery is not None:
                    recovery.record(
                        'tmdl', 'sort_by_column_missing',
                        item_name=f'{tname}.{cname}',
                        description=f'sortByColumn target "{target}" not found',
                        action='Removed sortByColumn',
                        severity='warning',
                    )
    return repairs


def _heal_hierarchies(model, recovery=None) -> int:
    repairs = 0
    for tbl in model.get('model', {}).get('tables', []) or []:
        tname = tbl.get('name', '') or ''
        col_names: Set[str] = {
            c.get('name', '') for c in tbl.get('columns', []) or []
            if c.get('name')
        }
        kept_hierarchies = []
        for hier in tbl.get('hierarchies', []) or []:
            hname = hier.get('name', '') or ''
            kept_levels = []
            for lvl in hier.get('levels', []) or []:
                src = lvl.get('column', '') or lvl.get('sourceColumn', '') or ''
                if src and src in col_names:
                    kept_levels.append(lvl)
                    continue
                repairs += 1
                if recovery is not None:
                    recovery.record(
                        'tmdl', 'hierarchy_level_missing_column',
                        item_name=f'{tname}.{hname}.{lvl.get("name", "?")}',
                        description=f'Level references missing column "{src}"',
                        action='Level dropped from hierarchy',
                        severity='warning',
                    )
            if kept_levels:
                hier['levels'] = kept_levels
                kept_hierarchies.append(hier)
            else:
                repairs += 1
                if recovery is not None:
                    recovery.record(
                        'tmdl', 'hierarchy_dropped',
                        item_name=f'{tname}.{hname}',
                        description='Hierarchy had no valid levels remaining',
                        action='Hierarchy removed',
                        severity='warning',
                    )
        tbl['hierarchies'] = kept_hierarchies
    return repairs


def _heal_display_folder_names(model, recovery=None) -> int:
    repairs = 0
    for tbl in model.get('model', {}).get('tables', []) or []:
        tname = tbl.get('name', '') or ''
        for item in (tbl.get('measures', []) or []) + (tbl.get('columns', []) or []):
            folder = item.get('displayFolder', '')
            if not folder:
                continue
            cleaned = folder.strip()
            cleaned = re.sub(r'\\{2,}', '\\\\', cleaned)
            cleaned = cleaned.strip('\\')
            if cleaned != folder:
                item['displayFolder'] = cleaned
                repairs += 1
                if recovery is not None:
                    recovery.record(
                        'tmdl', 'display_folder_normalized',
                        item_name=f'{tname}.{item.get("name", "?")}',
                        description=f'Display folder normalized',
                        action=f'"{folder}" -> "{cleaned}"',
                        severity='info',
                    )
    return repairs


def _heal_relationship_type_mismatch(model, recovery=None) -> int:
    repairs = 0
    tables = model.get('model', {}).get('tables', []) or []
    col_types: Dict[str, Dict[str, str]] = {}
    for tbl in tables:
        tname = tbl.get('name', '') or ''
        for col in tbl.get('columns', []) or []:
            cname = col.get('name', '') or ''
            dtype = (col.get('dataType', '') or '').lower()
            col_types.setdefault(tname, {})[cname] = dtype

    relationships = model.get('model', {}).get('relationships', []) or []
    kept = []
    for rel in relationships:
        from_tbl = rel.get('fromTable', '') or ''
        from_col = rel.get('fromColumn', '') or ''
        to_tbl = rel.get('toTable', '') or ''
        to_col = rel.get('toColumn', '') or ''
        from_type = col_types.get(from_tbl, {}).get(from_col, '')
        to_type = col_types.get(to_tbl, {}).get(to_col, '')
        from_family = _TYPE_FAMILY.get(from_type, from_type)
        to_family = _TYPE_FAMILY.get(to_type, to_type)
        if from_family and to_family and from_family != to_family:
            repairs += 1
            if recovery is not None:
                recovery.record(
                    'relationship', 'type_mismatch',
                    item_name=f'{from_tbl}.{from_col} -> {to_tbl}.{to_col}',
                    description=(f'Type mismatch: {from_type} ({from_family}) vs '
                                 f'{to_type} ({to_family})'),
                    action='Relationship removed',
                    severity='warning',
                )
            continue
        kept.append(rel)
    model.get('model', {})['relationships'] = kept
    return repairs


def _heal_invalid_identifier_chars(model, recovery=None) -> int:
    repairs = 0
    for tbl in model.get('model', {}).get('tables', []) or []:
        tname = tbl.get('name', '') or ''
        if _INVALID_NAME_CHARS.search(tname):
            new_name = _INVALID_NAME_CHARS.sub('', tname)
            tbl['name'] = new_name
            repairs += 1
            if recovery is not None:
                recovery.record(
                    'tmdl', 'invalid_identifier_chars',
                    item_name=tname, description='Control chars in table name',
                    action=f'Cleaned to "{new_name}"', severity='warning',
                )
        for col in tbl.get('columns', []) or []:
            cname = col.get('name', '') or ''
            if _INVALID_NAME_CHARS.search(cname):
                new_name = _INVALID_NAME_CHARS.sub('', cname)
                col['name'] = new_name
                repairs += 1
                if recovery is not None:
                    recovery.record(
                        'tmdl', 'invalid_identifier_chars',
                        item_name=f'{tbl.get("name","")}.{cname}',
                        description='Control chars in column name',
                        action=f'Cleaned to "{new_name}"', severity='warning',
                    )
        for m in tbl.get('measures', []) or []:
            mname = m.get('name', '') or ''
            if _INVALID_NAME_CHARS.search(mname):
                new_name = _INVALID_NAME_CHARS.sub('', mname)
                m['name'] = new_name
                repairs += 1
                if recovery is not None:
                    recovery.record(
                        'tmdl', 'invalid_identifier_chars',
                        item_name=f'{tbl.get("name","")}.{mname}',
                        description='Control chars in measure name',
                        action=f'Cleaned to "{new_name}"', severity='warning',
                    )
    return repairs


def _heal_int64_decimal_format(model, recovery=None) -> int:
    repairs = 0
    for tbl in model.get('model', {}).get('tables', []) or []:
        tname = tbl.get('name', '') or ''
        for col in tbl.get('columns', []) or []:
            dtype = (col.get('dataType', '') or '').lower()
            fmt = col.get('formatString', '') or ''
            if dtype == 'int64' and fmt and _DECIMAL_FMT.search(fmt):
                col['dataType'] = 'double'
                repairs += 1
                if recovery is not None:
                    recovery.record(
                        'tmdl', 'int64_decimal_format',
                        item_name=f'{tname}.{col.get("name", "?")}',
                        description=f'Int64 with decimal format "{fmt}"',
                        action='Promoted to double',
                        severity='info',
                    )
    return repairs


def _heal_datatype_casing(model, recovery=None) -> int:
    repairs = 0
    for tbl in model.get('model', {}).get('tables', []) or []:
        tname = tbl.get('name', '') or ''
        for col in tbl.get('columns', []) or []:
            dtype = col.get('dataType', '')
            if not dtype or dtype in _DATATYPE_VALID:
                continue
            canonical = _DATATYPE_CANONICAL.get(dtype.lower())
            if canonical and canonical != dtype:
                col['dataType'] = canonical
                repairs += 1
                if recovery is not None:
                    recovery.record(
                        'tmdl', 'datatype_casing',
                        item_name=f'{tname}.{col.get("name", "?")}',
                        description=f'Non-canonical dataType "{dtype}"',
                        action=f'Normalized to "{canonical}"',
                        severity='info',
                    )
    return repairs


def _heal_duplicate_relationships(model, recovery=None) -> int:
    repairs = 0
    relationships = model.get('model', {}).get('relationships', []) or []
    seen: Set[tuple] = set()
    kept = []
    for rel in relationships:
        key = (
            rel.get('fromTable', ''), rel.get('fromColumn', ''),
            rel.get('toTable', ''), rel.get('toColumn', ''),
        )
        if key in seen:
            rel['isActive'] = False
            repairs += 1
            if recovery is not None:
                recovery.record(
                    'relationship', 'duplicate_relationship',
                    item_name=f'{key[0]}.{key[1]} -> {key[2]}.{key[3]}',
                    description='Duplicate relationship',
                    action='Deactivated duplicate',
                    severity='warning',
                )
        else:
            seen.add(key)
        kept.append(rel)
    model.get('model', {})['relationships'] = kept
    return repairs


def _heal_iskey_ishidden_conflict(model, recovery=None) -> int:
    repairs = 0
    for tbl in model.get('model', {}).get('tables', []) or []:
        tname = tbl.get('name', '') or ''
        for col in tbl.get('columns', []) or []:
            is_key = col.get('isKey', False)
            is_hidden = col.get('isHidden', False)
            if is_key and is_hidden:
                col['isHidden'] = False
                repairs += 1
                if recovery is not None:
                    recovery.record(
                        'tmdl', 'iskey_ishidden_conflict',
                        item_name=f'{tname}.{col.get("name", "?")}',
                        description='isKey and isHidden both true',
                        action='Set isHidden = false',
                        severity='warning',
                    )
    return repairs


_ALL_HEALERS = [
    _heal_global_measure_dupes,
    _heal_self_referencing_measures,
    _heal_sort_by_column,
    _heal_hierarchies,
    _heal_display_folder_names,
    _heal_relationship_type_mismatch,
    _heal_invalid_identifier_chars,
    _heal_int64_decimal_format,
    _heal_datatype_casing,
    _heal_duplicate_relationships,
    _heal_iskey_ishidden_conflict,
]


def run_v3_healers(model: dict, recovery=None) -> int:
    """Run all v3 self-healing passes on model dict.

    Returns total number of repairs applied.
    """
    total = 0
    for healer in _ALL_HEALERS:
        try:
            count = healer(model, recovery)
            total += count
        except Exception:
            pass
    return total
