"""Run and report all parity roadmap phases.

This script executes the roadmap in 5 phases and produces:
- A machine-readable JSON report
- A human-readable Markdown summary

Phases:
1) Local parity baseline check
2) Strict upstream parity check
3) Test suite snapshot
4) Real-sample migration + quality gate
5) Unsupported/approximation audit for DAX conversion

Usage:
  py -3 tools/analysis/run_all_phases.py
  py -3 tools/analysis/run_all_phases.py --max-postcheck-warnings 3
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional


ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "artifacts" / "reports" / "phases"
DEFAULT_SAMPLE = ROOT / "examples" / "qlik" / "test_samples" / "large" / "large_enterprise_sales.json"
DEFAULT_OUTPUT_DIR = ROOT / "output" / "phase_runs"
RUN_CAPTURE = DEFAULT_OUTPUT_DIR / "run_result.json"
BACKLOG_SCRIPT = ROOT / "tools" / "analysis" / "generate_parity_backlog.py"
WEEKLY_DASHBOARD_SCRIPT = ROOT / "tools" / "analysis" / "generate_weekly_parity_dashboard.py"


@dataclass
class PhaseResult:
    name: str
    command: Optional[List[str]]
    returncode: int
    status: str
    duration_seconds: float
    details: Dict[str, object]


def _run_cmd(cmd: List[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def _duration(start: datetime, end: datetime) -> float:
    return round((end - start).total_seconds(), 3)


def _tail(text: str, lines: int = 20) -> str:
    parts = text.splitlines()
    return "\n".join(parts[-lines:])


def _phase_cmd(name: str, cmd: List[str]) -> PhaseResult:
    start = datetime.now(timezone.utc)
    proc = _run_cmd(cmd, ROOT)
    end = datetime.now(timezone.utc)
    ok = proc.returncode == 0
    return PhaseResult(
        name=name,
        command=cmd,
        returncode=proc.returncode,
        status="PASS" if ok else "FAIL",
        duration_seconds=_duration(start, end),
        details={
            "stdout_tail": _tail(proc.stdout, 30),
            "stderr_tail": _tail(proc.stderr, 30),
        },
    )


def _extract_final_json(text: str) -> Dict[str, object]:
    lines = text.splitlines()
    start_idx = None
    for i, line in enumerate(lines):
        if line.strip() == "{":
            start_idx = i
            break
    if start_idx is None:
        raise ValueError("No JSON object found in migrate output")
    payload = "\n".join(lines[start_idx:])
    return json.loads(payload)


def _phase_unsupported_audit() -> PhaseResult:
    start = datetime.now(timezone.utc)
    path = ROOT / "qlik_export" / "dax_converter.py"
    text = path.read_text(encoding="utf-8")

    unsupported = re.findall(r"UNSUPPORTED:", text)
    approximate = re.findall(r"approx|approximate", text, flags=re.IGNORECASE)

    explicit_markers = {
        "Skew": "UNSUPPORTED: Skew",
        "Hash128": "UNSUPPORTED: Hash128",
        "Hash160": "UNSUPPORTED: Hash160",
        "Hash256": "UNSUPPORTED: Hash256",
        "Evaluate": "UNSUPPORTED: Evaluate",
    }
    explicit_hits = {
        key: (marker in text) for key, marker in explicit_markers.items()
    }

    end = datetime.now(timezone.utc)
    return PhaseResult(
        name="Phase 5 - Unsupported and approximation audit",
        command=None,
        returncode=0,
        status="PASS",
        duration_seconds=_duration(start, end),
        details={
            "unsupported_markers": len(unsupported),
            "approximation_markers": len(approximate),
            "explicit_unsupported_functions": explicit_hits,
        },
    )


def _write_reports(report: Dict[str, object], report_dir: Path) -> Dict[str, str]:
    report_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = report_dir / f"phase_run_{ts}.json"
    md_path = report_dir / f"phase_run_{ts}.md"
    latest_json = report_dir / "latest.json"
    latest_md = report_dir / "latest.md"

    json_payload = json.dumps(report, indent=2, ensure_ascii=False)
    json_path.write_text(json_payload, encoding="utf-8")
    latest_json.write_text(json_payload, encoding="utf-8")

    lines: List[str] = []
    lines.append("# Phase Run Summary")
    lines.append("")
    lines.append(f"- Generated at: {report['generated_at_utc']}")
    lines.append(f"- Overall status: {report['overall_status']}")
    lines.append(f"- Phases run: {len(report['phases'])}")
    lines.append("")
    lines.append("## Results")
    lines.append("")
    for phase in report["phases"]:
        lines.append(f"- {phase['name']}: {phase['status']} (rc={phase['returncode']}, {phase['duration_seconds']}s)")
    lines.append("")
    lines.append("## Key Metrics")
    lines.append("")
    metrics = report.get("metrics", {})
    for key, value in metrics.items():
        lines.append(f"- {key}: {value}")

    md_payload = "\n".join(lines) + "\n"
    md_path.write_text(md_payload, encoding="utf-8")
    latest_md.write_text(md_payload, encoding="utf-8")

    return {
        "json": str(json_path),
        "markdown": str(md_path),
        "latest_json": str(latest_json),
        "latest_markdown": str(latest_md),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run all parity roadmap phases")
    parser.add_argument("--sample", default=str(DEFAULT_SAMPLE), help="Real sample input file")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Migration output directory")
    parser.add_argument("--max-postcheck-warnings", type=int, default=5)
    args = parser.parse_args()

    sample = Path(args.sample)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    phases: List[PhaseResult] = []

    # Phase 1
    phases.append(
        _phase_cmd(
            "Phase 1 - Local parity baseline",
            [sys.executable, "tools/analysis/parity_status_check.py"],
        )
    )

    # Phase 2
    phases.append(
        _phase_cmd(
            "Phase 2 - Upstream strict parity",
            [
                sys.executable,
                "tools/analysis/agent_feature_parity_check.py",
                "--upstream-repo",
                "cyphou/Qlik-To-PowerBI",
                "--strict-upstream",
            ],
        )
    )

    # Phase 3
    phases.append(
        _phase_cmd(
            "Phase 3 - Full test suite",
            [sys.executable, "-m", "pytest", "tests/", "-q", "--tb=short"],
        )
    )

    # Phase 4a: real sample run
    phase4a = _phase_cmd(
        "Phase 4A - Real sample migration",
        [
            sys.executable,
            "migrate.py",
            str(sample),
            "--output-dir",
            str(output_dir),
            "--self-heal-v3",
            "--post-check",
            "--json",
        ],
    )

    # Persist full stdout for quality gate parser
    RUN_CAPTURE.write_text(phase4a.details.get("stdout_tail", ""), encoding="utf-8")
    # Keep full output too for traceability
    full_capture = output_dir / "run_result_full.log"
    if phase4a.command is not None:
        proc_full = _run_cmd(phase4a.command, ROOT)
        full_capture.write_text(proc_full.stdout, encoding="utf-8")
        RUN_CAPTURE.write_text(proc_full.stdout, encoding="utf-8")
        phase4a.returncode = proc_full.returncode
        phase4a.status = "PASS" if proc_full.returncode == 0 else "FAIL"
        phase4a.details["stdout_tail"] = _tail(proc_full.stdout, 30)
        phase4a.details["stderr_tail"] = _tail(proc_full.stderr, 30)

    phases.append(phase4a)

    # Phase 4b: quality gate on captured output
    phase4b = _phase_cmd(
        "Phase 4B - Quality gate",
        [
            sys.executable,
            "tools/testing/real_sample_quality_gate.py",
            "--run-json",
            str(RUN_CAPTURE),
            "--max-postcheck-warnings",
            str(args.max_postcheck_warnings),
        ],
    )

    # enrich with parsed metrics when possible
    try:
        parsed = _extract_final_json(RUN_CAPTURE.read_text(encoding="utf-8"))
        post_check = parsed.get("post_check", {}) or {}
        phase4b.details["migration_status"] = parsed.get("status")
        phase4b.details["fidelity_score"] = parsed.get("fidelity_score")
        phase4b.details["post_check_warning_count"] = len(post_check.get("warnings", []) or [])
        phase4b.details["post_check_error_count"] = len(post_check.get("errors", []) or [])
    except Exception as exc:
        phase4b.details["parse_error"] = str(exc)

    phases.append(phase4b)

    # Phase 5
    phases.append(_phase_unsupported_audit())

    overall_ok = all(p.status == "PASS" for p in phases)

    metrics: Dict[str, object] = {}
    for p in phases:
        if p.name.startswith("Phase 4B"):
            for k in [
                "migration_status",
                "fidelity_score",
                "post_check_warning_count",
                "post_check_error_count",
            ]:
                if k in p.details:
                    metrics[k] = p.details[k]
        if p.name.startswith("Phase 5"):
            metrics["unsupported_markers"] = p.details.get("unsupported_markers")
            metrics["approximation_markers"] = p.details.get("approximation_markers")
            metrics["explicit_unsupported_functions"] = p.details.get("explicit_unsupported_functions")

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "overall_status": "PASS" if overall_ok else "FAIL",
        "phases": [asdict(p) for p in phases],
        "metrics": metrics,
        "artifacts": {
            "migration_run_capture": str(RUN_CAPTURE),
            "migration_run_full_log": str(output_dir / "run_result_full.log"),
        },
    }

    report_paths = _write_reports(report, REPORT_DIR)

    backlog_status = "SKIPPED"
    backlog_stdout = ""
    if BACKLOG_SCRIPT.exists():
        backlog_proc = _run_cmd([sys.executable, str(BACKLOG_SCRIPT)], ROOT)
        backlog_status = "PASS" if backlog_proc.returncode == 0 else "FAIL"
        backlog_stdout = _tail(backlog_proc.stdout, 10)
        report["backlog_generation"] = {
            "status": backlog_status,
            "returncode": backlog_proc.returncode,
            "stdout_tail": backlog_stdout,
            "stderr_tail": _tail(backlog_proc.stderr, 10),
        }
        report_paths = _write_reports(report, REPORT_DIR)

    dashboard_status = "SKIPPED"
    dashboard_stdout = ""
    if WEEKLY_DASHBOARD_SCRIPT.exists():
        dashboard_proc = _run_cmd([sys.executable, str(WEEKLY_DASHBOARD_SCRIPT)], ROOT)
        dashboard_status = "PASS" if dashboard_proc.returncode == 0 else "FAIL"
        dashboard_stdout = _tail(dashboard_proc.stdout, 10)
        report["weekly_dashboard_generation"] = {
            "status": dashboard_status,
            "returncode": dashboard_proc.returncode,
            "stdout_tail": dashboard_stdout,
            "stderr_tail": _tail(dashboard_proc.stderr, 10),
        }
        report_paths = _write_reports(report, REPORT_DIR)

    print("Phase execution complete")
    print("========================")
    print(f"overall: {report['overall_status']}")
    for p in phases:
        print(f"- {p.name}: {p.status} (rc={p.returncode}, {p.duration_seconds}s)")
    print(f"report_json: {report_paths['json']}")
    print(f"report_md: {report_paths['markdown']}")
    print(f"backlog_generation: {backlog_status}")
    if backlog_stdout:
        print(backlog_stdout)
    print(f"weekly_dashboard_generation: {dashboard_status}")
    if dashboard_stdout:
        print(dashboard_stdout)

    return 0 if overall_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
