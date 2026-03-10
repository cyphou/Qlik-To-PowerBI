"""
Plugin architecture for the Qlik to Power BI migration pipeline.

Defines hook points that plugins can implement to customize behavior:

    - pre_extraction(source_file: str) -> None
    - post_extraction(extracted_data: dict) -> dict
    - pre_generation(converted_objects: dict) -> dict
    - post_generation(project_dir: str) -> None
    - transform_dax(dax_formula: str) -> str
    - transform_m_query(m_query: str) -> str
    - custom_visual_mapping(source_mark: str) -> str | None

Plugins are discovered via:
    1. A 'plugins' list in the config file (module paths)
    2. Manual registration via PluginManager.register()

Example plugin:

    class MyPlugin:
        name = "custom_connector"

        def transform_m_query(self, m_query):
            return m_query.replace("OldServer", "NewServer")

        def post_generation(self, project_dir):
            print(f"Generated project at: {project_dir}")
"""

import importlib
import logging

logger = logging.getLogger('qlik_to_powerbi.plugins')


class PluginBase:
    """Base class for migration plugins.

    Plugins can subclass this or implement the same methods as duck-typed classes.
    All hook methods are optional — only implement the ones you need.
    """

    name = "base_plugin"

    def pre_extraction(self, source_file):
        """Called before extraction begins.

        Args:
            source_file: Path to the source file (.qvf / .json)
        """
        pass

    def post_extraction(self, extracted_data):
        """Called after extraction, before generation.

        Can modify the extracted data dict in-place or return a new one.

        Args:
            extracted_data: Dict of all extracted JSON objects

        Returns:
            dict: Modified extracted data (or None to keep original)
        """
        return None

    def pre_generation(self, converted_objects):
        """Called before Power BI project generation.

        Can modify the converted objects in-place or return a new dict.

        Args:
            converted_objects: Dict of converted source objects

        Returns:
            dict: Modified converted objects (or None to keep original)
        """
        return None

    def post_generation(self, project_dir):
        """Called after Power BI project generation completes.

        Args:
            project_dir: Path to the generated .pbip project directory
        """
        pass

    def transform_dax(self, dax_formula):
        """Called for each DAX formula after conversion.

        Args:
            dax_formula: The converted DAX formula string

        Returns:
            str: Modified DAX formula (or original to keep unchanged)
        """
        return dax_formula

    def transform_m_query(self, m_query):
        """Called for each M query after generation.

        Args:
            m_query: The generated Power Query M string

        Returns:
            str: Modified M query (or original to keep unchanged)
        """
        return m_query

    def custom_visual_mapping(self, source_mark):
        """Override visual type mapping for a source mark type.

        Args:
            source_mark: The source mark type string (e.g., 'bar', 'line')

        Returns:
            str | None: PBI visual type string, or None to use default mapping
        """
        return None


class PluginManager:
    """Manages plugin lifecycle and hook dispatch.

    Usage:
        manager = PluginManager()
        manager.register(MyPlugin())
        manager.load_from_config(["my_module.MyPlugin"])

        # Dispatch hooks
        manager.call_hook("pre_extraction", source_file="app.qvf")
        modified = manager.apply_transform("transform_dax", formula)
    """

    def __init__(self):
        self._plugins = []

    def register(self, plugin):
        """Register a plugin instance.

        Args:
            plugin: Object implementing one or more hook methods
        """
        name = getattr(plugin, 'name', plugin.__class__.__name__)
        self._plugins.append(plugin)
        logger.info(f"Plugin registered: {name}")

    def load_from_config(self, plugin_specs):
        """Load plugins from config file specifications.

        Each spec can be:
            - "module.path.ClassName" — imports and instantiates
            - "module.path" — imports module and looks for 'Plugin' class

        Args:
            plugin_specs: List of plugin specification strings
        """
        for spec in (plugin_specs or []):
            try:
                if '.' in spec:
                    module_path, _, class_name = spec.rpartition('.')
                    if class_name[0].isupper():
                        # Looks like a class name
                        mod = importlib.import_module(module_path)
                        cls = getattr(mod, class_name)
                        self.register(cls())
                    else:
                        # Entire string is a module path
                        mod = importlib.import_module(spec)
                        if hasattr(mod, 'Plugin'):
                            self.register(mod.Plugin())
                        else:
                            logger.warning(f"Plugin module '{spec}' has no 'Plugin' class")
                else:
                    mod = importlib.import_module(spec)
                    if hasattr(mod, 'Plugin'):
                        self.register(mod.Plugin())
                    else:
                        logger.warning(f"Plugin module '{spec}' has no 'Plugin' class")
            except Exception as e:
                logger.error(f"Failed to load plugin '{spec}': {e}")

    def call_hook(self, hook_name, **kwargs):
        """Call a hook on all registered plugins.

        Args:
            hook_name: Method name to call (e.g., 'pre_extraction')
            **kwargs: Arguments to pass to the hook method

        Returns:
            The last non-None return value, or None
        """
        result = None
        for plugin in self._plugins:
            method = getattr(plugin, hook_name, None)
            if method and callable(method):
                try:
                    ret = method(**kwargs)
                    if ret is not None:
                        result = ret
                except Exception as e:
                    name = getattr(plugin, 'name', plugin.__class__.__name__)
                    logger.error(f"Plugin '{name}' hook '{hook_name}' failed: {e}")
        return result

    def apply_transform(self, hook_name, value):
        """Apply a chain of transformations from all plugins.

        Each plugin receives the output of the previous one.

        Args:
            hook_name: Transform method name (e.g., 'transform_dax')
            value: Initial value to transform

        Returns:
            Transformed value after all plugins have been applied
        """
        for plugin in self._plugins:
            method = getattr(plugin, hook_name, None)
            if method and callable(method):
                try:
                    result = method(value)
                    if result is not None:
                        value = result
                except Exception as e:
                    name = getattr(plugin, 'name', plugin.__class__.__name__)
                    logger.error(f"Plugin '{name}' transform '{hook_name}' failed: {e}")
        return value

    @property
    def plugins(self):
        """List of registered plugins."""
        return list(self._plugins)

    def has_plugins(self):
        """Check if any plugins are registered."""
        return bool(self._plugins)


# Global plugin manager instance
_manager = PluginManager()


def get_plugin_manager():
    """Get the global plugin manager instance."""
    return _manager


def reset_plugin_manager():
    """Reset the global plugin manager (mostly for testing)."""
    global _manager
    _manager = PluginManager()
    return _manager
