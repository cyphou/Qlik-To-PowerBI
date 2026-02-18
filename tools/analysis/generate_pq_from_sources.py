"""
Générateur de scripts Power Query M depuis fichiers sources
Crée automatiquement les scripts .pq pour Excel et CSV
"""
import sys
from pathlib import Path
import re

def sanitize_name(name: str) -> str:
    """Nettoie un nom de fichier pour créer un nom de table valide"""
    # Supprimer l'extension
    name = Path(name).stem
    # Remplacer espaces et caractères spéciaux par underscore
    name = re.sub(r'[^\w]+', '_', name)
    # Supprimer underscores multiples
    name = re.sub(r'_+', '_', name)
    # Supprimer underscores début/fin
    name = name.strip('_')
    return name

def generate_excel_pq(file_path: Path, sheet_name: str = None) -> str:
    """Génère un script Power Query M pour un fichier Excel"""
    table_name = sanitize_name(file_path.name)
    file_path_str = str(file_path).replace('\\', '\\\\')
    
    # Si pas de nom de feuille spécifié, utiliser le nom de fichier
    if not sheet_name:
        sheet_name = table_name
    
    script = f'''let
    // Source: {file_path.name}
    Source = Excel.Workbook(
        File.Contents("{file_path_str}"),
        null,
        true
    ),
    
    // Sélectionner la feuille '{sheet_name}'
    SheetData = Source{{[Item="{sheet_name}", Kind="Sheet"]}}[Data],
    
    // Promouvoir les en-têtes
    PromotedHeaders = Table.PromoteHeaders(
        SheetData,
        [PromoteAllScalars=true]
    ),
    
    // Détecter et appliquer les types de données automatiquement
    DetectedTypes = Table.TransformColumnTypes(
        PromotedHeaders,
        List.Transform(
            Table.ColumnNames(PromotedHeaders),
            each {{_, type any}}
        )
    )
in
    DetectedTypes
'''
    return script

def generate_csv_pq(file_path: Path, delimiter: str = ",", encoding: int = 65001) -> str:
    """Génère un script Power Query M pour un fichier CSV"""
    table_name = sanitize_name(file_path.name)
    file_path_str = str(file_path).replace('\\', '\\\\')
    
    script = f'''let
    // Source: {file_path.name}
    Source = Csv.Document(
        File.Contents("{file_path_str}"),
        [
            Delimiter="{delimiter}",
            Encoding={encoding},
            QuoteStyle=QuoteStyle.Csv
        ]
    ),
    
    // Promouvoir les en-têtes
    PromotedHeaders = Table.PromoteHeaders(
        Source,
        [PromoteAllScalars=true]
    ),
    
    // Détecter et appliquer les types de données automatiquement
    DetectedTypes = Table.TransformColumnTypes(
        PromotedHeaders,
        List.Transform(
            Table.ColumnNames(PromotedHeaders),
            each {{_, type any}}
        )
    )
in
    DetectedTypes
'''
    return script

def generate_all_pq_scripts(source_folder: str, output_folder: str = None):
    """Génère tous les scripts Power Query pour les fichiers d'un dossier"""
    source_path = Path(source_folder)
    
    if not source_path.exists():
        print(f"❌ Dossier introuvable: {source_folder}")
        return
    
    # Créer dossier de sortie
    if output_folder:
        output_path = Path(output_folder)
    else:
        output_path = Path("generated_power_query")
    
    output_path.mkdir(exist_ok=True)
    
    print(f"\n{'='*70}")
    print(f"GÉNÉRATION SCRIPTS POWER QUERY M")
    print(f"{'='*70}\n")
    print(f"📁 Source: {source_path}")
    print(f"📂 Sortie: {output_path}\n")
    
    generated_count = 0
    
    # Traiter fichiers Excel
    excel_files = list(source_path.glob("*.xlsx")) + list(source_path.glob("*.xls"))
    for excel_file in excel_files:
        table_name = sanitize_name(excel_file.name)
        output_file = output_path / f"{table_name}.pq"
        
        # Générer script
        script = generate_excel_pq(excel_file, sheet_name=table_name)
        
        # Sauvegarder
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(script)
        
        print(f"✅ {excel_file.name:40} → {output_file.name}")
        generated_count += 1
    
    # Traiter fichiers CSV
    csv_files = list(source_path.glob("*.csv"))
    for csv_file in csv_files:
        table_name = sanitize_name(csv_file.name)
        output_file = output_path / f"{table_name}.pq"
        
        # Générer script
        script = generate_csv_pq(csv_file)
        
        # Sauvegarder
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(script)
        
        print(f"✅ {csv_file.name:40} → {output_file.name}")
        generated_count += 1
    
    print(f"\n{'='*70}")
    print(f"✅ {generated_count} script(s) Power Query généré(s)")
    print(f"{'='*70}\n")
    
    # Instructions
    if generated_count > 0:
        print("📋 PROCHAINES ÉTAPES:\n")
        print("1. Ouvrir Power BI Desktop")
        print("2. Obtenir des données → Requête vide")
        print("3. Éditeur avancé → Copier le contenu d'un fichier .pq")
        print("4. OK → Renommer la requête")
        print("5. Répéter pour chaque fichier .pq")
        print("6. Fermer et appliquer\n")
        print("💡 Astuce: Créer une fonction Power Query pour automatiser !\n")
        
        # Créer un fichier récapitulatif
        summary_file = output_path / "README.txt"
        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write("SCRIPTS POWER QUERY GÉNÉRÉS\n")
            f.write("=" * 70 + "\n\n")
            f.write(f"Dossier source: {source_path}\n")
            f.write(f"Date génération: {Path(__file__).stat().st_mtime}\n\n")
            f.write("FICHIERS GÉNÉRÉS:\n\n")
            
            for pq_file in sorted(output_path.glob("*.pq")):
                f.write(f"  - {pq_file.name}\n")
            
            f.write("\n" + "=" * 70 + "\n")
            f.write("UTILISATION:\n\n")
            f.write("1. Ouvrir Power BI Desktop\n")
            f.write("2. Obtenir des données → Requête vide\n")
            f.write("3. Éditeur avancé → Copier contenu .pq\n")
            f.write("4. Répéter pour chaque fichier\n")
            f.write("5. Créer relations dans Vue Modèle\n\n")
        
        print(f"📄 Récapitulatif créé: {summary_file}\n")
    else:
        print("⚠️ Aucun fichier Excel ou CSV trouvé dans le dossier source\n")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python generate_pq_from_sources.py <dossier_source> [dossier_sortie]")
        print("\nExemple:")
        print('  python generate_pq_from_sources.py "C:\\Data\\Sources"')
        print('  python generate_pq_from_sources.py "C:\\Data\\Sources" "output_pq"')
        sys.exit(1)
    
    source = sys.argv[1]
    output = sys.argv[2] if len(sys.argv) > 2 else None
    
    generate_all_pq_scripts(source, output)
