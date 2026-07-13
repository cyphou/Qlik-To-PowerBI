# FAQ — Qlik to Power BI Migration

## General

### Q: What Qlik formats are supported?
- **QVF files** (.qvf) — Qlik Sense application packages (ZIP-based)
- **JSON exports** — Qlik Sense Engine API / metadata exports
- **Qlik load scripts** — converted via `qlik_script_converter.py`

### Q: What Power BI format is generated?
PBI Project 4.0 (`.pbip` + TMDL) — the modern, Git-friendly format.
Open with Power BI Desktop in **Developer Mode**.

### Q: Do I need Qlik Sense installed?
No. The migration reads QVF files directly (they are ZIP archives)
and parses JSON exports without any Qlik dependencies.

### Q: Do I need Power BI Desktop?
Only to open and validate the generated `.pbip` project.
Enable **Developer Mode** in Options → Preview features.

---

## Migration

### Q: How do I migrate a QVF file?
```bash
python migrate.py MyApp.qvf
```
This runs the full 2-step pipeline: extraction → generation.

### Q: Can I migrate from a JSON export?
```bash
python migrate.py export.json --output-dir output/my_project
```

### Q: How do I reuse extracted intermediate JSON?
```bash
python migrate.py MyApp.qvf --skip-extraction --output-dir output/existing_json
```

### Q: What are the 11 intermediate JSON files?
| File | Content |
|------|---------|
| `app_metadata.json` | App name, description, author, dates |
| `datasources.json` | Connection strings, tables, columns, types |
| `dimensions.json` | Master dimensions (fields, labels, groupings) |
| `measures.json` | Master measures (expressions, labels, formats) |
| `visualizations.json` | Chart types, dimension/measure bindings |
| `sheets.json` | Sheet layouts, cell positions |
| `variables.json` | Variables (name, definition, comment) |
| `loadscript.json` | Full Qlik load script |
| `associations.json` | Table associations / relationships |
| `bookmarks.json` | Bookmarks and selections |
| `master_items.json` | Master items (combined dim/measure refs) |

### Q: What does the Data Preparation Lineage section show?
It shows the preparation flow in the comparison report: Qlik load-script steps, Power Query M steps, layer classification (Bronze/Silver/Gold/Mart), purpose tags, complexity scoring, and multi-source steps such as JOIN/CONCATENATE.
For JSON-based runs, the comparison report falls back to the source app JSON `script` field when `loadscript.json` is unavailable, so lineage still renders in both single-file and batch runs.

### Q: Why might the lineage section still appear smaller than expected?
The report is data-dependent. Smaller apps will only show the steps present in that app. For JSON-based exports, the report now falls back to the `script` field in the source JSON when `loadscript.json` is unavailable.

### Q: How do I run batch migrations across nested folders?
Use `--batch-recursive` with `--batch` when your QVF or JSON exports are spread across subdirectories. The batch runner deduplicates by stem and processes `.json`, `.qvf`, and `.qvw` inputs.

---

## DAX Conversion

### Q: How many Qlik functions are converted to DAX?
175+ functions across 12 categories (string, math, date, aggregation,
set analysis, conditional, inter-record, type conversion, null handling,
logical, security, advanced).

### Q: Is Set Analysis converted?
Yes. `{<Year={2024}>}` → `CALCULATE(..., 'Table'[Year] = 2024)`.
Multi-field and complex modifiers are supported.

### Q: How are inter-record functions handled?
Functions like `Above(field, n)`, `Below(field, n)`, `Previous(field)`,
and `Peek(field, offset)` are converted to DAX `OFFSET` expressions.
`RangeSum(Above(X, 0, RowNo()))` generates a running total via
`CALCULATE(SUM(...), WINDOW(-INF, 0, ALLSELECTED(...)))`.

### Q: What about Aggr() expressions?
`Aggr()` is decomposed into DAX iterators:
- `Aggr(Sum(X), Dim)` → `SUMX(VALUES('T'[Dim]), X)`
- `Aggr(Count(X), Dim)` → `COUNTX(VALUES('T'[Dim]), 1)`
- `Aggr(Avg(X), Dim)` → `AVERAGEX(VALUES('T'[Dim]), X)`
- Multi-dim or unrecognized inner functions fall back to ADDCOLUMNS/SUMMARIZE.

### Q: Are P() and E() set analysis functions supported?
Yes (v7). `P({1} Field)` → `ALL('T'[Field])` (possible values)
and `E({1} Field)` → `EXCEPT(ALL('T'[Field]), VALUES('T'[Field]))` (excluded values).

### Q: What about dollar-sign expressions?
`$(=Year(Today())-1)` is expanded inline: the inner Qlik expression
is converted to DAX (`YEAR(TODAY()) - 1`). Variable references like
`$(vMyVar)` are resolved against the variables dictionary.

---

## Power Query M

### Q: Which data sources are supported?
25 connector types — see `docs/QLIK_TO_POWERQUERY_REFERENCE.md`.

### Q: How are QVD files handled?
QVD files have no native Power BI connector. The migration generates
a CSV-based M query with a comment explaining the QVD origin.
Convert QVD to CSV/Parquet before importing.

### Q: Can I chain transforms?
Yes. Use `inject_m_steps()` or `build_m_query_with_transforms()` from
`m_query_builder.py` to add 40+ transform types to any M query.

---

## TMDL

### Q: Is RLS (Row-Level Security) migrated?
Yes. Qlik Section Access is converted to TMDL roles with
`filterExpression` using `USERPRINCIPALNAME()`.
- Wildcard `*` entries generate an `RLS_AllUsers` role with `TRUE()` filter
- `OMIT` columns are annotated as OLS (Object-Level Security) migration notes
- `REDUCTION` columns are parsed into per-role reduce values

### Q: Are hierarchies preserved?
Yes. Qlik drill-group dimensions become TMDL hierarchies with levels.

### Q: Is a Calendar table auto-generated?
Yes. Call `TMDLGenerator.generate_calendar_table()` to get a complete
date dimension with Year, Month, Quarter, WeekNumber, DayOfWeek, etc.

### Q: How are geographic columns handled?
Column names like "Country", "City", "PostalCode" get automatic
`dataCategory` annotations for Power BI map visuals.

---

## Troubleshooting

### Q: Power BI Desktop shows "Cannot load model"
- Ensure Developer Mode is enabled
- Check TMDL syntax: balanced quotes, valid data types
- Verify relationships reference existing tables/columns

### Q: Measures show errors
- Qlik expressions may use functions without DAX equivalents
- Check the DAX conversion log for warnings
- Review `QLIK_TO_DAX_REFERENCE.md` for edge cases

### Q: Visuals appear empty
- Verify that visual data bindings reference existing model columns
- Check that table/column names match between TMDL and visual.json
- Ensure measures are defined in the correct table

---

## Plugins & CI/CD (v8)

### Q: How do I use the `--json` flag?
Run `python migrate.py app.qvf --json` to get machine-readable JSON output. The JSON includes status, table/measure/visual counts, warnings, and duration. This is ideal for CI/CD pipelines.

### Q: How do I create a custom plugin?
Create a Python class with a `name` attribute and implement any of the 7 hook methods (`pre_extraction`, `post_extraction`, `pre_generation`, `post_generation`, `transform_dax`, `transform_m_query`, `custom_visual_mapping`). Load it via `--plugins module.ClassName`. See `docs/guides/PLUGIN_DEVELOPMENT.md` for details.

### Q: Can plugins modify DAX expressions after conversion?
Yes — implement `transform_dax(self, formula)` and return the modified formula. Multiple plugins are chained in registration order.

### Q: What happens if a plugin raises an error?
The error is logged and the pipeline continues. Plugins never crash the migration.

---

## Enterprise Features (v9)

### Q: How do I generate Fabric-native artifacts?
```bash
python migrate.py app.json --output-format fabric
```
This generates Lakehouse delta tables, Dataflow Gen2 ingestion, PySpark ETL notebooks, a 3-stage Data Pipeline, and a DirectLake semantic model.

### Q: How do I merge multiple Qlik apps?
```bash
python migrate.py --merge app1.json app2.json app3.json
```
The merge engine uses fingerprint-based table matching with Jaccard column overlap scoring. Matching tables are deduplicated, and thin reports reference a shared semantic model.

### Q: How do I assess a portfolio of Qlik apps?
```bash
python migrate.py --assess-server exports/
```
Scans all JSON exports in the directory and produces a RED/YELLOW/GREEN assessment per app with complexity scores, effort estimates, and wave planning recommendations.

### Q: What does the DAX optimizer do?
After generation, the DAX optimizer automatically:
- Rewrites nested IF chains to SWITCH
- Simplifies ISBLANK patterns to COALESCE
- Folds constants (e.g., `1 + 2` → `3`)
- Extracts repeated sub-expressions into VARs
- Auto-generates Time Intelligence measures (YTD, QTD, MTD) when a Calendar table is detected

### Q: Is PII detection available?
Yes. `governance.py` scans column names and expressions for PII patterns (email, SSN, phone, credit card, etc.) and flags them in the migration report.

### Q: How does schema drift detection work?
`schema_drift.py` compares two versions of intermediate JSON files and reports added, removed, renamed, and type-changed columns. Useful for incremental migration scenarios.

### Q: What security validations are performed?
`security_validator.py` checks for:
- Path traversal attacks (e.g., `../../etc/passwd`)
- ZIP slip vulnerabilities in QVF extraction
- XXE injection in XML content
- Overly long file paths

### Q: What monitoring/observability is available?
`monitoring.py` exports migration metrics to Azure Monitor, Prometheus, or JSON format. `sla_tracker.py` tracks per-app migration time and fidelity against configurable SLA thresholds.

### Q: Can I deploy a shared model with thin reports?
Yes. After `--merge`, use the bundle deployer:
```python
from powerbi_import.deploy.bundle_deployer import BundleDeployer
deployer = BundleDeployer(workspace_id="...", token="...")
deployer.deploy_bundle("output/merged/")
```
This deploys the shared semantic model first, then all thin reports referencing it.
