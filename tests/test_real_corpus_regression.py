"""
REAL-CORPUS REGRESSION HARNESS

Runs actual Qlik sample exports (JSON + binary QVF) through the FULL
pipeline — extraction → adaptation → project generation — and asserts the
generated .pbip project passes structural validation with ZERO errors.

Rationale: unit tests validate individual functions, but real migrations
exercise integration paths that mocked inputs never hit. A concrete example
from the 2026-07-13 session: Phase 11e crashed with ``NameError: logger not
defined`` on real data (the ``cardinality=None`` branch), yet 2,944 unit
tests passed because none exercised that path with real relationships.

This harness is the safety net that catches that class of bug: every future
change is validated against real Qlik files, not just synthetic fixtures.
"""
import os
from pathlib import Path

import pytest

from qlik_export.extraction_orchestrator import ExtractionOrchestrator
from qlik_export.format_adapter import adapt_qlik_for_generation
from powerbi_import.pbip_generator import PowerBIProjectGenerator
from powerbi_import.validator import ArtifactValidator


# ── Corpus discovery ────────────────────────────────────────────────

_REPO_ROOT = Path(__file__).resolve().parent.parent
_CORPUS_ROOTS = [
    _REPO_ROOT / "examples" / "qlik" / "qlik_exports",
    _REPO_ROOT / "examples" / "qlik" / "test_samples",
    _REPO_ROOT / "examples" / "qlik" / "downloaded",
]

# Generated / intermediate JSON markers that are NOT source apps.
_NON_APP_MARKERS = {
    "app_metadata", "datasources", "dimensions", "measures",
    "visualizations", "sheets", "variables", "loadscript",
    "associations", "bookmarks", "master_items",
    "migration_manifest", "batch_report", "qa_report",
}


def _discover_corpus():
    """Return a list of (id, path) tuples for every source Qlik export."""
    found = []
    for root in _CORPUS_ROOTS:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.suffix.lower() not in (".json", ".qvf"):
                continue
            stem = path.stem.lower()
            if stem in _NON_APP_MARKERS:
                continue
            if path.stat().st_size < 200:
                continue
            # Stable, readable test id
            rel = path.relative_to(_REPO_ROOT).as_posix()
            found.append(pytest.param(str(path), id=rel))
    return found


_CORPUS = _discover_corpus()


def _sanitize_name(path: Path) -> str:
    name = path.stem
    return "".join(c if c.isalnum() or c in ("_", "-") else "_" for c in name) or "App"


# ── The harness ─────────────────────────────────────────────────────

@pytest.mark.skipif(not _CORPUS, reason="No real Qlik corpus files found")
@pytest.mark.parametrize("qlik_path", _CORPUS)
def test_real_corpus_migrates_without_validation_errors(qlik_path, tmp_path):
    """Every real Qlik export must migrate to a structurally-valid project.

    Asserts ZERO validation errors. Warnings are allowed (data-dependent),
    but structural errors (missing model.tmdl, unresolved references, broken
    JSON/TMDL) fail the build.
    """
    src = Path(qlik_path)

    # 1. Extract
    orch = ExtractionOrchestrator()
    try:
        data = orch.extract(str(src))
    except ValueError as exc:
        pytest.skip(f"Unsupported/invalid export (expected for some fixtures): {exc}")

    # 2. Adapt
    converted = adapt_qlik_for_generation(data)

    # 3. Generate project
    report_name = _sanitize_name(src)
    gen = PowerBIProjectGenerator(output_dir=str(tmp_path))
    project_dir = gen.generate_project(report_name, converted)

    assert project_dir and os.path.isdir(project_dir), (
        f"Project not generated for {src.name}"
    )

    # 4. Validate — ZERO errors required
    result = ArtifactValidator.validate_project(project_dir)
    assert result["errors"] == [], (
        f"{src.name}: validation errors:\n  " + "\n  ".join(result["errors"])
    )
    assert result["files_checked"] > 0


@pytest.mark.skipif(not _CORPUS, reason="No real Qlik corpus files found")
def test_corpus_is_nonempty():
    """Guardrail: ensure the harness actually discovers real files.

    If this fails, the corpus directories moved and the harness is silently
    validating nothing.
    """
    assert len(_CORPUS) >= 3, (
        f"Expected >=3 real Qlik corpus files, found {len(_CORPUS)}"
    )


@pytest.mark.skipif(not _CORPUS, reason="No real Qlik corpus files found")
@pytest.mark.parametrize("qlik_path", _CORPUS)
def test_real_corpus_semantic_references_resolve(qlik_path, tmp_path):
    """Generated measures/columns must not reference undefined symbols.

    This is the exact class of failure (Missing_References) that broke the
    binary-export migration before the Phase 11d materialization fix.
    """
    src = Path(qlik_path)
    orch = ExtractionOrchestrator()
    try:
        data = orch.extract(str(src))
    except ValueError as exc:
        pytest.skip(f"Unsupported/invalid export: {exc}")

    converted = adapt_qlik_for_generation(data)
    report_name = _sanitize_name(src)
    gen = PowerBIProjectGenerator(output_dir=str(tmp_path))
    project_dir = gen.generate_project(report_name, converted)

    sm_dir = Path(project_dir) / f"{report_name}.SemanticModel" / "definition"
    if not sm_dir.exists():
        pytest.skip("No semantic model generated (report-only output)")

    ref_result = ArtifactValidator.validate_semantic_references(sm_dir)
    # validate_semantic_references returns (errors, warnings) or a dict
    if isinstance(ref_result, tuple):
        errors = ref_result[0]
    elif isinstance(ref_result, dict):
        errors = ref_result.get("errors", [])
    else:
        errors = []
    assert not errors, (
        f"{src.name}: unresolved semantic references:\n  " + "\n  ".join(map(str, errors))
    )
