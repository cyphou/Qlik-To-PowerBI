"""Migration - Advanced Selection Objects (Input, Slider, Calendar, Search)"""
import json; from pathlib import Path
def gen_guide(output_dir: Path) -> str:
    path = output_dir / "ADVANCED_SELECTIONS_MIGRATION_GUIDE.md"
    content = """# 🎛️ Guide Migration - Advanced Selection Objects vers Power BI Filters

**Date :** 13 février 2026

## 📋 Mapping

| Qlik | Power BI | Solution |
|---|---|---|
| **Input Box** | Text parameter | What-If parameter |
| **Slider** | Numeric range | Numeric parameter |
| **Calendar** | Date range | Date parameter |
| **Search Box** | Field search | Filter with search |

## Input Box → What-If Parameter

```
1. Power BI → Modeling → New parameter
2. Type: Text, default value
3. Use in formulas
```

## Slider → Numeric What-If

```
1. Create parameter (Decimal 0-100)
2. Add visual
3. Use in DAX measures
```

## Calendar → Date Parameters

```
1. Create date parameter
2. link to date slicer
3. Use in date filters
```

## Search → Filters Avancés

Power BI filters natifs avec search:
- Segment avec search enabled
- Field list avec tri/filtre
- Custom filter avec regex

## 🚀 Steps

1. Identify advanced selection objects
2. Define equivalent parameters/filters
3. Implement in Power BI
4. Test user scenarios
5. Deploy

---

**Effort :** 3-5 jours | **Complexité :** Basique-Moyenne
"""
    with open(path, 'w') as f: f.write(content)
    return str(path)

def main():
    output_dir = Path("output/advanced_selections")
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"✅ Advanced Selections: {gen_guide(output_dir)}")
    return 0

if __name__ == "__main__":
    import sys; sys.exit(main())
