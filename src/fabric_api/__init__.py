"""Microsoft Fabric API deployment package.

Core migration classes (TMDLGenerator, Qlik converters) are always available.
Azure-dependent classes (FabricClient, FabricAuthenticator, FabricDeployer)
are lazy-imported and require ``pip install qlik-to-powerbi[azure]``.
"""
from __future__ import annotations

__version__ = "3.1.0"

# Always-available — no heavy dependencies
from .tmdl_generator import TMDLGenerator, create_pbi_project_from_migration
from .qlik_migrator import QlikToPowerBIMigrator, QlikToPowerBIConverter
from .qlik_model_converter import QlikToPowerBIModelConverter, QlikModelMigrator
from .qlik_script_converter import QlikScriptToPowerQueryConverter, QlikScriptMigrator
from .qvf_extractor import QVFExtractor
from .validator import ArtifactValidator
from .utils import DeploymentReport, ArtifactCache

# New v3.0 modules
from .dax_converter import convert_qlik_expression_to_dax, convert_measures_to_dax, convert_dimensions_to_dax
from .visual_generator import generate_visual_containers, create_visual_container, resolve_visual_type
from .m_query_generator import generate_m_query, generate_all_m_queries
from .m_query_builder import inject_m_steps, build_m_query_with_transforms
from .extraction_orchestrator import ExtractionOrchestrator


def __getattr__(name: str):
    """Lazy-load Azure-dependent classes on first access."""
    _azure_classes = {
        "FabricClient": ".client",
        "FabricAuthenticator": ".auth",
        "FabricDeployer": ".deployer",
    }
    if name in _azure_classes:
        import importlib

        module = importlib.import_module(_azure_classes[name], __package__)
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
