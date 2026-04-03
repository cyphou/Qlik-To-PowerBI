"""
Custom Visual Mapper Plugin
============================

Overrides the default Qlik → Power BI visual type mappings.

Use cases:
    - Map Qlik bar charts to a custom visual instead of clusteredBarChart
    - Route specific mark types to third-party AppSource visuals
    - Force all scatter plots to use a bubble chart variant

Usage:
    from examples.plugins.custom_visual_mapper import CustomVisualMapperPlugin
    from powerbi_import.plugins import get_plugin_manager

    manager = get_plugin_manager()
    manager.register(CustomVisualMapperPlugin())

Config file usage:
    {
        "plugins": ["examples.plugins.custom_visual_mapper.CustomVisualMapperPlugin"]
    }
"""

from powerbi_import.plugins import PluginBase


class CustomVisualMapperPlugin(PluginBase):
    """Override visual type mappings during migration.

    Attributes:
        name: Plugin identifier.
        VISUAL_OVERRIDES: Dict mapping Qlik mark type (lowercase)
            to Power BI visual type string.
    """

    name = "custom_visual_mapper"

    # Override mappings: Qlik_mark (lowercase) → pbi visual type
    VISUAL_OVERRIDES = {
        "bar": "clusteredBarChart",
        "gantt bar": "clusteredBarChart",
        "circle": "scatterChart",
        "square": "treemap",
    }

    def __init__(self, overrides=None):
        """Initialize with optional custom overrides.

        Args:
            overrides: Dict of {Qlik_mark: pbi_visual_type} to merge
                with the default VISUAL_OVERRIDES.
        """
        super().__init__()
        self._overrides = dict(self.VISUAL_OVERRIDES)
        if overrides:
            self._overrides.update(overrides)

    def custom_visual_mapping(self, Qlik_mark):
        """Return the overridden PBI visual type for a Qlik mark.

        Args:
            Qlik_mark: The Qlik mark type string (e.g., 'bar', 'line').

        Returns:
            str | None: The PBI visual type, or None to use the default mapping.
        """
        key = (Qlik_mark or "").strip().lower()
        return self._overrides.get(key)


# Convenience alias for config-based loading via "module.Plugin"
Plugin = CustomVisualMapperPlugin
