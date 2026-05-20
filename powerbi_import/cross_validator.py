"""Cross-artifact validator.

Bridges the TMDL semantic model and PBIR report: ensures every field
reference in the report actually exists in the model, and every
relationship / RLS role references real tables and columns.

Entry point: ``cross_validate(model, report_state)`` returns a
``CrossValidationResult`` with issues categorised as ERROR or WARNING.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


@dataclass
class CrossIssue:
    """Single cross-artifact validation issue."""
    category: str           # 'visual', 'filter', 'relationship', 'rls', 'orphan'
    severity: str           # 'error' or 'warning'
    message: str
    location: str = ''

    def to_dict(self) -> Dict[str, str]:
        return {
            'category': self.category,
            'severity': self.severity,
            'message': self.message,
            'location': self.location,
        }


@dataclass
class CrossValidationResult:
    """Aggregated cross-validation result."""
    issues: List[CrossIssue] = field(default_factory=list)

    @property
    def errors(self) -> List[CrossIssue]:
        return [i for i in self.issues if i.severity == 'error']

    @property
    def warnings(self) -> List[CrossIssue]:
        return [i for i in self.issues if i.severity == 'warning']

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'ok': self.ok,
            'error_count': len(self.errors),
            'warning_count': len(self.warnings),
            'issues': [i.to_dict() for i in self.issues],
        }


def _build_model_index(model: Dict[str, Any]) -> Tuple[
    Set[str],
    Dict[str, Set[str]],
    Dict[str, Set[str]],
]:
    """Extract sets of known tables, columns, and measures."""
    tables: Set[str] = set()
    columns: Dict[str, Set[str]] = {}
    measures: Dict[str, Set[str]] = {}
    for t in (model.get('model') or model).get('tables', []):
        name = t.get('name', '')
        if not name:
            continue
        tables.add(name)
        columns[name] = {c.get('name', '') for c in t.get('columns', []) if c.get('name')}
        measures[name] = {m.get('name', '') for m in t.get('measures', []) if m.get('name')}
    return tables, columns, measures


def _extract_visual_refs(visual_json: Dict[str, Any]) -> List[Tuple[str, str, str]]:
    """Return (table, field, 'column'|'measure') tuples from a visual's query."""
    refs: List[Tuple[str, str, str]] = []
    vblock = visual_json.get('visual') if isinstance(visual_json.get('visual'), dict) else None
    if not vblock:
        return refs
    query = vblock.get('query')
    if not isinstance(query, dict):
        return refs
    qs = query.get('queryState')
    if not isinstance(qs, dict):
        return refs
    for role_val in qs.values():
        if not isinstance(role_val, dict):
            continue
        for proj in (role_val.get('projections') or []):
            if not isinstance(proj, dict):
                continue
            fld = proj.get('field', {})
            if not isinstance(fld, dict):
                continue
            col_block = fld.get('Column')
            if isinstance(col_block, dict):
                entity = ''
                expr = col_block.get('Expression')
                if isinstance(expr, dict):
                    src = expr.get('SourceRef')
                    if isinstance(src, dict):
                        entity = src.get('Entity', '')
                prop = col_block.get('Property', '')
                if entity and prop:
                    refs.append((entity, prop, 'column'))
            mea_block = fld.get('Measure')
            if isinstance(mea_block, dict):
                entity = ''
                expr = mea_block.get('Expression')
                if isinstance(expr, dict):
                    src = expr.get('SourceRef')
                    if isinstance(src, dict):
                        entity = src.get('Entity', '')
                prop = mea_block.get('Property', '')
                if entity and prop:
                    refs.append((entity, prop, 'measure'))
            agg_block = fld.get('Aggregation')
            if isinstance(agg_block, dict):
                agg_expr = agg_block.get('Expression')
                if isinstance(agg_expr, dict):
                    inner_col = agg_expr.get('Column')
                    if isinstance(inner_col, dict):
                        entity = ''
                        ie = inner_col.get('Expression')
                        if isinstance(ie, dict):
                            src = ie.get('SourceRef')
                            if isinstance(src, dict):
                                entity = src.get('Entity', '')
                        prop = inner_col.get('Property', '')
                        if entity and prop:
                            refs.append((entity, prop, 'column'))
    return refs


def _check_visual_refs(
    report_state: Dict[str, Any],
    table_names: Set[str],
    columns: Dict[str, Set[str]],
    measures: Dict[str, Set[str]],
) -> List[CrossIssue]:
    issues: List[CrossIssue] = []
    for page in report_state.get('pages', []):
        for visual in page.get('visuals', []):
            loc = f"{page.get('name', '?')}/{visual.get('name', '?')}"
            for table, field_name, kind in _extract_visual_refs(visual.get('json', {})):
                if table not in table_names:
                    issues.append(CrossIssue(
                        'visual', 'error',
                        f"Visual references table '{table}' which doesn't exist in the model",
                        loc,
                    ))
                    continue
                if kind == 'column' and field_name not in columns.get(table, set()):
                    if field_name not in measures.get(table, set()):
                        issues.append(CrossIssue(
                            'visual', 'error',
                            f"Visual references '{table}'.'{field_name}' (column) — not found in model",
                            loc,
                        ))
                elif kind == 'measure' and field_name not in measures.get(table, set()):
                    if field_name not in columns.get(table, set()):
                        issues.append(CrossIssue(
                            'visual', 'error',
                            f"Visual references '{table}'.'{field_name}' (measure) — not found in model",
                            loc,
                        ))
    return issues


def _check_relationships(
    model: Dict[str, Any],
    table_names: Set[str],
    columns: Dict[str, Set[str]],
) -> List[CrossIssue]:
    issues: List[CrossIssue] = []
    m = model.get('model') or model
    for rel in m.get('relationships', []):
        ft = rel.get('fromTable', '')
        tt = rel.get('toTable', '')
        fc = rel.get('fromColumn', '')
        tc = rel.get('toColumn', '')
        if ft and ft not in table_names:
            issues.append(CrossIssue(
                'relationship', 'error',
                f"Relationship fromTable '{ft}' doesn't exist", ''))
        elif ft and fc and fc not in columns.get(ft, set()):
            issues.append(CrossIssue(
                'relationship', 'error',
                f"Relationship fromColumn '{ft}'.'{fc}' doesn't exist", ''))
        if tt and tt not in table_names:
            issues.append(CrossIssue(
                'relationship', 'error',
                f"Relationship toTable '{tt}' doesn't exist", ''))
        elif tt and tc and tc not in columns.get(tt, set()):
            issues.append(CrossIssue(
                'relationship', 'error',
                f"Relationship toColumn '{tt}'.'{tc}' doesn't exist", ''))
    return issues


def _check_rls(
    model: Dict[str, Any],
    table_names: Set[str],
) -> List[CrossIssue]:
    issues: List[CrossIssue] = []
    m = model.get('model') or model
    for role in m.get('roles', []):
        rname = role.get('name', '?')
        for tp in role.get('tablePermissions', []):
            tname = tp.get('name', '')
            if tname and tname not in table_names:
                issues.append(CrossIssue(
                    'rls', 'error',
                    f"RLS role '{rname}' references table '{tname}' which doesn't exist",
                    '',
                ))
    return issues


def _check_orphans(
    report_state: Dict[str, Any],
    table_names: Set[str],
    columns: Dict[str, Set[str]],
    measures: Dict[str, Set[str]],
) -> List[CrossIssue]:
    """Tables/measures defined in model but never referenced by any visual."""
    issues: List[CrossIssue] = []
    used_fields: Set[Tuple[str, str]] = set()
    for page in report_state.get('pages', []):
        for visual in page.get('visuals', []):
            for table, field_name, _ in _extract_visual_refs(visual.get('json', {})):
                used_fields.add((table, field_name))
    _SKIP = {'Calendar', 'DateTableTemplate', 'LocalDateTable'}
    for tname in table_names:
        if tname in _SKIP:
            continue
        for mname in measures.get(tname, set()):
            if (tname, mname) not in used_fields:
                issues.append(CrossIssue(
                    'orphan', 'warning',
                    f"Measure '{tname}'.'{mname}' is never referenced by any visual",
                    '',
                ))
    return issues


def cross_validate(
    model: Dict[str, Any],
    report_state: Optional[Dict[str, Any]] = None,
) -> CrossValidationResult:
    """Run all cross-artifact checks.

    Parameters
    ----------
    model : dict
        The semantic model dict (as built by ``tmdl_generator``).
    report_state : dict or None
        If ``None``, only model-internal checks run.
    """
    result = CrossValidationResult()
    if not model:
        return result

    table_names, columns, measures = _build_model_index(model)
    result.issues.extend(_check_relationships(model, table_names, columns))
    result.issues.extend(_check_rls(model, table_names))

    if report_state:
        result.issues.extend(
            _check_visual_refs(report_state, table_names, columns, measures))
        result.issues.extend(
            _check_orphans(report_state, table_names, columns, measures))

    return result
