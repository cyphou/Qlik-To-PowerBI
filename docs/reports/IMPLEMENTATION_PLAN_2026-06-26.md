# Full Roadmap Implementation Plan (Phases 1–5)

**Objective:** Execute all 5 phases of migration workspace roadmap to production readiness.

**Timeline:** Sequential execution across this session, targeting 37 days of effort (staged over following weeks).

**Status:** Phase 1 in progress

---

## Phase 1: Workspace Baseline and Control Plane (4 Days)

### Deliverables

#### 1.1 Formal Workspace Blueprint Document
**File:** `docs/guides/WORKSPACE_BLUEPRINT.md`
- Standard folder layout conventions
- Naming conventions (apps, manifests, outputs, artifacts)
- Manifest structure and validation rules
- Template repository structure
- Definition of workspace "healthy state"

#### 1.2 Canonical Connection Map Template
**File:** `docs/templates/CONNECTION_MAP_TEMPLATE.json`
- M query patterns for all 42 supported connectors
- Datasource-to-table mapping schema
- Column type inference rules
- Sample connections (SQL Server, CSV, Excel, Snowflake, etc.)

#### 1.3 Governance Config Template
**File:** `docs/templates/GOVERNANCE_CONFIG_TEMPLATE.json`
- Compliance rules (naming, PII detection, audit trail)
- Retention policies
- Role-based access control (RBAC) mapping
- Workspace security classification levels

#### 1.4 New-Program Quickstart Guide
**File:** `docs/guides/NEW_PROGRAM_QUICKSTART.md`
- 5-step onboarding for new migration programs
- Walkthrough: inventory → manifest → ready → execute → validate
- Troubleshooting checklist
- Command reference with examples

**Success Criteria:**
- ✅ Quickstart tested with 2 different sample portfolios
- ✅ Blueprint formally adopted as standard
- ✅ All templates have example usage

---

## Phase 2: Multi-App Throughput and Reliability (8.5 Days)

### Deliverables

#### 2.1 Per-Entry Failure Isolation
**Files:** `powerbi_import/import_to_powerbi.py`, `migrate.py`
- Add `--continue-on-error` flag (default: halt on first error)
- Track failed entries separately
- Generate per-entry failure report (app name, phase, error code, remediation)
- Implement skip list mechanism

#### 2.2 Batch Resumption Strategy
**File:** `scripts/batch_runner.py` (new)
- Checkpoint file (JSON): `{app_id, phase, timestamp, status}`
- `--resume-from checkpoint.json` flag
- Resume from checkpoint → skip completed entries
- Merge results from partial + resumed runs

#### 2.3 App-Size Tiering
**File:** `powerbi_import/app_profiler.py` (new)
- Classify apps by extraction/generation cost:
  - **Small (S)**: <100 tables, <5000 columns, <100 measures — 30–60 sec
  - **Medium (M)**: 100–500 tables, 5K–20K columns, 100–300 measures — 2–5 min
  - **Large (L)**: >500 tables, >20K columns, >300 measures — 10–30 min
- Analyze QVF structure to predict tier
- Profile output in manifest

#### 2.4 Parallel Worker Guidance
**File:** `scripts/worker_recommendation.py` (new)
- Input: manifest (list of apps + sizes)
- Calculate: total cost (sum of estimated times)
- Recommend worker count: `(total_cost_sec / 300) + 1` (per-5-min-worker)
- Output: suggested parallelism, estimated total time

#### 2.5 Performance Baseline and Benchmarks
**File:** `docs/reports/PERFORMANCE_BASELINE_2026-06-26.md`
- Run sample portfolio (5 S apps, 2 M apps, 1 L app)
- Document timings: extract, generate, validate per app
- Create benchmark curves (expected duration vs. table count)
- SLA targets: S=1 min, M=3 min, L=15 min

**Success Criteria:**
- ✅ 10-app manifest run with 2–3 simulated failures completes with resume
- ✅ Benchmark dataset published with timing curves
- ✅ Worker recommendation tool tested on 3 different portfolios

---

## Phase 3: Governance and Security Evidence (8 Days)

### Deliverables

#### 3.1 Security Extraction Audit Checklist
**File:** `docs/guides/SECURITY_AUDIT_CHECKLIST.md`
- RLS rule review (expected vs. actual)
- OLS (Object-Level Security) validation
- Section Access mapping verification
- Data-masking rule coverage
- Signing off on security mapping

#### 3.2 Image Inventory Process
**File:** `powerbi_import/image_inventory.py` (new)
- Extract embedded images from QVF
- Document: image ID, size, usage (page/visual), format
- Generate image manifest: `image_inventory.json`
- Track origin (embedded, linked, dataURI)
- Output image assets to `artifacts/images/{app_id}/`

#### 3.3 Power Query Inventory and Versioning
**File:** `powerbi_import/m_query_inventory.py` (new)
- Extract all M queries from manifest
- Generate query hash (fingerprint)
- Track variants across apps
- Produce `m_query_versions.json` (fingerprint → count of uses)
- Flag duplicate/similar queries for consolidation review

#### 3.4 Governance Gate Profile
**File:** `docs/templates/GOVERNANCE_GATE_PROFILE.json`
- Compliance rules (naming patterns, PII detection)
- Audit trail requirements (who/what/when)
- Retention policy (keep artifacts for X days)
- Data classification levels (public, internal, confidential)
- Escalation contact for violations

#### 3.5 Artifact Manifests with Lineage
**File:** `powerbi_import/artifact_lineage_manifest.py` (new)
- Generate `artifact_manifest.json` per app
- Track: field → M query → DAX expression → visual
- Include ownership, approval status, last modified
- Linkable IDs for traceability

**Success Criteria:**
- ✅ Security audit checklist reviewed with 1 app
- ✅ Image inventory extracted and sample images spot-checked
- ✅ M query deduplication identified 3+ consolidation opportunities
- ✅ Lineage manifest shows full field-to-visual traceability

---

## Phase 4: Validation and Quality Gates (8.5 Days)

### Deliverables

#### 4.1 Tiered Quality Gates System
**File:** `powerbi_import/quality_gates.py` (new)
- **Dev Gate:** Structural validation
  - TMDL syntax correctness
  - DAX expression balance + keywords
  - Column reference validity
  - Threshold: **HARD FAIL** on syntax errors
  
- **Test Gate:** QA + cross-validation
  - Cross-platform value comparison (Qlik vs. PBI)
  - Schema validation (expected columns present)
  - Measure calculation correctness (within ±0.1%)
  - Threshold: Fidelity **≥85%**
  
- **Prod Gate:** Preceptor + self-heal
  - Preceptor quality score (6 dimensions)
  - Self-healing recovery (11 model healers)
  - Cutover readiness check
  - Threshold: Quality **≥80%**, All healers pass

#### 4.2 Automatic Gate Enforcement in CLI
**File:** `migrate.py` (update)
- Add `--gate dev|test|prod` flag
- Add `--gate-enforce` (fail if gate condition not met)
- Add `--gate-report` (generate HTML pass/fail report)
- Integration: gates run after generation, before output

#### 4.3 Workspace-Level Summary Dashboard
**File:** `powerbi_import/workspace_summary_dashboard.py` (new)
- Generate HTML dashboard showing:
  - Per-app fidelity score (heatmap)
  - Gate pass rate by environment
  - Failure trends (last 7 runs)
  - Time series of success rate
- Drill-down: click app → detailed report

#### 4.4 Drift Detection Process
**File:** `powerbi_import/drift_detector.py` (new)
- Compare current run vs. baseline snapshot
- Detect schema changes: added/removed/renamed columns
- Detect measure/formula changes (hash comparison)
- Detect visual changes (binding updates)
- Output: `drift_report.json` with changeset

#### 4.5 Per-App Gate Reporting
**File:** `powerbi_import/gate_report_generator.py` (new)
- Generate HTML report per app per gate
- Structure: pass/fail + remediation hints
- Link to diagnostic logs (errors, warnings)
- QR code linking to runbook for common failures

**Success Criteria:**
- ✅ Failed test deployment rejected by prod gate
- ✅ Workspace dashboard shows 10+ app pass rates
- ✅ Drift detection identifies 2–3 intentional schema changes
- ✅ Gate report provides actionable remediation hints

---

## Phase 5: Cutover and Deployment at Scale (8 Days)

### Deliverables

#### 5.1 Promotion Runbook
**File:** `docs/guides/PROMOTION_RUNBOOK.md`
- Multi-wave cutover steps (Dev → Test → Prod)
- Pre-flight checklist (gates pass, security audit complete)
- Rollback decision tree (when to pull the cord)
- Communication templates (notifications, escalations)
- Sign-off procedure

#### 5.2 Deployment Strategy Matrix
**File:** `docs/guides/DEPLOYMENT_STRATEGY_MATRIX.md`
- **Per-App Deploy**
  - Use case: single app, isolated changes
  - Pros: low risk, fast rollback
  - Cons: high administrative overhead
  
- **Bundle Deploy**
  - Use case: related apps with shared semantic model
  - Pros: consistency, reduced workspace clutter
  - Cons: rollback affects multiple consumers
  
- **Rolling Promotion Waves**
  - Use case: 20+ app portfolio
  - Pros: risk distribution, phased validation
  - Cons: complex sequencing, longer duration

#### 5.3 Rollback Playbook and Incident Checklist
**File:** `docs/guides/ROLLBACK_PLAYBOOK.md`
- Immediate rollback: restore from staging backup (steps)
- Partial rollback: single app or bundle revert
- Incident checklist: what to check, who to notify, communication timing
- Post-mortem template: root cause analysis

#### 5.4 Post-Cutover Monitoring and Refresh Config
**File:** `powerbi_import/postcut_monitor.py` (new)
- Health checks: refresh success rate, query latency, error counts
- Alert rules: failure thresholds, escalation paths
- Refresh configuration: incremental vs. full, schedule optimization
- Monitoring dashboard: availability, performance SLAs

#### 5.5 Wave-Control Dashboard
**File:** `powerbi_import/wave_control_dashboard.py` (new)
- Real-time wave status (% complete, active apps)
- Dependency graph (app A → app B ordering)
- Promotion decision log (who approved what)
- Rollback candidates (fast to revert, high confidence)
- Estimated completion time

**Success Criteria:**
- ✅ Multi-wave cutover executed in staging
- ✅ Rollback tested and verified repeatable
- ✅ Wave dashboard shows all 10+ apps with correct status
- ✅ Post-cutover monitoring alerts on first degradation

---

## Execution Sequencing

```
Week 1: Phase 1 (4d) ─→ ✅ Production-ready blueprint + quickstart
            ↓
Week 2: Phase 2 (8.5d) ─→ ✅ Multi-app runs with failure recovery
        Phase 3 (parallel, 8d) ─→ ✅ Security/governance evidence
            ↓
Week 3: Phase 4 (8.5d) ─→ ✅ Quality gates + drift detection
            ↓
Week 4: Phase 5 (8d) ─→ ✅ Production cutover runbook + monitoring
            ↓
Production Readiness: Week 4–5 (pilot cutover, validation)
```

---

## Metrics and Success Criteria (All Phases)

| Phase | Success Metric | Definition |
|-------|---|---|
| 1 | Blueprint adoption | New team executes quickstart 2× with <30 min onboarding |
| 2 | Throughput reliability | 10-app manifest tolerates 2–3 failures, completes with resume |
| 3 | Evidence completeness | 100% of apps have auditable security/image/query artifacts |
| 4 | Gate effectiveness | Prod gate blocks all low-fidelity (<80%) deployments |
| 5 | Cutover success | Multi-wave deployment with rollback tested, repeatable |

---

## Risk Mitigation

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Phase 1 delays block all others | HIGH | CRITICAL | Execute Phase 1 within 4 days, parallel Phase 2+3 prep |
| Failure recovery complexity | MEDIUM | HIGH | Start with simple checkpoint file, iterate |
| Gate strictness over-filters | MEDIUM | MEDIUM | Set thresholds conservatively, collect baseline data first |
| Rollback untested in prod | HIGH | CRITICAL | Test rollback in staging before any prod deployment |

---

## Deliverables Checklist

### Phase 1
- [ ] WORKSPACE_BLUEPRINT.md published
- [ ] CONNECTION_MAP_TEMPLATE.json with examples
- [ ] GOVERNANCE_CONFIG_TEMPLATE.json
- [ ] NEW_PROGRAM_QUICKSTART.md with 2× walkthrough

### Phase 2
- [ ] --continue-on-error flag implemented + tested
- [ ] batch_runner.py with checkpoint resumption
- [ ] app_profiler.py with S/M/L tiering
- [ ] worker_recommendation.py tested on 3 portfolios
- [ ] PERFORMANCE_BASELINE_2026-06-26.md published

### Phase 3
- [ ] SECURITY_AUDIT_CHECKLIST.md with review workflow
- [ ] image_inventory.py extracting images + manifest
- [ ] m_query_inventory.py detecting duplicates
- [ ] GOVERNANCE_GATE_PROFILE.json template
- [ ] artifact_lineage_manifest.py generating full lineage

### Phase 4
- [ ] quality_gates.py with Dev/Test/Prod tiers
- [ ] --gate flag integrated into migrate.py
- [ ] workspace_summary_dashboard.py (HTML)
- [ ] drift_detector.py with schema/formula/visual changes
- [ ] gate_report_generator.py with remediation hints

### Phase 5
- [ ] PROMOTION_RUNBOOK.md published
- [ ] DEPLOYMENT_STRATEGY_MATRIX.md with 3 patterns
- [ ] ROLLBACK_PLAYBOOK.md tested in staging
- [ ] postcut_monitor.py with alerts + dashboards
- [ ] wave_control_dashboard.py showing live status

---

**Start Date:** 2026-06-26  
**Target Completion:** 2026-07-24 (4 weeks estimated)  
**Next Checkpoint:** Phase 1 completion (2026-06-30)
