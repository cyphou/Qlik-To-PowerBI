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
import os
import random
import socket
import ssl
import string
import time
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

        # QSEoW QRS API mandates a 16-char Xrfkey (CSRF token) in both the
        # query string and the X-Qlik-Xrfkey header on every request.
        self._xrfkey = ''.join(
            random.choices(string.ascii_letters + string.digits, k=16)
        )

        # Build SSL context
        self._ssl_context_error = None
        try:
            self._ssl_context = self._build_ssl_context()
        except (ssl.SSLError, OSError) as exc:
            # Keep the client constructible so test_connection() can return
            # a structured diagnostic instead of failing in __init__.
            self._ssl_context_error = str(exc)
            self._ssl_context = ssl.create_default_context()
            if not self.verify_ssl:
                self._ssl_context.check_hostname = False
                self._ssl_context.verify_mode = ssl.CERT_NONE

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

    def _apply_qrs_xrfkey(self, path, headers):
        """Append the mandatory Xrfkey to QSEoW QRS requests.

        The QRS API rejects any request that lacks a matching 16-char
        ``xrfkey`` query parameter and ``X-Qlik-Xrfkey`` header (HTTP 400).
        Cloud (``/api/v1``) endpoints do not use it.
        """
        if self._is_cloud or not path.startswith('/qrs'):
            return path, headers
        sep = '&' if '?' in path else '?'
        path = f'{path}{sep}xrfkey={self._xrfkey}'
        headers = dict(headers)
        headers['X-Qlik-Xrfkey'] = self._xrfkey
        return path, headers

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
        if self._ssl_context_error:
            raise QlikApiError(
                0,
                method,
                path,
                f'Invalid TLS/certificate configuration: {self._ssl_context_error}',
            )

        headers = self._build_headers()
        path, headers = self._apply_qrs_xrfkey(path, headers)
        url = f'{self.server}{path}'

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
            log_body = error_body if len(error_body) <= 500 else error_body[:500] + '…'
            logger.error("Qlik API error %d: %s %s — %s", e.code, method, path, log_body)
            raise QlikApiError(e.code, method, path, error_body) from e
        except urllib.error.URLError as e:
            logger.error("Qlik API connection error: %s — %s", path, e.reason)
            raise QlikApiError(0, method, path, str(e.reason)) from e

    # ── Connection / TLS / Certificate Diagnostics ────────────────

    def test_connection(self):
        """Run non-destructive connection, TLS, certificate and auth checks.

        Never raises — every problem is captured as a structured check so the
        caller can render a full diagnostic report. Performs, in order:

        1. URL/scheme validation (HTTPS expected).
        2. Client certificate / key / root-CA file validation (QSEoW).
        3. TCP reachability to host:port.
        4. TLS handshake — trusted (respecting ``verify_ssl``) plus an
           unverified read of the presented server certificate to report the
           subject, issuer and expiry regardless of trust.
        5. Authentication — a lightweight authenticated endpoint
           (``/api/v1/users/me`` for Cloud, ``/qrs/about`` for QSEoW).

        Returns:
            dict: ``{'ok', 'server', 'platform', 'auth_method', 'checks': [...]}``
            where each check is ``{'name', 'status': pass|warn|fail, 'message'}``.
        """
        checks = []

        def add(name, status, message):
            checks.append({'name': name, 'status': status, 'message': message})

        parts = urllib.parse.urlsplit(self.server)
        host = parts.hostname or ''
        port = parts.port or (443 if parts.scheme == 'https' else 80)
        platform = 'cloud' if self._is_cloud else 'qseow'
        auth_method = (
            'api_key' if self.api_key else
            'jwt' if self.jwt_token else
            'certificate' if self.cert_path else
            'none'
        )

        # 1. Scheme
        if parts.scheme == 'https':
            add('url', 'pass', f'HTTPS endpoint {host}:{port}')
        elif parts.scheme == 'http':
            add('url', 'warn', 'Endpoint uses plain HTTP — traffic is not encrypted')
        else:
            add('url', 'fail', f'Invalid/unsupported URL: {self.server!r}')
            return {'ok': False, 'server': self.server, 'platform': platform,
                    'auth_method': auth_method, 'checks': checks}

        # 2. Client certificate material (QSEoW certificate auth)
        if self.cert_path or self.key_path:
            if self.cert_path and not os.path.isfile(self.cert_path):
                add('client_cert', 'fail', f'Certificate file not found: {self.cert_path}')
            elif self.cert_path and not self.key_path:
                add('client_cert', 'fail',
                    'Client certificate provided without a private key (key_path)')
            else:
                try:
                    probe = ssl.create_default_context()
                    probe.load_cert_chain(self.cert_path, self.key_path)
                    add('client_cert', 'pass',
                        f'Client certificate + key loaded ({os.path.basename(self.cert_path)})')
                except (ssl.SSLError, OSError) as exc:
                    add('client_cert', 'fail', f'Failed to load client cert/key: {exc}')
        if self.root_cert_path:
            if not os.path.isfile(self.root_cert_path):
                add('root_ca', 'fail', f'Root CA file not found: {self.root_cert_path}')
            else:
                try:
                    probe = ssl.create_default_context()
                    probe.load_verify_locations(self.root_cert_path)
                    add('root_ca', 'pass', f'Root CA loaded ({os.path.basename(self.root_cert_path)})')
                except (ssl.SSLError, OSError) as exc:
                    add('root_ca', 'fail', f'Failed to load root CA: {exc}')

        # 3. TCP reachability
        try:
            with socket.create_connection((host, port), timeout=self.timeout):
                add('tcp', 'pass', f'TCP connection to {host}:{port} succeeded')
        except OSError as exc:
            add('tcp', 'fail', f'Cannot reach {host}:{port} — {exc}')
            return {'ok': False, 'server': self.server, 'platform': platform,
                    'auth_method': auth_method, 'checks': checks}

        # 4. TLS handshake + certificate inspection (HTTPS only)
        if parts.scheme == 'https':
            # 4a. Trusted handshake using the configured context.
            try:
                with socket.create_connection((host, port), timeout=self.timeout) as sock:
                    with self._ssl_context.wrap_socket(sock, server_hostname=host) as ss:
                        proto = ss.version()
                if not self.verify_ssl:
                    add('tls', 'warn',
                        f'TLS {proto} handshake OK but certificate verification is DISABLED')
                else:
                    add('tls', 'pass', f'TLS {proto} handshake succeeded (certificate trusted)')
            except ssl.SSLCertVerificationError as exc:
                add('tls', 'fail', f'Certificate verification failed: {exc.verify_message or exc}')
            except (ssl.SSLError, OSError) as exc:
                add('tls', 'fail', f'TLS handshake failed: {exc}')

            # 4b. Read the presented certificate (unverified) for reporting.
            cert = self._read_peer_certificate(host, port)
            if cert:
                self._append_cert_checks(cert, host, add)
            else:
                add('certificate', 'warn', 'Could not read server certificate details')

        # 5. Authenticated endpoint
        endpoint = '/api/v1/users/me' if self._is_cloud else '/qrs/about'
        try:
            self._request('GET', endpoint)
            add('auth', 'pass', f'Authenticated request to {endpoint} succeeded ({auth_method})')
        except QlikApiError as exc:
            if exc.status_code in (401, 403):
                add('auth', 'fail', f'Authentication rejected (HTTP {exc.status_code}) using {auth_method}')
            elif exc.status_code == 0:
                add('auth', 'fail', f'Connection error during auth probe: {exc.message}')
            else:
                add('auth', 'warn',
                    f'Auth probe returned HTTP {exc.status_code}; endpoint may differ on this server')

        ok = all(c['status'] != 'fail' for c in checks)
        return {'ok': ok, 'server': self.server, 'platform': platform,
                'auth_method': auth_method, 'checks': checks}

    def _read_peer_certificate(self, host, port):
        """Read the server certificate via an unverified TLS connection.

        Returns the parsed certificate dict (subject/issuer/notAfter/SAN) or
        ``None`` on failure. Uses an unverified context so expiry and issuer
        can be reported even when the chain is untrusted.
        """
        try:
            ctx = ssl._create_unverified_context()
            with socket.create_connection((host, port), timeout=self.timeout) as sock:
                with ctx.wrap_socket(sock, server_hostname=host) as ss:
                    der = ss.getpeercert(binary_form=True)
            if not der:
                return None
            pem = ssl.DER_cert_to_PEM_cert(der)
            tmp = None
            try:
                import tempfile
                with tempfile.NamedTemporaryFile(
                        'w', suffix='.pem', delete=False, encoding='utf-8') as fh:
                    fh.write(pem)
                    tmp = fh.name
                # Private but stable CPython helper that parses a PEM file.
                return ssl._ssl._test_decode_cert(tmp)
            finally:
                if tmp and os.path.isfile(tmp):
                    os.unlink(tmp)
        except Exception as exc:  # noqa: BLE001 - diagnostics must not raise
            logger.debug("Peer certificate read failed: %s", exc)
            return None

    @staticmethod
    def _append_cert_checks(cert, host, add):
        """Add subject/issuer/expiry/SAN checks from a parsed certificate."""
        def _rdn(field):
            for rdn in cert.get(field, ()):  # tuple of tuples of (k, v)
                for k, v in rdn:
                    if k in ('commonName', 'organizationName'):
                        return v
            return '?'

        subject_cn = _rdn('subject')
        issuer_cn = _rdn('issuer')
        add('cert_subject', 'pass', f'Subject: {subject_cn} | Issuer: {issuer_cn}')

        not_after = cert.get('notAfter')
        if not_after:
            try:
                expiry = ssl.cert_time_to_seconds(not_after)
                days = int((expiry - time.time()) / 86400)
                if days < 0:
                    add('cert_expiry', 'fail', f'Certificate EXPIRED {-days} day(s) ago ({not_after})')
                elif days <= 30:
                    add('cert_expiry', 'warn', f'Certificate expires in {days} day(s) ({not_after})')
                else:
                    add('cert_expiry', 'pass', f'Certificate valid for {days} more day(s) ({not_after})')
            except (ValueError, OverflowError):
                add('cert_expiry', 'warn', f'Could not parse notAfter: {not_after}')

        # Hostname / SAN coverage (ssl.match_hostname was removed in 3.12)
        sans = [v for typ, v in cert.get('subjectAltName', ()) if typ == 'DNS']
        if sans:
            covered = any(
                host == s or (s.startswith('*.') and host.endswith(s[1:]))
                for s in sans
            )
            status = 'pass' if covered else 'warn'
            add('cert_hostname', status,
                f'SAN DNS: {", ".join(sans[:5])}'
                + ('' if covered else f' (does not cover {host})'))

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
