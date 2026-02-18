"""Configuration settings for Fabric Deployment.

Lazy-loaded so that we don't require pydantic-settings at import time.
Import ``get_settings()`` when you need access to configuration.
"""
from __future__ import annotations

import os
import logging
from typing import Optional, Literal

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lightweight dataclass fallback when pydantic-settings is not installed
# ---------------------------------------------------------------------------
_settings_instance = None


def _load_dotenv() -> None:
    """Best-effort .env loading."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass


class _FallbackSettings:
    """Minimal settings object that reads from environment variables."""

    def __init__(self) -> None:
        _load_dotenv()
        self.fabric_workspace_id: str = os.getenv("FABRIC_WORKSPACE_ID", "")
        self.fabric_api_base_url: str = os.getenv("FABRIC_API_BASE_URL", "https://api.powerbi.com/v1.0")
        self.fabric_tenant_id: str = os.getenv("FABRIC_TENANT_ID", "")
        self.fabric_client_id: str = os.getenv("FABRIC_CLIENT_ID", "")
        self.fabric_client_secret: str = os.getenv("FABRIC_CLIENT_SECRET", "")
        self.use_managed_identity: bool = os.getenv("USE_MANAGED_IDENTITY", "false").lower() == "true"
        self.log_level: str = os.getenv("LOG_LEVEL", "INFO")
        self.log_format: str = os.getenv("LOG_FORMAT", "json")
        self.deployment_timeout: int = int(os.getenv("DEPLOYMENT_TIMEOUT", "300"))
        self.retry_attempts: int = int(os.getenv("RETRY_ATTEMPTS", "3"))
        self.retry_delay: int = int(os.getenv("RETRY_DELAY", "5"))


def _make_pydantic_settings():
    """Try to create a pydantic-settings based settings object."""
    from pydantic import Field, field_validator
    from pydantic_settings import BaseSettings

    class FabricSettings(BaseSettings):
        """Microsoft Fabric API configuration settings."""

        fabric_workspace_id: str = Field(default="")
        fabric_api_base_url: str = Field(
            default="https://api.powerbi.com/v1.0",
        )
        fabric_tenant_id: str = Field(default="")
        fabric_client_id: str = Field(default="")
        fabric_client_secret: str = Field(default="")
        use_managed_identity: bool = Field(default=False)
        log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
            default="INFO"
        )
        log_format: Literal["json", "text"] = Field(default="json")
        deployment_timeout: int = Field(default=300)
        retry_attempts: int = Field(default=3)
        retry_delay: int = Field(default=5)

        model_config = {
            "env_file": ".env",
            "case_sensitive": False,
        }

    return FabricSettings()


def get_settings():
    """Return the singleton settings instance (lazy-loaded)."""
    global _settings_instance
    if _settings_instance is not None:
        return _settings_instance

    try:
        _settings_instance = _make_pydantic_settings()
        logger.debug("Settings loaded via pydantic-settings")
    except Exception:
        _settings_instance = _FallbackSettings()
        logger.debug("Settings loaded via environment fallback")

    return _settings_instance


# Backwards-compatible alias so existing code that does
#   ``from config.settings import settings``
# or ``from fabric_api.config.settings import settings``
# keeps working.
settings = property(lambda self: get_settings())  # type: ignore[assignment]

# If someone does ``from … import settings`` at module level we give them a
# lazy proxy.  But for simplicity just eagerly create it — the fallback is
# cheap and doesn't require any optional dependency.
try:
    settings = _make_pydantic_settings()
except Exception:
    settings = _FallbackSettings()
