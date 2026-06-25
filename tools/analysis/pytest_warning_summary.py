"""Summarize warning trends from a pytest output log.

Input:
- pytest text output file

Output:
- JSON summary with total warnings and top categories
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Dict


WARNING_RE = re.compile(r"\b([A-Za-z_]+Warning)\b")


def _parse_warnings(text: str) -> Dict[str, object]:
    matches = WARNING_RE.findall(text)
    counter = Counter(matches)
    total = sum(counter.values())

    deprecation_count = counter.get("DeprecationWarning", 0)

    top = [{"name": name, "count": count} for name, count in counter.most_common(10)]
    return {
        "total_warning_mentions": total,
        "deprecation_warning_mentions": deprecation_count,
        "top_warning_types": top,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize pytest warning trends")
    parser.add_argument("--pytest-log", required=True, help="Path to pytest output log")
    parser.add_argument("--output-json", required=True, help="Path to output summary JSON")
    parser.add_argument("--output-md", default=None, help="Optional markdown summary output")
    args = parser.parse_args()

    log_path = Path(args.pytest_log)
    if not log_path.exists():
        print(f"[FAIL] Missing pytest log: {log_path}")
        return 2

    text = log_path.read_text(encoding="utf-8", errors="replace")
    summary = _parse_warnings(text)

    out_json = Path(args.output_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    if args.output_md:
        out_md = Path(args.output_md)
        lines = []
        lines.append("# Pytest Warning Summary")
        lines.append("")
        lines.append(f"- total_warning_mentions: {summary['total_warning_mentions']}")
        lines.append(f"- deprecation_warning_mentions: {summary['deprecation_warning_mentions']}")
        lines.append("")
        lines.append("## Top Warning Types")
        lines.append("")
        for item in summary["top_warning_types"]:
            lines.append(f"- {item['name']}: {item['count']}")
        lines.append("")
        out_md.parent.mkdir(parents=True, exist_ok=True)
        out_md.write_text("\n".join(lines), encoding="utf-8")

    print("Pytest warning summary generated")
    print(f"json: {out_json}")
    if args.output_md:
        print(f"md: {args.output_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
