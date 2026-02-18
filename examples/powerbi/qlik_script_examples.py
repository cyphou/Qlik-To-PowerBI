"""
Exemples d'utilisation de la migration de scripts Qlik.

Ces exemples montrent comment convertir des scripts Qlik en Power Query M.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / 'src'))

from fabric_api.qlik_script_converter import (
    QlikScriptMigrator,
    QlikScriptToPowerQueryConverter
)


def exemple_1_conversion_simple():
    """Exemple 1: Conversion d'une fonction Qlik simple."""
    print("\n=== Exemple 1: Conversion de Fonctions ===")
    
    converter = QlikScriptToPowerQueryConverter()
    
    # Exemples de conversions
    qlik_functions = [
        "Upper(CustomerName)",
        "Date(OrderDate, 'YYYY-MM-DD')",
        "Round(Price, 2)",
        "Year(SalesDate)",
        "If(Status = 'Active', 1, 0)",
        "Trim(ProductName)",
    ]
    
    print("\nConversions Qlik → Power Query M:")
    for qlik_func in qlik_functions:
        pq_func = converter.convert_qlik_function(qlik_func)
        print(f"  {qlik_func:35} → {pq_func}")


def exemple_2_migration_fichier():
    """Exemple 2: Migration d'un fichier script complet."""
    print("\n=== Exemple 2: Migration de Fichier ===")
    
    migrator = QlikScriptMigrator()
    
    # Migrer le script simple
    result = migrator.migrate_script_file(
        qlik_script_path='qlik_scripts/simple_load.qvs',
        output_path='powerquery_scripts/simple_load.pq'
    )
    
    if result['status'] == 'success':
        print(f"✓ Script migré: {result['output']}")
        print(f"\nPremiers 500 caractères du résultat:")
        print("-" * 60)
        print(result['pq_script'][:500])
        print("...")
    else:
        print(f"✗ Erreur: {result['error']}")


def exemple_3_rapport_conversion():
    """Exemple 3: Générer un rapport de conversion."""
    print("\n=== Exemple 3: Rapport de Conversion ===")
    
    qlik_script = """
    LOAD
        CustomerID,
        Upper(CustomerName) as Name,
        Lower(Email) as email,
        Year(RegistrationDate) as RegYear,
        If(Status = 'Active', 1, 0) as IsActive
    FROM [Customers.csv];
    """
    
    converter = QlikScriptToPowerQueryConverter()
    pq_script = converter.convert_qlik_script_to_powerquery(qlik_script)
    
    migrator = QlikScriptMigrator()
    report = migrator.generate_conversion_report(qlik_script, pq_script)
    
    print(f"\nFonctions Qlik utilisées: {', '.join(report['qlik_functions_used'])}")
    print(f"Fonctions Power Query générées: {', '.join(report['pq_functions_generated'][:5])}...")
    print(f"Taux de conversion: {report['conversion_rate']:.1f}%")
    
    if report['unconverted_functions']:
        print(f"\n⚠ Fonctions nécessitant révision:")
        for func in report['unconverted_functions']:
            print(f"   - {func}")


def exemple_4_conversion_inline():
    """Exemple 4: Conversion inline (sans fichiers)."""
    print("\n=== Exemple 4: Conversion Inline ===")
    
    qlik_script = """LOAD
    ProductID,
    ProductName,
    CategoryID
FROM [Products.csv]
(txt, codepage is 1252, embedded labels, delimiter is ',');
"""
    
    converter = QlikScriptToPowerQueryConverter()
    pq_script = converter.convert_qlik_script_to_powerquery(qlik_script)
    
    print("Script Qlik:")
    print(qlik_script)
    print("\nScript Power Query M généré:")
    print(pq_script)


def exemple_5_fonctions_date():
    """Exemple 5: Conversions de fonctions de date."""
    print("\n=== Exemple 5: Fonctions de Date ===")
    
    converter = QlikScriptToPowerQueryConverter()
    
    date_functions = [
        "Year(OrderDate)",
        "Month(OrderDate)",
        "Day(OrderDate)",
        "MonthName(OrderDate)",
        "WeekDay(OrderDate)",
        "YearStart(OrderDate)",
        "MonthStart(OrderDate)",
        "Today()",
        "Now()",
    ]
    
    print("\nConversions de fonctions de date:")
    for func in date_functions:
        converted = converter.convert_qlik_function(func)
        print(f"  {func:25} → {converted}")


if __name__ == '__main__':
    print("=" * 70)
    print("Exemples de Migration Scripts Qlik → Power Query M")
    print("=" * 70)
    
    # Exécuter les exemples
    exemple_1_conversion_simple()
    # exemple_2_migration_fichier()  # Décommenter si simple_load.qvs existe
    exemple_3_rapport_conversion()
    exemple_4_conversion_inline()
    exemple_5_fonctions_date()
    
    print("\n" + "=" * 70)
    print("Pour plus d'informations, voir: QLIK_SCRIPT_MIGRATION.md")
    print("=" * 70)
