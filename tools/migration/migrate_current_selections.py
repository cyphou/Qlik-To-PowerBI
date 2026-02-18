#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Générateur Current Selections Bar pour Power BI
Crée un visuel de filtres actifs similaire à Qlik
"""

from pathlib import Path
import json


class CurrentSelectionsGenerator:
    """Génère configuration pour barre de sélections actives"""
    
    def __init__(self, output_dir: Path = None):
        self.output_dir = output_dir or Path('output/selections')
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_dax_table(self, fields: list = None) -> str:
        """Génère table DAX pour afficher sélections"""
        
        if not fields:
            fields = ['Date', 'Product', 'Region', 'Customer']
        
        dax = """// Table DAX pour Current Selections
// Crée une table calculée affichant les filtres actifs

Current Selections = 
UNION(
"""
        
        for i, field in enumerate(fields):
            dax += f"""    SELECTCOLUMNS(
        DISTINCT({field}[{field}]),
        "Field", "{field}",
        "Value", {field}[{field}]
    )"""
            if i < len(fields) - 1:
                dax += ",\n"
        
        dax += "\n)\n"
        
        output_file = self.output_dir / "current_selections.dax"
        output_file.write_text(dax, encoding='utf-8')
        print(f"✅ Table DAX : {output_file}")
        
        return dax
    
    def generate_guide(self) -> str:
        """Génère guide de création"""
        
        guide = """# Current Selections - Barre de Filtres Actifs

## Équivalent Qlik → Power BI

**Qlik :** Current Selections Box affiche automatiquement les sélections actives  
**Power BI :** Nécessite configuration manuelle de la barre de filtres

---

## Solution 1 : Barre de Filtres Native (Simple)

### Activation

1. **Affichage** → **Volet Filtres**
2. Le volet affiche les filtres appliqués
3. Les utilisateurs voient les sélections

**Avantages :**
- Aucune configuration requise
- Fonctionne automatiquement

**Inconvénients :**
- Position fixe (côté droit)
- Style limité

---

## Solution 2 : Table Calculée (Avancé)

Pour un visuel similaire à Qlik Current Selections :

### 1. Créer Table Calculée

**Modélisation** → **Nouvelle table**

Copier le code DAX depuis `current_selections.dax`

### 2. Créer Visuel Table

1. Ajouter visuel **Table**
2. Champs : `Field`, `Value`
3. Positionner en haut du rapport

### 3. Formater

**Format visuel :**
- Arrière-plan : Gris clair
- Bordures : Activées
- Style condensé
- Police : 10-11pt

### 4. Synchroniser Filtres

Les

 filtres appliqués s'afficheront automatiquement dans la table.

---

## Solution 3 : Custom Visual (Optimal)

Utiliser un custom visual de la marketplace :

1. **Insérer** → **Obtenir plus de visuels**
2. Chercher "Filter Panel" ou "Advanced Filter"
3. Installer et configurer

**Recommandations :**
- [Filter Panel](https://appsource.microsoft.com/product/power-bi-visuals/...)
- Advanced Slicer Panel
- Filter Display

---

## Comparaison

| Fonctionnalité | Qlik | Power BI Natif | Table Calculée | Custom Visual |
|----------------|------|----------------|----------------|---------------|
| Auto-display | ✅ | ✅ | ⚠️ | ✅ |
| Personnalisable | ⚠️ | ❌ | ✅ | ✅ |
| Position libre | ❌ | ❌ | ✅ | ✅ |
| Aucun code | ✅ | ✅ | ❌ | ✅ |

---

## Exemple Configuration

Pour afficher sélections sur champs : Year, Product, Region

```dax
Current Selections = 
UNION(
    SELECTCOLUMNS(DISTINCT(Calendar[Year]), "Field", "Year", "Value", Calendar[Year]),
    SELECTCOLUMNS(DISTINCT(Products[Product]), "Field", "Product", "Value", Products[Product]),
    SELECTCOLUMNS(DISTINCT(Geography[Region]), "Field", "Region", "Value", Geography[Region])
)
```

**Utilisation :**
- Créer visuel Table
- Ajouter colonnes Field et Value
- Les filtres actifs s'affichent automatiquement

---

## Limites

⚠️ **Différence vs Qlik :**
- Power BI ne capture pas dynamiquement toutes les sélections comme Qlik
- Nécessite liste explicite de champs
- Pas de "clear all" intégré

**Solution :**
- Utiliser boutons "Effacer filtres" natifs de Power BI
- Configurer liste de champs importants

---

**✨ Fichiers générés dans :** `output/selections/`
"""
        
        guide_file = self.output_dir / "CURRENT_SELECTIONS_GUIDE.md"
        guide_file.write_text(guide, encoding='utf-8')
        print(f"✅ Guide : {guide_file}")
        
        return guide


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Générateur Current Selections")
    parser.add_argument('--fields', nargs='+', help='Liste de champs à monitorer')
    parser.add_argument('--output-dir', type=Path, default=Path('output/selections'))
    args = parser.parse_args()
    
    print("🔍 Générateur Current Selections\n")
    print("=" * 60)
    
    generator = CurrentSelectionsGenerator(output_dir=args.output_dir)
    
    # Génération
    print("\n📝 Génération des fichiers...")
    generator.generate_dax_table(fields=args.fields)
    generator.generate_guide()
    
    # Résumé
    print("\n" + "=" * 60)
    print("✅ Génération terminée !")
    print(f"📁 Fichiers dans : {args.output_dir}")
    print("\n💡 Consultez CURRENT_SELECTIONS_GUIDE.md pour les options")
    
    return 0


if __name__ == '__main__':
    exit(main())
