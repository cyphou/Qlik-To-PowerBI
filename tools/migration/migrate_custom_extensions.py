"""Migration - Custom Extensions vers Power BI Custom Visuals"""
import json
from pathlib import Path
def generate_custom_visuals_guide(output_dir: Path) -> str:
    guide_path = output_dir / "CUSTOM_VISUALS_MIGRATION_GUIDE.md"
    content = """# 🎨 Guide Migration - Qlik Extensions vers Custom Visuals Power BI

**Date :** 13 février 2026

## 📋 Aperçu

### Mapping

| Qlik Extension | Power BI Option | Effort |
|---|---|---|
| **Custom Visualization** | Custom Visual | 5-10j |
| **Highcharts** | Built-in or Custom | 2-5j |
| **D3.js** | Power BI Custom Visual | 5-10j |
| **Third-party** | Find equivalent | Variable |

## 🔨 Approche 1 : Utiliser Custom Visuals Existants

**AppSource (gratuit majorité) :**
- 200+ visuals disponibles
- Check compatibility avec votre données
- Importer dans Power BI Desktop
- Configurer et tester

**Exemples :**
- Deneb (Vega-Lite)
- Charticulator
- SVGMap
- Scroller
- R/Python visuals

## 🔧 Approche 2 : Développer Custom Visual

**Stack :**
- TypeScript
- D3.js ou Highcharts
- Power BI Visual API
- npm/webpack

**Étapes :**
1. Créer projet (pbiviz-tools)
2. Implémenter visual (TypeScript)
3. Tester localement
4. Certifier et publier

## 📊 Approche 3 : Remplacer par Built-ins

Evaluater: Custom Qlik extension VRAIMENT nécessaire?
- 80% cas: Built-in chart + formatting = suffisant
- 15% cas: AppSource custom visual
- 5% cas: Développer custom visual

## 🚀 Migration Steps

1. **Audit** : Lister toutes extensions
2. **Évaluer** : Custom visual ou built-in?
3. **Implémenter** : Tester solution
4. **Former** : Users sur nouvel visuel
5. **Déployer** : Power BI Service

---

**Effort :** 2-10 semaines | **Complexité :** Moyenne-Élevée
"""
    with open(guide_path, 'w') as f:
        f.write(content)
    return str(guide_path)

def main():
    output_dir = Path("output/custom_visuals")
    output_dir.mkdir(parents=True, exist_ok=True)
    guide_file = generate_custom_visuals_guide(output_dir)
    print(f"✅ Custom Visuals guide: {guide_file}")
    return 0

if __name__ == "__main__":
    import sys; sys.exit(main())
