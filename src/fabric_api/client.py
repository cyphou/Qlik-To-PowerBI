"""Fabric API client for making HTTP requests."""
import logging
import time
from typing import Dict, Any, Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from fabric_api.config.settings import get_settings
from .auth import FabricAuthenticator

logger = logging.getLogger(__name__)


class FabricClient:
    """HTTP client for Fabric API requests."""

    def __init__(self, authenticator: Optional[FabricAuthenticator] = None):
        """
        Initialize Fabric API Client.

        Args:
            authenticator: FabricAuthenticator instance (creates default if None)
        """
        self.authenticator = authenticator or FabricAuthenticator()
        settings = get_settings()
        self.base_url = settings.fabric_api_base_url
        self.workspace_id = settings.fabric_workspace_id
        self.session = self._create_session()

    def _create_session(self) -> requests.Session:
        """
        Create HTTP session with retry strategy.

        Returns:
            Configured requests Session
        """
        settings = get_settings()
        session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=settings.retry_attempts,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE']
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        
        return session

    def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, str]] = None
    ) -> requests.Response:
        """
        Make HTTP request to Fabric API.

        Args:
            method: HTTP method (GET, POST, PUT, PATCH, DELETE)
            endpoint: API endpoint path
            data: Request body data
            params: Query parameters

        Returns:
            Response object

        Raises:
            requests.RequestException: If request fails
        """
        url = f'{self.base_url}{endpoint}'
        headers = self.authenticator.get_headers()
        settings = get_settings()

        try:
            logger.debug(f'{method} {url}')
            response = self.session.request(
                method=method,
                url=url,
                json=data,
                params=params,
                headers=headers,
                timeout=settings.deployment_timeout
            )
            response.raise_for_status()
            logger.debug(f'Response status: {response.status_code}')
            return response
        except requests.exceptions.RequestException as e:
            logger.error(f'Request failed: {str(e)}')
            raise

    def get(self, endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """GET request."""
        response = self._request('GET', endpoint, params=params)
        return response.json() if response.text else {}

    def post(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """POST request."""
        response = self._request('POST', endpoint, data=data)
        return response.json() if response.text else {}

    def put(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """PUT request."""
        response = self._request('PUT', endpoint, data=data)
        return response.json() if response.text else {}

    def patch(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """PATCH request."""
        response = self._request('PATCH', endpoint, data=data)
        return response.json() if response.text else {}

    def delete(self, endpoint: str) -> Dict[str, Any]:
        """DELETE request."""
        response = self._request('DELETE', endpoint)
        return response.json() if response.text else {}

    def list_workspaces(self) -> Dict[str, Any]:
        """List all accessible workspaces."""
        return self.get('/workspaces')

    def get_workspace(self, workspace_id: str) -> Dict[str, Any]:
        """Get workspace details."""
        return self.get(f'/workspaces/{workspace_id}')

    def list_items(self, workspace_id: str, item_type: Optional[str] = None) -> Dict[str, Any]:
        """
        List items in workspace.

        Args:
            workspace_id: Workspace ID
            item_type: Filter by item type (Dataset, Report, etc.)
        """
        endpoint = f'/workspaces/{workspace_id}/items'
        params = {}
        if item_type:
            params['$filter'] = f"type eq '{item_type}'"
        return self.get(endpoint, params=params)
