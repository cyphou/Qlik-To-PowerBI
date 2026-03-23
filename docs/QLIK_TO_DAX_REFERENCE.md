# Qlik to DAX Reference — 175+ Function Mappings

Complete reference for Qlik expression → DAX conversion.

---

## String Functions (25)

| Qlik | DAX | Notes |
|------|-----|-------|
| Upper(s) | UPPER(s) | |
| Lower(s) | LOWER(s) | |
| Capitalize(s) | -- | Manual: UPPER(LEFT(s,1)) & LOWER(MID(s,2,LEN(s))) |
| Len(s) | LEN(s) | |
| Left(s,n) | LEFT(s,n) | |
| Right(s,n) | RIGHT(s,n) | |
| Mid(s,start,len) | MID(s,start,len) | |
| Trim(s) | TRIM(s) | |
| LTrim(s) | TRIM(s) | DAX has no LTrim |
| RTrim(s) | TRIM(s) | DAX has no RTrim |
| Replace(s,from,to) | SUBSTITUTE(s,from,to) | |
| SubField(s,delim,n) | -- | Manual: nested PATHITEM |
| PurgeChar(s,chars) | SUBSTITUTE(s,chars,"") | Iterative |
| KeepChar(s,chars) | -- | Manual: CODE/MID loop |
| Repeat(s,n) | REPT(s,n) | |
| TextBetween(s,a,b) | -- | MID + SEARCH pattern |
| Index(s,sub) | SEARCH(sub,s) | 1-based |
| SubStringCount | -- | LEN-based pattern |
| Ord(s) | CODE(s) | |
| Chr(n) | UNICHAR(n) | |
| Hash128/256 | -- | No DAX equivalent |
| Concat(vals,sep) | CONCATENATEX(table,col,sep) | |
| Text(n,fmt) | FORMAT(n,fmt) | |
| Num(s) | VALUE(s) | |
| Dual(text,num) | VALUE(text) | Drops text part |

## Math Functions (20)

| Qlik | DAX | Notes |
|------|-----|-------|
| Abs(x) | ABS(x) | |
| Ceil(x) | CEILING(x,1) | |
| Floor(x) | FLOOR(x,1) | |
| Round(x,n) | ROUND(x,n) | |
| Sqrt(x) | SQRT(x) | |
| Sqr(x) | POWER(x,2) | |
| Pow(x,y) | POWER(x,y) | |
| Exp(x) | EXP(x) | |
| Log(x) | LOG(x) | |
| Log10(x) | LOG10(x) | |
| Mod(x,y) | MOD(x,y) | |
| Div(x,y) | INT(DIVIDE(x,y,0)) | |
| Frac(x) | x - INT(x) | |
| Sign(x) | SIGN(x) | |
| Pi() | PI() | |
| Even(x) | EVEN(x) | |
| Odd(x) | ODD(x) | |
| Fact(n) | FACT(n) | |
| Combin(n,k) | COMBIN(n,k) | |
| Permut(n,k) | PERMUT(n,k) | |

## Date Functions (22)

| Qlik | DAX | Notes |
|------|-----|-------|
| Year(d) | YEAR(d) | |
| Month(d) | MONTH(d) | |
| Day(d) | DAY(d) | |
| Hour(d) | HOUR(d) | |
| Minute(d) | MINUTE(d) | |
| Second(d) | SECOND(d) | |
| WeekDay(d) | WEEKDAY(d) | |
| WeekYear(d) | WEEKNUM(d) | |
| Today() | TODAY() | |
| Now() | NOW() | |
| MakeDate(y,m,d) | DATE(y,m,d) | |
| MakeTime(h,m,s) | TIME(h,m,s) | |
| MonthStart(d) | STARTOFMONTH(d) | |
| MonthEnd(d) | ENDOFMONTH(d) | |
| YearStart(d) | STARTOFYEAR(d) | |
| YearEnd(d) | ENDOFYEAR(d) | |
| QuarterStart(d) | STARTOFQUARTER(d) | |
| QuarterEnd(d) | ENDOFQUARTER(d) | |
| AddMonths(d,n) | EDATE(d,n) | |
| AddYears(d,n) | EDATE(d,n*12) | |
| DateDiff(d1,d2,unit) | DATEDIFF(d1,d2,unit) | Needs unit mapping |
| InYearToDate(d,ref) | -- | CALCULATE + DATESYTD pattern |

## Aggregation Functions (15)

| Qlik | DAX | Notes |
|------|-----|-------|
| Sum(x) | SUM(x) | |
| Avg(x) | AVERAGE(x) | |
| Min(x) | MIN(x) | |
| Max(x) | MAX(x) | |
| Count(x) | COUNT(x) | |
| CountDistinct(x) | DISTINCTCOUNT(x) | |
| Median(x) | MEDIAN(x) | |
| Stdev(x) | STDEV.S(x) | |
| Fractile(x,p) | PERCENTILE.INC(x,p) | |
| Mode(x) | -- | TOPN + COUNTROWS pattern |
| Only(x) | -- | IF(COUNTROWS=1, ...) |
| FirstSortedValue | -- | TOPN + CALCULATE |
| RangeSum | SUMX | |
| RangeAvg | AVERAGEX | |
| RangeCount | COUNTROWS | |

## Set Analysis (10)

| Qlik Pattern | DAX Pattern |
|--------------|------------|
| `{<Field={Value}>}` | `CALCULATE(..., 'T'[Field] = Value)` |
| `{<F1={V1},F2={V2}>}` | `CALCULATE(..., 'T'[F1]=V1, 'T'[F2]=V2)` |
| `{<Year=Year(Today())>}` | `CALCULATE(..., 'T'[Year]=YEAR(TODAY()))` |
| `{1<Field={Value}>}` | `CALCULATE(..., ALL('T'), 'T'[Field]=Value)` |
| `{$<Field>}` | `CALCULATE(..., ALLEXCEPT('T', 'T'[Field]))` |
| `{<Field={"A","B"}>}` | `CALCULATE(..., 'T'[Field] IN {"A","B"})` |
| `{<Field={">100"}>}` | `CALCULATE(..., 'T'[Field] > 100)` |
| `{<-Field>}` | `CALCULATE(..., REMOVEFILTERS('T'[Field]))` |
| Nested set analysis | Nested CALCULATE |
| Alternative states | CALCULATE + ALLSELECTED |

## Conditional Functions (12)

| Qlik | DAX |
|------|-----|
| If(cond, then, else) | IF(cond, then, else) |
| Match(val, v1, v2...) | SWITCH(val, v1, r1, v2, r2, ...) |
| MixMatch | SWITCH(TRUE(), ...) |
| WildMatch | SWITCH(TRUE(), CONTAINSSTRING()...) |
| Pick(n, v1, v2...) | SWITCH(n, 1, v1, 2, v2, ...) |
| Alt(v1, v2, v3) | COALESCE(v1, v2, v3) |
| Class(x, size) | INT(x / size) * size |
| If(IsNull(x)) | IF(ISBLANK(x), ...) |

## Inter-Record Functions (8)

| Qlik | DAX | Notes |
|------|-----|-------|
| Above(expr) | EARLIER(col) | Context-dependent |
| Below(expr) | -- | No direct equivalent |
| Top(expr) | FIRSTNONBLANK | |
| Bottom(expr) | LASTNONBLANK | |
| RangeSum(Above(x,0,N)) | Window function | OFFSET-based |
| Rank(expr) | RANKX(ALL('T'), col) | |
| FieldValue(field,n) | INDEX + OFFSET | |
| Concat(field,sep) | CONCATENATEX('T', col, sep) | |

## Null Handling (6)

| Qlik | DAX |
|------|-----|
| IsNull(x) | ISBLANK(x) |
| Null() | BLANK() |
| NullCount(x) | COUNTBLANK(x) |
| Alt(x, default) | COALESCE(x, default) |
| If(IsNull(x),y,x) | IF(ISBLANK(x),y,x) |
| Coalesce(x,y,z) | COALESCE(x,y,z) |

## Logical Functions (8)

| Qlik | DAX |
|------|-----|
| AND / and | && |
| OR / or | \|\| |
| NOT / not | NOT() |
| = | = |
| <> | <> |
| True() | TRUE() |
| False() | FALSE() |
| Exists(field,val) | CONTAINS('T', col, val) |

## Security Functions (3)

| Qlik | DAX |
|------|-----|
| OSUser() | USERPRINCIPALNAME() |
| GetRegistryString | -- (no equivalent) |
| ComputerName | -- (no equivalent) |

## Advanced Functions (38)

| Qlik | DAX | Notes |
|------|-----|-------|
| Aggr(expr, dims) | SUMMARIZE('T', cols, "M", expr) | |
| ValueList | DATATABLE | |
| ValueLoop | GENERATESERIES | |
| RowNo() | ROWNUMBER() | Window function in newer DAX |
| RecNo() | ROWNUMBER() | |
| FieldValueCount | DISTINCTCOUNT | |
| GetFieldSelections | SELECTEDVALUE | |
| Peek/Previous | EARLIER / OFFSET | |
| NoOfRows | COUNTROWS | |
| NoOfFields | -- | No equivalent |
| GetSelectedCount | COUNTROWS(VALUES()) | |
| MaxString/MinString | MAXX/MINX | |
| Autonumber | ROWNUMBER() | |
| Hash128/256 | -- | No native hash in DAX |

---

## v7 Additions — Iterator & Window Functions

### Aggr() Decomposition (v7.0.0)

| Qlik Pattern | DAX Output | Iterator Used |
|-------------|-----------|---------------|
| `Aggr(Sum(X), Dim)` | `SUMX(VALUES('T'[Dim]), X)` | SUMX |
| `Aggr(Count(X), Dim)` | `COUNTX(VALUES('T'[Dim]), 1)` | COUNTX |
| `Aggr(Avg(X), Dim)` | `AVERAGEX(VALUES('T'[Dim]), X)` | AVERAGEX |
| `Aggr(Min(X), Dim)` | `MINX(VALUES('T'[Dim]), X)` | MINX |
| `Aggr(Max(X), Dim)` | `MAXX(VALUES('T'[Dim]), X)` | MAXX |
| `Aggr(Aggr(...))` | nested SUMMARIZE/iterators | Recursive |

### Inter-record OFFSET (v7.0.0)

| Qlik Pattern | DAX Output |
|-------------|-----------|
| `Previous(field)` | `OFFSET(-1, ALLSELECTED('T'))` |
| `Above(field, n)` | `OFFSET(-n, ALLSELECTED('T'))` |
| `Below(field, n)` | `OFFSET(n, ALLSELECTED('T'))` |
| `Peek(field, offset)` | `OFFSET(offset, ALLSELECTED('T'))` |
| `RangeSum(Above(X, 0, RowNo()))` | `CALCULATE(SUM(...), WINDOW(-INF, 0, ALLSELECTED(...)))` |

### Set Analysis P()/E() (v7.0.0)

| Qlik Pattern | DAX Output | Description |
|-------------|-----------|-------------|
| `P({1} Field)` | `ALL('T'[Field])` | Possible values (full domain) |
| `E({1} Field)` | `EXCEPT(ALL('T'[Field]), VALUES('T'[Field]))` | Excluded values |

### Dollar-Sign Expression Expansion (v7.0.0)

| Qlik Pattern | DAX Output | Description |
|-------------|-----------|-------------|
| `$(=Year(Today())-1)` | `YEAR(TODAY()) - 1` | Dynamic expression resolved to DAX |
| `$(vMyVar)` | resolved value | Variable substitution with Qlik→DAX conversion |

### Section Access → RLS (v7.0.0)

| Qlik Pattern | TMDL Output | Description |
|-------------|-------------|-------------|
| `USERID = *` | `TRUE()` filter | Wildcard → all users |
| `OMIT` column | OLS annotation comment | Object-Level Security note |
| `REDUCTION` column | `reduce_values` list | Row reduction per role |
