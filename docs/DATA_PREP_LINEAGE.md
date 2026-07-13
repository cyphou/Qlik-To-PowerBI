# Data Preparation Lineage — Complete Guide

## Overview

Data Prep Lineage tracks all data transformation operations in the Qlik-to-PowerBI migration pipeline, visualizing the complete flow from raw data sources through preparation stages to semantic models.

Current lineage extraction supports a multi-layer medallion-style view with explicit layer, purpose, complexity, and source-count metadata for each node.

## Features

### Qlik Load Script Analysis
Automatically extracts and visualizes:

- **Source Ingestion**: LOAD FROM (CSV, Excel, etc.)
- **Direct Queries**: SQL SELECT statements with database references
- **Generated Data**: AUTOGENERATE for calendar tables
- **Transformations**: RESIDENT loads, JOINs, CONCATENATEs
- **Security**: Section Access (RLS) configuration
- **Output**: STORE operations
- **Layering**: Bronze, Silver, Gold, and Mart classification when comments or table names provide the signal
- **Purpose**: Ingestion, transformation, aggregation, dimension, fact, export, and security tagging
- **Complexity**: Simple, moderate, and complex operation scoring

### Power Query M Transformations (Extensible)
Parseable patterns include:

- **Header Promotion**: PromoteHeaders operations
- **Type Conversions**: TransformColumnTypes
- **Row Filters**: FilterRows and conditional selections
- **Column Operations**: Rename, remove, reorder, split, merge
- **Data Aggregations**: GroupBy, Pivot, Unpivot
- **Custom Columns**: AddColumn, AddIndexColumn

### Fabric/ETL Stages
Supports upcoming integration with:
- Dataflow Gen2 ingestion
- PySpark notebook transformations
- Data Pipeline orchestration
- Lakehouse operations

## Generated Visualization

### HTML Timeline/Swim-Lane View

Each comparison report includes an interactive **Data Preparation Lineage** section showing:

```
┌─────────────────────────────────────────────┐
│ 📊 Data Preparation Lineage                │
├─────────────────────────────────────────────┤
│ 19 Transformation Steps | 17 Data Flows     │
├─────────────────────────────────────────────┤
│ ┌─ Bronze ───────────────────────────────┐ │
│ │ • RawSales                             │ │
│ │ • RawCustomers                         │ │
│ │ • RawProducts                          │ │
│ │ • RawSuppliers                         │ │
│ │ • StoreLocations                       │ │
│ └────────────────────────────────────────┘ │
│                  ↓                          │
│ ┌─ Silver ───────────────────────────────┐ │
│ │ • SalesFacts                           │ │
│ │ • Customers                            │ │
│ │ • Products                             │ │
│ └────────────────────────────────────────┘ │
│                  ↓                          │
│ ┌─ Gold ────────────────────────────────┐ │
│ │ • MonthlySummary                       │ │
│ │ • CustomerMetrics                      │ │
│ │ • ProductMetrics                       │ │
│ │ • RegionalAnalysis                     │ │
│ └────────────────────────────────────────┘ │
│                  ↓                          │
│ ┌─ Mart ────────────────────────────────┐ │
│ │ • FactSales                            │ │
│ │ • STORE outputs                        │ │
│ └────────────────────────────────────────┘ │
└─────────────────────────────────────────────┘
```

### Interactive Features

- **Click Nodes**: View transformation details (source, target, operation code)
- **Layer Grouping**: Organized by Bronze / Silver / Gold / Mart when available
- **Color Coding**: Different colors for each transformation type and layer lane
- **Purpose Tags**: Highlights ingestion, transformation, aggregation, export, and security steps
- **Legend**: Shows node type breakdown, counts, and complexity hints

## Usage

### Enable Data Prep Lineage (Default)

```bash
python migrate.py app.qvf --compare
```

Result: Comparison report includes both:
- End-to-End Data Lineage (field → DAX → visual)
- Data Preparation Lineage (source → transform → load)

For JSON-based runs, the comparison report now falls back to the source app JSON when `qlik_export/loadscript.json` is not available.
For nested corpora, pair comparison runs with `--batch-recursive` so the batch collector discovers every supported export.

### Generate the Multi-Layer Example

```bash
python migrate.py examples/qlik/qlik_exports/complex_dwh_demo.json --compare --data-prep-lineage
```

This example demonstrates:
- Bronze raw ingestion from CSV, Excel, and SQL sources
- Silver resident transformations with cleaning and deduplication
- Gold grouping and aggregation with `GROUP BY`
- Mart fact-table consolidation and QVD export

### Disable Data Prep Lineage

```bash
python migrate.py app.qvf --no-data-prep-lineage
```

### Example: Multi-Layer Warehouse Application

### Extracted Lineage

| Node ID | Layer | Purpose | Label | Source | Target |
|---------|-------|---------|-------|--------|--------|
| `qlik_section_access` | bronze | security | Section Access (RLS Configuration) | — | — |
| `qlik_load_1` | bronze | ingestion | Load RawSales from CSV | data/sources/sales_transactions.csv | RawSales |
| `qlik_load_2` | bronze | ingestion | Load RawCustomers from Excel | data/sources/customers.xlsx | RawCustomers |
| `qlik_sql_3` | bronze | ingestion | SQL Load from Products | ProductCatalog.dbo.Products | RawProducts |
| `qlik_resident_4` | silver | transformation | Transform SalesFacts | RawSales | SalesFacts |
| `qlik_resident_5` | silver | transformation | Transform Customers | RawCustomers | Customers |
| `qlik_resident_6` | silver | transformation | Transform Products | RawProducts | Products |
| `qlik_resident_7` | gold | aggregation | MonthlySummary | SalesFacts | MonthlySummary |
| `qlik_resident_8` | gold | aggregation | CustomerMetrics | SalesFacts | CustomerMetrics |
| `qlik_resident_9` | gold | aggregation | ProductMetrics | SalesFacts | ProductMetrics |
| `qlik_resident_10` | gold | aggregation | RegionalAnalysis | SalesFacts | RegionalAnalysis |
| `qlik_concat_11` | mart | fact_table | FactSales | SalesFacts | FactSales |
| `qlik_store_12` | mart | export | Store FactSales | FactSales | FactSales.qvd |

### Data Flows

Sequential data flow edges showing transformation chain:
1. Section Access → raw ingestion nodes
2. RawSales / RawCustomers / RawProducts → resident cleaning steps
3. Resident cleaning steps → aggregation nodes
4. Aggregation nodes → fact consolidation
5. Fact consolidation → STORE exports

## Architecture

### Module: `powerbi_import/data_prep_lineage.py`

**Classes**:
- `TransformStage` (Enum): 30+ transformation types
- `DataPrepNode`: Individual transformation step with metadata including `layer`, `purpose`, `complexity`, and `source_count`
- `DataPrepEdge`: Data flow connection between nodes
- `DataPrepLineage`: Complete transformation graph

**Functions**:
- `parse_qlik_script_lineage()`: Extract lineage from Qlik load script
- `parse_m_query_lineage()`: Extract lineage from Power Query M code
- `build_data_prep_lineage()`: Combine all sources into unified lineage
- `generate_data_prep_lineage_html()`: Create interactive visualization

### Integration

**Comparison Report** (`comparison_report.py`):
- Auto-discovers lineage_map.json from migration output
- Parses `loadscript.json` for Qlik script analysis
- Falls back to the source app JSON when a direct load script file is unavailable
- Embeds lineage section with statistics and visualization
- Enables interactive node detail modals

**CLI Support** (`migrate.py`):
- `--data-prep-lineage`: Enable data prep lineage (default)
- `--no-data-prep-lineage`: Disable if needed

## Transformation Type Catalog

### Connection & Ingestion
- `CONNECTION`: Data source connection
- `SOURCE`: Raw source identification
- `INGESTION`: Data ingestion operation

### Qlik Load Script Operations
- `QLIK_LOAD`: LOAD FROM CSV/Excel/database
- `QLIK_SQL`: SQL SELECT direct query
- `QLIK_RESIDENT`: Transform from resident table
- `QLIK_JOIN`: JOIN operations (LEFT/INNER/RIGHT/OUTER)
- `QLIK_CONCATENATE`: CONCATENATE unions
- `QLIK_MAPPING`: MAPPING clause operations
- `QLIK_STORE`: STORE to output file
- `QLIK_AUTOGENERATE`: AUTOGENERATE synthetic data
- `QLIK_SCRIPT_VARIABLE`: Script-level variables
- `QLIK_IF_STATEMENT`: Conditional load logic
- `QLIK_FOR_LOOP`: Iterative loading

### Power Query M Transformations
- `M_QUERY`: Generic M query operation
- `M_SOURCE`: Source step (Excel, CSV, database, web)
- `M_PROMOTED_HEADERS`: PromoteHeaders step
- `M_CHANGED_TYPE`: TransformColumnTypes step
- `M_FILTERED_ROWS`: FilterRows step
- `M_REMOVED_COLUMNS`: RemoveColumns step
- `M_RENAMED_COLUMNS`: RenameColumns step
- `M_REORDERED_COLUMNS`: ReorderColumns step
- `M_SPLIT_COLUMN`: SplitColumn operation
- `M_MERGED_COLUMNS`: MergeColumns operation
- `M_GROUPED`: GroupBy aggregation
- `M_PIVOTED`: Pivot transformation
- `M_UNPIVOTED`: Unpivot operation
- `M_CUSTOM_COLUMN`: AddColumn/custom calculation

### Fabric/ETL Stages
- `FABRIC_DATAFLOW`: Dataflow Gen2 ingestion
- `FABRIC_NOTEBOOK`: Spark/Python notebook transformation
- `FABRIC_PIPELINE`: Multi-stage data pipeline
- `FABRIC_LAKEHOUSE`: Lakehouse table load
- `SPARK_SQL`: Spark SQL transformation
- `SPARK_TRANSFORM`: PySpark DataFrame operation

### Load & Model
- `SEMANTIC_MODEL`: Semantic model definition
- `TMDL_TABLE`: TMDL table creation
- `POWER_BI_DATASET`: Power BI dataset load

## Output Files

Generated in comparison report:

```html
<div class="lineage-section">
  <h1>📊 Data Preparation Lineage</h1>
  <div class="stats">
    <div>8 Transformation Steps</div>
    <div>6 Data Flows</div>
    <div>1 Stage</div>
  </div>
  
  <div class="timeline">
    <!-- Swim-lane view with transformation nodes -->
    <!-- Each node is clickable with modal details -->
  </div>
  
  <div class="legend">
    <!-- Color-coded legend of node types -->
  </div>
</div>
```

## Benefits

✅ **Complete Transparency**: See exactly how data flows through preparation stages
✅ **Impact Analysis**: Identify which transformations affect specific columns
✅ **Debugging**: Trace data quality issues to specific load/transform steps
✅ **Documentation**: Auto-generated lineage serves as technical documentation
✅ **Governance**: Track data sources, security configurations, and transformations
✅ **Validation**: Verify all Qlik operations were correctly converted to Power BI
✅ **Training**: Visual lineage helps teams understand data architecture

## Roadmap

### Phase 1 (Current) ✅
- [x] Qlik load script parsing (LOAD, SQL, RESIDENT, JOIN, CONCATENATE, STORE)
- [x] Section Access (RLS) extraction
- [x] AUTOGENERATE recognition
- [x] Interactive HTML visualization
- [x] Integration with comparison reports

### Phase 2 (Planned)
- [ ] Power Query M step-by-step parsing
- [ ] Qlik script variable resolution and propagation
- [ ] Conditional logic (IF/ELSE) representation
- [ ] Loop iteration visualization

### Phase 3 (Planned)
- [ ] Fabric Dataflow Gen2 lineage
- [ ] PySpark/notebook transformation lineage
- [ ] Multi-app merge impact visualization
- [ ] Data quality metrics integration

### Phase 4 (Planned)
- [ ] GraphQL API for programmatic lineage access
- [ ] Column-level lineage (field-to-field tracking)
- [ ] Lineage export (GraphML, Neo4j)
- [ ] Lineage diff reports for version comparison

## API Reference

### Parse Qlik Script

```python
from powerbi_import.data_prep_lineage import parse_qlik_script_lineage

with open('loadscript.json') as f:
    script = json.load(f)['script']
    
lineage = parse_qlik_script_lineage(script)
print(f"Nodes: {lineage.node_count}")
print(f"Edges: {lineage.edge_count}")

# Access transformation chain
chain = lineage.get_transformation_chain('qlik_section_access')
print(f"Transformation chain: {chain}")
```

### Generate HTML Visualization

```python
from powerbi_import.data_prep_lineage import generate_data_prep_lineage_html

html = generate_data_prep_lineage_html(
    lineage,
    title='Data Preparation Lineage',
    output_file='lineage_report.html'
)
```

### Export to JSON

```python
lineage.to_json('lineage.json')

# Structure:
# {
#   "app_name": "qlik_sales_discovery_demo",
#   "source_type": "qlik",
#   "nodes": [...],
#   "edges": [...],
#   "stage_order": [...]
# }
```

## Troubleshooting

### No Data Prep Lineage Appearing

**Check 1**: Verify `loadscript.json` exists
```bash
ls qlik_export/loadscript.json
```

**Check 2**: Verify script content is not empty
```bash
python -c "import json; print(len(json.load(open('qlik_export/loadscript.json'))['script']))"
```

**Check 3**: If you migrated from a JSON export, confirm the source file still contains the `script` field. The report now falls back to that field when `loadscript.json` is unavailable.

**Check 4**: Enable debug logging
```bash
python migrate.py app.qvf --compare --verbose 2>&1 | grep -i lineage
```

### Incomplete Transformation Chain

**Cause**: Regex patterns may not match all Qlik syntax variations

**Solution**: Add custom patterns to `parse_qlik_script_lineage()`:
```python
# Pattern: your_qlik_operation
if re.search(r'YOUR_PATTERN', stmt, re.IGNORECASE):
    # Add node and edge
```

### Missing SQL Queries

**Check**: Verify SQL syntax is supported
```
✓ SQL SELECT ... FROM ... ;
✓ Products: SQL SELECT ... FROM ... ;
✗ exec sp_execute ... (stored procedures not supported yet)
```

## Contributing

To add support for new Qlik script patterns:

1. Update `TransformStage` enum with new type
2. Add regex pattern to `parse_qlik_script_lineage()`
3. Create node with appropriate stage
4. Add test case in `tests/test_data_prep_lineage.py`

Example:

```python
# Add to TransformStage
QLIK_YOUR_OPERATION = 'qlik_your_operation'

# Add pattern to parse_qlik_script_lineage()
if re.search(r'YOUR_PATTERN', stmt, re.IGNORECASE):
    lineage.add_node(
        f'qlik_your_op_{step_counter}',
        TransformStage.QLIK_YOUR_OPERATION,
        'Your Operation Label',
        transformation_type='your_operation'
    )
```

## See Also

- [END_TO_END_LINEAGE.md](END_TO_END_LINEAGE.md) - Field-level lineage (Qlik field → DAX → visual)
- [MAPPING_REFERENCE.md](MAPPING_REFERENCE.md) - Visual and function mappings
- [QLIK_TO_DAX_REFERENCE.md](QLIK_TO_DAX_REFERENCE.md) - DAX conversion reference

---

**Version**: 1.0  
**Last Updated**: June 2026  
**Status**: Production Ready ✅
