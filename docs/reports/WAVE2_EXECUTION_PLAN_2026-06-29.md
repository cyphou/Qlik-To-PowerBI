<!-- DOC-SHINY-BANNER -->
![Documentation](https://img.shields.io/badge/Documentation-Shiny_Style-0A66C2?style=flat-square&logo=readthedocs&logoColor=white)
![Maintained](https://img.shields.io/badge/Maintained-2026-2EA44F?style=flat-square&logo=github&logoColor=white)
![Navigation](https://img.shields.io/badge/Navigation-Quick_Access-6F42C1?style=flat-square&logo=bookstack&logoColor=white)
# Wave 2 Execution Plan (2026-06-29)

## Wave Metadata

- Wave Name: Wave-2
- Environment: test (promotion candidate to prod)
- Target Workspace(s): Wave2-Sales, Wave2-HR, Wave2-Enterprise
- Start Date: 2026-07-13
- End Date: 2026-07-17
- Release Manager: release-manager@company.com
- Migration Lead: migration-lead@company.com

## Included Qlik Apps

| App ID | App Name | Owner | Tier | Profile | Planned Window | Status |
|---|---|---|---|---|---|---|
| W2-001 | Sales Discovery Scale | analytics@company.com | B | fast | 2026-07-13 to 2026-07-14 | planned |
| W2-002 | HR Analytics Scale | hr-bi@company.com | B | strict | 2026-07-14 to 2026-07-16 | planned |
| W2-003 | Enterprise Sales Scale | sales-ops@company.com | C | regulated | 2026-07-15 to 2026-07-17 | planned |

## Entry Criteria

- [ ] Wave 1 closeout report approved
- [ ] Wave 2 manifest and profiles reviewed
- [ ] Top Wave 1 defects triaged with owners
- [ ] Dependencies and connectors validated
- [ ] RLS audit scope identified for strict and regulated apps
- [ ] Run registry updated with Wave 1 outcomes

## Execution Commands

```powershell
# Build ready manifests for Wave 2
python scripts/build_wave_manifests.py --input examples/waves/enterprise_wave2_portfolio.csv --output-dir examples/waves/generated_wave2 --include-profiles-template --output-root output/waves/enterprise_wave2/staging --make-ready

# Dry-run
python migrate.py --migration-manifest examples/waves/generated_wave2/wave_Wave-2_manifest_ready.json --dry-run --gate test

# Execute
python migrate.py --migration-manifest examples/waves/generated_wave2/wave_Wave-2_manifest_ready.json --gate test
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
| Throughput misses planned volume | High | Parallelize by profile and enforce pre-flight checks | Release Manager |
| Security review bottleneck | High | Timebox sign-off windows and assign backup approver | Security Lead |
| Repeat gate failures from recurring defects | Medium | Attach defect taxonomy to each failed entry in registry | QA Lead |

## Post-Wave Review

- Success Rate: TBD
- Mean Duration per App: TBD
- Common Failure Patterns: TBD
- Actions for Next Wave: TBD
