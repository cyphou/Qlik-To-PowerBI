"""Qlik Data Model to Power BI Model converter."""
import logging
import json
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class RelationshipCardinality(Enum):
    """Types de cardinalité des relations."""
    ONE_TO_MANY = "OneToMany"
    MANY_TO_ONE = "ManyToOne"
    ONE_TO_ONE = "OneToOne"
    MANY_TO_MANY = "ManyToMany"


class CrossFilterDirection(Enum):
    """Direction du filtre croisé."""
    SINGLE = "Single"
    BOTH = "Both"


@dataclass
class QlikAssociation:
    """Représente une association Qlik entre tables."""
    from_table: str
    from_field: str
    to_table: str
    to_field: str
    association_type: str = "natural"  # natural, synthetic, etc.


@dataclass
class PowerBIRelationship:
    """Représente une relation Power BI."""
    name: str
    from_table: str
    from_column: str
    to_table: str
    to_column: str
    cardinality: RelationshipCardinality
    cross_filter_direction: CrossFilterDirection
    is_active: bool = True
    security_filtering_behavior: str = "OneDirection"


@dataclass
class PowerBIHierarchy:
    """Représente une hiérarchie Power BI."""
    name: str
    table: str
    levels: List[Tuple[str, str]]  # [(nom_niveau, nom_colonne)]
    hidden: bool = False


@dataclass
class PowerBICalculatedColumn:
    """Représente une colonne calculée Power BI."""
    name: str
    table: str
    expression: str
    data_type: str
    format_string: Optional[str] = None


class QlikDataModelExtractor:
    """Extrait le modèle de données d'une application Qlik."""

    def __init__(self, qlik_app_data: Dict):
        """
        Initialiser l'extracteur.
        
        Args:
            qlik_app_data: Données de l'application Qlik (JSON)
        """
        self.qlik_app_data = qlik_app_data
        self.associations: List[QlikAssociation] = []
        self.tables: Dict[str, Set[str]] = {}  # table -> set de champs

    def extract_tables_and_fields(self) -> Dict[str, Set[str]]:
        """
        Extraire les tables et leurs champs.
        
        Supporte deux formats:
        1. Format loadScript (parsing du script Qlik)
        2. Format tables (structure directe pour tests)
        
        Returns:
            Dictionnaire table -> ensemble de champs
        """
        logger.info("Extraction des tables et champs...")
        
        # Format 1: Structure tables directe (pour tests et exemples)
        # Only use this path if the tables actually contain field data;
        # otherwise fall through to loadScript parsing.
        if 'tables' in self.qlik_app_data:
            has_fields = False
            for table in self.qlik_app_data['tables']:
                table_name = table['name']
                if table_name not in self.tables:
                    self.tables[table_name] = set()
                
                for field in table.get('fields', []):
                    field_name = field['name'] if isinstance(field, dict) else field
                    if field_name:
                        self.tables[table_name].add(field_name)
                        has_fields = True
            
            if has_fields:
                logger.info(f"Trouvé {len(self.tables)} tables (format direct)")
                return self.tables
            else:
                # Tables present but empty – reset and fall through
                self.tables = {}
                logger.debug("Tables vides dans format direct, fallback sur loadScript")
        
        # Format 2: Analyser les scripts de chargement si disponibles
        load_script = self.qlik_app_data.get('loadScript', '')
        
        if not load_script:
            logger.warning("Aucune source de données trouvée (ni 'tables' ni 'loadScript')")
            return self.tables
        
        # Parser des LOAD statements avec leur label de table Qlik
        # Format Qlik: TableName:\n LOAD field1, field2 ... FROM/RESIDENT/INLINE
        import re

        # Pattern: capture the table label before LOAD plus the field list.
        # The table label is a word followed by ':' on a preceding line.
        table_load_pattern = re.compile(
            r'(\w+)\s*:\s*\r?\n'               # table label  (e.g. "Sales:")
            r'\s*LOAD\s+'                       # LOAD keyword
            r'(.*?)'                            # field list   (non-greedy)
            r'\s+(?:FROM|RESIDENT|INLINE)\b',   # source type keyword
            re.IGNORECASE | re.DOTALL,
        )

        for match in table_load_pattern.finditer(load_script):
            table_name = match.group(1)
            fields_str = match.group(2)
            # Extract individual field names (handle "expr AS alias")
            fields = [f.strip().split(' as ')[-1].strip()
                      for f in fields_str.split(',')]
            # Remove empty / whitespace-only entries
            fields = [f for f in fields if f]

            if table_name not in self.tables:
                self.tables[table_name] = set()
            self.tables[table_name].update(fields)
            logger.debug(f"Table '{table_name}': {len(fields)} champs")
        
        logger.info(f"Trouvé {len(self.tables)} tables (parse loadScript)")
        return self.tables

    def infer_associations(self) -> List[QlikAssociation]:
        """
        Inférer les associations entre tables basées sur les champs communs.
        
        Supporte deux modes:
        1. Associations explicites (clé 'associations' dans les données)
        2. Inférence automatique (champs communs)
        
        Returns:
            Liste des associations
        """
        logger.info("Inférence des associations...")
        
        # Mode 1: Associations explicites (only if the list is non-empty)
        explicit_assocs = self.qlik_app_data.get('associations') or []
        if explicit_assocs:
            for assoc_data in explicit_assocs:
                assoc = QlikAssociation(
                    from_table=assoc_data.get('fromTable'),
                    from_field=assoc_data.get('fromField'),
                    to_table=assoc_data.get('toTable'),
                    to_field=assoc_data.get('toField'),
                    association_type=assoc_data.get('type', 'explicit')
                )
                self.associations.append(assoc)
            
            logger.info(f"Trouvé {len(self.associations)} associations explicites")
            return self.associations
        
        # Mode 2: Inférence automatique
        # Trouver les champs communs entre tables
        table_names = list(self.tables.keys())

        def _stem(name: str) -> str:
            """Poor-man's stem: Categories→categor, Products→product, etc."""
            n = name.lower()
            for suffix in ('ies', 'es', 's'):
                if len(n) > 3 and n.endswith(suffix):
                    return n[:-len(suffix)]
            return n

        def _is_dimension_table(table_name: str, field_name: str) -> bool:
            """Return True if *table_name* looks like the dimension for *field_name*.

            E.g. table "Customers" is the dimension for field "CustomerID".
            """
            import re as _re
            prefix = _re.sub(r'(?i)id$', '', field_name).lower()
            if not prefix:
                return False
            return _stem(table_name) == _stem(prefix)

        for i, table1 in enumerate(table_names):
            for table2 in table_names[i+1:]:
                common_fields = self.tables[table1] & self.tables[table2]
                
                for field in common_fields:
                    # In Power BI: fromColumn = many-side (fact table),
                    #              toColumn   = one-side  (dimension table).
                    if field.endswith('ID') or field.endswith('Id'):
                        # Identify which table is the dimension (one-side)
                        # by matching the field prefix to the table name.
                        if _is_dimension_table(table2, field):
                            fact_table, dim_table = table1, table2
                        elif _is_dimension_table(table1, field):
                            fact_table, dim_table = table2, table1
                        else:
                            # Fallback: table with more columns is the fact
                            if len(self.tables.get(table1, set())) >= len(self.tables.get(table2, set())):
                                fact_table, dim_table = table1, table2
                            else:
                                fact_table, dim_table = table2, table1

                        assoc = QlikAssociation(
                            from_table=fact_table,
                            from_field=field,
                            to_table=dim_table,
                            to_field=field,
                            association_type="natural"
                        )
                    else:
                        assoc = QlikAssociation(
                            from_table=table1,
                            from_field=field,
                            to_table=table2,
                            to_field=field,
                            association_type="natural"
                        )
                    
                    self.associations.append(assoc)
                    logger.debug(f"Association trouvée: {fact_table if (field.endswith('ID') or field.endswith('Id')) else table1}.{field} → {dim_table if (field.endswith('ID') or field.endswith('Id')) else table2}.{field}")
        
        logger.info(f"Trouvé {len(self.associations)} associations")
        return self.associations

    def extract_synthetic_keys(self) -> List[str]:
        """
        Identifier les clés synthétiques Qlik.
        
        Returns:
            Liste des noms de clés synthétiques
        """
        synthetic_keys = []
        
        # Les clés synthétiques Qlik commencent souvent par $Syn
        for table in self.tables.keys():
            if table.startswith('$Syn'):
                synthetic_keys.append(table)
        
        return synthetic_keys


# ── Data-type inference heuristics ──────────────────────────────
_NUMERIC_SUFFIXES = (
    "amount", "price", "cost", "total", "revenue", "salary", "rate",
    "balance", "fee", "tax", "discount", "margin", "budget",
    "weight", "height", "latitude", "longitude",
)
_INT_SUFFIXES = (
    "id", "quantity", "qty", "count", "number", "num", "index",
    "year", "quarter", "month", "day", "age", "rank", "order",
)
_DATE_SUFFIXES = ("date", "time", "datetime", "timestamp")


def _infer_column_datatype(col_name: str, measure_columns: set = None) -> str:
    """Infer a Power BI dataType from the column name.

    Returns one of: 'string', 'int64', 'double', 'dateTime'.
    """
    low = col_name.lower().strip()

    # Columns referenced by SUM / AVG measures should be numeric
    if measure_columns and col_name in measure_columns:
        return "double"

    # Date columns
    if any(low == s or low.endswith(s) for s in _DATE_SUFFIXES):
        return "dateTime"

    # Decimal-like columns (prices, amounts …) — check BEFORE int so
    # "discount" is not caught by the "count" suffix in _INT_SUFFIXES.
    if any(low == s or low.endswith(s) for s in _NUMERIC_SUFFIXES):
        return "double"

    # Integer-like columns (IDs, counts, years …)
    if any(low == s or low.endswith(s) for s in _INT_SUFFIXES):
        return "int64"

    # UnitPrice-style compound names: check if any suffix matches
    # by splitting on camelCase / underscore boundaries.
    # Split the ORIGINAL name (preserving case) so that camelCase
    # transitions like DateCommande → ["Date", "Commande"] work.
    import re as _re
    tokens = [t.lower() for t in _re.split(r'(?<=[a-z])(?=[A-Z])|_', col_name.strip()) if t]
    for tok in tokens:
        if tok in _DATE_SUFFIXES:
            return "dateTime"
        if tok in ("price", "amount", "cost", "total", "revenue", "salary",
                   "rate", "balance", "fee", "tax", "discount", "margin",
                   "montant", "prix", "solde"):
            return "double"
        if tok in ("id", "qty", "quantity", "count", "num", "number",
                   "year", "quarter", "month", "day", "age", "rank"):
            return "int64"

    return "string"


class QlikToPowerBIModelConverter:
    """Convertit un modèle de données Qlik en modèle Power BI."""

    def __init__(self):
        """Initialiser le convertisseur."""
        self.relationships: List[PowerBIRelationship] = []
        self.hierarchies: List[PowerBIHierarchy] = []
        self.calculated_columns: List[PowerBICalculatedColumn] = []

    def convert_association_to_relationship(
        self,
        association: QlikAssociation,
        table_info: Dict[str, Set[str]]
    ) -> PowerBIRelationship:
        """
        Convertir une association Qlik en relation Power BI.
        
        Args:
            association: Association Qlik
            table_info: Informations sur les tables
            
        Returns:
            Relation Power BI
        """
        # Déterminer la cardinalité
        # Heuristiques basées sur les noms de champs
        from_field = association.from_field
        to_field = association.to_field
        
        if from_field.endswith('ID') or from_field.endswith('Id'):
            # Probablement une relation Many-to-One
            cardinality = RelationshipCardinality.MANY_TO_ONE
        elif to_field.endswith('ID') or to_field.endswith('Id'):
            cardinality = RelationshipCardinality.ONE_TO_MANY
        else:
            # Par défaut
            cardinality = RelationshipCardinality.MANY_TO_ONE
        
        # Direction du filtre croisé
        # En Power BI, par défaut Single direction
        cross_filter = CrossFilterDirection.SINGLE
        
        relationship = PowerBIRelationship(
            name=f"{association.from_table}_{association.to_table}",
            from_table=association.from_table,
            from_column=association.from_field,
            to_table=association.to_table,
            to_column=association.to_field,
            cardinality=cardinality,
            cross_filter_direction=cross_filter,
            is_active=True
        )
        
        return relationship

    def create_date_hierarchy(
        self,
        table_name: str,
        date_column: str
    ) -> PowerBIHierarchy:
        """
        Créer une hiérarchie de dates standard.
        
        Args:
            table_name: Nom de la table
            date_column: Nom de la colonne de date
            
        Returns:Hiérarchie Power BI
        """
        hierarchy = PowerBIHierarchy(
            name=f"{date_column} Hierarchy",
            table=table_name,
            levels=[
                ("Year", "Year"),
                ("Quarter", "Quarter"),
                ("Month", "Month"),
                ("Day", "Day")
            ],
            hidden=False
        )
        
        return hierarchy

    # ── Qlik → DAX expression mapping ──────────────────────────────
    _QLIK_TO_DAX_FUNC = {
        "sum": "SUM",
        "count": "COUNT",
        "countnonnull": "COUNTA",
        "avg": "AVERAGE",
        "average": "AVERAGE",
        "min": "MIN",
        "max": "MAX",
    }

    def _qlik_expr_to_dax(
        self,
        qlik_expr: str,
        col_table_map: Dict[str, str],
    ) -> str:
        """Convert a simple Qlik expression to DAX.

        Supports: Sum(Column), Count(Column), Avg(Column), etc.
        Falls back to wrapping with SUM if the pattern is unrecognised.
        """
        import re as _re
        m = _re.match(r'(\w+)\(([^)]+)\)', qlik_expr.strip())
        if m:
            func, col = m.group(1).lower(), m.group(2).strip()
            dax_func = self._QLIK_TO_DAX_FUNC.get(func, "SUM")
            table = col_table_map.get(col, "")
            if table:
                return f"{dax_func}('{table}'[{col}])"
            return f"{dax_func}([{col}])"
        # Not a recognised aggregate – return as-is with a comment
        return f"/* TODO: review */ {qlik_expr}"

    def generate_model_bim(
        self,
        relationships: List[PowerBIRelationship],
        tables: List[str],
        hierarchies: List[PowerBIHierarchy] = None,
        qlik_measures: Optional[List[Dict]] = None,
    ) -> Dict:
        """
        Générer le fichier .bim (Business Intelligence Model) pour Power BI.
        
        Args:
            relationships: Liste des relations
            tables: Liste des tables
            hierarchies: Liste des hiérarchies
            qlik_measures: Mesures Qlik extraites [{name, expression, label}]
            
        Returns:
            Structure BIM (dictionnaire)
        """
        bim_model = {
            "name": "Migrated Qlik Model",
            "compatibilityLevel": 1600,
            "model": {
                "culture": "en-US",
                "dataSources": [],
                "tables": [],
                "relationships": [],
                "annotations": [
                    {
                        "name": "MigratedFrom",
                        "value": "Qlik Sense"
                    }
                ]
            }
        }
        
        # Ajouter les tables
        # tables parameter is a list of names, but self.extractor may have field info
        fields_map: Dict[str, Set[str]] = {}
        if hasattr(self, '_fields_map'):
            fields_map = self._fields_map

        # Determine which columns are referenced by SUM-like measures
        # so that we can force them to numeric types.
        measure_columns: set = set()
        if qlik_measures:
            import re as _re
            for qm in qlik_measures:
                m = _re.search(r'\(([^)]+)\)', qm.get('expression', ''))
                if m:
                    measure_columns.add(m.group(1).strip())

        # Format string defaults per data type
        _FORMAT_BY_TYPE = {
            "int64": "0",
            "double": "#,0.00",
            "dateTime": "Long Date",
        }

        for table_name in tables:
            # Build column definitions from extracted fields
            columns = []
            for field_name in sorted(fields_map.get(table_name, set())):
                dtype = _infer_column_datatype(field_name, measure_columns)
                col_def: Dict = {
                    "name": field_name,
                    "dataType": dtype,
                    "sourceColumn": field_name,
                }
                fmt = _FORMAT_BY_TYPE.get(dtype)
                if fmt:
                    col_def["formatString"] = fmt
                col_def["annotations"] = [
                    {"name": "SummarizationSetBy", "value": "Automatic"},
                ]
                if dtype == "dateTime":
                    col_def["annotations"].append(
                        {"name": "UnderlyingDateTimeDataType", "value": "Date"}
                    )
                columns.append(col_def)

            table_def = {
                "name": table_name,
                "columns": columns,
                "partitions": [
                    {
                        "name": f"{table_name}Partition",
                        "source": {
                            "type": "m",
                            "expression": f"let\\n    Source = #\\\"{table_name}\\\"\\nin\\n    Source"
                        }
                    }
                ],
                "measures": []
            }
            
            bim_model["model"]["tables"].append(table_def)

        # ── Convert Qlik measures to DAX and attach to the best table ─
        if qlik_measures:
            # Build col→table lookup for DAX generation
            col_table: Dict[str, str] = {}
            for tname, fset in fields_map.items():
                for fname in fset:
                    col_table[fname] = tname

            for qm in qlik_measures:
                qlik_expr = qm.get("expression", "")
                measure_name = qm.get("label") or qm.get("name", "Measure")
                dax_expr = self._qlik_expr_to_dax(qlik_expr, col_table)

                # Determine which table the measure belongs to
                import re as _re
                m = _re.search(r'\(([^)]+)\)', qlik_expr)
                col_ref = m.group(1).strip() if m else ""
                target_table = col_table.get(col_ref, "")
                if not target_table and bim_model["model"]["tables"]:
                    target_table = bim_model["model"]["tables"][0]["name"]

                # Infer a format string for the measure
                func_lower = qlik_expr.strip().split('(')[0].lower() if '(' in qlik_expr else ''
                if func_lower in ('sum', 'avg', 'average'):
                    meas_fmt = "#,0.00"
                elif func_lower in ('count', 'countnonnull'):
                    meas_fmt = "0"
                else:
                    meas_fmt = "#,0.00"

                # Add the measure to the target table
                for tbl in bim_model["model"]["tables"]:
                    if tbl["name"] == target_table:
                        tbl["measures"].append({
                            "name": measure_name,
                            "expression": dax_expr,
                            "formatString": meas_fmt,
                        })
                        logger.debug(f"Measure '{measure_name}' → table '{target_table}'")
                        break
        
        # Ajouter les relations
        for rel in relationships:
            relationship_def = {
                "name": rel.name,
                "fromTable": rel.from_table,
                "fromColumn": rel.from_column,
                "toTable": rel.to_table,
                "toColumn": rel.to_column,
                "crossFilteringBehavior": rel.cross_filter_direction.value,
                "securityFilteringBehavior": rel.security_filtering_behavior,
                "isActive": rel.is_active
            }
            
            bim_model["model"]["relationships"].append(relationship_def)
        
        # Ajouter les hiérarchies
        if hierarchies:
            for hierarchy in hierarchies:
                # Trouver la table correspondante
                for table in bim_model["model"]["tables"]:
                    if table["name"] == hierarchy.table:
                        if "hierarchies" not in table:
                            table["hierarchies"] = []
                        
                        hierarchy_def = {
                            "name": hierarchy.name,
                            "levels": [
                                {"name": level_name, "column": col_name, "ordinal": i}
                                for i, (level_name, col_name) in enumerate(hierarchy.levels)
                            ],
                            "hidden": hierarchy.hidden
                        }
                        
                        table["hierarchies"].append(hierarchy_def)
        
        return bim_model


class QlikModelMigrator:
    """Gestionnaire de migration du modèle de données Qlik."""

    def __init__(self):
        """Initialiser le migrateur de modèle."""
        self.extractor: Optional[QlikDataModelExtractor] = None
        self.converter = QlikToPowerBIModelConverter()

    def migrate_model(
        self,
        qlik_app_data: Dict,
        output_path: Path
    ) -> Dict:
        """
        Migrer le modèle de données complet.
        
        Args:
            qlik_app_data: Données de l'application Qlik
            output_path: Chemin de sortie pour le fichier BIM
            
        Returns:
            Résultat de la migration
        """
        logger.info("Début de la migration du modèle de données...")
        
        try:
            # Étape 1: Extraire le modèle Qlik
            self.extractor = QlikDataModelExtractor(qlik_app_data)
            tables = self.extractor.extract_tables_and_fields()
            self.converter._fields_map = tables
            associations = self.extractor.infer_associations()
            synthetic_keys = self.extractor.extract_synthetic_keys()
            
            if synthetic_keys:
                logger.warning(
                    f"Clés synthétiques détectées: {synthetic_keys}. "
                    "Révision manuelle recommandée."
                )
            
            # Étape 2: Convertir en modèle Power BI
            relationships = []
            for assoc in associations:
                rel = self.converter.convert_association_to_relationship(assoc, tables)
                relationships.append(rel)
            
            # Étape 3: Créer hiérarchies de dates
            hierarchies = []
            for table_name, fields in tables.items():
                for field in list(fields):
                    if 'date' in field.lower() or 'time' in field.lower():
                        hierarchy = self.converter.create_date_hierarchy(table_name, field)
                        hierarchies.append(hierarchy)
                        # Ensure hierarchy level columns exist in the table
                        for _level_name, col_name in hierarchy.levels:
                            tables[table_name].add(col_name)
            
            # Étape 4: Générer le fichier BIM
            qlik_measures = qlik_app_data.get('measures', [])
            bim_model = self.converter.generate_model_bim(
                relationships,
                list(tables.keys()),
                hierarchies,
                qlik_measures=qlik_measures,
            )
            
            # Étape 5: Sauvegarder
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(bim_model, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Modèle migré sauvegardé: {output_path}")
            
            return {
                'status': 'success',
                'tables_count': len(tables),
                'relationships_count': len(relationships),
                'hierarchies_count': len(hierarchies),
                'synthetic_keys': synthetic_keys,
                'output_file': str(output_path),
                'model': bim_model
            }
            
        except Exception as e:
            logger.error(f"Erreur lors de la migration du modèle: {str(e)}")
            return {
                'status': 'error',
                'error': str(e)
            }

    def generate_documentation(
        self,
        migration_result: Dict
    ) -> str:
        """
        Générer une documentation du modèle migré.
        
        Args:
            migration_result: Résultat de la migration
            
        Returns:
            Documentation en Markdown
        """
        doc = ["# Modèle de Données Migré - Qlik → Power BI\n"]
        doc.append(f"**Tables**: {migration_result['tables_count']}")
        doc.append(f"**Relations**: {migration_result['relationships_count']}")
        doc.append(f"**Hiérarchies**: {migration_result['hierarchies_count']}\n")
        
        if migration_result.get('synthetic_keys'):
            doc.append("## ⚠️ Clés Synthétiques Détectées\n")
            for key in migration_result['synthetic_keys']:
                doc.append(f"- `{key}` - Révision manuelle requise\n")
        
        # Détail des relations
        model = migration_result.get('model', {})
        relationships = model.get('model', {}).get('relationships', [])
        
        if relationships:
            doc.append("\n## Relations\n")
            for rel in relationships:
                doc.append(
                    f"- **{rel['fromTable']}**`.{rel['fromColumn']}` → "
                    f"**{rel['toTable']}**`.{rel['toColumn']}` "
                    f"({rel.get('crossFilteringBehavior', 'Single')})\n"
                )
        
        return ''.join(doc)
