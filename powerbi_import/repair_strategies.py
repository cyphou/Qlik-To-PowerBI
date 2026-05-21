"""Repair strategies for DAX/M/TMDL artifacts.

Provides a registry of deterministic (and optionally LLM-backed)
repair strategies that can be applied to artifacts with known issues.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger('qlik_to_powerbi.repair_strategies')

__all__ = ['RepairResult', 'RepairStrategy', 'RepairRegistry',
           'build_default_registry']


@dataclass
class RepairResult:
    """Outcome of a single repair attempt."""
    status: str  # 'repaired' | 'unchanged' | 'rejected' | 'error'
    artifact: str
    strategy: str
    issues_before: List[str] = field(default_factory=list)
    issues_after: List[str] = field(default_factory=list)
    notes: str = ''
    cost: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'status': self.status,
            'artifact': self.artifact,
            'strategy': self.strategy,
            'issues_before': self.issues_before,
            'issues_after': self.issues_after,
            'notes': self.notes,
            'cost': self.cost,
        }


class RepairStrategy:
    """A named repair strategy for a specific artifact type."""

    DETERMINISTIC = 'deterministic'
    LLM = 'llm'

    def __init__(self, name: str, fn: Callable, category: str = DETERMINISTIC,
                 applies_to: str = 'dax'):
        self.name = name
        self.fn = fn
        self.category = category
        self.applies_to = applies_to

    def attempt(self, artifact: str, issues: List[str],
                context: Optional[Dict] = None) -> RepairResult:
        try:
            result = self.fn(artifact, issues, context or {})
            if isinstance(result, RepairResult):
                return result
            if isinstance(result, str):
                if result != artifact:
                    return RepairResult(
                        status='repaired', artifact=result,
                        strategy=self.name,
                        issues_before=issues, issues_after=[],
                    )
                return RepairResult(
                    status='unchanged', artifact=artifact,
                    strategy=self.name,
                    issues_before=issues, issues_after=issues,
                )
            return RepairResult(
                status='unchanged', artifact=artifact,
                strategy=self.name,
                issues_before=issues, issues_after=issues,
                notes='Strategy returned unexpected type',
            )
        except Exception as e:
            return RepairResult(
                status='error', artifact=artifact,
                strategy=self.name,
                issues_before=issues,
                notes=str(e),
            )


class RepairRegistry:
    """Ordered collection of repair strategies."""

    def __init__(self, strategies: Optional[List[RepairStrategy]] = None):
        self._strategies: List[RepairStrategy] = list(strategies or [])

    def add(self, strategy: RepairStrategy) -> None:
        self._strategies.append(strategy)

    @property
    def strategies(self) -> List[RepairStrategy]:
        return list(self._strategies)

    def run(self, artifact: str, issues: List[str],
            context: Optional[Dict] = None, *,
            recovery_report=None,
            item_name: str = '') -> List[RepairResult]:
        results: List[RepairResult] = []
        current = artifact
        remaining_issues = list(issues)

        for strategy in self._strategies:
            if not remaining_issues:
                break
            result = strategy.attempt(current, remaining_issues, context)
            results.append(result)

            if result.status == 'repaired':
                current = result.artifact
                remaining_issues = result.issues_after
                if recovery_report is not None:
                    recovery_report.record(
                        'tmdl', f'repair_{strategy.name}',
                        item_name=item_name or 'artifact',
                        description=f'Applied repair: {strategy.name}',
                        action=result.notes or f'Repaired via {strategy.name}',
                        severity='info',
                    )

        return results


# ── Built-in repair functions ────────────────────────────────────

def _repair_qlik_leak(artifact: str, issues: List[str],
                       context: Dict) -> str:
    """Remove common Qlik function leaks from DAX expressions."""
    result = artifact
    replacements = {
        r'\bAGGR\s*\(': 'SUMX(',
        r'\bALT\s*\(': 'COALESCE(',
        r'\bONLY\s*\(': 'SELECTEDVALUE(',
        r'\bPEEK\s*\(': 'OFFSET(',
        r'\bPREVIOUS\s*\(': 'OFFSET(',
        r'\bMatch\s*\(': 'SWITCH(TRUE(),',
        r'\bWildMatch\s*\(': 'SWITCH(TRUE(),',
        r'\bPick\s*\(': 'SWITCH(',
        r'\bDual\s*\(': 'VALUE(',
    }
    for pattern, replacement in replacements.items():
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    return result


def _repair_paren_balance(artifact: str, issues: List[str],
                          context: Dict) -> str:
    """Attempt to fix unbalanced parentheses."""
    opens = artifact.count('(')
    closes = artifact.count(')')
    if opens > closes:
        return artifact + ')' * (opens - closes)
    if closes > opens:
        return '(' * (closes - opens) + artifact
    return artifact


def _repair_empty_measure(artifact: str, issues: List[str],
                          context: Dict) -> str:
    """Replace empty or whitespace-only measure with BLANK()."""
    if not artifact or not artifact.strip():
        return 'BLANK()'
    return artifact


def _repair_m_if_else(artifact: str, issues: List[str],
                      context: Dict) -> str:
    """Add missing else clauses to M if/then expressions."""
    result = artifact
    ifs = len(re.findall(r'\bif\b', result, re.IGNORECASE))
    elses = len(re.findall(r'\belse\b', result, re.IGNORECASE))
    while ifs > elses:
        result = result.rstrip() + ' else null'
        elses += 1
    return result


def _repair_single_quotes_m(artifact: str, issues: List[str],
                             context: Dict) -> str:
    """Replace single quotes with double quotes in M set literals."""
    def _fix_set(match):
        content = match.group(0)
        return content.replace("'", '"')
    return re.sub(r"\{[^}]*'[^']*'[^}]*\}", _fix_set, artifact)


def build_default_registry() -> RepairRegistry:
    """Build the default repair registry with built-in strategies."""
    registry = RepairRegistry()
    registry.add(RepairStrategy('qlik_leak_removal', _repair_qlik_leak,
                                RepairStrategy.DETERMINISTIC, 'dax'))
    registry.add(RepairStrategy('paren_balance', _repair_paren_balance,
                                RepairStrategy.DETERMINISTIC, 'dax'))
    registry.add(RepairStrategy('empty_measure', _repair_empty_measure,
                                RepairStrategy.DETERMINISTIC, 'dax'))
    registry.add(RepairStrategy('m_if_else', _repair_m_if_else,
                                RepairStrategy.DETERMINISTIC, 'm_query'))
    registry.add(RepairStrategy('m_single_quotes', _repair_single_quotes_m,
                                RepairStrategy.DETERMINISTIC, 'm_query'))
    return registry
