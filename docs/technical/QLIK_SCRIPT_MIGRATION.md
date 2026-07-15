<!-- DOC-SHINY-BANNER -->
![Documentation](https://img.shields.io/badge/Documentation-Shiny_Style-0A66C2?style=flat-square&logo=readthedocs&logoColor=white)
![Maintained](https://img.shields.io/badge/Maintained-2026-2EA44F?style=flat-square&logo=github&logoColor=white)
![Navigation](https://img.shields.io/badge/Navigation-Quick_Access-6F42C1?style=flat-square&logo=bookstack&logoColor=white)
# Migration Scripts Qlik → Power Query M

## 📋 Vue d'ensemble

Ce module convertit automatiquement les **scripts de chargement Qlik** (.qvs) en **scripts Power Query M** (.pq) pour Power BI.

### Ce qui est migré

✅ **Instructions LOAD**  
✅ **Transformations de colonnes**  
✅ **Fonctions Qlik → Fonctions M** (60+ fonctions)  
✅ **Conditions WHERE**  
✅ **Chargement depuis fichiers** (CSV, Excel, TXT)  
✅ **Agrégations** (GROUP BY)  
✅ **Jointures** (LEFT JOIN, INNER JOIN)  
✅ **Tables RESIDENT**  

## 🚀 Démarrage Rapide

### 1. Préparer vos scripts

Placez vos scripts Qlik (.qvs) dans le dossier `qlik_scripts/`

**Un exemple est fourni**: `qlik_scripts/example_sales_script.qvs`

### 2. Exécuter la migration

```bash
python migrate_qlik_scripts.py
```

### 3. Résultat

Les scripts Power Query M (.pq) sont générés dans `powerquery_scripts/`

## 📝 Exemple de Conversion

### Script Qlik (Input)

```qlik
LOAD
    CustomerID,
    Upper(CustomerName) as CustomerName,
    Country,
    Date(RegistrationDate, 'YYYY-MM-DD') as RegistrationDate,
    If(Status = 'Active', 1, 0) as IsActive
FROM [C:\Data\Customers.csv]
(txt, codepage is 1252, embedded labels, delimiter is ',')
WHERE Country <> 'Unknown';
```

### Script Power Query M (Output)

```m
// Query: Customers
let
    Source = Csv.Document(File.Contents("C:\Data\Customers.csv"),[Delimiter=",", Columns=auto, Encoding=65001, QuoteStyle=QuoteStyle.None]),
    PromotedHeaders = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    AddedColumns = Table.AddColumn(PromotedHeaders, "Calculated", each [
        CustomerID,
        CustomerName = Text.Upper([CustomerName]),
        Country,
        RegistrationDate = Date.From([RegistrationDate]),
        IsActive = if [Status] = 'Active' then 1 else 0
    ]),
    Filtered = Table.SelectRows(AddedColumns, each ([Country] <> 'Unknown'))
in
    Filtered
```

## 🔄 Conversions Supportées

### Fonctions de texte

| Qlik | Power Query M |
|------|---------------|
| `Upper(text)` | `Text.Upper(text)` |
| `Lower(text)` | `Text.Lower(text)` |
| `Len(text)` | `Text.Length(text)` |
| `Trim(text)` | `Text.Trim(text)` |
| `Left(text, n)` | `Text.Start(text, n)` |
| `Right(text, n)` | `Text.End(text, n)` |
| `Mid(text, start, len)` | `Text.Middle(text, start, len)` |
| `Replace(text, old, new)` | `Text.Replace(text, old, new)` |
| `SubField(text, delim)` | `Text.Split(text, delim)` |

### Fonctions de date

| Qlik | Power Query M |
|------|---------------|
| `Date(value)` | `Date.From(value)` |
| `Today()` | `Date.From(DateTime.LocalNow())` |
| `Now()` | `DateTime.LocalNow()` |
| `Year(date)` | `Date.Year(date)` |
| `Month(date)` | `Date.Month(date)` |
| `Day(date)` | `Date.Day(date)` |
| `MonthName(date)` | `Date.MonthName(date)` |
| `WeekDay(date)` | `Date.DayOfWeek(date)` |
| `YearStart(date)` | `Date.StartOfYear(date)` |
| `MonthStart(date)` | `Date.StartOfMonth(date)` |

### Fonctions numériques

| Qlik | Power Query M |
|------|---------------|
| `Round(num, dec)` | `Number.Round(num, dec)` |
| `Floor(num)` | `Number.RoundDown(num)` |
| `Ceil(num)` | `Number.RoundUp(num)` |
| `Abs(num)` | `Number.Abs(num)` |
| `Sqrt(num)` | `Number.Sqrt(num)` |
| `Mod(num, div)` | `Number.Mod(num, div)` |

### Fonctions conditionnelles

| Qlik | Power Query M |
|------|---------------|
| `If(cond, true, false)` | `if cond then true else false` |
| `Null()` | `null` |
| `IsNull(field)` | `field = null` |

### Agrégations (pour Group By)

| Qlik | Power Query M |
|------|---------------|
| `Sum(field)` | `List.Sum([field])` |
| `Avg(field)` | `List.Average([field])` |
| `Count(field)` | `List.Count([field])` |
| `Min(field)` | `List.Min([field])` |
| `Max(field)` | `List.Max([field])` |

## 📂 Types de sources supportés

### Fichiers

| Extension | Qlik | Power Query M |
|-----------|------|---------------|
| `.csv` | `FROM [file.csv]` | `Csv.Document(File.Contents("file.csv"))` |
| `.txt` | `FROM [file.txt]` | `Csv.Document(File.Contents("file.txt"))` |
| `.xlsx` | `FROM [file.xlsx]` | `Excel.Workbook(File.Contents("file.xlsx"))` |
| `.xls` | `FROM [file.xls]` | `Excel.Workbook(File.Contents("file.xls"))` |

### Bases de données

| Qlik | Power Query M |
|------|---------------|
| `SQL SELECT ...` | `Sql.Database("Server", "Database")` |
| `ODBC CONNECT ...` | `Odbc.DataSource("DSN")` |

### Tables réidentes

| Qlik | Power Query M |
|------|---------------|
| `RESIDENT TableName` | `TableName` (référence) |

## 💻 Utilisation Programmatique

### Migration simple

```python
from fabric_api.qlik_script_converter import QlikScriptMigrator

migrator = QlikScriptMigrator()

result = migrator.migrate_script_file(
    qlik_script_path='qlik_scripts/sales.qvs',
    output_path='powerquery_scripts/sales.pq'
)

if result['status'] == 'success':
    print(f"✓ Migré: {result['output']}")
```

### Conversion directe

```python
from fabric_api.qlik_script_converter import QlikScriptToPowerQueryConverter

converter = QlikScriptToPowerQueryConverter()

qlik_script = """
LOAD
    CustomerID,
    Upper(CustomerName) as Name
FROM [Customers.csv];
"""

pq_script = converter.convert_qlik_script_to_powerquery(qlik_script)
print(pq_script)
```

### Rapport de conversion

```python
migrator = QlikScriptMigrator()

report = migrator.generate_conversion_report(
    qlik_script=qlik_script,
    pq_script=pq_script
)

print(f"Taux de conversion: {report['conversion_rate']:.1f}%")
print(f"Fonctions non converties: {report['unconverted_functions']}")
```

## 🎯 Intégration dans le workflow

### Workflow complet: App Qlik → Power BI

```python
from fabric_api import QlikToPowerBIMigrator
from fabric_api.qlik_script_converter import QlikScriptMigrator
from pathlib import Path

# 1. Migrer le script de chargement
script_migrator = QlikScriptMigrator()
script_migrator.migrate_script_file(
    'qlik_scripts/sales_load.qvs',
    'powerquery_scripts/sales_load.pq'
)

# 2. Migrer l'application (visualisations)
app_migrator = QlikToPowerBIMigrator()
app_migrator.migrate_qlik_app(
    Path('qlik_exports/sales_app.json'),
    'Sales Dashboard'
)

# 3. Déployer vers Fabric
from fabric_api import FabricDeployer
deployer = FabricDeployer()
deployer.deploy_from_file(
    workspace_id='your-workspace-id',
    artifact_path=Path('migrated_artifacts/Sales Dashboard.json'),
    artifact_type='Report'
)
```

## ⚠️ Limitations

### Conversions manuelles requises

Certaines fonctionnalités Qlik n'ont pas d'équivalent direct en Power Query M:

❌ **Set Analysis** - Doit être recréé avec des filtres M  
❌ **Variables Qlik** - À définir comme paramètres Power Query  
❌ **Fonctions inter-enregistrements** (Previous, Peek, etc.) - Logique à recréer  
❌ **CONCATENATE** - Utiliser `Table.Combine()` manuellement  
❌ **Fichiers QVD** - Nécessite un connecteur personnalisé  
❌ **Sections du script** (HIDE, QUALIFY) - À gérer manuellement  

### Nécessite révision

⚠️ **Chemins de fichiers** - Mettre à jour les chemins absolus  
⚠️ **Connexions DB** - Configurer serveurs et credentials  
⚠️ **Formats de date** - Vérifier les formats régionaux  
⚠️ **Encodage** - Ajuster si nécessaire (UTF-8 vs ANSI)  
⚠️ **Optimisation** - Revoir les étapes pour performance  

## 📊 Exemple Complet

### Script Qlik original

```qlik
// Chargement des ventes
LOAD
    OrderID,
    OrderDate,
    CustomerID,
    ProductID,
    Quantity,
    UnitPrice,
    Quantity * UnitPrice as TotalAmount,
    Year(OrderDate) as OrderYear,
    Month(OrderDate) as OrderMonth
FROM [C:\Data\Sales.csv]
(txt, codepage is 1252, embedded labels, delimiter is ',')
WHERE OrderDate >= Date('2023-01-01');

// Agrégation par client
LOAD
    CustomerID,
    Sum(TotalAmount) as TotalSales,
    Count(OrderID) as OrderCount
RESIDENT Sales
GROUP BY CustomerID;
```

### Script Power Query M généré

```m
// Query: Sales
let
    Source = Csv.Document(File.Contents("C:\Data\Sales.csv"),[Delimiter=",", Columns=auto, Encoding=65001, QuoteStyle=QuoteStyle.None]),
    PromotedHeaders = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    AddedColumns = Table.AddColumn(PromotedHeaders, "Calculated", each [
        OrderID,
        OrderDate,
        CustomerID,
        ProductID,
        Quantity,
        UnitPrice,
        TotalAmount = [Quantity] * [UnitPrice],
        OrderYear = Date.Year([OrderDate]),
        OrderMonth = Date.Month([OrderDate])
    ]),
    Filtered = Table.SelectRows(AddedColumns, each ([OrderDate] >= Date.From('2023-01-01')))
in
    Filtered

// Query: CustomerSummary
let
    Source = Sales,
    Grouped = Table.Group(Source, {"CustomerID"}, {
        {"TotalSales", each List.Sum([TotalAmount]), type number},
        {"OrderCount", each List.Count([OrderID]), type number}
    })
in
    Grouped
```

## 🔧 Configuration Avancée

### Ajouter des conversions personnalisées

Modifier `qlik_script_converter.py`:

```python
# Ajouter vos propres mappings
CUSTOM_FUNCTION_MAP = {
    'MyCustomQlikFunc': 'MyCustomPQFunc',
    'SpecialTransform': 'Table.TransformColumns'
}

# Fusionner avec le mapping existant
QlikScriptToPowerQueryConverter.FUNCTION_MAP.update(CUSTOM_FUNCTION_MAP)
```

## 📝 Workflow recommandé

1. **Migration automatique** - Exécuter `migrate_qlik_scripts.py`
2. **Révision manuelle** - Ouvrir les fichiers .pq générés
3. **Ajustements** - Corriger chemins, connexions, fonctions non converties
4. **Test dans Power BI** - Copier le script dans Power Query Editor
5. **Validation** - Vérifier les données chargées
6. **Optimisation** - Améliorer les performances si nécessaire
7. **Documentation** - Noter les changements manuels

## 🆘 Dépannage

### Erreur: "LOAD statement mal formé"

→ Vérifier la syntaxe du LOAD  
→ S'assurer que FROM/RESIDENT/INLINE est présent  
→ Vérifier les virgules entre les champs  

### Erreur: "Fichier non trouvé"

→ Mettre à jour les chemins de fichiers absolus  
→ Vérifier que les sources existent  

### Fonctions non converties

→ Consulter le rapport de conversion  
→ Remplacer manuellement par équivalents M  
→ Référencer la [documentation Power Query M](https://learn.microsoft.com/power-query/)  

## 📚 Ressources

- **[Power Query M Reference](https://learn.microsoft.com/power-query/power-query-formula-language-spec)**
- **[Qlik Script Reference](https://help.qlik.com/en-US/sense/Subsystems/Hub/Content/Sense_Hub/Scripting/ScriptRegularStatements/script-regular-statements.htm)**
- **[Power BI Community](https://community.powerbi.com/)**

## ✅ Prochaines étapes après migration

1. ✅ Ouvrir Power BI Desktop
2. ✅ Créer nouvelle requête → Éditeur avancé
3. ✅ Copier-coller le script .pq
4. ✅ Ajuster les connexions aux sources
5. ✅ Tester le chargement des données
6. ✅ Valider les transformations
7. ✅ Créer les relations entre tables
8. ✅ Publier vers Power BI Service

---

**Note**: Cette conversion automatise ~80% du travail. Une révision manuelle est toujours recommandée pour garantir la qualité et l'exactitude.

