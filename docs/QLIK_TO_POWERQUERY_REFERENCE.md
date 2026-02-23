# Qlik to Power Query M Reference — 25 Connectors + 40 Transforms

---

## Connector Reference (25 types)

### File-Based Sources

#### Excel
```python
generate_m_query({
    "connectionType": "excel",
    "connection": {"path": "C:\\Data\\sales.xlsx"},
    "tableName": "Sheet1",
})
```
```m
let
    Source = Excel.Workbook(File.Contents("C:\Data\sales.xlsx"), null, true),
    Sheet = Source{[Item="Sheet1",Kind="Sheet"]}[Data],
    PromotedHeaders = Table.PromoteHeaders(Sheet, [PromoteAllScalars=true])
in
    PromotedHeaders
```

#### CSV
```python
generate_m_query({
    "connectionType": "csv",
    "connection": {"path": "C:\\Data\\data.csv", "delimiter": ","},
})
```

#### JSON / XML / PDF
Similar pattern — dispatches to `Json.Document`, `Xml.Tables`, `Pdf.Tables`.

### Database Sources

#### SQL Server
```python
generate_m_query({
    "connectionType": "sqlserver",
    "connection": {"server": "myserver", "database": "mydb"},
    "tableName": "dbo.Sales",
})
```

#### PostgreSQL / MySQL / Oracle
Same pattern with `PostgreSQL.Database`, `MySQL.Database`, `Oracle.Database`.

#### Cloud Data Warehouses
| Type | M Function | Extra Parameters |
|------|-----------|-----------------|
| BigQuery | `GoogleBigQuery.Database` | project, dataset |
| Snowflake | `Snowflake.Databases` | server, warehouse, database, schema |
| Redshift | `AmazonRedshift.Database` | server, database |
| Databricks | `Databricks.Catalogs` | server, httpPath, catalog |

#### Azure Sources
| Type | M Function |
|------|-----------|
| Azure SQL | `AzureSQL.Database` |
| Azure Synapse | `AzureSynapse.Database` |

### Other Sources
| Type | M Function | Notes |
|------|-----------|-------|
| SharePoint | `SharePoint.Files` | Site URL + file path |
| Google Sheets | `Web.BrowserContents` | Requires web connector auth |
| Salesforce | `Salesforce.Data` | Object name |
| Web | `Web.BrowserContents` | URL + HTML table parsing |
| ODBC | `Odbc.DataSource` | DSN or connection string |
| OLE DB | `OleDb.DataSource` | Provider connection string |

### QVD Files
QVD has no native Power BI connector. The migration generates a CSV fallback:
```m
let
    // QVD source: C:\Data\file.qvd
    // QVD files require the Qlik QVD connector or conversion to CSV/Parquet
    Source = Csv.Document(File.Contents("C:\Data\file.csv"), [Delimiter=",", Encoding=65001]),
    PromotedHeaders = Table.PromoteHeaders(Source, [PromoteAllScalars=true])
in
    PromotedHeaders
```

---

## Transform Reference (40+ types)

### Column Operations

| Transform | Function | Parameters |
|-----------|----------|-----------|
| rename | `rename_columns(prev, mapping)` | `{"old": "new"}` |
| remove | `remove_columns(prev, columns)` | `["col1", "col2"]` |
| select | `select_columns(prev, columns)` | `["col1", "col2"]` |
| duplicate | `duplicate_column(prev, source, new_name)` | |
| reorder | `reorder_columns(prev, columns)` | ordered list |
| split | `split_column_by_delimiter(prev, column, ",")` | |
| merge | `merge_columns(prev, columns, new_name, " ")` | |

### Value Operations

| Transform | Function |
|-----------|----------|
| replace | `replace_values(prev, column, old, new)` |
| replace_nulls | `replace_nulls(prev, column, replacement)` |
| trim | `trim_text(prev, columns)` |
| clean | `clean_text(prev, columns)` |
| upper | `upper_case(prev, columns)` |
| lower | `lower_case(prev, columns)` |
| proper | `proper_case(prev, columns)` |
| fill_down | `fill_down(prev, columns)` |
| fill_up | `fill_up(prev, columns)` |

### Filter Operations

| Transform | Function |
|-----------|----------|
| filter_values | `filter_values(prev, column, values)` |
| exclude | `exclude_values(prev, column, values)` |
| filter_range | `filter_range(prev, column, min, max)` |
| filter_nulls | `filter_nulls(prev, column, keep_nulls)` |
| filter_contains | `filter_contains(prev, column, text)` |
| distinct | `distinct_rows(prev, columns)` |
| top_n | `top_n(prev, column, n, ascending)` |

### Aggregate

```python
group_by(prev, ["Category"], [
    {"column": "Amount", "agg": "sum", "alias": "Total"},
    {"column": "Amount", "agg": "avg", "alias": "Average"},
])
```
Supported: `sum`, `avg`, `count`, `countd`, `min`, `max`, `median`, `stdev`

### Pivot / Unpivot

| Transform | Function |
|-----------|----------|
| unpivot | `unpivot(prev, columns, "Attribute", "Value")` |
| unpivot_other | `unpivot_other(prev, keep_columns)` |
| pivot | `pivot(prev, attribute_col, value_col, "sum")` |

### Join (6 kinds)

```python
join_tables(prev, "OtherTable", "ID", "ID",
            join_kind="left", expand_columns=["Name", "Age"])
```
Kinds: `inner`, `left`, `right`, `full`, `leftanti`, `rightanti`

### Union / Append

```python
append_tables(["Table1", "Table2", "Table3"])
wildcard_union("C:\\Data\\Folder", "*.csv")
```

### Reshape

| Transform | Function |
|-----------|----------|
| sort | `sort_rows(prev, [{"column": "Date", "ascending": False}])` |
| transpose | `transpose(prev)` |
| add_index | `add_index(prev, "RowNum", 1)` |
| skip_rows | `skip_rows(prev, 5)` |
| remove_top/bottom | `remove_top_rows(prev, 1)` |
| promote_headers | `promote_headers(prev)` |
| demote_headers | `demote_headers(prev)` |

### Calculated Columns

```python
add_custom_column(prev, "FullName",
                  '[FirstName] & " " & [LastName]', "type text")

add_conditional_column(prev, "Status", [
    {"column": "Amount", "operator": ">", "value": "1000", "result": "High"},
    {"column": "Amount", "operator": ">", "value": "500", "result": "Medium"},
], else_value="Low")
```

---

## Step Injection

Insert transforms into existing M queries:

```python
from fabric_api.m_query_builder import inject_m_steps, rename_columns, filter_values

base_query = '''let
    Source = Sql.Database("server", "db"),
    Table = Source{[Schema="dbo",Item="Sales"]}[Data]
in
    Table'''

steps = []
name, code = rename_columns("Table", {"OldCol": "NewCol"})
steps.append((name, code))
name, code = filter_values("RenamedColumns", "Status", ["Active"])
steps.append((name, code))

result = inject_m_steps(base_query, steps)
```

Or use the declarative API:

```python
from fabric_api.m_query_builder import build_m_query_with_transforms

result = build_m_query_with_transforms(base_query, [
    {"type": "rename", "mapping": {"OldCol": "NewCol"}},
    {"type": "filter_values", "column": "Status", "values": ["Active"]},
    {"type": "upper", "columns": ["Name"]},
])
```
