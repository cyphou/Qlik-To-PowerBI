# Changelog

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
