"""
Fabric deployment subpackage.

Provides authentication, HTTP client, and deployment orchestration
for publishing Power BI projects to Microsoft Fabric workspaces.
"""

from .auth import FabricAuthenticator
from .client import FabricClient
from .deployer import FabricDeployer
from .utils import DeploymentReport, ArtifactCache

__all__ = [
    'FabricAuthenticator',
    'FabricClient',
    'FabricDeployer',
    'DeploymentReport',
    'ArtifactCache',
]
