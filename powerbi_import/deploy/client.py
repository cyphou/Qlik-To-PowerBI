"""
Fabric API client for making HTTP requests.

Provides a resilient HTTP client with retry strategy for
Microsoft Fabric REST API operations.

Requires: pip install requests (optional dependency)
"""

import logging
import json as _json
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from powerbi_import.deploy.config.settings import get_settings
from powerbi_import.deploy.auth import FabricAuthenticator

logger = logging.getLogger(__name__)


class FabricClient:
    """HTTP client for Fabric API requests.

    Uses urllib from stdlib by default. If `requests` is installed,
    it will use requests with retry strategy instead.
    """

    def __init__(self, authenticator=None):
        """
        Initialize Fabric API Client.

        Args:
            authenticator: FabricAuthenticator instance (creates default if None)
        """
        if authenticator is None:
            authenticator = FabricAuthenticator()

        self.authenticator = authenticator

        settings = get_settings()
        self.base_url = settings.fabric_api_base_url
        self.workspace_id = settings.fabric_workspace_id
        self.timeout = settings.deployment_timeout
        self.retry_attempts = settings.retry_attempts
        self.retry_delay = settings.retry_delay
        self._session = None

        # Try to use requests if available
        try:
            import requests  # type: ignore[import-not-found]
            from requests.adapters import HTTPAdapter  # type: ignore[import-not-found]
            from urllib3.util.retry import Retry  # type: ignore[import-not-found]

            session = requests.Session()
            retry_strategy = Retry(
                total=self.retry_attempts,
                backoff_factor=1,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE'],
            )
            adapter = HTTPAdapter(max_retries=retry_strategy)
            session.mount('http://', adapter)
            session.mount('https://', adapter)
            self._session = session
            self._use_requests = True
            logger.debug('Using requests library with retry strategy')
        except ImportError:
            self._use_requests = False
            logger.debug('Using urllib (stdlib) — install requests for retry support')

    def _request(self, method, endpoint, data=None, params=None):
        """
        Make HTTP request to Fabric API.

        Args:
            method: HTTP method (GET, POST, PUT, PATCH, DELETE)
            endpoint: API endpoint path
            data: Request body data (dict)
            params: Query parameters (dict)

        Returns:
            Response dict

        Raises:
            Exception: If request fails
        """
        url = f'{self.base_url}{endpoint}'
        if params:
            query = '&'.join(f'{k}={v}' for k, v in params.items())
            url = f'{url}?{query}'

        headers = self.authenticator.get_headers()

        logger.debug(f'{method} {url}')

        if self._use_requests and self._session is not None:
            response = self._session.request(
                method=method,
                url=url,
                json=data,
                headers=headers,
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json() if response.text else {}
        else:
            # Fallback to urllib
            body = _json.dumps(data).encode('utf-8') if data else None
            req = Request(url, data=body, headers=headers, method=method)
            try:
                with urlopen(req, timeout=self.timeout) as resp:
                    resp_body = resp.read().decode('utf-8')
                    return _json.loads(resp_body) if resp_body else {}
            except HTTPError as e:
                logger.error(f'HTTP {e.code}: {e.reason}')
                raise
            except URLError as e:
                logger.error(f'URL error: {e.reason}')
                raise

    def get(self, endpoint, params=None):
        """GET request."""
        return self._request('GET', endpoint, params=params)

    def post(self, endpoint, data):
        """POST request."""
        return self._request('POST', endpoint, data=data)

    def put(self, endpoint, data):
        """PUT request."""
        return self._request('PUT', endpoint, data=data)

    def patch(self, endpoint, data):
        """PATCH request."""
        return self._request('PATCH', endpoint, data=data)

    def delete(self, endpoint):
        """DELETE request."""
        return self._request('DELETE', endpoint)

    def list_workspaces(self):
        """List all accessible workspaces."""
        return self.get('/workspaces')

    def get_workspace(self, workspace_id):
        """Get workspace details."""
        return self.get(f'/workspaces/{workspace_id}')

    def list_items(self, workspace_id, item_type=None):
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
