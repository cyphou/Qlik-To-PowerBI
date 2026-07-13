# Enterprise Scale Migration Roadmap (2026-06-29)

## Goal

Migrate multiple Qlik projects at enterprise scale using config-driven execution, strict security controls, and gated promotion across dev, test, and prod.

This update builds on the 2026-06-26 complex flow roadmap and reflects the current implementation state in this repository.

---

## Current Status Check (as of 2026-06-29)

### Completed

1. Environment quality gates are implemented and wired in CLI:
- Gate modes: dev, test, prod
- Override path: --force-deployment

2. Gate enforcement is active for:
- Single-file runs
- Batch runs
- Batch-config runs
- Manifest runs

3. Batch/manifest gate metrics now use real post-generation artifacts:
- Security export status
- Embedded image inventory counts
- Power Query inventory counts

4. Batch migration stats path is thread-safe for parallel worker execution.

5. Runner scripts are aligned to venv Python execution (with fallback strategy where needed).

6. Wave tooling is in place:
- Portfolio CSV
- Manifest builder script
- Wave 0 concrete portfolio and generated manifests
- Staging drill and complex flow scripts

7. Full regression run passed:
- 2908 tests passed

### Operational Gaps Remaining for True Scale

1. Centralized run registry is now templated, but not yet auto-populated from each run output.
2. No mandatory approval workflow enforcement before prod gate override (process currently script-driven).
3. Security sign-off workflow exists, but evidence collection and closure tracking are still manual.
4. Limited wave-level SLO dashboarding (success rate, rerun latency, gate failure taxonomy).

---

## Target Operating Model for Scale

Use a migration factory model with four parallel lanes:

1. Intake and Tiering Lane
- Portfolio ingestion from CSV/JSON templates
- Automatic tier and wave assignment
- Dependency and criticality tagging

2. Conversion Lane
- Config/manifest-driven execution only (no ad-hoc prod runs)
- Standardized profile usage: fast, strict, regulated

3. Security and Compliance Lane
- Mandatory security artifact bundle per app
- RLS/role review checkpoints
- Explicit approval records before prod promotion

4. Release and Operations Lane
- Gate-based promotion
- Rollback drill per wave
- Post-cutover incident and rerun management

---

## Updated 8-Week Roadmap

### Phase 0 (Week 1): Program Setup and Baseline Freeze

Deliverables:

1. Portfolio baseline frozen in one canonical file.
2. Wave governance matrix approved (owner, approver, SLA per wave).
3. Config standards frozen for profiles and gate thresholds.

Execution:

1. Build manifests from portfolio templates.
2. Produce Wave 0 and Wave 1 ready manifests.
3. Register baseline fidelity targets by app criticality.

Exit Criteria:

1. 100 percent of candidate apps have owner, tier, criticality, target wave.
2. All apps mapped to profile: fast, strict, or regulated.

### Phase 1 (Week 2-3): Pilot Factory (Wave 0)

Deliverables:

1. Wave 0 staged through dry-run and execution using test gate.
2. Security bundle generated for each app.
3. Gate failure taxonomy created from pilot defects.

Execution:

1. Use enterprise Wave 0 runner with manifest and gate controls.
2. Enforce staging rollback drill for each pilot batch.
3. Capture rerun timings and defect categories.

Exit Criteria:

1. Wave 0 success rate at or above 90 percent.
2. Zero untriaged gate failures.
3. Rollback drill completed and documented.

### Phase 2 (Week 4-5): Scale-Out (Wave 1 and Wave 2)

Deliverables:

1. Parallel wave execution for Tier A and stable Tier B apps.
2. Security sign-off workflow operational for regulated profiles.
3. Standard incident playbook for gate failures and reruns.

Execution:

1. Run hybrid mode for mixed complexity waves.
2. Reserve download-first path for Tier C and regulated Tier B.
3. Track gate trend lines: fidelity, RLS status, M-query review coverage.

Exit Criteria:

1. Wave throughput meets planned weekly app volume.
2. Mean rerun time below 30 minutes for non-source failures.
3. No prod promotion without documented security approval.

### Phase 3 (Week 6-7): Regulated and Complex Cutovers (Wave 3)

Deliverables:

1. Tier C cutover plan per app (owner, window, rollback point).
2. Executive risk log with top blockers and mitigations.
3. Formal prod readiness review gate.

Execution:

1. Download-first evidence capture before conversion.
2. Mandatory dual review of security and prepflow transformations.
3. Controlled prod gate execution with override audit trail.

Exit Criteria:

1. Tier C first-pass success at or above 80 percent.
2. Zero critical incidents without rollback path.

### Phase 4 (Week 8): Stabilization and Handover

Deliverables:

1. Migration factory runbook finalized.
2. Operations dashboard baseline and weekly review cadence.
3. Backlog of remaining optimization items prioritized.

Exit Criteria:

1. Incident rate below 2 percent in first two weeks post-cutover.
2. Steady-state ownership transitioned to operations team.

---

## Security and Config Control Plan

### Mandatory Artifacts Per Migrated App

1. security/security_extract.csv
2. images/embedded_images.csv and decoded image folder (if present)
3. power_query artifacts folder
4. quality gate JSON and HTML outputs
5. migration report with fidelity score

### Mandatory Controls

1. Regulated profile requires test and prod gate pass records.
2. Any prod override requires:
- Incident reference
- Approver identity
- Time-bound remediation action

3. No direct prod run without manifest entry and profile assignment.

---

## KPI Framework for Scale

### Throughput KPIs

1. Apps migrated per week (planned vs actual).
2. Wave completion rate on schedule.

### Quality KPIs

1. Median fidelity by wave and by criticality.
2. Gate pass rate by environment.

### Security KPIs

1. RLS audit pass ratio.
2. Security artifact completeness ratio.

### Reliability KPIs

1. Mean rerun time.
2. Post-cutover incident rate.

---

## Command-Ready Execution Track

### 1) Build wave manifests from portfolio

```powershell
python scripts/build_wave_manifests.py --input examples/waves/enterprise_wave0_portfolio.csv --output-dir examples/waves/generated_wave0 --include-profiles-template --output-root output/waves/enterprise_wave0/staging --make-ready
```

### 2) Execute Wave 0 with gate control

```powershell
./scripts/run_enterprise_wave0.ps1 -Gate test -MakeReady
```

### 3) Execute complex flow for mixed portfolio

```powershell
./scripts/run_enterprise_complex_flow.ps1 -Mode hybrid -Gate test -ManifestPath examples/waves/enterprise_complex_wave_manifest.template.json
```

### 4) Stage drill for rollback readiness

```powershell
./scripts/run_pilot_wave_staging.ps1 -Gate test -ManifestPath examples/waves/wave1_staging_manifest.json
```

---

## Next Update Trigger

Publish the next roadmap update after Wave 0 closeout with:

1. Actual gate pass/fail distributions.
2. Rerun and incident metrics.
3. Updated Wave 1 and Wave 2 capacity plan.
