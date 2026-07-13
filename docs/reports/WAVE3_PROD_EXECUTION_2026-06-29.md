# Wave 3 Prod Execution (2026-06-29)

## Scope

Wave 3 was executed using production gate enforcement in non-dry-run mode.

1. Manifest: examples/waves/generated_wave3/wave_Wave-3_manifest_ready.json
2. Gate: prod
3. Mode: execute

## Outcome

1. Total entries: 3
2. Succeeded: 3
3. Failed: 0
4. Duration: 0:00:03.843697

Apps:

1. large_enterprise_sales (regulated): passed prod execution
2. qlik_sales_discovery_demo (regulated): passed prod execution
3. sample_sales_from_qvf_downloaded (strict): passed prod execution

## Notes

1. Gate prod JSON and HTML reports were generated for all three apps.
2. Existing non-blocking conversion and validator warnings remain for regulated apps.
3. No gate-blocking failures occurred.

## Command Executed

```powershell
python migrate.py --migration-manifest examples/waves/generated_wave3/wave_Wave-3_manifest_ready.json --gate prod
```
