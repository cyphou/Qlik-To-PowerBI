<!-- DOC-SHINY-BANNER -->
![Documentation](https://img.shields.io/badge/Documentation-Shiny_Style-0A66C2?style=flat-square&logo=readthedocs&logoColor=white)
![Maintained](https://img.shields.io/badge/Maintained-2026-2EA44F?style=flat-square&logo=github&logoColor=white)
![Navigation](https://img.shields.io/badge/Navigation-Quick_Access-6F42C1?style=flat-square&logo=bookstack&logoColor=white)
# Migration du Modèle de Données Qlik → Power BI

## 📋 Vue d'ensemble

Ce module migre le **modèle de données** (relations entre tables, hiérarchies) d'une application Qlik vers un modèle Power BI.

### Ce qui est migré

✅ **Relations entre tables** - Inférées depuis les associations Qlik  
✅ **Cardinalités** - One-to-Many, Many-to-One, etc.  
✅ **Hiérarchies** - Hiérarchies de dates automatiques  
✅ **Fichier .bim** - Business Intelligence Model pour Power BI  
✅ **Documentation** - Rapport détaillé des relations  

## 🚀 Démarrage Rapide

### 1. Exporter l'application Qlik

Assurez-vous que votre export JSON Qlik contient le script de chargement (`loadScript`).

### 2. Exécuter la migration

```bash
python migrate_qlik_model.py
```

### 3. Résultat

Les fichiers générés dans `powerbi_models/`:
- `app_name_model.bim` - Modèle Power BI
- `app_name_model_doc.md` - Documentation des relations

## 📊 Extraction du Modèle

### Ce qui est extrait de Qlik

1. **Tables et champs** - À partir du script LOAD
2. **Associations naturelles** - Champs communs entre tables
3. **Clés synthétiques** - Détectées et signalées pour révision
4. **Colonnes de dates** - Pour créer des hiérarchies

### Inférence des Relations

#### Règles heuristiques

- **Champs nommés `*ID` ou `*Id`** → Probablement des clés étrangères
  - `CustomerID` dans `Sales` → Relation vers `Customers`
  - Direction: Many-to-One (plusieurs ventes par client)

- **Champs communs sans suffix ID** → Association naturelle
  - `Country` dans `Sales` et `Countries` → Relation possible
  - Nécessite révision manuelle

- **Cardinalité par défaut** → Many-to-One
  - Ajustable manuellement dans Power BI

## 🔄 Exemple de Migration

### Modèle Qlik (script de chargement)

```qlik
// Table Customers
LOAD
    CustomerID,
    CustomerName,
    Country
FROM [Customers.csv];

// Table Sales  
LOAD
    OrderID,
    OrderDate,
    CustomerID,
    ProductID,
    Amount
FROM [Sales.csv];

// Table Products
LOAD
    ProductID,
    ProductName,
    Category
FROM [Products.csv];
```

### Modèle Power BI généré (.bim)

```json
{
  "name": "Migrated Qlik Model",
  "model": {
    "tables": [
      {"name": "Customers", "columns": [...]},
      {"name": "Sales", "columns": [...]},
      {"name": "Products", "columns": [...]}
    ],
    "relationships": [
      {
        "name": "Sales_Customers",
        "fromTable": "Sales",
        "fromColumn": "CustomerID",
        "toTable": "Customers",
        "toColumn": "CustomerID",
        "crossFilteringBehavior": "Single",
        "isActive": true
      },
      {
        "name": "Sales_Products",
        "fromTable": "Sales",
        "fromColumn": "ProductID",
        "toTable": "Products",
        "toColumn": "ProductID",
        "crossFilteringBehavior": "Single",
        "isActive": true
      }
    ]
  }
}
```

### Visualisation du modèle

```
Customers (1) ←──── (*) Sales (*) ────→ (1) Products
   ↓                     ↓                    ↓
CustomerID           CustomerID           ProductID
CustomerName         ProductID            ProductName
Country              OrderDate            Category
                     Amount
```

## 📁 Hiérarchies Automatiques

### Hiérarchies de dates

Pour chaque colonne contenant "Date" ou "Time", une hiérarchie est créée:

```
OrderDate Hierarchy
├── Year
├── Quarter
├── Month
└── Day
```

### Exemple dans le .bim

```json
{
  "name": "OrderDate Hierarchy",
  "table": "Sales",
  "levels": [
    {"name": "Year", "column": "OrderDate.Year", "ordinal": 0},
    {"name": "Quarter", "column": "OrderDate.Quarter", "ordinal": 1},
    {"name": "Month", "column": "OrderDate.Month", "ordinal": 2},
    {"name": "Day", "column": "OrderDate.Day", "ordinal": 3}
  ]
}
```

## ⚠️ Clés Synthétiques Qlik

### Qu'est-ce qu'une clé synthétique ?

Qlik crée automatiquement des clés synthétiques (nommées `$Syn1`, `$Syn2`, etc.) quand plusieurs champs créent une association circulaire ou complexe.

### Dans Power BI

❌ **Les clés synthétiques ne sont pas supportées**

✅ **Solution**: Créer manuellement les relations appropriées

### Exemple

**Qlik détecte:**
```
$Syn1 Table (clé synthétique)
├── Country
├── Region
└── City
```

**Action requise:**
1. Identifier les vraies relations logiques
2. Créer les tables de dimension appropriées
3. Définir les relations explicitement dans Power BI

## 💻 Utilisation Programmatique

### Migration basique

```python
from fabric_api.qlik_model_converter import QlikModelMigrator
from pathlib import Path
import json

# Charger l'app Qlik
with open('qlik_exports/sales_app.json') as f:
    qlik_app = json.load(f)

# Migrer le modèle
migrator = QlikModelMigrator()
result = migrator.migrate_model(
    qlik_app,
    Path('powerbi_models/sales_model.bim')
)

if result['status'] == 'success':
    print(f"Tables: {result['tables_count']}")
    print(f"Relations: {result['relationships_count']}")
```

### Générer la documentation

```python
# Générer la documentation du modèle
doc = migrator.generate_documentation(result)

with open('model_documentation.md', 'w') as f:
    f.write(doc)
```

### Accéder aux détails

```python
# Obtenir les relations
bim_model = result['model']
relationships = bim_model['model']['relationships']

for rel in relationships:
    print(f"{rel['fromTable']}.{rel['fromColumn']} → "
          f"{rel['toTable']}.{rel['toColumn']}")
```

## 🎯 Intégration dans le Workflow Complet

### Workflow: Qlik → Power BI (Apps + Scripts + Modèle)

```python
from fabric_api import QlikToPowerBIMigrator, FabricDeployer
from fabric_api.qlik_script_converter import QlikScriptMigrator
from fabric_api.qlik_model_converter import QlikModelMigrator
from pathlib import Path
import json

# 1. Migrer les scripts de chargement
script_migrator = QlikScriptMigrator()
script_migrator.migrate_script_file(
    'qlik_scripts/sales_load.qvs',
    'powerquery_scripts/sales_load.pq'
)

# 2. Migrer le modèle de données
with open('qlik_exports/sales_app.json') as f:
    qlik_app = json.load(f)

model_migrator = QlikModelMigrator()
model_result = model_migrator.migrate_model(
    qlik_app,
    Path('powerbi_models/sales_model.bim')
)

# 3. Migrer l'application (visualisations)
app_migrator = QlikToPowerBIMigrator()
app_migrator.migrate_qlik_app(
    Path('qlik_exports/sales_app.json'),
    'Sales Dashboard'
)

# 4. Créer le rapport Power BI:
# - Importer les scripts .pq dans Power Query
# - Créer les relations depuis le .bim
# - Ajouter les visualisations migrées

# 5. Déployer vers Fabric
deployer = FabricDeployer()
deployer.deploy_from_file(
    workspace_id='your-workspace-id',
    artifact_path=Path('migrated_artifacts/Sales Dashboard.json'),
    artifact_type='Report'
)
```

## 📋 Cardinalités Supportées

| Type | Qlik | Power BI | Description |
|------|------|----------|-------------|
| 1:n | Association naturelle | One-to-Many | 1 client → Multiple commandes |
| n:1 | Association naturelle | Many-to-One | Multiple commandes → 1 client |
| 1:1 | Rare en Qlik | One-to-One | 1 employé → 1 badge |
| n:n | Via table ponte | Many-to-Many | Multiple produits ↔ Multiple catégories |

## 🔧 Personnalisation

### Ajuster les règles d'inférence

Modifier `qlik_model_converter.py`:

```python
def convert_association_to_relationship(self, association, table_info):
    # Vos règles personnalisées
    if association.from_table == 'FactSales':
        cardinality = RelationshipCardinality.MANY_TO_ONE
    elif association.from_field.startswith('Dim'):
        cardinality = RelationshipCardinality.ONE_TO_MANY
    else:
        cardinality = RelationshipCardinality.MANY_TO_ONE
    
    # ...
```

### Créer des hiérarchies personnalisées

```python
from fabric_api.qlik_model_converter import PowerBIHierarchy

# Hiérarchie géographique
geo_hierarchy = PowerBIHierarchy(
    name="Geography",
    table="Locations",
    levels=[
        ("Continent", "Continent"),
        ("Country", "Country"),
        ("Region", "Region"),
        ("City", "City")
    ]
)
```

## 📊 Utilisation du fichier .bim

### Dans Power BI Desktop

**Option 1: Tabular Editor (Recommandé)**
1. Installer [Tabular Editor](https://tabulareditor.com/)
2. Ouvrir votre fichier .pbix dans Power BI Desktop
3. Ouvrir Tabular Editor → Connecter au modèle
4. Importer le fichier .bim
5. Appliquer les changements

**Option 2: Création manuelle**
1. Ouvrir Power BI Desktop
2. Aller dans la vue 'Modèle'
3. Créer manuellement les relations selon la documentation
4. Vérifier les cardinalités et directions de filtrage

### Dans Power BI Service

1. Publier le rapport avec le modèle configuré
2. Les relations sont préservées

## ⚠️ Limitations et Révisions Nécessaires

### Révision Manuelle Obligatoire

❌ **Clés synthétiques** - Doivent être supprimées et remplacées  
❌ **Relations circulaires** - Doivent être corrigées  
❌ **Cardinalités complexes** - Peuvent nécessiter ajustement  
❌ **Bidirectionnalité** - À configurer selon besoins métier  

### Best Practices Power BI

⚠️ **Éviter les relations bidirectionnelles** (sauf cas spécifiques)  
⚠️ **Créer des tables de dates dédiées** (dimension commune)  
⚠️ **Utiliser des clés surrogates** pour les relations  
⚠️ **Tester les filtres croisés** après migration  

## 📝 Documentation Générée

### Contenu du fichier `*_model_doc.md`

```markdown
# Modèle de Données Migré - Qlik → Power BI

**Tables**: 5
**Relations**: 4
**Hiérarchies**: 2

## Relations

- **Sales**.`CustomerID` → **Customers**.`CustomerID` (Single)
- **Sales**.`ProductID` → **Products**.`ProductID` (Single)
- **Sales**.`OrderDate` → **Calendar`.`Date` (Single)
- **Products**.`CategoryID` → **Categories`.`CategoryID` (Single)

## ⚠️ Clés Synthétiques Détectées

- `$Syn1` - Révision manuelle requise
```

## 🆘 Dépannage

### "Aucune table trouvée"

→ Vérifier que l'export JSON contient le `loadScript`  
→ S'assurer que les LOAD statements sont bien formatés  

### "Trop de relations détectées"

→ Qlik peut avoir des associations multiples
→ Power BI nécessite un modèle en étoile/flocon de neige  
→ Simplifier le modèle manuellement  

### "Clés synthétiques $Syn*"

→ Identifier les champs causant la synthétisation  
→ Créer des tables intermédiaires si nécessaire  
→ Clarifier les relations métier  

## 📚 Ressources

- **[Power BI Data Modeling Best Practices](https://learn.microsoft.com/power-bi/guidance/star-schema)**
- **[Tabular Model Definition](https://learn.microsoft.com/analysis-services/tmsl/tabular-model-definition-language-tmsl)**
- **[Qlik Data Model](https://help.qlik.com/en-US/sense/Subsystems/Hub/Content/Sense_Hub/Introduction/data-model.htm)**

## ✅ Checklist Post-Migration

- [ ] Ouvrir le fichier .bim dans Tabular Editor
- [ ] Vérifier toutes les relations
- [ ] Corriger les cardinalités si nécessaire
- [ ] Supprimer les clés synthétiques
- [ ] Créer les relations manquantes
- [ ] Ajouter les hiérarchies personnalisées
- [ ] Configurer les formats d'affichage
- [ ] Tester les filtres croisés
- [ ] Valider les calculs de mesures
- [ ] Documenter les changements manuels

---

**Note**: Cette migration automatise ~70% du travail de modélisation. Une révision et validation manuelle sont essentielles pour un modèle optimal.

