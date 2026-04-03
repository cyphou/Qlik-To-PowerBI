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
