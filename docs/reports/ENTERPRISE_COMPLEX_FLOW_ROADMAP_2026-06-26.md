<!-- DOC-SHINY-BANNER -->
![Documentation](https://img.shields.io/badge/Documentation-Shiny_Style-0A66C2?style=flat-square&logo=readthedocs&logoColor=white)
![Maintained](https://img.shields.io/badge/Maintained-2026-2EA44F?style=flat-square&logo=github&logoColor=white)
![Navigation](https://img.shields.io/badge/Navigation-Quick_Access-6F42C1?style=flat-square&logo=bookstack&logoColor=white)
# Enterprise Complex Flow Roadmap (2026-06-26)

## Objective

Provide a production-safe migration roadmap for very large Qlik portfolios with many reports, extensive prep flow logic, complex section access, and high dependency density.

This roadmap answers a key design decision:

1. Download-First Flow
2. Generate-First Flow
3. Hybrid Wave Flow (recommended)

---

## Decision Framework: Download vs Generate

### Download-First Flow

Use when:

1. Apps are large and brittle.
2. Prep logic is business critical and must be inspected before generation.
3. You need deterministic evidence snapshots before any conversion.

Advantages:

1. Better forensic traceability.
2. Lower risk of hidden source anomalies.
3. Easier stakeholder sign-off before transformation.

Tradeoffs:

1. Slower throughput.
2. Higher upfront inventory effort.

### Generate-First Flow

Use when:

1. You need fast migration velocity.
2. Source app quality is already standardized.
3. You can tolerate iterative fixes after first conversion pass.

Advantages:

1. Fastest first-pass output.
2. Good for broad portfolio triage.

Tradeoffs:

1. More post-generation rework.
2. Higher risk of late discovery in prep flow logic.

### Hybrid Wave Flow (recommended)

For large enterprise portfolios, use:

1. Download-First for Tier C complex apps.
2. Generate-First for Tier A and stable Tier B apps.
3. Unified quality gates for all waves before promotion.

---

## Tiering Model for Big Qlik Apps

Classify each app before migration:

1. Tier A
Description: Simple visuals and low formula depth.
Threshold: Up to 10 sheets, limited set analysis.
Preferred flow: Generate-First.

2. Tier B
Description: Moderate complexity and moderate prep dependencies.
Threshold: 10 to 25 sheets, medium calc density.
Preferred flow: Hybrid.

3. Tier C
Description: High complexity, high prepflow coupling, complex security.
Threshold: 25+ sheets, heavy set analysis, advanced inter-record logic, section access complexity.
Preferred flow: Download-First.

---

## End-to-End Complex Flow Pipeline

### Stage 0: Intake and Inventory

Outputs:

1. App inventory with owner and criticality.
2. Complexity tier and wave assignment.
3. Prepflow dependency map.

Commands:

```powershell
python scripts/build_wave_manifests.py --input docs/templates/QLIK_APP_PORTFOLIO_TEMPLATE.csv --output-dir artifacts/manifests --include-profiles-template
```

### Stage 1: Source Download and Evidence Capture

Do this for Tier C and regulated Tier B:

1. Server diagnostics.
2. Snapshot extraction metadata.
3. Persist source evidence artifacts.

Commands:

```powershell
python migrate.py --server-url https://qlik.example.com --server-test
python migrate.py app.qvf --assess --json
```

### Stage 2: Conversion Execution

For each app run:

1. Extraction.
2. Generation.
3. Security and query inventories.

Commands:

```powershell
python migrate.py app.qvf --qa --cross-validate --schema-validate --self-heal-v3 --repair-strategies
```

### Stage 3: Enterprise Quality Gates

Use environment gates:

1. Dev gate for structure.
2. Test gate for QA and schema integrity.
3. Prod gate for security and release confidence.

Commands:

```powershell
python migrate.py app.qvf --gate dev
python migrate.py app.qvf --gate test
python migrate.py app.qvf --gate prod
```

Override only in controlled incidents:

```powershell
python migrate.py app.qvf --gate prod --force-deployment
```

### Stage 4: Wave Promotion and Rollback Drill

Before production wave:

1. Execute pilot wave in staging.
2. Validate gate artifacts.
3. Run rollback tabletop.

Commands:

```powershell
./scripts/run_pilot_wave_staging.ps1 -Gate test
```

---

## Next 6-Week Roadmap

### Week 1

1. Portfolio inventory and tiering complete.
2. Wave manifest templates approved.
3. Tier C candidate list finalized.

### Week 2

1. Download-First evidence pass for Tier C pilot apps.
2. Generate-First pass for Tier A pilot apps.
3. Baseline quality metrics captured.

### Week 3

1. Wave 0 pilot execution.
2. Gate defect triage.
3. Rollback drill execution.

### Week 4

1. Wave 1 execution for Tier A and stable Tier B.
2. M query and lineage review at scale.
3. Performance tuning for long-running apps.

### Week 5

1. Wave 2 execution including regulated Tier B.
2. Security sign-off cycle.
3. Cutover rehearsals.

### Week 6

1. Tier C production waves.
2. Executive closeout metrics.
3. Hand-off to steady-state operations.

---

## Prepflow-Specific Controls

For apps with heavy prepflow logic:

1. Require Download-First evidence capture.
2. Require dual validation on transformed M queries.
3. Require lineage report review before prod gate.
4. Require owner sign-off on top 20 business measures.

---

## KPI Targets

Execution KPIs:

1. Wave success rate above 95 percent.
2. Mean rerun time for failed app below 30 minutes.
3. Tier C success in first pass above 80 percent.

Quality KPIs:

1. Median fidelity in test above 85 percent.
2. Median fidelity in prod above 90 percent.
3. Critical gate failures in prod equal to 0.

Operations KPIs:

1. Rollback readiness validated for each wave.
2. Post-cutover incident rate below 2 percent.
3. Time to triage critical issues below 60 minutes.

---

## Recommendation

Use Hybrid Wave Flow as the default enterprise strategy.

1. Download-First for complex and regulated apps.
2. Generate-First for simpler high-throughput apps.
3. Gate-enforced promotion for all apps.
4. Rollback drill mandatory before each production wave.

