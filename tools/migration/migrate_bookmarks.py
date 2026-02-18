#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Migration des Bookmarks Qlik vers Signets Power BI
"""

import json
import zipfile
from pathlib import Path
from typing import List, Dict
from dataclasses import dataclass, field


@dataclass
class QlikBookmark:
    """Bookmark Qlik"""
    id: str
    name: str
    description: str = ""
    selections: Dict[str, List[str]] = field(default_factory=dict)
    sheet_id: str = ""


@dataclass
class PowerBIBookmark:
    """Signet Power BI"""
    name: str
    description: str
    page_name: str = ""
    filters: List[str] = field(default_factory=list)
    visual_states: List[Dict] = field(default_factory=list)


class BookmarkMigrator:
    """Migration bookmarks Qlik → Power BI"""
    
    def __init__(self, output_dir: Path = None):
        self.output_dir = output_dir or Path('output/bookmarks')
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def extract_bookmarks(self, qvf_path: Path) -> List[QlikBookmark]:
        """Extrait les bookmarks d'un QVF"""
        print(f"🔖 Extraction bookmarks depuis : {qvf_path}")
        
        bookmarks = []
        try:
            with zipfile.ZipFile(qvf_path, 'r') as qvf:
                if 'app.json' in qvf.namelist():
                    app_data = json.loads(qvf.read('app.json').decode('utf-8'))
                    
                    # Chercher bookmarks
                    if 'properties' in app_data and 'qBookmarkList' in app_data['properties']:
                        for bm in app_data['properties']['qBookmarkList']:
                            bookmark = QlikBookmark(
                                id=bm.get('qId', ''),
                                name=bm.get('qMetaDef', {}).get('title', 'Untitled'),
                                description=bm.get('qMetaDef', {}).get('description', ''),
                                selections=bm.get('qBookmark', {}).get('qStateData', [])
                            )
                            bookmarks.append(bookmark)
            
            print(f"✅ {len(bookmarks)} bookmarks trouvés")
        except Exception as e:
            print(f"❌ Erreur : {e}")
        
        return bookmarks
    
    def generate_guide(self) -> str:
        """Génère guide de migration bookmarks"""
        guide_file = self.output_dir / "BOOKMARK_MIGRATION_GUIDE.md"
        
        guide = """# Migration Bookmarks Qlik → Signets Power BI

## Conversion

Les bookmarks Qlik capturent :
- Sélections utilisateur
- État des objets (visibles/masqués)
- Feuille active

Les signets Power BI capturent :
- Filtres appliqués
- État des visuels (visibles/masqués)
- Page actuelle

## Étapes Manuelles

### 1. Identifier les Bookmarks Qlik

Liste extraite dans `bookmarks.json`

### 2. Créer Signets Power BI

Pour chaque bookmark :

1. Ouvrir Power BI Desktop
2. Appliquer les filtres correspondants
3. **Affichage** → **Signets** → **Ajouter**
4. Nommer le signet (même nom que Qlik)
5. Configurer options (données, affichage, page courante)

### 3. Tester

- Cliquer sur chaque signet
- Vérifier filtres appliqués
- Comparer avec Qlik

## Limitations

- Pas de migration automatique des sélections
- Les signets doivent être recréés manuellement
- Différences de comportement entre Qlik et Power BI

"""
        
        guide_file.write_text(guide, encoding='utf-8')
        print(f"✅ Guide généré : {guide_file}")
        return guide


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Migration Bookmarks Qlik")
    parser.add_argument('qvf_file', type=Path)
    parser.add_argument('--output-dir', type=Path, default=Path('output/bookmarks'))
    args = parser.parse_args()
    
    migrator = BookmarkMigrator(output_dir=args.output_dir)
    bookmarks = migrator.extract_bookmarks(args.qvf_file)
    
    # Sauvegarder
    output_file = args.output_dir / "bookmarks.json"
    with output_file.open('w', encoding='utf-8') as f:
        json.dump([{
            'id': b.id,
            'name': b.name,
            'description': b.description,
            'selections': b.selections
        } for b in bookmarks], f, indent=2, ensure_ascii=False)
    
    migrator.generate_guide()
    
    print(f"\n✅ {len(bookmarks)} bookmarks extraits")
    print(f"📁 Fichiers dans : {args.output_dir}")
    return 0


if __name__ == '__main__':
    exit(main())
