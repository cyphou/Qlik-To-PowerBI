"""Gateway and OAuth configuration generator for Power BI data connections.

Generates data gateway connection references and OAuth redirect templates
that users can configure with their actual credentials and gateway IDs.

Usage:
    from powerbi_import.gateway_config import GatewayConfigGenerator
    gen = GatewayConfigGenerator()
    config = gen.generate_gateway_config(datasources)
    gen.write_config(project_dir, config)
"""

import json
import os
import uuid


# ═══════════════════════════════════════════════════════════════════
# Connector → OAuth / Gateway mapping
# ═══════════════════════════════════════════════════════════════════

OAUTH_CONNECTORS = {
    'bigquery': {
        'provider': 'Google',
        'auth_type': 'OAuth2',
        'auth_url': 'https://accounts.google.com/o/oauth2/v2/auth',
        'token_url': 'https://oauth2.googleapis.com/token',
        'scopes': ['https://www.googleapis.com/auth/bigquery.readonly'],
    },
    'snowflake': {
        'provider': 'Snowflake',
        'auth_type': 'OAuth2',
        'auth_url': 'https://<account>.snowflakecomputing.com/oauth/authorize',
        'token_url': 'https://<account>.snowflakecomputing.com/oauth/token-request',
        'scopes': ['session:role:<role>'],
    },
    'salesforce': {
        'provider': 'Salesforce',
        'auth_type': 'OAuth2',
        'auth_url': 'https://login.salesforce.com/services/oauth2/authorize',
        'token_url': 'https://login.salesforce.com/services/oauth2/token',
        'scopes': ['api', 'refresh_token'],
    },
    'google_sheets': {
        'provider': 'Google',
        'auth_type': 'OAuth2',
        'auth_url': 'https://accounts.google.com/o/oauth2/v2/auth',
        'token_url': 'https://oauth2.googleapis.com/token',
        'scopes': ['https://www.googleapis.com/auth/spreadsheets.readonly'],
    },
    'google_analytics': {
        'provider': 'Google',
        'auth_type': 'OAuth2',
        'auth_url': 'https://accounts.google.com/o/oauth2/v2/auth',
        'token_url': 'https://oauth2.googleapis.com/token',
        'scopes': ['https://www.googleapis.com/auth/analytics.readonly'],
    },
    'azure_sql': {
        'provider': 'AzureAD',
        'auth_type': 'OAuth2',
        'auth_url': 'https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/authorize',
        'token_url': 'https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token',
        'scopes': ['https://database.windows.net/.default'],
    },
    'azure_synapse': {
        'provider': 'AzureAD',
        'auth_type': 'OAuth2',
        'auth_url': 'https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/authorize',
        'token_url': 'https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token',
        'scopes': ['https://database.windows.net/.default'],
    },
    'sharepoint': {
        'provider': 'AzureAD',
        'auth_type': 'OAuth2',
        'auth_url': 'https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/authorize',
        'token_url': 'https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token',
        'scopes': ['https://graph.microsoft.com/.default'],
    },
    'databricks': {
        'provider': 'Databricks',
        'auth_type': 'PersonalAccessToken',
        'auth_url': '',
        'token_url': '',
        'scopes': [],
    },
}

GATEWAY_CONNECTORS = frozenset({
    'sqlserver', 'postgresql', 'mysql', 'oracle', 'sap_hana', 'sap_bw',
    'teradata', 'db2', 'informix', 'odbc', 'oledb',
})


class GatewayConfigGenerator:
    """Generates gateway and OAuth configuration files for PBI data connections."""

    def generate_gateway_config(self, datasources):
        """Analyze datasources and generate connection configs.

        Args:
            datasources: List of datasource dicts from extraction.

        Returns:
            dict with 'connections', 'gateway', and 'oauth' sections.
        """
        connections = []
        gateway_needed = False
        oauth_configs = []

        for ds in (datasources or []):
            conn_type = (ds.get('connection_type') or ds.get('type') or '').lower().replace(' ', '_')
            conn_info = ds.get('connection', {}) if isinstance(ds.get('connection'), dict) else {}
            server = conn_info.get('server', ds.get('server', ''))
            database = conn_info.get('database', ds.get('database', ''))
            ds_name = ds.get('name', ds.get('caption', f'Datasource_{len(connections) + 1}'))

            conn_entry = {
                'id': str(uuid.uuid4()),
                'name': ds_name,
                'connection_type': conn_type,
                'server': server,
                'database': database,
                'auth_type': 'Windows',  # default
            }

            # Check if this connector needs a gateway
            if conn_type in GATEWAY_CONNECTORS or (server and not server.startswith('http')):
                gateway_needed = True
                conn_entry['requires_gateway'] = True
                conn_entry['gateway_id'] = '${GATEWAY_ID}'
            else:
                conn_entry['requires_gateway'] = False

            # Check if this connector supports OAuth
            if conn_type in OAUTH_CONNECTORS:
                oauth = OAUTH_CONNECTORS[conn_type].copy()
                oauth['datasource_name'] = ds_name
                oauth['client_id'] = '${CLIENT_ID}'
                oauth['client_secret'] = '${CLIENT_SECRET}'
                oauth['redirect_uri'] = 'https://login.microsoftonline.com/common/oauth2/nativeclient'
                oauth_configs.append(oauth)
                conn_entry['auth_type'] = 'OAuth2'

            connections.append(conn_entry)

        return {
            'connections': connections,
            'gateway': {
                'required': gateway_needed,
                'gateway_id': '${GATEWAY_ID}' if gateway_needed else None,
                'gateway_name': '${GATEWAY_NAME}' if gateway_needed else None,
                'cluster_id': '${GATEWAY_CLUSTER_ID}' if gateway_needed else None,
                'note': 'Configure these values with your on-premises data gateway installation' if gateway_needed else 'No gateway required — all connections are cloud-based',
            },
            'oauth': oauth_configs,
        }

    def write_config(self, project_dir, config):
        """Write gateway/OAuth config files to the project directory.

        Args:
            project_dir: Path to the .pbip project root.
            config: Config dict from ``generate_gateway_config()``.
        """
        config_dir = os.path.join(project_dir, 'ConnectionConfig')
        os.makedirs(config_dir, exist_ok=True)

        # Main gateway config
        gateway_file = os.path.join(config_dir, 'gateway_config.json')
        with open(gateway_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

        # OAuth redirect templates (one per OAuth-enabled datasource)
        for oauth in config.get('oauth', []):
            safe_name = (oauth.get('datasource_name', 'ds')
                         .replace(' ', '_').replace('/', '_')[:50])
            oauth_file = os.path.join(config_dir, f'oauth_{safe_name}.json')
            with open(oauth_file, 'w', encoding='utf-8') as f:
                json.dump(oauth, f, indent=2, ensure_ascii=False)

        return config_dir

    def generate_and_write(self, project_dir, datasources):
        """Convenience: generate config and write to project in one call."""
        config = self.generate_gateway_config(datasources)
        return self.write_config(project_dir, config)
