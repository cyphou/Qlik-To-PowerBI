# Modèle de Données Migré - Qlik → Power BI
**Tables**: 7**Relations**: 5**Hiérarchies**: 4

## Relations
- **Customers**`.CustomerID` → **Sales**`.CustomerID` (Single)
- **Products**`.ProductID` → **Sales**`.ProductID` (Single)
- **Employees**`.EmployeeID` → **Sales**`.EmployeeID` (Single)
- **Regions**`.RegionID` → **Customers**`.RegionID` (Single)
- **Categories**`.CategoryID` → **Products**`.CategoryID` (Single)
