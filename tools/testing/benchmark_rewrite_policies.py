"""Benchmark rewrite-policy effectiveness on residual autoheal errors.

Runs migrate.py across a QVF corpus for each policy:
- conservative
- balanced
- aggressive

Outputs:
- policy_benchmark_runs.json
- policy_benchmark_runs.csv
- policy_benchmark_summary.json
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, List


POLICIES = ["conservative", "balanced", "aggressive"]


@dataclass
class RunRow:
    app: str
    path: str
    policy: str
    status: str
    openable: bool
    stage: str
    duration_seconds: float
    autoheal_actions: int
    residual_errors: int
    initial_blocking_total: int
    final_blocking_total: int


def _parse_json_from_raw(raw: str) -> Dict:
    idx = raw.find("{")
    if idx < 0:
        return {}
    try:
        return json.loads(raw[idx:])
    except Exception:
        return {}


def _collect_qvf(root: str, recursive: bool) -> List[str]:
    out: List[str] = []
    if recursive:
        for r, _dirs, files in os.walk(root):
            for f in files:
                if f.lower().endswith(".qvf"):
                    out.append(os.path.join(r, f))
    else:
        for f in os.listdir(root):
            p = os.path.join(root, f)
            if os.path.isfile(p) and f.lower().endswith(".qvf"):
                out.append(p)
    return sorted(out)


def _run_migration(
    python_exe: str,
    repo_root: str,
    app_path: str,
    output_root: str,
    policy: str,
    skip_extraction: bool,
    strict_mode: bool,
) -> Dict:
    cmd = [
        python_exe,
        "migrate.py",
        app_path,
        "--output-dir",
        output_root,
        "--verify-open",
        "--json",
        "--quiet",
        "--rewrite-policy",
        policy,
    ]
    if skip_extraction:
        cmd.append("--skip-extraction")
    if strict_mode:
        cmd.append("--ensure-open-strict")

    proc = subprocess.run(
        cmd,
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    raw = (proc.stdout or "") + "\n" + (proc.stderr or "")
    parsed = _parse_json_from_raw(raw)
    if not parsed:
        return {
            "status": "parse_error",
            "duration_seconds": 0.0,
            "ensure_open": {},
        }
    return parsed


def _to_row(app_path: str, policy: str, result: Dict) -> RunRow:
    ensure = result.get("ensure_open") or {}
    final = ensure.get("final") or {}
    autoheal = ensure.get("autoheal") or {}
    taxonomy = ensure.get("root_cause_taxonomy") or {}
    initial_tax = taxonomy.get("initial") or {}
    final_tax = taxonomy.get("final") or {}
    residual = len(autoheal.get("remaining_errors") or [])

    return RunRow(
        app=os.path.basename(app_path),
        path=app_path,
        policy=policy,
        status=str(result.get("status", "error")),
        openable=bool(final.get("openable", ensure.get("openable", False))),
        stage=str(ensure.get("stage", "none")),
        duration_seconds=float(result.get("duration_seconds") or 0.0),
        autoheal_actions=int((ensure.get("autoheal_metrics") or {}).get("action_count", 0) or 0),
        residual_errors=int(residual),
        initial_blocking_total=int(initial_tax.get("total_blocking", 0) or 0),
        final_blocking_total=int(final_tax.get("total_blocking", 0) or 0),
    )


def _summarize(rows: List[RunRow]) -> Dict:
    by_policy: Dict[str, Dict] = {}
    for p in POLICIES:
        p_rows = [r for r in rows if r.policy == p]
        n = len(p_rows)
        if n == 0:
            by_policy[p] = {
                "runs": 0,
                "openable_rate": 0.0,
                "avg_duration_seconds": 0.0,
                "avg_autoheal_actions": 0.0,
                "avg_residual_errors": 0.0,
            }
            continue
        by_policy[p] = {
            "runs": n,
            "openable_rate": sum(1 for r in p_rows if r.openable) / n,
            "avg_duration_seconds": sum(r.duration_seconds for r in p_rows) / n,
            "avg_autoheal_actions": sum(r.autoheal_actions for r in p_rows) / n,
            "avg_residual_errors": sum(r.residual_errors for r in p_rows) / n,
        }

    baseline = by_policy["conservative"]["avg_residual_errors"]
    for p in POLICIES:
        current = by_policy[p]["avg_residual_errors"]
        if baseline > 0:
            by_policy[p]["residual_error_reduction_vs_conservative"] = (baseline - current) / baseline
        else:
            by_policy[p]["residual_error_reduction_vs_conservative"] = 0.0

    return {
        "generated_at": datetime.now().isoformat(),
        "policies": by_policy,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark rewrite-policy effectiveness")
    parser.add_argument("--input-root", default="c:\\QlikToPowerBI")
    parser.add_argument("--output-root", default="c:\\QlikToPowerBI\\migrated_output_policy_benchmark")
    parser.add_argument("--recursive", action="store_true")
    parser.add_argument("--skip-extraction", action="store_true")
    parser.add_argument("--strict-mode", action="store_true")
    parser.add_argument("--max-apps", type=int, default=0, help="0 means all apps")
    parser.add_argument(
        "--min-aggressive-reduction-vs-conservative",
        type=float,
        default=None,
        help="Fail if aggressive residual-error reduction vs conservative is below this ratio (e.g. 0.30)",
    )
    parser.add_argument(
        "--min-openable-rate",
        type=float,
        default=None,
        help="Fail if any policy openable_rate falls below this ratio (e.g. 0.99)",
    )
    args = parser.parse_args()

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    python_exe = sys.executable

    if not os.path.isdir(args.input_root):
        print(f"Input root not found: {args.input_root}")
        return 2

    apps = _collect_qvf(args.input_root, recursive=bool(args.recursive))
    if not apps:
        print(f"No QVF files found under: {args.input_root}")
        return 0

    if args.max_apps and args.max_apps > 0:
        apps = apps[: args.max_apps]

    os.makedirs(args.output_root, exist_ok=True)

    rows: List[RunRow] = []
    for app in apps:
        for policy in POLICIES:
            result = _run_migration(
                python_exe=python_exe,
                repo_root=repo_root,
                app_path=app,
                output_root=args.output_root,
                policy=policy,
                skip_extraction=bool(args.skip_extraction),
                strict_mode=bool(args.strict_mode),
            )
            row = _to_row(app, policy, result)
            rows.append(row)
            print(
                f"{row.app} | policy={row.policy} | status={row.status} | "
                f"openable={row.openable} | residual={row.residual_errors} | actions={row.autoheal_actions}"
            )

    summary = _summarize(rows)

    runs_json = os.path.join(args.output_root, "policy_benchmark_runs.json")
    runs_csv = os.path.join(args.output_root, "policy_benchmark_runs.csv")
    summary_json = os.path.join(args.output_root, "policy_benchmark_summary.json")

    with open(runs_json, "w", encoding="utf-8") as f:
        json.dump([asdict(r) for r in rows], f, indent=2, ensure_ascii=False)

    with open(runs_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(asdict(rows[0]).keys()))
        writer.writeheader()
        for r in rows:
            writer.writerow(asdict(r))

    with open(summary_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print("")
    print(f"RUNS_JSON={runs_json}")
    print(f"RUNS_CSV={runs_csv}")
    print(f"SUMMARY_JSON={summary_json}")

    policies = summary.get("policies") or {}
    failure_reasons: List[str] = []

    min_reduction = args.min_aggressive_reduction_vs_conservative
    if min_reduction is not None:
        aggressive_reduction = float(
            (policies.get("aggressive") or {}).get("residual_error_reduction_vs_conservative", 0.0)
        )
        if aggressive_reduction < float(min_reduction):
            failure_reasons.append(
                f"aggressive reduction {aggressive_reduction:.4f} < required {float(min_reduction):.4f}"
            )

    min_openable = args.min_openable_rate
    if min_openable is not None:
        threshold = float(min_openable)
        for policy in POLICIES:
            rate = float((policies.get(policy) or {}).get("openable_rate", 0.0))
            if rate < threshold:
                failure_reasons.append(
                    f"{policy} openable_rate {rate:.4f} < required {threshold:.4f}"
                )

    if failure_reasons:
        print("BENCHMARK_GATE=FAIL")
        for reason in failure_reasons:
            print(f"GATE_REASON={reason}")
        return 1

    if min_reduction is not None or min_openable is not None:
        print("BENCHMARK_GATE=PASS")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
