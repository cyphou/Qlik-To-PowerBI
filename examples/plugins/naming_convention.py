"""
Naming Convention Enforcer Plugin
==================================

Enforces naming rules on tables, columns, and measures during
migration.  Runs in the ``post_extraction`` hook to rename objects
before they are written into TMDL / PBIR files.

Supported conventions:
    - ``snake_case``: sales_amount
    - ``PascalCase``: SalesAmount
    - ``camelCase``: salesAmount

Usage:
    from examples.plugins.naming_convention import NamingConventionPlugin
    from powerbi_import.plugins import get_plugin_manager

    manager = get_plugin_manager()
    manager.register(NamingConventionPlugin(convention="PascalCase"))

Config file usage:
    {
        "plugins": ["examples.plugins.naming_convention.NamingConventionPlugin"]
    }
"""

import re

from powerbi_import.plugins import PluginBase


def _to_words(name):
    """Split a name into words by common separators and casing transitions.

    Handles: snake_case, camelCase, PascalCase, spaces, hyphens.
    """
    # Insert boundary before uppercase letters preceded by lowercase
    s = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', name)
    # Split on non-alphanumeric characters
    return [w for w in re.split(r'[^a-zA-Z0-9]+', s) if w]


def to_snake_case(name):
    """Convert name to snake_case."""
    return '_'.join(w.lower() for w in _to_words(name))


def to_pascal_case(name):
    """Convert name to PascalCase."""
    return ''.join(w.capitalize() for w in _to_words(name))


def to_camel_case(name):
    """Convert name to camelCase."""
    words = _to_words(name)
    if not words:
        return name
    return words[0].lower() + ''.join(w.capitalize() for w in words[1:])


# Map convention names to converter functions
_CONVERTERS = {
    'snake_case': to_snake_case,
    'PascalCase': to_pascal_case,
    'camelCase': to_camel_case,
}


class NamingConventionPlugin(PluginBase):
    """Rename tables, columns, and measures to a consistent naming convention.

    Attributes:
        name: Plugin identifier.
    """

    name = "naming_convention"

    def __init__(self, convention="PascalCase"):
        """Initialize with a naming convention.

        Args:
            convention: One of ``'snake_case'``, ``'PascalCase'``,
                ``'camelCase'``.  Defaults to ``'PascalCase'``.

        Raises:
            ValueError: If the convention is not recognized.
        """
        super().__init__()
        if convention not in _CONVERTERS:
            raise ValueError(
                f"Unknown convention '{convention}'. "
                f"Choose from: {', '.join(sorted(_CONVERTERS))}"
            )
        self._convention = convention
        self._convert = _CONVERTERS[convention]

    def post_extraction(self, extracted_data):
        """Rename fields in extracted data to the configured convention.

        Renames:
        - Table names in datasources
        - Column captions in datasources
        - Calculation names in calculations
        - Parameter names in parameters

        Args:
            extracted_data: Dict of all extracted JSON objects.

        Returns:
            dict: Modified extracted data with renamed identifiers.
        """
        if not extracted_data or not isinstance(extracted_data, dict):
            return None

        data = dict(extracted_data)

        # Rename table names
        for ds in data.get('datasources', []):
            if isinstance(ds, dict):
                for tbl in ds.get('tables', []):
                    if isinstance(tbl, dict) and 'name' in tbl:
                        tbl['name'] = self._convert(tbl['name'])

        # Rename column captions
        for ds in data.get('datasources', []):
            if isinstance(ds, dict):
                for tbl in ds.get('tables', []):
                    if isinstance(tbl, dict):
                        for col in tbl.get('columns', []):
                            if isinstance(col, dict) and 'caption' in col:
                                col['caption'] = self._convert(col['caption'])

        # Rename calculations
        for calc in data.get('calculations', []):
            if isinstance(calc, dict) and 'name' in calc:
                calc['name'] = self._convert(calc['name'])

        # Rename parameters
        for param in data.get('parameters', []):
            if isinstance(param, dict) and 'name' in param:
                param['name'] = self._convert(param['name'])

        return data


# Convenience alias for config-based loading via "module.Plugin"
Plugin = NamingConventionPlugin
