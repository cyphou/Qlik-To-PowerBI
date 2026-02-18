"""
Script de Migration QVD → Power BI
Génère les scripts nécessaires pour la migration
"""

import pandas as pd
from pathlib import Path
import json
from typing import List, Dict, Optional
import argparse


class QVDMigrationHelper:
    """Assistant de migration QVD vers Power BI."""
    
    def __init__(self, qvd_folder: str, export_folder: str):
        """
        Initialiser le helper.
        
        Args:
            qvd_folder: Dossier contenant les fichiers QVD
            export_folder: Dossier pour les exports
        """
        self.qvd_folder = Path(qvd_folder)
        self.export_folder = Path(export_folder)
        self.export_folder.mkdir(parents=True, exist_ok=True)
        
        print(f"📂 Dossier QVD : {self.qvd_folder}")
        print(f"📂 Dossier Export : {self.export_folder}")
    
    def scan_qvd_files(self) -> List[Path]:
        """Scanner les fichiers QVD disponibles."""
        if not self.qvd_folder.exists():
            print(f"❌ Dossier introuvable : {self.qvd_folder}")
            return []
        
        qvd_files = list(self.qvd_folder.glob("*.qvd"))
        print(f"\n✓ {len(qvd_files)} fichiers QVD trouvés")
        
        for qvd in qvd_files:
            size_mb = qvd.stat().st_size / (1024 ** 2)
            print(f"   • {qvd.name} ({size_mb:.1f} MB)")
        
        return qvd_files
    
    def generate_qlik_export_script(self, qvd_files: Optional[List[Path]] = None) -> Path:
        """
        Générer un script Qlik pour exporter les QVD en CSV.
        
        Args:
            qvd_files: Liste des fichiers QVD (optionnel)
            
        Returns:
            Chemin du script généré
        """
        if qvd_files is None:
            qvd_files = self.scan_qvd_files()
        
        if not qvd_files:
            raise ValueError("Aucun fichier QVD trouvé")
        
        print(f"\n📝 Génération du script Qlik...")
        
        # Générer le script
        script = f"""// ================================================================
// Script d'Export QVD → CSV
// Généré automatiquement par QVD Migration Helper
// Date: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}
// ================================================================

// Configuration des chemins
SET vExportPath = '{self.export_folder.as_posix()}/';
SET vQVDPath = '{self.qvd_folder.as_posix()}/';

// ================================================================
// Export des tables
// ================================================================

"""
        
        for i, qvd in enumerate(qvd_files, 1):
            table_name = qvd.stem.replace('-', '_').replace(' ', '_')
            
            script += f"""
// {i}. Export de {table_name}
{table_name}:
LOAD *
FROM [$(vQVDPath){qvd.name}] (qvd);

STORE {table_name} INTO [$(vExportPath){table_name}.csv] (txt);
DROP TABLE {table_name};

"""
        
        script += """
// ================================================================
// Fin du script
// ================================================================
"""
        
        # Sauvegarder
        script_file = self.export_folder / "01_export_qvd_to_csv.qvs"
        with open(script_file, 'w', encoding='utf-8') as f:
            f.write(script)
        
        print(f"✓ Script Qlik créé : {script_file}")
        print(f"\n📋 INSTRUCTIONS:")
        print(f"   1. Ouvrir QlikView ou Qlik Sense Desktop")
        print(f"   2. Créer un nouveau document")
        print(f"   3. Copier le contenu de : {script_file}")
        print(f"   4. Coller dans l'éditeur de script")
        print(f"   5. Recharger (Ctrl+R)")
        print(f"   6. Les CSV seront créés dans : {self.export_folder}")
        
        return script_file
    
    def csv_to_parquet(self, csv_files: Optional[List[Path]] = None) -> Dict:
        """
        Convertir les CSV en Parquet.
        
        Args:
            csv_files: Liste des CSV (optionnel, scanne le dossier sinon)
            
        Returns:
            Rapport de conversion
        """
        if csv_files is None:
            csv_files = list(self.export_folder.glob("*.csv"))
        
        if not csv_files:
            print("❌ Aucun fichier CSV trouvé")
            return {}
        
        print(f"\n🔄 Conversion CSV → Parquet...")
        print(f"   {len(csv_files)} fichiers à convertir")
        
        results = []
        
        for csv_file in csv_files:
            try:
                print(f"\n   Traitement : {csv_file.name}")
                
                # Lire CSV
                df = pd.read_csv(csv_file, encoding='utf-8-sig')
                
                # Sauvegarder Parquet
                parquet_file = csv_file.with_suffix('.parquet')
                df.to_parquet(parquet_file, engine='pyarrow', compression='snappy')
                
                # Statistiques
                csv_size = csv_file.stat().st_size / (1024 ** 2)
                parquet_size = parquet_file.stat().st_size / (1024 ** 2)
                compression = ((csv_size - parquet_size) / csv_size) * 100
                
                result = {
                    'table': csv_file.stem,
                    'csv_file': str(csv_file),
                    'parquet_file': str(parquet_file),
                    'csv_size_mb': round(csv_size, 2),
                    'parquet_size_mb': round(parquet_size, 2),
                    'compression_percent': round(compression, 1),
                    'rows': len(df),
                    'columns': len(df.columns)
                }
                
                results.append(result)
                
                print(f"      CSV: {csv_size:.1f} MB")
                print(f"      Parquet: {parquet_size:.1f} MB")
                print(f"      ✓ Compression: {compression:.1f}%")
                
            except Exception as e:
                print(f"      ❌ Erreur : {e}")
                continue
        
        # Sauvegarder rapport
        report = {
            'conversion_date': pd.Timestamp.now().isoformat(),
            'total_files': len(results),
            'files': results,
            'summary': {
                'total_csv_mb': sum(r['csv_size_mb'] for r in results),
                'total_parquet_mb': sum(r['parquet_size_mb'] for r in results),
                'total_rows': sum(r['rows'] for r in results)
            }
        }
        
        report_file = self.export_folder / "02_conversion_report.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2)
        
        print(f"\n✓ Rapport sauvegardé : {report_file}")
        print(f"\n📊 RÉSUMÉ:")
        print(f"   Fichiers convertis : {len(results)}")
        print(f"   Volume CSV total : {report['summary']['total_csv_mb']:.1f} MB")
        print(f"   Volume Parquet total : {report['summary']['total_parquet_mb']:.1f} MB")
        print(f"   Lignes totales : {report['summary']['total_rows']:,}")
        
        return report
    
    def generate_powerquery_script(self, use_parquet: bool = False) -> Path:
        """
        Générer un script Power Query pour charger les données.
        
        Args:
            use_parquet: True pour Parquet, False pour CSV
            
        Returns:
            Chemin du script généré
        """
        ext = '.parquet' if use_parquet else '.csv'
        files = sorted(self.export_folder.glob(f"*{ext}"))
        
        if not files:
            raise ValueError(f"Aucun fichier {ext} trouvé")
        
        print(f"\n📝 Génération du script Power Query...")
        print(f"   Format : {ext.upper()}")
        print(f"   {len(files)} tables")
        
        # En-tête
        script = f"""// ================================================================
// Script Power Query - Chargement des Données
// Généré automatiquement par QVD Migration Helper
// Date: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}
// Format: {ext.upper()}
// ================================================================

"""
        
        if use_parquet:
            script += """// Fonction helper pour charger Parquet
let
    LoadParquet = (FilePath as text) as table =>
        let
            Source = Parquet.Document(File.Contents(FilePath)),
            Data = Source{[Name="Data"]}[Data]
        in
            Data,
    
"""
        else:
            script += """// Fonction helper pour charger CSV
let
    LoadCSV = (FilePath as text) as table =>
        let
            Source = Csv.Document(File.Contents(FilePath), 
                [Delimiter=",", Columns=null, Encoding=65001, QuoteStyle=QuoteStyle.None]),
            PromotedHeaders = Table.PromoteHeaders(Source, [PromoteAllScalars=true])
        in
            PromotedHeaders,
    
"""
        
        # Charger chaque table
        script += "    // Tables\n"
        
        for i, file in enumerate(files):
            table_name = file.stem
            file_path = file.as_posix()
            
            if use_parquet:
                script += f'    {table_name} = LoadParquet("{file_path}"),\n'
            else:
                script += f'    {table_name} = LoadCSV("{file_path}"),\n'
        
        # Retourner la première table (à modifier selon besoin)
        first_table = files[0].stem
        script += f"""    
    // Retourner la première table (modifier selon besoin)
    Result = {first_table}
in
    Result
"""
        
        # Sauvegarder
        script_file = self.export_folder / f"03_load_data{'_parquet' if use_parquet else '_csv'}.pq"
        with open(script_file, 'w', encoding='utf-8') as f:
            f.write(script)
        
        print(f"✓ Script Power Query créé : {script_file}")
        print(f"\n📋 UTILISATION:")
        print(f"   1. Ouvrir Power BI Desktop")
        print(f"   2. Obtenir des données → Requête vide")
        print(f"   3. Éditeur avancé → Copier le contenu de : {script_file}")
        print(f"   4. OK → Fermer et appliquer")
        
        return script_file


def main():
    """Point d'entrée principal."""
    
    parser = argparse.ArgumentParser(
        description="Migration QVD vers Power BI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  # Générer script Qlik pour export CSV
  python migrate_qvd.py --qvd-folder "C:/QlikData/QVD" --export-folder "C:/Export" --generate-qlik-script
  
  # Convertir CSV en Parquet
  python migrate_qvd.py --export-folder "C:/Export" --csv-to-parquet
  
  # Générer script Power Query (CSV)
  python migrate_qvd.py --export-folder "C:/Export" --generate-powerquery
  
  # Générer script Power Query (Parquet)
  python migrate_qvd.py --export-folder "C:/Export" --generate-powerquery --use-parquet
  
  # Workflow complet
  python migrate_qvd.py --qvd-folder "C:/QlikData/QVD" --export-folder "C:/Export" --full-workflow
        """
    )
    
    parser.add_argument('--qvd-folder', required=False, 
                        help='Dossier contenant les fichiers QVD')
    parser.add_argument('--export-folder', required=True,
                        help='Dossier pour les exports')
    parser.add_argument('--generate-qlik-script', action='store_true',
                        help='Générer le script Qlik pour export CSV')
    parser.add_argument('--csv-to-parquet', action='store_true',
                        help='Convertir les CSV en Parquet')
    parser.add_argument('--generate-powerquery', action='store_true',
                        help='Générer le script Power Query')
    parser.add_argument('--use-parquet', action='store_true',
                        help='Utiliser Parquet au lieu de CSV')
    parser.add_argument('--full-workflow', action='store_true',
                        help='Exécuter le workflow complet')
    
    args = parser.parse_args()
    
    print("""
╔════════════════════════════════════════════════════════════════════╗
║           🔄 MIGRATION QVD → POWER BI                              ║
╚════════════════════════════════════════════════════════════════════╝
""")
    
    helper = QVDMigrationHelper(
        qvd_folder=args.qvd_folder or ".",
        export_folder=args.export_folder
    )
    
    # Workflow complet
    if args.full_workflow:
        print("\n🚀 WORKFLOW COMPLET\n")
        
        # 1. Générer script Qlik
        helper.generate_qlik_export_script()
        
        print(f"\n{'='*70}")
        input("⏸️  Exécutez le script Qlik, puis appuyez sur Entrée...")
        
        # 2. Convertir en Parquet
        helper.csv_to_parquet()
        
        # 3. Générer script Power Query
        helper.generate_powerquery_script(use_parquet=True)
        
        print(f"\n{'='*70}")
        print("✅ WORKFLOW TERMINÉ")
        print(f"📂 Tous les fichiers sont dans : {helper.export_folder}")
        
        return
    
    # Étapes individuelles
    if args.generate_qlik_script:
        helper.generate_qlik_export_script()
    
    if args.csv_to_parquet:
        helper.csv_to_parquet()
    
    if args.generate_powerquery:
        helper.generate_powerquery_script(use_parquet=args.use_parquet)
    
    # Si aucune action
    if not any([args.generate_qlik_script, args.csv_to_parquet, 
                args.generate_powerquery, args.full_workflow]):
        parser.print_help()


if __name__ == "__main__":
    main()
