# Workspace Blueprint for Qlik-to-Power BI Migration

**Version:** 1.0  
**Effective Date:** 2026-06-26  
**Applies To:** All migration workspaces using the automated pipeline

---

## 1. Workspace Structure and Conventions

### 1.1 Directory Layout (Standard)

```
workspace/
├── source/                        # Source artifacts (QVF files)
│   ├── portfolio.csv             # App inventory + profile selection
│   └── qvf/
│       ├── app_1.qvf
│       ├── app_2.qvf
│       └── ...
│
├── manifests/                     # Migration control files
│   ├── portfolio_from_repo.csv    # Auto-generated inventory
│   ├── wave_[Wave-ID]_manifest.json
│   ├── wave_[Wave-ID]_manifest_ready.json
│   └── wave_[Wave-ID]_manifest_ready_report.json
│
├── output/
│   ├── [App-ID]_pbip/            # Power BI project output
│   │   ├── .gitignore
│   │   ├── .platform             # Platform config
│   │   ├── model/
│   │   ├── report/
│   │   └── semantic/
│   │
│   ├── [App-ID]_artifacts/       # Diagnostic/evidence artifacts
│   │   ├── extraction_report.json
│   │   ├── generation_report.json
│   │   ├── fidelity_report.json
│   │   ├── lineage_manifest.json
│   │   ├── image_inventory.json
│   │   ├── m_query_versions.json
│   │   ├── security_audit.json
│   │   └── images/
│   │       ├── image_1.png
│   │       └── ...
│   │
│   └── migration_summary.json     # Wave-level result summary
│
└── logs/
    ├── wave_[ID]_[timestamp].log
    └── error_reports/
        └── [App-ID]_errors.log
```

### 1.2 Manifest Directory Structure

**Location:** `workspace/manifests/`

**File Naming Convention:**
- Portfolio inventory: `portfolio_[source].csv`
- Wave manifest (raw): `wave_Wave-[ID]_manifest.json`
- Wave manifest (ready): `wave_Wave-[ID]_manifest_ready.json`
- Wave report: `wave_Wave-[ID]_manifest_ready_report.json`

**Example:**
```
wave_Wave-0_manifest.json          # Raw manifest with all entries
wave_Wave-0_manifest_ready.json     # Filtered (valid QVF only, paths normalized)
wave_Wave-0_manifest_ready_report.json  # Skip report (why entries filtered)
```

---

## 2. App Naming Conventions

### 2.1 QVF File Names

**Format:** `{AppName}.qvf`
- Use original Qlik app name (spaces allowed, max 255 chars)
- Example: `Sales Analysis.qvf`, `HR Dashboard.qvf`

### 2.2 Output Directory Names

**Format:** `{App-ID}_pbip`
- `App-ID` = app name with spaces → underscores, lowercase, max 80 chars
- Example: `Sales_Analysis_pbip`, `HR_Dashboard_pbip`

### 2.3 Artifact Directory Names

**Format:** `{App-ID}_artifacts`
- Same `App-ID` as output directory for consistency
- Contains extraction/generation reports, images, queries, lineage

**Example:**
```
sales_analysis_pbip/          # Power BI project
sales_analysis_artifacts/     # Supporting evidence + diagnostics
```

---

## 3. Manifest Structure and Validation Rules

### 3.1 Wave Manifest Schema

**Raw Manifest:** `wave_Wave-[ID]_manifest.json`

```json
{
  "wave_id": "Wave-0",
  "created_at": "2026-06-26T10:00:00Z",
  "profile": "strict",
  "entries": [
    {
      "app_id": "sales_analysis",
      "source": "examples/qlik/sample_sales.qvf",
      "profile": "strict",
      "output_dir": "output/sales_analysis_pbip",
      "skip_extraction": false
    }
  ]
}
```

**Ready Manifest:** `wave_Wave-[ID]_manifest_ready.json`

- Paths normalized (relative to manifest directory or repo root)
- Invalid QVF files filtered out (not valid ZIP containers)
- Only entries with valid, accessible source files included

**Skip Report:** `wave_Wave-[ID]_manifest_ready_report.json`

```json
{
  "total_entries": 3,
  "valid_entries": 1,
  "skipped_entries": 2,
  "skipped": [
    {
      "app_id": "invalid_qvf",
      "reason": "not_valid_zip",
      "details": "File exists but is not a valid QVF container"
    },
    {
      "app_id": "missing_app",
      "reason": "file_not_found",
      "details": "Path does not exist relative to manifest or repo root"
    }
  ]
}
```

### 3.2 Validation Rules

**QVF File Validation:**
- [ ] File exists at source path
- [ ] File is a valid ZIP container (can be opened with zipfile.ZipFile)
- [ ] File contains Qlik app structure (manifest.json or workbook.json)

**Manifest Entry Validation:**
- [ ] `app_id` is unique within wave
- [ ] `source` path resolves (relative to manifest directory OR repo root)
- [ ] `profile` is one of: `fast`, `strict`, `regulated`
- [ ] `output_dir` is writable

**Path Resolution Order:**
1. Try as absolute path
2. Try relative to manifest directory
3. Try relative to repo root (via `--repo-root` flag)

---

## 4. Profile Definitions

### 4.1 Fast Profile
- **Best For:** Quick prototype, proof of concept
- **Extraction:** Skip secondary load script analysis
- **Generation:** Basic TMDL, no optimization
- **Validation:** Structural check only
- **Duration:** 30–60 seconds per app

### 4.2 Strict Profile (Default)
- **Best For:** Production migration, high-fidelity requirement
- **Extraction:** Full Qlik script + expression analysis
- **Generation:** Optimized TMDL, DAX recipes, calculated columns
- **Validation:** Cross-platform value comparison, fidelity >85%
- **Duration:** 2–5 minutes per app

### 4.3 Regulated Profile
- **Best For:** Healthcare, finance, compliance-required workloads
- **Extraction:** Full + security role extraction, PII detection
- **Generation:** RLS/OLS mapping, audit trail, lineage manifest
- **Validation:** Security audit, compliance gate, fidelity >90%
- **Duration:** 5–15 minutes per app

**Profile Selection:**
- Default: `strict`
- Override per-wave: `--profile fast|strict|regulated` in manifest build
- Override per-app: `profile` field in manifest entry

---

## 5. Migration Execution Workflow

### 5.1 Standard Workflow (5 Steps)

```
Step 1: Inventory
  └─ Create portfolio.csv (app names, paths, profiles)
     Command: Manual or tool (build_wave_manifests.py)

Step 2: Generate Manifests
  └─ Build wave manifests from portfolio
     Command: python scripts/build_wave_manifests.py --input portfolio.csv
     Output: wave_Wave-0_manifest.json (raw + ready + report)

Step 3: Validate Readiness
  └─ Inspect skip report, fix invalid entries
     Command: Review wave_Wave-0_manifest_ready_report.json
     Decision: Proceed if valid entries >0

Step 4: Execute Wave
  └─ Run migration for all valid entries
     Command: python migrate.py --migration-manifest wave_Wave-0_manifest_ready.json
     Options: --continue-on-error (skip failures), --profile strict

Step 5: Validate Results
  └─ Inspect migration summary + per-app reports
     Output: output/migration_summary.json + per-app artifacts
     Decision: Deploy to Power BI or remediate + rerun
```

### 5.2 Remediation Workflow (On Failures)

```
Detect Failure
  └─ Review error log: logs/error_reports/[App-ID]_errors.log

Classify Failure
  ├─ Extraction: Malformed QVF, missing datasource
  ├─ Generation: Unsupported Qlik function, DAX conversion error
  ├─ Validation: Fidelity check failed, security audit failed
  └─ Deployment: Power BI API error, permission denied

Remediate
  ├─ Extraction: Fix QVF (re-extract from source)
  ├─ Generation: Apply fix (--repair-strategies, --self-heal-v3)
  ├─ Validation: Increase threshold or exclude problematic object
  └─ Deployment: Check credentials, workload capacity

Resume
  └─ python migrate.py --migration-manifest wave_Wave-0_manifest_ready.json
                       --resume-from checkpoint.json
                       (skips completed, retries failed)
```

---

## 6. Artifact Organization and Naming

### 6.1 Extraction Artifacts

**Location:** `output/[App-ID]_artifacts/`

```
extraction_report.json          # QVF parse summary
  - datasources (count, names)
  - tables (count, columns)
  - measures, dimensions, sheets
  - variables, bookmarks, master items
  - extraction duration (seconds)

11_json_files/ (intermediate)
  ├─ app_metadata.json
  ├─ datasources.json
  ├─ dimensions.json
  ├─ measures.json
  ├─ visualizations.json
  ├─ sheets.json
  ├─ variables.json
  ├─ loadscript.json
  ├─ associations.json
  ├─ bookmarks.json
  └─ master_items.json
```

### 6.2 Generation Artifacts

```
generation_report.json          # TMDL output summary
  - tables, columns, measures, relationships
  - calculated columns (count, formulas)
  - visuals (count, types)
  - generation duration (seconds)
  - generation success flag

fidelity_report.json            # Validation results
  - fidelity_score (0–100%)
  - measure_fidelity (per measure, avg %)
  - cross_platform_comparison (Qlik vs. PBI value samples)
  - validation duration (seconds)

lineage_manifest.json           # End-to-end traceability
  - field_id → m_query_step → dax_expression → visual
  - ownership, approval_status, last_modified
```

### 6.3 Evidence Artifacts

```
image_inventory.json            # Extracted images
  - image_id, size (bytes), format
  - usage (page/visual), origin
  - reference to images/ directory

m_query_versions.json           # M query deduplication
  - query_hash → count (occurrences)
  - consolidation_candidates (similar hashes)

security_audit.json             # RLS/OLS/Sec Access mapping
  - rls_rules_found (count)
  - section_access_roles (list)
  - data_masking_rules (count)
  - unmapped_roles (review required)

artifact_manifest.json          # Governance + lineage
  - app_id, created_at, created_by
  - data_classification (public/internal/confidential)
  - retention_policy (keep_days)
  - audit_trail (who/what/when)
```

---

## 7. Definition of "Healthy" Workspace

A migration workspace is **healthy** when:

- ✅ All source QVF files exist and validate as ZIP containers
- ✅ Manifest files follow naming convention and pass schema validation
- ✅ Output directories follow naming convention (lowercase, underscores, max 80 chars)
- ✅ Per-app artifacts present: extraction, generation, fidelity reports
- ✅ Fidelity >85% for all apps (or documented exception)
- ✅ Security audit completed for regulated apps
- ✅ Image inventory and M query deduplication reports available
- ✅ Zero unexpected files in output/ (only `.pbip` + `_artifacts` directories)
- ✅ Git tracking: `.pbip/` committed, `artifacts/` and `output/` in .gitignore
- ✅ Logs directory cleaned after successful wave (>7 days old)

**Health Check Command:**
```bash
python scripts/workspace_health_check.py --workspace-root .
```

---

## 8. Template Repository Structure

**For New Programs:** Copy this structure as starting point.

```
new_program/
├── source/
│   └── README.md (instructions: copy QVF files here)
├── manifests/
│   └── README.md (instructions: run build_wave_manifests.py)
├── output/
│   └── .gitkeep
├── logs/
│   └── .gitkeep
├── portfolio.csv (example)
└── README.md (program-specific documentation)
```

---

## 9. Documentation and Runbooks

| Document | Location | Purpose |
|---|---|---|
| CLI Reference | `docs/guides/CLI_REFERENCE.md` | Command usage + flags |
| Migration Guide | `docs/guides/MIGRATION_GUIDE.md` | Step-by-step walkthrough |
| Troubleshooting | `docs/guides/TROUBLESHOOTING.md` | Common errors + fixes |
| Security Audit | `docs/guides/SECURITY_AUDIT_CHECKLIST.md` | RLS/OLS review process |
| Quickstart | `docs/guides/NEW_PROGRAM_QUICKSTART.md` | 5-step onboarding |

---

## 10. Governance and Compliance

### 10.1 Data Classification

- **Public:** No PII, can be shared externally
- **Internal:** Organizational data, shared within team
- **Confidential:** Contains PII or business-sensitive data, restricted access

**Requirement:** Classify every app in manifest; default to `internal`.

### 10.2 Audit Trail

Every migration run generates JSONL audit log:
```json
{"timestamp": "2026-06-26T10:00:00Z", "event": "extraction_start", "app_id": "sales_analysis"}
{"timestamp": "2026-06-26T10:01:30Z", "event": "extraction_complete", "app_id": "sales_analysis", "duration_sec": 90}
{"timestamp": "2026-06-26T10:05:00Z", "event": "generation_complete", "app_id": "sales_analysis", "fidelity": 92.5}
```

**Storage:** `logs/wave_[ID]_[timestamp].log` (JSONL format, retained 30 days)

### 10.3 Sign-Off Procedure

Before production deployment:
- [ ] Security audit completed (RLS/OLS reviewed)
- [ ] Fidelity >85% (or exception documented)
- [ ] Image inventory reviewed + approved
- [ ] M query consolidation candidates reviewed
- [ ] Lineage manifest spot-checked (sample fields traced)
- [ ] Post-cutover monitoring configured
- [ ] Rollback plan documented

---

## 11. Revision History

| Version | Date | Changes |
|---|---|---|
| 1.0 | 2026-06-26 | Initial blueprint, 5-step workflow, health check definition |

---

## 12. Related Documents

- [CLI Reference](CLI_REFERENCE.md)
- [Migration Guide](MIGRATION_GUIDE.md)
- [New Program Quickstart](NEW_PROGRAM_QUICKSTART.md)
- [Security Audit Checklist](SECURITY_AUDIT_CHECKLIST.md)
- [Wave Execution Plan Template](../templates/WAVE_EXECUTION_PLAN_TEMPLATE.md)
- [Qlik App Portfolio Template](../templates/QLIK_APP_PORTFOLIO_TEMPLATE.csv)

---

**Approved By:** Migration Program Lead  
**Effective Date:** 2026-06-26  
**Next Review:** 2026-08-26 (after first production wave)
