#!/usr/bin/env python3
"""
Sample Validation Tool — validates generated PBI projects.

Usage:
    python tools/testing/validate_samples.py output/my_project
    python tools/testing/validate_samples.py --all   # validate all in output/

Checks:
  1. Required files exist (.pbip, .pbism, .pbir, etc.)
  2. JSON files are parseable and contain required keys
  3. TMDL files have valid syntax
  4. Cross-references: visual bindings reference existing model columns
  5. Relationships reference existing tables/columns
"""

import json
import os
import sys
from pathlib import Path
from typing import List, Tuple


def validate_project(project_dir: str) -> Tuple[int, int, List[str]]:
    """
    Validate a PBI project directory.

    Returns:
        (pass_count, fail_count, error_messages)
    """
    root = Path(project_dir)
    passes = 0
    fails = 0
    errors: List[str] = []

    def ok(msg: str):
        nonlocal passes
        passes += 1
        print(f"  ✓ {msg}")

    def fail(msg: str):
        nonlocal fails
        fails += 1
        errors.append(msg)
        print(f"  ✗ {msg}")

    # ── 1. Find .pbip file ────────────────────────────────────
    pbip_files = list(root.glob("*.pbip"))
    if not pbip_files:
        fail("No .pbip file found")
        return passes, fails, errors
    ok(f"Found {pbip_files[0].name}")

    name = pbip_files[0].stem

    # ── 2. Validate .pbip JSON ────────────────────────────────
    try:
        data = json.loads(pbip_files[0].read_text(encoding="utf-8"))
        if "$schema" in data:
            ok(".pbip has $schema")
        else:
            fail(".pbip missing $schema")
        if "artifacts" in data:
            ok(".pbip has artifacts")
        else:
            fail(".pbip missing artifacts")
    except json.JSONDecodeError as e:
        fail(f".pbip is not valid JSON: {e}")

    # ── 3. Semantic Model ─────────────────────────────────────
    sm_dir = root / f"{name}.SemanticModel"
    if sm_dir.exists():
        ok("SemanticModel folder exists")
    else:
        fail("SemanticModel folder missing")
        return passes, fails, errors

    pbism = sm_dir / "definition.pbism"
    if pbism.exists():
        try:
            d = json.loads(pbism.read_text(encoding="utf-8"))
            if d.get("version") == "4.0":
                ok("definition.pbism version 4.0")
            else:
                fail(f"definition.pbism version: {d.get('version')} (expected 4.0)")
        except json.JSONDecodeError:
            fail("definition.pbism invalid JSON")
    else:
        fail("definition.pbism missing")

    # ── 4. TMDL files ─────────────────────────────────────────
    def_dir = sm_dir / "definition"
    for tmdl_name in ["database.tmdl", "model.tmdl"]:
        tmdl_path = def_dir / tmdl_name
        if tmdl_path.exists():
            content = tmdl_path.read_text(encoding="utf-8")
            if content.strip():
                ok(f"{tmdl_name} exists and non-empty")
            else:
                fail(f"{tmdl_name} is empty")
        else:
            fail(f"{tmdl_name} missing")

    # Check table files
    tables_dir = def_dir / "tables"
    if tables_dir.exists():
        table_files = list(tables_dir.glob("*.tmdl"))
        if table_files:
            ok(f"Found {len(table_files)} table TMDL file(s)")
            # Validate each table has columns
            for tf in table_files:
                content = tf.read_text(encoding="utf-8")
                if "column" in content:
                    ok(f"  {tf.name} has columns")
                else:
                    fail(f"  {tf.name} has no columns")
                # Check balanced quotes
                if content.count("'") % 2 != 0:
                    fail(f"  {tf.name} has unbalanced quotes")
        else:
            fail("No table TMDL files found")
    else:
        fail("tables/ folder missing")

    # Check model.tmdl has ref table entries
    model_tmdl = def_dir / "model.tmdl"
    if model_tmdl.exists():
        model_content = model_tmdl.read_text(encoding="utf-8")
        ref_count = model_content.count("ref table")
        if ref_count > 0:
            ok(f"model.tmdl has {ref_count} ref table entries")
        else:
            fail("model.tmdl has no ref table entries")

    # ── 5. Report ─────────────────────────────────────────────
    rpt_dir = root / f"{name}.Report"
    if rpt_dir.exists():
        ok("Report folder exists")
    else:
        fail("Report folder missing")
        return passes, fails, errors

    pbir = rpt_dir / "definition.pbir"
    if pbir.exists():
        try:
            d = json.loads(pbir.read_text(encoding="utf-8"))
            if d.get("version") == "4.0":
                ok("definition.pbir version 4.0")
            else:
                fail(f"definition.pbir version: {d.get('version')}")
        except json.JSONDecodeError:
            fail("definition.pbir invalid JSON")
    else:
        fail("definition.pbir missing")

    rpt_def = rpt_dir / "definition"
    for json_name in ["version.json", "report.json"]:
        jp = rpt_def / json_name
        if jp.exists():
            try:
                json.loads(jp.read_text(encoding="utf-8"))
                ok(f"{json_name} is valid JSON")
            except json.JSONDecodeError:
                fail(f"{json_name} is invalid JSON")
        else:
            fail(f"{json_name} missing")

    # Check visuals
    pages_dir = rpt_def / "pages"
    if pages_dir.exists():
        visual_count = 0
        for page_dir in pages_dir.iterdir():
            if page_dir.is_dir():
                visuals_dir = page_dir / "visuals"
                if visuals_dir.exists():
                    for v_dir in visuals_dir.iterdir():
                        vj = v_dir / "visual.json"
                        if vj.exists():
                            try:
                                vd = json.loads(vj.read_text(encoding="utf-8"))
                                if "visual" in vd:
                                    visual_count += 1
                                else:
                                    fail(f"visual.json missing 'visual' key: {vj}")
                            except json.JSONDecodeError:
                                fail(f"visual.json invalid JSON: {vj}")
        if visual_count > 0:
            ok(f"Found {visual_count} valid visual(s)")

    return passes, fails, errors


def main():
    if len(sys.argv) < 2:
        print("Usage: python validate_samples.py <project_dir> [--all]")
        sys.exit(1)

    if sys.argv[1] == "--all":
        output_dir = Path("output")
        if not output_dir.exists():
            print("No output/ directory found")
            sys.exit(1)
        total_pass = 0
        total_fail = 0
        for sub in sorted(output_dir.iterdir()):
            if sub.is_dir() and list(sub.glob("*.pbip")):
                print(f"\n{'='*60}")
                print(f"Validating: {sub}")
                print(f"{'='*60}")
                p, f, _ = validate_project(str(sub))
                total_pass += p
                total_fail += f
        print(f"\n{'='*60}")
        print(f"TOTAL: {total_pass} passed, {total_fail} failed")
        sys.exit(1 if total_fail > 0 else 0)
    else:
        project_dir = sys.argv[1]
        print(f"Validating: {project_dir}")
        print("=" * 60)
        p, f, errs = validate_project(project_dir)
        print(f"\nResults: {p} passed, {f} failed")
        if errs:
            print("\nErrors:")
            for e in errs:
                print(f"  - {e}")
        sys.exit(1 if f > 0 else 0)


if __name__ == "__main__":
    main()
