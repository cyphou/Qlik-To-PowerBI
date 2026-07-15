<p align="center">
  <img src="docs/images/logo.svg" alt="Qlik to Power BI" width="480"/>
</p>

# Contributing to Qlik to Power BI Migration Tool

Thank you for your interest in contributing! This guide covers the development setup, coding standards, and contribution workflow.

---

## Development Setup

### Prerequisites

- Python 3.12+ (tested on 3.12–3.14)
- Power BI Desktop (December 2025+) for validating output
- Git

### Getting Started

```bash
# Clone the repository
git clone <repo-url>
cd QlikToPowerBI

# Create a virtual environment
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # macOS/Linux

# Install development dependencies
pip install -r requirements.txt

# Run tests
python -m unittest discover -s tests -v
```

### Project Structure

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for a detailed architecture overview.

```
qlik_export/      → Extraction layer (Qlik QVF/JSON → 11 intermediate JSON)
powerbi_import/   → Generation layer (JSON → .pbip project, 55 modules)
tests/            → Unit and integration tests (2,000 tests across 44 files)
docs/             → Documentation
examples/         → Sample Qlik apps
artifacts/        → Migration output
.github/agents/   → 10 AI agent definitions (preceptorship model)
```

## Coding Standards

### No External Dependencies

The core migration pipeline uses **Python standard library only**. This is a strict design requirement:

- `xml.etree`, `json`, `os`, `re`, `uuid`, `zipfile`, `argparse`, `datetime`, `copy`, `logging`, `glob`
- Optional: `azure-identity` (deployment auth), `requests` (HTTP client), `pydantic-settings` (typed config)

If your change requires a new dependency, it must be behind a `try/except ImportError` guard.

### Style

- Follow PEP 8 with `flake8` (errors only: E9, F63, F7, F82)
- `ruff` is also configured in CI
- Maximum line length: 120 characters (soft limit)
- Use type hints where practical (validated with pyrightconfig.json)

### Naming Conventions

- Module-level functions for `tmdl_generator.py` (not a class)
- Class-based for `PBIPGenerator`, `QlikExtractor`, `ArtifactValidator`
- Private methods prefixed with `_`
- Constants as `UPPER_SNAKE_CASE`

### DAX Formulas

- All DAX output must be single-line (multi-line formulas condensed)
- Apostrophes in table names escaped: `'Name'` → `''Name''`
- Use `SELECTEDVALUE()` for scalar references (not `VALUES()`)
- Cross-table refs use `RELATED()` for manyToOne, `LOOKUPVALUE()` for manyToMany

## Testing

### Running Tests

```bash
# All tests
python -m pytest tests/ -v

# Single test file
python -m pytest tests/test_dax_converter.py -v

# Single test method
python -m pytest tests/test_dax_converter.py::TestDaxConverter::test_isnull_to_isblank -v
```

### Test Structure

| File | Focus |
|------|-------|
| `test_dax_converter.py` | DAX formula conversion |
| `test_dax_coverage.py` | DAX edge cases across all categories |
| `test_m_query_builder.py` | M query generation |
| `test_tmdl_generator.py` | TMDL semantic model |
| `test_visual_generator.py` | Visual container generation |
| `test_pbip_generator.py` | .pbip project structure |
| `test_feature_gaps.py` | Specific feature implementations |
| `test_infrastructure.py` | Validator, deployer, config |
| `test_extraction.py` | Qlik XML extraction |
| `test_prep_flow_parser.py` | Prep flow parsing |
| `test_non_regression.py` | Per-sample project regression |
| `test_integration.py` | End-to-end pipeline tests |
| `test_assessment.py` | Pre-migration assessment |
| ... | 44 test files total — see [README](README.md) for full list |

### Writing Tests

- Use `unittest.TestCase` (not pytest)
- Tests write to `tempfile.mkdtemp()` and clean up in `tearDown`
- No mocking of file I/O — tests use real temp directories
- Each test should be independent and self-contained

## Contribution Workflow

### 1. Create a Branch

```bash
git checkout -b feature/your-feature-name
```

### 2. Make Changes

- Follow the coding standards above
- Add tests for any new functionality
- Update documentation if adding new features

### 3. Run Tests

```bash
python -m unittest discover -s tests -v
```

All existing tests must pass. New features should include tests.

### 4. Validate Sample Migrations

```bash
# Migrate all samples and validate
python migrate.py --batch examples/Qlik_samples/ --output-dir /tmp/test_output

# Compact alias form (single entrypoint)
python migrate.py --source examples/Qlik_samples/ --out /tmp/test_output
```

### 5. Submit a Pull Request

- Provide a clear description of the change
- Reference any related issues
- Include before/after screenshots for visual changes

## Multi-Agent Development Model

This project uses a **Preceptorship Model** with 10 AI agents. When contributing, be aware of file ownership:

| Agent | Owns |
|-------|------|
| Orchestrator (Tech Lead) | `migrate.py`, `import_to_powerbi.py`, `wizard.py`, `plugins.py` |
| Extractor | `qlik_export/*.py` (except `dax_converter.py`, `m_query_builder.py`) |
| Converter | `dax_converter.py`, `m_query_builder.py`, `dax_optimizer.py` |
| Generator | `tmdl_generator.py`, `pbip_generator.py`, `visual_generator.py`, Fabric generators |
| Assessor | `assessment.py`, `server_assessment.py`, `validator.py` |
| Merger | `shared_model.py`, `merge_config.py` |
| Deployer | `deploy/` subpackage, `telemetry.py`, `gateway_config.py` |
| Tester | `tests/*.py` |
| Preceptor | Reviews all — read-only access, delegates fixes |

Each change follows **Plan → Assign → Implement → Review**. See `.github/agents/` for full definitions.

## Areas for Contribution

### High Priority

- Additional DAX conversion patterns (see GAP_ANALYSIS.md §5)
- Additional connector types for M queries
- Performance optimization for large apps

### Medium Priority

- New visual type mappings (see GAP_ANALYSIS.md §4)
- Enhanced formatting migration
- Integration tests with Fabric workspace

### Low Priority

- API documentation generation (sphinx/pdoc)
- Property-based testing for formula conversion
- PBIR schema validation against Microsoft's published schemas

## Release Process

1. Update `CHANGELOG.md` with the new version
2. Run full test suite: `python -m unittest discover -s tests -v`
3. Validate all sample migrations
4. Create a Git tag: `git tag v1.x.x`
5. Push to main: `git push origin main --tags`
