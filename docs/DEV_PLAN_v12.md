<!-- DOC-SHINY-BANNER -->
![Documentation](https://img.shields.io/badge/Documentation-Shiny_Style-0A66C2?style=flat-square&logo=readthedocs&logoColor=white)
![Maintained](https://img.shields.io/badge/Maintained-2026-2EA44F?style=flat-square&logo=github&logoColor=white)
![Navigation](https://img.shields.io/badge/Navigation-Quick_Access-6F42C1?style=flat-square&logo=bookstack&logoColor=white)
# DEV_PLAN v12.x - Live Execution Plan

This document replaces the previous v12 gap list and reflects the current repository state.

## Current Baseline (2026-06-24)

- Package version aligned at 12.0.0 across project entry points.
- Preceptorship and self-healing pipeline implemented.
- Cutover, full lineage, script lineage, PDF/PPTX/package reporting implemented.
- Multi-agent model implemented and documented.

For the latest status snapshot, see:
- docs/reports/ROADMAP_STATUS_2026-06-24.md
- docs/reports/NEXT_EVOLUTION_ROADMAP_2026-07-15.md

## Execution Goals

1. Keep source-of-truth docs synchronized with implementation.
2. Automate parity and drift checks to prevent stale planning.
3. Increase migration reliability with targeted test and benchmark expansion.
4. Establish repeatable upstream sync review against TableauToPowerBI baseline.

## Milestone A - Source-of-truth stabilization (Done + guardrails)

Status: In progress (core updates done, guardrails now added)

Completed:
- Version metadata and headline README status refreshed.
- Historical plan replaced by live execution plan.

Guardrails:
- Add and use tools/analysis/parity_status_check.py in release checks.
- Fail release checklist if versions/required modules/required flags drift.

## Milestone B - Deterministic parity matrix (Next)

Status: Planned

Deliverables:
- Expand parity_status_check.py into a matrix reporter:
  - feature -> module(s)
  - feature -> CLI flags
  - feature -> minimal test coverage indicator
- Emit both human-readable and JSON output for CI usage.

Definition of done:
- A single command returns pass/fail with actionable missing items.

## Milestone C - Reliability hardening (Priority)

Status: Planned

Focus areas:
- DAX edge-case conversions (nested conditionals, set analysis edge paths).
- Power Query escaping and step-chain integrity.
- Relationship synthesis and bridge-table validation.
- Large-app performance and memory profile safeguards.

Deliverables:
- New targeted tests in tests/ for each focus area.
- Benchmark script(s) for extraction and generation stages.

## Sprint 1 Execution (P0) - Code Quality + Desktop Openability

Status: Active (starts 2026-07-16)

Scope:
- Improve migrated artifact quality before Desktop load.
- Enforce deterministic Desktop runtime openability gate.
- Close static-vs-runtime validation gap with hard pass/fail criteria.

### Day 1 - Runtime gate baseline

Tasks:
- Finalize runtime probe reliability in `tools/testing/desktop_openability_probe.ps1`.
- Keep strict fail behavior in `tools/testing/desktop_openability.py`:
  - fail when runtime status is not `model_loaded`
  - fail when live table/relationship counts differ from expected TMDL
  - fail on new Frown snapshots
- Add deterministic probe diagnostics to runtime payload (`port_source`, `msmdsrv_pid`, `port_file`, `workspace_data_dir`).

Validation commands:
- `python tools/testing/desktop_openability.py "<path-to>.pbip" --inspect-only`
- `python tools/testing/desktop_openability.py "<path-to>.pbip" --timeout 90 --report output/desktop_openability_<app>.json`

Acceptance:
- At least 1 real app reaches `status: passed` with `runtime.status: model_loaded`.

### Day 2 - CI integration of runtime openability

Tasks:
- Extend `.github/workflows/openability-gate.yml` to run runtime gate on a known-good PBIP sample in addition to static checks.
- Add artifact upload for runtime JSON reports from `output/desktop_openability_*.json`.
- Gate merge when runtime gate fails.

Validation commands:
- `pwsh scripts/run_openability_batch.ps1`
- CI run includes both static and runtime checks.

Acceptance:
- CI red on runtime failure, green on runtime success, with downloadable JSON evidence.

### Day 3 - Migrated code quality invariants

Tasks:
- Add/strengthen model invariants in `powerbi_import/openability.py` and related validators:
  - reject relationship endpoints unresolved in final serialized TMDL
  - reject relationship endpoints on calculated tables
  - reject model-wide measure/column name collisions (case-insensitive)
  - reject non-primitive M type identifiers in `type table [...]` contexts
- Ensure error messages contain table/column/source context.

Validation commands:
- `python -m pytest tests/test_openability.py tests/test_openability_guard.py -q`

Acceptance:
- New invalid fixtures fail deterministically with actionable diagnostics.

### Day 4 - Regression hardening on real migration failures

Tasks:
- Add regression tests for recent FEI/EIG failure modes:
  - invalid column ID relationship references
  - M alias leak around tab-aligned `AS`
  - calculated-table relationship endpoint rejection
- Cover both unit and integration surfaces where practical.

Validation commands:
- `python -m pytest tests/test_tmdl_canonical.py tests/test_desktop_openability.py -q --tb=short`

Acceptance:
- Reproduced failures are permanently guarded by tests.

### Day 5 - Batch confidence run and release checklist

Tasks:
- Run runtime gate over a representative mini-batch (known-good + known-bad).
- Document pass/fail matrix in `docs/reports/` with root cause mapping.
- Update release checklist to require runtime evidence before publish.

Validation commands:
- `python -m pytest tests/ -q --tb=short`
- `python tools/testing/desktop_openability.py "<app>.pbip" --timeout 90 --report output/desktop_openability_<app>.json`

Acceptance:
- Batch summary shows no false positive openability passes.
- Release checklist explicitly includes runtime openability evidence.

### Sprint 1 exit criteria

- Runtime openability gate is part of normal validation flow.
- At least 3 real PBIP migrations pass runtime openability with exact model counts.
- All newly fixed failure modes are test-protected.
- CI and local runbook produce equivalent pass/fail decisions.

## Milestone D - Upstream sync protocol (Ongoing)

Status: Planned

Monthly process:
1. Pull latest TableauToPowerBI delta.
2. Map delta to local feature matrix.
3. Port, close, or deprecate with rationale.
4. Update CHANGELOG and roadmap status document.

## Operator Runbook (Current)

## 1) Baseline migration

python migrate.py app.qvf --output-dir output/migration_run

## 2) Quality and repair gates

python migrate.py app.qvf --qa --self-heal-v3 --repair-strategies --preceptor-review --cross-validate --schema-validate

## 3) Cutover + lineage + reports

python migrate.py app.qvf --cutover-plan --full-lineage --script-lineage --pdf-report --pptx-report --package

## 4) Optional deploy

python migrate.py app.qvf --deploy WORKSPACE_ID --deploy-refresh

## 5) Parity/status verification

python tools/analysis/parity_status_check.py

## Action Backlog

- Clarify whether subscription_migrator.py is required or superseded by subscription_generator.py.
- Decide whether prep_lineage naming should be introduced as aliases or permanently retired in favor of script_lineage.
- Add CI job executing parity_status_check.py and failing on drift.

