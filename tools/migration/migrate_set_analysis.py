#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Migration Set Analysis Qlik vers DAX Power BI
Convertit les expressions Set Analysis complexes en expressions DAX
"""

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import json


@dataclass
class SetExpression:
    """Représente une expression Set Analysis Qlik"""
    original: str
    set_modifier: str = ""
    aggregation_func: str = ""
    field: str = ""
    identifier: str = ""  # 1, $, $1, etc.
    operators: List[str] = None
    
    def __post_init__(self):
        if self.operators is None:
            self.operators = []


@dataclass
class DAXExpression:
    """Représente l'expression DAX équivalente"""
    dax_code: str
    complexity: str  # Simple, Moderate, Complex
    confidence: float  # 0.0 à 1.0
    notes: str = ""
    manual_review_needed: bool = False


class SetAnalysisConverter:
    """Convertisseur Set Analysis → DAX"""
    
    # Mapping agrégations Qlik → DAX
    AGGREGATION_MAP = {
        'sum': 'SUM',
        'avg': 'AVERAGE',
        'count': 'COUNT',
        'min': 'MIN',
        'max': 'MAX',
        'median': 'MEDIAN',
        'stdev': 'STDEV.P',
        'only': 'SELECTEDVALUE'
    }
    
    # Modifiers Set Analysis courants
    SET_MODIFIERS = {
        '<Year={$(vCurrentYear)}>': 'YEAR([Date]) = [CurrentYear]',
        '<Month=>': 'ALL(Calendar[Month])',
        '<Product={"A","B"}>': 'Product[Name] IN {"A", "B"}',
    }
    
    def __init__(self, output_dir: Path = None):
        self.output_dir = output_dir or Path('output/set_analysis')
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.conversions: List[Tuple[SetExpression, DAXExpression]] = []
        
    def convert_expression(self, qlik_expr: str) -> DAXExpression:
        """Convertit une expression Set Analysis en DAX"""
        
        # Parser l'expression
        set_expr = self._parse_set_analysis(qlik_expr)
        
        # Convertir selon la complexité
        if self._is_simple_aggregation(set_expr):
            dax = self._convert_simple_aggregation(set_expr)
        elif self._has_set_modifier(set_expr):
            dax = self._convert_with_set_modifier(set_expr)
        else:
            dax = self._convert_complex_expression(set_expr)
        
        # Enregistrer la conversion
        self.conversions.append((set_expr, dax))
        
        return dax
    
    def _parse_set_analysis(self, expr: str) -> SetExpression:
        """Parse une expression Set Analysis"""
        
        # Pattern général: Aggregation({SetIdentifier<SetModifiers>} Field)
        pattern = r'(\w+)\s*\(\s*(\{[^}]+\})\s*([^)]+)\s*\)'
        match = re.search(pattern, expr, re.IGNORECASE)
        
        if match:
            agg_func = match.group(1).lower()
            set_part = match.group(2)
            field = match.group(3).strip()
            
            # Parser la partie set
            set_identifier, modifiers = self._parse_set_part(set_part)
            
            return SetExpression(
                original=expr,
                aggregation_func=agg_func,
                field=field,
                identifier=set_identifier,
                set_modifier=modifiers
            )
        
        # Agrégation simple sans Set Analysis
        simple_pattern = r'(\w+)\s*\(\s*([^)]+)\s*\)'
        simple_match = re.search(simple_pattern, expr, re.IGNORECASE)
        
        if simple_match:
            return SetExpression(
                original=expr,
                aggregation_func=simple_match.group(1).lower(),
                field=simple_match.group(2).strip()
            )
        
        return SetExpression(original=expr)
    
    def _parse_set_part(self, set_part: str) -> Tuple[str, str]:
        """Parse la partie {Set} de l'expression"""
        # Retirer les accolades
        set_content = set_part.strip('{}')
        
        # Identifier: 1, $, $1, etc.
        identifier_match = re.match(r'^\s*([\$\d]+)', set_content)
        identifier = identifier_match.group(1) if identifier_match else '1'
        
        # Modifiers: <Year={2023}>
        modifiers = re.sub(r'^\s*[\$\d]+', '', set_content).strip()
        
        return identifier, modifiers
    
    def _is_simple_aggregation(self, set_expr: SetExpression) -> bool:
        """Vérifie si c'est une agrégation simple sans Set Analysis"""
        return not set_expr.set_modifier and set_expr.aggregation_func
    
    def _has_set_modifier(self, set_expr: SetExpression) -> bool:
        """Vérifie si l'expression a des modifiers Set Analysis"""
        return bool(set_expr.set_modifier)
    
    def _convert_simple_aggregation(self, set_expr: SetExpression) -> DAXExpression:
        """Convertit une agrégation simple"""
        
        dax_func = self.AGGREGATION_MAP.get(
            set_expr.aggregation_func, 
            set_expr.aggregation_func.upper()
        )
        
        # Extraire table et colonne
        table_col = self._parse_field(set_expr.field)
        
        dax_code = f"{dax_func}({table_col})"
        
        return DAXExpression(
            dax_code=dax_code,
            complexity="Simple",
            confidence=0.95,
            notes="Conversion directe d'agrégation"
        )
    
    def _convert_with_set_modifier(self, set_expr: SetExpression) -> DAXExpression:
        """Convertit une expression avec Set Analysis"""
        
        # Extraire les conditions du modifier
        conditions = self._parse_set_modifiers(set_expr.set_modifier)
        
        # Construire l'expression DAX
        dax_func = self.AGGREGATION_MAP.get(
            set_expr.aggregation_func,
            set_expr.aggregation_func.upper()
        )
        
        table_col = self._parse_field(set_expr.field)
        
        # Générer les filtres
        filter_expressions = []
        for condition in conditions:
            dax_filter = self._condition_to_dax(condition)
            if dax_filter:
                filter_expressions.append(dax_filter)
        
        # Construire avec CALCULATE
        if filter_expressions:
            filters = ",\n    ".join(filter_expressions)
            dax_code = f"CALCULATE(\n    {dax_func}({table_col}),\n    {filters}\n)"
            complexity = "Moderate"
            confidence = 0.75
        else:
            dax_code = f"{dax_func}({table_col})"
            complexity = "Simple"
            confidence = 0.85
        
        return DAXExpression(
            dax_code=dax_code,
            complexity=complexity,
            confidence=confidence,
            notes=f"Set Analysis converti avec {len(filter_expressions)} filtre(s)",
            manual_review_needed=len(filter_expressions) > 2
        )
    
    def _convert_complex_expression(self, set_expr: SetExpression) -> DAXExpression:
        """Convertit une expression complexe (nécessite révision)"""
        
        # Tentative de conversion basique
        dax_code = f"// Expression complexe - Révision manuelle requise\n"
        dax_code += f"// Original: {set_expr.original}\n"
        dax_code += f"// TODO: Convertir en DAX approprié"
        
        return DAXExpression(
            dax_code=dax_code,
            complexity="Complex",
            confidence=0.3,
            notes="Expression complexe nécessitant révision manuelle",
            manual_review_needed=True
        )
    
    def _parse_field(self, field: str) -> str:
        """Parse un nom de champ Qlik et le convertit en syntaxe DAX"""
        # Retirer les guillemets ou crochets
        field = field.strip('[]"')
        
        # Si le champ contient un point, c'est probablement Table.Column
        if '.' in field:
            return field
        
        # Sinon, ajouter des crochets DAX
        return f'[{field}]'
    
    def _parse_set_modifiers(self, modifiers: str) -> List[Dict]:
        """Parse les modifiers Set Analysis"""
        conditions = []
        
        # Pattern: <Field=Value> ou <Field={Value1,Value2}>
        pattern = r'<\s*(\w+)\s*=\s*([^>]+)>'
        
        matches = re.finditer(pattern, modifiers)
        for match in matches:
            field = match.group(1)
            value = match.group(2).strip()
            
            conditions.append({
                'field': field,
                'operator': '=',
                'value': value
            })
        
        return conditions
    
    def _condition_to_dax(self, condition: Dict) -> str:
        """Convertit une condition Set Analysis en filtre DAX"""
        field = condition['field']
        value = condition['value']
        
        # Valeur entre accolades = liste
        if value.startswith('{') and value.endswith('}'):
            # Liste de valeurs
            values = value.strip('{}').split(',')
            values_clean = [v.strip().strip('"\'') for v in values]
            
            if len(values_clean) == 1:
                # Valeur unique
                return f"{field}[{field}] = \"{values_clean[0]}\""
            else:
                # Plusieurs valeurs avec IN
                values_str = ', '.join([f'"{v}"' for v in values_clean])
                return f"{field}[{field}] IN {{{values_str}}}"
        
        # Vide = ignorer le filtre (ALL)
        elif not value:
            return f"ALL({field}[{field}])"
        
        # Variable Qlik
        elif value.startswith('$'):
            var_name = value.strip('$()').strip()
            return f"{field}[{field}] = [{var_name}]"
        
        # Valeur simple
        else:
            value_clean = value.strip('"\'')
            return f"{field}[{field}] = \"{value_clean}\""
    
    def convert_batch(self, qlik_file: Path) -> List[Tuple[SetExpression, DAXExpression]]:
        """Convertit toutes les expressions d'un fichier"""
        print(f"📊 Conversion expressions Set Analysis depuis : {qlik_file}")
        
        # Lire le fichier (JSON, XML, ou texte)
        expressions = self._extract_expressions_from_file(qlik_file)
        
        print(f"✅ {len(expressions)} expressions trouvées")
        
        results = []
        for expr in expressions:
            dax = self.convert_expression(expr)
            results.append((SetExpression(original=expr), dax))
        
        return results
    
    def _extract_expressions_from_file(self, file_path: Path) -> List[str]:
        """Extrait les expressions Set Analysis d'un fichier"""
        expressions = []
        
        content = file_path.read_text(encoding='utf-8')
        
        # Pattern pour détecter Set Analysis
        pattern = r'\w+\s*\(\s*\{[^}]+\}\s*[^)]+\)'
        
        matches = re.finditer(pattern, content, re.MULTILINE)
        for match in matches:
            expressions.append(match.group(0))
        
        return expressions
    
    def generate_conversion_report(self, output_file: Path = None) -> Dict:
        """Génère un rapport de conversion"""
        output_file = output_file or self.output_dir / "conversion_report.json"
        
        report = {
            "total_expressions": len(self.conversions),
            "by_complexity": {
                "Simple": len([c for _, d in self.conversions if d.complexity == "Simple"]),
                "Moderate": len([c for _, d in self.conversions if d.complexity == "Moderate"]),
                "Complex": len([c for _, d in self.conversions if d.complexity == "Complex"])
            },
            "manual_review_needed": len([c for _, d in self.conversions if d.manual_review_needed]),
            "average_confidence": sum([d.confidence for _, d in self.conversions]) / len(self.conversions) if self.conversions else 0,
            "conversions": [
                {
                    "qlik": qlik.original,
                    "dax": dax.dax_code,
                    "complexity": dax.complexity,
                    "confidence": dax.confidence,
                    "manual_review": dax.manual_review_needed,
                    "notes": dax.notes
                }
                for qlik, dax in self.conversions
            ]
        }
        
        with output_file.open('w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Rapport de conversion : {output_file}")
        return report
    
    def generate_dax_file(self, output_file: Path = None) -> str:
        """Génère un fichier DAX avec toutes les conversions"""
        output_file = output_file or self.output_dir / "converted_measures.dax"
        
        dax = "// Mesures DAX converties depuis Set Analysis Qlik\n\n"
        
        for i, (qlik, dax_expr) in enumerate(self.conversions, 1):
            dax += f"// Mesure {i}\n"
            dax += f"// Source Qlik: {qlik.original}\n"
            dax += f"// Complexité: {dax_expr.complexity} | Confiance: {dax_expr.confidence:.0%}\n"
            if dax_expr.manual_review_needed:
                dax += f"// ⚠️ RÉVISION MANUELLE REQUISE\n"
            dax += f"// {dax_expr.notes}\n\n"
            dax += f"Measure_{i} = \n"
            dax += f"{dax_expr.dax_code}\n\n"
            dax += "-" * 60 + "\n\n"
        
        output_file.write_text(dax, encoding='utf-8')
        print(f"✅ Fichier DAX généré : {output_file}")
        
        return dax
    
    def generate_patterns_guide(self, output_file: Path = None) -> str:
        """Génère un guide de patterns de conversion"""
        output_file = output_file or self.output_dir / "PATTERNS_GUIDE.md"
        
        guide = """# Guide des Patterns Set Analysis → DAX

## Patterns Courants

### 1. Agrégation Simple

**Qlik:**
```qlik
Sum(Sales)
```

**DAX:**
```dax
SUM(Sales[Amount])
```

**Confiance:** 95% | **Révision:** Non requise

---

### 2. Filtre sur Année en Cours

**Qlik:**
```qlik
Sum({<Year={$(vCurrentYear)}>} Sales)
```

**DAX:**
```dax
CALCULATE(
    SUM(Sales[Amount]),
    Calendar[Year] = [CurrentYear]
)
```

**Confiance:** 85% | **Révision:** Vérifier nom de la variable

---

### 3. Ignorer Sélection (Clear Selection)

**Qlik:**
```qlik
Sum({1} Sales)
```

**DAX:**
```dax
CALCULATE(
    SUM(Sales[Amount]),
    ALL(Sales)
)
```

**Confiance:** 90% | **Révision:** Non requise

---

### 4. Sélection Alternative

**Qlik:**
```qlik
Sum({$<Product={'A','B','C'}>} Sales)
```

**DAX:**
```dax
CALCULATE(
    SUM(Sales[Amount]),
    Product[Name] IN {"A", "B", "C"}
)
```

**Confiance:** 85% | **Révision:** Vérifier nom de colonne

---

### 5. Année Précédente

**Qlik:**
```qlik
Sum({<Year={$(=Year(Today())-1)}>} Sales)
```

**DAX:**
```dax
CALCULATE(
    SUM(Sales[Amount]),
    SAMEPERIODLASTYEAR(Calendar[Date])
)
```

**Confiance:** 80% | **Révision:** Vérifier table calendrier

---

### 6. Cumulatif (YTD)

**Qlik:**
```qlik
Sum({<Month={"<=$(vCurrentMonth)"}>} Sales)
```

**DAX:**
```dax
TOTALYTD(
    SUM(Sales[Amount]),
    Calendar[Date]
)
```

**Confiance:** 75% | **Révision:** Adapter selon besoin

---

### 7. Intersection de Sets (ET logique)

**Qlik:**
```qlik
Sum({<Year={2023}, Region={'North'}>} Sales)
```

**DAX:**
```dax
CALCULATE(
    SUM(Sales[Amount]),
    Calendar[Year] = 2023,
    Region[Name] = "North"
)
```

**Confiance:** 90% | **Révision:** Non requise

---

### 8. Exclusion (Sauf)

**Qlik:**
```qlik
Sum({<Product-={'Discontinued'}>} Sales)
```

**DAX:**
```dax
CALCULATE(
    SUM(Sales[Amount]),
    Product[Status] <> "Discontinued"
)
```

**Confiance:** 85% | **Révision:** Vérifier syntaxe

---

### 9. Variable dans Set Analysis

**Qlik:**
```qlik
Sum({<Year={$(vSelectedYear)}>} Sales)
```

**DAX:**
```dax
CALCULATE(
    SUM(Sales[Amount]),
    Calendar[Year] = [SelectedYear]
)
```

**Confiance:** 70% | **Révision:** Créer paramètre What-If

---

### 10. P() - Sélection Possible

**Qlik:**
```qlik
Sum({<Year=P({1<Year={2023}>})>} Sales)
```

**DAX:**
```dax
// Pattern complexe - Conversion manuelle
CALCULATE(
    SUM(Sales[Amount]),
    FILTER(
        ALL(Calendar[Year]),
        Calendar[Year] = 2023
    )
)
```

**Confiance:** 50% | **Révision:** REQUISE

---

## Modifiers Avancés

### E() - Excluded Values

**Qlik:** `{<Field=E({SetExpression})>}`  
**DAX:** `EXCEPT()` ou `FILTER(ALL(...), NOT(...))`  
**Confiance:** 60%

### P() - Possible Values

**Qlik:** `{<Field=P({SetExpression})>}`  
**DAX:** `FILTER(ALL(...), ...)`  
**Confiance:** 50%

### Implicit Set Modifier

**Qlik:** `{<Field=>}`  
**DAX:** `ALL(Table[Field])`  
**Confiance:** 90%

---

## Limitations Connues

### ⚠️ Pas d'Équivalent Direct

1. **Alternate States**
   - Qlik : `Sum({State1} Sales)`
   - Power BI : Non supporté nativement
   - Alternative : Créer mesures séparées

2. **Set Operations Complexes (Union/Intersection)**
   - Qlik : `Sum({Set1 + Set2} Sales)`
   - DAX : Combiner avec `UNION()` ou `INTERSECT()`
   - Complexité : Élevée

3. **Indirect Set Reference**
   - Qlik : `{$1}`, `{$2}`
   - DAX : Non applicable
   - Alternative : Refactoriser

---

## Checklist de Révision

Avant d'utiliser une mesure DAX convertie :

- [ ] Vérifier les noms de tables et colonnes
- [ ] Tester avec données réelles
- [ ] Comparer résultats Qlik vs Power BI
- [ ] Valider comportement avec filtres
- [ ] Vérifier performances (temps de réponse)
- [ ] Documenter les différences si nécessaire

---

## Ressources

- [DAX Patterns](https://www.daxpatterns.com/)
- [SQLBI - DAX Guide](https://dax.guide/)
- [Set Analysis vs DAX Comparison](https://community.powerbi.com/t5/Community-Blog/Set-Analysis-vs-DAX/ba-p/238)

"""
        
        output_file.write_text(guide, encoding='utf-8')
        print(f"✅ Guide de patterns : {output_file}")
        
        return guide


def main():
    """Fonction principale"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Conversion Set Analysis Qlik → DAX Power BI"
    )
    parser.add_argument(
        'expression',
        nargs='?',
        help='Expression Qlik à convertir (ou fichier avec --file)'
    )
    parser.add_argument(
        '--file',
        type=Path,
        help='Fichier contenant expressions Qlik'
    )
    parser.add_argument(
        '--output-dir',
        type=Path,
        default=Path('output/set_analysis'),
        help='Dossier de sortie'
    )
    parser.add_argument(
        '--generate-patterns',
        action='store_true',
        help='Générer guide de patterns'
    )
    
    args = parser.parse_args()
    
    converter = SetAnalysisConverter(output_dir=args.output_dir)
    
    print("🔄 Conversion Set Analysis → DAX\n")
    print("=" * 60)
    
    if args.generate_patterns:
        converter.generate_patterns_guide()
        print("\n✅ Guide de patterns généré !")
        return 0
    
    if args.file:
        # Conversion par lot
        converter.convert_batch(args.file)
        converter.generate_dax_file()
        converter.generate_conversion_report()
    elif args.expression:
        # Conversion simple
        dax = converter.convert_expression(args.expression)
        print(f"\n📊 Expression Qlik:")
        print(f"   {args.expression}")
        print(f"\n➡️  Expression DAX:")
        print(f"   {dax.dax_code}")
        print(f"\n📈 Complexité: {dax.complexity}")
        print(f"   Confiance: {dax.confidence:.0%}")
        if dax.manual_review_needed:
            print(f"   ⚠️ Révision manuelle requise")
        print(f"   Note: {dax.notes}")
    else:
        print("❌ Fournir une expression ou utiliser --file")
        return 1
    
    print("\n" + "=" * 60)
    print("✅ Conversion terminée !")
    
    return 0


if __name__ == '__main__':
    exit(main())
