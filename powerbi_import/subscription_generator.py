"""Subscription generator — migrate Qlik alert/notification rules to Power BI subscriptions.

Converts Qlik task triggers, data-driven alerts, and notification rules
into Power BI subscription JSON configs.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SubscriptionRule:
    """A single Power BI subscription/alert rule."""
    name: str
    report_name: str
    page_name: str = ''
    visual_name: str = ''
    schedule_type: str = 'daily'   # daily, weekly, after_refresh
    schedule_time: str = '08:00'
    days_of_week: List[str] = field(default_factory=lambda: ['Monday'])
    recipients: List[str] = field(default_factory=list)
    subject: str = ''
    include_screenshot: bool = True
    condition: Optional[Dict[str, Any]] = None
    source_rule: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            'name': self.name,
            'reportName': self.report_name,
            'pageName': self.page_name,
            'visualName': self.visual_name,
            'schedule': {
                'type': self.schedule_type,
                'time': self.schedule_time,
            },
            'recipients': self.recipients,
            'subject': self.subject or f'Power BI: {self.report_name}',
            'includeScreenshot': self.include_screenshot,
        }
        if self.schedule_type == 'weekly':
            result['schedule']['daysOfWeek'] = self.days_of_week
        if self.condition:
            result['condition'] = self.condition
        if self.source_rule:
            result['_sourceRule'] = self.source_rule
        return result


def _map_schedule(qlik_trigger: Dict[str, Any]) -> Dict[str, str]:
    """Map Qlik task trigger to PBI schedule type."""
    trigger_type = qlik_trigger.get('type', '').lower()

    if trigger_type in ('on_reload', 'on_success', 'task_event'):
        return {'type': 'after_refresh', 'time': ''}

    if trigger_type in ('daily', 'once_a_day'):
        time_of_day = qlik_trigger.get('time', '08:00')
        return {'type': 'daily', 'time': time_of_day}

    if trigger_type in ('weekly',):
        time_of_day = qlik_trigger.get('time', '08:00')
        return {'type': 'weekly', 'time': time_of_day}

    if trigger_type in ('hourly', 'every_n_hours'):
        return {'type': 'daily', 'time': '08:00'}

    return {'type': 'daily', 'time': '08:00'}


def _map_condition(qlik_condition: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Map a Qlik data-driven condition to PBI alert condition."""
    if not qlik_condition:
        return None

    measure = qlik_condition.get('measure', qlik_condition.get('field', ''))
    operator = qlik_condition.get('operator', 'above')
    threshold = qlik_condition.get('threshold', qlik_condition.get('value', 0))

    op_map = {
        'above': 'greaterThan',
        'below': 'lessThan',
        'equal': 'equal',
        'not_equal': 'notEqual',
        'greater_than': 'greaterThan',
        'less_than': 'lessThan',
        '>': 'greaterThan',
        '<': 'lessThan',
        '=': 'equal',
        '>=': 'greaterThanOrEqual',
        '<=': 'lessThanOrEqual',
    }
    pbi_op = op_map.get(operator, 'greaterThan')

    return {
        'measure': measure,
        'operator': pbi_op,
        'threshold': threshold,
    }


def convert_qlik_alerts(
    alerts: List[Dict[str, Any]],
    report_name: str = '',
) -> List[SubscriptionRule]:
    """Convert Qlik alert definitions to Power BI subscription rules.

    Args:
        alerts: List of Qlik alert dicts with keys like 'name', 'condition',
            'recipients', 'trigger', 'sheet', 'visualization'.
        report_name: Default report name for the subscriptions.
    """
    rules: List[SubscriptionRule] = []

    for alert in alerts:
        name = alert.get('name', alert.get('title', 'Unnamed Alert'))
        trigger = alert.get('trigger', {})
        schedule = _map_schedule(trigger)
        condition = _map_condition(alert.get('condition', {}))

        recipients = alert.get('recipients', [])
        if isinstance(recipients, str):
            recipients = [r.strip() for r in recipients.split(';') if r.strip()]

        rule = SubscriptionRule(
            name=name,
            report_name=report_name or alert.get('app_name', 'Report'),
            page_name=alert.get('sheet', alert.get('page', '')),
            visual_name=alert.get('visualization', alert.get('visual', '')),
            schedule_type=schedule['type'],
            schedule_time=schedule.get('time', '08:00'),
            recipients=recipients,
            subject=alert.get('subject', ''),
            include_screenshot=alert.get('include_screenshot', True),
            condition=condition,
            source_rule=alert,
        )
        rules.append(rule)

    return rules


def convert_qlik_tasks(
    tasks: List[Dict[str, Any]],
    report_name: str = '',
) -> List[SubscriptionRule]:
    """Convert Qlik task triggers to Power BI refresh subscriptions.

    Args:
        tasks: List of Qlik task dicts with keys like 'name', 'triggers',
            'recipients'.
        report_name: Default report name.
    """
    rules: List[SubscriptionRule] = []

    for task in tasks:
        name = task.get('name', 'Unnamed Task')
        triggers = task.get('triggers', [task.get('trigger', {})])
        if isinstance(triggers, dict):
            triggers = [triggers]

        recipients = task.get('recipients', task.get('notify', []))
        if isinstance(recipients, str):
            recipients = [r.strip() for r in recipients.split(';') if r.strip()]

        for i, trigger in enumerate(triggers):
            schedule = _map_schedule(trigger)
            suffix = f' (trigger {i+1})' if len(triggers) > 1 else ''
            rule = SubscriptionRule(
                name=f'{name}{suffix}',
                report_name=report_name or 'Report',
                schedule_type=schedule['type'],
                schedule_time=schedule.get('time', '08:00'),
                recipients=recipients,
                subject=f'Refresh: {name}',
                include_screenshot=False,
                source_rule=task,
            )
            rules.append(rule)

    return rules


def generate_subscriptions_json(
    rules: List[SubscriptionRule],
    output_path: str = '',
) -> str:
    """Write subscription rules to a JSON file.

    Returns the JSON string.
    """
    data = {
        'version': '1.0',
        'generated': datetime.now().isoformat(),
        'subscription_count': len(rules),
        'subscriptions': [r.to_dict() for r in rules],
    }
    json_str = json.dumps(data, indent=2, ensure_ascii=False)

    if output_path:
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(json_str)
        logger.info("Subscriptions written to: %s", output_path)

    return json_str


def generate_subscriptions_powershell(
    rules: List[SubscriptionRule],
    output_path: str = '',
) -> str:
    """Generate a PowerShell script to create PBI subscriptions via REST API.

    Returns the script text.
    """
    lines = [
        '# Auto-generated Power BI subscription setup script',
        '# Requires: MicrosoftPowerBIMgmt module',
        '# Run: Install-Module -Name MicrosoftPowerBIMgmt',
        '',
        'Connect-PowerBIServiceAccount',
        '',
    ]

    for rule in rules:
        esc_name = rule.name.replace("'", "''")
        esc_report = rule.report_name.replace("'", "''")
        lines.append(f"# Subscription: {rule.name}")
        lines.append(f"# Source report: {rule.report_name}")
        lines.append(f"# Schedule: {rule.schedule_type} at {rule.schedule_time}")
        if rule.recipients:
            lines.append(f"# Recipients: {', '.join(rule.recipients)}")
        lines.append(f"Write-Host 'TODO: Create subscription "
                     f"''{esc_name}'' for report ''{esc_report}'''")
        lines.append('')

    script = '\n'.join(lines)

    if output_path:
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(script)
        logger.info("PowerShell script written to: %s", output_path)

    return script
