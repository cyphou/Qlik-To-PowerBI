"""Validate a generated PBIP with Power BI Desktop on Windows.

The existing openability checks validate files statically. This tool adds a
runtime gate: it derives the expected model shape from TMDL, opens the PBIP in
Desktop, queries the local Analysis Services model, and rejects partial loads.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable


_TABLE_RE = re.compile(r"^table\s+(.+?)\s*$")
_RELATIONSHIP_RE = re.compile(r"^relationship\s+(.+?)\s*$")
_PARTITION_RE = re.compile(r"^partition\s+.+?\s*=\s*(\w+)\s*$")
_ENDPOINT_RE = re.compile(r"^(?:fromColumn|toColumn):\s*(.+?)\s*$")


@dataclass
class ProjectExpectation:
    pbip_path: str
    project_name: str
    semantic_model_dir: str
    table_count: int
    relationship_count: int
    calculated_tables: list[str] = field(default_factory=list)
    calculated_relationship_endpoints: list[str] = field(default_factory=list)

    @property
    def statically_safe(self) -> bool:
        return not self.calculated_relationship_endpoints


@dataclass
class RuntimeObservation:
    status: str = "error"
    process_id: int | None = None
    process_responding: bool = False
    title: str = ""
    visible_windows: list[str] = field(default_factory=list)
    port: int | None = None
    workspace_data_dir: str = ""
    port_file: str = ""
    port_source: str = ""
    msmdsrv_pid: int | None = None
    table_count: int | None = None
    relationship_count: int | None = None
    metadata_error: str = ""
    new_frowns: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0


def _unquote_tmdl_name(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == "'":
        return value[1:-1].replace("''", "'")
    return value


def _endpoint_table(reference: str) -> str:
    reference = reference.strip()
    if reference.startswith("'"):
        index = 1
        while index < len(reference):
            if reference[index] == "'":
                if index + 1 < len(reference) and reference[index + 1] == "'":
                    index += 2
                    continue
                return _unquote_tmdl_name(reference[: index + 1])
            index += 1
        return ""
    return reference.split(".", 1)[0].strip()


def _iter_lines(paths: Iterable[Path]) -> Iterable[tuple[Path, str]]:
    for path in paths:
        for line in path.read_text(encoding="utf-8").splitlines():
            yield path, line.strip()


def inspect_project(pbip_path: str | os.PathLike[str]) -> ProjectExpectation:
    pbip = Path(pbip_path).resolve()
    if not pbip.is_file() or pbip.suffix.casefold() != ".pbip":
        raise ValueError(f"PBIP file not found: {pbip}")

    semantic_models = sorted(pbip.parent.glob("*.SemanticModel"))
    if len(semantic_models) != 1:
        raise ValueError(
            f"Expected one .SemanticModel beside {pbip.name}, found {len(semantic_models)}"
        )

    definition = semantic_models[0] / "definition"
    table_files = sorted((definition / "tables").glob("*.tmdl"))
    relationships_file = definition / "relationships.tmdl"
    if not table_files:
        raise ValueError(f"No TMDL tables found under {definition}")

    table_names: list[str] = []
    calculated_tables: set[str] = set()
    for path in table_files:
        current_table = ""
        for _source, line in _iter_lines([path]):
            match = _TABLE_RE.match(line)
            if match:
                current_table = _unquote_tmdl_name(match.group(1))
                table_names.append(current_table)
                continue
            partition = _PARTITION_RE.match(line)
            if current_table and partition and partition.group(1).casefold() == "calculated":
                calculated_tables.add(current_table)

    relationship_count = 0
    calculated_endpoints: list[str] = []
    if relationships_file.is_file():
        for _source, line in _iter_lines([relationships_file]):
            if _RELATIONSHIP_RE.match(line):
                relationship_count += 1
                continue
            endpoint = _ENDPOINT_RE.match(line)
            if endpoint:
                table_name = _endpoint_table(endpoint.group(1))
                if table_name in calculated_tables:
                    calculated_endpoints.append(endpoint.group(1))

    return ProjectExpectation(
        pbip_path=str(pbip),
        project_name=pbip.stem,
        semantic_model_dir=str(semantic_models[0]),
        table_count=len(table_names),
        relationship_count=relationship_count,
        calculated_tables=sorted(calculated_tables),
        calculated_relationship_endpoints=calculated_endpoints,
    )


def evaluate_runtime(
    expected: ProjectExpectation,
    runtime: RuntimeObservation,
) -> list[str]:
    issues: list[str] = []
    if not expected.statically_safe:
        issues.append(
            "relationships reference calculated tables: "
            + ", ".join(expected.calculated_relationship_endpoints)
        )
    if runtime.status != "model_loaded":
        issues.append(f"Desktop runtime status is {runtime.status!r}, not 'model_loaded'")
    if not runtime.process_responding:
        issues.append("Power BI Desktop is not responding")
    if runtime.title != expected.project_name:
        issues.append(
            f"Desktop title is {runtime.title!r}, expected {expected.project_name!r}"
        )
    unexpected_windows = [
        title for title in runtime.visible_windows if title != expected.project_name
    ]
    if unexpected_windows:
        issues.append("unexpected visible Desktop windows: " + ", ".join(unexpected_windows))
    if runtime.table_count != expected.table_count:
        issues.append(
            f"live table count is {runtime.table_count}, expected {expected.table_count}"
        )
    if runtime.relationship_count != expected.relationship_count:
        issues.append(
            "live relationship count is "
            f"{runtime.relationship_count}, expected {expected.relationship_count}"
        )
    if runtime.metadata_error:
        issues.append(f"live model metadata query failed: {runtime.metadata_error}")
    if runtime.new_frowns:
        issues.append("new Power BI Frown archive(s): " + ", ".join(runtime.new_frowns))
    return issues


def _run_desktop_probe(
    expected: ProjectExpectation,
    *,
    timeout_seconds: int,
    desktop_exe: str | None,
    keep_open: bool,
) -> RuntimeObservation:
    probe = Path(__file__).with_name("desktop_openability_probe.ps1")
    command = [
        "pwsh",
        "-NoProfile",
        "-NonInteractive",
        "-File",
        str(probe),
        "-PbipPath",
        expected.pbip_path,
        "-ExpectedTitle",
        expected.project_name,
        "-TimeoutSeconds",
        str(max(5, timeout_seconds)),
    ]
    if desktop_exe:
        command.extend(["-DesktopExe", desktop_exe])
    if keep_open:
        command.append("-KeepOpen")

    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=max(15, timeout_seconds + 15),
        check=False,
    )
    raw = (completed.stdout or "").strip()
    if completed.returncode != 0:
        error = (completed.stderr or raw or "Desktop probe failed").strip()
        return RuntimeObservation(status="probe_error", metadata_error=error)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        detail = (completed.stderr or raw or str(exc)).strip()
        return RuntimeObservation(status="probe_error", metadata_error=detail)
    allowed = RuntimeObservation.__dataclass_fields__.keys()
    return RuntimeObservation(**{key: value for key, value in data.items() if key in allowed})


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Open a PBIP in Power BI Desktop and verify the live model."
    )
    parser.add_argument("pbip", help="Path to the .pbip file")
    parser.add_argument(
        "--inspect-only",
        action="store_true",
        help="Print expected TMDL counts without launching Desktop",
    )
    parser.add_argument("--report", help="Optional JSON report path")
    parser.add_argument(
        "--timeout",
        type=int,
        default=90,
        help="Maximum seconds to wait for Desktop model loading (default: 90)",
    )
    parser.add_argument("--desktop-exe", help="Explicit PBIDesktop.exe path")
    parser.add_argument(
        "--keep-open",
        action="store_true",
        help="Leave the launched Desktop process open after validation",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        expected = inspect_project(args.pbip)
    except (OSError, UnicodeError, ValueError) as exc:
        payload = {"status": "error", "openable": False, "error": str(exc)}
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 2

    runtime = None
    issues: list[str] = []
    if args.inspect_only:
        if not expected.statically_safe:
            issues.append(
                "relationships reference calculated tables: "
                + ", ".join(expected.calculated_relationship_endpoints)
            )
        status = "inspected"
    else:
        runtime = _run_desktop_probe(
            expected,
            timeout_seconds=args.timeout,
            desktop_exe=args.desktop_exe,
            keep_open=args.keep_open,
        )
        issues = evaluate_runtime(expected, runtime)
        status = "passed" if not issues else "failed"

    payload = {
        "status": status,
        "openable": not issues,
        "issues": issues,
        "expected": asdict(expected),
        "runtime": asdict(runtime) if runtime else None,
    }
    output = json.dumps(payload, indent=2, ensure_ascii=False)
    print(output)
    if args.report:
        Path(args.report).write_text(output + "\n", encoding="utf-8")
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())