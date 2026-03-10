"""Qlik to Power BI migration module."""
import logging
import json
from typing import Dict, Any, List, Optional
from pathlib import Path
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class QlikObjectType(Enum):
    """Qlik object types."""
    APP = 'app'
    SHEET = 'sheet'
    VISUALIZATION = 'visualization'
    DIMENSION = 'dimension'
    MEASURE = 'measure'
    MASTER_ITEM = 'masterobject'


class VisualizationType(Enum):
    """Visualization type mappings."""
    BARCHART = 'barchart'
    LINECHART = 'linechart'
    PIECHART = 'piechart'
    TABLE = 'table'
    PIVOT = 'pivot-table'
    SCATTERPLOT = 'scatterplot'
    TREEMAP = 'treemap'
    KPI = 'kpi'
    GAUGE = 'gauge'
    MAP = 'map'


@dataclass
class QlikDimension:
    """Qlik dimension structure."""
    name: str
    field: str
    label: str
    grouping: Optional[str] = None


@dataclass
class QlikMeasure:
    """Qlik measure structure."""
    name: str
    expression: str
    label: str
    format: Optional[str] = None
    aggregation: Optional[str] = None


@dataclass
class QlikVisualization:
    """Qlik visualization structure."""
    id: str
    type: str
    title: str
    dimensions: List[QlikDimension]
    measures: List[QlikMeasure]
    properties: Dict[str, Any]


class QlikToPowerBIConverter:
    """Convert Qlik objects to Power BI format."""

    # Qlik to Power BI visual type mapping
    VISUAL_TYPE_MAP = {
        'barchart': 'clusteredBarChart',
        'linechart': 'lineChart',
        'piechart': 'pieChart',
        'table': 'table',
        'pivot-table': 'pivotTable',
        'scatterplot': 'scatterChart',
        'treemap': 'treemap',
        'kpi': 'card',
        'gauge': 'gauge',
        'map': 'map',
    }

    # Qlik aggregation to DAX mapping
    AGGREGATION_MAP = {
        'Sum': 'SUM',
        'Avg': 'AVERAGE',
        'Count': 'COUNT',
        'Min': 'MIN',
        'Max': 'MAX',
        'Only': 'FIRSTNONBLANK',
    }

    @staticmethod
    def convert_qlik_expression_to_dax(qlik_expr: str) -> str:
        """
        Convert Qlik expression to DAX.

        Args:
            qlik_expr: Qlik expression (e.g., "Sum(Sales)")

        Returns:
            DAX expression
        """
        # Simple conversion - enhance this based on your needs
        dax = qlik_expr

        # Replace Qlik functions with DAX equivalents
        replacements = {
            'Sum(': 'SUM(',
            'Avg(': 'AVERAGE(',
            'Count(': 'COUNT(',
            'Min(': 'MIN(',
            'Max(': 'MAX(',
            'Only(': 'FIRSTNONBLANK(',
            'If(': 'IF(',
            'Date(': 'DATE(',
            'Year(': 'YEAR(',
            'Month(': 'MONTH(',
            'Day(': 'DAY(',
        }

        for qlik_func, dax_func in replacements.items():
            dax = dax.replace(qlik_func, dax_func)

        logger.debug(f'Converted Qlik expression: {qlik_expr} -> {dax}')
        return dax

    @staticmethod
    def convert_dimension(qlik_dim: QlikDimension) -> Dict[str, Any]:
        """Convert Qlik dimension to Power BI format."""
        return {
            'name': qlik_dim.name,
            'column': qlik_dim.field,
            'displayName': qlik_dim.label or qlik_dim.name,
        }

    @staticmethod
    def convert_measure(qlik_measure: QlikMeasure) -> Dict[str, Any]:
        """Convert Qlik measure to Power BI measure."""
        dax_expression = QlikToPowerBIConverter.convert_qlik_expression_to_dax(
            qlik_measure.expression
        )

        return {
            'name': qlik_measure.name,
            'expression': dax_expression,
            'displayName': qlik_measure.label or qlik_measure.name,
            'formatString': qlik_measure.format or '#,0.00',
        }

    @staticmethod
    def convert_visualization(qlik_viz: QlikVisualization) -> Dict[str, Any]:
        """Convert Qlik visualization to Power BI visual."""
        pbi_visual_type = QlikToPowerBIConverter.VISUAL_TYPE_MAP.get(
            qlik_viz.type.lower(),
            'table'  # Default fallback
        )

        return {
            'name': qlik_viz.id,
            'visualType': pbi_visual_type,
            'title': qlik_viz.title,
            'dimensions': [
                QlikToPowerBIConverter.convert_dimension(dim)
                for dim in qlik_viz.dimensions
            ],
            'measures': [
                QlikToPowerBIConverter.convert_measure(measure)
                for measure in qlik_viz.measures
            ],
            'properties': qlik_viz.properties,
        }


class QlikMetadataExtractor:
    """Extract metadata from Qlik Sense apps."""

    def __init__(self, qlik_app_path: Path):
        """
        Initialize Qlik metadata extractor.

        Args:
            qlik_app_path: Path to Qlik app export (JSON)
        """
        self.qlik_app_path = qlik_app_path
        self.app_data: Dict[str, Any] = {}

    def load_qlik_app(self) -> Dict[str, Any]:
        """Load Qlik app from JSON export."""
        logger.info(f'Loading Qlik app from: {self.qlik_app_path}')

        with open(self.qlik_app_path, 'r', encoding='utf-8') as f:
            self.app_data = json.load(f)

        logger.info(f'Loaded Qlik app: {self.app_data.get("qTitle", "Unknown")}')
        return self.app_data

    def extract_dimensions(self) -> List[QlikDimension]:
        """Extract dimensions from Qlik app."""
        dimensions = []

        for item in self.app_data.get('properties', {}).get('qDimensionList', {}).get('qItems', []):
            dim = QlikDimension(
                name=item.get('qInfo', {}).get('qId', ''),
                field=item.get('qDim', {}).get('qFieldDefs', [''])[0],
                label=item.get('qMeta', {}).get('title', ''),
                grouping=item.get('qDim', {}).get('qGrouping', None)
            )
            dimensions.append(dim)

        logger.info(f'Extracted {len(dimensions)} dimensions')
        return dimensions

    def extract_measures(self) -> List[QlikMeasure]:
        """Extract measures from Qlik app."""
        measures = []

        for item in self.app_data.get('properties', {}).get('qMeasureList', {}).get('qItems', []):
            measure = QlikMeasure(
                name=item.get('qInfo', {}).get('qId', ''),
                expression=item.get('qMeasure', {}).get('qDef', ''),
                label=item.get('qMeta', {}).get('title', ''),
                format=item.get('qMeasure', {}).get('qNumFormat', {}).get('qFmt', None)
            )
            measures.append(measure)

        logger.info(f'Extracted {len(measures)} measures')
        return measures

    def extract_visualizations(self) -> List[QlikVisualization]:
        """Extract visualizations from Qlik sheets."""
        visualizations = []

        for sheet in self.app_data.get('sheets', []):
            for child in sheet.get('cells', []):
                viz_type = child.get('type', 'table')
                
                viz = QlikVisualization(
                    id=child.get('name', ''),
                    type=viz_type,
                    title=child.get('title', ''),
                    dimensions=[],  # Populated from references
                    measures=[],    # Populated from references
                    properties=child.get('properties', {})
                )
                visualizations.append(viz)

        logger.info(f'Extracted {len(visualizations)} visualizations')
        return visualizations


class QlikToPowerBIMigrator:
    """Migrate Qlik Sense apps to Power BI reports."""

    def __init__(self, output_dir: Path = None):
        """
        Initialize migrator.

        Args:
            output_dir: Directory for migrated artifacts
        """
        self.output_dir = output_dir or Path('migrated_artifacts')
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.converter = QlikToPowerBIConverter()

    def migrate_qlik_app(
        self,
        qlik_app_path: Path,
        report_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Migrate Qlik app to Power BI report structure.

        Args:
            qlik_app_path: Path to Qlik app export (JSON)
            report_name: Name for Power BI report

        Returns:
            Power BI report definition
        """
        logger.info(f'Starting migration: {qlik_app_path}')

        # Extract Qlik metadata
        extractor = QlikMetadataExtractor(qlik_app_path)
        app_data = extractor.load_qlik_app()

        dimensions = extractor.extract_dimensions()
        measures = extractor.extract_measures()
        visualizations = extractor.extract_visualizations()

        # Convert to Power BI format
        pbi_dimensions = [
            self.converter.convert_dimension(dim) for dim in dimensions
        ]
        pbi_measures = [
            self.converter.convert_measure(measure) for measure in measures
        ]

        # Build Power BI report structure
        pbi_report = {
            'displayName': report_name or app_data.get('qTitle', 'Migrated Report'),
            'type': 'Report',
            'definition': {
                'version': '1.0',
                'culture': 'en-US',
                'model': {
                    'tables': [
                        {
                            'name': 'MigratedData',
                            'columns': pbi_dimensions,
                            'measures': pbi_measures,
                        }
                    ]
                },
                'pages': [
                    {
                        'name': 'Page1',
                        'displayName': 'Overview',
                        'visuals': [
                            self.converter.convert_visualization(viz)
                            for viz in visualizations
                        ]
                    }
                ],
                'dataModelSchema': self._generate_dataset_schema(dimensions, measures),
            }
        }

        # Save migrated report
        output_file = self.output_dir / f'{report_name or "migrated_report"}.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(pbi_report, f, indent=2, ensure_ascii=False)

        logger.info(f'Migration complete. Saved to: {output_file}')
        return pbi_report

    def _generate_dataset_schema(
        self,
        dimensions: List[QlikDimension],
        measures: List[QlikMeasure]
    ) -> Dict[str, Any]:
        """Generate Power BI dataset schema from Qlik objects."""
        return {
            'name': 'MigratedDataset',
            'tables': [
                {
                    'name': 'FactTable',
                    'columns': [
                        {
                            'name': dim.field,
                            'dataType': 'string',
                            'sourceColumn': dim.field
                        }
                        for dim in dimensions
                    ],
                    'measures': [
                        {
                            'name': measure.name,
                            'expression': self.converter.convert_qlik_expression_to_dax(
                                measure.expression
                            )
                        }
                        for measure in measures
                    ]
                }
            ]
        }

    def batch_migrate(
        self,
        qlik_apps_dir: Path
    ) -> List[Dict[str, Any]]:
        """
        Migrate multiple Qlik apps from directory.

        Args:
            qlik_apps_dir: Directory containing Qlik app JSON exports

        Returns:
            List of migration results
        """
        results = []

        for qlik_file in qlik_apps_dir.glob('*.json'):
            try:
                logger.info(f'Migrating: {qlik_file.name}')
                report_name = qlik_file.stem

                pbi_report = self.migrate_qlik_app(qlik_file, report_name)
                results.append({
                    'source': str(qlik_file),
                    'status': 'success',
                    'report': pbi_report
                })
            except Exception as e:
                logger.error(f'Failed to migrate {qlik_file.name}: {str(e)}')
                results.append({
                    'source': str(qlik_file),
                    'status': 'failed',
                    'error': str(e)
                })

        logger.info(f'Batch migration complete: {len(results)} apps processed')
        return results
