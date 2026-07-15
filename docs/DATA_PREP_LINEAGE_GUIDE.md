<!-- DOC-SHINY-BANNER -->
![Documentation](https://img.shields.io/badge/Documentation-Shiny_Style-0A66C2?style=flat-square&logo=readthedocs&logoColor=white)
![Maintained](https://img.shields.io/badge/Maintained-2026-2EA44F?style=flat-square&logo=github&logoColor=white)
![Navigation](https://img.shields.io/badge/Navigation-Quick_Access-6F42C1?style=flat-square&logo=bookstack&logoColor=white)
# Multi-Layer Data Preparation Lineage — Complete Examples Guide

**Status**: ✅ COMPLETE — Fully functional with complex warehouse example

## Overview

This guide demonstrates comprehensive multi-layer data preparation lineage extraction for Qlik applications, supporting the **Medallion Architecture** pattern (Bronze → Silver → Gold → Mart layers).

The current implementation classifies each node by layer, purpose, complexity, and source count, and it falls back to the source JSON when a standalone load script file is not available in the extracted workspace.

### What is Data Prep Lineage?

Data prep lineage tracks the **transformation flow** of data through your pipeline:

```
Raw Data (Bronze) → Cleaned Data (Silver) → Business KPIs (Gold) → Analytics Schema (Mart)
   ↓                    ↓                       ↓                       ↓
Sales.csv         SalesFacts               MonthlySummary            FactSales
Customers.xlsx    Customers               CustomerMetrics           BudgetFacts
Products DB       Products                ProductMetrics            ConsolidatedFacts
```

---

## Architecture: 4-Layer Data Warehouse

### Layer 1: BRONZE (Raw Ingestion)
- **Purpose**: Load data as-is from external sources
- **Characteristics**: No transformations, minimal validation
- **Data Sources**: CSV files, Excel workbooks, SQL databases, APIs
- **Examples**:
  - `RawSales` ← CSV file (sales_transactions.csv)
  - `RawCustomers` ← Excel workbook (customers.xlsx)
  - `RawProducts` ← SQL database (ProductCatalog.dbo.Products)

### Layer 2: SILVER (Cleaned & Standardized)
- **Purpose**: Clean, deduplicate, and standardize data
- **Characteristics**: Applied business rules, data quality checks
- **Operations**: 
  - Column renaming/standardization (TRIM, LOWER, DATE conversion)
  - Deduplication (LOAD DISTINCT)
  - Filtering (WHERE clauses)
  - Basic calculations (computed fields, adjustments)
- **Examples**:
  - `SalesFacts` ← RawSales (filtered, enriched)
  - `Customers` ← RawCustomers (deduplicated)
  - `Products` ← RawProducts (standardized columns)

### Layer 3: GOLD (Business Aggregations & KPIs)
- **Purpose**: Create aggregated metrics and business logic
- **Characteristics**: GROUP BY operations, pre-calculated metrics
- **Operations**: 
  - Aggregations (SUM, COUNT, AVG, MIN, MAX)
  - Multi-table aggregations (facts with dimensions)
  - Complex calculations (lifecycle metrics, cohort analysis)
- **Examples**:
  - `MonthlySummary` ← SalesFacts GROUP BY (Year, Month, Region)
  - `CustomerMetrics` ← SalesFacts GROUP BY (CustomerID, Segment)
  - `ProductMetrics` ← SalesFacts GROUP BY (ProductID, Category)
  - `RegionalAnalysis` ← SalesFacts GROUP BY (RegionCode)

### Layer 4: MART (Dimensional Star Schema)
- **Purpose**: Optimized for analytics and reporting
- **Characteristics**: Star/snowflake schema, denormalization
- **Operations**:
  - Fact table consolidation (CONCATENATE / UNION)
  - Dimension table organization
  - Multi-source fact tables (actual + budget + target)
- **Examples**:
  - `FactSales` ← SalesFacts + Budget adjustments
  - `BudgetFacts` ← Budget data (parallel fact table)
  - `TargetFacts` ← Sales targets (parallel fact table)
  - `ConsolidatedFacts` ← Multi-source UNION

---

## Complete Example: Complex DWH Demo

### File Structure
```
examples/
  qlik/
    qlik_exports/
      complex_dwh_demo.json       ← Full example with all 4 layers
```

### Example Lineage Output

```
COMPLEX LINEAGE ANALYSIS
Total Nodes: 19
Total Edges: 17

BY LAYER:
  BRONZE       -  1 operations
  SILVER       -  4 operations
  GOLD         -  4 operations
  MART         - 10 operations

BY PURPOSE:
  aggregation          -  4 operations
  export               -  5 operations
  ingestion            -  5 operations
  security             -  1 operations
  transformation       -  4 operations

TRANSFORMATION CHAIN:
  1. Load RawSales from data/sources/sales_transactions.csv
  2. Load RawCustomers from data/sources/customers.xlsx
  3. Load RawProducts from SQL [ProductCatalog].[dbo].[Products]
  4. Load RawSuppliers from data/sources/suppliers.xlsx
  5. Load StoreLocations from data/sources/store_locations.csv
  6. Transform SalesFacts (RESIDENT RawSales with filters)
  7. Transform Customers (RESIDENT RawCustomers deduplicated)
  8. Transform Products (RESIDENT RawProducts standardized)
  9. Aggregate MonthlySummary (GROUP BY Year, Month, Region)
  10. Aggregate CustomerMetrics (GROUP BY CustomerID, Segment)
  11. Aggregate ProductMetrics (GROUP BY ProductID, Category)
  12. Aggregate RegionalAnalysis (GROUP BY RegionCode)
  13. Consolidate FactSales (CONCATENATE with UNION SELECT)
  14. Export to QVD files (5 STORE operations)
```

---

## Qlik Script Structure

### Bronze Layer Example
```qlik
// ========== Raw Sales Transactions ==========
RawSales:
LOAD
    OrderID,
    OrderDate,
    CustomerID,
    ProductID,
    Quantity,
    UnitPrice,
    SalesAmount,
    RegionCode
FROM [data/sources/sales_transactions.csv]
(txt, codepage is 1252, embedded labels, delimiter is ',', msq);

// ========== Raw Customers ==========
RawCustomers:
LOAD
    CustomerID,
    CustomerName,
    Email,
    RegistrationDate,
    CustomerSegment
FROM [data/sources/customers.xlsx]
(ooxml, embedded labels, table is Sheet1);

// ========== SQL Database Source ==========
RawProducts:
SQL SELECT 
    ProductID,
    ProductName,
    CategoryID,
    CategoryName,
    UnitCost,
    ListPrice
FROM [ProductCatalog].[dbo].[Products];
```

### Silver Layer Example
```qlik
// ========== Cleaned Sales Facts ==========
SalesFacts:
LOAD
    OrderID & '-' & CustomerID & '-' & ProductID as SalesKey,
    OrderID,
    DATE(OrderDate) as OrderDate,
    CustomerID,
    ProductID,
    TRIM(RegionCode) as RegionCode,
    Quantity,
    UnitPrice,
    SalesAmount,
    SalesAmount * (1 + IF(Quantity > 100, 0.05, 0)) as AdjustedSalesAmount
RESIDENT RawSales
WHERE OrderDate >= '$(vStartDate)' AND OrderDate <= '$(vEndDate)';

// ========== Deduplicated Customers ==========
Customers:
LOAD DISTINCT
    CustomerID,
    TRIM(CustomerName) as CustomerName,
    LOWER(TRIM(Email)) as Email,
    DATE(RegistrationDate) as RegistrationDate,
    TRIM(CustomerSegment) as CustomerSegment
RESIDENT RawCustomers;
```

### Gold Layer Example
```qlik
// ========== Monthly Sales Summary ==========
MonthlySummary:
LOAD
    YEAR(OrderDate) & '-' & MONTH(OrderDate) as YearMonth,
    YEAR(OrderDate) as Year,
    MONTH(OrderDate) as Month,
    RegionCode,
    SUM(SalesAmount) as TotalSales,
    COUNT(DISTINCT OrderID) as OrderCount,
    COUNT(DISTINCT CustomerID) as CustomerCount,
    AVG(SalesAmount) as AvgOrderValue
RESIDENT SalesFacts
GROUP BY 
    YEAR(OrderDate),
    MONTH(OrderDate),
    RegionCode;

// ========== Customer Cohort Analysis ==========
CustomerMetrics:
LOAD
    CustomerID,
    CustomerSegment,
    MIN(OrderDate) as FirstOrderDate,
    MAX(OrderDate) as LastOrderDate,
    COUNT(DISTINCT OrderID) as TotalOrders,
    SUM(SalesAmount) as LifetimeSalesValue
RESIDENT SalesFacts
GROUP BY CustomerID, CustomerSegment;
```

### Mart Layer Example
```qlik
// ========== Fact Table: Sales ==========
FactSales:
CONCATENATE (SalesFacts)
LOAD
    SalesKey,
    OrderID,
    OrderDate,
    CustomerID,
    ProductID,
    RegionCode,
    Quantity,
    SalesAmount,
    AdjustedSalesAmount,
    'ACTUAL' as RecordType
RESIDENT SalesFacts;

// ========== Multi-Source Consolidation ==========
ConsolidatedFacts:
LOAD * FROM [data/warehouse/fact_sales.qvd]
UNION
LOAD * FROM [data/warehouse/budget_facts.qvd]
UNION
LOAD * FROM [data/warehouse/target_facts.qvd];
```

---

## Lineage Extraction Features

### Node Metadata Tracked

Each transformation node tracks:

| Field | Description | Example |
|-------|-------------|---------|
| `id` | Unique identifier | `qlik_load_0`, `qlik_resident_1` |
| `stage` | Transformation type | `QLIK_LOAD`, `QLIK_SQL`, `QLIK_JOIN` |
| `label` | Human-readable name | `Load RawSales from CSV` |
| `source_table` | Input data source | `sales_transactions.csv`, `RawSales` |
| `target_table` | Output data object | `RawSales`, `SalesFacts` |
| `layer` | Data warehouse layer | `bronze`, `silver`, `gold`, `mart` |
| `purpose` | Functional purpose | `ingestion`, `transformation`, `aggregation` |
| `complexity` | Operation complexity | `simple`, `moderate`, `complex` |
| `source_count` | Number of source tables | `1` (LOAD), `2` (JOIN), `3+` (UNION) |
| `operation_code` | Original statement (truncated) | `LOAD ... FROM [...]` |

### Layer Detection

Layers are detected from:
1. **Explicit LAYER comments** in script (first priority)
2. **Table naming patterns**:
   - `raw_*` / `bronze_*` → Bronze layer
   - `*_fact` / `*_measure` → Fact tables (Mart)
   - `*_dim` / `*_dimension` → Dimensions
   - `*_metric` / `*_summary` → Gold layer
3. **Operation type heuristics**:
   - `LOAD FROM` / `SQL SELECT` → Ingestion (Bronze)
   - `RESIDENT` → Transformation (Silver)
   - `GROUP BY` → Aggregation (Gold)

### Purpose Classification

Purpose is inferred from operations:

| Purpose | Detection | Examples |
|---------|-----------|----------|
| `ingestion` | LOAD FROM, SQL SELECT | RawSales, RawCustomers |
| `transformation` | RESIDENT LOAD | SalesFacts, Customers |
| `aggregation` | GROUP BY with SUM/AVG/COUNT | MonthlySummary, CustomerMetrics |
| `fact_table` | Table names with "fact"/"measure" | FactSales |
| `dimension` | Table names with "dim"/"dimension" | DimDate, DimProduct |
| `join` | JOIN operations | Multi-table enrichments |
| `union` | CONCATENATE/UNION | ConsolidatedFacts |
| `export` | STORE statements | Archive/QVD export |
| `security` | Section Access | RLS Configuration |

### Complexity Classification

Complexity indicates transformation difficulty:

| Level | Criteria | Examples |
|-------|----------|----------|
| `simple` | Basic LOAD, single source | Load CSV, Load Excel |
| `moderate` | Multi-step transforms, basic aggregation | GROUP BY single table, RESIDENT with filter |
| `complex` | Multi-source joins, complex aggregations | JOIN + GROUP BY, nested calculations |

---

## Usage: Extracting Lineage

### Python API

```python
from powerbi_import.data_prep_lineage import parse_qlik_script_lineage, generate_data_prep_lineage_html
import json

# Load Qlik script
with open('export.json', 'r') as f:
    data = json.load(f)
    script = data['script']

# Parse lineage
lineage = parse_qlik_script_lineage(script)

# Analyze by layer
nodes_by_layer = {}
for node in lineage.nodes.values():
    layer = node.layer
    if layer not in nodes_by_layer:
        nodes_by_layer[layer] = []
    nodes_by_layer[layer].append(node)

print(f"Bronze operations: {len(nodes_by_layer.get('bronze', []))}")
print(f"Silver operations: {len(nodes_by_layer.get('silver', []))}")
print(f"Gold operations: {len(nodes_by_layer.get('gold', []))}")
print(f"Mart operations: {len(nodes_by_layer.get('mart', []))}")

# Generate HTML visualization
html = generate_data_prep_lineage_html(lineage)
with open('lineage_visualization.html', 'w') as f:
    f.write(html)
```

### CLI Usage

```bash
# Full migration with data prep lineage
python migrate.py examples/qlik/qlik_exports/complex_dwh_demo.json \
  --output-dir output/lineage_demo \
  --compare \
  --data-prep-lineage

# Output includes:
# - MIGRATION_DASHBOARD_*.html (with lineage section)
# - project.pbip (Power BI project)
# - comparison_report.html (with data prep lineage visualization)
```

For larger nested corpora, use `--batch-recursive` with `--batch` so the comparison report can include lineage for every discovered export.

---

## Visualization

### Interactive HTML Report

The generated comparison report includes an interactive lineage section with:

1. **Swim-lane layout** grouped by transformation stage
2. **Color-coded nodes** by operation type:
   - Blue: Ingestion (LOAD, SQL SELECT)
   - Green: Transformation (RESIDENT)
   - Orange: Aggregation (GROUP BY)
   - Purple: Export/Storage (STORE)
3. **Interactive features**:
   - Click nodes to view details
   - Hover for transformation code preview
   - Filter by layer/purpose
4. **Statistics panel**:
   - Node count by stage
   - Edge count (data flows)
   - Complexity distribution
   - Layer breakdown

### Example HTML Output

```html
<div id="lineage-visualization">
  <canvas id="lineage-canvas"></canvas>
  <div id="node-details"></div>
  <div id="statistics">
    <h4>Lineage Statistics</h4>
    <ul>
      <li>Total Nodes: 19</li>
      <li>Total Edges: 17</li>
      <li>Bronze Layer: 1</li>
      <li>Silver Layer: 4</li>
      <li>Gold Layer: 4</li>
      <li>Mart Layer: 10</li>
    </ul>
  </div>
</div>
```

---

## Examples: Common Patterns

### Pattern 1: Simple Raw-to-Processed Pipeline

```qlik
// Bronze: Raw data
RawTransactions:
LOAD * FROM [transactions.csv] (csv, delimiter is ',');

// Silver: Cleaned data
Transactions:
LOAD
    TransactionID,
    DATE(TransactionDate) as Date,
    TRIM(CustomerID) as CustomerID,
    Amount
RESIDENT RawTransactions;

// Gold: Aggregated metrics
DailyMetrics:
LOAD
    Date,
    SUM(Amount) as DailyTotal,
    COUNT(DISTINCT CustomerID) as UniqueCustomers
RESIDENT Transactions
GROUP BY Date;
```

**Lineage Extraction**:
- 3 nodes (RawTransactions → Transactions → DailyMetrics)
- Layer progression: bronze → silver → gold
- Purpose progression: ingestion → transformation → aggregation

### Pattern 2: Multi-Source Fact Table

```qlik
// Bronze: Multiple sources
SalesOrders:
LOAD * FROM [sales_orders.csv] (csv);

CancellationData:
LOAD * FROM [cancellations.xlsx] (ooxml);

ReturnData:
LOAD * FROM [returns.xlsx] (ooxml);

// Silver: Unified transactions
Transactions:
LOAD OrderID, Amount FROM SalesOrders
WHERE OrderStatus = 'Completed';

// Gold: Fact table consolidation
FactTransactions:
LOAD
    OrderID,
    Amount,
    'Sales' as TransactionType
RESIDENT Transactions
UNION
LOAD
    OrderID,
    -Amount as Amount,
    'Cancellation' as TransactionType
RESIDENT CancellationData
UNION
LOAD
    OrderID,
    -Amount as Amount,
    'Return' as TransactionType
RESIDENT ReturnData;
```

**Lineage Extraction**:
- 6 nodes (3 sources → 1 unified → 1 consolidated fact table)
- Multi-source detection (source_count=3 for union)
- Purpose: ingestion → transformation → fact consolidation

### Pattern 3: Dimensional Modeling

```qlik
// Bronze: Raw dimensions & facts
RawCustomers:
LOAD * FROM [customers.csv];

RawOrders:
LOAD * FROM [orders.csv];

RawProducts:
LOAD * FROM [products.csv];

// Silver: Dimensions
DimCustomer:
LOAD DISTINCT
    CustomerID,
    TRIM(CustomerName) as CustomerName,
    TRIM(Country) as Country
RESIDENT RawCustomers;

DimProduct:
LOAD DISTINCT
    ProductID,
    TRIM(ProductName) as ProductName,
    TRIM(Category) as Category
RESIDENT RawProducts;

// Mart: Fact table with dimensions
FactOrders:
LOAD
    OrderID,
    OrderDate,
    CustomerID,
    ProductID,
    Quantity * UnitPrice as Amount
RESIDENT RawOrders;
```

**Lineage Extraction**:
- 6 nodes (3 sources → 2 dimensions + 1 fact)
- Purpose detection: dimensions vs facts
- Complexity: moderate (multi-table relationships)

---

## Advanced: Custom Layer Comments

Mark layers explicitly in your Qlik script:

```qlik
// ========== LAYER: BRONZE ==========
// Raw data ingestion - no transformations
RawSales:
LOAD * FROM [sales.csv];

RawCustomers:
LOAD * FROM [customers.xlsx];

// ========== LAYER: SILVER ==========
// Data cleaning and standardization
SalesFacts:
LOAD * RESIDENT RawSales WHERE Amount > 0;

Customers:
LOAD DISTINCT * RESIDENT RawCustomers;

// ========== LAYER: GOLD ==========
// Business aggregations and KPIs
MonthlySales:
LOAD
    Month,
    SUM(Amount) as MonthlyRevenue
RESIDENT SalesFacts
GROUP BY Month;

// ========== LAYER: MART ==========
// Analytics-ready star schema
FactSales:
CONCATENATE
LOAD * RESIDENT SalesFacts;
```

The parser automatically detects `LAYER: BRONZE`, `LAYER: SILVER`, etc.

---

## Integration with Migration Pipeline

### Step 1: Extract Qlik Application
```bash
python migrate.py app.qvf --output-dir output/
```

### Step 2: Review Data Prep Lineage
```bash
# Open generated comparison_report.html
# Look for "Data Preparation Lineage" section
# Verify layer categorization matches expectations
```

If you migrated from a JSON export, the report can recover the script directly from the source JSON when `qlik_export/loadscript.json` is missing.

### Step 3: Validate Layer-to-Power BI Mapping
- Bronze → External Data Sources (M queries)
- Silver → Data Gateway/Lakehouse tables
- Gold → Staging semantic model
- Mart → Public semantic model (reports)

### Step 4: Generate Power BI Reports
```bash
# Generated .pbip project includes:
# - M queries for bronze/silver transformations
# - DAX measures for gold aggregations
# - Model relationships for mart schema
```

---

## Testing & Validation

### Run Extraction Test

```bash
cd c:\GitHub Project\QlikToPowerBI
venv\Scripts\python.exe test_complex_lineage.py
```

**Expected Output**:
```
COMPLEX LINEAGE ANALYSIS
Total Nodes: 19
Total Edges: 17

BY LAYER:
  BRONZE       -  1 operations
  SILVER       -  4 operations
  GOLD         -  4 operations
  MART         - 10 operations

BY PURPOSE:
  ingestion            -  5 operations
  transformation       -  4 operations
  aggregation          -  4 operations
  export               -  5 operations
  security             -  1 operations
```

---

## Summary

✅ **Fully Implemented Features**:
- Multi-layer lineage extraction (Bronze/Silver/Gold/Mart)
- Purpose classification (ingestion/transformation/aggregation/fact/dimension/export/security)
- Complexity assessment (simple/moderate/complex)
- Source count tracking (single/multi-source)
- Interactive HTML visualization
- CLI integration with migration pipeline
- Complete example (complex_dwh_demo.json) with 4 layers, 6 parallel flows

📊 **Example Statistics**:
- Example nodes: 19 total transformations
- Example edges: 17 data flows
- Layer distribution: 1 Bronze, 4 Silver, 4 Gold, 10 Mart
- Purpose breakdown: 5 ingestions, 4 transformations, 4 aggregations, 5 exports, 1 security

🎯 **Use Cases**:
- Understand data flow before migration
- Validate layer categorization
- Identify complex transformations requiring manual review
- Document data warehouse architecture
- Plan Power BI dataset design
- Validate end-to-end lineage in comparison reports

