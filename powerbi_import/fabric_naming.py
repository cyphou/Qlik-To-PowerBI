"""
Name sanitisation helpers for Fabric artifact generation.

Provides sanitisation functions for table names, column names,
query names, pipeline names, and Python variable names used
across Lakehouse, Dataflow, Notebook, and Pipeline generators.
"""

from __future__ import annotations

import re

# ── Pre-compiled patterns ──────────────────────────────────────────

_BRACKETS = re.compile(r'[\[\]]')
_NON_ALNUM_UNDER = re.compile(r'[^a-zA-Z0-9_]')
_NON_ALNUM_UNDER_SPACE = re.compile(r'[^a-zA-Z0-9_ ]')
_LEADING_DIGITS = re.compile(r'^[0-9]+')
_MULTI_UNDER = re.compile(r'_+')


def _base_sanitize(name: str, *, allow_spaces: bool = False,
                   lowercase: bool = False, fallback: str = 'name') -> str:
    """Core sanitisation: strip brackets, replace bad chars, collapse underscores."""
    name = _BRACKETS.sub('', name)
    pattern = _NON_ALNUM_UNDER_SPACE if allow_spaces else _NON_ALNUM_UNDER
    name = pattern.sub('_', name)
    name = _MULTI_UNDER.sub('_', name).strip('_')
    if lowercase:
        name = name.lower()
    return name or fallback


def sanitize_table_name(name: str) -> str:
    """Sanitise for Lakehouse / Delta Lake table names."""
    if '.' in name:
        name = name.rsplit('.', 1)[-1]
    name = _base_sanitize(name, lowercase=True, fallback='table')
    name = _LEADING_DIGITS.sub('', name)
    return _MULTI_UNDER.sub('_', name).strip('_') or 'table'


def sanitize_column_name(name: str) -> str:
    """Sanitise for Delta Lake / Spark column names."""
    name = _base_sanitize(name, fallback='column')
    name = _LEADING_DIGITS.sub('_', name)
    return _MULTI_UNDER.sub('_', name).strip('_') or 'column'


def sanitize_query_name(name: str) -> str:
    """Sanitise for Dataflow Gen2 query names (spaces allowed)."""
    return _base_sanitize(name, allow_spaces=True, fallback='Query')


def sanitize_pipeline_name(name: str) -> str:
    """Sanitise for Pipeline activity / reference names."""
    return _base_sanitize(name, fallback='activity')


def make_python_var(name: str) -> str:
    """Convert a table/column name to a valid Python variable name."""
    name = _base_sanitize(name, lowercase=True, fallback='table')
    name = _LEADING_DIGITS.sub('', name)
    return _MULTI_UNDER.sub('_', name).strip('_') or 'table'


def sanitize_filesystem_name(name: str) -> str:
    """Sanitise a name for filesystem paths (keeps spaces, wider charset)."""
    safe = re.sub(r'[<>:"/\\|?*]', '_', name)
    return safe.strip().strip('.')
