"""Migration - GeoAnalytics vers Azure Maps & Power BI Maps"""
import json; from pathlib import Path
def gen_geo_guide(output_dir: Path) -> str:
    path = output_dir / "GEOANALYTICS_MIGRATION_GUIDE.md"
    content = """# 🗺️ Guide Migration - GeoAnalytics vers Azure Maps

**Date :** 13 février 2026

## 📋 Aperçu

### Qlik GeoAnalytics
- Spatial analysis (distance, clustering)
- Location routing
- Geo enrichment
- Custom maps

### Power BI Options

| Feature | Power BI Solution |
|---|---|
| **Basic map** | Built-in map visual |
| **Advanced analytics** | Azure Maps SDK / R |
| **Clustering** | Bing Maps / Custom |
| **Routing** | Azure Maps REST API |

## 🎨 Approche 1 : Built-in Maps

Power BI native support:
- Scatter maps
- Bubble maps
- Shape maps
- Bing cartograms

Suffisant pour 80% cas.

## 🎨 Approche 2 : Azure Maps Integration

Pour cas complexes:
```
Power BI → Azure Maps SDK → Custom visual
```

**Setup :**
1. Create Azure Maps account
2. Get API key
3. Create custom visual avec Maps SDK
4. Import Power BI

## 🎨 Approche 3 : R/Python with Maps

```r
# R example - ggmap, leaflet
library(leaflet)
leaflet(data) %>%
  addTiles() %>%
  addMarkers(~lon, ~lat)
```

## 🚀 Steps

1. Audit Qlik spatial features
2. Évaluer si Power BI natif suffit
3. Si complexe → Azure Maps ou R
4. Tester performances
5. Déployer

---

**Effort :** 1-2 semaines | **Complexité :** Moyenne
"""
    with open(path, 'w') as f: f.write(content)
    return str(path)

def main():
    output_dir = Path("output/geoanalytics")
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"✅ GeoAnalytics: {gen_geo_guide(output_dir)}")
    return 0

if __name__ == "__main__":
    import sys; sys.exit(main())
