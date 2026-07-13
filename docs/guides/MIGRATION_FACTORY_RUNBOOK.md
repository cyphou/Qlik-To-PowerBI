# Migration Factory Runbook (2026-06-29)

## Purpose

This runbook is the stable operational reference for running Qlik → Power BI migrations at scale using the config-driven factory model. It reflects validated behavior from Wave 0 through Wave 3 production execution.

---

## Prerequisites

| Item | Required |
|---|---|
| Python 3.14+ with venv activated | `.\venv\Scripts\Activate.ps1` |
| Portfolio CSV (apps to migrate) | `examples/waves/enterprise_wave*_portfolio.csv` |
| Source Qlik app files (JSON or QVF) | Located under `examples/qlik/` |
| Connection map per app | `docs/templates/CONNECTION_MAP_TEMPLATE.json` |
| Governance config | `docs/templates/GOVERNANCE_CONFIG_TEMPLATE.json` |

---

## Step 1 — Prepare Portfolio

Create or update a portfolio CSV (copy from `QLIK_APP_PORTFOLIO_TEMPLATE.csv`) with:

| Column | Required | Notes |
|---|---|---|
| `app_id` | Y | Unique ID per app |
| `app_name` | Y | Display name |
| `source_path` | Y | Path to JSON or QVF |
| `profile` | Y | `fast`, `strict`, or `regulated` |
| `target_workspace` | Y | Output subfolder |
| `target_wave` | Y | `Wave-0` through `Wave-N` |
| `business_owner` | Y | Email for sign-off |
| `criticality` | Y | `low`, `medium`, `high` |
| `complexity_tier` | Y | `A`, `B`, or `C` |

---

## Step 2 — Build Manifests

```powershell
python scripts/build_wave_manifests.py \
  --input examples/waves/enterprise_waveN_portfolio.csv \
  --output-dir examples/waves/generated_waveN \
  --include-profiles-template \
  --output-root output/waves/enterprise_waveN/staging \
  --make-ready
```

Check the `*_ready_report.json` to confirm 0 skipped entries.

---

## Step 3 — Dry-Run (Test Gate)

```powershell
python migrate.py \
  --migration-manifest examples/waves/generated_waveN/wave_Wave-N_manifest_ready.json \
  --dry-run --gate test
```

All entries should show `[OK]` and fidelity ≥ fidelity_target from portfolio.

---

## Step 4 — Execute (Test Gate)

```powershell
python migrate.py \
  --migration-manifest examples/waves/generated_waveN/wave_Wave-N_manifest_ready.json \
  --gate test
```

Gate JSON and HTML artifacts are written to each app's `quality_gates/` folder.

---

## Step 5 — Review Gate Artifacts

For each app:

1. Open `quality_gates/gate_test.json` — confirm `overall_passed: true`.
2. Review validator warnings in run output — categorize as blocking or non-blocking.
3. Check fidelity score against portfolio target.

---

## Step 6 — RLS Sign-Off (Strict / Regulated Profiles)

1. Open `docs/templates/RLS_AUDIT_SIGNOFF_TEMPLATE.md` and fill one copy per app.
2. Security lead reviews roles in `<app>.SemanticModel/definition/roles/`.
3. Record sign-off reference ID in the live run registry.

Reference: [RLS Audit Workflow](docs/guides/RLS_AUDIT_WORKFLOW.md)

---

## Step 7 — Prod Gate Rehearsal

```powershell
python migrate.py \
  --migration-manifest examples/waves/generated_waveN/wave_Wave-N_manifest_ready.json \
  --dry-run --gate prod
```

All entries must show `overall_passed: true` under prod gate.

---

## Step 8 — Production Execution

```powershell
python migrate.py \
  --migration-manifest examples/waves/generated_waveN/wave_Wave-N_manifest_ready.json \
  --gate prod
```

---

## Step 9 — Update Run Registry

Update `docs/reports/WAVE_RUN_REGISTRY_*.csv`:

1. Change `status` from `planned` → `completed`.
2. Record `start_time_utc`, `end_time_utc`, `fidelity_score`.
3. Confirm `gate_overall_passed = true`.
4. Confirm `rls_signoff_id` is populated for strict/regulated apps.

---

## Step 10 — Publish Wave Status Report

Create `docs/reports/WAVE<N>_STATUS_YYYY-MM-DD.md` (use Wave 1/2/3 examples as template).

Include:
1. App-by-app outcomes
2. Gate and fidelity summary
3. Validator warnings and known non-blocking items
4. Commands executed

---

## Override Policy

Force-override is only allowed when:

1. An incident reference is opened and attached.
2. An approver identity is recorded.
3. A remediation target date is set.

Command:

```powershell
python migrate.py --migration-manifest <manifest> --gate prod --force-deployment
```

---

## Escalation Path

| Severity | Action |
|---|---|
| Critical gate failure | Block wave, triage within 4 hours, assign owner |
| High gate failure | Block promotion, triage within 1 business day |
| Low/warning | Log in status report, add to backlog, do not block |
| Fidelity < target | Review migration report, fix source issue or adjust target |

---

## Known Non-Blocking Patterns (as of 2026-06-29)

1. `LOAD statement mal formé` — load script parse warning from complex scripts; extraction succeeds.
2. Unknown column/measure `[Year]` in Orders — time-intelligence reference gap; tracked in backlog.
3. Unmatched parenthesis in advanced inter-record measures — DAX conversion limitation for `RangeSum(Above(...))` and `Aggr(Top-N)`; add to manual review list.
4. Ambiguous Calendar relationship deactivated — expected for multi-date tables; requires manual reactivation for specific use cases.
