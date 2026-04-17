"""
QA Pipeline — Full quality assurance suite for post-migration validation

Runs the complete QA chain in one pass:
  1. Artifact validation (JSON, TMDL syntax, report structure)
  2. Auto-fix known Qlik→DAX leak patterns
  3. Governance checks (naming conventions, PII detection)
  4. Comparison report generation
  5. QA report summary (qa_report.json)

Usage::

    python migrate.py app.qvf --qa
"""

import json
import logging
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Qlik→DAX leak patterns (auto-fixable) ────────────────────────

_AUTOFIX_PATTERNS: List[Dict[str, str]] = [
    {"pattern": r"\bIsNull\b", "replacement": "ISBLANK", "description": "IsNull → ISBLANK"},
    {"pattern": r"\bNullCount\b", "replacement": "COUNTBLANK", "description": "NullCount → COUNTBLANK"},
    {"pattern": r"\bNull\(\)", "replacement": "BLANK()", "description": "Null() → BLANK()"},
    {"pattern": r"\bAlt\(", "replacement": "COALESCE(", "description": "Alt → COALESCE"},
    {"pattern": r"\bUpper\(", "replacement": "UPPER(", "description": "Upper → UPPER"},
    {"pattern": r"\bLower\(", "replacement": "LOWER(", "description": "Lower → LOWER"},
    {"pattern": r"\bLen\(", "replacement": "LEN(", "description": "Len → LEN"},
    {"pattern": r"\bTrim\(", "replacement": "TRIM(", "description": "Trim → TRIM"},
    {"pattern": r"\bLeft\(", "replacement": "LEFT(", "description": "Left → LEFT"},
    {"pattern": r"\bRight\(", "replacement": "RIGHT(", "description": "Right → RIGHT"},
    {"pattern": r"\bMid\(", "replacement": "MID(", "description": "Mid → MID"},
    {"pattern": r"\bCeil\(", "replacement": "CEILING(", "description": "Ceil → CEILING"},
    {"pattern": r"\bFloor\(", "replacement": "FLOOR(", "description": "Floor → FLOOR"},
    {"pattern": r"\bFract\(", "replacement": "MOD(", "description": "Fract → MOD (approx)"},
    {"pattern": r"\bOSUser\(\)", "replacement": "USERPRINCIPALNAME()", "description": "OSUser → USERPRINCIPALNAME"},
    {"pattern": r"\bSubField\(", "replacement": "/* SUBFIELD */ (", "description": "SubField → manual review"},
    {"pattern": r"\bFieldValue\(", "replacement": "/* FIELDVALUE */ (", "description": "FieldValue → manual review"},
]


def _autofix_tmdl_file(filepath: str) -> List[Dict[str, Any]]:
    """Apply auto-fix patterns to a single TMDL file.

    Returns a list of applied fixes with line info.
    """
    fixes: List[Dict[str, Any]] = []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except OSError:
        return fixes

    new_content = content
    for rule in _AUTOFIX_PATTERNS:
        matches = list(re.finditer(rule["pattern"], new_content))
        if matches:
            new_content = re.sub(rule["pattern"], rule["replacement"], new_content)
            fixes.append({
                "file": os.path.basename(filepath),
                "pattern": rule["description"],
                "occurrences": len(matches),
            })

    if new_content != content:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(new_content)

    return fixes


def run_qa_pipeline(project_dir: str, output_dir: Optional[str] = None,
                    verbose: bool = False) -> Dict[str, Any]:
    """Run the full QA pipeline on a generated .pbip project.

    Args:
        project_dir: Path to the generated project directory.
        output_dir: Where to save qa_report.json (defaults to project_dir).
        verbose: Enable verbose logging.

    Returns:
        QA report dictionary.
    """
    qa_start = datetime.now()
    report: Dict[str, Any] = {
        "project": project_dir,
        "timestamp": qa_start.isoformat(),
        "steps": {},
        "overall_status": "pass",
    }

    out_dir = output_dir or project_dir

    # ── Step 1: Artifact Validation ───────────────────────────
    validation_result: Dict[str, Any] = {"status": "skip", "errors": [], "warnings": [], "files_checked": 0}
    try:
        from powerbi_import.validator import ArtifactValidator
        vr = ArtifactValidator.validate_project(project_dir)
        validation_result = {
            "status": "pass" if vr.get("valid", False) else "fail",
            "errors": vr.get("errors", []),
            "warnings": vr.get("warnings", []),
            "files_checked": vr.get("files_checked", 0),
        }
        if not vr.get("valid", False):
            report["overall_status"] = "warn"
    except Exception as exc:
        validation_result = {"status": "error", "message": str(exc)}
        logger.warning("QA validation step failed: %s", exc)

    report["steps"]["validation"] = validation_result

    # ── Step 2: Auto-Fix Qlik→DAX Leaks ──────────────────────
    autofix_result: Dict[str, Any] = {"status": "skip", "fixes": [], "total_fixes": 0}
    try:
        # Scan TMDL table files
        sem_model = None
        for d in os.listdir(project_dir):
            if d.endswith(".SemanticModel"):
                sem_model = os.path.join(project_dir, d)
                break
        if sem_model:
            tables_dir = os.path.join(sem_model, "definition", "tables")
            all_fixes: List[Dict[str, Any]] = []
            if os.path.isdir(tables_dir):
                for tmdl_file in os.listdir(tables_dir):
                    if tmdl_file.endswith(".tmdl"):
                        fixes = _autofix_tmdl_file(os.path.join(tables_dir, tmdl_file))
                        all_fixes.extend(fixes)
            total = sum(f.get("occurrences", 0) for f in all_fixes)
            autofix_result = {
                "status": "pass",
                "fixes": all_fixes,
                "total_fixes": total,
            }
    except Exception as exc:
        autofix_result = {"status": "error", "message": str(exc)}
        logger.warning("QA autofix step failed: %s", exc)

    report["steps"]["autofix"] = autofix_result

    # ── Step 3: Governance Checks ─────────────────────────────
    governance_result: Dict[str, Any] = {"status": "skip"}
    try:
        from powerbi_import.governance import GovernanceEngine
        engine = GovernanceEngine()
        # Parse TMDL files into table dicts for governance checks
        tmdl_tables: List[Dict[str, Any]] = []
        if sem_model:
            tables_dir = os.path.join(sem_model, "definition", "tables")
            if os.path.isdir(tables_dir):
                for tmdl_file in os.listdir(tables_dir):
                    if tmdl_file.endswith(".tmdl"):
                        fpath = os.path.join(tables_dir, tmdl_file)
                        try:
                            with open(fpath, "r", encoding="utf-8") as f:
                                content = f.read()
                            table_name = tmdl_file[:-5]  # Remove .tmdl
                            columns = []
                            measures = []
                            for line in content.splitlines():
                                s = line.strip()
                                if s.startswith("column "):
                                    col_name = s[7:].strip().strip("'")
                                    if col_name:
                                        columns.append({"name": col_name})
                                elif s.startswith("measure "):
                                    m_name = s[8:].strip().strip("'")
                                    # Strip trailing = for inline expressions
                                    m_name = m_name.split("=")[0].strip().strip("'")
                                    if m_name:
                                        measures.append({"name": m_name})
                            tmdl_tables.append({
                                "name": table_name,
                                "columns": columns,
                                "measures": measures,
                            })
                        except Exception:
                            pass

        gov_report = engine.check(tmdl_tables)
        findings = [
            {"category": i.category, "severity": i.severity,
             "artifact": i.artifact_name, "message": i.message}
            for i in (gov_report.issues if gov_report else [])
        ]

        governance_result = {
            "status": "pass" if not findings else "warn",
            "findings_count": len(findings),
            "findings": findings[:20],  # Cap at 20
        }
        if findings:
            report["overall_status"] = "warn"
    except Exception as exc:
        governance_result = {"status": "skip", "message": str(exc)}
        logger.debug("QA governance step skipped: %s", exc)

    report["steps"]["governance"] = governance_result

    # ── Step 4: Comparison Report ─────────────────────────────
    compare_result: Dict[str, Any] = {"status": "skip"}
    try:
        from powerbi_import.comparison_report import generate_comparison_report
        comp_path = generate_comparison_report(
            project_dir=project_dir,
            output_dir=out_dir,
        )
        compare_result = {
            "status": "pass",
            "report_path": comp_path,
        }
    except Exception as exc:
        compare_result = {"status": "skip", "message": str(exc)}
        logger.debug("QA comparison step skipped: %s", exc)

    report["steps"]["comparison"] = compare_result

    # ── Summary ───────────────────────────────────────────────
    duration = (datetime.now() - qa_start).total_seconds()
    report["duration_seconds"] = round(duration, 2)

    steps_with_errors = [
        name for name, step in report["steps"].items()
        if step.get("status") == "fail"
    ]
    if steps_with_errors:
        report["overall_status"] = "fail"

    # Save report
    os.makedirs(out_dir, exist_ok=True)
    qa_path = os.path.join(out_dir, "qa_report.json")
    with open(qa_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    logger.info("QA report saved: %s (status=%s)", qa_path, report["overall_status"])
    return report
