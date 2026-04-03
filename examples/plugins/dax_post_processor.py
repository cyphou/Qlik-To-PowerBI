"""
DAX Post-Processor Plugin
==========================

Applies custom DAX transformations after the standard Qlik → DAX
conversion.  Useful for organization-specific adjustments such as:

    - Replace server/database names in DAX expressions
    - Wrap all measures with error handling (IFERROR)
    - Inject comments or annotations
    - Enforce formatting conventions

Usage:
    from examples.plugins.dax_post_processor import DaxPostProcessorPlugin
    from powerbi_import.plugins import get_plugin_manager

    manager = get_plugin_manager()
    manager.register(DaxPostProcessorPlugin())

Config file usage:
    {
        "plugins": ["examples.plugins.dax_post_processor.DaxPostProcessorPlugin"]
    }
"""

import re

from powerbi_import.plugins import PluginBase


class DaxPostProcessorPlugin(PluginBase):
    """Apply custom transformations to every converted DAX formula.

    Attributes:
        name: Plugin identifier.
    """

    name = "dax_post_processor"

    # Default replacements: list of (pattern, replacement) tuples.
    # Patterns are applied in order using re.sub().
    DEFAULT_REPLACEMENTS = [
        # Example: normalise whitespace around operators
        (r'\s*\+\s*', ' + '),
        (r'\s*-\s*', ' - '),
    ]

    def __init__(self, replacements=None, wrap_iferror=False):
        """Initialize with optional custom replacements.

        Args:
            replacements: List of (regex_pattern, replacement) tuples
                to apply to each DAX formula.  Defaults to
                DEFAULT_REPLACEMENTS if not provided.
            wrap_iferror: If True, wrap every measure-level DAX formula
                with IFERROR(formula, BLANK()).
        """
        super().__init__()
        self._replacements = (
            replacements if replacements is not None
            else list(self.DEFAULT_REPLACEMENTS)
        )
        self._wrap_iferror = wrap_iferror

    def add_replacement(self, pattern, replacement):
        """Add a regex replacement rule.

        Args:
            pattern: Python regex pattern string.
            replacement: Replacement string (may contain back-references).
        """
        self._replacements.append((pattern, replacement))

    def transform_dax(self, dax_formula):
        """Apply configured transformations to the DAX formula.

        Args:
            dax_formula: The converted DAX formula string.

        Returns:
            str: Modified DAX formula.
        """
        if not dax_formula:
            return dax_formula

        result = dax_formula
        for pattern, replacement in self._replacements:
            result = re.sub(pattern, replacement, result)

        if self._wrap_iferror and result.strip():
            result = f"IFERROR({result}, BLANK())"

        return result


# Convenience alias for config-based loading via "module.Plugin"
Plugin = DaxPostProcessorPlugin
