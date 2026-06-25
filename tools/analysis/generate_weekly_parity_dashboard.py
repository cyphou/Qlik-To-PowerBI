"""Generate a weekly parity dashboard artifact from phase run history."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[2]
PHASES_DIR = ROOT / "artifacts" / "reports" / "phases"
OUT_JSON = PHASES_DIR / "weekly_dashboard_latest.json"
OUT_MD = PHASES_DIR / "weekly_dashboard_latest.md"


def _load(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _collect_runs() -> List[Path]:
    return sorted(PHASES_DIR.glob("phase_run_*.json"))


def _run_row(path: Path) -> Dict[str, Any]:
    data = _load(path)
    metrics = data.get("metrics", {}) or {}
    return {
        "file": str(path),
        "generated_at_utc": data.get("generated_at_utc"),
        "overall_status": data.get("overall_status"),
        "unsupported_markers": metrics.get("unsupported_markers"),
        "approximation_markers": metrics.get("approximation_markers"),
        "post_check_warning_count": metrics.get("post_check_warning_count"),
        "fidelity_score": metrics.get("fidelity_score"),
    }


def main() -> int:
    runs = _collect_runs()
    rows = [_run_row(p) for p in runs[-20:]]

    latest = rows[-1] if rows else {}
    previous = rows[-2] if len(rows) > 1 else {}

    delta = {}
    for key in [
        "unsupported_markers",
        "approximation_markers",
        "post_check_warning_count",
        "fidelity_score",
    ]:
        if latest and previous and latest.get(key) is not None and previous.get(key) is not None:
            try:
                delta[key] = float(latest[key]) - float(previous[key])
            except Exception:
                delta[key] = None

    dashboard = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "runs_considered": len(rows),
        "latest": latest,
        "previous": previous,
        "delta": delta,
        "history": rows,
    }

    PHASES_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(dashboard, indent=2, ensure_ascii=False), encoding="utf-8")

    lines: List[str] = []
    lines.append("# Weekly Parity Dashboard")
    lines.append("")
    lines.append(f"- Generated at: {dashboard['generated_at_utc']}")
    lines.append(f"- Runs considered: {dashboard['runs_considered']}")
    lines.append("")

    if latest:
        lines.append("## Latest KPI")
        lines.append("")
        for key in [
            "overall_status",
            "unsupported_markers",
            "approximation_markers",
            "post_check_warning_count",
            "fidelity_score",
        ]:
            lines.append(f"- {key}: {latest.get(key)}")
        lines.append("")

    if delta:
        lines.append("## Delta vs Previous Run")
        lines.append("")
        for key, value in delta.items():
            lines.append(f"- {key}: {value}")
        lines.append("")

    lines.append("## Recent Runs")
    lines.append("")
    for row in rows[-10:]:
        lines.append(
            f"- {row.get('generated_at_utc')} | status={row.get('overall_status')} "
            f"| unsupported={row.get('unsupported_markers')} "
            f"| approx={row.get('approximation_markers')} "
            f"| warnings={row.get('post_check_warning_count')} "
            f"| fidelity={row.get('fidelity_score')}"
        )

    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("Weekly parity dashboard generated")
    print(f"json: {OUT_JSON}")
    print(f"md: {OUT_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
