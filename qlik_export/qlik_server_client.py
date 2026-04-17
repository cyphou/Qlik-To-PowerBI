"""
Qlik Sense REST API client for direct extraction.

Connects to Qlik Sense Enterprise on Windows (QSEoW) or Qlik Cloud
to extract app metadata, reload tasks, and object definitions directly
from the server — without needing a ``.qvf`` file export.

Authentication methods:
- **Certificates** (QSEoW): client certificate + key pair
- **API Key** (Qlik Cloud): bearer token / API key
- **JWT** (Qlik Cloud): JSON Web Token

Usage::

    from qlik_export.qlik_server_client import QlikServerClient

    # Qlik Cloud
    client = QlikServerClient(
        server='https://tenant.qlikcloud.com',
        api_key='your-api-key',
    )

    # QSEoW with certificates
    client = QlikServerClient(
        server='https://qlik-server.corp.com',
        cert_path='client.pem',
        key_path='client_key.pem',
    )

    apps = client.list_apps()
    app_data = client.get_app('app-guid')
    tasks = client.get_reload_tasks('app-guid')
    objects = client.get_app_objects('app-guid')

.. note::

    This module uses only the Python standard library (``urllib``).
    For production use, consider adding ``requests`` as an optional
    dependency for connection pooling and retry support.
"""

import json
import logging
import ssl
import urllib.request
import urllib.parse
import urllib.error

logger = logging.getLogger(__name__)


class QlikServerClient:
    """REST API client for Qlik Sense Enterprise / Qlik Cloud.

    Provides methods to list apps, retrieve app metadata, and extract
    objects for migration without requiring a ``.qvf`` export.

    Args:
        server: Base URL of the Qlik server (e.g. ``'https://qlik.corp.com'``).
        api_key: API key for Qlik Cloud authentication.
        cert_path: Path to client certificate PEM file (QSEoW).
        key_path: Path to client private key PEM file (QSEoW).
        root_cert_path: Optional CA root certificate for QSEoW.
        user_directory: Qlik user directory (QSEoW, default: ``'INTERNAL'``).
        user_id: Qlik user ID (QSEoW, default: ``'sa_api'``).
        jwt_token: JWT token for Qlik Cloud authentication.
        verify_ssl: Whether to verify SSL certificates (default: True).
        timeout: Request timeout in seconds (default: 30).
    """

    def __init__(self, server, api_key=None, cert_path=None, key_path=None,
                 root_cert_path=None, user_directory='INTERNAL', user_id='sa_api',
                 jwt_token=None, verify_ssl=True, timeout=30):
        self.server = server.rstrip('/')
        self.api_key = api_key
        self.cert_path = cert_path
        self.key_path = key_path
        self.root_cert_path = root_cert_path
        self.user_directory = user_directory
        self.user_id = user_id
        self.jwt_token = jwt_token
        self.verify_ssl = verify_ssl
        self.timeout = timeout

        # Detect platform
        self._is_cloud = 'qlikcloud.com' in server.lower() or api_key or jwt_token

        # Build SSL context
        self._ssl_context = self._build_ssl_context()

    def _build_ssl_context(self):
        """Build SSL context for HTTPS connections."""
        ctx = ssl.create_default_context()

        if not self.verify_ssl:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

        if self.cert_path and self.key_path:
            ctx.load_cert_chain(self.cert_path, self.key_path)

        if self.root_cert_path:
            ctx.load_verify_locations(self.root_cert_path)

        return ctx

    def _build_headers(self):
        """Build HTTP headers for API requests."""
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }

        if self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'
        elif self.jwt_token:
            headers['Authorization'] = f'Bearer {self.jwt_token}'
        elif not self._is_cloud:
            # QSEoW: use X-Qlik-User header with certificate auth
            headers['X-Qlik-User'] = (
                f'UserDirectory={self.user_directory};'
                f'UserId={self.user_id}'
            )

        return headers

    def _request(self, method, path, data=None):
        """Make an HTTP request to the Qlik API.

        Args:
            method: HTTP method ('GET', 'POST', 'PUT', 'DELETE').
            path: API path (e.g. '/api/v1/apps').
            data: Optional request body (dict, will be JSON-encoded).

        Returns:
            dict or list: Parsed JSON response.

        Raises:
            QlikApiError: On HTTP error responses.
        """
        url = f'{self.server}{path}'
        headers = self._build_headers()

        body = json.dumps(data).encode('utf-8') if data else None

        req = urllib.request.Request(url, data=body, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req, context=self._ssl_context,
                                        timeout=self.timeout) as resp:
                response_body = resp.read().decode('utf-8')
                if response_body:
                    return json.loads(response_body)
                return {}
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8', errors='replace') if e.fp else ''
            logger.error("Qlik API error %d: %s %s — %s", e.code, method, path, error_body)
            raise QlikApiError(e.code, method, path, error_body) from e
        except urllib.error.URLError as e:
            logger.error("Qlik API connection error: %s — %s", path, e.reason)
            raise QlikApiError(0, method, path, str(e.reason)) from e

    # ── App Operations ────────────────────────────────────────────

    def list_apps(self):
        """List all apps accessible to the authenticated user.

        Returns:
            list[dict]: App summaries with id, name, description, etc.
        """
        if self._is_cloud:
            result = self._request('GET', '/api/v1/items?resourceType=app&limit=100')
            return result.get('data', [])
        else:
            return self._request('GET', '/qrs/app/full')

    def get_app(self, app_id):
        """Get detailed metadata for a single app.

        Args:
            app_id: App GUID.

        Returns:
            dict: Full app metadata.
        """
        if self._is_cloud:
            return self._request('GET', f'/api/v1/apps/{app_id}')
        else:
            return self._request('GET', f'/qrs/app/{app_id}')

    def get_app_objects(self, app_id, object_types=None):
        """Get all objects (sheets, visualizations, etc.) from an app.

        Args:
            app_id: App GUID.
            object_types: Optional list to filter by type
                (e.g. ``['sheet', 'masterobject', 'dimension', 'measure']``).

        Returns:
            list[dict]: App objects with type, properties, etc.
        """
        if self._is_cloud:
            result = self._request('GET', f'/api/v1/apps/{app_id}/objects')
            objects = result.get('data', result) if isinstance(result, dict) else result
        else:
            filter_str = ''
            if object_types:
                type_filters = ' or '.join(
                    f"objectType eq '{t}'" for t in object_types
                )
                filter_str = f'?filter={urllib.parse.quote(type_filters)}'
            objects = self._request(
                'GET', f'/qrs/app/object/full{filter_str}')

        if object_types and isinstance(objects, list):
            objects = [
                obj for obj in objects
                if (obj.get('qType') or obj.get('objectType', '')).lower()
                in [t.lower() for t in object_types]
            ]

        return objects if isinstance(objects, list) else []

    def get_app_script(self, app_id):
        """Get the load script of an app.

        Args:
            app_id: App GUID.

        Returns:
            str: The complete load script.
        """
        if self._is_cloud:
            result = self._request('GET', f'/api/v1/apps/{app_id}/script')
            return result.get('script', '') if isinstance(result, dict) else str(result)
        else:
            result = self._request('GET', f'/qrs/app/{app_id}/script')
            return result if isinstance(result, str) else str(result)

    # ── Reload Task Operations ────────────────────────────────────

    def get_reload_tasks(self, app_id=None):
        """Get reload tasks, optionally filtered by app.

        Args:
            app_id: Optional app GUID to filter tasks.

        Returns:
            list[dict]: Reload task definitions with triggers/schedules.
        """
        if self._is_cloud:
            path = '/api/v1/reloads'
            if app_id:
                path += f'?appId={app_id}'
            result = self._request('GET', path)
            return result.get('data', []) if isinstance(result, dict) else result
        else:
            path = '/qrs/reloadtask/full'
            if app_id:
                path += f'?filter=app.id eq {app_id}'
            return self._request('GET', path)

    def get_task_schedules(self, app_id=None):
        """Get scheduled triggers for reload tasks.

        Args:
            app_id: Optional app GUID to filter.

        Returns:
            list[dict]: Schedule trigger definitions.
        """
        tasks = self.get_reload_tasks(app_id)
        schedules = []

        for task in (tasks if isinstance(tasks, list) else []):
            task_name = task.get('name', '')
            triggers = task.get('schemaEvents', task.get('triggers', []))

            for trigger in (triggers if isinstance(triggers, list) else []):
                schedules.append({
                    'task_name': task_name,
                    'trigger': trigger,
                    'app_id': app_id or task.get('app', {}).get('id', ''),
                })

        return schedules

    # ── Dimension & Measure Operations ────────────────────────────

    def get_master_dimensions(self, app_id):
        """Get master dimensions from an app.

        Args:
            app_id: App GUID.

        Returns:
            list[dict]: Master dimension definitions.
        """
        objects = self.get_app_objects(app_id, object_types=['dimension'])
        return objects

    def get_master_measures(self, app_id):
        """Get master measures from an app.

        Args:
            app_id: App GUID.

        Returns:
            list[dict]: Master measure definitions.
        """
        objects = self.get_app_objects(app_id, object_types=['measure'])
        return objects

    # ── Data Connection Operations ────────────────────────────────

    def get_data_connections(self, app_id=None):
        """Get data connections.

        Args:
            app_id: Optional app GUID to scope connections.

        Returns:
            list[dict]: Data connection definitions.
        """
        if self._is_cloud:
            path = '/api/v1/data-connections'
            if app_id:
                path += f'?appId={app_id}'
            result = self._request('GET', path)
            return result.get('data', []) if isinstance(result, dict) else result
        else:
            path = '/qrs/dataconnection/full'
            return self._request('GET', path)

    # ── Stream & Space Operations ─────────────────────────────────

    def list_streams(self):
        """List all streams (QSEoW) or spaces (Cloud).

        Returns:
            list[dict]: Stream/space definitions.
        """
        if self._is_cloud:
            result = self._request('GET', '/api/v1/spaces')
            return result.get('data', []) if isinstance(result, dict) else result
        else:
            return self._request('GET', '/qrs/stream/full')

    # ── Extraction Helper ─────────────────────────────────────────

    def extract_app_for_migration(self, app_id):
        """Extract all data needed for migration from a single app.

        Convenience method that calls multiple API endpoints and
        assembles the result into the same 11-key structure used
        by the offline ``.qvf`` extractor.

        Args:
            app_id: App GUID.

        Returns:
            dict: Extraction data with keys matching the 11 intermediate
                JSON files (app_metadata, datasources, dimensions, etc.).
        """
        logger.info("Extracting app %s from server %s", app_id, self.server)

        app_meta = self.get_app(app_id)
        objects = self.get_app_objects(app_id)
        tasks = self.get_reload_tasks(app_id)
        connections = self.get_data_connections(app_id)

        # Classify objects
        sheets = [o for o in objects
                  if (o.get('qType') or o.get('objectType', '')).lower() == 'sheet']
        dimensions = [o for o in objects
                      if (o.get('qType') or o.get('objectType', '')).lower() == 'dimension']
        measures_list = [o for o in objects
                         if (o.get('qType') or o.get('objectType', '')).lower() == 'measure']
        visualizations = [o for o in objects
                          if (o.get('qType') or o.get('objectType', '')).lower()
                          in ('visualization', 'masterobject', 'chart')]
        bookmarks = [o for o in objects
                     if (o.get('qType') or o.get('objectType', '')).lower() == 'bookmark']
        variables = [o for o in objects
                     if (o.get('qType') or o.get('objectType', '')).lower() == 'variable']

        # Try to get load script
        try:
            script = self.get_app_script(app_id)
        except QlikApiError:
            script = ''

        return {
            'app_metadata': {
                'name': app_meta.get('name', ''),
                'description': app_meta.get('description', ''),
                'id': app_id,
                'server': self.server,
                '_reload_tasks': tasks,
                '_connections': connections,
            },
            'datasources': _connections_to_datasources(connections),
            'dimensions': dimensions,
            'measures': measures_list,
            'visualizations': visualizations,
            'sheets': sheets,
            'variables': variables,
            'loadscript': {'script': script},
            'associations': [],
            'bookmarks': bookmarks,
            'master_items': dimensions + measures_list,
        }


def _connections_to_datasources(connections):
    """Convert Qlik data connections to datasource format."""
    datasources = []
    for conn in (connections if isinstance(connections, list) else []):
        ds = {
            'name': conn.get('qName') or conn.get('name', ''),
            'connection': {
                'type': conn.get('qType') or conn.get('type', ''),
                'connectionString': conn.get('qConnectionString', ''),
                'server': conn.get('qServer', conn.get('server', '')),
                'database': conn.get('qDatabase', conn.get('database', '')),
            },
            'tables': [],
            'columns': [],
        }
        datasources.append(ds)
    return datasources


class QlikApiError(Exception):
    """Exception raised for Qlik API errors."""

    def __init__(self, status_code, method, path, message=''):
        self.status_code = status_code
        self.method = method
        self.path = path
        self.message = message
        super().__init__(
            f'Qlik API error {status_code}: {method} {path} — {message}'
        )
