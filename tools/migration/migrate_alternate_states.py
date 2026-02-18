"""Migration - Alternate States vers Dynamic Report Slicing"""
import json
from pathlib import Path
def generate_alternate_states_guide(output_dir: Path) -> str:
    guide_path = output_dir / "ALTERNATE_STATES_MIGRATION_GUIDE.md"
    content = """# 🔀 Guide Migration - Alternate States vers Dynamic Slicing

**Date :** 13 février 2026

## 📋 Concept

### Qlik Alternate States

Permet deux contextes de sélection indépendants sur même app
```
State A: Revenue viewed by Department
State B: Revenue viewed by Region (sélections indépendantes)
```

### Power BI Équivalent

Power BI n'a pas "alternate states" natifs, solutions:
1. **Multiple Report Pages** - Séparé contextes
2. **Bookmarks** - Capturer états
3. **Report Filters** - Vérifier contextes dynamiquement
4. **Field Parameters** - Sélection dynamique axes

## 🎨 Approche 1 : Multiple Pages

**Page 1 :** Revenue by Department (own slicers)
**Page 2 :** Revenue by Region (own slicers)  
**Page 3 :** Combined view with both

## 🎨 Approche 2 : Field Parameters

Utiliser Field Parameters (Power BI new feature):
```vb
// Parameter table
Category = {"Department", "Region", "Product"}

// Dynamic measure
[Revenue] = 
IF(
    SELECTEDVALUE(Category[Category]) = "Department",
    // Calculate by dept,
    // Calculate by region
)
```

## 🚀 Steps Migration

1. Identifier alternate states Qlik
2. Choisir approche (pages OU field parameters)
3. Créer rapports correspondants
4. Tester contextes indépendants
5. Former utilisateurs

---

**Effort :** 2-3 jours | **Complexité :** Moyenne
"""
    with open(guide_path, 'w') as f:
        f.write(content)
    return str(guide_path)

def main():
    output_dir = Path("output/alternate_states")
    output_dir.mkdir(parents=True, exist_ok=True)
    guide_file = generate_alternate_states_guide(output_dir)
    print(f"✅ Alternate States guide: {guide_file}")
    return 0

if __name__ == "__main__":
    import sys; sys.exit(main())
