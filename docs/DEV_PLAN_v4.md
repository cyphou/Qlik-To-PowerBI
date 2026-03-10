# Development Plan — v4.0.0

> **Qlik → Power BI Migration Toolkit**
> Target: Q2 2026 · Architecture: `qlik_export/` + `powerbi_import/` 2-step pipeline

---

## Current State (post v3.1 restructure)

The project was restructured to mirror the TableauToPowerBI 2-folder architecture:

| Layer | Role | Status |
|-------|------|--------|
| `qlik_export/` | Qlik-specific extraction (11 JSON files) | ✅ Created — 11 modules |
| `qlik_export/format_adapter.py` | Qlik 11-key → Tableau 16-key bridge | ✅ Created — 603 lines |
| `qlik_export/datasource_extractor.py` | API bridge (3 Tableau-named wrappers) | ✅ Created — 148 lines |
| `powerbi_import/` | Shared PBI generation layer (from Tableau project) | ⚠️ Copied — 200+ Tableau refs remain |
| `migrate.py` | New 2-step CLI entry point | ✅ Created — 700+ lines |
| `src/fabric_api/` | Old module package (v3.1) | ⚠️ Still exists — duplicate code |
| `tests/` | 15 test files | ⚠️ All import from old `fabric_api.*` path |
| `examples/` + `tools/` | Usage examples + migration scripts | ⚠️ All import from old `fabric_api.*` path |

---

## Phase 1 — Clean Architecture (Priority: HIGH)

Eliminate duplicate code, fix imports, remove Tableau-specific naming.

### 1.1 Resolve the `src/fabric_api/` duplication

The same modules exist in both `src/fabric_api/` and `qlik_export/`. One copy must be authoritative.

| Task | Files | Effort |
|------|-------|--------|
| Decide canonical location for each module | All `.py` in both dirs | Design decision |
| Keep `qlik_export/` as the canonical source for Qlik-specific code | 10 modules | — |
| Move `auth.py`, `client.py`, `deployer.py`, `validator.py`, `utils.py` into `powerbi_import/deploy/` (already there) | 5 files | S |
| Update `src/fabric_api/__init__.py` to re-export from `qlik_export/` + `powerbi_import/` (backward compat shim) | 1 file | S |
| OR delete `src/fabric_api/` entirely and fix all imports | ~30 files | L |

**Recommendation:** Keep `src/fabric_api/` as a thin re-export shim for backward compatibility. Mark it deprecated. All new code imports from `qlik_export/` or `powerbi_import/`.

### 1.2 Rename Tableau references in `powerbi_import/`

200+ Tableau-specific references across 11+ files. Prioritize functional code over comments.

| Priority | File | Changes Required |
|----------|------|------------------|
| **P0** | `tmdl_generator.py` | Rename `_clean_tableau_field_ref` → `_clean_field_ref`, `_convert_tableau_format_to_pbi` → `_convert_format_to_pbi`, update imports from `datasource_extractor` |
| **P0** | `pbip_generator.py` | Rename `_convert_number_format(tableau_format)` → `_convert_number_format(source_format)`, `"TableauMigrationTheme"` → `"QlikMigrationTheme"`, `"Tableau Migration"` → `"Qlik Migration"` |
| **P0** | `config/migration_config.py` | Rename `tableau_file` → `source_file`, update config key, property, and logger namespace |
| **P1** | `comparison_report.py` | Rename dict keys `'tableau'` → `'source'`, `'tableau_formula'` → `'source_formula'`, update HTML strings |
| **P1** | `plugins.py` | Rename parameter `tableau_file` → `source_file`, `tableau_mark` → `source_mark`, logger namespace |
| **P1** | `migration_report.py` | Rename `_TABLEAU_LEAK_PATTERNS` → `_SOURCE_LEAK_PATTERNS` |
| **P1** | `assessment.py` | Update docstrings and string literals ("Tableau workbook" → "Qlik application") |
| **P1** | `strategy_advisor.py` | Update docstrings ("Tableau Prep flow" → "Qlik load script") |
| **P2** | `m_query_generator.py` | Update docstrings only |
| **P2** | `telemetry.py` | Update docstring ("TableauToPowerBI" → "QlikToPowerBI") |
| **P2** | `telemetry_dashboard.py` | Update HTML title |
| **P2** | `wizard.py` | Update prompts & labels |
| **P2** | `import_to_powerbi.py` | Rename `_load_tableau_format_files` → `_load_legacy_format_files` |

**Estimated effort:** 3-4 hours for P0+P1, 1-2 hours for P2.

### 1.3 Fix `sys.path` manipulation

Replace `sys.path.insert()` hacks with proper package structure.

| Task | Location | Approach |
|------|----------|----------|
| Add `pyproject.toml` package discovery for `qlik_export` and `powerbi_import` | `pyproject.toml` | `packages = [{include = "qlik_export"}, {include = "powerbi_import"}]` |
| Replace bare imports in `datasource_extractor.py` | `qlik_export/datasource_extractor.py` | `from qlik_export.dax_converter import ...` |
| Replace `sys.path.insert` in `migrate.py` | `migrate.py` | Direct package imports after editable install |
| Replace `sys.path.insert` in `powerbi_import/tmdl_generator.py` | `powerbi_import/tmdl_generator.py` | `from qlik_export.datasource_extractor import ...` |
| Replace `sys.path.insert` in `conftest.py` | `tests/conftest.py` | `pip install -e .` makes both packages importable |

**Prerequisite:** Decide on the `src/fabric_api/` question first (1.1).

### 1.4 Clean up dead artifacts

| Task | Files |
|------|-------|
| Remove `src/fabric_api/tableau/` (empty directory) | 1 dir |
| Remove or archive `migrate_old.py` after validation | 1 file |
| Remove `src/fabric_api/base/` if unused (empty `__init__.py` only) | 1 dir |

---

## Phase 2 — Test Suite Migration (Priority: HIGH)

### 2.1 Update test imports

9 test files import from `fabric_api.*`. Update to new package paths.

| Test File | Current Import | Target Import |
|-----------|---------------|--------------|
| `test_simple_unit.py` | `fabric_api.dax_converter` | `qlik_export.dax_converter` |
| `test_edge_cases.py` | `fabric_api.dax_converter`, etc. | `qlik_export.dax_converter`, etc. |
| `test_medium_integration.py` | `fabric_api.*` | `qlik_export.*` |
| `test_complex_e2e.py` | `fabric_api.*` | `qlik_export.*` |
| `test_tmdl_generator.py` | `fabric_api.tmdl_generator` | `powerbi_import.tmdl_generator` |
| `test_pipeline_scenarios.py` | `fabric_api.qvf_extractor`, etc. | `qlik_export.*` |
| `test_v31_features.py` | `fabric_api.*` | `qlik_export.*` |
| `test_auth.py` | `fabric_api.auth` | `powerbi_import.deploy.auth` |
| `test_client.py` | `fabric_api.client` | `powerbi_import.deploy.client` |

### 2.2 Update `conftest.py`

Remove `sys.path.insert(0, str(project_root / "src"))` hack. Replace with editable install or direct package path.

### 2.3 Add new architecture tests

| Test | Purpose |
|------|---------|
| `test_format_adapter.py` | Unit tests for Qlik→Tableau format transformation |
| `test_import_to_powerbi.py` | Integration test: JSON loading → PowerBIImporter |
| `test_migrate_cli.py` | CLI argument parsing, exit codes, dry-run mode |
| `test_pipeline_e2e.py` | Full pipeline: sample .qvf → .pbip output validation |

### 2.4 Run full test suite

```bash
pytest tests/ -v --tb=short
```

Fix all failures before proceeding.

---

## Phase 3 — Examples & Tools Update (Priority: MEDIUM)

### 3.1 Update examples

| File | Action |
|------|--------|
| `examples/powerbi/ADVANCED_PATTERNS.py` | Update all `from fabric_api import ...` to new paths |
| `examples/powerbi/pbi_project_examples.py` | Same |
| `examples/powerbi/examples.py` | Same |
| `examples/powerbi/qlik_migration_examples.py` | Same |
| `examples/powerbi/qlik_model_examples.py` | Same |
| `examples/powerbi/qlik_script_examples.py` | Check + update |
| `examples/powerbi/qvf_examples.py` | Check + update |
| `examples/powerbi/TROUBLESHOOTING.py` | Check + update |

### 3.2 Update tools

| File | Action |
|------|--------|
| `tools/migration/migrate_qlik_model.py` | `fabric_api.qlik_model_converter` → `qlik_export.qlik_model_converter` |
| `tools/migration/migrate_qlik_scripts.py` | `fabric_api.qlik_script_converter` → `qlik_export.qlik_script_converter` |
| `tools/migration/migrate_qlik_to_pbi.py` | Update all `fabric_api` imports |
| `tools/testing/test_migration_hybride.py` | Update all `fabric_api` imports |
| `tools/testing/test_migration_suite.py` | Update all `fabric_api` imports |
| `tools/testing/generate_sample_artifacts.py` | Update all `fabric_api` imports |

---

## Phase 4 — Format Adapter Hardening (Priority: MEDIUM)

### 4.1 Improve `format_adapter.py`

| Task | Description |
|------|-------------|
| Handle edge cases in datasource restructuring | Empty tables, missing columns, duplicate names |
| Improve Qlik expression → DAX formula passthrough | Expressions with nested `{< >}` set analysis |
| Add unit tests for every mapping function | `_adapt_datasources`, `_adapt_calculations`, `_adapt_worksheets`, etc. |
| Add logging for unmapped visual types | Track which Qlik chart types hit the fallback |
| Handle master item cross-references | Master items that reference other master items |

### 4.2 Improve `datasource_extractor.py`

| Task | Description |
|------|-------------|
| Rename Tableau-named wrappers | `convert_tableau_formula_to_dax` → `convert_formula_to_dax` (keep old name as alias) |
| Add more type mappings | Handle Qlik-specific types (`dual`, `timestamp`, `interval`) |
| Add error handling for missing modules | Graceful fallback if dax_converter unavailable |

---

## Phase 5 — Pipeline Robustness (Priority: MEDIUM)

### 5.1 End-to-end validation

| Task | Description |
|------|-------------|
| Test full migration with sample QVF | Use existing `examples/qlik/` samples |
| Validate generated .pbip opens in PBI Desktop | Manual or automated check |
| Validate TMDL syntax in generated tables | Balanced quotes, valid DAX, correct TMDL keywords |
| Compare output with `artifacts/powerbi_projects/` samples | Regression check |

### 5.2 Error handling improvements

| Task | Location |
|------|----------|
| Better error messages when `qlik_export/*.json` files missing | `import_to_powerbi.py` |
| Graceful handling of corrupt/incomplete QVF files | `qvf_extractor.py` |
| Progress indicators for large apps | `migrate.py` extraction step |
| Structured error reporting in batch mode | `migrate.py` batch functions |

### 5.3 Performance

| Task | Description |
|------|-------------|
| Profile large app migration (100+ sheets) | Identify bottlenecks |
| Lazy-load modules in `migrate.py` | Avoid importing all of `powerbi_import` for `--help` |
| Optimize `format_adapter.py` for large datasource lists | Avoid O(n²) loops |

---

## Phase 6 — Documentation & CI (Priority: LOW)

### 6.1 Update documentation

| File | Action |
|------|--------|
| `CHANGELOG.md` | Add v4.0.0 section documenting architecture change |
| `README.md` | Update architecture diagram, package paths, usage examples |
| `.github/copilot-instructions.md` | Update project structure section |
| `docs/MAPPING_REFERENCE.md` | Verify all references still valid |
| `docs/technical/*.md` | Update any `src/fabric_api/` path references |

### 6.2 Update CI/CD

| Task | Description |
|------|-------------|
| Update `.github/workflows/deploy.yml` | Ensure tests run with new package structure |
| Add linting step | `flake8` or `ruff` for import validation |
| Add `pyproject.toml` package config | Proper `[project]` and `[tool.setuptools.packages]` |

### 6.3 Update `pyproject.toml`

```toml
[project]
name = "qlik-to-powerbi"
version = "4.0.0"

[tool.setuptools.packages.find]
include = ["qlik_export*", "powerbi_import*"]
```

---

## Execution Order

```
Phase 1.1  ─── Resolve src/fabric_api/ duplication ──────────────── Week 1
Phase 1.2  ─── Rename Tableau refs in powerbi_import/ (P0+P1) ──── Week 1
Phase 1.3  ─── Fix sys.path hacks ──────────────────────────────── Week 1
Phase 1.4  ─── Clean up dead artifacts ─────────────────────────── Week 1
Phase 2.1  ─── Update test imports ─────────────────────────────── Week 2
Phase 2.2  ─── Update conftest.py ──────────────────────────────── Week 2
Phase 2.3  ─── Add new architecture tests ──────────────────────── Week 2
Phase 2.4  ─── Run full test suite ─────────────────────────────── Week 2
Phase 3    ─── Update examples & tools ────────────────────────── Week 3
Phase 4    ─── Format adapter hardening ───────────────────────── Week 3
Phase 5    ─── Pipeline robustness ────────────────────────────── Week 4
Phase 6    ─── Documentation & CI ─────────────────────────────── Week 4
```

---

## Risk Register

| Risk | Impact | Mitigation |
|------|--------|------------|
| Removing `src/fabric_api/` breaks external consumers | HIGH | Keep as deprecated re-export shim |
| Tableau-specific logic in `powerbi_import/` produces wrong output for Qlik data | MEDIUM | Tableau-specific transforms are no-ops for Qlik data; validate with test suite |
| `format_adapter.py` mapping gaps for exotic Qlik objects | MEDIUM | Add fallback logging; iterate based on real-world QVF files |
| Test suite passes on old paths but fails on new paths | LOW | Run tests on both import paths during transition |
| `powerbi_import/` drift from upstream TableauToPowerBI project | LOW | Document divergence; consider shared package long-term |

---

## Definition of Done (v4.0.0)

- [ ] No duplicate module files — single canonical location per module
- [ ] Zero `"Tableau"` references in functional code (comments OK during transition)
- [ ] Zero `sys.path.insert` hacks — proper package imports everywhere
- [ ] All 15 test files pass with new import paths
- [ ] 4+ new tests covering `format_adapter`, `import_to_powerbi`, CLI, E2E pipeline
- [ ] Full pipeline tested: sample `.qvf` → `.pbip` that opens in Power BI Desktop
- [ ] `CHANGELOG.md` and `README.md` updated
- [ ] `migrate_old.py` removed
- [ ] `src/fabric_api/tableau/` and `src/fabric_api/base/` removed
