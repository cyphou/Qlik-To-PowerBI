"""
Data-driven alerts generator.

Extracts alert conditions from Qlik TWB XML and generates
Power BI alert rule configurations.

Qlik data alerts are threshold-based notifications on measures.
Power BI supports similar alerts on dashboard tiles (cards, gauges, KPIs).
This module maps Qlik alert definitions to a PBI-compatible alert
rules JSON structure.

Usage::

    from powerbi_import.alerts_generator import extract_alerts, generate_alert_rules
    alerts = extract_alerts(extracted_data)
    rules = generate_alert_rules(alerts)
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Alert condition operators ────────────────────────────────────

_OPERATOR_MAP = {
    'above': 'greaterThan',
    'below': 'lessThan',
    'above-or-equal': 'greaterThanOrEqual',
    'below-or-equal': 'lessThanOrEqual',
    '>': 'greaterThan',
    '<': 'lessThan',
    '>=': 'greaterThanOrEqual',
    '<=': 'lessThanOrEqual',
    '=': 'equal',
    '==': 'equal',
    '!=': 'notEqual',
}

# ── Frequency mapping ───────────────────────────────────────────

_FREQUENCY_MAP = {
    'once': 'once',
    'always': 'always',
    'daily': 'atMostOncePerDay',
    'hourly': 'atMostOncePerHour',
}


def extract_alerts(extracted_data: Dict) -> List[Dict]:
    """Extract alert-like conditions from Qlik extracted data.

    Looks for:
    1. Parameters named with alert-related keywords (threshold, alert, limit)
    2. Calculations that reference alert parameters
    3. Reference lines with constant values (threshold markers)

    Args:
        extracted_data: Dict of extracted JSON objects from Qlik.

    Returns:
        List of alert definition dicts with keys:
        - name: Alert name
        - measure: Measure or field being monitored
        - operator: Comparison operator
        - threshold: Threshold value
        - frequency: Notification frequency
        - source: Where the alert was detected
    """
    alerts = []

    # 1. Extract from parameters with alert-related names
    _extract_from_parameters(extracted_data, alerts)

    # 2. Extract from calculations that contain threshold logic
    _extract_from_calculations(extracted_data, alerts)

    # 3. Extract from worksheets with reference lines
    _extract_from_reference_lines(extracted_data, alerts)

    logger.info("Extracted %d alert condition(s) from Qlik data", len(alerts))
    return alerts


def _extract_from_parameters(extracted_data: Dict, alerts: List[Dict]) -> None:
    """Extract alerts from parameters with alert/threshold keywords."""
    parameters = extracted_data.get('parameters', [])
    if isinstance(parameters, dict):
        parameters = parameters.get('parameters', [])

    alert_keywords = re.compile(
        r'alert|threshold|limit|target|goal|benchmark|warning|critical',
        re.IGNORECASE,
    )

    for param in parameters:
        name = param.get('name') or param.get('caption', '')
        if not alert_keywords.search(name):
            continue

        value = param.get('value') or param.get('current_value')
        if value is None:
            continue

        # Try to parse as numeric
        try:
            threshold = float(value)
        except (ValueError, TypeError):
            continue

        # Infer operator from name
        operator = 'greaterThan'
        name_lower = name.lower()
        if 'min' in name_lower or 'floor' in name_lower or 'lower' in name_lower:
            operator = 'lessThan'
        elif 'max' in name_lower or 'ceiling' in name_lower or 'upper' in name_lower:
            operator = 'greaterThan'

        alerts.append({
            'name': f'Alert: {name}',
            'measure': _infer_measure_from_param(name, extracted_data),
            'operator': operator,
            'threshold': threshold,
            'frequency': 'atMostOncePerDay',
            'source': f'parameter:{name}',
        })


def _extract_from_calculations(extracted_data: Dict, alerts: List[Dict]) -> None:
    """Extract alert conditions from calculations with IF/threshold patterns."""
    calculations = extracted_data.get('calculations', [])
    if isinstance(calculations, dict):
        calculations = calculations.get('calculations', [])

    # Pattern: IF [Measure] > [Parameters].[Threshold] THEN ...
    threshold_pattern = re.compile(
        r'IF\s*\(?.*?\[([^\]]+)\]\s*([><=!]+)\s*'
        r'(?:\[Parameters\]\.\[([^\]]+)\]|(\d+(?:\.\d+)?))',
        re.IGNORECASE,
    )

    alert_keywords = re.compile(
        r'alert|threshold|flag|warning|breach|violation',
        re.IGNORECASE,
    )

    for calc in calculations:
        formula = calc.get('formula', '')
        calc_name = calc.get('caption') or calc.get('name', '')

        if not formula:
            continue

        # Only consider calculations with alert-like names or threshold refs
        if not alert_keywords.search(calc_name) and '[Parameters]' not in formula:
            continue

        match = threshold_pattern.search(formula)
        if match:
            measure = match.group(1)
            op_str = match.group(2)
            param_name = match.group(3)
            literal_val = match.group(4)

            operator = _OPERATOR_MAP.get(op_str, 'greaterThan')

            threshold = None
            if literal_val:
                try:
                    threshold = float(literal_val)
                except (ValueError, TypeError):
                    pass
            elif param_name:
                # Look up parameter value
                threshold = _lookup_param_value(param_name, extracted_data)

            if threshold is not None:
                alerts.append({
                    'name': f'Alert: {calc_name}',
                    'measure': measure,
                    'operator': operator,
                    'threshold': threshold,
                    'frequency': 'atMostOncePerDay',
                    'source': f'calculation:{calc_name}',
                })


def _extract_from_reference_lines(extracted_data: Dict, alerts: List[Dict]) -> None:
    """Extract alert-like conditions from reference lines on worksheets."""
    worksheets = extracted_data.get('worksheets', [])
    if isinstance(worksheets, dict):
        worksheets = worksheets.get('worksheets', [])

    for ws in worksheets:
        ref_lines = ws.get('reference_lines', [])
        ws_name = ws.get('name', 'Unknown')

        for rl in ref_lines:
            value = rl.get('value')
            label = rl.get('label', '')
            if value is None:
                continue
            try:
                threshold = float(value)
            except (ValueError, TypeError):
                continue

            # Only treat as alert if label suggests a threshold
            if not re.search(r'target|goal|threshold|limit|alert', label, re.IGNORECASE):
                continue

            # Try to find the primary measure from worksheet fields
            measure = _infer_measure_from_worksheet(ws)

            alerts.append({
                'name': f'Alert: {label or ws_name} reference line',
                'measure': measure or ws_name,
                'operator': 'greaterThan',
                'threshold': threshold,
                'frequency': 'atMostOncePerDay',
                'source': f'reference_line:{ws_name}',
            })


def _infer_measure_from_param(param_name: str, extracted_data: Dict) -> str:
    """Try to find which measure a parameter is associated with."""
    calculations = extracted_data.get('calculations', [])
    if isinstance(calculations, dict):
        calculations = calculations.get('calculations', [])

    for calc in calculations:
        formula = calc.get('formula', '')
        if param_name in formula:
            # Return the calculation name as the likely related measure
            return calc.get('caption') or calc.get('name', 'Unknown')
    return 'Unknown'


def _infer_measure_from_worksheet(ws: Dict) -> Optional[str]:
    """Try to find the primary measure field from a worksheet."""
    fields = ws.get('fields', [])
    for f in fields:
        if isinstance(f, dict):
            role = f.get('role', '')
            if role == 'measure':
                return f.get('name') or f.get('caption', '')
        elif isinstance(f, str) and f.startswith('[') and f.endswith(']'):
            return f[1:-1]
    return None


def _lookup_param_value(param_name: str, extracted_data: Dict) -> Optional[float]:
    """Look up a parameter's current value."""
    parameters = extracted_data.get('parameters', [])
    if isinstance(parameters, dict):
        parameters = parameters.get('parameters', [])

    for param in parameters:
        name = param.get('name') or param.get('caption', '')
        if name == param_name or name.replace(' ', '') == param_name.replace(' ', ''):
            value = param.get('value') or param.get('current_value')
            if value is not None:
                try:
                    return float(value)
                except (ValueError, TypeError):
                    pass
    return None


def generate_alert_rules(alerts: List[Dict]) -> List[Dict]:
    """Convert extracted alert definitions to Power BI alert rule format.

    Power BI alert rules are JSON structures that define:
    - condition: operator + threshold
    - measure: the measure to evaluate
    - frequency: how often to check / notify

    Args:
        alerts: List of alert dicts from ``extract_alerts()``.

    Returns:
        List of PBI alert rule dicts.
    """
    rules = []
    for alert in alerts:
        rule = {
            'name': alert['name'],
            'condition': {
                'operator': alert.get('operator', 'greaterThan'),
                'threshold': alert.get('threshold', 0),
            },
            'measure': alert.get('measure', 'Unknown'),
            'frequency': alert.get('frequency', 'atMostOncePerDay'),
            'isEnabled': True,
            'migrationSource': alert.get('source', ''),
            'migrationNote': (
                'Auto-generated from Qlik alert condition. '
                'Configure notification recipients in Power BI Service.'
            ),
        }
        rules.append(rule)

    return rules


def save_alert_rules(rules: List[Dict], output_dir: str) -> str:
    """Save alert rules to a JSON file.

    Args:
        rules: List of alert rule dicts from ``generate_alert_rules()``.
        output_dir: Directory to write the alert rules file.

    Returns:
        Path to the saved JSON file.
    """
    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, 'alert_rules.json')

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump({
            'alertRules': rules,
            'migrationNote': (
                'These alert rules were extracted from Qlik data alerts '
                'and threshold parameters. Configure them in Power BI Service '
                'by pinning the corresponding visuals to a dashboard and '
                'setting up alerts on the tile.'
            ),
        }, f, indent=2, ensure_ascii=False)

    logger.info("Saved %d alert rule(s) to %s", len(rules), filepath)
    return filepath
