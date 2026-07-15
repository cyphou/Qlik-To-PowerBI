"""DAX expression validator (lightweight).

Conversion guardrail utility to verify generated DAX strings
before they are emitted into model artifacts.
"""

import re
from typing import List


__all__ = ['validate_dax_expression', 'DaxExpressionValidator']


_QLIK_FUNC_LEAK = re.compile(
    r'\b(AGGR|DUAL|FIELDVALUE|PEEK|PREVIOUS'
    r'|ABOVE|BELOW|BEFORE|AFTER|NOOFROWS|NOOFCOLUMNS'
    r'|DIMENSIONALITY|SECONDARYDIMENSIONALITY'
    r'|RANGESUM|RANGEAVG|RANGECOUNT|RANGEMAX|RANGEMIN'
    r'|RANGESKEW|RANGEKURTOSIS|RANGESTDEV|RANGECORREL'
    r'|RANGEFRACTILE|RANGEIRR|RANGENPV|RANGENULLCOUNT'
    r'|RANGEMISSINGCOUNT|RANGETEXTCOUNT|RANGENUMERICCOUNT'
    r'|RANGEMINSTRING|RANGEMAXSTRING|RANGEONLY'
    r'|CONCAT|KEEPCHAR|PURGECHAR|REPEAT|SUBFIELD'
    r'|SUBSTRINGCOUNT|CAPITALIZE|EVALUATE'
    r'|OSUSER|GETREGISTRYSTRING|GETFOLDERNAME'
    r'|DOCUMENTNAME|DOCUMENTPATH|DOCUMENTTITLE'
    r'|RELOADTIME|GETACTIVESHEET|GETOBJECTFIELD)\b\s*\(',
    re.IGNORECASE,
)


def _check_balanced(expr: str) -> List[str]:
    issues = []
    pairs = {')': '(', ']': '[', '}': '{'}
    openers = set(pairs.values())
    stack = []
    for idx, ch in enumerate(expr):
        if ch in openers:
            stack.append((ch, idx))
        elif ch in pairs:
            if not stack:
                issues.append(f'unmatched closing "{ch}" at pos {idx}')
            elif stack[-1][0] != pairs[ch]:
                issues.append(
                    f'mismatched bracket at pos {idx}: expected close for "{stack[-1][0]}" but got "{ch}"'
                )
                stack.pop()
            else:
                stack.pop()
    for ch, idx in stack:
        issues.append(f'unmatched opening "{ch}" at pos {idx}')
    return issues


def _check_quotes(expr: str) -> List[str]:
    issues = []
    in_double = False
    in_single = False
    bracket_depth = 0
    i = 0
    n = len(expr)
    while i < n:
        ch = expr[i]
        if ch == '[' and not in_double and not in_single:
            bracket_depth += 1
            i += 1
            continue
        if ch == ']' and bracket_depth and not in_double and not in_single:
            bracket_depth -= 1
            i += 1
            continue
        if ch == '"' and not in_single:
            if in_double and i + 1 < n and expr[i + 1] == '"':
                i += 2
                continue
            in_double = not in_double
            i += 1
            continue
        if ch == "'" and not in_double and bracket_depth == 0:
            if in_single and i + 1 < n and expr[i + 1] == "'":
                i += 2
                continue
            in_single = not in_single
            i += 1
            continue
        i += 1
    if in_double:
        issues.append('unterminated double-quoted string literal')
    if in_single:
        issues.append('unterminated single-quoted identifier')
    return issues


def validate_dax_expression(expr: str) -> List[str]:
    """Validate a generated DAX expression.

    Returns a list of issue messages. Empty list means valid enough to emit.
    """
    if not expr or not str(expr).strip():
        return ['empty DAX expression']

    text = str(expr)
    issues: List[str] = []
    issues.extend(_check_quotes(text))
    issues.extend(_check_balanced(text))

    if _QLIK_FUNC_LEAK.search(text):
        issues.append('unconverted Qlik function token detected in DAX output')

    if re.search(r'\b(None|undefined)\b', text, re.IGNORECASE):
        issues.append('invalid literal token detected in DAX output')

    if '/*' in text and '*/' not in text:
        issues.append('unterminated block comment')

    return issues


class DaxExpressionValidator:
    """Class wrapper for compatibility with validator patterns."""

    @staticmethod
    def validate_expression(expr: str) -> List[str]:
        return validate_dax_expression(expr)
