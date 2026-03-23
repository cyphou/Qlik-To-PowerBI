# DEV_PLAN v8.0 — Polish, Extensibility & Production Readiness

**Baseline:** v7.0.0 — 949 tests passing, 175+ DAX functions, 60+ visual types  
**Target:** v8.0.0 — Fix critical gaps, wire plugin system, expand test coverage, production-grade docs

---

## Phase 1 — Critical Fixes

### 1a. assessment.py: Remove Tableau Remnants
`powerbi_import/assessment.py` still contains Tableau-specific detection logic inherited from an earlier scaffold.

**Changes required:**
- Replace `my_workbook.twbx` in docstring with `my_app.qvf` (line ~15)
- Remove `_LOD_PATTERN` (`{FIXED|INCLUDE|EXCLUDE}`) — Tableau LOD, not Qlik (line ~89)
- Remove `_TABLE_CALC_PATTERN` (`RUNNING_*`, `WINDOW_*`) — Tableau table calcs (line ~93)
- Remove `SCRIPT_BOOL|SCRIPT_INT|SCRIPT_REAL|SCRIPT_STR` checks (line ~70)
- Remove `REGEXP_EXTRACT`, `RAWSQL_*` pattern groups (line ~81)
- Rename `workbook_name` → `app_name` across 5+ references
- Replace with **Qlik-specific checks**: Set Analysis complexity, Aggr nesting depth, Section Access usage, variable chain depth, stacked LOAD patterns

### 1b. DAX Stub Functions: Complete or Document
13 functions return `/* manual */`, hardcoded `0`, or passthrough `{0}`:

| Function | Current | Action |
|----------|---------|--------|
| `Correl` | `/* CORREL: manual */ 0` | Implement via `SUMX`/`AVERAGEX` Pearson formula |
| `BitCount` | `/* BitCount: no direct DAX */ 0` | Implement via `MOD`/`DIVIDE` bit-counting loop |
| `Skew` | `STDEV.S( /* skew: manual */` | Document as unsupported (no DAX equivalent) |
| `NetWorkDays` | `DATEDIFF({0},{1},DAY)` | Fix `{0}/{1}` → actual arg substitution |
| `KeepChar` | `/* KeepChar manual */ {0}` | Implement via nested `SUBSTITUTE` chain |
| `SubField` | passthrough | Map to `PATHITEM` for delimiter-split patterns |
| `Hash128/160/256` | passthrough | Document as unsupported (no DAX hash functions) |
| `Evaluate` | passthrough | Document as unsupported (dynamic eval impossible in DAX) |
| `MapSubstring` | partial `SUBSTITUTE` | Complete multi-map `SUBSTITUTE` chain |
| `Atan2` | simplified `ATAN({1}/{0})` | Implement proper 4-quadrant `ATAN2` via `IF`/`PI` |
| `Interval` | partial `VALUE` | Map to DAX `FORMAT` with HH:MM:SS |

**Additionally fix `{0}/{1}` placeholder patterns** — ~15 functions use Python `str.format` style but `_apply_function_map()` does not perform argument substitution. Implement `_substitute_args()` to split Qlik function arguments and replace `{0}`, `{1}`, etc.

### 1c. Custom Visual GUID Verification
`WordCloud1633006498960` in `visual_generator.py` uses an epoch timestamp — verify or replace with the official AppSource GUID for Word Cloud by Jason Thomas.

---

## Phase 2 — Test Coverage Expansion

### 2a. qlik_export Module Tests (NEW files)

| Module | Lines | Priority | Test File |
|--------|-------|----------|-----------|
| `dax_converter.py` | 1,178 | **CRITICAL** | `test_dax_converter.py` |
| `m_query_generator.py` | ~800 | HIGH | `test_m_query_generator.py` |
| `qlik_script_converter.py` | ~900 | HIGH | `test_qlik_script_converter.py` |
| `m_query_builder.py` | ~700 | HIGH | `test_m_query_builder.py` |
| `extraction_orchestrator.py` | ~600 | MEDIUM | `test_extraction_orchestrator.py` |
| `datasource_extractor.py` | ~400 | MEDIUM | `test_datasource_extractor.py` |
| `qlik_migrator.py` | ~300 | LOW | covered via integration |
| `qlik_model_converter.py` | ~200 | LOW | covered via integration |
| `qvf_extractor.py` | ~150 | LOW | covered via integration |

**Key test coverage targets:**
- `dax_converter.py`: All 164 `_SIMPLE_FUNCTION_MAP` entries, all 13 stub functions, `{0}/{1}` substitution, nested set analysis, Aggr decomposition, inter-record OFFSET
- `m_query_generator.py`: All 25 connector types, custom column injection, transform steps
- `qlik_script_converter.py`: JOIN/CONCATENATE/WHERE/GROUP BY/ORDER BY, stacked LOADs, inline tables

### 2b. powerbi_import Module Tests (NEW files)

| Module | Lines | Priority | Test File |
|--------|-------|----------|-----------|
| `assessment.py` | ~1,100 | HIGH (after Phase 1a fix) | `test_assessment.py` |
| `wizard.py` | ~500 | MEDIUM | `test_wizard.py` |
| `migration_report.py` | ~400 | MEDIUM | `test_migration_report.py` |
| `incremental.py` | ~300 | MEDIUM | `test_incremental.py` |
| `telemetry.py` | ~200 | LOW | `test_telemetry.py` |
| `progress.py` | ~150 | LOW | `test_progress.py` |
| `strategy_advisor.py` | ~300 | LOW | `test_strategy_advisor.py` |
| `comparison_report.py` | ~200 | LOW | via integration |
| `gateway_config.py` | ~150 | LOW | via integration |

**Target:** +200 tests minimum from Phase 2.

---

## Phase 3 — Visual & Reporting Enhancements

### 3a. Drillthrough Pages
Qlik "drill-to" sheet actions → Power BI drillthrough pages:
- Detect `navigation.action = "drillTo"` in visualization config
- Generate page with `drillFilterTarget` configuration
- Map drill fields to drillthrough filters

### 3b. Tooltip Pages
Qlik custom tooltip objects → Power BI tooltip pages:
- Detect `tooltip.visualization` references
- Generate tooltip page with reduced dimensions (320×240 px)
- Link source visual `tooltipType = "report"` to tooltip page

### 3c. Conditional Formatting — Icon Sets
Currently supports color rules. Extend to icon set formatting:
- Detect Qlik expression-based conditional icons
- Map to Power BI icon set conditional formatting (traffic lights, flags, arrows)

### 3d. Alternate States → Bookmarks
Integrate logic from `tools/migration/migrate_alternate_states.py`:
- Parse Qlik alternate state definitions
- Map to Power BI bookmark groups with state-specific selections
- Generate bookmark JSON in report structure

### 3e. Background Image Support
Detect Qlik sheet/object background images:
- Extract image references from sheet/visualization metadata
- Generate `StaticResources/RegisteredResources/` directory with images
- Reference in page/visual JSON configuration

---

## Phase 4 — Plugin System & Pipeline

### 4a. Wire PluginManager into Pipeline
`powerbi_import/plugins.py` has a complete `PluginManager` with 7 hooks but is never instantiated.

**Integration points:**
1. `migrate.py` → create `PluginManager`, load from config
2. `extraction_orchestrator.py` → call `pre_extraction()` / `post_extraction()`
3. `dax_converter.py` → call `transform_dax()` after each expression
4. `m_query_generator.py` → call `transform_m_query()` after each query
5. `pbip_generator.py` → call `pre_generation()` / `post_generation()`
6. `visual_generator.py` → call `custom_visual_mapping()` for unknown types

### 4b. Structured JSON Output for CI/CD
Add `--json` flag to `migrate.py` for machine-parseable output:
```json
{
  "status": "success",
  "input": "app.qvf",
  "output_dir": "output/app",
  "tables": 5,
  "measures": 12,
  "visuals": 8,
  "warnings": ["SubField: manual conversion required"],
  "duration_seconds": 3.2
}
```

### 4c. Progress Callbacks
Add optional progress callback to long operations:
- `extraction_orchestrator.py` → per-file extraction progress
- `pbip_generator.py` → per-table/per-page generation progress
- Wire to CLI progress bars (simple `[3/11] Extracting datasources...`)

---

## Phase 5 — Documentation Overhaul

### 5a. English Documentation
Create English versions of key guides:
- `docs/guides/QUICK_START.md` (English version of PRET_A_LEMPLOI)
- `docs/guides/MIGRATION_GUIDE.md` (English technical guide)
- `docs/guides/DEPLOYMENT_GUIDE.md` (Azure Fabric deployment)
- `docs/guides/PLUGIN_DEVELOPMENT.md` (how to create custom plugins)

### 5b. Update Existing Docs
- `README.md` → update test count (949+), add v7/v8 features, fix test command
- `MAPPING_REFERENCE.md` → add v7 DAX mappings (Aggr iterators, OFFSET, P()/E())
- `QLIK_TO_DAX_REFERENCE.md` → add v7 function additions
- `QLIK_OBJECTS_COVERAGE.md` → add v7 object coverage (Section Access OMIT/wildcard)
- `copilot-instructions.md` → update test count, add v7/v8 features
- `FAQ.md` → add v7 Q&A entries

### 5c. API Reference
Auto-generate API reference for key modules:
- `qlik_export/dax_converter.py` — public API
- `powerbi_import/pbip_generator.py` — public API
- `powerbi_import/import_to_powerbi.py` — public API

---

## Phase 6 — Housekeeping & Release

### 6a. Dead Code Audit
- Remove or archive unused shims in `src/fabric_api/`
- Clean up any remaining `tableau_` prefixed variables in `wizard.py`
- Evaluate `tools/migration/` scripts: promote essential ones, archive others

### 6b. CI/CD Enhancements
- Add test coverage reporting to `.github/workflows/ci.yml`
- Add linting step (ruff or flake8)
- Add `--json` output validation in CI

### 6c. Version & Changelog
- Bump all `__version__` to `8.0.0`
- Update `CHANGELOG.md`
- Tag release

---

## Success Metrics

| Metric | v7.0.0 | v8.0.0 Target |
|--------|--------|---------------|
| Tests | 949 | 1,200+ |
| DAX stubs fixed | 13 remaining | ≤ 3 (unsupported-only) |
| Modules with tests | 18/31 | 27/31 |
| Tableau remnants | 8+ locations | 0 |
| Plugin hooks wired | 0/7 | 7/7 |
| English guides | 0 | 4 |
| CI coverage report | No | Yes |
