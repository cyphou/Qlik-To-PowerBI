"""
Configuration settings for Fabric Deployment.

Lazy-loaded so that we don't require pydantic-settings at import time.
Uses environment variables with optional .env file support.

Environment Variables:
    FABRIC_WORKSPACE_ID:   Target Fabric workspace ID
    FABRIC_API_BASE_URL:   Fabric API base URL (default: https://api.powerbi.com/v1.0)
    FABRIC_TENANT_ID:      Azure AD tenant ID
    FABRIC_CLIENT_ID:      Service Principal client ID
    FABRIC_CLIENT_SECRET:  Service Principal client secret
    USE_MANAGED_IDENTITY:  Use Managed Identity (true/false)
    LOG_LEVEL:             Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    LOG_FORMAT:            Log format (json or text)
    DEPLOYMENT_TIMEOUT:    HTTP timeout in seconds (default: 300)
    RETRY_ATTEMPTS:        Number of retry attempts (default: 3)
    RETRY_DELAY:           Delay between retries in seconds (default: 5)
"""

import os
import logging

logger = logging.getLogger(__name__)

_settings_instance = None


def _load_dotenv():
    """Best-effort .env loading (no-op if python-dotenv is not installed)."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass


class _FallbackSettings:
    """Minimal settings object that reads from environment variables.

    Works without any external dependencies — uses os.getenv() directly.
    Validates setting values on initialization.
    """

    _VALID_LOG_LEVELS = {'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'}
    _VALID_LOG_FORMATS = {'text', 'json'}

    def __init__(self):
        _load_dotenv()
        self.fabric_workspace_id = os.getenv('FABRIC_WORKSPACE_ID', '')
        self.fabric_api_base_url = os.getenv('FABRIC_API_BASE_URL',
                                              'https://api.powerbi.com/v1.0')
        self.fabric_tenant_id = os.getenv('FABRIC_TENANT_ID', '')
        self.fabric_client_id = os.getenv('FABRIC_CLIENT_ID', '')
        self.fabric_client_secret = os.getenv('FABRIC_CLIENT_SECRET', '')
        self.use_managed_identity = os.getenv('USE_MANAGED_IDENTITY',
                                               'false').lower() == 'true'

        # Log level validation
        raw_log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
        if raw_log_level not in self._VALID_LOG_LEVELS:
            logger.warning(f"Invalid LOG_LEVEL '{raw_log_level}', defaulting to INFO")
            raw_log_level = 'INFO'
        self.log_level = raw_log_level

        # Log format validation
        raw_log_format = os.getenv('LOG_FORMAT', 'text').lower()
        if raw_log_format not in self._VALID_LOG_FORMATS:
            logger.warning(f"Invalid LOG_FORMAT '{raw_log_format}', defaulting to text")
            raw_log_format = 'text'
        self.log_format = raw_log_format

        # Numeric settings with validation
        self.deployment_timeout = self._parse_positive_number(
            'DEPLOYMENT_TIMEOUT', '300', default=300)
        self.retry_attempts = self._parse_positive_int(
            'RETRY_ATTEMPTS', '3', default=3)
        self.retry_delay = self._parse_positive_number(
            'RETRY_DELAY', '5', default=5)

    @staticmethod
    def _parse_positive_int(env_name, raw_default, default=0):
        """Parse a positive integer from env var, with validation."""
        raw = os.getenv(env_name, raw_default)
        try:
            val = int(raw)
            if val < 0:
                logger.warning(f"{env_name}={val} is negative, using {default}")
                return default
            return val
        except (ValueError, TypeError):
            logger.warning(f"Invalid {env_name}='{raw}', using {default}")
            return default

    @staticmethod
    def _parse_positive_number(env_name, raw_default, default=0):
        """Parse a positive number (int or float) from env var."""
        raw = os.getenv(env_name, raw_default)
        try:
            val = float(raw)
            if val < 0:
                logger.warning(f"{env_name}={val} is negative, using {default}")
                return default
            return val
        except (ValueError, TypeError):
            logger.warning(f"Invalid {env_name}='{raw}', using {default}")
            return default


def _make_pydantic_settings():
    """Try to create a pydantic-settings based settings object.

    Returns a Pydantic model if pydantic-settings is installed,
    otherwise raises ImportError.
    """
    from pydantic import Field
    from pydantic_settings import BaseSettings

    class FabricSettings(BaseSettings):
        """Microsoft Fabric API configuration settings."""

        fabric_workspace_id: str = Field(default='')
        fabric_api_base_url: str = Field(
            default='https://api.powerbi.com/v1.0',
        )
        fabric_tenant_id: str = Field(default='')
        fabric_client_id: str = Field(default='')
        fabric_client_secret: str = Field(default='')
        use_managed_identity: bool = Field(default=False)
        log_level: str = Field(default='INFO')
        log_format: str = Field(default='text')
        deployment_timeout: int = Field(default=300)
        retry_attempts: int = Field(default=3)
        retry_delay: int = Field(default=5)

        model_config = {
            'env_file': '.env',
            'case_sensitive': False,
        }

    return FabricSettings()


def get_settings():
    """Return the singleton settings instance (lazy-loaded).

    Falls back to _FallbackSettings (pure stdlib) if pydantic-settings
    is not installed.
    """
    global _settings_instance
    if _settings_instance is not None:
        return _settings_instance

    try:
        _settings_instance = _make_pydantic_settings()
        logger.debug('Settings loaded via pydantic-settings')
    except Exception:
        _settings_instance = _FallbackSettings()
        logger.debug('Settings loaded via environment fallback')

    return _settings_instance
