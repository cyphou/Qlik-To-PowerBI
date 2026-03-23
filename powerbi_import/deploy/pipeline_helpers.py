"""Deployment pipeline helpers — configuration, scheduling, labels."""

from typing import Any, Dict, List, Optional
import uuid


def _new_guid() -> str:
    return str(uuid.uuid4())


def generate_deployment_config(
    workspace_dev: str = "",
    workspace_test: str = "",
    workspace_prod: str = "",
) -> Dict[str, Any]:
    """Generate deployment pipeline configuration."""
    return {
        "deploymentPipeline": {
            "stages": [
                {"name": "Development", "workspaceId": workspace_dev or _new_guid()},
                {"name": "Test", "workspaceId": workspace_test or _new_guid()},
                {"name": "Production", "workspaceId": workspace_prod or _new_guid()},
            ],
            "rules": {
                "parameterRules": [],
                "datasourceRules": [],
            },
        },
    }


def generate_sensitivity_label(
    label_id: str = "",
    label_name: str = "General",
) -> Dict[str, Any]:
    """Generate sensitivity label metadata for the .pbip project."""
    return {
        "sensitivityLabel": {
            "labelId": label_id or _new_guid(),
            "displayName": label_name,
        },
    }


def generate_refresh_schedule(
    frequency: str = "Daily",
    times: Optional[List[str]] = None,
    timezone: str = "UTC",
) -> Dict[str, Any]:
    """Generate scheduled refresh configuration."""
    return {
        "refreshSchedule": {
            "frequency": frequency,
            "times": times or ["07:00", "19:00"],
            "timeZone": timezone,
            "enabled": True,
            "notifyOption": "MailOnFailure",
        },
    }


def generate_incremental_refresh_policy(
    table_name: str,
    date_column: str = "Date",
    incremental_days: int = 30,
    archive_days: int = 365,
) -> Dict[str, Any]:
    """Generate incremental refresh policy metadata for a table."""
    return {
        "refreshPolicy": {
            "policyType": "basic",
            "rollingWindowGranularity": "day",
            "rollingWindowPeriods": archive_days,
            "incrementalGranularity": "day",
            "incrementalPeriods": incremental_days,
            "pollingExpression": (
                f"let MaxDate = List.Max(Source[{date_column}]) in MaxDate"
            ),
        },
    }
