#!/usr/bin/env python
"""
Script de migration des scripts Qlik vers Power Query M.

Ce script convertit les scripts de chargement Qlik (.qvs) en scripts Power Query M (.pq).

Usage:
    python migrate_qlik_scripts.py

Configuration:
    - Placer les scripts Qlik dans le dossier 'qlik_scripts/'
    - Les scripts Power Query seront générés dans 'powerquery_scripts/'
"""

import sys
import logging
from pathlib import Path

# Ajouter le chemin source
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / 'src'))

from fabric_api.qlik_script_converter import QlikScriptMigrator, QlikScriptToPowerQueryConverter

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Migrer les scripts Qlik vers Power Query M."""
    
    print("=" * 70)
    print("Migration Scripts Qlik → Power Query M")
    print("=" * 70)
    
    # Configuration
    qlik_scripts_dir = Path('qlik_scripts')
    output_dir = Path('powerquery_scripts')
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Vérifier les fichiers
    qlik_files = list(qlik_scripts_dir.glob('*.qvs'))
    if not qlik_files:
        print(f"\n⚠ Aucun fichier .qvs trouvé dans {qlik_scripts_dir}")
        print("Placez vos scripts Qlik (.qvs) dans ce dossier")
        return 1
    
    print(f"\nTrouvé {len(qlik_files)} script(s) Qlik à migrer")
    
    # Créer le migrateur
    migrator = QlikScriptMigrator()
    
    # Migrer chaque script
    results = []
    for qlik_file in qlik_files:
        print(f"\n📄 Migration de: {qlik_file.name}")
        
        output_file = output_dir / f'{qlik_file.stem}.pq'
        
        result = migrator.migrate_script_file(
            str(qlik_file),
            str(output_file)
        )
        
        results.append(result)
        
        if result['status'] == 'success':
            print(f"   ✓ Converti → {output_file.name}")
            
            # Générer rapport de conversion
            with open(qlik_file, 'r', encoding='utf-8') as f:
                qlik_script = f.read()
            
            report = migrator.generate_conversion_report(
                qlik_script,
                result['pq_script']
            )
            
            print(f"   📊 Taux de conversion: {report['conversion_rate']:.1f}%")
            
            if report['unconverted_functions']:
                print(f"   ⚠ Fonctions nécessitant révision manuelle:")
                for func in report['unconverted_functions'][:5]:  # Max 5
                    print(f"      - {func}")
        else:
            print(f"   ✗ Erreur: {result['error']}")
    
    # Résumé
    print("\n" + "=" * 70)
    successful = sum(1 for r in results if r['status'] == 'success')
    failed = sum(1 for r in results if r['status'] == 'error')
    
    print(f"Résumé:")
    print(f"  ✓ Réussis: {successful}")
    print(f"  ✗ Échoués: {failed}")
    print(f"\nScripts Power Query M générés dans: {output_dir}/")
    print("=" * 70)
    
    # Instructions suivantes
    print("\n📝 Prochaines étapes:")
    print("1. Ouvrir Power BI Desktop")
    print("2. Aller dans Accueil → Transformer les données")
    print("3. Créer une nouvelle requête vide")
    print("4. Ouvrir l'Éditeur avancé")
    print("5. Copier-coller le contenu du fichier .pq généré")
    print("6. Revoir et ajuster les connexions aux sources de données")
    print("7. Tester et valider les transformations")
    
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
