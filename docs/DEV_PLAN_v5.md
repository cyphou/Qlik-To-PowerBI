<!-- DOC-SHINY-BANNER -->
![Documentation](https://img.shields.io/badge/Documentation-Shiny_Style-0A66C2?style=flat-square&logo=readthedocs&logoColor=white)
![Maintained](https://img.shields.io/badge/Maintained-2026-2EA44F?style=flat-square&logo=github&logoColor=white)
![Navigation](https://img.shields.io/badge/Navigation-Quick_Access-6F42C1?style=flat-square&logo=bookstack&logoColor=white)
# Development Plan — v5.0.0

> **Qlik → Power BI Migration Toolkit**
> Target: Q2 2026 · Version: 5.0.0 · Builds on v4.0.0 (Clean Architecture Release)

---

## Current State (post v4.0.0)

| Area | Status | Details |
|------|--------|---------|
| Architecture | ✅ Clean | `qlik_export/` + `powerbi_import/` canonical, `src/fabric_api/` shim |
| Tests | ✅ 538 pass | All imports migrated; 0 failures |
| Naming | ⚠️ 95% done | Residual `tableau_file` / `adapt_qlik_to_tableau_format` in bridge layer |
| `sys.path` hacks | ⚠️ Partial | Fixed in packages; 5 remain in `migrate.py` |
| TMDLGenerator | ⚠️ Duplicated | Class-based (1607 lines in `src/fabric_api/`) vs function-based (3561 lines in `powerbi_import/`) — not consolidated |
| Format adapter | ⚠️ Fragile | Zero input validation, 1 log statement, missing object types |
| Test coverage | ⚠️ Gaps | Zero tests for `format_adapter.py`, `migrate.py` CLI, `import_to_powerbi.py` |
| Documentation | ⚠️ Stale | README still shows `src/fabric_api/` as canonical; stale code examples |

---

## Phase 1 — Critical Test Coverage (Priority: **CRITICAL**)

Zero-coverage modules form the bridge between Qlik extraction and PBI generation — breakage here silently produces wrong output.

### 1.1 Test `format_adapter.py` — the Qlik→generation bridge

| Test | Validates |
|------|-----------|
| `test_adapt_empty_input` | `adapt_qlik_to_tableau_format({})` returns valid structure, no crash |
| `test_adapt_none_input` | `adapt_qlik_to_tableau_format(None)` raises `ValueError` (guard) |
| `test_adapt_minimal_single_table` | One datasource, one table, basic columns → correct 16-key output |
| `test_adapt_measures_and_dimensions` | Measures + dimensions → `calculations` list with correct `role` |
| `test_adapt_relationships` | Qlik associations → Tableau-format `relationships` |
| `test_adapt_visualizations` | Qlik chart type → `worksheets` list with correct visual types |
| `test_adapt_variables` | Variables → `parameters` list |
| `test_adapt_duplicate_table_names` | Two datasources with same `tableName` → deduplicated or error |
| `test_adapt_missing_columns` | Datasource with empty `columns` list → no crash, fallback applied |
| `test_chart_type_mapping_coverage` | All 37 mapped chart types → expected PBI visual type |
| `test_chart_type_unknown_fallback` | Unknown Qlik type → `clusteredBarChart` fallback + logged warning |
| `test_adapt_hierarchies_from_drill_groups` | Drill-group dimensions → `hierarchies` output (NEW feature) |
| `test_adapt_master_items` | Master items → referenced in dimensions/measures |
| `test_expression_passthrough` | Complex Qlik expression strings → preserved in `formula` field |

**Estimated effort:** 4-6 hours · Creates `tests/test_format_adapter.py`

### 1.2 Test `migrate.py` CLI

| Test | Validates |
|------|-----------|
| `test_help_flag` | `--help` exits 0 with usage text |
| `test_missing_input_file` | Nonexistent file → `ExitCode.INPUT_ERROR` |
| `test_invalid_extension` | `.xlsx` file → error message |
| `test_dry_run` | `--dry-run` → prints steps, doesn't write files |
| `test_assess_mode` | `--assess` → produces assessment without generation |
| `test_json_input` | `.json` file → skips extraction, runs generation |
| `test_qvf_input` | `.qvf` file → runs extraction then generation |
| `test_output_dir_flag` | `--output-dir custom/` → writes into custom directory |
| `test_quiet_flag` | `--quiet` → no stdout (except errors) |
| `test_batch_config` | `--batch-config` → processes multiple files |
| `test_validate_flag` | `--validate` → post-generation TMDL validation (NEW feature) |

**Estimated effort:** 3-4 hours · Creates `tests/test_migrate_cli.py`

### 1.3 Test `import_to_powerbi.py` — the generation orchestrator

| Test | Validates |
|------|-----------|
| `test_import_from_json_files` | Load 11 JSON files → `PowerBIImporter.import_all()` succeeds |
| `test_import_missing_json` | Missing `datasources.json` → clear error, not `KeyError` |
| `test_import_corrupt_json` | Malformed JSON → error logged, not silently swallowed |
| `test_import_empty_datasources` | Empty datasources list → generates empty project (no crash) |
| `test_output_structure` | Generated `.pbip` project contains required directories and files |

**Estimated effort:** 2-3 hours · Creates `tests/test_import_to_powerbi.py`

---

## Phase 2 — TMDLGenerator Consolidation (Priority: **HIGH**)

Two diverged implementations cause maintenance overhead, confusion, and test fragility.

### 2.1 Inventory unique features

| Feature | `src/fabric_api/` (class-based) | `powerbi_import/` (function-based) | Action |
|---------|-----|-----|--------|
| TMDL semantic model building | Basic | Advanced (M2M, ambiguous paths, calc groups, field params) | Keep powerbi_import |
| Visual JSON generation | `_write_visual_json` / `_build_query_state` | None | Port to `powerbi_import/pbip_generator.py` |
| Calendar table | `generate_calendar_table()` | `_add_date_table()` (richer) | Keep powerbi_import version |
| Parameter tables | `generate_parameter_table()` | `_create_parameter_tables()` (richer) | Keep powerbi_import version |
| Data category inference | `infer_data_category()` | `_map_semantic_role_to_category()` | Keep powerbi_import version |
| Deployment config | `generate_deployment_config()` | Not present | Port to `powerbi_import/deploy/` |
| Sensitivity label | `generate_sensitivity_label()` | Not present | Port to `powerbi_import/deploy/` |
| Refresh schedule | `generate_refresh_schedule()` | Not present | Port to `powerbi_import/deploy/` |
| Incremental refresh | `generate_incremental_refresh_policy()` | `detect_refresh_policy()` | Merge into powerbi_import |
| Theme JSON | `generate_theme_json()` | Not present | Port to `powerbi_import/pbip_generator.py` |
| `create_pbi_project_from_migration()` | Top-level convenience | Not present | Port to `powerbi_import/pbip_generator.py` |

### 2.2 Porting plan

```
Step 1: Port deployment features → powerbi_import/deploy/deployment_config.py  (NEW)
          - generate_deployment_config()
          - generate_sensitivity_label()
          - generate_refresh_schedule()
          - generate_incremental_refresh_policy()

Step 2: Port visual/project features → powerbi_import/pbip_generator.py
          - generate_theme_json()   (if not already present)
          - create_pbi_project_from_migration()   (wrapper function)

Step 3: Reduce src/fabric_api/tmdl_generator.py to a thin shim
          - class TMDLGenerator wraps powerbi_import functions
          - create_pbi_project_from_migration re-exports from powerbi_import

Step 4: Update tests to import from canonical locations
          - test_tmdl_generator.py → powerbi_import.tmdl_generator
          - test_v31_features.py → individual powerbi_import modules
```

### 2.3 Delete dead visual_generator

`src/fabric_api/visual_generator.py` (847 lines) is dead code — the `__init__.py` shim already imports from `powerbi_import.visual_generator`. Delete it.

**Estimated effort:** 8-12 hours total for TMDLGenerator consolidation

---

## Phase 3 — Format Adapter Hardening (Priority: **HIGH**)

### 3.1 Input validation & error handling

| Fix | Location | Details |
|-----|----------|---------|
| Guard against `None`/non-dict input | `adapt_qlik_to_tableau_format()` entry | Raise `ValueError` with clear message |
| Guard against empty datasources | `_adapt_datasources()` | Return empty list, log warning |
| Handle duplicate table names | `_adapt_datasources()` | Append suffix (`_2`, `_3`) or merge columns |
| Log unmapped chart types | `_adapt_worksheets()` | `logger.warning(f"Unmapped Qlik type: {qlik_type}")` |
| Handle missing `columns` key | `_adapt_datasources()` | Default to `[]`, don't crash |

### 3.2 Populate missing object types

Currently `hierarchies`, `sets`, `groups`, `bins`, `filters`, `actions`, `sort_orders`, `aliases`, `user_filters` are always empty `[]`. Qlik data has some of these:

| Object | Source in Qlik data | Target |
|--------|-------------------|--------|
| Hierarchies | `dimensions` with `isDrillGroup: true` → levels | `extra_objects.hierarchies` |
| Filters | `visualizations` with type `filterpane` | `extra_objects.filters` |
| Bookmarks (selections) | `bookmarks.json` | `extra_objects.bookmarks` |
| Variables → Parameters | Already done | ✅ |

### 3.3 Rename bridge function

| Current | Proposed | Reason |
|---------|----------|--------|
| `adapt_qlik_to_tableau_format()` | `adapt_qlik_for_generation()` | The output format is the generation layer's input format, not "Tableau format" |

Update all call sites: `migrate.py` L935, `import_to_powerbi.py` L101-102, all tests.

### 3.4 Add comprehensive logging

Replace the single `logger.info` with structured logging:

```
logger.info("Adapting Qlik data: %d datasources, %d visualizations", ...)
logger.warning("Empty columns in datasource '%s' — using fallback", table_name)
logger.warning("Unmapped Qlik chart type '%s' → defaulting to clusteredBarChart", qlik_type)
logger.error("Duplicate table name '%s' — appending suffix", table_name)
logger.debug("Mapped %d measures, %d dimensions, %d relationships", ...)
```

**Estimated effort:** 6-8 hours

---

## Phase 4 — Pipeline Robustness (Priority: **MEDIUM**)

### 4.1 Eliminate `sys.path` hacks from `migrate.py`

5 remaining `sys.path.insert()` calls at lines 163, 228, 290, 823, 934.

| Current | Fix |
|---------|-----|
| `sys.path.insert(0, .../qlik_export); from extraction_orchestrator import ...` | `from qlik_export.extraction_orchestrator import ...` |
| `sys.path.insert(0, .../powerbi_import); from import_to_powerbi import ...` | `from powerbi_import.import_to_powerbi import ...` |
| `sys.path.insert(0, .../powerbi_import); from migration_report import ...` | `from powerbi_import.migration_report import ...` |
| `sys.path.insert(0, .../powerbi_import); from config.migration_config import ...` | `from powerbi_import.config.migration_config import ...` |
| `sys.path.insert(0, qlik_dir); from format_adapter import ...` | `from qlik_export.format_adapter import ...` |

### 4.2 Add `--validate` CLI flag

Wire up `powerbi_import/validator.py` into `migrate.py`:

```python
parser.add_argument('--validate', action='store_true',
                    help='Run post-generation TMDL/DAX validation')
```

After generation, if `--validate`, call `ArtifactValidator.validate_project(output_dir)` and report issues.

### 4.3 Fix silent JSON loading failures

`_load_json()` in `migrate.py` catches all exceptions and returns `[]`. Add:

```python
except json.JSONDecodeError as e:
    logger.error("Corrupt JSON file '%s': %s", path, e)
    raise SystemExit(ExitCode.INPUT_ERROR)
except FileNotFoundError:
    logger.warning("Optional JSON file not found: '%s'", path)
    return []
```

### 4.4 Progress indicators

Add elapsed-time and step counters:

```
[1/3] Extracting from app.qvf... (2.1s)
[2/3] Adapting to generation format... (0.3s)
[3/3] Generating .pbip project... (1.8s)
✓ Migration complete in 4.2s
```

For batch mode: `[3/15] Processing HR_Analytics.qvf... ✓ (3.1s) — 12 remaining`

### 4.5 Remaining `tableau` naming cleanup

| Location | Current | Proposed |
|----------|---------|----------|
| `migrate.py` L826-827 | `getattr(config, 'tableau_file', None)` | `getattr(config, 'source_file', None)` |
| `migrate.py` L251 | `'TableauMigrationTheme.json'` | `'QlikMigrationTheme.json'` |
| `powerbi_import/wizard.py` L180 | `tableau_file=config['source_file']` | `source_file=config['source_file']` |
| `powerbi_import/config/migration_config.py` | `tableau_file` property | Remove (already has `source_file` as primary) |
| `qlik_export/datasource_extractor.py` L65,107 | `map_tableau_to_powerbi_type` alias | Keep alias but add deprecation warning |

**Estimated effort:** 4-6 hours

---

## Phase 5 — Documentation Refresh (Priority: **MEDIUM**)

### 5.1 README.md overhaul

| Section | Issue | Fix |
|---------|-------|-----|
| Project Structure tree | Shows `src/fabric_api/` as canonical | Rewrite with `qlik_export/` + `powerbi_import/` as primary |
| Programmatic Usage | `from fabric_api import ...` | Update to `from qlik_export import ...` / `from powerbi_import import ...` |
| Testing section | `pytest --cov=fabric_api tests/` | `pytest --cov=qlik_export --cov=powerbi_import tests/` |
| Migration coverage table | 9 visual types | Match the 60+ from docs |
| Mermaid dependency graph | Missing `format_adapter`, `pbip_generator` | Add full module graph |
| Quick Start examples | Old import paths | New canonical paths |

### 5.2 Technical docs updates

| File | Issue |
|------|-------|
| `docs/technical/QVF_MIGRATION_GUIDE.md` L435 | References `src/fabric_api/qvf_extractor.py` → `qlik_export/qvf_extractor.py` |
| `docs/MAPPING_REFERENCE.md` | Verify all import paths |
| `docs/guides/PRET_A_LEMPLOI.md` | Check examples use new paths |
| `docs/guides/QUICK_START_HYBRIDE.md` | Check examples use new paths |

### 5.3 Version & metadata

| Item | Current | Target |
|------|---------|--------|
| `src/fabric_api/__init__.py` `__version__` | `"3.1.0"` | `"5.0.0"` |
| `pyproject.toml` version | `"4.0.0"` | `"5.0.0"` |
| `CHANGELOG.md` | v4.0.0 latest | Add v5.0.0 section |

**Estimated effort:** 3-4 hours

---

## Phase 6 — Dead Code Cleanup (Priority: **LOW**)

### 6.1 Delete dead files

| File | Reason |
|------|--------|
| `src/fabric_api/visual_generator.py` (847 lines) | Dead — `__init__.py` re-exports from `powerbi_import.visual_generator` |
| 13 individual shim modules in `src/fabric_api/` | Redundant — `__init__.py` already re-exports everything; individual files are never directly imported |

### 6.2 Consolidate fabric_api shim

After Phase 2 (TMDLGenerator merge):
- `src/fabric_api/tmdl_generator.py` → thin shim re-exporting from `powerbi_import`
- `__init__.py` → simplified, only re-exports + deprecation warning
- Total `src/fabric_api/` should be ~2 files: `__init__.py` + `tmdl_generator.py` shim

### 6.3 Clean up `test_phase5_modules.py`

Currently 257 lines but only checks file existence. Either:
- Convert to real behavioral tests (per Phase 1), or
- Delete and rely on Phase 1 tests + E2E coverage

**Estimated effort:** 2-3 hours

---

## Execution Order

```
Phase 1.1  ─── Test format_adapter.py ─────────────────────── Week 1  (CRITICAL)
Phase 1.2  ─── Test migrate.py CLI ────────────────────────── Week 1  (CRITICAL)
Phase 1.3  ─── Test import_to_powerbi.py ──────────────────── Week 1  (CRITICAL)
Phase 3.1  ─── Format adapter validation & error handling ─── Week 2  (HIGH)
Phase 3.2  ─── Populate missing object types ──────────────── Week 2  (HIGH)
Phase 3.3  ─── Rename adapt_qlik_to_tableau_format ────────── Week 2  (HIGH)
Phase 4.1  ─── Eliminate sys.path hacks from migrate.py ──── Week 2  (MEDIUM)
Phase 4.2  ─── Add --validate flag ────────────────────────── Week 2  (MEDIUM)
Phase 2.1  ─── TMDLGenerator feature inventory ───────────── Week 3  (HIGH)
Phase 2.2  ─── Port unique features to powerbi_import ────── Week 3  (HIGH)
Phase 2.3  ─── Delete dead visual_generator ───────────────── Week 3  (LOW)
Phase 4.3  ─── Fix silent JSON failures ───────────────────── Week 3  (MEDIUM)
Phase 4.4  ─── Progress indicators ────────────────────────── Week 3  (MEDIUM)
Phase 4.5  ─── Final tableau naming cleanup ───────────────── Week 3  (MEDIUM)
Phase 5    ─── Documentation refresh ──────────────────────── Week 4  (MEDIUM)
Phase 6    ─── Dead code cleanup ──────────────────────────── Week 4  (LOW)
```

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Test count | ≥ 600 (currently 538) |
| Test coverage (format_adapter) | ≥ 80% line coverage |
| Test coverage (migrate.py CLI) | ≥ 70% line coverage |
| `sys.path.insert` calls | 0 (currently 5 in migrate.py + 1 in fabric_api/__init__.py) |
| Remaining `tableau` references in functional code | 0 (currently ~12) |
| TMDLGenerator implementations | 1 canonical + 1 shim (currently 2 full implementations) |
| Dead code in `src/fabric_api/` | ≤ 2 files (currently ~16 files) |
| README architecture accuracy | Matches actual project structure |

---

## Risk Register

| Risk | Impact | Mitigation |
|------|--------|------------|
| TMDLGenerator merge breaks `create_pbi_project_from_migration()` API | HIGH | Keep backward-compat wrapper; test all 9 consuming test files |
| Renaming `adapt_qlik_to_tableau_format` breaks external scripts | MEDIUM | Keep old name as deprecated alias for 1 release |
| New tests surface latent bugs in format_adapter | MEDIUM | Fix bugs found — the whole point of the tests |
| Documentation update effort underestimated | LOW | Prioritize README + CHANGELOG; defer technical docs |
| Removing sys.path hacks breaks execution without editable install | MEDIUM | Add `conftest.py` path setup as safety net; document `pip install -e .` requirement |

---

## Definition of Done (v5.0.0)

- [ ] ≥ 60 new tests across `format_adapter`, `migrate` CLI, `import_to_powerbi`
- [ ] `format_adapter.py` validates input, logs warnings/errors, handles edge cases
- [ ] TMDLGenerator consolidated — single canonical implementation in `powerbi_import/`
- [ ] `src/fabric_api/tmdl_generator.py` is a thin backward-compat shim
- [ ] `src/fabric_api/visual_generator.py` deleted (dead code)
- [ ] Zero `sys.path.insert()` hacks in `migrate.py`
- [ ] `adapt_qlik_to_tableau_format` → `adapt_qlik_for_generation` (old name kept as deprecated alias)
- [ ] `--validate` CLI flag wired to `ArtifactValidator`
- [ ] README.md reflects actual `qlik_export/` + `powerbi_import/` architecture
- [ ] All 600+ tests pass
- [ ] `CHANGELOG.md` documents v5.0.0

