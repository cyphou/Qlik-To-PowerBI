<!-- Copilot instructions for the Qlik to Power BI migration project -->

# Project: Qlik to Power BI Migration

Automated migration of Qlik artifacts to Power BI format.

## Architecture — Pipeline

```
Qlik source → [qlik_export] → Extraction → [output, powerbi_import, src/fabric_api] → Power BI
```

## Project Structure

- **Source / Extraction**: `qlik_export/`
- **Target / Generation**: `output/`, `powerbi_import/`, `src/fabric_api/`
- **Tests**: `tests/` (71 test files)
- **Docs**: `docs/`

## Key Modules

- **Extraction**:
  - `qlik_export\__init__.py`
  - `qlik_export\datasource_extractor.py`
  - `qlik_export\dax_converter.py`
  - `qlik_export\extraction_orchestrator.py`
  - `qlik_export\format_adapter.py`
  - `qlik_export\m_query_builder.py`
  - `qlik_export\m_query_generator.py`
  - `qlik_export\qlik_migrator.py`
  - `qlik_export\qlik_model_converter.py`
  - `qlik_export\qlik_script_converter.py`
  - `qlik_export\qlik_server_client.py`
  - `qlik_export\qvf_extractor.py`
  - `src\fabric_api\extraction_orchestrator.py`
  - `src\fabric_api\qvf_extractor.py`
- **Generation**:
  - `generate_report.py`
  - `powerbi_import\__init__.py`
  - `powerbi_import\alerts_generator.py`
  - `powerbi_import\api_server.py`
  - `powerbi_import\assessment.py`
  - `powerbi_import\calc_column_utils.py`
  - `powerbi_import\comparison_report.py`
  - `powerbi_import\config\__init__.py`
  - `powerbi_import\config\migration_config.py`
  - `powerbi_import\dataflow_generator.py`
  - `powerbi_import\dax_optimizer.py`
  - `powerbi_import\dax_query_generator.py`
  - `powerbi_import\dax_recipes.py`
  - `powerbi_import\deploy\__init__.py`
  - `powerbi_import\deploy\auth.py`
  - ... and 66 more
- **Conversion**:
  - `examples\plugins\dax_post_processor.py`
  - `src\fabric_api\dax_converter.py`
  - `src\fabric_api\qlik_model_converter.py`
  - `src\fabric_api\qlik_script_converter.py`
- **Assessment**:
  - `src\fabric_api\validator.py`
- **Deployment**:
  - `src\fabric_api\auth.py`
  - `src\fabric_api\client.py`
  - `src\fabric_api\deployer.py`
- **Orchestration**:
  - `migrate.py`
  - `src\main.py`
  - `tools\migration\migrate_advanced_aggregations.py`
  - `tools\migration\migrate_advanced_selections.py`
  - `tools\migration\migrate_alternate_states.py`
  - `tools\migration\migrate_bookmarks.py`
  - `tools\migration\migrate_collaboration.py`
  - `tools\migration\migrate_current_selections.py`
  - `tools\migration\migrate_custom_extensions.py`
  - `tools\migration\migrate_data_alerts.py`
  - `tools\migration\migrate_geoanalytics.py`
  - `tools\migration\migrate_inter_record_functions.py`
  - `tools\migration\migrate_listboxes.py`
  - `tools\migration\migrate_mashups.py`
  - `tools\migration\migrate_master_items.py`
  - ... and 14 more
- **Utilities**:
  - `examples\plugins\__init__.py`
  - `examples\plugins\custom_visual_mapper.py`
  - `examples\plugins\naming_convention.py`
  - `examples\powerbi\ADVANCED_PATTERNS.py`
  - `examples\powerbi\TROUBLESHOOTING.py`
  - `examples\powerbi\examples.py`
  - `examples\powerbi\pbi_project_examples.py`
  - `examples\powerbi\qlik_migration_examples.py`
  - `examples\powerbi\qlik_model_examples.py`
  - `examples\powerbi\qlik_script_examples.py`
  - `examples\powerbi\qvf_examples.py`
  - `scripts\check_m_syntax.py`
  - `scripts\recover_excel_data.py`
  - `scripts\verify_fields.py`
  - `scripts\version_bump.py`
  - ... and 9 more

## Hard Constraints

1. **Read before write** — never assume file contents from memory
2. **Test after every change** — run `pytest tests/ --tb=short -q`
3. **No duplicate functions** — always search for an existing name before creating one
4. **Git hygiene** — commit only when tests pass, conventional messages (`feat:`, `fix:`, `test:`, `docs:`)

## Multi-Agent Architecture

This project uses a specialized agent architecture. See `docs/AGENTS.md` for the full
architecture diagram and `.github/agents/` for per-agent definitions.

## Workflow Rules

### 1. Plan Before Build
- For multi-step work, create a plan before starting
- If something goes sideways, STOP and re-plan

### 2. Read Before Write
- **Always read target code before editing**
- Read `copilot-instructions.md` at session start for project rules

### 3. Testing Contract
- Run `pytest tests/ --tb=short -q` after EVERY implementation change
- If tests fail → fix them before reporting completion
- New features **require** new tests
- Never weaken test assertions to make tests pass

### 4. Scope Discipline
- Only modify files directly related to the task
- No drive-by refactors
- Prefer the smallest change that solves the problem
