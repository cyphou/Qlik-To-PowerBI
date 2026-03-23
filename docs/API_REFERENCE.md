# API Reference

Public API documentation for key modules in the Qlik to Power BI migration toolkit.

---

## Table of Contents

1. [DAX Converter](#dax-converter) — `qlik_export/dax_converter.py`
2. [PBIP Generator](#pbip-generator) — `powerbi_import/pbip_generator.py`
3. [Power BI Importer](#power-bi-importer) — `powerbi_import/import_to_powerbi.py`
4. [Plugin System](#plugin-system) — `powerbi_import/plugins.py`
5. [Progress Tracking](#progress-tracking) — `powerbi_import/progress.py`

---

## DAX Converter

**Module:** `qlik_export.dax_converter`

### `convert_qlik_expression_to_dax()`

Convert a single Qlik expression to DAX.

```python
def convert_qlik_expression_to_dax(
    qlik_expr: str,
    table_name: str = "",
    col_table_map: Optional[Dict[str, str]] = None,
    relationships: Optional[List[Dict]] = None,
    is_calculated_column: bool = False,
    variables: Optional[Dict[str, str]] = None,
) -> str
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `qlik_expr` | `str` | Qlik expression (e.g. `"Sum(Sales)"`, `"If(IsNull([Amt]), 0, [Amt])"`) |
| `table_name` | `str` | Table where this expression lives |
| `col_table_map` | `dict` | `{column_name: table_name}` lookup for `RELATED()` insertion |
| `relationships` | `list` | List of relationship dicts for cross-table inference |
| `is_calculated_column` | `bool` | Whether this is a row-level calculated column |
| `variables` | `dict` | `{var_name: var_definition}` for `$(vName)` expansion |

**Returns:** DAX expression string.

**Example:**

```python
from qlik_export.dax_converter import convert_qlik_expression_to_dax

dax = convert_qlik_expression_to_dax("Sum({<Year={2024}>} Sales)")
# → "CALCULATE(SUM('Table'[Sales]), 'Table'[Year] = 2024)"
```

---

### `convert_qlik_format_to_dax()`

Convert a Qlik number/date format string to DAX format string.

```python
def convert_qlik_format_to_dax(qlik_format: str) -> str
```

---

### `convert_qlik_type_to_dax()`

Convert a Qlik data type to DAX data type.

```python
def convert_qlik_type_to_dax(qlik_type: str) -> str
```

---

### `convert_measures_to_dax()`

Batch convert a list of Qlik measures.

```python
def convert_measures_to_dax(
    measures: List[Dict],
    table_name: str = "",
    col_table_map: Optional[Dict[str, str]] = None,
) -> List[Dict]
```

Returns measures with `dax_expression` field added.

---

### `convert_dimensions_to_dax()`

Batch convert Qlik dimensions (including calculated dimensions).

```python
def convert_dimensions_to_dax(
    dimensions: List[Dict],
    table_name: str = "",
    col_table_map: Optional[Dict[str, str]] = None,
    relationships: Optional[List[Dict]] = None,
) -> List[Dict]
```

Returns dimensions with `dax_expression` field added.

---

## PBIP Generator

**Module:** `powerbi_import.pbip_generator`

### Class: `PowerBIProjectGenerator`

Generates complete Power BI Project (`.pbip`) files from converted objects.

```python
class PowerBIProjectGenerator:
    def __init__(self, output_dir='artifacts/powerbi_projects/')
```

### `generate_project()`

Main entry point — generates a complete PBIP project.

```python
def generate_project(
    self,
    report_name: str,
    converted_objects: dict,
    calendar_start: int = None,
    calendar_end: int = None,
    culture: str = None,
    model_mode: str = 'import',
    output_format: str = 'pbip',
    paginated: bool = False,
) -> str
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `report_name` | `str` | Report name (used for folder/file naming) |
| `converted_objects` | `dict` | All converted objects (tables, measures, visuals, etc.) |
| `calendar_start` | `int` | Start year for auto Calendar table (default: 2020) |
| `calendar_end` | `int` | End year for auto Calendar table (default: 2030) |
| `culture` | `str` | Override culture/locale for semantic model |
| `model_mode` | `str` | `'import'`, `'directquery'`, etc. |
| `output_format` | `str` | `'pbip'`, `'pbir'`, `'tmdl'` |
| `paginated` | `bool` | Generate paginated report layout alongside interactive |

**Returns:** Path to the generated project directory.

**Example:**

```python
from powerbi_import.pbip_generator import PowerBIProjectGenerator

gen = PowerBIProjectGenerator(output_dir='output/')
path = gen.generate_project("Sales", converted_objects)
# → "output/Sales/"
```

---

### `create_semantic_model_structure()`

Creates the SemanticModel directory structure.

```python
def create_semantic_model_structure(self, project_dir, report_name, converted_objects) -> str
```

---

### `create_tmdl_model()`

Creates the semantic model in TMDL format.

```python
def create_tmdl_model(self, sm_dir, report_name, converted_objects)
```

---

### `create_report_structure()`

Creates the Report structure in PBIR v4.0 format.

```python
def create_report_structure(self, project_dir, report_name, converted_objects) -> str
```

**Generated structure:**

```
Report/
  .platform
  definition.pbir
  definition/
    version.json
    report.json
    pages/
      pages.json
      {pageName}/
        page.json
        visuals/
          {visualId}/
            visual.json
```

---

## Power BI Importer

**Module:** `powerbi_import.import_to_powerbi`

### Class: `PowerBIImporter`

Reads Qlik intermediate JSON files, transforms them into `converted_objects`, and invokes the generator.

```python
class PowerBIImporter:
    def __init__(self, source_dir=None)
```

### `import_all()`

Import all extracted objects and generate a Power BI project.

```python
def import_all(
    self,
    generate_pbip: bool = True,
    report_name: str = None,
    output_dir: str = None,
    calendar_start: int = None,
    calendar_end: int = None,
    culture: str = None,
    model_mode: str = 'import',
    output_format: str = 'pbip',
    paginated: bool = False,
    validate: bool = True,
)
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `generate_pbip` | `bool` | Generate Power BI Projects (`.pbip`) |
| `report_name` | `str` | Override report name |
| `output_dir` | `str` | Custom output directory |
| `calendar_start` | `int` | Start year for Calendar table |
| `calendar_end` | `int` | End year for Calendar table |
| `culture` | `str` | Override culture/locale |
| `model_mode` | `str` | Semantic model mode |
| `output_format` | `str` | Output format |
| `paginated` | `bool` | Generate paginated report |
| `validate` | `bool` | Run post-generation validation |

---

### `generate_powerbi_project()`

Generate a Power BI Project from pre-converted objects.

```python
def generate_powerbi_project(
    self,
    report_name: str,
    converted_objects: dict,
    output_dir: str = None,
    calendar_start: int = None,
    calendar_end: int = None,
    culture: str = None,
    model_mode: str = 'import',
    output_format: str = 'pbip',
    paginated: bool = False,
) -> str
```

---

## Plugin System

**Module:** `powerbi_import.plugins`

### Class: `PluginManager`

Manages plugin lifecycle and hook dispatch.

```python
class PluginManager:
    def register(self, plugin) -> None
    def load_from_config(self, plugin_specs: list) -> None
    def call_hook(self, hook_name: str, **kwargs) -> Any
    def apply_transform(self, hook_name: str, value: str) -> str
    def has_plugins(self) -> bool
    @property
    def plugins(self) -> list
```

### Class: `PluginBase`

Optional base class for plugins. All methods are no-ops by default.

```python
class PluginBase:
    name = "base_plugin"
    def pre_extraction(self, source_file: str) -> None
    def post_extraction(self, extracted_data: dict) -> dict | None
    def pre_generation(self, converted_objects: dict) -> dict | None
    def post_generation(self, project_dir: str) -> None
    def transform_dax(self, dax_formula: str) -> str
    def transform_m_query(self, m_query: str) -> str
    def custom_visual_mapping(self, source_mark: str) -> str | None
```

### Module Functions

```python
def get_plugin_manager() -> PluginManager
def reset_plugin_manager() -> PluginManager
```

---

## Progress Tracking

**Module:** `powerbi_import.progress`

### Class: `MigrationProgress`

Step-level progress tracking with optional callback and CLI progress bar.

```python
class MigrationProgress:
    def __init__(self, total_steps: int, on_step=None, show_bar: bool = True)
    def start(self, name: str) -> None
    def complete(self, message: str = "") -> None
    def fail(self, error: str) -> None
    def skip(self, name: str, reason: str = "") -> None
    def summary(self) -> dict
```

### Class: `NullProgress`

Silent no-op variant for JSON/quiet mode.

```python
class NullProgress:
    def start(self, name: str) -> None
    def complete(self, message: str = "") -> None
    def fail(self, error: str) -> None
    def skip(self, name: str, reason: str = "") -> None
```
