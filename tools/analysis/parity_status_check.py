"""Repository parity and drift checker.

Checks core consistency claims used by docs and release workflow:
- version alignment
- required v12 modules
- required v12 CLI flags in migrate.py

Exit code:
- 0: all checks passed
- 1: one or more checks failed
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


REQUIRED_MODULES = [
    "powerbi_import/preceptor.py",
    "powerbi_import/self_healing_v3.py",
    "powerbi_import/repair_strategies.py",
    "powerbi_import/self_healing_report.py",
    "powerbi_import/cutover_manager.py",
    "powerbi_import/full_lineage.py",
    "powerbi_import/pdf_renderer.py",
    "powerbi_import/pptx_report.py",
    "powerbi_import/report_packager.py",
    "powerbi_import/goals_generator.py",
    "powerbi_import/script_lineage.py",
    "powerbi_import/script_lineage_report.py",
    "powerbi_import/automation.py",
]

REQUIRED_FLAGS = [
    "--preceptor-review",
    "--self-heal-v3",
    "--repair-strategies",
    "--cutover-plan",
    "--full-lineage",
    "--pdf-report",
    "--pptx-report",
    "--package",
    "--goals",
    "--script-lineage",
]

REQUIRED_README_LINKS = [
    "docs/DEV_PLAN_v12.md",
    "docs/reports/ROADMAP_STATUS_2026-06-24.md",
    "tools/analysis/parity_status_check.py",
]

REQUIRED_DOC_FILES = [
    "docs/DEV_PLAN_v12.md",
    "docs/reports/ROADMAP_STATUS_2026-06-24.md",
]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def extract_version(pattern: str, text: str) -> str | None:
    match = re.search(pattern, text, re.MULTILINE)
    return match.group(1) if match else None


def check_versions(repo_root: Path) -> dict:
    pyproject = read_text(repo_root / "pyproject.toml")
    pbi_init = read_text(repo_root / "powerbi_import" / "__init__.py")
    qlik_init = read_text(repo_root / "qlik_export" / "__init__.py")

    expected = extract_version(r'^version\s*=\s*"([^"]+)"', pyproject)
    powerbi_version = extract_version(r"__version__\s*=\s*'([^']+)'", pbi_init)
    qlik_version = extract_version(r"__version__\s*=\s*'([^']+)'", qlik_init)

    errors = []
    if expected is None:
        errors.append("Cannot parse project version from pyproject.toml")
    if powerbi_version is None:
        errors.append("Cannot parse powerbi_import package version")
    if qlik_version is None:
        errors.append("Cannot parse qlik_export package version")

    if expected and powerbi_version and expected != powerbi_version:
        errors.append(
            f"Version mismatch: pyproject={expected}, powerbi_import={powerbi_version}"
        )
    if expected and qlik_version and expected != qlik_version:
        errors.append(
            f"Version mismatch: pyproject={expected}, qlik_export={qlik_version}"
        )

    return {
        "check": "versions",
        "expected": expected,
        "powerbi_import": powerbi_version,
        "qlik_export": qlik_version,
        "ok": len(errors) == 0,
        "errors": errors,
    }


def check_modules(repo_root: Path) -> dict:
    missing = [rel for rel in REQUIRED_MODULES if not (repo_root / rel).exists()]
    return {
        "check": "required_modules",
        "required_count": len(REQUIRED_MODULES),
        "missing": missing,
        "ok": len(missing) == 0,
    }


def check_flags(repo_root: Path) -> dict:
    migrate_text = read_text(repo_root / "migrate.py")
    missing = [flag for flag in REQUIRED_FLAGS if flag not in migrate_text]
    return {
        "check": "required_flags",
        "required_count": len(REQUIRED_FLAGS),
        "missing": missing,
        "ok": len(missing) == 0,
    }


def check_docs(repo_root: Path) -> dict:
    pyproject = read_text(repo_root / "pyproject.toml")
    readme = read_text(repo_root / "README.md")

    expected = extract_version(r'^version\s*=\s*"([^"]+)"', pyproject)
    badge_token = f"version-{expected}" if expected else None

    missing_readme_links = [
        link for link in REQUIRED_README_LINKS if link not in readme
    ]
    missing_doc_files = [
        rel for rel in REQUIRED_DOC_FILES if not (repo_root / rel).exists()
    ]

    errors = []
    if expected is None:
        errors.append("Cannot parse project version for README badge validation")
    elif badge_token not in readme:
        errors.append(
            f"README version badge does not contain expected token: {badge_token}"
        )

    return {
        "check": "docs_consistency",
        "expected_version": expected,
        "missing_readme_links": missing_readme_links,
        "missing_doc_files": missing_doc_files,
        "ok": len(errors) == 0
        and len(missing_readme_links) == 0
        and len(missing_doc_files) == 0,
        "errors": errors,
    }


def build_report(repo_root: Path) -> dict:
    results = [
        check_versions(repo_root),
        check_modules(repo_root),
        check_flags(repo_root),
        check_docs(repo_root),
    ]
    return {
        "repo": str(repo_root),
        "all_ok": all(r["ok"] for r in results),
        "results": results,
    }


def print_human(report: dict) -> None:
    print("Parity Status Check")
    print("===================")
    print(f"Repository: {report['repo']}")
    print(f"Overall: {'PASS' if report['all_ok'] else 'FAIL'}")

    for result in report["results"]:
        name = result["check"]
        status = "PASS" if result["ok"] else "FAIL"
        print(f"\n[{status}] {name}")

        if name == "versions":
            print(f"  expected: {result['expected']}")
            print(f"  powerbi_import: {result['powerbi_import']}")
            print(f"  qlik_export: {result['qlik_export']}")
            for err in result.get("errors", []):
                print(f"  - {err}")

        if name in {"required_modules", "required_flags"}:
            missing = result["missing"]
            if missing:
                print("  missing:")
                for item in missing:
                    print(f"  - {item}")
            else:
                print("  missing: none")

        if name == "docs_consistency":
            print(f"  expected_version: {result['expected_version']}")
            for err in result.get("errors", []):
                print(f"  - {err}")
            if result["missing_readme_links"]:
                print("  missing_readme_links:")
                for link in result["missing_readme_links"]:
                    print(f"  - {link}")
            else:
                print("  missing_readme_links: none")
            if result["missing_doc_files"]:
                print("  missing_doc_files:")
                for rel in result["missing_doc_files"]:
                    print(f"  - {rel}")
            else:
                print("  missing_doc_files: none")


def main() -> int:
    parser = argparse.ArgumentParser(description="Check parity/status drift")
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root path (default: current directory)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Emit JSON report",
    )
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    report = build_report(repo_root)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_human(report)

    return 0 if report["all_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
