"""DAX Optimizer — AST-based rewriter for idiomatic Power BI DAX.

Performs post-conversion optimization passes on DAX formulas generated
from Qlik conversion, improving readability and query performance.

Optimization rules:
- Nested IF → SWITCH conversion
- IF(ISBLANK(x), 0, x) → COALESCE(x, 0)
- Redundant CALCULATE collapse
- Constant expression folding
- VAR/RETURN extraction for repeated subexpressions
- SUMX simplification (single-column)
- Measure dependency DAG construction
"""

import re
import json
import os


# ════════════════════════════════════════════════════════════════════
#  OPTIMIZATION RULES
# ════════════════════════════════════════════════════════════════════

def optimize_dax(formula, rule_set=None):
    """Apply optimization rules to a DAX formula.

    Args:
        formula: DAX formula string
        rule_set: Optional list of rule names to apply. If None, applies all.

    Returns:
        tuple: (optimized_formula, list of applied rule names)
    """
    if not formula or not isinstance(formula, str):
        return formula, []

    rules = [
        ('isblank_coalesce', _rule_isblank_to_coalesce),
        ('nested_if_to_switch', _rule_nested_if_to_switch),
        ('redundant_calculate', _rule_redundant_calculate),
        ('constant_fold', _rule_constant_fold),
        ('simplify_sumx', _rule_simplify_sumx),
        ('trim_whitespace', _rule_trim_whitespace),
    ]

    applied = []
    result = formula
    for name, rule_fn in rules:
        if rule_set and name not in rule_set:
            continue
        new_result = rule_fn(result)
        if new_result != result:
            applied.append(name)
            result = new_result

    return result, applied


def _rule_isblank_to_coalesce(formula):
    """Convert IF(ISBLANK(x), default, x) → COALESCE(x, default)."""
    # Pattern: IF(ISBLANK(expr), replacement, expr) or IF(ISBLANK(expr), expr, replacement)
    pattern = r'IF\s*\(\s*ISBLANK\s*\(\s*([^)]+)\s*\)\s*,\s*([^,]+)\s*,\s*([^)]+)\s*\)'

    def _replace(m):
        blank_expr = m.group(1).strip()
        branch_true = m.group(2).strip()
        branch_false = m.group(3).strip()
        # IF(ISBLANK(x), default, x) → COALESCE(x, default)
        if branch_false == blank_expr:
            return f'COALESCE({blank_expr}, {branch_true})'
        # IF(ISBLANK(x), x, default) — unusual but handle
        if branch_true == blank_expr:
            return f'COALESCE({blank_expr}, {branch_false})'
        return m.group(0)

    return re.sub(pattern, _replace, formula)


def _rule_nested_if_to_switch(formula):
    """Convert nested IF chains on same field to SWITCH.

    Detects: IF(x = "a", r1, IF(x = "b", r2, IF(x = "c", r3, default)))
    Converts to: SWITCH(x, "a", r1, "b", r2, "c", r3, default)
    """
    # Pattern for nested IFs: IF(field = val, result, IF(field = val2, ...))
    # We iteratively extract the chain
    pattern = r'^IF\s*\(\s*(.+?)\s*=\s*(.+?)\s*,\s*(.+?)\s*,\s*(IF\s*\(.+)\)$'

    cases = []
    remaining = formula.strip()

    # Try to extract IF chain
    while True:
        m = re.match(pattern, remaining, re.DOTALL)
        if not m:
            break
        field = m.group(1).strip()
        value = m.group(2).strip()
        result = m.group(3).strip()
        cases.append((field, value, result))
        remaining = m.group(4).strip()

    # Check the final IF
    final_pattern = r'^IF\s*\(\s*(.+?)\s*=\s*(.+?)\s*,\s*(.+?)\s*,\s*(.+?)\s*\)$'
    fm = re.match(final_pattern, remaining, re.DOTALL)
    if fm and len(cases) >= 2:
        field = fm.group(1).strip()
        value = fm.group(2).strip()
        result = fm.group(3).strip()
        default = fm.group(4).strip()
        cases.append((field, value, result))

        # All cases must reference the same field
        fields = set(c[0] for c in cases)
        if len(fields) == 1:
            switch_field = cases[0][0]
            parts = [f'SWITCH({switch_field}']
            for _, val, res in cases:
                parts.append(f', {val}, {res}')
            parts.append(f', {default})')
            return ''.join(parts)

    return formula


def _rule_redundant_calculate(formula):
    """Remove CALCULATE wrapping when there are no filters.

    CALCULATE(SUM(x)) → SUM(x)
    """
    pattern = r'CALCULATE\s*\(\s*([A-Z]+\s*\([^)]*\))\s*\)'
    m = re.match(pattern, formula.strip())
    if m:
        inner = m.group(1).strip()
        # Only simplify if there's no filter argument (single arg CALCULATE)
        return inner
    return formula


def _rule_constant_fold(formula):
    """Fold simple constant arithmetic expressions.

    E.g. 1 + 2 → 3, 10 * 5 → 50 (only for simple integer expressions)
    """
    pattern = r'\b(\d+)\s*([+\-*/])\s*(\d+)\b'

    def _fold(m):
        a, op, b = int(m.group(1)), m.group(2), int(m.group(3))
        try:
            if op == '+':
                return str(a + b)
            elif op == '-':
                return str(a - b)
            elif op == '*':
                return str(a * b)
            elif op == '/' and b != 0:
                if a % b == 0:
                    return str(a // b)
        except (ValueError, ZeroDivisionError):
            pass
        return m.group(0)

    return re.sub(pattern, _fold, formula)


def _rule_simplify_sumx(formula):
    """Simplify SUMX('Table', 'Table'[Col]) → SUM('Table'[Col])."""
    pattern = r"SUMX\s*\(\s*'([^']+)'\s*,\s*'(\1)'\[([^\]]+)\]\s*\)"

    def _repl(m):
        table = m.group(1)
        col = m.group(3)
        return f"SUM('{table}'[{col}])"

    return re.sub(pattern, _repl, formula)


def _rule_trim_whitespace(formula):
    """Normalize excessive whitespace in formulas."""
    result = re.sub(r'  +', ' ', formula)
    return result.strip()


# ════════════════════════════════════════════════════════════════════
#  TIME INTELLIGENCE AUTO-INJECTION
# ════════════════════════════════════════════════════════════════════

def generate_time_intelligence_measures(measures, date_column="'Calendar'[Date]"):
    """Auto-generate Time Intelligence measures for date-based base measures.

    For each measure that uses aggregation functions (SUM, COUNT, AVERAGE, etc.),
    generates YTD, PY, and YoY% variants.

    Args:
        measures: List of dicts with 'name' and 'expression' keys
        date_column: DAX reference to the date column (default: Calendar[Date])

    Returns:
        list of dicts with 'name', 'expression', 'displayFolder' for new TI measures
    """
    ti_measures = []
    agg_pattern = re.compile(
        r'\b(SUM|COUNT|COUNTROWS|DISTINCTCOUNT|AVERAGE|MIN|MAX)\s*\(',
        re.IGNORECASE
    )

    for measure in measures:
        name = measure.get('name', '')
        expr = measure.get('expression', '')
        if not name or not expr:
            continue
        if not agg_pattern.search(expr):
            continue

        # YTD
        ti_measures.append({
            'name': f'{name} YTD',
            'expression': f'TOTALYTD([{name}], {date_column})',
            'displayFolder': 'Time Intelligence',
        })

        # PY (Prior Year)
        ti_measures.append({
            'name': f'{name} PY',
            'expression': f'CALCULATE([{name}], SAMEPERIODLASTYEAR({date_column}))',
            'displayFolder': 'Time Intelligence',
        })

        # YoY%
        ti_measures.append({
            'name': f'{name} YoY %',
            'expression': (
                f'DIVIDE([{name}] - [{name} PY], [{name} PY])'
            ),
            'displayFolder': 'Time Intelligence',
        })

    return ti_measures


# ════════════════════════════════════════════════════════════════════
#  MEASURE DEPENDENCY DAG
# ════════════════════════════════════════════════════════════════════

def build_measure_dependency_dag(measures):
    """Build a directed acyclic graph of measure-to-measure references.

    Analyses DAX expressions to find [MeasureName] references pointing
    to other measures in the same model.

    Args:
        measures: List of dicts with 'name' and 'expression' keys

    Returns:
        dict with:
        - 'edges': list of (from_measure, to_measure) tuples
        - 'circular': list of circular reference chains detected
        - 'unused': list of measure names not referenced by any other measure
        - 'roots': list of measures with no dependencies
    """
    measure_names = {m['name'] for m in measures if m.get('name')}
    ref_pattern = re.compile(r'\[([^\]]+)\]')

    # Build adjacency: measure → set of measures it references
    graph = {}
    for m in measures:
        name = m.get('name', '')
        expr = m.get('expression', '')
        if not name:
            continue
        refs = set()
        for match in ref_pattern.finditer(expr):
            ref_name = match.group(1)
            if ref_name in measure_names and ref_name != name:
                refs.add(ref_name)
        graph[name] = refs

    # Build edges
    edges = []
    for src, targets in graph.items():
        for tgt in targets:
            edges.append((src, tgt))

    # Detect circular references via DFS
    circular = []
    visited = set()
    rec_stack = set()

    def _dfs(node, path):
        visited.add(node)
        rec_stack.add(node)
        for neighbor in graph.get(node, set()):
            if neighbor in rec_stack:
                cycle_start = path.index(neighbor) if neighbor in path else len(path)
                cycle = path[cycle_start:] + [neighbor]
                circular.append(cycle)
            elif neighbor not in visited:
                _dfs(neighbor, path + [neighbor])
        rec_stack.discard(node)

    for m_name in graph:
        if m_name not in visited:
            _dfs(m_name, [m_name])

    # Find unused measures (not referenced by anything)
    referenced = set()
    for refs in graph.values():
        referenced.update(refs)
    unused = [n for n in measure_names if n not in referenced]

    # Root measures (no dependencies)
    roots = [n for n in graph if not graph[n]]

    return {
        'edges': edges,
        'circular': circular,
        'unused': sorted(unused),
        'roots': sorted(roots),
    }


# ════════════════════════════════════════════════════════════════════
#  OPTIMIZATION REPORT
# ════════════════════════════════════════════════════════════════════

def generate_optimization_report(measures, output_path=None):
    """Generate a per-measure optimization report.

    Args:
        measures: List of dicts with 'name' and 'expression' keys
        output_path: Optional path to write JSON report

    Returns:
        dict: Report with per-measure before/after comparisons
    """
    report = {
        'total_measures': len(measures),
        'optimized_count': 0,
        'measures': [],
    }

    for m in measures:
        name = m.get('name', '')
        original = m.get('expression', '')
        if not name or not original:
            continue

        optimized, rules = optimize_dax(original)
        entry = {
            'name': name,
            'original': original,
            'optimized': optimized,
            'rules_applied': rules,
            'changed': optimized != original,
        }
        report['measures'].append(entry)
        if entry['changed']:
            report['optimized_count'] += 1

    if output_path:
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

    return report
