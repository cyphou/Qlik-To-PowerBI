#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Migration Thèmes et Couleurs Qlik vers Power BI
Extrait palettes de couleurs et thème visuel
"""

import json
import zipfile
from pathlib import Path
from typing import Dict, List
import re


class ThemeMigrator:
    """Migration thème Qlik → Power BI"""
    
    def __init__(self, output_dir: Path = None):
        self.output_dir = output_dir or Path('output/theme')
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.colors: List[str] = []
        self.theme_config: Dict = {}
    
    def extract_theme(self, qvf_path: Path) -> Dict:
        """Extrait le thème d'un QVF"""
        print(f"🎨 Extraction thème depuis : {qvf_path}")
        
        try:
            with zipfile.ZipFile(qvf_path, 'r') as qvf:
                if 'app.json' in qvf.namelist():
                    app_data = json.loads(qvf.read('app.json').decode('utf-8'))
                    
                    # Chercher configurations de couleurs
                    if 'properties' in app_data:
                        theme = app_data['properties'].get('theme', {})
                        self.theme_config = theme
                        
                        # Extraire palette
                        if 'dataColors' in theme:
                            self.colors = theme['dataColors']
                        elif 'properties' in theme and 'dataColors' in theme['properties']:
                            self.colors = theme['properties']['dataColors']
            
            print(f"✅ Thème extrait : {len(self.colors)} couleurs")
        except Exception as e:
            print(f"⚠️ Extraction partielle : {e}")
        
        return self.theme_config
    
    def generate_powerbi_theme(self, output_file: Path = None) -> Dict:
        """Génère fichier JSON thème Power BI"""
        output_file = output_file or self.output_dir / "theme.json"
        
        # Template thème Power BI
        theme = {
            "name": "Qlik Theme Migrated",
            "dataColors": self.colors if self.colors else [
                "#4477AA", "#EE6677", "#228833", "#CCBB44", 
                "#66CCEE", "#AA3377", "#BBBBBB"
            ],
            "background": "#FFFFFF",
            "foreground": "#333333",
            "tableAccent": "#4477AA",
            "good": "#228833",
            "neutral": "#CCBB44",
            "bad": "#EE6677",
            "maximum": "#EE6677",
            "center": "#CCBB44",
            "minimum": "#228833",
            "visualStyles": {
                "*": {
                    "*": {
                        "border": [{"show": True, "color": {"solid": {"color": "#E0E0E0"}}}],
                        "background": [{"show": True, "color": {"solid": {"color": "#FFFFFF"}}}]
                    }
                }
            }
        }
        
        with output_file.open('w', encoding='utf-8') as f:
            json.dump(theme, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Thème Power BI : {output_file}")
        return theme
    
    def generate_color_palette_html(self, output_file: Path = None) -> str:
        """Génère aperçu HTML des couleurs"""
        output_file = output_file or self.output_dir / "color_palette.html"
        
        html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Palette de Couleurs Qlik → Power BI</title>
    <style>
        body { font-family: 'Segoe UI', sans-serif; padding: 20px; background: #f5f5f5; }
        h1 { color: #333; }
        .palette { display: flex; flex-wrap: wrap; gap: 10px; margin: 20px 0; }
        .color { 
            width: 120px; 
            height: 120px; 
            border-radius: 8px; 
            display: flex; 
            flex-direction: column;
            align-items: center; 
            justify-content: center;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            color: white;
            text-shadow: 1px 1px 2px rgba(0,0,0,0.5);
            font-weight: bold;
        }
        .color-code { font-size: 12px; margin-top: 5px; }
        .instructions { background: white; padding: 20px; border-radius: 8px; margin-top: 20px; }
    </style>
</head>
<body>
    <h1>🎨 Palette de Couleurs Migrée</h1>
    <p>Couleurs extraites de l'application Qlik</p>
    
    <div class="palette">
"""
        
        for i, color in enumerate(self.colors or [], 1):
            html += f'        <div class="color" style="background-color: {color};">\n'
            html += f'            <div>Couleur {i}</div>\n'
            html += f'            <div class="color-code">{color}</div>\n'
            html += f'        </div>\n'
        
        html += """    </div>
    
    <div class="instructions">
        <h2>📋 Utilisation dans Power BI</h2>
        <ol>
            <li>Ouvrir Power BI Desktop</li>
            <li><strong>Affichage</strong> → <strong>Thèmes</strong> → <strong>Parcourir les thèmes</strong></li>
            <li>Sélectionner le fichier <code>theme.json</code></li>
            <li>Le thème sera appliqué à tous les visuels</li>
        </ol>
        
        <h3>Modification Manuelle</h3>
        <p>Vous pouvez éditer <code>theme.json</code> pour :</p>
        <ul>
            <li>Ajouter/modifier les couleurs de données</li>
            <li>Changer les couleurs d'arrière-plan</li>
            <li>Personnaliser les styles de visuels</li>
        </ul>
        
        <h3>Documentation</h3>
        <p><a href="https://learn.microsoft.com/power-bi/create-reports/desktop-report-themes">Guide Microsoft - Thèmes Power BI</a></p>
    </div>
</body>
</html>
"""
        
        output_file.write_text(html, encoding='utf-8')
        print(f"✅ Aperçu HTML : {output_file}")
        return html
    
    def generate_guide(self, output_file: Path = None) -> str:
        """Génère guide migration thème"""
        output_file = output_file or self.output_dir / "THEME_GUIDE.md"
        
        guide = f"""# Migration Thème Qlik → Power BI

## Palette Extraite

**Nombre de couleurs :** {len(self.colors)}

Couleurs :
"""
        
        for i, color in enumerate(self.colors, 1):
            guide += f"{i}. {color}\n"
        
        guide += """
---

## Application du Thème

### Méthode 1 : Fichier JSON (Recommandé)

1. Ouvrir Power BI Desktop
2. **Affichage** → **Thèmes** → **Parcourir les thèmes**
3. Sélectionner `theme.json`
4. Cliquer **Ouvrir**

Le thème s'applique automatiquement à tous les visuels du rapport.

### Méthode 2 : Couleurs Manuelles

Si vous préférez appliquer les couleurs manuellement :

1. Sélectionner un visuel
2. **Format** → **Couleurs de données**
3. Choisir les couleurs depuis la palette extraite

---

## Personnalisation

Le fichier `theme.json` peut être édité pour :

### Couleurs de Données

```json
"dataColors": [
    "#4477AA",  // Couleur 1
    "#EE6677",  // Couleur 2
    ...
]
```

### Couleurs de Fond

```json
"background": "#FFFFFF",
"foreground": "#333333"
```

### Couleurs Conditionnelles

```json
"good": "#228833",      // Vert (positif)
"neutral": "#CCBB44",   // Jaune (neutre)
"bad": "#EE6677"        // Rouge (négatif)
```

---

## Aperçu Visuel

Ouvrez `color_palette.html` dans un navigateur pour voir les couleurs.

---

## Fichiers Générés

| Fichier | Description |
|---------|-------------|
| `theme.json` | Thème Power BI prêt à importer |
| `color_palette.html` | Aperçu visuel des couleurs |
| `THEME_GUIDE.md` | Ce guide |

---

## Ressources

- [Documentation Microsoft - Thèmes](https://learn.microsoft.com/power-bi/create-reports/desktop-report-themes)
- [Galerie de thèmes Power BI](https://community.powerbi.com/t5/Themes-Gallery/bd-p/ThemesGallery)

---

**✨ Fichiers dans :** `{self.output_dir}`
"""
        
        output_file.write_text(guide, encoding='utf-8')
        print(f"✅ Guide : {output_file}")
        return guide


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Migration Thème Qlik → Power BI")
    parser.add_argument('qvf_file', type=Path, help='Fichier QVF')
    parser.add_argument('--output-dir', type=Path, default=Path('output/theme'))
    args = parser.parse_args()
    
    if not args.qvf_file.exists():
        print(f"❌ Fichier non trouvé : {args.qvf_file}")
        return 1
    
    print("🎨 Migration Thème Qlik → Power BI\n")
    print("=" * 60)
    
    migrator = ThemeMigrator(output_dir=args.output_dir)
    
    # Extraction
    migrator.extract_theme(args.qvf_file)
    
    # Génération
    print("\n📝 Génération des fichiers...")
    migrator.generate_powerbi_theme()
    migrator.generate_color_palette_html()
    migrator.generate_guide()
    
    # Résumé
    print("\n" + "=" * 60)
    print("✅ Migration terminée !")
    print(f"🎨 Thème avec {len(migrator.colors)} couleurs")
    print(f"📁 Fichiers dans : {args.output_dir}")
    print("\n💡 Ouvrez color_palette.html pour voir les couleurs")
    
    return 0


if __name__ == '__main__':
    exit(main())
