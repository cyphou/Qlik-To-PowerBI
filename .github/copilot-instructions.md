# Qlik to Power BI Migration — Copilot Context

## Project Overview

Automated migration toolkit that converts Qlik Sense applications (.qvf, JSON exports)
into **PBI Projects** (`.pbip` / TMDL) — the modern, Git-friendly Power BI format.

## Architecture

### 2-Step Pipeline

```
.qvf / .json → [Extraction] → 11 JSON files → [Generation] → .pbip project
```

1. **Extraction** (`extraction_orchestrator.py`): parse QVF or JSON → produce 11 intermediate JSON files
2. **Generation** (`tmdl_generator.py` + `visual_generator.py`): consume JSON → produce .pbip project

### Single entry point

```bash
python migrate.py app.qvf                  # Full pipeline
python migrate.py export.json              # From JSON export
python migrate.py app.qvf --output-dir out # Custom output
python migrate.py app.qvf --skip-extraction # Reuse existing JSON
```

## Project Structure

```
├── migrate.py                          # Root CLI entry point
├── src/fabric_api/                     # Core library
│   ├── tmdl_generator.py              # PBI Project / TMDL output
│   ├── dax_converter.py               # 175+ Qlik expression → DAX conversions
│   ├── visual_generator.py            # 60+ visual types, 30+ config templates
│   ├── m_query_generator.py           # 25 connector types → Power Query M
│   ├── m_query_builder.py             # 40+ chainable M transforms + inject_m_steps
│   ├── extraction_orchestrator.py     # QVF/JSON → 11 intermediate JSON files
│   ├── qlik_migrator.py              # QlikApp → Power BI converter
│   ├── qlik_model_converter.py
│   ├── qlik_script_converter.py      # Qlik script → Power Query M (30 functions)
│   ├── qvf_extractor.py             # .qvf ZIP reader
│   ├── config/                       # Settings (pydantic-settings)
│   ├── auth.py                       # Azure auth (lazy-loaded)
│   ├── client.py                     # Fabric REST client
│   ├── deployer.py                   # Fabric deployment
│   ├── validator.py                  # Artifact validation
│   └── utils.py                      # Reports & caching
├── tools/migration/                   # 28 standalone migration scripts
├── tools/analysis/                    # Diagnostic tools
├── tools/testing/                     # Integration test suites
├── tests/                            # pytest test suite
├── examples/                         # Usage examples & samples
└── docs/                             # Guides, references, reports
```

## 11 Intermediate JSON Files

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

## DAX Conversion — 175+ Functions

| Category | Count | Examples |
|----------|-------|---------|
| String | 25 | Upper→UPPER, Lower→LOWER, Len→LEN, Mid→MID, Replace→SUBSTITUTE |
| Math | 20 | Abs→ABS, Ceil→CEILING, Floor→FLOOR, Sqrt→SQRT, Mod→MOD |
| Date | 22 | Year→YEAR, Month→MONTH, Today→TODAY, MonthStart→STARTOFMONTH |
| Aggregation | 15 | Sum→SUM, Avg→AVERAGE, Count→COUNT, CountDistinct→DISTINCTCOUNT |
| Set Analysis | 10 | `{<Year={2024}>}` → `CALCULATE(..., 'Table'[Year] = 2024)` |
| Conditional | 12 | If→IF, Match→SWITCH, Pick→SWITCH, Alt→COALESCE |
| Inter-record | 8 | Above→EARLIER, RangeSum→window, Rank→RANKX |
| Type conversion | 8 | Num→VALUE, Text→FORMAT, Date→DATEVALUE |
| Null handling | 6 | IsNull→ISBLANK, Null→BLANK, NullCount→COUNTBLANK |
| Logical | 8 | AND→&&, OR→||, NOT→NOT, =→= |
| Security | 3 | OSUser→USERPRINCIPALNAME |
| Advanced | 38 | Aggr→SUMMARIZE, Dual→VALUE, Class→INT/DIVIDE |

## Power Query M — 25 Connector Types

Excel, CSV, SQL Server, PostgreSQL, BigQuery, Oracle, MySQL, Snowflake, Teradata,
SAP HANA, Redshift, Databricks, Spark, Azure SQL, Azure Synapse, Google Sheets,
SharePoint, JSON, XML, PDF, Salesforce, Web, QVD, ODBC, OLE DB

## Power Query M — 40+ Transform Generators

| Category | Transforms |
|----------|-----------|
| Column ops | rename, remove, select, duplicate, reorder, split, merge |
| Value ops | replace, replace nulls, trim, clean, upper/lower/proper, fill down/up |
| Filter ops | filter values, exclude, range, nulls, contains, distinct, top N |
| Aggregate | group by (sum/avg/count/countd/min/max/median/stdev) |
| Pivot | unpivot, unpivot other, pivot |
| Join | inner/left/right/full/leftanti/rightanti with auto-expand |
| Union | append tables, wildcard union |
| Reshape | sort, transpose, add index, skip/remove rows, promote/demote headers |
| Calculated | add custom column, conditional column |

## Visual Type Mapping — 60+ Types

| Qlik Type | Power BI Visual |
|-----------|----------------|
| barchart | clusteredBarChart |
| linechart | lineChart |
| piechart | pieChart |
| combo | lineStackedColumnComboChart |
| scatter | scatterChart |
| treemap | treemap |
| kpi | card / kpi |
| gauge | gauge |
| table | tableEx |
| pivot-table | pivotTable |
| map | map |
| waterfall | waterfallChart |
| boxplot | boxAndWhisker |
| histogram | clusteredColumnChart |
| distributionplot | scatterChart |
| filterpane | slicer |
| text-image | textbox |
| container | actionButton/group |
| mekko | stackedBarChart |
| bullet | bulletChart |
| wordcloud | wordCloud |
| ... | 40+ more mappings |

## TMDL Features

- Tables with columns (dataType, formatString, sourceColumn, isHidden, dataCategory)
- Measures with DAX expressions
- Calculated columns with DAX expressions and RELATED() auto-insertion
- Hierarchies from Qlik drill-group dimensions
- Relationships with crossFilteringBehavior
- RLS roles from Section Access (filterExpression + USERPRINCIPALNAME)
- Parameter/What-If tables (GENERATESERIES, DATATABLE, SELECTEDVALUE)
- Auto-generated Calendar table with time intelligence
- Expressions (shared Power Query M)
- Sets/Groups/Bins → calculated columns

## Development Rules

1. **No external dependencies** for core migration — standard library + existing deps only
2. **TMDL output** — all `tables/*.tmdl` must have valid TMDL syntax (Power BI Desktop parseable)
3. **DAX expressions** — balanced parentheses, valid keywords, quoted column references
4. **Calculated column vs. measure** — classify based on Qlik expression role
5. **RELATED()** — auto-insert when a calculated column references another table (manyToOne)
6. **LOOKUPVALUE()** — use for manyToMany cross-table references
7. **Set Analysis → CALCULATE** — map modifiers to ALLEXCEPT/REMOVEFILTERS/VALUES
8. **Column deduplication** — eliminate duplicate columns across datasources
9. **Visual data bindings** — projections must reference existing model columns
10. **formatString** — preserve Qlik number formats (convert to DAX format strings)
11. **Test coverage** — every new feature must have corresponding test cases
