<!-- DOC-SHINY-BANNER -->
![Documentation](https://img.shields.io/badge/Documentation-Shiny_Style-0A66C2?style=flat-square&logo=readthedocs&logoColor=white)
![Maintained](https://img.shields.io/badge/Maintained-2026-2EA44F?style=flat-square&logo=github&logoColor=white)
![Navigation](https://img.shields.io/badge/Navigation-Quick_Access-6F42C1?style=flat-square&logo=bookstack&logoColor=white)
# Wave 3 Prod Gate Rehearsal (2026-06-29)

## Scope

Production gate rehearsal was executed in dry-run mode for the Wave 3 ready manifest.

1. Manifest: examples/waves/generated_wave3/wave_Wave-3_manifest_ready.json
2. Gate: prod
3. Mode: dry-run

## Outcome

1. Total entries: 3
2. Succeeded: 3
3. Failed: 0
4. Duration: 0:00:03.719188

Apps:

1. large_enterprise_sales (regulated): passed prod gate rehearsal
2. qlik_sales_discovery_demo (regulated): passed prod gate rehearsal
3. sample_sales_from_qvf_downloaded (strict): passed prod gate rehearsal

## Observations

1. Existing non-blocking conversion/validator warnings remain visible in logs for regulated apps.
2. No prod gate blocking failures occurred in rehearsal.
3. Gate prod JSON/HTML reports were generated under each app quality_gates folder.

## Command Executed

```powershell
python migrate.py --migration-manifest examples/waves/generated_wave3/wave_Wave-3_manifest_ready.json --dry-run --gate prod
```

## Promotion Readiness Note

Wave 3 is technically ready for promotion flow from a gate-policy perspective, pending process requirements:

1. RLS sign-off evidence closure for regulated apps.
2. Approver records and any policy-required change tickets.

