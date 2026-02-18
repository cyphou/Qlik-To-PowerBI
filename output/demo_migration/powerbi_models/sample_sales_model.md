# Modèle de Données Migré - Qlik → Power BI
**Tables**: 4**Relations**: 3**Hiérarchies**: 1

## Relations
- **Sales**`.CustomerID` → **Customers**`.CustomerID` (Single)
- **Sales**`.ProductID` → **Products**`.ProductID` (Single)
- **Products**`.CategoryID` → **Categories**`.CategoryID` (Single)
