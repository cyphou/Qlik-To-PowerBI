<!-- DOC-SHINY-BANNER -->
![Documentation](https://img.shields.io/badge/Documentation-Shiny_Style-0A66C2?style=flat-square&logo=readthedocs&logoColor=white)
![Maintained](https://img.shields.io/badge/Maintained-2026-2EA44F?style=flat-square&logo=github&logoColor=white)
![Navigation](https://img.shields.io/badge/Navigation-Quick_Access-6F42C1?style=flat-square&logo=bookstack&logoColor=white)
# Next Roadmap After Wave 2 (2026-06-29)

## Current Baseline

1. Wave 1 complete: 3/3 passed under test gate.
2. Wave 2 complete: 3/3 passed under test gate.
3. Live registry active and updated through Wave 2.

Current quality baseline:

1. Gate pass rate: 100% for Wave 1 and Wave 2.
2. Fidelity: 100% for all executed apps.
3. Known non-blocking risk: validator warning for unknown [Year] reference on the large regulated app.

---

## Next Roadmap (Wave 3 + Stabilization)

### Stage A: Wave 3 Regulated and Complex Cutover Readiness (Week 6-7)

Primary goal:

1. Validate the most complex, flow-heavy, parameterized reporting apps using strict governance and sign-off controls.

Scope for Wave 3:

1. large_enterprise_sales.json (regulated)
2. qlik_sales_discovery_demo.json (regulated)
3. sample_sales_from_qvf_downloaded.json (strict)

Execution outputs required per app:

1. Migration report JSON
2. Gate JSON and HTML
3. Security artifacts
4. RLS sign-off status
5. Registry row update (planned -> completed)

### Stage B: Stabilization and Handover Prep (Week 8)

Primary goal:

1. Move from wave execution to repeatable operations with auditable controls.

Deliverables:

1. Finalized runbook update with Wave 3 lessons.
2. Defect taxonomy update from Wave 3 failures and warnings.
3. Production promotion checklist with approver identity and incident references.

---

## Command Track (Ready to Execute)

```powershell
python scripts/build_wave_manifests.py --input examples/waves/enterprise_wave3_portfolio.csv --output-dir examples/waves/generated_wave3 --include-profiles-template --output-root output/waves/enterprise_wave3/staging --make-ready

python migrate.py --migration-manifest examples/waves/generated_wave3/wave_Wave-3_manifest_ready.json --dry-run --gate test

python migrate.py --migration-manifest examples/waves/generated_wave3/wave_Wave-3_manifest_ready.json --gate test
```

Optional pre-prod gate rehearsal (after sign-off completion):

```powershell
python migrate.py --migration-manifest examples/waves/generated_wave3/wave_Wave-3_manifest_ready.json --dry-run --gate prod
```

---

## Governance Controls for Wave 3

1. Strict and regulated profiles require completed RLS sign-off references before prod promotion.
2. Any prod override requires incident reference, approver identity, and remediation date.
3. Registry must be updated at three points: dry-run start, execute start, closeout.
4. Blocker triage SLA: all high/critical gate failures triaged within 1 business day.

---

## Exit Criteria

1. Wave 3 test-gate pass rate at or above 90%.
2. No untriaged high/critical gate failures.
3. RLS sign-off references present for strict and regulated entries.
4. Post-wave summary and KPI rollup published.

---

## Risks and Mitigations

1. Load script parser warnings on complex apps.
- Mitigation: Track as known warning unless gate impact increases; attach warning evidence in status report.

2. Time-intelligence reference mismatch (example: [Year]).
- Mitigation: Add targeted remediation backlog item and validate affected measures in cutover review.

3. Security sign-off bottleneck.
- Mitigation: Pre-assign backup approver and timebox review windows.

