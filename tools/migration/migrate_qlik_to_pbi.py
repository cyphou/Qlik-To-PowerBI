#!/usr/bin/env python
"""
Script de migration Qlik Sense vers Power BI.

Ce script automatise la migration des applications Qlik vers des rapports Power BI
et les déploie dans un workspace Fabric.

Usage:
    python migrate_qlik_to_pbi.py

Configuration:
    - Placer les exports Qlik JSON dans le dossier 'qlik_exports/'
    - Configurer .env avec vos credentials Fabric
    - Les rapports migrés seront sauvegardés dans 'migrated_artifacts/'
"""

import sys
import logging
from pathlib import Path
from typing import List, Dict, Any

# Ajouter le chemin source
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / 'src'))

from fabric_api.qlik_migrator import QlikToPowerBIMigrator
from fabric_api import FabricDeployer
from fabric_api.utils import DeploymentReport
from fabric_api.config.settings import settings

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def validate_environment():
    """Valider que l'environnement est correctement configuré."""
    logger.info("Validation de l'environnement...")
    
    # Vérifier les dossiers
    qlik_dir = Path('qlik_exports')
    if not qlik_dir.exists():
        logger.warning(f"Création du dossier: {qlik_dir}")
        qlik_dir.mkdir(parents=True)
    
    # Vérifier les fichiers Qlik
    qlik_files = list(qlik_dir.glob('*.json'))
    if not qlik_files:
        logger.warning(f"Aucun fichier Qlik trouvé dans {qlik_dir}")
        logger.info("Placez vos exports Qlik JSON dans ce dossier")
        return False
    
    logger.info(f"Trouvé {len(qlik_files)} fichier(s) Qlik à migrer")
    
    # Vérifier la configuration Fabric
    try:
        workspace_id = settings.fabric_workspace_id
        if not workspace_id or workspace_id == 'your-workspace-id':
            logger.error("FABRIC_WORKSPACE_ID non configuré dans .env")
            return False
        logger.info(f"Workspace Fabric: {workspace_id}")
    except Exception as e:
        logger.error(f"Erreur de configuration: {e}")
        return False
    
    return True


def migrate_qlik_apps() -> List[Dict[str, Any]]:
    """
    Migrer les applications Qlik vers Power BI.
    
    Returns:
        Liste des résultats de migration
    """
    logger.info("=== Début de la migration Qlik → Power BI ===")
    
    qlik_exports_dir = Path('qlik_exports')
    migrated_dir = Path('migrated_artifacts')
    
    # Créer le migrateur
    migrator = QlikToPowerBIMigrator(output_dir=migrated_dir)
    
    # Migrer en batch
    results = migrator.batch_migrate(qlik_exports_dir)
    
    # Statistiques
    successful = [r for r in results if r['status'] == 'success']
    failed = [r for r in results if r['status'] == 'failed']
    
    logger.info(f"\nRésultats de migration:")
    logger.info(f"  ✓ Réussies: {len(successful)}")
    logger.info(f"  ✗ Échouées: {len(failed)}")
    
    if failed:
        logger.warning("\nÉchecs de migration:")
        for result in failed:
            logger.warning(f"  - {Path(result['source']).name}: {result['error']}")
    
    return results


def deploy_to_fabric(migration_results: List[Dict[str, Any]]) -> DeploymentReport:
    """
    Déployer les rapports migrés vers Fabric.
    
    Args:
        migration_results: Résultats de la migration
        
    Returns:
        Rapport de déploiement
    """
    logger.info("\n=== Déploiement vers Microsoft Fabric ===")
    
    workspace_id = settings.fabric_workspace_id
    migrated_dir = Path('migrated_artifacts')
    
    # Créer le déployeur et le rapport
    deployer = FabricDeployer()
    report = DeploymentReport(workspace_id)
    
    # Déployer chaque rapport migré avec succès
    successful_migrations = [
        r for r in migration_results if r['status'] == 'success'
    ]
    
    for migration in successful_migrations:
        source_file = Path(migration['source'])
        artifact_name = source_file.stem
        artifact_path = migrated_dir / f"{artifact_name}.json"
        
        try:
            logger.info(f"Déploiement de: {artifact_name}")
            
            result = deployer.deploy_from_file(
                workspace_id=workspace_id,
                artifact_path=artifact_path,
                artifact_type='Report',
                overwrite=True
            )
            
            logger.info(f"  ✓ Déployé avec l'ID: {result.get('id', 'N/A')}")
            
            report.add_result(
                artifact_name=artifact_name,
                artifact_type='Report',
                status='success',
                item_id=result.get('id')
            )
            
        except Exception as e:
            logger.error(f"  ✗ Échec du déploiement: {str(e)}")
            
            report.add_result(
                artifact_name=artifact_name,
                artifact_type='Report',
                status='failed',
                error=str(e)
            )
    
    return report


def main():
    """Point d'entrée principal du script."""
    try:
        logger.info("=" * 60)
        logger.info("Migration Qlik Sense → Power BI (Microsoft Fabric)")
        logger.info("=" * 60)
        
        # Étape 1: Validation
        if not validate_environment():
            logger.error("Validation de l'environnement échouée")
            return 1
        
        # Étape 2: Migration
        migration_results = migrate_qlik_apps()
        
        if not any(r['status'] == 'success' for r in migration_results):
            logger.error("Aucune migration réussie, arrêt du déploiement")
            return 1
        
        # Étape 3: Déploiement
        deployment_report = deploy_to_fabric(migration_results)
        
        # Étape 4: Rapport final
        logger.info("\n" + "=" * 60)
        deployment_report.print_summary()
        
        # Sauvegarder le rapport
        report_path = Path('migration_deployment_report.json')
        deployment_report.save(report_path)
        logger.info(f"\nRapport détaillé sauvegardé: {report_path}")
        
        logger.info("\n=== Migration et déploiement terminés ===")
        
        # Code de sortie basé sur les échecs
        if any(r['status'] == 'failed' for r in deployment_report.results):
            logger.warning("Certains déploiements ont échoué")
            return 1
        
        return 0
        
    except Exception as e:
        logger.error(f"Erreur fatale: {str(e)}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
