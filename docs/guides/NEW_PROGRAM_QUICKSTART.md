# New Program Quickstart: 5-Step Onboarding for Qlik-to-Power BI Migration

**Duration:** 1 hour (first time), 15 minutes (repeat)  
**Audience:** Migration analysts, team leads  
**Prerequisite:** Access to Qlik QVF source files, Power BI workspace  

---

## Overview

This guide walks you through your first Qlik-to-Power BI migration using the automated pipeline. Follow 5 steps to go from source QVF files → production-ready Power BI projects.

**Quick Links:**
- [Workspace Blueprint](WORKSPACE_BLUEPRINT.md) — Directory layout, naming conventions
- [CLI Reference](CLI_REFERENCE.md) — All command flags and options
- [Troubleshooting](TROUBLESHOOTING.md) — Common errors and fixes
- [Connection Map Template](../templates/CONNECTION_MAP_TEMPLATE.json) — Datasource mapping

---

## Step 1: Inventory Your Qlik Apps (10 minutes)

### 1.1 Create Portfolio CSV

Create a file `source/portfolio.csv` listing all Qlik apps you want to migrate:

```csv
app_name,source_path,profile,notes
Sales Analysis,qvf/sales_analysis.qvf,strict,Production app
HR Dashboard,qvf/hr_dashboard.qvf,fast,Quick prototype
Customer 360,qvf/customer_360.qvf,regulated,Contains PII
```

**CSV Columns:**
- `app_name`: Human-readable app name (spaces allowed)
- `source_path`: Path to QVF file (relative to `source/`)
- `profile`: Migration profile (`fast`, `strict`, `regulated`)
- `notes`: Optional comments (use case, special requirements)

**Profile Guide:**
- **`fast`** — Quick prototype, limited optimization (30–60 sec per app)
- **`strict`** — Production migration, high fidelity (2–5 min per app) ← **recommended**
- **`regulated`** — Compliance-required (healthcare, finance), security audit (5–15 min per app)

### 1.2 Validate Paths

```bash
# Check that QVF files exist
Get-Item source/qvf/*.qvf
```

**Expected Output:**
```
Mode    LastWriteTime        Length Name
----    -----------------    ------ ----
-a---   2026-06-26 10:00:00  2.5MB sales_analysis.qvf
```

**Troubleshooting:**
- File not found? → Copy QVF to `source/qvf/` directory
- Wrong path? → Update CSV with correct relative path

---

## Step 2: Generate Migration Manifests (5 minutes)

### 2.1 Build Wave Manifests

```bash
cd C:\GitHub Project\QlikToPowerBI

# Activate venv (first time only)
.\venv\Scripts\Activate.ps1

# Generate manifests from portfolio CSV
python scripts/build_wave_manifests.py `
  --input source/portfolio.csv `
  --output-dir artifacts/manifests `
  --make-ready
```

**What This Does:**
- Reads `portfolio.csv`
- Creates wave manifests (raw + ready)
- Validates QVF files (checks they're valid ZIP containers)
- Normalizes file paths
- Generates skip report (if any entries are invalid)

### 2.2 Inspect Results

```bash
# List generated manifests
Get-Item artifacts/manifests/wave*.json

# View skip report (if failures occurred)
Get-Content artifacts/manifests/wave_Wave-0_manifest_ready_report.json | ConvertFrom-Json | Format-Table
```

**Expected Output (skip report):**
```json
{
  "total_entries": 3,
  "valid_entries": 3,
  "skipped_entries": 0,
  "skipped": []
}
```

**If Entries Were Skipped:**
- Check `wave_Wave-0_manifest_ready_report.json` for reasons
- Possible reasons: `not_valid_zip`, `file_not_found`
- Fix path or QVF file, then regenerate

### 2.3 Review Manifest Structure

```bash
# Show manifest content (first 50 lines)
Get-Content artifacts/manifests/wave_Wave-0_manifest_ready.json -Head 50
```

**Expected Structure:**
```json
{
  "wave_id": "Wave-0",
  "created_at": "2026-06-26T...",
  "profile": "strict",
  "entries": [
    {
      "app_id": "sales_analysis",
      "source": "qvf/sales_analysis.qvf",
      "profile": "strict",
      "output_dir": "output/sales_analysis_pbip",
      "skip_extraction": false
    }
  ]
}
```

**✅ All Good?** → Move to Step 3

---

## Step 3: Execute Migration Wave (3–15 minutes depending on app size)

### 3.1 Run Migration

```bash
# Execute ready manifest
python migrate.py `
  --migration-manifest artifacts/manifests/wave_Wave-0_manifest_ready.json `
  --profile strict `
  --continue-on-error
```

**Flags Explained:**
- `--migration-manifest` — Input manifest file (use the `*_ready.json` version)
- `--profile strict` — Use strict profile (high fidelity, full optimization)
- `--continue-on-error` — Skip failures, continue with next app

### 3.2 Monitor Progress

Watch console output; you'll see:
```
[INFO] Starting migration wave Wave-0
[INFO] Processing 3 apps...
[INFO] App 1/3: Extracting sales_analysis...
[INFO] Extraction complete (90 sec)
[INFO] Generating TMDL model...
[INFO] Generation complete (120 sec)
[INFO] Validating fidelity...
[INFO] Fidelity score: 92.5%
[SUCCESS] sales_analysis complete
[INFO] App 2/3: Extracting hr_dashboard...
...
```

### 3.3 Check Results

```bash
# List output directories
Get-Item output/*/

# Show per-app artifacts
Get-Item output/sales_analysis_artifacts/
```

**Expected Directory Structure:**
```
output/
├── sales_analysis_pbip/          # Power BI project
├── sales_analysis_artifacts/     # Diagnostic reports
│   ├── extraction_report.json
│   ├── generation_report.json
│   ├── fidelity_report.json
│   ├── lineage_manifest.json
│   └── images/
├── hr_dashboard_pbip/
├── hr_dashboard_artifacts/
└── migration_summary.json        # Wave summary
```

### 3.4 Review Fidelity Scores

```bash
# Show migration summary
Get-Content output/migration_summary.json | ConvertFrom-Json | Format-Table
```

**Fidelity Score Guide:**
| Score | Meaning | Action |
|-------|---------|--------|
| ≥90% | Excellent | Ready to deploy |
| 85–89% | Good | Review artifacts, minor fixes may be needed |
| 70–84% | Acceptable | Requires remediation or manual adjustment |
| <70% | Poor | Do not deploy; investigate + remediate |

**Default Requirement:** ≥85% for production

---

## Step 4: Validate and Review (10–20 minutes)

### 4.1 Check Fidelity Reports

```bash
# Open fidelity report in text editor
code output/sales_analysis_artifacts/fidelity_report.json
```

**Key Fields to Review:**
- `fidelity_score` — Overall percentage match
- `measure_fidelity` — Per-measure accuracy
- `cross_platform_comparison` — Sample values (Qlik vs. Power BI)

### 4.2 Spot-Check Lineage

```bash
# View field-to-visual traceability
Get-Content output/sales_analysis_artifacts/lineage_manifest.json | ConvertFrom-Json | Format-List
```

**Look For:**
- Every visual has mapped datasource
- Measures trace back to Qlik expressions
- Calculated columns have DAX definitions

### 4.3 Review Images (if embedded)

```bash
# List extracted images
Get-Item output/sales_analysis_artifacts/images/

# Check image inventory
Get-Content output/sales_analysis_artifacts/image_inventory.json | ConvertFrom-Json | Format-Table
```

### 4.4 Security Review (for regulated profile)

```bash
# Check security audit
Get-Content output/sales_analysis_artifacts/security_audit.json | ConvertFrom-Json
```

**For Regulated Apps, Verify:**
- [ ] RLS roles mapped correctly
- [ ] No unmapped roles
- [ ] PII detection completed
- [ ] Data classification assigned

---

## Step 5: Deploy to Power BI (5–10 minutes)

### 5.1 Open Power BI Project Locally

```bash
# Open .pbip project in Power BI Desktop
# (Requires Power BI Desktop June 2024+)

$project = "output/sales_analysis_pbip"
start $project
```

### 5.2 Validate in Power BI Desktop

Checklist:
- [ ] All tables load (no red error badges)
- [ ] Measures calculate correctly
- [ ] Relationships are correct (check Diagram view)
- [ ] Visuals render without errors
- [ ] Date hierarchy exists (auto-generated calendar)

### 5.3 Publish to Power BI Service

```bash
# Deploy to Power BI workspace
python migrate.py output/sales_analysis_pbip `
  --deploy WORKSPACE_ID `
  --deploy-refresh
```

**To Get `WORKSPACE_ID`:**
1. Go to Power BI Service: `https://app.powerbi.com`
2. Select workspace
3. Copy ID from URL: `workspaces/{WORKSPACE_ID}`

### 5.4 Configure Refresh Schedule (if needed)

In Power BI Service:
1. Go to Settings → Datasets
2. Find your semantic model
3. Set refresh schedule (e.g., 8 AM daily)
4. Save credentials if prompted

---

## Common Issues and Quick Fixes

### Issue: "File not found" error

**Cause:** QVF path incorrect or file missing

**Fix:**
```bash
# Verify file exists
Test-Path source/qvf/my_app.qvf

# Update CSV with correct path
# Regenerate manifests
python scripts/build_wave_manifests.py --input source/portfolio.csv --make-ready
```

### Issue: "Not a valid QVF" error

**Cause:** File is corrupted or not actually a QVF

**Fix:**
```bash
# Check if file is a valid ZIP
$file = "source/qvf/my_app.qvf"
[System.Reflection.Assembly]::LoadWithPartialName('System.IO.Compression') | Out-Null
try {
  $zip = [System.IO.Compression.ZipFile]::OpenRead($file)
  $zip.Dispose()
  Write-Host "Valid ZIP"
} catch {
  Write-Host "Not a valid ZIP - may be corrupted"
}
```

### Issue: Fidelity <85%

**Cause:** Qlik features not fully supported (dynamic aggregation, conditional expressions, etc.)

**Fix:**
```bash
# Review error log
Get-Content logs/error_reports/my_app_errors.log

# Check fidelity report for specific measure failures
Get-Content output/my_app_artifacts/fidelity_report.json | ConvertFrom-Json | Format-List

# Rerun with self-healing
python migrate.py app.qvf --self-heal-v3 --repair-strategies

# Manual fix: Update DAX expression in Power BI Desktop
```

### Issue: "Timeout" or "Connection refused"

**Cause:** Large app taking too long, or datasource unreachable

**Fix:**
```bash
# For large apps, increase timeout
python migrate.py app.qvf --timeout 600  # 10 minutes

# Test datasource connectivity
# (Add connection test command here)

# Rerun with --continue-on-error to skip this app
python migrate.py --migration-manifest wave.json --continue-on-error
```

---

## Next Steps After First Migration

### ✅ Success Path
1. **Review Results** — Check fidelity reports, spot-check visuals
2. **Deploy to Test** — Push to Power BI test workspace, have users validate
3. **Migrate Remaining Apps** — Generate new manifest with additional apps
4. **Scale Up** — Use Phase 2 batch runner for 10+ app migrations

### 🔧 Remediation Path
1. **Document Issues** — Log any formulas/features not converted
2. **Apply Fixes** — Use `--repair-strategies`, `--self-heal-v3` flags
3. **Rerun Migration** — Re-execute with `--resume-from checkpoint.json`
4. **Manual Adjustment** — Final tweaks in Power BI Desktop

---

## Reference Materials

| Resource | Location | Purpose |
|----------|----------|---------|
| Workspace Blueprint | `docs/guides/WORKSPACE_BLUEPRINT.md` | Directory layout, conventions |
| CLI Reference | `docs/guides/CLI_REFERENCE.md` | All command flags + examples |
| Troubleshooting | `docs/guides/TROUBLESHOOTING.md` | Common errors + solutions |
| Connection Map | `docs/templates/CONNECTION_MAP_TEMPLATE.json` | Datasource mapping |
| Governance Config | `docs/templates/GOVERNANCE_CONFIG_TEMPLATE.json` | Compliance rules |
| Migration Guide | `docs/guides/MIGRATION_GUIDE.md` | Deep dive on each phase |

---

## Getting Help

| Question | Contact |
|----------|---------|
| Technical issue? | Slack: #qlik-to-pbi or GitHub Issues |
| Fidelity concerns? | Escalate to data_steward@company.com |
| Security/compliance? | Email: compliance_team@company.com |
| Permission denied? | Contact workspace_admin@company.com |

---

## Success Checklist

- [ ] Portfolio CSV created with ≥1 app
- [ ] Manifests generated with all entries valid
- [ ] Migration completed with ≥85% fidelity
- [ ] Artifacts reviewed (lineage, images, security)
- [ ] Power BI project opens without errors
- [ ] Refreshed in Power BI Service successfully
- [ ] Users can access and view reports

**✅ All checked?** Congratulations! You've completed your first migration. Move on to Phase 2 (batch migrations) or Phase 3 (security governance) as needed.

---

**Document Version:** 1.0  
**Last Updated:** 2026-06-26  
**Next Review:** 2026-08-26 (after first production wave)
