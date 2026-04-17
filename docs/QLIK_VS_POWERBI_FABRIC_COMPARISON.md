# Qlik Sense vs Power BI vs Microsoft Fabric — Platform Comparison

Side-by-side mapping of platform concepts, architecture, and capabilities.

---

## 1. Platform Architecture

| Concept | Qlik Sense | Power BI | Microsoft Fabric |
|:--------|:-----------|:---------|:-----------------|
| **Deployment** | On-prem (QMC) or Qlik Cloud | Power BI Service (SaaS) or PBI Report Server | SaaS (Azure-integrated) |
| **Engine** | Associative Engine (in-memory) | VertiPaq (columnar in-memory) + DirectQuery | VertiPaq + DirectLake + Spark |
| **Query language** | Qlik expressions + Set Analysis | DAX (measures) + Power Query M (ETL) | DAX + M + T-SQL + KQL + PySpark |
| **App model** | QVF app (self-contained) | .pbix / .pbip project | Workspace with multiple item types |
| **Multi-tenancy** | Streams + Security Rules | Workspaces + App permissions | Capacity + Workspace + Domain |
| **Git integration** | None native | PBIP + Git integration | Native Git integration (all items) |
| **File format** | .qvf (binary ZIP) | .pbix (binary) / .pbip (text, Git-friendly) | Item definitions (JSON/TMDL) |

---

## 2. Data Layer

| Concept | Qlik Sense | Power BI | Microsoft Fabric |
|:--------|:-----------|:---------|:-----------------|
| **ETL tool** | Load Script (in-app) | Power Query M (Dataflows) | Data Factory Pipelines + Dataflow Gen2 |
| **Script language** | Qlik Script (proprietary) | Power Query M (functional) | M + PySpark + T-SQL |
| **Data storage** | QVD files (proprietary binary) | .pbix internal storage | OneLake (Delta/Parquet, open format) |
| **Data lake** | QVD folders on share | Azure Data Lake (external) | OneLake (built-in, unified) |
| **Data warehouse** | N/A (in-memory only) | N/A (use Azure Synapse) | Fabric Warehouse (T-SQL) |
| **Lakehouse** | N/A | N/A | Fabric Lakehouse (Spark + T-SQL) |
| **Real-time ingestion** | Qlik Replicate (CDC) | Streaming dataflows | Eventhouse (KQL) + Real-Time Intelligence |
| **Connectors** | 100+ via Qlik connectors | 200+ via Power Query | 200+ via Power Query + Spark + Shortcuts |
| **Incremental load** | QVD + WHERE clause | Incremental Refresh (parameters) | Incremental Refresh + Notebooks |
| **Data caching** | QVD snapshots | Import mode cache | Delta tables in OneLake |

### ETL Pattern Comparison

```
┌─── Qlik Sense ──────────────────────────────────────┐
│  Load Script → QVD → Associative Model (in-memory)  │
└──────────────────────────────────────────────────────┘

┌─── Power BI ────────────────────────────────────────┐
│  Power Query M → VertiPaq Model (Import)            │
│  or → DirectQuery → Source DB                       │
└──────────────────────────────────────────────────────┘

┌─── Microsoft Fabric ────────────────────────────────┐
│  Pipeline/Dataflow/Notebook                         │
│      → OneLake (Delta)                              │
│          → DirectLake Semantic Model (zero-copy)    │
└──────────────────────────────────────────────────────┘
```

---

## 3. Semantic / Data Model Layer

| Concept | Qlik Sense | Power BI | Microsoft Fabric |
|:--------|:-----------|:---------|:-----------------|
| **Model type** | Associative (star/snowflake auto-join) | Star schema (explicit relationships) | Star schema (TMDL) |
| **Relationships** | Automatic association by field name | Explicit (1:1, 1:N, M:N) with cross-filter | Same as PBI + DirectLake |
| **Measures** | Master Measures (Qlik expressions) | DAX Measures (in model) | DAX Measures |
| **Dimensions** | Master Dimensions (field + label) | Columns + Hierarchies | Columns + Hierarchies |
| **Calculated columns** | Load script / expression | DAX calculated columns | DAX or Spark-computed |
| **Calculated tables** | Load script RESIDENT | DAX (DATATABLE, CALENDAR) | DAX or Delta table |
| **Calendar/Date table** | Master Calendar (script) | Auto date/time or DAX CALENDAR | Same, or Lakehouse date dim |
| **Hierarchies** | Drill groups (dimensions) | Explicit hierarchies in TMDL | Same |
| **Parameters** | Variables (`LET`/`SET`) | What-If parameters (GENERATESERIES) | Same |
| **Variables** | `$(vVariable)` dollar-sign expansion | DAX measures / parameters | Same |
| **Set Analysis** | `{<Field={Value}>}` | `CALCULATE(…, filter)` | Same |
| **Aggregation scoping** | `Aggr(Sum(X), Dim)` | `SUMX(VALUES(…), …)` iterators | Same |
| **Inter-record** | `Previous()`, `Above()`, `Peek()` | `OFFSET()`, `WINDOW()` (DAX) | Same |
| **Model format** | Binary in .qvf | TMDL (text) in .pbip | TMDL (text) |
| **Shared model** | N/A (each app has own model) | Shared Semantic Model | Shared Semantic Model |
| **Thin reports** | N/A | Live-connected reports | Live-connected reports |

---

## 4. Visualization & Reporting Layer

| Concept | Qlik Sense | Power BI | Microsoft Fabric |
|:--------|:-----------|:---------|:-----------------|
| **Report container** | App → Sheets | Report → Pages | Report → Pages |
| **Visual types** | 30+ native + extensions | 30+ native + AppSource marketplace | Same as PBI |
| **Custom visuals** | Extensions (JavaScript) | Custom visuals (TypeScript/R/Python) | Same |
| **Filters** | Filter pane / Selections bar | Filter pane / Slicers | Same |
| **Bookmarks** | Bookmarks (selection state) | Bookmarks (visibility + filter state) | Same |
| **Drill-down** | Master dimension drill groups | Drill-down / Drill-through pages | Same |
| **Tooltips** | Custom tooltip objects | Tooltip pages | Same |
| **Conditional show/hide** | Show condition (expression) | Bookmark toggle / Dynamic visibility | Same |
| **Themes** | Custom theme JSON | Theme JSON (dataColors, etc.) | Same |
| **Responsive layout** | Grid layout (auto-resize) | Canvas (fixed) or responsive containers | Same |
| **Stories** | Data Storytelling (slides) | PowerPoint export / Metrics | Same |
| **Paginated reports** | NPrinting | Paginated Reports (RDL) | Paginated Reports |
| **Alerting** | Data-driven alerts | Data-driven alerts | Same + Data Activator |
| **Mobile** | Qlik Sense Mobile app | Power BI Mobile app | Same |
| **Embedded** | Mashup API (iframe/JS) | Embedded analytics (JS SDK) | Same |
| **Natural language** | Insight Advisor (NLP) | Q&A visual | Copilot in Power BI |

---

## 5. Security & Governance

| Concept | Qlik Sense | Power BI | Microsoft Fabric |
|:--------|:-----------|:---------|:-----------------|
| **Row-Level Security** | Section Access (LOAD-based) | RLS Roles (DAX filterExpression) | Same + OneLake RBAC |
| **Object-Level Security** | OMIT columns in Section Access | OLS (perspectives) | Same |
| **Authentication** | Windows AD / SAML / OIDC | Azure AD / Entra ID | Entra ID |
| **Authorization** | Security Rules (QMC) | Workspace roles + App permissions | Workspace roles + Item permissions |
| **Data sensitivity** | N/A | Sensitivity labels (MIP) | Sensitivity labels + Purview |
| **Audit** | QMC audit logs | Activity logs / Audit API | Unified audit + Purview |
| **Data lineage** | Impact analysis (limited) | Lineage view | Purview lineage (end-to-end) |
| **Certification** | N/A | Certified / Promoted datasets | Endorsed (Certified/Promoted) |
| **Tenant governance** | QMC admin | Admin portal + tenant settings | Admin portal + Capacity + Domains |

### RLS Migration Pattern

```
┌─── Qlik Section Access ────────────────────────┐
│  Section Access;                                │
│  LOAD * INLINE [                                │
│    ACCESS, USERID,       FIELD, VALUE           │
│    USER,   user@org.com, Region, "West"         │
│  ];                                             │
│  Section Application;                           │
└─────────────────────────────────────────────────┘
                    ↓ migrates to ↓
┌─── Power BI / Fabric RLS ──────────────────────┐
│  role 'WestRegion'                              │
│    filterExpression =                           │
│      [Region] = "West"                          │
│      && USERPRINCIPALNAME() = "user@org.com"    │
│                                                 │
│  // Assigned in PBI Service / Fabric workspace  │
└─────────────────────────────────────────────────┘
```

---

## 6. Deployment & Administration

| Concept | Qlik Sense | Power BI | Microsoft Fabric |
|:--------|:-----------|:---------|:-----------------|
| **Deployment unit** | QVF app → Stream | .pbix → Workspace → App | Items → Workspace |
| **Deployment pipeline** | N/A (manual or API) | Deployment pipelines (Dev→Test→Prod) | Deployment pipelines |
| **CI/CD** | CLI tools / API | Azure DevOps + REST API + PBIP | Git integration + REST API |
| **Server admin** | QMC (Qlik Management Console) | Admin Portal | Admin Portal + Capacity mgmt |
| **Scheduling** | Tasks (QMC scheduler) | Scheduled Refresh | Scheduled Refresh + Pipelines |
| **Gateway** | Qlik DataTransfer (on-prem) | On-premises Data Gateway | On-premises Data Gateway |
| **Capacity model** | Server license (tokens/cores) | Per-user (Pro/PPU) or Capacity (P/F) | Fabric Capacity Units (CU) |
| **API** | QRS API + Engine API (WebSocket) | REST API + XMLA endpoint | REST API + XMLA + SQL + Spark |
| **Migration tooling** | N/A | **This project!** 🚀 | **This project!** (--output-format fabric) |

---

## 7. AI & Advanced Analytics

| Concept | Qlik Sense | Power BI | Microsoft Fabric |
|:--------|:-----------|:---------|:-----------------|
| **AI assistant** | Insight Advisor | Copilot in Power BI | Copilot (cross-experience) |
| **AutoML** | Qlik AutoML (separate) | N/A (use Azure ML) | ML models in Notebooks |
| **NLP search** | Insight Advisor Chat | Q&A visual | Copilot natural language |
| **Anomaly detection** | N/A | Anomaly detection visual | Data Activator |
| **Key influencers** | N/A | Key Influencers visual | Same |
| **Predictive** | Qlik Predict | Azure ML + R/Python visuals | Spark ML in Notebooks |
| **Smart narratives** | N/A | Smart Narrative visual | Same |

---

## 8. Data Integration & Prep Comparison

| Concept | Qlik Sense | Power BI | Microsoft Fabric |
|:--------|:-----------|:---------|:-----------------|
| **Visual data prep** | Data Manager | Power Query Editor | Dataflow Gen2 |
| **Script-based ETL** | Load Script | Power Query M (Advanced Editor) | Notebooks (PySpark/SQL) |
| **CDC / Replication** | Qlik Replicate | N/A (use ADF) | Mirroring + Data Pipeline |
| **Data profiling** | Data Manager profiling | Column profiling in PQ Editor | Data profiling + Purview |
| **Data quality** | N/A | N/A | Data Quality rules (preview) |
| **Flow orchestration** | N/A | Dataflows | Data Factory Pipelines |
| **Prep flows** | Qlik Sense scripting (no visual prep) | Dataflows Gen2 | Data Factory + Notebooks |

---

## 9. Migration Decision Matrix

Use this to decide **where** each Qlik component should land:

| Qlik Component | Small/Medium (PBI) | Enterprise (Fabric) |
|:---------------|:-------------------|:--------------------|
| QVD files | Import mode (Power Query) | OneLake (Delta via Dataflow) |
| Load scripts | Power Query M | Notebooks (PySpark) or Dataflow Gen2 |
| Data model | TMDL Semantic Model (Import) | TMDL Semantic Model (DirectLake) |
| Visualizations | Power BI Report (.pbip) | Power BI Report (.pbip) |
| Section Access | RLS roles in model | RLS roles + OneLake RBAC |
| Scheduled tasks | Scheduled Refresh | Data Pipeline orchestration |
| NPrinting reports | Paginated Reports | Paginated Reports |
| Qlik Replicate (CDC) | Azure Data Factory | Fabric Mirroring |
| Extensions | Custom visuals (AppSource) | Custom visuals |
| Mashups | Power BI Embedded | Power BI Embedded |

---

## 10. Key Conceptual Differences

### Associative vs Star Schema
```
Qlik: ANY field can filter ANY other field (associative)
 ┌─────┐   ┌─────┐   ┌─────┐
 │ T1  │───│ T2  │───│ T3  │   All connections are bidirectional
 └─────┘   └─────┘   └─────┘   by default — green/white/gray selection model

PBI:  Explicit relationships, directional cross-filtering
 ┌─────┐   ┌─────┐   ┌─────┐
 │Dim1 │──→│Fact │←──│Dim2 │   Star schema: dimensions filter facts
 └─────┘   └─────┘   └─────┘   Cross-filter direction matters
```

**Migration impact:** Qlik's auto-association means users expect **any selection to filter everything**. In PBI, you must:
1. Build explicit relationships
2. Set cross-filter direction (`bothDirections` if needed)
3. Use `CROSSFILTER()` DAX function for dynamic switching
4. Consider bidirectional filtering carefully (performance + ambiguity)

### Set Analysis vs CALCULATE
```
Qlik:  Sum({<Year={2024}, Region={"West","East"}>} Sales)
PBI:   CALCULATE(SUM(Sales), Year[Year] = 2024, Region[Region] IN {"West","East"})
```
Both achieve the same result — filter context modification — but:
- Qlik Set Analysis is **declarative** (describe the set)
- DAX CALCULATE is **imperative** (apply filter arguments)

### Variables vs Measures
```
Qlik:  SET vTarget = 1000000;        // Used as $(vTarget) anywhere
PBI:   Target = 1000000              // DAX measure, evaluated in context
       or What-If parameter          // GENERATESERIES + SELECTEDVALUE
```

### In-Memory vs DirectLake
```
Qlik:  ALL data loaded into RAM — always in-memory, no fallback
PBI:   Import (VertiPaq in-memory) or DirectQuery (query passthrough)
Fabric: DirectLake — reads Delta/Parquet from OneLake, zero-copy,
        falls back to DirectQuery if data exceeds memory
```

---

## Quick Reference Card

| I want to… | Qlik Sense | Power BI / Fabric |
|:-----------|:-----------|:------------------|
| Load data from SQL | `SQL SELECT * FROM …` | `Sql.Database("server","db")` |
| Filter a measure | `{<Field={Val}>}` | `CALCULATE(…, filter)` |
| Create a running total | `RangeSum(Above(…))` | `CALCULATE(SUM(…), WINDOW(…))` |
| Reference another table | Automatic association | `RELATED()` / `LOOKUPVALUE()` |
| Row-level security | Section Access | RLS role + `USERPRINCIPALNAME()` |
| Schedule a refresh | QMC Task | Scheduled Refresh / Pipeline |
| Embed in a web app | Mashup API | Power BI Embedded SDK |
| Use AI / NLP | Insight Advisor | Copilot / Q&A visual |
| Store reusable data | QVD files | OneLake Delta tables |
| Share across reports | N/A (per-app model) | Shared Semantic Model |

---

*Generated for QlikToPowerBI v9.1.0 — see [MAPPING_REFERENCE.md](MAPPING_REFERENCE.md) for detailed function-level mappings.*
