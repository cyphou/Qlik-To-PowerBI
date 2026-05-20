# Agent Behavior Instructions — Qlik to Power BI Migration

Rules for AI coding agents working in this codebase. Read `.github/copilot-instructions.md`
for full project context.

**Multi-agent architecture**: This project uses a specialized agent model.
See `docs/AGENTS.md` for the full architecture diagram and `.github/agents/` for per-agent definitions.

---

## Project Context (Quick Reference)

- **Pipeline**: Qlik source → [qlik_export] → Extraction → [output, powerbi_import, src/fabric_api] → Power BI
- **Source**: `qlik_export/`
- **Target**: `output/`, `powerbi_import/`, `src/fabric_api/`
- **Tests**: `pytest tests/ --tb=short -q` — 71 test files
- **Agents**: See `.github/agents/` and `docs/AGENTS.md`

---

## Learned Lessons (Global)

### File Edit Safety
- Use `elem is not None` instead of `if elem` (Python 3.14 `Element.__bool__()` change)
- `replace_string_in_file` fails on duplicate matches — use unique surrounding context
- Always include 3-5 lines of unchanged context before and after the target text
- Read the file FIRST, then edit — never assume content from memory

### Function Safety
- Always `grep_search` for an existing function/class name before creating a new one
- Test function signatures MUST match implementation

---

## Workflow Rules

### 1. Plan Before Build
- For multi-step work, create a plan before starting
- If something goes sideways, STOP and re-plan

### 2. Read Before Write
- **Always read target code before editing** — never assume file contents
- Check `docs/` for current project context

### 3. Testing Contract
- Run `pytest tests/ --tb=short -q` after EVERY implementation change
- If tests fail → fix them before reporting completion
- New features **require** new tests — no exceptions
- Never weaken test assertions to make tests pass

### 4. Scope Discipline
- Only modify files directly related to the task
- No drive-by refactors, no "while I'm here" improvements
- Prefer the smallest change that solves the problem
