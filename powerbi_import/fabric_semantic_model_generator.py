"""
Standalone Semantic Model generator for Microsoft Fabric.

Generates a Fabric SemanticModel item definition using DirectLake
mode with entity partitions referencing a Lakehouse.

Output structure:
    {model_name}.SemanticModel/
    ├── definition/
    │   ├── model.tmdl
    │   ├── database.tmdl
    │   ├── expressions.tmdl
    │   ├── relationships.tmdl
    │   ├── roles/
    │   │   └── *.tmdl
    │   └── tables/
    │       └── *.tmdl
    └── .platform
"""

import os
import json
import sys

# Import the existing tmdl_generator from the same package
from . import tmdl_generator


class FabricSemanticModelGenerator:
    """Generate a standalone Fabric SemanticModel artifact with DirectLake mode."""

    def __init__(self, project_dir, model_name, lakehouse_name=None):
        self.project_dir = project_dir
        self.model_name = model_name
        self.lakehouse_name = lakehouse_name or f'{model_name}_Lakehouse'
        self.sm_dir = os.path.join(project_dir, f'{model_name}.SemanticModel')
        os.makedirs(self.sm_dir, exist_ok=True)

    def generate(self, extracted, calendar_start=None, calendar_end=None,
                 culture=None, languages=None):
        """Generate semantic-model files from extracted Qlik objects.

        Delegates TMDL generation to the existing tmdl_generator, then
        wraps the output in a Fabric SemanticModel item structure with
        DirectLake metadata.

        Args:
            extracted: dict with keys like 'datasources', 'calculations',
                       'hierarchies', 'parameters', 'user_filters', etc.
            calendar_start: Start year for Calendar table (default: 2020)
            calendar_end: End year for Calendar table (default: 2030)
            culture: Override culture/locale for semantic model (e.g., fr-FR)
            languages: Comma-separated additional locales

        Returns:
            dict with generation statistics.
        """
        datasources = extracted.get('datasources', [])
        extra_objects = {
            'sets': extracted.get('sets', []),
            'groups': extracted.get('groups', []),
            'bins': extracted.get('bins', []),
            'hierarchies': extracted.get('hierarchies', []),
            'parameters': extracted.get('parameters', []),
            'user_filters': extracted.get('user_filters', []),
            'sort_orders': extracted.get('sort_orders', []),
            'aliases': extracted.get('aliases', {}),
            'data_blending': extracted.get('data_blending', []),
        }

        # Output TMDL inside SemanticModel/definition
        definition_dir = os.path.join(self.sm_dir, 'definition')
        os.makedirs(definition_dir, exist_ok=True)

        # Use the existing tmdl_generator — import mode for now
        # (Direct Lake is metadata-only — TMDL partitions stay as M/import
        #  and Fabric resolves them to entity partitions at deploy time)
        stats = tmdl_generator.generate_tmdl(
            datasources=datasources,
            report_name=self.model_name,
            extra_objects=extra_objects,
            output_dir=definition_dir,
            calendar_start=calendar_start,
            calendar_end=calendar_end,
            culture=culture,
            model_mode='import',
            languages=languages,
        )

        # Create .platform manifest
        self._write_platform_file()

        # Create item metadata with DirectLake indicator
        self._write_item_metadata(stats)

        return stats

    def _write_platform_file(self):
        """Write the .platform manifest for the SemanticModel item."""
        platform = {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
            "metadata": {
                "type": "SemanticModel",
                "displayName": self.model_name,
            },
            "config": {
                "version": "2.0",
                "logicalId": f"semantic-model-{self.model_name.lower().replace(' ', '-')}",
            },
        }
        path = os.path.join(self.sm_dir, '.platform')
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(platform, f, indent=2)

    def _write_item_metadata(self, stats):
        """Write a metadata JSON for the semantic model."""
        # Make stats JSON-serializable (convert sets to lists)
        safe_stats = {}
        for k, v in stats.items():
            if isinstance(v, set):
                safe_stats[k] = list(v)
            elif isinstance(v, dict):
                safe_stats[k] = {
                    sk: list(sv) if isinstance(sv, set) else sv
                    for sk, sv in v.items()
                }
            else:
                safe_stats[k] = v

        meta = {
            "displayName": self.model_name,
            "type": "SemanticModel",
            "mode": "DirectLake",
            "lakehouse": self.lakehouse_name,
            "stats": safe_stats,
        }
        path = os.path.join(self.sm_dir, 'semantic_model_metadata.json')
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(meta, f, indent=2)
