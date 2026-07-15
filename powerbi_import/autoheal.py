"""Closed-loop autoheal for generated PBIP projects.

Autoheal runs deterministic repairs on DAX and Power Query M partitions,
then validates each fix before applying it.
"""

from __future__ import annotations

import glob
import os
import re
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional, Tuple

from powerbi_import.m_healing import heal_m
from powerbi_import.openability import extract_m_partitions

try:
    from powerbi_import.dax_validator import validate_dax_expression
except Exception:  # pragma: no cover
    def validate_dax_expression(expr):  # type: ignore
        return []

try:
    from powerbi_import.m_validator import validate_m_query
except Exception:  # pragma: no cover
    def validate_m_query(expr):  # type: ignore
        return []


_MEASURE_RE = re.compile(r"^(\s*measure\s+(?:'(?:[^']|'')+'|[^=\n]+?)\s*=\s*)(.+?)\s*$")
_MEASURE_NAME_RE = re.compile(r"^\s*measure\s+(?:'((?:[^']|'')+)'|([^\s=]+))")
_PARTITION_RE = re.compile(r"^\tpartition\s+(.+?)\s*=\s*(\w+)\s*$")
_SOURCE_RE = re.compile(r"^\t\tsource\s*=\s*$")


@dataclass
class ErrorRecord:
    artifact: str
    file: str
    location: str
    message: str
    severity: str = "error"


@dataclass
class HealAction:
    file: str
    artifact: str
    location: str
    before: str
    after: str
    source: str
    confidence: str
    validated: bool


@dataclass
class AutoHealReport:
    project_dir: str
    iterations: int = 0
    actions: List[HealAction] = field(default_factory=list)
    remaining_errors: List[ErrorRecord] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return bool(self.actions)

    @property
    def clean(self) -> bool:
        return not self.remaining_errors

    def to_dict(self) -> Dict:
        return {
            "project_dir": self.project_dir,
            "iterations": self.iterations,
            "changed": self.changed,
            "clean": self.clean,
            "action_count": len(self.actions),
            "actions": [asdict(a) for a in self.actions],
            "remaining_errors": [asdict(e) for e in self.remaining_errors],
        }


class StaticValidatorSource:
    """Collect DAX/M errors from generated TMDL artifacts."""

    def collect(self, project_dir: str) -> List[ErrorRecord]:
        errors: List[ErrorRecord] = []
        for tmdl in _iter_tmdl(project_dir):
            try:
                text = _read(tmdl)
            except OSError:
                continue
            for line in text.splitlines():
                m = _MEASURE_RE.match(line)
                if not m:
                    continue
                name = _measure_name(line)
                for issue in validate_dax_expression(m.group(2)):
                    errors.append(ErrorRecord("dax", tmdl, name or "measure", issue))
            for pname, m_expr in extract_m_partitions(text):
                if not m_expr.strip():
                    continue
                for issue in validate_m_query(m_expr):
                    errors.append(ErrorRecord("m", tmdl, pname, issue))
        return errors


class AutoHealer:
    """Iterative deterministic auto-healer."""

    def __init__(self, max_iterations: int = 3, error_source: Optional[StaticValidatorSource] = None):
        self.max_iterations = max(1, int(max_iterations))
        self.error_source = error_source or StaticValidatorSource()

    def heal_project(self, project_dir: str) -> AutoHealReport:
        report = AutoHealReport(project_dir=project_dir)
        if not project_dir or not os.path.isdir(project_dir):
            report.remaining_errors.append(
                ErrorRecord("info", project_dir, "project", "project dir not found", severity="info")
            )
            return report

        for _ in range(self.max_iterations):
            report.iterations += 1
            changed = False
            for tmdl in _iter_tmdl(project_dir):
                try:
                    original = _read(tmdl)
                except OSError:
                    continue
                after_dax, dax_actions = _heal_measure_lines(original, tmdl)
                after_m, m_actions = _heal_m_partitions(after_dax, tmdl)
                if after_m != original:
                    _write(tmdl, after_m)
                    changed = True
                report.actions.extend(dax_actions)
                report.actions.extend(m_actions)

            residual = self.error_source.collect(project_dir)
            report.remaining_errors = residual
            if not residual or not changed:
                break

        report.remaining_errors = self.error_source.collect(project_dir)
        return report


def heal_dax_expression(expr: str) -> Tuple[str, bool]:
    """Small deterministic DAX fixer with validation safety."""
    original = expr
    fixed = expr
    replacements = [
        (r"\bIsNull\s*\(", "ISBLANK("),
        (r"\bNullCount\s*\(", "COUNTBLANK("),
        (r"\bNull\s*\(\)", "BLANK()"),
        (r"\bAlt\s*\(", "COALESCE("),
        (r"\bUpper\s*\(", "UPPER("),
        (r"\bLower\s*\(", "LOWER("),
    ]
    for pat, repl in replacements:
        fixed = re.sub(pat, repl, fixed)

    open_paren = fixed.count("(")
    close_paren = fixed.count(")")
    if open_paren > close_paren:
        fixed += ")" * (open_paren - close_paren)

    if fixed != original and not validate_dax_expression(fixed):
        return fixed, True
    return original, False


def _heal_measure_lines(text: str, tmdl_path: str) -> Tuple[str, List[HealAction]]:
    out_lines: List[str] = []
    actions: List[HealAction] = []
    for line in text.splitlines():
        m = _MEASURE_RE.match(line)
        if not m:
            out_lines.append(line)
            continue
        prefix, expr = m.group(1), m.group(2)
        fixed, changed = heal_dax_expression(expr)
        if changed:
            out_lines.append(prefix + fixed)
            actions.append(HealAction(
                file=tmdl_path,
                artifact="dax",
                location=_measure_name(line) or "measure",
                before=expr,
                after=fixed,
                source="deterministic",
                confidence="high",
                validated=True,
            ))
        else:
            out_lines.append(line)
    new_text = "\n".join(out_lines)
    if text.endswith("\n"):
        new_text += "\n"
    return new_text, actions


def _heal_m_partitions(text: str, tmdl_path: str) -> Tuple[str, List[HealAction]]:
    lines = text.splitlines()
    actions: List[HealAction] = []
    i, n = 0, len(lines)
    while i < n:
        pm = _PARTITION_RE.match(lines[i])
        if not pm:
            i += 1
            continue
        pname = pm.group(1).strip().strip("'").replace("''", "'")
        is_m = pm.group(2) == "m"
        i += 1
        if not is_m:
            continue
        if i >= n or not _SOURCE_RE.match(lines[i]):
            continue
        i += 1
        start = i
        block: List[str] = []
        while i < n and lines[i].startswith("\t\t\t\t"):
            block.append(lines[i][4:])
            i += 1
        original_m = "\n".join(block)
        if not original_m.strip():
            continue
        healed = heal_m(original_m)
        if not healed.changed:
            continue
        if validate_m_query(healed.healed):
            continue
        healed_lines = healed.healed.splitlines()
        replacement = [("\t\t\t\t" + ln) for ln in healed_lines]
        lines[start:i] = replacement
        delta = len(replacement) - (i - start)
        i += delta
        n = len(lines)
        actions.append(HealAction(
            file=tmdl_path,
            artifact="m",
            location=pname,
            before=original_m,
            after=healed.healed,
            source="deterministic",
            confidence="high",
            validated=True,
        ))
    new_text = "\n".join(lines)
    if text.endswith("\n"):
        new_text += "\n"
    return new_text, actions


def _iter_tmdl(project_dir: str) -> List[str]:
    return glob.glob(os.path.join(project_dir, "**", "*.tmdl"), recursive=True)


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def _write(path: str, text: str) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def _measure_name(line: str) -> Optional[str]:
    m = _MEASURE_NAME_RE.match(line)
    if not m:
        return None
    return (m.group(1) or m.group(2) or "").replace("''", "'")
