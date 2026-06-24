# TableauToPowerBI ← QlikToPowerBI Parity Gap Analysis and Sync Roadmap

## Executive Summary

This document provides a prioritized roadmap for syncing TableauToPowerBI upstream with v12 hardening features and agent architecture improvements discovered in QlikToPowerBI.

**Parity score: 0.757 (75.7%)**
- Agent-side: 93.3% (14/15 files)
- Feature modules: 76.9% (10/13)
- CLI flags: 30.0% (3/10)

---

## Part 1: Agent Architecture Gaps

### Missing agent file

| File | Status | Impact | Priority |
|------|--------|--------|----------|
| `.github/agents/preceptor.agent.md` | Missing in TableauToPowerBI | Preceptorship loop requires guidance; blocks quality gate automation | **P1** |

### Agent files present but diverged

All 14 existing agent files are present but with content differences (hash mismatch).

**Recommendation:** Perform a side-by-side diff and adopt QlikToPowerBI agent definitions which include:
- Explicit role boundaries and tool scoping
- Preceptorship loop documentation
- Cross-agent consistency rules
- Learned pitfalls registry

---

## Part 2: Feature Module Gaps

### Missing modules (3)

| Module | Purpose | Status | Priority | Est. LOC |
|--------|---------|--------|----------|----------|
| `powerbi_import/script_lineage.py` | Qlik load script → Mermaid/JSON lineage | Not present | **P1** | 300–400 |
| `powerbi_import/script_lineage_report.py` | HTML report wrapper for script lineage | Not present | **P1** | 150–200 |
| `powerbi_import/automation.py` | Batch migration and post-migration workflows | Not present | **P2** | 250–350 |

### Present modules (10)

These are confirmed present in TableauToPowerBI:
- `powerbi_import/preceptor.py`
- `powerbi_import/self_healing_v3.py`
- `powerbi_import/repair_strategies.py`
- `powerbi_import/self_healing_report.py`
- `powerbi_import/cutover_manager.py`
- `powerbi_import/full_lineage.py`
- `powerbi_import/pdf_renderer.py`
- `powerbi_import/pptx_report.py`
- `powerbi_import/report_packager.py`
- `powerbi_import/goals_generator.py`

---

## Part 3: CLI Flag Gaps

### Missing flags (7)

| Flag | Purpose | Status | Priority | Implementation |
|------|---------|--------|----------|-----------------|
| `--preceptor-review` | Enable quality gate loop (DRAFT→REVIEW→APPROVE) | Not wired | **P1** | Wire `preceptor.py` to `migrate.py` |
| `--self-heal-v3` | Enable v3 self-healing (default: basic) | Not wired | **P1** | Wire `self_healing_v3.py` to `migrate.py` |
| `--repair-strategies` | Load pluggable repair tactics | Not wired | **P1** | Wire `repair_strategies.py` to `migrate.py` |
| `--pdf-report` | Generate PDF migration report | Not wired | **P2** | Wire `pdf_renderer.py` to output pipeline |
| `--pptx-report` | Generate PPTX migration report | Not wired | **P2** | Wire `pptx_report.py` to output pipeline |
| `--package` | Create ZIP bundle with manifest | Not wired | **P2** | Wire `report_packager.py` to output pipeline |
| `--script-lineage` | Generate Qlik load script lineage report | Not wired | **P1** | Wire `script_lineage.py` and `script_lineage_report.py` to output pipeline |

### Present flags (3)

These are confirmed wired in TableauToPowerBI's `migrate.py`:
- `--cutover-plan`
- `--full-lineage`
- `--goals`

---

## Part 4: Recommended Sync Roadmap

### Phase 1: Agent Architecture (1–2 days)

**Objective:** Align agent definitions and introduce preceptorship model.

1. Port `.github/agents/preceptor.agent.md` from QlikToPowerBI
2. Diff all 14 existing agent files and adopt higher-fidelity versions
3. Add preceptorship loop guidance to agent workflow
4. Test agent invocation and boundaries

**Deliverables:**
- [ ] preceptor.agent.md added
- [ ] All 15 agent files at content parity
- [ ] .github/agents/README.md updated with parity date

**Success criteria:** `parity_status_check.py` passes with all 15 agents present

---

### Phase 2: CLI Flag Wiring (2–3 days)

**Objective:** Wire missing flags to existing modules in `migrate.py`.

1. Add `--preceptor-review` flag handler
2. Add `--self-heal-v3` flag handler
3. Add `--repair-strategies` flag handler
4. Add `--pdf-report`, `--pptx-report`, `--package` flag handlers
5. Add `--script-lineage` flag handler

**Order of execution:**
1. Wire quality gates first (`--preceptor-review`, `--self-heal-v3`, `--repair-strategies`)
2. Wire output pipeline next (`--pdf-report`, `--pptx-report`, `--package`)
3. Wire lineage last (`--script-lineage`)

**Deliverables:**
- [ ] `migrate.py` updated with 7 new flags
- [ ] Each flag integrated into post-generation pipeline
- [ ] Tests added for each flag

**Success criteria:** `parity_status_check.py` reports all 10 flags present in migrate.py

---

### Phase 3: Missing Feature Modules (3–4 days)

**Objective:** Port missing modules from QlikToPowerBI.

1. Port `script_lineage.py` (Qlik load script extraction + lineage graph)
2. Port `script_lineage_report.py` (HTML report wrapper)
3. Port `automation.py` (batch migration, post-migration workflows)

**Implementation order:**
1. Start with `script_lineage.py` (no dependencies on other missing modules)
2. Then `script_lineage_report.py` (depends on `script_lineage.py`)
3. Finally `automation.py` (depends on CLI and migration pipeline)

**Deliverables:**
- [ ] `powerbi_import/script_lineage.py` added
- [ ] `powerbi_import/script_lineage_report.py` added
- [ ] `powerbi_import/automation.py` added
- [ ] Tests added for each module
- [ ] Integrated into post-generation pipeline

**Success criteria:** `parity_status_check.py` reports all 13 required modules present

---

## Part 5: Verification and Testing

### Pre-sync checklist

- [ ] Fork or branch TableauToPowerBI to `feature/qlik-parity-sync-v12`
- [ ] Run `parity_status_check.py` baseline (should show drift vs. this report)
- [ ] Run `agent_feature_parity_check.py --upstream-path .` baseline (should report current gaps)

### Post-phase checkpoints

After each phase, run:

```bash
# Verify local consistency
py tools/analysis/parity_status_check.py

# Verify agent parity
py tools/analysis/agent_feature_parity_check.py --upstream-path "C:/GitHub Project/QlikToPowerBI"

# Run full test suite
pytest tests/ --tb=short -q
```

### Acceptance criteria for full sync

All three checks must pass:

1. **Parity checker:** All versions aligned, all modules present, all flags wired
2. **Agent parity:** score ≥ 0.95 (agent 15/15, modules 13/13, flags 10/10)
3. **Test suite:** All existing tests pass + new tests for ported features pass

---

## Part 6: Implementation Aids

### File transfer checklist

**From QlikToPowerBI to TableauToPowerBI:**

Agent files to copy:
- [ ] `.github/agents/preceptor.agent.md`

Python modules to port:
- [ ] `powerbi_import/script_lineage.py`
- [ ] `powerbi_import/script_lineage_report.py`
- [ ] `powerbi_import/automation.py`

### Testing strategy

For each ported module, add tests to TableauToPowerBI's `tests/`:
- `tests/test_script_lineage.py` (unit + integration)
- `tests/test_script_lineage_report.py` (output validation)
- `tests/test_automation.py` (batch workflow)

### Documentation updates

Update TableauToPowerBI docs after sync:
- [ ] `docs/AGENTS.md` — add preceptor role, parity workflow
- [ ] `README.md` — add new CLI flags
- [ ] `CHANGELOG.md` — document v12 parity milestone
- [ ] `docs/reports/PARITY_SYNC_2026-06-24.md` — record this sync

---

## Part 7: Timeline and Effort

| Phase | Duration | Effort | Blocker |
|-------|----------|--------|---------|
| **Phase 1: Agent Architecture** | 1–2 days | 2–3 eng-days | None |
| **Phase 2: CLI Flag Wiring** | 2–3 days | 3–4 eng-days | Phase 1 must complete |
| **Phase 3: Feature Modules** | 3–4 days | 5–6 eng-days | Phase 2 must complete |
| **Phase 4: Testing + Validation** | 1–2 days | 2–3 eng-days | All prior phases |
| **Total** | **~9–11 days** | **~12–16 eng-days** | — |

---

## Part 8: Success Metrics

### Before sync

```
Local parity (QlikToPowerBI): PASS (15/15 agents, 13/13 modules, 10/10 flags)
Upstream parity (TableauToPowerBI): score 0.757
  - Agents: 14/15 (93.3%)
  - Modules: 10/13 (76.9%)
  - Flags: 3/10 (30.0%)
```

### After sync (Target)

```
Local parity (TableauToPowerBI): PASS (15/15 agents, 13/13 modules, 10/10 flags)
Upstream parity (TableauToPowerBI): score ≥ 0.95
  - Agents: 15/15 (100.0%)
  - Modules: 13/13 (100.0%)
  - Flags: 10/10 (100.0%)
```

---

## Part 9: Downstream Sync

After TableauToPowerBI sync completes at 100% parity, this repository (QlikToPowerBI) can adopt upstream improvements by:

1. Checking if TableauToPowerBI has introduced new agents or features
2. Diff and port back any innovations that apply to Qlik domain
3. Document in `CHANGELOG.md` as "synced upstream from TableauToPowerBI"

This ensures bidirectional knowledge flow and prevents regressions.

---

## Appendix: Reference Commands

### Local parity check (QlikToPowerBI)

```bash
py -3 tools/analysis/parity_status_check.py
```

### Upstream parity check against QlikToPowerBI

```bash
py -3 tools/analysis/agent_feature_parity_check.py --upstream-path "C:/GitHub Project/QlikToPowerBI"
```

### Strict mode (fail if upstream not at parity)

```bash
py -3 tools/analysis/agent_feature_parity_check.py --upstream-path "C:/GitHub Project/QlikToPowerBI" --strict-upstream
```

### JSON output for tracking

```bash
py -3 tools/analysis/agent_feature_parity_check.py --upstream-path "C:/GitHub Project/QlikToPowerBI" --json > parity_result_2026-06-24.json
```

---

## Document Metadata

- **Generated:** 2026-06-24
- **Parity baseline:** v12.0.0 (QlikToPowerBI)
- **Upstream:** TableauToPowerBI (local path)
- **Score (before sync):** 0.757
- **Score (target):** ≥ 0.95
- **Maintainer:** QlikToPowerBI parity team
- **Review status:** Ready for upstream intake
