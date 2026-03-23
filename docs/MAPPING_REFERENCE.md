# Mapping Reference — Qlik → Power BI

Complete mapping tables for all conversion categories.

---

## Visual Type Mapping (60+)

| Qlik Type | Power BI Visual | Notes |
|-----------|----------------|-------|
| barchart | clusteredBarChart | |
| linechart | lineChart | |
| piechart | pieChart | |
| combo | lineStackedColumnComboChart | |
| scatter | scatterChart | |
| treemap | treemap | |
| kpi | card | or kpi visual |
| gauge | gauge | |
| table | tableEx | |
| pivot-table | pivotTable | |
| map | map | |
| waterfall | waterfallChart | |
| boxplot | boxAndWhisker | |
| histogram | clusteredColumnChart | binned |
| distributionplot | scatterChart | |
| filterpane | slicer | |
| text-image | textbox | |
| container | actionButton | group |
| mekko | stackedBarChart | |
| bullet | bulletChart | custom visual |
| wordcloud | wordCloud | custom visual |
| sankey | sankeyDiagram | custom visual |
| funnelchart | funnel | |
| donutchart | donutChart | |
| areachart | areaChart | |
| stackedbarchart | stackedBarChart | |
| 100%barchart | hundredPercentStackedBarChart | |
| stackedcolumnchart | stackedColumnChart | |
| 100%columnchart | hundredPercentStackedColumnChart | |
| lineareachart | lineStackedColumnComboChart | |
| ribbonchart | ribbonChart | |
| matrixplot | matrix | |
| organizationchart | decompositionTree | |
| nlp | qAndA | |
| variwidthtable | tableEx | |
| buttongroup | slicer | button style |

---

## Data Type Mapping

| Qlik Type | TMDL dataType | Power Query M Type |
|-----------|---------------|-------------------|
| integer / int | int64 | Int64.Type |
| num / number / decimal | double | type number |
| money / currency | decimal | Currency.Type |
| text / string | string | type text |
| date | dateTime | type date |
| timestamp / datetime | dateTime | type datetime |
| time | dateTime | type time |
| boolean | boolean | type logical |
| dual | string | type text |

---

## Connector Type Mapping (25)

| Qlik Source | Power Query M Function | Key Parameters |
|-------------|----------------------|----------------|
| Excel / XLSX / XLS | Excel.Workbook | path, sheet |
| CSV / TXT | Csv.Document | path, delimiter |
| SQL Server / MSSQL | Sql.Database | server, database |
| PostgreSQL | PostgreSQL.Database | server, database |
| Oracle | Oracle.Database | server |
| MySQL | MySQL.Database | server, database |
| BigQuery | GoogleBigQuery.Database | project, dataset |
| Snowflake | Snowflake.Databases | server, warehouse |
| Teradata | Teradata.Database | server |
| SAP HANA | SapHana.Database | server |
| Redshift | AmazonRedshift.Database | server, database |
| Databricks | Databricks.Catalogs | server, httpPath |
| Spark | SparkHive.Database | server |
| Azure SQL | AzureSQL.Database | server, database |
| Azure Synapse | AzureSynapse.Database | server, database |
| Google Sheets | Web.BrowserContents | url |
| SharePoint | SharePoint.Files | siteUrl |
| JSON | Json.Document | path |
| XML | Xml.Tables | path |
| PDF | Pdf.Tables | path |
| Salesforce | Salesforce.Data | object |
| Web | Web.BrowserContents | url |
| QVD | Csv.Document (converted) | path |
| ODBC | Odbc.DataSource | dsn |
| OLE DB | OleDb.DataSource | connectionString |

---

## Aggregation Mapping

| Qlik Function | DAX Function | TMDL Function ID |
|---------------|-------------|-------------------|
| Sum | SUM | 1 |
| Min | MIN | 2 |
| Max | MAX | 3 |
| Count | COUNT | 4 |
| CountNonNull | COUNTA | 5 |
| Avg / Average | AVERAGE | 6 |
| CountDistinct | DISTINCTCOUNT | N/A (measure only) |
| Median | MEDIAN | N/A (measure only) |
| Stdev | STDEV.S | N/A (measure only) |

---

## Geographic Data Category Mapping

| Column Name Pattern | PBI dataCategory |
|--------------------|-----------------|
| country, countryregion | Country |
| state, province, region | StateOrProvince |
| city | City |
| postalcode, zipcode, zip | PostalCode |
| address | Address |
| county | County |
| continent | Continent |
| latitude, lat | Latitude |
| longitude, lon, lng | Longitude |

---

## Cross-Filter Behavior Mapping

| Qlik Behavior | TMDL Value |
|---------------|-----------|
| Single | oneDirection |
| Both | bothDirections |
| Automatic | automatic |

---

## Number Format Mapping

| Qlik Format | DAX formatString |
|-------------|-----------------|
| #,##0 | #,##0 |
| #,##0.00 | #,##0.00 |
| 0% | 0% |
| 0.0% | 0.0% |
| $#,##0 | $#,##0 |
| yyyy-MM-dd | yyyy-MM-dd |
| dd/MM/yyyy | dd/MM/yyyy |
| hh:mm:ss | hh:mm:ss |

Most Qlik number formats translate directly to DAX format strings.

---

## v7 DAX Enhancements

### Aggr() → Iterator Decomposition

| Qlik Pattern | DAX Output |
|-------------|-----------|
| `Aggr(Sum(Sales), Region)` | `SUMX(VALUES('T'[Region]), [Sales])` |
| `Aggr(Count(OrderID), Region)` | `COUNTX(VALUES('T'[Region]), 1)` |
| `Aggr(Avg(Price), Category)` | `AVERAGEX(VALUES('T'[Category]), [Price])` |
| `Aggr(Min(Date), Customer)` | `MINX(VALUES('T'[Customer]), [Date])` |
| `Aggr(Max(Amount), Product)` | `MAXX(VALUES('T'[Product]), [Amount])` |

### Inter-record → OFFSET / WINDOW

| Qlik Pattern | DAX Output |
|-------------|-----------|
| `Previous(field)` | `OFFSET(-1, ALLSELECTED('T'))` |
| `Above(field, n)` | `OFFSET(-n, ALLSELECTED('T'))` |
| `Below(field, n)` | `OFFSET(n, ALLSELECTED('T'))` |
| `Peek(field, offset)` | `OFFSET(offset, ALLSELECTED('T'))` |
| `RangeSum(Above(X, 0, RowNo()))` | `CALCULATE(SUM(...), WINDOW(-INF, 0, ALLSELECTED(...)))` |

### Set Analysis P()/E() Functions

| Qlik Pattern | DAX Output |
|-------------|-----------|
| `P({1} Field)` | `ALL('T'[Field])` |
| `E({1} Field)` | `EXCEPT(ALL('T'[Field]), VALUES('T'[Field]))` |

### Section Access → RLS Enhancements

| Qlik Pattern | Power BI / TMDL |
|-------------|-----------------|
| `USERID = *` | RLS role with `TRUE()` filter (all users) |
| `OMIT` column | Documented as OLS migration note |
| `REDUCTION` column | Mapped to reduce_values per role |

### Dollar-Sign Expression Expansion

| Qlik Pattern | DAX Output |
|-------------|-----------|
| `$(=Year(Today())-1)` | `YEAR(TODAY()) - 1` |
| `$(vMyVar)` | Resolved variable value with Qlik→DAX conversion |
