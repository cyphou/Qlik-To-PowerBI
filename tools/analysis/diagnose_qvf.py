"""
Script de diagnostic pour fichiers QVF
Identifie le type de fichier QVF et propose des solutions
"""
import sys
import zipfile
from pathlib import Path

def diagnose_qvf(qvf_path: str):
    """Diagnostique un fichier QVF et affiche des informations"""
    path = Path(qvf_path)
    
    if not path.exists():
        print(f"❌ Fichier introuvable: {qvf_path}")
        return
    
    print(f"\n{'='*70}")
    print(f"DIAGNOSTIC FICHIER QVF")
    print(f"{'='*70}\n")
    
    print(f"📁 Fichier: {path.name}")
    print(f"📏 Taille: {path.stat().st_size:,} octets ({path.stat().st_size / 1024 / 1024:.2f} MB)")
    
    # Lire les premiers octets
    with open(path, 'rb') as f:
        header = f.read(20)
    
    print(f"\n🔍 Signature (20 premiers octets):")
    hex_str = ' '.join(f'{b:02X}' for b in header)
    print(f"   {hex_str}")
    
    # Vérifier si c'est un ZIP standard
    is_zip = header[:2] == b'PK'
    
    print(f"\n📦 Type de fichier:")
    if is_zip:
        print(f"   ✅ Format ZIP standard (Qlik Sense Desktop)")
        try:
            with zipfile.ZipFile(path, 'r') as z:
                files = z.namelist()
                print(f"\n   Contenu de l'archive ({len(files)} fichiers):")
                for f in files[:10]:  # Afficher les 10 premiers
                    print(f"      - {f}")
                if len(files) > 10:
                    print(f"      ... et {len(files) - 10} autres fichiers")
        except Exception as e:
            print(f"   ⚠️ Erreur lors de la lecture ZIP: {e}")
    else:
        print(f"   ⚠️ Format propriétaire Qlik (probablement Qlik Cloud)")
        print(f"   ℹ️ Signature détectée: {header[:4].hex().upper()}")
        
        # Analyser le type
        if header[:2] == b'\xFF\xFF':
            print(f"\n   💡 Ce fichier semble être au format Qlik Cloud (binaire propriétaire)")
            print(f"   📝 Ce format n'est pas directement lisible comme un ZIP")
        
    print(f"\n{'='*70}")
    print(f"SOLUTIONS")
    print(f"{'='*70}\n")
    
    if is_zip:
        print("✅ Vous pouvez utiliser directement le script migrate_qvf.py:")
        print(f'   python migrate_qvf.py "{qvf_path}" --output-dir "output"')
    else:
        print("⚠️ Ce fichier QVF est au format Qlik Cloud (non-ZIP).")
        print("\n📋 Solutions possibles:\n")
        print("1️⃣ EXPORTER DEPUIS QLIK CLOUD (Recommandé)")
        print("   • Ouvrir l'app dans Qlik Cloud")
        print("   • Menu → Exporter → 'Exporter au format QVF Desktop'")
        print("   • Cela créera un fichier .qvf au format ZIP\n")
        
        print("2️⃣ UTILISER QLIK SENSE DESKTOP")
        print("   • Importer ce .qvf dans Qlik Sense Desktop")
        print("   • Ouvrir l'application")
        print("   • Exporter à nouveau (cela créera un ZIP)\n")
        
        print("3️⃣ MIGRATION MANUELLE DES DONNÉES")
        print("   • Les fichiers sources sont disponibles:")
        source_dir = path.parent
        data_files = list(source_dir.glob("*.xlsx")) + list(source_dir.glob("*.csv"))
        if data_files:
            print(f"     Trouvés dans {source_dir.name}:")
            for df in data_files:
                print(f"       - {df.name} ({df.stat().st_size / 1024:.1f} KB)")
            print("\n   • Vous pouvez:")
            print("     a) Importer ces fichiers directement dans Power BI")
            print("     b) Recréer le modèle manuellement")
        else:
            print("     ℹ️ Fichiers sources non trouvés dans le même dossier")
        
        print("\n4️⃣ API QLIK ENGINE (Avancé)")
        print("   • Utiliser l'API Qlik Engine pour extraire métadonnées")
        print("   • Nécessite accès à Qlik Sense Server/Cloud")
    
    print(f"\n{'='*70}\n")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python diagnose_qvf.py <chemin_fichier.qvf>")
        sys.exit(1)
    
    diagnose_qvf(sys.argv[1])
