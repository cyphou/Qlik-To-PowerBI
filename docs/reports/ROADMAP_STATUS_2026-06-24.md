<!-- DOC-SHINY-BANNER -->
![Documentation](https://img.shields.io/badge/Documentation-Shiny_Style-0A66C2?style=flat-square&logo=readthedocs&logoColor=white)
![Maintained](https://img.shields.io/badge/Maintained-2026-2EA44F?style=flat-square&logo=github&logoColor=white)
![Navigation](https://img.shields.io/badge/Navigation-Quick_Access-6F42C1?style=flat-square&logo=bookstack&logoColor=white)
# QlikToPowerBI Status and Migration Roadmap (2026-06-24)

## Scope

- Current repository status (versions, agents, feature readiness).
- Parity checkpoint against the TableauToPowerBI baseline referenced by this repo.
- Migration execution roadmap for production use.

## Current Status Snapshot

### Version and documentation consistency

- Project package version is `12.0.0` in `pyproject.toml`.
- `powerbi_import/__init__.py` is `12.0.0`.
- `qlik_export/__init__.py` is `12.0.0`.
- `README.md` top badges have been refreshed to current v12 status.

### Codebase readiness

- `migrate.py` includes v12 flags and post-generation wiring:
  - `--preceptor-review`
  - `--self-heal-v3`
  - `--repair-strategies`
  - `--cutover-plan`
  - `--full-lineage`
  - `--pdf-report`
  - `--pptx-report`
  - `--package`
  - `--goals`
  - `--script-lineage`
- Implemented modules include preceptor, self-healing, cutover, full lineage, PDF/PPTX/package, goals, automation.

### Agent model

- Specialized multi-agent model is present and documented:
  - Orchestrator, Extractor, Converter, Dax, Wiring, Semantic, Visual, Generator, Assessor, Merger, Deployer, Reviewer, Tester, plus Preceptor role guidance.
- Preceptorship process is documented and integrated with quality review and escalation logic.

### Measured repository indicators (quick scan)

- Test files detected: `82`.
- Approximate test functions detected: `2745`.
- Top-level `powerbi_import/*.py` modules detected: `83`.

## TableauToPowerBI Parity Check

## What is confirmed from this repo

- Changelog and plans indicate major parity waves were already ported (v9-v12).
- Core parity areas appear implemented:
  - Visual mapping depth
  - DAX conversion breadth
  - QA gates and validators
  - Deployment/fabric/merge capabilities
  - Preceptorship + self-healing + reporting stack

## What is not directly confirmed

- Live upstream verification of latest TableauToPowerBI release was not available via accessible GitHub endpoints during this check.
- Treat this roadmap as parity with the baseline declared in local docs, then run a focused upstream diff once source access is available.

## Known Gaps and Risks to Close First

1. Remaining parity modules from older plan naming are not present (`subscription_migrator.py`, `prep_lineage.py`, `prep_lineage_report.py`), and may require either:
   - implementation, or
   - explicit deprecation/rename mapping to existing modules.
2. Upstream TableauToPowerBI live delta is still not directly validated in this snapshot and should be re-checked when authoritative upstream access is available.
3. Parity drift must be monitored continuously with automated checks.

## Implemented Since Initial Snapshot

- Version and README metadata drift fixed.
- `docs/DEV_PLAN_v12.md` replaced by a live execution plan.
- Automated checker added: `tools/analysis/parity_status_check.py`.

## Recommended Roadmap (Next 4 Milestones)

## Milestone 1: Source-of-truth cleanup (1-2 days)

- Align all visible versions to `12.x` or chosen next version.
- Refresh README badges and feature matrix from current code.
- Replace `DEV_PLAN_v12.md` with a status-based roadmap that starts from implemented reality.

## Milestone 2: Parity validation harness (2-4 days)

- Build a deterministic parity matrix (feature -> module -> tests -> CLI flags).
- Add a script that asserts parity claims against actual files/flags.
- Add regression tests for v12 flag combinations used in production.

## Milestone 3: Migration reliability hardening (1-2 weeks)

- Expand edge-case tests for:
  - DAX complex expressions
  - M transformations and escaping
  - relationship/bridge synthesis
  - large-app memory and runtime thresholds
- Add benchmark gates for extraction and generation stages.

## Milestone 4: Upstream sync protocol (ongoing)

- Define a monthly sync process:
  - Pull upstream feature delta.
  - Map to existing modules.
  - Port or close with rationale.
  - Update changelog and parity matrix.

## Migration Execution Blueprint (How to Migrate Safely)

## 1) Baseline migration

```bash
python migrate.py app.qvf --output-dir output/migration_run
```

## 2) Enable quality and repair gates

```bash
python migrate.py app.qvf \
  --qa \
  --self-heal-v3 \
  --repair-strategies \
  --preceptor-review \
  --cross-validate \
  --schema-validate
```

## 3) Generate cutover and lineage artifacts

```bash
python migrate.py app.qvf \
  --cutover-plan \
  --full-lineage \
  --script-lineage \
  --pdf-report \
  --pptx-report \
  --package
```

## 4) Optional deploy path

```bash
python migrate.py app.qvf --deploy <WORKSPACE_ID> --deploy-refresh
```

## Immediate Action List

1. Update version and badges for consistency.
2. Refresh roadmap doc to remove completed items and expose real open work.
3. Add parity matrix automation to prevent future plan drift.
4. Run full regression and publish a v12.x stabilization note.
