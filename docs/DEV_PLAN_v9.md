# DEV_PLAN v9.0 — Enterprise Features, Fabric-Native & Multi-App Merge

**Baseline:** v8.0.0 — 1,626 tests passing, 175+ DAX functions, 75+ visual types, 55 modules  
**Delivered:** v9.0.0 — 1,892 tests passing, AST-based DAX optimizer, Fabric-native generation, multi-app merge engine, enterprise governance & observability

---

## What Was Delivered in v9.0

### Phase 1 — DAX Intelligence (✅ Complete)

| Module | Status | Description |
|--------|--------|-------------|
| `dax_optimizer.py` | ✅ Ported & wired | AST-based DAX rewriter: IF→SWITCH, ISBLANK→COALESCE, constant folding, VAR extraction, SUMX simplification, Time Intelligence auto-generation, measure dependency DAG |
| `dax_recipes.py` | ✅ Ported | Industry-specific KPI templates (Healthcare, Finance, Retail) — 15+ pre-built measures per industry |
| `dax_query_generator.py` | ✅ Ported | DAX Studio validation query auto-generation for post-migration testing |
| `model_templates.py` | ✅ Ported | Pre-built star schema skeletons for common scenarios |
| `llm_client.py` | ✅ Ported | LLM-assisted DAX refinement (OpenAI/Anthropic) — optional, zero-dep |

**CLI integration:** DAX optimizer runs automatically after each successful generation in `migrate.py`.

### Phase 2 — Fabric-Native Generation (✅ Complete)

| Module | Status | Description |
|--------|--------|-------------|
| `fabric_constants.py` | ✅ Ported | Spark type maps, PySpark conversion maps, sanitization functions |
| `fabric_naming.py` | ✅ Ported | Artifact name sanitization for Lakehouse/Dataflow/Pipeline |
| `calc_column_utils.py` | ✅ Ported | Calculated column classification — Qlik→PySpark expression mapping |
| `lakehouse_generator.py` | ✅ Ported | Delta table schemas, Spark DDL, Lakehouse metadata |
| `dataflow_generator.py` | ✅ Ported | Power Query M ingestion for Dataflow Gen2 with Lakehouse destinations |
| `notebook_generator.py` | ✅ Ported | PySpark ETL notebooks (9 connector templates) |
| `pipeline_generator.py` | ✅ Ported | 3-stage Data Pipeline orchestrator (Dataflow → Notebook → Semantic Model) |
| `fabric_semantic_model_generator.py` | ✅ Ported | DirectLake semantic model pointing to Lakehouse tables |
| `fabric_project_generator.py` | ✅ Ported & wired | Fabric artifacts orchestrator — coordinates all Fabric generators |

**CLI integration:** `python migrate.py app.json --output-format fabric` routes to `FabricProjectGenerator`.

### Phase 3 — Multi-App Merge Engine (✅ Complete)

| Module | Status | Description |
|--------|--------|-------------|
| `shared_model.py` | ✅ Ported & wired | Fingerprint-based table matching, Jaccard column overlap scoring, deduplication |
| `thin_report_generator.py` | ✅ Ported | Thin reports with `byPath` references to shared semantic model |
| `merge_assessment.py` | ✅ Ported | Merge JSON report |
| `merge_config.py` | ✅ Ported | Per-table merge rules (save/load for reproducibility) |
| `merge_report_html.py` | ✅ Ported | Merge HTML dashboard |
| `global_assessment.py` | ✅ Ported | Cross-app merge cluster analysis |

**CLI integration:** `python migrate.py --merge app1.json app2.json app3.json`

### Phase 4 — Enterprise Governance & Validation (✅ Complete)

| Module | Status | Description |
|--------|--------|-------------|
| `governance.py` | ✅ Ported | PII detection, naming conventions, sensitivity labels, JSONL audit trail |
| `security_validator.py` | ✅ Ported | Path validation, ZIP slip defense, XXE protection |
| `equivalence_tester.py` | ✅ Ported | Cross-platform value comparison |
| `regression_suite.py` | ✅ Ported | Snapshot-based drift detection |
| `schema_drift.py` | ✅ Ported | Column/formula change detection (added/removed/renamed) |
| `visual_diff.py` | ✅ Ported | Side-by-side HTML comparison |
| `sla_tracker.py` | ✅ Ported | Per-app SLA compliance (max time, min fidelity) |

### Phase 5 — Portfolio Assessment & Observability (✅ Complete)

| Module | Status | Description |
|--------|--------|-------------|
| `server_assessment.py` | ✅ Ported & wired | RED/YELLOW/GREEN per app, complexity heatmap, effort estimation, wave planning |
| `monitoring.py` | ✅ Ported | Metrics export to Azure Monitor, Prometheus, JSON |
| `recovery_report.py` | ✅ Ported | Self-healing recovery tracking |
| `alerts_generator.py` | ✅ Ported | Threshold-based PBI data-driven alerts |

**CLI integration:** `python migrate.py --assess-server exports/`

### Phase 6 — Enterprise APIs & Deployment (✅ Complete)

| Module | Status | Description |
|--------|--------|-------------|
| `api_server.py` | ✅ Ported | REST API server (stdlib, zero deps) |
| `notebook_api.py` | ✅ Ported | Jupyter interactive migration API |
| `paginated_generator.py` | ✅ Ported | RDL-style paginated report generator |
| `permission_mapper.py` | ✅ Ported | RLS permission PowerShell script generator |
| `marketplace.py` | ✅ Ported | Versioned pattern registry |
| `deploy/bundle_deployer.py` | ✅ Ported | Bundle deployer (shared model + thin reports) |
| `deploy/multi_tenant.py` | ✅ Ported | Multi-tenant deployment with template substitution |
| `deploy/pbi_client.py` | ✅ Ported | Power BI Service REST API client |
| `deploy/pbi_deployer.py` | ✅ Ported | Blue/green deployment, refresh scheduling |

### Phase 7 — Visual Generator Enrichment (✅ Complete)

14 new visual types added to `VISUAL_TYPE_MAP`:
- sankey, chord, sunburst, decompositionTree, shapeMap, narrative, influenceAnalysis, anomalyDetection, smartNarrative, paginated, embedded, rVisualization, pythonVisualization, aiInsight

9 new custom visual GUIDs in `CUSTOM_VISUAL_GUIDS`:
- sankey, chord, sunburst, infographic, pulse, horizon, timeline, radarChart, aster

16-entry `QLIK_EXTENSION_MAP` for Qlik extension → Power BI visual resolution.

Auto-generated measures system (`_add_auto_measure`, `get_auto_generated_measures`, `clear_auto_generated_measures`).

### Phase 8 — Infrastructure (✅ Complete)

| Asset | Status | Description |
|-------|--------|-------------|
| 9 agent definitions | ✅ Created | `.github/agents/` — Assessor, Converter, Deployer, Extractor, Generator, Merger, Orchestrator, Tester, shared |
| 5 CI workflows | ✅ Created | `.github/workflows/` — ci, deploy, gh-pages, pr-diff, publish |
| Dockerfile | ✅ Created | Production container for REST API server (python:3.12-slim) |
| web/app.py | ✅ Created | Streamlit 6-step migration wizard |
| scripts/ | ✅ Created | 5 utility scripts (M syntax check, version bump, etc.) |
| examples/ | ✅ Expanded | marketplace/, plugins/ directories |
| Config files | ✅ Created | .coveragerc, pyrightconfig.json, setup.cfg, config.example.json, CONTRIBUTING.md |

### Phase 9 — Test Coverage (✅ Complete)

12 new test files, 266 new tests:

| Test File | Tests | Focus |
|-----------|-------|-------|
| `test_dax_optimizer.py` | 37 | AST-based DAX rewriting (IF→SWITCH, COALESCE, constant folding, VAR, time intelligence, DAG) |
| `test_dax_recipes.py` | 17 | Industry KPI templates (Healthcare, Finance, Retail) |
| `test_model_templates.py` | 12 | Star schema skeletons (retail, healthcare, finance, SaaS) |
| `test_governance.py` | 26 | PII detection, naming conventions, sensitivity labels, audit trail |
| `test_security_validator.py` | 26 | Path traversal, ZIP slip, XXE, sanitization |
| `test_schema_drift.py` | 13 | Column change detection (added/removed/renamed/type changes) |
| `test_monitoring.py` | 10 | Azure Monitor, Prometheus, JSON metrics export |
| `test_sla_tracker.py` | 12 | Per-app SLA compliance, violations, timing |
| `test_fabric_native.py` | 33 | Lakehouse, Dataflow, Notebook, Pipeline, DirectLake, FabricProject |
| `test_shared_model.py` | 18 | Fingerprint matching, merge, thin reports, config persistence |
| `test_v9_cli_features.py` | 24 | --output-format fabric, --merge, --assess-server CLI flags |
| `test_v9_visual_types.py` | 38 | 14 new visual types, 9 GUIDs, extension map, auto-measures |

---

## v9.0.0 Final Stats

| Metric | v8.0.0 | v9.0.0 |
|--------|--------|--------|
| Tests | 1,626 | 1,892 |
| Test files | 29 | 41 |
| powerbi_import modules | 20 | 55 |
| Visual types | 60+ | 75+ |
| Custom visual GUIDs | 9 | 18 |
| CLI flags | 10 | 13 (+fabric, +merge, +assess-server) |
| Agent definitions | 0 | 9 |
| CI workflows | 2 | 5 |
| Sample migrations | 5/5 at 100% | 5/5 at 100% |

---

## v9.1 Roadmap (Next)

### Priority 1 — DAX Stub Completion
13 functions still return `/* manual */` or passthrough. Implement or formally document as unsupported:

| Function | Action |
|----------|--------|
| `Correl` | Implement via SUMX/AVERAGEX Pearson formula |
| `BitCount` | Implement via MOD/DIVIDE bit-counting |
| `Skew` | Document as unsupported |
| `NetWorkDays` | Fix `{0}/{1}` arg substitution |
| `KeepChar` | Implement nested SUBSTITUTE |
| `SubField` | Map to PATHITEM |
| `Hash128/160/256` | Document as unsupported |
| `Evaluate` | Document as unsupported (dynamic eval) |
| `MapSubstring` | Complete multi-map SUBSTITUTE chain |
| `Atan2` | Implement 4-quadrant via IF/PI |
| `Interval` | Map to FORMAT with HH:MM:SS |

### Priority 2 — Qlik-specific Assessment Overhaul
`assessment.py` still contains some Tableau-inherited patterns. Replace with:
- Set Analysis complexity scoring
- Aggr nesting depth analysis
- Section Access completeness checks
- Variable chain depth analysis
- Stacked LOAD pattern detection

### Priority 3 — Visual Report Fidelity
- Drillthrough pages from Qlik drill-to sheet actions
- Tooltip pages from custom tooltip objects
- Conditional formatting icon sets (traffic lights, flags, arrows)
- Background images from sheet/object metadata
- Dynamic zone visibility → bookmark toggle groups

### Priority 4 — Load Script Converter Enhancement
`qlik_script_converter.py` handles 30 statement types — expand to:
- `MAPPING LOAD` → Power Query lookup tables
- `APPLYMAP` → Table.Join or List.PositionOf
- `CROSSTABLE` → Table.UnpivotOtherColumns
- `GENERIC LOAD` → Table.Pivot
- `HIERARCHY` / `HIERARCHYBELONGSTO` → parent-child rewrite
- `INTERVALMATCH` → Table.AddFuzzyClusterColumn or range join

### Priority 5 — Integration Testing
- End-to-end Fabric generation test with real Qlik app
- Multi-app merge test with overlapping tables
- Bundle deployment dry-run test
- SLA tracker integration with CI

### Priority 6 — Documentation
- Enterprise migration guide (8-phase playbook)
- Known limitations document
- Architecture decision records (ADRs)
- Update GAP_ANALYSIS.md with v9 closures

---

## Success Metrics

| Metric | v9.0.0 | v9.1.0 Target |
|--------|--------|---------------|
| Tests | 1,892 | 2,100+ |
| DAX stubs remaining | 13 | ≤ 3 (unsupported-only) |
| Assessment Qlik-native | Partial | 100% |
| Load script coverage | 30 statements | 36+ statements |
| Sample migrations | 5 | 8+ (incl. Fabric output) |
| E2E integration tests | 0 | 5+ |
