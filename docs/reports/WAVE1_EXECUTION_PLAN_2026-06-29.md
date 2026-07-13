# Wave 1 Execution Plan (2026-06-29)

## Wave Metadata

- Wave Name: Wave-1
- Environment: test (promotion candidate to prod)
- Target Workspace(s): Wave1-Sales, Wave1-HR, Wave1-Enterprise
- Start Date: 2026-07-06
- End Date: 2026-07-10
- Release Manager: release-manager@company.com
- Migration Lead: migration-lead@company.com

## Included Qlik Apps

| App ID | App Name | Owner | Tier | Profile | Planned Window | Status |
|---|---|---|---|---|---|---|
| W1-001 | Sales Discovery Wave | analytics@company.com | B | fast | 2026-07-06 to 2026-07-07 | planned |
| W1-002 | HR Analytics Wave | hr-bi@company.com | B | strict | 2026-07-07 to 2026-07-09 | planned |
| W1-003 | Enterprise Sales Wave | sales-ops@company.com | C | regulated | 2026-07-08 to 2026-07-10 | planned |

## Entry Criteria

- [ ] Source app inventory finalized
- [ ] Manifest and profiles reviewed
- [ ] Server diagnostics completed (`--server-test`)
- [ ] Dependencies and connectors validated
- [ ] RLS audit scope identified for strict and regulated apps
- [ ] Run registry initialized from template

## Execution Commands

```powershell
# Build ready manifests for Wave 1
python scripts/build_wave_manifests.py --input examples/waves/enterprise_wave1_portfolio.csv --output-dir examples/waves/generated_wave1 --include-profiles-template --output-root output/waves/enterprise_wave1/staging --make-ready

# Dry-run
python migrate.py --migration-manifest examples/waves/generated_wave1/wave_Wave-1_manifest_ready.json --dry-run --gate test

# Execute
python migrate.py --migration-manifest examples/waves/generated_wave1/wave_Wave-1_manifest_ready.json --gate test
```

## Quality Gates

- [ ] Extraction integrity
- [ ] Schema validation (`--schema-validate`)
- [ ] Cross-validation (`--cross-validate`)
- [ ] QA pipeline (`--qa`)
- [ ] Security extract reviewed
- [ ] RLS audit sign-off completed for strict and regulated apps
- [ ] Fidelity threshold met
- [ ] Business owner sign-off

RLS workflow references:

- [RLS Audit Workflow](../guides/RLS_AUDIT_WORKFLOW.md)
- [RLS Audit Sign-Off Template](../templates/RLS_AUDIT_SIGNOFF_TEMPLATE.md)

## Exit Criteria

- [ ] All in-scope apps are completed or have approved exceptions
- [ ] Deployment logs archived
- [ ] Wave summary report published
- [ ] Rollback validation completed
- [ ] RLS sign-off records archived for strict and regulated apps
- [ ] Run registry updated with final status and approver names

## Risks and Mitigations

| Risk | Impact | Mitigation | Owner |
|---|---|---|---|
| Connector auth drift | High | Validate connection map pre-run | Migration Lead |
| Missing RLS evidence | High | Pre-create sign-off records and reviewers | Security Lead |
| Fidelity regression from rename/collision pattern | Medium | Compare latest migration report and gate details before promotion | QA Lead |

## Post-Wave Review

- Success Rate: TBD
- Mean Duration per App: TBD
- Common Failure Patterns: TBD
- Actions for Next Wave: TBD