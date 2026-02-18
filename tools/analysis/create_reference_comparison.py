"""
CRÉATION OBLIGATOIRE D'UN FICHIER DE RÉFÉRENCE

Sans fichier de référence créé par Power BI Desktop, 
nous continuerons à deviner le format.
"""

import sys
from pathlib import Path
import zipfile

print("""
╔════════════════════════════════════════════════════════════════════╗
║                  🔴 ACTION REQUISE - URGENT 🔴                      ║
╠════════════════════════════════════════════════════════════════════╣
║                                                                    ║
║  Nous avons essayé 4 approches différentes d'encodage :           ║
║                                                                    ║
║  ❌ 1. BOM manuel + UTF-16 LE  → '﻿2.130.754.0' (BOM dans string) ║
║  ❌ 2. ASCII pur               → '⸳�' (lu comme UTF-16 LE)        ║
║  ❌ 3. encode('utf-16')        → '﻿3.0' (MÊME problème que #1)   ║
║  ❌ 4. Tentative actuelle      → Échec encore                      ║
║                                                                    ║
║  Sans fichier de référence Power BI Desktop, nous devinons !      ║
║                                                                    ║
╚════════════════════════════════════════════════════════════════════╝

╔════════════════════════════════════════════════════════════════════╗
║           📋 INSTRUCTIONS - À SUIVRE MAINTENANT :                  ║
╠════════════════════════════════════════════════════════════════════╣
║                                                                    ║
║  1️⃣  Ouvrir Power BI Desktop                                      ║
║                                                                    ║
║  2️⃣  Créer un rapport VIDE (ne rien ajouter du tout)              ║
║                                                                    ║
║  3️⃣  Fichier → Enregistrer sous                                   ║
║      Nom      : reference.pbix                                     ║
║      Dossier  : test_files\\                                       ║
║                                                                    ║
║  4️⃣  Fermer Power BI Desktop                                      ║
║                                                                    ║
║  5️⃣  Relancer ce script : python create_reference_comparison.py   ║
║                                                                    ║
╚════════════════════════════════════════════════════════════════════╝
""")

reference_path = Path("test_files/reference.pbix")

if not reference_path.exists():
    print(f"\n❌ {reference_path} n'existe pas encore\n")
    print("Suivez les instructions ci-dessus, puis relancez ce script.\n")
    sys.exit(1)

print(f"\n✓ {reference_path} trouvé !")
print("\nAnalyse en cours...\n")

# Analyser le fichier de référence
with zipfile.ZipFile(reference_path, 'r') as z:
    print("="*70)
    print("STRUCTURE DU FICHIER REFERENCE.PBIX")
    print("="*70)
    
    files = z.namelist()
    print(f"\n📦 {len(files)} fichiers dans l'archive:\n")
    
    for filename in sorted(files):
        info = z.getinfo(filename)
        print(f"  • {filename:<30} {info.file_size:>6} bytes")
    
    # Analyser le fichier Version
    if 'Version' in files:
        print("\n" + "="*70)
        print("ANALYSE DÉTAILLÉE DU FICHIER VERSION")
        print("="*70)
        
        version_data = z.read('Version')
        print(f"\nTaille: {len(version_data)} bytes")
        print(f"\nHexdump complet:")
        
        for i in range(0, len(version_data), 16):
            chunk = version_data[i:i+16]
            hex_str = ' '.join(f'{b:02x}' for b in chunk)
            ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
            print(f"  {i:04x}: {hex_str:<48} {ascii_str}")
        
        print(f"\nPremiers 10 bytes (déc): {list(version_data[:10])}")
        print(f"Premiers 10 bytes (hex): {version_data[:10].hex()}")
        
        # Essayer différents décodages
        print(f"\nTentatives de décodage:")
        
        # UTF-16 LE avec BOM
        if version_data[:2] == b'\xff\xfe':
            try:
                decoded = version_data[2:].decode('utf-16-le')
                print(f"  UTF-16 LE (sans BOM): '{decoded}'")
                print(f"  Repr: {repr(decoded)}")
            except:
                print(f"  UTF-16 LE (sans BOM): ÉCHEC")
        
        # UTF-16 avec BOM
        try:
            decoded = version_data.decode('utf-16')
            print(f"  UTF-16 (avec BOM): '{decoded}'")
            print(f"  Repr: {repr(decoded)}")
        except:
            print(f"  UTF-16 (avec BOM): ÉCHEC")
        
        # UTF-8
        try:
            decoded = version_data.decode('utf-8')
            print(f"  UTF-8: '{decoded}'")
        except:
            print(f"  UTF-8: ÉCHEC")
        
        # ASCII  
        try:
            decoded = version_data.decode('ascii')
            print(f"  ASCII: '{decoded}'")
        except:
            print(f"  ASCII: ÉCHEC")
    
    # Analyser [Content_Types].xml
    if '[Content_Types].xml' in files:
        print("\n" + "="*70)
        print("[Content_Types].xml")
        print("="*70)
        
        ct_data = z.read('[Content_Types].xml')
        print(f"\n{ct_data.decode('utf-8')}")

print("\n" + "="*70)
print("✅ ANALYSE TERMINÉE")
print("="*70)
print("""
Maintenant, nous pouvons comparer byte-par-byte avec notre fichier généré
et corriger exactement ce qui ne va pas.
""")
