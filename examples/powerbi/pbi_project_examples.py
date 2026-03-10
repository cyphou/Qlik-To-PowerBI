"""
Exemples de génération de projets Power BI (TMDL / .pbip)
Teste le module tmdl_generator.py
"""

import sys
from pathlib import Path
import logging
import json

# Ajouter src au path
_project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_project_root / 'src'))

from fabric_api.tmdl_generator import TMDLGenerator, create_pbi_project_from_migration
from qlik_export.qvf_extractor import QVFExtractor
from qlik_export.qlik_model_converter import QlikModelMigrator
from qlik_export.qlik_script_converter import QlikScriptToPowerQueryConverter

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def example_create_basic_pbi_project():
    """Exemple 1: Créer un projet PBI basique."""
    print("="*70)
    print("EXEMPLE 1: Création d'un Projet PBI (TMDL) Basique")
    print("="*70)

    generator = TMDLGenerator()

    # Modèle minimal
    simple_model = {
        "name": "SimpleModel",
        "compatibilityLevel": 1567,
        "model": {
            "culture": "en-US",
            "tables": [
                {
                    "name": "Sales",
                    "columns": [
                        {"name": "Amount", "dataType": "double"},
                        {"name": "Date", "dataType": "dateTime"}
                    ]
                }
            ],
            "relationships": []
        }
    }

    pbip_path = generator.create_pbi_project(
        output_dir=Path("test_files/simple_report"),
        report_name="Simple Report",
        bim_model=simple_model
    )

    print(f"\n✓ Projet PBI créé: {pbip_path}")
    print(f"\n💡 Ouvrez ce fichier .pbip dans Power BI Desktop (Developer Mode)!")

    return pbip_path


def example_create_pbi_project_from_qvf():
    """Exemple 2: Créer un projet PBI depuis un fichier QVF."""
    print("\n" + "="*70)
    print("EXEMPLE 2: Projet PBI depuis Fichier QVF")
    print("="*70)

    # Vérifier si le QVF d'exemple existe
    qvf_path = Path("test_files/sample_sales.qvf")

    if not qvf_path.exists():
        from qvf_examples import create_sample_qvf
        qvf_path = create_sample_qvf()

    # Extraire le QVF
    print("\n📦 Extraction du QVF...")
    extractor = QVFExtractor(qvf_path)
    qlik_data = extractor.extract_all()
    summary = extractor.get_summary()

    print(f"✓ {summary['app_name']} extrait")

    # Créer le modèle BIM
    print("\n🗂️  Création du modèle BIM...")
    model_migrator = QlikModelMigrator()
    model_output = Path("test_files/temp_model.bim")
    model_result = model_migrator.migrate_model(qlik_data, model_output)

    # Charger le BIM
    with open(model_output, 'r', encoding='utf-8') as f:
        bim_model = json.load(f)

    print(f"✓ Modèle créé: {model_result['tables_count']} tables")

    # Convertir le script
    print("\n📜 Conversion du script...")
    script_converter = QlikScriptToPowerQueryConverter()
    pq_script = ""

    if qlik_data.get('loadScript'):
        pq_script = script_converter.convert_qlik_script_to_powerquery(
            qlik_data['loadScript']
        )
        print(f"✓ Script converti: {len(pq_script)} caractères")

    # Générer le projet PBI
    print("\n🎨 Génération du projet PBI (TMDL)...")
    generator = TMDLGenerator()

    pbip_path = generator.create_pbi_project(
        output_dir=Path("test_files/from_qvf"),
        report_name=summary['app_name'],
        bim_model=bim_model,
        power_query_script=pq_script,
        visualizations=qlik_data.get('visualizations', []),
        dimensions=qlik_data.get('dimensions', []),
        measures=qlik_data.get('measures', [])
    )

    print(f"\n✓ Projet PBI créé depuis QVF: {pbip_path}")
    print(f"\n🎉 Ouvrez {pbip_path.name} dans Power BI Desktop (Developer Mode)!")

    # Nettoyer le fichier temporaire
    model_output.unlink()

    return pbip_path


def example_create_pbi_project_from_migration_folder():
    """Exemple 3: Créer un projet PBI depuis un dossier de migration."""
    print("\n" + "="*70)
    print("EXEMPLE 3: Projet PBI depuis Dossier de Migration")
    print("="*70)

    # Vérifier si le dossier powerbi_models existe
    migration_dir = Path(".")

    if not (migration_dir / "powerbi_models").exists():
        print("⚠️  Pas de dossier de migration trouvé")
        print("   Exécutez d'abord: python qvf_examples.py")
        return None

    print(f"\n📂 Dossier de migration: {migration_dir}")

    # Créer le projet PBI
    pbip_path = create_pbi_project_from_migration(
        migration_output_dir=migration_dir,
        project_output_dir=Path("test_files/from_migration"),
        report_name="Sales Dashboard"
    )

    print(f"\n✓ Projet PBI créé depuis migration: {pbip_path}")

    return pbip_path


def example_pbi_project_with_visualizations():
    """Exemple 4: Projet PBI avec visualisations."""
    print("\n" + "="*70)
    print("EXEMPLE 4: Projet PBI avec Visualisations")
    print("="*70)

    # Données de test
    dimensions = [
        {"name": "Customer", "field": "CustomerName"},
        {"name": "Product", "field": "ProductName"}
    ]

    measures = [
        {"name": "Revenue", "expression": "SUM(Sales[Amount])"},
        {"name": "Quantity", "expression": "SUM(Sales[Quantity])"}
    ]

    visualizations = [
        {"type": "barchart", "name": "Sales by Customer"},
        {"type": "linechart", "name": "Trend"},
        {"type": "kpi", "name": "Total Revenue"},
        {"type": "table", "name": "Detail Table"}
    ]

    # Modèle
    model = {
        "name": "VisualizationModel",
        "compatibilityLevel": 1567,
        "model": {
            "culture": "en-US",
            "tables": [
                {
                    "name": "Sales",
                    "columns": [
                        {"name": "CustomerName", "dataType": "string"},
                        {"name": "ProductName", "dataType": "string"},
                        {"name": "Amount", "dataType": "double"},
                        {"name": "Quantity", "dataType": "int64"}
                    ],
                    "measures": [
                        {"name": "Revenue", "expression": "SUM(Sales[Amount])", "formatString": "#,0.00"},
                        {"name": "Quantity", "expression": "SUM(Sales[Quantity])"}
                    ]
                }
            ]
        }
    }

    # Générer le projet PBI
    generator = TMDLGenerator()
    pbip_path = generator.create_pbi_project(
        output_dir=Path("test_files/with_visuals"),
        report_name="Dashboard with Visuals",
        bim_model=model,
        visualizations=visualizations,
        dimensions=dimensions,
        measures=measures
    )

    print(f"\n✓ Projet PBI avec visualisations créé: {pbip_path}")
    print(f"✓ Visuels: {len(visualizations)}")
    print(f"✓ Dimensions: {len(dimensions)}")
    print(f"✓ Mesures: {len(measures)}")

    return pbip_path


def inspect_pbi_project_structure():
    """Exemple 5: Inspecter la structure d'un projet PBI créé."""
    print("\n" + "="*70)
    print("EXEMPLE 5: Inspection de la Structure du Projet PBI")
    print("="*70)

    project_dir = Path("test_files/simple_report")

    if not project_dir.exists():
        print("⚠️  Projet introuvable, création...")
        example_create_basic_pbi_project()

    print(f"\n📦 Inspection de: {project_dir}")

    def print_tree(directory: Path, prefix: str = ""):
        entries = sorted(directory.iterdir(), key=lambda e: (not e.is_dir(), e.name))
        for i, entry in enumerate(entries):
            is_last = i == len(entries) - 1
            connector = "└── " if is_last else "├── "
            print(f"{prefix}{connector}{entry.name}")
            if entry.is_dir():
                extension = "    " if is_last else "│   "
                print_tree(entry, prefix + extension)

    print_tree(project_dir)

    # Afficher le contenu des fichiers TMDL
    tmdl_files = list(project_dir.rglob("*.tmdl"))
    for tmdl_file in tmdl_files:
        print(f"\n📊 {tmdl_file.relative_to(project_dir)}:")
        content = tmdl_file.read_text(encoding="utf-8")
        for line in content.split("\n")[:15]:
            print(f"   {line}")
        total_lines = len(content.split("\n"))
        if total_lines > 15:
            print(f"   ... ({total_lines - 15} lignes supplémentaires)")


def main():
    """Exécute tous les exemples de génération de projets PBI."""
    print("\n" + "🎯 EXEMPLES DE GÉNÉRATION DE PROJETS PBI (TMDL)".center(70))
    print("="*70)
    print("Module: tmdl_generator.py")
    print("Format: PBI Project (.pbip) + TMDL (Tabular Model Definition Language)")
    print("="*70)

    # Créer le dossier de test
    Path("test_files").mkdir(exist_ok=True)

    try:
        # Exemple 1: Projet basique
        pbip1 = example_create_basic_pbi_project()

        # Exemple 2: Projet depuis QVF
        pbip2 = example_create_pbi_project_from_qvf()

        # Exemple 3: Projet depuis dossier de migration
        pbip3 = example_create_pbi_project_from_migration_folder()

        # Exemple 4: Projet avec visualisations
        pbip4 = example_pbi_project_with_visualizations()

        # Exemple 5: Inspection
        inspect_pbi_project_structure()

        # Résumé
        print("\n" + "="*70)
        print("✅ TOUS LES EXEMPLES RÉUSSIS")
        print("="*70)

        print(f"\n📁 Projets PBI générés:")
        pbip_files = list(Path("test_files").rglob("*.pbip"))
        for pbip_file in pbip_files:
            print(f"   • {pbip_file.relative_to(Path('test_files'))}")

        print(f"\n💡 Utilisation:")
        print(f"   # Ouvrir dans Power BI Desktop (Developer Mode):")
        if pbip_files:
            print(f"   start {pbip_files[0]}")

        print(f"\n   # Migrer un QVF avec génération TMDL:")
        print(f"   python migrate_qvf.py votre_app.qvf --create-pbi-project")

        print(f"\n🎉 Génération de projets PBI (TMDL) complètement testée !")
        print(f"\n⚠️  Note: Ouvrez les fichiers .pbip dans Power BI Desktop")
        print(f"   avec le mode Développeur activé (Options > Preview features).")
        print(f"   Les fichiers TMDL sont compatibles Git / CI-CD.")

        return 0

    except Exception as e:
        print(f"\n❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
