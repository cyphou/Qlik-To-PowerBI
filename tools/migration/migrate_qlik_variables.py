#!/usr/bin/env python3
"""
Migration des Variables Qlik vers Parametres Power BI
Extrait les variables d'un fichier QVF et genere les equivalents Power BI
"""

import json
import zipfile
import re
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import xml.etree.ElementTree as ET


@dataclass
class QlikVariable:
    """Représente une variable Qlik"""
    name: str
    definition: str
    description: str = ""
    is_reserved: bool = False
    variable_type: str = "expression"  # expression, input, system
    
    def is_numeric(self) -> bool:
        """Vérifie si la variable contient une valeur numérique"""
        try:
            float(self.definition)
            return True
        except (ValueError, TypeError):
            return False
    
    def is_date(self) -> bool:
        """Vérifie si la variable est une date"""
        date_patterns = [
            r'\d{4}-\d{2}-\d{2}',
            r'\d{2}/\d{2}/\d{4}',
            r'Date\(',
            r'Today\(',
            r'YearStart\(',
            r'MonthStart\('
        ]
        return any(re.search(pattern, self.definition, re.IGNORECASE) for pattern in date_patterns)
    
    def is_list(self) -> bool:
        """Vérifie si la variable contient une liste"""
        return ',' in self.definition or 'valuelist' in self.definition.lower()


@dataclass  
class PowerBIParameter:
    """Représente un paramètre Power BI"""
    name: str
    value: Any
    parameter_type: str  # Text, Number, Date, List
    description: str = ""
    m_code: str = ""
    dax_measure: str = ""
    
    def generate_m_parameter(self) -> str:
        """Génère le code M pour le paramètre"""
        if self.m_code:
            return self.m_code
            
        if self.parameter_type == "Number":
            return f'{self.name} = {self.value} meta [IsParameterQuery=true, Type="Number", IsParameterQueryRequired=true]'
        elif self.parameter_type == "Date":
            return f'{self.name} = #date({self.value}) meta [IsParameterQuery=true, Type="Date", IsParameterQueryRequired=true]'
        elif self.parameter_type == "List":
            values = self.value.split(',') if isinstance(self.value, str) else self.value
            list_str = '{' + ', '.join([f'"{v.strip()}"' for v in values]) + '}'
            return f'{self.name} = {list_str} meta [IsParameterQuery=true, Type="List", IsParameterQueryRequired=true]'
        else:  # Text
            return f'{self.name} = "{self.value}" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]'


class QlikVariableMigrator:
    """Gestionnaire de migration des variables Qlik vers Power BI"""
    
    # Variables système Qlik réservées
    RESERVED_VARIABLES = {
        'ScriptError', 'ScriptErrorCount', 'ScriptErrorList',
        'QvPath', 'QvRoot', 'QvWorkPath', 'QvWorkRoot',
        'QlikViewVersion', 'ErrorMode', 'Verbatim',
        'NullValue', 'OtherSymbol', 'QlikCommunityName'
    }
    
    def __init__(self, output_dir: Path = None):
        self.output_dir = output_dir or Path('output/variables')
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.variables: List[QlikVariable] = []
        self.parameters: List[PowerBIParameter] = []
        
    def extract_variables_from_qvf(self, qvf_path: Path) -> List[QlikVariable]:
        """Extrait les variables d'un fichier QVF"""
        print(f"📂 Extraction variables depuis : {qvf_path}")
        
        try:
            with zipfile.ZipFile(qvf_path, 'r') as qvf:
                # Lire le fichier app.json qui contient les variables
                if 'app.json' in qvf.namelist():
                    app_data = json.loads(qvf.read('app.json').decode('utf-8'))
                    self.variables = self._parse_variables_from_json(app_data)
                    
                # Essayer aussi LoadScript.xml
                if 'LoadScript.xml' in qvf.namelist():
                    script_data = qvf.read('LoadScript.xml').decode('utf-8')
                    script_vars = self._parse_variables_from_script(script_data)
                    self.variables.extend(script_vars)
                    
            print(f"✅ {len(self.variables)} variables trouvées")
            return self.variables
            
        except Exception as e:
            print(f"❌ Erreur extraction : {e}")
            return []
    
    def _parse_variables_from_json(self, app_data: Dict) -> List[QlikVariable]:
        """Parse les variables depuis app.json"""
        variables = []
        
        # Chercher dans qVariableList
        if 'properties' in app_data and 'qVariableList' in app_data['properties']:
            for var_data in app_data['properties']['qVariableList']:
                var = QlikVariable(
                    name=var_data.get('qName', ''),
                    definition=var_data.get('qDefinition', ''),
                    description=var_data.get('qComment', ''),
                    is_reserved=var_data.get('qName', '') in self.RESERVED_VARIABLES
                )
                if not var.is_reserved:
                    variables.append(var)
        
        return variables
    
    def _parse_variables_from_script(self, script_xml: str) -> List[QlikVariable]:
        """Parse les variables depuis LoadScript.xml"""
        variables = []
        
        # Pattern pour SET et LET
        set_pattern = r'(?:SET|LET)\s+(\w+)\s*=\s*(.+?)(?:;|\n)'
        
        matches = re.finditer(set_pattern, script_xml, re.IGNORECASE | re.MULTILINE)
        for match in matches:
            var_name = match.group(1).strip()
            var_def = match.group(2).strip()
            
            if var_name not in self.RESERVED_VARIABLES:
                var = QlikVariable(
                    name=var_name,
                    definition=var_def,
                    variable_type='input' if match.group(0).upper().startswith('LET') else 'expression'
                )
                variables.append(var)
        
        return variables
    
    def convert_to_powerbi_parameters(self) -> List[PowerBIParameter]:
        """Convertit les variables Qlik en paramètres Power BI"""
        print(f"\n🔄 Conversion de {len(self.variables)} variables...")
        
        for var in self.variables:
            param = self._convert_variable(var)
            if param:
                self.parameters.append(param)
        
        print(f"✅ {len(self.parameters)} paramètres générés")
        return self.parameters
    
    def _convert_variable(self, var: QlikVariable) -> Optional[PowerBIParameter]:
        """Convertit une variable Qlik en paramètre Power BI"""
        
        # Déterminer le type
        if var.is_numeric():
            param_type = "Number"
            value = var.definition
        elif var.is_date():
            param_type = "Date"
            value = self._convert_date_expression(var.definition)
        elif var.is_list():
            param_type = "List"
            value = var.definition
        else:
            param_type = "Text"
            value = var.definition.strip("'\"")
        
        # Générer le code M
        param = PowerBIParameter(
            name=var.name,
            value=value,
            parameter_type=param_type,
            description=var.description or f"Migré depuis variable Qlik: {var.name}"
        )
        
        # Générer aussi une mesure DAX si nécessaire
        if param_type == "Number":
            param.dax_measure = f"{var.name} = {value}"
        
        return param
    
    def _convert_date_expression(self, expr: str) -> str:
        """Convertit une expression de date Qlik en date Power BI"""
        # Today() -> Date.From(DateTime.LocalNow())
        expr = re.sub(r'Today\(\)', 'Date.From(DateTime.LocalNow())', expr, flags=re.IGNORECASE)
        
        # YearStart() -> Date.StartOfYear()
        expr = re.sub(r'YearStart\(([^)]+)\)', r'Date.StartOfYear(\1)', expr, flags=re.IGNORECASE)
        
        # MonthStart() -> Date.StartOfMonth()
        expr = re.sub(r'MonthStart\(([^)]+)\)', r'Date.StartOfMonth(\1)', expr, flags=re.IGNORECASE)
        
        return expr
    
    def generate_m_code(self, output_file: Path = None) -> str:
        """Génère le fichier Power Query M avec tous les paramètres"""
        output_file = output_file or self.output_dir / "parameters.pq"
        
        m_code = "// Paramètres Power BI générés depuis variables Qlik\n"
        m_code += "// Importez ce fichier dans Power BI Desktop\n\n"
        
        for param in self.parameters:
            m_code += f"// {param.description}\n"
            m_code += param.generate_m_parameter() + "\n\n"
        
        output_file.write_text(m_code, encoding='utf-8')
        print(f"✅ Code M généré : {output_file}")
        
        return m_code
    
    def generate_dax_measures(self, output_file: Path = None) -> str:
        """Génère les mesures DAX correspondantes"""
        output_file = output_file or self.output_dir / "measures.dax"
        
        dax_code = "// Mesures DAX pour utiliser les paramètres\n\n"
        
        for param in self.parameters:
            if param.dax_measure:
                dax_code += f"// Paramètre: {param.name}\n"
                dax_code += f"{param.dax_measure}\n\n"
        
        output_file.write_text(dax_code, encoding='utf-8')
        print(f"✅ Mesures DAX générées : {output_file}")
        
        return dax_code
    
    def generate_parameter_table(self, output_file: Path = None) -> str:
        """Génère une table de paramètres pour What-If"""
        output_file = output_file or self.output_dir / "parameter_table.pq"
        
        m_code = "// Table de paramètres pour What-If Analysis\n\n"
        
        for param in self.parameters:
            if param.parameter_type == "Number":
                m_code += f"// Table pour {param.name}\n"
                m_code += f"let\n"
                m_code += f"    Source = List.Numbers(0, 100, 1),\n"
                escaped_name = param.name.replace('"', '\\"')
                m_code += f'    #"Converted to Table" = Table.FromList(Source, Splitter.SplitByNothing(), {{"{escaped_name}"}}, null, ExtraValues.Error)' + "\n"
                m_code += f"in\n"
                m_code += f"    #\"Converted to Table\"\n\n"
        
        output_file.write_text(m_code, encoding='utf-8')
        print(f"✅ Tables de paramètres générées : {output_file}")
        
        return m_code
    
    def generate_migration_report(self, output_file: Path = None) -> Dict:
        """Génère un rapport de migration"""
        output_file = output_file or self.output_dir / "migration_report.json"
        
        report = {
            "total_variables": len(self.variables),
            "converted_parameters": len(self.parameters),
            "conversion_rate": f"{len(self.parameters)/len(self.variables)*100:.1f}%" if self.variables else "0%",
            "variables": [
                {
                    "name": var.name,
                    "type": var.variable_type,
                    "definition": var.definition,
                    "converted": any(p.name == var.name for p in self.parameters)
                }
                for var in self.variables
            ],
            "parameters": [
                {
                    "name": param.name,
                    "type": param.parameter_type,
                    "value": str(param.value),
                    "description": param.description
                }
                for param in self.parameters
            ]
        }
        
        with output_file.open('w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Rapport de migration : {output_file}")
        return report
    
    def generate_user_guide(self, output_file: Path = None) -> str:
        """Génère un guide utilisateur pour la configuration manuelle"""
        output_file = output_file or self.output_dir / "GUIDE_CONFIGURATION.md"
        
        guide = f"""# Guide de Configuration des Paramètres Power BI

## Variables Qlik Migrées

**Total variables trouvées :** {len(self.variables)}  
**Paramètres générés :** {len(self.parameters)}

---

## Étapes d'Import

### 1. Importer les Paramètres Power Query

1. Ouvrir Power BI Desktop
2. **Accueil** → **Transformer les données** → **Éditeur Power Query**
3. **Nouvelle source** → **Requête vide**
4. Dans la barre de formule, coller le contenu de `parameters.pq`
5. Répéter pour chaque paramètre

### 2. Créer les Paramètres What-If (pour valeurs numériques)

"""
        
        # Ajouter instructions pour chaque paramètre What-If
        numeric_params = [p for p in self.parameters if p.parameter_type == "Number"]
        if numeric_params:
            guide += "**Paramètres numériques détectés :**\n\n"
            for param in numeric_params:
                guide += f"""
#### Paramètre : {param.name}

1. **Modélisation** → **Nouveau paramètre**
2. Nom : `{param.name}`
3. Valeur par défaut : `{param.value}`
4. Type : Nombre décimal
5. Minimum/Maximum : À définir selon vos besoins
6. Incrément : À définir

Mesure DAX générée automatiquement :
```dax
{param.name} = {param.value}
```

"""
        
        guide += """
### 3. Configurer les Paramètres de Date

"""
        
        date_params = [p for p in self.parameters if p.parameter_type == "Date"]
        if date_params:
            for param in date_params:
                guide += f"""
#### Paramètre : {param.name}

Power Query M :
```m
{param.generate_m_parameter()}
```

Utilisation dans vos requêtes :
```m
Table.SelectRows(Source, each [Date] >= {param.name})
```

"""
        
        guide += """
### 4. Utiliser les Paramètres dans vos Mesures

Les paramètres peuvent être référencés dans vos mesures DAX :

```dax
Sales Filtered = 
CALCULATE(
    SUM(Sales[Amount]),
    Sales[Year] = [YearParameter]
)
```

---

## Liste Complète des Paramètres

| Nom | Type | Valeur | Description |
|-----|------|--------|-------------|
"""
        
        for param in self.parameters:
            guide += f"| {param.name} | {param.parameter_type} | {param.value} | {param.description} |\n"
        
        guide += """
---

## Dépannage

### Erreur : "Le paramètre n'est pas reconnu"
- Vérifiez que le paramètre est bien créé dans l'éditeur Power Query
- La casse doit correspondre exactement

### Erreur de type
- Vérifiez que le type du paramètre correspond à son utilisation
- Utilisez des conversions si nécessaire : `Number.From()`, `Date.From()`, etc.

### Paramètre What-If ne filtre pas
- Vérifiez que la mesure DAX utilise bien `[NomParametre]` avec crochets
- La table de paramètres doit être marquée comme "table de paramètres"

---

**✨ Tous les fichiers générés se trouvent dans :** `{self.output_dir}`
"""
        
        output_file.write_text(guide, encoding='utf-8')
        print(f"✅ Guide utilisateur : {output_file}")
        
        return guide


def main():
    """Fonction principale"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Migration des variables Qlik vers paramètres Power BI"
    )
    parser.add_argument(
        'qvf_file',
        type=Path,
        help='Chemin vers le fichier QVF'
    )
    parser.add_argument(
        '--output-dir',
        type=Path,
        default=Path('output/variables'),
        help='Dossier de sortie (défaut: output/variables)'
    )
    
    args = parser.parse_args()
    
    # Vérifier que le fichier existe
    if not args.qvf_file.exists():
        print(f"❌ Fichier non trouvé : {args.qvf_file}")
        return 1
    
    # Migration
    print("🚀 Migration Variables Qlik → Paramètres Power BI\n")
    print("=" * 60)
    
    migrator = QlikVariableMigrator(output_dir=args.output_dir)
    
    # Extraction
    variables = migrator.extract_variables_from_qvf(args.qvf_file)
    if not variables:
        print("⚠️ Aucune variable trouvée dans le fichier QVF")
        return 0
    
    # Conversion
    parameters = migrator.convert_to_powerbi_parameters()
    
    # Génération des fichiers
    print("\n📝 Génération des fichiers...")
    migrator.generate_m_code()
    migrator.generate_dax_measures()
    migrator.generate_parameter_table()
    migrator.generate_migration_report()
    migrator.generate_user_guide()
    
    # Résumé
    print("\n" + "=" * 60)
    print("✅ Migration terminée !")
    print(f"📊 {len(variables)} variables → {len(parameters)} paramètres")
    print(f"📁 Fichiers générés dans : {args.output_dir}")
    print("\n📖 Consultez GUIDE_CONFIGURATION.md pour les étapes suivantes")
    
    return 0


if __name__ == '__main__':
    exit(main())
