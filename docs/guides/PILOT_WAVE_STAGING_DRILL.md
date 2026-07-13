# Pilot Wave Staging Drill

This drill validates end-to-end execution for the first staging wave and confirms rollback readiness.

## Objectives

- Verify manifest-based wave execution works with environment gates.
- Confirm gate reports are generated per app.
- Simulate rollback decision flow before production cutover.

## Prerequisites

- Virtual environment is active.
- Staging manifest exists at `examples/waves/wave1_staging_manifest.json`.
- Pilot applications listed in the manifest exist and are accessible.

## Step 1: Dry Run

Run a no-write pass to validate parsing and flow:

```powershell
python migrate.py --migration-manifest examples/waves/wave1_staging_manifest.json --gate test --dry-run
```

Expected outcome:

- Command exits with success.
- No output artifacts are written.

## Step 2: Execute Staging Wave

Run the pilot wave against staging:

```powershell
python migrate.py --migration-manifest examples/waves/wave1_staging_manifest.json --gate test
```

Expected outcome:

- Per-app migration summaries are emitted.
- Gate report files are generated in each app output folder under `quality_gates/`.
- Any gate failure causes the app to be marked failed in summary.

## Step 3: Verify Gate Artifacts

For each app output, confirm these files exist:

- `gate_test.json`
- `gate_test.html`

Review:

- `overall_passed`
- `blocked_reasons`
- `warnings`

## Step 4: Rollback Drill (Tabletop)

Use this decision path:

- If any app has blocking gate failures in planned prod profile:
  - Do not promote.
  - Open remediation ticket.
  - Re-run after fixes.
- If staging run encounters critical execution errors:
  - Stop wave.
  - Follow Procedure 1 from `docs/guides/ROLLBACK_PLAYBOOK.md`.

## Step 5: Promote Readiness Decision

Pilot wave is ready for production planning only if all are true:

- No critical migration errors.
- All required gate checks pass for target environment.
- Rollback contacts and communication templates are validated.

## Optional: Scripted Run

Use the helper script:

```powershell
./scripts/run_pilot_wave_staging.ps1 -Gate test
```

Add force override only for controlled test scenarios:

```powershell
./scripts/run_pilot_wave_staging.ps1 -Gate prod -ForceDeployment
```
