"""
Power BI Service REST API client.

Provides authentication and HTTP client for Power BI REST API operations
(publish, refresh, rebind, etc.) — separate from the Fabric API client,
which targets the Fabric Items REST surface.

Supported auth flows:
  - Service Principal (client credentials) via ``azure-identity``
  - Managed Identity via ``azure-identity``
  - Falls back to environment-based token if ``azure-identity`` is not installed

Requires: ``azure-identity`` (optional) and ``requests`` (optional)
"""

import logging
import json as _json
import os
import base64
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

logger = logging.getLogger(__name__)

PBI_API_BASE = 'https://api.powerbi.com/v1.0/myorg'
PBI_SCOPE = 'https://analysis.windows.net/powerbi/api/.default'


class PBIServiceClient:
    """HTTP client for Power BI Service REST API.

    Authenticates via Azure AD and provides methods for PBI workspace
    operations: import, publish, refresh, get status.
    """

    def __init__(self, tenant_id=None, client_id=None, client_secret=None,
                 use_managed_identity=False):
        """Initialize PBI Service client.

        Args:
            tenant_id: Azure AD tenant ID (or PBI_TENANT_ID env var)
            client_id: Azure AD app (client) ID (or PBI_CLIENT_ID env var)
            client_secret: Client secret (or PBI_CLIENT_SECRET env var)
            use_managed_identity: Use managed identity instead of SP
        """
        self.tenant_id = tenant_id or os.getenv('PBI_TENANT_ID', '')
        self.client_id = client_id or os.getenv('PBI_CLIENT_ID', '')
        self.client_secret = client_secret or os.getenv('PBI_CLIENT_SECRET', '')
        self.use_managed_identity = use_managed_identity
        self._token = None
        self._token_expires_on = 0
        self._session = None

        # Try requests library
        try:
            import requests  # type: ignore[import-not-found]
            self._session = requests.Session()
            self._use_requests = True
        except ImportError:
            self._use_requests = False

    def _get_token(self):
        """Acquire an Azure AD access token."""
        if self._token and self._token_expires_on:
            import time
            if time.time() < self._token_expires_on - 300:  # 5 min buffer
                return self._token

        try:
            from azure.identity import (  # type: ignore[import-not-found]
                ClientSecretCredential,
                DefaultAzureCredential,
            )
            if self.use_managed_identity:
                cred = DefaultAzureCredential()
            else:
                cred = ClientSecretCredential(
                    tenant_id=self.tenant_id,
                    client_id=self.client_id,
                    client_secret=self.client_secret,
                )
            token = cred.get_token(PBI_SCOPE)
            self._token = token.token
            self._token_expires_on = getattr(token, 'expires_on', 0)
        except ImportError:
            # No azure-identity — check for pre-set token
            self._token = os.getenv('PBI_ACCESS_TOKEN', '')
            self._token_expires_on = 0
            if not self._token:
                raise RuntimeError(
                    'azure-identity not installed and PBI_ACCESS_TOKEN not set. '
                    'Install azure-identity or provide a token via environment.'
                )

        return self._token

    def _headers(self):
        """Build request headers with Bearer token."""
        token = self._get_token()
        return {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }

    def _request(self, method, url, data=None, files=None, raw_body=None):
        """Execute an HTTP request against the PBI REST API.

        Args:
            method: HTTP method
            url: Full URL
            data: JSON body (dict)
            files: Multipart file data (for requests only)
            raw_body: Raw bytes body (for urllib)

        Returns:
            dict: Parsed JSON response (or empty dict)
        """
        logger.debug(f'{method} {url}')

        if self._use_requests and self._session is not None:
            headers = self._headers()
            if files:
                # Multipart — don't set Content-Type, requests does it
                headers.pop('Content-Type', None)
                resp = self._session.request(
                    method=method, url=url, headers=headers,
                    files=files, timeout=300,
                )
            else:
                resp = self._session.request(
                    method=method, url=url, headers=headers,
                    json=data, timeout=300,
                )
            resp.raise_for_status()
            return resp.json() if resp.text else {}
        else:
            headers = self._headers()
            body = None
            if raw_body:
                body = raw_body
                headers['Content-Type'] = 'application/octet-stream'
            elif data:
                body = _json.dumps(data).encode('utf-8')
            req = Request(url, data=body, headers=headers, method=method)
            try:
                with urlopen(req, timeout=300) as resp:
                    resp_body = resp.read().decode('utf-8')
                    return _json.loads(resp_body) if resp_body else {}
            except HTTPError as e:
                error_body = e.read().decode('utf-8', errors='replace') if e.fp else ''
                logger.error(f'HTTP {e.code}: {e.reason} — {error_body}')
                raise

    # ── Workspace operations ──────────────────────────────────────

    def list_workspaces(self):
        """List all workspaces accessible to the service principal.

        Returns:
            list[dict]: Workspace objects with id, name, type.
        """
        result = self._request('GET', f'{PBI_API_BASE}/groups')
        return result.get('value', [])

    def get_workspace(self, workspace_id):
        """Get details of a specific workspace.

        Args:
            workspace_id: Power BI workspace (group) ID.

        Returns:
            dict: Workspace details.
        """
        return self._request('GET', f'{PBI_API_BASE}/groups/{workspace_id}')

    # ── Import / Publish ──────────────────────────────────────────

    def import_pbix(self, workspace_id, pbix_path, dataset_name=None,
                    overwrite=True):
        """Import a .pbix file into a workspace.

        Args:
            workspace_id: Target workspace ID.
            pbix_path: Path to .pbix file on disk.
            dataset_name: Display name (defaults to filename stem).
            overwrite: Whether to overwrite existing dataset/report.

        Returns:
            dict: Import operation response with id and status.
        """
        if not dataset_name:
            dataset_name = os.path.splitext(os.path.basename(pbix_path))[0]

        params = f'datasetDisplayName={dataset_name}'
        if overwrite:
            params += '&nameConflict=CreateOrOverwrite'
        else:
            params += '&nameConflict=Abort'

        url = f'{PBI_API_BASE}/groups/{workspace_id}/imports?{params}'

        with open(pbix_path, 'rb') as f:
            file_content = f.read()

        if self._use_requests and self._session:
            files = {'file': (os.path.basename(pbix_path), file_content,
                              'application/x-zip-compressed')}
            return self._request('POST', url, files=files)
        else:
            return self._request('POST', url, raw_body=file_content)

    def get_import_status(self, workspace_id, import_id):
        """Check the status of an import operation.

        Args:
            workspace_id: Workspace ID.
            import_id: Import operation ID from import_pbix.

        Returns:
            dict: Import status with importState ('Publishing', 'Succeeded', 'Failed').
        """
        url = f'{PBI_API_BASE}/groups/{workspace_id}/imports/{import_id}'
        return self._request('GET', url)

    # ── Dataset operations ────────────────────────────────────────

    def list_datasets(self, workspace_id):
        """List datasets in a workspace.

        Returns:
            list[dict]: Dataset objects.
        """
        result = self._request(
            'GET', f'{PBI_API_BASE}/groups/{workspace_id}/datasets'
        )
        return result.get('value', [])

    def refresh_dataset(self, workspace_id, dataset_id):
        """Trigger a dataset refresh.

        Args:
            workspace_id: Workspace ID.
            dataset_id: Dataset ID.

        Returns:
            dict: Refresh response (empty on success — 202 Accepted).
        """
        url = f'{PBI_API_BASE}/groups/{workspace_id}/datasets/{dataset_id}/refreshes'
        return self._request('POST', url, data={})

    def get_refresh_history(self, workspace_id, dataset_id, top=1):
        """Get dataset refresh history.

        Args:
            workspace_id: Workspace ID.
            dataset_id: Dataset ID.
            top: Number of most recent refreshes to return.

        Returns:
            list[dict]: Refresh history entries.
        """
        url = (f'{PBI_API_BASE}/groups/{workspace_id}/datasets/{dataset_id}'
               f'/refreshes?$top={top}')
        result = self._request('GET', url)
        return result.get('value', [])

    # ── Report operations ─────────────────────────────────────────

    def list_reports(self, workspace_id):
        """List reports in a workspace.

        Returns:
            list[dict]: Report objects.
        """
        result = self._request(
            'GET', f'{PBI_API_BASE}/groups/{workspace_id}/reports'
        )
        return result.get('value', [])

    def delete_report(self, workspace_id, report_id):
        """Delete a report.

        Args:
            workspace_id: Workspace ID.
            report_id: Report ID.
        """
        url = f'{PBI_API_BASE}/groups/{workspace_id}/reports/{report_id}'
        return self._request('DELETE', url)
