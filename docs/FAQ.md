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
Functions like `Above()`, `Below()`, `RangeSum()`, and `Rank()` are
converted to DAX equivalents (`EARLIER`, window functions, `RANKX`).

### Q: What about Aggr() expressions?
`Aggr()` → `SUMMARIZE()` with appropriate grouping columns.

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
