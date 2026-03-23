# Migration Guide — Qlik to Power BI

Complete technical reference for migrating Qlik Sense applications to Power BI using the automated pipeline.

---

## Table of Contents

1. [Architecture](#architecture)
2. [Prerequisites](#prerequisites)
3. [Migration Pipeline](#migration-pipeline)
4. [Extraction Phase](#extraction-phase)
5. [Generation Phase](#generation-phase)
6. [DAX Conversion](#dax-conversion)
7. [Power Query M Generation](#power-query-m-generation)
8. [Visual Mapping](#visual-mapping)
9. [Advanced Features](#advanced-features)
10. [Troubleshooting](#troubleshooting)

---

## Architecture

The migration follows a 2-step pipeline:

```
.qvf / .json → [Extraction] → 11 JSON files → [Generation] → .pbip project
```

### Step 1: Extraction
Parses the Qlik source (QVF binary or JSON export) and produces 11 intermediate JSON files representing every aspect of the Qlik application.

### Step 2: Generation
Consumes the intermediate JSON files and generates a complete PBIP project with TMDL semantic model and report definition.

---

## Prerequisites

- **Python 3.10+**
- **Power BI Desktop** (April 2024 or later for PBIP support)
- No Qlik Sense installation required
- No external Python dependencies for core migration

### Installation

```bash
git clone https://github.com/cyphou/Qlik-To-PowerBI.git
cd QlikToPowerBI
pip install -r requirements.txt
```

---

## Migration Pipeline

### Basic Usage

```bash
# From QVF file
python migrate.py app.qvf

# From JSON export
python migrate.py export.json

# Custom output directory
python migrate.py app.qvf --output-dir output/my_app

# Skip extraction (reuse existing JSON files)
python migrate.py app.qvf --skip-extraction

# Machine-readable JSON output for CI/CD
python migrate.py app.qvf --json

# Load custom plugins
python migrate.py app.qvf --plugins my_plugin.ServerRenamer
```

### CLI Options

| Flag | Description |
|------|-------------|
| `--output-dir DIR` | Custom output directory |
| `--skip-extraction` | Skip extraction, reuse existing intermediate JSON |
| `--json` | Output structured JSON result (suppresses human output) |
| `--plugins MODULE...` | Load plugin modules (space-separated) |
| `--dry-run` | Show what would be done without executing |
| `--verbose` | Enable detailed logging |

---

## Extraction Phase

The extraction phase parses the Qlik source and produces 11 intermediate JSON files:

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

These files are human-readable and can be inspected or manually edited between extraction and generation.

---

## Generation Phase

The generation phase produces a complete PBIP project:

### TMDL Semantic Model
- **Tables** with columns (dataType, formatString, sourceColumn, isHidden, dataCategory)
- **Measures** with DAX expressions
- **Calculated columns** with DAX and automatic `RELATED()` insertion
- **Hierarchies** from Qlik drill-group dimensions
- **Relationships** with crossFilteringBehavior
- **RLS roles** from Section Access (filterExpression + `USERPRINCIPALNAME()`)
- **Parameters** / What-If tables (`GENERATESERIES`, `DATATABLE`, `SELECTEDVALUE`)
- **Calendar table** with time intelligence (auto-generated)
- **Expressions** (shared Power Query M)

### Report Definition
- 60+ visual types mapped from Qlik equivalents
- Page layouts preserving sheet structure
- Data bindings linking visuals to model columns
- Bookmarks with filter state
- Background images on pages

---

## DAX Conversion

175+ Qlik expressions are converted to DAX:

| Category | Count | Examples |
|----------|-------|---------|
| String | 25 | `Upper`→`UPPER`, `Len`→`LEN`, `Replace`→`SUBSTITUTE` |
| Math | 20 | `Ceil`→`CEILING`, `Floor`→`FLOOR`, `Mod`→`MOD` |
| Date | 22 | `Year`→`YEAR`, `MonthStart`→`STARTOFMONTH` |
| Aggregation | 15 | `Sum`→`SUM`, `CountDistinct`→`DISTINCTCOUNT` |
| Set Analysis | 10 | `{<Year={2024}>}` → `CALCULATE(..., 'Table'[Year] = 2024)` |
| Conditional | 12 | `If`→`IF`, `Match`→`SWITCH`, `Alt`→`COALESCE` |
| Inter-record | 8 | `Above`/`Below`→`OFFSET`, `RangeSum`→`WINDOW` |
| Advanced | 38 | `Aggr`→`SUMMARIZE`/`SUMX`, `Dual`→`VALUE` |

### Set Analysis

Qlik set analysis modifiers are translated to `CALCULATE` with appropriate filter arguments:

```
// Qlik
Sum({<Year={2024}, Region={'US'}>} Sales)

// DAX
CALCULATE(SUM('Sales'[Sales]), 'Date'[Year] = 2024, 'Geography'[Region] = "US")
```

### Inter-record Functions

| Qlik | DAX |
|------|-----|
| `Above(field, n)` | `OFFSET(field, -n)` |
| `Below(field, n)` | `OFFSET(field, n)` |
| `Previous(field)` | `OFFSET(field, -1)` |
| `RangeSum(Above(field, 0, RowNo()))` | Running total via `CALCULATE`/`WINDOW` |
| `Rank(expr)` | `RANKX(ALL('Table'), expr)` |

---

## Power Query M Generation

### 25 Connector Types

Excel, CSV, SQL Server, PostgreSQL, BigQuery, Oracle, MySQL, Snowflake, Teradata, SAP HANA, Redshift, Databricks, Spark, Azure SQL, Azure Synapse, Google Sheets, SharePoint, JSON, XML, PDF, Salesforce, Web, QVD, ODBC, OLE DB

### 40+ Transform Generators

| Category | Transforms |
|----------|-----------|
| Column ops | rename, remove, select, duplicate, reorder, split, merge |
| Value ops | replace, replace nulls, trim, clean, upper/lower/proper, fill |
| Filter ops | filter values, exclude, range, nulls, contains, distinct, top N |
| Aggregate | group by (sum/avg/count/countd/min/max/median/stdev) |
| Pivot | unpivot, unpivot other, pivot |
| Join | inner/left/right/full/leftanti/rightanti with auto-expand |
| Union | append tables, wildcard union |
| Reshape | sort, transpose, add index, skip/remove rows, headers |
| Calculated | add custom column, conditional column |

---

## Visual Mapping

60+ Qlik visual types map to Power BI equivalents:

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
| filterpane | slicer |
| text-image | textbox |
| *(40+ more)* | ... |

---

## Advanced Features

### Section Access → RLS

Qlik Section Access is converted to Power BI Row-Level Security:
- `ACCESS` field → role assignment
- `USERID` → `USERPRINCIPALNAME()` filter expression
- `REDUCTION` → table filter expressions
- `OMIT` → Object-Level Security (OLS) annotations
- Wildcard `*` → universal access

### Hierarchies

Qlik drill-group dimensions produce TMDL hierarchies with levels.

### Calendar Table

An auto-generated calendar table is created when date columns are detected, including:
- Date, Year, Quarter, Month, MonthName, Day, DayOfWeek, WeekNumber
- Time intelligence functions ready to use

### Dollar-Sign Expansion

Qlik `$(=expression)` patterns are expanded with the expression converted to DAX.

---

## Troubleshooting

### Model doesn't load in Power BI Desktop
- Ensure Power BI Desktop is April 2024 or later
- Open the `.pbip` file (not individual TMDL files)

### Measures show errors
- Check the DAX syntax in `tables/*.tmdl`
- Verify column references use `'TableName'[ColumnName]` format
- Run with `--verbose` for detailed conversion logs

### Empty visuals
- Verify data source connections are configured
- Check that column names in visual bindings match the model

### Plugin not loading
- Use fully qualified module path: `my_package.my_module.MyPluginClass`
- Ensure the module is on `PYTHONPATH`

See also: [FAQ](../FAQ.md)
