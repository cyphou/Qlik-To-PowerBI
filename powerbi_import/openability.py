"""Power BI Desktop openability preflight (Sprint 221).

Verifies — WITHOUT opening Power BI Desktop — that a generated ``.pbip`` will
load cleanly, with a dedicated focus on **Power Query (M) generation**, the most
common silent load failure.

Checks (blocking = would stop Desktop from opening the report):
    structure     required project files/dirs present (SemanticModel, Report, .pbir)
    json_parse    every .json (visual/page/report/.pbir/.platform/.pbip) parses
    tmdl_present  the semantic model has at least one .tmdl
    power_query   every M partition extracted from TMDL validates (the focus)
    dax           every measure expression validates
    schema        PBIR/visual files carry a $schema (advisory)

Public API:
    check_openability(project_dir) -> OpenabilityReport
    extract_m_partitions(tmdl_text) -> list[(partition_name, m_text)]
"""

from __future__ import annotations

import glob
import json
import os
import re
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Tuple

try:
    from powerbi_import.dax_validator import validate_dax_expression
except Exception:  # noqa: BLE001
    def validate_dax_expression(expr):  # type: ignore
        return []
try:
    from powerbi_import.m_validator import validate_m_query
except Exception:  # noqa: BLE001
    def validate_m_query(text):  # type: ignore
        return []

# TMDL partition of type ``m`` and its ``source =`` block (M lines are indented
# with exactly 4 tabs by the generator; see tmdl_generator._write_partition).
_PARTITION_RE = re.compile(r"^\tpartition\s+(.+?)\s*=\s*(\w+)\s*$")
_SOURCE_RE = re.compile(r"^\t\tsource\s*=\s*$")
_MEASURE_RE = re.compile(r"^\s*measure\s+(?:'(?:[^']|'')+'|[^=\n]+?)\s*=\s*(.+?)\s*$")


@dataclass
class CheckResult:
    name: str
    ok: bool
    severity: str            # error (blocking) | warning
    issues: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class OpenabilityReport:
    project_dir: str
    checks: List[CheckResult] = field(default_factory=list)

    @property
    def blocking_issues(self) -> List[str]:
        out = []
        for c in self.checks:
            if not c.ok and c.severity == "error":
                out.extend(f"[{c.name}] {i}" for i in c.issues)
        return out

    @property
    def openable(self) -> bool:
        return not self.blocking_issues

    @property
    def warnings(self) -> List[str]:
        out = []
        for c in self.checks:
            if not c.ok and c.severity == "warning":
                out.extend(f"[{c.name}] {i}" for i in c.issues)
        return out

    def to_dict(self) -> Dict:
        return {
            "project_dir": self.project_dir,
            "openable": self.openable,
            "blocking_count": len(self.blocking_issues),
            "warning_count": len(self.warnings),
            "blocking_issues": self.blocking_issues,
            "warnings": self.warnings,
            "checks": [c.to_dict() for c in self.checks],
        }


# ════════════════════════════════════════════════════════════════════
#  M partition extraction (the Power Query focus)
# ════════════════════════════════════════════════════════════════════

def extract_m_partitions(tmdl_text: str) -> List[Tuple[str, str]]:
    """Return [(partition_name, m_expression)] for every ``= m`` partition.

    The generator writes each M line prefixed with 4 tabs after ``source =``;
    the block ends at the first dedented or blank line.
    """
    lines = tmdl_text.splitlines()
    out: List[Tuple[str, str]] = []
    i, n = 0, len(lines)
    is_m = False
    name = ""
    while i < n:
        line = lines[i]
        pm = _PARTITION_RE.match(line)
        if pm:
            name = pm.group(1).strip().strip("'").replace("''", "'")
            is_m = pm.group(2) == "m"
            i += 1
            continue
        if is_m and _SOURCE_RE.match(line):
            i += 1
            block = []
            while i < n:
                l = lines[i]
                if l.startswith("\t\t\t\t"):
                    block.append(l[4:])
                    i += 1
                else:
                    break
            out.append((name, "\n".join(block)))
            is_m = False
            continue
        i += 1
    return out


# ════════════════════════════════════════════════════════════════════
#  Checks
# ════════════════════════════════════════════════════════════════════

def _check_structure(project_dir) -> CheckResult:
    issues = []
    has_sm = bool(glob.glob(os.path.join(project_dir, "**", "*.SemanticModel"),
                            recursive=True)) or bool(_tmdl_files(project_dir))
    has_report = bool(glob.glob(os.path.join(project_dir, "**", "definition.pbir"),
                                recursive=True)) or bool(
        glob.glob(os.path.join(project_dir, "**", "*.Report"), recursive=True))
    if not has_sm:
        issues.append("no semantic model (.SemanticModel / .tmdl) found")
    if not has_report:
        issues.append("no report (definition.pbir / .Report) found")
    return CheckResult("structure", not issues, "error", issues)


def _check_json_parse(project_dir) -> CheckResult:
    issues = []
    patterns = ["*.json", "*.pbir", "*.pbip", ".platform"]
    seen = set()
    for pat in patterns:
        for fp in glob.glob(os.path.join(project_dir, "**", pat), recursive=True):
            if fp in seen:
                continue
            seen.add(fp)
            try:
                with open(fp, "r", encoding="utf-8") as fh:
                    json.load(fh)
            except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
                issues.append(f"{os.path.relpath(fp, project_dir)}: {exc}")
    return CheckResult("json_parse", not issues, "error", issues)


def _check_tmdl_present(project_dir) -> CheckResult:
    tmdls = _tmdl_files(project_dir)
    if not tmdls:
        return CheckResult("tmdl_present", False, "error",
                           ["no .tmdl files in the semantic model"])
    return CheckResult("tmdl_present", True, "error", [])


def _check_power_query(project_dir) -> CheckResult:
    """Validate every M partition — the Power Query generation focus."""
    issues = []
    for tmdl in _tmdl_files(project_dir):
        try:
            text = _read(tmdl)
        except OSError:
            continue
        for name, m_expr in extract_m_partitions(text):
            if not m_expr.strip():
                continue
            for problem in validate_m_query(m_expr):
                issues.append(f"{os.path.relpath(tmdl, project_dir)} :: "
                              f"partition '{name}': {problem}")
    return CheckResult("power_query", not issues, "error", issues)


def _check_dax(project_dir) -> CheckResult:
    issues = []
    for tmdl in _tmdl_files(project_dir):
        try:
            for line in _read(tmdl).splitlines():
                m = _MEASURE_RE.match(line)
                if not m:
                    continue
                for problem in validate_dax_expression(m.group(1)):
                    issues.append(f"{os.path.relpath(tmdl, project_dir)}: {problem}")
        except OSError:
            continue
    return CheckResult("dax", not issues, "error", issues)


def _check_schema(project_dir) -> CheckResult:
    issues = []
    for fp in glob.glob(os.path.join(project_dir, "**", "visual.json"), recursive=True):
        data = _read_json(fp)
        if isinstance(data, dict) and "$schema" not in data:
            issues.append(f"{os.path.relpath(fp, project_dir)}: missing $schema")
    return CheckResult("schema", not issues, "warning", issues)


def check_openability(project_dir: str) -> OpenabilityReport:
    """Run the full PBI Desktop openability preflight."""
    report = OpenabilityReport(project_dir=project_dir)
    if not project_dir or not os.path.isdir(project_dir):
        report.checks.append(CheckResult("structure", False, "error",
                                         ["project dir not found"]))
        return report
    report.checks = [
        _check_structure(project_dir),
        _check_json_parse(project_dir),
        _check_tmdl_present(project_dir),
        _check_power_query(project_dir),
        _check_dax(project_dir),
        _check_schema(project_dir),
    ]
    return report


# ════════════════════════════════════════════════════════════════════
#  Helpers
# ════════════════════════════════════════════════════════════════════

def _tmdl_files(project_dir):
    return glob.glob(os.path.join(project_dir, "**", "*.tmdl"), recursive=True)


def _read(path):
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def _read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
