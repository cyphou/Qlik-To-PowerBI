# Wave 1 Status (2026-06-29)

## Execution Summary

Wave 1 was generated and executed from the ready manifest using test gate enforcement.

1. Manifest: examples/waves/generated_wave1/wave_Wave-1_manifest_ready.json
2. Entries: 3
3. Succeeded: 3
4. Failed: 0
5. Duration: 0:00:02.259068

## App Outcomes

1. small_sales (profile: fast)
- Fidelity: 100.0%
- Gate: passed
- Blocking reasons: none

2. medium_hr_analytics (profile: strict)
- Fidelity: 100.0%
- Gate: passed
- Blocking reasons: none

3. large_enterprise_sales (profile: regulated)
- Fidelity: 100.0%
- Gate: passed
- Blocking reasons: none
- Validator warning: unknown column/measure [Year] in Orders (non-blocking)

## Notes

1. Gate JSON and HTML reports were produced for all 3 apps in each app quality_gates folder.
2. Load script converter emitted a known non-blocking parse warning for the regulated app; migration and gate still passed.
3. Live run registry created: docs/reports/WAVE_RUN_REGISTRY_2026-06-29.csv

## Commands Executed

```powershell
python scripts/build_wave_manifests.py --input examples/waves/enterprise_wave1_portfolio.csv --output-dir examples/waves/generated_wave1 --include-profiles-template --output-root output/waves/enterprise_wave1/staging --make-ready

python migrate.py --migration-manifest examples/waves/generated_wave1/wave_Wave-1_manifest_ready.json --dry-run --gate test

python migrate.py --migration-manifest examples/waves/generated_wave1/wave_Wave-1_manifest_ready.json --gate test
```
