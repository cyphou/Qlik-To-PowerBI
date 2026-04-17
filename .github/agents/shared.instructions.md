---
description: "Shared rules for all agents in the Qlik to Power BI migration project. USE FOR: enforcing project-wide constraints, coding standards, and safety rules."
---

# Shared Project Rules — Qlik to Power BI Migration

All agents MUST follow these rules. They apply to every file in the project.

## Pipeline Architecture

```
.qvf → [Extraction] → 17 JSON files → [Generation] → .pbip (PBIR v4.0 + TMDL)
                                                      → Fabric-native (Lakehouse + Dataflow + Notebook + SemanticModel + Pipeline)
```

- **Source**: `qlik_export/` — extraction + DAX converter + M query builder
- **Target**: `powerbi_import/` — TMDL generator + PBIR report + visual generator + Fabric generators
- **Tests**: `tests/` — 6,714+ tests across 140+ files
- **Docs**: `docs/` — architecture, dev plan, gap analysis, known limitations, roadmap

## Hard Constraints

1. **No external dependencies** — Python standard library only for core migration
2. **No duplicate functions** — always `grep_search` for an existing name before creating one
3. **Read before write** — never assume file contents from memory
4. **Test after every change** — run `pytest tests/ --tb=short -q`
5. **Git hygiene** — commit only when tests pass, conventional messages (`feat:`, `fix:`, `test:`, `docs:`)

## Python Conventions

- Python 3.12+ compatible
- `unittest.TestCase` for all test classes
- No type annotations on code you didn't write
- No docstrings on code you didn't write
- Prefer smallest change that solves the problem

## Learned Pitfalls (Global)

- Use `elem is not None` instead of `if elem` (Python 3.14 `Element.__bool__()` change)
- `replace_string_in_file` fails on duplicate matches — use unique surrounding context
- Never weaken test assertions to make tests pass
- Stage only files related to the current task
- M `if...then` without `else` causes Power BI M engine error "Token 'else' expected" — always emit `else null`
- M single-quoted strings in `IN {…}` sets must be converted to double-quoted
- `inject_m_steps()` can produce duplicate step names when called multiple times — use dedup suffix
- Calendar `Date.MonthName()`/`Date.DayOfWeekName()` must pass explicit culture parameter
- Connection string values must be escaped with `_m_escape_string()` before M injection

## Preceptorship Model

This project uses a **Preceptorship** workflow inspired by medical training.
Each task follows a structured **Plan → Assign → Implement → Review** cycle
supervised by two senior roles:

```
              ┌────────────┐     ┌────────────┐
              │  Tech Lead │     │ Preceptor  │
              │(Orchestrator)    │ (Reviewer)  │
              └──────┬─────┘     └──────┬─────┘
                     │   architectural    │  quality
                     │   oversight        │  review
          ┌──────────┼──────────┬────────┼────────┐
          ▼          ▼          ▼        ▼        ▼
      ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ...
      │Extractor│ │Converter│ │Generator│ │Deployer│
      └────────┘ └────────┘ └────────┘ └────────┘
       Plan→Assign→Implement→Review (each agent)
```

### Roles

| Role | Agent | Responsibility |
|------|-------|---------------|
| **Tech Lead** | Orchestrator | Architectural decisions, cross-agent planning, pipeline coordination, breaking tasks into assignments |
| **Preceptor** | Preceptor | Quality review, code standards enforcement, cross-agent consistency, pitfall detection, test adequacy validation |
| **Specialist** | Extractor, Converter, Generator, Assessor, Merger, Deployer, Tester | Domain-specific implementation following the 4-step cycle |

### The 4-Step Cycle (Every Specialist Agent)

1. **Plan** — Before writing code, outline what changes are needed, which files are affected, and what the expected outcome is. Use `manage_todo_list` to track steps. Flag risks or unknowns.
2. **Assign** — Confirm ownership. If parts of the task cross into another agent's domain, state the handoff explicitly (files, functions, data structures). Do NOT touch files you don't own.
3. **Implement** — Make the smallest change that solves the problem. Follow all Hard Constraints. Write code, not comments about code.
4. **Review** — Self-check before completion:
   - [ ] Tests pass (`pytest tests/ --tb=short -q`)
   - [ ] No regressions in adjacent modules
   - [ ] Cross-agent contracts preserved (function signatures, JSON schemas, dict keys)
   - [ ] Pitfalls from "Learned Pitfalls" section avoided
   - [ ] Handoff notes written if follow-up work is needed

### When to Escalate

- **To Tech Lead (Orchestrator)**: Architectural questions, new CLI flags, pipeline flow changes, cross-cutting concerns affecting 3+ agents
- **To Preceptor**: Unsure about code quality, need review of complex DAX/M/TMDL output, want validation of a non-obvious approach, merge conflict between agent domains

## Cross-Agent Handoff Protocol

When your task requires work outside your domain:
1. Complete your part fully (including tests for your domain)
2. State clearly what the next agent needs to do
3. List the exact files and functions involved
4. Provide any intermediate artifacts (JSON, dict structures)

## Key References

- Project rules: `.github/copilot-instructions.md`
- Development plan: `docs/DEVELOPMENT_PLAN.md`
- Gap analysis: `docs/GAP_ANALYSIS.md`
- Known limitations: `docs/KNOWN_LIMITATIONS.md`
- Roadmap: `docs/ROADMAP.md`
- Deployment guide: `docs/DEPLOYMENT_GUIDE.md`
- Agent architecture: `docs/AGENTS.md`

## Cross-Cutting Utilities

- `powerbi_import/security_validator.py` — Shared security module (path validation, ZIP slip defense, XXE protection, credential redaction). Used by Extractor, Orchestrator, Deployer.
- `powerbi_import/recovery_report.py` — Self-healing recovery tracker. Used by Generator (TMDL self-repair, visual fallback).
