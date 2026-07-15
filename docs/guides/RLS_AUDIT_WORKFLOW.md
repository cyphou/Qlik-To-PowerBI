<!-- DOC-SHINY-BANNER -->
![Documentation](https://img.shields.io/badge/Documentation-Shiny_Style-0A66C2?style=flat-square&logo=readthedocs&logoColor=white)
![Maintained](https://img.shields.io/badge/Maintained-2026-2EA44F?style=flat-square&logo=github&logoColor=white)
![Navigation](https://img.shields.io/badge/Navigation-Quick_Access-6F42C1?style=flat-square&logo=bookstack&logoColor=white)
# RLS Audit Workflow

This workflow defines how Row-Level Security evidence is reviewed and approved for migration waves using `strict` and `regulated` profiles.

## Purpose

Use this workflow to ensure Power BI RLS generated from Qlik Section Access is reviewed before promotion beyond development.

This guide is intended for:

- Migration leads
- Security reviewers
- Business owners
- Release managers

---

## When RLS Audit Is Required

RLS audit is required when any of the following are true:

1. The migration profile is `strict`.
2. The migration profile is `regulated`.
3. The source Qlik app contains Section Access or equivalent access reduction logic.
4. The target Power BI dataset is intended for shared or production use.

RLS audit is optional by default for `fast` profile apps unless the wave owner upgrades the app to stricter controls.

---

## Required Evidence Per App

Each audited app must have the following evidence collected:

1. `security/security_extract.csv`
2. Gate JSON for the target environment
3. Migration report JSON with fidelity score
4. Reviewer notes covering role mapping and expected audience
5. Final sign-off record

---

## Review Steps

### Step 1: Confirm Scope

Validate:

1. App ID and app name
2. Migration profile
3. Business owner
4. Target environment

### Step 2: Review Source Security

Review the source app for:

1. Section Access usage
2. Reduction fields
3. Omitted fields or hidden content logic
4. Named user groups, roles, or exceptions

### Step 3: Review Generated Security Artifact

Open `security/security_extract.csv` and verify:

1. Expected roles are present
2. Expected tables are represented
3. Filter expressions are populated when required
4. No unexpected broad-access role is introduced

### Step 4: Compare Business Intent

Confirm with the business owner:

1. Which audiences should see which rows
2. Whether any role exceptions are intentional
3. Whether Power BI behavior matches Qlik intent closely enough for release

### Step 5: Record Decision

Mark one of the following:

1. Approved
2. Approved with follow-up
3. Rejected

If rejected, promotion must stop until remediation is complete.

---

## Minimum Sign-Off Roles

For `strict` profile apps:

1. Migration lead
2. Business owner

For `regulated` profile apps:

1. Migration lead
2. Security reviewer
3. Business owner
4. Release manager

---

## Exit Criteria For Promotion

An app is ready for wave promotion only if all are true:

1. Fidelity threshold is met for the target gate
2. `security_extract.csv` exists and is reviewed
3. Sign-off record is completed
4. No unresolved RLS defects remain open

---

## Storage Convention

Store sign-off records with wave documentation using one file per app.

Recommended naming:

- `docs/reports/security/<wave>/<app_id>_rls_signoff.md`

If you need a starter record, use:

- `docs/templates/RLS_AUDIT_SIGNOFF_TEMPLATE.md`

---

## Recommended Weekly Governance Check

For each wave, review:

1. Apps requiring RLS audit
2. Apps approved
3. Apps pending review
4. Apps blocked for security reasons
5. Common defect patterns

