"""Migration - On-Demand App Generation vers Dynamic Report Patterns"""
import json; from pathlib import Path
def gen_guide(output_dir: Path) -> str:
    path = output_dir / "ON_DEMAND_GENERATION_MIGRATION_GUIDE.md"
    content = """# 🚀 Guide Migration - On-Demand App Generation vers Power BI Alternatives

**Date :** 13 février 2026

## 📋 Concept

### Qlik On-Demand App Generation
Utiliser données user pour générer apps personnalisées dynamiquement

### Power BI Alternatives

| Approche | Description | Use Case |
|---|---|---|
| **Parameterized Reports** | Single report + parameters | User sees filtered data |
| **Dynamic Pages** | Tooltip pages with drill-through | Exploration |
| **Bookmarks** | Saved report states | Quick views |
| **RLS + Roles** | Row-level security | Separate data by user |

## 🎨 Approche 1 : Parameterized Reports

```
1. Create single Power BI report
2. Add parameters (department, region, etc)
3. Share via link with parameter values
4. User sees personalized view
```

## 🎨 Approche 2 : Dynamic Drill-Through Pages

```
Dashboard → Click object → Drill-through to detail page
Detail page filtered by clicked object
```

## 🎨 Approche 3 : RLS + Different Workspaces

```
User A → Workspace A (filtered data via RLS) → Report
User B → Workspace B (filtered data via RLS) → Report
```

## 🚀 Steps

1. Analyze on-demand generation logic
2. Choose approach (parameters vs RLS vs drill-through)
3. Implement in Power BI
4. Test user scenarios
5. Document for support

---

**Effort :** 1-3 semaines | **Complexité :** Moyenne
"""
    with open(path, 'w') as f: f.write(content)
    return str(path)

def main():
    output_dir = Path("output/on_demand_generation")
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"✅ On-Demand Generation: {gen_guide(output_dir)}")
    return 0

if __name__ == "__main__":
    import sys; sys.exit(main())
