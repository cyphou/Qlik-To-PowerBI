# Plugin Development Guide

Create custom plugins to extend the Qlik to Power BI migration pipeline.

---

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Plugin API](#plugin-api)
4. [Hook Reference](#hook-reference)
5. [Transform Hooks](#transform-hooks)
6. [Loading Plugins](#loading-plugins)
7. [Examples](#examples)
8. [Testing Plugins](#testing-plugins)

---

## Overview

The migration pipeline supports plugins at 7 hook points:

| Hook | Phase | Purpose |
|------|-------|---------|
| `pre_extraction` | Before extraction | Validate inputs, set up state |
| `post_extraction` | After extraction | Modify extracted data |
| `pre_generation` | Before generation | Transform converted objects |
| `post_generation` | After generation | Post-processing, notifications |
| `transform_dax` | Each DAX formula | Rewrite DAX expressions |
| `transform_m_query` | Each M query | Rewrite Power Query M |
| `custom_visual_mapping` | Each visual | Override visual type mapping |

---

## Quick Start

### 1. Create a Plugin

```python
# my_plugins.py

class ServerRenamer:
    """Renames server references in generated M queries."""
    name = "server_renamer"

    def transform_m_query(self, m_query):
        return m_query.replace("OldServer", "NewServer")

    def post_generation(self, project_dir):
        print(f"Migration complete: {project_dir}")
```

### 2. Use It

```bash
python migrate.py app.qvf --plugins my_plugins.ServerRenamer
```

That's it. The plugin's `transform_m_query` will be called for every generated M query, and `post_generation` will run after the project is created.

---

## Plugin API

### Base Class (Optional)

You can subclass `PluginBase` for IDE autocompletion, but it's not required. Any object with matching method signatures works (duck typing).

```python
from powerbi_import.plugins import PluginBase

class MyPlugin(PluginBase):
    name = "my_plugin"

    def transform_dax(self, dax_formula):
        # Your custom DAX transformation
        return dax_formula
```

### Duck-Typed Plugin

```python
class MyPlugin:
    name = "my_plugin"

    def transform_dax(self, dax_formula):
        return dax_formula
```

Both approaches are equivalent. Only implement the hooks you need — all others are optional.

### Required Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `name` | `str` | Human-readable plugin identifier (used in logs) |

---

## Hook Reference

### `pre_extraction(source_file: str) -> None`

Called before the extraction phase begins.

```python
def pre_extraction(self, source_file):
    print(f"Starting extraction of: {source_file}")
    # Validate file exists, check permissions, etc.
```

### `post_extraction(extracted_data: dict) -> dict | None`

Called after extraction completes. Can modify or replace the extracted data.

```python
def post_extraction(self, extracted_data):
    # Add custom metadata
    extracted_data['custom_field'] = 'value'
    return extracted_data  # Return modified data
```

Return `None` to keep the original data unchanged.

### `pre_generation(converted_objects: dict) -> dict | None`

Called before Power BI project generation. Can modify converted objects.

```python
def pre_generation(self, converted_objects):
    # Filter out certain tables
    if 'tables' in converted_objects:
        converted_objects['tables'] = [
            t for t in converted_objects['tables']
            if not t['name'].startswith('_tmp')
        ]
    return converted_objects
```

### `post_generation(project_dir: str) -> None`

Called after the PBIP project is generated.

```python
def post_generation(self, project_dir):
    # Send notification, copy files, trigger deployment
    print(f"Project generated at: {project_dir}")
```

---

## Transform Hooks

Transform hooks are chained — each plugin receives the output of the previous one.

### `transform_dax(dax_formula: str) -> str`

Called for each converted DAX formula. Use this to apply organization-specific naming conventions or fix known conversion issues.

```python
def transform_dax(self, dax_formula):
    # Replace legacy table names
    formula = dax_formula.replace("'OldSales'", "'FactSales'")
    formula = formula.replace("'OldCustomer'", "'DimCustomer'")
    return formula
```

### `transform_m_query(m_query: str) -> str`

Called for each generated Power Query M expression.

```python
def transform_m_query(self, m_query):
    # Update server names for new environment
    return m_query.replace(
        '"qlik-prod-server"',
        '"powerbi-prod-server"'
    )
```

### `custom_visual_mapping(source_mark: str) -> str | None`

Override the default visual type mapping for specific chart types.

```python
def custom_visual_mapping(self, source_mark):
    # Use custom visual for sankey diagrams
    if source_mark == "sankey":
        return "sankeyDiagram"
    # Return None to use default mapping
    return None
```

---

## Loading Plugins

### Via CLI

```bash
# Single plugin
python migrate.py app.qvf --plugins my_module.MyPlugin

# Multiple plugins (applied in order)
python migrate.py app.qvf --plugins my_module.Plugin1 my_module.Plugin2
```

### Via Code

```python
from powerbi_import.plugins import get_plugin_manager

pm = get_plugin_manager()
pm.register(MyPlugin())

# Or load from module paths
pm.load_from_config(["my_module.MyPlugin"])
```

### Plugin Resolution

The `--plugins` argument accepts module paths in these formats:

| Format | Behavior |
|--------|----------|
| `module.ClassName` | Import `module`, instantiate `ClassName` |
| `package.module.ClassName` | Import `package.module`, instantiate `ClassName` |
| `module` | Import `module`, look for a `Plugin` class |

Ensure the plugin module is importable (on `PYTHONPATH` or in the project directory).

---

## Examples

### Table Renamer

```python
class TableRenamer:
    """Apply corporate naming conventions to tables."""
    name = "table_renamer"

    RENAMES = {
        "'Sales'": "'FactSales'",
        "'Customers'": "'DimCustomer'",
        "'Products'": "'DimProduct'",
        "'Calendar'": "'DimDate'",
    }

    def transform_dax(self, dax_formula):
        for old, new in self.RENAMES.items():
            dax_formula = dax_formula.replace(old, new)
        return dax_formula
```

### Migration Logger

```python
import json
from datetime import datetime
from pathlib import Path

class MigrationLogger:
    """Log migration events to a JSON file."""
    name = "migration_logger"

    def __init__(self):
        self.events = []

    def pre_extraction(self, source_file):
        self.events.append({
            "event": "extraction_start",
            "source": source_file,
            "time": datetime.now().isoformat(),
        })

    def post_generation(self, project_dir):
        self.events.append({
            "event": "generation_complete",
            "output": project_dir,
            "time": datetime.now().isoformat(),
        })
        log_path = Path(project_dir) / "migration_log.json"
        log_path.write_text(json.dumps(self.events, indent=2))
```

### Custom Visual Registry

```python
class CustomVisuals:
    """Map Qlik extensions to custom Power BI visuals."""
    name = "custom_visuals"

    MAPPINGS = {
        "sankey": "sankeyDiagram",
        "network": "forceDirectedGraph",
        "calendar-heatmap": "calendarVisual",
        "radar": "radarChart",
    }

    def custom_visual_mapping(self, source_mark):
        return self.MAPPINGS.get(source_mark)
```

---

## Testing Plugins

### Unit Testing

```python
import pytest
from powerbi_import.plugins import PluginManager

def test_table_renamer():
    pm = PluginManager()
    pm.register(TableRenamer())

    result = pm.apply_transform("transform_dax", "SUM('Sales'[Amount])")
    assert "'FactSales'" in result
    assert "'Sales'" not in result

def test_custom_visual():
    pm = PluginManager()
    pm.register(CustomVisuals())

    assert pm.call_hook("custom_visual_mapping", source_mark="sankey") == "sankeyDiagram"
    assert pm.call_hook("custom_visual_mapping", source_mark="unknown") is None
```

### Integration Testing

```python
def test_plugin_in_pipeline():
    from powerbi_import.plugins import reset_plugin_manager

    pm = reset_plugin_manager()
    pm.register(TableRenamer())

    # Run migration and verify output contains renamed tables
    # ...
```

### Error Handling

Plugins that raise exceptions are caught and logged — they don't crash the pipeline:

```python
class FlakyPlugin:
    name = "flaky"

    def transform_dax(self, formula):
        raise RuntimeError("oops")

# Pipeline continues, original formula is preserved
```
