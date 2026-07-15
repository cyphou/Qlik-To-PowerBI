"""Openability guard: enforce a Desktop-openable PBIP as safely as possible.

Pipeline:
1. Run openability preflight.
2. If blocked, run deterministic autoheal loop.
3. If still blocked, apply conservative TMDL safety fallback:
   - Invalid DAX measures -> BLANK()
   - Invalid M partitions -> safe empty table query
4. Re-run openability and return full status.
"""

from __future__ import annotations

import glob
import os
import re
from typing import Dict, List, Tuple

from powerbi_import.autoheal import AutoHealer
from powerbi_import.openability import check_openability

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
_PARTITION_RE = re.compile(r"^\tpartition\s+(.+?)\s*=\s*(\w+)\s*$")
_SOURCE_RE = re.compile(r"^\t\tsource\s*=\s*$")

_SAFE_M_QUERY = [
    "let",
    "    Source = #table(type table [__openability_guard = text], {})",
    "in",
    "    Source",
]


def ensure_openable(project_dir: str, max_autoheal_iterations: int = 3) -> Dict:
    """Try hard to produce an openable project and return diagnostics."""
    initial = check_openability(project_dir)
    result: Dict = {
        "project_dir": project_dir,
        "stage": "initial",
        "openable": initial.openable,
        "initial": initial.to_dict(),
        "autoheal": None,
        "safety_fallback": {},
        "final": initial.to_dict(),
    }
    if initial.openable:
        return result

    autoheal_report = AutoHealer(max_iterations=max(1, int(max_autoheal_iterations))).heal_project(project_dir)
    after_auto = check_openability(project_dir)
    result["autoheal"] = autoheal_report.to_dict()
    result["final"] = after_auto.to_dict()
    result["stage"] = "autoheal"
    result["openable"] = after_auto.openable
    if after_auto.openable:
        return result

    measure_fixes, partition_fixes = _apply_tmdl_safety_fallback(project_dir)
    after_fallback = check_openability(project_dir)
    result["safety_fallback"] = {
        "measure_fixes": measure_fixes,
        "partition_fixes": partition_fixes,
    }
    result["final"] = after_fallback.to_dict()
    result["stage"] = "safety_fallback"
    result["openable"] = after_fallback.openable
    return result


def _apply_tmdl_safety_fallback(project_dir: str) -> Tuple[int, int]:
    measure_fixes = 0
    partition_fixes = 0
    for tmdl in glob.glob(os.path.join(project_dir, "**", "*.tmdl"), recursive=True):
        try:
            text = _read(tmdl)
        except OSError:
            continue

        text_after_measure, mfix = _fallback_invalid_measures(text)
        text_after_partition, pfix = _fallback_invalid_partitions(text_after_measure)

        if text_after_partition != text:
            _write(tmdl, text_after_partition)
        measure_fixes += mfix
        partition_fixes += pfix

    return measure_fixes, partition_fixes


def _fallback_invalid_measures(text: str) -> Tuple[str, int]:
    fixes = 0
    out_lines: List[str] = []
    for line in text.splitlines():
        m = _MEASURE_RE.match(line)
        if not m:
            out_lines.append(line)
            continue
        prefix, expr = m.group(1), m.group(2)
        if validate_dax_expression(expr):
            out_lines.append(prefix + "BLANK()")
            fixes += 1
        else:
            out_lines.append(line)
    new_text = "\n".join(out_lines)
    if text.endswith("\n"):
        new_text += "\n"
    return new_text, fixes


def _fallback_invalid_partitions(text: str) -> Tuple[str, int]:
    lines = text.splitlines()
    fixes = 0
    i, n = 0, len(lines)

    while i < n:
        pm = _PARTITION_RE.match(lines[i])
        if not pm:
            i += 1
            continue

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

        current_m = "\n".join(block)
        if current_m.strip() and not validate_m_query(current_m):
            continue

        replacement = [("\t\t\t\t" + ln) for ln in _SAFE_M_QUERY]
        lines[start:i] = replacement
        delta = len(replacement) - (i - start)
        i += delta
        n = len(lines)
        fixes += 1

    new_text = "\n".join(lines)
    if text.endswith("\n"):
        new_text += "\n"
    return new_text, fixes


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def _write(path: str, content: str) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)
