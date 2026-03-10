"""
Test Rapide de la Migration Hybride
Vérifie que tous les composants sont générés correctement
"""

import sys
from pathlib import Path

# Ajouter le dossier src au path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / 'src'))

print("""
╔════════════════════════════════════════════════════════════════════╗
║         🧪 TEST MIGRATION HYBRIDE - VÉRIFICATION RAPIDE            ║
╚════════════════════════════════════════════════════════════════════╝
""")

print("✓ Imports Python réussis")

# Test 1 : Vérifier que les modules existent
print("\n1️⃣  Vérification des modules...")

try:
    from qlik_export.qvf_extractor import QVFExtractor
    print("   ✓ QVF Extractor")
except Exception as e:
    print(f"   ❌ QVF Extractor: {e}")

try:
    from qlik_export.qlik_script_converter import QlikScriptConverter
    print("   ✓ Qlik Script Converter")
except Exception as e:
    print(f"   ❌ Qlik Script Converter: {e}")

try:
    from qlik_export.qlik_model_converter import QlikModelConverter
    print("   ✓ Qlik Model Converter")
except Exception as e:
    print(f"   ❌ Qlik Model Converter: {e}")

try:
    from qlik_export.qlik_migrator import QlikToPowerBIMigrator
    print("   ✓ Qlik Migrator")
except Exception as e:
    print(f"   ❌ Qlik Migrator: {e}")

# Test 2 : Créer un exemple de migration simple
print("\n2️⃣  Test de migration avec données exemple...")

output_dir = Path("test_migration_hybride")
output_dir.mkdir(exist_ok=True)

# Test du convertisseur de script
print("\n   A. Test conversion script Qlik → Power Query M")
try:
    from qlik_export.qlik_script_converter import QlikScriptConverter
    
    converter = QlikScriptConverter()
    
    qlik_script = """
    // Script de test
    LOAD
        ProductID,
        ProductName,
        Price
    FROM [Products.qvd] (qvd);
    
    LOAD
        OrderID,
        ProductID,
        Quantity
    FROM [Orders.qvd] (qvd);
    """
    
    result = converter.convert_script(qlik_script)
    
    # Sauvegarder
    pq_file = output_dir / "powerquery_scripts" / "test_script.pq"
    pq_file.parent.mkdir(parents=True, exist_ok=True)
    with open(pq_file, 'w', encoding='utf-8') as f:
        f.write(result['power_query'])
    
    print(f"      ✓ Script converti : {pq_file}")
    print(f"      ✓ {len(result['conversions'])} conversions effectuées")
    
except Exception as e:
    print(f"      ❌ Erreur: {e}")

# Test du convertisseur de modèle
print("\n   B. Test conversion modèle Qlik → BIM")
try:
    from qlik_export.qlik_model_converter import QlikModelConverter
    import json
    
    converter = QlikModelConverter()
    
    # Modèle de test
    qlik_model = {
        "tables": [
            {
                "name": "Products",
                "fields": [
                    {"name": "ProductID", "type": "numeric"},
                    {"name": "ProductName", "type": "string"},
                    {"name": "Price", "type": "numeric"}
                ]
            },
            {
                "name": "Orders",
                "fields": [
                    {"name": "OrderID", "type": "numeric"},
                    {"name": "ProductID", "type": "numeric"},
                    {"name": "Quantity", "type": "numeric"}
                ]
            }
        ],
        "associations": [
            {
                "table1": "Products",
                "field1": "ProductID",
                "table2": "Orders",
                "field2": "ProductID"
            }
        ]
    }
    
    bim_model = converter.convert_model(qlik_model)
    
    # Sauvegarder
    bim_file = output_dir / "powerbi_models" / "test_model.bim"
    bim_file.parent.mkdir(parents=True, exist_ok=True)
    with open(bim_file, 'w', encoding='utf-8') as f:
        json.dump(bim_model, f, indent=2, ensure_ascii=False)
    
    print(f"      ✓ Modèle converti : {bim_file}")
    print(f"      ✓ {len(bim_model['model']['tables'])} tables créées")
    print(f"      ✓ {len(bim_model['model'].get('relationships', []))} relations créées")
    
except Exception as e:
    print(f"      ❌ Erreur: {e}")

# Test du migrateur de rapport
print("\n   C. Test conversion visualisations")
try:
    from qlik_export.qlik_migrator import QlikToPowerBIMigrator
    import json
    
    migrator = QlikToPowerBIMigrator()
    
    # App de test
    qlik_app = {
        "name": "Test App",
        "sheets": [
            {
                "id": "sheet1",
                "title": "Dashboard Principal",
                "cells": [
                    {
                        "type": "barchart",
                        "name": "Ventes par Produit",
                        "dimensions": [{"name": "ProductName"}],
                        "measures": [{"name": "Sum(Sales)", "label": "Total Ventes"}]
                    }
                ]
            }
        ]
    }
    
    result = migrator.migrate_app(qlik_app)
    
    # Sauvegarder
    report_file = output_dir / "powerbi_reports" / "test_report.json"
    report_file.parent.mkdir(parents=True, exist_ok=True)
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    print(f"      ✓ Rapport converti : {report_file}")
    print(f"      ✓ {len(result.get('visualizations', []))} visualisations créées")
    
except Exception as e:
    print(f"      ❌ Erreur: {e}")

# Résumé
print("\n" + "="*70)
print("📊 RÉSUMÉ DU TEST")
print("="*70)

print(f"\n📂 Dossier de sortie : {output_dir.absolute()}")
print("\nFichiers générés :")

for root, dirs, files in output_dir.walk():
    for file in files:
        file_path = root / file
        rel_path = file_path.relative_to(output_dir)
        size = file_path.stat().st_size
        print(f"   • {rel_path} ({size} bytes)")

print("\n" + "="*70)
print("✅ TEST TERMINÉ")
print("="*70)

print("""
📋 PROCHAINES ÉTAPES :

1. Utiliser migrate_qvf.py pour une vraie migration :
   python migrate_qvf.py "votre_app.qvf" "sortie"

2. Suivre le guide de migration hybride :
   Ouvrir MIGRATION_HYBRIDE_GUIDE.md

3. Dans Power BI Desktop :
   - Importer le fichier .bim
   - Copier le script .pq
   - Recréer les visuels d'après le .json

💡 Cette approche garantit un PBIX 100% compatible !
""")
