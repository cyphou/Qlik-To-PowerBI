"""
Qlik reload task schedules → Power BI refresh configuration.

Extracts scheduled reload tasks from Qlik Sense (task metadata or
QMC export) and generates Power BI-compatible refresh schedules for
deployment via the Power BI REST API or Fabric pipelines.

Qlik Sense uses a task-based scheduler with triggers (daily, weekly,
event-based).  Power BI Service uses scheduled refresh with time
slots.  This module bridges the gap by:

1. Parsing Qlik task schedules from metadata exports.
2. Mapping Qlik recurrence patterns to PBI refresh slots.
3. Generating ``refresh_schedule.json`` for the deployment layer.
4. Generating PowerShell scripts for PBI Service refresh configuration.

Usage::

    from powerbi_import.refresh_generator import (
        parse_qlik_tasks,
        generate_refresh_schedule,
        generate_refresh_powershell,
    )

    tasks = parse_qlik_tasks(task_metadata)
    schedule = generate_refresh_schedule(tasks, timezone='UTC')
    ps_script = generate_refresh_powershell(schedule, dataset_id='...')
"""

import json
import os
import logging

logger = logging.getLogger(__name__)


# Qlik trigger type → PBI schedule pattern
_RECURRENCE_MAP = {
    'daily': 'Daily',
    'weekly': 'Weekly',
    'monthly': 'Monthly',
    'once': 'Once',
    'continuous': 'Daily',
    'hourly': 'Daily',
    'minutely': 'Daily',
    'event': 'Daily',  # Event-based triggers → daily as fallback
    'on_success': 'Daily',
    'on_failure': 'Daily',
}

# Default time slots when Qlik doesn't specify exact times (UTC)
_DEFAULT_TIME_SLOTS = ['06:00', '12:00', '18:00']


def parse_qlik_tasks(task_metadata):
    """Parse Qlik reload task metadata into normalized task objects.

    Accepts task metadata from various Qlik sources:
    - QMC task export (JSON array of task objects)
    - App metadata with ``reloadTask`` key
    - Raw trigger definitions

    Args:
        task_metadata: dict or list — Qlik task metadata.
            If dict: expects ``tasks`` or ``reloadTasks`` key.
            If list: each item is a task dict.

    Returns:
        list[dict]: Normalized tasks, each with:
            - ``name``: Task name
            - ``app_name``: Source app name
            - ``enabled``: bool
            - ``triggers``: list of trigger dicts with:
                - ``type``: 'daily' | 'weekly' | 'monthly' | 'once' | 'event'
                - ``start_time``: 'HH:MM' string (UTC)
                - ``days``: list of day names (for weekly)
                - ``day_of_month``: int (for monthly)
                - ``interval_minutes``: int (for continuous/minutely)
    """
    if not task_metadata:
        return []

    # Normalize to list
    if isinstance(task_metadata, dict):
        tasks_raw = (task_metadata.get('tasks')
                     or task_metadata.get('reloadTasks')
                     or task_metadata.get('items')
                     or [task_metadata])
    elif isinstance(task_metadata, list):
        tasks_raw = task_metadata
    else:
        return []

    tasks = []
    for raw in tasks_raw:
        if not isinstance(raw, dict):
            continue

        task = {
            'name': raw.get('name') or raw.get('taskName') or 'ReloadTask',
            'app_name': (raw.get('app', {}).get('name')
                         if isinstance(raw.get('app'), dict) else
                         raw.get('appName', '')),
            'enabled': raw.get('enabled', True),
            'triggers': [],
        }

        # Parse triggers/schedules
        triggers = (raw.get('triggers')
                    or raw.get('schemaEvents')
                    or raw.get('compositeEvents')
                    or [])

        for trigger in triggers:
            if not isinstance(trigger, dict):
                continue

            trigger_type = (trigger.get('type')
                            or trigger.get('eventType')
                            or trigger.get('recurrence')
                            or 'daily').lower()

            start_time = _extract_time(trigger)
            days = _extract_days(trigger)
            day_of_month = trigger.get('dayOfMonth') or trigger.get('day', 0)
            interval = trigger.get('intervalMinutes') or trigger.get('interval', 0)

            task['triggers'].append({
                'type': trigger_type,
                'start_time': start_time,
                'days': days,
                'day_of_month': int(day_of_month) if day_of_month else 0,
                'interval_minutes': int(interval) if interval else 0,
            })

        # Default trigger if none specified
        if not task['triggers']:
            task['triggers'].append({
                'type': 'daily',
                'start_time': '06:00',
                'days': [],
                'day_of_month': 0,
                'interval_minutes': 0,
            })

        tasks.append(task)

    return tasks


def _extract_time(trigger):
    """Extract time string from a trigger definition."""
    # Try common Qlik time fields
    for key in ('startTime', 'time', 'startDateTime', 'nextExecution'):
        val = trigger.get(key, '')
        if val and isinstance(val, str):
            # Extract HH:MM from datetime or time string
            if 'T' in val:
                time_part = val.split('T')[-1][:5]
                return time_part
            if ':' in val:
                return val[:5]
    return '06:00'


def _extract_days(trigger):
    """Extract day-of-week list from a trigger definition."""
    days_raw = trigger.get('daysOfWeek') or trigger.get('days') or []
    if isinstance(days_raw, str):
        days_raw = [d.strip() for d in days_raw.split(',')]

    # Normalize day names
    day_map = {
        'mon': 'Monday', 'monday': 'Monday',
        'tue': 'Tuesday', 'tuesday': 'Tuesday',
        'wed': 'Wednesday', 'wednesday': 'Wednesday',
        'thu': 'Thursday', 'thursday': 'Thursday',
        'fri': 'Friday', 'friday': 'Friday',
        'sat': 'Saturday', 'saturday': 'Saturday',
        'sun': 'Sunday', 'sunday': 'Sunday',
        '0': 'Sunday', '1': 'Monday', '2': 'Tuesday',
        '3': 'Wednesday', '4': 'Thursday', '5': 'Friday', '6': 'Saturday',
    }

    result = []
    for d in days_raw:
        key = str(d).lower().strip()
        if key in day_map:
            result.append(day_map[key])
    return result


def generate_refresh_schedule(tasks, timezone='UTC', max_refreshes_per_day=8):
    """Generate Power BI refresh schedule from parsed Qlik tasks.

    Maps Qlik reload triggers to PBI scheduled refresh time slots.
    Power BI Pro allows up to 8 refreshes/day; Premium allows 48.

    Args:
        tasks: List of normalized task dicts from ``parse_qlik_tasks()``.
        timezone: IANA timezone string (e.g. ``'UTC'``, ``'America/New_York'``).
        max_refreshes_per_day: Maximum refresh slots (8 for Pro, 48 for Premium).

    Returns:
        dict: Refresh schedule configuration with keys:
            - ``enabled``: bool
            - ``timezone``: str
            - ``days``: list of day names
            - ``times``: list of 'HH:MM' strings
            - ``notifyOption``: 'MailOnFailure' | 'NoNotification'
            - ``source_tasks``: original task names (for lineage)
    """
    if not tasks:
        return _empty_schedule(timezone)

    enabled_tasks = [t for t in tasks if t.get('enabled', True)]
    if not enabled_tasks:
        return _empty_schedule(timezone)

    # Collect all time slots and days across tasks
    all_times = set()
    all_days = set()
    source_names = []

    for task in enabled_tasks:
        source_names.append(task.get('name', ''))
        for trigger in task.get('triggers', []):
            start_time = trigger.get('start_time', '06:00')
            trigger_type = trigger.get('type', 'daily')

            all_times.add(start_time)

            # Expand time slots for frequent refreshes
            interval = trigger.get('interval_minutes', 0)
            if interval and interval > 0 and trigger_type in ('continuous', 'hourly', 'minutely'):
                hour, minute = map(int, start_time.split(':'))
                total_minutes = hour * 60 + minute
                while total_minutes < 24 * 60:
                    h, m = divmod(total_minutes, 60)
                    all_times.add(f'{h:02d}:{m:02d}')
                    total_minutes += max(interval, 30)  # Minimum 30-min spacing

            # Collect days
            trigger_days = trigger.get('days', [])
            if trigger_days:
                all_days.update(trigger_days)
            elif trigger_type in ('daily', 'continuous', 'hourly', 'minutely'):
                all_days.update(['Monday', 'Tuesday', 'Wednesday', 'Thursday',
                                 'Friday', 'Saturday', 'Sunday'])
            elif trigger_type == 'monthly':
                # Monthly triggers run on all days (PBI doesn't support day-of-month)
                all_days.update(['Monday', 'Tuesday', 'Wednesday', 'Thursday',
                                 'Friday', 'Saturday', 'Sunday'])

    # Limit to max refreshes per day
    sorted_times = sorted(all_times)
    if len(sorted_times) > max_refreshes_per_day:
        # Keep evenly spaced time slots
        step = len(sorted_times) / max_refreshes_per_day
        sorted_times = [sorted_times[int(i * step)] for i in range(max_refreshes_per_day)]

    # Default to weekdays if no days specified
    if not all_days:
        all_days = {'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'}

    # Sort days in calendar order
    day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday',
                 'Friday', 'Saturday', 'Sunday']
    sorted_days = [d for d in day_order if d in all_days]

    return {
        'enabled': True,
        'timezone': timezone,
        'days': sorted_days,
        'times': sorted_times,
        'notifyOption': 'MailOnFailure',
        'source_tasks': source_names,
    }


def _empty_schedule(timezone='UTC'):
    """Return a disabled schedule placeholder."""
    return {
        'enabled': False,
        'timezone': timezone,
        'days': [],
        'times': [],
        'notifyOption': 'NoNotification',
        'source_tasks': [],
    }


def generate_refresh_powershell(schedule, dataset_id='<DATASET_ID>',
                                group_id='<GROUP_ID>'):
    """Generate PowerShell script to configure PBI scheduled refresh.

    Uses the Power BI REST API ``PATCH /groups/{groupId}/datasets/{datasetId}/refreshSchedule``.

    Args:
        schedule: Refresh schedule dict from ``generate_refresh_schedule()``.
        dataset_id: Power BI dataset GUID (placeholder if unknown).
        group_id: Power BI workspace GUID (placeholder if unknown).

    Returns:
        str: PowerShell script content.
    """
    days_json = json.dumps(schedule.get('days', []))
    times_json = json.dumps(schedule.get('times', []))
    enabled = str(schedule.get('enabled', False)).lower()
    notify = schedule.get('notifyOption', 'MailOnFailure')
    timezone = schedule.get('timezone', 'UTC')

    script = f'''# Power BI Scheduled Refresh Configuration
# Auto-generated from Qlik reload task migration
# Source tasks: {', '.join(schedule.get('source_tasks', []))}

# Prerequisites: Install-Module -Name MicrosoftPowerBIMgmt
# Login: Connect-PowerBIServiceAccount

$groupId = "{group_id}"
$datasetId = "{dataset_id}"

$scheduleBody = @{{
    value = @{{
        enabled = ${enabled}
        notifyOption = "{notify}"
        days = @({', '.join(f'"{d}"' for d in schedule.get('days', []))})
        times = @({', '.join(f'"{t}"' for t in schedule.get('times', []))})
        localTimeZoneId = "{timezone}"
    }}
}} | ConvertTo-Json -Depth 5

$uri = "https://api.powerbi.com/v1.0/myorg/groups/$groupId/datasets/$datasetId/refreshSchedule"

Invoke-PowerBIRestMethod -Url $uri -Method Patch -Body $scheduleBody

Write-Host "Refresh schedule configured for dataset $datasetId"
Write-Host "  Days: {', '.join(schedule.get('days', []))}"
Write-Host "  Times: {', '.join(schedule.get('times', []))}"
Write-Host "  Timezone: {timezone}"
'''
    return script


def write_refresh_config(schedule, output_dir, report_name='Report'):
    """Write refresh schedule to a JSON file in the project directory.

    Creates ``refresh_schedule.json`` alongside the migration metadata.

    Args:
        schedule: Refresh schedule dict.
        output_dir: Project output directory.
        report_name: Report name for the filename.

    Returns:
        str: Path to the created file.
    """
    filename = f'{report_name}_refresh_schedule.json'
    filepath = os.path.join(output_dir, filename)

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(schedule, f, indent=2, ensure_ascii=False)

    logger.info("Wrote refresh schedule: %s", filepath)
    return filepath
