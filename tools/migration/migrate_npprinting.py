"""Migration - NPrinting Templates vers Power BI Paginated Reports"""
import json
from pathlib import Path


def generate_npprinting_guide(output_dir: Path) -> str:
    guide_path = output_dir / "NPPRINTING_MIGRATION_GUIDE.md"
    content = """# 📄 Guide Migration - NPrinting vers Power BI Paginated Reports

**Date :** 13 février 2026

## 📋 Aperçu

### Mapping Qlik → Power BI

| Qlik | Power BI | Complexité |
|------|----------|-----------|
| **NPrinting Report** | Paginated Report (.rdl) | Moyenne |
| **Template** | Report Layout | Moyenne |
| **Filters** | Report Parameters | Faible |
| **Subscriptions** | Email Subscriptions | Faible |
| **Tasks** | Scheduled Exports | Moyen |

## 🎨 Approche 1 : Paginated Reports

### Qlik NPrinting

```
Template → RLS Data → Excel/PDF Distribution
```

### Power BI Paginated Report

**Structure PBIX :**
- Report datasets (requêtes)
- Report pages (layout)
- Parameters (filtres)
- Subscriptions (distribution)

**Création :**
1. Power BI Report Builder
2. Créer dataset (SQL/Power BI)
3. Designer layout (tablix, rectangles, texte)
4. Ajouter paramètres
5. Tester rendering PDF/Excel

## 📊 Approche 2 : Power BI Reports + Subscriptions

Plutôt que Paginated Reports complexes, utiliser:
- Power BI Reports standard
- Abonnements Power BI Service
- Export Power Automate si résultats particuliers

## 🚀 Migration Steps

1. **Analyser NPrinting Templates**
2. **Évaluer complexité**
3. **Créer Paginated Reports OU Power BI Reports**
4. **Configurer distribution**
5. **Valider output**

## 📋 Checklist

- [ ] Documenter tous templates NPrinting
- [ ] Lister filtres/paramètres
- [ ] Créer rapports correspondants
- [ ] Tester distribution
- [ ] Former utilisateurs

---

**Effort :** 1-2 semaines | **Complexité :** Moyenne-Élevée
"""
    with open(guide_path, 'w') as f:
        f.write(content); return str(guide_path)

def main():
    output_dir = Path("output/npprinting")
    output_dir.mkdir(parents=True, exist_ok=True)
    guide_file = generate_npprinting_guide(output_dir)
    print(f"✅ NPrinting guide: {guide_file}")
    return 0

if __name__ == "__main__":
    import sys; sys.exit(main())
