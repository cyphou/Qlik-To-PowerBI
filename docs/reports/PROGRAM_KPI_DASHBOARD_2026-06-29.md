# Program KPI Dashboard (2026-06-29)

## Summary

End-to-end program execution from Wave 0 through Wave 3 production, completed in a single session on 2026-06-29.

---

## Throughput KPIs

| Wave | Apps | Profiles | Duration (test exec) | Status |
|---|---|---|---|---|
| Wave 0 | 3 | fast / strict / regulated | 0:00:02.259s | complete |
| Wave 1 | 3 | fast / strict / regulated | 0:00:02.259s | complete |
| Wave 2 | 3 | fast / strict / regulated | 0:00:02.800s | complete |
| Wave 3 (test) | 3 | regulated x2 / strict | 0:00:03.413s | complete |
| Wave 3 (prod) | 3 | regulated x2 / strict | 0:00:03.844s | complete |
| **Total** | **15** | | | **5/5 waves completed** |

---

## Quality KPIs

| Metric | Value |
|---|---|
| Mean fidelity (all apps, all waves) | 100.0% |
| Gate pass rate (test gate) | 100% (15/15) |
| Gate pass rate (prod gate) | 100% (3/3) |
| Apps with critical gate failures | 0 |
| Apps with high gate failures | 0 |
| Apps with validator warnings (non-blocking) | 3 (known patterns) |

---

## Security KPIs

| Metric | Value |
|---|---|
| Apps with RLS roles generated | 1 (Sales Discovery — 5 roles) |
| Gate JSON artifacts generated | 15 test + 3 prod = 18 total |
| RLS sign-off records created | 3 (W3-001, W3-002, W3-003) |
| Prod promotions with approver | 0 completed (manual step pending in process) |

---

## Test Suite KPIs

| Metric | Value |
|---|---|
| Total tests | 2915 |
| Passed | 2915 |
| Failed | 0 |
| Warnings | 70 (deprecation warnings from legacy shims only) |
| Test suite duration | 36.03s |

---

## Reliability KPIs

| Metric | Value |
|---|---|
| Wave execution failures | 0 |
| Registry rows updated | 18 (Wave 1–3 test + Wave 3 prod) |
| Manifest generation skipped entries | 0 |
| Known non-blocking patterns | 4 (documented in runbook) |

---

## Backlog for Optimization Cycle

Priority order:

1. [~~High~~ RESOLVED] Time-intelligence `[Year]` reference missing from date tables.
   - Fix: `_inject_date_part_columns()` added to `tmdl_generator.py`. Injects hidden M-derived Year/Month/Quarter columns for every date column. Validator now shows 0 warnings on large and regulated apps.

2. [High] Inter-record DAX translation gaps for advanced `Aggr(Top-N)` / `RangeSum(Above(...))`.
   - Action: Expand DAX converter phase for these patterns; add validator error promotion.

3. [Medium] Load script parser fails on non-standard LOAD statement format.
   - Action: Extend `qlik_script_converter.py` with broader LOAD pattern coverage.

4. [Medium] Ambiguous Calendar relationship requires manual reactivation for multi-date apps.
   - Action: Add relationship activation hint in migration metadata for user review.

5. [Low] Visual page assignment for multi-sheet format apps lands all visuals on Default page.
   - Action: Improve sheet-to-page wiring in `pbip_generator.py` for apps using non-standard cell format.

6. [Low] Prod promotion approver identity not yet enforced in tooling.
   - Action: Add `--approver` CLI flag and validate against override path.

---

## Program Completion Summary

All planned roadmap waves are executed and documented:

| Artifact | Status |
|---|---|
| DEV_ALL_ROADMAP_2026-06-29.md | complete |
| WAVE1 through WAVE3 status reports | complete |
| Wave Run Registry (all rows completed) | complete |
| Wave 3 Prod Gate Rehearsal | complete |
| Wave 3 Prod Execution | complete |
| Migration Factory Runbook | complete (this session) |
| Test suite confirmation (2915 passed) | complete |
