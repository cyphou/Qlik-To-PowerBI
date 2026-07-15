<!-- DOC-SHINY-BANNER -->
![Documentation](https://img.shields.io/badge/Documentation-Shiny_Style-0A66C2?style=flat-square&logo=readthedocs&logoColor=white)
![Maintained](https://img.shields.io/badge/Maintained-2026-2EA44F?style=flat-square&logo=github&logoColor=white)
![Navigation](https://img.shields.io/badge/Navigation-Quick_Access-6F42C1?style=flat-square&logo=bookstack&logoColor=white)
# Deployment Guide — Azure Fabric

Deploy migrated Power BI projects to Microsoft Fabric / Power BI Service.

---

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Authentication](#authentication)
4. [Deployment Pipeline](#deployment-pipeline)
5. [Configuration](#configuration)
6. [Gateway Configuration](#gateway-configuration)
7. [CI/CD Integration](#cicd-integration)

---

## Overview

After migration produces a `.pbip` project, you can deploy it to Microsoft Fabric or Power BI Service for organizational use. The toolkit includes deployment utilities in `powerbi_import/deploy/`.

---

## Prerequisites

- **Microsoft Fabric** or **Power BI Premium** workspace
- **Azure AD** application registration (for service principal auth)
- **Power BI REST API** permissions:
  - `Dataset.ReadWrite.All`
  - `Workspace.ReadWrite.All`
  - `Report.ReadWrite.All`

---

## Authentication

### Service Principal (recommended for CI/CD)

```python
from powerbi_import.deploy.auth import get_auth_token

token = get_auth_token(
    tenant_id="your-tenant-id",
    client_id="your-client-id",
    client_secret="your-client-secret",
)
```

### Interactive Login (development)

```python
from powerbi_import.deploy.auth import get_auth_token

token = get_auth_token(tenant_id="your-tenant-id", interactive=True)
```

---

## Deployment Pipeline

### Step 1: Migrate

```bash
python migrate.py "app.qvf" --output-dir output/my_app
```

### Step 2: Validate

```bash
python migrate.py "app.qvf" --dry-run
```

### Step 3: Deploy

```python
from powerbi_import.deploy.deployer import deploy_pbip

result = deploy_pbip(
    project_dir="output/my_app",
    workspace_id="your-workspace-guid",
    auth_token=token,
)

print(f"Dataset ID: {result.dataset_id}")
print(f"Report ID: {result.report_id}")
```

---

## Configuration

### Environment Variables

| Variable | Description |
|----------|-------------|
| `PBI_TENANT_ID` | Azure AD tenant ID |
| `PBI_CLIENT_ID` | App registration client ID |
| `PBI_CLIENT_SECRET` | App registration client secret |
| `PBI_WORKSPACE_ID` | Target workspace ID |

### Config File

Create `powerbi_import/config/deploy.json`:

```json
{
  "tenant_id": "your-tenant-id",
  "workspace_id": "your-workspace-id",
  "preferred_capacity": "your-capacity-id",
  "overwrite_existing": true
}
```

---

## Gateway Configuration

If your data sources require an on-premises data gateway:

```python
from powerbi_import.gateway_config import configure_gateway

configure_gateway(
    dataset_id=result.dataset_id,
    gateway_id="your-gateway-id",
    datasource_credentials={
        "SQL_Server": {"username": "sa", "password": "***"},
    },
    auth_token=token,
)
```

---

## CI/CD Integration

### GitHub Actions

```yaml
name: Migrate and Deploy
on:
  push:
    paths: ['qlik_exports/**']

jobs:
  migrate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - run: pip install -r requirements.txt

      - name: Migrate
        run: python migrate.py qlik_exports/app.json --json > result.json

      - name: Check result
        run: |
          python -c "
          import json, sys
          r = json.load(open('result.json'))
          if r['status'] != 'success':
              print('Migration failed:', r.get('warnings'))
              sys.exit(1)
          print(f'Tables: {r[\"tables\"]}, Measures: {r[\"measures\"]}, Visuals: {r[\"visuals\"]}')
          "

      - name: Deploy
        env:
          PBI_TENANT_ID: ${{ secrets.PBI_TENANT_ID }}
          PBI_CLIENT_ID: ${{ secrets.PBI_CLIENT_ID }}
          PBI_CLIENT_SECRET: ${{ secrets.PBI_CLIENT_SECRET }}
          PBI_WORKSPACE_ID: ${{ secrets.PBI_WORKSPACE_ID }}
        run: python -m powerbi_import.deploy.deployer --project-dir artifacts/powerbi_projects/app
```

### Azure DevOps

```yaml
trigger:
  paths:
    include:
      - qlik_exports/*

pool:
  vmImage: ubuntu-latest

steps:
  - task: UsePythonVersion@0
    inputs:
      versionSpec: '3.12'

  - script: |
      pip install -r requirements.txt
      python migrate.py qlik_exports/app.json --json > result.json
    displayName: Migrate

  - script: |
      python -m powerbi_import.deploy.deployer \
        --project-dir artifacts/powerbi_projects/app \
        --workspace-id $(PBI_WORKSPACE_ID)
    env:
      PBI_TENANT_ID: $(PBI_TENANT_ID)
      PBI_CLIENT_ID: $(PBI_CLIENT_ID)
      PBI_CLIENT_SECRET: $(PBI_CLIENT_SECRET)
    displayName: Deploy to Fabric
```

### Using `--json` for Automation

The `--json` flag outputs a structured result for programmatic consumption:

```json
{
  "status": "success",
  "input": "app.qvf",
  "output_dir": "artifacts/powerbi_projects/app",
  "tables": 12,
  "measures": 45,
  "visuals": 28,
  "pages": 6,
  "warnings": [],
  "duration_seconds": 3.2
}
```

---

## v9 Deployment Options

### Fabric-Native Output

Generate Fabric-specific artifacts instead of standard PBIP:

```bash
python migrate.py app.json --output-format fabric --output-dir output/fabric_project
```

This produces:
- **Lakehouse/** — Delta table schemas and DDL
- **Dataflow/** — Power Query M for Dataflow Gen2
- **Notebook/** — PySpark ETL notebooks (9 connector templates)
- **Pipeline/** — 3-stage orchestration (Dataflow → Notebook → Semantic Model)
- **SemanticModel/** — DirectLake model pointing to Lakehouse tables

### Bundle Deployment (Shared Model + Thin Reports)

After merging multiple apps:

```python
from powerbi_import.deploy.bundle_deployer import BundleDeployer

deployer = BundleDeployer(
    workspace_id="your-workspace-id",
    auth_token=token,
)
deployer.deploy_bundle("output/merged/")
# Deploys shared semantic model first, then thin reports
```

### Multi-Tenant Deployment

Deploy the same migration to multiple tenants with template substitution:

```python
from powerbi_import.deploy.multi_tenant import MultiTenantDeployer

deployer = MultiTenantDeployer(template_dir="output/my_app")
deployer.deploy(
    tenants=[
        {"tenant_id": "t1", "workspace_id": "w1", "server": "db1.example.com"},
        {"tenant_id": "t2", "workspace_id": "w2", "server": "db2.example.com"},
    ],
    auth_token=token,
)
```

### Blue/Green Deployment

```python
from powerbi_import.deploy.pbi_deployer import PBIDeployer

deployer = PBIDeployer(workspace_id="ws-id", auth_token=token)
deployer.deploy_blue_green(
    project_dir="output/my_app",
    refresh_after_deploy=True,
)
```

Use this to gate deployments, aggregate metrics, or feed dashboards.

