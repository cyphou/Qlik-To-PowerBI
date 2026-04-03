# Example Plugins

This directory contains example plugins for the Qlik to Power BI migration pipeline.

## Available Plugins

| Plugin | File | Hook | Description |
|--------|------|------|-------------|
| **CustomVisualMapperPlugin** | `custom_visual_mapper.py` | `custom_visual_mapping` | Override Qlik → PBI visual type mappings |
| **DaxPostProcessorPlugin** | `dax_post_processor.py` | `transform_dax` | Apply regex-based DAX transformations after conversion |
| **NamingConventionPlugin** | `naming_convention.py` | `post_extraction` | Enforce naming conventions (snake_case, PascalCase, camelCase) |

## Quick Start

### 1. Register manually in code

```python
from powerbi_import.plugins import get_plugin_manager
from examples.plugins.naming_convention import NamingConventionPlugin

manager = get_plugin_manager()
manager.register(NamingConventionPlugin(convention="snake_case"))
```

### 2. Load from config file

Add a `plugins` list to your `config.json`:

```json
{
    "plugins": [
        "examples.plugins.custom_visual_mapper.CustomVisualMapperPlugin",
        "examples.plugins.dax_post_processor.DaxPostProcessorPlugin",
        "examples.plugins.naming_convention.NamingConventionPlugin"
    ]
}
```

### 3. Use the module-level `Plugin` alias

Each example exposes a `Plugin` alias at module level, so you can reference
just the module path:

```json
{
    "plugins": ["examples.plugins.custom_visual_mapper"]
}
```

## Writing Your Own Plugin

1. Create a Python file with a class that inherits from `PluginBase` (or implements the same methods):

```python
from powerbi_import.plugins import PluginBase

class MyPlugin(PluginBase):
    name = "my_plugin"

    def transform_dax(self, dax_formula):
        # Your custom logic here
        return dax_formula.replace("OLD_TABLE", "NEW_TABLE")
```

2. Register it via code or config file.

## Available Hooks

| Hook | Signature | When Called |
|------|-----------|------------|
| `pre_extraction` | `(Qlik_file: str) -> None` | Before Qlik XML parsing |
| `post_extraction` | `(extracted_data: dict) -> dict` | After extraction, before generation |
| `pre_generation` | `(converted_objects: dict) -> dict` | Before PBI project generation |
| `post_generation` | `(project_dir: str) -> None` | After PBI project generation |
| `transform_dax` | `(dax_formula: str) -> str` | For each converted DAX formula |
| `transform_m_query` | `(m_query: str) -> str` | For each generated M query |
| `custom_visual_mapping` | `(Qlik_mark: str) -> str\|None` | Visual type resolution |
