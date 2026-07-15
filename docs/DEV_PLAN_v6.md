<!-- DOC-SHINY-BANNER -->
![Documentation](https://img.shields.io/badge/Documentation-Shiny_Style-0A66C2?style=flat-square&logo=readthedocs&logoColor=white)
![Maintained](https://img.shields.io/badge/Maintained-2026-2EA44F?style=flat-square&logo=github&logoColor=white)
![Navigation](https://img.shields.io/badge/Navigation-Quick_Access-6F42C1?style=flat-square&logo=bookstack&logoColor=white)
# Development Plan — v6.0.0

> **Qlik → Power BI Migration Toolkit**
> Target: Q2–Q3 2026 · Version: 6.0.0 · Builds on v5.0.0 (Pipeline Hardening Release)
> Theme: **"Make It Actually Work End-to-End"**

---

## Current State (post v5.0.0)

| Area | Status | Details |
|------|--------|---------|
| Architecture | ✅ Clean | `qlik_export/` + `powerbi_import/` canonical, `src/fabric_api/` shim, 0 `sys.path` hacks |
| Tests | ✅ ~620 pass | 85+ new tests in v5 (format_adapter, CLI, import_to_powerbi) |
| Naming | ✅ 99% done | `adapt_qlik_for_generation`, `source_file`, ~12 low-priority `tableau` refs remain |
| Pipeline | ⚠️ Crashes on real files | `ExtractionOrchestrator` constructor arg mismatch (I4), intermediate JSON key mismatch (I3) |
| Pages | ❌ Single page only | All visuals on one page, 10/20 visual limit, `sheets.json` ignored |
| Load scripts | ❌ Not wired | `qlik_script_converter.py` exists but never called from pipeline |
| DAX depth | ⚠️ 175+ mappings, gaps | Variable expansion ($), TOTAL qualifier, nested Aggr, complex set analysis all missing |
| Standalone tools | ❌ 0/28 integrated | `tools/migration/` scripts produce standalone output, never consumed by pipeline |
| TMDLGenerator | ⚠️ Duplicated | Class-based (1607 lines) vs function-based (3561 lines) — not consolidated |
| Visual fidelity | ⚠️ Basic | No filters, sort, conditional formatting, slicer config, bookmarks in output |
| Version sync | ⚠️ Misaligned | `pyproject.toml` 5.0.0, `powerbi_import/__init__.py` 1.0.0, `qlik_export/__init__.py` 1.0.0 |

### v5 Completion Summary

| v5 Phase | Status | What's Done | What Remains |
|----------|--------|-------------|--------------|
| 1 — Test Coverage | ✅ Done | 85+ tests, 3 new suites | — |
| 2 — TMDLGenerator Consolidation | ❌ Not started | — | Full porting + shim (8-12h) |
| 3 — Format Adapter Hardening | ✅ Partial | Rename, validation, logging | Missing object types (hierarchies from drill-groups, filters from filterpanes, bookmarks) |
| 4 — Pipeline Robustness | ✅ Partial | sys.path removed, `--validate`, JSON fix | Progress indicators, ~12 tableau refs |
| 5 — Documentation Refresh | ❌ Not started | — | README, technical docs, examples |
| 6 — Dead Code Cleanup | ❌ Not started | — | Delete `src/fabric_api/visual_generator.py`, consolidate shim |

### GAP_ANALYSIS Summary (71 gaps)

| Severity | Count | Key Examples |
|----------|-------|-------------|
| **CRITICAL** | 9 | Pipeline crash (I4), JSON key mismatch (I3), single page (C1), 10-vis limit (E1), load scripts not wired (B1), preceding LOAD (B4), $() expansion (D1), variable-as-measure (D10), standalone tools (I1) |
| **HIGH** | 18 | QVD stub (A5), INLINE/JOIN/CONCATENATE in scripts (B3/B5/B6), composite models (C2), calc groups (C3), nested Aggr (D3), TOTAL qualifier (D5), filters/sort/slicers (E3-E6), bookmarks (F1), theme integration (G1) |
| **MEDIUM** | 30 | Import mode (A1), M parameters (A2), display folders (C4), descriptions (C5), per-visual bindings (E13), conditional formatting (E4), number formats (G3) |
| **LOW** | 14 | Gateway config (A4), sensitivity labels (H1), mobile layout (E12) |

---

## Phase 1 — Fix P0 Pipeline Blockers (Priority: **CRITICAL**)

The pipeline currently crashes on any real QVF file. These 5 fixes make end-to-end migration functional.

### 1.1 Fix `ExtractionOrchestrator` constructor call _(GAP I4)_

`migrate.py` line ~48 passes 2 args; the class takes 1.

| File | Current | Fix |
|------|---------|-----|
| `migrate.py` | `ExtractionOrchestrator(qlik_file, output_dir)` | Match constructor signature: pass `qlik_file` via method call |
| `qlik_export/extraction_orchestrator.py` | `__init__(self, output_dir)` | Add `qlik_file` parameter or document the correct call sequence |

**Test:** `python migrate.py examples/qlik/sample.json --dry-run` must not crash.

### 1.2 Fix intermediate JSON key mapping _(GAP I3)_

`load_intermediate_json()` loads 11 files keyed as `datasources`, `measures`, etc. But `run_generation()` reads `data.get("bim_model")`, `data.get("power_query_script")` — keys that don't exist.

| Task | Detail |
|------|--------|
| Inventory `run_generation()` parameter expectations | Map each `data.get(...)` call to the correct intermediate JSON key |
| Fix `run_generation()` or the key mapping dict | Either rename keys in `load_intermediate_json()` output or update `run_generation()` argument resolution |
| Add integration test | Load sample JSON dir → call `run_generation()` → verify output is non-empty |

### 1.3 Generate multi-page reports from `sheets.json` _(GAP C1/E2)_

Currently `_write_pbir_definition()` creates a single "Page 1". Qlik apps typically have 5-15 sheets.

| Task | Detail |
|------|--------|
| Parse `sheets.json` | Each sheet → one PBI page with `displayName` from sheet title |
| Map visuals to pages | Use sheet ID / visualization `sheetId` to assign visuals to correct page |
| Write per-page `page.json` | One `pages/<pageN>/page.json` per sheet with its visual containers |
| Fallback | If `sheets.json` is empty, create one page with all visuals (current behavior) |

### 1.4 Remove 10/20 visual limit _(GAP E1)_

| File | Current | Fix |
|------|---------|-----|
| `tmdl_generator.py` L499 | `visualizations[:10]` | Remove slice — use all |
| `visual_generator.py` | 20-visual limit | Remove slice — use all |

### 1.5 Wire `qlik_script_converter.py` into extraction pipeline _(GAP B1)_

The converter exists (413 lines, 30 function mappings) but is never called.

| Task | Detail |
|------|--------|
| Call from `extraction_orchestrator.py` | After extracting `loadscript.json`, parse it and enrich `datasources.json` with M queries |
| Merge script-derived datasources | Load script parsing may discover tables not in QVF metadata — merge into datasource list |
| Handle parse failures gracefully | Log warning, keep metadata-only datasources as fallback |

**Phase 1 Definition of Done:**
- [ ] `python migrate.py sample.qvf --output-dir out` completes without crash
- [ ] Output contains N pages (matching input sheet count)
- [ ] All visuals present in output (no truncation)
- [ ] Datasources populated from both metadata and load script
- [ ] 5+ integration tests validating end-to-end flow

**Estimated effort:** 12-16 hours

---

## Phase 2 — DAX Accuracy & Expression Depth (Priority: **HIGH**)

The DAX converter handles 175+ functions but misses critical patterns that affect every real Qlik app.

### 2.1 Implement dollar-sign variable expansion _(GAP D1/D10)_

Qlik `$(vVariable)` in expressions must be resolved before DAX conversion.

| Task | Detail |
|------|--------|
| Build variable resolution table | Load `variables.json` → dict of `{name: definition}` |
| Expand `$(...)` recursively | Replace `$(vName)` with the variable definition (max depth 10 to prevent infinite loops) |
| Handle `$(=expression)` | Dollar-sign with `=` prefix evaluates at load time — inline the expression |
| Run expansion before DAX conversion | Insert as first step in `convert_qlik_expression_to_dax()` |
| Convert variable-as-measure | Variables whose definitions are aggregation expressions → DAX measures |
| Convert variable-as-parameter | Variables whose definitions are static values → M parameters or TMDL measures |

### 2.2 Implement TOTAL qualifier _(GAP D5)_

| Qlik | DAX | Rule |
|------|-----|------|
| `Sum(TOTAL Sales)` | `CALCULATE(SUM('T'[Sales]), REMOVEFILTERS())` | Ignore all dimensions |
| `Sum(TOTAL <Dim1> Sales)` | `CALCULATE(SUM('T'[Sales]), ALLEXCEPT('T', 'T'[Dim1]))` | Keep only named dimensions |
| `Count(TOTAL DISTINCT Region)` | `CALCULATE(DISTINCTCOUNT('T'[Region]), REMOVEFILTERS())` | With aggregation variant |

### 2.3 Fix `Sum(If(...))` → `CALCULATE` pattern _(GAP D6)_

| Qlik | Current (wrong) | Correct DAX |
|------|-----------------|-------------|
| `Sum(If(Region="North", Sales))` | `SUM(IF(Region="North", Sales))` ❌ | `CALCULATE(SUM('T'[Sales]), 'T'[Region] = "North")` |
| `Sum(If(Year>2020, Amount, 0))` | `SUM(IF(Year>2020, Amount, 0))` ❌ | `SUMX(FILTER('T', 'T'[Year] > 2020), 'T'[Amount])` |

Detection: regex for `Sum\s*\(\s*If\s*\(`, `Avg\s*\(\s*If\s*\(`, etc. Convert based on inner condition structure.

### 2.4 Add `Concat()` → `CONCATENATEX()` _(GAP D9)_

| Qlik | DAX |
|------|-----|
| `Concat(ProductName, ', ')` | `CONCATENATEX(VALUES('T'[ProductName]), 'T'[ProductName], ", ")` |
| `Concat(DISTINCT Region, '; ', Region)` | `CONCATENATEX(VALUES('T'[Region]), 'T'[Region], "; ", 'T'[Region], ASC)` |

### 2.5 Improve nested Aggr() handling _(GAP D3)_

Current `_convert_aggr()` uses a flat regex → broken DAX for non-trivial cases.

| Task | Detail |
|------|--------|
| Implement bracket-matching parser | Count `(` and `)` to find the correct closing paren |
| Extract inner expression + dimensions | `Aggr(expr, dim1, dim2)` → `ADDCOLUMNS(SUMMARIZE(VALUES('T'[dim1], 'T'[dim2])), "Result", expr)` |
| Handle nested Aggr | Recursive: convert inner Aggr first, then outer |
| Integrate `migrate_advanced_aggregations.py` patterns | Port the confidence-scored patterns into `dax_converter.py` |

### 2.6 Expand set analysis parser _(GAP D2)_

| Pattern | Current | Needed |
|---------|---------|--------|
| `{<Year={2024}>}` | ✅ | — |
| `{<Year={2024}, Region={"North"}>}` | ✅ | — |
| `{<Region={"North"}-{"Alaska"}>}` | ❌ | Set subtraction → EXCEPT filter |
| `{<Year=Year+{2024}>}` | ❌ | Set union → extend filter |
| `{1<Year={2024}>}` | ❌ | `1` → ALL then apply modifier |
| `{$<Year={2024}>}` | ❌ | `$` → current selection ∩ modifier |

**Phase 2 Definition of Done:**
- [ ] `$(vVar)` expanded in all expressions before DAX conversion
- [ ] TOTAL qualifier correctly generates CALCULATE + REMOVEFILTERS/ALLEXCEPT
- [ ] `Sum(If(...))` pattern produces valid CALCULATE or SUMX
- [ ] `Concat()` → `CONCATENATEX()` works with separator and sort
- [ ] Nested Aggr produces valid DAX (up to 2 levels)
- [ ] Set analysis subtraction/union operators handled
- [ ] 30+ new unit tests in `test_dax_converter.py`

**Estimated effort:** 16-20 hours

---

## Phase 3 — Integrate Standalone Tools into Pipeline (Priority: **HIGH**)

28 migration tools in `tools/migration/` produce valuable output but none feed the pipeline.

### 3.1 Integrate theme generation _(GAP G1)_

| Task | Detail |
|------|--------|
| Call `migrate_theme.py` logic from extraction | Extract color palette from QVF/JSON into `app_metadata.json` theme section |
| Place `theme.json` into PBIR output | `<Report>/StaticResources/SharedResources/BaseThemes/CY24SU11.json` |
| Reference in `report.json` | Add `themeCollection.customTheme` reference |

### 3.2 Integrate variable migration _(GAP D10/I1)_

| Task | Detail |
|------|--------|
| Call `migrate_qlik_variables.py` logic from format adapter | Variables with aggregation expressions → measures list |
| Variables with static values → M parameters | Generate TMDL `expression` block for M parameters |
| Dollar-sign expansion before DAX | Use the resolution table from Phase 2.1 |

### 3.3 Integrate Section Access / RLS _(GAP I1)_

| Task | Detail |
|------|--------|
| Call `migrate_section_access.py` logic during generation | Parse load script for `Section Access;` block |
| Generate RLS roles in TMDL | `_write_roles_tmdl()` already supports this — wire the input |
| Generate USERPRINCIPALNAME() filters | Map Qlik NTNAME/USERID to `USERPRINCIPALNAME()` in filterExpression |

### 3.4 Consolidate duplicate DAX converters _(GAP I2)_

| File | Current | Fix |
|------|---------|-----|
| `qlik_migrator.py` | `convert_qlik_expression_to_dax()` — 11 basic mappings | Replace with call to `dax_converter.convert_expression()` |
| `qlik_model_converter.py` | `_qlik_expr_to_dax()` — 7 basic mappings | Replace with call to `dax_converter.convert_expression()` |
| `dax_converter.py` | 175+ mappings — canonical engine | Add public entry point `convert_expression(qlik_expr, context=None)` |

**Phase 3 Definition of Done:**
- [ ] Theme colors from Qlik app appear in generated PBI project
- [ ] Variables with aggregation expressions become DAX measures
- [ ] Section Access → RLS roles generated in TMDL (when present in load script)
- [ ] Only one DAX converter path exists (all callers use `dax_converter.py`)
- [ ] 15+ integration tests

**Estimated effort:** 12-16 hours

---

## Phase 4 — Visual Report Fidelity (Priority: **MEDIUM**)

The generated visuals have correct types but lack interactive features that make them usable.

### 4.1 Per-visual dimension/measure bindings _(GAP E13)_

| Task | Detail |
|------|--------|
| Extract per-visual dims/measures from Qlik visualization | Each visualization has `qHyperCubeDef.qDimensions` and `qMeasures` |
| Store in `visualizations.json` | Add `dimensions` and `measures` arrays per visualization |
| Use in `visual_generator.py` | Replace global fallback with per-visual bindings |
| Distribute to correct data roles | dims[0] → Category, dims[1] → Series (not ALL dims to ALL roles) |

### 4.2 Visual-level filters _(GAP E3)_

| Task | Detail |
|------|--------|
| Extract dimension limits from visualization | Qlik `qStateCounts`, limit counts, show-others |
| Generate `filters` array in visual container | PBI visual `filters` with `Basic`/`Advanced` filter types |

### 4.3 Sort order preservation _(GAP E5)_

| Qlik Sort | PBI Equivalent |
|-----------|---------------|
| By expression | `sortBy` in visual query state |
| By frequency | Sort by count measure |
| By alphabetical | sortDirection: ascending/descending |
| By load order | (no direct equivalent — preserve as default) |

### 4.4 Slicer configuration _(GAP E6)_

| Qlik Filter Pane Config | PBI Slicer Equivalent |
|--------------------------|----------------------|
| Single field, list | `slicer.mode: Basic`, `slicer.type: List` |
| Single field, dropdown | `general.filter.type: Dropdown` |
| Date range | `slicer.type: Range`, `slicer.rangeType: DateTime` |
| Multi-select | `singleSelect: false` |
| Search enabled | `search.enabled: true` |

### 4.5 Bookmark generation _(GAP F1)_

| Task | Detail |
|------|--------|
| Read `bookmarks.json` | Already extracted — `id`, `name`, `selections` |
| Generate `bookmarks` array in `report.json` | PBI bookmarks with displayName, explorationState |
| Map selections → filter state | Qlik field selections → PBI filter values |

**Phase 4 Definition of Done:**
- [ ] Each visual binds to its own dimensions/measures (not global)
- [ ] Visual-level filters generated for visuals with dimension limits
- [ ] Sort orders from Qlik preserved in visual query state
- [ ] Slicers have correct mode (list/dropdown/range) and selection type
- [ ] Bookmarks present in report.json with selection state
- [ ] 20+ tests for visual generation features

**Estimated effort:** 14-18 hours

---

## Phase 5 — Load Script Deep Conversion (Priority: **MEDIUM**)

The script converter handles basic `LOAD ... FROM file` but misses Qlik-specific patterns.

### 5.1 Preceding / stacked LOAD _(GAP B4)_

```qlik
// Qlik pattern:
LOAD *, Date(Date#(DateField, 'YYYY-MM-DD'), 'DD/MM/YYYY') as FormattedDate;
LOAD * FROM DataSource.qvd (qvd);
```

Fix `parse_qlik_load()` splitting logic to detect stacked LOADs (`;` between them, not `\n`).

### 5.2 CONCATENATE → `Table.Combine()` _(GAP B5)_

| Qlik | M |
|------|---|
| `CONCATENATE(Orders) LOAD * FROM Returns.qvd` | Append source `Returns` to existing query `Orders`: `Table.Combine({Orders, Source})` |

### 5.3 JOIN in load script → M Join _(GAP B6)_

| Qlik | M |
|------|---|
| `LEFT JOIN(Orders) LOAD CustID, CustName FROM Customers.csv` | `Table.NestedJoin(Orders, "CustID", Customers, "CustID", "Cust", JoinKind.LeftOuter)` + Expand |

### 5.4 INLINE LOAD → `#table()` _(GAP B3)_

```qlik
RegionMap:
LOAD * INLINE [
  Code, Region
  N, North
  S, South
];
```
→ `#table({"Code", "Region"}, {{"N", "North"}, {"S", "South"}})`

### 5.5 MAPPING LOAD + ApplyMap → Table.Join _(GAP B8)_

| Qlik | M / DAX |
|------|---------|
| `MAPPING LOAD Key, Value FROM map.csv` | M: staging query (not enabled for load) |
| `ApplyMap('Map', Field, 'Default')` | DAX: `LOOKUPVALUE('Map'[Value], 'Map'[Key], [Field], "Default")` |

**Phase 5 Definition of Done:**
- [ ] Stacked/preceding LOADs parsed correctly (2-level)
- [ ] CONCATENATE produces `Table.Combine()` in M
- [ ] LEFT/INNER JOIN in script → `Table.NestedJoin()` in M
- [ ] INLINE LOAD → `#table()` in M
- [ ] MAPPING LOAD → staging query + LOOKUPVALUE in DAX
- [ ] 25+ tests for script conversion patterns

**Estimated effort:** 14-18 hours

---

## Phase 6 — Complete v5 Leftovers + Housekeeping (Priority: **MEDIUM-LOW**)

### 6.1 TMDLGenerator consolidation _(v5 Phase 2)_

| Step | Detail |
|------|--------|
| Port deployment features | `generate_deployment_config()`, `generate_sensitivity_label()`, `generate_refresh_schedule()` → `powerbi_import/deploy/` |
| Port visual/project features | `generate_theme_json()`, `create_pbi_project_from_migration()` → `powerbi_import/pbip_generator.py` |
| Reduce `src/fabric_api/tmdl_generator.py` | Thin shim wrapping `powerbi_import` functions |
| Update tests | All imports from canonical locations |

### 6.2 Dead code cleanup _(v5 Phase 6)_

| File | Action |
|------|--------|
| `src/fabric_api/visual_generator.py` (847 lines) | **Delete** — `__init__.py` already re-exports from `powerbi_import` |
| 13 individual shim modules | **Delete** — `__init__.py` handles all re-exports |
| `test_phase5_modules.py` (257 lines) | **Replace** with real behavioral tests or delete |

### 6.3 Version synchronization

| File | Current | Target |
|------|---------|--------|
| `pyproject.toml` | `5.0.0` | `6.0.0` |
| `src/fabric_api/__init__.py` | `5.0.0` | `6.0.0` |
| `powerbi_import/__init__.py` | `1.0.0` | `6.0.0` |
| `qlik_export/__init__.py` | `1.0.0` | `6.0.0` |

### 6.4 Documentation refresh _(v5 Phase 5)_

| Target | Issue | Fix |
|--------|-------|-----|
| `README.md` | Shows `src/fabric_api/` as canonical | Rewrite structure tree |
| `README.md` | Programmatic usage: `from fabric_api import ...` | Update to `from qlik_export/powerbi_import import ...` |
| `README.md` | 9 visual types in coverage table | Update to 60+ |
| `docs/technical/*.md` | References to old paths | Audit and fix |
| `MAPPING_REFERENCE.md` | Import paths | Verify |

### 6.5 Progress indicators _(v5 Phase 4.4)_

```
[1/4] Extracting from app.qvf...                    (2.1s)
[2/4] Parsing load script → Power Query M...         (0.8s)
[3/4] Adapting to generation format...                (0.3s)
[4/4] Generating .pbip project (3 pages, 47 visuals) (1.8s)
✓ Migration complete in 5.0s → output/my_app/
```

### 6.6 Remaining `tableau` naming cleanup (~12 refs)

| Location | Current | Fix |
|----------|---------|-----|
| `migrate.py` L826-827 | `getattr(config, 'tableau_file', None)` | `getattr(config, 'source_file', None)` |
| `powerbi_import/wizard.py` L180 | `tableau_file=config[...]` | `source_file=config[...]` |
| `qlik_export/datasource_extractor.py` | `map_tableau_to_powerbi_type` alias | Add deprecation warning |

**Phase 6 Definition of Done:**
- [ ] Single TMDLGenerator implementation in `powerbi_import/`
- [ ] `src/fabric_api/` reduced to 2 files: `__init__.py` + `tmdl_generator.py` shim
- [ ] All `__version__` strings read `6.0.0`
- [ ] README accurately describes current architecture
- [ ] CLI shows progress with elapsed time
- [ ] Zero `tableau` references in functional code paths

**Estimated effort:** 10-14 hours

---

## Execution Schedule

```
Phase 1    ─── Fix P0 pipeline blockers ──────────── Week 1–2   (CRITICAL)
 ├─ 1.1  ExtractionOrchestrator constructor fix
 ├─ 1.2  Intermediate JSON key mapping fix
 ├─ 1.3  Multi-page report generation
 ├─ 1.4  Remove visual limits
 └─ 1.5  Wire load script converter

Phase 2    ─── DAX accuracy & expression depth ───── Week 2–4   (HIGH)
 ├─ 2.1  Dollar-sign variable expansion
 ├─ 2.2  TOTAL qualifier → CALCULATE
 ├─ 2.3  Sum(If) → CALCULATE/SUMX
 ├─ 2.4  Concat → CONCATENATEX
 ├─ 2.5  Nested Aggr bracket matching
 └─ 2.6  Set analysis operators (+, -, *, P(), E())

Phase 3    ─── Integrate standalone tools ────────── Week 3–5   (HIGH)
 ├─ 3.1  Theme → PBIR output
 ├─ 3.2  Variables → measures/parameters
 ├─ 3.3  Section Access → RLS in TMDL
 └─ 3.4  Consolidate DAX converter callers

Phase 4    ─── Visual report fidelity ────────────── Week 5–6   (MEDIUM)
 ├─ 4.1  Per-visual dimension/measure bindings
 ├─ 4.2  Visual-level filters
 ├─ 4.3  Sort order preservation
 ├─ 4.4  Slicer configuration
 └─ 4.5  Bookmark generation

Phase 5    ─── Load script deep conversion ───────── Week 6–8   (MEDIUM)
 ├─ 5.1  Preceding/stacked LOAD
 ├─ 5.2  CONCATENATE → Table.Combine
 ├─ 5.3  JOIN → Table.NestedJoin
 ├─ 5.4  INLINE LOAD → #table()
 └─ 5.5  MAPPING LOAD + ApplyMap

Phase 6    ─── v5 leftovers + housekeeping ───────── Week 8–9   (MEDIUM-LOW)
 ├─ 6.1  TMDLGenerator consolidation
 ├─ 6.2  Dead code cleanup
 ├─ 6.3  Version sync → 6.0.0
 ├─ 6.4  Documentation refresh
 ├─ 6.5  CLI progress indicators
 └─ 6.6  Remaining tableau naming cleanup
```

---

## Success Metrics

| Metric | v5.0.0 Baseline | v6.0.0 Target |
|--------|-----------------|---------------|
| Pipeline completes on sample QVF | ❌ Crashes | ✅ End-to-end |
| Pages generated per multi-sheet app | 1 | N (matching sheet count) |
| Visuals per page limit | 10 | Unlimited |
| DAX functions mapped | 175 | 200+ |
| Dollar-sign variables resolved | 0% | 100% |
| Standalone tools integrated | 0/28 | 4/28 (highest impact) |
| Tests passing | ~620 | 750+ |
| Modules with zero test coverage | 6 | 3 |
| `__version__` alignment | 3 values | 1 (6.0.0 everywhere) |

---

## Risk Register

| Risk | Impact | Mitigation |
|------|--------|------------|
| ExtractionOrchestrator fix may reveal deeper QVF parsing issues | HIGH | Add defensive fallback: if QVF parsing fails, try JSON-dict path |
| Dollar-sign expansion may cause infinite recursion | MEDIUM | Cap recursion depth at 10; detect circular refs and abort with warning |
| Multi-page generation may break existing tests | MEDIUM | Run full test suite after each sub-task; snapshot comparison |
| TMDLGenerator consolidation may lose features | MEDIUM | Inventory comparison table (v5 §2.1) before any deletion |
| Bracket-matching parser for Aggr() may be fragile | LOW | Implement iterative char-by-char scanner, not regex |

---

## Appendix: Files to Modify per Phase

### Phase 1
| File | Changes |
|------|---------|
| `migrate.py` | Fix ExtractionOrchestrator call, fix JSON key mapping, add multi-page generation call |
| `qlik_export/extraction_orchestrator.py` | Fix constructor, wire `qlik_script_converter` |
| `powerbi_import/tmdl_generator.py` | Remove `[:10]` slice, iterate sheets for pages |
| `powerbi_import/visual_generator.py` | Remove 20-visual limit |

### Phase 2
| File | Changes |
|------|---------|
| `qlik_export/dax_converter.py` | $() expansion, TOTAL, Sum(If), Concat, Aggr bracket parser, set operators |
| `tests/test_dax_converter.py` | 30+ new tests (create if not exists) |

### Phase 3
| File | Changes |
|------|---------|
| `qlik_export/format_adapter.py` | Variable → measure/parameter classification |
| `powerbi_import/tmdl_generator.py` | Theme placement, RLS from Section Access |
| `powerbi_import/pbip_generator.py` | Theme reference in report.json |
| `qlik_export/qlik_migrator.py` | Replace local DAX converter with `dax_converter.py` |
| `qlik_export/qlik_model_converter.py` | Replace local DAX converter with `dax_converter.py` |

### Phase 4
| File | Changes |
|------|---------|
| `qlik_export/extraction_orchestrator.py` | Per-visual dims/measures extraction |
| `powerbi_import/visual_generator.py` | Filters, sort, slicer config, proper role distribution |
| `powerbi_import/tmdl_generator.py` | Bookmark generation in report.json |

### Phase 5
| File | Changes |
|------|---------|
| `qlik_export/qlik_script_converter.py` | Stacked LOAD, CONCATENATE, JOIN, INLINE, MAPPING LOAD |
| `tests/test_qlik_script_converter.py` | 25+ new tests (create if not exists) |

### Phase 6
| File | Changes |
|------|---------|
| `src/fabric_api/tmdl_generator.py` | Reduce to shim |
| `src/fabric_api/visual_generator.py` | **Delete** |
| `powerbi_import/__init__.py` | Version → 6.0.0 |
| `qlik_export/__init__.py` | Version → 6.0.0 |
| `pyproject.toml` | Version → 6.0.0 |
| `README.md` | Rewrite architecture section |
| `migrate.py` | Progress indicators, remaining tableau refs |

