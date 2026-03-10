"""
Configuration for different deployment environments.

Provides per-environment settings (dev/staging/production) with
different timeouts, retries, log levels, and approval requirements.
"""

from enum import Enum


class EnvironmentType(Enum):
    """Deployment environment types."""
    DEVELOPMENT = 'development'
    STAGING = 'staging'
    PRODUCTION = 'production'


class EnvironmentConfig:
    """Environment-specific configurations."""

    CONFIGS = {
        EnvironmentType.DEVELOPMENT: {
            'log_level': 'DEBUG',
            'log_format': 'text',
            'deployment_timeout': 600,
            'retry_attempts': 3,
            'retry_delay': 2,
            'validate_before_deploy': True,
            'archive_artifacts': False,
        },
        EnvironmentType.STAGING: {
            'log_level': 'INFO',
            'log_format': 'text',
            'deployment_timeout': 300,
            'retry_attempts': 3,
            'retry_delay': 5,
            'validate_before_deploy': True,
            'archive_artifacts': True,
        },
        EnvironmentType.PRODUCTION: {
            'log_level': 'INFO',
            'log_format': 'text',
            'deployment_timeout': 300,
            'retry_attempts': 5,
            'retry_delay': 10,
            'validate_before_deploy': True,
            'archive_artifacts': True,
            'require_approval': True,
        },
    }

    @classmethod
    def get_config(cls, environment):
        """Get configuration for an environment.

        Args:
            environment: EnvironmentType enum value

        Returns:
            Dict of environment-specific settings
        """
        return cls.CONFIGS.get(environment,
                               cls.CONFIGS[EnvironmentType.DEVELOPMENT])

    @classmethod
    def apply_config(cls, environment):
        """Apply environment-specific settings to the global config.

        Args:
            environment: EnvironmentType enum value
        """
        from .settings import get_settings
        config = cls.get_config(environment)
        settings = get_settings()
        for key, value in config.items():
            if hasattr(settings, key):
                setattr(settings, key, value)
