"""
Fabric-native artifact orchestrator.

Coordinates the generation of all Fabric artifacts from extracted
Qlik data:
  1. Lakehouse (table schemas, DDL)
  2. Dataflow Gen2 (Power Query M ingestion)
  3. PySpark Notebook (ETL pipeline)
  4. Semantic Model (DirectLake TMDL)
  5. Pipeline (orchestration)

This module is invoked when ``--output-format fabric`` is specified
on the CLI.
"""

import os
import json
from datetime import datetime

from .lakehouse_generator import LakehouseGenerator
from .dataflow_generator import DataflowGenerator
from .notebook_generator import NotebookGenerator
from .pipeline_generator import PipelineGenerator
from .fabric_semantic_model_generator import FabricSemanticModelGenerator


def _json_default(obj):
    """JSON serializer for objects not serializable by default json code."""
    if isinstance(obj, set):
        return list(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


class FabricProjectGenerator:
    """Orchestrates generation of a complete Fabric project from Qlik data."""

    def __init__(self, output_dir=None):
        self.output_dir = output_dir or os.path.join('artifacts', 'fabric_projects', 'migrated')

    def generate_project(self, project_name, extracted_data,
                         calendar_start=None, calendar_end=None,
                         culture=None, languages=None):
        """Generate all Fabric artifacts for a migrated Qlik app.

        Args:
            project_name: Name for the Fabric project (used in all artifact names).
            extracted_data: Dict with all extracted Qlik objects
                            (datasources, worksheets, calculations, etc.).
            calendar_start: Start year for Calendar table.
            calendar_end: End year for Calendar table.
            culture: Override culture/locale.
            languages: Comma-separated additional locales.

        Returns:
            dict with project_path and per-artifact stats.
        """
        project_dir = os.path.join(self.output_dir, project_name)
        os.makedirs(project_dir, exist_ok=True)

        results = {
            'project_path': project_dir,
            'project_name': project_name,
            'generated_at': datetime.now().isoformat(),
            'artifacts': {},
        }

        # 1. Lakehouse
        print(f"  [1/5] Generating Lakehouse...")
        lh_gen = LakehouseGenerator(project_dir, project_name)
        lh_stats = lh_gen.generate(extracted_data)
        results['artifacts']['lakehouse'] = lh_stats
        print(f"         Tables: {lh_stats['tables']}, Columns: {lh_stats['columns']}, "
              f"Calc columns: {lh_stats['calc_columns']}")

        # 2. Dataflow Gen2
        print(f"  [2/5] Generating Dataflow Gen2...")
        df_gen = DataflowGenerator(project_dir, project_name)
        df_stats = df_gen.generate(extracted_data)
        results['artifacts']['dataflow'] = df_stats
        print(f"         Queries: {df_stats['queries']}, Calc columns: {df_stats['calc_columns']}")

        # 3. PySpark Notebook
        print(f"  [3/5] Generating PySpark Notebooks...")
        nb_gen = NotebookGenerator(project_dir, project_name)
        nb_stats = nb_gen.generate(extracted_data)
        results['artifacts']['notebook'] = nb_stats
        print(f"         Notebooks: {nb_stats['notebooks']}, Cells: {nb_stats['cells']}")

        # 4. Semantic Model (DirectLake)
        print(f"  [4/5] Generating DirectLake Semantic Model...")
        sm_gen = FabricSemanticModelGenerator(
            project_dir, project_name,
            lakehouse_name=f'{project_name}_Lakehouse',
        )
        sm_stats = sm_gen.generate(
            extracted_data,
            calendar_start=calendar_start,
            calendar_end=calendar_end,
            culture=culture,
            languages=languages,
        )
        results['artifacts']['semantic_model'] = sm_stats
        print(f"         Tables: {sm_stats.get('tables', 0)}, "
              f"Measures: {sm_stats.get('measures', 0)}, "
              f"Relationships: {sm_stats.get('relationships', 0)}")

        # 5. Pipeline
        print(f"  [5/5] Generating Data Pipeline...")
        pipe_gen = PipelineGenerator(
            project_dir, project_name,
            lakehouse_name=f'{project_name}_Lakehouse',
        )
        pipe_stats = pipe_gen.generate(extracted_data)
        results['artifacts']['pipeline'] = pipe_stats
        print(f"         Activities: {pipe_stats['activities']}, Stages: {pipe_stats['stages']}")

        # Write project metadata
        meta_path = os.path.join(project_dir, 'fabric_project_metadata.json')
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, default=_json_default)

        print(f"\n  [OK] Fabric project created: {project_dir}")
        return results
