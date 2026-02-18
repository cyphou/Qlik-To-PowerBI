"""
Exemples d'utilisation pour la migration Qlik → Power BI.

Ces exemples montrent différentes façons d'utiliser le module de migration.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / 'src'))

from fabric_api import QlikToPowerBIMigrator, FabricDeployer
from fabric_api.qlik_migrator import QlikMetadataExtractor, QlikToPowerBIConverter


def exemple_1_migration_simple():
    """
    Exemple 1: Migration simple d'une application Qlik.
    """
    print("\n=== Exemple 1: Migration Simple ===")
    
    # Initialiser le migrateur
    migrator = QlikToPowerBIMigrator(output_dir=Path('migrated_artifacts'))
    
    # Migrer une application Qlik
    pbi_report = migrator.migrate_qlik_app(
        qlik_app_path=Path('qlik_exports/example_qlik_app.json'),
        report_name='Tableau de Bord Ventes Migré'
    )
    
    print(f"✓ Migration réussie: {pbi_report['displayName']}")
    print(f"  Fichier: migrated_artifacts/Tableau de Bord Ventes Migré.json")


def exemple_2_migration_et_deploiement():
    """
    Exemple 2: Migrer et déployer directement vers Fabric.
    """
    print("\n=== Exemple 2: Migration + Déploiement ===")
    
    # Étape 1: Migration
    migrator = QlikToPowerBIMigrator()
    pbi_report = migrator.migrate_qlik_app(
        qlik_app_path=Path('qlik_exports/example_qlik_app.json'),
        report_name='Sales Dashboard'
    )
    
    print(f"✓ Migré: {pbi_report['displayName']}")
    
    # Étape 2: Déploiement
    deployer = FabricDeployer()
    
    # IMPORTANT: Remplacer 'your-workspace-id' par votre vrai workspace ID
    # result = deployer.deploy_from_file(
    #     workspace_id='your-workspace-id',
    #     artifact_path=Path('migrated_artifacts/Sales Dashboard.json'),
    #     artifact_type='Report',
    #     overwrite=True
    # )
    # print(f"✓ Déployé avec l'ID: {result['id']}")
    
    print("  Note: Décommenter le code ci-dessus et configurer workspace_id")


def exemple_3_migration_batch():
    """
    Exemple 3: Migration en batch de plusieurs applications.
    """
    print("\n=== Exemple 3: Migration Batch ===")
    
    migrator = QlikToPowerBIMigrator()
    
    # Migrer toutes les apps du dossier
    results = migrator.batch_migrate(
        qlik_apps_dir=Path('qlik_exports')
    )
    
    print(f"\nRésultats:")
    for result in results:
        status = '✓' if result['status'] == 'success' else '✗'
        source = Path(result['source']).name
        
        if result['status'] == 'success':
            print(f"  {status} {source}")
        else:
            print(f"  {status} {source}: {result['error']}")


def exemple_4_extraction_metadata():
    """
    Exemple 4: Extraire et inspecter les métadonnées Qlik.
    """
    print("\n=== Exemple 4: Extraction Métadonnées ===")
    
    # Charger l'app Qlik
    extractor = QlikMetadataExtractor(
        qlik_app_path=Path('qlik_exports/example_qlik_app.json')
    )
    app_data = extractor.load_qlik_app()
    
    print(f"Application: {app_data.get('qTitle', 'N/A')}")
    
    # Extraire dimensions
    dimensions = extractor.extract_dimensions()
    print(f"\nDimensions ({len(dimensions)}):")
    for dim in dimensions:
        print(f"  - {dim.label}: {dim.field}")
    
    # Extraire mesures
    measures = extractor.extract_measures()
    print(f"\nMesures ({len(measures)}):")
    for measure in measures:
        print(f"  - {measure.label}: {measure.expression}")


def exemple_5_conversion_expressions():
    """
    Exemple 5: Convertir des expressions Qlik en DAX.
    """
    print("\n=== Exemple 5: Conversion Expressions ===")
    
    converter = QlikToPowerBIConverter()
    
    # Exemples d'expressions Qlik
    qlik_expressions = [
        "Sum(Sales)",
        "Avg(Price)",
        "Count(OrderID)",
        "Sum(Sales) / Sum(Quantity)",
        "If(Sum(Profit) > 0, 'Profitable', 'Loss')",
        "Year(OrderDate)",
    ]
    
    print("Conversions Qlik → DAX:")
    for qlik_expr in qlik_expressions:
        dax_expr = converter.convert_qlik_expression_to_dax(qlik_expr)
        print(f"  {qlik_expr:40} → {dax_expr}")


def exemple_6_workflow_complet():
    """
    Exemple 6: Workflow complet bout en bout.
    """
    print("\n=== Exemple 6: Workflow Complet ===")
    
    from fabric_api.utils import DeploymentReport
    
    # Configuration
    qlik_dir = Path('qlik_exports')
    workspace_id = 'your-workspace-id'  # À configurer
    
    # Étape 1: Migration
    print("\n1. Migration des applications Qlik...")
    migrator = QlikToPowerBIMigrator()
    migration_results = migrator.batch_migrate(qlik_dir)
    
    successful_migrations = [
        r for r in migration_results if r['status'] == 'success'
    ]
    print(f"   Migrations réussies: {len(successful_migrations)}")
    
    # Étape 2: Déploiement (simulé)
    print("\n2. Déploiement vers Fabric...")
    report = DeploymentReport(workspace_id)
    
    for migration in successful_migrations:
        artifact_name = Path(migration['source']).stem
        # Simulation du déploiement
        report.add_result(
            artifact_name=artifact_name,
            artifact_type='Report',
            status='success',  # ou 'failed' en cas d'échec
            item_id=f'sim-{artifact_name}-id'
        )
    
    # Étape 3: Rapport
    print("\n3. Génération du rapport...")
    report.print_summary()
    report.save(Path('workflow_report.json'))
    print("   Rapport sauvegardé: workflow_report.json")


def exemple_7_validation_pre_migration():
    """
    Exemple 7: Valider les fichiers Qlik avant migration.
    """
    print("\n=== Exemple 7: Validation Pré-Migration ===")
    
    import json
    
    qlik_dir = Path('qlik_exports')
    
    print("Validation des fichiers Qlik:")
    for qlik_file in qlik_dir.glob('*.json'):
        try:
            with open(qlik_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Vérifications basiques
            has_title = 'qTitle' in data
            has_dimensions = 'qDimensionList' in data.get('properties', {})
            has_measures = 'qMeasureList' in data.get('properties', {})
            has_sheets = 'sheets' in data
            
            checks = [has_title, has_dimensions, has_measures, has_sheets]
            valid = all(checks)
            
            status = '✓' if valid else '⚠'
            print(f"  {status} {qlik_file.name}")
            
            if not valid:
                if not has_title:
                    print(f"      - Manque: qTitle")
                if not has_dimensions:
                    print(f"      - Manque: dimensions")
                if not has_measures:
                    print(f"      - Manque: mesures")
                if not has_sheets:
                    print(f"      - Manque: sheets")
                    
        except json.JSONDecodeError:
            print(f"  ✗ {qlik_file.name}: JSON invalide")
        except Exception as e:
            print(f"  ✗ {qlik_file.name}: {str(e)}")


if __name__ == '__main__':
    print("=" * 70)
    print("Exemples de Migration Qlik → Power BI")
    print("=" * 70)
    
    # Exécuter les exemples
    # Décommenter ceux que vous voulez exécuter
    
    exemple_1_migration_simple()
    # exemple_2_migration_et_deploiement()
    exemple_3_migration_batch()
    exemple_4_extraction_metadata()
    exemple_5_conversion_expressions()
    # exemple_6_workflow_complet()
    exemple_7_validation_pre_migration()
    
    print("\n" + "=" * 70)
    print("Pour plus d'informations, voir: QLIK_MIGRATION_GUIDE.md")
    print("=" * 70)
