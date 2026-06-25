"""Generate executable P0/P1/P2 backlog from the latest phase report.

Inputs:
- artifacts/reports/phases/latest.json

Outputs:
- artifacts/reports/phases/parity_backlog_latest.json
- artifacts/reports/phases/parity_backlog_latest.md
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List


ROOT = Path(__file__).resolve().parents[2]
PHASES_DIR = ROOT / "artifacts" / "reports" / "phases"
LATEST_REPORT = PHASES_DIR / "latest.json"
OUT_JSON = PHASES_DIR / "parity_backlog_latest.json"
OUT_MD = PHASES_DIR / "parity_backlog_latest.md"


def _load_latest() -> Dict[str, object]:
    if not LATEST_REPORT.exists():
        raise FileNotFoundError(f"Missing phase report: {LATEST_REPORT}")
    return json.loads(LATEST_REPORT.read_text(encoding="utf-8"))


def _base_backlog(metrics: Dict[str, object]) -> Dict[str, object]:
    explicit_unsup = metrics.get("explicit_unsupported_functions", {}) or {}
    unsupported_list = [k for k, v in explicit_unsup.items() if bool(v)]

    backlog = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_report": str(LATEST_REPORT),
        "context": {
            "migration_status": metrics.get("migration_status"),
            "fidelity_score": metrics.get("fidelity_score"),
            "post_check_warning_count": metrics.get("post_check_warning_count"),
            "post_check_error_count": metrics.get("post_check_error_count"),
            "unsupported_markers": metrics.get("unsupported_markers"),
            "approximation_markers": metrics.get("approximation_markers"),
            "explicit_unsupported_functions": unsupported_list,
        },
        "epics": [
            {
                "id": "P0-UNSUPPORTED-CLOSURE",
                "priority": "P0",
                "goal": "Close explicit unsupported Qlik function gaps",
                "items": [
                    {
                        "id": "P0-1",
                        "title": "Implement deterministic handling for Skew",
                        "owner": "Dax",
                        "estimate_days": 2,
                        "acceptance": [
                            "No 'UNSUPPORTED: Skew' marker emitted in migrated expressions",
                            "Unit tests cover scalar, measure, and nested use cases",
                            "Strict mode can fail on unresolved Skew only when requested",
                        ],
                    },
                    {
                        "id": "P0-2",
                        "title": "Implement safe handling strategy for Hash128/Hash160/Hash256",
                        "owner": "Converter",
                        "estimate_days": 3,
                        "acceptance": [
                            "No unsupported hash markers in output for covered paths",
                            "Documented behavior in mapping reference",
                            "Regression tests for each hash function",
                        ],
                    },
                    {
                        "id": "P0-3",
                        "title": "Implement Evaluate() migration policy",
                        "owner": "Orchestrator",
                        "estimate_days": 3,
                        "acceptance": [
                            "Evaluate paths are either transformed or explicitly blocked by policy",
                            "Policy behavior exposed via CLI flag and documented",
                            "CI check validates no silent fallback remains",
                        ],
                    },
                ],
                "exit_criteria": {
                    "unsupported_markers_target": 0,
                    "explicit_unsupported_functions_target": [],
                },
            },
            {
                "id": "P1-APPROX-FIDELITY",
                "priority": "P1",
                "goal": "Reduce approximation risk in expression conversion",
                "items": [
                    {
                        "id": "P1-1",
                        "title": "Harden Correl conversion and validation",
                        "owner": "Dax",
                        "estimate_days": 2,
                        "acceptance": [
                            "Correlation conversion validated against reference datasets",
                            "Deviation threshold documented and tested",
                        ],
                    },
                    {
                        "id": "P1-2",
                        "title": "Improve NetWorkDays for holiday-aware scenarios",
                        "owner": "Wiring",
                        "estimate_days": 2,
                        "acceptance": [
                            "Holiday table support available",
                            "Conversion tests for weekend-only and holiday-aware modes",
                        ],
                    },
                    {
                        "id": "P1-3",
                        "title": "Refine KeepChar and BitCount approximations",
                        "owner": "Converter",
                        "estimate_days": 2,
                        "acceptance": [
                            "Reduced approximation warnings for representative corpus",
                            "No regression in existing DAX conversion tests",
                        ],
                    },
                ],
                "exit_criteria": {
                    "approximation_markers_target": 1,
                    "quality_gate_postcheck_warnings_max": 2,
                },
            },
            {
                "id": "P2-GOVERNANCE-AUTOMATION",
                "priority": "P2",
                "goal": "Operationalize parity governance and release gating",
                "items": [
                    {
                        "id": "P2-1",
                        "title": "Add CI gate for parity backlog targets",
                        "owner": "Tester",
                        "estimate_days": 2,
                        "acceptance": [
                            "CI fails if unsupported markers exceed target",
                            "CI fails if strict upstream parity check fails",
                        ],
                    },
                    {
                        "id": "P2-2",
                        "title": "Track deprecated TMDL generator usage cleanup",
                        "owner": "Generator",
                        "estimate_days": 3,
                        "acceptance": [
                            "Warnings trend reduced in test suite output",
                            "Migration path documented for remaining call sites",
                        ],
                    },
                    {
                        "id": "P2-3",
                        "title": "Publish weekly parity dashboard artifact",
                        "owner": "Preceptor",
                        "estimate_days": 2,
                        "acceptance": [
                            "Weekly report with phase status and KPI deltas generated",
                            "Artifacts retained in reports directory",
                        ],
                    },
                ],
                "exit_criteria": {
                    "weekly_phase_runs": 1,
                    "report_artifacts_present": True,
                },
            },
        ],
    }
    return backlog


def _to_markdown(backlog: Dict[str, object]) -> str:
    ctx = backlog["context"]
    lines: List[str] = []
    lines.append("# Parity Backlog P0/P1/P2")
    lines.append("")
    lines.append(f"- Generated at: {backlog['generated_at_utc']}")
    lines.append(f"- Source report: {backlog['source_report']}")
    lines.append("")
    lines.append("## Current Metrics")
    lines.append("")
    for key in [
        "migration_status",
        "fidelity_score",
        "post_check_warning_count",
        "post_check_error_count",
        "unsupported_markers",
        "approximation_markers",
    ]:
        lines.append(f"- {key}: {ctx.get(key)}")
    lines.append(f"- explicit_unsupported_functions: {', '.join(ctx.get('explicit_unsupported_functions', [])) or 'none'}")
    lines.append("")

    for epic in backlog["epics"]:
        lines.append(f"## {epic['priority']} - {epic['id']}")
        lines.append("")
        lines.append(f"- Goal: {epic['goal']}")
        lines.append("")
        lines.append("### Items")
        lines.append("")
        for item in epic["items"]:
            lines.append(f"- {item['id']} {item['title']} (owner: {item['owner']}, estimate: {item['estimate_days']}d)")
            for crit in item["acceptance"]:
                lines.append(f"  - AC: {crit}")
        lines.append("")
        lines.append("### Exit Criteria")
        lines.append("")
        for k, v in epic["exit_criteria"].items():
            lines.append(f"- {k}: {v}")
        lines.append("")

    return "\n".join(lines) + "\n"


def main() -> int:
    report = _load_latest()
    metrics = report.get("metrics", {}) or {}
    backlog = _base_backlog(metrics)

    PHASES_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(backlog, indent=2, ensure_ascii=False), encoding="utf-8")
    OUT_MD.write_text(_to_markdown(backlog), encoding="utf-8")

    print("Parity backlog generated")
    print(f"json: {OUT_JSON}")
    print(f"md: {OUT_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
