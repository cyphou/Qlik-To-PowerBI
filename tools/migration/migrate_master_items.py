#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Migration Master Items Qlik vers Power BI
Extrait dimensions et mesures maîtres pour les recréer dans Power BI
"""

import json
import zipfile
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass, field


@dataclass
class MasterDimension:
    """Dimension maître Qlik"""
    id: str
    name: str
    field: str
    label_expression: Optional[str] = None
    grouping: List[str] = field(default_factory=list)
    description: str = ""


@dataclass
class MasterMeasure:
    """Mesure maître Qlik"""
    id: str
    name: str
    expression: str
    description: str = ""
    format: str = ""
    number_format: Optional[Dict] = None


class MasterItemsMigrator:
    """Migration Master Items Qlik → Power BI"""
    
    def __init__(self, output_dir: Path = None):
        self.output_dir = output_dir or Path('output/master_items')
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.dimensions: List[MasterDimension] = []
        self.measures: List[MasterMeasure] = []
    
    def extract_master_items(self, qvf_path: Path) -> tuple:
        """Extrait les master items d'un QVF"""
        print(f"📐 Extraction Master Items depuis : {qvf_path}")
        
        try:
            with zipfile.ZipFile(qvf_path, 'r') as qvf:
                if 'app.json' in qvf.namelist():
                    app_data = json.loads(qvf.read('app.json').decode('utf-8'))
                    
                    # Dimensions maîtres
                    if 'properties' in app_data:
                        # Dimensions
                        dim_list = app_data['properties'].get('qDimensionList', [])
                        for dim in dim_list:
                            dimension = MasterDimension(
                                id=dim.get('qInfo', {}).get('qId', ''),
                                name=dim.get('qMetaDef', {}).get('title', ''),
                                field=dim.get('qDim', {}).get('qFieldDefs', [''])[0],
                                label_expression=dim.get('qDim', {}).get('qLabelExpression'),
                                grouping=dim.get('qDim', {}).get('qFieldDefs', []),
                                description=dim.get('qMetaDef', {}).get('description', '')
                            )
                            self.dimensions.append(dimension)
                        
                        # Mesures
                        measure_list = app_data['properties'].get('qMeasureList', [])
                        for meas in measure_list:
                            measure = MasterMeasure(
                                id=meas.get('qInfo', {}).get('qId', ''),
                                name=meas.get('qMetaDef', {}).get('title', ''),
                                expression=meas.get('qMeasure', {}).get('qDef', ''),
                                description=meas.get('qMetaDef', {}).get('description', ''),
                                format=meas.get('qMeasure', {}).get('qNumFormat', {}).get('qFmt', ''),
                                number_format=meas.get('qMeasure', {}).get('qNumFormat')
                            )
                            self.measures.append(measure)
            
            print(f"✅ {len(self.dimensions)} dimensions + {len(self.measures)} mesures trouvées")
        except Exception as e:
            print(f"❌ Erreur : {e}")
        
        return self.dimensions, self.measures
    
    def generate_dax_measures(self, output_file: Path = None) -> str:
        """Génère les mesures DAX"""
        output_file = output_file or self.output_dir / "master_measures.dax"
        
        dax = "// Mesures DAX depuis Master Items Qlik\n\n"
        
        for measure in self.measures:
            dax += f"// {measure.description}\n" if measure.description else ""
            dax += f"{measure.name} = \n"
            
            # Convertir expression Qlik en DAX basique
            dax_expr = self._convert_expression_to_dax(measure.expression)
            dax += f"    {dax_expr}\n\n"
            
            if measure.number_format:
                dax += f"// Format: {measure.format}\n"
            
            dax += "-" * 60 + "\n\n"
        
        output_file.write_text(dax, encoding='utf-8')
        print(f"✅ Mesures DAX : {output_file}")
        return dax
    
    def _convert_expression_to_dax(self, qlik_expr: str) -> str:
        """Conversion basique expression Qlik → DAX"""
        # Simple mapping
        expr = qlik_expr
        expr = expr.replace('Sum(', 'SUM(').replace('sum(', 'SUM(')
        expr = expr.replace('Avg(', 'AVERAGE(').replace('avg(', 'AVERAGE(')
        expr = expr.replace('Count(', 'COUNT(').replace('count(', 'COUNT(')
        expr = expr.replace('Min(', 'MIN(').replace('min(', 'MIN(')
        expr = expr.replace('Max(', 'MAX(').replace('max(', 'MAX(')
        
        # Ajouter commentaire si Set Analysis détecté
        if '{' in expr and '}' in expr:
            return f"// TODO: Convertir Set Analysis\n    // Original: {qlik_expr}\n    // Utiliser migrate_set_analysis.py"
        
        return expr
    
    def generate_dimension_table(self, output_file: Path = None) -> str:
        """Génère table M pour dimensions"""
        output_file = output_file or self.output_dir / "master_dimensions.pq"
        
        m_code = "// Dimensions depuis Master Items\n\n"
        
        for dim in self.dimensions:
            m_code += f"// Dimension: {dim.name}\n"
            if dim.description:
                m_code += f"// {dim.description}\n"
            
            if len(dim.grouping) > 1:
                # Hiérarchie
                m_code += f"// Hiérarchie: {', '.join(dim.grouping)}\n"
            
            m_code += f"// Champ: {dim.field}\n\n"
        
        output_file.write_text(m_code, encoding='utf-8')
        print(f"✅ Dimensions : {output_file}")
        return m_code
    
    def generate_config_json(self, output_file: Path = None) -> Dict:
        """Génère configuration JSON complète"""
        output_file = output_file or self.output_dir / "master_items_config.json"
        
        config = {
            "master_dimensions": [
                {
                    "id": d.id,
                    "name": d.name,
                    "field": d.field,
                    "grouping": d.grouping,
                    "description": d.description,
                    "is_hierarchy": len(d.grouping) > 1
                }
                for d in self.dimensions
            ],
            "master_measures": [
                {
                    "id": m.id,
                    "name": m.name,
                    "expression": m.expression,
                    "description": m.description,
                    "format": m.format,
                    "has_set_analysis": '{' in m.expression and '}' in m.expression
                }
                for m in self.measures
            ],
            "statistics": {
                "total_dimensions": len(self.dimensions),
                "total_measures": len(self.measures),
                "hierarchies": len([d for d in self.dimensions if len(d.grouping) > 1]),
                "measures_with_set_analysis": len([m for m in self.measures if '{' in m.expression])
            }
        }
        
        with output_file.open('w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Configuration : {output_file}")
        return config
    
    def generate_migration_guide(self, output_file: Path = None) -> str:
        """Génère guide de migration"""
        output_file = output_file or self.output_dir / "MASTER_ITEMS_GUIDE.md"
        
        guide = f"""# Migration Master Items Qlik → Power BI

## Résumé

**Master Dimensions trouvées :** {len(self.dimensions)}  
**Master Measures trouvées :** {len(self.measures)}

---

## Master Dimensions → Colonnes Calculées / Hiérarchies

### Dans Power BI Desktop

Les dimensions maîtres Qlik deviennent des colonnes ou hiérarchies dans Power BI.

#### Dimensions Simples

Pour chaque dimension :

1. **Données** → Sélectionner la table
2. **Modélisation** → **Nouvelle colonne**
3. Utiliser la formule DAX :

"""
        
        for dim in self.dimensions:
            if len(dim.grouping) == 1:
                guide += f"""
**{dim.name}**
```dax
{dim.name} = [{dim.field}]
```
"""
        
        guide += """
#### Hiérarchies

Pour les dimensions groupées :

1. **Données** → Clic droit sur la colonne de niveau supérieur
2. **Créer une hiérarchie**
3. Glisser-déposer les autres niveaux

"""
        
        hierarchies = [d for d in self.dimensions if len(d.grouping) > 1]
        if hierarchies:
            guide += "**Hiérarchies détectées :**\n\n"
            for hier in hierarchies:
                guide += f"**{hier.name}**\n"
                for i, level in enumerate(hier.grouping, 1):
                    guide += f"  {i}. {level}\n"
                guide += "\n"
        
        guide += f"""
---

## Master Measures → Mesures DAX

Les mesures maîtres Qlik deviennent des mesures DAX dans Power BI.

### Création

1. **Données** → Sélectionner une table
2. **Modélisation** → **Nouvelle mesure**
3. Copier le code DAX depuis `master_measures.dax`

### Mesures Converties ({len(self.measures)})

"""
        
        for measure in self.measures:
            guide += f"""
#### {measure.name}

**Description :** {measure.description or 'N/A'}  
**Format :** {measure.format or 'Auto'}

**Expression Qlik :**
```qlik
{measure.expression}
```

"""
            if '{' in measure.expression and '}' in measure.expression:
                guide += "⚠️ **Contient Set Analysis** - Utiliser `migrate_set_analysis.py`\n\n"
        
        guide += """
---

## Utilisation

### Dans les Visuels

Les master items migrés sont disponibles comme :
- **Dimensions** → Champs de table (ou hiérarchies)
- **Mesures** → Mesures DAX

Glisser-déposer dans les visuels comme d'habitude.

### Réutilisabilité

✅ Avantage : Une fois créées, les mesures DAX sont réutilisables  
✅ Hiérarchies : Explorables en drill-up/down  
✅ Format : Appliqué automatiquement si configuré

---

## Fichiers Générés

| Fichier | Description |
|---------|-------------|
| `master_measures.dax` | Toutes les mesures DAX |
| `master_dimensions.pq` | Liste des dimensions |
| `master_items_config.json` | Configuration complète |
| `MASTER_ITEMS_GUIDE.md` | Ce guide |

---

## Checklist

- [ ] Créer toutes les mesures DAX depuis `master_measures.dax`
- [ ] Créer les hiérarchies identifiées
- [ ] Appliquer les formats aux mesures
- [ ] Tester avec des visuels
- [ ] Valider résultats vs Qlik

---

**✨ Fichiers dans :** `{self.output_dir}`
"""
        
        output_file.write_text(guide, encoding='utf-8')
        print(f"✅ Guide : {output_file}")
        return guide


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Migration Master Items Qlik")
    parser.add_argument('qvf_file', type=Path, help='Fichier QVF')
    parser.add_argument('--output-dir', type=Path, default=Path('output/master_items'))
    args = parser.parse_args()
    
    if not args.qvf_file.exists():
        print(f"❌ Fichier non trouvé : {args.qvf_file}")
        return 1
    
    print("📐 Migration Master Items Qlik → Power BI\n")
    print("=" * 60)
    
    migrator = MasterItemsMigrator(output_dir=args.output_dir)
    
    # Extraction
    dimensions, measures = migrator.extract_master_items(args.qvf_file)
    
    if not dimensions and not measures:
        print("⚠️ Aucun master item trouvé")
        return 0
    
    # Génération
    print("\n📝 Génération des fichiers...")
    migrator.generate_dax_measures()
    migrator.generate_dimension_table()
    migrator.generate_config_json()
    migrator.generate_migration_guide()
    
    # Résumé
    print("\n" + "=" * 60)
    print("✅ Migration terminée !")
    print(f"📊 {len(dimensions)} dimensions + {len(measures)} mesures")
    print(f"📁 Fichiers dans : {args.output_dir}")
    
    return 0


if __name__ == '__main__':
    exit(main())
