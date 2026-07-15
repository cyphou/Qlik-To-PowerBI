<!-- DOC-SHINY-BANNER -->
![Documentation](https://img.shields.io/badge/Documentation-Shiny_Style-0A66C2?style=flat-square&logo=readthedocs&logoColor=white)
![Maintained](https://img.shields.io/badge/Maintained-2026-2EA44F?style=flat-square&logo=github&logoColor=white)
![Navigation](https://img.shields.io/badge/Navigation-Quick_Access-6F42C1?style=flat-square&logo=bookstack&logoColor=white)
# Wave 2 Status (2026-06-29)

## Execution Summary

Wave 2 was generated and executed from the ready manifest using test gate enforcement.

1. Manifest: examples/waves/generated_wave2/wave_Wave-2_manifest_ready.json
2. Entries: 3
3. Succeeded: 3
4. Failed: 0
5. Duration: 0:00:02.800069

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
3. Live run registry updated: docs/reports/WAVE_RUN_REGISTRY_2026-06-29.csv

## Commands Executed

```powershell
python scripts/build_wave_manifests.py --input examples/waves/enterprise_wave2_portfolio.csv --output-dir examples/waves/generated_wave2 --include-profiles-template --output-root output/waves/enterprise_wave2/staging --make-ready

python migrate.py --migration-manifest examples/waves/generated_wave2/wave_Wave-2_manifest_ready.json --dry-run --gate test

python migrate.py --migration-manifest examples/waves/generated_wave2/wave_Wave-2_manifest_ready.json --gate test
```

