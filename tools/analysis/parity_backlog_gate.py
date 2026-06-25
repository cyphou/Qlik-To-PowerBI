"""Enforce parity targets from latest phase report and parity backlog.

This gate fails when exit criteria are not met.

Checks:
- P0 unsupported markers <= target
- P0 explicit unsupported functions match target set
- P1 approximation markers <= target
- P1 post-check warnings <= target
- Phase 2 strict upstream parity phase is PASS
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[2]
PHASES_DIR = ROOT / "artifacts" / "reports" / "phases"
LATEST_REPORT = PHASES_DIR / "latest.json"
LATEST_BACKLOG = PHASES_DIR / "parity_backlog_latest.json"


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _find_epic(backlog: Dict[str, Any], epic_id: str) -> Dict[str, Any]:
    for epic in backlog.get("epics", []):
        if epic.get("id") == epic_id:
            return epic
    raise KeyError(f"Epic not found: {epic_id}")


def _phase_status(report: Dict[str, Any], phase_prefix: str) -> str:
    for phase in report.get("phases", []):
        name = str(phase.get("name", ""))
        if name.startswith(phase_prefix):
            return str(phase.get("status", "UNKNOWN"))
    return "UNKNOWN"


def _as_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(v) for v in value]
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description="Parity backlog gate")
    parser.add_argument("--report", default=str(LATEST_REPORT), help="Path to latest phase report JSON")
    parser.add_argument("--backlog", default=str(LATEST_BACKLOG), help="Path to parity backlog JSON")
    args = parser.parse_args()

    report = _load_json(Path(args.report))
    backlog = _load_json(Path(args.backlog))

    metrics = report.get("metrics", {}) or {}

    p0 = _find_epic(backlog, "P0-UNSUPPORTED-CLOSURE")
    p1 = _find_epic(backlog, "P1-APPROX-FIDELITY")

    p0_exit = p0.get("exit_criteria", {}) or {}
    p1_exit = p1.get("exit_criteria", {}) or {}

    unsupported_markers = int(metrics.get("unsupported_markers", 0))
    unsupported_target = int(p0_exit.get("unsupported_markers_target", 0))

    explicit_actual_map = metrics.get("explicit_unsupported_functions", {}) or {}
    explicit_actual = sorted([k for k, v in explicit_actual_map.items() if bool(v)])
    explicit_target = sorted(_as_list(p0_exit.get("explicit_unsupported_functions_target", [])))

    approx_markers = int(metrics.get("approximation_markers", 0))
    approx_target = int(p1_exit.get("approximation_markers_target", 0))

    postcheck_warnings = int(metrics.get("post_check_warning_count", 0))
    warnings_target = int(p1_exit.get("quality_gate_postcheck_warnings_max", 0))

    strict_phase_status = _phase_status(report, "Phase 2 - Upstream strict parity")

    failures: List[str] = []

    if unsupported_markers > unsupported_target:
        failures.append(
            f"unsupported_markers {unsupported_markers} > target {unsupported_target}"
        )

    if explicit_actual != explicit_target:
        failures.append(
            f"explicit_unsupported_functions {explicit_actual} != target {explicit_target}"
        )

    if approx_markers > approx_target:
        failures.append(
            f"approximation_markers {approx_markers} > target {approx_target}"
        )

    if postcheck_warnings > warnings_target:
        failures.append(
            f"post_check_warning_count {postcheck_warnings} > target {warnings_target}"
        )

    if strict_phase_status != "PASS":
        failures.append(
            f"strict upstream parity phase status is {strict_phase_status}, expected PASS"
        )

    print("Parity Backlog Gate")
    print("===================")
    print(f"unsupported_markers: {unsupported_markers} (target <= {unsupported_target})")
    print(f"explicit_unsupported_functions: {explicit_actual} (target {explicit_target})")
    print(f"approximation_markers: {approx_markers} (target <= {approx_target})")
    print(f"post_check_warning_count: {postcheck_warnings} (target <= {warnings_target})")
    print(f"strict_phase_status: {strict_phase_status}")

    if failures:
        print("[FAIL] Gate failed")
        for item in failures:
            print(f"- {item}")
        return 1

    print("[PASS] Gate passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
