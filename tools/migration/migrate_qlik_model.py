#!/usr/bin/env python
"""
Script de migration du modèle de données Qlik vers Power BI.

Ce script extrait le modèle de données (relations, hiérarchies) d'une application Qlik
et génère le fichier .bim pour Power BI.

Usage:
    python migrate_qlik_model.py

Configuration:
    - Placer les exports JSON Qlik dans 'qlik_exports/'
    - Les modèles Power BI (.bim) seront générés dans 'powerbi_models/'
"""

import sys
import logging
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / 'src'))

from qlik_export.qlik_model_converter import QlikModelMigrator

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Migrer les modèles de données Qlik vers Power BI."""
    
    print("=" * 70)
    print("Migration Modèles de Données Qlik → Power BI")
    print("=" * 70)
    
    # Configuration
    qlik_exports_dir = Path('qlik_exports')
    models_output_dir = Path('powerbi_models')
    models_output_dir.mkdir(parents=True, exist_ok=True)
    
    # Vérifier les fichiers
    qlik_files = list(qlik_exports_dir.glob('*.json'))
    if not qlik_files:
        print(f"\n⚠ Aucun fichier JSON trouvé dans {qlik_exports_dir}")
        print("Placez vos exports Qlik JSON dans ce dossier")
        return 1
    
    print(f"\nTrouvé {len(qlik_files)} application(s) Qlik")
    
    # Créer le migrateur
    migrator = QlikModelMigrator()
    
    # Migrer chaque application
    results = []
    for qlik_file in qlik_files:
        print(f"\n📊 Migration du modèle: {qlik_file.name}")
        
        try:
            # Charger l'application Qlik
            with open(qlik_file, 'r', encoding='utf-8') as f:
                qlik_app_data = json.load(f)
            
            # Migrer le modèle
            output_file = models_output_dir / f'{qlik_file.stem}_model.bim'
            result = migrator.migrate_model(qlik_app_data, output_file)
            
            results.append(result)
            
            if result['status'] == 'success':
                print(f"   ✓ Modèle migré → {output_file.name}")
                print(f"   📊 Tables: {result['tables_count']}")
                print(f"   🔗 Relations: {result['relationships_count']}")
                print(f"   📁 Hiérarchies: {result['hierarchies_count']}")
                
                if result.get('synthetic_keys'):
                    print(f"   ⚠ Clés synthétiques: {len(result['synthetic_keys'])}")
                    for key in result['synthetic_keys'][:3]:
                        print(f"      - {key}")
                
                # Générer documentation
                doc = migrator.generate_documentation(result)
                doc_file = models_output_dir / f'{qlik_file.stem}_model_doc.md'
                with open(doc_file, 'w', encoding='utf-8') as f:
                    f.write(doc)
                print(f"   📝 Documentation → {doc_file.name}")
                
            else:
                print(f"   ✗ Erreur: {result['error']}")
                
        except Exception as e:
            print(f"   ✗ Erreur: {str(e)}")
            results.append({'status': 'error', 'error': str(e)})
    
    # Résumé
    print("\n" + "=" * 70)
    successful = sum(1 for r in results if r['status'] == 'success')
    failed = sum(1 for r in results if r['status'] == 'error')
    
    print(f"Résumé:")
    print(f"  ✓ Réussis: {successful}")
    print(f"  ✗ Échoués: {failed}")
    print(f"\nModèles Power BI générés dans: {models_output_dir}/")
    print("=" * 70)
    
    # Instructions suivantes
    print("\n📝 Prochaines étapes:")
    print("1. Ouvrir Power BI Desktop")
    print("2. Aller dans Fichier → Paramètres et options → Options")
    print("3. Prévisualiser les fonctionnalités → 'Model view'")
    print("4. Utiliser l'onglet 'Modélisation' pour créer les relations")
    print("5. OU importer le fichier .bim via des outils externes (Tabular Editor)")
    print("6. Vérifier les relations suggérées")
    print("7. Ajuster les cardinalités si nécessaire")
    print("8. Tester les filtres croisés")
    
    print("\n⚠️ Important:")
    print("- Réviser toutes les relations générées automatiquement")
    print("- Vérifier les cardinalités (1:n, n:n)")
    print("- Configurer la direction des filtres croisés")
    print("- Supprimer les clés synthétiques si présentes")
    print("- Créer les relations manquantes")
    
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
