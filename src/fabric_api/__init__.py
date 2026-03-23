"""Microsoft Fabric API deployment package — DEPRECATED.

This package is a backward-compatibility shim.  New code should import
directly from ``qlik_export.*`` (Qlik extraction) or ``powerbi_import.*``
(Power BI generation / deployment).

Core migration classes (TMDLGenerator, Qlik converters) are re-exported
from their canonical locations.  Azure-dependent classes (FabricClient,
FabricAuthenticator, FabricDeployer) are lazy-imported.
"""
from __future__ import annotations

import os
import sys
import warnings

__version__ = "8.0.0"

# Ensure project root is on sys.path so canonical packages are importable
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

warnings.warn(
    "The 'fabric_api' package is deprecated. "
    "Import from 'qlik_export' or 'powerbi_import' instead.",
    DeprecationWarning,
    stacklevel=2,
)

# ── Re-exports from canonical locations ──────────────────────────
# Qlik extraction modules  (qlik_export.*)
from qlik_export.qlik_migrator import QlikToPowerBIMigrator, QlikToPowerBIConverter
from qlik_export.qlik_model_converter import QlikToPowerBIModelConverter, QlikModelMigrator
from qlik_export.qlik_script_converter import QlikScriptToPowerQueryConverter, QlikScriptMigrator
from qlik_export.qvf_extractor import QVFExtractor
from qlik_export.dax_converter import convert_qlik_expression_to_dax, convert_measures_to_dax, convert_dimensions_to_dax
from qlik_export.m_query_generator import generate_m_query, generate_all_m_queries
from qlik_export.m_query_builder import inject_m_steps, build_m_query_with_transforms
from qlik_export.extraction_orchestrator import ExtractionOrchestrator

# Power BI generation modules  (powerbi_import.*)
from powerbi_import.validator import ArtifactValidator
from powerbi_import.visual_generator import generate_visual_containers, create_visual_container, resolve_visual_type

# TMDLGenerator + create_pbi_project_from_migration remain local
# (unique to this package, not yet migrated to powerbi_import)
from .tmdl_generator import TMDLGenerator, create_pbi_project_from_migration

# Deployment utilities  (powerbi_import.deploy.*)
from powerbi_import.deploy.utils import DeploymentReport, ArtifactCache


def __getattr__(name: str):
    """Lazy-load Azure-dependent classes on first access."""
    _azure_classes = {
        "FabricClient": "powerbi_import.deploy.client",
        "FabricAuthenticator": "powerbi_import.deploy.auth",
        "FabricDeployer": "powerbi_import.deploy.deployer",
    }
    if name in _azure_classes:
        import importlib

        module = importlib.import_module(_azure_classes[name])
        cls = getattr(module, name)
        globals()[name] = cls  # cache for subsequent access
        return cls
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # Core (always available)
    "TMDLGenerator",
    "create_pbi_project_from_migration",
    "QlikToPowerBIMigrator",
    "QlikToPowerBIConverter",
    "QlikToPowerBIModelConverter",
    "QlikModelMigrator",
    "QlikScriptToPowerQueryConverter",
    "QlikScriptMigrator",
    "QVFExtractor",
    "ArtifactValidator",
    "DeploymentReport",
    "ArtifactCache",
    # DAX conversion (v3.0)
    "convert_qlik_expression_to_dax",
    "convert_measures_to_dax",
    "convert_dimensions_to_dax",
    # Visual generation (v3.0)
    "generate_visual_containers",
    "create_visual_container",
    "resolve_visual_type",
    # Power Query M (v3.0)
    "generate_m_query",
    "generate_all_m_queries",
    "inject_m_steps",
    "build_m_query_with_transforms",
    # Extraction orchestrator (v3.0)
    "ExtractionOrchestrator",
    # Azure (lazy)
    "FabricClient",
    "FabricAuthenticator",
    "FabricDeployer",
]
