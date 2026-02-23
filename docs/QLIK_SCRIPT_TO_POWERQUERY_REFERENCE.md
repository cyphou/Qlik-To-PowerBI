# Qlik Script to Power Query Reference

Guide for converting Qlik load scripts to Power Query M using
`qlik_script_converter.py` and the new `m_query_generator.py` / `m_query_builder.py`.

---

## Qlik Script Statements → Power Query M

### Data Loading

| Qlik Statement | Power Query M Equivalent |
|---------------|------------------------|
| `LOAD * FROM 'file.csv' (txt, ...)` | `Csv.Document(File.Contents("file.csv"))` |
| `LOAD * FROM 'file.xlsx' (ooxml, ...)` | `Excel.Workbook(File.Contents("file.xlsx"))` |
| `SQL SELECT ... FROM table` | `Sql.Database("server", "db")` |
| `LOAD * FROM 'file.qvd' (qvd)` | `Csv.Document(...)` (converted) |
| `LOAD * INLINE [...]` | `#table(columns, rows)` |
| `LOAD * RESIDENT Table` | Referenced step name |

### Joins

| Qlik | Power Query M |
|------|--------------|
| `LEFT JOIN` | `Table.NestedJoin(..., JoinKind.LeftOuter)` |
| `INNER JOIN` | `Table.NestedJoin(..., JoinKind.Inner)` |
| `RIGHT JOIN` | `Table.NestedJoin(..., JoinKind.RightOuter)` |
| `OUTER JOIN` | `Table.NestedJoin(..., JoinKind.FullOuter)` |
| `CONCATENATE` | `Table.Combine({Table1, Table2})` |

### Transformations

| Qlik Statement | Power Query M |
|---------------|--------------|
| `WHERE condition` | `Table.SelectRows(prev, each [col] ...)` |
| `GROUP BY ... ; LOAD Sum(x)` | `Table.Group(prev, {"col"}, {{"Sum", each List.Sum([x])}})` |
| `ORDER BY col asc` | `Table.Sort(prev, {{"col", Order.Ascending}})` |
| `DISTINCT` | `Table.Distinct(prev)` |
| `NOCONCATENATE` | Separate query (no auto-append) |
| `DROP TABLE` | N/A (Power Query manages scope) |
| `RENAME FIELD old TO new` | `Table.RenameColumns(prev, {{"old", "new"}})` |

### Variable/Parameter

| Qlik | Power Query M / DAX |
|------|---------------------|
| `LET vVar = expression;` | Parameter query or DAX variable |
| `SET vVar = expression;` | M parameter: `"value" meta [IsParameterQuery=true]` |

---

## Function Mapping (30 in qlik_script_converter)

| Qlik Function | Power Query M | Notes |
|---------------|--------------|-------|
| Upper(s) | Text.Upper(s) | |
| Lower(s) | Text.Lower(s) | |
| Len(s) | Text.Length(s) | |
| Left(s,n) | Text.Start(s,n) | |
| Right(s,n) | Text.End(s,n) | |
| Mid(s,p,n) | Text.Middle(s,p-1,n) | 0-indexed in M |
| Trim(s) | Text.Trim(s) | |
| Replace(s,a,b) | Text.Replace(s,a,b) | |
| SubField(s,d,n) | Text.Split(s,d){n-1} | |
| Num(s) | Number.FromText(s) | |
| Text(n,f) | Text.From(n) | Format lost |
| Date(n) | Date.From(n) | |
| Time(n) | Time.From(n) | |
| Timestamp(n) | DateTime.From(n) | |
| Year(d) | Date.Year(d) | |
| Month(d) | Date.Month(d) | |
| Day(d) | Date.Day(d) | |
| Hour(t) | Time.Hour(t) | |
| Minute(t) | Time.Minute(t) | |
| Second(t) | Time.Second(t) | |
| Today() | DateTime.LocalNow() | Date part |
| Now() | DateTime.LocalNow() | |
| MakeDate(y,m,d) | #date(y,m,d) | |
| If(c,t,e) | if c then t else e | |
| IsNull(x) | x = null | |
| Null() | null | |
| Ceil(x) | Number.RoundUp(x) | |
| Floor(x) | Number.RoundDown(x) | |
| Round(x,n) | Number.Round(x,n) | |
| Abs(x) | Number.Abs(x) | |

---

## Source Type Mapping (8 in qlik_script_converter)

| Qlik Source Type | Power Query Pattern |
|-----------------|-------------------|
| txt (CSV) | `Csv.Document(File.Contents(...))` |
| ooxml (Excel) | `Excel.Workbook(File.Contents(...))` |
| qvd | `Csv.Document(...)` with conversion note |
| ODBC/OLEDB | `Odbc.DataSource(...)` / `OleDb.DataSource(...)` |
| SQL SELECT | `Sql.Database/PostgreSQL.Database(...)` |
| web | `Web.BrowserContents(...)` |
| json | `Json.Document(File.Contents(...))` |
| xml | `Xml.Tables(File.Contents(...))` |

---

## Common Script Patterns

### Mapping Table
```qlik
// Qlik
Mapping:
MAPPING LOAD Key, Value
FROM 'mapping.csv' (txt, ...);

ApplyMap('Mapping', Field, 'Default')
```
```m
// Power Query M
let
    Mapping = Csv.Document(File.Contents("mapping.csv")),
    MappingTable = Table.PromoteHeaders(Mapping),
    // Use Table.NestedJoin to lookup values
    Joined = Table.NestedJoin(MainTable, "Key", MappingTable, "Key", "Lookup", JoinKind.LeftOuter),
    Expanded = Table.ExpandTableColumn(Joined, "Lookup", {"Value"})
in
    Expanded
```

### Preceding Load (Stacked)
```qlik
// Qlik
Table:
LOAD *,
     Year(Date) as Year,
     Month(Date) as MonthNum;
LOAD * FROM 'data.csv' (txt, ...);
```
```m
// Power Query M
let
    Source = Csv.Document(File.Contents("data.csv")),
    Headers = Table.PromoteHeaders(Source),
    AddYear = Table.AddColumn(Headers, "Year", each Date.Year([Date]), Int64.Type),
    AddMonth = Table.AddColumn(AddYear, "MonthNum", each Date.Month([Date]), Int64.Type)
in
    AddMonth
```

### Incremental Load
```qlik
// Qlik
LET vLastLoad = Peek('MaxDate', 0, 'Control');
SQL SELECT * FROM orders WHERE date > '$(vLastLoad)';
```
```m
// Power Query M — use incremental refresh parameters
let
    RangeStart = #datetime(2024, 1, 1, 0, 0, 0),  // Parameter
    RangeEnd = #datetime(2024, 12, 31, 23, 59, 59),  // Parameter
    Source = Sql.Database("server", "db"),
    Orders = Source{[Schema="dbo",Item="orders"]}[Data],
    Filtered = Table.SelectRows(Orders, each [date] >= RangeStart and [date] < RangeEnd)
in
    Filtered
```

---

## Tips

1. **Preceding loads** → chain `Table.AddColumn` steps
2. **Mapping tables** → `Table.NestedJoin` with left outer join
3. **Resident loads** → reference an earlier query step
4. **QVD files** → convert to CSV/Parquet first, or use custom connector
5. **Inline loads** → `#table({"Col1","Col2"}, {{"val1","val2"}})`
6. **Wildcards** → `Folder.Files(path)` + filter + combine
7. **Section Access** → migrate to TMDL roles (see `roles.tmdl`)
