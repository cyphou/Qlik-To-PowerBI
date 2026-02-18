#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Migration Section Access Qlik vers Row Level Security Power BI
Extrait les règles de sécurité et génère le code RLS équivalent
"""

import json
import zipfile
import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
import xml.etree.ElementTree as ET


@dataclass
class SecurityRule:
    """Représente une règle de sécurité Qlik"""
    access: str  # ADMIN, USER
    userid: str
    password: Optional[str] = None
    omit_field: Optional[str] = None
    reduce_field: Optional[str] = None
    reduce_values: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        if isinstance(self.reduce_values, str):
            self.reduce_values = [v.strip() for v in self.reduce_values.split(',')]


@dataclass
class RLSRole:
    """Représente un rôle RLS Power BI"""
    name: str
    table_name: str
    dax_filter: str
    description: str = ""
    users: List[str] = field(default_factory=list)
    
    def generate_dax(self) -> str:
        """Génère l'expression DAX pour le filtre"""
        return self.dax_filter


class SectionAccessMigrator:
    """Gestionnaire de migration Section Access vers RLS"""
    
    def __init__(self, output_dir: Path = None):
        self.output_dir = output_dir or Path('output/security')
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.security_rules: List[SecurityRule] = []
        self.rls_roles: List[RLSRole] = []
        
    def extract_section_access(self, qvf_path: Path) -> List[SecurityRule]:
        """Extrait les règles Section Access d'un QVF"""
        print(f"🔐 Extraction Section Access depuis : {qvf_path}")
        
        try:
            with zipfile.ZipFile(qvf_path, 'r') as qvf:
                # Lire le script de chargement
                if 'LoadScript.xml' in qvf.namelist():
                    script_data = qvf.read('LoadScript.xml').decode('utf-8')
                    self.security_rules = self._parse_section_access(script_data)
            
            print(f"✅ {len(self.security_rules)} règles de sécurité trouvées")
            return self.security_rules
            
        except Exception as e:
            print(f"❌ Erreur extraction : {e}")
            return []
    
    def _parse_section_access(self, script_content: str) -> List[SecurityRule]:
        """Parse le Section Access depuis le script Qlik"""
        rules = []
        
        # Trouver la section SECTION ACCESS
        section_pattern = r'SECTION\s+ACCESS;(.+?)SECTION\s+APPLICATION;'
        match = re.search(section_pattern, script_content, re.IGNORECASE | re.DOTALL)
        
        if not match:
            print("⚠️ Aucune Section Access trouvée")
            return rules
        
        section_content = match.group(1)
        
        # Parser les tables LOAD inline de Section Access
        load_pattern = r'LOAD\s+\*\s+INLINE\s+\[(.+?)\];'
        load_matches = re.finditer(load_pattern, section_content, re.IGNORECASE | re.DOTALL)
        
        for load_match in load_matches:
            inline_data = load_match.group(1)
            rules.extend(self._parse_inline_data(inline_data))
        
        return rules
    
    def _parse_inline_data(self, inline_data: str) -> List[SecurityRule]:
        """Parse les données inline de Section Access"""
        rules = []
        lines = [l.strip() for l in inline_data.strip().split('\n') if l.strip()]
        
        if len(lines) < 2:
            return rules
        
        # Première ligne = headers
        headers = [h.strip().upper() for h in lines[0].split(',')]
        
        # Lignes suivantes = données
        for line in lines[1:]:
            values = [v.strip() for v in line.split(',')]
            
            if len(values) != len(headers):
                continue
            
            rule_data = dict(zip(headers, values))
            
            rule = SecurityRule(
                access=rule_data.get('ACCESS', 'USER').upper(),
                userid=rule_data.get('USERID', rule_data.get('NTNAME', '')),
                password=rule_data.get('PASSWORD'),
                omit_field=rule_data.get('OMIT'),
                reduce_field=self._extract_reduce_field(rule_data),
                reduce_values=self._extract_reduce_values(rule_data)
            )
            
            rules.append(rule)
        
        return rules
    
    def _extract_reduce_field(self, rule_data: Dict) -> Optional[str]:
        """Extrait le champ de réduction depuis les données"""
        # Chercher des colonnes comme REGION, COUNTRY, etc.
        for key in rule_data.keys():
            if key not in ['ACCESS', 'USERID', 'NTNAME', 'PASSWORD', 'OMIT']:
                return key
        return None
    
    def _extract_reduce_values(self, rule_data: Dict) -> List[str]:
        """Extrait les valeurs de réduction"""
        values = []
        for key, value in rule_data.items():
            if key not in ['ACCESS', 'USERID', 'NTNAME', 'PASSWORD', 'OMIT'] and value:
                values.append(value)
        return values
    
    def convert_to_rls(self) -> List[RLSRole]:
        """Convertit les règles Section Access en rôles RLS"""
        print(f"\n🔄 Conversion de {len(self.security_rules)} règles...")
        
        # Grouper par type de filtre
        filter_groups = self._group_by_filter()
        
        # Créer un rôle RLS par groupe
        for filter_key, rules in filter_groups.items():
            role = self._create_rls_role(filter_key, rules)
            if role:
                self.rls_roles.append(role)
        
        print(f"✅ {len(self.rls_roles)} rôles RLS générés")
        return self.rls_roles
    
    def _group_by_filter(self) -> Dict[str, List[SecurityRule]]:
        """Groupe les règles par type de filtre"""
        groups = {}
        
        for rule in self.security_rules:
            if rule.reduce_field:
                key = (rule.reduce_field, tuple(sorted(rule.reduce_values)))
                if key not in groups:
                    groups[key] = []
                groups[key].append(rule)
        
        return groups
    
    def _create_rls_role(self, filter_key: Tuple, rules: List[SecurityRule]) -> Optional[RLSRole]:
        """Crée un rôle RLS depuis un groupe de règles"""
        field_name, values = filter_key
        
        if not field_name or not values:
            return None
        
        # Assumer que le champ existe dans une table (à adapter)
        table_name = self._guess_table_name(field_name)
        
        # Générer le filtre DAX
        dax_filter = self._generate_dax_filter(table_name, field_name, values)
        
        # Nom du rôle
        role_name = f"RLS_{field_name}_{'_'.join(values[:2])}"  # Limiter la longueur
        
        # Collecter les utilisateurs
        users = [rule.userid for rule in rules if rule.userid]
        
        role = RLSRole(
            name=role_name,
            table_name=table_name,
            dax_filter=dax_filter,
            description=f"Accès limité sur {field_name}",
            users=users
        )
        
        return role
    
    def _guess_table_name(self, field_name: str) -> str:
        """Devine le nom de table depuis le nom de champ"""
        # Heuristiques courantes
        if 'region' in field_name.lower():
            return 'Geography'
        elif 'country' in field_name.lower():
            return 'Geography'
        elif 'product' in field_name.lower():
            return 'Products'
        elif 'salesperson' in field_name.lower() or 'employee' in field_name.lower():
            return 'Employees'
        else:
            return 'FactTable'  # Par défaut
    
    def _generate_dax_filter(self, table_name: str, field_name: str, values: Tuple) -> str:
        """Génère l'expression DAX de filtrage"""
        
        if len(values) == 1:
            # Filtre simple
            value = values[0]
            if value == '*':
                # Wildcard = accès total
                return "TRUE()"
            else:
                return f"[{field_name}] = \"{value}\""
        else:
            # Filtre multiple avec IN
            values_str = ', '.join([f'"{v}"' for v in values if v != '*'])
            return f"[{field_name}] IN {{{values_str}}}"
    
    def generate_rls_script(self, output_file: Path = None) -> str:
        """Génère le script PowerShell pour configurer RLS"""
        output_file = output_file or self.output_dir / "configure_rls.ps1"
        
        script = """# Script de configuration Row Level Security (RLS) Power BI
# Généré depuis Section Access Qlik

# Ce script utilise l'API REST Power BI pour configurer les rôles RLS
# Prérequis: Module PowerShell Power BI installé

# Install-Module -Name MicrosoftPowerBIMgmt

# Connexion
Connect-PowerBIServiceAccount

$workspaceId = "VOTRE_WORKSPACE_ID"
$datasetId = "VOTRE_DATASET_ID"

"""
        
        for role in self.rls_roles:
            script += f"""
# Rôle: {role.name}
$roleName = "{role.name}"
$tableFilters = @{{
    "{role.table_name}" = "{role.dax_filter}"
}}

# Créer le rôle (via API REST ou Power BI Desktop)
# Note: La création de rôles doit se faire dans Power BI Desktop
# Ce script applique seulement les utilisateurs aux rôles existants

$users = @(
"""
            for user in role.users:
                script += f'    "{user}",\n'
            
            script += """)

# Ajouter les utilisateurs au rôle
foreach ($user in $users) {
    Add-PowerBIWorkspaceUser -WorkspaceId $workspaceId `
                              -DatasetId $datasetId `
                              -RoleName $roleName `
                              -PrincipalType "User" `
                              -Identifier $user `
                              -AccessRight "View"
}

Write-Host "✅ Utilisateurs ajoutés au rôle: $roleName"
"""
        
        output_file.write_text(script, encoding='utf-8')
        print(f"✅ Script PowerShell RLS : {output_file}")
        
        return script
    
    def generate_rls_dax(self, output_file: Path = None) -> str:
        """Génère les expressions DAX pour les rôles"""
        output_file = output_file or self.output_dir / "rls_filters.dax"
        
        dax = "// Expressions DAX pour Row Level Security\n"
        dax += "// À configurer dans Power BI Desktop → Modélisation → Gérer les rôles\n\n"
        
        for role in self.rls_roles:
            dax += f"// Rôle: {role.name}\n"
            dax += f"// Description: {role.description}\n"
            dax += f"// Table: {role.table_name}\n"
            dax += f"// Filtre DAX:\n"
            dax += f"{role.dax_filter}\n\n"
            dax += "-" * 60 + "\n\n"
        
        output_file.write_text(dax, encoding='utf-8')
        print(f"✅ Filtres DAX générés : {output_file}")
        
        return dax
    
    def generate_user_mapping(self, output_file: Path = None) -> Dict:
        """Génère le mapping utilisateurs → rôles"""
        output_file = output_file or self.output_dir / "user_role_mapping.json"
        
        mapping = {
            "roles": []
        }
        
        for role in self.rls_roles:
            mapping["roles"].append({
                "role_name": role.name,
                "table": role.table_name,
                "filter": role.dax_filter,
                "users": role.users,
                "description": role.description
            })
        
        with output_file.open('w', encoding='utf-8') as f:
            json.dump(mapping, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Mapping utilisateurs : {output_file}")
        return mapping
    
    def generate_test_queries(self, output_file: Path = None) -> str:
        """Génère des requêtes DAX de test pour valider RLS"""
        output_file = output_file or self.output_dir / "test_rls.dax"
        
        tests = "// Requêtes DAX pour tester Row Level Security\n\n"
        
        for role in self.rls_roles:
            tests += f"// Test du rôle: {role.name}\n"
            tests += "EVALUATE\n"
            tests += f"FILTER(\n"
            tests += f"    {role.table_name},\n"
            tests += f"    {role.dax_filter}\n"
            tests += ")\n\n"
            tests += "-" * 60 + "\n\n"
        
        output_file.write_text(tests, encoding='utf-8')
        print(f"✅ Requêtes de test : {output_file}")
        
        return tests
    
    def generate_migration_guide(self, output_file: Path = None) -> str:
        """Génère le guide de migration RLS"""
        output_file = output_file or self.output_dir / "GUIDE_RLS_MIGRATION.md"
        
        guide = f"""# Guide de Migration Section Access → Row Level Security

## Règles Qlik Détectées

**Total règles Section Access :** {len(self.security_rules)}  
**Rôles RLS générés :** {len(self.rls_roles)}

---

## Étapes de Configuration

### 1. Créer les Rôles dans Power BI Desktop

1. Ouvrir votre fichier PBIX dans Power BI Desktop
2. **Modélisation** → **Gérer les rôles**
3. Cliquer **Créer**

Pour chaque rôle, configurer :

"""
        
        for role in self.rls_roles:
            guide += f"""
#### Rôle : {role.name}

- Nom du rôle : `{role.name}`
- Table : `{role.table_name}`
- Expression DAX de filtre :

```dax
{role.dax_filter}
```

**Utilisateurs concernés ({len(role.users)}) :**
"""
            for user in role.users[:10]:  # Limiter l'affichage
                guide += f"- {user}\n"
            
            if len(role.users) > 10:
                guide += f"- ... et {len(role.users) - 10} autres\n"
            
            guide += "\n---\n\n"
        
        guide += """
### 2. Tester les Rôles (Power BI Desktop)

1. **Modélisation** → **Afficher comme**
2. Sélectionner le rôle à tester
3. Vérifier que les données filtrées sont correctes
4. Répéter pour chaque rôle

### 3. Publier le Rapport

1. **Fichier** → **Publier** → **Publier sur Power BI**
2. Sélectionner l'espace de travail
3. Attendre la publication

### 4. Assigner les Utilisateurs aux Rôles (Service Power BI)

#### Option A : Via Interface Web

1. Se connecter à **app.powerbi.com**
2. Aller dans l'espace de travail
3. Cliquer sur **...** à côté du dataset → **Sécurité**
4. Pour chaque rôle :
   - Chercher et ajouter les utilisateurs/groupes
   - Cliquer **Enregistrer**

#### Option B : Via PowerShell

Utiliser le script généré :

```powershell
.\\configure_rls.ps1
```

Modifier les variables:
- `$workspaceId` : ID de votre espace de travail
- `$datasetId` : ID de votre dataset

---

## Mapping Section Access → RLS

### Correspondances

| Concept Qlik | Équivalent Power BI | Notes |
|--------------|---------------------|-------|
| SECTION ACCESS | Row Level Security (RLS) | Sécurité au niveau ligne |
| ACCESS = USER | Rôle RLS | Utilisateur standard |
| ACCESS = ADMIN | Admin espace de travail | Pas de filtre RLS |
| USERID/NTNAME | Utilisateurs assignés | Email Azure AD |
| Réduction de champ | Filtre DAX sur table | Expression sur colonne |
| OMIT | Non supporté | Alternative : colonne masquée |

### Limitations Connues

⚠️ **Différences importantes :**

1. **Pas de OMIT direct**
   - Qlik : OMIT masque des champs entiers
   - Power BI : Masquer les colonnes (mais visibles aux admins)
   - Alternative : Ne pas inclure la colonne dans le modèle

2. **Authentification**
   - Qlik : USERID/PASSWORD dans Section Access
   - Power BI : Azure AD / Microsoft 365
   - Migration : Mapper USERID sur email corporate

3. **Granularité**
   - Qlik : Réduction au niveau utilisateur
   - Power BI : Rôles partagés
   - Solution : Créer un rôle par combinaison de filtre

4. **Wildcards (\\*)**
   - Qlik : \\* = accès total
   - Power BI : Créer rôle sans filtre ou utiliser TRUE()

---

## Validation et Tests

### Checklist de Validation

- [ ] Tous les rôles créés dans Power BI Desktop
- [ ] Expressions DAX testées avec "Afficher comme"
- [ ] Rapport publié sur le service
- [ ] Utilisateurs assignés aux rôles corrects
- [ ] Tests de connexion avec comptes utilisateur
- [ ] Vérification des données visibles/masquées
- [ ] Documentation des exceptions et cas spéciaux

### Tests Recommandés

1. **Test par rôle**
   - Se connecter avec un compte de chaque rôle
   - Vérifier que les bonnes données apparaissent
   - Confirmer que les données interdites sont masquées

2. **Test des combinaisons**
   - Si un utilisateur a plusieurs rôles
   - Power BI applique l'UNION des filtres (plus permissif)

3. **Test des performances**
   - RLS peut ralentir les requêtes
   - Surveiller les temps de réponse

---

## Dépannage

### Problème : Utilisateur voit toutes les données

**Causes possibles :**
- L'utilisateur est Admin de l'espace de travail (RLS ne s'applique pas)
- L'utilisateur n'est assigné à aucun rôle (voir tout par défaut)
- Expression DAX incorrecte (TRUE() par erreur)

**Solutions :**
- Retirer les droits admin si nécessaire
- Assigner à un rôle spécifique
- Tester l'expression DAX avec EVALUATE

### Problème : Utilisateur ne voit aucune donnée

**Causes possibles :**
- Expression DAX trop restrictive
- Aucune donnée ne correspond au filtre
- Problème de casse dans les valeurs

**Solutions :**
- Vérifier l'expression DAX
- Tester avec "Afficher comme" dans Desktop
- Utiliser UPPER() ou LOWER() pour normaliser

### Problème : Performances dégradées

**Causes possibles :**
- Filtres

 RLS complexes
- Tables non optimisées
- Trop de rôles différents

**Solutions :**
- Simplifier les expressions DAX
- Créer des colonnes calculées si nécessaire
- Utiliser des index appropriés

---

## Fichiers Générés

| Fichier | Description | Utilisation |
|---------|-------------|-------------|
| `rls_filters.dax` | Expressions DAX des filtres | Copier dans Power BI Desktop |
| `configure_rls.ps1` | Script PowerShell | Automatiser assignation utilisateurs |
| `user_role_mapping.json` | Mapping utilisateurs-rôles | Référence |
| `test_rls.dax` | Requêtes de test | Valider les filtres |

---

## Ressources

- [Documentation RLS Microsoft](https://learn.microsoft.com/power-bi/enterprise/service-admin-rls)
- [Meilleures pratiques RLS](https://learn.microsoft.com/power-bi/guidance/rls-guidance)
- [Tutoriel vidéo RLS](https://www.youtube.com/results?search_query=power+bi+row+level+security)

---

**✨ Tous les fichiers se trouvent dans :** `{self.output_dir}`

**⚠️ Important :** Testez soigneusement avant de déployer en production !
"""
        
        output_file.write_text(guide, encoding='utf-8')
        print(f"✅ Guide de migration : {output_file}")
        
        return guide


def main():
    """Fonction principale"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Migration Section Access Qlik vers Row Level Security Power BI"
    )
    parser.add_argument(
        'qvf_file',
        type=Path,
        help='Chemin vers le fichier QVF'
    )
    parser.add_argument(
        '--output-dir',
        type=Path,
        default=Path('output/security'),
        help='Dossier de sortie (défaut: output/security)'
    )
    
    args = parser.parse_args()
    
    # Vérifier que le fichier existe
    if not args.qvf_file.exists():
        print(f"❌ Fichier non trouvé : {args.qvf_file}")
        return 1
    
    # Migration
    print("🔐 Migration Section Access → Row Level Security\n")
    print("=" * 60)
    
    migrator = SectionAccessMigrator(output_dir=args.output_dir)
    
    # Extraction
    rules = migrator.extract_section_access(args.qvf_file)
    if not rules:
        print("⚠️ Aucune règle Section Access trouvée")
        print("ℹ️ Le fichier QVF ne contient peut-être pas de Section Access")
        return 0
    
    # Conversion
    roles = migrator.convert_to_rls()
    
    # Génération des fichiers
    print("\n📝 Génération des fichiers...")
    migrator.generate_rls_dax()
    migrator.generate_rls_script()
    migrator.generate_user_mapping()
    migrator.generate_test_queries()
    migrator.generate_migration_guide()
    
    # Résumé
    print("\n" + "=" * 60)
    print("✅ Migration terminée !")
    print(f"🔐 {len(rules)} règles Section Access → {len(roles)} rôles RLS")
    print(f"📁 Fichiers générés dans : {args.output_dir}")
    print("\n📖 Consultez GUIDE_RLS_MIGRATION.md pour les étapes suivantes")
    print("\n⚠️  IMPORTANT : Testez soigneusement avant déploiement production !")
    
    return 0


if __name__ == '__main__':
    exit(main())
