"""Configuration management for Qlik to Power BI migration."""

from .migration_config import MigrationConfig, load_config

__all__ = ['MigrationConfig', 'load_config']
