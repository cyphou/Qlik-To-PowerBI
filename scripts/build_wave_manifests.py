"""Build migration manifest files from a Qlik app portfolio template.

Supports CSV and JSON portfolio inputs and emits:
- one consolidated manifest with all selected apps
- one manifest per wave (Wave-0/1/2/3)

Example:
    python scripts/build_wave_manifests.py \
        --input docs/templates/QLIK_APP_PORTFOLIO_TEMPLATE.csv \
        --output-dir artifacts/manifests
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from collections import defaultdict
from typing import Any


DEFAULT_PROFILES: dict[str, dict[str, Any]] = {
    "fast": {
        "mode": "import",
        "bridge_tables": "none",
        "output_format": "pbip",
    },
    "strict": {
        "mode": "import",
        "bridge_tables": "auto",
        "output_format": "pbip",
    },
    "regulated": {
        "mode": "import",
        "bridge_tables": "auto",
        "output_format": "pbip",
        "culture": "en-US",
    },
}


def _parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    text = str(value).strip().lower()
    return text in {"1", "true", "yes", "y", "on"}


def _norm_text(value: Any) -> str:
    return str(value or "").strip()


def _auto_wave_for_app(app: dict[str, Any]) -> str:
    """Assign a wave from criticality/complexity signals when missing."""
    tier = _norm_text(app.get("complexity_tier")).upper()
    criticality = _norm_text(app.get("criticality")).lower()
    sec_access = _norm_text(app.get("section_access_complexity")).lower()
    has_extensions = _parse_bool(app.get("custom_extensions"))

    if tier == "C" and (criticality == "high" or sec_access == "high" or has_extensions):
        return "Wave-3"
    if tier == "C":
        return "Wave-2"
    if criticality == "high" or tier == "B":
        return "Wave-1"
    return "Wave-0"


def _load_csv_portfolio(path: str) -> list[dict[str, Any]]:
    with open(path, "r", encoding="utf-8", newline="") as f:
        return [dict(row) for row in csv.DictReader(f)]


def _load_json_portfolio(path: str) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    if isinstance(payload, list):
        return payload, {}, {}

    if not isinstance(payload, dict):
        raise ValueError("JSON input must be an object or array")

    apps = payload.get("apps", payload.get("entries", []))
    if not isinstance(apps, list):
        raise ValueError("JSON 'apps' (or 'entries') must be an array")

    defaults = payload.get("defaults", {})
    profiles = payload.get("profiles", {})
    if not isinstance(defaults, dict):
        defaults = {}
    if not isinstance(profiles, dict):
        profiles = {}
    return apps, defaults, profiles


def _build_entry(app: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    source_path = _norm_text(app.get("source_path") or app.get("file"))
    if not source_path:
        return {}

    profile = _norm_text(app.get("profile")) or args.default_profile
    entry: dict[str, Any] = {
        "file": source_path,
        "profile": profile,
    }

    culture = _norm_text(app.get("culture"))
    if culture:
        entry["culture"] = culture

    target_workspace = _norm_text(app.get("target_workspace"))
    if args.output_root and target_workspace:
        entry["output_dir"] = os.path.join(args.output_root, target_workspace)
    elif args.output_root:
        entry["output_dir"] = args.output_root

    # Optional artifact packs if portfolio includes them.
    transform_files = app.get("transform_files", [])
    config_files = app.get("config_files", [])
    if isinstance(transform_files, str) and transform_files.strip():
        entry["transform_files"] = [p.strip() for p in transform_files.split(";") if p.strip()]
    elif isinstance(transform_files, list) and transform_files:
        entry["transform_files"] = transform_files

    if isinstance(config_files, str) and config_files.strip():
        entry["config_files"] = [p.strip() for p in config_files.split(";") if p.strip()]
    elif isinstance(config_files, list) and config_files:
        entry["config_files"] = config_files

    return entry


def _write_json(path: str, payload: dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")


def _sanitize_wave_name(name: str) -> str:
    sanitized = _norm_text(name).replace(" ", "_")
    for ch in "<>:\"/\\|?*":
        sanitized = sanitized.replace(ch, "_")
    return sanitized or "Wave-0"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build migration manifest(s) from a Qlik app portfolio CSV/JSON.",
    )
    parser.add_argument("--input", required=True, help="Path to portfolio CSV or JSON")
    parser.add_argument(
        "--format",
        choices=["auto", "csv", "json"],
        default="auto",
        help="Input format. Default auto-detect from extension.",
    )
    parser.add_argument(
        "--output-dir",
        default=os.path.join("artifacts", "manifests"),
        help="Output directory for generated manifest files.",
    )
    parser.add_argument(
        "--default-profile",
        default="strict",
        help="Profile used when app row has no profile.",
    )
    parser.add_argument(
        "--waves",
        default="",
        help="Optional comma-separated wave filter (e.g. Wave-0,Wave-1).",
    )
    parser.add_argument(
        "--auto-wave",
        action="store_true",
        help="Infer wave from criticality/complexity when target_wave is missing.",
    )
    parser.add_argument(
        "--output-root",
        default="",
        help=(
            "Optional output root used to fill manifest entry output_dir. "
            "When target_workspace exists, output_dir becomes <output_root>/<workspace>."
        ),
    )
    parser.add_argument(
        "--include-profiles-template",
        action="store_true",
        help="Inject standard profile templates (fast/strict/regulated).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute and print summary without writing files.",
    )
    args = parser.parse_args()

    input_path = args.input
    fmt = args.format
    if fmt == "auto":
        ext = os.path.splitext(input_path)[1].lower()
        fmt = "json" if ext == ".json" else "csv"

    defaults: dict[str, Any] = {}
    profiles: dict[str, Any] = {}
    if fmt == "json":
        apps, defaults, profiles = _load_json_portfolio(input_path)
    else:
        apps = _load_csv_portfolio(input_path)

    selected_waves = {
        w.strip() for w in args.waves.split(",") if w.strip()
    }

    wave_entries: dict[str, list[dict[str, Any]]] = defaultdict(list)
    skipped_missing_file = 0

    for app in apps:
        entry = _build_entry(app, args)
        if not entry:
            skipped_missing_file += 1
            continue

        wave = _norm_text(app.get("target_wave"))
        if not wave and args.auto_wave:
            wave = _auto_wave_for_app(app)
        if not wave:
            wave = "Wave-0"

        if selected_waves and wave not in selected_waves:
            continue

        wave_entries[wave].append(entry)

    if args.include_profiles_template:
        merged_profiles = dict(DEFAULT_PROFILES)
        merged_profiles.update(profiles)
        profiles = merged_profiles

    all_entries: list[dict[str, Any]] = []
    for wave_name in sorted(wave_entries.keys()):
        all_entries.extend(wave_entries[wave_name])

    if not all_entries:
        print("No entries selected. Nothing to write.")
        return 1

    all_manifest = {
        "defaults": defaults,
        "profiles": profiles,
        "entries": all_entries,
    }

    if args.dry_run:
        print("Dry run summary")
        print(f"  Input apps:         {len(apps)}")
        print(f"  Entries emitted:    {len(all_entries)}")
        print(f"  Waves emitted:      {len(wave_entries)}")
        print(f"  Missing source_path:{skipped_missing_file}")
        for wave_name in sorted(wave_entries.keys()):
            print(f"  - {wave_name}: {len(wave_entries[wave_name])}")
        return 0

    os.makedirs(args.output_dir, exist_ok=True)

    all_path = os.path.join(args.output_dir, "all_apps_manifest.json")
    _write_json(all_path, all_manifest)

    emitted_paths = [all_path]
    for wave_name in sorted(wave_entries.keys()):
        payload = {
            "defaults": defaults,
            "profiles": profiles,
            "entries": wave_entries[wave_name],
        }
        wave_file = f"wave_{_sanitize_wave_name(wave_name)}_manifest.json"
        wave_path = os.path.join(args.output_dir, wave_file)
        _write_json(wave_path, payload)
        emitted_paths.append(wave_path)

    print("Generated manifest files:")
    for path in emitted_paths:
        print(f"  - {path}")
    print(f"Total entries: {len(all_entries)}")
    print(f"Skipped missing source_path/file: {skipped_missing_file}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
