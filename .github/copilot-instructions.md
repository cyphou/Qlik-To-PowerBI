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
python migrate.py app.qvf --json           # Machine-readable JSON output
python migrate.py app.qvf --plugins m.Cls  # Load custom plugins
python migrate.py app.qvf --dry-run        # Preview without executing
python migrate.py app.qvf --verbose        # Detailed logging
python migrate.py --server-url https://qlik.example.com --server-app-id abc123  # Direct server extraction
python migrate.py app.qvf --refresh-schedule  # Generate PBI refresh config
```

## Project Structure

```
├── migrate.py                          # Root CLI entry point
├── qlik_export/                        # Qlik-specific extraction (canonical)
│   ├── dax_converter.py               # 175+ Qlik expression → DAX conversions
│   ├── extraction_orchestrator.py     # QVF/JSON → 11 intermediate JSON files
│   ├── format_adapter.py             # Qlik 11-key → generation-layer bridge
│   ├── datasource_extractor.py       # API bridge (type/formula/M adapters)
│   ├── m_query_generator.py          # 42 connector types → Power Query M
│   ├── m_query_builder.py            # 40+ chainable M transforms + inject_m_steps
│   ├── qlik_migrator.py              # QlikApp → Power BI converter
│   ├── qlik_model_converter.py
│   ├── qlik_script_converter.py      # Qlik script → Power Query M (30 functions)
│   └── qvf_extractor.py              # .qvf ZIP reader
├── powerbi_import/                     # Power BI generation layer (canonical)
│   ├── tmdl_generator.py             # TMDL semantic model output
│   ├── pbip_generator.py             # Full .pbip project output
│   ├── visual_generator.py           # 75+ visual types, 30+ config templates
│   ├── import_to_powerbi.py          # Import orchestrator
│   ├── plugins.py                    # Plugin architecture (7 hooks)
│   ├── progress.py                   # Step-level progress tracking
│   ├── validator.py                  # Artifact validation
│   ├── dax_optimizer.py              # AST-based DAX rewriter (IF→SWITCH, COALESCE, etc.)
│   ├── dax_recipes.py                # Industry KPI templates (Healthcare/Finance/Retail)
│   ├── dax_query_generator.py        # DAX Studio validation query generator
│   ├── model_templates.py            # Pre-built star schema skeletons
│   ├── governance.py                 # PII detection, naming conventions, audit trail
│   ├── security_validator.py         # Path/ZIP slip/XXE protection
│   ├── monitoring.py                 # Metrics export (Azure Monitor, Prometheus, JSON)
│   ├── alerts_generator.py           # Threshold-based PBI alert rules
│   ├── lineage_map.py                # Source-to-target provenance tracking
│   ├── qa_pipeline.py                # Full QA pipeline (17 auto-fix patterns)
│   ├── recovery_report.py            # Self-healing recovery tracking
│   ├── sla_tracker.py                # Per-app SLA compliance
│   ├── schema_drift.py               # Column/formula change detection
│   ├── equivalence_tester.py         # Cross-platform value comparison
│   ├── regression_suite.py           # Snapshot-based drift detection
│   ├── visual_diff.py                # Side-by-side HTML comparison
│   ├── marketplace.py                # Versioned pattern registry
│   ├── api_server.py                 # REST API server (stdlib)
│   ├── notebook_api.py               # Jupyter interactive migration API
│   ├── paginated_generator.py        # RDL-style paginated reports
│   ├── permission_mapper.py          # RLS PowerShell script generator
│   ├── llm_client.py                 # LLM-assisted DAX refinement
│   ├── server_assessment.py          # Portfolio-level assessment & wave planning
│   ├── shared_model.py               # Multi-app merge engine (fingerprint matching)
│   ├── thin_report_generator.py      # Thin reports with shared semantic model
│   ├── merge_assessment.py           # Merge JSON report
│   ├── merge_config.py               # Reproducible merge decisions
│   ├── merge_report_html.py          # Merge HTML dashboard
│   ├── global_assessment.py          # Cross-app merge analysis
│   ├── fabric_constants.py           # Spark type maps, Fabric patterns
│   ├── fabric_naming.py              # Fabric artifact name sanitization
│   ├── lakehouse_generator.py        # Delta table schemas & DDL
│   ├── dataflow_generator.py         # Power Query M for Dataflow Gen2
│   ├── notebook_generator.py         # PySpark ETL notebooks
│   ├── pipeline_generator.py         # 3-stage Fabric Data Pipeline
│   ├── fabric_semantic_model_generator.py  # DirectLake semantic model
│   ├── fabric_project_generator.py   # Fabric artifacts orchestrator
│   ├── calc_column_utils.py          # Calculated column classification
│   ├── config/                       # Migration config (pydantic-settings)
│   └── deploy/                       # Azure deployment (auth, client, deployer,
│       │                             #   bundle_deployer, multi_tenant,
│       │                             #   pbi_client, pbi_deployer)
│       └── config/                   # Environment-based deployment config
├── src/fabric_api/                     # Deprecated — backward-compat shims
│   ├── tmdl_generator.py             # Unique TMDLGenerator class (not yet migrated)
│   ├── visual_generator.py           # Unique implementation (not yet migrated)
│   └── *.py                          # Re-export shims → qlik_export/powerbi_import
├── tools/migration/                   # 28 standalone migration scripts
├── tools/analysis/                    # Diagnostic tools
├── tools/testing/                     # Integration test suites
├── scripts/                          # Utility scripts (M syntax check, version bump)
├── web/                              # Streamlit migration wizard
├── tests/                            # pytest test suite
├── examples/                         # Usage examples, marketplace, plugins
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
| Inter-record | 8 | Above/Below→OFFSET, RangeSum→WINDOW, Rank→RANKX |
| Type conversion | 8 | Num→VALUE, Text→FORMAT, Date→DATEVALUE |
| Null handling | 6 | IsNull→ISBLANK, Null→BLANK, NullCount→COUNTBLANK |
| Logical | 8 | AND→&&, OR→\|\|, NOT→NOT, =→= |
| Security | 3 | OSUser→USERPRINCIPALNAME |
| Advanced | 38 | Aggr→SUMMARIZE/SUMX, Dual→VALUE, Class→INT/DIVIDE |

## Power Query M — 42 Connector Types

Excel, CSV, SQL Server, PostgreSQL, BigQuery, Oracle, MySQL, Snowflake, Teradata,
SAP HANA, Redshift, Databricks, Spark, Azure SQL, Azure Synapse, Google Sheets,
SharePoint, JSON, XML, PDF, Salesforce, Web, QVD, ODBC, OLE DB, OData,
Google Analytics, Azure Blob, Vertica, Impala, Hadoop Hive, Presto,
Fabric Lakehouse, Dataverse, MongoDB, Cosmos DB, Athena, DB2, GeoJSON,
SAP BW, Custom SQL

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

## Visual Type Mapping — 75+ Types

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
- Section Access → RLS with wildcard `*`, OMIT (OLS annotation), REDUCTION parsing
- Aggr() decomposition → SUMX/COUNTX/AVERAGEX/MINX/MAXX iterators
- Inter-record OFFSET for Previous/Above/Below/Peek
- RangeSum running total via CALCULATE/WINDOW
- P()/E() set analysis → ALL/EXCEPT
- Dollar-sign expression expansion `$(=expr)` with Qlik→DAX conversion

## Current Stats (v11.0.0)

- **2,605 tests** across 73 test files
- **70 powerbi_import modules** (including quality gates, planning, and feedback)
- **42 data connectors** in M query generator (was 25 in v9)
- **~91 CLI flags** (added --server-url, --server-api-key, --server-cert, --server-app-id, --refresh-schedule, --refresh-timezone)
- **120+ visual type mappings** (was 75+ in v10.0)
- **164 entries** in `_SIMPLE_FUNCTION_MAP`
- **4 DAX stubs remaining** (Skew, Hash128/160/256, Evaluate — truly unsupported)
- **5/6 sample migrations** pass at 100% fidelity
- **Plugin system** with 7 hook points (`--plugins` CLI flag)
- **JSON output** for CI/CD (`--json` CLI flag)
- **Progress callbacks** for pipeline visibility
- **10 agent definitions** for multi-agent Copilot workflows (preceptorship model)
- **5 CI workflows** (lint, test, deploy, gh-pages, publish)
- **Lineage map** for full source-to-target provenance tracking
- **QA pipeline** with 17 auto-fix patterns for Qlik→DAX leaks
- **Qlik Server client** for direct extraction (QSEoW + Cloud)
- **GeoJSON passthrough** — auto-wired into project generation
- **Refresh schedule generator** — Qlik reload tasks → PBI refresh config

## Multi-Agent Preceptorship Model

```
Tech Lead (Orchestrator) ← architecture, planning
Preceptor               ← quality review, standards
Specialists             ← Plan → Assign → Implement → Review
```

- **Orchestrator** (Tech Lead): pipeline coordination, CLI, cross-agent planning
- **Preceptor**: quality review, cross-agent consistency, pitfall detection
- **Extractor**: Qlik QVF/JSON parsing → 11 intermediate JSON
- **Converter**: 175+ DAX conversions, 42 M connectors, 40+ transforms
- **Generator**: TMDL, PBIR, 75+ visual types, Fabric-native output
- **Assessor**: readiness scoring, strategy advising, visual diff
- **Merger**: multi-app merge, fingerprint matching, thin reports
- **Deployer**: PBI Service / Fabric deployment, Azure AD auth
- **Tester**: 2,000 tests, regression suites

See `.github/agents/` for full agent definitions.

## v9 — Enterprise Features (ported from TableauToPowerBI)

### DAX Intelligence
- AST-based DAX optimizer (IF→SWITCH, COALESCE, constant folding, VAR extraction)
- Industry-specific KPI templates (Healthcare, Finance, Retail)
- DAX Studio validation query auto-generation
- Pre-built star schema model templates
- LLM-assisted DAX refinement (OpenAI/Anthropic)

### Fabric-Native Generation (`--output-format fabric`)
- Lakehouse delta table schemas & DDL
- Dataflow Gen2 Power Query M ingestion
- PySpark ETL notebooks (9 connector templates)
- 3-stage Data Pipeline orchestrator
- DirectLake semantic model

### Multi-App Merge Engine
- Fingerprint-based table matching & deduplication
- Thin reports with shared semantic model (byPath)
- Merge assessment JSON & HTML reports
- Per-table merge rules (save/load for reproducibility)
- Cross-app merge cluster analysis

### Enterprise Governance & Validation
- PII detection, naming conventions, audit trail (JSONL)
- Security: path validation, ZIP slip defense, XXE protection
- Equivalence testing: cross-platform value comparison
- Regression snapshots for drift detection
- Schema drift detection (added/removed/renamed columns)
- Visual diff: side-by-side HTML comparison
- SLA compliance tracking (max time, min fidelity)

### Portfolio Assessment & Observability
- Server-level assessment: RED/YELLOW/GREEN per app
- Complexity heatmap, effort estimation, wave planning
- Metrics export to Azure Monitor, Prometheus, JSON
- Self-healing recovery tracking
- Threshold-based PBI data-driven alerts

### Enterprise APIs & Automation
- REST API server (stdlib, zero deps)
- Jupyter-based interactive migration API
- RDL-style paginated report generator
- RLS permission PowerShell script generator
- Versioned pattern registry (marketplace)
- Streamlit web migration wizard

### Enhanced Deployment
- Bundle deployer (shared model + thin reports)
- Multi-tenant deployment with template substitution
- Power BI Service REST API (blue/green deployment)
- Refresh scheduling

## v8 Visual & Reporting Features

- Navigation actions from Qlik buttons/sheets → Power BI button actions
- Viz-in-tooltip extraction and preservation
- Alternate states (`qStateName`) extraction from Qlik objects
- Icon set conditional formatting (4 presets: arrows, flags, stars, circles)
- Background images on report pages from Qlik sheet backgrounds
- Bookmarks with filter state wired into report.json
- 4 English documentation guides + API reference

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
12. **Run tests** — `pytest tests/ -q --tb=short` (must all pass before commit)
