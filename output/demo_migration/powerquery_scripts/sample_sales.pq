// Erreur de conversion: LOAD statement mal formé
// Script Qlik original:
// 
// Script de chargement des ventes

SET ThousandSep=' ';
SET DecimalSep=',';
SET MoneyFormat='# ##0,00 €';
SET DateFormat='DD/MM/YYYY';

// Chargement des ventes
Sales:

// Query: Table2
let
    Source = Csv.Document(File.Contents("Sales.csv"),[Delimiter=",", Columns=auto, Encoding=65001, QuoteStyle=QuoteStyle.None]),
    PromotedHeaders = Table.PromoteHeaders(Source, [PromoteAllScalars=true])
,\n    SelectedColumns = Table.SelectColumns(PromotedHeaders, {"SaleID", "CustomerID", "ProductID", "OrderDate", "Amount", "Quantity"})

in
    SelectedColumns

// Query: Table3
let
    Source = Excel.Workbook(File.Contents("Customers.xlsx"), null, true),
    Sheet1 = Source{{[Item="Sheet1",Kind="Sheet"]}}[Data],
    PromotedHeaders = Table.PromoteHeaders(Sheet1, [PromoteAllScalars=true])
,\n    SelectedColumns = Table.SelectColumns(PromotedHeaders, {"CustomerID", "CustomerName", "Country", "City", "Region"})

in
    SelectedColumns

// Query: Table4
let
    Source = Qvd.Document(File.Contents("Products.qvd"))
,\n    SelectedColumns = Table.SelectColumns(Source, {"ProductID", "ProductName", "CategoryID", "UnitPrice"})

in
    SelectedColumns

// Erreur de conversion: cannot access local variable 'base_table' where it is not associated with a value
// Script Qlik original:
// LOAD
    CategoryID,
    CategoryName,
    Description
INLINE [
    CategoryID, CategoryName, Description
    1, Electronics, Electronic devices
    2, Clothing, Apparel and accessories
    3, Food, Food products
];

