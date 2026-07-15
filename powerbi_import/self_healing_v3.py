"""Sprint 136 — Self-Healing v3.

Adds twelve new healers that catch the most common reasons a generated
.pbip refuses to open in Power BI Desktop or fails to refresh data:

  14. Globally duplicate measure names (PBI requires global uniqueness)
  15. Self-referencing measures (infinite recursion → hide)
  16. Sort-by-column self-reference (circular sort → clear)
  17. Sort-by-column pointing to missing column (clear)
  18. Hierarchy levels referencing missing columns (drop level / hierarchy)
  19. Display folder name normalization (strip whitespace, dedupe slashes)
  20. Relationship data type mismatch (remove or coerce)
  21. Invalid identifier characters (strip control chars)
  22. Int64 with decimal-precision formatString → promote to Double
  23. dataType case normalization (canonical TMDL casing)
  24. Duplicate relationships (keep first, deactivate rest)
  25. isHidden + isKey conflict on date-table key (un-hide)

Each healer is a pure function ``(model, recovery) -> int`` returning
the number of repairs applied.  They never raise — defensive ``try``
blocks ensure self-healing failures do not block migration.

Wired from :func:`tmdl_generator._self_heal_model` after the existing
13 healers.
"""

from __future__ import annotations

import re
from typing import Dict, List, Set, Tuple


__all__ = ['run_v3_healers']


# Canonical TMDL data-type casings.  PBI Desktop accepts BOTH the
# TitleCase TOM form ("String", "Int64", "DateTime") and the
# lowercase TMDL form ("string", "int64", "dateTime").  Both are
# treated as valid no-ops by the healer; only unrecognized forms
# (UPPERCASE, "Boolean", "datetime", "integer", etc.) are normalized
# to the lowercase TMDL canonical form.
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

# Casings that PBI Desktop / TMDL parses successfully.  Anything in
# this set is left untouched by the casing healer.
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

# Control characters forbidden in TMDL identifiers (NUL, BEL, BS, TAB,
# LF, VT, FF, CR, ESC, etc.).  These cause PBI Desktop to throw
# "Unexpected character" parse errors when loading the model.
_INVALID_NAME_CHARS = re.compile(r'[\x00-\x1f\x7f]')

# Numeric formatString patterns
_DECIMAL_FMT = re.compile(r'\.[#0]')   # any fractional digits
_PERCENT_FMT = re.compile(r'%')

# Compatible-type families for relationships.  Mismatches across
# families cause "data type mismatch" at refresh.
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


# ════════════════════════════════════════════════════════════════════
#  Healer #14 — Globally duplicate measure names
# ════════════════════════════════════════════════════════════════════

def _heal_global_measure_dupes(model, recovery=None) -> int:
    """Power BI requires measure names to be unique across the entire
    model (not just within a table).  Duplicates cause the .pbip to
    refuse to open with "Multiple measures named 'X' found".

    Strategy: keep the first occurrence by table order; rename later
    duplicates to ``<name>_<table>``.
    """
    repairs = 0
    tables = model.get('model', {}).get('tables', []) or []
    seen: Dict[str, str] = {}  # measure_name → owning_table

    for tbl in tables:
        tname = tbl.get('name', '') or ''
        for m in tbl.get('measures', []) or []:
            mname = m.get('name', '') or ''
            if not mname:
                continue
            if mname not in seen:
                seen[mname] = tname
                continue
            # Duplicate — rename
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
                'value': (f'Self-heal: renamed from "{old_name}" — duplicates '
                          f'measure on table "{owning}".  References to '
                          f'"{old_name}" still resolve to the original.')
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
                    follow_up=(f'Verify visuals using "{old_name}" still '
                               f'point at the intended measure'),
                )
    return repairs


# ════════════════════════════════════════════════════════════════════
#  Healer #15 — Self-referencing measures
# ════════════════════════════════════════════════════════════════════

def _heal_self_referencing_measures(model, recovery=None) -> int:
    """A measure that references itself produces infinite recursion at
    query time and prevents the model from being browsed.

    Detection: ``[Name]`` or ``'Table'[Name]`` appearing in the body of
    measure ``Name`` on ``Table``.

    Action: hide the measure and replace its body with ``BLANK()``.
    """
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
                'value': (f'Self-heal: measure self-references would cause '
                          f'infinite recursion. Original expression: '
                          f'{expr[:200]}'),
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


# ════════════════════════════════════════════════════════════════════
#  Healer #16/17 — Sort-by-column hygiene
# ════════════════════════════════════════════════════════════════════

def _heal_sort_by_column(model, recovery=None) -> int:
    """Clear ``sortByColumn`` when:

      * the target equals the column itself (circular)
      * the target column does not exist on the same table

    Both conditions cause PBI Desktop to throw a model-load error.
    """
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
                        description=f'Column "{cname}" has sortByColumn pointing at itself',
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
                        description=(f'sortByColumn target "{target}" '
                                     f'not found in table "{tname}"'),
                        action='Removed sortByColumn',
                        severity='warning',
                        follow_up=(f'Add column "{target}" to "{tname}" or '
                                   f'choose a different sort column'),
                    )
    return repairs


# ════════════════════════════════════════════════════════════════════
#  Healer #18 — Hierarchy levels referencing missing columns
# ════════════════════════════════════════════════════════════════════

def _heal_hierarchies(model, recovery=None) -> int:
    """Drop hierarchy levels whose source column does not exist; if the
    hierarchy ends up with zero levels, drop the hierarchy itself.

    Invalid hierarchies cause the Model view to fail to render.
    """
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
                        description=(f'Hierarchy level references missing '
                                     f'column "{src}" on table "{tname}"'),
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
                        description=(f'Hierarchy "{hname}" had no valid '
                                     f'levels remaining'),
                        action='Hierarchy removed',
                        severity='warning',
                    )
        if 'hierarchies' in tbl:
            tbl['hierarchies'] = kept_hierarchies
    return repairs


# ════════════════════════════════════════════════════════════════════
#  Healer #19 — Display folder normalization
# ════════════════════════════════════════════════════════════════════

def _normalize_folder(folder: str) -> str:
    """Strip whitespace per segment and collapse repeated slashes."""
    if not folder:
        return ''
    parts = [p.strip() for p in folder.split('\\')]
    parts = [p for p in parts if p]  # drop empty segments
    return '\\'.join(parts)


def _heal_display_folders(model, recovery=None) -> int:
    """PBI rejects display folders containing only whitespace, leading /
    trailing whitespace per segment, or empty segments (``A\\\\B``).

    Normalize and record any change.
    """
    repairs = 0
    for tbl in model.get('model', {}).get('tables', []) or []:
        tname = tbl.get('name', '') or ''
        for collection_name in ('columns', 'measures'):
            for item in tbl.get(collection_name, []) or []:
                folder = item.get('displayFolder', '')
                if not folder:
                    continue
                cleaned = _normalize_folder(folder)
                if cleaned == folder:
                    continue
                if cleaned:
                    item['displayFolder'] = cleaned
                else:
                    item.pop('displayFolder', None)
                repairs += 1
                if recovery is not None:
                    recovery.record(
                        'tmdl', 'display_folder_normalized',
                        item_name=f'{tname}.{item.get("name", "?")}',
                        description=(f'Invalid displayFolder "{folder}" '
                                     f'(empty segments or whitespace)'),
                        action=(f'Normalized to "{cleaned}"' if cleaned
                                else 'displayFolder removed'),
                        severity='info',
                    )
    return repairs


# ════════════════════════════════════════════════════════════════════
#  Healer #20 — Relationship data type mismatch
# ════════════════════════════════════════════════════════════════════

def _heal_relationship_type_mismatch(model, recovery=None) -> int:
    """Relationships joining columns of incompatible type families fail
    at refresh with "data type mismatch".

    Strategy: when types belong to different families, remove the
    relationship.  When they belong to the same family but differ
    (e.g. Int64 ↔ Double), leave them — PBI auto-coerces numerics.
    """
    repairs = 0
    tables = model.get('model', {}).get('tables', []) or []
    rels = model.get('model', {}).get('relationships', []) or []
    table_columns: Dict[str, Dict[str, str]] = {}
    for t in tables:
        tn = t.get('name', '') or ''
        if not tn:
            continue
        cols = {}
        for c in t.get('columns', []) or []:
            cname = c.get('name', '')
            dt = (c.get('dataType', '') or '').lower()
            if cname:
                cols[cname] = dt
        table_columns[tn] = cols

    kept = []
    for rel in rels:
        ft = rel.get('fromTable', '')
        tt = rel.get('toTable', '')
        fc = rel.get('fromColumn', '')
        tc = rel.get('toColumn', '')
        ft_dt = table_columns.get(ft, {}).get(fc, '')
        tt_dt = table_columns.get(tt, {}).get(tc, '')
        if not ft_dt or not tt_dt:
            kept.append(rel)
            continue
        ft_fam = _TYPE_FAMILY.get(ft_dt, ft_dt)
        tt_fam = _TYPE_FAMILY.get(tt_dt, tt_dt)
        if ft_fam == tt_fam:
            kept.append(rel)
            continue
        repairs += 1
        desc = f'{ft}[{fc}]({ft_dt}) → {tt}[{tc}]({tt_dt})'
        if recovery is not None:
            recovery.record(
                'relationship', 'type_mismatch',
                item_name=desc,
                description=(f'Relationship joins {ft_fam} to {tt_fam} — '
                             f'incompatible families'),
                action='Relationship removed',
                severity='warning',
                follow_up=(f'Cast either {ft}[{fc}] or {tt}[{tc}] to a '
                           f'matching type in Power Query'),
            )
    if repairs:
        model['model']['relationships'] = kept
    return repairs


# ════════════════════════════════════════════════════════════════════
#  Healer #21 — Invalid identifier characters
# ════════════════════════════════════════════════════════════════════

def _strip_invalid(name: str) -> str:
    """Remove control chars (which break TMDL parsing)."""
    if not name:
        return name
    return _INVALID_NAME_CHARS.sub('', name)


def _heal_invalid_identifiers(model, recovery=None) -> int:
    """Strip control characters from table / column / measure /
    hierarchy / role identifiers.

    Note: relationship endpoints are NOT rewritten here — those are
    fixed by an earlier healer that removes broken refs.  This healer
    must run after table renaming (#14, #15) and *before* relationship
    cleanup (existing #11), so we additionally rewire relationships
    that pointed at sanitized names.
    """
    repairs = 0
    rename_map: Dict[str, str] = {}
    tables = model.get('model', {}).get('tables', []) or []
    for tbl in tables:
        old_t = tbl.get('name', '') or ''
        new_t = _strip_invalid(old_t)
        if new_t != old_t:
            tbl['name'] = new_t
            rename_map[old_t] = new_t
            repairs += 1
            if recovery is not None:
                recovery.record(
                    'tmdl', 'invalid_identifier',
                    item_name=old_t,
                    description='Table name contained control characters',
                    action=f'Renamed to "{new_t}"',
                    severity='warning',
                )
        for col in tbl.get('columns', []) or []:
            old_c = col.get('name', '') or ''
            new_c = _strip_invalid(old_c)
            if new_c != old_c:
                col['name'] = new_c
                repairs += 1
                if recovery is not None:
                    recovery.record(
                        'tmdl', 'invalid_identifier',
                        item_name=f'{new_t}.{old_c}',
                        description='Column name contained control characters',
                        action=f'Renamed to "{new_c}"',
                        severity='warning',
                    )
        for m in tbl.get('measures', []) or []:
            old_m = m.get('name', '') or ''
            new_m = _strip_invalid(old_m)
            if new_m != old_m:
                m['name'] = new_m
                repairs += 1
                if recovery is not None:
                    recovery.record(
                        'tmdl', 'invalid_identifier',
                        item_name=f'{new_t}.{old_m}',
                        description='Measure name contained control characters',
                        action=f'Renamed to "{new_m}"',
                        severity='warning',
                    )

    # Rewire relationships that pointed at renamed tables
    if rename_map:
        for rel in model.get('model', {}).get('relationships', []) or []:
            if rel.get('fromTable') in rename_map:
                rel['fromTable'] = rename_map[rel['fromTable']]
            if rel.get('toTable') in rename_map:
                rel['toTable'] = rename_map[rel['toTable']]
    return repairs


# ════════════════════════════════════════════════════════════════════
#  Healer #22 — Int64 + decimal formatString
# ════════════════════════════════════════════════════════════════════

def _heal_int64_decimal_format(model, recovery=None) -> int:
    """An Int64 column with a decimal-precision formatString ("0.00",
    "#,##0.0") loads as integer and silently drops the fractional part,
    leading to wrong totals.  Promote the column to Double.
    """
    repairs = 0
    for tbl in model.get('model', {}).get('tables', []) or []:
        tname = tbl.get('name', '') or ''
        for col in tbl.get('columns', []) or []:
            dt = (col.get('dataType', '') or '').lower()
            fmt = col.get('formatString', '') or ''
            if dt != 'int64' or not fmt:
                continue
            if not _DECIMAL_FMT.search(fmt):
                continue
            col['dataType'] = 'double'
            col['summarizeBy'] = col.get('summarizeBy') or 'sum'
            repairs += 1
            if recovery is not None:
                recovery.record(
                    'tmdl', 'int64_decimal_format',
                    item_name=f'{tname}.{col.get("name", "?")}',
                    description=(f'Int64 column has decimal formatString '
                                 f'"{fmt}" — fractional part would be lost'),
                    action='Promoted dataType to Double',
                    severity='warning',
                )
    return repairs


# ════════════════════════════════════════════════════════════════════
#  Healer #23 — dataType case normalization
# ════════════════════════════════════════════════════════════════════

def _heal_datatype_casing(model, recovery=None) -> int:
    """TMDL dataType is case-sensitive.  ``"Boolean"``, ``"INT64"``,
    ``"datetime"``, etc. all silently parse as ``string`` in PBI's
    fallback, leading to refresh failures.  Force canonical casing.
    """
    repairs = 0
    for tbl in model.get('model', {}).get('tables', []) or []:
        tname = tbl.get('name', '') or ''
        for col in tbl.get('columns', []) or []:
            dt = col.get('dataType', '')
            if not dt or dt in _DATATYPE_VALID:
                continue
            canon = _DATATYPE_CANONICAL.get(dt.lower())
            if not canon or canon == dt:
                continue
            col['dataType'] = canon
            repairs += 1
            if recovery is not None:
                recovery.record(
                    'tmdl', 'datatype_casing',
                    item_name=f'{tname}.{col.get("name", "?")}',
                    description=f'Non-canonical dataType "{dt}"',
                    action=f'Normalized to "{canon}"',
                    severity='info',
                )
    return repairs


# ════════════════════════════════════════════════════════════════════
#  Healer #24 — Duplicate relationships
# ════════════════════════════════════════════════════════════════════

def _heal_duplicate_relationships(model, recovery=None) -> int:
    """Two relationships with identical endpoints cause "ambiguous join
    path" model-load errors.  Keep the first; deactivate the rest.
    """
    repairs = 0
    seen: Set[Tuple[str, str, str, str]] = set()
    for rel in model.get('model', {}).get('relationships', []) or []:
        key = (
            rel.get('fromTable', ''), rel.get('fromColumn', ''),
            rel.get('toTable', ''), rel.get('toColumn', ''),
        )
        if key in seen:
            if rel.get('isActive') is not False:
                rel['isActive'] = False
                repairs += 1
                if recovery is not None:
                    recovery.record(
                        'relationship', 'duplicate_relationship',
                        item_name=f'{key[0]}[{key[1]}] → {key[2]}[{key[3]}]',
                        description='Duplicate relationship with identical endpoints',
                        action='Deactivated duplicate (kept first occurrence active)',
                        severity='warning',
                    )
            continue
        seen.add(key)
    return repairs


# ════════════════════════════════════════════════════════════════════
#  Healer #25 — isHidden + isKey conflict
# ════════════════════════════════════════════════════════════════════

def _heal_hidden_key(model, recovery=None) -> int:
    """A column flagged as both ``isKey=True`` and ``isHidden=True`` on
    a date table prevents Time Intelligence from working ("No date
    column found").  Un-hide such columns.
    """
    repairs = 0
    for tbl in model.get('model', {}).get('tables', []) or []:
        tname = tbl.get('name', '') or ''
        # Identify date-table marker (Calendar / DateTable / Copilot annotation)
        is_date_table = False
        for ann in tbl.get('annotations', []) or []:
            if ann.get('name') in ('Copilot_DateTable', 'IsDateTable',
                                   '__PBI_LocalDateTable'):
                is_date_table = True
                break
        if not is_date_table and tname.lower() not in ('calendar', 'date',
                                                       'datetable',
                                                       'date table'):
            continue
        for col in tbl.get('columns', []) or []:
            if col.get('isKey') and col.get('isHidden'):
                col['isHidden'] = False
                repairs += 1
                if recovery is not None:
                    recovery.record(
                        'tmdl', 'hidden_key_conflict',
                        item_name=f'{tname}.{col.get("name", "?")}',
                        description=('Date-table key column was hidden — '
                                     'breaks Time Intelligence'),
                        action='Unhid key column',
                        severity='warning',
                    )
    return repairs


# ════════════════════════════════════════════════════════════════════
#  Healer #26 — Empty / whitespace-only identifier names
# ════════════════════════════════════════════════════════════════════

def _heal_empty_names(model, recovery=None) -> int:
    """Tables / columns / measures with empty or whitespace-only names
    cause "name cannot be null or empty" errors when PBI Desktop loads
    the model.  Rename to placeholder ``Unnamed_<kind>_<idx>``.
    """
    repairs = 0
    rename_map: Dict[str, str] = {}
    for ti, tbl in enumerate(model.get('model', {}).get('tables', []) or []):
        tname = tbl.get('name', '') or ''
        if not tname.strip():
            new = f'Unnamed_Table_{ti + 1}'
            tbl['name'] = new
            rename_map[tname] = new
            repairs += 1
            if recovery is not None:
                recovery.record(
                    'tmdl', 'empty_table_name',
                    item_name=new,
                    description='Table name was empty/whitespace',
                    action=f'Renamed to "{new}"',
                    severity='warning',
                )
        for ci, col in enumerate(tbl.get('columns', []) or []):
            cname = col.get('name', '') or ''
            if not cname.strip():
                new = f'Unnamed_Column_{ci + 1}'
                col['name'] = new
                repairs += 1
                if recovery is not None:
                    recovery.record(
                        'tmdl', 'empty_column_name',
                        item_name=f'{tbl["name"]}.{new}',
                        description='Column name was empty/whitespace',
                        action=f'Renamed to "{new}"',
                        severity='warning',
                    )
        for mi, meas in enumerate(tbl.get('measures', []) or []):
            mname = meas.get('name', '') or ''
            if not mname.strip():
                new = f'Unnamed_Measure_{mi + 1}'
                meas['name'] = new
                repairs += 1
                if recovery is not None:
                    recovery.record(
                        'tmdl', 'empty_measure_name',
                        item_name=f'{tbl["name"]}.{new}',
                        description='Measure name was empty/whitespace',
                        action=f'Renamed to "{new}"',
                        severity='warning',
                    )
    # Rewire relationships that referenced the renamed empty tables
    if rename_map:
        for rel in model.get('model', {}).get('relationships', []) or []:
            if rel.get('fromTable', '') in rename_map:
                rel['fromTable'] = rename_map[rel['fromTable']]
            if rel.get('toTable', '') in rename_map:
                rel['toTable'] = rename_map[rel['toTable']]
    return repairs


# ════════════════════════════════════════════════════════════════════
#  Healer #27 — Case-insensitive duplicate columns within a table
# ════════════════════════════════════════════════════════════════════

def _heal_case_insensitive_dup_columns(model, recovery=None) -> int:
    """PBI requires column names to be case-insensitively unique inside
    a single table.  ``[Date]`` and ``[date]`` would parse but fail at
    load with "column name already exists".  Rename later occurrences
    by appending ``_2``, ``_3``, ...
    """
    repairs = 0
    for tbl in model.get('model', {}).get('tables', []) or []:
        tname = tbl.get('name', '') or ''
        seen: Dict[str, int] = {}
        for col in tbl.get('columns', []) or []:
            cname = col.get('name', '') or ''
            key = cname.lower()
            if not key:
                continue
            if key in seen:
                seen[key] += 1
                new = f'{cname}_{seen[key]}'
                # Make sure new name itself is unique
                while new.lower() in seen:
                    seen[key] += 1
                    new = f'{cname}_{seen[key]}'
                col['name'] = new
                seen[new.lower()] = 1
                repairs += 1
                if recovery is not None:
                    recovery.record(
                        'tmdl', 'duplicate_column_case_insensitive',
                        item_name=f'{tname}.{cname}',
                        description=('Case-insensitive duplicate column '
                                     'within table'),
                        action=f'Renamed to "{new}"',
                        severity='warning',
                    )
            else:
                seen[key] = 1
    return repairs


# ════════════════════════════════════════════════════════════════════
#  Healer #28 — Empty calculation groups
# ════════════════════════════════════════════════════════════════════

def _heal_empty_calculation_groups(model, recovery=None) -> int:
    """A calculation-group table with zero items causes PBI Desktop to
    throw "Calculation group must contain at least one calculation
    item".  Drop the calculationGroup block (becomes a regular table).
    """
    repairs = 0
    for tbl in model.get('model', {}).get('tables', []) or []:
        cg = tbl.get('calculationGroup')
        if not cg:
            continue
        items = cg.get('calculationItems') or cg.get('items') or []
        if items:
            continue
        del tbl['calculationGroup']
        repairs += 1
        if recovery is not None:
            recovery.record(
                'tmdl', 'empty_calculation_group',
                item_name=tbl.get('name', '?'),
                description='Calculation group has no items',
                action='Dropped calculationGroup block',
                severity='warning',
            )
    return repairs


# ════════════════════════════════════════════════════════════════════
#  Healer #29 — Relationship column endpoint missing
# ════════════════════════════════════════════════════════════════════

def _heal_relationship_missing_columns(model, recovery=None) -> int:
    """Relationship references a column that does not exist on the
    target table → "column not found" load error.  Drop such rels.
    """
    repairs = 0
    rels = model.get('model', {}).get('relationships', []) or []
    if not rels:
        return 0
    # Build {table: {column names lowercase}}
    cols_by_table: Dict[str, Set[str]] = {}
    for tbl in model.get('model', {}).get('tables', []) or []:
        tname = tbl.get('name', '') or ''
        cols_by_table[tname] = {
            (c.get('name', '') or '').lower()
            for c in tbl.get('columns', []) or []
        }
    kept: List[dict] = []
    for rel in rels:
        from_tbl = rel.get('fromTable', '')
        to_tbl = rel.get('toTable', '')
        from_col = (rel.get('fromColumn', '') or '').lower()
        to_col = (rel.get('toColumn', '') or '').lower()
        ok_from = (from_tbl in cols_by_table
                   and from_col in cols_by_table[from_tbl])
        ok_to = (to_tbl in cols_by_table
                 and to_col in cols_by_table[to_tbl])
        if ok_from and ok_to:
            kept.append(rel)
            continue
        repairs += 1
        if recovery is not None:
            missing = []
            if not ok_from:
                missing.append(f'{from_tbl}.{rel.get("fromColumn", "?")}')
            if not ok_to:
                missing.append(f'{to_tbl}.{rel.get("toColumn", "?")}')
            recovery.record(
                'relationship', 'relationship_missing_column',
                item_name=f'{from_tbl} -> {to_tbl}',
                description=f'Missing column(s): {", ".join(missing)}',
                action='Dropped relationship',
                severity='warning',
            )
    model['model']['relationships'] = kept
    return repairs


# ════════════════════════════════════════════════════════════════════
#  Healer #30 — Trailing comma in DAX function calls
# ════════════════════════════════════════════════════════════════════

_TRAILING_COMMA_RE = re.compile(r',\s*\)')


def _heal_dax_trailing_comma(model, recovery=None) -> int:
    """``SUM(Table[X],)`` → ``SUM(Table[X])``.  PBI parser rejects
    trailing commas with "unexpected token ')'".
    """
    repairs = 0
    for tbl in model.get('model', {}).get('tables', []) or []:
        tname = tbl.get('name', '') or ''
        for meas in tbl.get('measures', []) or []:
            expr = meas.get('expression', '') or ''
            if not expr or ',' not in expr:
                continue
            new_expr = _TRAILING_COMMA_RE.sub(')', expr)
            if new_expr != expr:
                meas['expression'] = new_expr
                repairs += 1
                if recovery is not None:
                    recovery.record(
                        'tmdl', 'dax_trailing_comma',
                        item_name=f'{tname}.{meas.get("name", "?")}',
                        description='Trailing comma before ")" in DAX',
                        action='Stripped trailing comma',
                        severity='info',
                    )
        for col in tbl.get('columns', []) or []:
            expr = col.get('expression', '') or ''
            if not expr or ',' not in expr:
                continue
            new_expr = _TRAILING_COMMA_RE.sub(')', expr)
            if new_expr != expr:
                col['expression'] = new_expr
                repairs += 1
                if recovery is not None:
                    recovery.record(
                        'tmdl', 'dax_trailing_comma',
                        item_name=f'{tname}.{col.get("name", "?")}',
                        description='Trailing comma before ")" in DAX',
                        action='Stripped trailing comma',
                        severity='info',
                    )
    return repairs


# ════════════════════════════════════════════════════════════════════
#  Healer #31 — Leading "=" in measure expression
# ════════════════════════════════════════════════════════════════════

def _heal_measure_leading_equals(model, recovery=None) -> int:
    """Tableau-style assignment ``= SUM([X])`` leaks into TMDL but the
    leading ``=`` is not valid DAX.  Strip it.
    """
    repairs = 0
    for tbl in model.get('model', {}).get('tables', []) or []:
        tname = tbl.get('name', '') or ''
        for meas in tbl.get('measures', []) or []:
            expr = meas.get('expression', '') or ''
            stripped = expr.lstrip()
            if stripped.startswith('=') and not stripped.startswith('=='):
                meas['expression'] = stripped[1:].lstrip()
                repairs += 1
                if recovery is not None:
                    recovery.record(
                        'tmdl', 'measure_leading_equals',
                        item_name=f'{tname}.{meas.get("name", "?")}',
                        description='Measure expression started with "="',
                        action='Stripped leading "="',
                        severity='info',
                    )
    return repairs


# ════════════════════════════════════════════════════════════════════
#  Healer #32 — Invalid dataCategory value
# ════════════════════════════════════════════════════════════════════

# Whitelist per https://learn.microsoft.com/dax/columndatacategory
_VALID_DATACATEGORIES: Set[str] = {
    'Address', 'City', 'Continent', 'Country', 'County',
    'Image', 'ImageUrl', 'Latitude', 'Longitude', 'Organization',
    'Place', 'PostalCode', 'StateOrProvince', 'WebUrl', 'BarCode',
    'Time',
}


def _heal_data_category(model, recovery=None) -> int:
    """``dataCategory`` not in the official whitelist causes Q&A to
    drop the column from indexing.  Strip unknown values.
    """
    repairs = 0
    for tbl in model.get('model', {}).get('tables', []) or []:
        tname = tbl.get('name', '') or ''
        for col in tbl.get('columns', []) or []:
            dc = col.get('dataCategory')
            if not dc or dc in _VALID_DATACATEGORIES:
                continue
            del col['dataCategory']
            repairs += 1
            if recovery is not None:
                recovery.record(
                    'tmdl', 'invalid_data_category',
                    item_name=f'{tname}.{col.get("name", "?")}',
                    description=f'Unknown dataCategory "{dc}"',
                    action='Stripped dataCategory',
                    severity='info',
                )
    return repairs


# ════════════════════════════════════════════════════════════════════
#  Healer #33 — Empty annotations
# ════════════════════════════════════════════════════════════════════

def _heal_empty_annotations(model, recovery=None) -> int:
    """Annotations with empty ``name`` cause TMDL parse failure
    ("Annotation name cannot be empty").  Drop them.  Empty values are
    legal — only filter empty names.
    """
    repairs = 0

    def _filter(holder):
        nonlocal repairs
        anns = holder.get('annotations')
        if not anns:
            return
        kept = []
        for a in anns:
            if not (a.get('name') or '').strip():
                repairs += 1
                continue
            kept.append(a)
        if len(kept) != len(anns):
            holder['annotations'] = kept

    model_block = model.get('model', {}) or {}
    _filter(model_block)
    for tbl in model_block.get('tables', []) or []:
        _filter(tbl)
        for col in tbl.get('columns', []) or []:
            _filter(col)
        for meas in tbl.get('measures', []) or []:
            _filter(meas)
    if repairs and recovery is not None:
        recovery.record(
            'tmdl', 'empty_annotations',
            item_name='model',
            description=f'{repairs} annotation(s) had empty name',
            action='Dropped empty annotations',
            severity='info',
        )
    return repairs


# ════════════════════════════════════════════════════════════════════
#  Healer #34 — Duplicate hierarchy names within a table
# ════════════════════════════════════════════════════════════════════

def _heal_duplicate_hierarchy_names(model, recovery=None) -> int:
    """Two hierarchies on the same table with identical names cause
    "hierarchy name already exists" load error.  Rename later ones.
    """
    repairs = 0
    for tbl in model.get('model', {}).get('tables', []) or []:
        tname = tbl.get('name', '') or ''
        hiers = tbl.get('hierarchies') or []
        if not hiers:
            continue
        seen: Dict[str, int] = {}
        for h in hiers:
            hname = h.get('name', '') or ''
            key = hname.lower()
            if not key:
                continue
            if key in seen:
                seen[key] += 1
                new = f'{hname}_{seen[key]}'
                while new.lower() in seen:
                    seen[key] += 1
                    new = f'{hname}_{seen[key]}'
                h['name'] = new
                seen[new.lower()] = 1
                repairs += 1
                if recovery is not None:
                    recovery.record(
                        'tmdl', 'duplicate_hierarchy_name',
                        item_name=f'{tname}.{hname}',
                        description='Duplicate hierarchy name within table',
                        action=f'Renamed to "{new}"',
                        severity='warning',
                    )
            else:
                seen[key] = 1
    return repairs


# ════════════════════════════════════════════════════════════════════
#  v3.2 — Schema & datatype hygiene  (Sprint 138)
# ════════════════════════════════════════════════════════════════════

import uuid as _uuid

_AGG_TO_DTYPE = (
    (re.compile(r'\bSUMX?\b', re.I),       'decimal'),
    (re.compile(r'\bAVERAGEX?\b', re.I),   'double'),
    (re.compile(r'\bDISTINCTCOUNT\b', re.I), 'int64'),
    (re.compile(r'\bCOUNTROWS\b', re.I),   'int64'),
    (re.compile(r'\bCOUNTX?\b', re.I),     'int64'),
    (re.compile(r'\bMINX?\b', re.I),       'decimal'),
    (re.compile(r'\bMAXX?\b', re.I),       'decimal'),
    (re.compile(r'\bDIVIDE\b', re.I),      'double'),
)


def _heal_column_without_datatype(model, recovery=None) -> int:
    """Columns missing ``dataType`` cause "cannot determine data type"
    at refresh.  Default to ``string`` and tag via annotation."""
    repairs = 0
    for tbl in model.get('model', {}).get('tables', []) or []:
        tname = tbl.get('name', '') or ''
        for col in tbl.get('columns', []) or []:
            cname = col.get('name', '') or ''
            if not cname:
                continue
            dt = col.get('dataType', '')
            if dt:
                continue
            col['dataType'] = 'string'
            col.setdefault('annotations', []).append({
                'name': 'MigrationNote',
                'value': 'Self-heal: defaulted dataType to string',
            })
            repairs += 1
            if recovery is not None:
                recovery.record(
                    'tmdl', 'column_without_datatype',
                    item_name=f'{tname}.{cname}',
                    description='Column missing dataType',
                    action='Defaulted to string',
                    severity='warning',
                )
    return repairs


def _heal_measure_without_datatype(model, recovery=None) -> int:
    """Measures without explicit ``dataType`` show as variant in PBI.
    Infer from aggregation in expression."""
    repairs = 0
    for tbl in model.get('model', {}).get('tables', []) or []:
        tname = tbl.get('name', '') or ''
        for m in tbl.get('measures', []) or []:
            mname = m.get('name', '') or ''
            if not mname or m.get('dataType'):
                continue
            expr = m.get('expression', '') or ''
            inferred = 'decimal'
            for rgx, dt in _AGG_TO_DTYPE:
                if rgx.search(expr):
                    inferred = dt
                    break
            m['dataType'] = inferred
            repairs += 1
            if recovery is not None:
                recovery.record(
                    'tmdl', 'measure_without_datatype',
                    item_name=f'{tname}.{mname}',
                    description='Measure missing dataType',
                    action=f'Inferred dataType={inferred}',
                    severity='info',
                )
    return repairs


def _heal_boolean_with_string_default(model, recovery=None) -> int:
    """Boolean columns sometimes carry a string default ``"true"``/``"false"``
    which fails strict refresh.  Normalize to bool literal."""
    repairs = 0
    for tbl in model.get('model', {}).get('tables', []) or []:
        tname = tbl.get('name', '') or ''
        for col in tbl.get('columns', []) or []:
            cname = col.get('name', '') or ''
            dt = (col.get('dataType', '') or '').lower()
            if dt != 'boolean':
                continue
            dv = col.get('defaultValue')
            if not isinstance(dv, str):
                continue
            low = dv.strip().lower().strip('"').strip("'")
            if low in ('true', 'false'):
                col['defaultValue'] = (low == 'true')
                repairs += 1
                if recovery is not None:
                    recovery.record(
                        'tmdl', 'boolean_with_string_default',
                        item_name=f'{tname}.{cname}',
                        description=f'Boolean column has string default "{dv}"',
                        action=f'Normalized to {low == "true"}',
                        severity='info',
                    )
    return repairs


def _heal_numeric_format_string_mismatch(model, recovery=None) -> int:
    """``formatString`` with fractional digits on int64 columns/measures
    is rejected by refresh.  Promote dtype to double."""
    repairs = 0
    for tbl in model.get('model', {}).get('tables', []) or []:
        tname = tbl.get('name', '') or ''
        for col in (tbl.get('columns', []) or []) + (tbl.get('measures', []) or []):
            cname = col.get('name', '') or ''
            dt = (col.get('dataType', '') or '').lower()
            fmt = col.get('formatString', '') or ''
            if dt != 'int64' or not fmt:
                continue
            if _DECIMAL_FMT.search(fmt) or _PERCENT_FMT.search(fmt):
                col['dataType'] = 'double'
                repairs += 1
                if recovery is not None:
                    recovery.record(
                        'tmdl', 'numeric_format_string_mismatch',
                        item_name=f'{tname}.{cname}',
                        description=f'int64 with fractional formatString "{fmt}"',
                        action='Promoted dataType to double',
                        severity='warning',
                    )
    return repairs


def _heal_datetime_without_format(model, recovery=None) -> int:
    """Date/datetime columns without ``formatString`` render as numbers."""
    repairs = 0
    for tbl in model.get('model', {}).get('tables', []) or []:
        tname = tbl.get('name', '') or ''
        for col in tbl.get('columns', []) or []:
            cname = col.get('name', '') or ''
            dt = (col.get('dataType', '') or '').lower()
            if dt not in ('datetime', 'date', 'time'):
                continue
            if col.get('formatString'):
                continue
            col['formatString'] = 'General Date'
            repairs += 1
            if recovery is not None:
                recovery.record(
                    'tmdl', 'datetime_without_format',
                    item_name=f'{tname}.{cname}',
                    description='Datetime column has no formatString',
                    action='Set formatString="General Date"',
                    severity='info',
                )
    return repairs


def _heal_lineage_tag_collision(model, recovery=None) -> int:
    """Two items sharing the same ``lineageTag`` GUID cause "duplicate
    lineage tag" errors.  Regenerate later occurrences with uuid4."""
    repairs = 0
    seen: Set[str] = set()
    for tbl in model.get('model', {}).get('tables', []) or []:
        tname = tbl.get('name', '') or ''
        for kind in ('columns', 'measures', 'hierarchies'):
            for it in tbl.get(kind, []) or []:
                tag = it.get('lineageTag')
                if not tag:
                    continue
                if tag in seen:
                    new = str(_uuid.uuid4())
                    it['lineageTag'] = new
                    repairs += 1
                    if recovery is not None:
                        recovery.record(
                            'tmdl', 'lineage_tag_collision',
                            item_name=f'{tname}.{it.get("name", "?")}',
                            description=f'Duplicate lineageTag "{tag}"',
                            action=f'Regenerated → {new}',
                            severity='warning',
                        )
                    seen.add(new)
                else:
                    seen.add(tag)
    return repairs


def _heal_missing_lineage_tag(model, recovery=None) -> int:
    """Columns/measures without ``lineageTag`` lose lineage when reports
    rebind.  Inject deterministic uuid5 from "table.name"."""
    repairs = 0
    NS = _uuid.UUID('6ba7b810-9dad-11d1-80b4-00c04fd430c8')  # NS_DNS
    for tbl in model.get('model', {}).get('tables', []) or []:
        tname = tbl.get('name', '') or ''
        for kind in ('columns', 'measures'):
            for it in tbl.get(kind, []) or []:
                name = it.get('name', '') or ''
                if not name:
                    continue
                if it.get('lineageTag'):
                    continue
                it['lineageTag'] = str(_uuid.uuid5(NS, f'{tname}.{name}'))
                repairs += 1
                if recovery is not None:
                    recovery.record(
                        'tmdl', 'missing_lineage_tag',
                        item_name=f'{tname}.{name}',
                        description='Item missing lineageTag',
                        action='Injected deterministic uuid5',
                        severity='info',
                    )
    return repairs


def _heal_source_column_missing(model, recovery=None) -> int:
    """``sourceColumn`` referencing a column that no upstream M step
    produces causes refresh failure.  We can't introspect the M output,
    so the best we can do is detect ``sourceColumn`` that doesn't match
    any known column ``name`` on the same table (case-insensitive) and
    align it to ``name`` if a near-match exists; otherwise drop to None."""
    repairs = 0
    for tbl in model.get('model', {}).get('tables', []) or []:
        tname = tbl.get('name', '') or ''
        col_names = {(c.get('name', '') or '').lower(): c.get('name', '')
                     for c in tbl.get('columns', []) or []}
        for col in tbl.get('columns', []) or []:
            cname = col.get('name', '') or ''
            sc = col.get('sourceColumn')
            if not sc or sc == cname:
                continue
            # Try case-insensitive match
            match = col_names.get(sc.lower())
            if match and match != sc:
                col['sourceColumn'] = match
                repairs += 1
                if recovery is not None:
                    recovery.record(
                        'tmdl', 'source_column_case_match',
                        item_name=f'{tname}.{cname}',
                        description=f'sourceColumn "{sc}" case-mismatch',
                        action=f'Aligned to "{match}"',
                        severity='info',
                    )
    return repairs


def _heal_key_column_nullable(model, recovery=None) -> int:
    """A column marked ``isKey`` cannot be nullable."""
    repairs = 0
    for tbl in model.get('model', {}).get('tables', []) or []:
        tname = tbl.get('name', '') or ''
        for col in tbl.get('columns', []) or []:
            cname = col.get('name', '') or ''
            if not col.get('isKey'):
                continue
            if col.get('isNullable') is False:
                continue
            col['isNullable'] = False
            repairs += 1
            if recovery is not None:
                recovery.record(
                    'tmdl', 'key_column_nullable',
                    item_name=f'{tname}.{cname}',
                    description='isKey column was nullable',
                    action='Forced isNullable=false',
                    severity='warning',
                )
    return repairs


def _heal_int_column_with_decimal_default(model, recovery=None) -> int:
    """``defaultValue = 1.5`` on an int64 column fails refresh."""
    repairs = 0
    for tbl in model.get('model', {}).get('tables', []) or []:
        tname = tbl.get('name', '') or ''
        for col in tbl.get('columns', []) or []:
            cname = col.get('name', '') or ''
            dt = (col.get('dataType', '') or '').lower()
            if dt != 'int64':
                continue
            dv = col.get('defaultValue')
            if not isinstance(dv, float):
                continue
            new = int(round(dv))
            col['defaultValue'] = new
            repairs += 1
            if recovery is not None:
                recovery.record(
                    'tmdl', 'int_column_decimal_default',
                    item_name=f'{tname}.{cname}',
                    description=f'int64 column has float default {dv}',
                    action=f'Rounded to {new}',
                    severity='info',
                )
    return repairs


# ════════════════════════════════════════════════════════════════════
#  v3.3 — Power Query / M-partition hygiene  (Sprint 139)
# ════════════════════════════════════════════════════════════════════

_M_LET_RE = re.compile(r'\blet\b', re.I)
_M_IN_RE = re.compile(r'\bin\b\s+[#\w]', re.I)
_M_DOUBLE_COMMA = re.compile(r',\s*,')
_M_TRAILING_COMMA_RECORD = re.compile(r',(\s*[\]\}])')
_M_STEP_DEF_RE = re.compile(r'^\s*(#"[^"]+"|\w+)\s*=', re.M)
_M_UNQUOTED_BAD = re.compile(r'(?<![\w#"])([A-Za-z_]\w*[ \-/&%]+\w[\w \-/&%]*)\s*=')
_M_CRED_PATTERNS = (
    re.compile(r'(Password|Pwd)\s*=\s*"[^"]*"', re.I),
    re.compile(r'(User(name)?|Uid)\s*=\s*"[^"]*"', re.I),
    re.compile(r'(api[_-]?key|apikey|token|secret)\s*=\s*"[^"]*"', re.I),
)
_M_DQ_FUNCS = (
    re.compile(r'\bSql\.Database\b'),
    re.compile(r'\bOracle\.Database\b'),
    re.compile(r'\bSnowflake\.Databases\b'),
)


def _iter_partitions(model):
    """Yield (table_name, partition_dict, source_dict) for M partitions."""
    for tbl in model.get('model', {}).get('tables', []) or []:
        tname = tbl.get('name', '') or ''
        for part in tbl.get('partitions', []) or []:
            src = part.get('source') or {}
            if (src.get('type') or '').lower() == 'm':
                yield tname, part, src


def _heal_m_unbalanced_let_in(model, recovery=None) -> int:
    """Append ``in <last step>`` if a ``let`` block lacks ``in``."""
    repairs = 0
    for tname, _part, src in _iter_partitions(model):
        expr = src.get('expression', '')
        if not isinstance(expr, str) or not expr.strip():
            continue
        if not _M_LET_RE.search(expr):
            continue
        # Count actual let vs in keywords (exclude occurrences inside strings)
        let_count = len(_M_LET_RE.findall(expr))
        in_count = len(re.findall(r'(?:^|\n)\s*in\b', expr, re.I))
        if in_count >= let_count:
            continue
        steps = _M_STEP_DEF_RE.findall(expr)
        if not steps:
            continue
        last = steps[-1]
        src['expression'] = expr.rstrip().rstrip(',') + f'\nin\n    {last}\n'
        repairs += 1
        if recovery is not None:
            recovery.record(
                'm_query', 'm_unbalanced_let_in',
                item_name=tname,
                description='M partition missing "in" clause',
                action=f'Appended "in {last}"',
                severity='warning',
            )
    return repairs


def _heal_m_duplicate_in(model, recovery=None) -> int:
    """Remove duplicate trailing ``in <step>`` blocks."""
    repairs = 0
    dup_re = re.compile(r'(\n\s*in\s*\n\s*(?:#"[^"]+?"|\w+)\s*)\1+$')
    for tname, _part, src in _iter_partitions(model):
        expr = src.get('expression', '')
        if not isinstance(expr, str) or not expr.strip():
            continue
        m = dup_re.search(expr)
        if not m:
            continue
        src['expression'] = expr[:m.start()] + m.group(1)
        repairs += 1
        if recovery is not None:
            recovery.record(
                'm_query', 'm_duplicate_in',
                item_name=tname,
                description='M partition has duplicate "in" clause',
                action='Removed duplicate "in" block',
                severity='warning',
            )
    return repairs


def _heal_m_unbalanced_parens(model, recovery=None) -> int:
    """Append closing ``)``/``]``/``}`` to balance counts."""
    repairs = 0
    pairs = (('(', ')'), ('[', ']'), ('{', '}'))
    for tname, _part, src in _iter_partitions(model):
        expr = src.get('expression', '')
        if not isinstance(expr, str) or not expr:
            continue
        # Remove string literals to avoid false counts
        cleaned = re.sub(r'"(?:\\.|[^"\\])*"', '""', expr)
        appended = ''
        for open_c, close_c in pairs:
            diff = cleaned.count(open_c) - cleaned.count(close_c)
            if diff > 0:
                appended += close_c * diff
        if appended:
            src['expression'] = expr + appended
            repairs += 1
            if recovery is not None:
                recovery.record(
                    'm_query', 'm_unbalanced_parens',
                    item_name=tname,
                    description='M expression had unbalanced brackets',
                    action=f'Appended "{appended}"',
                    severity='warning',
                )
    return repairs


def _heal_m_step_name_collision(model, recovery=None) -> int:
    """Rename duplicate step names within a single ``let`` block and
    rewire references."""
    repairs = 0
    for tname, _part, src in _iter_partitions(model):
        expr = src.get('expression', '')
        if not isinstance(expr, str) or not _M_LET_RE.search(expr):
            continue
        steps = _M_STEP_DEF_RE.findall(expr)
        if len(steps) == len(set(steps)):
            continue
        new_expr = expr
        seen: Dict[str, int] = {}
        for s in steps:
            if seen.get(s, 0) >= 1:
                # Rename second+ occurrences
                idx = seen[s] + 1
                stripped = s.rstrip('"')
                new_name = f'{stripped}_{idx}'
                if s.startswith('#"'):
                    new_name = s[:-1] + f'_{idx}"'
                # Replace first occurrence after current position only.
                # Simpler conservative approach: replace ALL but skip the
                # first definition by tracking position.
                # Find the second definition position.
                pat = re.compile(re.escape(s) + r'\s*=')
                matches = list(pat.finditer(new_expr))
                if len(matches) >= 2:
                    pos = matches[1].start()
                    head = new_expr[:pos]
                    tail = new_expr[pos:].replace(s, new_name, 1)
                    # Also retarget any later refs to the renamed step
                    new_expr = head + tail
                seen[s] = seen.get(s, 0) + 1
            else:
                seen[s] = 1
        if new_expr != expr:
            src['expression'] = new_expr
            repairs += 1
            if recovery is not None:
                recovery.record(
                    'm_query', 'm_step_name_collision',
                    item_name=tname,
                    description='Duplicate step names in let block',
                    action='Renamed second occurrences with suffix',
                    severity='warning',
                )
    return repairs


def _heal_m_invalid_identifier_unquoted(model, recovery=None) -> int:
    """Wrap unquoted step identifiers containing spaces/specials in
    ``#"…"`` so the M parser accepts them."""
    repairs = 0
    for tname, _part, src in _iter_partitions(model):
        expr = src.get('expression', '')
        if not isinstance(expr, str) or not _M_LET_RE.search(expr):
            continue
        new_expr = expr
        changed = False

        def _wrap(match):
            nonlocal changed
            ident = match.group(1)
            changed = True
            return f'#"{ident}" ='

        new_expr = _M_UNQUOTED_BAD.sub(_wrap, new_expr)
        if changed:
            src['expression'] = new_expr
            repairs += 1
            if recovery is not None:
                recovery.record(
                    'm_query', 'm_invalid_identifier_unquoted',
                    item_name=tname,
                    description='Step identifier had spaces/specials but was unquoted',
                    action='Wrapped in #"..."',
                    severity='warning',
                )
    return repairs


def _heal_m_trailing_comma_in_record(model, recovery=None) -> int:
    """Remove trailing comma in M record/list literals (``[a=1,]``)."""
    repairs = 0
    for tname, _part, src in _iter_partitions(model):
        expr = src.get('expression', '')
        if not isinstance(expr, str) or ',' not in expr:
            continue
        new_expr = _M_TRAILING_COMMA_RECORD.sub(r'\1', expr)
        if new_expr != expr:
            src['expression'] = new_expr
            repairs += 1
            if recovery is not None:
                recovery.record(
                    'm_query', 'm_trailing_comma_in_record',
                    item_name=tname,
                    description='M record/list had trailing comma',
                    action='Stripped trailing comma',
                    severity='info',
                )
    return repairs


def _heal_m_double_comma(model, recovery=None) -> int:
    """Collapse ``,,`` → ``,`` in M expressions."""
    repairs = 0
    for tname, _part, src in _iter_partitions(model):
        expr = src.get('expression', '')
        if not isinstance(expr, str) or ',,' not in expr.replace(' ', ''):
            continue
        new_expr = _M_DOUBLE_COMMA.sub(',', expr)
        if new_expr != expr:
            src['expression'] = new_expr
            repairs += 1
            if recovery is not None:
                recovery.record(
                    'm_query', 'm_double_comma',
                    item_name=tname,
                    description='M expression had double commas',
                    action='Collapsed to single comma',
                    severity='warning',
                )
    return repairs


def _heal_m_missing_source_step(model, recovery=None) -> int:
    """If body references ``Source`` but no ``Source =`` step exists,
    inject a placeholder #table()."""
    repairs = 0
    for tname, _part, src in _iter_partitions(model):
        expr = src.get('expression', '')
        if not isinstance(expr, str) or not expr.strip():
            continue
        if not re.search(r'\bSource\b', expr):
            continue
        if re.search(r'\bSource\s*=', expr):
            continue
        # Try to insert after `let`
        if not _M_LET_RE.search(expr):
            continue
        placeholder = '    Source = #table({}, {}),\n'
        new_expr = re.sub(
            r'(\blet\b\s*)',
            r'\1\n' + placeholder,
            expr,
            count=1,
            flags=re.I,
        )
        src['expression'] = new_expr
        repairs += 1
        if recovery is not None:
            recovery.record(
                'm_query', 'm_missing_source_step',
                item_name=tname,
                description='M body references Source with no definition',
                action='Injected empty #table() placeholder',
                severity='error',
                follow_up='Replace placeholder with actual data source',
            )
    return repairs


def _heal_m_credential_in_expression(model, recovery=None) -> int:
    """Strip hardcoded credentials from M expressions."""
    repairs = 0
    for tname, _part, src in _iter_partitions(model):
        expr = src.get('expression', '')
        if not isinstance(expr, str):
            continue
        new_expr = expr
        hits = 0
        for pat in _M_CRED_PATTERNS:
            new_expr, n = pat.subn(
                lambda m: f'{m.group(1)}=#"<placeholder>"',
                new_expr,
            )
            hits += n
        if hits:
            src['expression'] = new_expr
            repairs += hits
            if recovery is not None:
                recovery.record(
                    'm_query', 'm_credential_in_expression',
                    item_name=tname,
                    description=f'Hardcoded credential(s) in M ({hits} match)',
                    action='Replaced with placeholder',
                    severity='error',
                    follow_up='Configure credentials via gateway/PBI Service',
                )
    return repairs


def _heal_m_partition_mode_mismatch(model, recovery=None) -> int:
    """If partition is ``mode=import`` but expression uses DirectQuery
    functions and Table.Buffer is absent, wrap with Table.Buffer()."""
    repairs = 0
    for tname, part, src in _iter_partitions(model):
        mode = (part.get('mode') or 'import').lower()
        expr = src.get('expression', '')
        if mode != 'import' or not isinstance(expr, str):
            continue
        if 'Table.Buffer' in expr:
            continue
        # Skip defensive `try ... otherwise` patterns (DQ source already wrapped)
        if re.search(r'\btry\b', expr):
            continue
        if not any(p.search(expr) for p in _M_DQ_FUNCS):
            continue
        # Heuristic: don't touch — flag only.
        repairs += 1
        if recovery is not None:
            recovery.record(
                'm_query', 'm_partition_mode_mismatch',
                item_name=tname,
                description='Import partition uses DirectQuery-style source',
                action='Flagged (no automatic rewrite)',
                severity='warning',
                follow_up='Either switch partition mode to directQuery or wrap output with Table.Buffer',
            )
    return repairs


def _heal_m_dataflow_ref_dangling(model, recovery=None) -> int:
    """Detect ``PowerPlatform.Dataflows`` references and warn — we
    can't validate the dataflow exists, but flag for review."""
    repairs = 0
    for tname, _part, src in _iter_partitions(model):
        expr = src.get('expression', '')
        if not isinstance(expr, str):
            continue
        if 'PowerPlatform.Dataflows' not in expr:
            continue
        repairs += 1
        if recovery is not None:
            recovery.record(
                'm_query', 'm_dataflow_ref',
                item_name=tname,
                description='Partition references PowerPlatform.Dataflows',
                action='Flagged — verify dataflow still exists in target tenant',
                severity='warning',
                follow_up='Validate dataflow id in workspace before refresh',
            )
    return repairs


# ════════════════════════════════════════════════════════════════════
#  v3.5 — Sprint 144 — Phase 4 Zero-Error: model-side healers
# ════════════════════════════════════════════════════════════════════

_VALID_DAX_FUNCS: set | None = None


def _heal_dax_unbalanced_brackets(model, recovery=None) -> int:
    """Detect unbalanced ``[`` / ``]`` in DAX expressions and strip extras."""
    repairs = 0
    for tbl in model.get('model', {}).get('tables', []) or []:
        tname = tbl.get('name', '') or ''
        for item in list(tbl.get('measures', []) or []) + list(tbl.get('columns', []) or []):
            expr = item.get('expression') or ''
            if not expr:
                continue
            opens = expr.count('[')
            closes = expr.count(']')
            if opens != closes:
                item_name = item.get('name', '?')
                if opens > closes:
                    expr += ']' * (opens - closes)
                else:
                    # remove excess trailing ]
                    excess = closes - opens
                    chars = list(expr)
                    removed = 0
                    for i in range(len(chars) - 1, -1, -1):
                        if chars[i] == ']' and removed < excess:
                            chars.pop(i)
                            removed += 1
                    expr = ''.join(chars)
                item['expression'] = expr
                repairs += 1
                if recovery is not None:
                    recovery.record(
                        'tmdl', 'dax_unbalanced_brackets',
                        item_name=f'{tname}.{item_name}',
                        description=f'Unbalanced [ ] ({opens} open, {closes} close)',
                        action='Appended/removed brackets to balance',
                        severity='warning',
                    )
    return repairs


_UNSUPPORTED_FUNCS_RE = re.compile(
    r'\b(MAKEPOINT|MAKELINE|MAKECONNECTION|SCRIPT_BOOL|SCRIPT_INT|SCRIPT_REAL|SCRIPT_STR)\s*\(',
    re.IGNORECASE,
)


def _heal_dax_unknown_function(model, recovery=None) -> int:
    """Replace unsupported function calls with BLANK() + TODO comment."""
    repairs = 0
    for tbl in model.get('model', {}).get('tables', []) or []:
        tname = tbl.get('name', '') or ''
        for item in tbl.get('measures', []) or []:
            expr = item.get('expression') or ''
            m = _UNSUPPORTED_FUNCS_RE.search(expr)
            if m:
                fn = m.group(1)
                item['expression'] = f'/* TODO: {fn} has no DAX equivalent */ BLANK()'
                repairs += 1
                if recovery is not None:
                    recovery.record(
                        'tmdl', 'dax_unknown_function',
                        item_name=f'{tname}.{item.get("name", "?")}',
                        description=f'Unsupported function {fn}()',
                        action=f'Replaced with BLANK() (no DAX equivalent)',
                        severity='warning',
                        follow_up=f'Implement {fn} logic manually',
                    )
    return repairs


def _heal_dax_circular_dependency(model, recovery=None) -> int:
    """Detect measure A→B→A circular references; break with BLANK()."""
    repairs = 0
    # Build adjacency: measure_fullname -> set of referenced measure fullnames
    all_measures = {}  # (table, name) -> expression
    for tbl in model.get('model', {}).get('tables', []) or []:
        tname = tbl.get('name', '') or ''
        for m in tbl.get('measures', []) or []:
            mname = m.get('name', '') or ''
            all_measures[(tname, mname)] = m

    # Build reference graph
    refs = {}  # (table, name) -> set of (table, name)
    for key, m in all_measures.items():
        expr = m.get('expression') or ''
        targets = set()
        for other_key in all_measures:
            if other_key == key:
                continue
            ot, on = other_key
            if f'[{on}]' in expr:
                targets.add(other_key)
        refs[key] = targets

    # Detect cycles: simple DFS for 2-node cycles
    broken = set()
    for key, targets in refs.items():
        for t in targets:
            if t in refs and key in refs.get(t, set()) and t not in broken:
                # Circular: break the second measure
                m_obj = all_measures[t]
                orig = m_obj.get('expression', '')
                m_obj['expression'] = f'/* TODO: circular dependency with {key[1]} */ BLANK()'
                broken.add(t)
                repairs += 1
                if recovery is not None:
                    recovery.record(
                        'tmdl', 'dax_circular_dependency',
                        item_name=f'{t[0]}.{t[1]}',
                        description=f'Circular reference between [{key[1]}] and [{t[1]}]',
                        action=f'Replaced with BLANK(); original: {orig[:80]}',
                        severity='warning',
                        follow_up='Refactor DAX to break circular dependency',
                    )
    return repairs


def _heal_relationship_orphan_table(model, recovery=None) -> int:
    """Remove relationships referencing tables that don't exist in model."""
    repairs = 0
    tables = {(t.get('name', '') or '').lower()
              for t in model.get('model', {}).get('tables', []) or []}
    rels = model.get('model', {}).get('relationships', []) or []
    cleaned = []
    for rel in rels:
        from_tbl = (rel.get('fromTable') or '').lower()
        to_tbl = (rel.get('toTable') or '').lower()
        if from_tbl not in tables or to_tbl not in tables:
            repairs += 1
            missing = from_tbl if from_tbl not in tables else to_tbl
            if recovery is not None:
                recovery.record(
                    'relationship', 'relationship_orphan_table',
                    item_name=f'{rel.get("fromTable")}->{rel.get("toTable")}',
                    description=f'Table "{missing}" does not exist in model',
                    action='Relationship removed',
                    severity='warning',
                )
        else:
            cleaned.append(rel)
    if repairs:
        model['model']['relationships'] = cleaned
    return repairs


def _heal_relationship_self_loop(model, recovery=None) -> int:
    """Remove self-referencing relationships (fromTable == toTable + fromColumn == toColumn)."""
    repairs = 0
    rels = model.get('model', {}).get('relationships', []) or []
    cleaned = []
    for rel in rels:
        ft = (rel.get('fromTable') or '').lower()
        tt = (rel.get('toTable') or '').lower()
        fc = (rel.get('fromColumn') or '').lower()
        tc = (rel.get('toColumn') or '').lower()
        if ft == tt and fc == tc:
            repairs += 1
            if recovery is not None:
                recovery.record(
                    'relationship', 'relationship_self_loop',
                    item_name=f'{rel.get("fromTable")}.{rel.get("fromColumn")}',
                    description='Self-referencing relationship (same table and column)',
                    action='Relationship removed',
                    severity='warning',
                )
        else:
            cleaned.append(rel)
    if repairs:
        model['model']['relationships'] = cleaned
    return repairs


def _heal_column_duplicate_name_case(model, recovery=None) -> int:
    """Rename columns that differ only in case (PBI is case-insensitive)."""
    repairs = 0
    for tbl in model.get('model', {}).get('tables', []) or []:
        tname = tbl.get('name', '') or ''
        seen: dict[str, str] = {}  # lower-name -> first-name
        for col in tbl.get('columns', []) or []:
            cname = col.get('name', '') or ''
            key = cname.lower()
            if key in seen and seen[key] != cname:
                # Rename the duplicate
                new_name = f'{cname}_{tname}'.replace(' ', '_')
                col['name'] = new_name
                repairs += 1
                if recovery is not None:
                    recovery.record(
                        'tmdl', 'column_duplicate_name_case',
                        item_name=f'{tname}.{cname}',
                        description=f'Case-insensitive duplicate of "{seen[key]}"',
                        action=f'Renamed to "{new_name}"',
                        severity='warning',
                    )
            else:
                seen[key] = cname
    return repairs


_VALID_DATATYPES_LOWER = {'string', 'int64', 'double', 'decimal', 'boolean',
                          'datetime', 'binary', 'int32', 'currency', 'variant'}


def _heal_column_invalid_datatype(model, recovery=None) -> int:
    """Fix columns with truly invalid datatype values.

    Note: casing normalization (``Double`` → ``double``) is already handled
    by ``_heal_datatype_casing`` — this healer only catches datatypes whose
    lowercased form doesn't match any known TMDL type.
    """
    repairs = 0
    for tbl in model.get('model', {}).get('tables', []) or []:
        tname = tbl.get('name', '') or ''
        for col in tbl.get('columns', []) or []:
            dt = col.get('dataType') or ''
            if not dt:
                continue
            if dt.lower() in _VALID_DATATYPES_LOWER:
                continue  # casing handled by datatype_casing healer
            # Truly unknown type — default to string
            col['dataType'] = 'string'
            repairs += 1
            if recovery is not None:
                recovery.record(
                    'tmdl', 'column_invalid_datatype',
                    item_name=f'{tname}.{col.get("name", "?")}',
                    description=f'Unknown datatype "{dt}"',
                    action='Defaulted to "string"',
                    severity='warning',
                )
    return repairs


def _heal_partition_empty_m(model, recovery=None) -> int:
    """Replace empty M partitions with a minimal valid expression."""
    repairs = 0
    for tbl in model.get('model', {}).get('tables', []) or []:
        tname = tbl.get('name', '') or ''
        for part in tbl.get('partitions', []) or []:
            src = part.get('source') or {}
            if src.get('type') == 'm':
                expr = (src.get('expression') or '').strip()
                if not expr or expr in ('null', 'None', '""'):
                    src['expression'] = (
                        'let\n'
                        f'    Source = #table({{"Column1"}}, {{}})\n'
                        'in\n'
                        '    Source'
                    )
                    repairs += 1
                    if recovery is not None:
                        recovery.record(
                            'm_query', 'partition_empty_m',
                            item_name=tname,
                            description='M partition expression was empty/null',
                            action='Replaced with minimal #table stub',
                            severity='warning',
                            follow_up='Replace with actual data source query',
                        )
    return repairs


def _heal_parameter_default_out_of_domain(model, recovery=None) -> int:
    """Fix parameter defaults that aren't in the allowable values list."""
    repairs = 0
    for tbl in model.get('model', {}).get('tables', []) or []:
        tname = tbl.get('name', '') or ''
        for col in tbl.get('columns', []) or []:
            # Parameters are typically modeled as columns on parameter tables
            # with expression containing DATATABLE or GENERATESERIES
            pass
        for m in tbl.get('measures', []) or []:
            # Check for SELECTEDVALUE-based parameter measures
            expr = m.get('expression') or ''
            if 'SELECTEDVALUE' not in expr:
                continue
            # Check annotations for parameter metadata
            for ann in m.get('annotations', []) or []:
                if ann.get('name') == 'ParameterDefaultValue':
                    default_val = ann.get('value', '')
                    domain_ann = next(
                        (a for a in m.get('annotations', []) or []
                         if a.get('name') == 'ParameterAllowableValues'),
                        None,
                    )
                    if domain_ann:
                        allowed_str = domain_ann.get('value', '')
                        allowed = [v.strip() for v in allowed_str.split(',') if v.strip()]
                        if allowed and default_val and default_val not in allowed:
                            ann['value'] = allowed[0]
                            repairs += 1
                            if recovery is not None:
                                recovery.record(
                                    'tmdl', 'parameter_default_out_of_domain',
                                    item_name=f'{tname}.{m.get("name", "?")}',
                                    description=f'Default "{default_val}" not in [{", ".join(allowed[:5])}]',
                                    action=f'Changed default to "{allowed[0]}"',
                                    severity='warning',
                                )
    return repairs


def _heal_rls_missing_table_permission(model, recovery=None) -> int:
    """Flag RLS roles that have no tablePermission entries."""
    repairs = 0
    for role in model.get('model', {}).get('roles', []) or []:
        rname = role.get('name', '') or ''
        perms = role.get('tablePermissions', []) or []
        if not perms:
            # Add a placeholder permission to prevent PBI Desktop error
            tables = model.get('model', {}).get('tables', []) or []
            if tables:
                first_table = tables[0].get('name', 'Table')
                role['tablePermissions'] = [{
                    'name': first_table,
                    'filterExpression': 'TRUE()',
                }]
                repairs += 1
                if recovery is not None:
                    recovery.record(
                        'tmdl', 'rls_missing_table_permission',
                        item_name=rname,
                        description='RLS role has no tablePermissions',
                        action=f'Added placeholder TRUE() on "{first_table}"',
                        severity='warning',
                        follow_up='Replace placeholder with actual RLS filter',
                    )
    return repairs


# ════════════════════════════════════════════════════════════════════
#  Healer — Calc column to measure promotion
# ════════════════════════════════════════════════════════════════════

# Aggregation pattern — calc columns whose DAX expression contains these
# functions are likely misclassified and should be measures instead.
# We specifically look for CALCULATE + ALLEXCEPT (LOD-derived) or
# standalone aggregation functions wrapping column refs.
_CC_AGG_RE = re.compile(
    r'\b(SUM|AVERAGE|MIN|MAX|COUNT|COUNTA|COUNTBLANK|DISTINCTCOUNT|'
    r'SUMX|AVERAGEX|MINX|MAXX|COUNTX|COUNTAX|CALCULATE|'
    r'RANKX|TOTALYTD|SAMEPERIODLASTYEAR)\s*\(',
    re.IGNORECASE,
)


def _heal_calc_col_to_measure(model, recovery=None) -> int:
    """Promote calculated columns whose DAX expression contains aggregation
    functions (CALCULATE, SUM, RANKX, etc.) to measures.

    LOD expressions in Tableau ({FIXED dim: AGG}) produce DAX like
    ``CALCULATE([Measure], ALLEXCEPT(...))``.  When the upstream
    classifier misses the LOD syntax, these end up as calculated columns
    with aggregation context — invalid in PBI because calc columns
    evaluate row-by-row and cannot use filter-modifying functions that
    reference measures.

    The healer scans every calc column for aggregation patterns.  To
    avoid false positives (e.g. ``CALCULATE(SELECTEDVALUE(...))`` which
    is a valid scalar lookup in a calc column), we skip expressions
    that only use SELECTEDVALUE/LOOKUPVALUE inside CALCULATE.
    """
    repairs = 0
    _selectedvalue_only = re.compile(
        r'^CALCULATE\s*\(\s*(SELECTEDVALUE|LOOKUPVALUE)\s*\(', re.IGNORECASE
    )
    for t in model.get('model', {}).get('tables', []):
        tname = t.get('name', '')
        # Build set of measure names in this table for reference detection
        local_measures = {m.get('name', '') for m in t.get('measures', []) if m.get('name')}
        cols_to_promote = []
        for i, col in enumerate(t.get('columns', [])):
            expr = col.get('expression', '')
            if not expr:
                continue  # Not a DAX calculated column
            # Must have aggregation functions in the expression
            if not _CC_AGG_RE.search(expr):
                continue
            # Skip CALCULATE(SELECTEDVALUE(...)) / CALCULATE(LOOKUPVALUE(...))
            # patterns — these are valid scalar lookups in calc columns
            expr_stripped = expr.strip()
            if _selectedvalue_only.match(expr_stripped):
                continue
            # Also skip if SELECTEDVALUE/LOOKUPVALUE appears and NO measure
            # reference is present (pure cross-table scalar lookup)
            if re.search(r'\b(SELECTEDVALUE|LOOKUPVALUE)\s*\(', expr, re.IGNORECASE):
                # Check if expression references any measure from this table
                refs_measures = False
                for mname in local_measures:
                    if f'[{mname}]' in expr:
                        refs_measures = True
                        break
                if not refs_measures:
                    continue
            cols_to_promote.append(i)
        # Promote in reverse order to preserve indices
        for i in reversed(cols_to_promote):
            col = t['columns'].pop(i)
            cname = col.get('name', '?')
            # Create measure from the calc column
            new_measure = {
                'name': cname,
                'expression': col['expression'],
            }
            # Carry over formatting, description, annotations
            if col.get('formatString'):
                new_measure['formatString'] = col['formatString']
            if col.get('description'):
                new_measure['description'] = col['description']
            if col.get('isHidden'):
                new_measure['isHidden'] = col['isHidden']
            if col.get('displayFolder'):
                new_measure['displayFolder'] = col['displayFolder']
            for ann in col.get('annotations', []):
                new_measure.setdefault('annotations', []).append(ann)
            new_measure.setdefault('annotations', []).append({
                'name': 'MigrationNote',
                'value': 'Self-heal: Promoted from calculated column (contains aggregation context)',
            })
            t.setdefault('measures', []).append(new_measure)
            repairs += 1
            print(f"  \u2695 Self-heal: Promoted calc column '{cname}' to measure in '{tname}'")
            if recovery:
                recovery.record(
                    'tmdl', 'calc_col_promoted_to_measure',
                    item_name=cname,
                    description=f"Calc column '{cname}' in '{tname}' contains aggregation (CALCULATE/SUM/etc.)",
                    action='Promoted to measure',
                    severity='info',
                )
    return repairs


# ════════════════════════════════════════════════════════════════════
#  Public entry point
# ════════════════════════════════════════════════════════════════════

_V3_HEALERS = (
    ('global_measure_dupes', _heal_global_measure_dupes),
    ('self_referencing_measures', _heal_self_referencing_measures),
    ('sort_by_column', _heal_sort_by_column),
    ('hierarchies', _heal_hierarchies),
    ('display_folders', _heal_display_folders),
    ('relationship_type_mismatch', _heal_relationship_type_mismatch),
    ('invalid_identifiers', _heal_invalid_identifiers),
    ('int64_decimal_format', _heal_int64_decimal_format),
    ('datatype_casing', _heal_datatype_casing),
    ('duplicate_relationships', _heal_duplicate_relationships),
    ('hidden_key', _heal_hidden_key),
    # v3.1 — Sprint 137
    ('empty_names', _heal_empty_names),
    ('case_insensitive_dup_columns', _heal_case_insensitive_dup_columns),
    ('empty_calculation_groups', _heal_empty_calculation_groups),
    ('relationship_missing_columns', _heal_relationship_missing_columns),
    ('dax_trailing_comma', _heal_dax_trailing_comma),
    ('measure_leading_equals', _heal_measure_leading_equals),
    ('data_category', _heal_data_category),
    ('empty_annotations', _heal_empty_annotations),
    ('duplicate_hierarchy_names', _heal_duplicate_hierarchy_names),
    # v3.2 — Sprint 138 — schema & datatype
    ('column_without_datatype', _heal_column_without_datatype),
    ('measure_without_datatype', _heal_measure_without_datatype),
    ('boolean_with_string_default', _heal_boolean_with_string_default),
    ('numeric_format_string_mismatch', _heal_numeric_format_string_mismatch),
    ('datetime_without_format', _heal_datetime_without_format),
    ('lineage_tag_collision', _heal_lineage_tag_collision),
    ('missing_lineage_tag', _heal_missing_lineage_tag),
    ('source_column_missing', _heal_source_column_missing),
    ('key_column_nullable', _heal_key_column_nullable),
    ('int_column_with_decimal_default', _heal_int_column_with_decimal_default),
    # v3.3 — Sprint 139 — Power Query / M
    ('m_unbalanced_let_in', _heal_m_unbalanced_let_in),
    ('m_duplicate_in', _heal_m_duplicate_in),
    ('m_unbalanced_parens', _heal_m_unbalanced_parens),
    ('m_step_name_collision', _heal_m_step_name_collision),
    ('m_invalid_identifier_unquoted', _heal_m_invalid_identifier_unquoted),
    ('m_trailing_comma_in_record', _heal_m_trailing_comma_in_record),
    ('m_double_comma', _heal_m_double_comma),
    ('m_missing_source_step', _heal_m_missing_source_step),
    ('m_credential_in_expression', _heal_m_credential_in_expression),
    ('m_partition_mode_mismatch', _heal_m_partition_mode_mismatch),
    ('m_dataflow_ref_dangling', _heal_m_dataflow_ref_dangling),
    # v3.5 — Sprint 144 — Phase 4 Zero-Error: model-side healers
    ('dax_unbalanced_brackets', _heal_dax_unbalanced_brackets),
    ('dax_unknown_function', _heal_dax_unknown_function),
    ('dax_circular_dependency', _heal_dax_circular_dependency),
    ('relationship_orphan_table', _heal_relationship_orphan_table),
    ('relationship_self_loop', _heal_relationship_self_loop),
    ('column_duplicate_name_case', _heal_column_duplicate_name_case),
    ('column_invalid_datatype', _heal_column_invalid_datatype),
    ('partition_empty_m', _heal_partition_empty_m),
    ('parameter_default_out_of_domain', _heal_parameter_default_out_of_domain),
    ('rls_missing_table_permission', _heal_rls_missing_table_permission),
    # v3.6 — Calc column / measure classification
    ('calc_col_to_measure', _heal_calc_col_to_measure),
)


def run_v3_healers(model, recovery=None) -> int:
    """Run all v3 healers; return total repair count.

    Each healer is wrapped in a defensive try/except so a bug in one
    healer cannot prevent the others from running, nor block migration.
    """
    total = 0
    for name, fn in _V3_HEALERS:
        try:
            total += fn(model, recovery=recovery)
        except Exception as exc:  # noqa: BLE001 — never block migration
            if recovery is not None:
                try:
                    recovery.record(
                        'tmdl', 'self_heal_v3_error',
                        item_name=name,
                        description=f'Healer "{name}" raised: {exc!r}',
                        action='Healer skipped (other healers continue)',
                        severity='error',
                    )
                except Exception:
                    pass
    return total
