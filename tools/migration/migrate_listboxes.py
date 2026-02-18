#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Migration List Boxes Qlik vers Segments Power BI
"""

import json
import zipfile
from pathlib import Path
from typing import List, Dict
from dataclasses import dataclass


@dataclass
class QlikListBox:
    """List Box QlikView"""
    field: str
    title: str
    sheet_name: str = ""
    multi_select: bool = True
    search_enabled: bool = True


@dataclass
class PowerBISlicer:
    """Segment Power BI"""
    field: str
    table: str
    display_name: str
    slicer_type: str = "List"  # List, Dropdown, Tile
    multi_select: bool = True


class ListBoxMigrator:
    """Migration List Box → Segment"""
    
    # Mapping types de champs vers tables probables
    FIELD_TO_TABLE = {
        'year': 'Calendar',
        'month': 'Calendar',
        'quarter': 'Calendar',
        'date': 'Calendar',
        'product': 'Products',
        'category': 'Products',
        'customer': 'Customers',
        'region': 'Geography',
        'country': 'Geography',
        'city': 'Geography',
        'salesperson': 'Employees',
        'employee': 'Employees'
    }
    
    def __init__(self, output_dir: Path = None):
        self.output_dir = output_dir or Path('output/listboxes')
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def convert_listbox(self, listbox: QlikListBox) -> PowerBISlicer:
        """Convertit un list box en segment"""
        
        # Deviner la table
        table = self._guess_table(listbox.field)
        
        slicer = PowerBISlicer(
            field=listbox.field,
            table=table,
            display_name=listbox.title or listbox.field,
            slicer_type="List" if not listbox.search_enabled else "Dropdown",
            multi_select=listbox.multi_select
        )
        
        return slicer
    
    def _guess_table(self, field: str) -> str:
        """Devine la table depuis le nom du champ"""
        field_lower = field.lower()
        
        for keyword, table in self.FIELD_TO_TABLE.items():
            if keyword in field_lower:
                return table
        
        return "FactTable"
    
    def generate_slicer_config(self, slicers: List[PowerBISlicer]) -> str:
        """Génère configuration JSON pour segments"""
        
        config = {
            "slicers": [
                {
                    "field": s.field,
                    "table": s.table,
                    "displayName": s.display_name,
                    "type": s.slicer_type,
                    "multiSelect": s.multi_select
                }
                for s in slicers
            ]
        }
        
        output_file = self.output_dir / "slicer_config.json"
        with output_file.open('w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Configuration : {output_file}")
        return json.dumps(config, indent=2)
    
    def generate_guide(self) -> str:
        """Génère guide de création segments"""
        guide_file = self.output_dir / "SLICER_GUIDE.md"
        
        guide = """# Migration List Boxes → Segments Power BI

## Correspondances

| Objet Qlik | Power BI | Notes |
|------------|----------|-------|
| List Box | Segment (Liste) | Sélection multiple |
| Dropdown | Segment (Liste déroulante) | Économise l'espace |
| Multi Box | Plusieurs segments | Un par champ |
| Current Selections | Barre de filtres | Difficile actuelle |

## Création Manuelle

Pour chaque list box identifié dans `slicer_config.json` :

### 1. Ajouter le Segment

1. **Visualisations** → Icône **Segment**
2. Champ : Glisser le champ depuis la liste
3. Position : Placer sur le rapport

### 2. Configurer

**Format** → **Segment** :
- Type : Liste, Liste déroulante, ou Mosaïque
- Orientation : Verticale ou Horizontale
- Sélection multiple : OUI/NON
- Recherche : Activer si >50 valeurs

### 3. Style Visuel

- Couleur d'arrière-plan
- Bordures
- Taille de police
- Alignement

## Recommandations

**List Box avec recherche** → Segment Liste déroulante  
**List Box simple** → Segment Liste  
**Dimensions clés (Year, Region)** → Segment Mosaïque

## Synchronisation

Pour synchroniser plusieurs segments :
**Affichage** → **Synchroniser les segments**

"""
        
        guide_file.write_text(guide, encoding='utf-8')
        print(f"✅ Guide : {guide_file}")
        return guide


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Migration List Boxes")
    parser.add_argument('--example', action='store_true', help='Générer exemple')
    parser.add_argument('--output-dir', type=Path, default=Path('output/listboxes'))
    args = parser.parse_args()
    
    migrator = ListBoxMigrator(output_dir=args.output_dir)
    
    if args.example:
        # Exemple
        example_listboxes = [
            QlikListBox("Year", "Année", multi_select=True),
            QlikListBox("Region", "Région", multi_select=True),
            QlikListBox("Product", "Produit", multi_select=True, search_enabled=True)
        ]
        
        slicers = [migrator.convert_listbox(lb) for lb in example_listboxes]
        migrator.generate_slicer_config(slicers)
        migrator.generate_guide()
        
        print(f"\n✅ Exemple généré avec {len(slicers)} segments")
        print(f"📁 Fichiers dans : {args.output_dir}")
    else:
        print("Utilisez --example pour générer un exemple")
    
    return 0


if __name__ == '__main__':
    exit(main())
