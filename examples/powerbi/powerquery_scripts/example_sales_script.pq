// Erreur de conversion: LOAD statement mal formé
// Script Qlik original:
// // Script Qlik Exemple - Chargement des Ventes

// ============================================
// Chargement des données clients
// ============================================

// Query: Table2
let
    Source = Csv.Document(File.Contents("C:\Data\Customers.csv"),[Delimiter=",", Columns=auto, Encoding=65001, QuoteStyle=QuoteStyle.None]),
    PromotedHeaders = Table.PromoteHeaders(Source, [PromoteAllScalars=true])
,
    AddedColumns = Table.AddColumn(PromotedHeaders, "Calculated", each [
        CustomerID
        CustomerName = Text.Upper(CustomerName)
        Country
        Region
        Date(RegistrationDate
        RegistrationDate = 'YYYY-MM-DD')
        If(Status = 'Active'
        1
        IsActive = 0)
    ])

in
    AddedColumns

// Query: Table3
let
    Source = Excel.Workbook(File.Contents("C:\Data\Products.xlsx"), null, true),
    Sheet1 = Source{{[Item="Sheet1",Kind="Sheet"]}}[Data],
    PromotedHeaders = Table.PromoteHeaders(Sheet1, [PromoteAllScalars=true])
,
    AddedColumns = Table.AddColumn(PromotedHeaders, "Calculated", each [
        ProductID
        ProductName
        Category
        SubCategory
        Round(UnitPrice
        UnitPrice = 2)
        LaunchYear = Date.Year(LaunchDate)
        LaunchMonth = Date.Month(LaunchDate)
    ])

in
    AddedColumns

// Query: Table4
let
    Source = Csv.Document(File.Contents("C:\Data\Sales.csv"),[Delimiter=",", Columns=auto, Encoding=65001, QuoteStyle=QuoteStyle.None]),
    PromotedHeaders = Table.PromoteHeaders(Source, [PromoteAllScalars=true])
,
    AddedColumns = Table.AddColumn(PromotedHeaders, "Calculated", each [
        OrderID
        OrderDate
        CustomerID
        ProductID
        Quantity
        UnitPrice
        TotalAmount = Quantity * UnitPrice
        If(Discount > 0
        Quantity * UnitPrice * (1 - Discount)
        NetAmount = Quantity * UnitPrice)
        OrderYear = Date.Year(OrderDate)
        OrderMonth = Date.Month(OrderDate)
        OrderMonthName = Date.MonthName(OrderDate)
        OrderWeekDay = Date.DayOfWeek(OrderDate)
    ])
,
    Filtered = Table.SelectRows(AddedColumns, each (OrderDate >= Date.From('2023-01-01') AND Status <> 'Cancelled'))

in
    Filtered

// Query: Table5
let
    Source = TempCalendar
,
    AddedColumns = Table.AddColumn(Source, "Calculated", each [
        CalendarDate = Date.From(Date)
        Year = Date.Year(Date)
        Month = Date.Month(Date)
        Day = Date.Day(Date)
        MonthName = Date.MonthName(Date)
        WeekDay = Date.DayOfWeek(Date)
        If(WeekDay(Date) >= 5
        'Weekend'
        DayType = 'Weekday')
        YearStart = Date.StartOfYear(Date)
        YearEnd = Date.EndOfYear(Date)
        MonthStart = Date.StartOfMonth(Date)
        MonthEnd = Date.EndOfMonth(Date)
    ])

in
    AddedColumns

// Query: Table6
let
    Source = Sales
,
    AddedColumns = Table.AddColumn(Source, "Calculated", each [
        CustomerID
        TotalSales = List.Sum(TotalAmount)
        AvgOrderValue = List.Average(TotalAmount)
        OrderCount = List.Count(OrderID)
        FirstOrderDate = List.Min(OrderDate)
        LastOrderDate = List.Max(OrderDate)
    ])

in
    AddedColumns
