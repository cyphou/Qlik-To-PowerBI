<!-- DOC-SHINY-BANNER -->
![Documentation](https://img.shields.io/badge/Documentation-Shiny_Style-0A66C2?style=flat-square&logo=readthedocs&logoColor=white)
![Maintained](https://img.shields.io/badge/Maintained-2026-2EA44F?style=flat-square&logo=github&logoColor=white)
![Navigation](https://img.shields.io/badge/Navigation-Quick_Access-6F42C1?style=flat-square&logo=bookstack&logoColor=white)
# 🔄 Migration Alternative - Qlik Cloud QVF → Power BI

## 📋 Situation

Vous avez un fichier **QVF Qlik Cloud** (format binaire propriétaire) qui ne peut pas être migré directement avec `migrate_qvf.py`.

**Fichier détecté :** `Demo App - Qlik Cloud Reporting.qvf`
- Format : Qlik Cloud (binaire, signature `FF FF 01 00`)
- Taille : 0.28 MB
- Type : NON compatible avec extraction ZIP

---

## ✅ Solution Recommandée : Migration Manuelle des Données

### Fichiers Sources Disponibles

Les fichiers de données Excel/CSV sont présents dans le dossier :

```
C:\Users\pidoudet\Downloads\ReportingExampleMaterials\ReportingExampleMaterials\
├── Cities.xlsx (16.3 KB)
├── Customers.xlsx (31.5 KB)
├── Item master.xlsx (32.7 KB)
├── Sales.xlsx (11.4 MB) ⭐ Fichier principal
└── Sales rep.csv (6.6 KB)
```

---

## 🚀 Étapes de Migration (30-45 minutes)

### ÉTAPE 1 : Créer le Modèle Power BI (15 min)

1. **Ouvrir Power BI Desktop**

2. **Importer les données sources**
   ```
   Obtenir des données → Excel
   → Sélectionner : Cities.xlsx, Customers.xlsx, Item master.xlsx, Sales.xlsx
   
   Obtenir des données → Texte/CSV
   → Sélectionner : Sales rep.csv
   ```

3. **Transformer si nécessaire** (Power Query)
   - Vérifier types de colonnes
   - Renommer tables si besoin
   - Supprimer colonnes inutiles

4. **Fermer et appliquer**

---

### ÉTAPE 2 : Créer les Relations (5 min)

1. **Aller dans : Vue Modèle**

2. **Créer les relations probables :**
   
   Relations typiques pour ce type d'app :
   ```
   Sales → Customers
   └─ via Customer ID
   
   Sales → Item master
   └─ via Item ID / Product ID
   
   Sales → Sales rep
   └─ via Sales Rep ID
   
   Sales → Cities (optionnel)
   └─ via City ID
   ```

3. **Vérifier cardinalité**
   - `Sales` (table de faits) : côté "plusieurs" (∞)
   - Autres tables (dimensions) : côté "un" (1)

---

### ÉTAPE 3 : Créer les Mesures (10 min)

Mesures typiques pour une app Sales :

```dax
// Mesures de base
Total Sales = SUM(Sales[Sales Amount])

Total Quantity = SUM(Sales[Quantity])

Average Sale = AVERAGE(Sales[Sales Amount])

Number of Transactions = COUNTROWS(Sales)

// Mesures avancées
Sales YTD = TOTALYTD([Total Sales], 'Calendar'[Date])

Sales vs PY = 
VAR CurrentSales = [Total Sales]
VAR PreviousYearSales = CALCULATE([Total Sales], SAMEPERIODLASTYEAR('Calendar'[Date]))
RETURN
CurrentSales - PreviousYearSales

YoY Growth % = 
DIVIDE(
    [Total Sales] - CALCULATE([Total Sales], SAMEPERIODLASTYEAR('Calendar'[Date])),
    CALCULATE([Total Sales], SAMEPERIODLASTYEAR('Calendar'[Date])),
    0
) * 100
```

---

### ÉTAPE 4 : Créer les Visualisations (10 min)

**Visuels recommandés pour une app Sales :**

1. **KPI Cards**
   - Champs : `[Total Sales]`, `[Total Quantity]`, `[Number of Transactions]`
   - Type : Carte (Card)

2. **Sales Trends**
   - Axe X : Date (hiérarchie)
   - Axe Y : `[Total Sales]`
   - Type : Graphique en courbes

3. **Sales by Product/Category**
   - Axe : Product Name / Category
   - Valeurs : `[Total Sales]`
   - Type : Graphique à barres

4. **Sales by Region/City**
   - Emplacement : City, Region
   - Taille : `[Total Sales]`
   - Type : Carte (Map)

5. **Top Customers**
   - Lignes : Customer Name
   - Valeurs : `[Total Sales]`
   - Type : Table ou Matrice

6. **Sales Rep Performance**
   - Axe : Sales Rep Name
   - Valeurs : `[Total Sales]`, `[Number of Transactions]`
   - Type : Graphique à barres groupées

---

## 🔧 Script Power Query Automatisé (Optionnel)

Si vous voulez automatiser l'import, créez ce script Power Query M :

```m
let
    // Dossier source
    SourceFolder = "C:\Users\pidoudet\Downloads\ReportingExampleMaterials\ReportingExampleMaterials\",
    
    // Import Cities
    Cities = Excel.Workbook(File.Contents(SourceFolder & "Cities.xlsx"), null, true),
    CitiesTable = Cities{[Item="Cities",Kind="Sheet"]}[Data],
    CitiesHeaders = Table.PromoteHeaders(CitiesTable, [PromoteAllScalars=true]),
    
    // Import Customers
    Customers = Excel.Workbook(File.Contents(SourceFolder & "Customers.xlsx"), null, true),
    CustomersTable = Customers{[Item="Customers",Kind="Sheet"]}[Data],
    CustomersHeaders = Table.PromoteHeaders(CustomersTable, [PromoteAllScalars=true]),
    
    // Import Item Master
    ItemMaster = Excel.Workbook(File.Contents(SourceFolder & "Item master.xlsx"), null, true),
    ItemMasterTable = ItemMaster{[Item="Item master",Kind="Sheet"]}[Data],
    ItemMasterHeaders = Table.PromoteHeaders(ItemMasterTable, [PromoteAllScalars=true]),
    
    // Import Sales (fichier principal)
    Sales = Excel.Workbook(File.Contents(SourceFolder & "Sales.xlsx"), null, true),
    SalesTable = Sales{[Item="Sales",Kind="Sheet"]}[Data],
    SalesHeaders = Table.PromoteHeaders(SalesTable, [PromoteAllScalars=true]),
    
    // Import Sales Rep (CSV)
    SalesRep = Csv.Document(File.Contents(SourceFolder & "Sales rep.csv"), [Delimiter=",", Encoding=65001]),
    SalesRepHeaders = Table.PromoteHeaders(SalesRep, [PromoteAllScalars=true])
in
    SalesHeaders  // Retourne la table Sales
```

**Pour utiliser ce script :**
1. Power BI Desktop → Obtenir des données → Requête vide
2. Éditeur avancé
3. Coller le script ci-dessus
4. Modifier le chemin `SourceFolder` si nécessaire
5. Répéter pour chaque table (Cities, Customers, etc.)

---

## ⚡ Alternative : Générer Script Automatiquement

Utilisez ce script Python pour générer tous les scripts Power Query :

```bash
cd "c:\Users\pidoudet\OneDrive - Microsoft\Boulot\PBI SME\OracleToPostgre\fabric-deployment"

python generate_pq_from_sources.py "C:\Users\pidoudet\Downloads\ReportingExampleMaterials\ReportingExampleMaterials"
```

**Cela va générer :**
- `cities.pq` - Script Power Query pour Cities
- `customers.pq` - Script Power Query pour Customers
- `item_master.pq` - Script Power Query pour Item Master
- `sales.pq` - Script Power Query pour Sales
- `sales_rep.pq` - Script Power Query pour Sales Rep

---

## 📊 Résultat Attendu

Après ces 4 étapes, vous aurez :

✅ **Modèle de données** complet avec 5 tables  
✅ **Relations** entre tables (modèle en étoile)  
✅ **Mesures DAX** pour analyses  
✅ **Visualisations** interactives  
✅ **Rapport fonctionnel** Power BI

**Temps total : 30-45 minutes**

---

## 🆘 Besoin du Format ZIP pour Migration Automatique ?

Si vous avez accès à **Qlik Cloud** ou **Qlik Sense Desktop**, voici comment obtenir un QVF au format ZIP :

### Option A : Depuis Qlik Cloud

1. Ouvrir l'app dans Qlik Cloud
2. Menu (⋮) → **Exporter**
3. Choisir : **"Exporter au format Desktop"** ou **"Export for Qlik Sense Desktop"**
4. Le fichier téléchargé sera au format ZIP ✅
5. Utiliser `migrate_qvf.py` sur ce nouveau fichier

### Option B : Via Qlik Sense Desktop

1. **Importer** ce QVF dans Qlik Sense Desktop
   - Ouvrir Qlik Sense Desktop
   - Hub → Importer une app → Sélectionner le .qvf
2. **Ouvrir** l'application importée
3. **Exporter** à nouveau
   - Menu → Exporter → Sauvegarder comme .qvf
4. Le nouveau fichier sera au format ZIP ✅
5. Utiliser `migrate_qvf.py` sur ce fichier

---

## 🎯 Étapes Suivantes

**Choix 1 : Migration Manuelle (Recommandé pour ce cas)**
```bash
# Générer les scripts Power Query pour les fichiers sources
python generate_pq_from_sources.py "C:\Users\pidoudet\Downloads\ReportingExampleMaterials\ReportingExampleMaterials"

# Puis importer dans Power BI Desktop
```

**Choix 2 : Obtenir QVF au Format ZIP**
- Suivre "Option A" ou "Option B" ci-dessus
- Puis utiliser : `python migrate_qvf.py <nouveau_fichier.qvf>`

---

## 📞 Support

**Diagnostic QVF :**
```bash
python diagnose_qvf.py "chemin/vers/fichier.qvf"
```

**Documentation :**
- [QUICK_START_HYBRIDE.md](QUICK_START_HYBRIDE.md) - Migration QVF standard
- [README_MIGRATION_COMPLETE.md](README_MIGRATION_COMPLETE.md) - Vue d'ensemble

---

**✨ Bonne migration !**

*Note : Cette approche manuelle est parfois PLUS rapide que la migration automatique pour des modèles simples avec fichiers sources disponibles.*

