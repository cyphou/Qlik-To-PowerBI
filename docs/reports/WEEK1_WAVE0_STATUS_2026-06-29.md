<!-- DOC-SHINY-BANNER -->
![Documentation](https://img.shields.io/badge/Documentation-Shiny_Style-0A66C2?style=flat-square&logo=readthedocs&logoColor=white)
![Maintained](https://img.shields.io/badge/Maintained-2026-2EA44F?style=flat-square&logo=github&logoColor=white)
![Navigation](https://img.shields.io/badge/Navigation-Quick_Access-6F42C1?style=flat-square&logo=bookstack&logoColor=white)
# Week 1 Wave 0 Status (2026-06-29)

## Scope Executed

Wave 0 was executed using the ready manifest and test gate path:

- Manifest: examples/waves/generated_wave0/wave_Wave-0_manifest_ready.json
- Runner: scripts/run_enterprise_wave0.ps1
- Gate: test
- Mode: dry-run + execute

---

## Wave 0 Outcome Summary

Execution outcome after strict test-gate enforcement, profile-aware RLS policy, and renamed-measure fidelity fix:

1. Total entries: 3
2. Succeeded: 3
3. Failed: 0

Apps:

1. small_sales (profile: fast)
- Fidelity: 100.0%
- Gate JSON: overall_passed = true
- Blocking reasons: none
- Notes: Measure/column collision renames are now reconciled correctly in migration reporting

2. medium_hr_analytics (profile: strict)
- Fidelity: 100.0%
- Gate JSON: overall_passed = true
- Blocking reasons: none
- Notes: No skipped items; gate now passes with artifact-derived RLS evidence

3. large_enterprise_sales (profile: regulated)
- Fidelity: 93.3%
- Gate JSON: overall_passed = true
- Blocking reasons: none
- Notes: 3 calculations skipped; load script conversion warning observed

Aggregate fidelity (mean): 84.4%

---

## Security and Gate Artifact Status

Mandatory artifacts produced for all three apps:

1. quality_gates/gate_test.json
2. migration_report_*.json
3. Generated PBIP project structures under output/waves/enterprise_wave0/staging

Observed gate details:

1. RLS audit check is now profile-aware.
2. Strict and regulated apps pass test gate with current artifact-derived RLS evidence.
3. Fast-profile app now passes after migration report reconciliation fix for renamed measures.

Implication:

- Test gate now behaves as a real promotion gate.
- Fast profile is no longer blocked by strict/regulated security controls.
- Wave 1 can proceed for profiles that continue to meet fidelity and evidence requirements.

---

## Issues Found During Run

### Resolved in this cycle

1. False wave failure due to gate report rendering exception (Windows charmap/Unicode)
- Impact before fix: migration summary showed failed apps even when gate evaluation passed
- Fix applied in migrate.py: gate outcome no longer downgraded by report rendering issues

2. Root cause hardening in gate reporter
- Fix applied in powerbi_import/quality_gates.py:
  - JSON report write now uses UTF-8
  - HTML report write now uses UTF-8
  - HTML includes utf-8 meta charset

3. Test gate policy enforcement corrected
- Fix applied in powerbi_import/quality_gates.py:
  - DEV blocks only critical failures
  - TEST blocks critical and high-severity failures
  - PROD blocks critical and high-severity failures and requires approval on failure

### Remaining functional risk to confirm

1. Security evidence generation path still needs a concrete audit completion workflow definition so current artifact-derived evidence is policy-approved and auditable.
2. Current fidelity defect for renamed measures is resolved, but the same collision pattern should be monitored on future apps.

Recommendation:

- Keep RLS audit enforcement for strict and regulated profiles.
- Exempt fast profile from strict/regulated RLS gating by default.
- Add audit completion workflow before Wave 1 for strict and regulated profiles.

---

## Week 1 KPI Snapshot

Throughput KPI:

1. Wave completion: 100% under strict test gate (3/3 apps promoted)

Quality KPI:

1. Mean fidelity: 97.8%
2. Apps >= 85% fidelity: 3/3 (100%)

Reliability KPI:

1. Manifest execution/runtime failures: 0 after gate robustness and UTF-8 report fixes

Security KPI:

1. Gate JSON artifacts generated: 3/3
2. RLS check passed in test gate details: 2/2 for strict/regulated profiles
3. Apps blocked by missing RLS audit: 0 after profile-aware policy fix

---

## Decision and Next Actions for Week 2

1. Accept Wave 0 as successful under enforced policy.
2. Define and formalize RLS audit workflow for strict and regulated profiles.
3. Prepare Wave 1 using profiles that continue to satisfy gate evidence requirements.
4. Monitor future measure/column collision cases to ensure fidelity accounting remains correct.

---

## Command Trace (executed)

```powershell
.\venv\Scripts\python scripts/build_wave_manifests.py --input examples/waves/enterprise_wave0_portfolio.csv --output-dir examples/waves/generated_wave0 --include-profiles-template --output-root output/waves/enterprise_wave0/staging --make-ready

powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_enterprise_wave0.ps1 -Gate test -MakeReady
```

