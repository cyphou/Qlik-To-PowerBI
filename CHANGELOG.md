# Changelog

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
