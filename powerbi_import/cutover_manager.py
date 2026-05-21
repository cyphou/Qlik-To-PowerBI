"""Cutover manager — orchestrates the migration cutover process.

Provides a structured approach to transitioning from Qlik to Power BI,
tracking readiness checks, managing parallel-run periods, and generating
cutover runbooks.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger('qlik_to_powerbi.cutover_manager')

__all__ = [
    'CutoverPlan', 'CutoverStep', 'CutoverManager',
    'ReadinessCheck', 'ReadinessResult',
]


@dataclass
class ReadinessCheck:
    """A single readiness check for cutover."""
    name: str
    category: str  # 'data', 'visual', 'security', 'performance', 'governance'
    description: str = ''
    required: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'category': self.category,
            'description': self.description,
            'required': self.required,
        }


@dataclass
class ReadinessResult:
    """Result of evaluating a readiness check."""
    check_name: str
    passed: bool
    detail: str = ''
    severity: str = 'info'  # 'info', 'warning', 'error'

    def to_dict(self) -> Dict[str, Any]:
        return {
            'check_name': self.check_name,
            'passed': self.passed,
            'detail': self.detail,
            'severity': self.severity,
        }


@dataclass
class CutoverStep:
    """A step in the cutover plan."""
    order: int
    name: str
    description: str = ''
    owner: str = ''
    status: str = 'pending'  # 'pending', 'in_progress', 'completed', 'skipped', 'failed'
    notes: str = ''
    duration_minutes: int = 0
    dependencies: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'order': self.order,
            'name': self.name,
            'description': self.description,
            'owner': self.owner,
            'status': self.status,
            'notes': self.notes,
            'duration_minutes': self.duration_minutes,
            'dependencies': self.dependencies,
        }


@dataclass
class CutoverPlan:
    """Full cutover plan with steps and readiness checks."""
    app_name: str
    created_at: str = ''
    steps: List[CutoverStep] = field(default_factory=list)
    readiness_results: List[ReadinessResult] = field(default_factory=list)
    parallel_run_days: int = 14
    rollback_plan: str = ''
    status: str = 'draft'  # 'draft', 'ready', 'in_progress', 'completed', 'rolled_back'

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

    @property
    def ready(self) -> bool:
        required = [r for r in self.readiness_results if
                    any(c.required for c in _DEFAULT_CHECKS if c.name == r.check_name)]
        return all(r.passed for r in required) if required else False

    @property
    def total_duration_minutes(self) -> int:
        return sum(s.duration_minutes for s in self.steps)

    @property
    def completed_steps(self) -> int:
        return sum(1 for s in self.steps if s.status == 'completed')

    def to_dict(self) -> Dict[str, Any]:
        return {
            'app_name': self.app_name,
            'created_at': self.created_at,
            'status': self.status,
            'parallel_run_days': self.parallel_run_days,
            'rollback_plan': self.rollback_plan,
            'total_duration_minutes': self.total_duration_minutes,
            'completed_steps': self.completed_steps,
            'total_steps': len(self.steps),
            'ready': self.ready,
            'steps': [s.to_dict() for s in self.steps],
            'readiness_results': [r.to_dict() for r in self.readiness_results],
        }

    def save(self, output_path: str) -> str:
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2)
        logger.info("Cutover plan saved to %s", output_path)
        return output_path


# ── Default readiness checks ────────────────────────────────────

_DEFAULT_CHECKS: List[ReadinessCheck] = [
    ReadinessCheck('data_validation', 'data',
                   'All data sources connected and refreshable', True),
    ReadinessCheck('measure_parity', 'data',
                   'All measures produce matching values', True),
    ReadinessCheck('visual_fidelity', 'visual',
                   'Visual output matches Qlik within acceptable tolerance', True),
    ReadinessCheck('rls_configured', 'security',
                   'Row-level security roles configured', False),
    ReadinessCheck('performance_baseline', 'performance',
                   'Report load time within SLA', False),
    ReadinessCheck('governance_review', 'governance',
                   'Naming conventions and PII checks passed', False),
    ReadinessCheck('user_acceptance', 'visual',
                   'Key stakeholders have approved the migration', True),
    ReadinessCheck('refresh_schedule', 'data',
                   'Data refresh schedule configured', False),
    ReadinessCheck('gateway_configured', 'data',
                   'On-premises gateway configured (if applicable)', False),
    ReadinessCheck('workspace_permissions', 'security',
                   'Workspace permissions assigned', True),
]

# ── Default cutover steps ────────────────────────────────────────

_DEFAULT_STEPS: List[Dict[str, Any]] = [
    {'order': 1, 'name': 'Pre-cutover validation',
     'description': 'Run all readiness checks', 'duration_minutes': 30},
    {'order': 2, 'name': 'Deploy to production workspace',
     'description': 'Publish .pbip to production Power BI workspace',
     'duration_minutes': 15, 'dependencies': ['Pre-cutover validation']},
    {'order': 3, 'name': 'Configure data refresh',
     'description': 'Set up scheduled refresh and gateway bindings',
     'duration_minutes': 20, 'dependencies': ['Deploy to production workspace']},
    {'order': 4, 'name': 'Parallel run start',
     'description': 'Both Qlik and Power BI reports available to users',
     'duration_minutes': 5, 'dependencies': ['Configure data refresh']},
    {'order': 5, 'name': 'User validation',
     'description': 'Key users validate data accuracy in parallel',
     'duration_minutes': 60, 'dependencies': ['Parallel run start']},
    {'order': 6, 'name': 'Qlik decommission',
     'description': 'Disable Qlik app access, redirect users to Power BI',
     'duration_minutes': 15, 'dependencies': ['User validation']},
    {'order': 7, 'name': 'Post-cutover monitoring',
     'description': 'Monitor usage and performance for regression',
     'duration_minutes': 30, 'dependencies': ['Qlik decommission']},
]


class CutoverManager:
    """Manages the cutover lifecycle for a Qlik-to-Power-BI migration."""

    def __init__(self):
        self.checks = list(_DEFAULT_CHECKS)

    def create_plan(self, app_name: str, *,
                    parallel_run_days: int = 14,
                    custom_steps: Optional[List[Dict]] = None) -> CutoverPlan:
        plan = CutoverPlan(
            app_name=app_name,
            parallel_run_days=parallel_run_days,
            rollback_plan=(
                f'If critical issues found during parallel run:\n'
                f'1. Re-enable Qlik app access\n'
                f'2. Notify users of rollback\n'
                f'3. Document issues for remediation\n'
                f'4. Schedule re-cutover after fixes'
            ),
        )

        steps_data = custom_steps if custom_steps else _DEFAULT_STEPS
        for step_data in steps_data:
            plan.steps.append(CutoverStep(**step_data))

        return plan

    def evaluate_readiness(self, plan: CutoverPlan,
                          migration_report: Optional[Dict] = None,
                          review_report: Optional[Dict] = None) -> CutoverPlan:
        for check in self.checks:
            passed = False
            detail = ''

            if check.name == 'data_validation':
                if migration_report:
                    summary = migration_report.get('summary', {})
                    total = summary.get('total', 0)
                    exact = summary.get('exact', 0)
                    if total > 0 and exact / total >= 0.7:
                        passed = True
                        detail = f'{exact}/{total} items exact'
                    else:
                        detail = f'Only {exact}/{total} exact'
                else:
                    detail = 'No migration report available'

            elif check.name == 'measure_parity':
                if migration_report:
                    summary = migration_report.get('summary', {})
                    unsupported = summary.get('unsupported', 0)
                    passed = unsupported == 0
                    detail = f'{unsupported} unsupported items'
                else:
                    detail = 'No migration report'

            elif check.name == 'visual_fidelity':
                if review_report:
                    score = review_report.get('final_score', 0)
                    passed = score >= 4.0
                    detail = f'Review score: {score}/5.0'
                else:
                    detail = 'No review report'

            elif check.name == 'user_acceptance':
                detail = 'Requires manual confirmation'
                passed = False

            elif check.name == 'workspace_permissions':
                detail = 'Requires manual verification'
                passed = False

            else:
                passed = True
                detail = 'Auto-approved (non-critical)'

            severity = 'error' if check.required and not passed else 'warning' if not passed else 'info'
            plan.readiness_results.append(ReadinessResult(
                check_name=check.name, passed=passed,
                detail=detail, severity=severity,
            ))

        return plan

    def generate_runbook(self, plan: CutoverPlan) -> str:
        """Generate a markdown runbook from the cutover plan."""
        lines = [
            f'# Cutover Runbook: {plan.app_name}',
            f'',
            f'**Created:** {plan.created_at}',
            f'**Status:** {plan.status}',
            f'**Parallel Run:** {plan.parallel_run_days} days',
            f'**Estimated Duration:** {plan.total_duration_minutes} minutes',
            f'',
            f'## Readiness Checks',
            f'',
        ]

        for r in plan.readiness_results:
            icon = '[PASS]' if r.passed else '[FAIL]'
            lines.append(f'- {icon} **{r.check_name}**: {r.detail}')

        lines.extend(['', '## Cutover Steps', ''])

        for step in sorted(plan.steps, key=lambda s: s.order):
            status_icon = {
                'pending': '[ ]', 'in_progress': '[>]',
                'completed': '[x]', 'skipped': '[-]', 'failed': '[!]',
            }.get(step.status, '[ ]')
            lines.append(f'{status_icon} **Step {step.order}: {step.name}**')
            if step.description:
                lines.append(f'    {step.description}')
            if step.duration_minutes:
                lines.append(f'    Duration: {step.duration_minutes} min')
            if step.dependencies:
                lines.append(f'    Dependencies: {", ".join(step.dependencies)}')
            lines.append('')

        lines.extend(['## Rollback Plan', '', plan.rollback_plan, ''])

        return '\n'.join(lines)

    def save_runbook(self, plan: CutoverPlan, output_path: str) -> str:
        content = self.generate_runbook(plan)
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
        logger.info("Cutover runbook saved to %s", output_path)
        return output_path
