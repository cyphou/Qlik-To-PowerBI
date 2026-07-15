<!-- DOC-SHINY-BANNER -->
![Documentation](https://img.shields.io/badge/Documentation-Shiny_Style-0A66C2?style=flat-square&logo=readthedocs&logoColor=white)
![Maintained](https://img.shields.io/badge/Maintained-2026-2EA44F?style=flat-square&logo=github&logoColor=white)
![Navigation](https://img.shields.io/badge/Navigation-Quick_Access-6F42C1?style=flat-square&logo=bookstack&logoColor=white)
# Next Evolution Roadmap (2026-07-15)

## Objective

Make QlikToPowerBI the most reliable and complete migration toolkit by combining:

1. Zero-blocker Desktop openability by default.
2. Maximum semantic and visual fidelity on complex enterprise apps.
3. Production-grade CI gates, observability, and repeatable operations.
4. Fast, scalable execution on large portfolios.

---

## Baseline (Already Delivered)

1. Always-on openability guard in migration flow (`ensure_open` default enabled).
2. Deterministic autoheal for DAX and Power Query M partitions.
3. Safety fallback path to preserve Desktop openability when autoheal is not sufficient.
4. Batch openability checker script and PR gate workflow.

Operational references:

1. scripts/run_openability_batch.ps1
2. .github/workflows/openability-gate.yml

---

## North-Star KPIs

1. Desktop openability pass rate: >= 99.5% on release corpus.
2. First-pass migration success (no manual fix before open): >= 95%.
3. Fidelity score median on enterprise corpus: >= 97%.
4. Mean migration runtime per app (P50): -20% vs current baseline.
5. Reopen regression rate (already-openable app becomes non-openable): 0.

---

## Workstreams

### WS1 - Openability and Recovery Excellence (P0)

Goal:

1. Make openability deterministic and diagnosable for all app classes.

Planned evolution:

1. Add richer root-cause taxonomy in `ensure_open` output (M syntax, DAX parse, structure, schema, references).
2. Add per-healer hit rates and confidence summaries (what fixed what).
3. Add optional strict mode: fail if safety fallback touched critical objects (for regulated runs).
4. Add openability trend report (daily/weekly pass rate over corpus).

Definition of done:

1. `ensure_open` JSON contains categorized failures + repair trace.
2. CI artifacts include machine-readable root-cause and trend-ready metrics.

### WS2 - Conversion Intelligence and Auto-Correction (P0)

Goal:

1. Increase first-pass fidelity and reduce manual post-fix work.

Planned evolution:

1. Expand deterministic DAX remediation coverage (set-analysis edge patterns, nested conditional rewrites, known source-function leaks).
2. Expand M remediation coverage (step-chain breakage, malformed records/lists, identifier quoting edge cases).
3. Add guarded rewrite policies: `conservative | balanced | aggressive`.
4. Add post-repair semantic checks to block risky rewrites.

Definition of done:

1. >= 30% reduction in residual DAX/M validation errors on benchmark corpus.
2. No increase in regression failures on historical green apps.

### WS3 - Semantic and Visual Fidelity Parity (P1)

Goal:

1. Close remaining parity gaps on high-value Tableau/Qlik enterprise patterns.

Planned evolution:

1. Relationship synthesis hardening for dense many-to-many models.
2. Visual query binding repair for sparse/restitution models.
3. Better handling of advanced filter/bookmark/slicer target integrity.
4. Extend parity matrix reporting for feature-to-test traceability.

Definition of done:

1. Fidelity >= 97% median and >= 93% P10 on enterprise corpus.
2. Visual unbound-rate < 0.5% on generated reports.

### WS4 - CI/CD and Governance Hardening (P1)

Goal:

1. Make quality gates mandatory and auditable across PR and release paths.

Planned evolution:

1. Add release gate pipeline: openability + qa + schema + cross-validate + security validators.
2. Add signed artifact manifest with gate results and tool versions.
3. Add policy profile matrix (fast, strict, regulated) in CI.
4. Add fail-fast checks for drift between roadmap commitments and implemented flags/modules.

Definition of done:

1. PR and release gates both enforce non-negotiable checks.
2. Every promoted artifact has an auditable evidence bundle.

### WS5 - Performance and Scale (P1)

Goal:

1. Keep reliability gains while improving throughput on large portfolios.

Planned evolution:

1. Profile openability and autoheal hotspots (partition parsing, validators, file IO).
2. Add parallel-safe execution model for batch runs with bounded workers.
3. Add corpus-level benchmark dashboard (P50/P90 runtime, memory profile).
4. Introduce adaptive strategy: skip expensive repair passes when clean signals are strong.

Definition of done:

1. >= 20% runtime improvement on benchmark corpus with same or better pass rate.

### WS6 - Operator Experience (P2)

Goal:

1. Make operations simple, explainable, and self-service.

Planned evolution:

1. Add one-command enterprise check mode (batch + gate + summary markdown).
2. Add concise remediation hints in failure output (next exact command to run).
3. Add migration health dashboard export for leadership reporting.

Definition of done:

1. Operators can run end-to-end quality check with one command and no manual parsing.

---

## 30/60/90 Day Plan

### Day 0-30 (Stabilize and Instrument)

1. Deliver root-cause taxonomy in `ensure_open` output.
2. Add per-healer effectiveness telemetry.
3. Add strict mode behavior for regulated workflows.
4. Introduce release gate draft workflow and dry-run it on corpus.

### Day 31-60 (Lift Fidelity and Throughput)

1. Expand DAX/M remediation packs with measurable coverage targets.
2. Improve relationship and visual binding recovery paths.
3. Add performance benchmark suite and optimize top bottlenecks.
4. Publish first trend dashboard for openability and fidelity.

### Day 61-90 (Operationalize at Scale)

1. Promote release gate to required status check.
2. Finalize profile-based policy matrix in CI.
3. Freeze vNext runbook and support handover package.
4. Lock KPI review cadence with weekly status report.

---

## Risks and Mitigations

1. Over-aggressive auto-repair may hide semantic defects.
- Mitigation: conservative default policy + post-repair validation + strict mode option.

2. Corpus drift can reduce gate representativeness.
- Mitigation: monthly corpus refresh and parity drift checks.

3. Runtime overhead from deeper validation.
- Mitigation: adaptive pass strategy and performance budget in CI.

4. False confidence from openability-only success.
- Mitigation: keep fidelity and semantic correctness KPIs as co-equal release criteria.

---

## Exit Criteria for This Roadmap

1. Openability >= 99.5% on maintained corpus.
2. First-pass success >= 95%.
3. No critical regression escapes in two consecutive release cycles.
4. Required PR and release gates enforced in repository settings.
5. Documented and repeatable operations with evidence artifacts.

