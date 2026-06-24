# Multi-Agent Architecture — Qlik to Power BI Migration

This project uses a **specialized agent model**. Each agent has scoped domain knowledge,
file ownership, and clear boundaries.

## Quick Reference

| Agent | Invoke When | Owns |
|-------|-------------|------|
| **@orchestrator** | Pipeline coordination, CLI, batch | `migrate.py`, orchestration modules |
| **@extractor** | Parsing Qlik source artifacts | `qlik_export/` extraction modules |
| **@converter** | Formula/expression conversion (coordination layer) | Delegates to @dax and @wiring |
| **@dax** | DAX/formula correctness, conversion, optimization | DAX conversion modules |
| **@wiring** | DAX↔M bridge, query generation, classification | M query modules |
| **@semantic** | Semantic model (TMDL), relationships, RLS | Semantic model generators |
| **@visual** | Report layout, visual containers, filters | Report/visual generators |
| **@generator** | Cross-cutting generation coordination | `output/`, `powerbi_import/`, `src/fabric_api/` generators |
| **@assessor** | Migration readiness, scoring, strategy, validation | Assessment modules |
| **@merger** | Shared model, multi-source merge | Merge modules |
| **@deployer** | Deployment, auth, gateway, telemetry | Deployment modules |
| **@reviewer** | Artifact quality review, preceptorship loop | Quality review modules |
| **@tester** | Tests, coverage, fixtures, regression | `tests/` |

## Architecture Diagram

```
                        ┌──────────────┐
                        │ Orchestrator │  ← CLI entry, pipeline coordination
                        └──────┬───────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
        ┌─────▼─────┐   ┌─────▼─────┐   ┌─────▼─────┐
        │ Extractor  │   │ Converter │   │ Generator  │
        │(Qlik parse)│  │ (coord.)  │   │ (coord.)   │
        └──────┬─────┘   └─────┬─────┘   └─────┬──────┘
               │          ┌────┴────┐     ┌─────┴──────┐
               │          │         │     │            │
               │     ┌────▼───┐ ┌───▼───┐ ┌▼────────┐ ┌▼──────┐
               │     │  DAX   │ │Wiring │ │Semantic │ │Visual │
               │     │(formula)│ │(DAX↔M)│ │(model)  │ │(report)│
               │     └────────┘ └───────┘ └─────────┘ └───────┘
               │                              │
               │        ┌────────────────┬────┴────┐
               │        │                │         │
               │  ┌─────▼─────┐   ┌─────▼───┐  ┌──▼─────┐
               │  │  Assessor  │   │ Merger  │  │Deployer│
               │  │ (Analysis) │   │ (Merge) │  │(Deploy)│
               │  └────────────┘   └─────────┘  └────────┘
               │
              ┌┴───────────────────────────────────────────┐
              │                 Reviewer                    │
              │    (Preceptorship loop — reviews artifacts  │
              │     from Semantic + Visual + DAX + Wiring)  │
              └────────────────────────────────────────────┘

              ┌────────────────────────────────────────────┐
              │                  Tester                     │
              │    (Cross-cutting — reads all, writes       │
              │     only to tests/)    │
              └────────────────────────────────────────────┘
```

## The Preceptorship Loop

Every migration passes through a **quality gate** before artifacts are finalized:

```
DRAFT (Agent)  ──→  REVIEW (@reviewer)  ──→  APPROVE? (≥ 4★?)
     ↑                                           │
     │                  YES ─────────────────────→ DONE (artifacts ready)
     │                   NO ─────────────────────→ COACH (structured feedback)
     │                                                │
     └────────────────────────────────────────────────┘
                       (max 3 cycles, then escalate)
```

### Review Dimensions (5-star scoring)

| Dimension | What @reviewer Checks |
|-----------|----------------------|
| **Completeness** | All source objects have corresponding output |
| **Formula Correctness** | Valid syntax, correct conversion from Qlik formulas |
| **Query Validity** | Proper quoting, valid expressions |
| **Model Structure** | Valid relationships, proper cardinality |
| **Report Fidelity** | Visual types mapped correctly, filters at right level |

### Scoring Rules

- **≥ 4★ average** across all dimensions → **APPROVE**
- **< 4★ average** → **COACH** — @reviewer provides specific feedback per dimension
- **After 3 failed cycles** → **ESCALATE** to user

## Agent Parity Workflow (TableauToPowerBI)

This repository includes an automated parity workflow for agents and migration
feature surface (modules + CLI flags).

### Primary tooling

- `tools/analysis/parity_status_check.py`
       - Local governance checks (versions, required modules, required flags, docs consistency)
- `tools/analysis/agent_feature_parity_check.py`
       - Local agent + feature parity checks
       - Optional upstream comparison against `OWNER/REPO`

### Commands

Local parity only:

```bash
py -3 tools/analysis/agent_feature_parity_check.py
```

Local + upstream parity:

```bash
py -3 tools/analysis/agent_feature_parity_check.py --upstream-repo OWNER/REPO --branch main
```

Local filesystem upstream parity:

```bash
py -3 tools/analysis/agent_feature_parity_check.py --upstream-path "C:/GitHub Project/TableauToPowerBI"
```

Scan built-in candidate repositories:

```bash
py -3 tools/analysis/agent_feature_parity_check.py --scan-default-candidates
```

Scan candidate repositories from file:

```bash
py -3 tools/analysis/agent_feature_parity_check.py --candidate-file PATH_TO_LIST
```

Strict upstream mode (non-zero exit if upstream parity fails):

```bash
py -3 tools/analysis/agent_feature_parity_check.py --upstream-repo OWNER/REPO --strict-upstream
```

Machine-readable output:

```bash
py -3 tools/analysis/agent_feature_parity_check.py --upstream-repo OWNER/REPO --json
```

### Interpretation rules

- `local_agents` fail means local `.github/agents` set is incomplete.
- `local_features` fail means required v12 modules or CLI flags drifted.
- `upstream_agents` fail means upstream lacks one or more local agent files or paths differ.
- `upstream_features` fail means upstream lacks one or more required modules/flags from the current parity baseline.

### Current reference report

- See `docs/reports/TABLEAU_AGENT_FEATURE_PARITY_2026-06-24.md` for the latest
       snapshot and workflow notes.- See `docs/reports/TABLEAU_PARITY_SYNC_ROADMAP_2026-06-24.md` for upstream
  alignment gaps and implementation plan.