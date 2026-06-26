# Full Migration Workspace Roadmap (2026-06-26)

## Objective

Establish an end-to-end, production-grade workspace model for large-scale Qlik to Power BI migrations, including planning, execution, governance, validation, and deployment.

This roadmap extends current capabilities (manifest orchestration, server diagnostics, and artifact exports) into a repeatable operating model for multi-app migration programs.

---

## Scope

In scope:
- Multi-app migration orchestration in one workspace
- Profile-driven execution and environment-specific overrides
- Workspace artifact governance (security, images, Power Query, lineage)
- Quality gates and release readiness criteria
- Operational runbooks for batch, resume, and cutover

Out of scope:
- Rebuilding visual templates manually in Power BI Desktop
- Replacing source-system data governance processes
- Non-Qlik source migration

---

## Qlik Apps Portfolio Strategy

This roadmap treats Qlik apps as first-class migration units with explicit
inventory, prioritization, and wave controls.

### App inventory model

Track each Qlik app with:
- app id / source file
- business owner
- criticality (low/medium/high)
- data volume tier (S/M/L)
- complexity indicators:
  - set analysis depth
  - inter-record/table calc usage
  - custom visuals/extensions
  - section access complexity
- target workspace and deployment wave

### App tiering (execution class)

- Tier A (simple): standard visuals, limited calc complexity
- Tier B (moderate): multiple sheets, moderate DAX conversion complexity
- Tier C (complex): dense set analysis, advanced security, or extension-heavy

### Wave planning for Qlik apps

1. Wave 0 (pilot): 3–5 apps across A/B/C tiers
2. Wave 1: high-value Tier A + stable Tier B apps
3. Wave 2: remaining Tier B apps with governance hardening
4. Wave 3: Tier C apps with expanded validation and manual review buffers

### Per-app acceptance gates

Each app must pass:
- extraction integrity checks
- model generation and validation checks
- RLS/security extraction review
- visual coverage sanity checks
- fidelity threshold and owner sign-off

### Recommended app-level commands

```bash
# App diagnostics (server/TLS/auth)
python migrate.py --server-url https://qlik.example.com --server-test

# Single app migration with strict quality gates
python migrate.py <app.qvf> --qa --cross-validate --schema-validate --preceptor-review --self-heal-v3

# Multi-app wave run through manifest
python migrate.py --migration-manifest examples/migration_manifest.example.json
```

---

## Target Workspace Operating Model

### Workspace layout

- Source inputs: app exports, server extraction metadata
- Migration control: manifest, profiles, config maps, governance rules
- Execution outputs: generated PBIP/TMDL projects
- Evidence outputs: validation reports, drift reports, QA reports
- Deployment outputs: bundle/deploy logs and promotion records

### Execution principles

1. Manifest-first orchestration for all multi-app runs
2. Deterministic output folder conventions
3. Mandatory quality gates before deployment
4. Traceable artifact packaging per migrated app
5. Repeatable roll-forward and rollback procedures

---

## Phased Roadmap

## Phase 1 - Workspace Baseline and Control Plane

Status: Planned

Deliverables:
- Standard workspace blueprint for migration programs
- Canonical manifest conventions (defaults, profiles, entries)
- Run profile taxonomy (fast, strict, regulated)
- Control files convention:
  - migration manifest
  - governance config
  - connection map
  - optional merge config

Definition of done:
- New migration program can start from one documented folder layout and one manifest template
- At least 3 profiles validated in real runs

---

## Phase 2 - Multi-App Throughput and Reliability

Status: Planned

Deliverables:
- Robust batch and manifest runbook with resume strategy
- Failure isolation strategy (per-entry fail without full-stop)
- Parallel worker guidance by app-size tier (S, M, L)
- Performance benchmark baseline for extraction and generation

Definition of done:
- 95% of entries complete in one pass on benchmark dataset
- Partial failures reported with actionable per-entry diagnostics

---

## Phase 3 - Governance and Security Evidence

Status: Planned

Deliverables:
- Standardized security extraction output review process
- Embedded-image inventory process for report hardening
- Power Query inventory policy (versioning and review)
- Governance gate profile for regulated workspaces

Definition of done:
- Every app output includes auditable security/image/query evidence
- Governance checks integrated into release gate checklist

---

## Phase 4 - Validation and Quality Gates

Status: Planned

Deliverables:
- Tiered quality gates by environment:
  - Dev gate: structural validation
  - Test gate: QA + cross-validation + schema validation
  - Prod gate: preceptor + self-heal + cutover readiness
- Workspace-level dashboard/reporting for fidelity and failure trends
- Drift detection process for iterative migrations

Definition of done:
- Promotion blocked automatically when gate criteria fail
- Workspace summary report includes pass/fail by app and gate

---

## Phase 5 - Cutover and Deployment at Scale

Status: Planned

Deliverables:
- Promotion runbook for workspace-wide cutover
- Deployment strategy matrix:
  - per-app deploy
  - bundle deploy
  - rolling promotion waves
- Rollback playbook and incident checklist
- Post-cutover monitoring and refresh verification process

Definition of done:
- Multi-app cutover executed with documented wave controls
- Rollback tested in staging and proven repeatable

---

## Recommended Command Packs

### Baseline multi-app run

```bash
python migrate.py --migration-manifest examples/migration_manifest.example.json
```

### Build wave manifests from portfolio inventory

```bash
python scripts/build_wave_manifests.py --input docs/templates/QLIK_APP_PORTFOLIO_TEMPLATE.csv --output-dir artifacts/manifests --include-profiles-template
python migrate.py --migration-manifest artifacts/manifests/wave_Wave-0_manifest.json
```

### Strict quality gate run

```bash
python migrate.py app.qvf --qa --cross-validate --schema-validate --preceptor-review --self-heal-v3 --repair-strategies
```

### Server diagnostics before extraction wave

```bash
python migrate.py --server-url https://qlik.example.com --server-test
```

### Deploy wave

```bash
python migrate.py app.qvf --deploy WORKSPACE_ID --deploy-refresh
```

---

## Risk Register (Top Items)

1. Source variability across apps causes profile drift
Mitigation: enforce profile templates and per-entry override limits

2. Large app performance degrades parallel throughput
Mitigation: app-size tiering, worker caps, benchmark baselines

3. Security mapping ambiguity for RLS edge cases
Mitigation: mandatory role extraction review and pre-prod validation gate

4. Workspace output sprawl reduces traceability
Mitigation: strict folder conventions and artifact manifests

---

## Metrics and KPIs

Execution KPIs:
- App success rate per wave
- Mean migration duration per app tier
- Failure rate by phase (extract/generate/validate/deploy)

Quality KPIs:
- Median fidelity score
- Gate pass rate by environment
- Drift incidents per release cycle

Operations KPIs:
- Mean time to rerun failed entry
- Rollback success rate
- Deployment wave completion time

---

## Next Actions (30/60/90)

### Next 30 days
- Finalize workspace blueprint and manifest conventions
- Publish profile catalog and sample manifests
- Baseline benchmark dataset and throughput targets

### Next 60 days
- Implement environment-tiered quality gates
- Introduce workspace-level summary reporting
- Run first full migration workspace pilot

### Next 90 days
- Execute wave-based deployment runbook in production-like environment
- Validate rollback and incident process
- Freeze v1 operating model and governance checklist

---

## Related Documents

- [CLI Reference](../guides/CLI_REFERENCE.md)
- [Migration Guide](../guides/MIGRATION_GUIDE.md)
- [Roadmap Status 2026-06-24](ROADMAP_STATUS_2026-06-24.md)
- [Parity Index 2026-06-24](INDEX_2026-06-24.md)
- [Qlik App Portfolio CSV Template](../templates/QLIK_APP_PORTFOLIO_TEMPLATE.csv)
- [Qlik App Portfolio JSON Template](../templates/qlik_app_portfolio.template.json)
- [Wave Execution Plan Template](../templates/WAVE_EXECUTION_PLAN_TEMPLATE.md)
