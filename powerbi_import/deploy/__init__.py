"""
Fabric deployment subpackage.

Provides authentication, HTTP client, and deployment orchestration
for publishing Power BI projects to Microsoft Fabric workspaces.
"""

from .auth import FabricAuthenticator
from .client import FabricClient
from .deployer import FabricDeployer
from .utils import DeploymentReport, ArtifactCache
from .pipeline_helpers import (
    generate_deployment_config,
    generate_incremental_refresh_policy,
    generate_refresh_schedule,
    generate_sensitivity_label,
)

__all__ = [
    'FabricAuthenticator',
    'FabricClient',
    'FabricDeployer',
    'DeploymentReport',
    'ArtifactCache',
    'generate_deployment_config',
    'generate_incremental_refresh_policy',
    'generate_refresh_schedule',
    'generate_sensitivity_label',
]
