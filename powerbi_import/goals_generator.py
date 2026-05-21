"""Goals generator — converts Qlik KPIs to Power BI Goals/Metrics.

Scans Qlik measures, KPI objects, and variables for KPI-like patterns
and generates Power BI Goals JSON (scorecard format).
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger('qlik_to_powerbi.goals_generator')

__all__ = [
    'PbiGoal', 'GoalsGenerator', 'generate_goals',
]

# Patterns that suggest a measure is a KPI
_KPI_PATTERNS = [
    re.compile(r'\btarget\b', re.IGNORECASE),
    re.compile(r'\bgoal\b', re.IGNORECASE),
    re.compile(r'\bkpi\b', re.IGNORECASE),
    re.compile(r'\bbenchmark\b', re.IGNORECASE),
    re.compile(r'\bthreshold\b', re.IGNORECASE),
    re.compile(r'\bbudget\b', re.IGNORECASE),
    re.compile(r'\bquota\b', re.IGNORECASE),
    re.compile(r'\bforecast\b', re.IGNORECASE),
    re.compile(r'\bsla\b', re.IGNORECASE),
    re.compile(r'\bperformance\b', re.IGNORECASE),
]

_STATUS_RULES_TEMPLATE = [
    {'value': 2, 'expression': '[Current] >= [Target]', 'label': 'On Track'},
    {'value': 1, 'expression': '[Current] >= [Target] * 0.8', 'label': 'At Risk'},
    {'value': 0, 'expression': 'true', 'label': 'Behind'},
]


@dataclass
class PbiGoal:
    """A Power BI Goal/Metric definition."""
    name: str
    description: str = ''
    current_measure: str = ''
    target_measure: str = ''
    current_dax: str = ''
    target_dax: str = ''
    owner: str = ''
    start_date: str = ''
    end_date: str = ''
    status_rules: List[Dict[str, Any]] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    source_type: str = ''  # 'kpi_object', 'measure_pair', 'variable'

    def __post_init__(self):
        if not self.status_rules:
            self.status_rules = list(_STATUS_RULES_TEMPLATE)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            'name': self.name,
            'description': self.description,
            'currentValue': {
                'measure': self.current_measure,
                'dax': self.current_dax,
            },
            'targetValue': {
                'measure': self.target_measure,
                'dax': self.target_dax,
            },
            'statusRules': self.status_rules,
        }
        if self.owner:
            d['owner'] = self.owner
        if self.start_date:
            d['startDate'] = self.start_date
        if self.end_date:
            d['endDate'] = self.end_date
        if self.tags:
            d['tags'] = self.tags
        if self.source_type:
            d['sourceType'] = self.source_type
        return d


class GoalsGenerator:
    """Generates Power BI Goals from Qlik KPI-like objects."""

    def __init__(self, app_name: str = ''):
        self.app_name = app_name
        self.goals: List[PbiGoal] = []

    def scan_measures(self, measures: List[Dict[str, Any]],
                      dax_map: Optional[Dict[str, str]] = None) -> List[PbiGoal]:
        """Scan measures for KPI-like patterns and create goal pairs."""
        dax_map = dax_map or {}
        measure_index: Dict[str, Dict] = {}
        for m in measures:
            name = m.get('name', '') or m.get('title', '')
            if name:
                measure_index[name.lower()] = m

        for m in measures:
            name = m.get('name', '') or m.get('title', '')
            expr = m.get('expression', '') or m.get('definition', '')
            if not name:
                continue

            # Check if this looks like a target/goal measure
            is_target = any(p.search(name) for p in _KPI_PATTERNS)
            if not is_target:
                continue

            # Try to find a matching "current" measure
            base_name = name
            for pattern in _KPI_PATTERNS:
                base_name = pattern.sub('', base_name).strip(' _-')

            current_measure = None
            for candidate_name in [base_name, f'{base_name} Actual',
                                   f'{base_name} Current', f'Actual {base_name}']:
                if candidate_name.lower() in measure_index:
                    current_measure = measure_index[candidate_name.lower()]
                    break

            if current_measure:
                current_name = current_measure.get('name', '') or current_measure.get('title', '')
                goal = PbiGoal(
                    name=base_name or name,
                    description=f'KPI: {base_name or name}',
                    current_measure=current_name,
                    target_measure=name,
                    current_dax=dax_map.get(current_name, ''),
                    target_dax=dax_map.get(name, ''),
                    source_type='measure_pair',
                    tags=['auto-detected'],
                )
                self.goals.append(goal)

        return self.goals

    def scan_kpi_objects(self, visualizations: List[Dict[str, Any]],
                        dax_map: Optional[Dict[str, str]] = None) -> List[PbiGoal]:
        """Scan Qlik KPI objects for goals."""
        dax_map = dax_map or {}
        for viz in visualizations:
            if not isinstance(viz, dict):
                continue
            vtype = (viz.get('type', '') or viz.get('visualization', '')).lower()
            if vtype not in ('kpi', 'gauge'):
                continue

            measures_list = viz.get('measures', []) or []
            if not measures_list:
                continue

            primary = measures_list[0] if measures_list else {}
            primary_name = primary.get('name', '') or primary.get('label', '') or 'KPI'
            primary_expr = primary.get('expression', '') or primary.get('definition', '')

            target_name = ''
            target_expr = ''
            if len(measures_list) > 1:
                target = measures_list[1]
                target_name = target.get('name', '') or target.get('label', '')
                target_expr = target.get('expression', '') or target.get('definition', '')

            goal = PbiGoal(
                name=primary_name,
                description=f'From Qlik {vtype} object',
                current_measure=primary_name,
                target_measure=target_name,
                current_dax=dax_map.get(primary_name, primary_expr),
                target_dax=dax_map.get(target_name, target_expr),
                source_type='kpi_object',
                tags=['qlik-kpi'],
            )
            self.goals.append(goal)

        return self.goals

    def scan_variables(self, variables: List[Dict[str, Any]]) -> List[PbiGoal]:
        """Scan Qlik variables for KPI-like patterns."""
        for var in variables:
            if not isinstance(var, dict):
                continue
            name = var.get('name', '') or var.get('qName', '')
            definition = var.get('definition', '') or var.get('qDefinition', '')
            if not name:
                continue

            is_kpi = any(p.search(name) for p in _KPI_PATTERNS)
            if not is_kpi:
                continue

            goal = PbiGoal(
                name=name,
                description=var.get('comment', '') or var.get('description', ''),
                current_measure=name,
                current_dax=definition,
                source_type='variable',
                tags=['qlik-variable'],
            )
            self.goals.append(goal)

        return self.goals

    def to_dict(self) -> Dict[str, Any]:
        return {
            'app_name': self.app_name,
            'created_at': datetime.now().isoformat(),
            'goals_count': len(self.goals),
            'goals': [g.to_dict() for g in self.goals],
        }

    def save(self, output_path: str) -> str:
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2)
        logger.info("Goals saved to %s (%d goals)", output_path, len(self.goals))
        return output_path


def generate_goals(app_name: str, qlik_data: Dict[str, Any],
                   dax_map: Optional[Dict[str, str]] = None,
                   output_path: Optional[str] = None) -> Dict[str, Any]:
    """Convenience function to generate goals from Qlik data."""
    gen = GoalsGenerator(app_name=app_name)
    gen.scan_measures(qlik_data.get('measures', []), dax_map)
    gen.scan_kpi_objects(qlik_data.get('visualizations', []), dax_map)
    gen.scan_variables(qlik_data.get('variables', []))

    result = gen.to_dict()
    if output_path:
        gen.save(output_path)
    return result
