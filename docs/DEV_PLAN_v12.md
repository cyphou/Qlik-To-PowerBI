# DEV_PLAN v12.0 — Roadmap to TableauToPowerBI Parity

**Baseline:** v11.0.0 — 2,605 tests, 70 powerbi_import modules, 73 test files  
**Target:** v15.0.0 — ~4,000+ tests, ~84 powerbi_import modules, feature parity with TableauToPowerBI v38

---

## Gap Analysis Summary

| Metric | QlikToPowerBI v11 | TableauToPowerBI v38 | Gap |
|--------|-------------------|----------------------|-----|
| Tests | 2,605 | 8,511+ | 3.3× behind |
| Modules (powerbi_import) | 70 | 74 | 4 missing + depth gaps |
| Test files | 73 | ~180 | ~107 behind |
| CLI flags | ~98 | ~120 | ~22 missing |
| Visual mappings | 120+ | 118+ | ✓ At parity |
| DAX conversions | 175+ | 180+ | Near parity |
| M connectors | 42 | 33 | ✓ Ahead |

### Missing Modules (14)

| Module | Category | Priority |
|--------|----------|----------|
| `preceptor.py` | Quality gates | P1 |
| `self_healing_v3.py` | Quality gates | P1 |
| `repair_strategies.py` | Quality gates | P1 |
| `self_healing_report.py` | Quality gates | P1 |
| `cutover_manager.py` | Enterprise ops | P2 |
| `full_lineage.py` | Lineage | P2 |
| `pdf_renderer.py` | Report export | P3 |
| `pptx_report.py` | Report export | P3 |
| `report_packager.py` | Report export | P3 |
| `subscription_migrator.py` | Server integration | P3 |
| `goals_generator.py` | PBI features | P4 |
| `prep_lineage.py` | Qlik-specific lineage | P4 |
| `prep_lineage_report.py` | Qlik-specific lineage | P4 |
| `automation.py` | Post-migration | P4 |

---

## Phase 1 — Preceptor & Self-Healing (v12.0.0)

**Goal:** Structured quality gate loop with auto-repair and audit trail.

| Module | Description | Estimated Tests |
|--------|-------------|-----------------|
| `preceptor.py` | DRAFT→REVIEW→APPROVE quality gate loop with 6-dimension scoring (DAX correctness, M syntax, visual fidelity, schema integrity, lineage coverage, naming conventions) | 30 |
| `self_healing_v3.py` | Advanced self-healing — detects and auto-fixes broken DAX references, orphan measures, missing relationships, stale column refs, format string issues | 35 |
| `repair_strategies.py` | Pluggable repair tactics: column rename propagation, table alias resolution, expression rewrite, fallback measure injection | 25 |
| `self_healing_report.py` | JSONL audit trail of every auto-repair action with before/after snapshots | 15 |

### CLI Additions
```
--preceptor              # Enable quality gate loop (DRAFT→REVIEW→APPROVE)
--preceptor-strict       # Fail on any REVIEW score < 0.8
--self-heal              # Enable v3 self-healing (default: basic)
--repair-log FILE        # Write repair audit trail to FILE
```

### Pipeline Wiring
- Preceptor runs after QA pipeline, before rollback engine
- Self-healing v3 runs inside preceptor loop (up to 3 iterations)
- Repair strategies are registered via plugin hooks
- Self-healing report appends to recovery_report output

### Integration with Existing Modules
- `qa_pipeline.py` → feeds issues to preceptor scoring
- `dax_validator.py` → preceptor dimension: DAX correctness
- `m_validator.py` → preceptor dimension: M syntax
- `cross_validator.py` → preceptor dimension: schema integrity
- `rollback_engine.py` → preceptor verdict feeds rollback decision
- `feedback_loop.py` → unresolved preceptor issues auto-filed

### Deliverables
- [ ] `powerbi_import/preceptor.py` (~350 lines)
- [ ] `powerbi_import/self_healing_v3.py` (~300 lines)
- [ ] `powerbi_import/repair_strategies.py` (~250 lines)
- [ ] `powerbi_import/self_healing_report.py` (~150 lines)
- [ ] `tests/test_preceptor.py` (30 tests)
- [ ] `tests/test_self_healing_v3.py` (35 tests)
- [ ] `tests/test_repair_strategies.py` (25 tests)
- [ ] `tests/test_self_healing_report.py` (15 tests)
- [ ] CLI flags wired into `migrate.py`
- [ ] CHANGELOG entry

**Target:** ~2,710 tests, 74 modules

---

## Phase 2 — Enterprise Cutover & Full Lineage (v13.0.0)

**Goal:** Production cutover orchestration with parallel-run validation and comprehensive lineage.

| Module | Description | Estimated Tests |
|--------|-------------|-----------------|
| `cutover_manager.py` | Migration cutover lifecycle — wave scheduling, snapshot-based rollback, parallel-run validation, go/no-go checklist, UAT sign-off tracking | 40 |
| `full_lineage.py` | Comprehensive end-to-end lineage: Qlik data source → load script → table → field → measure → visual → report page. Mermaid + JSON + HTML output | 30 |

### CLI Additions
```
--cutover                # Enable cutover mode (snapshot before migration)
--cutover-wave N         # Run only wave N from migration plan
--parallel-run           # Keep both Qlik and PBI artifacts for comparison
--cutover-rollback       # Restore from last snapshot
--full-lineage           # Generate comprehensive lineage report
--lineage-format (json|html|mermaid)  # Lineage output format
```

### Pipeline Wiring
- Cutover manager wraps the entire migration pipeline
- Creates snapshot before extraction, validates after generation
- Parallel-run mode keeps Qlik JSON alongside PBI output for comparison
- Full lineage collects data from extraction → generation → validation
- Integrates with `dependency_graph.py` for cross-app lineage
- Integrates with `equivalence_tester.py` for parallel-run value comparison

### Deliverables
- [ ] `powerbi_import/cutover_manager.py` (~400 lines)
- [ ] `powerbi_import/full_lineage.py` (~350 lines)
- [ ] `tests/test_cutover_manager.py` (40 tests)
- [ ] `tests/test_full_lineage.py` (30 tests)
- [ ] CLI flags wired into `migrate.py`
- [ ] CHANGELOG entry

**Target:** ~2,780 tests, 76 modules

---

## Phase 3 — Report Export Suite (v14.0.0)

**Goal:** Professional migration deliverables — PDF, PPTX, and bundled packages.

| Module | Description | Estimated Tests |
|--------|-------------|-----------------|
| `pdf_renderer.py` | Print-optimized HTML → PDF via stdlib (`weasyprint` optional, fallback to browser print CSS). Includes migration summary, fidelity scores, visual mapping table, issue list | 20 |
| `pptx_report.py` | 5-slide executive summary: (1) Migration overview, (2) Fidelity scorecard, (3) Object mapping table, (4) Risk/issue summary, (5) Next steps. Uses `python-pptx` if available, falls back to XML generation | 20 |
| `report_packager.py` | ZIP bundler: HTML migration report + PDF + PPTX + lineage JSON + validation CSV + README. Single artifact for stakeholder distribution | 15 |

### CLI Additions
```
--pdf                    # Generate PDF migration report
--pptx                   # Generate PPTX executive summary
--report-package         # Generate ZIP bundle with all report formats
--report-title TITLE     # Custom report title
--report-author AUTHOR   # Custom author name
```

### Integration
- All three modules consume data from `migration_report.py` output
- PDF renderer reuses `html_template.py` CSS with print media queries
- Report packager includes outputs from lineage, QA, and validation steps
- Optional dependencies: `weasyprint`, `python-pptx` (graceful degradation)

### Deliverables
- [ ] `powerbi_import/pdf_renderer.py` (~250 lines)
- [ ] `powerbi_import/pptx_report.py` (~300 lines)
- [ ] `powerbi_import/report_packager.py` (~200 lines)
- [ ] `tests/test_pdf_renderer.py` (20 tests)
- [ ] `tests/test_pptx_report.py` (20 tests)
- [ ] `tests/test_report_packager.py` (15 tests)
- [ ] CLI flags wired into `migrate.py`
- [ ] CHANGELOG entry

**Target:** ~2,835 tests, 79 modules

---

## Phase 4 — Server Integration & PBI Goals (v15.0.0)

**Goal:** Deep Qlik Server migration + PBI Goals/Scorecard generation.

| Module | Description | Estimated Tests |
|--------|-------------|-----------------|
| `subscription_migrator.py` | Qlik Server task chains + distribution lists → PBI subscriptions + Power Automate flows. Handles reload triggers, email distribution, conditional alerts | 25 |
| `goals_generator.py` | Convert Qlik KPIs (master measures with targets/thresholds) → PBI Goals/Scorecard JSON. Supports status rules, sparklines, owner assignment | 20 |
| `automation.py` | Post-migration automation scripts: workspace permission sync, dataset refresh validation, report URL redirect map, user notification templates | 20 |

### CLI Additions
```
--migrate-subscriptions  # Convert Qlik tasks/alerts → PBI subscriptions
--goals                  # Generate PBI Goals from Qlik KPIs
--automation             # Generate post-migration automation scripts
--create-workspace NAME  # Create PBI workspace before deployment
--gateway-bind ID        # Bind datasets to on-premises gateway
```

### Integration
- `subscription_migrator.py` extends existing `subscription_generator.py`
- Goals generator reads from `measures.json` (master measures with targets)
- Automation scripts integrate with `deploy/` subpackage
- Gateway binding extends `gateway_config.py`

### Deliverables
- [ ] `powerbi_import/subscription_migrator.py` (~300 lines)
- [ ] `powerbi_import/goals_generator.py` (~250 lines)
- [ ] `powerbi_import/automation.py` (~200 lines)
- [ ] `tests/test_subscription_migrator.py` (25 tests)
- [ ] `tests/test_goals_generator.py` (20 tests)
- [ ] `tests/test_automation.py` (20 tests)
- [ ] CLI flags wired into `migrate.py`
- [ ] CHANGELOG entry

**Target:** ~2,900 tests, 82 modules

---

## Phase 5 — Test Coverage & Hardening (v15.1.0)

**Goal:** Close the test coverage gap and harden existing modules.

### Test Expansion Targets

| Area | Current | Target | New Tests |
|------|---------|--------|-----------|
| DAX converter edge cases | ~200 | 400 | +200 |
| Visual generator (120+ types) | ~150 | 300 | +150 |
| M query transforms (40+) | ~100 | 200 | +100 |
| TMDL generator | ~80 | 150 | +70 |
| Fabric generators | ~40 | 100 | +60 |
| Integration / E2E | ~30 | 80 | +50 |
| Deployment pipeline | ~20 | 60 | +40 |
| Merge engine | ~30 | 60 | +30 |
| Server extraction | ~20 | 50 | +30 |
| **Total new tests** | | | **+730** |

### Hardening
- [ ] Property-based tests for DAX/M validators (edge cases)
- [ ] Mutation testing pass with `mutmut` (target: 90%+ killed)
- [ ] Performance benchmarks for large apps (1000+ objects)
- [ ] Memory profiling for merge engine with 50+ apps
- [ ] Fuzz testing for QVF parser

### Deliverables
- [ ] 30+ new test files
- [ ] Mutation testing baseline
- [ ] Performance benchmark suite
- [ ] CI workflow update for coverage threshold bump (80% → 85%)

**Target:** ~3,630 tests, 82 modules

---

## Phase 6 — Qlik-Specific Lineage (v15.2.0)

**Goal:** Deep Qlik load script lineage — analogous to Tableau Prep lineage.

| Module | Description | Estimated Tests |
|--------|-------------|-----------------|
| `script_lineage.py` | Parse Qlik load script → directed graph of LOAD/STORE/DROP/RENAME/QUALIFY operations. Track field provenance from source → resident → final table | 30 |
| `script_lineage_report.py` | Interactive HTML report showing load script flow, field-level lineage, data transformations applied at each step | 20 |

### CLI Additions
```
--script-lineage         # Generate load script lineage analysis
--script-lineage-format (json|html|mermaid)
```

### Deliverables
- [ ] `powerbi_import/script_lineage.py` (~350 lines)
- [ ] `powerbi_import/script_lineage_report.py` (~250 lines)
- [ ] `tests/test_script_lineage.py` (30 tests)
- [ ] `tests/test_script_lineage_report.py` (20 tests)

**Target:** ~3,680 tests, 84 modules

---

## Release Timeline

| Version | Phase | Focus | New Modules | Cumulative Tests |
|---------|-------|-------|-------------|------------------|
| **v12.0.0** | 1 | Preceptor & Self-Healing | +4 | ~2,710 |
| **v13.0.0** | 2 | Cutover & Full Lineage | +2 | ~2,780 |
| **v14.0.0** | 3 | Report Export Suite | +3 | ~2,835 |
| **v15.0.0** | 4 | Server Integration & Goals | +3 | ~2,900 |
| **v15.1.0** | 5 | Test Hardening | +0 | ~3,630 |
| **v15.2.0** | 6 | Qlik Script Lineage | +2 | ~3,680 |

---

## Priority Order

```
P1  Preceptor + Self-Healing    ← biggest quality impact, blocks nothing
P2  Cutover + Full Lineage      ← enterprise requirement, uses P1 output
P3  Report Export Suite          ← stakeholder-facing, independent of P1/P2
P3  Server Integration + Goals  ← extends existing infrastructure
P4  Test Hardening              ← continuous, can run in parallel
P4  Qlik Script Lineage         ← Qlik-specific depth, independent
```

---

## Already at Parity ✓

These areas are at or ahead of TableauToPowerBI — no work needed:

- ✓ Visual type mappings (120+ vs 118+)
- ✓ M connectors (42 vs 33) — Qlik is **ahead**
- ✓ DAX conversions (175+ vs 180+) — near parity
- ✓ Fabric-native generation (all 5 generators)
- ✓ Multi-app merge engine (shared model + thin reports)
- ✓ DAX optimizer (AST-based rewriter)
- ✓ Quality validators (DAX, M, cross, schema, preflight)
- ✓ Rollback engine + migration planner
- ✓ Feedback loop + dependency graph
- ✓ Monitoring + alerting + SLA tracking
- ✓ Plugin system (7 hooks)
- ✓ REST API server
- ✓ Deployment pipeline (PBI Service + Fabric + multi-tenant)
