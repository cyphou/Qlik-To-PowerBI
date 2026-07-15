# CLI Reference

This page documents the current command-line interface of `migrate.py`.

## Quick Usage

```bash
python migrate.py <qlik_file> [options]
```

## Simplified Usage (Recommended)

```bash
# Single-file migration
python migrate.py --source sales.qvf

# Folder migration
python migrate.py --source exports/

# Migration + deploy
python migrate.py --source sales.qvf --workspace <workspace_id>

# Preset aliases
python migrate.py --source sales.qvf --preset balanced
python migrate.py --source sales.qvf --preset max

# Folder -> folder operational wrapper (PowerShell)
./scripts/simple_migration.ps1 -SourceFolder "C:\QlikExports" -TargetFolder "C:\QlikMigrated"
```

`<qlik_file>` can be:
- `.qvf`
- `.json` export
- `.qvw` (with converted sibling `.json`/`.qvf`)

## High-Value Command Patterns

### Single app migration

```bash
python migrate.py sales.qvf
python migrate.py sales.qvf --output-dir artifacts/powerbi_projects/migrated
python migrate.py sales.qvf --skip-extraction
```

### Batch migration

```bash
python migrate.py --batch exports/
python migrate.py --batch exports/ --workers 4 --resume
python migrate.py --batch exports/ --batch-recursive --workers 4
```

### Batch migration from config file

```bash
python migrate.py --batch-config config/batch.json
```

### Profile-based manifest migration

```bash
python migrate.py --migration-manifest examples/migration_manifest.example.json
```

### Build wave manifests from portfolio templates

```bash
# CSV portfolio -> all_apps_manifest.json + wave_*.json
python scripts/build_wave_manifests.py --input docs/templates/QLIK_APP_PORTFOLIO_TEMPLATE.csv --output-dir artifacts/manifests --include-profiles-template

# Also emit runnable *_ready manifests (path-normalized + invalid QVF filtered)
python scripts/build_wave_manifests.py --input docs/templates/QLIK_APP_PORTFOLIO_TEMPLATE.csv --output-dir artifacts/manifests --include-profiles-template --make-ready

# JSON portfolio + auto wave split by criticality/complexity
python scripts/build_wave_manifests.py --input docs/templates/qlik_app_portfolio.template.json --output-dir artifacts/manifests --auto-wave

# Run a generated wave manifest
python migrate.py --migration-manifest artifacts/manifests/wave_Wave-0_manifest.json

# Run a ready wave manifest
python migrate.py --migration-manifest artifacts/manifests/wave_Wave-0_manifest_ready.json
```

### Direct extraction from Qlik server/cloud

```bash
python migrate.py --server-url https://qlik.example.com --server-app-id <app_id>
python migrate.py --server-url https://tenant.region.qlikcloud.com --server-app-id <app_id> --server-api-key <key>
```

### Connection and TLS diagnostics (no migration)

```bash
python migrate.py --server-url https://qlik.example.com --server-test
```

### Shared semantic model / merge workflows

```bash
python migrate.py --shared-model app1.qvf app2.qvf --model-name SharedSales
python migrate.py --merge app1.json app2.json
python migrate.py --assess-server exports/
```

### Governance / QA / validation

```bash
python migrate.py sales.qvf --qa
python migrate.py sales.qvf --validate --post-check --cross-validate --schema-validate
python migrate.py sales.qvf --governance --governance-config config/governance.json
```

### Deployment

```bash
python migrate.py sales.qvf --deploy <workspace_id> --deploy-refresh
python migrate.py --shared-model app1.qvf app2.qvf --deploy-bundle <workspace_id> --bundle-refresh
```

### Reports and packaging

```bash
python migrate.py sales.qvf --full-lineage --pdf-report --pptx-report --package --goals --script-lineage
```

---

## Full Option Index

### Core input/output and execution
- `--source`
- `--src`
- `--out`
- `--preset` (`fast`, `balanced`, `max`)
- `--workspace`
- `--simple-mode` (`fast`, `balanced`, `max`)
- `--help-simple`
- `--skip-extraction`
- `--wizard`
- `--output-dir`
- `--verbose`, `-v`
- `--quiet`, `-q`
- `--log-file`
- `--batch`
- `--batch-recursive`
- `--dry-run`
- `--calendar-start`
- `--calendar-end`
- `--culture`
- `--assess`
- `--mode` (`import`, `directquery`, `composite`)
- `--rollback`
- `--output-format` (`pbip`, `tmdl`, `pbir`, `fabric`)
- `--config`
- `--incremental`
- `--telemetry`
- `--paginated`
- `--batch-config`
- `--migration-manifest`
- `--profile`
- `--validate`
- `--post-check`
- `--json`
- `--plugins`

### Legacy compatibility options
- `--simple-command` (`migrate`, `migrate-max`, `assess`, `compare`, `qa`, `batch`, `batch-max`, `deploy`, `server-test`)
- `--target`
- `--workspace-id`

### Merge, portfolio, and shared model
- `--merge`
- `--assess-server`
- `--shared-model`
- `--model-name`
- `--assess-merge`
- `--force-merge`
- `--strict-merge`
- `--merge-preview`
- `--save-merge-config`
- `--merge-config`
- `--global-assess`

### Comparison, quality, and governance
- `--compare`
- `--no-compare`
- `--dashboard`
- `--optimize-dax`
- `--no-optimize-dax`
- `--time-intelligence` (`auto`, `none`)
- `--qa`
- `--governance`
- `--governance-config`
- `--monitor`
- `--check-drift`
- `--sla-config`
- `--validate-data`
- `--bridge-tables` (`auto`, `none`)
- `--preflight`
- `--force`
- `--connection-map`
- `--strict`
- `--evaluate-policy` (`passthrough`, `blank`, `block`)
- `--cross-validate`
- `--schema-validate`
- `--report-issue`

### Deployment and runtime behavior
- `--deploy`
- `--deploy-refresh`
- `--deploy-bundle`
- `--bundle-refresh`
- `--multi-tenant`
- `--workers`
- `--parallel`
- `--resume`
- `--jsonl-log`
- `--web-ui`
- `--web-port`
- `--endorse` (`promoted`, `certified`)
- `--manifest`
- `--languages`
- `--rolling`
- `--consolidate`
- `--skip-conversion`
- `--sync`
- `--sample-data`

### LLM-assisted refinement
- `--llm-refine`
- `--llm-provider` (`openai`, `anthropic`, `azure`)
- `--llm-model`
- `--llm-key`
- `--llm-endpoint`
- `--llm-max-calls`
- `--llm-dry-run`

### Qlik server/cloud extraction and diagnostics
- `--server-url`
- `--server-api-key`
- `--server-cert`
- `--server-key`
- `--server-root-cert`
- `--server-jwt`
- `--server-user-directory`
- `--server-user-id`
- `--server-no-verify`
- `--server-timeout`
- `--server-test`
- `--server-app-id`

### Refresh schedule generation
- `--refresh-schedule`
- `--refresh-timezone`

### v12 quality/post-processing options
- `--preceptor-review`
- `--self-heal-v3`
- `--repair-strategies`
- `--cutover-plan`
- `--full-lineage`
- `--data-prep-lineage`
- `--no-data-prep-lineage`
- `--pdf-report`
- `--pptx-report`
- `--package`
- `--goals`
- `--script-lineage`

---

## Notes

- Use `python migrate.py --help` for the live, authoritative help text.
- `--batch` scans one folder by default; add `--batch-recursive` to collect `.json`, `.qvf`, and `.qvw` files from nested subfolders with stem-level de-duplication.
- `--batch-config` and `--migration-manifest` are mutually exclusive execution paths and are evaluated before standard single-file processing.
- `--server-test` runs diagnostics and exits without executing migration generation.
- `scripts/build_wave_manifests.py` generates manifest files from portfolio templates; it is intended as a pre-step before `--migration-manifest` runs.
- `--make-ready` emits additional `*_ready.json` and `*_ready_report.json` files with normalized paths and skipped invalid/missing source entries.
