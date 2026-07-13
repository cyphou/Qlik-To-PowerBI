# Dev-All Roadmap Execution Pack (2026-06-29)

## Objective

Convert the enterprise migration roadmap into execution-ready artifacts for Weeks 2-8 with explicit owners, gates, commands, and sign-off checkpoints.

This pack is the direct implementation response to "go dev all roadmap" and is designed to be used with existing manifest/profile tooling.

---

## Scope of This Execution Pack

1. Week-by-week execution model from Wave 1 through stabilization.
2. Ready-to-fill Wave run plans for Wave 1 and Wave 2.
3. Centralized run registry template for status, blockers, approvals, and evidence.
4. Portfolio CSVs for Wave 1 and Wave 2 manifest generation.
5. Command track for repeatable execution in dev/test/prod lanes.

---

## Program Roles and RACI

| Workstream | Responsible | Accountable | Consulted | Informed |
|---|---|---|---|---|
| Intake and wave planning | Migration Lead | Release Manager | Business Owner | Security Lead |
| Manifest/profile validation | Migration Lead | Release Manager | Platform Engineer | Business Owner |
| Gate and quality controls | Platform Engineer | Migration Lead | QA Lead | Security Lead |
| RLS and security sign-off | Security Lead | Release Manager | Business Owner | Migration Lead |
| Prod promotion approval | Release Manager | Program Sponsor | Security Lead | All owners |

---

## Week-by-Week Delivery Plan

### Week 2: Wave 1 Preparation

Deliverables:

1. Wave 1 plan completed and approved.
2. Wave 1 manifests generated from portfolio CSV.
3. RLS sign-off records initialized for strict and regulated apps.
4. Run registry initialized and baselined.

Execution commands:

```powershell
python scripts/build_wave_manifests.py --input examples/waves/enterprise_wave1_portfolio.csv --output-dir examples/waves/generated_wave1 --include-profiles-template --output-root output/waves/enterprise_wave1/staging --make-ready

python migrate.py --migration-manifest examples/waves/generated_wave1/wave_Wave-1_manifest_ready.json --gate test
```

Exit criteria:

1. 100% Wave 1 apps mapped to owner and profile.
2. Gate test pass rate at or above 90%.
3. All strict/regulated apps have RLS sign-off records in progress.

### Week 3: Wave 1 Closeout and Wave 2 Readiness

Deliverables:

1. Wave 1 closeout report with KPI rollup.
2. Wave 2 plan completed and approved.
3. Top recurring defects categorized and assigned.

Execution commands:

```powershell
python scripts/build_wave_manifests.py --input examples/waves/enterprise_wave2_portfolio.csv --output-dir examples/waves/generated_wave2 --include-profiles-template --output-root output/waves/enterprise_wave2/staging --make-ready

python migrate.py --migration-manifest examples/waves/generated_wave2/wave_Wave-2_manifest_ready.json --gate test
```

Exit criteria:

1. Wave 1 unresolved blockers count is zero or has approved exceptions.
2. Mean rerun time below 30 minutes for non-source failures.

### Week 4-5: Wave 2 Scale Execution

Deliverables:

1. Parallel execution of Tier B and selected Tier C candidate apps.
2. Security evidence bundle completeness at 100%.
3. Run registry updated daily with approvals and blockers.

Execution controls:

1. Test gate mandatory for all apps.
2. Prod gate allowed only after sign-off is complete.
3. Force override requires incident reference and remediation ETA.

Exit criteria:

1. Throughput meets planned app volume.
2. No prod promotion without approver and evidence link.

### Week 6-7: Wave 3 Regulated Cutovers

Deliverables:

1. Regulated app cutover windows and rollback plans.
2. Dual review completed for security and transformation risk.
3. Executive risk log refreshed each wave run.

Execution controls:

1. Download-first evidence for all regulated entries.
2. Strict prod gate with approval traceability.

Exit criteria:

1. First-pass success at or above 80% for regulated set.
2. Zero critical incidents without rollback path.

### Week 8: Stabilization and Handover

Deliverables:

1. Final migration factory runbook release.
2. Weekly operations cadence with KPI dashboard ownership.
3. Backlog triage and prioritization for optimization cycle.

Exit criteria:

1. Incident rate below 2% in the first two weeks after cutover.
2. Operational ownership formally transferred.

---

## Mandatory Governance Checkpoints

1. Wave execution plan approved before run window opens.
2. Run registry updated at dry-run start, execute start, and closeout.
3. RLS sign-off completed for strict/regulated profiles before prod promotion.
4. Security artifact bundle archived with each app run.
5. Any prod override includes incident ID, approver, and remediation target date.

---

## Artifact Index

Use these artifacts together:

1. docs/reports/WAVE1_EXECUTION_PLAN_2026-06-29.md
2. docs/reports/WAVE2_EXECUTION_PLAN_2026-06-29.md
3. docs/templates/WAVE_RUN_REGISTRY_TEMPLATE.csv
4. examples/waves/enterprise_wave1_portfolio.csv
5. examples/waves/enterprise_wave2_portfolio.csv
6. docs/guides/RLS_AUDIT_WORKFLOW.md
7. docs/templates/RLS_AUDIT_SIGNOFF_TEMPLATE.md

---

## Notes

1. This execution pack is intentionally profile-aware: fast profile is optimized for velocity, while strict and regulated profiles are promoted only with full audit evidence.
2. Keep this file as the source of truth for roadmap execution sequencing; per-wave plans track operational detail.