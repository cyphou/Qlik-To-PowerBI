"""Authentication module for Microsoft Fabric API."""
import logging
from typing import Dict, Optional

try:
    from azure.identity import ClientSecretCredential, DefaultAzureCredential
except ImportError:  # pragma: no cover
    ClientSecretCredential = None  # type: ignore[assignment,misc]
    DefaultAzureCredential = None  # type: ignore[assignment,misc]

from fabric_api.config.settings import get_settings

logger = logging.getLogger(__name__)


class FabricAuthenticator:
    """Handles authentication with Microsoft Fabric API."""

    AUTHORITY_URL = 'https://login.microsoftonline.com'
    SCOPE = ['https://analysis.windows.net/powerbi/api/.default']

    def __init__(self, use_managed_identity: bool = False):
        """
        Initialize Fabric Authenticator.

        Args:
            use_managed_identity: Use Managed Identity instead of Service Principal
        """
        self.use_managed_identity = use_managed_identity
        self._token: Optional[str] = None
        self._credential = None
        self._init_credential()

    def _init_credential(self):
        """Initialize appropriate credential based on configuration."""
        settings = get_settings()
        if self.use_managed_identity:
            if DefaultAzureCredential is None:
                raise ImportError("pip install azure-identity  is required for authentication")
            logger.info('Initializing Managed Identity credential')
            self._credential = DefaultAzureCredential()
        else:
            if ClientSecretCredential is None:
                raise ImportError("pip install azure-identity  is required for authentication")
            logger.info('Initializing Service Principal credential')
            self._credential = ClientSecretCredential(
                tenant_id=settings.fabric_tenant_id,
                client_id=settings.fabric_client_id,
                client_secret=settings.fabric_client_secret
            )

    def get_token(self) -> str:
        """
        Get access token for Fabric API.

        Returns:
            Access token string

        Raises:
            Exception: If token acquisition fails
        """
        try:
            token = self._credential.get_token(*self.SCOPE)
            logger.debug('Successfully acquired access token')
            self._token = token.token
            return self._token
        except Exception as e:
            logger.error(f'Failed to acquire access token: {str(e)}')
            raise

    def get_headers(self) -> Dict[str, str]:
        """
        Get HTTP headers with authorization token.

        Returns:
            Dictionary of HTTP headers
        """
        token = self.get_token()
        return {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
