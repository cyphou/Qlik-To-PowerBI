"""
Exemples d'extraction et migration de fichiers QVF
Teste le module qvf_extractor.py
"""

import sys
from pathlib import Path
import zipfile
import json

# Ajouter src au path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / 'src'))

from qlik_export.qvf_extractor import QVFExtractor, extract_qvf


def create_sample_qvf():
    """
    Créer un fichier QVF d'exemple pour les tests.
    
    Un fichier QVF réel est une archive ZIP contenant:
    - Métadonnées XML
    - Scripts de chargement
    - Objets JSON (dimensions, mesures, feuilles)
    """
    qvf_path = Path("test_files/sample_sales.qvf")
    qvf_path.parent.mkdir(exist_ok=True)
    
    print("="*70)
    print("Création d'un fichier QVF d'exemple")
    print("="*70)
    
    with zipfile.ZipFile(qvf_path, 'w') as qvf:
        # 1. Métadonnées (app.xml simplifié)
        app_xml = """<?xml version="1.0" encoding="UTF-8"?>
<QlikApp>
    <Title>Application Ventes Exemple</Title>
    <Description>Application de démonstration pour la migration</Description>
    <Author>Migration Tool</Author>
    <CreateDate>2026-02-12</CreateDate>
    <ModifyDate>2026-02-12</ModifyDate>
</QlikApp>"""
        qvf.writestr('app.xml', app_xml)
        
        # 2. Script de chargement
        load_script = """
// Script de chargement des ventes

SET ThousandSep=' ';
SET DecimalSep=',';
SET MoneyFormat='# ##0,00 €';
SET DateFormat='DD/MM/YYYY';

// Chargement des ventes
Sales:
LOAD
    SaleID,
    CustomerID,
    ProductID,
    OrderDate,
    Amount,
    Quantity
FROM [Sales.csv]
(txt, codepage is 1252, embedded labels, delimiter is ',');

// Chargement des clients
Customers:
LOAD
    CustomerID,
    CustomerName,
    Country,
    City,
    Region
FROM [Customers.xlsx]
(ooxml, embedded labels, table is Customers);

// Chargement des produits
Products:
LOAD
    ProductID,
    ProductName,
    CategoryID,
    UnitPrice
FROM [Products.qvd]
(qvd);

// Catégories
Categories:
LOAD
    CategoryID,
    CategoryName,
    Description
INLINE [
    CategoryID, CategoryName, Description
    1, Electronics, Electronic devices
    2, Clothing, Apparel and accessories
    3, Food, Food products
];
"""
        qvf.writestr('loadscript.txt', load_script)
        
        # 3. Dimensions
        dimension1 = {
            "qInfo": {"qId": "dim-001", "qType": "dimension"},
            "qMetaDef": {"title": "Client"},
            "qDim": {
                "qFieldDefs": ["CustomerName"],
                "qFieldLabels": ["Nom du Client"]
            }
        }
        qvf.writestr('dimension_customer.json', json.dumps(dimension1, indent=2))
        
        dimension2 = {
            "qInfo": {"qId": "dim-002", "qType": "dimension"},
            "qMetaDef": {"title": "Produit"},
            "qDim": {
                "qFieldDefs": ["ProductName"],
                "qFieldLabels": ["Nom du Produit"]
            }
        }
        qvf.writestr('dimension_product.json', json.dumps(dimension2, indent=2))
        
        # 4. Mesures
        measure1 = {
            "qInfo": {"qId": "measure-001", "qType": "measure"},
            "qMetaDef": {"title": "Chiffre d'Affaires"},
            "qMeasure": {
                "qDef": "Sum(Amount)",
                "qLabel": "CA Total"
            }
        }
        qvf.writestr('measure_revenue.json', json.dumps(measure1, indent=2))
        
        measure2 = {
            "qInfo": {"qId": "measure-002", "qType": "measure"},
            "qMetaDef": {"title": "Quantité Vendue"},
            "qMeasure": {
                "qDef": "Sum(Quantity)",
                "qLabel": "Qté Totale"
            }
        }
        qvf.writestr('measure_quantity.json', json.dumps(measure2, indent=2))
        
        # 5. Feuille (sheet)
        sheet1 = {
            "qInfo": {"qId": "sheet-001", "qType": "sheet"},
            "qMetaDef": {
                "title": "Tableau de Bord Ventes",
                "description": "Vue d'ensemble des ventes"
            },
            "cells": [
                {"name": "KPI-001", "type": "kpi", "col": 0, "row": 0},
                {"name": "Chart-001", "type": "barchart", "col": 1, "row": 0},
                {"name": "Table-001", "type": "table", "col": 0, "row": 1}
            ]
        }
        qvf.writestr('sheet_dashboard.json', json.dumps(sheet1, indent=2))
        
        # 6. Variables
        variable1 = {
            "qName": "vCurrentYear",
            "qDefinition": "Year(Today())",
            "qComment": "Année en cours"
        }
        qvf.writestr('variable_year.json', json.dumps(variable1, indent=2))
    
    print(f"✓ Fichier QVF créé: {qvf_path}")
    print(f"✓ Taille: {qvf_path.stat().st_size / 1024:.1f} KB")
    
    return qvf_path


def example_extract_qvf():
    """Exemple 1: Extraction basique d'un fichier QVF."""
    print("\n" + "="*70)
    print("EXEMPLE 1: Extraction Basique d'un Fichier QVF")
    print("="*70)
    
    # Créer un fichier QVF d'exemple
    qvf_path = create_sample_qvf()
    
    # Extraire les données
    print("\nExtraction des données...")
    extractor = QVFExtractor(qvf_path)
    data = extractor.extract_all()
    
    # Afficher le résumé
    summary = extractor.get_summary()
    
    print(f"\n📊 Résumé de l'Extraction:")
    print(f"   • Application: {summary['app_name']}")
    print(f"   • Dimensions: {summary['dimensions_count']}")
    print(f"   • Mesures: {summary['measures_count']}")
    print(f"   • Feuilles: {summary['sheets_count']}")
    print(f"   • Tables: {summary['tables_count']}")
    print(f"   • Variables: {summary['variables_count']}")
    print(f"   • Script: {summary['script_length']} caractères")
    
    # Détails des dimensions
    if data.get('dimensions'):
        print(f"\n📐 Dimensions extraites:")
        for dim in data['dimensions']:
            print(f"   • {dim['name']}: {dim['field']}")
    
    # Détails des mesures
    if data.get('measures'):
        print(f"\n📏 Mesures extraites:")
        for measure in data['measures']:
            print(f"   • {measure['name']}: {measure['expression']}")
    
    return data


def example_export_to_json():
    """Exemple 2: Export des données en JSON."""
    print("\n" + "="*70)
    print("EXEMPLE 2: Export en JSON")
    print("="*70)
    
    qvf_path = Path("test_files/sample_sales.qvf")
    
    if not qvf_path.exists():
        qvf_path = create_sample_qvf()
    
    # Extraire et exporter
    extractor = QVFExtractor(qvf_path)
    extractor.extract_all()
    
    json_output = Path("qlik_exports/sample_sales_from_qvf.json")
    extractor.export_to_json(json_output)
    
    print(f"\n✓ Fichier JSON exporté: {json_output}")
    print(f"✓ Taille: {json_output.stat().st_size / 1024:.1f} KB")
    
    # Vérifier le contenu
    with open(json_output, 'r', encoding='utf-8') as f:
        exported_data = json.load(f)
    
    print(f"\n📄 Contenu du JSON:")
    print(f"   • Clés principales: {', '.join(exported_data.keys())}")
    print(f"   • Dimensions: {len(exported_data.get('dimensions', []))}")
    print(f"   • Mesures: {len(exported_data.get('measures', []))}")
    
    return json_output


def example_quick_extract():
    """Exemple 3: Extraction rapide avec fonction utilitaire."""
    print("\n" + "="*70)
    print("EXEMPLE 3: Extraction Rapide")
    print("="*70)
    
    qvf_path = Path("test_files/sample_sales.qvf")
    
    if not qvf_path.exists():
        qvf_path = create_sample_qvf()
    
    # Méthode rapide
    print("\nExtraction rapide...")
    data = extract_qvf(
        qvf_path,
        output_json_path=Path("qlik_exports/quick_export.json")
    )
    
    print(f"✓ Extraction terminée")
    print(f"✓ JSON exporté: qlik_exports/quick_export.json")
    
    return data


def example_inspect_qvf_structure():
    """Exemple 4: Inspecter la structure interne d'un QVF."""
    print("\n" + "="*70)
    print("EXEMPLE 4: Inspection de la Structure QVF")
    print("="*70)
    
    qvf_path = Path("test_files/sample_sales.qvf")
    
    if not qvf_path.exists():
        qvf_path = create_sample_qvf()
    
    print(f"\nInspection de: {qvf_path}")
    
    # Lister le contenu de l'archive
    with zipfile.ZipFile(qvf_path, 'r') as qvf:
        file_list = qvf.namelist()
        
        print(f"\n📦 Contenu de l'archive ({len(file_list)} fichiers):")
        
        # Grouper par type
        xml_files = [f for f in file_list if f.endswith('.xml')]
        json_files = [f for f in file_list if f.endswith('.json')]
        script_files = [f for f in file_list if 'script' in f.lower()]
        
        if xml_files:
            print(f"\n   📄 Fichiers XML ({len(xml_files)}):")
            for f in xml_files:
                print(f"      • {f}")
        
        if script_files:
            print(f"\n   📜 Scripts ({len(script_files)}):")
            for f in script_files:
                size = qvf.getinfo(f).file_size
                print(f"      • {f} ({size} bytes)")
        
        if json_files:
            print(f"\n   🔧 Objets JSON ({len(json_files)}):")
            for f in json_files:
                print(f"      • {f}")


def example_migration_workflow():
    """Exemple 5: Workflow complet avec les autres modules."""
    print("\n" + "="*70)
    print("EXEMPLE 5: Workflow Complet de Migration")
    print("="*70)
    
    qvf_path = Path("test_files/sample_sales.qvf")
    
    if not qvf_path.exists():
        qvf_path = create_sample_qvf()
    
    # Import des autres modules
    from qlik_export.qlik_script_converter import QlikScriptToPowerQueryConverter
    from qlik_export.qlik_model_converter import QlikModelMigrator
    
    # Étape 1: Extraction
    print("\n🔍 Étape 1: Extraction du QVF")
    extractor = QVFExtractor(qvf_path)
    qlik_data = extractor.extract_all()
    summary = extractor.get_summary()
    print(f"   ✓ {summary['app_name']} extrait")
    
    # Étape 2: Migration du script
    print("\n📜 Étape 2: Migration du Script")
    if qlik_data.get('loadScript'):
        script_converter = QlikScriptToPowerQueryConverter()
        pq_script = script_converter.convert_qlik_script_to_powerquery(qlik_data['loadScript'])
        
        script_output = Path("powerquery_scripts/from_qvf_sample.pq")
        script_output.parent.mkdir(exist_ok=True)
        
        with open(script_output, 'w', encoding='utf-8') as f:
            f.write(pq_script)
        
        print(f"   ✓ Script Power Query généré: {script_output}")
    
    # Étape 3: Migration du modèle
    print("\n🗂️  Étape 3: Migration du Modèle")
    model_migrator = QlikModelMigrator()
    
    # Préparer les données au format attendu
    if not qlik_data.get('tables') and qlik_data.get('dataModel', {}).get('tables'):
        qlik_data['tables'] = qlik_data['dataModel']['tables']
    
    model_output = Path("powerbi_models/from_qvf_sample.bim")
    model_result = model_migrator.migrate_model(qlik_data, model_output)
    
    print(f"   ✓ Modèle BIM généré: {model_output}")
    print(f"   ✓ Tables: {model_result['tables_count']}")
    print(f"   ✓ Relations: {model_result['relationships_count']}")
    
    # Étape 4: Migration des visualisations
    print("\n📊 Étape 4: Migration des Visualisations")
    print(f"   ✓ Dimensions: {len(qlik_data.get('dimensions', []))}")
    print(f"   ✓ Mesures: {len(qlik_data.get('measures', []))}")
    print(f"   ✓ Feuilles: {len(qlik_data.get('sheets', []))}")
    
    print("\n✅ Migration complète terminée!")
    
    return {
        'extraction': summary,
        'script': script_output if qlik_data.get('loadScript') else None,
        'model': model_output,
        'model_stats': model_result
    }


def main():
    """Exécute tous les exemples."""
    print("\n" + "🎯 EXEMPLES D'EXTRACTION DE FICHIERS QVF".center(70))
    print("="*70)
    print("Module: qvf_extractor.py")
    print("Fonctionnalités: Extraction QVF, Export JSON, Migration Complète")
    print("="*70)
    
    try:
        # Créer les dossiers nécessaires
        Path("test_files").mkdir(exist_ok=True)
        Path("qlik_exports").mkdir(exist_ok=True)
        
        # Exemple 1: Extraction basique
        data1 = example_extract_qvf()
        
        # Exemple 2: Export JSON
        json_path = example_export_to_json()
        
        # Exemple 3: Extraction rapide
        data3 = example_quick_extract()
        
        # Exemple 4: Inspection structure
        example_inspect_qvf_structure()
        
        # Exemple 5: Workflow complet
        result5 = example_migration_workflow()
        
        # Résumé final
        print("\n" + "="*70)
        print("✅ TOUS LES EXEMPLES RÉUSSIS")
        print("="*70)
        
        print(f"\n📁 Fichiers générés:")
        print(f"   • test_files/sample_sales.qvf")
        print(f"   • qlik_exports/sample_sales_from_qvf.json")
        print(f"   • qlik_exports/quick_export.json")
        print(f"   • powerquery_scripts/from_qvf_sample.pq")
        print(f"   • powerbi_models/from_qvf_sample.bim")
        
        print(f"\n💡 Utilisation:")
        print(f"   # Migrer votre propre fichier QVF:")
        print(f"   python migrate_qvf.py votre_fichier.qvf")
        
        print(f"\n🎉 Extraction QVF complètement testée !")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
