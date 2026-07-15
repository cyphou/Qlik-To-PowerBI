<!-- DOC-SHINY-BANNER -->
![Documentation](https://img.shields.io/badge/Documentation-Shiny_Style-0A66C2?style=flat-square&logo=readthedocs&logoColor=white)
![Maintained](https://img.shields.io/badge/Maintained-2026-2EA44F?style=flat-square&logo=github&logoColor=white)
![Navigation](https://img.shields.io/badge/Navigation-Quick_Access-6F42C1?style=flat-square&logo=bookstack&logoColor=white)
# Wave 3 Execution Plan (2026-06-29)

## Wave Metadata

- Wave Name: Wave-3
- Environment: test (prod rehearsal after sign-off)
- Target Workspace(s): Wave3-Enterprise, Wave3-Discovery, Wave3-Downloaded
- Start Date: 2026-07-20
- End Date: 2026-07-24
- Release Manager: release-manager@company.com
- Migration Lead: migration-lead@company.com

## Included Qlik Apps

| App ID | App Name | Owner | Tier | Profile | Planned Window | Status |
|---|---|---|---|---|---|---|
| W3-001 | Enterprise Sales Regulated | sales-ops@company.com | C | regulated | 2026-07-20 to 2026-07-22 | planned |
| W3-002 | Sales Discovery Complex | analytics-architecture@company.com | C | regulated | 2026-07-21 to 2026-07-23 | planned |
| W3-003 | Downloaded Sales Integration | dataops@company.com | B | strict | 2026-07-22 to 2026-07-24 | planned |

## Entry Criteria

- [ ] Wave 2 closeout and KPI review approved
- [ ] Manifest and profiles reviewed
- [ ] Source diagnostics completed
- [ ] Dependencies and connectors validated
- [ ] RLS audit scope identified and sign-off records pre-created for strict/regulated apps
- [ ] Run registry entries created for Wave 3

## Execution Commands

```powershell
# Build ready manifests for Wave 3
python scripts/build_wave_manifests.py --input examples/waves/enterprise_wave3_portfolio.csv --output-dir examples/waves/generated_wave3 --include-profiles-template --output-root output/waves/enterprise_wave3/staging --make-ready

# Dry-run (test gate)
python migrate.py --migration-manifest examples/waves/generated_wave3/wave_Wave-3_manifest_ready.json --dry-run --gate test

# Execute (test gate)
python migrate.py --migration-manifest examples/waves/generated_wave3/wave_Wave-3_manifest_ready.json --gate test

# Optional prod rehearsal after approvals
python migrate.py --migration-manifest examples/waves/generated_wave3/wave_Wave-3_manifest_ready.json --dry-run --gate prod
```

## Quality Gates

- [ ] Extraction integrity
- [ ] Schema validation
- [ ] Cross-validation
- [ ] QA pipeline completed
- [ ] Security extract reviewed
- [ ] RLS audit sign-off completed for strict and regulated apps
- [ ] Fidelity threshold met
- [ ] Business owner sign-off

References:

- [RLS Audit Workflow](../guides/RLS_AUDIT_WORKFLOW.md)
- [RLS Audit Sign-Off Template](../templates/RLS_AUDIT_SIGNOFF_TEMPLATE.md)
- [Wave Run Registry](WAVE_RUN_REGISTRY_2026-06-29.csv)

## Exit Criteria

- [ ] All in-scope apps completed or have approved exceptions
- [ ] Logs and gate artifacts archived
- [ ] Wave 3 status report published
- [ ] Registry rows updated to final state
- [ ] Rollback validation completed

## Risks and Mitigations

| Risk | Impact | Mitigation | Owner |
|---|---|---|---|
| Complex load script warning impact | High | Track warnings and verify gate outcomes per app | Migration Lead |
| Time-intelligence field mismatch | Medium | Validate measures and track remediation in backlog | QA Lead |
| Security sign-off delays | High | Assign backup approver and enforce review SLA | Security Lead |

## Post-Wave Review

- Success Rate: TBD
- Mean Duration per App: TBD
- High/Critical Failures: TBD
- Actions for Stabilization Stage: TBD

