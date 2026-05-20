---
description: "Shared rules for all agents in the Qlik to Power BI migration project. USE FOR: enforcing project-wide constraints, coding standards, and safety rules."
---

# Shared Project Rules — Qlik to Power BI Migration

All agents MUST follow these rules. They apply to every file in the project.

## Pipeline Architecture

```
Qlik source → [qlik_export] → Extraction → [output, powerbi_import, src/fabric_api] → Power BI
```

- **Source**: `qlik_export/`
- **Target**: `output/`, `powerbi_import/`, `src/fabric_api/`
- **Tests**: `tests/`
- **Docs**: `docs/`

## Hard Constraints

1. **No duplicate functions** — always search for an existing name before creating one
2. **Read before write** — never assume file contents from memory
3. **Test after every change** — run `pytest tests/ --tb=short -q`
4. **Git hygiene** — commit only when tests pass, conventional messages (`feat:`, `fix:`, `test:`, `docs:`)

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
