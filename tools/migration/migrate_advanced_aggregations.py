"""
Migration des Agrégations Avancées Qlik vers DAX

Ce module convertit les agrégations complexes Qlik en expressions DAX Power BI.

Author: Migration Team
Date: 2026-02-13
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Tuple
import argparse


class AdvancedAggregationConverter:
    """Convertit les agrégations Qlik avancées en DAX."""
    
    def __init__(self):
        self.conversion_patterns = {
            # Agrégations hiérarchiques
            'hierarchy': {
                'qlik': r'Aggr\(Sum\(\$(Field)\), \$(Dimension)\)',
                'dax': 'SUMX({0}, {1})',
                'confidence': 85,
                'example': 'Aggr(Sum(Sales), Region) → SUMX(VALUES(Region), [Sales Measure])'
            },
            # Agrégations sur partitions
            'partition': {
                'qlik': r'Sum\(\$\(expr\)\) / Sum\(Total \$\(expr\)\)',
                'dax': '{0} / CALCULATE({0}, ALL({1}))',
                'confidence': 90,
                'example': 'Sum(Sales) / Sum(Total Sales) → Measure / ALL Measure'
            },
            # Agrégations avec conditions
            'conditional': {
                'qlik': r'Sum\(If\(condition, \$\(expr\), 0\)\)',
                'dax': 'SUMX(FILTER({0}, condition), {1})',
                'confidence': 80,
                'example': 'Sum(If(Region="North", Sales, 0)) → SUMX(FILTER, [Measure])'
            },
            # Agrégations cumulées
            'running_total': {
                'qlik': r'RangeSum\(\$1:\$\(Index\)\)',
                'dax': 'CALCULATE({0}, ALL(Date), Date <= MAX(Date))',
                'confidence': 85,
                'example': 'RangeSum($1:$n) → CALCULATE with Date filter'
            },
            # Moyennes mobiles
            'moving_average': {
                'qlik': r'Avg\(Range\)',
                'dax': 'AVERAGEX(OFFSET, {0})',
                'confidence': 75,
                'example': 'Moving average → OFFSET + AVERAGEX'
            },
            # Agrégations multi-niveaux
            'multi_level': {
                'qlik': r'Aggr\(Aggr\(...\), ...\)',
                'dax': 'SUMX(VALUES(...), CALCULATE({0}, {1}))',
                'confidence': 70,
                'example': 'Nested Aggr → SUMX with nested CALCULATE'
            }
        }
    
    def convert_aggr_function(self, expression: str) -> Dict:
        """
        Convertit une fonction Aggr() Qlik.
        
        Args:
            expression: Expression Qlik avec Aggr()
            
        Returns:
            Dictionnaire avec conversion et confiance
        """
        result = {
            "original": expression,
            "dax": "",
            "confidence": 0,
            "notes": [],
            "pattern": "custom"
        }
        
        # Parser expression Aggr
        aggr_match = re.search(r'Aggr\((.*?),\s*(.+?)\)$', expression)
        if not aggr_match:
            result['notes'].append("Impossible de parser Aggr()")
            return result
        
        inner_expr = aggr_match.group(1)
        dimension = aggr_match.group(2)
        
        # Détecter le type d'agrégation interne
        if inner_expr.startswith('Sum'):
            result['dax'] = f"SUMX(VALUES({dimension}), [{inner_expr.replace('Sum(', '').replace(')', '')}])"
            result['confidence'] = 85
        elif inner_expr.startswith('Count'):
            result['dax'] = f"COUNTX(VALUES({dimension}), 1)"
            result['confidence'] = 80
        elif inner_expr.startswith('Avg'):
            result['dax'] = f"AVERAGEX(VALUES({dimension}), [{inner_expr.replace('Avg(', '').replace(')', '')}])"
            result['confidence'] = 85
        else:
            result['dax'] = f"SUMX(VALUES({dimension}), [{inner_expr}])"
            result['confidence'] = 70
            result['notes'].append("Expression personnalisée - vérifier DAX généré")
        
        return result
    
    def convert_running_total(self, expression: str) -> Dict:
        """Convertit RangeSum() en running total DAX."""
        result = {
            "original": expression,
            "dax": "",
            "confidence": 0,
            "notes": []
        }
        
        # Parser RangeSum
        rangesum_match = re.search(r'RangeSum\(\$(\d+):\$\((.+?)\)\)', expression)
        if rangesum_match:
            start = rangesum_match.group(1)
            field = rangesum_match.group(2)
            
            # Générer DAX pour cumul
            result['dax'] = f"""
Running_Total = 
    CALCULATE(
        [Total_Measure],
        ALL('Date'),
        'Date'[Date] <= MAX('Date'[Date])
    )
"""
            result['confidence'] = 85
            result['notes'].append("Nécessite colonne Date triée")
        
        return result
    
    def convert_multi_level_aggr(self, expression: str) -> Dict:
        """Convertit aggégations imbriquées."""
        result = {
            "original": expression,
            "dax": "",
            "confidence": 0,
            "notes": []
        }
        
        # Détecter agrégations imbriquées
        nested_count = expression.count('Aggr(')
        
        if nested_count >= 2:
            result['dax'] = """
-- Agrégation multi-niveaux
SUMX(
    VALUES(Dimension1),
    CALCULATE(
        [Inner_Measure],
        VALUES(Dimension2)
    )
)
"""
            result['confidence'] = 70
            result['notes'].append("Vérifier logique imbrication")
            result['notes'].append("Peut nécessiter restructuration modèle")
        
        return result


def generate_advanced_aggregations_guide(output_dir: Path) -> str:
    """Génère un guide des agrégations avancées."""
    guide_path = output_dir / "ADVANCED_AGGREGATIONS_GUIDE.md"
    
    guide_content = """# 📊 Guide Agrégations Avancées - Qlik vers DAX

**Date de génération :** 13 février 2026

---

## 📋 Types d'Agrégations Avancées

### 1. Aggr() - Agrégations Hiérarchiques

**Qlik :**
```qlik
Aggr(Sum(Sales), Region, Product)
```

**DAX :**
```dax
SUMX(
    VALUES(Region),
    CALCULATE(
        [Total_Sales],
        VALUES(Product)
    )
)
```

**Cas d'usage :**
- Totaux par groupe multiple
- Hiérarchies multi-niveaux
- Sous-totaux imbriqués

---

### 2. RangeSum() - Totaux Cumulés

**Qlik :**
```qlik
RangeSum($1:$5)  -- Cumul des 5 premières lignes
```

**DAX :**
```dax
Running_Total = 
    CALCULATE(
        [Measure],
        ALL('Date'),
        'Date'[Date] <= MAX('Date'[Date])
    )
```

**Cas d'usage :**
- Cumuls année à date
- Running totals
- Progressif trésorerie

---

### 3. Avg() avec Conditions Complexes

**Qlik :**
```qlik
Avg(If(Region="North", Sales, 0))
```

**DAX :**
```dax
Conditional_Avg = 
    AVERAGEX(
        FILTER(
            'Sales',
            'Sales'[Region] = "North"
        ),
        'Sales'[Amount]
    )
```

**Cas d'usage :**
- Moyennes conditionnelles
- Moyennes sur sous-ensemble
- Statistiques filtrées

---

### 4. Agrégations sur Partitions

**Qlik :**
```qlik
Sum(Sales) / Sum(Total Sales)  -- Pourcentage du total
```

**DAX :**
```dax
Pct_of_Total = 
    [Total_Sales] / 
    CALCULATE(
        [Total_Sales],
        ALL('Product'),
        ALL('Region')
    )
```

**Cas d'usage :**
- Pourcentages
- Analyses de contribution
- Proportions

---

### 5. Moyennes Mobiles

**Qlik :**
```qlik
Avg(Range) -- Sur fenêtre de 3 périodes
```

**DAX :**
```dax
Moving_Avg_3M = 
    AVERAGEX(
        DATESBETWEEN(
            'Date'[Date],
            DATE(YEAR(TODAY()), MONTH(TODAY())-2, 1),
            TODAY()
        ),
        [Monthly_Sales]
    )
```

**Cas d'usage :**
- Lissage tendances
- Analyse volatilité
- Prévisions

---

## 🔄 Patterns Courants

### Pattern 1: Aggr + Sum Imbriqué

```qlik
-- Qlik
Aggr(Sum(Sales), Region)

-- DAX
SUMX(
    DISTINCT(VALUES(Region)),
    CALCULATE([Total_Sales], VALUES(Region))
)
```

**Variation avec plusieurs dimensions :**
```dax
SUMX(
    SUMMARIZECOLUMNS(
        Region[Region],
        Product[Category],
        "Sales", [Total_Sales]
    ),
    [Sales]
)
```

### Pattern 2: Partition avec Total

```qlik
-- Qlik
Sum({<Region={"North"}>} Sales) / Sum(Total Sales)

-- DAX
Pct_North_Sales = 
    CALCULATE(
        [Total_Sales],
        'Region'[Region] = "North"
    ) /
    CALCULATE(
        [Total_Sales],
        ALL('Region')
    )
```

### Pattern 3: Running Totals

```qlik
-- Qlik
Sum(Range(1, RowNo()))

-- DAX
YTD_Sales = 
    CALCULATE(
        [Total_Sales],
        DATESBETWEEN(
            'Date'[Date],
            DATE(YEAR(TODAY()), 1, 1),
            MAX('Date'[Date])
        )
    )
```

### Pattern 4: Agrégations Conditionnelles

```qlik
-- Qlik
Sum(If(Sales > 1000, Sales, 0))

-- DAX
High_Sales = 
    SUMX(
        FILTER(
            'Sales',
            'Sales'[Amount] > 1000
        ),
        'Sales'[Amount]
    )
```

---

## 💡 Recommandations

### ✅ À Faire

1. **Tester chaque conversion en DAX**
   ```dax
   -- Créer mesure test
   Test_Measure = SUMX(...)
   -- Comparer avec résultat Qlik
   ```

2. **Valider la hiérarchie**
   - Vérifier ordre dimensions
   - Tester sur différentes sélections

3. **Optimiser performance**
   - Utiliser SUMMARIZECOLUMNS si possible
   - Éviter imbrications trop profondes

4. **Documenter conversions**
   - Ajouter commentaires DAX
   - Noter variations si nécessaire

### ⚠️ À Éviter

1. ❌ Imbrications excessives (> 3 niveaux)
2. ❌ Sous-requêtes dans Filter complexes
3. ❌ Variables sans contexte clair
4. ❌ Mesures dépendant ordre d'évaluation

---

## 🧪 Testing

### Checklist Validation

- [ ] Résultats identiques Qlik/Power BI
- [ ] Performance acceptable (< 1 seconde)
- [ ] Édition slicers correcte
- [ ] Accumulation données (Total > Details)
- [ ] Zéro et NULL traités correctly

### Comparaison Qlik vs DAX

```sql
-- Qlik
Sum({<Year={2025}>} Sales) / Sum(Total Sales)

-- DAX (équivalent)
Measure_Pct_2025 = 
    CALCULATE(
        [Total_Sales],
        'Date'[Year] = 2025
    ) /
    CALCULATE(
        [Total_Sales],
        ALL('Date')
    )
```

---

## 📚 Ressources

- [CALCULATE Function](https://dax.guide/calculate/)
- [Aggregation Functions](https://dax.guide/sx/sumx/)
- [Context in DAX](https://docs.microsoft.com/power-bi/dax-basics)

---

**✨ Guide généré automatiquement par migrate_advanced_aggregations.py**
"""
    
    with open(guide_path, 'w', encoding='utf-8') as f:
        f.write(guide_content)
    
    return str(guide_path)


def generate_conversion_templates(output_dir: Path) -> str:
    """Génère des templates de conversion."""
    template_path = output_dir / "aggregation_templates.dax"
    
    templates = """-- Templates de Conversion Agrégations Avancées

-- ============================================
-- 1. TEMPLATE: Aggr() Simple
-- ============================================
Measure_By_Dimension = 
    SUMX(
        DISTINCT(VALUES('Dimension'[Field])),
        CALCULATE([Base_Measure], 'Dimension'[Field])
    )


-- ============================================
-- 2. TEMPLATE: Aggr() Multi-Dimensions
-- ============================================
Measure_Multi_Dim = 
    SUMX(
        SUMMARIZECOLUMNS(
            'Dim1'[Field1],
            'Dim2'[Field2],
            "MeasureValue", [Base_Measure]
        ),
        [MeasureValue]
    )


-- ============================================
-- 3. TEMPLATE: Running Total / YTD
-- ============================================
YTD_Measure = 
    CALCULATE(
        [Base_Measure],
        DATESBETWEEN(
            'Date'[Date],
            DATE(YEAR(MAX('Date'[Date])), 1, 1),
            MAX('Date'[Date])
        )
    )

MTD_Measure = 
    CALCULATE(
        [Base_Measure],
        DATESBETWEEN(
            'Date'[Date],
            DATE(YEAR(MAX('Date'[Date])), MONTH(MAX('Date'[Date])), 1),
            MAX('Date'[Date])
        )
    )


-- ============================================
-- 4. TEMPLATE: Pourcentage du Total
-- ============================================
Pct_of_Total = 
    DIVIDE(
        [Base_Measure],
        CALCULATE([Base_Measure], ALL('Dimension')),
        0
    )

Pct_Parent = 
    DIVIDE(
        [Base_Measure],
        CALCULATE([Base_Measure], ALL('Dim_Child')),
        0
    )


-- ============================================
-- 5. TEMPLATE: Moyenne Conditionnelle
-- ============================================
Conditional_Avg = 
    AVERAGEX(
        FILTER(
            'Table',
            'Table'[Field] = [Condition]
        ),
        'Table'[MeasureField]
    )


-- ============================================
-- 6. TEMPLATE: Moyenne Mobile
-- ============================================
Moving_Avg_3Months = 
    AVERAGEX(
        DATESBETWEEN(
            'Date'[Date],
            EDATE(MAX('Date'[Date]), -2),
            MAX('Date'[Date])
        ),
        [Monthly_Measure]
    )


-- ============================================
-- 7. TEMPLATE: Ranking / Top N
-- ============================================
Rank = 
    RANKX(
        ALL('Product'[Name]),
        [Total_Sales],,
        DESC
    )

Top_N = 
    IF(
        [Rank] <= 10,
        [Total_Sales],
        BLANK()
    )


-- ============================================
-- 8. TEMPLATE: Cumul Croisant
-- ============================================
Cumulative_by_Product = 
    CALCULATE(
        [Base_Measure],
        FILTER(
            ALL('Product'),
            [Product_Rank] <= MAX([Product_Rank])
        )
    )


-- ============================================
-- 9. TEMPLATE: Variance / % Change
-- ============================================
YoY_Change = 
    DIVIDE(
        [Current_Year_Sales] - [Prior_Year_Sales],
        [Prior_Year_Sales],
        0
    )

Month_over_Month = 
    DIVIDE(
        [Current_Month_Sales] - [Prior_Month_Sales],
        [Prior_Month_Sales],
        0
    )


-- ============================================
-- 10. TEMPLATE: Nested Aggregations
-- ============================================
Double_Aggregation = 
    SUMX(
        VALUES('Dim1'),
        CALCULATE(
            SUMX(
                VALUES('Dim2'),
                [Base_Measure]
            ),
            'Dim1'[Field] = EARLIER('Dim1'[Field])
        )
    )


-- ============================================
-- CONDITIONS COMMUNES AVEC IF
-- ============================================

-- SimpleIf
Measure_If = 
    IF([Base_Measure] > 1000, [Base_Measure], 0)

-- Switch (Multiples conditions)
Measure_Switch = 
    SWITCH(
        TRUE(),
        [Base_Measure] > 1000, "High",
        [Base_Measure] > 500, "Medium",
        "Low"
    )


-- ============================================
-- HELPER FUNCTIONS
-- ============================================

-- Obtenir valeur précédente (mois)
Prior_Month_Value = 
    CALCULATE(
        [Base_Measure],
        EDATE(MAX('Date'[Date]), -1)
    )

-- Cumul depuis début année
Cumulative_YTD = 
    CALCULATE(
        [Base_Measure],
        DATESBETWEEN(
            'Date'[Date],
            STARTOFYEAR('Date'[Date]),
            MAX('Date'[Date])
        )
    )

-- Moyenne sur dernier N jours
Rolling_7Day_Avg = 
    AVERAGEX(
        DATESBETWEEN(
            'Date'[Date],
            MAX('Date'[Date]) - 7,
            MAX('Date'[Date])
        ),
        [Daily_Measure]
    )
"""
    
    with open(template_path, 'w', encoding='utf-8') as f:
        f.write(templates)
    
    return str(template_path)


def main():
    parser = argparse.ArgumentParser(
        description="Migrer agrégations avancées Qlik vers DAX"
    )
    parser.add_argument(
        "--expressions",
        nargs='+',
        help="Expressions à convertir"
    )
    parser.add_argument(
        "--file",
        help="Fichier avec expressions (une par ligne)"
    )
    parser.add_argument(
        "--output-dir",
        default="output/aggregations",
        help="Répertoire de sortie"
    )
    parser.add_argument(
        "--templates",
        action="store_true",
        help="Générer templates DAX"
    )
    
    args = parser.parse_args()
    
    # Créer répertoire
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    converter = AdvancedAggregationConverter()
    
    # Générer guide
    print("📊 Génération du guide agrégations avancées...")
    guide_path = generate_advanced_aggregations_guide(output_dir)
    print(f"✅ Guide: {guide_path}")
    
    # Générer templates
    template_path = generate_conversion_templates(output_dir)
    print(f"✅ Templates: {template_path}")
    
    # Traiter expressions si données
    if args.expressions or args.file:
        expressions = args.expressions or []
        
        if args.file and Path(args.file).exists():
            with open(args.file) as f:
                expressions.extend([line.strip() for line in f if line.strip()])
        
        conversions = []
        for expr in expressions:
            print(f"\n🔄 Conversion: {expr}")
            
            if 'Aggr' in expr:
                result = converter.convert_aggr_function(expr)
            elif 'RangeSum' in expr:
                result = converter.convert_running_total(expr)
            elif 'Aggr' in expr and expr.count('Aggr') > 1:
                result = converter.convert_multi_level_aggr(expr)
            else:
                result = {
                    "original": expr,
                    "dax": "-- Conversion personnalisée requise",
                    "confidence": 50,
                    "notes": ["Expression non reconnue - revoir manuellement"]
                }
            
            conversions.append(result)
            print(f"  DAX: {result['dax'][:60]}...")
            print(f"  Confiance: {result['confidence']}%")
        
        # Sauvegarder conversions
        conv_file = output_dir / "conversions.json"
        with open(conv_file, 'w') as f:
            json.dump(conversions, f, indent=2)
        print(f"\n✅ Conversions: {conv_file}")
    
    print(f"\n📚 Ressources générées:")
    print(f"  - {guide_path}")
    print(f"  - {template_path}")
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
