"""Configuration file for different environments."""
from enum import Enum
from typing import Dict

from fabric_api.config.settings import get_settings


class EnvironmentType(Enum):
    """Deployment environment types."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class EnvironmentConfig:
    """Environment-specific configurations."""

    CONFIGS: Dict[EnvironmentType, Dict] = {
        EnvironmentType.DEVELOPMENT: {
            "log_level": "DEBUG",
            "log_format": "text",
            "deployment_timeout": 600,
            "retry_attempts": 3,
            "retry_delay": 2,
            "validate_before_deploy": True,
            "archive_artifacts": False,
        },
        EnvironmentType.STAGING: {
            "log_level": "INFO",
            "log_format": "json",
            "deployment_timeout": 300,
            "retry_attempts": 3,
            "retry_delay": 5,
            "validate_before_deploy": True,
            "archive_artifacts": True,
        },
        EnvironmentType.PRODUCTION: {
            "log_level": "INFO",
            "log_format": "json",
            "deployment_timeout": 300,
            "retry_attempts": 5,
            "retry_delay": 10,
            "validate_before_deploy": True,
            "archive_artifacts": True,
            "require_approval": True,
        },
    }

    @classmethod
    def get_config(cls, environment: EnvironmentType) -> Dict:
        """Get configuration for environment."""
        return cls.CONFIGS.get(environment, cls.CONFIGS[EnvironmentType.DEVELOPMENT])

    @classmethod
    def apply_config(cls, environment: EnvironmentType):
        """Apply environment-specific settings."""
        config = cls.get_config(environment)
        settings = get_settings()
        for key, value in config.items():
            if hasattr(settings, key):
                setattr(settings, key, value)
