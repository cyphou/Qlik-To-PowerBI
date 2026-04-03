"""
Merge Configuration — Save/Load merge decisions for reproducible migrations.

Exports merge decisions (table accept/reject, measure resolution, conflict
handling) to a JSON configuration file. Allows manual editing and re-import
for deterministic, reproducible shared model migrations.

Usage::

    from powerbi_import.merge_config import save_merge_config, load_merge_config

    # After assessment — save decisions
    save_merge_config(assessment, app_names, "merge_config.json")

    # Before merge — load and apply saved decisions
    config = load_merge_config("merge_config.json")
    assessment = apply_merge_config(assessment, config)
"""

from __future__ import annotations

import json
import logging
import os
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Current config schema version
_CONFIG_VERSION = "1.0"


def save_merge_config(assessment, app_names: List[str],
                      output_path: str,
                      merged: dict = None) -> str:
    """Export merge decisions to a JSON config file.

    Args:
        assessment: MergeAssessment from assess_merge().
        app_names: List of app names.
        output_path: Path to write the config JSON.
        merged: Optional merged converted_objects (for field mappings).

    Returns:
        Path to the written config file.
    """
    config = {
        "version": _CONFIG_VERSION,
        "apps": list(app_names),
        "merge_score": assessment.merge_score,
        "recommendation": assessment.recommendation,
        "table_decisions": [],
        "measure_decisions": [],
        "parameter_decisions": [],
        "options": {
            "force_merge": False,
            "column_overlap_threshold": 0.7,
            "auto_namespace": True,
            "keep_hidden_columns": True,
            "calendar_merge_strategy": "widest_range",
        },
    }

    # Table decisions — accept/reject each merge candidate
    for mc in assessment.merge_candidates:
        config["table_decisions"].append({
            "table_name": mc.table_name,
            "action": "merge",  # merge | skip
            "apps": [s[0] for s in mc.sources],
            "column_overlap": round(mc.column_overlap, 3),
            "conflicts": mc.conflicts,
        })

    # Include unique tables too (for reference)
    for wb, tables in assessment.unique_tables.items():
        for tname in tables:
            config["table_decisions"].append({
                "table_name": tname,
                "action": "include",  # include | exclude
                "apps": [wb],
                "column_overlap": 0.0,
                "conflicts": [],
            })

    # Measure decisions — how to resolve each conflict
    for mc in assessment.measure_conflicts:
        config["measure_decisions"].append({
            "measure_name": mc.name,
            "action": "namespace",  # namespace | keep_first | keep_last | custom
            "variants": mc.variants,
            "custom_name": None,
        })

    # Parameter decisions
    for pc in assessment.parameter_conflicts:
        config["parameter_decisions"].append({
            "parameter_name": pc.get("name", ""),
            "action": "namespace",
            "variants": pc.get("variants", {}),
        })

    # RLS role decisions
    config["rls_rules"] = []
    if merged:
        from powerbi_import.shared_model import consolidate_rls_roles
        try:
            all_ext = [merged]  # placeholder — caller may supply real list
            # If assessment carries rls_consolidations, use those
            rls_cons = getattr(assessment, 'rls_consolidations', None)
            if rls_cons is None:
                rls_cons = []
            for rc in rls_cons:
                config["rls_rules"].append({
                    "role_name": rc.role_name,
                    "action": rc.action,
                    "strategy": "or",
                    "source_apps": rc.source_apps,
                    "tables": rc.tables_affected,
                    "merged_expression": rc.merged_expression,
                })
        except Exception:
            pass

    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    logger.info("Merge config saved: %s", output_path)
    return output_path


def load_merge_config(config_path: str) -> dict:
    """Load a merge config file.

    Args:
        config_path: Path to the merge config JSON.

    Returns:
        Config dict with table/measure/parameter decisions.

    Raises:
        FileNotFoundError: If config file doesn't exist.
        ValueError: If config version is unsupported.
    """
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)

    version = config.get("version", "")
    if version != _CONFIG_VERSION:
        raise ValueError(
            f"Unsupported merge config version '{version}' "
            f"(expected '{_CONFIG_VERSION}')"
        )

    logger.info("Merge config loaded: %s", config_path)
    return config


def apply_merge_config(assessment, config: dict):
    """Apply saved merge decisions to an assessment.

    Modifies the assessment in-place based on config decisions:
    - Removes merge candidates marked as "skip"
    - Removes unique tables marked as "exclude"
    - Updates measure conflict resolution strategy

    Args:
        assessment: MergeAssessment to modify.
        config: Config dict from load_merge_config().

    Returns:
        Modified assessment.
    """
    # Build lookup of table decisions
    table_actions = {}
    for td in config.get("table_decisions", []):
        table_actions[td["table_name"]] = td.get("action", "merge")

    # Filter merge candidates based on saved decisions
    filtered_candidates = []
    for mc in assessment.merge_candidates:
        action = table_actions.get(mc.table_name, "merge")
        if action == "skip":
            logger.info("Skipping table '%s' per config", mc.table_name)
            # Move to unique tables for each app
            for src_wb, _, _ in mc.sources:
                assessment.unique_tables.setdefault(src_wb, []).append(mc.table_name)
        else:
            filtered_candidates.append(mc)
    assessment.merge_candidates = filtered_candidates

    # Filter unique tables
    for wb in list(assessment.unique_tables.keys()):
        filtered = []
        for tname in assessment.unique_tables[wb]:
            action = table_actions.get(tname, "include")
            if action != "exclude":
                filtered.append(tname)
            else:
                logger.info("Excluding table '%s' from %s per config",
                            tname, wb)
        assessment.unique_tables[wb] = filtered

    # Update measure conflict decisions
    measure_actions = {}
    for md in config.get("measure_decisions", []):
        measure_actions[md["measure_name"]] = md

    # Store on the assessment for use during merge
    assessment._merge_config = config

    # Store RLS rule decisions on the assessment
    assessment._rls_rules = {
        r["role_name"]: r for r in config.get("rls_rules", [])
    }

    # Apply force_merge from config
    options = config.get("options", {})
    if options.get("force_merge"):
        assessment.recommendation = "merge"

    # Recalculate unique table count
    assessment.unique_table_count = (
        len(assessment.merge_candidates) +
        sum(len(v) for v in assessment.unique_tables.values())
    )

    return assessment


def get_measure_action(config: dict, measure_name: str) -> str:
    """Get the configured action for a measure conflict.

    Returns:
        One of: "namespace", "keep_first", "keep_last", "custom"
    """
    for md in config.get("measure_decisions", []):
        if md.get("measure_name") == measure_name:
            return md.get("action", "namespace")
    return "namespace"
