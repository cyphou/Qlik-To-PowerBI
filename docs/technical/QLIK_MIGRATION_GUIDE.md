# Guide de Migration Qlik vers Power BI

Ce guide explique comment migrer vos rapports Qlik Sense vers Power BI en utilisant l'API Fabric.

## 📋 Vue d'ensemble

Le module `qlik_migrator.py` automatise la migration de vos applications Qlik Sense vers des rapports Power BI, incluant:

- ✅ **Dimensions** → Colonnes Power BI
- ✅ **Mesures** → Mesures DAX Power BI
- ✅ **Visualisations** → Visuels Power BI
- ✅ **Expressions Qlik** → Expressions DAX
- ✅ **Tableaux de bord** → Pages de rapport Power BI

## 🔄 Processus de Migration

### Étape 1: Exporter l'application Qlik

#### Via Qlik Sense Desktop
1. Ouvrir l'application dans Qlik Sense
2. Utiliser l'API Engine pour exporter les métadonnées
3. Exporter en format JSON

#### Via QMC (Qlik Management Console)
1. Se connecter à QMC
2. Aller dans **Apps**
3. Sélectionner l'application
4. Exporter les métadonnées (nécessite un script personnalisé)

#### Exemple de script d'export Qlik
```javascript
// Script Qlik pour extraire les métadonnées
const enigma = require('enigma.js');
const schema = require('enigma.js/schemas/12.20.0.json');
const WebSocket = require('ws');

const config = {
  schema,
  url: 'ws://localhost:4848/app/engineData',
  createSocket: url => new WebSocket(url)
};

(async () => {
  const session = enigma.create(config);
  const global = await session.open();
  const doc = await global.openDoc('your-app-id');
  
  // Extraire dimensions
  const dimensionList = await doc.getDimensionList();
  
  // Extraire mesures
  const measureList = await doc.getMeasureList();
  
  // Extraire feuilles
  const sheets = await doc.getSheets();
  
  // Sauvegarder en JSON
  const metadata = {
    qTitle: await doc.getAppLayout().qTitle,
    properties: {
      qDimensionList: dimensionList,
      qMeasureList: measureList
    },
    sheets: sheets
  };
  
  console.log(JSON.stringify(metadata, null, 2));
  
  await session.close();
})();
```

### Étape 2: Préparer l'environnement

```bash
# Installer les dépendances supplémentaires si nécessaire
pip install -r requirements.txt

# Créer le dossier pour les exports Qlik
mkdir qlik_exports
mkdir migrated_artifacts
```

### Étape 3: Migrer les applications

#### Migration simple (une application)

```python
from pathlib import Path
from fabric_api.qlik_migrator import QlikToPowerBIMigrator

# Initialiser le migrateur
migrator = QlikToPowerBIMigrator(output_dir=Path('migrated_artifacts'))

# Migrer une application Qlik
pbi_report = migrator.migrate_qlik_app(
    qlik_app_path=Path('qlik_exports/sales_dashboard.json'),
    report_name='Sales Dashboard PBI'
)

print(f"Migration réussie: {pbi_report['displayName']}")
```

#### Migration en batch (plusieurs applications)

```python
from pathlib import Path
from fabric_api.qlik_migrator import QlikToPowerBIMigrator

migrator = QlikToPowerBIMigrator(output_dir=Path('migrated_artifacts'))

# Migrer toutes les applications d'un dossier
results = migrator.batch_migrate(
    qlik_apps_dir=Path('qlik_exports')
)

# Afficher les résultats
for result in results:
    if result['status'] == 'success':
        print(f"✓ {result['source']}")
    else:
        print(f"✗ {result['source']}: {result['error']}")
```

### Étape 4: Déployer vers Fabric

```python
from fabric_api import FabricDeployer
from pathlib import Path

deployer = FabricDeployer()

# Déployer le rapport migré
result = deployer.deploy_from_file(
    workspace_id='your-workspace-id',
    artifact_path=Path('migrated_artifacts/Sales Dashboard PBI.json'),
    artifact_type='Report',
    overwrite=True
)

print(f"Déployé avec l'ID: {result['id']}")
```

## 🔀 Conversions Supportées

### Types de visualisations

| Qlik Sense | Power BI | Statut |
|------------|----------|--------|
| Bar Chart | Clustered Bar Chart | ✅ |
| Line Chart | Line Chart | ✅ |
| Pie Chart | Pie Chart | ✅ |
| Table | Table | ✅ |
| Pivot Table | Matrix | ✅ |
| Scatter Plot | Scatter Chart | ✅ |
| Treemap | Treemap | ✅ |
| KPI | Card | ✅ |
| Gauge | Gauge | ✅ |
| Map | Map | ✅ |
| Combo Chart | Combo Chart | ⚠️ Partiel |
| Filter Pane | Slicer | ⚠️ Manuel |

### Fonctions d'agrégation

| Qlik | DAX |
|------|-----|
| `Sum(Sales)` | `SUM([Sales])` |
| `Avg(Price)` | `AVERAGE([Price])` |
| `Count(CustomerID)` | `COUNT([CustomerID])` |
| `Min(Date)` | `MIN([Date])` |
| `Max(Date)` | `MAX([Date])` |
| `Only(Category)` | `FIRSTNONBLANK([Category])` |

### Fonctions Set Analysis (limitations)

⚠️ **Important**: Le Set Analysis de Qlik n'a pas d'équivalent direct en DAX. Ces expressions nécessitent une conversion manuelle.

**Qlik:**
```qlik
Sum({<Year={2023}>} Sales)
```

**DAX équivalent:**
```dax
CALCULATE(
    SUM([Sales]),
    'Calendar'[Year] = 2023
)
```

## 📝 Format de fichier Qlik attendu

### Structure JSON minimale

```json
{
  "qTitle": "Mon Application Qlik",
  "properties": {
    "qDimensionList": {
      "qItems": [
        {
          "qInfo": {
            "qId": "dim1",
            "qType": "dimension"
          },
          "qMeta": {
            "title": "Product Category"
          },
          "qDim": {
            "qFieldDefs": ["ProductCategory"],
            "qGrouping": "N"
          }
        }
      ]
    },
    "qMeasureList": {
      "qItems": [
        {
          "qInfo": {
            "qId": "mea1",
            "qType": "measure"
          },
          "qMeta": {
            "title": "Total Sales"
          },
          "qMeasure": {
            "qDef": "Sum(Sales)",
            "qNumFormat": {
              "qFmt": "#,##0.00"
            }
          }
        }
      ]
    }
  },
  "sheets": [
    {
      "qProperty": {
        "qInfo": {
          "qId": "sheet1",
          "qType": "sheet"
        },
        "qMetaDef": {
          "title": "Dashboard"
        }
      },
      "cells": [
        {
          "name": "viz1",
          "type": "barchart",
          "title": "Sales by Category",
          "properties": {}
        }
      ]
    }
  ]
}
```

## 🎯 Workflow complet

### Script Python complet

```python
#!/usr/bin/env python
"""Script complet de migration Qlik vers Power BI."""
import sys
from pathlib import Path

# Ajouter le chemin source
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from fabric_api.qlik_migrator import QlikToPowerBIMigrator
from fabric_api import FabricDeployer
from fabric_api.config.settings import get_settings
settings = get_settings()

def main():
    """Migrer et déployer les applications Qlik."""
    
    # Configuration
    qlik_exports_dir = Path('qlik_exports')
    migrated_dir = Path('migrated_artifacts')
    workspace_id = settings.fabric_workspace_id
    
    # Étape 1: Migration
    print("=== Migration des applications Qlik ===")
    migrator = QlikToPowerBIMigrator(output_dir=migrated_dir)
    
    migration_results = migrator.batch_migrate(qlik_exports_dir)
    
    successful = [r for r in migration_results if r['status'] == 'success']
    print(f"\nRésultats: {len(successful)}/{len(migration_results)} migrations réussies")
    
    # Étape 2: Déploiement
    print("\n=== Déploiement vers Fabric ===")
    deployer = FabricDeployer()
    
    for artifact_file in migrated_dir.glob('*.json'):
        try:
            result = deployer.deploy_from_file(
                workspace_id=workspace_id,
                artifact_path=artifact_file,
                artifact_type='Report',
                overwrite=True
            )
            print(f"✓ Déployé: {artifact_file.name} (ID: {result['id']})")
        except Exception as e:
            print(f"✗ Échec: {artifact_file.name} - {e}")
    
    print("\n=== Migration et déploiement terminés ===")

if __name__ == '__main__':
    main()
```

Sauvegarder comme `migrate_qlik_to_pbi.py` et exécuter:

```bash
python migrate_qlik_to_pbi.py
```

## ⚠️ Limitations et Considérations

### Limitations techniques

1. **Set Analysis**: Conversion manuelle requise pour les expressions complexes
2. **Variables Qlik**: Doivent être recréées manuellement en DAX
3. **Extensions Qlik**: Non supportées, nécessitent des visuels personnalisés Power BI
4. **Scripts de chargement**: Doivent être migrés séparément (Power Query M)
5. **NPrinting/Alertes**: Non inclus dans la migration

### Données

⚠️ **Important**: Cette migration ne transfert **PAS** les données. Vous devez:

1. Migrer les scripts de chargement Qlik → Power Query M
2. Recréer les connexions aux sources de données
3. Configurer l'actualisation planifiée dans Power BI

### Post-migration requise

Après migration automatique, vérifier/ajuster manuellement:

- [ ] Formatage des visuels
- [ ] Couleurs et thèmes
- [ ] Interactions entre visuels
- [ ] Filtres et slicers
- [ ] Tri et hiérarchies
- [ ] Mesures complexes (Set Analysis)
- [ ] Connexions aux données
- [ ] RLS (Row-Level Security)

## 🔧 Personnalisation

### Ajouter des conversions de fonctions

Modifier `qlik_migrator.py`:

```python
def convert_qlik_expression_to_dax(qlik_expr: str) -> str:
    """Convertir expression Qlik en DAX."""
    dax = qlik_expr
    
    # Ajouter vos conversions personnalisées
    custom_replacements = {
        'YourQlikFunc(': 'YourDAXFunc(',
        # ... autres conversions
    }
    
    for qlik_func, dax_func in custom_replacements.items():
        dax = dax.replace(qlik_func, dax_func)
    
    return dax
```

### Personnaliser le mapping des visuels

```python
class QlikToPowerBIConverter:
    VISUAL_TYPE_MAP = {
        'barchart': 'clusteredBarChart',
        'your-custom-viz': 'your-pbi-visual',
        # Ajouter vos mappings
    }
```

## 📊 Exemple complet

### Fichier Qlik: `sales_dashboard.json`

```json
{
  "qTitle": "Tableau de bord des ventes",
  "properties": {
    "qDimensionList": {
      "qItems": [
        {
          "qInfo": {"qId": "dim_product"},
          "qMeta": {"title": "Produit"},
          "qDim": {"qFieldDefs": ["Product"]}
        },
        {
          "qInfo": {"qId": "dim_region"},
          "qMeta": {"title": "Région"},
          "qDim": {"qFieldDefs": ["Region"]}
        }
      ]
    },
    "qMeasureList": {
      "qItems": [
        {
          "qInfo": {"qId": "mea_sales"},
          "qMeta": {"title": "Ventes totales"},
          "qMeasure": {
            "qDef": "Sum(Sales)",
            "qNumFormat": {"qFmt": "#,##0 €"}
          }
        }
      ]
    }
  },
  "sheets": [
    {
      "cells": [
        {
          "name": "viz_sales_by_product",
          "type": "barchart",
          "title": "Ventes par produit"
        }
      ]
    }
  ]
}
```

### Commande de migration

```bash
python -c "
from pathlib import Path
from fabric_api.qlik_migrator import QlikToPowerBIMigrator

migrator = QlikToPowerBIMigrator()
migrator.migrate_qlik_app(
    Path('qlik_exports/sales_dashboard.json'),
    'Tableau de bord des ventes'
)
"
```

### Résultat: `migrated_artifacts/Tableau de bord des ventes.json`

Fichier Power BI prêt au déploiement!

## 🆘 Support

### Problèmes courants

**Erreur: "Invalid Qlik app format"**
→ Vérifier la structure JSON du fichier exporté

**Expressions DAX incorrectes**
→ Réviser manuellement les mesures complexes après migration

**Visuels manquants**
→ Vérifier que le type de visualisation est supporté

### Ressources

- [Qlik Engine API](https://help.qlik.com/en-US/sense-developer/APIs-and-SDKs.htm)
- [Power BI REST API](https://learn.microsoft.com/en-us/rest/api/power-bi/)
- [DAX Guide](https://dax.guide/)
- [Enigma.js](https://github.com/qlik-oss/enigma.js)

## 📈 Prochaines fonctionnalités

- [ ] Support NPrinting → Power BI Subscriptions
- [ ] Migration des scripts de chargement → Power Query M
- [ ] Conversion Set Analysis avancée
- [ ] Migration des extensions Qlik → Custom visuals Power BI
- [ ] Outil de comparaison avant/après migration

---

**Note**: Cette migration automatise la structure du rapport. Une révision manuelle est toujours recommandée pour garantir la qualité et l'exactitude.
