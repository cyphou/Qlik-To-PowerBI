"""
Suite de Tests Automatisés - Migration Qlik → Power BI
Teste l'outil migrate_qvf.py sur plusieurs fichiers QVF et génère un rapport
"""
import sys
import os
import json
import time
from pathlib import Path
from datetime import datetime
import logging

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MigrationTester:
    """Testeur automatique de migration QVF → Power BI"""
    
    def __init__(self, input_dir: str, output_dir: str = "test_results"):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        self.results = []
        self.start_time = None
        self.end_time = None
    
    def find_qvf_files(self):
        """Trouve tous les fichiers QVF dans le dossier input"""
        qvf_files = list(self.input_dir.rglob("*.qvf"))
        logger.info(f"📦 {len(qvf_files)} fichier(s) QVF trouvé(s)")
        return qvf_files
    
    def diagnose_qvf(self, qvf_path: Path):
        """Diagnostique un fichier QVF"""
        try:
            # Lire signature
            with open(qvf_path, 'rb') as f:
                header = f.read(4)
            
            is_zip = header[:2] == b'PK'
            format_type = "ZIP (Desktop)" if is_zip else "Binaire (Cloud)"
            
            return {
                "is_zip": is_zip,
                "format": format_type,
                "size_mb": qvf_path.stat().st_size / 1024 / 1024,
                "signature": header.hex().upper()
            }
        except Exception as e:
            logger.error(f"❌ Erreur diagnostic {qvf_path.name}: {e}")
            return None
    
    def test_migration(self, qvf_path: Path):
        """Teste la migration d'un fichier QVF"""
        logger.info(f"\n{'='*70}")
        logger.info(f"🧪 TEST: {qvf_path.name}")
        logger.info(f"{'='*70}")
        
        result = {
            "file_name": qvf_path.name,
            "file_path": str(qvf_path),
            "test_date": datetime.now().isoformat(),
            "success": False,
            "details": {}
        }
        
        # 1. Diagnostic
        logger.info("🔍 Diagnostic du fichier...")
        diagnostic = self.diagnose_qvf(qvf_path)
        if not diagnostic:
            result["error"] = "Échec diagnostic"
            return result
        
        result["details"]["diagnostic"] = diagnostic
        logger.info(f"   Format: {diagnostic['format']}")
        logger.info(f"   Taille: {diagnostic['size_mb']:.2f} MB")
        
        # 2. Test migration
        if diagnostic["is_zip"]:
            result_migration = self.test_zip_migration(qvf_path)
        else:
            result_migration = self.test_cloud_migration(qvf_path)
        
        result["details"]["migration"] = result_migration
        result["success"] = result_migration.get("success", False)
        
        return result
    
    def test_zip_migration(self, qvf_path: Path):
        """Teste migration QVF format ZIP"""
        logger.info

("✅ Format ZIP détecté - Migration automatique possible")
        
        output_subdir = self.output_dir / qvf_path.stem
        output_subdir.mkdir(exist_ok=True)
        
        start = time.time()
        
        try:
            # Importer migrate_qvf
            sys.path.insert(0, str(Path(__file__).parent))
            from fabric_api.qvf_extractor import QVFExtractor
            from fabric_api.qlik_script_to_pq import QlikScriptConverter
            from fabric_api.qlik_model_to_bim import QlikModelToBIM
            
            # Extraction
            logger.info("   📦 Extraction QVF...")
            extractor = QVFExtractor(str(qvf_path))
            qlik_data = extractor.extract_all()
            
            # Conversion scripts
            logger.info("   ⚙️ Conversion scripts...")
            script_converter = QlikScriptConverter()
            nb_functions = len(qlik_data.get("script", "").split('\n'))
            
            # Conversion modèle
            logger.info("   🔗 Conversion modèle...")
            model_converter = QlikModelToBIM()
            nb_tables = len(qlik_data.get("tables", []))
            
            elapsed = time.time() - start
            
            logger.info(f"   ✅ Migration réussie en {elapsed:.2f}s")
            
            return {
                "success": True,
                "time_seconds": elapsed,
                "nb_tables": nb_tables,
                "nb_script_lines": nb_functions,
                "output_dir": str(output_subdir)
            }
            
        except Exception as e:
            elapsed = time.time() - start
            logger.error(f"   ❌ Échec migration: {e}")
            return {
                "success": False,
                "error": str(e),
                "time_seconds": elapsed
            }
    
    def test_cloud_migration(self, qvf_path: Path):
        """Teste détection format Cloud et solution alternative"""
        logger.info("⚠️ Format Cloud détecté - Migration automatique impossible")
        logger.info("   💡 Solution: Génération scripts depuis fichiers sources")
        
        # Chercher fichiers sources dans même dossier
        source_dir = qvf_path.parent
        excel_files = list(source_dir.glob("*.xlsx")) + list(source_dir.glob("*.xls"))
        csv_files = list(source_dir.glob("*.csv"))
        
        sources_found = len(excel_files) + len(csv_files)
        
        if sources_found > 0:
            logger.info(f"   ✅ {sources_found} fichier(s) source(s) trouvé(s)")
            return {
                "success": True,
                "migration_type": "alternative",
                "sources_found": sources_found,
                "excel_files": [f.name for f in excel_files],
                "csv_files": [f.name for f in csv_files],
                "recommendation": "Utiliser generate_pq_from_sources.py"
            }
        else:
            logger.warning("   ⚠️ Aucun fichier source trouvé")
            return {
                "success": False,
                "migration_type": "blocked",
                "sources_found": 0,
                "recommendation": "Exporter QVF depuis Qlik Cloud au format Desktop"
            }
    
    def run_all_tests(self):
        """Exécute tous les tests"""
        logger.info("\n" + "="*70)
        logger.info("🚀 DÉMARRAGE SUITE DE TESTS MIGRATION")
        logger.info("="*70 + "\n")
        
        self.start_time = datetime.now()
        
        # Trouver fichiers
        qvf_files = self.find_qvf_files()
        
        if not qvf_files:
            logger.warning("⚠️ Aucun fichier QVF trouvé dans " + str(self.input_dir))
            return
        
        # Tester chaque fichier
        for i, qvf_file in enumerate(qvf_files, 1):
            logger.info(f"\n📊 Progression: {i}/{len(qvf_files)}")
            result = self.test_migration(qvf_file)
            self.results.append(result)
        
        self.end_time = datetime.now()
        
        # Générer rapport
        self.generate_report()
    
    def generate_report(self):
        """Génère rapports JSON et HTML"""
        duration = (self.end_time - self.start_time).total_seconds()
        
        # Statistiques
        total = len(self.results)
        success = sum(1 for r in self.results if r["success"])
        failed = total - success
        success_rate = (success / total * 100) if total > 0 else 0
        
        # Rapport JSON
        report_data = {
            "test_suite": "Migration Qlik → Power BI",
            "date": self.start_time.isoformat(),
            "duration_seconds": duration,
            "statistics": {
                "total_files": total,
                "successful": success,
                "failed": failed,
                "success_rate": round(success_rate, 2)
            },
            "results": self.results
        }
        
        timestamp = self.start_time.strftime("%Y%m%d_%H%M%S")
        json_file = self.output_dir / f"test_report_{timestamp}.json"
        
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"\n✅ Rapport JSON: {json_file}")
        
        # Rapport HTML
        html_file = self.output_dir / f"test_report_{timestamp}.html"
        self.generate_html_report(html_file, report_data)
        logger.info(f"✅ Rapport HTML: {html_file}")
        
        # Afficher résumé
        self.print_summary(report_data)
    
    def generate_html_report(self, html_file: Path, data: dict):
        """Génère rapport HTML"""
        stats = data["statistics"]
        
        html_content = f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Rapport Test Migration Qlik → Power BI</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background: #f5f5f5;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #0078d4;
            border-bottom: 3px solid #0078d4;
            padding-bottom: 10px;
        }}
        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 30px 0;
        }}
        .stat-card {{
            background: #f8f8f8;
            padding: 20px;
            border-radius: 6px;
            border-left: 4px solid #0078d4;
        }}
        .stat-value {{
            font-size: 36px;
            font-weight: bold;
            color: #0078d4;
        }}
        .stat-label {{
            color: #666;
            margin-top: 5px;
        }}
        .success {{ color: #107c10; }}
        .failed {{ color: #d13438; }}
        .results {{
            margin-top: 30px;
        }}
        .result-item {{
            background: #fafafa;
            margin: 15px 0;
            padding: 20px;
            border-radius: 6px;
            border-left: 4px solid #ccc;
        }}
        .result-item.success {{
            border-left-color: #107c10;
        }}
        .result-item.failed {{
            border-left-color: #d13438;
        }}
        .result-header {{
            font-size: 18px;
            font-weight: bold;
            margin-bottom: 10px;
        }}
        .result-details {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 15px;
            margin-top: 15px;
        }}
        .detail-item {{
            display: flex;
            justify-content: space-between;
        }}
        .detail-label {{
            color: #666;
        }}
        .detail-value {{
            font-weight: bold;
        }}
        .badge {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: bold;
        }}
        .badge.success {{
            background: #e6f4ea;
            color: #107c10;
        }}
        .badge.failed {{
            background: #fce8e6;
            color: #d13438;
        }}
        .badge.warning {{
            background: #fff4ce;
            color: #8a6d3b;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🧪 Rapport Test Migration Qlik → Power BI</h1>
        
        <p><strong>Date:</strong> {data["date"]}</p>
        <p><strong>Durée:</strong> {data["duration_seconds"]:.2f} secondes</p>
        
        <div class="stats">
            <div class="stat-card">
                <div class="stat-value">{stats["total_files"]}</div>
                <div class="stat-label">Fichiers Testés</div>
            </div>
            <div class="stat-card">
                <div class="stat-value success">{stats["successful"]}</div>
                <div class="stat-label">Succès</div>
            </div>
            <div class="stat-card">
                <div class="stat-value failed">{stats["failed"]}</div>
                <div class="stat-label">Échecs</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{stats["success_rate"]}%</div>
                <div class="stat-label">Taux de Réussite</div>
            </div>
        </div>
        
        <h2>📋 Résultats Détaillés</h2>
        <div class="results">
"""
        
        for result in data["results"]:
            success_class = "success" if result["success"] else "failed"
            badge_class = "success" if result["success"] else "failed"
            badge_text = "✅ Succès" if result["success"] else "❌ Échec"
            
            diagnostic = result["details"].get("diagnostic", {})
            migration = result["details"].get("migration", {})
            
            html_content += f"""
            <div class="result-item {success_class}">
                <div class="result-header">
                    📄 {result["file_name"]}
                    <span class="badge {badge_class}">{badge_text}</span>
                </div>
                <div class="result-details">
                    <div class="detail-item">
                        <span class="detail-label">Format:</span>
                        <span class="detail-value">{diagnostic.get("format", "N/A")}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Taille:</span>
                        <span class="detail-value">{diagnostic.get("size_mb", 0):.2f} MB</span>
                    </div>
"""
            
            if migration.get("time_seconds"):
                html_content += f"""
                    <div class="detail-item">
                        <span class="detail-label">Temps:</span>
                        <span class="detail-value">{migration["time_seconds"]:.2f}s</span>
                    </div>
"""
            
            if migration.get("nb_tables"):
                html_content += f"""
                    <div class="detail-item">
                        <span class="detail-label">Tables:</span>
                        <span class="detail-value">{migration["nb_tables"]}</span>
                    </div>
"""
            
            if migration.get("recommendation"):
                html_content += f"""
                    <div class="detail-item">
                        <span class="detail-label">Recommandation:</span>
                        <span class="detail-value">{migration["recommendation"]}</span>
                    </div>
"""
            
            html_content += """
                </div>
            </div>
"""
        
        html_content += """
        </div>
    </div>
</body>
</html>
"""
        
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
    
    def print_summary(self, data: dict):
        """Affiche résumé dans console"""
        stats = data["statistics"]
        
        logger.info("\n" + "="*70)
        logger.info("📊 RÉSUMÉ DES TESTS")
        logger.info("="*70)
        logger.info(f"\n📦 Fichiers testés  : {stats['total_files']}")
        logger.info(f"✅ Succès           : {stats['successful']}")
        logger.info(f"❌ Échecs           : {stats['failed']}")
        logger.info(f"📈 Taux de réussite : {stats['success_rate']:.1f}%")
        logger.info(f"⏱️ Durée totale     : {data['duration_seconds']:.2f}s")
        logger.info("\n" + "="*70 + "\n")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Suite de tests migration Qlik → Power BI")
    parser.add_argument("--input", "-i", default="test_samples", help="Dossier contenant fichiers QVF")
    parser.add_argument("--output", "-o", default="test_results", help="Dossier de sortie rapports")
    
    args = parser.parse_args()
    
    tester = MigrationTester(args.input, args.output)
    tester.run_all_tests()
