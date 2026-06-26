# Parity Backlog P0/P1/P2

- Generated at: 2026-06-26T09:04:50.551834+00:00
- Source report: C:\GitHub Project\QlikToPowerBI\artifacts\reports\phases\latest.json

## Current Metrics

- migration_status: success
- fidelity_score: 100.0
- post_check_warning_count: 0
- post_check_error_count: 0
- unsupported_markers: 0
- approximation_markers: 0
- explicit_unsupported_functions: none

## P0 - P0-UNSUPPORTED-CLOSURE

- Goal: Close explicit unsupported Qlik function gaps

### Items

- P0-1 Implement deterministic handling for Skew (owner: Dax, estimate: 2d)
  - AC: No 'UNSUPPORTED: Skew' marker emitted in migrated expressions
  - AC: Unit tests cover scalar, measure, and nested use cases
  - AC: Strict mode can fail on unresolved Skew only when requested
- P0-2 Implement safe handling strategy for Hash128/Hash160/Hash256 (owner: Converter, estimate: 3d)
  - AC: No unsupported hash markers in output for covered paths
  - AC: Documented behavior in mapping reference
  - AC: Regression tests for each hash function
- P0-3 Implement Evaluate() migration policy (owner: Orchestrator, estimate: 3d)
  - AC: Evaluate paths are either transformed or explicitly blocked by policy
  - AC: Policy behavior exposed via CLI flag and documented
  - AC: CI check validates no silent fallback remains

### Exit Criteria

- unsupported_markers_target: 0
- explicit_unsupported_functions_target: []

## P1 - P1-APPROX-FIDELITY

- Goal: Reduce approximation risk in expression conversion

### Items

- P1-1 Harden Correl conversion and validation (owner: Dax, estimate: 2d)
  - AC: Correlation conversion validated against reference datasets
  - AC: Deviation threshold documented and tested
- P1-2 Improve NetWorkDays for holiday-aware scenarios (owner: Wiring, estimate: 2d)
  - AC: Holiday table support available
  - AC: Conversion tests for weekend-only and holiday-aware modes
- P1-3 Refine KeepChar and BitCount approximations (owner: Converter, estimate: 2d)
  - AC: Reduced approximation warnings for representative corpus
  - AC: No regression in existing DAX conversion tests

### Exit Criteria

- approximation_markers_target: 1
- quality_gate_postcheck_warnings_max: 2

## P2 - P2-GOVERNANCE-AUTOMATION

- Goal: Operationalize parity governance and release gating

### Items

- P2-1 Add CI gate for parity backlog targets (owner: Tester, estimate: 2d)
  - AC: CI fails if unsupported markers exceed target
  - AC: CI fails if strict upstream parity check fails
- P2-2 Track deprecated TMDL generator usage cleanup (owner: Generator, estimate: 3d)
  - AC: Warnings trend reduced in test suite output
  - AC: Migration path documented for remaining call sites
- P2-3 Publish weekly parity dashboard artifact (owner: Preceptor, estimate: 2d)
  - AC: Weekly report with phase status and KPI deltas generated
  - AC: Artifacts retained in reports directory

### Exit Criteria

- weekly_phase_runs: 1
- report_artifacts_present: True

