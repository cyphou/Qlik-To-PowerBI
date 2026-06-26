# Dev All Phases Board

- Generated at: 2026-06-26T09:04:51.615466+00:00
- Phase overall status: PASS

## Metrics

- migration_status: success
- fidelity_score: 100.0
- post_check_warning_count: 0
- post_check_error_count: 0
- unsupported_markers: 0
- approximation_markers: 0
- explicit_unsupported_functions: {'Skew': False, 'Hash128': False, 'Hash160': False, 'Hash256': False, 'Evaluate': False}

## Execution Summary

- epics: 3
- items: 9
- next_items: 3
- queued_items: 6

## P0 P0-UNSUPPORTED-CLOSURE

- Goal: Close explicit unsupported Qlik function gaps

### Items

- P0-1 Implement deterministic handling for Skew (owner: Dax, status: next, estimate: 2d)
- P0-2 Implement safe handling strategy for Hash128/Hash160/Hash256 (owner: Converter, status: next, estimate: 3d)
- P0-3 Implement Evaluate() migration policy (owner: Orchestrator, status: next, estimate: 3d)

## P1 P1-APPROX-FIDELITY

- Goal: Reduce approximation risk in expression conversion

### Items

- P1-1 Harden Correl conversion and validation (owner: Dax, status: queued, estimate: 2d)
- P1-2 Improve NetWorkDays for holiday-aware scenarios (owner: Wiring, status: queued, estimate: 2d)
- P1-3 Refine KeepChar and BitCount approximations (owner: Converter, status: queued, estimate: 2d)

## P2 P2-GOVERNANCE-AUTOMATION

- Goal: Operationalize parity governance and release gating

### Items

- P2-1 Add CI gate for parity backlog targets (owner: Tester, status: queued, estimate: 2d)
- P2-2 Track deprecated TMDL generator usage cleanup (owner: Generator, status: queued, estimate: 3d)
- P2-3 Publish weekly parity dashboard artifact (owner: Preceptor, status: queued, estimate: 2d)

## Issue Files

- C:\GitHub Project\QlikToPowerBI\artifacts\reports\phases\issues\p0-1-implement-deterministic-handling-for-skew.md
- C:\GitHub Project\QlikToPowerBI\artifacts\reports\phases\issues\p0-2-implement-safe-handling-strategy-for-hash128hash160hash256.md
- C:\GitHub Project\QlikToPowerBI\artifacts\reports\phases\issues\p0-3-implement-evaluate-migration-policy.md
- C:\GitHub Project\QlikToPowerBI\artifacts\reports\phases\issues\p1-1-harden-correl-conversion-and-validation.md
- C:\GitHub Project\QlikToPowerBI\artifacts\reports\phases\issues\p1-2-improve-networkdays-for-holiday-aware-scenarios.md
- C:\GitHub Project\QlikToPowerBI\artifacts\reports\phases\issues\p1-3-refine-keepchar-and-bitcount-approximations.md
- C:\GitHub Project\QlikToPowerBI\artifacts\reports\phases\issues\p2-1-add-ci-gate-for-parity-backlog-targets.md
- C:\GitHub Project\QlikToPowerBI\artifacts\reports\phases\issues\p2-2-track-deprecated-tmdl-generator-usage-cleanup.md
- C:\GitHub Project\QlikToPowerBI\artifacts\reports\phases\issues\p2-3-publish-weekly-parity-dashboard-artifact.md
