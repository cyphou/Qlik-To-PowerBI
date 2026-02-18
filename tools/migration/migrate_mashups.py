"""Migration - Mashups vers Embedded Analytics"""
import json; from pathlib import Path
def gen_guide(output_dir: Path) -> str:
    path = output_dir / "MASHUPS_MIGRATION_GUIDE.md"
    content = """# 🔗 Guide Migration - Mashups vers Embedded Analytics Power BI

**Date :** 13 février 2026

## 📋 Concept

### Qlik Mashups
Embed Qlik app/objects dans custom application (HTML/JavaScript)

### Power BI Embedded
Service cloud pour embed rapports dans apps

## 🎨 Approche 1 : Power BI Embedded

```json
{
  "capacity": "Premium",
  "app": "My App",
  "report": "Sales Dashboard",
  "embed_tokens": "Generated tokens for users"
}
```

**Avantages :**
- ✅ Sécurité AAD native
- ✅ RLS intégré
- ✅ Licensing simple
- ✅ Scaling automatique

## 🎨 Approche 2 : Power BI REST API

Register custom app → Générer tokens → Embed via API

```javascript
// JavaScript
powerbi.embed(config, {
  type: 'report',
  tokenExpiration: 3600
});
```

## 🎨 Approche 3 : Azure App Owns Data

Pour embedded SaaS:
- Service principal auth
- Embed sans user license
- Usage-based pricing

## 🚀 Steps

1. Audit Qlik mashups
2. Define embedding strategy
3. Setup Power BI Embedded/Premium capacity
4. Develop app avec SDK/API
5. Test & deploy

---

**Effort :** 2-4 semaines | **Complexité :** Élevée
"""
    with open(path, 'w') as f: f.write(content)
    return str(path)

def main():
    output_dir = Path("output/mashups")
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"✅ Mashups: {gen_guide(output_dir)}")
    return 0

if __name__ == "__main__":
    import sys; sys.exit(main())
