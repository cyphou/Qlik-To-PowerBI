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
    initial_dict = initial.to_dict()
    result: Dict = {
        "project_dir": project_dir,
        "stage": "initial",
        "openable": initial.openable,
        "initial": initial_dict,
        "autoheal": None,
        "autoheal_metrics": {
            "action_count": 0,
            "by_artifact": {},
            "by_confidence": {},
            "by_source": {},
        },
        "safety_fallback": {},
        "final": initial_dict,
        "stage_trace": [_stage_entry("initial", initial_dict)],
        "root_cause_taxonomy": {
            "initial": _build_root_cause_taxonomy(initial_dict),
            "final": _build_root_cause_taxonomy(initial_dict),
        },
    }
    if initial.openable:
        return result

    autoheal_report = AutoHealer(max_iterations=max(1, int(max_autoheal_iterations))).heal_project(project_dir)
    autoheal_dict = autoheal_report.to_dict()
    after_auto = check_openability(project_dir)
    after_auto_dict = after_auto.to_dict()
    result["autoheal"] = autoheal_dict
    result["autoheal_metrics"] = _build_autoheal_metrics(autoheal_dict)
    result["final"] = after_auto_dict
    result["stage"] = "autoheal"
    result["openable"] = after_auto.openable
    result["stage_trace"].append(_stage_entry("autoheal", after_auto_dict))
    result["root_cause_taxonomy"]["final"] = _build_root_cause_taxonomy(after_auto_dict)
    if after_auto.openable:
        return result

    measure_fixes, partition_fixes = _apply_tmdl_safety_fallback(project_dir)
    after_fallback = check_openability(project_dir)
    result["safety_fallback"] = {
        "measure_fixes": measure_fixes,
        "partition_fixes": partition_fixes,
    }
    after_fallback_dict = after_fallback.to_dict()
    result["final"] = after_fallback_dict
    result["stage"] = "safety_fallback"
    result["openable"] = after_fallback.openable
    result["stage_trace"].append(_stage_entry("safety_fallback", after_fallback_dict))
    result["root_cause_taxonomy"]["final"] = _build_root_cause_taxonomy(after_fallback_dict)
    return result


def _stage_entry(stage_name: str, openability: Dict) -> Dict:
    return {
        "stage": stage_name,
        "openable": bool(openability.get("openable")),
        "blocking_count": int(openability.get("blocking_count", 0) or 0),
        "warning_count": int(openability.get("warning_count", 0) or 0),
    }


def _build_root_cause_taxonomy(openability: Dict) -> Dict:
    """Categorize blocking issues by check and coarse reason class."""
    issues = openability.get("blocking_issues") or []
    by_check: Dict[str, int] = {}
    by_reason: Dict[str, int] = {}
    normalized: List[str] = []

    for issue in issues:
        issue_text = str(issue)
        normalized.append(issue_text)
        check = _extract_check_name(issue_text)
        reason = _classify_reason(check, issue_text)
        by_check[check] = by_check.get(check, 0) + 1
        by_reason[reason] = by_reason.get(reason, 0) + 1

    return {
        "total_blocking": len(normalized),
        "by_check": by_check,
        "by_reason": by_reason,
        "sample_issues": normalized[:5],
    }


def _extract_check_name(issue_text: str) -> str:
    m = re.match(r"^\[([^\]]+)\]", issue_text)
    if m:
        return m.group(1).strip().lower()
    return "unknown"


def _classify_reason(check_name: str, issue_text: str) -> str:
    text = issue_text.lower()
    if check_name == "power_query":
        if "quoted identifier" in text or "let/in" in text or "string literal" in text:
            return "m_syntax"
        if "credential" in text:
            return "m_credentials"
        return "m_other"
    if check_name == "dax":
        if "unknown function" in text:
            return "dax_unknown_function"
        if "unmatched" in text or "syntax" in text:
            return "dax_syntax"
        return "dax_other"
    if check_name == "json_parse":
        return "json_parse"
    if check_name == "structure":
        return "structure_missing"
    if check_name == "tmdl_present":
        return "tmdl_missing"
    return "other"


def _build_autoheal_metrics(autoheal_report: Dict) -> Dict:
    actions = autoheal_report.get("actions") or []
    by_artifact: Dict[str, int] = {}
    by_confidence: Dict[str, int] = {}
    by_source: Dict[str, int] = {}

    for action in actions:
        artifact = str(action.get("artifact", "unknown") or "unknown")
        confidence = str(action.get("confidence", "unknown") or "unknown")
        source = str(action.get("source", "unknown") or "unknown")
        by_artifact[artifact] = by_artifact.get(artifact, 0) + 1
        by_confidence[confidence] = by_confidence.get(confidence, 0) + 1
        by_source[source] = by_source.get(source, 0) + 1

    return {
        "action_count": len(actions),
        "by_artifact": by_artifact,
        "by_confidence": by_confidence,
        "by_source": by_source,
    }


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
