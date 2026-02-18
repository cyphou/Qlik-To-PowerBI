# Migration Qlik → Power BI

Automated migration toolkit that converts Qlik Sense applications into
**PBI Projects** (`.pbip` / TMDL) — the modern, Git-friendly Power BI format.

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Format](https://img.shields.io/badge/output-PBI%20Project%20%2F%20TMDL-brightgreen)

---

## Quick Start

```bash
# 1. Install
python -m venv venv && venv\Scripts\activate
pip install -e ".[dev]"          # core + test deps
# pip install -e ".[all]"       # adds azure-identity for Fabric deployment

# 2. Migrate a QVF file → PBI Project (TMDL)
python tools/migration/migrate_qvf.py "MonApp.qvf" --create-pbi-project

# 3. Open the generated .pbip in Power BI Desktop (Developer Mode)
```

> **Tip:** Enable *Developer Mode* in Power BI Desktop → Options → Preview features.

---

## What Gets Generated

```
output/
└── MonApp/
    ├── MonApp.pbip                          # Open this in PBI Desktop
    ├── MonApp.SemanticModel/
    │   ├── definition.bism
    │   └── definition/
    │       ├── database.tmdl
    │       ├── model.tmdl
    │       ├── tables/
    │       │   ├── Sales.tmdl
    │       │   └── Customers.tmdl
    │       ├── relationships.tmdl
    │       └── expressions.tmdl
    └── MonApp.Report/
        ├── definition.pbir
        └── report.json
```

All files are plain text → **fully Git-trackable and CI/CD-friendly**.

---

## Project Structure

```
├── src/fabric_api/           # Core library
│   ├── tmdl_generator.py     # PBI Project / TMDL output
│   ├── qlik_migrator.py      # QlikApp → Power BI converter
│   ├── qlik_model_converter.py
│   ├── qlik_script_converter.py
│   ├── qvf_extractor.py      # .qvf ZIP reader
│   ├── config/               # Settings (pydantic-settings + env fallback)
│   ├── auth.py               # Azure auth (lazy-loaded)
│   ├── client.py             # Fabric REST client
│   ├── deployer.py           # Fabric deployment
│   ├── validator.py          # Artifact validation
│   └── utils.py              # Reports & caching
│
├── tools/
│   ├── migration/            # CLI migration scripts
│   ├── analysis/             # Diagnostic tools
│   └── testing/              # Integration test suites
│
├── examples/powerbi/         # Usage examples
├── tests/                    # pytest test suite
├── docs/                     # Guides, technical docs, reports
├── pyproject.toml            # Package metadata & deps
└── requirements.txt          # Pinned dependencies
```

---

## Features

### Migration Coverage (95 % automated)

| Qlik Component | Power BI Equivalent | Tool |
|---|---|---|
| Applications (.qvf) | Scripts ETL → Power Query M | `migrate_qvf.py` |
| Data models | Tables / relationships / hierarchies → TMDL | `migrate_qvf.py` |
| Visualizations (9 types) | PBI visuals (report.json) | `migrate_qvf.py` |
| Load scripts | 60+ functions → Power Query M | `migrate_qlik_scripts.py` |
| Variables | What-If parameters | `migrate_qlik_variables.py` |
| Section Access | Row Level Security (RLS) | `migrate_section_access.py` |
| Set Analysis | DAX CALCULATE | `migrate_set_analysis.py` |
| Bookmarks | Power BI bookmarks | `migrate_bookmarks.py` |
| Master Items | DAX measures / dimensions | `migrate_master_items.py` |
| Themes | JSON colour palette | `migrate_theme.py` |
| Stories | PowerPoint presentations | `migrate_stories.py` |
| GeoAnalytics | Azure Maps | `migrate_geoanalytics.py` |
| NPrinting | Paginated Reports | `migrate_npprinting.py` |
| …and 10 more modules | | see `tools/migration/` |

### Analysis Tools

| Tool | Usage |
|---|---|
| `diagnose_qvf.py` | `python tools/analysis/diagnose_qvf.py file.qvf` |
| `generate_pq_from_sources.py` | `python tools/analysis/generate_pq_from_sources.py folder` |

---

## Installation

### Prerequisites

- Python 3.10+
- Power BI Desktop (Developer Mode enabled)

### Install as editable package

```bash
python -m venv venv
venv\Scripts\activate
pip install -e ".[dev]"        # core + pytest
# Optional: pip install -e ".[all]"   # + azure-identity
```

Or from `requirements.txt`:

```bash
pip install -r requirements.txt
```

---

## Testing

```bash
# All tests
pytest

# TMDL generator tests only
pytest tests/test_tmdl_generator.py -v

# With coverage
pytest --cov=fabric_api tests/
```

---

## Programmatic Usage

```python
from fabric_api import TMDLGenerator

gen = TMDLGenerator()
gen.create_pbi_project(
    output_dir="output/my_project",
    report_name="Sales Dashboard",
    bim_model=my_bim_dict,             # optional
    power_query_script=pq_string,      # optional
    visualizations=viz_list,           # optional
)
```

Or from a migration output folder:

```python
from fabric_api import create_pbi_project_from_migration
from pathlib import Path

create_pbi_project_from_migration(
    migration_output_dir=Path("output/migrated/app"),
    project_output_dir=Path("output/pbi_project"),
    report_name="Sales Dashboard",
)
```

---

## Documentation

| Guide | Description |
|---|---|
| [PRET_A_LEMPLOI.md](docs/guides/PRET_A_LEMPLOI.md) | 3-command quick start |
| [QUICK_START_HYBRIDE.md](docs/guides/QUICK_START_HYBRIDE.md) | QVF migration walkthrough |
| [GUIDE_POWER_BI_IMPORT.md](docs/guides/GUIDE_POWER_BI_IMPORT.md) | Detailed PBI Desktop import |
| [QLIK_OBJECTS_COVERAGE.md](docs/technical/QLIK_OBJECTS_COVERAGE.md) | 72 Qlik objects — 100 % coverage |
| [PLAN_DE_TEST.md](docs/technical/PLAN_DE_TEST.md) | Test strategy |

Historical phase-completion notes are in `docs/archive/`.

---

## References

- [Power BI Developer Mode](https://learn.microsoft.com/power-bi/developer/projects/projects-overview)
- [TMDL Overview](https://learn.microsoft.com/analysis-services/tmdl/tmdl-overview)
- [Microsoft Fabric REST API](https://learn.microsoft.com/rest/api/fabric/)
- [DAX Guide](https://dax.guide/)
- [Qlik Engine API](https://help.qlik.com/en-US/sense-developer/APIs-and-SDKs.htm)

---

MIT License
