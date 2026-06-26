# Wave Execution Plan Template

## Wave Metadata

- Wave Name:
- Environment:
- Target Workspace(s):
- Start Date:
- End Date:
- Release Manager:
- Migration Lead:

## Included Qlik Apps

| App ID | App Name | Owner | Tier | Profile | Planned Window | Status |
|---|---|---|---|---|---|---|
| APP-001 | Sales Executive | alice@company.com | B | strict | 2026-07-01 to 2026-07-03 | planned |

## Entry Criteria

- [ ] Source app inventory finalized
- [ ] Manifest and profiles reviewed
- [ ] Server diagnostics completed (`--server-test`)
- [ ] Dependencies and connectors validated

## Execution Commands

```bash
# Wave diagnostics
python migrate.py --server-url https://qlik.example.com --server-test

# Manifest wave run
python migrate.py --migration-manifest path/to/wave_manifest.json
```

## Quality Gates

- [ ] Extraction integrity
- [ ] Schema validation (`--schema-validate`)
- [ ] Cross-validation (`--cross-validate`)
- [ ] QA pipeline (`--qa`)
- [ ] Security extract reviewed
- [ ] Fidelity threshold met
- [ ] Business owner sign-off

## Exit Criteria

- [ ] All in-scope apps are completed or have approved exceptions
- [ ] Deployment logs archived
- [ ] Wave summary report published
- [ ] Rollback validation completed

## Risks and Mitigations

| Risk | Impact | Mitigation | Owner |
|---|---|---|---|
| Connector auth drift | High | Validate connection map pre-run | Migration Lead |

## Post-Wave Review

- Success Rate:
- Mean Duration per App:
- Common Failure Patterns:
- Actions for Next Wave:
