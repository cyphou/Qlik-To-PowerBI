"""
Migration des Qlik Sheet Actions vers Boutons Power BI

Ce module extrait les Sheet Actions Qlik et génère une documentation
pour la création de boutons de navigation Power BI.

Author: Migration Team
Date: 2026-02-13
"""

import json
import zipfile
from pathlib import Path
from typing import Dict, List
import argparse


def extract_sheet_actions_from_qvf(qvf_path: str) -> Dict:
    """
    Extrait les sheet actions depuis un fichier QVF.
    
    Args:
        qvf_path: Chemin vers le fichier QVF
        
    Returns:
        Dictionnaire contenant les sheet actions trouvées
    """
    actions_data = {
        "sheet_actions": [],
        "navigation_patterns": [],
        "metadata": {
            "source_file": Path(qvf_path).name,
            "total_actions": 0,
            "total_sheets": 0
        }
    }
    
    try:
        with zipfile.ZipFile(qvf_path, 'r') as qvf:
            if 'app.json' in qvf.namelist():
                app_data = json.loads(qvf.read('app.json').decode('utf-8'))
                
                # Extraire feuilles et leurs actions
                if 'qSheetList' in app_data:
                    for sheet in app_data['qSheetList']:
                        sheet_id = sheet.get('qInfo', {}).get('qId')
                        sheet_title = sheet.get('qMetaDef', {}).get('title', 'Untitled')
                        
                        sheet_actions = {
                            "sheet_id": sheet_id,
                            "sheet_title": sheet_title,
                            "actions": []
                        }
                        
                        # Extraire actions de la feuille
                        if 'qSheetDef' in sheet and 'qMetaDef' in sheet['qSheetDef']:
                            meta = sheet['qSheetDef']['qMetaDef']
                            
                            # Chercher les actions personnalisées
                            if 'actions' in meta:
                                for action in meta['actions']:
                                    action_info = {
                                        "id": action.get('id'),
                                        "label": action.get('label', 'Action'),
                                        "type": action.get('type', 'unknown'),
                                        "target": {}
                                    }
                                    
                                    # Déterminer le type d'action
                                    if 'navigation' in action:
                                        nav = action['navigation']
                                        if 'targetSheetId' in nav:
                                            action_info['target']['type'] = 'sheet'
                                            action_info['target']['sheet_id'] = nav['targetSheetId']
                                        elif 'targetUri' in nav:
                                            action_info['target']['type'] = 'url'
                                            action_info['target']['url'] = nav['targetUri']
                                    
                                    sheet_actions['actions'].append(action_info)
                        
                        if sheet_actions['actions']:
                            actions_data['sheet_actions'].append(sheet_actions)
                            actions_data['metadata']['total_actions'] += len(sheet_actions['actions'])
                    
                    actions_data['metadata']['total_sheets'] = len(app_data['qSheetList'])
                    
    except zipfile.BadZipFile:
        print(f"❌ Erreur: {qvf_path} n'est pas un fichier QVF valide")
    except Exception as e:
        print(f"❌ Erreur lors de l'extraction: {str(e)}")
    
    return actions_data


def generate_power_bi_button_guide(actions_data: Dict, output_dir: Path) -> str:
    """
    Génère un guide pour créer des boutons Power BI.
    
    Args:
        actions_data: Données des actions extraites
        output_dir: Répertoire de sortie
        
    Returns:
        Chemin du guide généré
    """
    guide_path = output_dir / "NAVIGATION_BUTTONS_GUIDE.md"
    
    guide_content = f"""# 🔘 Guide Navigation - Qlik Sheet Actions vers Power BI

**Date de génération :** 13 février 2026  
**Fichier source :** {actions_data['metadata']['source_file']}  
**Actions trouvées :** {actions_data['metadata']['total_actions']}  
**Feuilles avec actions :** {len(actions_data['sheet_actions'])}

---

## 📋 Actions Détectées

"""
    
    for sheet_action in actions_data['sheet_actions']:
        guide_content += f"""
### Feuille: {sheet_action['sheet_title']}

| Action | Type | Cible |
|--------|------|-------|
"""
        for action in sheet_action['actions']:
            target_text = "N/A"
            if action['target']:
                if action['target']['type'] == 'sheet':
                    target_text = f"Sheet: {action['target'].get('sheet_id', '?')}"
                elif action['target']['type'] == 'url':
                    target_text = f"URL: {action['target'].get('url', '?')}"
            
            guide_content += f"| {action['label']} | {action['type']} | {target_text} |\n"
    
    guide_content += """

---

## 🎯 Approches de Migration

### Approche 1 : Boutons de Navigation (Recommandé)

**Avantages :**
- ✅ Expérience utilisateur similaire à Qlik
- ✅ Navigation fluide
- ✅ Facile à créer

**Étapes :**
1. **Créer des Pages** pour chaque "feuille Qlik"
   - Page 1: Vue Vue des ventes
   - Page 2: Vue Inventaire
   - etc.

2. **Ajouter des Boutons**
   - Insérer → Bouton
   - Définir Action (Navigation vers page)
   - Placer en haut/côté du rapport

3. **DAX pour Paramètres Dynamiques**
   ```dax
   -- Afficher/masquer boutons selon permissions
   Page_Visible = 
   IF( 
       USERPRINCIPALNAME() = "user@company.com", 
       TRUE, 
       FALSE 
   )
   ```

### Approche 2 : Bookmarks (Alternative)

**Avantages :**
- ✅ Très rapide à créer
- ✅ Chaque bookmark = un état visuel

**Étapes :**
1. Créer bookmarks pour chaque "vue" Qlik
2. Ajouter boutons qui activent bookmarks
3. Personnaliser apparence boutons

### Approche 3 : Pages Dynamiques

**Avantages :**
- ✅ Très flexible
- ✅ Cachage intelligent

**Étapes :**
1. Créer paramètre `SelectedPage`
   ```dax
   SelectedPage = {"Sales", "Inventory", "Marketing"}
   ```

2. Masquer/Afficher pages conditionnellement
3. Boutons changent la valeur de `SelectedPage`

---

## 🛠️ Implémentation Détaillée

### Créer Boutons de Navigation

#### Étape 1: Préparer les Pages

1. Ouvrir Power BI Desktop
2. Créer pages pour chaque destination Qlik
3. Nommer les pages clairement
   ```
   Pages:
   - Page d'accueil
   - Ventes
   - Inventaire
   - Rapports
   ```

#### Étape 2: Ajouter des Boutons

**Dans Power BI Desktop :**

1. Aller sur page d'accueil
2. Insérer → Bouton
3. Configurer:
   - Style du bouton
   - Texte: "Aller à Ventes"
   - Couleur personnalisée

4. Ajouter action:
   - Type d'action: Page navigation
   - Destination: "Ventes"

#### Étape 3: Formatage

**Code Power Query pour style boutons :**
```powerquery
let
    Buttons = Table.FromRecords({
        [Label="Ventes", Color="#4477AA"],
        [Label="Inventaire", Color="#66CCEE"],
        [Label="Rapports", Color="#228833"]
    })
in
    Buttons
```

---

## 📊 Comparaison: Qlik Sheet Actions vs Power BI

| Fonctionnalité | Qlik | Power BI |
|----------------|------|----------|
| **Navigation directe** | ✅ Natives | ⚠️ Via boutons |
| **Actions contextuelles** | ✅ | ⚠️ Limitées |
| **Signets** | ✅ Marque-pages | ✅ Bookmarks |
| **Filtres à la navigation** | ✅ | ✅ Via DAX |
| **Facilité création** | ✅⭐⭐⭐ | ⚠️⭐⭐ |
| **Flexibilité** | ✅ | ✅⭐⭐⭐ |

---

## 💻 Exemples de Code DAX

### Navigation Conditionnelle

```dax
-- Mesure pour afficher/masquer bouton
Can_Access_Sales = 
IF(
    OR(
        USERPRINCIPALNAME() = "admin@company.com",
        CONTAINS(
            MemberRoles,
            "GroupId",
            VALUE(
                GENERATESERIES(1, 10) -- Simule lookup rôles
            )
        )
    ),
    TRUE,
    FALSE
)
```

### Déterminer la Page Actuelle

```dax
Current_Page = 
VAR PageList = {
    ("Sales", 1),
    ("Inventory", 2),
    ("Reports", 3)
}
VAR UserAccess = CALCULATETABLE(PageList)
RETURN
    FIRSTNONBLANK(UserAccess, 1)
```

---

## ✅ Checklist de Migration

- [ ] Identifier toutes les Sheet Actions Qlik
- [ ] Lister les destinations (inter-feuilles, URLs, etc.)
- [ ] Créer pages Power BI correspondantes
- [ ] Ajouter boutons de navigation
- [ ] Tester navigation complète
- [ ] Configurer permissions d'accès
- [ ] Former utilisateurs
- [ ] Tester en production

---

## 🎨 Best Practices

1. **Cohérence Visuelle**
   - Utiliser même style/couleur boutons
   - Placer boutons même endroit chaque page
   - Icônes intuitives

2. **Hiérarchie d'Information**
   - Bouton "Retour" bien visible
   - Navigation logique (tableau de bord → détails)
   - Miettes de pain (breadcrumbs)

3. **Performance**
   - Éviter trop de boutons (max 5-6)
   - Boutons = navigation critique only
   - URLs externes en popup

4. **Accessibility**
   - Alt text pour boutons
   - Contraste couleurs suffisant
   - Keyboard navigation

---

## 📚 Ressources

- [Power BI Navigation Techniques](https://docs.microsoft.com/power-bi/)
- [Buttons in Power BI](https://learn.microsoft.com/power-bi/create-reports/desktop-buttons)
- [Page Navigation](https://learn.microsoft.com/power-bi/create-reports/desktop-page-navigation)

---

**✨ Guide généré automatiquement par migrate_navigation.py**
"""
    
    with open(guide_path, 'w', encoding='utf-8') as f:
        f.write(guide_content)
    
    return str(guide_path)


def generate_actions_config(actions_data: Dict, output_dir: Path) -> str:
    """
    Génère un fichier JSON de configuration des actions.
    
    Args:
        actions_data: Données des actions
        output_dir: Répertoire de sortie
        
    Returns:
        Chemin du fichier de configuration
    """
    config_path = output_dir / "navigation_config.json"
    
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(actions_data, f, indent=2, ensure_ascii=False)
    
    return str(config_path)


def main():
    parser = argparse.ArgumentParser(
        description="Migrer Qlik Sheet Actions vers Boutons Power BI"
    )
    parser.add_argument(
        "qvf_path",
        nargs='?',
        help="Chemin vers le fichier QVF"
    )
    parser.add_argument(
        "--output-dir",
        default="output/navigation",
        help="Répertoire de sortie (défaut: output/navigation)"
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
        print("🔘 Génération d'un guide d'exemple...")
        example_data = {
            "sheet_actions": [
                {
                    "sheet_id": "sheet1",
                    "sheet_title": "Sales Dashboard",
                    "actions": [
                        {
                            "id": "nav_detail",
                            "label": "View Details",
                            "type": "navigation",
                            "target": {"type": "sheet", "sheet_id": "sheet2"}
                        }
                    ]
                },
                {
                    "sheet_id": "sheet2",
                    "sheet_title": "Sales Details",
                    "actions": [
                        {
                            "id": "nav_back",
                            "label": "Back to Dashboard",
                            "type": "navigation",
                            "target": {"type": "sheet", "sheet_id": "sheet1"}
                        }
                    ]
                }
            ],
            "navigation_patterns": [
                "Dashboard → Details",
                "Details → Dashboard",
                "Dashboard → External Link"
            ],
            "metadata": {
                "source_file": "example.qvf",
                "total_actions": 2,
                "total_sheets": 2
            }
        }
    else:
        # Extraire depuis QVF
        qvf_path = args.qvf_path
        if not Path(qvf_path).exists():
            print(f"❌ Fichier introuvable: {qvf_path}")
            return 1
        
        print(f"📂 Lecture de {qvf_path}...")
        example_data = extract_sheet_actions_from_qvf(qvf_path)
        
        if example_data['metadata']['total_actions'] == 0:
            print("⚠️ Aucune Sheet Action trouvée")
            print("💡 Conseil: Les Sheet Actions sont courantes en QlikView.")
    
    # Générer fichiers
    print(f"\n📝 Génération des fichiers de sortie...")
    
    config_file = generate_actions_config(example_data, output_dir)
    print(f"✅ Configuration: {config_file}")
    
    guide_file = generate_power_bi_button_guide(example_data, output_dir)
    print(f"✅ Guide: {guide_file}")
    
    print(f"\n🎯 Résumé:")
    print(f"  Actions trouvées: {example_data['metadata']['total_actions']}")
    print(f"  Feuilles: {example_data['metadata']['total_sheets']}")
    
    print(f"\n📊 Prochaines étapes:")
    print(f"  1. Consulter: {guide_file}")
    print(f"  2. Créer pages Power BI")
    print(f"  3. Ajouter boutons de navigation")
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
