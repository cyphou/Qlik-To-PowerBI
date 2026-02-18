"""
Extracteur de fichiers QVF (Qlik View File)
Permet de migrer directement les fichiers .qvf sans export JSON
"""

import json
import logging
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional, Any
import re

logger = logging.getLogger(__name__)


class QVFExtractor:
    """
    Extrait les données d'un fichier QVF Qlik Sense.
    
    Structure d'un fichier QVF:
    - C'est une archive ZIP
    - Contient des fichiers XML et JSON
    - app.xml: Métadonnées de l'application
    - loadscript.txt: Script de chargement
    - Dossiers avec objets (sheets, dimensions, measures, etc.)
    """

    def __init__(self, qvf_path: Path):
        """
        Initialiser l'extracteur.
        
        Args:
            qvf_path: Chemin vers le fichier .qvf
        """
        self.qvf_path = Path(qvf_path)
        self.app_data: Dict[str, Any] = {}
        
        if not self.qvf_path.exists():
            raise FileNotFoundError(f"Fichier QVF introuvable: {qvf_path}")
        
        if not self.qvf_path.suffix.lower() == '.qvf':
            raise ValueError(f"Format invalide. Attendu .qvf, reçu: {self.qvf_path.suffix}")

    def extract_all(self) -> Dict[str, Any]:
        """
        Extraire toutes les données du fichier QVF.
        
        Returns:
            Dictionnaire contenant toutes les données extraites
        """
        logger.info(f"Extraction du fichier QVF: {self.qvf_path}")
        
        with zipfile.ZipFile(self.qvf_path, 'r') as qvf_zip:
            # Lister le contenu
            file_list = qvf_zip.namelist()
            logger.debug(f"Fichiers dans QVF: {len(file_list)}")
            
            # Extraire les métadonnées
            self.app_data['metadata'] = self._extract_metadata(qvf_zip)
            
            # Extraire le script de chargement
            self.app_data['loadScript'] = self._extract_load_script(qvf_zip)
            
            # Extraire les dimensions
            self.app_data['dimensions'] = self._extract_dimensions(qvf_zip)
            
            # Extraire les mesures
            self.app_data['measures'] = self._extract_measures(qvf_zip)
            
            # Extraire les feuilles (sheets)
            self.app_data['sheets'] = self._extract_sheets(qvf_zip)
            
            # Extraire les visualisations
            self.app_data['visualizations'] = self._extract_visualizations(qvf_zip)
            
            # Extraire le modèle de données
            self.app_data['dataModel'] = self._extract_data_model(qvf_zip)
            
            # Extraire les variables
            self.app_data['variables'] = self._extract_variables(qvf_zip)
        
        logger.info("Extraction QVF terminée avec succès")
        return self.app_data

    def _extract_metadata(self, qvf_zip: zipfile.ZipFile) -> Dict:
        """Extraire les métadonnées de l'application."""
        metadata = {}
        
        try:
            # Lire app.xml s'il existe
            if 'app.xml' in qvf_zip.namelist():
                with qvf_zip.open('app.xml') as f:
                    tree = ET.parse(f)
                    root = tree.getroot()
                    
                    metadata['name'] = root.findtext('.//Title', 'Untitled App')
                    metadata['description'] = root.findtext('.//Description', '')
                    metadata['author'] = root.findtext('.//Author', '')
                    metadata['created'] = root.findtext('.//CreateDate', '')
                    metadata['modified'] = root.findtext('.//ModifyDate', '')
            
            logger.info(f"Métadonnées extraites: {metadata.get('name', 'N/A')}")
        
        except Exception as e:
            logger.warning(f"Impossible d'extraire les métadonnées: {e}")
        
        return metadata

    def _extract_load_script(self, qvf_zip: zipfile.ZipFile) -> str:
        """Extraire le script de chargement."""
        script = ""
        
        try:
            # Le script peut être dans loadscript.txt ou loadscript.qvs
            script_files = ['loadscript.txt', 'loadscript.qvs', 'LoadScript.txt']
            
            for script_file in script_files:
                if script_file in qvf_zip.namelist():
                    with qvf_zip.open(script_file) as f:
                        script = f.read().decode('utf-8', errors='ignore')
                    logger.info(f"Script de chargement extrait: {len(script)} caractères")
                    break
        
        except Exception as e:
            logger.warning(f"Impossible d'extraire le script: {e}")
        
        return script

    def _extract_dimensions(self, qvf_zip: zipfile.ZipFile) -> List[Dict]:
        """Extraire les dimensions."""
        dimensions = []
        
        try:
            # Les dimensions sont dans des fichiers JSON
            dimension_files = [f for f in qvf_zip.namelist() 
                             if 'dimension' in f.lower() and f.endswith('.json')]
            
            for dim_file in dimension_files:
                with qvf_zip.open(dim_file) as f:
                    dim_data = json.load(f)
                    
                    # Format Qlik Engine JSON
                    if 'qDim' in dim_data:
                        dimension = {
                            'name': dim_data.get('qMetaDef', {}).get('title', ''),
                            'field': dim_data.get('qDim', {}).get('qFieldDefs', [''])[0],
                            'label': dim_data.get('qDim', {}).get('qFieldLabels', [''])[0],
                            'id': dim_data.get('qInfo', {}).get('qId', '')
                        }
                        dimensions.append(dimension)
            
            logger.info(f"Dimensions extraites: {len(dimensions)}")
        
        except Exception as e:
            logger.warning(f"Impossible d'extraire les dimensions: {e}")
        
        return dimensions

    def _extract_measures(self, qvf_zip: zipfile.ZipFile) -> List[Dict]:
        """Extraire les mesures."""
        measures = []
        
        try:
            # Les mesures sont dans des fichiers JSON
            measure_files = [f for f in qvf_zip.namelist() 
                           if 'measure' in f.lower() and f.endswith('.json')]
            
            for measure_file in measure_files:
                with qvf_zip.open(measure_file) as f:
                    measure_data = json.load(f)
                    
                    # Format Qlik Engine JSON
                    if 'qMeasure' in measure_data:
                        measure = {
                            'name': measure_data.get('qMetaDef', {}).get('title', ''),
                            'expression': measure_data.get('qMeasure', {}).get('qDef', ''),
                            'label': measure_data.get('qMeasure', {}).get('qLabel', ''),
                            'id': measure_data.get('qInfo', {}).get('qId', '')
                        }
                        measures.append(measure)
            
            logger.info(f"Mesures extraites: {len(measures)}")
        
        except Exception as e:
            logger.warning(f"Impossible d'extraire les mesures: {e}")
        
        return measures

    def _extract_sheets(self, qvf_zip: zipfile.ZipFile) -> List[Dict]:
        """Extraire les feuilles (pages)."""
        sheets = []
        
        try:
            # Les feuilles sont dans des fichiers JSON
            sheet_files = [f for f in qvf_zip.namelist() 
                         if 'sheet' in f.lower() and f.endswith('.json')]
            
            for sheet_file in sheet_files:
                with qvf_zip.open(sheet_file) as f:
                    sheet_data = json.load(f)
                    
                    sheet = {
                        'name': sheet_data.get('qMetaDef', {}).get('title', ''),
                        'description': sheet_data.get('qMetaDef', {}).get('description', ''),
                        'id': sheet_data.get('qInfo', {}).get('qId', ''),
                        'cells': sheet_data.get('cells', [])
                    }
                    sheets.append(sheet)
            
            logger.info(f"Feuilles extraites: {len(sheets)}")
        
        except Exception as e:
            logger.warning(f"Impossible d'extraire les feuilles: {e}")
        
        return sheets

    def _extract_visualizations(self, qvf_zip: zipfile.ZipFile) -> List[Dict]:
        """Extraire les visualisations."""
        visualizations = []
        
        try:
            # Les visualisations peuvent être dans plusieurs endroits
            viz_patterns = ['object', 'chart', 'visualization']
            
            for pattern in viz_patterns:
                viz_files = [f for f in qvf_zip.namelist() 
                           if pattern in f.lower() and f.endswith('.json')]
                
                for viz_file in viz_files:
                    try:
                        with qvf_zip.open(viz_file) as f:
                            viz_data = json.load(f)
                            
                            # Identifier le type de visualisation
                            viz_type = viz_data.get('visualization', '')
                            
                            if not viz_type:
                                # Essayer d'autres formats
                                viz_type = viz_data.get('qInfo', {}).get('qType', 'unknown')
                            
                            visualization = {
                                'type': viz_type,
                                'name': viz_data.get('title', ''),
                                'id': viz_data.get('qInfo', {}).get('qId', ''),
                                'properties': viz_data
                            }
                            visualizations.append(visualization)
                    
                    except json.JSONDecodeError:
                        continue
            
            logger.info(f"Visualisations extraites: {len(visualizations)}")
        
        except Exception as e:
            logger.warning(f"Impossible d'extraire les visualisations: {e}")
        
        return visualizations

    def _extract_data_model(self, qvf_zip: zipfile.ZipFile) -> Dict:
        """
        Extraire le modèle de données.
        
        Le modèle est déduit du script de chargement.
        """
        model = {
            'tables': [],
            'associations': []
        }
        
        try:
            script = self.app_data.get('loadScript', '')
            
            if not script:
                return model
            
            # Parser les tables depuis le script Qlik
            # Format Qlik: TableName:\n LOAD field1, field2 ... FROM/RESIDENT/INLINE
            table_load_pattern = re.compile(
                r'(\w+)\s*:\s*\r?\n'              # table label  (e.g. "Sales:")
                r'\s*LOAD\s+'                       # LOAD keyword
                r'(.*?)'                             # field list   (non-greedy)
                r'\s+(?:FROM|RESIDENT|INLINE)\b',   # source type keyword
                re.IGNORECASE | re.DOTALL,
            )

            for match in table_load_pattern.finditer(script):
                table_name = match.group(1)
                fields_str = match.group(2)
                # Extract individual field names (handle "expr AS alias")
                field_list = [f.strip().split(' as ')[-1].strip()
                              for f in fields_str.split(',')]
                field_list = [f for f in field_list if f]

                model['tables'].append({
                    'name': table_name,
                    'fields': [{'name': f} for f in field_list]
                })
            
            logger.info(f"Modèle de données extrait: {len(model['tables'])} tables")
        
        except Exception as e:
            logger.warning(f"Impossible d'extraire le modèle: {e}")
        
        return model

    def _extract_variables(self, qvf_zip: zipfile.ZipFile) -> List[Dict]:
        """Extraire les variables."""
        variables = []
        
        try:
            # Les variables peuvent être dans un fichier variables.json
            variable_files = [f for f in qvf_zip.namelist() 
                            if 'variable' in f.lower() and f.endswith('.json')]
            
            for var_file in variable_files:
                with qvf_zip.open(var_file) as f:
                    var_data = json.load(f)
                    
                    variable = {
                        'name': var_data.get('qName', ''),
                        'value': var_data.get('qDefinition', ''),
                        'comment': var_data.get('qComment', '')
                    }
                    variables.append(variable)
            
            logger.info(f"Variables extraites: {len(variables)}")
        
        except Exception as e:
            logger.warning(f"Impossible d'extraire les variables: {e}")
        
        return variables

    def export_to_json(self, output_path: Path) -> Path:
        """
        Exporter les données extraites au format JSON compatible avec les autres modules.
        
        Args:
            output_path: Chemin du fichier JSON de sortie
            
        Returns:
            Chemin du fichier créé
        """
        if not self.app_data:
            self.extract_all()
        
        # Formater pour compatibilité avec les autres modules
        export_data = {
            'name': self.app_data.get('metadata', {}).get('name', 'Unnamed App'),
            'description': self.app_data.get('metadata', {}).get('description', ''),
            'loadScript': self.app_data.get('loadScript', ''),
            'dimensions': self.app_data.get('dimensions', []),
            'measures': self.app_data.get('measures', []),
            'sheets': self.app_data.get('sheets', []),
            'visualizations': self.app_data.get('visualizations', []),
            'tables': self.app_data.get('dataModel', {}).get('tables', []),
            'associations': self.app_data.get('dataModel', {}).get('associations', []),
            'variables': self.app_data.get('variables', []),
            'metadata': self.app_data.get('metadata', {})
        }
        
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Données exportées vers: {output_path}")
        return output_path

    def get_summary(self) -> Dict:
        """
        Obtenir un résumé des données extraites.
        
        Returns:
            Dictionnaire avec les statistiques
        """
        if not self.app_data:
            self.extract_all()
        
        return {
            'app_name': self.app_data.get('metadata', {}).get('name', 'N/A'),
            'dimensions_count': len(self.app_data.get('dimensions', [])),
            'measures_count': len(self.app_data.get('measures', [])),
            'sheets_count': len(self.app_data.get('sheets', [])),
            'visualizations_count': len(self.app_data.get('visualizations', [])),
            'tables_count': len(self.app_data.get('dataModel', {}).get('tables', [])),
            'variables_count': len(self.app_data.get('variables', [])),
            'script_length': len(self.app_data.get('loadScript', ''))
        }


def extract_qvf(qvf_path: Path, output_json_path: Optional[Path] = None) -> Dict:
    """
    Fonction utilitaire pour extraire rapidement un fichier QVF.
    
    Args:
        qvf_path: Chemin vers le fichier .qvf
        output_json_path: Chemin optionnel pour exporter en JSON
        
    Returns:
        Données extraites
    """
    extractor = QVFExtractor(qvf_path)
    data = extractor.extract_all()
    
    if output_json_path:
        extractor.export_to_json(output_json_path)
    
    return data
