"""
Fabric Data Pipeline generator.

Creates a Microsoft Fabric Data Pipeline definition that orchestrates:
    1. Dataflow Gen2 refresh  (ingest raw data)
    2. Notebook execution     (PySpark transforms → Delta tables)
    3. Semantic Model refresh (DirectLake model picks up fresh data)

Output:
    {pipeline_name}.Pipeline/
    ├── pipeline_definition.json
    ├── pipeline_metadata.json
    └── .platform
"""

import os
import json
import re
from datetime import datetime

from .fabric_naming import sanitize_pipeline_name as _sanitize


class PipelineGenerator:
    """Generate a Fabric Data Pipeline artifact."""

    def __init__(self, project_dir, pipeline_name, lakehouse_name=None):
        self.project_dir = project_dir
        self.pipeline_name = pipeline_name
        self.lakehouse_name = lakehouse_name or pipeline_name
        self.pipe_dir = os.path.join(project_dir, f'{pipeline_name}.Pipeline')
        os.makedirs(self.pipe_dir, exist_ok=True)

    def generate(self, extracted):
        """Generate pipeline definition from extracted Qlik objects.

        Args:
            extracted: dict with at least 'datasources'.

        Returns:
            dict  {'activities': int, 'stages': int}
        """
        datasources = extracted.get('datasources', [])

        activities = self._build_activities(datasources)
        pipeline_def = self._build_pipeline_definition(activities)

        def_path = os.path.join(self.pipe_dir, 'pipeline_definition.json')
        with open(def_path, 'w', encoding='utf-8') as f:
            json.dump(pipeline_def, f, indent=2)

        meta = {
            'displayName': self.pipeline_name,
            'type': 'Pipeline',
            'generated_at': datetime.now().isoformat(),
            'activities': len(activities),
            'stages': self._count_stages(activities),
            'lakehouse': self.lakehouse_name,
        }
        meta_path = os.path.join(self.pipe_dir, 'pipeline_metadata.json')
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(meta, f, indent=2)

        self._write_platform_file()

        return {
            'activities': len(activities),
            'stages': meta['stages'],
        }

    def _build_activities(self, datasources):
        """Build the ordered list of pipeline activities."""
        activities = []

        df_activities = self._dataflow_activities(datasources)
        activities.extend(df_activities)

        nb_activity = self._notebook_activity(
            depends_on=[a['name'] for a in df_activities]
        )
        activities.append(nb_activity)

        sm_activity = self._semantic_model_refresh_activity(
            depends_on=[nb_activity['name']]
        )
        activities.append(sm_activity)

        return activities

    def _dataflow_activities(self, datasources):
        """Create one Dataflow refresh activity per datasource."""
        activities = []
        for idx, ds in enumerate(datasources):
            ds_name = ds.get('name', f'Datasource_{idx + 1}')
            safe_name = _sanitize(ds_name)
            activity = {
                'name': f'Refresh_Dataflow_{safe_name}',
                'type': 'RefreshDataflow',
                'dependsOn': [],
                'policy': {
                    'timeout': '0.12:00:00',
                    'retry': 2,
                    'retryIntervalInSeconds': 30,
                    'secureOutput': False,
                    'secureInput': False,
                },
                'typeProperties': {
                    'dataflowId': '{{DATAFLOW_ID}}',
                    'workspaceId': '{{WORKSPACE_ID}}',
                    'notifyOption': 'NoNotification',
                    'dataflowType': 'DataflowFabric',
                },
                'description': f'Refresh Dataflow Gen2 for datasource: {ds_name}',
            }
            activities.append(activity)
        return activities

    def _notebook_activity(self, depends_on=None):
        """Create a Notebook execution activity."""
        return {
            'name': 'Run_ETL_Notebook',
            'type': 'TridentNotebook',
            'dependsOn': [
                {'activity': dep, 'dependencyConditions': ['Succeeded']}
                for dep in (depends_on or [])
            ],
            'policy': {
                'timeout': '0.02:00:00',
                'retry': 1,
                'retryIntervalInSeconds': 60,
            },
            'typeProperties': {
                'notebookId': '{{NOTEBOOK_ID}}',
                'workspaceId': '{{WORKSPACE_ID}}',
            },
            'description': 'Execute PySpark ETL notebook to transform data into Delta tables.',
        }

    def _semantic_model_refresh_activity(self, depends_on=None):
        """Create a Semantic Model refresh activity."""
        return {
            'name': 'Refresh_SemanticModel',
            'type': 'TridentDatasetRefresh',
            'dependsOn': [
                {'activity': dep, 'dependencyConditions': ['Succeeded']}
                for dep in (depends_on or [])
            ],
            'policy': {
                'timeout': '0.01:00:00',
                'retry': 1,
                'retryIntervalInSeconds': 30,
                'secureOutput': False,
                'secureInput': False,
            },
            'typeProperties': {
                'datasetId': '{{SEMANTIC_MODEL_ID}}',
                'workspaceId': '{{WORKSPACE_ID}}',
            },
            'description': 'Refresh the DirectLake semantic model after ETL completes.',
        }

    def _build_pipeline_definition(self, activities):
        """Assemble the full pipeline definition document."""
        return {
            '$schema': 'https://developer.microsoft.com/json-schemas/fabric/pipeline/definition/2.0.0/schema.json',
            'name': self.pipeline_name,
            'properties': {
                'description': (
                    f'Auto-generated migration pipeline for {self.pipeline_name}. '
                    'Orchestrates Dataflow refresh → Notebook ETL → Semantic Model refresh.'
                ),
                'activities': activities,
                'annotations': [
                    'Generated by Qlik to Power BI Migration Tool',
                ],
                'parameters': {
                    'LakehouseName': {
                        'type': 'String',
                        'defaultValue': self.lakehouse_name,
                    },
                },
            },
        }

    def _write_platform_file(self):
        """Write .platform manifest for the Pipeline item."""
        platform = {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
            "metadata": {
                "type": "DataPipeline",
                "displayName": self.pipeline_name,
            },
            "config": {
                "version": "2.0",
                "logicalId": f"pipeline-{self.pipeline_name.lower().replace(' ', '-')}",
            },
        }
        path = os.path.join(self.pipe_dir, '.platform')
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(platform, f, indent=2)

    @staticmethod
    def _count_stages(activities):
        """Count pipeline stages (layers of dependency)."""
        if not activities:
            return 0
        stages = 1
        for a in activities:
            deps = a.get('dependsOn', [])
            if deps:
                stages = max(stages, 2)
                for d in deps:
                    if isinstance(d, dict) and d.get('activity', '').startswith('Run_ETL'):
                        stages = max(stages, 3)
        return stages
