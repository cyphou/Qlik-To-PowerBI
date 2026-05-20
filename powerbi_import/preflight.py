"""Pre-flight rejection gate for Qlik migrations.

Runs *before* extraction. Refuses migration early when the input is
doomed to fail. Pure read-only, zero external dependencies, fast
(< 200 ms for any workbook).

Severity ladder:
  * ``BLOCKER``  — migration cannot proceed
  * ``WARNING``  — proceed but flag
  * ``ADVISORY`` — informational
"""

from __future__ import annotations

import logging
import os
import re
import zipfile
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger(__name__)

BLOCKER = "blocker"
WARNING = "warning"
ADVISORY = "advisory"

SUPPORTED_EXTENSIONS = {".qvf", ".qvw", ".json"}

# Soft thresholds
LARGE_WORKBOOK_BYTES = 500 * 1024 * 1024     # 500 MB
LARGE_VISUAL_COUNT = 1_000

# Path traversal patterns
_TRAVERSAL_PAT = re.compile(r"(^|/)\.\.(/|$)")


@dataclass
class PreflightIssue:
    """A single issue raised by pre-flight."""
    severity: str
    code: str
    message: str
    suggestion: str = ""

    def as_dict(self) -> dict:
        return {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "suggestion": self.suggestion,
        }


@dataclass
class PreflightResult:
    """Aggregated pre-flight result."""
    path: str
    issues: List[PreflightIssue] = field(default_factory=list)

    def add(self, severity: str, code: str, message: str,
            suggestion: str = "") -> None:
        self.issues.append(PreflightIssue(severity, code, message, suggestion))

    @property
    def blockers(self) -> List[PreflightIssue]:
        return [i for i in self.issues if i.severity == BLOCKER]

    @property
    def warnings(self) -> List[PreflightIssue]:
        return [i for i in self.issues if i.severity == WARNING]

    @property
    def advisories(self) -> List[PreflightIssue]:
        return [i for i in self.issues if i.severity == ADVISORY]

    @property
    def ok(self) -> bool:
        return not self.blockers

    def as_dict(self) -> dict:
        return {
            "path": self.path,
            "ok": self.ok,
            "blockers": [i.as_dict() for i in self.blockers],
            "warnings": [i.as_dict() for i in self.warnings],
            "advisories": [i.as_dict() for i in self.advisories],
        }

    def format_console(self) -> str:
        if not self.issues:
            return "Pre-flight: OK (no issues detected)"
        lines = ["Pre-flight summary:"]
        for sev, label in (
            (BLOCKER, "BLOCKER"),
            (WARNING, "WARNING"),
            (ADVISORY, "ADVISORY"),
        ):
            for issue in [i for i in self.issues if i.severity == sev]:
                lines.append(f"  [{label}] {issue.code}: {issue.message}")
                if issue.suggestion:
                    lines.append(f"           → {issue.suggestion}")
        return "\n".join(lines)


def _check_path(path: str, result: PreflightResult) -> bool:
    """Reject empty / null-byte / non-existent / wrong-extension paths."""
    if not path:
        result.add(BLOCKER, "empty_path", "No input path provided")
        return False

    if "\x00" in path:
        result.add(BLOCKER, "null_byte_path",
                    "Path contains a null byte (security risk)")
        return False

    resolved = os.path.realpath(path)
    if not os.path.exists(resolved):
        result.add(BLOCKER, "missing_file", f"File not found: {path}")
        return False

    ext = os.path.splitext(resolved)[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        result.add(
            BLOCKER, "unsupported_extension",
            f"Extension {ext!r} is not supported",
            suggestion=f"Use one of {sorted(SUPPORTED_EXTENSIONS)}",
        )
        return False

    return True


def _check_size(path: str, result: PreflightResult) -> None:
    """Advise on very large files."""
    try:
        size = os.path.getsize(path)
    except OSError:
        return
    if size > LARGE_WORKBOOK_BYTES:
        mb = size // (1024 * 1024)
        result.add(
            ADVISORY, "large_workbook",
            f"Input file is {mb} MB — migration may be slow",
            suggestion="Consider splitting via --shared-model",
        )


def _check_qvf_integrity(path: str, result: PreflightResult) -> bool:
    """For .qvf files: verify they are valid SQLite databases (or at
    least appear to be valid archives).
    """
    ext = os.path.splitext(path)[1].lower()
    if ext != '.qvf':
        return True

    try:
        with open(path, 'rb') as f:
            header = f.read(16)
    except OSError as e:
        result.add(BLOCKER, "read_error", f"Cannot read file: {e}")
        return False

    # QVF files are SQLite databases — check the SQLite magic header
    if header[:6] != b'SQLite' and not header[:4] == b'PK\x03\x04':
        result.add(
            WARNING, "unknown_format",
            "File does not appear to be a standard QVF (SQLite) format",
            suggestion="The file may still be processable via JSON extraction",
        )

    return True


def _check_json_integrity(path: str, result: PreflightResult) -> bool:
    """For .json files: verify they are valid JSON."""
    ext = os.path.splitext(path)[1].lower()
    if ext != '.json':
        return True

    try:
        import json
        with open(path, 'r', encoding='utf-8') as f:
            json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        result.add(
            BLOCKER, "corrupt_json",
            f"JSON file is malformed: {e}",
            suggestion="Fix the JSON syntax or re-export from Qlik",
        )
        return False

    return True


def run_preflight(path: str) -> PreflightResult:
    """Run all pre-flight checks against ``path``.

    Returns a :class:`PreflightResult`. Inspect ``result.ok`` to decide
    whether to proceed.
    """
    result = PreflightResult(path=path)

    if not _check_path(path, result):
        return result

    _check_size(path, result)
    _check_qvf_integrity(path, result)
    _check_json_integrity(path, result)

    return result


__all__ = [
    "BLOCKER", "WARNING", "ADVISORY",
    "PreflightIssue", "PreflightResult",
    "run_preflight",
]
