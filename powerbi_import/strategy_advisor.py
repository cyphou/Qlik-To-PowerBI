"""
Migration Strategy Advisor for Qlik → Power BI.

Automatically recommends the optimal data-loading approach — **Import Mode**
(Power Query M), **DirectQuery**, or **Composite** — based on Qlik app
characteristics extracted from the source file.

Decision signals
~~~~~~~~~~~~~~~~
+--------------------------------------+--------+-------------+
| Signal                               | Import | DirectQuery |
+--------------------------------------+--------+-------------+
| Simple connectors (SQL, Excel…)      | ✓      |             |
| Complex connectors (BigQuery…)       |        | ✓           |
| Few tables (≤ 5)                     | ✓      |             |
| Many tables (> 5)                    |        | ✓           |
| Few columns (≤ 50 total)            | ✓      |             |
| Many columns (> 50)                 |        | ✓           |
| No Custom SQL                        | ✓      |             |
| Custom SQL present                   |        | ✓           |
| Simple calcs only                    | ✓      |             |
| Set Analysis / Aggr / dollar-sign    |        | ✓           |
| Few calculated columns (≤ 10)       | ✓      |             |
| Many calculated columns (> 10)      |        | ✓           |
| Stacked LOADs / Section Access       |        | ✓           |
+--------------------------------------+--------+-------------+

Scoring
~~~~~~~
Each signal awards points to either ``import_mode`` or ``directquery``.
The strategy with the higher score wins.  When scores are close
(within a configurable margin), **composite** model is recommended.

Usage (CLI)::

    python migrate.py my_app.qvf --assess

Usage (programmatic)::

    from powerbi_import.strategy_advisor import recommend_strategy
    rec = recommend_strategy(extracted_data)
    print(rec.summary)
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Connector classification ────────────────────────────────────────

# Connectors that Power Query M handles well → favour Import Mode
_PQ_FRIENDLY_CONNECTORS = frozenset({
    'Excel', 'CSV', 'SQL Server', 'PostgreSQL', 'MySQL',
    'GeoJSON', 'OData', 'Azure Blob', 'ADLS',
})

# Connectors better suited for DirectQuery / live connection
_DQ_FRIENDLY_CONNECTORS = frozenset({
    'BigQuery', 'Oracle', 'SAP BW', 'Snowflake',
    'Google Analytics',
})

# Qlik complex formula patterns — set analysis, Aggr, dollar-sign, inter-record
_COMPLEX_FORMULA_PATTERN = re.compile(
    r'\{\s*<'                                # Set Analysis {<...>}
    r'|\bAggr\s*\('                           # Aggr() nesting
    r'|\$\(\s*='                               # Dollar-sign expression $(=...)
    r'|\bTOTAL\b'                              # TOTAL qualifier
    r'|\bPeek\s*\('                            # Peek() inter-record
    r'|\bPrevious\s*\('                        # Previous() inter-record
    r'|\bAbove\s*\('                           # Above() inter-record
    r'|\bBelow\s*\('                           # Below() inter-record
    r'|\bRangeSum\s*\(',                       # RangeSum running totals
    re.IGNORECASE,
)

# Section Access pattern — indicates RLS complexity
_SECTION_ACCESS_PATTERN = re.compile(
    r'Section\s+Access', re.IGNORECASE,
)

# Qlik aggregation detection
_AGG_PATTERN = re.compile(
    r'\b(Sum|Count|CountDistinct|Avg|Min|Max|Median|Stdev|Only|'
    r'Mode|Fractile|Correl|Skew|FirstSortedValue|Concat|'
    r'RangeSum|RangeAvg|RangeCount|RangeMin|RangeMax|RangeStdev|'
    r'Rank|NumericCount|NullCount|MissingCount|TextCount)\s*\(',
    re.IGNORECASE,
)


# ── Scoring thresholds ──────────────────────────────────────────────

TABLE_THRESHOLD = 5        # ≤ 5 → import, > 5 → directquery
COLUMN_THRESHOLD = 50      # ≤ 50 → import, > 50 → directquery
CALC_COL_THRESHOLD = 10    # ≤ 10 → import, > 10 → directquery
MARGIN = 2                 # score gap ≤ margin → recommend composite


# ── Calculation classification ──────────────────────────────────────

def _classify_calculations(calculations):
    """Split source calculations into calculated columns vs measures.

    Returns (calc_columns, measures) — two lists.
    """
    calc_columns = []
    measures = []

    for calc in calculations:
        formula = calc.get('formula', '').strip()
        if not formula:
            continue

        role = calc.get('role', 'measure')
        is_literal = '[' not in formula
        has_aggregation = bool(_AGG_PATTERN.search(formula))

        is_calc_col = (not is_literal) and (
            role == 'dimension' or not has_aggregation
        )

        if is_calc_col:
            calc_columns.append(calc)
        else:
            measures.append(calc)

    return calc_columns, measures


# ── Data classes ────────────────────────────────────────────────────

@dataclass
class StrategySignal:
    """A single decision signal contributing to the recommendation."""
    name: str
    description: str
    favours: str            # 'import' | 'directquery'
    weight: int = 1         # how many score points this signal awards


@dataclass
class StrategyRecommendation:
    """Result of the strategy analysis."""
    strategy: str                       # 'import' | 'directquery' | 'composite'
    import_score: int = 0
    directquery_score: int = 0
    signals: List[StrategySignal] = field(default_factory=list)
    summary: str = ''

    @property
    def connection_mode(self) -> str:
        """Return the recommended Power BI connection mode."""
        return {
            'import': 'Import',
            'directquery': 'DirectQuery',
            'composite': 'Composite (Import + DirectQuery)',
        }.get(self.strategy, 'Import')


# ── Main advisor function ──────────────────────────────────────────

def recommend_strategy(
    extracted: Dict,
    *,
    prep_flow: bool = False,
    table_threshold: int = TABLE_THRESHOLD,
    column_threshold: int = COLUMN_THRESHOLD,
    calc_col_threshold: int = CALC_COL_THRESHOLD,
    margin: int = MARGIN,
) -> StrategyRecommendation:
    """Analyse extracted source data and recommend a data-loading strategy.

    Args:
        extracted: dict loaded by ``PowerBIImporter._load_converted_objects()``
                   — must contain ``datasources``, ``calculations``,
                   ``custom_sql`` keys (others optional).
        prep_flow: True if a Prep flow is being merged.
        table_threshold: Tables above this favour DirectQuery.
        column_threshold: Columns above this favour DirectQuery.
        calc_col_threshold: Calculated columns above this favour DirectQuery.
        margin: When ``|import_score − directquery_score| ≤ margin``,
                recommend *composite*.

    Returns:
        ``StrategyRecommendation`` with strategy, scores, and signals.
    """
    signals: List[StrategySignal] = []

    datasources = extracted.get('datasources', [])
    calculations = extracted.get('calculations', [])
    custom_sql = extracted.get('custom_sql', [])

    # ── 1. Connector analysis ───────────────────────────────────
    connector_types = set()
    for ds in datasources:
        conn = ds.get('connection', {})
        conn_type = conn.get('type', 'Unknown')
        connector_types.add(conn_type)

    pq_count = len(connector_types & _PQ_FRIENDLY_CONNECTORS)
    dq_count = len(connector_types & _DQ_FRIENDLY_CONNECTORS)

    if pq_count > 0 and dq_count == 0:
        signals.append(StrategySignal(
            'connectors_simple',
            f'All connectors Power Query-friendly ({", ".join(sorted(connector_types & _PQ_FRIENDLY_CONNECTORS))})',
            'import', weight=2,
        ))
    elif dq_count > 0:
        signals.append(StrategySignal(
            'connectors_complex',
            f'Complex connectors present ({", ".join(sorted(connector_types & _DQ_FRIENDLY_CONNECTORS))})',
            'directquery', weight=2,
        ))

    # ── 2. Table count ──────────────────────────────────────────
    total_tables = sum(len(ds.get('tables', [])) for ds in datasources)
    if total_tables <= table_threshold:
        signals.append(StrategySignal(
            'few_tables',
            f'{total_tables} table(s) — small dataset',
            'import',
        ))
    else:
        signals.append(StrategySignal(
            'many_tables',
            f'{total_tables} table(s) — large dataset',
            'directquery',
        ))

    # ── 3. Column count ─────────────────────────────────────────
    total_columns = 0
    for ds in datasources:
        for tbl in ds.get('tables', []):
            total_columns += len(tbl.get('columns', []))
        total_columns += len(ds.get('columns', []))

    if total_columns <= column_threshold:
        signals.append(StrategySignal(
            'few_columns',
            f'{total_columns} column(s) — manageable schema',
            'import',
        ))
    else:
        signals.append(StrategySignal(
            'many_columns',
            f'{total_columns} column(s) — wide schema',
            'directquery',
        ))

    # ── 4. Custom SQL ───────────────────────────────────────────
    if custom_sql:
        signals.append(StrategySignal(
            'custom_sql',
            f'{len(custom_sql)} custom SQL query/queries',
            'directquery', weight=2,
        ))
    else:
        signals.append(StrategySignal(
            'no_custom_sql',
            'No custom SQL',
            'import',
        ))

    # ── 5. Calculation complexity ───────────────────────────────
    complex_calc_count = 0

    calc_columns, measures = _classify_calculations(calculations)
    calc_col_count = len(calc_columns)

    for calc in calculations:
        formula = calc.get('formula', '')
        if _COMPLEX_FORMULA_PATTERN.search(formula):
            complex_calc_count += 1

    if complex_calc_count == 0:
        signals.append(StrategySignal(
            'simple_calcs',
            'All calculations are simple (no Set Analysis/Aggr/dollar-sign)',
            'import',
        ))
    else:
        parts = []
        if complex_calc_count:
            parts.append(f'{complex_calc_count} Set Analysis/Aggr/dollar-sign calc(s)')
        signals.append(StrategySignal(
            'complex_calcs',
            f'Complex calculations: {", ".join(parts)}',
            'directquery', weight=2,
        ))

    # ── 6. Calculated column volume ─────────────────────────────
    if calc_col_count <= calc_col_threshold:
        signals.append(StrategySignal(
            'few_calc_cols',
            f'{calc_col_count} calculated column(s)',
            'import',
        ))
    else:
        signals.append(StrategySignal(
            'many_calc_cols',
            f'{calc_col_count} calculated column(s) — heavy materialisation',
            'directquery',
        ))

    # ── 7. Prep flow ────────────────────────────────────────────
    if prep_flow:
        signals.append(StrategySignal(
            'prep_flow',
            'Prep flow transforms present',
            'directquery', weight=2,
        ))

    # ── Scoring ─────────────────────────────────────────────────
    imp_score = sum(s.weight for s in signals if s.favours == 'import')
    dq_score = sum(s.weight for s in signals if s.favours == 'directquery')

    gap = abs(imp_score - dq_score)
    if gap <= margin:
        strategy = 'composite'
    elif imp_score > dq_score:
        strategy = 'import'
    else:
        strategy = 'directquery'

    # ── Summary ─────────────────────────────────────────────────
    strategy_label = {
        'import': 'Import Mode (Power Query M)',
        'directquery': 'DirectQuery',
        'composite': 'Composite Model (Import + DirectQuery)',
    }
    summary_lines = [
        f'Recommended strategy: {strategy_label[strategy]}',
        f'  Import score: {imp_score}   DirectQuery score: {dq_score}',
        '',
        '  Signals:',
    ]
    for s in signals:
        arrow = '→ Import' if s.favours == 'import' else '→ DirectQuery'
        summary_lines.append(f'    [{arrow:>15}] {s.description} (weight={s.weight})')

    summary = '\n'.join(summary_lines)

    recommendation = StrategyRecommendation(
        strategy=strategy,
        import_score=imp_score,
        directquery_score=dq_score,
        signals=signals,
        summary=summary,
    )

    logger.info('Strategy recommendation: %s (Import=%d DQ=%d)',
                strategy, imp_score, dq_score)

    return recommendation


def print_recommendation(rec: StrategyRecommendation) -> None:
    """Pretty-print the strategy recommendation to stdout."""
    print()
    print('┌' + '─' * 68 + '┐')
    print('│' + ' MIGRATION STRATEGY RECOMMENDATION'.center(68) + '│')
    print('├' + '─' * 68 + '┤')
    print(f'│  Strategy:  {rec.strategy.upper():<54} │')
    print(f'│  Import score: {rec.import_score:<6}  '
          f'DirectQuery score: {rec.directquery_score:<19} │')
    print('├' + '─' * 68 + '┤')
    for s in rec.signals:
        arrow = 'IMP' if s.favours == 'import' else 'DQ'
        line = f'  [{arrow}] {s.description}'
        if s.weight > 1:
            line += f' (x{s.weight})'
        # Truncate long lines for the box
        if len(line) > 66:
            line = line[:63] + '...'
        print(f'│{line:<68}│')
    print('├' + '─' * 68 + '┤')
    mode_str = rec.connection_mode
    print(f'│  Connection Mode: {mode_str:<48} │')
    print('└' + '─' * 68 + '┘')
    print()
