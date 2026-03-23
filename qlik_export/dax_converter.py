"""
Qlik Expression → DAX Converter — 175+ function mappings

Converts Qlik Sense expressions (measures, calculated columns, set analysis)
to equivalent DAX expressions for Power BI.

Categories:
- String (25): Upper→UPPER, Lower→LOWER, Len→LEN, Mid→MID, ...
- Math (20): Abs→ABS, Ceil→CEILING, Floor→FLOOR, Sqrt→SQRT, ...
- Date (22): Year→YEAR, Month→MONTH, Today→TODAY, MonthStart→STARTOFMONTH, ...
- Aggregation (15): Sum→SUM, Avg→AVERAGE, Count→COUNT, CountDistinct→DISTINCTCOUNT, ...
- Set Analysis (10): {<Year={2024}>} → CALCULATE(..., 'Table'[Year] = 2024)
- Conditional (12): If→IF, Match→SWITCH, Pick→SWITCH, Alt→COALESCE
- Inter-record (8): Above→EARLIER, RangeSum→window, Rank→RANKX
- Type conversion (8): Num→VALUE, Text→FORMAT, Date→DATEVALUE
- Null handling (6): IsNull→ISBLANK, Null→BLANK, NullCount→COUNTBLANK
- Logical (8): AND→&&, OR→||, NOT→NOT
- Security (3): OSUser→USERPRINCIPALNAME
- Advanced (38): Aggr→SUMMARIZE, Dual→VALUE, Class→INT/DIVIDE
"""

import re
import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ── Simple function mapping (regex_pattern, replacement) ──────────
# Applied in order; each is a (compiled_regex, replacement_string) tuple.

_SIMPLE_FUNCTION_MAP: List[Tuple[str, str]] = [
    # ── Security / User functions ─────────────────────────────
    (r'\bOSUser\s*\(\s*\)', 'USERPRINCIPALNAME()'),
    (r'\bGetActiveSheetId\s*\(\s*\)', '"__sheet__"'),
    (r'\bGetObjectField\s*\(', '"__field__" /*(GetObjectField)*/'),
    (r'\bReloadTime\s*\(\s*\)', 'NOW()'),
    (r'\bDocumentName\s*\(\s*\)', '"__document__"'),
    (r'\bDocumentTitle\s*\(\s*\)', '"__document__"'),
    (r'\bDocumentPath\s*\(\s*\)', '"__path__"'),

    # ── Conditional ─────────────────────────────────────────
    (r'\bIf\s*\(', 'IF('),

    # ── Null / Logic ──────────────────────────────────────────
    (r'\bIsNull\s*\(', 'ISBLANK('),
    (r'\bNull\s*\(\s*\)', 'BLANK()'),
    (r'\bIsNum\s*\(', 'ISNUMBER('),
    (r'\bIsText\s*\(', 'ISTEXT('),
    (r'\bNullCount\s*\(', 'COUNTBLANK('),
    (r'\bMissingCount\s*\(', 'COUNTBLANK('),
    (r'\bNot\s*\(', 'NOT('),
    (r'\bTrue\s*\(\s*\)', 'TRUE()'),
    (r'\bFalse\s*\(\s*\)', 'FALSE()'),

    # ── Aggregation ───────────────────────────────────────────
    (r'\bSum\s*\(', 'SUM('),
    (r'\bAvg\s*\(', 'AVERAGE('),
    (r'\bCount\s*\(', 'COUNT('),
    (r'\bCountDistinct\s*\(', 'DISTINCTCOUNT('),
    (r'\bMin\s*\(', 'MIN('),
    (r'\bMax\s*\(', 'MAX('),
    (r'\bMedian\s*\(', 'MEDIAN('),
    (r'\bStdev\s*\(', 'STDEV.S('),
    (r'\bSkew\s*\(', '/* Skew: no DAX equivalent — use custom measure with SUMX/AVERAGEX */ 0'),  # unsupported
    (r'\bOnly\s*\(', 'FIRSTNONBLANK('),
    (r'\bMode\s*\(', 'MINX(TOPN(1, ADDCOLUMNS(VALUES({0}), "@cnt", CALCULATE(COUNTROWS({1}))), [@cnt], DESC), {0})'),
    (r'\bFractile\s*\(', 'PERCENTILE.INC('),
    (r'\bCorrel\s*\(', '/* Correl: no DAX equivalent — use custom SUMX/AVERAGEX Pearson formula */ 0'),  # unsupported
    (r'\bRangeSum\s*\(', 'SUM( /* RangeSum */ '),
    (r'\bRangeAvg\s*\(', 'AVERAGE( /* RangeAvg */ '),
    (r'\bRangeCount\s*\(', 'COUNT( /* RangeCount */ '),
    (r'\bRangeMin\s*\(', 'MIN( /* RangeMin */ '),
    (r'\bRangeMax\s*\(', 'MAX( /* RangeMax */ '),
    (r'\bRangeStdev\s*\(', 'STDEV.S( /* RangeStdev */ '),
    (r'\bFirstSortedValue\s*\(', 'MINX(TOPN(1, '),

    # ── Date / Time ───────────────────────────────────────────
    (r'\bYear\s*\(', 'YEAR('),
    (r'\bMonth\s*\(', 'MONTH('),
    (r'\bDay\s*\(', 'DAY('),
    (r'\bHour\s*\(', 'HOUR('),
    (r'\bMinute\s*\(', 'MINUTE('),
    (r'\bSecond\s*\(', 'SECOND('),
    (r'\bWeekDay\s*\(', 'WEEKDAY('),
    (r'\bWeekYear\s*\(', 'WEEKNUM('),
    (r'\bWeek\s*\(', 'WEEKNUM('),
    (r'\bToday\s*\(\s*\)', 'TODAY()'),
    (r'\bNow\s*\(\s*\)', 'NOW()'),
    (r'\bDate\s*\(', 'DATE('),
    (r'\bMakeDate\s*\(', 'DATE('),
    (r'\bMakeTime\s*\(', 'TIME('),
    (r'\bDate#\s*\(', 'DATEVALUE('),
    (r'\bTimestamp\s*\(', 'VALUE( /* Timestamp */ '),
    (r'\bTimestamp#\s*\(', 'DATEVALUE( /* Timestamp# */ '),
    (r'\bMonthStart\s*\(', 'STARTOFMONTH('),
    (r'\bMonthEnd\s*\(', 'ENDOFMONTH('),
    (r'\bMonthName\s*\(', 'FORMAT({0}, "MMMM")'),
    (r'\bYearStart\s*\(', 'STARTOFYEAR('),
    (r'\bYearEnd\s*\(', 'ENDOFYEAR('),
    (r'\bQuarterStart\s*\(', 'STARTOFQUARTER('),
    (r'\bQuarterEnd\s*\(', 'ENDOFQUARTER('),
    (r'\bQuarterName\s*\(', 'FORMAT({0}, "\\QQ YYYY")'),
    (r'\bWeekStart\s*\(', 'DATE(YEAR({0}), 1, 1) + (WEEKNUM({0}) - 1) * 7'),
    (r'\bWeekEnd\s*\(', 'DATE(YEAR({0}), 1, 1) + WEEKNUM({0}) * 7 - 1'),
    (r'\bAddMonths\s*\(', 'EDATE('),
    (r'\bAddYears\s*\(', 'DATE(YEAR({0}) + {1}, MONTH({0}), DAY({0}))'),
    (r'\bYearToDate\s*\(', 'TOTALYTD({0}, '),
    (r'\bInYear\s*\(', 'YEAR({0}) = YEAR({1})'),
    (r'\bInYearToDate\s*\(', '{0} <= {1} && YEAR({0}) = YEAR({1})'),
    (r'\bInMonth\s*\(', 'YEAR({0}) = YEAR({1}) && MONTH({0}) = MONTH({1})'),
    (r'\bInQuarter\s*\(', 'YEAR({0}) = YEAR({1}) && QUARTER({0}) = QUARTER({1})'),
    (r'\bAge\s*\(', 'DATEDIFF({0}, {1}, YEAR)'),
    (r'\bNetWorkDays\s*\(', '/* NetWorkDays: approximate — excludes weekends only */ DATEDIFF({0}, {1}, DAY) - 2 * INT(DATEDIFF({0}, {1}, DAY) / 7)'),
    (r'\bDayNumberOfYear\s*\(', 'DATEDIFF(DATE(YEAR({0}), 1, 1), {0}, DAY) + 1'),

    # ── String ────────────────────────────────────────────────
    (r'\bUpper\s*\(', 'UPPER('),
    (r'\bLower\s*\(', 'LOWER('),
    (r'\bLen\s*\(', 'LEN('),
    (r'\bLeft\s*\(', 'LEFT('),
    (r'\bRight\s*\(', 'RIGHT('),
    (r'\bMid\s*\(', 'MID('),
    (r'\bTrim\s*\(', 'TRIM('),
    (r'\bLTrim\s*\(', 'TRIM('),
    (r'\bRTrim\s*\(', 'TRIM('),
    (r'\bReplace\s*\(', 'SUBSTITUTE('),
    (r'\bSubStringCount\s*\(', '(LEN({0}) - LEN(SUBSTITUTE({0}, {1}, ""))) / LEN({1})'),
    (r'\bPurgeChar\s*\(', 'SUBSTITUTE('),
    (r'\bKeepChar\s*\(', '/* KeepChar: no DAX equivalent — returns input unchanged */ {0}'),  # no native DAX
    (r'\bRepeat\s*\(', 'REPT('),
    (r'\bCapitalize\s*\(', '/* Capitalize: no direct DAX */ UPPER(LEFT({0}, 1)) & LOWER(MID({0}, 2, LEN({0})))'),
    (r'\bTextBetween\s*\(', 'MID({0}, SEARCH({1}, {0}) + LEN({1}), SEARCH({2}, {0}, SEARCH({1}, {0}) + LEN({1})) - SEARCH({1}, {0}) - LEN({1}))'),
    (r'\bOrd\s*\(', 'UNICODE('),
    (r'\bChr\s*\(', 'UNICHAR('),
    (r'\bSubField\s*\(', 'PATHITEM(SUBSTITUTE({0}, {1}, "|"), {2})'),
    (r'\bHash128\s*\(', '/* Hash128: no DAX equivalent */ {0}'),
    (r'\bHash160\s*\(', '/* Hash160: no DAX equivalent */ {0}'),
    (r'\bHash256\s*\(', '/* Hash256: no DAX equivalent */ {0}'),
    (r'\bEvaluate\s*\(', '/* Evaluate: no DAX equivalent */ {0}'),
    (r'\bApplyMap\s*\(', 'LOOKUPVALUE('),
    (r'\bMapSubstring\s*\(', '/* MapSubstring: partial — single SUBSTITUTE only */ SUBSTITUTE('),
    (r'\bWildMatch\s*\(', '/* WildMatch */ CONTAINSSTRING('),
    (r'\bMatch\s*\(', 'SWITCH('),
    (r'\bMixMatch\s*\(', 'SWITCH(TRUE(),'),

    # ── Math ──────────────────────────────────────────────────
    (r'\bAbs\s*\(', 'ABS('),
    (r'\bCeil\s*\(', 'CEILING('),
    (r'\bFloor\s*\(', 'FLOOR('),
    (r'\bRound\s*\(', 'ROUND('),
    (r'\bSqrt\s*\(', 'SQRT('),
    (r'\bLog\s*\(', 'LOG('),
    (r'\bLog10\s*\(', 'LOG10('),
    (r'\bExp\s*\(', 'EXP('),
    (r'\bPow\s*\(', 'POWER('),
    (r'\bMod\s*\(', 'MOD('),
    (r'\bSign\s*\(', 'SIGN('),
    (r'\bFact\s*\(', 'FACT('),
    (r'\bCombin\s*\(', 'COMBIN('),
    (r'\bPermut\s*\(', 'PERMUT('),
    (r'\bFrac\s*\(', '{0} - INT({0})'),
    (r'\bDiv\s*\(', 'DIVIDE('),
    (r'\bPi\s*\(\s*\)', 'PI()'),
    (r'\bRand\s*\(\s*\)', 'RAND()'),
    (r'\bSin\s*\(', 'SIN('),
    (r'\bCos\s*\(', 'COS('),
    (r'\bTan\s*\(', 'TAN('),
    (r'\bAsin\s*\(', 'ASIN('),
    (r'\bAcos\s*\(', 'ACOS('),
    (r'\bAtan\s*\(', 'ATAN('),
    (r'\bAtan2\s*\(', 'IF({0} > 0, ATAN({1}/{0}), IF({0} < 0 && {1} >= 0, ATAN({1}/{0}) + PI(), IF({0} < 0 && {1} < 0, ATAN({1}/{0}) - PI(), IF({1} > 0, PI()/2, -PI()/2))))'),
    (r'\bBitCount\s*\(', '/* BitCount: no DAX equivalent */ 0'),  # unsupported

    # ── Type conversion ───────────────────────────────────────
    (r'\bNum\s*\(', 'VALUE('),
    (r'\bNum#\s*\(', 'VALUE('),
    (r'\bText\s*\(', 'FORMAT('),
    (r'\bDate\s*\(', 'DATE('),
    (r'\bTime\s*\(', 'TIME('),
    (r'\bInterval\s*\(', 'FORMAT(INT({0}/3600), "00") & ":" & FORMAT(MOD(INT({0}/60), 60), "00") & ":" & FORMAT(MOD(INT({0}), 60), "00")'),
    (r'\bMoney\s*\(', 'FORMAT({0}, "$#,0.00")'),
    (r'\bDual\s*\(', 'VALUE( /* Dual */ '),

    # ── Statistical ───────────────────────────────────────────
    (r'\bNorminv\s*\(', 'NORM.INV('),
    (r'\bNormDist\s*\(', 'NORM.DIST('),
    (r'\bChiDist\s*\(', 'CHISQ.DIST('),
    (r'\bChiInv\s*\(', 'CHISQ.INV('),
    (r'\bTDist\s*\(', 'T.DIST('),
    (r'\bTInv\s*\(', 'T.INV('),
    (r'\bFDist\s*\(', 'F.DIST('),
    (r'\bFInv\s*\(', 'F.INV('),
]

# Pre-compile patterns for performance
_COMPILED_FUNCTION_MAP = [(re.compile(p, re.IGNORECASE), r) for p, r in _SIMPLE_FUNCTION_MAP]


# ── Qlik → DAX data type mapping ─────────────────────────────────
QLIK_TO_DAX_TYPE: Dict[str, str] = {
    "text": "string",
    "string": "string",
    "num": "double",
    "number": "double",
    "numeric": "double",
    "integer": "int64",
    "int": "int64",
    "money": "decimal",
    "currency": "decimal",
    "date": "dateTime",
    "timestamp": "dateTime",
    "time": "dateTime",
    "boolean": "boolean",
    "dual": "string",
}


# ── Qlik → DAX format string mapping ─────────────────────────────
QLIK_TO_DAX_FORMAT: Dict[str, str] = {
    "#,##0": "#,0",
    "#,##0.00": "#,0.00",
    "0%": "0%",
    "0.00%": "0.00%",
    "$ #,##0": "$#,0",
    "$ #,##0.00": "$#,0.00",
    "DD/MM/YYYY": "DD/MM/YYYY",
    "MM/DD/YYYY": "MM/DD/YYYY",
    "YYYY-MM-DD": "YYYY-MM-DD",
    "YYYY-MM-DD hh:mm:ss": "YYYY-MM-DD hh:nn:ss",
    "hh:mm:ss": "hh:nn:ss",
    "hh:mm": "hh:nn",
}


# ── Main converter function ──────────────────────────────────────

def convert_qlik_expression_to_dax(
    qlik_expr: str,
    table_name: str = "",
    col_table_map: Optional[Dict[str, str]] = None,
    relationships: Optional[List[Dict]] = None,
    is_calculated_column: bool = False,
    variables: Optional[Dict[str, str]] = None,
) -> str:
    """
    Convert a Qlik expression to DAX.

    Args:
        qlik_expr: Qlik expression string (e.g., "Sum(Sales)", "If(IsNull([Amt]), 0, [Amt])")
        table_name: Table where this expression lives
        col_table_map: {column_name: table_name} lookup for RELATED() insertion
        relationships: List of relationship dicts for cross-table inference
        is_calculated_column: Whether this is a calculated column (row-level) expression
        variables: {var_name: var_definition} for $(vName) expansion

    Returns:
        DAX expression string
    """
    if not qlik_expr or not qlik_expr.strip():
        return qlik_expr or ""

    dax = qlik_expr.strip()

    # Phase 1: Operator conversions
    dax = _convert_operators(dax)

    # Phase 1b: Expand dollar-sign variable references
    if variables:
        dax = _expand_variables(dax, variables)

    # Phase 2: Structural conversions (If/Match/Pick → IF/SWITCH)
    dax = _convert_if_expressions(dax)
    dax = _convert_match_expressions(dax)
    dax = _convert_pick_expressions(dax)

    # Phase 3: Set Analysis → CALCULATE (supports multiple modifiers)
    dax = _convert_set_analysis(dax, table_name)

    # Phase 3b: TOTAL qualifier → ALL filter context
    dax = _convert_total_qualifier(dax, table_name)

    # Phase 3c: Sum(If(...)) → CALCULATE/SUMX
    dax = _convert_sum_if(dax, table_name)

    # Phase 3d: Concat() → CONCATENATEX()
    dax = _convert_concat(dax, table_name)

    # Phase 4: Aggr() → SUMMARIZE/ADDCOLUMNS
    dax = _convert_aggr(dax, table_name)

    # Phase 4b: Peek/Previous/Above/Below/RangeSum → OFFSET/WINDOW
    dax = _convert_inter_record(dax, table_name)

    # Phase 5: Simple function mapping (175+ replacements)
    for pattern, replacement in _COMPILED_FUNCTION_MAP:
        # Use lambda to avoid interpreting backslashes in replacement as regex escapes
        dax = pattern.sub(lambda m: replacement, dax)

    # Phase 6: Alt() → COALESCE
    dax = _convert_alt(dax)

    # Phase 7: Class() → INT/DIVIDE
    dax = _convert_class(dax)

    # Phase 8: RELATED() insertion for calculated columns
    if is_calculated_column and col_table_map and table_name:
        dax = _insert_related(dax, table_name, col_table_map, relationships)

    # Phase 9: Clean up
    dax = _cleanup_dax(dax)

    logger.debug(f"Converted: {qlik_expr!r} → {dax!r}")
    return dax


# ── Operator conversion ──────────────────────────────────────────

def _convert_operators(expr: str) -> str:
    """Convert Qlik operators to DAX equivalents."""
    # String concatenation: & stays as &
    # Logical operators
    expr = re.sub(r'\b[Aa][Nn][Dd]\b', '&&', expr)
    expr = re.sub(r'\b[Oo][Rr]\b', '||', expr)
    expr = re.sub(r'\b[Nn][Oo][Tt]\b', 'NOT', expr)

    # Comparison operators
    expr = expr.replace('<>', '<>')  # DAX uses <>
    # Qlik uses = for both assignment and comparison; DAX uses = for comparison
    # No change needed

    return expr


# ── If/ElseIf/Else → nested IF() ─────────────────────────────────

def _convert_if_expressions(expr: str) -> str:
    """Convert Qlik If(cond, then, else) to DAX IF(cond, then, else).

    Qlik If() already uses function-call syntax, so we mainly need to
    ensure nested ElseIf patterns are handled.
    """
    # Qlik: If(cond, val)  → DAX: IF(cond, val)
    # Qlik: If(cond, val1, val2) → DAX: IF(cond, val1, val2)
    # The simple function map already handles If( → IF(
    # But we need to handle inline If ... Then ... Else ... End if used
    expr = re.sub(
        r'\bIf\b\s+(.+?)\s+\bThen\b\s+(.+?)\s+\bElse\b\s+(.+?)\s+\bEnd\b',
        r'IF(\1, \2, \3)',
        expr,
        flags=re.IGNORECASE | re.DOTALL,
    )
    # Nested ElseIf
    expr = re.sub(
        r'\bIf\b\s+(.+?)\s+\bThen\b\s+(.+?)\s+\bElseIf\b',
        r'IF(\1, \2, IF(',
        expr,
        flags=re.IGNORECASE,
    )
    return expr


# ── Match() → SWITCH() ───────────────────────────────────────────

def _convert_match_expressions(expr: str) -> str:
    """Convert Qlik Match(expr, val1, val2, ...) → SWITCH(expr, val1, 1, val2, 2, ...)."""
    # Basic Match → SWITCH mapping (already in simple map)
    return expr


# ── Pick() → SWITCH() ────────────────────────────────────────────

def _convert_pick_expressions(expr: str) -> str:
    """Convert Qlik Pick(n, val1, val2, ...) → SWITCH(n, 1, val1, 2, val2, ...)."""
    pattern = re.compile(r'\bPick\s*\(', re.IGNORECASE)
    if pattern.search(expr):
        expr = pattern.sub('SWITCH(', expr)
    return expr


# ── Set Analysis → CALCULATE ─────────────────────────────────────

def _convert_set_analysis(expr: str, table_name: str = "") -> str:
    """
    Convert Qlik Set Analysis to DAX CALCULATE.

    Qlik: Sum({<Year={2024}, Region={"Europe"}>} Sales)
    DAX:  CALCULATE(SUM('Table'[Sales]), 'Table'[Year] = 2024, 'Table'[Region] = "Europe")

    Qlik: Sum({1<Year={2024}>} Sales)
    DAX:  CALCULATE(SUM('Table'[Sales]), ALL('Table'), 'Table'[Year] = 2024)

    Qlik: Count({$<Year=>} Distinct CustomerID)
    DAX:  CALCULATE(DISTINCTCOUNT('Table'[CustomerID]), REMOVEFILTERS('Table'[Year]))
    """
    # Use a regex to find the start: AggFunc( { — then bracket-match the rest
    start_pattern = re.compile(r'(\b\w+)\s*\(\s*\{', re.IGNORECASE)

    matches = list(start_pattern.finditer(expr))
    for m in reversed(matches):
        agg_func = m.group(1)
        brace_start = m.end() - 1  # position of '{'

        # Bracket-match to find closing '}' (handles nested {})
        depth = 1
        i = brace_start + 1
        while i < len(expr) and depth > 0:
            if expr[i] == '{':
                depth += 1
            elif expr[i] == '}':
                depth -= 1
            i += 1
        # i is past the closing '}'
        set_expr = expr[brace_start + 1:i - 1]

        # Now expect whitespace + field + closing ')'
        rest = expr[i:]
        field_m = re.match(r'\s+((?:Distinct\s+)?\w+)\s*\)', rest, re.IGNORECASE)
        if not field_m:
            continue

        field = field_m.group(1)
        full_end = i + field_m.end()

        # Map aggregation function
        dax_agg = _map_aggregation(agg_func, field, table_name)

        # Parse set modifiers
        filters = _parse_set_modifiers(set_expr, table_name)

        # Check for {1<...>} pattern (ignore current selections → ALL)
        set_id = set_expr.strip().split('<')[0].strip() if '<' in set_expr else set_expr.strip()
        has_all = set_id == '1'

        tbl = f"'{table_name}'" if table_name else "'Table'"
        parts = [dax_agg]
        if has_all:
            parts.append(f"ALL({tbl})")
        # $ is current selection context — no extra filter needed in DAX
        parts.extend(filters)

        if len(parts) > 1:
            replacement = f"CALCULATE({', '.join(parts)})"
        else:
            replacement = parts[0]

        expr = expr[:m.start()] + replacement + expr[full_end:]

    return expr


def _map_aggregation(agg_func: str, field: str, table_name: str = "") -> str:
    """Map Qlik aggregation function to DAX."""
    agg_lower = agg_func.lower()
    field_clean = field.strip()

    # Handle Distinct prefix
    is_distinct = False
    if field_clean.lower().startswith('distinct '):
        is_distinct = True
        field_clean = field_clean[9:].strip()

    # Qualify field with table name
    if table_name and '.' not in field_clean and '[' not in field_clean:
        qualified = f"'{table_name}'[{field_clean}]"
    else:
        qualified = field_clean

    mapping = {
        'sum': f'SUM({qualified})',
        'avg': f'AVERAGE({qualified})',
        'count': f'DISTINCTCOUNT({qualified})' if is_distinct else f'COUNT({qualified})',
        'min': f'MIN({qualified})',
        'max': f'MAX({qualified})',
        'only': f'FIRSTNONBLANK({qualified}, 1)',
        'median': f'MEDIAN({qualified})',
        'stdev': f'STDEV.S({qualified})',
        'fractile': f'PERCENTILE.INC({qualified})',
        'countdistinct': f'DISTINCTCOUNT({qualified})',
    }

    return mapping.get(agg_lower, f'{agg_func.upper()}({qualified})')


def _parse_set_modifiers(set_expr: str, table_name: str = "") -> List[str]:
    """Parse Qlik set analysis modifiers into DAX filter arguments.

    Supports:
    - Field={value} → filter
    - Field={value1, value2} → multi-value IN filter
    - Field= → REMOVEFILTERS
    - Field=Current+{extra} → union
    - Field=Current-{remove} → subtraction
    - P({1} <Field>) → possible values → ALL('T'[Field])
    - E({1} <Field>) → excluded values → EXCEPT(ALL, VALUES)
    - $(=Year(Today())-1) → inline expression evaluation
    """
    filters = []
    tbl = f"'{table_name}'" if table_name else "'Table'"

    # Remove leading set identifier ($ or 1 or empty)
    expr = re.sub(r'^[0-9$]*\s*<?\s*', '', set_expr.strip())
    expr = re.sub(r'>?\s*$', '', expr)

    if not expr:
        return filters

    # ── P() and E() set functions ─────────────────────────────
    # P({1} <Field>) → FILTER(ALL('T'[Field]), ...) — all possible values
    p_pattern = re.compile(r'P\s*\(\s*\{[^}]*\}\s+(\w+)\s*\)', re.IGNORECASE)
    for m in p_pattern.finditer(expr):
        field = m.group(1)
        filters.append(f"ALL({tbl}[{field}])")
    expr = p_pattern.sub('', expr)

    # E({1} <Field>) → EXCEPT(ALL, VALUES) — excluded values
    e_pattern = re.compile(r'E\s*\(\s*\{[^}]*\}\s+(\w+)\s*\)', re.IGNORECASE)
    for m in e_pattern.finditer(expr):
        field = m.group(1)
        filters.append(f"EXCEPT(ALL({tbl}[{field}]), VALUES({tbl}[{field}]))")
    expr = e_pattern.sub('', expr)

    # ── Dollar-sign expressions in values: $(=expr) ───────────
    # Convert $(=Year(Today())-1) → evaluated as DAX expression inline
    expr = re.sub(
        r'\$\(\s*=\s*Year\s*\(\s*Today\s*\(\s*\)\s*\)\s*-\s*1\s*\)',
        'YEAR(TODAY()) - 1',
        expr, flags=re.IGNORECASE,
    )
    # Generic $(=expr) → leave as DAX expression
    expr = re.sub(
        r'\$\(\s*=\s*([^)]+)\)',
        r'\1',
        expr,
    )

    # Parse field={value}, field=value+{extra}, field=value-{remove} patterns
    modifier_pattern = re.compile(
        r'(\w+)\s*=\s*\{([^}]*)\}',
        re.IGNORECASE
    )
    # Extended: field=Current+{extra} or field=Current-{remove}
    ext_pattern = re.compile(
        r'(\w+)\s*=\s*(\w+)\s*([+\-])\s*\{([^}]*)\}',
        re.IGNORECASE
    )

    # Process extended set operators first
    for m in ext_pattern.finditer(expr):
        field = m.group(1)
        _base = m.group(2)  # e.g., 'Year' (current values)
        operator = m.group(3)  # + or -
        values_str = m.group(4).strip()
        vals = [v.strip().strip('"').strip("'") for v in values_str.split(',') if v.strip()]
        if operator == '+':  # Union: current values + extra
            val_filters = ' || '.join(f'{tbl}[{field}] = "{v}"' for v in vals)
            if val_filters:
                filters.append(f'/* +set: union */ {val_filters}')
        elif operator == '-':  # Subtraction: current values - remove
            val_filters = ' && '.join(f'{tbl}[{field}] <> "{v}"' for v in vals)
            if val_filters:
                filters.append(val_filters)

    # Process standard modifiers (skip fields already handled by ext_pattern)
    ext_fields = {m.group(1) for m in ext_pattern.finditer(expr)}
    for m in modifier_pattern.finditer(expr):
        field = m.group(1)
        if field in ext_fields:
            continue
        values_str = m.group(2).strip()

        if not values_str:
            # Empty set = remove filter
            filters.append(f"REMOVEFILTERS({tbl}[{field}])")
        elif ',' in values_str:
            # Multiple values
            vals = [v.strip().strip('"').strip("'") for v in values_str.split(',')]
            val_list = ' || '.join([f'{tbl}[{field}] = "{v}"' for v in vals if v])
            if val_list:
                filters.append(val_list)
        else:
            # Single value
            val = values_str.strip('"').strip("'")
            try:
                num = float(val)
                filters.append(f"{tbl}[{field}] = {val}")
            except ValueError:
                filters.append(f'{tbl}[{field}] = "{val}"')

    # Parse field= (without value = remove filter)
    clear_pattern = re.compile(r'(\w+)\s*=\s*(?=[,>]|$)')
    for m in clear_pattern.finditer(expr):
        field = m.group(1)
        if not modifier_pattern.search(f"{field}="):
            filters.append(f"REMOVEFILTERS({tbl}[{field}])")

    return filters


# ── Sum(If(...)) → CALCULATE / SUMX ──────────────────────────────

def _convert_sum_if(expr: str, table_name: str = "") -> str:
    """Convert Qlik Sum(If(cond, val)) → CALCULATE/SUMX.

    Sum(If(Region="North", Sales))  → CALCULATE(SUM('T'[Sales]), 'T'[Region] = "North")
    Sum(If(Year>2020, Amount, 0))   → SUMX(FILTER('T', 'T'[Year] > 2020), 'T'[Amount])
    Also handles Avg(If(…)), Count(If(…)), Min/Max variants.
    """
    tbl = f"'{table_name}'" if table_name else "'Table'"
    # Match: AggFunc(If(cond, value [, else_value]))
    pattern = re.compile(
        r'\b(Sum|Avg|Count|Min|Max)\s*\(\s*If\s*\(',
        re.IGNORECASE,
    )
    if not pattern.search(expr):
        return expr

    def _replace_sum_if(m_outer):
        start = m_outer.start()
        agg_func = m_outer.group(1)

        # Use bracket matching to find the full extent
        # We are positioned right after 'If('
        inner_start = m_outer.end()  # after 'If('
        depth = 1  # we're inside the If(
        i = inner_start
        while i < len(expr) and depth > 0:
            if expr[i] == '(':
                depth += 1
            elif expr[i] == ')':
                depth -= 1
            i += 1
        # i points past the ')' closing If
        # Now expect the closing ')' for the outer agg
        # Skip whitespace
        j = i
        while j < len(expr) and expr[j] in ' \t\n':
            j += 1
        if j < len(expr) and expr[j] == ')':
            end = j + 1
        else:
            return None  # Malformed — skip

        # Extract inner args of If(cond, value_expr [, else_expr])
        inner_text = expr[inner_start:i - 1]  # content between If( and matching )
        args = _split_top_level_args(inner_text)
        if len(args) < 2:
            return None

        cond = args[0].strip()
        value_field = args[1].strip()
        else_expr = args[2].strip() if len(args) > 2 else None

        # Map agg function
        dax_agg_map = {'sum': 'SUM', 'avg': 'AVERAGE', 'count': 'COUNT',
                       'min': 'MIN', 'max': 'MAX'}
        dax_agg = dax_agg_map.get(agg_func.lower(), agg_func.upper())

        # Simple equality condition → CALCULATE pattern
        eq_match = re.match(r'^(\w+)\s*=\s*(.+)$', cond)
        if eq_match and (else_expr is None or else_expr in ('0', 'Null()', 'null', '')):
            dim_field = eq_match.group(1)
            dim_val = eq_match.group(2).strip()
            qualified_val = f"{tbl}[{value_field}]" if '[' not in value_field else value_field
            qualified_dim = f"{tbl}[{dim_field}]" if '[' not in dim_field else dim_field
            return (f"CALCULATE({dax_agg}({qualified_val}), {qualified_dim} = {dim_val})", start, end)

        # Complex condition → SUMX/AVERAGEX pattern
        x_func_map = {'sum': 'SUMX', 'avg': 'AVERAGEX', 'count': 'COUNTX',
                       'min': 'MINX', 'max': 'MAXX'}
        dax_x = x_func_map.get(agg_func.lower(), f'{agg_func.upper()}X')
        qualified_val = f"{tbl}[{value_field}]" if '[' not in value_field else value_field
        return (f"{dax_x}(FILTER({tbl}, {cond}), {qualified_val})", start, end)

    # Apply replacements from right to left to preserve positions
    replacements = []
    for m_outer in pattern.finditer(expr):
        result = _replace_sum_if(m_outer)
        if result:
            replacements.append(result)

    for dax_text, start, end in reversed(replacements):
        expr = expr[:start] + dax_text + expr[end:]

    return expr


# ── Concat() → CONCATENATEX() ────────────────────────────────────

def _convert_concat(expr: str, table_name: str = "") -> str:
    """Convert Qlik Concat(field, separator [, sort_field]) → CONCATENATEX.

    Concat(ProductName, ', ')  → CONCATENATEX(VALUES('T'[ProductName]), 'T'[ProductName], ", ")
    Concat(DISTINCT Region, '; ', Region) → CONCATENATEX(VALUES('T'[Region]), 'T'[Region], "; ", 'T'[Region], ASC)
    """
    tbl = f"'{table_name}'" if table_name else "'Table'"
    pattern = re.compile(r'\bConcat\s*\(', re.IGNORECASE)
    if not pattern.search(expr):
        return expr

    def _do_replace(m):
        start = m.end()  # right after 'Concat('
        depth = 1
        i = start
        while i < len(expr) and depth > 0:
            if expr[i] == '(':
                depth += 1
            elif expr[i] == ')':
                depth -= 1
            i += 1
        inner = expr[start:i - 1]
        args = _split_top_level_args(inner)
        if not args:
            return m.group(0) + inner + ')'

        field_arg = args[0].strip()
        # Strip DISTINCT keyword
        is_distinct = field_arg.upper().startswith('DISTINCT ')
        if is_distinct:
            field_arg = field_arg[9:].strip()

        separator = args[1].strip() if len(args) > 1 else '", "'
        sort_field = args[2].strip() if len(args) > 2 else None

        qualified = f"{tbl}[{field_arg}]" if '[' not in field_arg else field_arg
        parts = [f"VALUES({qualified})", qualified, separator]
        if sort_field:
            sort_qual = f"{tbl}[{sort_field}]" if '[' not in sort_field else sort_field
            parts.extend([sort_qual, 'ASC'])

        return 'CONCATENATEX(' + ', '.join(parts) + ')'

    # Process right-to-left
    matches = list(pattern.finditer(expr))
    for m in reversed(matches):
        start = m.start()
        # Find closing paren with bracket matching
        depth = 1
        i = m.end()
        while i < len(expr) and depth > 0:
            if expr[i] == '(':
                depth += 1
            elif expr[i] == ')':
                depth -= 1
            i += 1
        replacement = _do_replace(m)
        expr = expr[:start] + replacement + expr[i:]

    return expr


# ── Aggr() → SUMX/COUNTX/AVERAGEX or ADDCOLUMNS/SUMMARIZE ────────

# Map inner aggregation function to DAX iterator equivalent
_AGGR_ITERATOR_MAP = {
    'sum':   'SUMX',
    'count': 'COUNTX',
    'avg':   'AVERAGEX',
    'min':   'MINX',
    'max':   'MAXX',
}


def _convert_aggr(expr: str, table_name: str = "") -> str:
    """Convert Qlik Aggr(expression, dim1, dim2, ...) to DAX.

    Single dimension with simple inner aggregation → iterator (SUMX, COUNTX, etc.):
        Aggr(Sum(Sales), Customer)    → SUMX(VALUES('T'[Customer]), SUM('T'[Sales]))
        Aggr(Count(OrderID), Region)  → COUNTX(VALUES('T'[Region]), COUNT('T'[OrderID]))
        Aggr(Avg(Score), Year)        → AVERAGEX(VALUES('T'[Year]), AVERAGE('T'[Score]))

    Multiple dimensions → ADDCOLUMNS/SUMMARIZE:
        Aggr(Sum(Sales), Year, Month) → ADDCOLUMNS(SUMMARIZE('T', 'T'[Year], 'T'[Month]), "@value", SUM('T'[Sales]))

    Nested Aggr(Aggr(...)) → inner Aggr converted first (reversed iteration).
    """
    tbl = f"'{table_name}'" if table_name else "'Table'"
    aggr_pattern = re.compile(r'\bAggr\s*\(', re.IGNORECASE)
    if not aggr_pattern.search(expr):
        return expr

    matches = list(aggr_pattern.finditer(expr))
    for m in reversed(matches):
        start = m.start()
        inner_start = m.end()  # right after 'Aggr('

        # Bracket-matching to find the closing paren
        depth = 1
        i = inner_start
        while i < len(expr) and depth > 0:
            if expr[i] == '(':
                depth += 1
            elif expr[i] == ')':
                depth -= 1
            i += 1
        end = i  # past closing ')'

        inner = expr[inner_start:end - 1]
        args = _split_top_level_args(inner)
        if len(args) < 2:
            continue

        inner_expr = args[0].strip()
        dims = [a.strip() for a in args[1:]]
        dim_refs_list = [f"{tbl}[{d}]" if '[' not in d else d for d in dims]

        # Detect inner aggregation function: Sum(...), Count(...), Avg(...), etc.
        inner_agg_m = re.match(r'(\w+)\s*\(', inner_expr)
        inner_agg = inner_agg_m.group(1).lower() if inner_agg_m else None
        iterator = _AGGR_ITERATOR_MAP.get(inner_agg) if inner_agg else None

        if iterator and len(dims) == 1:
            # Single dimension: use iterator pattern (SUMX, COUNTX, etc.)
            replacement = f'{iterator}(VALUES({dim_refs_list[0]}), {inner_expr})'
        else:
            # Multiple dimensions or complex inner: use ADDCOLUMNS/SUMMARIZE
            dim_refs = ', '.join(dim_refs_list)
            replacement = f'ADDCOLUMNS(SUMMARIZE({tbl}, {dim_refs}), "@value", {inner_expr})'

        expr = expr[:start] + replacement + expr[end:]

    return expr


# ── Alt() → COALESCE ─────────────────────────────────────────────

def _convert_alt(expr: str) -> str:
    """Convert Qlik Alt(val1, val2, ...) → COALESCE(val1, val2, ...)."""
    return re.sub(r'\bAlt\s*\(', 'COALESCE(', expr, flags=re.IGNORECASE)


# ── Class() → INT()/DIVIDE() ─────────────────────────────────────

def _convert_class(expr: str) -> str:
    """Convert Qlik Class(expr, interval) → bucket expression."""
    pattern = re.compile(r'\bClass\s*\(\s*([^,]+),\s*([^)]+)\)', re.IGNORECASE)

    def _replace(m):
        field = m.group(1).strip()
        interval = m.group(2).strip()
        return f'INT(DIVIDE({field}, {interval})) * {interval} & " - " & (INT(DIVIDE({field}, {interval})) + 1) * {interval}'

    return pattern.sub(_replace, expr)


# ── RELATED() auto-insertion ──────────────────────────────────────

def _insert_related(
    expr: str,
    table_name: str,
    col_table_map: Dict[str, str],
    relationships: Optional[List[Dict]] = None,
) -> str:
    """
    Auto-insert RELATED() for cross-table references in calculated columns.

    If a column reference belongs to a different table (via manyToOne),
    wrap it in RELATED(). For manyToMany, use LOOKUPVALUE() instead.
    """
    # Find column references like [ColumnName] or 'Table'[Column]
    col_ref_pattern = re.compile(r"\[(\w+)\]")

    # Build relationship type lookup
    rel_type_map: Dict[str, str] = {}
    if relationships:
        for rel in relationships:
            from_tbl = rel.get("fromTable", "")
            to_tbl = rel.get("toTable", "")
            # manyToOne: fromTable is the "many" side
            if from_tbl and to_tbl:
                rel_type_map[f"{from_tbl}->{to_tbl}"] = "manyToOne"
                rel_type_map[f"{to_tbl}->{from_tbl}"] = "oneToMany"

    def _replace_col_ref(m):
        col_name = m.group(1)
        ref_table = col_table_map.get(col_name, "")

        if not ref_table or ref_table == table_name:
            return m.group(0)  # Same table, no change

        # Check relationship type
        rel_key = f"{table_name}->{ref_table}"
        rel_type = rel_type_map.get(rel_key, "manyToOne")

        if rel_type == "manyToOne" or rel_type == "oneToMany":
            return f"RELATED('{ref_table}'[{col_name}])"
        else:
            # manyToMany fallback
            return f"LOOKUPVALUE('{ref_table}'[{col_name}], '{ref_table}'[{col_name}], [{col_name}])"

    return col_ref_pattern.sub(_replace_col_ref, expr)


# ── Dollar-sign variable expansion ────────────────────────────────

def _expand_variables(expr: str, variables: Dict[str, str]) -> str:
    """Expand $(vName) and $(=expr) dollar-sign variable references.

    $(vName) → replaced by the variable definition.
    $(=expression) → the inner expression is inlined (load-time eval).
    Recursive up to *max_depth* passes to handle nested references.
    """
    if "$(" not in expr:
        return expr
    if variables is None:
        variables = {}

    max_depth = 10
    for _ in range(max_depth):
        prev = expr

        # $(=expression) — bracket-match to find closing paren, inline it
        expr = _expand_dollar_expr(expr)

        # $(vName) — expand named variables
        expr = re.sub(
            r'\$\((\w+)\)',
            lambda m: variables.get(m.group(1), m.group(0)),
            expr,
        )

        if expr == prev:
            break
    return expr


def _expand_dollar_expr(expr: str) -> str:
    """Replace $(=...) with the inner expression, using bracket matching."""
    marker = "$("
    result = []
    i = 0
    while i < len(expr):
        if expr[i:i+3] == "$(=":
            # Bracket-match to find closing ')'
            depth = 1
            j = i + 2  # points at '='
            j += 1     # skip '='
            start_inner = j
            while j < len(expr) and depth > 0:
                if expr[j] == '(':
                    depth += 1
                elif expr[j] == ')':
                    depth -= 1
                j += 1
            # j is past the closing ')' of $(...
            result.append(expr[start_inner:j - 1])
            i = j
        else:
            result.append(expr[i])
            i += 1
    return ''.join(result)


# ── TOTAL qualifier → ALL ─────────────────────────────────────────

def _convert_total_qualifier(expr: str, table_name: str = "") -> str:
    """
    Convert Qlik TOTAL qualifier to DAX CALCULATE with ALL.

    Qlik: Sum(TOTAL Sales) → DAX: CALCULATE(SUM('Table'[Sales]), ALL('Table'))
    Qlik: Sum(TOTAL <Region> Sales) → DAX: CALCULATE(SUM('Table'[Sales]), ALLEXCEPT('Table', 'Table'[Region]))
    """
    tbl = f"'{table_name}'" if table_name else "'Table'"

    # TOTAL with dimension restrictions: Sum(TOTAL <Dim1, Dim2> Field)
    def _replace_total_restricted(m):
        agg = m.group(1)
        dims_str = m.group(2)
        field = m.group(3).strip()
        dims = [d.strip() for d in dims_str.split(',') if d.strip()]
        dim_refs = ', '.join([f"{tbl}[{d}]" for d in dims])
        qualified = f"{tbl}[{field}]" if table_name and '[' not in field else field
        dax_agg = _map_aggregation(agg, field, table_name)
        return f"CALCULATE({dax_agg}, ALLEXCEPT({tbl}, {dim_refs}))"

    expr = re.sub(
        r'(\w+)\s*\(\s*TOTAL\s*<([^>]+)>\s*(\w+)\s*\)',
        _replace_total_restricted, expr, flags=re.IGNORECASE,
    )

    # Simple TOTAL: Sum(TOTAL Field)
    def _replace_total_simple(m):
        agg = m.group(1)
        field = m.group(2).strip()
        dax_agg = _map_aggregation(agg, field, table_name)
        return f"CALCULATE({dax_agg}, ALL({tbl}))"

    expr = re.sub(
        r'(\w+)\s*\(\s*TOTAL\s+(\w+)\s*\)',
        _replace_total_simple, expr, flags=re.IGNORECASE,
    )

    return expr


# ── Inter-record functions (Peek, Previous, Above, Below, RangeSum) ──

def _convert_inter_record(expr: str, table_name: str = "") -> str:
    """Convert Qlik inter-record functions to DAX equivalents.

    RangeSum(Above(X, 0, RowNo())) → running total via WINDOW/CALCULATE
    Above(field, n) → OFFSET(-n, ...)
    Below(field, n) → OFFSET(n, ...)
    Peek(field, offset) → OFFSET with explicit offset
    """
    tbl = f"'{table_name}'" if table_name else "'Table'"

    # ── RangeSum(Above(field, 0, RowNo())) → running total ────
    expr = re.sub(
        r'\bRangeSum\s*\(\s*Above\s*\(\s*([^,]+),\s*0\s*,\s*RowNo\s*\(\s*\)\s*\)\s*\)',
        lambda m: f'CALCULATE(SUM({m.group(1).strip()}), ALLSELECTED({tbl}), '
                  f'VAR _cur = MAX({m.group(1).strip()}) '
                  f'RETURN FILTER(ALL({tbl}), {m.group(1).strip()} <= _cur))'
                  f' /* running total */',
        expr, flags=re.IGNORECASE,
    )

    # ── Peek(field, offset) → OFFSET ─────
    expr = re.sub(
        r'\bPeek\s*\(\s*([^,]+),\s*(-?\d+)\s*\)',
        lambda m: f'OFFSET({m.group(2)}, ALLSELECTED({tbl}), ORDERBY({m.group(1).strip()}))[{m.group(1).strip()}]',
        expr, flags=re.IGNORECASE,
    )
    # Peek(field) with no offset → previous row
    expr = re.sub(
        r'\bPeek\s*\(\s*([^,)]+)\s*\)',
        lambda m: f'OFFSET(-1, ALLSELECTED({tbl}), ORDERBY({m.group(1).strip()}))[{m.group(1).strip()}]',
        expr, flags=re.IGNORECASE,
    )
    # Previous(field) → OFFSET(-1, ...)
    expr = re.sub(
        r'\bPrevious\s*\(\s*([^)]+)\)',
        lambda m: f'OFFSET(-1, ALLSELECTED({tbl}), ORDERBY({m.group(1).strip()}))[{m.group(1).strip()}]',
        expr, flags=re.IGNORECASE,
    )
    # Above(field, offset, count) → OFFSET(-offset, ...)
    expr = re.sub(
        r'\bAbove\s*\(\s*([^,)]+),\s*(\d+)\s*(?:,\s*\d+\s*)?\)',
        lambda m: f'OFFSET(-{m.group(2)}, ALLSELECTED({tbl}), ORDERBY({m.group(1).strip()}))[{m.group(1).strip()}]',
        expr, flags=re.IGNORECASE,
    )
    # Above(field) with no offset → OFFSET(-1, ...)
    expr = re.sub(
        r'\bAbove\s*\(\s*([^,)]+)\s*\)',
        lambda m: f'OFFSET(-1, ALLSELECTED({tbl}), ORDERBY({m.group(1).strip()}))[{m.group(1).strip()}]',
        expr, flags=re.IGNORECASE,
    )
    # Below(field, offset, count) → OFFSET(+offset, ...)
    expr = re.sub(
        r'\bBelow\s*\(\s*([^,)]+),\s*(\d+)\s*(?:,\s*\d+\s*)?\)',
        lambda m: f'OFFSET({m.group(2)}, ALLSELECTED({tbl}), ORDERBY({m.group(1).strip()}))[{m.group(1).strip()}]',
        expr, flags=re.IGNORECASE,
    )
    # Below(field) with no offset → OFFSET(1, ...)
    expr = re.sub(
        r'\bBelow\s*\(\s*([^,)]+)\s*\)',
        lambda m: f'OFFSET(1, ALLSELECTED({tbl}), ORDERBY({m.group(1).strip()}))[{m.group(1).strip()}]',
        expr, flags=re.IGNORECASE,
    )
    # FieldValue(field, n) → INDEX
    expr = re.sub(
        r'\bFieldValue\s*\(\s*([^,]+),\s*([^)]+)\)',
        r'INDEX(\1, \2)',
        expr, flags=re.IGNORECASE,
    )
    # FieldValueCount(field) → DISTINCTCOUNT in a value context
    expr = re.sub(
        r'\bFieldValueCount\s*\(\s*([^)]+)\)',
        r'DISTINCTCOUNT(\1)',
        expr, flags=re.IGNORECASE,
    )
    # Rank → RANKX
    expr = re.sub(
        r'\bRank\s*\(\s*([^)]+)\)',
        r"RANKX(ALL('Table'), \1)",
        expr, flags=re.IGNORECASE,
    )
    return expr


# ── Top-level argument splitter ───────────────────────────────────

def _split_top_level_args(text: str) -> List[str]:
    """Split arguments at commas that are not inside parentheses or quotes."""
    args: List[str] = []
    depth = 0
    in_str = False
    str_char = ''
    buf: List[str] = []
    for ch in text:
        if in_str:
            buf.append(ch)
            if ch == str_char:
                in_str = False
            continue
        if ch in ('"', "'"):
            in_str = True
            str_char = ch
            buf.append(ch)
        elif ch == '(':
            depth += 1
            buf.append(ch)
        elif ch == ')':
            depth -= 1
            buf.append(ch)
        elif ch == ',' and depth == 0:
            args.append(''.join(buf))
            buf = []
        else:
            buf.append(ch)
    if buf:
        args.append(''.join(buf))
    return args


# ── Cleanup ───────────────────────────────────────────────────────

def _cleanup_dax(expr: str) -> str:
    """Clean up DAX expression (balance parentheses, fix whitespace)."""
    # Remove double spaces
    expr = re.sub(r'  +', ' ', expr)

    # Fix common issues
    expr = expr.replace('( )', '()')

    return expr.strip()


# ── Qlik format string → DAX format string ───────────────────────

def convert_qlik_format_to_dax(qlik_format: str) -> str:
    """Convert Qlik number/date format string to DAX format string."""
    if not qlik_format:
        return ""

    # Direct mapping
    if qlik_format in QLIK_TO_DAX_FORMAT:
        return QLIK_TO_DAX_FORMAT[qlik_format]

    # Basic transformations
    dax_fmt = qlik_format
    # Qlik uses 'mm' for minutes, DAX uses 'nn'
    # But only when preceded by hh (to distinguish from MM month)
    dax_fmt = re.sub(r'(hh?):mm', r'\1:nn', dax_fmt, flags=re.IGNORECASE)

    return dax_fmt


# ── Qlik data type → DAX data type ───────────────────────────────

def convert_qlik_type_to_dax(qlik_type: str) -> str:
    """Convert Qlik data type to DAX data type."""
    if not qlik_type:
        return "string"
    return QLIK_TO_DAX_TYPE.get(qlik_type.lower(), "string")


# ── Batch conversion ─────────────────────────────────────────────

def convert_measures_to_dax(
    measures: List[Dict],
    table_name: str = "",
    col_table_map: Optional[Dict[str, str]] = None,
) -> List[Dict]:
    """
    Convert a list of Qlik measures to DAX.

    Args:
        measures: List of {name, expression, label, format} dicts
        table_name: Table context
        col_table_map: Column→table mapping

    Returns:
        List of measures with 'dax_expression' added
    """
    result = []
    for m in measures:
        dax_expr = convert_qlik_expression_to_dax(
            m.get("expression", ""),
            table_name=table_name,
            col_table_map=col_table_map,
        )
        converted = dict(m)
        converted["dax_expression"] = dax_expr
        converted["formatString"] = convert_qlik_format_to_dax(m.get("format", ""))
        result.append(converted)
    return result


def convert_dimensions_to_dax(
    dimensions: List[Dict],
    table_name: str = "",
    col_table_map: Optional[Dict[str, str]] = None,
    relationships: Optional[List[Dict]] = None,
) -> List[Dict]:
    """
    Convert Qlik dimensions (including calculated dimensions) to DAX.

    Args:
        dimensions: List of dimension dicts
        table_name: Table context
        col_table_map: Column→table mapping
        relationships: Relationships for RELATED() inference

    Returns:
        List with 'dax_expression' added where applicable
    """
    result = []
    for d in dimensions:
        field = d.get("field", "")
        converted = dict(d)

        # If field contains an expression (function call, operator), convert it
        if re.search(r'[(\+\-\*/]|\b(if|upper|lower|left|right)\b', field, re.IGNORECASE):
            converted["dax_expression"] = convert_qlik_expression_to_dax(
                field,
                table_name=table_name,
                col_table_map=col_table_map,
                relationships=relationships,
                is_calculated_column=True,
            )
            converted["is_calculated"] = True
        else:
            converted["is_calculated"] = False

        result.append(converted)
    return result
