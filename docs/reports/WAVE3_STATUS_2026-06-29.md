<!-- DOC-SHINY-BANNER -->
![Documentation](https://img.shields.io/badge/Documentation-Shiny_Style-0A66C2?style=flat-square&logo=readthedocs&logoColor=white)
![Maintained](https://img.shields.io/badge/Maintained-2026-2EA44F?style=flat-square&logo=github&logoColor=white)
![Navigation](https://img.shields.io/badge/Navigation-Quick_Access-6F42C1?style=flat-square&logo=bookstack&logoColor=white)
# Wave 3 Status (2026-06-29)

## Execution Summary

Wave 3 was generated and executed from the ready manifest using test gate enforcement.

1. Manifest: examples/waves/generated_wave3/wave_Wave-3_manifest_ready.json
2. Entries: 3
3. Succeeded: 3
4. Failed: 0
5. Dry-run duration: 0:00:04.722520
6. Execute duration: 0:00:03.412852

## App Outcomes

1. large_enterprise_sales (profile: regulated)
- Fidelity: 100.0%
- Gate: passed
- Blocking reasons: none
- Validator warning: unknown column/measure [Year] in Orders (non-blocking)

2. qlik_sales_discovery_demo (profile: regulated)
- Fidelity: 100.0%
- Gate: passed
- Blocking reasons: none
- RLS roles parsed: 5
- Validator warnings: unmatched parenthesis in two converted measures and unknown column/measure references (non-blocking)

3. sample_sales_from_qvf_downloaded (profile: strict)
- Fidelity: 100.0%
- Gate: passed
- Blocking reasons: none
- Validator warnings: none

## Notes

1. Gate JSON and HTML reports were generated for all three apps under each app quality_gates folder.
2. Load script converter emitted known non-blocking parse warnings for the two regulated apps.
3. Live run registry was updated with final Wave 3 execution entries.

## Commands Executed

```powershell
python scripts/build_wave_manifests.py --input examples/waves/enterprise_wave3_portfolio.csv --output-dir examples/waves/generated_wave3 --include-profiles-template --output-root output/waves/enterprise_wave3/staging --make-ready

python migrate.py --migration-manifest examples/waves/generated_wave3/wave_Wave-3_manifest_ready.json --dry-run --gate test

python migrate.py --migration-manifest examples/waves/generated_wave3/wave_Wave-3_manifest_ready.json --gate test
```

