<!-- DOC-SHINY-BANNER -->
![Documentation](https://img.shields.io/badge/Documentation-Shiny_Style-0A66C2?style=flat-square&logo=readthedocs&logoColor=white)
![Maintained](https://img.shields.io/badge/Maintained-2026-2EA44F?style=flat-square&logo=github&logoColor=white)
![Navigation](https://img.shields.io/badge/Navigation-Quick_Access-6F42C1?style=flat-square&logo=bookstack&logoColor=white)
# Next Evolution - Issue Drafts (2026-07-15)

Use these issue definitions with GitHub CLI or manually in the web UI.

Repository:

1. cyphou/Qlik-To-PowerBI

---

## Issue 1

Title:

1. [P0] Openability guard: add root-cause taxonomy and healer effectiveness metrics

Body:

```markdown
## Objective
Enhance openability diagnostics so failures and repairs are fully explainable and trendable.

## Scope
- Add root-cause taxonomy in `ensure_open` output (M syntax, DAX parse, structure, schema, references).
- Add per-healer metrics and confidence summaries in output/report artifacts.
- Include stage-level trace (`initial`, `autoheal`, `safety_fallback`) with counts.

## Acceptance Criteria
- `migrate.py --json` includes categorized failure and repair metadata under `ensure_open`.
- `scripts/run_openability_batch.ps1` exports taxonomy fields in JSON/CSV.
- Documentation updated with example output.
```

---

## Issue 2

Title:

1. [P0] Extend deterministic DAX remediation pack with guarded rewrite policies

Body:

```markdown
## Objective
Increase first-pass conversion success while keeping semantic safety.

## Scope
- Extend DAX remediation patterns for common source-function leaks and nested conditional edge cases.
- Add rewrite policy modes: `conservative`, `balanced`, `aggressive`.
- Add post-repair validation safety checks to prevent risky rewrites.

## Acceptance Criteria
- New policy flag available in CLI and documented.
- Residual DAX validator failures reduced by >= 30% on benchmark corpus.
- No regression in openability pass rate.
```

---

## Issue 3

Title:

1. [P0] Extend deterministic Power Query M remediation coverage

Body:

```markdown
## Objective
Reduce M syntax and partition-load failures in complex generated models.

## Scope
- Improve repair coverage for step-chain breakage, malformed records/lists, and identifier quoting edge cases.
- Add partition-level repair trace details in autoheal output.
- Add focused test corpus for M failures.

## Acceptance Criteria
- New M repair cases covered by tests.
- M-related blocking issues reduced by >= 30% on benchmark corpus.
- `ensure_open` output includes per-partition repair outcomes.
```

---

## Issue 4

Title:

1. [P1] Fidelity hardening: many-to-many relationship synthesis and visual binding recovery

Body:

```markdown
## Objective
Improve fidelity for dense relationship graphs and sparse/restitution models.

## Scope
- Harden relationship synthesis/deactivation strategy for ambiguous paths.
- Improve visual query binding repair for unbound columns/measures.
- Add integrity checks for filter/bookmark/slicer target references.

## Acceptance Criteria
- Fidelity median >= 97% on enterprise corpus.
- Visual unbound-rate < 0.5%.
- Added regression tests for dense M2M + sparse model scenarios.
```

---

## Issue 5

Title:

1. [P1] Release gate workflow: enforce openability + qa + schema + cross-validate

Body:

```markdown
## Objective
Promote a production-grade release gate in addition to PR openability gate.

## Scope
- Add release workflow combining openability, QA pipeline, schema validation, cross-validation.
- Persist signed evidence manifest for promoted artifacts.
- Support policy profiles (`fast`, `strict`, `regulated`) in CI matrix.

## Acceptance Criteria
- Release workflow exists and is documented.
- Required checks can be enabled in repo settings.
- Promotion artifact includes evidence bundle and gate outcomes.
```

---

## Issue 6

Title:

1. [P1] Performance and scale: profile/optimize openability and autoheal pipeline

Body:

```markdown
## Objective
Maintain reliability gains while reducing runtime on large portfolios.

## Scope
- Add benchmark suite for openability and autoheal stages.
- Profile hotspots in validators and partition traversal.
- Implement optimizations and publish trend metrics.

## Acceptance Criteria
- Runtime improvement >= 20% on benchmark corpus.
- No decline in openability or fidelity KPIs.
- Benchmark report generated and archived in CI artifacts.
```

