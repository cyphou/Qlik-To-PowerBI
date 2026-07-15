"""Confidence-scored Power Query M self-healing.

Small, idempotent healers for common M syntax defects generated during
migration. The API is intentionally minimal and dependency-free so it can
be reused by autoheal and custom workflows.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

try:
    from powerbi_import.calc_column_utils import _quote_m_ids
except Exception:  # pragma: no cover
    def _quote_m_ids(m_expr: str) -> str:  # type: ignore
        return m_expr


@dataclass
class HealAction:
    """One deterministic healing action."""

    name: str
    category: str
    confidence: str
    before: str
    after: str
    description: str


@dataclass
class HealReport:
    """Aggregated result of one M healing pass."""

    original: str
    healed: str
    actions: List[HealAction] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return self.original != self.healed


HIGH = "high"
MEDIUM = "medium"
DEFAULT_REWRITE_POLICY = "balanced"


def _m_spans(expr: str) -> List[Tuple[int, int]]:
    """Return [start, end) opaque spans in M text.

    Opaque spans: strings, bracket access, line/block comments.
    """
    spans: List[Tuple[int, int]] = []
    i, n = 0, len(expr)
    while i < n:
        ch = expr[i]
        two = expr[i:i + 2]
        if ch == '"':
            start = i
            i += 1
            while i < n:
                if expr[i] == '"' and i + 1 < n and expr[i + 1] == '"':
                    i += 2
                    continue
                if expr[i] == '"':
                    i += 1
                    break
                i += 1
            spans.append((start, i))
            continue
        if two == "//":
            start = i
            while i < n and expr[i] not in "\r\n":
                i += 1
            spans.append((start, i))
            continue
        if two == "/*":
            start = i
            i += 2
            while i < n and expr[i:i + 2] != "*/":
                i += 1
            i = min(n, i + 2)
            spans.append((start, i))
            continue
        if ch == "[":
            start = i
            i += 1
            while i < n and expr[i] != "]":
                i += 1
            if i < n:
                i += 1
            spans.append((start, i))
            continue
        i += 1
    return spans


def _in_span(idx: int, spans: List[Tuple[int, int]]) -> bool:
    for s, e in spans:
        if s <= idx < e:
            return True
        if idx < s:
            break
    return False


def _paren_profile(expr: str) -> Tuple[int, bool]:
    spans = _m_spans(expr)
    depth = 0
    went_negative = False
    for i, ch in enumerate(expr):
        if ch not in "()":
            continue
        if _in_span(i, spans):
            continue
        depth += 1 if ch == "(" else -1
        if depth < 0:
            went_negative = True
    return depth, went_negative


def heal_quote_identifiers(m: str) -> Tuple[str, Optional[HealAction]]:
    healed = _quote_m_ids(m)
    if healed == m:
        return m, None
    return healed, HealAction(
        "quote_identifiers", "m_syntax", HIGH, m, healed,
        "Quoted field identifiers containing special characters",
    )


def heal_trailing_comma(m: str) -> Tuple[str, Optional[HealAction]]:
    spans = _m_spans(m)
    out: List[str] = []
    changed = False
    i, n = 0, len(m)
    while i < n:
        ch = m[i]
        if ch == "," and not _in_span(i, spans):
            j = i + 1
            while j < n and m[j] in " \t\r\n":
                j += 1
            nxt = m[j] if j < n else ""
            is_in_kw = (m[j:j + 2] == "in" and (j + 2 >= n or m[j + 2] in " \t\r\n"))
            if j >= n or nxt == ")" or is_in_kw:
                changed = True
                i += 1
                continue
        out.append(ch)
        i += 1
    if not changed:
        return m, None
    healed = "".join(out)
    return healed, HealAction(
        "trailing_comma", "m_syntax", HIGH, m, healed,
        "Removed dangling comma before ')', 'in', or end",
    )


def heal_balance_parens(m: str) -> Tuple[str, Optional[HealAction]]:
    net, went_negative = _paren_profile(m)
    if net <= 0 or went_negative:
        return m, None
    healed = m + (")" * net)
    return healed, HealAction(
        "balance_parens", "m_syntax", HIGH if net == 1 else MEDIUM,
        m, healed, f"Appended {net} closing parenthesis/parentheses",
    )


def heal_missing_in_clause(m: str) -> Tuple[str, Optional[HealAction]]:
    """Add a top-level 'in <LastStep>' for incomplete let blocks.

    Conservative by design: only applies when expression starts with 'let'
    and no top-level 'in' line exists.
    """
    lines = m.splitlines()
    if not lines:
        return m, None

    first = lines[0].strip().lower()
    if first != "let":
        return m, None

    has_in = any(re.match(r"^\s*in\b", ln, flags=re.IGNORECASE) for ln in lines)
    if has_in:
        return m, None

    step_name: Optional[str] = None
    assign_re = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=")
    for ln in lines[1:]:
        m_assign = assign_re.match(ln)
        if m_assign:
            step_name = m_assign.group(1)

    if not step_name:
        return m, None

    healed = m.rstrip() + f"\nin\n    {step_name}"
    return healed, HealAction(
        "missing_in_clause",
        "m_syntax",
        MEDIUM,
        m,
        healed,
        "Added missing top-level 'in' clause using last let step",
    )


def heal_m(m: str, rewrite_policy: str = DEFAULT_REWRITE_POLICY) -> HealReport:
    original = m
    current = m
    actions: List[HealAction] = []
    policy = str(rewrite_policy or DEFAULT_REWRITE_POLICY).strip().lower()

    def _apply(fn):
        nonlocal current
        new_text, action = fn(current)
        if action is not None and new_text != current:
            actions.append(action)
            current = new_text

    _apply(heal_quote_identifiers)
    _apply(heal_trailing_comma)
    _apply(heal_balance_parens)
    if policy == "aggressive":
        _apply(heal_missing_in_clause)

    return HealReport(original=original, healed=current, actions=actions)
