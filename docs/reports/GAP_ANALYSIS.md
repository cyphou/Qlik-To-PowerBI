# QlikToPowerBI Migration Toolkit — Comprehensive Gap Analysis

**Date:** 2026-02-23  
**Auditor:** GitHub Copilot  
**Scope:** Full codebase review of all core modules, standalone migration scripts, and output quality

---

## Executive Summary

The toolkit has a **solid foundational architecture**: a 2-step pipeline (extract → generate), 11 intermediate JSON files, 10 core Python modules, and 28 standalone migration scripts. The TMDL/PBIR output structure targets PBI Project 4.0 format correctly. However, significant gaps remain in **data transformation depth**, **visual report fidelity**, **DAX edge cases**, and **end-to-end integration** between the standalone tools and the core pipeline.

| Category | Implemented | Missing/Partial | Severity Distribution |
|----------|------------|-----------------|----------------------|
| A. Data Sources & Connections | 25 connectors | 6 gaps | 1 HIGH, 3 MEDIUM, 2 LOW |
| B. Data Transformations (M) | 40+ transforms | 12 gaps | 3 CRITICAL, 4 HIGH, 5 MEDIUM |
| C. Data Model (TMDL) | Tables, columns, relationships, RLS, hierarchies, calendar | 8 gaps | 1 CRITICAL, 3 HIGH, 4 MEDIUM |
| D. Calculated Fields (DAX) | 175+ function mappings, set analysis, Aggr | 10 gaps | 2 CRITICAL, 4 HIGH, 4 MEDIUM |
| E. Reports & Visuals | 60+ types, query state, grid layout | 14 gaps | 2 CRITICAL, 5 HIGH, 7 MEDIUM |
| F. Dashboards & Interactivity | Bookmarks extracted | 8 gaps | 1 HIGH, 4 MEDIUM, 3 LOW |
| G. Formatting & Theming | Theme tool exists (standalone) | 6 gaps | 1 HIGH, 3 MEDIUM, 2 LOW |
| H. Deployment & Operations | Fabric deployer exists | 7 gaps | 2 MEDIUM, 5 LOW |

**Total unique gaps identified: 71**  
**Critical: 9 | High: 18 | Medium: 30 | Low: 14**

---

## A. DATA SOURCES & CONNECTIONS

### What's Implemented

`m_query_generator.py` (597 lines) supports **25 connector types** with full `let ... in` M queries:

| Connector | Status | Notes |
|-----------|--------|-------|
| Excel (.xlsx/.xls) | ✅ Full | With type step & promoted headers |
| CSV/Text | ✅ Full | Delimiter & encoding support |
| SQL Server | ✅ Full | Schema/table resolution |
| PostgreSQL | ✅ Full | Schema/table resolution |
| Oracle | ✅ Full | Schema parsing from table name |
| MySQL | ✅ Full | |
| BigQuery | ✅ Full | BillingProject support |
| Snowflake | ✅ Full | Warehouse/database/schema |
| Teradata | ✅ Full | |
| SAP HANA | ✅ Full | |
| Redshift | ✅ Full | |
| Databricks | ✅ Full | HTTP path + catalog |
| Spark | ✅ Basic | |
| Azure SQL | ✅ Full | |
| Azure Synapse | ✅ Full | |
| Google Sheets | ✅ Basic | Web.BrowserContents workaround |
| SharePoint | ✅ Full | |
| JSON | ✅ Basic | Single-level only |
| XML | ✅ Basic | |
| PDF | ✅ Basic | |
| Salesforce | ✅ Full | |
| Web | ✅ Basic | |
| QVD | ⚠️ Stub | Falls back to CSV — note in comment |
| ODBC | ✅ Full | DSN-based |
| OLE DB | ✅ Full | |

### Gaps

| # | Gap | Severity | Detail |
|---|-----|----------|--------|
| A1 | **Import mode vs DirectQuery** — no mode selection | **MEDIUM** | All generated M queries assume Import mode. `_gen_m_sql_server` etc. never emit `[EnableFolding=true]` or DirectQuery hints. The TMDL partition `mode: import` is hardcoded. |
| A2 | **Parameterized data sources** — no M parameters | **MEDIUM** | No support for `#"Server Name"` parameters in M queries. Qlik uses variables for server/path; PBI uses M parameters. `migrate_qlik_variables.py` generates M parameter *definitions* but they are **not injected** into the M queries produced by `m_query_generator.py`. |
| A3 | **Incremental refresh** — completely missing | **MEDIUM** | No `refreshPolicy` in TMDL output. Qlik apps with partial reload have no equivalent generated. |
| A4 | **Gateway configuration** — completely missing | **LOW** | No gateway data source mapping or `connectionDetails` in TMDL. Post-migration manual step. |
| A5 | **QVD native reading** — stub only | **HIGH** | `_gen_m_qvd()` emits a comment saying "requires Qlik QVD connector or conversion to CSV". `migrate_qvd.py` generates a Qlik export script to CSV, but the pipeline doesn't auto-invoke it. For Qlik-to-PBI migration, QVD is an extremely common source. |
| A6 | **Custom SQL / native query passthrough** — missing | **LOW** | Qlik `SQL SELECT` statements from load scripts are not converted to `Value.NativeQuery()` in M. The script converter (`qlik_script_converter.py`) detects `source_type='sql'` but produces a placeholder `Sql.Database("ServerName", "DatabaseName")`. |

---

## B. DATA TRANSFORMATIONS (Power Query M)

### What's Implemented

**`m_query_builder.py`** (582 lines): 40+ chainable transform functions + `inject_m_steps()` engine:
- Column ops: rename, remove, select, duplicate, reorder, split, merge
- Value ops: replace, replace_nulls, trim, clean, upper/lower/proper, fill_down/up
- Filter ops: filter_values, exclude, filter_range, filter_nulls, filter_contains, distinct, top_n
- Aggregate: group_by (8 aggregation types)
- Pivot: unpivot, unpivot_other, pivot
- Join: inner/left/right/full/leftanti/rightanti with auto-expand
- Union: append_tables, wildcard_union
- Reshape: sort, transpose, add_index, skip/remove rows, promote/demote headers
- Calculated: add_custom_column, add_conditional_column

**`qlik_script_converter.py`** (413 lines): Parses Qlik LOAD statements and converts to M:
- Detects file sources (CSV, Excel, QVD), resident loads, inline, SQL
- Converts field expressions with aliases
- Applies WHERE clauses
- Maps ~30 Qlik functions → M equivalents

### Gaps

| # | Gap | Severity | Detail |
|---|-----|----------|--------|
| B1 | **Qlik load script → M pipeline not wired** | **CRITICAL** | `qlik_script_converter.py` exists but is **never called** from `extraction_orchestrator.py` or `migrate.py`. The loadscript is extracted to `loadscript.json` but never parsed into M queries. The 11 intermediate JSON `datasources.json` is populated from QVF metadata structure, not from actual script parsing. |
| B2 | **Resident loads** — stub/partial | **CRITICAL** | `qlik_script_converter.py` detects `RESIDENT` source type but generates `Source = ResidentTableName` which is invalid M. Should generate a reference to the query name in the same mashup. |
| B3 | **INLINE loads** — not converted | **HIGH** | Qlik `LOAD * INLINE [...]` data is detected but produces no M output. Should generate `#table(...)` or `Table.FromRows(...)`. |
| B4 | **Preceding LOAD** — completely missing | **CRITICAL** | Qlik's `LOAD expr1, expr2 ; LOAD * FROM source` (preceding load / stacked loads) pattern is not parsed. `parse_qlik_load()` splits on `\n(?=LOAD\s)` which breaks stacked loads. |
| B5 | **CONCATENATE** — not parsed | **HIGH** | Qlik `CONCATENATE(TableName) LOAD ...` is not handled. Should generate `Table.Combine()`. |
| B6 | **JOIN in load script** — not parsed | **HIGH** | Qlik `LEFT JOIN(Table) LOAD ...` / `INNER JOIN(Table) LOAD ...` in scripts is not handled. `m_query_builder.py` has `join_tables()` but it's not wired to the script parser. |
| B7 | **QUALIFY / UNQUALIFY** — not parsed | **MEDIUM** | Qlik `QUALIFY *; UNQUALIFY TableKey;` patterns are not parsed. Affects column naming in multi-table models. |
| B8 | **MAPPING LOAD + ApplyMap** — not converted | **HIGH** | Qlik `MAPPING LOAD` creates lookup tables used by `ApplyMap()`. These should become M `Table.Join()` + column selection, or PBI `LOOKUPVALUE()`. `dax_converter.py` maps `ApplyMap( → LOOKUPVALUE(` but argument parsing is incomplete. |
| B9 | **FOR EACH / Subroutines / SUB** — not parsed | **MEDIUM** | Qlik scripting constructs (`FOR EACH file IN filelist(...)`, `SUB LoadData`, `CALL LoadData`) are completely ignored. |
| B10 | **LET / SET variables in script** — not resolved | **MEDIUM** | Qlik `SET vPath = ...` / `LET vStart = ...` are extracted to `variables.json` but never substituted into load script expressions (dollar-sign expansion `$(vPath)`). |
| B11 | **WHERE clause conversion** — partial | **MEDIUM** | `qlik_script_converter.py` extracts WHERE clauses but passes them through `convert_qlik_function()` without proper M condition syntax conversion (e.g., Qlik `=` vs M `=`, Qlik `<>` vs M `<>`, string quoting). |
| B12 | **Complex transforms from Qlik script** — not inferred | **MEDIUM** | The 40+ transforms in `m_query_builder.py` are never automatically inferred from Qlik load script patterns (e.g., `LOAD DISTINCT`, `GROUP BY`, `ORDER BY`, `NOCONCATENATE`). |

---

## C. DATA MODEL (TMDL)

### What's Implemented

**`tmdl_generator.py`** (1259 lines) generates full PBI Project 4.0:

| Feature | Status | Code Location |
|---------|--------|---------------|
| `database.tmdl` | ✅ | `_write_database_tmdl()` — compatibilityLevel |
| `model.tmdl` | ✅ | `_write_model_tmdl()` — culture, defaultPowerBIDataSourceVersion, discourageImplicitMeasures, ref table entries, annotations |
| Table TMDL files | ✅ | `_write_table_tmdl()` — columns with dataType, formatString, lineageTag, summarizeBy, sourceColumn, dataCategory, isHidden, sortByColumn |
| Calculated columns | ✅ | `type: calculated` with DAX expression in column definition |
| Measures | ✅ | DAX expression + formatString + lineageTag |
| Hierarchies | ✅ | From Qlik drill-group dimensions (level name + column) |
| Relationships | ✅ | `_write_relationships_tmdl()` — fromColumn, toColumn, crossFilteringBehavior (oneDirection/bothDirections/automatic), isActive |
| Expressions (M) | ✅ | `_write_expressions_tmdl()` — shared Power Query with queryGroup |
| Partitions | ✅ | M expression source with mode (import) |
| RLS roles | ✅ | `_write_roles_tmdl()` — from Section Access, with modelPermission, tablePermission, filterExpression |
| Calendar table | ✅ | `generate_calendar_table()` — full M-generated Date table with 10 columns, time intelligence |
| Parameter tables | ✅ | `generate_parameter_table()` — GENERATESERIES + SELECTEDVALUE |
| Geographic dataCategory | ✅ | `infer_data_category()` — 17 patterns (country, city, lat/lon, etc.) |
| Data type inference | ✅ | `_infer_column_datatype()` — heuristic from column name suffixes |

### Gaps

| # | Gap | Severity | Detail |
|---|-----|----------|--------|
| C1 | **Multi-page reports** — only 1 page generated | **CRITICAL** | `_write_pbir_definition()` creates a single "Page 1". Qlik apps typically have multiple sheets → should become multiple PBI pages. `sheets.json` is extracted but never iterated to create separate pages. |
| C2 | **Composite models / DirectQuery** — not supported | **HIGH** | All partitions use `mode: import`. No support for `mode: directQuery` or dual/composite model mixing. |
| C3 | **Calculation groups** — completely missing | **HIGH** | No TMDL generation for calculation groups (e.g., time intelligence switching: YTD/QTD/MTD). These are common in advanced Qlik apps using set analysis patterns. |
| C4 | **Display folders** — missing | **MEDIUM** | No `displayFolder` property on columns or measures. Large Qlik apps with many measures need folder organization. |
| C5 | **Descriptions / annotations** — partial | **MEDIUM** | Table-level annotations are written. Column/measure `description` property is never emitted despite being available in Qlik metadata. |
| C6 | **Perspectives** — missing | **MEDIUM** | No `perspective` TMDL blocks. Less common but used in large enterprise Qlik apps. |
| C7 | **Translations / cultures** — missing | **MEDIUM** | Only one culture in model.tmdl. No `culture` TMDL file for multi-language Qlik apps. |
| C8 | **Aggregation tables** — missing | **HIGH** | No support for generating aggregation tables (Import over DirectQuery pattern). |

---

## D. CALCULATED FIELDS (DAX)

### What's Implemented

**`dax_converter.py`** (696 lines) — multi-phase converter:

| Phase | Feature | Status |
|-------|---------|--------|
| 1 | Operator conversion (AND→&&, OR→||, NOT) | ✅ |
| 2 | Structural: If/Then/Else/End → IF(), ElseIf nesting | ✅ |
| 3 | Match → SWITCH, Pick → SWITCH | ✅ |
| 4 | Set Analysis → CALCULATE (single/multi modifiers, {1<>} → ALL, empty set → REMOVEFILTERS) | ✅ |
| 5 | Aggr() → ADDCOLUMNS/SUMMARIZE | ⚠️ Partial |
| 6 | 175+ simple function replacements (regex-based) | ✅ |
| 7 | Alt → COALESCE | ✅ |
| 8 | Class → INT/DIVIDE bucketing | ✅ |
| 9 | RELATED() auto-insertion for calculated columns | ✅ |
| 10 | LOOKUPVALUE() for manyToMany | ✅ |
| 11 | Batch conversion (measures + dimensions) | ✅ |
| 12 | Format string conversion | ✅ (12 mappings) |
| 13 | Data type conversion | ✅ (12 type mappings) |

**Standalone tools:**
- `migrate_set_analysis.py` (710 lines): Advanced set analysis → CALCULATE with confidence scoring
- `migrate_advanced_aggregations.py` (778 lines): Aggr, running totals, moving averages, multi-level
- `migrate_inter_record_functions.py`: Guide for Peek/Previous/RowNo/Above/Below → DAX

### Gaps

| # | Gap | Severity | Detail |
|---|-----|----------|--------|
| D1 | **Dollar-sign expansion $()** — not resolved | **CRITICAL** | Qlik `$(vVariable)` in expressions is never expanded. The variable definitions are in `variables.json` but not substituted before DAX conversion. Example: `Sum({<Year=$(vCurrentYear)>} Sales)` stays as-is. |
| D2 | **Complex set analysis (multiple modifiers + operators)** — partial | **HIGH** | `_parse_set_modifiers()` handles `field={value}` and `field=` (empty → REMOVEFILTERS). Missing: set operators (`+`, `-`, `*`), P()/E() set identifiers, nested set expressions, inter-modifier logic (`<Year={2024}, Region={"North"}-{"Alaska"}>` — the subtraction). |
| D3 | **Nested Aggr()** — not handled | **HIGH** | `_convert_aggr()` does a simple regex replacement `Aggr( → ADDCOLUMNS(SUMMARIZE(VALUES(` without proper bracket matching. Nested `Aggr(Aggr(...))` produces invalid DAX. `migrate_advanced_aggregations.py` handles some patterns but is **not integrated** into `dax_converter.py`. |
| D4 | **Peek / Previous / Above / Below** — not in core converter | **HIGH** | Inter-record functions have regex mappings (`Above → EARLIER`, `RangeSum → SUM`) but these are **semantically incorrect**: Qlik `Above(Sum(Sales))` is a window function, not `EARLIER()`. The standalone guide in `migrate_inter_record_functions.py` describes LAG/OFFSET but is documentation-only, not automated. |
| D5 | **Total qualifier** — not converted | **HIGH** | Qlik `Sum(TOTAL Sales)`, `Sum(TOTAL <Dim1> Sales)` (ignore all/some dimensions) should become `CALCULATE(SUM(...), REMOVEFILTERS())` or `ALLEXCEPT()`. Not handled. |
| D6 | **Conditional aggregation pattern** — weak | **MEDIUM** | `Sum(If(Condition, Value, 0))` should ideally become `SUMX(FILTER(...), ...)` or `CALCULATE(SUM(...), ...)`. Currently the If→IF and Sum→SUM mappings produce `SUM(IF(...))` which is invalid (SUM expects a column, not an expression). |
| D7 | **Date#() / Num#() with format argument** — format ignored | **MEDIUM** | `Date#(expr, 'DD/MM/YYYY')` → `DATEVALUE(expr)` but the format parameter is discarded. |
| D8 | **Field value functions (FieldValue, FieldIndex, GetFieldSelections)** — missing | **MEDIUM** | No mapping for these Qlik functions which inspect current selections. |
| D9 | **String concatenation in aggregation context** — not handled | **MEDIUM** | Qlik `Concat(Field, ', ')` should become `CONCATENATEX()` in DAX. Not mapped. |
| D10 | **Variable-as-measure pattern** — not migrated | **CRITICAL** | Qlik variables used as measures (e.g., `=$(vSalesMeasure)` where `vSalesMeasure = Sum(Sales)`) are extracted to `variables.json` but **never converted to DAX measures or M parameters**. The `migrate_qlik_variables.py` tool generates parameter definitions but is **not integrated** into the pipeline. |

---

## E. REPORTS & VISUALS

### What's Implemented

**`visual_generator.py`** (669 lines):
- 60+ visual type mappings (Qlik type → PBI visual type)
- 30+ config templates with per-type axis, legend, data label settings
- Query state builder with role-based projections (VISUAL_DATA_ROLES: 30 types)
- Grid layout from Qlik cell coordinates (24-col grid + bounds)
- Title propagation from Qlik visualization

**`tmdl_generator.py`** visual output:
- PBIR format visual containers with $schema 2.5.0
- Proper position (x, y, z, width, height, tabOrder)
- queryState with dimension/measure projections per data role
- Named measure and inline aggregation support

### Gaps

| # | Gap | Severity | Detail |
|---|-----|----------|--------|
| E1 | **Only 10 visuals per page** — arbitrary limit | **CRITICAL** | `_write_pbir_definition()` at line 499: `for i, viz in enumerate(visualizations[:10])`. Similarly `visual_generator.py` limits to 20. Typical Qlik sheets have 15-30 objects. |
| E2 | **Single page only** — repeated from C1 | **CRITICAL** | All visuals dumped onto one page. Qlik sheets should map to separate PBI pages. |
| E3 | **Visual-level filters** — not generated | **HIGH** | No `filters` property on visual containers. Qlik visualizations often have per-object dimension/measure limits. |
| E4 | **Conditional formatting** — completely missing | **HIGH** | No visual `objects` properties for conditional formatting rules (color scales, rules, field-value-based). Qlik apps extensively use expression-based coloring. |
| E5 | **Sort orders** — not preserved | **HIGH** | Qlik dimension sort (by expression, by frequency, by load order) is lost. No `sortBy` in visual query state. |
| E6 | **Slicer configuration** — basic only | **HIGH** | Slicers get `mode: Basic` template but no: list vs dropdown vs range style, single vs multi select, search enabled, relative date slicer. |
| E7 | **Drill-through pages** — missing | **HIGH** | Qlik drill-down/drill-to actions are not converted to PBI drill-through page definitions. |
| E8 | **Tooltip pages** — missing | **MEDIUM** | No custom tooltip page generation. |
| E9 | **Page-level / report-level filters** — missing | **MEDIUM** | Only visual-level projections. No `filters` in page.json or report.json. |
| E10 | **Reference lines / trend lines** — missing | **MEDIUM** | No analytics pane configuration (constant lines, trend lines, min/max/average lines). |
| E11 | **Visual interactions** — missing | **MEDIUM** | No cross-filter / cross-highlight configuration between visuals. |
| E12 | **Mobile layout** — missing | **MEDIUM** | No phone layout definition in pages. |
| E13 | **Per-visual dimensions/measures** — partial | **MEDIUM** | `create_visual_container()` attempts `viz_dims = visualization.get("dimensions", dimensions)` but falls back to global dims/measures for all visuals when the visualization dict doesn't carry its own bindings — which is the common case since extraction doesn't reliably populate per-visual dims/measures. |
| E14 | **Text/image content** — not migrated | **MEDIUM** | `textbox` type is mapped but no text content is placed in the visual. Qlik text-image objects have HTML/markdown. |

---

## F. DASHBOARDS & INTERACTIVITY

### What's Implemented

- **Bookmarks extracted** to `bookmarks.json` (id, name, selections)
- Standalone `migrate_bookmarks.py` (150 lines): Extracts from QVF, generates migration guide (documentation only)
- Standalone `migrate_navigation.py` (479 lines): Extracts sheet actions from QVF, generates action button M code examples
- Standalone `migrate_alternate_states.py`: Documentation guide for alternate states → field parameters

### Gaps

| # | Gap | Severity | Detail |
|---|-----|----------|--------|
| F1 | **Bookmarks → PBI bookmarks** — extraction only, no generation | **HIGH** | `bookmarks.json` is produced but never consumed by `tmdl_generator.py`. No bookmark definitions in report.json output. |
| F2 | **Action buttons / page navigation** — not generated | **MEDIUM** | `migrate_navigation.py` produces documentation, not actual visual.json action button configs. |
| F3 | **Filter pane ↔ slicer sync** — not handled | **MEDIUM** | Qlik filter pane = multi-field slicer. PBI equivalent (slicer sync groups) not generated. |
| F4 | **Alternate states** — doc only | **MEDIUM** | `migrate_alternate_states.py` produces a markdown guide, no code generation. |
| F5 | **Current selections object** — ignored | **MEDIUM** | Qlik "current selections" box has no direct PBI equivalent. Not even documented in output. |
| F6 | **Q&A visual** — not generated | **LOW** | No Q&A or Smart Narrative visuals generated as replacements for Qlik NLP features. |
| F7 | **Decomposition tree** — mapped but not wired | **LOW** | `decompositionTree` is in VISUAL_TYPE_MAP and VISUAL_DATA_ROLES but never auto-selected from Qlik drill-group dimensions. |
| F8 | **Spotlight (focus mode)** — N/A | **LOW** | Not a migration concern per se — PBI has it built in. |

---

## G. FORMATTING & THEMING

### What's Implemented

- **Standalone `migrate_theme.py`** (299 lines): Extracts Qlik theme from QVF (color palettes), generates Power BI `theme.json` file and HTML preview
- `tmdl_generator.py` includes a `themeCollection.baseTheme` in report.json (CY24SU06)
- Format strings: 12 Qlik→DAX format mappings in `dax_converter.py`

### Gaps

| # | Gap | Severity | Detail |
|---|-----|----------|--------|
| G1 | **Theme not integrated into pipeline** | **HIGH** | `migrate_theme.py` is standalone. The generated `theme.json` is **not placed** into the PBIR output structure. It should go into `<Report>/StaticResources/SharedResources/BaseThemes/` or referenced in report.json. |
| G2 | **Conditional formatting (expression-based colors)** — missing | **MEDIUM** | Qlik uses expression-based coloring (`=If(Sales>1000, RGB(0,128,0), RGB(255,0,0))`). No equivalent PBI conditional formatting rules generated in visual objects. |
| G3 | **Number formatting** — limited | **MEDIUM** | Only 12 format string mappings. Missing: custom Qlik formats like `'#,##0;(#,##0)'` (negative in parens), `'R #,##0'` (currency prefix), `'0.0%'` variations. The fallback `re.sub(r'(hh?):mm', ...)` only handles time minutes. |
| G4 | **Font mapping** — missing | **MEDIUM** | Qlik custom fonts are not mapped to PBI font families. |
| G5 | **Visual-level colors** — not migrated | **LOW** | Per-visual data point colors, series colors from Qlik are not transferred to PBI visual objects. |
| G6 | **Background / border styling** — missing | **LOW** | Qlik object background colors and borders are lost. |

---

## H. DEPLOYMENT & OPERATIONS

### What's Implemented

- **`deployer.py`** (236 lines): Fabric REST API deployment (deploy_dataset, deploy_report, deploy_notebook, deploy_pipeline, batch deploy with dependency ordering)
- **`auth.py`**: Azure authentication (lazy-loaded, token-based)
- **`client.py`**: Fabric REST client
- **`validator.py`**: Artifact validation
- `migrate_power_automate.py`: Generates Power Automate flow foundations for refresh scheduling
- `migrate_section_access.py` (642 lines): Full Section Access → RLS migration with DAX filter generation, USERPRINCIPALNAME mapping, TMDL role generation

### Gaps

| # | Gap | Severity | Detail |
|---|-----|----------|--------|
| H1 | **Sensitivity labels** — not applied | **LOW** | No sensitivity label property in deployment. |
| H2 | **Endorsement (certified/promoted)** — not configured | **LOW** | No endorsement metadata in generated artifacts. |
| H3 | **Deployment pipeline config** — not generated | **MEDIUM** | `deployer.py` deploys to a single workspace. No dev→test→prod pipeline configuration. |
| H4 | **Scheduled refresh config** — not automated | **MEDIUM** | `migrate_power_automate.py` generates flow definitions but doesn't configure PBI scheduled refresh via REST API. |
| H5 | **RLS testing** — not automated | **LOW** | `migrate_section_access.py` generates roles but no automated test/validation of RLS filters. |
| H6 | **Incremental refresh policies** — missing | **LOW** | No `refreshPolicy` TMDL block. |
| H7 | **Workspace / capacity assignment** — not handled | **LOW** | No automation for assigning to Premium/Fabric capacity. |

---

## INTEGRATION GAPS (Cross-Cutting)

These are architectural issues that span multiple categories:

| # | Gap | Severity | Detail |
|---|-----|----------|--------|
| I1 | **Standalone tools not wired into pipeline** | **CRITICAL** | 28 scripts in `tools/migration/` (set analysis, variables, themes, section access, bookmarks, navigation, etc.) are **completely standalone**. None are called from `migrate.py` or `extraction_orchestrator.py`. The most impactful ones (`migrate_set_analysis.py`, `migrate_qlik_variables.py`, `migrate_theme.py`, `migrate_section_access.py`) should feed into the intermediate JSON or generation step. |
| I2 | **Duplicate converters** | **MEDIUM** | `qlik_migrator.py` has its own `convert_qlik_expression_to_dax()` (11 basic mappings) separate from the 175+ mapping engine in `dax_converter.py`. `qlik_model_converter.py` has `_qlik_expr_to_dax()` with another 7 basic mappings. These should use `dax_converter.py` exclusively. |
| I3 | **`load_intermediate_json()` mismatch** | **MEDIUM** | `migrate.py` calls `load_intermediate_json(json_dir)` which loads the 11 JSON files, but `run_generation()` passes `data.get("bim_model")`, `data.get("power_query_script")`, etc. These keys don't match the intermediate file names (`datasources`, `measures`, `dimensions`, `loadscript`...). The generation step likely receives `None` for most parameters. |
| I4 | **ExtractionOrchestrator constructor mismatch** | **HIGH** | `migrate.py` line 48: `ExtractionOrchestrator(qlik_file, output_dir)` passes 2 args, but the class constructor takes `output_dir` only: `__init__(self, output_dir: str = "output")`. This will crash at runtime. |
| I5 | **No end-to-end validation** | **MEDIUM** | No automated check that generated .pbip can be opened in PBI Desktop. The `validator.py` validates structure but doesn't parse TMDL syntax. |

---

## PRIORITY RECOMMENDATIONS

### P0 — Must Fix (Blocks Any Real Migration)

1. **I4**: Fix `ExtractionOrchestrator` constructor call in `migrate.py` — the pipeline crashes immediately
2. **I3**: Fix intermediate JSON key mapping in `run_generation()` — generation receives empty data
3. **C1/E2**: Generate multiple PBI pages from Qlik sheets — single-page output is unusable
4. **E1**: Remove the 10/20 visual limit — truncates most Qlik apps
5. **B1**: Wire `qlik_script_converter.py` into the extraction pipeline to parse load scripts into M queries

### P1 — High Impact

6. **D1/D10**: Implement dollar-sign expansion for variables in expressions
7. **I1**: Integrate at least `migrate_theme.py`, `migrate_qlik_variables.py`, `migrate_section_access.py` into pipeline
8. **B4**: Handle preceding/stacked LOAD patterns
9. **D5**: Implement TOTAL qualifier → CALCULATE + REMOVEFILTERS
10. **G1**: Place generated theme.json into PBIR output structure

### P2 — Quality Improvements

11. **I2**: Consolidate duplicate DAX converters to use `dax_converter.py`
12. **D2**: Expand set analysis parser for operators (+/-/*) and P()/E()
13. **E3-E6**: Add filters, sort, conditional formatting, slicer config to visuals
14. **B5-B6**: Handle CONCATENATE and JOIN in Qlik script parsing
15. **A5**: Improve QVD handling (auto-detect, generate Parquet conversion script)

---

## TOOL COVERAGE MATRIX

| Standalone Tool | Produces Code? | Integrated in Pipeline? | Impact |
|----------------|---------------|------------------------|--------|
| `migrate_set_analysis.py` | ✅ DAX expressions | ❌ | HIGH |
| `migrate_advanced_aggregations.py` | ✅ DAX patterns | ❌ | HIGH |
| `migrate_section_access.py` | ✅ RLS roles + DAX | ❌ | HIGH |
| `migrate_qlik_variables.py` | ✅ M parameters | ❌ | HIGH |
| `migrate_theme.py` | ✅ theme.json | ❌ | MEDIUM |
| `migrate_bookmarks.py` | ⚠️ Guide only | ❌ | MEDIUM |
| `migrate_navigation.py` | ✅ M code examples | ❌ | MEDIUM |
| `migrate_qvd.py` | ✅ Qlik export script | ❌ | MEDIUM |
| `migrate_qlik_scripts.py` | ✅ M queries | ❌ | HIGH |
| `migrate_qlik_model.py` | ✅ BIM model | ❌ | HIGH |
| `migrate_inter_record_functions.py` | ⚠️ Guide only | ❌ | LOW |
| `migrate_alternate_states.py` | ⚠️ Guide only | ❌ | LOW |
| `migrate_master_items.py` | ? | ❌ | MEDIUM |
| `migrate_listboxes.py` | ? | ❌ | MEDIUM |
| `migrate_stories.py` | ⚠️ PPT script | ❌ | LOW |
| `migrate_data_alerts.py` | ✅ PA flows | ❌ | LOW |
| `migrate_collaboration.py` | ? | ❌ | LOW |
| `migrate_custom_extensions.py` | ? | ❌ | LOW |
| `migrate_mashups.py` | ? | ❌ | LOW |
| `migrate_npprinting.py` | ? | ❌ | LOW |
| `migrate_on_demand_generation.py` | ? | ❌ | LOW |
| `migrate_power_automate.py` | ✅ PA flow JSON | ❌ | LOW |
| `migrate_rest_api.py` | ? | ❌ | LOW |
| `migrate_geoanalytics.py` | ? | ❌ | LOW |
| `migrate_current_selections.py` | ? | ❌ | LOW |
| `migrate_advanced_selections.py` | ? | ❌ | LOW |
| `migrate_qlik_to_pbi.py` | ✅ Full migration | ❌ (alt pipeline) | HIGH |
| `migrate_qvf.py` | ✅ QVF extraction | ❌ | HIGH |

---

## APPENDIX: Code-Level Observations

### `dax_converter.py`
- **Strong**: 175+ regex patterns, well-organized by category, pre-compiled for performance
- **Weak**: Regex-only approach cannot handle nested expressions or bracket matching. `_convert_aggr()` uses `Aggr\s*\( → ADDCOLUMNS(SUMMARIZE(VALUES(` which produces syntactically broken DAX for any non-trivial Aggr
- **Missing**: No AST/tokenizer for complex expressions — all conversions are single-pass regex

### `visual_generator.py`  
- **Strong**: 60+ type mappings, 30+ config templates, proper PBIR queryState building with data roles
- **Weak**: `build_query_state()` assigns ALL dimensions to EVERY dimension role, and ALL measures to the FIRST measure role. Should distribute dims[0] to Category, dims[1] to Series, etc.

### `tmdl_generator.py`
- **Strong**: Full PBI Project 4.0 structure, correct JSON schemas, proper TMDL syntax for all blocks
- **Weak**: Single monolithic class (1259 lines). Calendar/parameter generators are static methods not utilized by the pipeline.

### `extraction_orchestrator.py`
- **Strong**: Clean 11-file contract, supports QVF + JSON + Engine API formats
- **Weak**: QVF extraction delegates to `qvf_extractor.py` which may not populate all fields (e.g. datasources from data model is structure-dependent). The JSON dict parser has good fallback logic but doesn't parse load scripts.

### `qlik_script_converter.py`
- **Decent**: Parses LOAD with FROM/RESIDENT/INLINE, field aliases, WHERE clauses
- **Weak**: No preceding LOAD, no CONCATENATE, no JOIN, no SUB/CALL, no variable substitution. The converted M output has formatting issues (e.g., `',\\n'` instead of `',\n'`).
