<!-- DOC-SHINY-BANNER -->
![Documentation](https://img.shields.io/badge/Documentation-Shiny_Style-0A66C2?style=flat-square&logo=readthedocs&logoColor=white)
![Maintained](https://img.shields.io/badge/Maintained-2026-2EA44F?style=flat-square&logo=github&logoColor=white)
![Navigation](https://img.shields.io/badge/Navigation-Quick_Access-6F42C1?style=flat-square&logo=bookstack&logoColor=white)
# API Reference

Public API documentation for key modules in the Qlik to Power BI migration toolkit.

> **Version:** 9.0.0

---

## Table of Contents

1. [DAX Converter](#dax-converter) — `qlik_export/dax_converter.py`
2. [PBIP Generator](#pbip-generator) — `powerbi_import/pbip_generator.py`
3. [Power BI Importer](#power-bi-importer) — `powerbi_import/import_to_powerbi.py`
4. [Plugin System](#plugin-system) — `powerbi_import/plugins.py`
5. [Progress Tracking](#progress-tracking) — `powerbi_import/progress.py`
6. [DAX Optimizer](#dax-optimizer) — `powerbi_import/dax_optimizer.py` *(v9)*
7. [Shared Model Builder](#shared-model-builder) — `powerbi_import/shared_model.py` *(v9)*
8. [Fabric Project Generator](#fabric-project-generator) — `powerbi_import/fabric_project_generator.py` *(v9)*
9. [Server Assessment](#server-assessment) — `powerbi_import/server_assessment.py` *(v9)*
10. [Governance](#governance) — `powerbi_import/governance.py` *(v9)*

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

---

## DAX Optimizer

**Module:** `powerbi_import.dax_optimizer` *(v9)*

AST-based DAX rewriter that optimizes generated DAX expressions for readability and performance.

### `optimize_dax()`

Apply all optimization passes to a DAX expression.

```python
def optimize_dax(expression: str) -> str
```

**Optimizations applied:**
- Nested IF → SWITCH rewrite
- ISBLANK(x, default, x) → COALESCE(x, default)
- Constant folding (e.g., `1 + 2` → `3`)
- VAR extraction for repeated sub-expressions
- SUMX simplification
- Time Intelligence auto-generation

### `build_measure_dag()`

Build a directed acyclic graph of measure dependencies.

```python
def build_measure_dag(measures: list) -> dict
```

**Returns:** `{measure_name: [dependency1, dependency2, ...]}` — topological dependency map.

### `optimize_model()`

Optimize all measures in a converted model.

```python
def optimize_model(converted_objects: dict) -> dict
```

---

## Shared Model Builder

**Module:** `powerbi_import.shared_model` *(v9)*

Multi-app merge engine with fingerprint-based table matching.

### Class: `SharedModelBuilder`

```python
class SharedModelBuilder:
    def __init__(self)
    def add_app(self, app_name: str, converted_objects: dict) -> None
    def merge(self) -> dict
    def get_merge_report(self) -> dict
```

### `add_app()`

Register an app's converted objects for merging.

### `merge()`

Merge all registered apps into a single shared semantic model. Uses Jaccard column overlap scoring to match tables across apps.

**Returns:** Merged `converted_objects` dict with deduplicated tables and unified measures.

### `get_merge_report()`

Generate a merge assessment report with match scores and conflict details.

---

## Fabric Project Generator

**Module:** `powerbi_import.fabric_project_generator` *(v9)*

Orchestrates generation of Fabric-native artifacts.

### Class: `FabricProjectGenerator`

```python
class FabricProjectGenerator:
    def __init__(self, output_dir: str = "output/fabric")
    def generate(self, app_name: str, converted_objects: dict) -> str
```

**Generated artifacts:**
- Lakehouse delta table schemas & DDL
- Dataflow Gen2 Power Query M ingestion
- PySpark ETL notebooks (9 connector templates)
- 3-stage Data Pipeline orchestrator
- DirectLake semantic model

**Returns:** Path to the generated Fabric project directory.

---

## Server Assessment

**Module:** `powerbi_import.server_assessment` *(v9)*

Portfolio-level assessment for batch migration planning.

### `assess_server()`

Assess a directory of Qlik exports for migration readiness.

```python
def assess_server(export_dir: str) -> dict
```

**Returns:** Assessment dict with per-app RED/YELLOW/GREEN status, complexity scores, effort estimates, and wave planning recommendations.

---

## Governance

**Module:** `powerbi_import.governance` *(v9)*

Enterprise governance checks for migrated artifacts.

### `check_pii()`

Scan column names and expressions for PII patterns.

```python
def check_pii(converted_objects: dict) -> list
```

**Returns:** List of PII findings with column name, table, and PII type (email, SSN, phone, etc.).

### `check_naming_conventions()`

Validate naming conventions against configurable rules.

```python
def check_naming_conventions(converted_objects: dict, rules: dict = None) -> list
```

### `generate_audit_trail()`

Generate a JSONL audit trail of all migration decisions.

```python
def generate_audit_trail(migration_events: list, output_path: str) -> str
```

