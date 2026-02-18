"""
Migration complète d'un fichier QVF Qlik vers Power BI
Extrait tout depuis le .qvf et migre en 3 étapes
"""

import sys
import json
from pathlib import Path
import logging

# Ajouter src au path
_project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_project_root / 'src'))

from fabric_api.qvf_extractor import QVFExtractor
from fabric_api.qlik_migrator import QlikToPowerBIMigrator
from fabric_api.qlik_script_converter import QlikScriptToPowerQueryConverter
from fabric_api.qlik_model_converter import QlikModelMigrator
from fabric_api.tmdl_generator import TMDLGenerator, create_pbi_project_from_migration

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def migrate_qvf_complete(
    qvf_path: Path,
    output_base_dir: Path = Path("migrated_from_qvf"),
    create_pbi_project: bool = False
) -> dict:
    """
    Migration complète d'un fichier QVF en 3 étapes.
    
    Args:
        qvf_path: Chemin vers le fichier .qvf
        output_base_dir: Répertoire de base pour les fichiers générés
        create_pbi_project: Si True, génère aussi un projet PBI (.pbip / TMDL)
        
    Returns:
        Résultats de la migration
    """
    qvf_path = Path(qvf_path)
    output_base_dir = Path(output_base_dir)
    
    logger.info("="*70)
    logger.info(f"MIGRATION COMPLÈTE: {qvf_path.name}")
    logger.info("="*70)
    
    # Créer les dossiers de sortie
    output_base_dir.mkdir(exist_ok=True)
    scripts_dir = output_base_dir / "powerquery_scripts"
    models_dir = output_base_dir / "powerbi_models"
    reports_dir = output_base_dir / "powerbi_reports"
    
    for dir_path in [scripts_dir, models_dir, reports_dir]:
        dir_path.mkdir(exist_ok=True)
    
    results = {
        'qvf_file': str(qvf_path),
        'status': 'success',
        'steps': {}
    }
    
    try:
        # ========================================
        # ÉTAPE 0: EXTRACTION DU FICHIER QVF
        # ========================================
        logger.info("\n" + "="*70)
        logger.info("ÉTAPE 0: Extraction du fichier QVF")
        logger.info("="*70)
        
        extractor = QVFExtractor(qvf_path)
        qlik_data = extractor.extract_all()
        summary = extractor.get_summary()
        
        logger.info(f"✓ Application: {summary['app_name']}")
        logger.info(f"✓ Dimensions: {summary['dimensions_count']}")
        logger.info(f"✓ Mesures: {summary['measures_count']}")
        logger.info(f"✓ Feuilles: {summary['sheets_count']}")
        logger.info(f"✓ Tables: {summary['tables_count']}")
        logger.info(f"✓ Script: {summary['script_length']} caractères")
        
        # Sauvegarder en JSON intermédiaire (optionnel, pour debug)
        json_path = output_base_dir / f"{qvf_path.stem}_extracted.json"
        extractor.export_to_json(json_path)
        logger.info(f"✓ Export JSON: {json_path}")
        
        results['steps']['extraction'] = {
            'status': 'success',
            'summary': summary,
            'json_file': str(json_path)
        }
        
        # ========================================
        # ÉTAPE 1: MIGRATION DU SCRIPT DE CHARGEMENT
        # ========================================
        logger.info("\n" + "="*70)
        logger.info("ÉTAPE 1: Migration du Script de Chargement")
        logger.info("="*70)
        
        if qlik_data.get('loadScript'):
            converter = QlikScriptToPowerQueryConverter()
            pq_script = converter.convert_qlik_script_to_powerquery(qlik_data['loadScript'])
            
            script_output = scripts_dir / f"{qvf_path.stem}.pq"
            with open(script_output, 'w', encoding='utf-8') as f:
                f.write(pq_script)
            
            logger.info(f"✓ Script Power Query généré: {script_output}")
            
            results['steps']['script_migration'] = {
                'status': 'success',
                'output_file': str(script_output),
                'original_length': len(qlik_data['loadScript']),
                'converted_length': len(pq_script)
            }
        else:
            logger.warning("⚠️  Aucun script de chargement trouvé")
            results['steps']['script_migration'] = {
                'status': 'skipped',
                'reason': 'No load script found'
            }
        
        # ========================================
        # ÉTAPE 2: MIGRATION DU MODÈLE DE DONNÉES
        # ========================================
        logger.info("\n" + "="*70)
        logger.info("ÉTAPE 2: Migration du Modèle de Données")
        logger.info("="*70)
        
        model_migrator = QlikModelMigrator()
        model_output = models_dir / f"{qvf_path.stem}_model.bim"
        
        model_result = model_migrator.migrate_model(qlik_data, model_output)
        
        logger.info(f"✓ Modèle BIM généré: {model_output}")
        logger.info(f"✓ Tables: {model_result['tables_count']}")
        logger.info(f"✓ Relations: {model_result['relationships_count']}")
        logger.info(f"✓ Hiérarchies: {model_result['hierarchies_count']}")
        
        # Générer documentation du modèle
        doc_content = model_migrator.generate_documentation(model_result)
        doc_output = models_dir / f"{qvf_path.stem}_model.md"
        with open(doc_output, 'w', encoding='utf-8') as f:
            f.write(doc_content)
        logger.info(f"✓ Documentation: {doc_output}")
        
        results['steps']['model_migration'] = {
            'status': 'success',
            'output_file': str(model_output),
            'documentation': str(doc_output),
            'tables_count': model_result['tables_count'],
            'relationships_count': model_result['relationships_count'],
            'hierarchies_count': model_result['hierarchies_count']
        }
        
        # ========================================
        # ÉTAPE 3: MIGRATION DE L'APPLICATION (VISUALISATIONS)
        # ========================================
        logger.info("\n" + "="*70)
        logger.info("ÉTAPE 3: Migration de l'Application (Visualisations)")
        logger.info("="*70)
        
        app_migrator = QlikToPowerBIMigrator()
        
        # Sauvegarder temporairement les données extraites
        temp_json = output_base_dir / "temp_app.json"
        extractor.export_to_json(temp_json)
        
        # Migrer l'application
        app_name = summary['app_name'] or qvf_path.stem
        app_migrator.migrate_qlik_app(
            temp_json,
            app_name
        )
        
        # Déplacer le fichier vers le bon dossier si nécessaire
        default_output = Path("migrated_artifacts") / f"{app_name}.json"
        report_output = reports_dir / f"{app_name}.json"
        
        if default_output.exists() and default_output != report_output:
            import shutil
            shutil.move(str(default_output), str(report_output))
        
        # Nettoyer le fichier temporaire
        if temp_json.exists():
            temp_json.unlink()
        
        logger.info(f"✓ Rapport Power BI généré: {report_output}")
        
        results['steps']['app_migration'] = {
            'status': 'success',
            'output_file': str(report_output),
            'app_name': app_name
        }
        
        # ========================================
        # ÉTAPE 4 (OPTIONNELLE): GÉNÉRATION PROJET PBI (TMDL)
        # ========================================
        if create_pbi_project:
            logger.info("\n" + "="*70)
            logger.info("ÉTAPE 4: Génération du projet PBI (.pbip / TMDL)")
            logger.info("="*70)
            
            try:
                project_output = output_base_dir / app_name
                
                # Load the migrated report JSON for visualizations
                report_data = {}
                if report_output.exists():
                    with open(report_output, 'r', encoding='utf-8') as f:
                        report_data = json.load(f)
                
                # Extract visuals from the migrated report (pages → visuals)
                migrated_visuals = []
                pages = report_data.get('definition', {}).get('pages', [])
                for page in pages:
                    for v in page.get('visuals', []):
                        migrated_visuals.append({
                            'type': v.get('visualType', 'table'),
                            'name': v.get('name', ''),
                            'title': v.get('title', ''),
                        })
                
                # Fall back to original extracted data if no migrated visuals
                visualizations = migrated_visuals or qlik_data.get('visualizations', [])
                
                # Créer le projet PBI depuis les fichiers de migration
                generator = TMDLGenerator()
                
                pbip_path = generator.create_pbi_project(
                    output_dir=project_output,
                    report_name=app_name,
                    bim_model=model_result.get('model'),
                    power_query_script=pq_script if qlik_data.get('loadScript') else None,
                    visualizations=visualizations,
                    dimensions=qlik_data.get('dimensions', []),
                    measures=qlik_data.get('measures', [])
                )
                
                logger.info(f"✓ Projet PBI généré: {pbip_path}")
                logger.info(f"✓ Dossier: {project_output}")
                
                results['steps']['pbi_project_generation'] = {
                    'status': 'success',
                    'output_dir': str(project_output),
                    'pbip_file': str(pbip_path)
                }
                
            except Exception as e:
                logger.warning(f"⚠️ Impossible de générer le projet PBI: {e}")
                results['steps']['pbi_project_generation'] = {
                    'status': 'warning',
                    'error': str(e)
                }
        
        # ========================================
        # RÉSUMÉ FINAL
        # ========================================
        logger.info("\n" + "="*70)
        logger.info("✅ MIGRATION COMPLÈTE RÉUSSIE")
        logger.info("="*70)
        
        logger.info(f"\n📁 Fichiers générés dans: {output_base_dir}")
        logger.info(f"\n📄 Power Query Scripts:")
        logger.info(f"   {scripts_dir / f'{qvf_path.stem}.pq'}")
        
        logger.info(f"\n📊 Modèle Power BI:")
        logger.info(f"   {model_output}")
        logger.info(f"   {doc_output}")
        
        logger.info(f"\n📈 Rapport Power BI:")
        logger.info(f"   {report_output}")
        
        pbi_step = results['steps'].get('pbi_project_generation', {})
        if pbi_step.get('status') == 'success':
            logger.info(f"\n📦 Projet PBI (.pbip / TMDL):")
            logger.info(f"   {pbi_step['output_dir']}")
            logger.info(f"   → Ouvrir le fichier .pbip dans Power BI Desktop (Developer Mode)!")
        
        logger.info(f"\n🎯 Prochaines Étapes:")
        
        if pbi_step.get('status') == 'success':
            logger.info(f"   1. Ouvrir {app_name}.pbip dans Power BI Desktop (Developer Mode)")
            logger.info(f"   2. Vérifier les données et visualisations")
            logger.info(f"   3. Ajuster si nécessaire")
            logger.info(f"   4. Publier vers Power BI Service / Fabric")
            logger.info(f"   💡 Les fichiers TMDL sont compatibles Git / CI-CD")
        else:
            logger.info(f"   1. Ouvrir Power BI Desktop")
            logger.info(f"   2. Power Query: Importer {qvf_path.stem}.pq")
            logger.info(f"   3. Modèle: Ouvrir {qvf_path.stem}_model.bim avec Tabular Editor")
            logger.info(f"   4. Visualisations: Recréer depuis {app_name}.json")
        
        return results
        
    except Exception as e:
        logger.error(f"❌ Erreur lors de la migration: {e}")
        import traceback
        traceback.print_exc()
        
        results['status'] = 'error'
        results['error'] = str(e)
        return results


def main():
    """Point d'entrée principal."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Migrer un fichier QVF Qlik vers Power BI'
    )
    parser.add_argument(
        'qvf_file',
        type=Path,
        help='Chemin vers le fichier .qvf à migrer'
    )
    parser.add_argument(
        '--output-dir',
        type=Path,
        default=Path('migrated_from_qvf'),
        help='Répertoire de sortie (défaut: migrated_from_qvf)'
    )
    parser.add_argument(
        '--create-pbi-project',
        action='store_true',
        help='Générer aussi un projet PBI (.pbip / TMDL)'
    )
    
    args = parser.parse_args()
    
    # Vérifier que le fichier existe
    if not args.qvf_file.exists():
        logger.error(f"❌ Fichier introuvable: {args.qvf_file}")
        return 1
    
    # Exécuter la migration
    results = migrate_qvf_complete(
        args.qvf_file, 
        args.output_dir,
        create_pbi_project=args.create_pbi_project
    )
    
    # Code de sortie
    return 0 if results['status'] == 'success' else 1


if __name__ == "__main__":
    exit(main())
