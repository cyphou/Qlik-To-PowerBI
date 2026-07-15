"""Power Query M syntax validator (lightweight).

A non-parsing-but-thorough validator for generated M queries. Returns a
list of issue strings (empty => valid).

Checks performed:

  * Balanced parentheses ``(`` ``)``
  * Balanced brackets ``[`` ``]``
  * Balanced braces ``{`` ``}`` (M list literals)
  * Equal count of ``let`` / ``in`` keywords (one ``in`` per ``let``)
  * Quoted-identifier syntax: every ``#"..."`` is properly closed
  * String literal closure: every ``"`` has a matching ``"``
  * No trailing comma directly before ``in`` keyword
    * No residual Qlik function-call syntax or single-quoted literals
    * No function-style ``if(...)`` or malformed row-field references
  * No empty M expression

The validator is *string-aware* — bracket/brace counts ignore characters
inside string literals (including quoted identifiers).
"""

import re
from typing import List


__all__ = ['validate_m_query', 'MQueryValidator']


_M_STRING_LITERAL = re.compile(r'"(?:[^"]|"")*"')


def _strip_strings_and_comments(text: str) -> str:
    """Replace string literals, comments, and quoted identifiers with
    placeholders so that subsequent character-level checks ignore their
    contents.  Preserves length and line breaks.
    """
    out = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        # Quoted identifier #"..."
        if ch == '#' and i + 1 < n and text[i + 1] == '"':
            j = i + 2
            while j < n:
                if text[j] == '"':
                    if j + 1 < n and text[j + 1] == '"':
                        j += 2
                        continue
                    j += 1
                    break
                j += 1
            out.append(' ' * (j - i))
            i = j
            continue
        # Plain string "..."
        if ch == '"':
            j = i + 1
            while j < n:
                if text[j] == '"':
                    if j + 1 < n and text[j + 1] == '"':
                        j += 2
                        continue
                    j += 1
                    break
                j += 1
            out.append(' ' * (j - i))
            i = j
            continue
        # Line comment // ... \n
        if ch == '/' and i + 1 < n and text[i + 1] == '/':
            j = text.find('\n', i)
            if j == -1:
                j = n
            out.append(' ' * (j - i))
            i = j
            continue
        # Block comment /* ... */
        if ch == '/' and i + 1 < n and text[i + 1] == '*':
            j = text.find('*/', i + 2)
            if j == -1:
                j = n
            else:
                j += 2
            block = text[i:j]
            out.append(''.join('\n' if c == '\n' else ' ' for c in block))
            i = j
            continue
        out.append(ch)
        i += 1
    return ''.join(out)


def _check_quoted_identifiers(text: str) -> List[str]:
    """Detect unterminated ``#"..."`` quoted identifiers in the raw text."""
    issues = []
    i = 0
    n = len(text)
    while i < n - 1:
        if text[i] == '#' and text[i + 1] == '"':
            j = i + 2
            closed = False
            while j < n:
                if text[j] == '"':
                    if j + 1 < n and text[j + 1] == '"':
                        j += 2
                        continue
                    closed = True
                    j += 1
                    break
                j += 1
            if not closed:
                line_no = text[:i].count('\n') + 1
                issues.append(f'unterminated quoted identifier #"... at line {line_no}')
            i = j
        else:
            i += 1
    return issues


def _check_string_literals(text: str) -> List[str]:
    """Detect unterminated string literals in the raw text."""
    issues = []
    i = 0
    n = len(text)
    in_str = False
    str_start = 0
    while i < n:
        ch = text[i]
        # Skip past quoted identifiers
        if not in_str and ch == '#' and i + 1 < n and text[i + 1] == '"':
            j = i + 2
            while j < n:
                if text[j] == '"':
                    if j + 1 < n and text[j + 1] == '"':
                        j += 2
                        continue
                    j += 1
                    break
                j += 1
            i = j
            continue
        # Skip line comments
        if not in_str and ch == '/' and i + 1 < n and text[i + 1] == '/':
            i = text.find('\n', i)
            if i == -1:
                return issues
            continue
        if not in_str:
            if ch == '"':
                in_str = True
                str_start = i
            i += 1
            continue
        # In string
        if ch == '"':
            if i + 1 < n and text[i + 1] == '"':
                i += 2
                continue
            in_str = False
        i += 1
    if in_str:
        line_no = text[:str_start].count('\n') + 1
        issues.append(f'unterminated string literal "... at line {line_no}')
    return issues


def _check_brackets(text: str) -> List[str]:
    """Verify bracket balance on a string-stripped copy of the M text."""
    issues = []
    pairs = {')': '(', ']': '[', '}': '{'}
    openers = set(pairs.values())
    stack = []
    for idx, ch in enumerate(text):
        if ch in openers:
            stack.append((ch, idx))
        elif ch in pairs:
            if not stack:
                line_no = text[:idx].count('\n') + 1
                issues.append(f'unmatched closing "{ch}" at line {line_no}')
            elif stack[-1][0] != pairs[ch]:
                exp_open = stack[-1][0]
                line_no = text[:idx].count('\n') + 1
                issues.append(
                    f'mismatched brackets at line {line_no}: '
                    f'expected to close "{exp_open}" but found "{ch}"'
                )
                stack.pop()
            else:
                stack.pop()
    for ch, idx in stack:
        line_no = text[:idx].count('\n') + 1
        issues.append(f'unmatched opening "{ch}" at line {line_no}')
    return issues


_LET_RE = re.compile(r'\blet\b')
_IN_RE = re.compile(r'\bin\b')


def _check_let_in(stripped: str) -> List[str]:
    """Each ``let`` block must be terminated by exactly one ``in``."""
    issues = []
    let_count = len(_LET_RE.findall(stripped))
    in_count = len(_IN_RE.findall(stripped))
    if let_count != in_count:
        issues.append(
            f'unbalanced let/in: {let_count} let, {in_count} in '
            '(each let block needs exactly one matching in)'
        )
    return issues


_TRAILING_COMMA_BEFORE_IN = re.compile(r',\s*\bin\b')


def _check_trailing_comma(stripped: str) -> List[str]:
    if _TRAILING_COMMA_BEFORE_IN.search(stripped):
        return ['trailing comma before "in" keyword']
    return []


_QLIK_FUNCTION_CALL = re.compile(
    r'\b(?:AutoNumberHash256|concat|exists|inmonth|inmonthtodate|inyeartodate|match|num|text|week|weekstart|weekyear)\s*\(',
    re.IGNORECASE,
)

_M_PRIMITIVE_TYPE_IDENTIFIERS = {
    'any', 'anynonnull', 'binary', 'date', 'datetime', 'datetimezone',
    'duration', 'function', 'list', 'logical', 'none', 'null', 'number',
    'record', 'table', 'text', 'time', 'type',
}


def _check_generated_expression_grammar(m_text: str, stripped: str) -> List[str]:
    """Reject Qlik constructs that are balanced text but invalid M grammar."""
    checks = (
        (re.compile(r"(?:^|[,(=<>+\-*/&])\s*'[^'\r\n]*'", re.MULTILINE),
         'single-quoted literal; Power Query M strings require double quotes'),
        (re.compile(r'\bif\s*\(', re.IGNORECASE),
         'function-style if(...); Power Query M requires if ... then ... else'),
        (re.compile(r'\beach\s*=\s*null\s*\(', re.IGNORECASE),
         'invalid IsNull conversion (= null(...))'),
        (_QLIK_FUNCTION_CALL,
         'residual Qlik function call'),
        (re.compile(r'\b(?:AND|OR|NOT)\b'),
         'uppercase Qlik boolean operator; Power Query M requires lowercase keywords'),
        (re.compile(r'\beach\s*\*\s*(?:[,\r\n)]|$)', re.IGNORECASE),
         'bare wildcard expression after each'),
        (re.compile(r'\[\s*\['),
         'nested row-field brackets'),
        (re.compile(r'\[\s*"(?:[^"]|"")*"\s*\]'),
         'string literal used as a row-field identifier'),
        (re.compile(r'\bDate\.From\s*\([^()\r\n]*,', re.IGNORECASE),
         'Date.From called with a Qlik format argument'),
    )

    issues = []
    for pattern, message in checks:
        haystack = m_text if 'single-quoted' in message or 'row-field identifier' in message else stripped
        match = pattern.search(haystack)
        if match:
            line_no = haystack[:match.start()].count('\n') + 1
            issues.append(f'{message} at line {line_no}')

    for match in re.finditer(
        r'\bas\s+(?:nullable\s+)?([A-Za-z_][\w.]*)',
        stripped,
        re.IGNORECASE,
    ):
        type_identifier = match.group(1)
        if type_identifier.casefold() not in _M_PRIMITIVE_TYPE_IDENTIFIERS:
            line_no = stripped[:match.start()].count('\n') + 1
            issues.append(
                f'invalid M type identifier after "as": {type_identifier} '
                f'at line {line_no}'
            )

    structured_type = re.search(
        r'\btype\s+table\s*\[[^]]*\b(?:Byte|Int8|Int16|Int32|Int64|Single|Double|Decimal|Currency)\.Type',
        stripped,
        re.IGNORECASE | re.DOTALL,
    )
    if structured_type:
        line_no = stripped[:structured_type.start()].count('\n') + 1
        issues.append(
            'non-primitive type expression inside type table declaration '
            f'at line {line_no}'
        )
    return issues


def validate_m_query(m_text: str) -> List[str]:
    """Run all M validation checks.

    Returns a list of issue strings; empty list means the M text passed
    every check.
    """
    if not m_text or not m_text.strip():
        return ['empty M expression']

    issues: List[str] = []
    issues.extend(_check_quoted_identifiers(m_text))
    issues.extend(_check_string_literals(m_text))
    stripped = _strip_strings_and_comments(m_text)
    issues.extend(_check_brackets(stripped))
    issues.extend(_check_let_in(stripped))
    issues.extend(_check_trailing_comma(stripped))
    issues.extend(_check_generated_expression_grammar(m_text, stripped))
    return issues


class MQueryValidator:
    """Class wrapper for callers that prefer dotted access."""

    @staticmethod
    def validate(m_text: str) -> List[str]:
        return validate_m_query(m_text)

    @staticmethod
    def is_valid(m_text: str) -> bool:
        return not validate_m_query(m_text)
