<!-- DOC-SHINY-BANNER -->
![Documentation](https://img.shields.io/badge/Documentation-Shiny_Style-0A66C2?style=flat-square&logo=readthedocs&logoColor=white)
![Maintained](https://img.shields.io/badge/Maintained-2026-2EA44F?style=flat-square&logo=github&logoColor=white)
![Navigation](https://img.shields.io/badge/Navigation-Quick_Access-6F42C1?style=flat-square&logo=bookstack&logoColor=white)
# DEV_PLAN v7.0 — Hardening, Test Coverage & Pipeline Integration

**Baseline:** v6.0.0 — 756 tests passing  
**Target:** v7.0.0 — DAX accuracy deepening, critical test coverage, pipeline wiring, legacy cleanup

---

## Phase 1 — DAX Accuracy Deepening

### 1a. Aggr() Decomposition
Enhance `_convert_aggr()` to decompose inner aggregation functions:
- `Aggr(Sum(X), Dim)` → `SUMX(VALUES('T'[Dim]), X)`
- `Aggr(Count(X), Dim)` → `COUNTX(VALUES('T'[Dim]), 1)`
- `Aggr(Avg(X), Dim)` → `AVERAGEX(VALUES('T'[Dim]), X)`
- `Aggr(Min/Max(X), Dim)` → `MINX/MAXX(VALUES('T'[Dim]), X)`
- Nested `Aggr(Aggr(...))` support
- Multi-dim: `SUMMARIZE` with iterator

### 1b. Inter-record: RangeSum + improved Peek/Above/Below
- `RangeSum(Above(X, 0, RowNo()))` → running total via `CALCULATE/WINDOW`
- `Above(field, n)` → `OFFSET(-n, ...)`
- `Below(field, n)` → `OFFSET(n, ...)`
- `Peek(field, offset)` → `OFFSET` with explicit offset

### 1c. Set Analysis: P()/E() Functions
- `P({1} <Field>)` → `FILTER(ALL('T'[Field]), ...)`
- `E({1} <Field>)` → `EXCEPT(ALL('T'[Field]), VALUES('T'[Field]))`
- `Sum({<Year=$(=Year(Today())-1)>} Sales)` → `CALCULATE(SUM(...), SAMEPERIODLASTYEAR(...))`

---

## Phase 2 — Critical Test Coverage

### 2a. test_pbip_generator.py (NEW)
Dedicated tests for `pbip_generator.py` (2,560 lines, 0 existing tests):
- Project structure generation
- TMDL file output
- PBIR report output
- Multi-table, multi-measure scenarios
- Edge cases (empty datasources, unicode names)

### 2b. test_visual_generator.py (NEW)
Dedicated tests for `visual_generator.py` (1,357 lines, 0 existing tests):
- All 60+ visual type mappings
- Config template generation
- Dimension/measure binding
- Conditional formatting, sort config

### 2c. Expand test_tmdl_generator.py
From 371 lines → comprehensive coverage of 3,022-line module:
- RLS roles with OMIT, reduce, wildcards
- Hierarchies, calculated columns, measures
- Calendar table generation
- Expressions (Power Query M)

---

## Phase 3 — Pipeline Wiring

- Wire `validator.py` as optional post-generation auto-check in `import_all()`
- Wire `migration_report.py` for auto summary generation
- Pass `paginated` parameter through `import_all()` → `generate_powerbi_project()`

---

## Phase 4 — Section Access Improvements

Port unique logic from `tools/migration/migrate_section_access.py`:
- OMIT field detection and mapping to RLS `filterExpression`
- Reduce field/value extraction
- Wildcard `*` → `TRUE()` in RLS roles

---

## Phase 5 — Legacy TMDLGenerator Deprecation

- Reduce `src/fabric_api/tmdl_generator.py` to minimal shim with deprecation warning
- Verify all functionality covered by canonical `powerbi_import/` modules
- Update any remaining direct imports

---

## Phase 6 — CI/CD, Changelog & Version

- Create `.github/workflows/ci.yml` (pytest + lint)
- Update CHANGELOG.md with v7.0.0 entries
- Bump version references

