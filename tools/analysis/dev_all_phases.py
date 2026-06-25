"""Developer execution mode for all phases.

This script is a developer-friendly wrapper around run_all_phases.py.
It executes all phases, then materializes execution artifacts:
- dev board JSON/Markdown with actionable status per backlog item
- one issue-ready Markdown file per backlog item

Usage:
  py -3 tools/analysis/dev_all_phases.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List


ROOT = Path(__file__).resolve().parents[2]
PHASES_DIR = ROOT / "artifacts" / "reports" / "phases"
BACKLOG_FILE = PHASES_DIR / "parity_backlog_latest.json"
LATEST_PHASES = PHASES_DIR / "latest.json"
ISSUES_DIR = PHASES_DIR / "issues"
DEV_BOARD_JSON = PHASES_DIR / "dev_board_latest.json"
DEV_BOARD_MD = PHASES_DIR / "dev_board_latest.md"


def _run_all_phases() -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "tools/analysis/run_all_phases.py"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def _load_json(path: Path) -> Dict[str, object]:
    if not path.exists():
        raise FileNotFoundError(f"Missing required artifact: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_slug(text: str) -> str:
    out = []
    for ch in text.lower():
        if ch.isalnum():
            out.append(ch)
        elif ch in ("-", "_", " "):
            out.append("-")
    slug = "".join(out)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-")


def _item_status(priority: str) -> str:
    # Initial sequencing strategy for development mode.
    return "next" if priority == "P0" else "queued"


def _build_dev_board(backlog: Dict[str, object], phase_report: Dict[str, object]) -> Dict[str, object]:
    epics_out: List[Dict[str, object]] = []
    total_items = 0

    for epic in backlog.get("epics", []):
        items_out = []
        priority = str(epic.get("priority", "P2"))
        for item in epic.get("items", []):
            total_items += 1
            items_out.append(
                {
                    "id": item.get("id"),
                    "title": item.get("title"),
                    "owner": item.get("owner"),
                    "estimate_days": item.get("estimate_days"),
                    "status": _item_status(priority),
                    "acceptance": item.get("acceptance", []),
                }
            )

        epics_out.append(
            {
                "id": epic.get("id"),
                "priority": priority,
                "goal": epic.get("goal"),
                "exit_criteria": epic.get("exit_criteria", {}),
                "items": items_out,
            }
        )

    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": {
            "phase_report": str(LATEST_PHASES),
            "backlog": str(BACKLOG_FILE),
        },
        "phase_overall_status": phase_report.get("overall_status", "unknown"),
        "phase_metrics": phase_report.get("metrics", {}),
        "summary": {
            "epics": len(epics_out),
            "items": total_items,
            "next_items": sum(
                1 for e in epics_out for i in e.get("items", []) if i.get("status") == "next"
            ),
            "queued_items": sum(
                1 for e in epics_out for i in e.get("items", []) if i.get("status") == "queued"
            ),
        },
        "epics": epics_out,
    }


def _write_issue_files(dev_board: Dict[str, object]) -> List[str]:
    ISSUES_DIR.mkdir(parents=True, exist_ok=True)
    written: List[str] = []

    for epic in dev_board.get("epics", []):
        priority = epic.get("priority", "P2")
        epic_id = epic.get("id", "EPIC")
        for item in epic.get("items", []):
            item_id = item.get("id", "ITEM")
            title = item.get("title", "Untitled")
            owner = item.get("owner", "Unassigned")
            estimate = item.get("estimate_days", "?")
            status = item.get("status", "queued")
            acceptance = item.get("acceptance", [])

            slug = _safe_slug(f"{item_id}-{title}")
            path = ISSUES_DIR / f"{slug}.md"

            lines = []
            lines.append(f"# {item_id} {title}")
            lines.append("")
            lines.append(f"- Epic: {epic_id}")
            lines.append(f"- Priority: {priority}")
            lines.append(f"- Owner: {owner}")
            lines.append(f"- Estimate (days): {estimate}")
            lines.append(f"- Status: {status}")
            lines.append("")
            lines.append("## Acceptance Criteria")
            lines.append("")
            for ac in acceptance:
                lines.append(f"- [ ] {ac}")
            lines.append("")
            lines.append("## Implementation Notes")
            lines.append("")
            lines.append("- Scope:")
            lines.append("- Risks:")
            lines.append("- Tests:")
            lines.append("- Docs updates:")
            lines.append("")

            path.write_text("\n".join(lines), encoding="utf-8")
            written.append(str(path))

    return written


def _to_markdown(dev_board: Dict[str, object], issue_paths: List[str]) -> str:
    lines: List[str] = []
    lines.append("# Dev All Phases Board")
    lines.append("")
    lines.append(f"- Generated at: {dev_board['generated_at_utc']}")
    lines.append(f"- Phase overall status: {dev_board['phase_overall_status']}")
    lines.append("")
    lines.append("## Metrics")
    lines.append("")
    for key, value in (dev_board.get("phase_metrics", {}) or {}).items():
        lines.append(f"- {key}: {value}")
    lines.append("")
    lines.append("## Execution Summary")
    lines.append("")
    summary = dev_board.get("summary", {})
    for key in ["epics", "items", "next_items", "queued_items"]:
        lines.append(f"- {key}: {summary.get(key)}")
    lines.append("")

    for epic in dev_board.get("epics", []):
        lines.append(f"## {epic.get('priority')} {epic.get('id')}")
        lines.append("")
        lines.append(f"- Goal: {epic.get('goal')}")
        lines.append("")
        lines.append("### Items")
        lines.append("")
        for item in epic.get("items", []):
            lines.append(
                f"- {item.get('id')} {item.get('title')}"
                f" (owner: {item.get('owner')}, status: {item.get('status')}, estimate: {item.get('estimate_days')}d)"
            )
        lines.append("")

    lines.append("## Issue Files")
    lines.append("")
    for p in issue_paths:
        lines.append(f"- {p}")

    lines.append("")
    return "\n".join(lines)


def main() -> int:
    phase_proc = _run_all_phases()
    if phase_proc.returncode != 0:
        print("run_all_phases failed")
        print(phase_proc.stdout)
        print(phase_proc.stderr)
        return phase_proc.returncode

    backlog = _load_json(BACKLOG_FILE)
    phase_report = _load_json(LATEST_PHASES)

    dev_board = _build_dev_board(backlog, phase_report)
    issue_paths = _write_issue_files(dev_board)

    PHASES_DIR.mkdir(parents=True, exist_ok=True)
    DEV_BOARD_JSON.write_text(json.dumps(dev_board, indent=2, ensure_ascii=False), encoding="utf-8")
    DEV_BOARD_MD.write_text(_to_markdown(dev_board, issue_paths), encoding="utf-8")

    print("Dev all phases complete")
    print(f"dev_board_json: {DEV_BOARD_JSON}")
    print(f"dev_board_md: {DEV_BOARD_MD}")
    print(f"issue_files: {len(issue_paths)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
