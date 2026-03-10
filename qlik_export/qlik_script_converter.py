"""Qlik Script to Power Query M converter."""
import logging
import re
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class QlikCommandType(Enum):
    """Types de commandes Qlik."""
    LOAD = 'LOAD'
    SQL = 'SQL'
    RESIDENT = 'RESIDENT'
    FROM = 'FROM'
    WHERE = 'WHERE'
    LEFT_JOIN = 'LEFT JOIN'
    INNER_JOIN = 'INNER JOIN'
    OUTER_JOIN = 'OUTER JOIN'
    CONCATENATE = 'CONCATENATE'
    QUALIFY = 'QUALIFY'
    UNQUALIFY = 'UNQUALIFY'
    MAPPING = 'MAPPING'
    FOR_EACH = 'FOR EACH'
    INLINE = 'INLINE'
    PRECEDING = 'PRECEDING'
    STORE = 'STORE'


@dataclass
class QlikLoadStatement:
    """Représente une instruction LOAD Qlik."""
    fields: List[str]
    source: str
    source_type: str  # 'file', 'sql', 'resident', 'inline'
    where_clause: Optional[str] = None
    table_name: Optional[str] = None


class QlikScriptToPowerQueryConverter:
    """Convertit les scripts Qlik en scripts Power Query M."""

    # Mapping des fonctions Qlik → Power Query M
    FUNCTION_MAP = {
        # Fonctions de texte
        'Upper': 'Text.Upper',
        'Lower': 'Text.Lower',
        'Len': 'Text.Length',
        'Trim': 'Text.Trim',
        'LTrim': 'Text.TrimStart',
        'RTrim': 'Text.TrimEnd',
        'SubField': 'Text.Split',
        'Left': 'Text.Start',
        'Right': 'Text.End',
        'Mid': 'Text.Middle',
        'Replace': 'Text.Replace',
        
        # Fonctions de date
        'Date': 'Date.From',
        'Today': 'Date.From(DateTime.LocalNow())',
        'Now': 'DateTime.LocalNow',
        'Year': 'Date.Year',
        'Month': 'Date.Month',
        'Day': 'Date.Day',
        'MonthName': 'Date.MonthName',
        'WeekDay': 'Date.DayOfWeek',
        'YearStart': 'Date.StartOfYear',
        'YearEnd': 'Date.EndOfYear',
        'MonthStart': 'Date.StartOfMonth',
        'MonthEnd': 'Date.EndOfMonth',
        
        # Fonctions numériques
        'Round': 'Number.Round',
        'Floor': 'Number.RoundDown',
        'Ceil': 'Number.RoundUp',
        'Abs': 'Number.Abs',
        'Sqrt': 'Number.Sqrt',
        'Exp': 'Number.Exp',
        'Log': 'Number.Log',
        'Mod': 'Number.Mod',
        
        # Fonctions conditionnelles
        'If': 'if',
        'Null': 'null',
        'IsNull': '= null',
        
        # Fonctions d'agrégation (pour Group By)
        'Sum': 'List.Sum',
        'Avg': 'List.Average',
        'Count': 'List.Count',
        'Min': 'List.Min',
        'Max': 'List.Max',
    }

    # Mapping types de sources
    SOURCE_TYPE_MAP = {
        'txt': 'Csv.Document',
        'csv': 'Csv.Document',
        'xlsx': 'Excel.Workbook',
        'xls': 'Excel.Workbook',
        'qvd': 'Qvd.Document',  # Nécessite connecteur personnalisé
        'sql': 'Sql.Database',
        'odbc': 'Odbc.DataSource',
    }

    @staticmethod
    def convert_qlik_function(qlik_func: str) -> str:
        """
        Convertit une fonction Qlik en équivalent Power Query M.
        
        Args:
            qlik_func: Expression de fonction Qlik
            
        Returns:
            Expression Power Query M
        """
        pq_func = qlik_func
        
        # Remplacer les fonctions connues
        for qlik_name, pq_name in QlikScriptToPowerQueryConverter.FUNCTION_MAP.items():
            pattern = rf'\b{qlik_name}\s*\('
            if re.search(pattern, pq_func, re.IGNORECASE):
                pq_func = re.sub(pattern, f'{pq_name}(', pq_func, flags=re.IGNORECASE)
        
        # Convertir l'opérateur de concaténation & en &
        pq_func = pq_func.replace(' & ', ' & ')
        
        return pq_func

    @staticmethod
    def parse_qlik_load(qlik_script: str) -> QlikLoadStatement:
        """
        Parse une instruction LOAD Qlik.
        
        Args:
            qlik_script: Script Qlik LOAD
            
        Returns:
            QlikLoadStatement parsé
        """
        # Nettoyer le script
        script = ' '.join(qlik_script.split())
        
        # Extraire les champs (entre LOAD et FROM/RESIDENT/INLINE)
        load_match = re.search(
            r'LOAD\s+(.*?)\s+(?:FROM|RESIDENT|INLINE)',
            script,
            re.IGNORECASE | re.DOTALL
        )
        
        if not load_match:
            raise ValueError("LOAD statement mal formé")
        
        fields_str = load_match.group(1)
        fields = [f.strip().rstrip(',') for f in fields_str.split(',')]
        
        # Déterminer le type de source
        if 'FROM' in script.upper():
            source_type = 'file'
            from_match = re.search(r'FROM\s+\[(.*?)\]', script, re.IGNORECASE)
            source = from_match.group(1) if from_match else ''
        elif 'RESIDENT' in script.upper():
            source_type = 'resident'
            resident_match = re.search(r'RESIDENT\s+(\w+)', script, re.IGNORECASE)
            source = resident_match.group(1) if resident_match else ''
        elif 'INLINE' in script.upper():
            source_type = 'inline'
            source = 'inline_data'
        else:
            source_type = 'sql'
            source = ''
        
        # Extraire WHERE clause
        where_match = re.search(r'WHERE\s+(.*?)(?:;|$)', script, re.IGNORECASE)
        where_clause = where_match.group(1).strip() if where_match else None
        
        return QlikLoadStatement(
            fields=fields,
            source=source,
            source_type=source_type,
            where_clause=where_clause
        )

    @staticmethod
    def _parse_field_expression(field: str) -> Tuple[str, Optional[str]]:
        """
        Parse une expression de champ Qlik.
        
        Returns:
            (expression, alias) ou (field_name, None)
        """
        # Vérifier si c'est un alias (field as alias)
        if ' as ' in field.lower():
            parts = re.split(r'\s+as\s+', field, maxsplit=1, flags=re.IGNORECASE)
            expr = parts[0].strip()
            alias = parts[1].strip()
            return (expr, alias)
        else:
            # Juste un nom de champ
            return (field.strip(), None)

    @staticmethod
    def convert_load_to_powerquery(load_stmt: QlikLoadStatement) -> str:
        """
        Convertit une instruction LOAD en Power Query M.
        
        Args:
            load_stmt: QlikLoadStatement
            
        Returns:
            Script Power Query M
        """
        pq_script = []
        
        # Étape 1: Charger la source
        if load_stmt.source_type == 'file':
            # Déterminer le type de fichier
            file_ext = load_stmt.source.split('.')[-1].lower()
            pq_function = QlikScriptToPowerQueryConverter.SOURCE_TYPE_MAP.get(
                file_ext, 'Csv.Document'
            )
            
            if file_ext in ['xlsx', 'xls']:
                pq_script.append(f'let\n    Source = Excel.Workbook(File.Contents("{load_stmt.source}"), null, true),')
                pq_script.append('    Sheet1 = Source{{[Item="Sheet1",Kind="Sheet"]}}[Data],')
                pq_script.append('    PromotedHeaders = Table.PromoteHeaders(Sheet1, [PromoteAllScalars=true])')
                base_table = 'PromotedHeaders'
            elif file_ext in ['csv', 'txt']:
                pq_script.append(f'let\n    Source = Csv.Document(File.Contents("{load_stmt.source}"),[Delimiter=",", Columns=auto, Encoding=65001, QuoteStyle=QuoteStyle.None]),')
                pq_script.append('    PromotedHeaders = Table.PromoteHeaders(Source, [PromoteAllScalars=true])')
                base_table = 'PromotedHeaders'
            else:
                pq_script.append(f'let\n    Source = {pq_function}(File.Contents("{load_stmt.source}"))')
                base_table = 'Source'
                
        elif load_stmt.source_type == 'resident':
            pq_script.append(f'let\n    Source = {load_stmt.source}')
            base_table = 'Source'
            
        elif load_stmt.source_type == 'sql':
            pq_script.append('let\n    Source = Sql.Database("ServerName", "DatabaseName"),')
            pq_script.append('    Table = Source{{[Schema="dbo",Item="TableName"]}}[Data]')
            base_table = 'Table'
        
        # Étape 2: Sélectionner et transformer les colonnes
        if load_stmt.fields:
            # Séparer les colonnes simples des colonnes calculées
            simple_columns = []
            calculated_columns = []
            
            for field in load_stmt.fields:
                expr, alias = QlikScriptToPowerQueryConverter._parse_field_expression(field)
                
                # Si c'est une expression (contient des fonctions ou opérateurs)
                if re.search(r'[()\+\-\*/]|\bif\b|\bupper\b|\blower\b', expr, re.IGNORECASE):
                    # Colonne calculée
                    pq_expr = QlikScriptToPowerQueryConverter.convert_qlik_function(expr)
                    col_name = alias if alias else expr
                    calculated_columns.append((col_name, pq_expr))
                else:
                    # Colonne simple (peut avoir un alias)
                    if alias:
                        calculated_columns.append((alias, f'[{expr}]'))
                    else:
                        simple_columns.append(expr)
            
            # Ajouter les colonnes calculées
            if calculated_columns:
                for i, (col_name, pq_expr) in enumerate(calculated_columns):
                    pq_script.append(f',\n    AddColumn{i+1} = Table.AddColumn({base_table}, "{col_name}", each {pq_expr})')
                    base_table = f'AddColumn{i+1}'
            
            # Sélectionner uniquement les colonnes nécessaires si spécifié
            if simple_columns or calculated_columns:
                all_columns = simple_columns + [name for name, _ in calculated_columns]
                column_list = '", "'.join(all_columns)
                pq_script.append(f',\\n    SelectedColumns = Table.SelectColumns({base_table}, {{"{column_list}"}})')
                base_table = 'SelectedColumns'
        
        # Étape 3: Appliquer WHERE clause
        if load_stmt.where_clause:
            # Convertir la condition WHERE en Power Query
            pq_condition = QlikScriptToPowerQueryConverter.convert_qlik_function(
                load_stmt.where_clause
            )
            pq_script.append(f',\n    Filtered = Table.SelectRows({base_table}, each ({pq_condition}))')
            base_table = 'Filtered'
        
        # Étape finale
        pq_script.append(f'\nin\n    {base_table}')
        
        return '\n'.join(pq_script)

    @staticmethod
    def convert_qlik_script_to_powerquery(qlik_script: str) -> str:
        """
        Convertit un script Qlik complet en Power Query M.
        
        Handles: LOAD, INLINE, CONCATENATE, MAPPING LOAD, QUALIFY/UNQUALIFY,
        preceding LOADs, FOR EACH wildcards, and LET/SET variables.
        
        Args:
            qlik_script: Script Qlik complet
            
        Returns:
            Script Power Query M
        """
        pq_scripts = []
        
        # ── Pre-process: extract QUALIFY/UNQUALIFY, LET/SET ───
        qualify_fields: List[str] = []
        unqualify_all = False
        variables: Dict[str, str] = {}
        
        for line in qlik_script.split('\n'):
            stripped = line.strip()
            # QUALIFY *  or QUALIFY field1, field2
            q_match = re.match(r'^QUALIFY\s+(.+);?\s*$', stripped, re.IGNORECASE)
            if q_match:
                fields = q_match.group(1).strip().rstrip(';')
                if fields == '*':
                    qualify_fields = ['*']
                else:
                    qualify_fields.extend(f.strip() for f in fields.split(','))
            # UNQUALIFY *  or UNQUALIFY field1, field2
            uq_match = re.match(r'^UNQUALIFY\s+(.+);?\s*$', stripped, re.IGNORECASE)
            if uq_match:
                fields = uq_match.group(1).strip().rstrip(';')
                if fields == '*':
                    unqualify_all = True
                    qualify_fields = []
            # LET vName = expression;  or  SET vName = value;
            var_match = re.match(r'^(?:LET|SET)\s+(\w+)\s*=\s*(.+?);?\s*$', stripped, re.IGNORECASE)
            if var_match:
                variables[var_match.group(1)] = var_match.group(2).strip()
        
        # ── Expand variables in script ────────────────────────
        processed = qlik_script
        for vname, vval in variables.items():
            processed = processed.replace(f'$({vname})', vval)
        
        # ── Handle FOR EACH wildcards ─────────────────────────
        for_each_match = re.search(
            r'FOR\s+EACH\s+(\w+)\s+IN\s+FileList\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)',
            processed, re.IGNORECASE
        )
        if for_each_match:
            var_name = for_each_match.group(1)
            file_pattern = for_each_match.group(2)
            folder = file_pattern.rsplit('\\', 1)[0] if '\\' in file_pattern else file_pattern.rsplit('/', 1)[0]
            ext = file_pattern.rsplit('.', 1)[-1] if '.' in file_pattern else 'csv'
            pq_scripts.append(f'// FOR EACH {var_name} IN FileList pattern → Folder.Files')
            pq_scripts.append(f'let')
            pq_scripts.append(f'    Source = Folder.Files("{folder}"),')
            pq_scripts.append(f'    FilteredFiles = Table.SelectRows(Source, each Text.EndsWith([Name], ".{ext}")),')
            pq_scripts.append(f'    CombinedData = Table.Combine(Table.TransformRows(FilteredFiles, each Csv.Document([Content], [Delimiter=",", Encoding=65001])))')
            pq_scripts.append(f'in')
            pq_scripts.append(f'    CombinedData')
            pq_scripts.append('')
        
        # ── Handle INLINE loads ───────────────────────────────
        inline_pattern = re.compile(
            r'(?:(\w+):[\s\n]+)?'  # optional table_name:
            r'LOAD\s+(.*?)\s+'
            r'INLINE\s*\[(.*?)\]',
            re.IGNORECASE | re.DOTALL
        )
        for m in inline_pattern.finditer(processed):
            table_name = m.group(1) or 'InlineTable'
            fields_str = m.group(2)
            inline_data = m.group(3)
            
            # Parse inline data rows
            rows = [r.strip() for r in inline_data.strip().split('\n') if r.strip()]
            if rows:
                header = rows[0]
                col_names = [c.strip() for c in header.split(',')]
                data_rows = rows[1:]
                
                col_defs = ', '.join([f'"{c}"' for c in col_names])
                row_strs = []
                for row in data_rows:
                    vals = [v.strip() for v in row.split(',')]
                    row_str = '{' + ', '.join([f'"{v}"' for v in vals]) + '}'
                    row_strs.append(f'    {row_str}')
                
                pq_scripts.append(f'// Inline table: {table_name}')
                pq_scripts.append('let')
                pq_scripts.append(f'    Source = #table({{{col_defs}}}, {{')
                pq_scripts.append(',\n'.join(row_strs))
                pq_scripts.append('    })')
                pq_scripts.append('in')
                pq_scripts.append('    Source')
                pq_scripts.append('')
        
        # ── Handle MAPPING LOAD → lookup table ───────────────
        mapping_pattern = re.compile(
            r'(\w+):\s*\n?\s*MAPPING\s+LOAD\s+(.*?)\s+FROM\s+\[([^\]]+)\]',
            re.IGNORECASE | re.DOTALL
        )
        for m in mapping_pattern.finditer(processed):
            map_name = m.group(1)
            fields_str = m.group(2)
            source_path = m.group(3)
            
            pq_scripts.append(f'// Mapping table: {map_name} (use as lookup in Power BI)')
            pq_scripts.append('let')
            ext = source_path.rsplit('.', 1)[-1].lower() if '.' in source_path else 'csv'
            if ext in ('xlsx', 'xls'):
                pq_scripts.append(f'    Source = Excel.Workbook(File.Contents("{source_path}"), null, true),')
                pq_scripts.append(f'    Sheet = Source{{0}}[Data],')
                pq_scripts.append(f'    Promoted = Table.PromoteHeaders(Sheet, [PromoteAllScalars=true])')
            else:
                pq_scripts.append(f'    Source = Csv.Document(File.Contents("{source_path}"), [Delimiter=",", Encoding=65001]),')
                pq_scripts.append(f'    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars=true])')
            pq_scripts.append('in')
            pq_scripts.append('    Promoted')
            pq_scripts.append('')
        
        # ── Handle CONCATENATE(Table) LOAD → Table.Combine ───
        concat_pattern = re.compile(
            r'CONCATENATE\s*\(\s*(\w+)\s*\)\s*\n?\s*LOAD',
            re.IGNORECASE
        )
        
        # ── Standard LOAD statements ──────────────────────────
        load_statements = re.split(r'\n(?=(?:\w+:\s*\n?\s*)?LOAD\s)', processed, flags=re.IGNORECASE)
        
        for i, load_stmt_str in enumerate(load_statements):
            if not load_stmt_str.strip():
                continue
            
            # Skip if it's a MAPPING LOAD (already handled)
            if re.search(r'\bMAPPING\s+LOAD\b', load_stmt_str, re.IGNORECASE):
                continue
            # Skip if it's an INLINE (already handled)
            if re.search(r'\bINLINE\s*\[', load_stmt_str, re.IGNORECASE):
                continue
            # Skip non-LOAD lines
            if not re.search(r'\bLOAD\b', load_stmt_str, re.IGNORECASE):
                continue
                
            try:
                # Check for CONCATENATE prefix
                is_concat = bool(concat_pattern.search(load_stmt_str))
                concat_target = None
                if is_concat:
                    cm = concat_pattern.search(load_stmt_str)
                    concat_target = cm.group(1) if cm else None
                
                # Extract table name prefix
                table_name_match = re.match(r'^(\w+):\s*\n?\s*(?:CONCATENATE\s*\(\w+\)\s*)?LOAD', load_stmt_str, re.IGNORECASE)
                table_label = table_name_match.group(1) if table_name_match else f'Table{i+1}'
                
                # Parser l'instruction
                load_stmt = QlikScriptToPowerQueryConverter.parse_qlik_load(load_stmt_str)
                load_stmt.table_name = table_label
                
                # Convertir en Power Query
                pq_script = QlikScriptToPowerQueryConverter.convert_load_to_powerquery(load_stmt)
                
                if is_concat and concat_target:
                    pq_scripts.append(f'// CONCATENATE({concat_target}) → Table.Combine')
                    pq_scripts.append(f'// Append this result to {concat_target} using Table.Combine')
                
                pq_scripts.append(f'// Query: {table_label}')
                pq_scripts.append(pq_script)
                pq_scripts.append('')
                
            except Exception as e:
                logger.error(f'Erreur lors de la conversion: {str(e)}')
                pq_scripts.append(f'// Erreur de conversion: {str(e)}')
                pq_scripts.append(f'// Script Qlik original:\n// {load_stmt_str}')
                pq_scripts.append('')
        
        return '\n'.join(pq_scripts)


class QlikScriptMigrator:
    """Gestionnaire de migration des scripts Qlik."""

    def __init__(self):
        """Initialiser le migrateur de scripts."""
        self.converter = QlikScriptToPowerQueryConverter()

    def migrate_script_file(self, qlik_script_path: str, output_path: str) -> Dict[str, str]:
        """
        Migrer un fichier de script Qlik vers Power Query M.
        
        Args:
            qlik_script_path: Chemin du script Qlik (.qvs)
            output_path: Chemin de sortie (.pq ou .m)
            
        Returns:
            Dictionnaire avec résultats
        """
        logger.info(f'Migration du script: {qlik_script_path}')
        
        try:
            # Lire le script Qlik
            with open(qlik_script_path, 'r', encoding='utf-8') as f:
                qlik_script = f.read()
            
            # Convertir
            pq_script = self.converter.convert_qlik_script_to_powerquery(qlik_script)
            
            # Sauvegarder
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(pq_script)
            
            logger.info(f'Script migré sauvegardé: {output_path}')
            
            return {
                'status': 'success',
                'input': qlik_script_path,
                'output': output_path,
                'pq_script': pq_script
            }
            
        except Exception as e:
            logger.error(f'Erreur de migration: {str(e)}')
            return {
                'status': 'error',
                'input': qlik_script_path,
                'error': str(e)
            }

    def generate_conversion_report(
        self,
        qlik_script: str,
        pq_script: str
    ) -> Dict[str, any]:
        """
        Générer un rapport de conversion.
        
        Args:
            qlik_script: Script Qlik original
            pq_script: Script Power Query converti
            
        Returns:
            Rapport de conversion
        """
        # Analyser les fonctions utilisées
        qlik_functions = set(re.findall(r'\b(\w+)\s*\(', qlik_script))
        pq_functions = set(re.findall(r'\b(\w+)\.\w+\s*\(', pq_script))
        
        # Identifier les fonctions non converties
        unconverted = qlik_functions - set(self.converter.FUNCTION_MAP.keys())
        
        return {
            'qlik_functions_used': list(qlik_functions),
            'pq_functions_generated': list(pq_functions),
            'unconverted_functions': list(unconverted),
            'conversion_rate': len(qlik_functions - unconverted) / len(qlik_functions) * 100 if qlik_functions else 100,
            'recommendations': [
                f'Revoir manuellement la fonction: {func}'
                for func in unconverted
            ]
        }
