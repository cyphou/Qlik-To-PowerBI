"""Quality gate for real-sample migration JSON output.

Reads a migrate.py --json output capture (which may contain log lines before
final JSON), extracts the final JSON object, and enforces warning thresholds.

Usage:
  python tools/testing/real_sample_quality_gate.py \
      --run-json output/nightly/run_result.json \
      --max-postcheck-warnings 5
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict


def _extract_final_json(text: str) -> Dict[str, Any]:
    lines = text.splitlines()
    start_idx = None
    for i, line in enumerate(lines):
        if line.strip() == "{":
            start_idx = i
            break
    if start_idx is None:
        raise ValueError("No JSON object found in run output")
    payload = "\n".join(lines[start_idx:])
    return json.loads(payload)


def main() -> int:
    parser = argparse.ArgumentParser(description="Quality gate for real-sample migrate output")
    parser.add_argument("--run-json", required=True, help="Path to captured migrate output")
    parser.add_argument("--max-postcheck-warnings", type=int, default=5)
    args = parser.parse_args()

    run_path = Path(args.run_json)
    if not run_path.exists():
        print(f"[FAIL] Missing run output: {run_path}")
        return 2

    text = run_path.read_text(encoding="utf-8")
    result = _extract_final_json(text)

    status = result.get("status", "unknown")
    fidelity = float(result.get("fidelity_score", 0.0))
    post_check = result.get("post_check", {}) or {}
    warnings = post_check.get("warnings", []) or []

    warning_count = len(warnings)
    print("Quality Gate Summary")
    print("====================")
    print(f"status: {status}")
    print(f"fidelity_score: {fidelity}")
    print(f"post_check_warnings: {warning_count}")
    print(f"max_allowed: {args.max_postcheck_warnings}")

    if status != "success":
        print("[FAIL] Migration status is not success")
        return 1

    if warning_count > args.max_postcheck_warnings:
        print("[FAIL] Warning threshold exceeded")
        return 1

    print("[PASS] Quality gate passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
