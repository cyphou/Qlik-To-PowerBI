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
