"""
Migration des Qlik Stories vers PowerPoint

Ce module extrait les Stories Qlik Sense et génère une présentation PowerPoint
avec les snapshots et narrations.

Author: Migration Team
Date: 2026-02-13
"""

import json
import zipfile
import sys
from pathlib import Path
from typing import Dict, List, Optional
import argparse


def extract_stories_from_qvf(qvf_path: str) -> Dict:
    """
    Extrait les stories depuis un fichier QVF.
    
    Args:
        qvf_path: Chemin vers le fichier QVF
        
    Returns:
        Dictionnaire contenant les stories trouvées
    """
    stories_data = {
        "stories": [],
        "metadata": {
            "source_file": Path(qvf_path).name,
            "total_stories": 0,
            "total_slides": 0
        }
    }
    
    try:
        with zipfile.ZipFile(qvf_path, 'r') as qvf:
            # Lire app.json pour les stories
            if 'app.json' in qvf.namelist():
                app_data = json.loads(qvf.read('app.json').decode('utf-8'))
                
                # Extraire stories (qStoryList dans Qlik Sense)
                if 'qStoryList' in app_data:
                    for story in app_data['qStoryList']:
                        story_info = {
                            "id": story.get('qInfo', {}).get('qId', 'unknown'),
                            "title": story.get('qMetaDef', {}).get('title', 'Untitled Story'),
                            "description": story.get('qMetaDef', {}).get('description', ''),
                            "slides": []
                        }
                        
                        # Extraire slides de la story
                        if 'qStoryDef' in story and 'qSlides' in story['qStoryDef']:
                            for idx, slide in enumerate(story['qStoryDef']['qSlides'], 1):
                                slide_info = {
                                    "slide_number": idx,
                                    "title": slide.get('qMetaDef', {}).get('title', f'Slide {idx}'),
                                    "description": slide.get('qMetaDef', {}).get('description', ''),
                                    "items": []
                                }
                                
                                # Extraire items du slide (snapshots, text, images)
                                if 'qItems' in slide:
                                    for item in slide['qItems']:
                                        item_type = item.get('qType', 'unknown')
                                        item_info = {
                                            "type": item_type,
                                            "id": item.get('qId', ''),
                                            "position": item.get('qPosition', {})
                                        }
                                        
                                        if item_type == 'snapshot':
                                            item_info['snapshot_id'] = item.get('qSnapshotId', '')
                                        elif item_type == 'text':
                                            item_info['text'] = item.get('qText', '')
                                        
                                        slide_info['items'].append(item_info)
                                
                                story_info['slides'].append(slide_info)
                        
                        stories_data['stories'].append(story_info)
                        stories_data['metadata']['total_slides'] += len(story_info['slides'])
                
                stories_data['metadata']['total_stories'] = len(stories_data['stories'])
                
    except zipfile.BadZipFile:
        print(f"❌ Erreur: {qvf_path} n'est pas un fichier QVF valide")
        return stories_data
    except Exception as e:
        print(f"❌ Erreur lors de l'extraction: {str(e)}")
        return stories_data
    
    return stories_data


def generate_powerpoint_script(stories_data: Dict, output_dir: Path) -> str:
    """
    Génère un script PowerShell pour créer une présentation PowerPoint.
    
    Args:
        stories_data: Données des stories extraites
        output_dir: Répertoire de sortie
        
    Returns:
        Chemin du fichier script généré
    """
    script_path = output_dir / "create_presentation.ps1"
    
    script_content = """# Script PowerShell pour créer une présentation PowerPoint depuis Qlik Stories
# Généré automatiquement par migrate_stories.py

# Vérifier PowerPoint est installé
try {
    $PowerPoint = New-Object -ComObject PowerPoint.Application
} catch {
    Write-Host "❌ PowerPoint n'est pas installé sur ce système" -ForegroundColor Red
    exit 1
}

$PowerPoint.Visible = $true

# Créer nouvelle présentation
$Presentation = $PowerPoint.Presentations.Add()

"""
    
    # Générer slides pour chaque story
    for story in stories_data['stories']:
        script_content += f"""
# Story: {story['title']}
# Description: {story['description']}

"""
        for slide_info in story['slides']:
            script_content += f"""
# Slide {slide_info['slide_number']}: {slide_info['title']}
$Slide = $Presentation.Slides.Add($Presentation.Slides.Count + 1, 1)  # ppLayoutText
$Slide.Shapes.Title.TextFrame.TextRange.Text = "{slide_info['title']}"

"""
            # Ajouter description si présente
            if slide_info['description']:
                script_content += f"""$Slide.Shapes[2].TextFrame.TextRange.Text = "{slide_info['description']}"

"""
            
            # Ajouter notes sur les items du slide
            if slide_info['items']:
                items_text = f"Items du slide ({len(slide_info['items'])}):\\n"
                for item in slide_info['items']:
                    items_text += f"- {item['type']}\\n"
                
                script_content += f"""# Notes: {items_text}
$Slide.NotesPage.Shapes[2].TextFrame.TextRange.Text = "{items_text}"

"""
    
    # Sauvegarder présentation
    script_content += f"""
# Sauvegarder présentation
$OutputPath = "{output_dir.absolute()}\\qlik_stories.pptx"
$Presentation.SaveAs($OutputPath)

Write-Host "✅ Présentation créée: $OutputPath" -ForegroundColor Green

# Fermer PowerPoint
$Presentation.Close()
$PowerPoint.Quit()

[System.Runtime.Interopservices.Marshal]::ReleaseComObject($PowerPoint) | Out-Null
Remove-Variable PowerPoint
"""
    
    # Écrire le script
    with open(script_path, 'w', encoding='utf-8') as f:
        f.write(script_content)
    
    return str(script_path)


def generate_stories_config(stories_data: Dict, output_dir: Path) -> str:
    """
    Génère un fichier JSON de configuration des stories.
    
    Args:
        stories_data: Données des stories
        output_dir: Répertoire de sortie
        
    Returns:
        Chemin du fichier de configuration
    """
    config_path = output_dir / "stories_config.json"
    
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(stories_data, f, indent=2, ensure_ascii=False)
    
    return str(config_path)


def generate_markdown_guide(stories_data: Dict, output_dir: Path) -> str:
    """
    Génère un guide markdown pour la migration des stories.
    
    Args:
        stories_data: Données des stories
        output_dir: Répertoire de sortie
        
    Returns:
        Chemin du guide généré
    """
    guide_path = output_dir / "STORIES_MIGRATION_GUIDE.md"
    
    guide_content = f"""# 📊 Guide de Migration - Qlik Stories vers PowerPoint

**Date de génération :** 13 février 2026  
**Fichier source :** {stories_data['metadata']['source_file']}  
**Stories trouvées :** {stories_data['metadata']['total_stories']}  
**Slides totaux :** {stories_data['metadata']['total_slides']}

---

## 📋 Résumé des Stories

"""
    
    for idx, story in enumerate(stories_data['stories'], 1):
        guide_content += f"""
### Story {idx}: {story['title']}

**Description :** {story['description'] or 'Aucune description'}  
**Nombre de slides :** {len(story['slides'])}

"""
        
        for slide in story['slides']:
            guide_content += f"""
#### Slide {slide['slide_number']}: {slide['title']}
- **Description :** {slide['description'] or 'Aucune'}
- **Éléments :** {len(slide['items'])} items
"""
            if slide['items']:
                for item in slide['items']:
                    guide_content += f"  - {item['type']}"
                    if item['type'] == 'text' and 'text' in item:
                        guide_content += f": {item['text'][:50]}..."
                    guide_content += "\n"
    
    guide_content += """

---

## 🚀 Migration vers PowerPoint

### Approche 1 : Script PowerShell Automatique (Recommandé)

1. **Exécuter le script PowerShell généré :**
   ```powershell
   .\\create_presentation.ps1
   ```

2. **Résultat :**
   - Fichier `qlik_stories.pptx` créé
   - Un slide par page de story
   - Titres et descriptions conservés

### Approche 2 : Export Manuel depuis Qlik Sense

1. **Ouvrir l'application dans Qlik Sense**
2. **Pour chaque Story :**
   - Ouvrir la Story
   - Menu → Export → PowerPoint
   - Sauvegarder le fichier

3. **Fusionner les présentations** (optionnel)

### Approche 3 : Recréer dans Power BI (Slides App)

**Alternative :** Utiliser une application Power BI avec navigation type "slideshow"

**Avantages :**
- Données dynamiques (vs statiques PowerPoint)
- Interaction avec les visuels
- Actualisation automatique

**Limitations :**
- Pas de narration story comme Qlik
- Nécessite création manuelle des "pages"

---

## 📊 Comparaison Qlik Stories vs Alternatives

| Caractéristique | Qlik Stories | PowerPoint | Power BI Slides App |
|-----------------|--------------|------------|---------------------|
| **Narration guidée** | ✅ Excellente | ✅ Bonne | ⚠️ Limitée |
| **Snapshots dynamiques** | ✅ | ❌ Statiques | ✅ |
| **Annotations** | ✅ | ✅ | ⚠️ Limitées |
| **Export facile** | ✅ | ✅ | ⚠️ Embed only |
| **Collaboration** | ✅ | ✅ | ✅ |
| **Données temps réel** | ❌ | ❌ | ✅ |

---

## ✅ Checklist de Migration

- [ ] Exécuter `create_presentation.ps1`
- [ ] Vérifier titres et descriptions
- [ ] Ajouter images/graphiques manuellement si nécessaire
- [ ] Re-capturer snapshots depuis Power BI (si données dynamiques)
- [ ] Tester présentation complète
- [ ] Partager avec utilisateurs finaux

---

## 💡 Recommandations

1. **Pour présentations statiques :**
   - Utiliser PowerPoint généré
   - Ajouter screenshots Power BI

2. **Pour présentations dynamiques :**
   - Créer rapport Power BI avec navigation
   - Utiliser boutons "Next/Previous"
   - Bookmarks pour chaque "slide"

3. **Contenu mixte :**
   - PowerPoint pour narration
   - Liens vers rapports Power BI pour exploration

---

## 📞 Support

Pour questions ou problèmes, consulter :
- [Power BI Best Practices](https://docs.microsoft.com/power-bi/)
- [PowerPoint Automation](https://docs.microsoft.com/office/vba/powerpoint)

---

**✨ Guide généré automatiquement par migrate_stories.py**
"""
    
    with open(guide_path, 'w', encoding='utf-8') as f:
        f.write(guide_content)
    
    return str(guide_path)


def main():
    parser = argparse.ArgumentParser(
        description="Migrer Qlik Stories vers PowerPoint"
    )
    parser.add_argument(
        "qvf_path",
        nargs='?',
        help="Chemin vers le fichier QVF"
    )
    parser.add_argument(
        "--output-dir",
        default="output/stories",
        help="Répertoire de sortie (défaut: output/stories)"
    )
    parser.add_argument(
        "--example",
        action="store_true",
        help="Générer un guide d'exemple sans QVF"
    )
    
    args = parser.parse_args()
    
    # Créer répertoire de sortie
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    if args.example or not args.qvf_path:
        # Générer exemple
        print("📊 Génération d'un guide d'exemple...")
        example_data = {
            "stories": [
                {
                    "id": "example-1",
                    "title": "Sales Performance Story",
                    "description": "Q4 sales analysis and trends",
                    "slides": [
                        {
                            "slide_number": 1,
                            "title": "Overview",
                            "description": "Q4 2025 Summary",
                            "items": [
                                {"type": "snapshot", "id": "snap1"},
                                {"type": "text", "text": "Sales increased 15% YoY"}
                            ]
                        },
                        {
                            "slide_number": 2,
                            "title": "Regional Performance",
                            "description": "Sales by region",
                            "items": [
                                {"type": "snapshot", "id": "snap2"}
                            ]
                        }
                    ]
                }
            ],
            "metadata": {
                "source_file": "example.qvf",
                "total_stories": 1,
                "total_slides": 2
            }
        }
    else:
        # Extraire depuis QVF
        qvf_path = args.qvf_path
        if not Path(qvf_path).exists():
            print(f"❌ Fichier introuvable: {qvf_path}")
            return 1
        
        print(f"📂 Lecture de {qvf_path}...")
        example_data = extract_stories_from_qvf(qvf_path)
        
        if example_data['metadata']['total_stories'] == 0:
            print("⚠️ Aucune story trouvée dans ce fichier QVF")
            print("💡 Conseil: Les stories sont spécifiques à Qlik Sense.")
            return 0
    
    # Générer fichiers de sortie
    print(f"\n📝 Génération des fichiers de sortie...")
    
    config_file = generate_stories_config(example_data, output_dir)
    print(f"✅ Configuration: {config_file}")
    
    script_file = generate_powerpoint_script(example_data, output_dir)
    print(f"✅ Script PowerShell: {script_file}")
    
    guide_file = generate_markdown_guide(example_data, output_dir)
    print(f"✅ Guide: {guide_file}")
    
    print(f"\n🎯 Résumé:")
    print(f"  Stories trouvées: {example_data['metadata']['total_stories']}")
    print(f"  Slides totaux: {example_data['metadata']['total_slides']}")
    
    print(f"\n📊 Prochaines étapes:")
    print(f"  1. Exécuter: {script_file}")
    print(f"  2. Ouvrir: {output_dir}\\qlik_stories.pptx")
    print(f"  3. Consulter: {guide_file}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
