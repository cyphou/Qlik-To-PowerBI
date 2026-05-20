"""Migration planner — enterprise planning for Qlik-to-Power BI migrations.

Provides weighted effort estimation, dependency-cluster wave assignment,
workspace mapping, and permission mapping for portfolio-scale migrations.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class AppAssessment:
    """Assessment for a single Qlik app."""
    app_name: str
    visual_count: int = 0
    measure_count: int = 0
    connector_count: int = 0
    has_rls: bool = False
    has_custom_sql: bool = False
    complexity: str = 'low'       # low/medium/high/critical
    effort_hours: float = 0.0
    wave: int = 0
    workspace: str = ''
    dependencies: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'app_name': self.app_name,
            'visual_count': self.visual_count,
            'measure_count': self.measure_count,
            'connector_count': self.connector_count,
            'has_rls': self.has_rls,
            'has_custom_sql': self.has_custom_sql,
            'complexity': self.complexity,
            'effort_hours': self.effort_hours,
            'wave': self.wave,
            'workspace': self.workspace,
            'dependencies': self.dependencies,
        }


@dataclass
class MigrationPlan:
    """Aggregated migration plan for a portfolio."""
    apps: List[AppAssessment] = field(default_factory=list)
    total_effort_hours: float = 0.0
    wave_count: int = 0
    workspace_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'total_apps': len(self.apps),
            'total_effort_hours': self.total_effort_hours,
            'wave_count': self.wave_count,
            'workspace_count': self.workspace_count,
            'apps': [a.to_dict() for a in self.apps],
        }


# ── Effort estimation ────────────────────────────────────────────

_VISUAL_WEIGHT = 0.15      # hours per visual
_MEASURE_WEIGHT = 0.25     # hours per measure
_CONNECTOR_WEIGHT = 1.0    # hours per connector type
_RLS_PENALTY = 4.0         # extra hours for RLS
_CUSTOM_SQL_PENALTY = 2.0  # extra hours for custom SQL
_BASE_EFFORT = 2.0         # base overhead per app


def estimate_effort(visual_count: int, measure_count: int,
                    connector_count: int, has_rls: bool = False,
                    has_custom_sql: bool = False) -> float:
    """Estimate migration effort in hours."""
    effort = _BASE_EFFORT
    effort += visual_count * _VISUAL_WEIGHT
    effort += measure_count * _MEASURE_WEIGHT
    effort += connector_count * _CONNECTOR_WEIGHT
    if has_rls:
        effort += _RLS_PENALTY
    if has_custom_sql:
        effort += _CUSTOM_SQL_PENALTY
    return round(effort, 1)


def classify_complexity(visual_count: int, measure_count: int,
                        connector_count: int, has_rls: bool = False,
                        has_custom_sql: bool = False) -> str:
    """Classify app complexity as low/medium/high/critical."""
    score = visual_count + measure_count * 2 + connector_count * 5
    if has_rls:
        score += 20
    if has_custom_sql:
        score += 10

    if score <= 20:
        return 'low'
    elif score <= 60:
        return 'medium'
    elif score <= 120:
        return 'high'
    return 'critical'


# ── Wave assignment ──────────────────────────────────────────────

def assign_waves(apps: List[AppAssessment],
                 max_per_wave: int = 10) -> List[AppAssessment]:
    """Assign apps to migration waves based on complexity.

    Strategy: simplest first (low → medium → high → critical),
    with a max number of apps per wave.
    """
    complexity_order = {'low': 0, 'medium': 1, 'high': 2, 'critical': 3}
    sorted_apps = sorted(
        apps,
        key=lambda a: complexity_order.get(a.complexity, 99)
    )

    wave = 1
    count = 0
    for app in sorted_apps:
        if count >= max_per_wave:
            wave += 1
            count = 0
        app.wave = wave
        count += 1

    return sorted_apps


# ── Workspace mapping ────────────────────────────────────────────

def map_workspaces(apps: List[AppAssessment],
                   strategy: str = 'one_per_app') -> List[AppAssessment]:
    """Assign workspace names to apps.

    Strategies:
        - 'one_per_app': Each app gets its own workspace
        - 'by_wave': Apps in the same wave share a workspace
        - 'single': All apps go to one workspace
    """
    if strategy == 'single':
        for app in apps:
            app.workspace = 'Migrated_Qlik_Apps'
    elif strategy == 'by_wave':
        for app in apps:
            app.workspace = f'Migration_Wave_{app.wave}'
    else:  # one_per_app
        for app in apps:
            safe_name = app.app_name.replace(' ', '_')[:50]
            app.workspace = f'PBI_{safe_name}'
    return apps


# ── Plan builder ─────────────────────────────────────────────────

def build_migration_plan(
    app_metadata_list: List[Dict[str, Any]],
    max_per_wave: int = 10,
    workspace_strategy: str = 'one_per_app',
) -> MigrationPlan:
    """Build a complete migration plan from app metadata.

    Args:
        app_metadata_list: List of dicts with keys like 'app_name',
            'visual_count', 'measure_count', 'connector_count',
            'has_rls', 'has_custom_sql', 'dependencies'.
        max_per_wave: Max apps per migration wave.
        workspace_strategy: 'one_per_app', 'by_wave', or 'single'.
    """
    assessments = []
    for meta in app_metadata_list:
        vc = meta.get('visual_count', 0)
        mc = meta.get('measure_count', 0)
        cc = meta.get('connector_count', 0)
        rls = meta.get('has_rls', False)
        csql = meta.get('has_custom_sql', False)

        assessment = AppAssessment(
            app_name=meta.get('app_name', 'Unknown'),
            visual_count=vc,
            measure_count=mc,
            connector_count=cc,
            has_rls=rls,
            has_custom_sql=csql,
            complexity=classify_complexity(vc, mc, cc, rls, csql),
            effort_hours=estimate_effort(vc, mc, cc, rls, csql),
            dependencies=meta.get('dependencies', []),
        )
        assessments.append(assessment)

    assessments = assign_waves(assessments, max_per_wave)
    assessments = map_workspaces(assessments, workspace_strategy)

    plan = MigrationPlan(
        apps=assessments,
        total_effort_hours=sum(a.effort_hours for a in assessments),
        wave_count=max((a.wave for a in assessments), default=0),
        workspace_count=len({a.workspace for a in assessments}),
    )

    return plan
