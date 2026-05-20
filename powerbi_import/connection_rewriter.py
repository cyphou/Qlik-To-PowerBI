"""Connection string intelligence for Qlik migrations.

Parses Qlik connection metadata into structured ConnectionInfo objects,
supports environment-based server name rewriting, and generates gateway
configuration scripts.
"""

import json
import logging
import os

logger = logging.getLogger(__name__)


class ConnectionInfo:
    """Structured representation of a datasource connection."""

    def __init__(self, connector_type='', server='', port='', database='',
                 schema='', auth_type='', ssl=False, warehouse='',
                 project='', role='', filename='', service_name='',
                 custom_sql='', username='', extra=None):
        self.connector_type = connector_type
        self.server = server
        self.port = port
        self.database = database
        self.schema = schema
        self.auth_type = auth_type
        self.ssl = ssl
        self.warehouse = warehouse
        self.project = project
        self.role = role
        self.filename = filename
        self.service_name = service_name
        self.custom_sql = custom_sql
        self.username = username
        self.extra = extra or {}

    def to_dict(self):
        d = {
            'connector_type': self.connector_type,
            'server': self.server,
            'port': self.port,
            'database': self.database,
            'schema': self.schema,
            'auth_type': self.auth_type,
            'ssl': self.ssl,
        }
        if self.warehouse:
            d['warehouse'] = self.warehouse
        if self.project:
            d['project'] = self.project
        if self.role:
            d['role'] = self.role
        if self.filename:
            d['filename'] = self.filename
        if self.service_name:
            d['service_name'] = self.service_name
        if self.custom_sql:
            d['custom_sql'] = self.custom_sql
        if self.username:
            d['username'] = self.username
        if self.extra:
            d['extra'] = self.extra
        return d

    @classmethod
    def from_qlik_connection(cls, conn_dict):
        """Parse a Qlik connection dict into ConnectionInfo.

        Args:
            conn_dict: Dict with connection attributes from extraction.
        """
        details = conn_dict if isinstance(conn_dict, dict) else {}
        conn_type = details.get('type', details.get('connector_type', ''))
        return cls(
            connector_type=conn_type,
            server=details.get('server', details.get('host', '')),
            port=str(details.get('port', '')),
            database=details.get('database', details.get('dbname', '')),
            schema=details.get('schema', ''),
            auth_type=details.get('authentication', 'prompt'),
            ssl=details.get('ssl', False),
            warehouse=details.get('warehouse', ''),
            project=details.get('project', ''),
            role=details.get('role', ''),
            filename=details.get('filename', details.get('directory', '')),
            service_name=details.get('service', ''),
            custom_sql=details.get('custom_sql', ''),
            username=details.get('username', ''),
            extra={k: v for k, v in details.items()
                   if k not in ('type', 'connector_type', 'server', 'host',
                                'port', 'database', 'dbname', 'schema',
                                'authentication', 'ssl', 'warehouse',
                                'project', 'role', 'filename', 'directory',
                                'service', 'custom_sql', 'username')},
        )


def parse_connections(datasources_json):
    """Extract all connections from datasources extraction JSON.

    Args:
        datasources_json: List of datasource dicts from extraction.

    Returns:
        list[ConnectionInfo]: Parsed connection objects.
    """
    connections = []
    for ds in (datasources_json or []):
        conn_map = ds.get('connection_map', {})
        if conn_map:
            connections.append(ConnectionInfo.from_qlik_connection(conn_map))
        for conn in ds.get('connections', []):
            connections.append(ConnectionInfo.from_qlik_connection(conn))
    return connections


def load_connection_map(path):
    """Load a connection mapping JSON file.

    Format::

        {
            "source_server": "target_server",
            "prod-qlik-db.corp:5432": "prod-pbi-db.corp:5432"
        }
    """
    if not path or not os.path.exists(path):
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def rewrite_m_query(m_query, connection_map):
    """Rewrite server names in an M query using the connection map."""
    result = m_query
    for source, target in connection_map.items():
        result = result.replace(source, target)
    return result


def rewrite_connections(connections, connection_map):
    """Apply rewriting rules to a list of ConnectionInfo objects."""
    rewritten = []
    for conn in connections:
        new_conn = ConnectionInfo(
            connector_type=conn.connector_type,
            server=connection_map.get(conn.server, conn.server),
            port=conn.port,
            database=connection_map.get(conn.database, conn.database),
            schema=conn.schema,
            auth_type=conn.auth_type,
            ssl=conn.ssl,
            warehouse=conn.warehouse,
            project=conn.project,
            role=conn.role,
            filename=conn.filename,
            service_name=conn.service_name,
            custom_sql=conn.custom_sql,
            username=conn.username,
            extra=conn.extra,
        )
        full_server = f"{conn.server}:{conn.port}" if conn.port else conn.server
        if full_server in connection_map:
            parts = connection_map[full_server].split(':', 1)
            new_conn.server = parts[0]
            if len(parts) > 1:
                new_conn.port = parts[1]
        rewritten.append(new_conn)
    return rewritten


_OAUTH_TEMPLATES = {
    'Google Sheets': {
        'auth_type': 'OAuth2',
        'provider': 'Google',
        'scopes': ['https://www.googleapis.com/auth/spreadsheets.readonly'],
        'redirect_uri': 'https://oauth.powerbi.com/views/oauthredirect.html',
    },
    'Salesforce': {
        'auth_type': 'OAuth2',
        'provider': 'Salesforce',
        'scopes': ['api', 'refresh_token'],
        'redirect_uri': 'https://oauth.powerbi.com/views/oauthredirect.html',
    },
    'Snowflake': {
        'auth_type': 'OAuth2/SSO',
        'provider': 'Azure AD',
        'scopes': ['session:role:any'],
        'note': 'Configure SSO via Azure AD SAML or OAuth external browser',
    },
    'Databricks': {
        'auth_type': 'PAT/OAuth',
        'provider': 'Databricks',
        'note': 'Use Personal Access Token or Azure AD OAuth for Databricks',
    },
    'BigQuery': {
        'auth_type': 'OAuth2',
        'provider': 'Google',
        'scopes': ['https://www.googleapis.com/auth/bigquery.readonly'],
        'redirect_uri': 'https://oauth.powerbi.com/views/oauthredirect.html',
    },
}


def generate_oauth_template(connector_type):
    """Generate an OAuth credential template for a connector."""
    return _OAUTH_TEMPLATES.get(connector_type)


def generate_credential_templates(connections):
    """Generate credential templates for all connections."""
    templates = []
    for conn in connections:
        template = {
            'connector_type': conn.connector_type,
            'server': conn.server,
            'database': conn.database,
            'auth_type': conn.auth_type,
        }
        oauth = generate_oauth_template(conn.connector_type)
        if oauth:
            template['oauth'] = oauth
        else:
            template['credential_type'] = 'username_password'
            template['username_placeholder'] = conn.username or '<USERNAME>'
            template['password_placeholder'] = '<PASSWORD>'
        templates.append(template)
    return templates


_GATEWAY_CONN_TYPE_MAP = {
    'SQL Server': 'Sql',
    'PostgreSQL': 'PostgreSql',
    'Oracle': 'Oracle',
    'MySQL': 'MySql',
    'SAP HANA': 'SapHana',
    'Teradata': 'Teradata',
    'IBM DB2': 'DB2',
    'Amazon Redshift': 'AmazonRedshift',
    'Snowflake': 'Snowflake',
}


def generate_gateway_powershell(connections,
                                 gateway_cluster_id='<GATEWAY_CLUSTER_ID>'):
    """Generate PowerShell script for gateway datasource binding."""
    lines = [
        '# Auto-generated Gateway Datasource Configuration',
        '# Run in PowerShell with MicrosoftPowerBIMgmt module installed',
        '',
        'Import-Module MicrosoftPowerBIMgmt',
        'Connect-PowerBIServiceAccount',
        '',
        f'$gatewayClusterId = "{gateway_cluster_id}"',
        '',
    ]

    for i, conn in enumerate(connections):
        gw_type = _GATEWAY_CONN_TYPE_MAP.get(conn.connector_type, 'Other')
        ds_name = f"{conn.connector_type}_{conn.database or conn.server}_{i}"
        lines.append(f'# --- Datasource {i + 1}: {conn.connector_type} ---')
        lines.append(f'$dsParams{i} = @{{')
        lines.append(f'    "connectionDetails" = @{{')
        lines.append(f'        "server" = "{conn.server}"')
        if conn.database:
            lines.append(f'        "database" = "{conn.database}"')
        lines.append(f'    }}')
        lines.append(f'    "credentialDetails" = @{{')
        lines.append(f'        "credentialType" = "Basic"')
        lines.append(f'        "credentials" = \'{{\"credentialData\":[')
        lines.append(f'            {{\"name\":\"username\",\"value\":\"{conn.username or "<USER>"}\"}},'
                     f'{{\"name\":\"password\",\"value\":\"<PASSWORD>\"}}]}}\'')
        lines.append(f'    }}')
        lines.append(f'}}')
        lines.append(
            f'Add-PowerBIDataGatewayClusterDatasource '
            f'-GatewayClusterId $gatewayClusterId '
            f'-DatasourceType "{gw_type}" '
            f'-ConnectionDetails ($dsParams{i}.connectionDetails | ConvertTo-Json) '
            f'-CredentialDetails ($dsParams{i}.credentialDetails | ConvertTo-Json) '
            f'-DatasourceName "{ds_name}"'
        )
        lines.append('')

    return '\n'.join(lines)


def detect_connection_drift(old_connections, new_connections):
    """Detect changes between two sets of connections."""
    drifts = []
    max_len = max(len(old_connections), len(new_connections))

    for i in range(max_len):
        if i >= len(old_connections):
            drifts.append({
                'type': 'added',
                'index': i,
                'connector': new_connections[i].connector_type,
                'server': new_connections[i].server,
            })
            continue
        if i >= len(new_connections):
            drifts.append({
                'type': 'removed',
                'index': i,
                'connector': old_connections[i].connector_type,
                'server': old_connections[i].server,
            })
            continue

        old_c = old_connections[i]
        new_c = new_connections[i]
        fields_to_check = [
            'connector_type', 'server', 'port', 'database', 'schema',
            'auth_type', 'ssl', 'warehouse', 'project', 'role',
        ]
        for fld in fields_to_check:
            old_val = getattr(old_c, fld, '')
            new_val = getattr(new_c, fld, '')
            if str(old_val) != str(new_val):
                drifts.append({
                    'type': 'changed',
                    'index': i,
                    'connector': new_c.connector_type,
                    'field': fld,
                    'old_value': str(old_val),
                    'new_value': str(new_val),
                })

    return drifts
