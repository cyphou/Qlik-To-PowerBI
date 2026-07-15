# Qlik to Power BI Migration

![Qlik Sense](https://img.shields.io/badge/Qlik_Sense-009848?style=for-the-badge&logo=qlik&logoColor=white)
![Arrow](https://img.shields.io/badge/%E2%86%92-grey?style=for-the-badge)
![Power BI](https://img.shields.io/badge/Power_BI-F2C811?style=for-the-badge&logo=powerbi&logoColor=black)

![Python](https://img.shields.io/badge/python-3.12%2B-3776AB?style=flat-square&logo=python&logoColor=white)
![Version](https://img.shields.io/badge/version-12.0.0-blue?style=flat-square)
![License](https://img.shields.io/badge/license-MIT-yellow?style=flat-square)

Migrate Qlik Sense applications to Power BI `.pbip` projects with one automatic command.

## Installation

Create a virtual environment and install the development dependencies:

```bash
python -m venv venv
venv\Scripts\activate
pip install -e ".[dev]"
```

## Quick Start

Migrate one Qlik application:

```bash
python migrate.py app.qvf
```

The same command accepts a folder and migrates every supported application:

```bash
python migrate.py ./exports
```

Use `--out` only when the generated project must be written elsewhere:

```bash
python migrate.py app.qvf --out ./output
```

Input routing, Binary model discovery, many-to-many bridge generation,
validation, repair, and Power BI Desktop openability checks are automatic.

## Output

A successful run generates a Power BI project:

```text
artifacts/powerbi_projects/<AppName>/
  <AppName>.pbip
  <AppName>.SemanticModel/
  <AppName>.Report/
```

Open the `.pbip` directly in Power BI Desktop (Developer Mode).

## What Is Covered

- Qlik expressions to DAX conversion
- Qlik load script to Power Query M conversion
- Visual mapping to PBIR report layout
- TMDL semantic model generation
- Validation, QA, and deployment workflows

## Documentation

Start with the documentation hub:

- [docs/README.md](docs/README.md)

Most used guides:

- [Quick Start](docs/guides/QUICK_START.md)
- [CLI Reference](docs/guides/CLI_REFERENCE.md)
- [Migration Guide](docs/guides/MIGRATION_GUIDE.md)
- [Deployment Guide](docs/guides/DEPLOYMENT_GUIDE.md)
- [FAQ](docs/FAQ.md)

## Testing

The repository includes more than 2,000 automated tests covering extraction,
conversion, generation, validation, and Power BI Desktop openability.

```bash
# Run tests
python -m pytest tests/ -q

# Focused CLI tests
python -m pytest tests/test_new_cli_flags.py tests/test_simple_mode.py -q
```
