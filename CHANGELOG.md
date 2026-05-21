# Changelog

## v12.0.0 — Preceptorship, Self-Healing & Reporting

### New Modules (14)

#### Phase 1: Preceptorship & Self-Healing
- **`preceptor.py`** — Preceptorship loop engine (6-dimension quality review, APPROVED/COACHING/ESCALATED scoring)
- **`self_healing_v3.py`** — 11 model healers (duplicate measures, self-refs, sort-by-column, hierarchies, relationships, datatypes)
- **`repair_strategies.py`** — Registry of deterministic repair strategies (Qlik leak cleanup, paren balancing, M if/else)
- **`self_healing_report.py`** — JSONL audit trail of all auto-repair actions

#### Phase 2: Cutover & Lineage
- **`cutover_manager.py`** — Migration cutover orchestration (readiness checks, runbook generation)
- **`full_lineage.py`** — End-to-end provenance tracking (Qlik field → M query → DAX → TMDL → visual)

#### Phase 3: Reporting & Packaging
- **`pdf_renderer.py`** — Migration summary PDF (weasyprint) or HTML fallback
- **`pptx_report.py`** — PowerPoint executive summary (python-pptx) or Markdown fallback
- **`report_packager.py`** — ZIP bundle with all migration artifacts + manifest.json

#### Phase 4: Goals & Automation
- **`goals_generator.py`** — Qlik KPIs → Power BI Goals/Metrics JSON
- **`automation.py`** — Batch migration orchestration for multiple apps with HTML summary

#### Phase 6: Script Lineage
- **`script_lineage.py`** — Qlik load script parser → lineage graph (LOAD/FROM/RESIDENT/JOIN/MAPPING)
- **`script_lineage_report.py`** — HTML visualization with Mermaid diagrams + JSON export

### New CLI Flags (10)
- `--preceptor-review` — Run preceptorship quality review loop
- `--self-heal-v3` — Run v3 model healers (11 checks)
- `--repair-strategies` — Run deterministic repair strategies
- `--cutover-plan` — Generate migration cutover runbook
- `--full-lineage` — End-to-end provenance lineage map
- `--pdf-report` — PDF migration summary report
- `--pptx-report` — PowerPoint executive summary
- `--package` — ZIP bundle of all migration artifacts
- `--goals` — Extract Qlik KPIs → PBI Goals/Metrics
- `--script-lineage` — Qlik load script lineage report

### Pipeline Wiring
- Self-healing v3 runs after QA pipeline (fixes model-level issues)
- Repair strategies run on DAX/M expressions after QA
- Preceptor review runs post-repair as final quality gate
- Full lineage, cutover, goals, script lineage run after generation
- PDF/PPTX/package run as final reporting step

### Stats
- **~2,900 tests** across 86 test files (was 2,605 across 73)
- **84 powerbi_import modules** (was 70)
- **~101 CLI flags** (was ~91)

## v11.0.0 — Quality Gates, Planning & Feedback (TableauToPowerBI sync)

### New Modules (11)
- **`dax_validator.py`** — Lightweight DAX expression validator (balanced delimiters, Qlik function leak detection)
- **`m_validator.py`** — Power Query M syntax validator (balanced parens/brackets, let/in matching)
- **`cross_validator.py`** — TMDL model ↔ PBIR report cross-validation (orphan measures, missing columns)
- **`preflight.py`** — Pre-migration rejection gate (file existence, format, size, corruption checks)
- **`connection_rewriter.py`** — Connection string intelligence (parsing, env-based rewriting, gateway scripts)
- **`rollback_engine.py`** — Severity-based quality gate (ship/quarantine/rollback decisions)
- **`schema_validator.py`** — PBIR v4.0 JSON structural validator with auto-repair
- **`migration_planner.py`** — Enterprise planning (effort estimation, wave assignment, workspace mapping)
- **`feedback_loop.py`** — Issue reporting and regression fixture generation
- **`dependency_graph.py`** — Data-lineage and cross-app dependency analysis with cycle/orphan detection
- **`subscription_generator.py`** — Qlik alert/notification → Power BI subscription migration

### New CLI Flags (7)
- `--preflight` / `--force` — Pre-migration validation gate
- `--connection-map FILE` — Connection string rewriting rules
- `--strict` — Strict mode (rollback on any error)
- `--cross-validate` — TMDL ↔ PBIR cross-validation
- `--schema-validate` — PBIR JSON schema validation
- `--report-issue DESC` — File a feedback issue from CLI

### Pipeline Wiring
- Preflight runs before extraction (rejects unsupported/corrupt inputs)
- Schema/cross-validate/rollback/connection-rewrite run after QA pipeline
- All new modules integrated into `migrate.py` execution flow

### Stats
- **2,605 tests** across 73 test files (was 2,427 across 62)
- **70 powerbi_import modules** (was 59)

## v10.1.0 — Gap Closure & Pipeline Wiring

### REST API Server Fix
- **Fixed broken `api_server.py`**: rewrote `_run_migration()` to use actual Qlik extraction pipeline (`ExtractionOrchestrator` + `PowerBIImporter`) instead of non-existent `Qlik_export.extract_Qlik_data`
- **Updated file extensions**: `.qvf`/`.json` accepted (was `.twb`/`.twbx`/`.tds`/`.tdsx`)
- **Fixed all Tableau references**: docstrings, default filenames, server help text
- **Fixed stale Tableau references** in `notebook_api.py` and `deploy/multi_tenant.py`
- **16 new tests** for api_server (imports, multipart parsing, rate limiting, job management)

### Bridge Table Improvements
- **Composite key support**: M2M relationships between the same table pair with multiple columns are now merged into a single bridge table with all column pairs
- **Synthetic key detection**: Qlik `$Syn*` tables are automatically flagged as manyToMany candidates in both `_inject_relationships()` and `_detect_many_to_many()`
- **Bridge table validation**: Post-generation validation checks balanced parentheses, referenced table existence, relationship connectivity, and minimum column count
- **Table pair grouping**: Bridge tables now group by alphabetically-sorted table pairs for deterministic naming

### Visual Mapping Expansion
- Expanded `VISUAL_TYPE_MAP` from 75 to **120+ entries** (parity with TableauToPowerBI)
  - Bar/column (12), line/area (10), combo (9), pie/donut (5), map (10), KPI/card/gauge (15), table/matrix (10), specialty (30+)
- Expanded `APPROXIMATION_MAP` from 12 to **27+ entries** with migration notes
- Expanded `_QLIK_CHART_TYPE_MAP` in format_adapter with **25+ new Qlik-specific types**

### Power Query File Generation
- New `_write_power_query_files()` in `tmdl_generator.py`
- Writes each table's M query as `.pq` files in `definition/expressions/`
- Integrated as step 10 in the TMDL pipeline

### New Modules
- **`geo_passthrough.py`**: GeoJSON/shapefile passthrough for Power BI shape maps
  - `detect_geo_sources()`, `copy_geo_resources()`, `build_shape_map_config()`, `extract_geo_properties()`
  - Auto-wired into `PowerBIProjectGenerator.generate_project()` — inline GeoJSON detected and written to `RegisteredResources/`
- **`refresh_generator.py`**: Qlik reload tasks → PBI refresh schedules
  - `parse_qlik_tasks()`, `generate_refresh_schedule()`, `generate_refresh_powershell()`, `write_refresh_config()`
  - Wired into `migrate.py` post-generation pipeline (`--refresh-schedule` flag)
- **`qlik_server_client.py`**: Qlik Sense Enterprise/Cloud REST API client
  - Supports QSEoW (certificates), Cloud (API key/JWT), auto-detection
  - `list_apps()`, `get_app()`, `get_app_objects()`, `get_app_script()`, `get_reload_tasks()`, `extract_app_for_migration()`
  - Wired into `migrate.py` as `--server-url` extraction mode

### New CLI Flags
- **`--server-url URL`**: Direct extraction from Qlik Sense server
- **`--server-api-key KEY`**: API key for Qlik Cloud auth
- **`--server-cert PATH`**: Client certificate for QSEoW auth
- **`--server-app-id ID`**: App ID to extract from server
- **`--refresh-schedule`**: Generate PBI refresh schedule from Qlik reload tasks
- **`--refresh-timezone TZ`**: Timezone for refresh schedule (default: UTC)

### Tests
- **20 new tests**: geo wiring (3), CLI flags (6), refresh wiring (2), server wiring (3), plus 6 flag tests in existing test file
- Total test count: **2,454** (up from 2,407)

---

## v10.0.0 — Full Parity with TableauToPowerBI

### New CLI Flags (~60 new flags)
- **`--qa`**: Full QA pipeline (validate → auto-fix → governance → comparison → qa_report.json)
- **`--governance`**: Run governance checks (naming conventions, PII detection)
- **`--compare` / `--no-compare`**: Generate comparison report after migration
- **`--dashboard`**: Generate telemetry dashboard HTML
- **`--optimize-dax`**: Enable DAX optimizer pass
- **`--time-intelligence`**: Auto-inject time intelligence measures
- **`--monitor`**: Export metrics (json/prometheus/azure)
- **`--deploy WORKSPACE`**: Deploy to Power BI Service
- **`--deploy-refresh`**: Trigger dataset refresh after deploy
- **`--deploy-bundle`**: Bundle deployment (shared model + thin reports)
- **`--shared-model FILE [FILE ...]`**: Build shared semantic model from multiple apps
- **`--model-name`**: Name for the shared semantic model
- **`--assess-merge`**: Merge assessment only (preview mode)
- **`--merge-preview`**: Preview merge without generating
- **`--save-merge-config` / `--merge-config`**: Save/load merge decisions
- **`--global-assess`**: Cross-app merge cluster analysis
- **`--check-drift PATH`**: Schema drift detection
- **`--sla-config`**: SLA compliance tracking
- **`--llm-refine`**: LLM-assisted DAX refinement
- **`--llm-provider` / `--llm-model` / `--llm-key` / `--llm-endpoint`**: LLM configuration
- **`--llm-max-calls` / `--llm-dry-run`**: LLM limits and preview mode
- **`--workers` / `--parallel`**: Parallel batch migration
- **`--resume`**: Resume from checkpoint
- **`--jsonl-log`**: Structured JSONL logging
- **`--web-ui` / `--web-port`**: Launch Streamlit migration wizard
- **`--endorse`**: Endorsement level during deploy
- **`--manifest`**: Generate artifact manifest
- **`--validate-data`**: Cross-platform equivalence testing
- **`--sync`**: Auto-deploy after generation
- **`--multi-tenant`**: Multi-tenant template substitution
- **`--rolling`**: Rolling calendar window
- **`--consolidate`**: Consolidate duplicate columns
- **`--skip-conversion`**: Skip DAX conversion pass
- **`--languages`**: Multi-culture TMDL generation

### New Modules
- **`powerbi_import/lineage_map.py`**: Source-to-target provenance tracking (lineage_map.json)
  - Tracks: datasource→table, measure→DAX, dimension→column/hierarchy, variable→parameter, visualization→visual, sheet→page, association→relationship, bookmark→PBI bookmark
- **`powerbi_import/qa_pipeline.py`**: Full QA pipeline (validate → auto-fix → governance → compare)
  - 17 Qlik→DAX leak auto-fix patterns (IsNull→ISBLANK, Null→BLANK, Alt→COALESCE, OSUser→USERPRINCIPALNAME, etc.)

### Data Connectors — 25 → 42
17 new M query generators: OData, Google Analytics, Azure Blob, Vertica, Impala, Hadoop Hive, Presto, Fabric Lakehouse, Dataverse, MongoDB, Cosmos DB, Athena, DB2, GeoJSON/Shapefile, SAP BW, Custom SQL (with aliases)

### Handler Wiring
- Lineage map automatically generated after migration
- LLM refinement pass after DAX optimization
- Governance audit integrated into post-generation pipeline
- Comparison report auto-generated
- QA pipeline runs validate → auto-fix → governance → compare
- Deploy to Power BI Service with refresh and endorsement
- Manifest generation with artifact inventory
- Global assessment for cross-app merge analysis
- Schema drift detection mode
- Shared model mode with merge config, thin reports, and bundle deploy
- Monitoring metrics export (JSON/Prometheus/Azure Monitor)
- Data validation via equivalence testing

### Tests
- **122 new tests** across 4 new test files:
  - `test_lineage_map.py` (30 tests): LineageEntry, LineageMap, build_lineage_map
  - `test_qa_pipeline.py` (17 tests): Auto-fix patterns, full QA pipeline
  - `test_new_connectors.py` (36 tests): All 17 new connectors + aliases + existing
  - `test_new_cli_flags.py` (39 tests): CLI flag definitions, _build_calc_map_from_tmdl
- Total test count: **2,213** (up from 2,091)

## v9.1.0 — Preceptorship Multi-Agent Model & v9.1 Roadmap Delivery

### Multi-Agent Architecture
- **Preceptor agent**: New quality guardian agent that reviews work across all specialists, enforces standards, catches pitfalls, validates cross-agent consistency
- **Preceptorship workflow**: All specialist agents now follow a structured **Plan → Assign → Implement → Review** cycle
- **Tech Lead role**: Orchestrator formalized as Tech Lead — architectural decisions, task decomposition, cross-agent coordination
- **Escalation paths**: Each specialist knows when to escalate to Preceptor (quality) vs Orchestrator (architecture)
- **Self-review checklist**: Standardized review criteria embedded in every agent definition
- **10 agent definitions**: Orchestrator (Tech Lead), Preceptor, Extractor, Converter, Generator, Assessor, Merger, Deployer, Tester, plus shared instructions

### DAX Stub Completion (P1)
- **KeepChar**: Improved from `UNSUPPORTED` to approximate SUBSTITUTE chain stripping common non-alphanumeric characters
- **MapSubstring**: Improved annotation — now "maps substrings via lookup — chain SUBSTITUTE per mapping entry"
- All 8 other stubs already implemented: Correl (Pearson), BitCount (8-bit MOD), Atan2 (4-quadrant), Interval (FORMAT), SubField (PATHITEM), NetWorkDays (DATEDIFF)
- 4 functions remain formally unsupported: Skew, Hash128, Hash160, Hash256, Evaluate

### Dynamic Zone Visibility (P3)
- `visual_generator.py`: Worksheets with `dynamicZone` metadata now emit `conditionalVisibility` and `_dynamicZoneMeta` on the visual container
- `pbip_generator.py`: New `_create_dynamic_zone_bookmarks()` method generates bookmark entries with `targetVisualType: "toggleVisibility"` wired into `report.json`

### Integration Testing (P5)
- **91 new tests** in `test_v91_features.py` covering DAX stubs, assessment Qlik-native checks, dynamic zones, drillthrough, icon sets, background images, script converter, E2E pipeline, Fabric modules, merge modules, SLA, governance
- Total test count: **2,091** (up from 2,000)

### Test Fixes
- Updated pre-existing test assertions in `test_dax_stub_fixes.py` and `test_dax_stubs_v91.py` to match improved KeepChar/MapSubstring output

## v9.0.0 — Enterprise Features (ported from TableauToPowerBI)

### New Modules — 35 modules ported from TableauToPowerBI

#### DAX Intelligence (4 modules)
- **dax_optimizer.py**: AST-based DAX rewriter (IF→SWITCH, COALESCE, constant folding, VAR extraction)
- **dax_recipes.py**: Industry KPI templates (Healthcare, Finance, Retail)
- **dax_query_generator.py**: DAX Studio validation query auto-generation
- **model_templates.py**: Pre-built star schema model skeletons

#### Fabric-Native Generation (9 modules)
- **fabric_constants.py**, **fabric_naming.py**: Spark type maps, naming sanitization
- **lakehouse_generator.py**: Delta table schemas & DDL
- **dataflow_generator.py**: Power Query M for Dataflow Gen2
- **notebook_generator.py**: PySpark ETL notebooks (9 connector templates)
- **pipeline_generator.py**: 3-stage Fabric Data Pipeline
- **fabric_semantic_model_generator.py**: DirectLake semantic model
- **fabric_project_generator.py**: Fabric artifacts orchestrator
- **calc_column_utils.py**: Calculated column classification

#### Multi-App Merge Engine (6 modules)
- **shared_model.py**: Fingerprint-based table matching & deduplication
- **thin_report_generator.py**: Thin reports with shared semantic model
- **merge_assessment.py**, **merge_config.py**, **merge_report_html.py**, **global_assessment.py**

#### Enterprise Governance & Validation (6 modules)
- **governance.py**: PII detection, naming conventions, audit trail (JSONL)
- **security_validator.py**: Path/ZIP slip/XXE protection
- **equivalence_tester.py**: Cross-platform value comparison
- **regression_suite.py**: Snapshot-based drift detection
- **schema_drift.py**: Column/formula change detection
- **visual_diff.py**: Side-by-side HTML comparison

#### Enterprise APIs & Services (3 modules)
- **api_server.py**: REST API server (stdlib, zero deps)
- **notebook_api.py**: Jupyter interactive migration API
- **paginated_generator.py**: RDL-style paginated reports

#### Observability & SLA (4 modules)
- **monitoring.py**: Metrics export (Azure Monitor, Prometheus, JSON)
- **alerts_generator.py**: Threshold-based PBI data-driven alerts
- **recovery_report.py**: Self-healing recovery tracking
- **sla_tracker.py**: Per-app SLA compliance

#### Advanced Features (3 modules)
- **llm_client.py**: LLM-assisted DAX refinement (OpenAI/Anthropic)
- **marketplace.py**: Versioned pattern registry
- **permission_mapper.py**: RLS PowerShell script generator

### Portfolio Assessment
- **server_assessment.py**: Server-level RED/YELLOW/GREEN per app, complexity heatmap, wave planning

### Enhanced Deployment (4 new deploy modules)
- **bundle_deployer.py**: Shared model + thin reports atomic deployment
- **multi_tenant.py**: Multi-tenant template substitution
- **pbi_client.py**: Power BI Service REST API
- **pbi_deployer.py**: Blue/green deployment, refresh scheduling

### Visual Generator Enrichment
- Added 14 new visual type mappings (azureMap, violin, parallel coordinates, calendar heatmap, etc.)
- Added 9 new custom visual GUIDs (Violin, Parallel Coords, Calendar, OrgChart, Timeline, Radar, Dendrogram, Sunburst)
- Added auto-generated measures system for dynamic measure creation
- Added Qlik extension visual mapping (QLIK_EXTENSION_MAP — 16 extensions)

### Infrastructure
- 9 Copilot agent definitions (.github/agents/)
- 3 additional CI workflows (gh-pages, pr-diff, publish)
- Streamlit migration wizard (web/app.py)
- 5 utility scripts (scripts/)
- Root configs: Dockerfile, .coveragerc, pyrightconfig.json, setup.cfg, config.example.json, CONTRIBUTING.md
- Example marketplace patterns and plugin samples

### Stats
- **55 powerbi_import modules** (was 20 in v8)
- **1626 tests** all passing
- **75+ visual types** (was 60+)
- **9 agent definitions** for multi-agent Copilot workflows
- **5 CI workflows**

---

## v8.0.0 — Polish, Extensibility & Production Readiness

### Phase 1 — Critical Fixes (+98 tests)

- **DAX stub coverage**: Added 25+ DAX function stubs for previously unmapped Qlik functions
- **Test cleanup**: Removed stale Tableau-related test references, standardized test fixtures

### Phase 2 — Test Coverage Expansion (+430 tests)

- **test_edge_cases.py**: Comprehensive edge case coverage — empty inputs, malformed data, boundary conditions
- **test_pipeline_scenarios.py**: End-to-end pipeline scenarios with varied input combinations
- **test_migration_validation.py**: Post-migration artifact validation tests
- **test_medium_integration.py**: Medium-complexity integration tests bridging unit ↔ E2E

### Phase 3 — Visual & Reporting Enhancements (+34 tests)

- **Navigation actions**: Button/sheet-level actions extracted from Qlik → Power BI navigation
- **Viz-in-tooltip**: Tooltip visualization references extracted and preserved
- **Alternate states**: Qlik alternate selection states (`qStateName`) extraction
- **Icon set conditional formatting**: 4 presets (arrows, flags, stars, circles) in visual config
- **Background images**: Sheet background images extracted and applied to report pages
- **Bookmarks**: Bookmark filter state wired into report.json generation

### Phase 4 — Plugin System & Pipeline (+24 tests)

- **PluginManager wiring**: 4 hook points in `migrate.py` — `pre_extraction`, `post_extraction`, `pre_generation`, `post_generation`
- **`--json` flag**: Structured JSON output for CI/CD — status, tables, measures, visuals, pages, warnings, duration
- **`--plugins` flag**: Runtime plugin loading from module paths (`module.ClassName`)
- **Progress callbacks**: `MigrationProgress` wired into extraction + generation with CLI progress bar

### Phase 5 — Documentation Overhaul (+9 tests)

- **English guides**: `QUICK_START.md`, `MIGRATION_GUIDE.md`, `DEPLOYMENT_GUIDE.md`, `PLUGIN_DEVELOPMENT.md`
- **API Reference**: `docs/API_REFERENCE.md` — public API for dax_converter, pbip_generator, import_to_powerbi, plugins, progress
- **README update**: v8.0.0 version, 1610→1619 test count, `--json`/`--plugins` examples, new doc links
- **copilot-instructions update**: v8.0.0 stats, plugin/JSON features
- **FAQ update**: v8 plugin & CI/CD Q&A section

### Phase 6 — Housekeeping & Release

- **Dead code audit**: Documented `src/fabric_api/` shim status, added deprecation README
- **CI/CD enhancements**: pytest-cov coverage reporting, ruff linter (replaces pylint), `--json` validation job, coverage artifact upload
- **Version bump**: All `__version__` strings → `8.0.0`
- **CHANGELOG update**: This entry

### Stats

- Tests: 949 → 1619+ (+670)
- New test files: 6 (test_phase4_plugin_pipeline.py, plus expanded test_documentation.py, test_edge_cases.py, test_pipeline_scenarios.py, test_migration_validation.py, test_medium_integration.py)
- 4 new English documentation guides + API reference
- Plugin system with 7 hook points
- CI/CD: coverage reporting, ruff linting, JSON output validation

---

## v7.0.0 — DAX Deep Accuracy & Full Test Coverage

### Phase 1 — DAX Accuracy Deepening (38 tests)

- **Aggr() decomposition**: `Aggr(Sum(X), Dim)` → `SUMX(VALUES('T'[Dim]), X)` using iterator pattern (SUMX, COUNTX, AVERAGEX, MINX, MAXX); multi-dim or unrecognized inner function falls back to ADDCOLUMNS/SUMMARIZE
- **Inter-record OFFSET**: `Previous(X)` → `OFFSET(-1, ALLSELECTED(...))`, `Above(X, n)` / `Below(X, n)` → `OFFSET(±n, ...)`, `Peek(X, offset)` → `OFFSET(offset, ...)`
- **RangeSum running total**: `RangeSum(Above(X, 0, RowNo()))` → `CALCULATE(SUM(...), WINDOW(-INF, 0, ALLSELECTED(...)))`
- **P()/E() set analysis**: `P({1} Field)` → `ALL('T'[Field])`, `E({1} Field)` → `EXCEPT(ALL('T'[Field]), VALUES('T'[Field]))`
- **Dollar-sign expressions**: `$(=Year(Today())-1)` → `YEAR(TODAY()) - 1` with Qlik→DAX function conversion

### Phase 2 — Critical Test Coverage (+133 tests)

- **`test_pbip_generator.py`** (28 tests): Project structure, TMDL output, report generation, edge cases for `PowerBIProjectGenerator`
- **`test_visual_generator.py`** (74 tests): 60+ visual type mappings, custom visuals, config templates, containers, batch generation, sparklines, small multiples, proportional layout
- **`test_tmdl_canonical.py`** (31 tests): `generate_tmdl()` entry point, `_build_semantic_model`, relationships, hierarchies, RLS roles, calendar tables, edge cases

### Phase 3 — Pipeline Wiring

- **Paginated passthrough**: `import_all(paginated=True)` flows through to `generate_powerbi_project()`
- **Post-generation validation**: `import_all(validate=True)` runs `ArtifactValidator.validate_project()` after project creation
- **Return path**: `generate_powerbi_project()` now returns the project output path

### Phase 4 — Section Access Enhancements (22 tests)

- **Wildcard `*` → TRUE()**: Section Access `USERID = *` now generates `RLS_AllUsers` role with `TRUE()` filter (previously skipped)
- **OMIT column parsing**: `OMIT` header in SECTION ACCESS LOAD INLINE → `omit_fields` list per role; annotated as Object-Level Security (OLS) migration note
- **REDUCTION column parsing**: `REDUCTION` header → `reduce_values` list per role
- **Pre-built filter passthrough**: `_create_rls_roles()` accepts `filter_expression` directly from `_parse_section_access()` for streamlined pipeline

### Phase 5 — Legacy Deprecation

- **TMDLGenerator class**: Added runtime `DeprecationWarning` on instantiation (points to `powerbi_import.tmdl_generator` + `powerbi_import.pbip_generator`)
- **`create_pbi_project_from_migration()`**: Added runtime `DeprecationWarning` (points to `powerbi_import.import_to_powerbi.import_all()`)

### Phase 6 — CI/CD & Housekeeping

- **GitHub Actions CI**: `.github/workflows/ci.yml` — pytest + lint on push/PR
- **Version bump**: All `__version__` strings updated to `7.0.0`
- **CHANGELOG update**: This entry

### Stats

- Tests: 756 → 949 (+193)
- New test files: `test_v7_phase1.py` (38), `test_pbip_generator.py` (28), `test_visual_generator.py` (74), `test_tmdl_canonical.py` (31), `test_v7_phase4.py` (22)
- Key files modified: `dax_converter.py`, `format_adapter.py`, `tmdl_generator.py`, `import_to_powerbi.py`, `src/fabric_api/tmdl_generator.py`, `src/fabric_api/__init__.py`

---

## v6.0.0 — Make It Actually Work End-to-End

### Phase 1 — Pipeline Blockers (29 tests)

- Removed 20-visual-per-page cap in `visual_generator.py`
- Removed 10-field cap for table/matrix projections in `pbip_generator.py`
- Wired `qlik_script_converter.py` into extraction pipeline with load script → datasource enrichment
- Fixed table name extraction for labeled LOAD statements
- Created `docs/DEV_PLAN_v6.md` — 6-phase plan

### Phase 2 — DAX Accuracy (44 tests)

- **Variable expansion**: `$(=expression)` with bracket matching via `_expand_dollar_expr()`
- **Sum(If) pattern**: `Sum(If(cond, val))` → `CALCULATE(SUM(...), filter)` / `SUMX(FILTER(...))`
- **Concat()**: `Concat(field, sep)` → `CONCATENATEX(VALUES(...), ..., sep)`
- **Aggr() rewrite**: Proper bracket matching for nested expressions via `_split_top_level_args()`
- **Set Analysis extended**: Bracket matching for `{<Year={2024}>}`, `{1<...>}` ALL, `{$<...>}` current, subtraction/union operators

### Phase 3 — Integrate Standalone Tools (13 tests)

- **Theme injection**: Qlik theme colors from `app_metadata` → `theme_colors` in dashboards
- **Variable promotion**: Variables containing aggregation expressions promoted from parameters to calculations
- **Section Access → RLS**: `_parse_section_access()` parses SECTION ACCESS blocks into RLS `user_filters`
- **DAX converter consolidation**: `qlik_migrator.py` and `qlik_model_converter.py` now delegate to canonical `dax_converter.py`

### Phase 4 — Visual Report Fidelity (21 tests)

- **Visual filters**: Explicit filters + topN from dimension `qOtherLimit`
- **Sort orders**: Explicit `sort` property + inferred from `qSortCriterias`
- **Slicer config**: Dropdown/list mode, single select, search, date range detection
- **Bookmark state**: Selections/filters from `bm.selections` + `captured_sheet`

### Phase 5 — Load Script Deep Conversion (22 tests)

- **JOIN → Table.NestedJoin**: `LEFT/INNER/RIGHT/OUTER JOIN(Table)` mapped to `Table.NestedJoin()` with correct JoinKind
- **CONCATENATE → Table.Combine**: `CONCATENATE(Table)` produces `Table.Combine()` annotations
- **Stacked LOAD detection**: Two-LOAD-before-FROM pattern recognized and annotated
- **parse_qlik_load prefix stripping**: CONCATENATE/JOIN prefixes stripped before LOAD parsing
- **Split regex updated**: Statement splitting handles JOIN/CONCATENATE directives correctly

### Phase 6 — Housekeeping

- **TMDLGenerator consolidation** (6.1): Deployment helpers (`generate_deployment_config`, `generate_sensitivity_label`, `generate_refresh_schedule`, `generate_incremental_refresh_policy`) moved to `powerbi_import/deploy/pipeline_helpers.py`; `src/fabric_api/tmdl_generator.py` methods now delegate
- **Dead code cleanup** (6.2): `src/fabric_api/visual_generator.py` kept as compatibility layer (unique API); shim modules preserved for backward compatibility
- **Version sync** (6.3): All `__version__` strings updated to `6.0.0` (`pyproject.toml`, `qlik_export`, `powerbi_import`, `src/fabric_api`)
- **Documentation refresh** (6.4): README project structure updated to show canonical `qlik_export/` + `powerbi_import/`; programmatic usage examples updated; visual coverage table: 9 → 60+
- **CLI progress indicators** (6.5): Extraction and generation steps now show elapsed time; final summary shows total duration with output path
- **Tableau naming cleanup** (6.6): `wizard.py` `tableau_file` → `source_file`; deprecated `map_tableau_to_powerbi_type` and `convert_tableau_formula_to_dax` with deprecation warnings; `MigrationConfig.tableau_file` property now warns; comments/docstrings updated

### Stats

- Tests: 627 → 756 (+129)
- New test files: `test_v6_phase1.py` (29), `test_v6_phase2.py` (44), `test_v6_phase3.py` (13), `test_v6_phase4.py` (21), `test_v6_phase5.py` (22)
- Key files modified: `dax_converter.py`, `format_adapter.py`, `qlik_migrator.py`, `qlik_model_converter.py`, `qlik_script_converter.py`, `migrate.py`, `README.md`
- New files: `powerbi_import/deploy/pipeline_helpers.py`

---

## v5.0.0 — Pipeline Hardening & Test Coverage Release

### New Test Suites (Phase 1)

- **`test_format_adapter.py`**: 45+ tests for the Qlik→generation bridge layer — input validation, chart-type mapping, datasource/calculation/visual/parameter/story adaptation, edge cases
- **`test_migrate_cli.py`**: 25+ tests for CLI argument parsing, exit codes, `--dry-run`, `--skip-extraction`, batch modes, `_load_json` resilience
- **`test_import_to_powerbi.py`**: 15+ tests for `PowerBIImporter` JSON loading, format adapter integration, legacy fallback, error handling

### Format Adapter Hardening (Phase 3)

- **Renamed** `adapt_qlik_to_tableau_format` → `adapt_qlik_for_generation` (old name kept as deprecated alias with `DeprecationWarning`)
- **Input validation**: `None` and non-dict inputs now raise `ValueError` with clear message
- **Logging**: added warnings for empty columns, unmapped chart types, missing datasource names, empty datasources
- **Edge-case resilience**: missing `columns` key, empty table name, string connection fallback all handled

### Pipeline Robustness (Phase 4)

- **Eliminated all 5 `sys.path.insert()` hacks** in `migrate.py` — replaced with proper package imports (`qlik_export.*`, `powerbi_import.*`)
- **Added `--validate` CLI flag**: runs `ArtifactValidator.validate_project()` post-generation for TMDL/schema validation
- **Fixed `_load_json()` silent failures**: corrupt JSON now logs explicit error; missing files log debug message (no more bare `except Exception: pass`)
- **Renamed `tableau_file` → `source_file`** in `migration_config.py` defaults, with backward-compat migration for legacy config files

### Housekeeping

- **Fixed unqualified import** in `powerbi_import/import_to_powerbi.py` (`pbip_generator` → try/except with `powerbi_import.pbip_generator`)

### Version & Metadata

- Bumped `pyproject.toml` version to `5.0.0`
- Bumped `src/fabric_api/__init__.py` `__version__` to `5.0.0`

---

## v4.0.0 — Clean Architecture Release

### Architecture Overhaul

- **2-folder canonical layout**: `qlik_export/` (Qlik extraction) + `powerbi_import/` (PBI generation)
- **`src/fabric_api/` converted to backward-compatibility shim**: 13 modules now re-export from canonical locations with deprecation warnings. `tmdl_generator.py` and `visual_generator.py` remain local (unique `TMDLGenerator` class).
- **200+ Tableau references renamed** across 17 files in `powerbi_import/`:
  - `_clean_tableau_field_ref` → `_clean_field_ref`
  - `_convert_tableau_format_to_pbi` → `_convert_source_format_to_pbi`
  - `TableauMigrationTheme` → `QlikMigrationTheme`
  - `_TABLEAU_FUNCTION_LEAK_PATTERNS` → `_SOURCE_FUNCTION_LEAK_PATTERNS`
  - `_RE_TABLEAU_DERIVATION_REF` → `_RE_SOURCE_DERIVATION_REF`
  - All function parameters, config keys, docstrings, and UI strings updated
- **Proper package imports**: `sys.path.insert()` hacks replaced with package imports in `datasource_extractor.py`, `tmdl_generator.py`, `pbip_generator.py`, `import_to_powerbi.py`
- **`pyproject.toml` updated**: discovers `fabric_api`, `qlik_export`, and `powerbi_import` packages
- **Test suite migrated**: 58 import statements updated across 9 test files to use canonical `qlik_export.*` / `powerbi_import.deploy.*` paths
- **Examples & tools updated**: 28+ imports updated across 8 example files and 6 tool files

### Cleanup

- Removed empty `src/fabric_api/tableau/` directory
- Removed broken `src/fabric_api/base/` directory (dead abstract pipeline)
- Removed deprecated `migrate_old.py` (replaced by `migrate.py`)

---

## v3.0.0 — February 2026

### Unified Migration Pipeline (Phase 6)

- **Root-level `migrate.py` CLI**: single-command migration entry point
  - `python migrate.py app.qvf` — full pipeline (extract → convert → generate)
  - `python migrate.py app_export.json` — from Qlik JSON export
  - `--skip-extraction` flag to reuse existing intermediate JSON
  - `--output-dir` to specify output location
  - argparse-based CLI with clear help text
- **Extraction orchestrator** (`src/fabric_api/extraction_orchestrator.py`):
  - Extracts all 16 object types from QVF or JSON into structured intermediate JSON files
  - Produces: `datasources.json`, `dimensions.json`, `measures.json`, `visualizations.json`, `sheets.json`, `variables.json`, `loadscript.json`, `associations.json`, `bookmarks.json`, `master_items.json`, `app_metadata.json`
  - Clean 2-step pipeline: Extract → Intermediate JSON → Generate
- **Comprehensive DAX converter** (`src/fabric_api/dax_converter.py`, ~1300 lines):
  - **175+ Qlik expression → DAX function mappings** across 12 categories
  - String functions: Upper→UPPER, Lower→LOWER, Len→LEN, Mid→MID, Left→LEFT, Right→RIGHT, etc.
  - Math functions: Abs→ABS, Ceil→CEILING, Floor→FLOOR, Sqrt→SQRT, Log→LOG, Exp→EXP, etc.
  - Date functions: Year→YEAR, Month→MONTH, Day→DAY, Date→DATE, Today→TODAY, Now→NOW, etc.
  - Aggregation: Sum→SUM, Avg→AVERAGE, Count→COUNT, CountDistinct→DISTINCTCOUNT, etc.
  - Set Analysis → CALCULATE+ALLEXCEPT/REMOVEFILTERS (automatic)
  - Aggr() → SUMMARIZE/ADDCOLUMNS (automatic)
  - If()/Match()/Pick() → IF()/SWITCH() (automatic)
  - Inter-record: Above→EARLIER, Below→LATER, RangeSum→RUNNING_SUM emulation
  - Security: OSUser→USERPRINCIPALNAME
  - Type conversion, null handling, logical operators
- **Visual generator** (`src/fabric_api/visual_generator.py`, ~500 lines):
  - **60+ visual type mappings**: all Qlik chart types → Power BI visuals
  - **30+ visual config templates** with per-type axis, legend, data label, marker settings
  - Deep per-type query state building (gauge roles, KPI, combo Y/Y2, pie/donut, waterfall, box plot)
  - Grid layout positioning from Qlik sheet cell coordinates
- **Power Query M generator** (`src/fabric_api/m_query_generator.py`, ~300 lines):
  - **25 connector types**: Excel, CSV, SQL Server, PostgreSQL, BigQuery, Oracle, MySQL, Snowflake, Teradata, SAP HANA, Redshift, Databricks, Spark, Azure SQL/Synapse, Google Sheets, SharePoint, JSON, XML, PDF, Salesforce, Web, QVD, ODBC, OLE DB
  - Connection-metadata-to-M generators per connector type
- **Power Query M builder** (`src/fabric_api/m_query_builder.py`, ~800 lines):
  - **40+ chainable M transformation generators**: rename, remove, select, duplicate, reorder, split, merge, replace, replace nulls, trim, clean, fill down/up, filter, exclude, range, distinct, top N, aggregate, pivot, unpivot, join, union, sort, transpose, add index, conditional column, skip rows, promote/demote headers
  - `inject_m_steps()` for chainable step insertion with `{prev}` placeholder pattern

### Enhanced TMDL Generation (Phase 5.5)

- **Hierarchies in TMDL**: generated from Qlik drill-group dimensions
- **RLS roles in TMDL**: Section Access rules → `filterExpression` with `USERPRINCIPALNAME()`
- **Parameter/What-If tables**: Qlik variables → `GENERATESERIES`/`DATATABLE` + `SELECTEDVALUE` measures
- **Auto-generated Calendar table** with time intelligence columns (Year, Quarter, Month, Week, Day)
- **Geographic `dataCategory`** annotations (City, Country, StateOrProvince, Latitude, Longitude)
- **Column `isHidden` and `formatString`** properties in TMDL
- **`RELATED()` auto-insertion** for cross-table calculated column references
- **Sets/Groups/Bins** → calculated columns/tables

### Documentation (Phase 5)

- **`docs/FAQ.md`**: comprehensive FAQ covering Set Analysis, Aggr(), Section Access, variables, TMDL format, relationships
- **`docs/MAPPING_REFERENCE.md`**: unified reference — 60+ visual mappings, DAX functions, data types, connectors
- **`docs/QLIK_TO_DAX_REFERENCE.md`**: 175-function reference table with status icons
- **`docs/QLIK_TO_POWERQUERY_REFERENCE.md`**: 108+ property reference — connectors, column types, transforms
- **`docs/QLIK_SCRIPT_TO_POWERQUERY_REFERENCE.md`**: 165+ operation reference across 18 categories

### Testing (Phase 5)

- **End-to-end output validation tests** (`tests/test_migration_validation.py`):
  - Project structure completeness (all required .pbip files)
  - JSON validity (all generated JSON files parse correctly)
  - TMDL syntax validation (quotes, parentheses, keywords, expressions)
  - DAX formula validation (balanced parentheses, valid keywords, function names)
  - Visual→table cross-reference validation
- **Sample QVF and JSON** files for complete migration testing
- **`tools/testing/validate_samples.py`** — batch validation of sample migrations

### Copilot Context

- **`.github/copilot-instructions.md`**: 250-line AI context file describing full architecture, pipeline, object types, DAX mapping, visual types, development rules

## v2.0.0 — February 2026

### PBI Project / TMDL output (Phase 4)

- **PBIR v4.0 format**: `.pbip` projects compliant with Power BI Desktop December 2025 format
  - Schemas: `report/3.1.0`, `page/2.0.0`, `visualContainer/2.5.0`
  - SemanticModel in TMDL format (Tabular Model Definition Language)
- **TMDL model**: `database.tmdl`, `model.tmdl`, `relationships.tmdl`, `tables/*.tmdl`, `expressions.tmdl`
- **PBI Project creation from JSON or BIM model**: `TMDLGenerator.create_pbi_project()`
- **QVF extraction**: direct ZIP-based extraction of .qvf files
- **28 migration modules** in `tools/migration/` covering Qlik-specific features:
  - Variables, Section Access, Set Analysis, Bookmarks, Master Items
  - Alternate States, Stories, Themes, Custom Extensions
  - GeoAnalytics, NPrinting, Data Alerts, Collaboration
  - Advanced Aggregations, Inter-Record Functions, Listboxes
  - Current Selections, Navigation, REST API, Power Automate
- **Fabric deployment**: optional Azure-based deployment via `FabricClient`/`FabricDeployer`

### Testing & CI/CD

- **pytest framework** with fixtures and `conftest.py`
- **8 test files**: auth, client, documentation, integration, migration modules, TMDL generator, pipeline scenarios
- **GitHub Actions workflow** (`.github/workflows/deploy.yml`): validate → test → deploy

## v1.0.0 — February 2026

### Initial version

- Core library (`src/fabric_api/`): TMDL generator, Qlik migrator, script converter, QVF extractor
- Qlik expression → DAX basic conversion (6 aggregation mappings)
- Qlik script → Power Query M conversion (30 function mappings, 8 source types)
- Configuration via pydantic-settings + `.env` fallback
- Documentation and examples
