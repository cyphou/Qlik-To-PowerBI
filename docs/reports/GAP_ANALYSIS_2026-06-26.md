# Gap Analysis: Migration Workspace Roadmap (2026-06-26)

## Executive Summary

**Just Delivered (This Sprint):**
- ✅ Native ready-manifest generation (`--make-ready` mode in wave builder)
- ✅ Runnable repo-ready manifests with path normalization and invalid QVF filtering
- ✅ Test coverage and validation (3 tests passing)
- ✅ Updated CLI reference and README

**Current Phase Status:**
- **Phase 1 (Workspace Baseline)** — ~60% complete
- **Phase 2 (Multi-App Throughput)** — 0% (not started)
- **Phase 3 (Governance/Security)** — 0% (not started)
- **Phase 4 (Quality Gates)** — 0% (not started)
- **Phase 5 (Deployment/Cutover)** — 0% (not started)

---

## Phase 1 — Workspace Baseline and Control Plane

### Status: Partially Complete (~60%)

#### ✅ Completed
| Deliverable | Status | Evidence |
|---|---|---|
| Wave manifest conventions | ✅ Complete | `scripts/build_wave_manifests.py` with multi-wave support |
| Ready-manifest automation | ✅ Complete | `--make-ready` flag, path normalization, invalid QVF filtering |
| Profile taxonomy (fast/strict/regulated) | ✅ Complete | 3 profiles defined in manifest defaults |
| Manifest templates | ✅ Complete | CSV and JSON portfolio templates in `docs/templates/` |
| CLI reference | ✅ Complete | Updated `docs/guides/CLI_REFERENCE.md` |
| Executable wave runs | ✅ Complete | Validated: 1 succeeded, 100% fidelity |

#### ⏳ Pending
| Deliverable | Dependency | Effort |
|---|---|---|
| Standard workspace blueprint document | None | **1 day** — formalize folder layout, file naming, conventions |
| Canonical connection map template | None | **0.5 days** — example M query + datasource mappings |
| Governance config template | Phase 3 input | **0.5 days** — compliance, audit, retention rules |
| New-program quickstart guide | All above | **1 day** — step-by-step for onboarding new migration |

**Phase 1 Definition of Done:** ❌ Not yet achieved
- Blueprint exists but not published as formal standard
- Manifests validated but profile catalog incomplete
- Need: canonical quickstart for new programs

---

## Phase 2 — Multi-App Throughput and Reliability

### Status: Not Started (0%)

#### 🎯 Key Deliverables
| Item | Effort | Notes |
|---|---|---|
| Batch runbook with resume strategy | **2 days** | Handle per-entry failures + resume from checkpoint |
| Failure isolation (per-entry fail, continue) | **1.5 days** | Currently: one failure halts manifest run |
| App-size tiering (S/M/L) | **1 day** | Classify apps by extraction/generation cost |
| Parallel worker guidance | **1 day** | Recommend worker count by total app size |
| Performance benchmark baseline | **3 days** | Run sample portfolio, document timings by tier |

**Estimated Phase 2 Effort:** 8.5 days

**Blockers:** None — can start immediately after Phase 1 quickstart.

**Critical Path Impact:** HIGH — needed for production 10–50 app migrations.

---

## Phase 3 — Governance and Security Evidence

### Status: Not Started (0%)

#### 🎯 Key Deliverables
| Item | Effort | Dependency |
|---|---|---|
| Security extraction audit checklist | **1 day** | Standardize RLS/OLS review process |
| Image inventory process | **2 days** | Extract embedded images, document origin/usage |
| Power Query inventory + versioning | **1.5 days** | Track M query variants, diffs, approval workflow |
| Governance gate profile | **2 days** | Compliance rules, audit trail, retention policy |
| Artifact manifests (lineage, ownership) | **1.5 days** | Track field → M → DAX → visual provenance |

**Estimated Phase 3 Effort:** 8 days

**Blockers:** Requires Phase 1 blueprint complete.

**Critical Path Impact:** MEDIUM — required for regulated (financial, healthcare) workspaces.

---

## Phase 4 — Validation and Quality Gates

### Status: Not Started (0%)

#### 🎯 Key Deliverables
| Item | Effort | Dependency |
|---|---|---|
| Tiered gate system (Dev/Test/Prod) | **2 days** | Gate specs, pass/fail rules, automation |
| Workspace summary dashboard | **2 days** | Real-time fidelity, pass rate, failure trends |
| Drift detection process | **2 days** | Schema, measure, visual diff on reruns |
| Automatic gate enforcement | **1.5 days** | CLI integration, promotion blocking |
| Per-app gate reporting | **1 day** | Structured report with remediation hints |

**Estimated Phase 4 Effort:** 8.5 days

**Blockers:** Requires Phase 2 (resume) + Phase 3 (governance).

**Critical Path Impact:** HIGH — gating is prerequisite for any production deployment.

---

## Phase 5 — Cutover and Deployment at Scale

### Status: Not Started (0%)

#### 🎯 Key Deliverables
| Item | Effort | Dependency |
|---|---|---|
| Promotion runbook (workspace cutover) | **1.5 days** | Wave-based, approval gates, pre-flight checks |
| Deployment strategy matrix (3 patterns) | **1 day** | Per-app, bundle, rolling; pros/cons |
| Rollback playbook + incident checklist | **2 days** | Restore procedures, communication templates |
| Post-cutover monitoring + refresh config | **2 days** | Health checks, error alerting, diagnostics |
| Wave-control dashboard | **1.5 days** | Status, timeline, dependency tracking |

**Estimated Phase 5 Effort:** 8 days

**Blockers:** Requires Phase 4 complete; assume Phase 5 follows after 60-day pilot.

**Critical Path Impact:** CRITICAL — production release cannot proceed without this.

---

## Roadmap Burn-Down

| Phase | Status | Effort | Start Criteria | Target End |
|---|---|---|---|---|
| Phase 1 | 60% complete | 4 days remaining | Immediate | 30 days |
| Phase 2 | Not started | 8.5 days | Phase 1 + 2 days | 60 days |
| Phase 3 | Not started | 8 days | Phase 1 complete | 60 days |
| Phase 4 | Not started | 8.5 days | Phase 2+3 complete | 75 days |
| Phase 5 | Not started | 8 days | Phase 4 + pilot complete | 90+ days |
| **Total** | **~11% complete** | **~37 days** | — | **90 days** |

---

## Critical Path to Production

```
Phase 1 (4d)
  ↓
Phase 2 (8.5d) ← Parallel: Phase 3 (8d) ← Can start after Phase 1
  ↓
Phase 4 (8.5d) ← Gates required before any deployment
  ↓
Phase 5 (8d) ← Pilot runs, then production cutover
  ↓
Production Go-Live
```

**Minimum time to production (critical path):** ~29–30 days (if done back-to-back without rework).

---

## Gaps by Category

### ❌ Control Plane Gaps
- [ ] Formal workspace blueprint document
- [ ] Governance config template
- [ ] Connection map template
- [ ] New-program quickstart guide

### ❌ Execution Gaps
- [ ] Batch resumption strategy
- [ ] Per-entry failure isolation
- [ ] App-size tiering logic
- [ ] Performance baseline (S/M/L apps)

### ❌ Evidence Gaps
- [ ] Security extraction audit process
- [ ] Image inventory (extract + track)
- [ ] Power Query versioning process
- [ ] Lineage artifact manifest

### ❌ Validation Gaps
- [ ] Tiered quality gates (Dev/Test/Prod)
- [ ] Workspace summary dashboard
- [ ] Drift detection logic
- [ ] Automatic gate enforcement in CLI

### ❌ Deployment Gaps
- [ ] Promotion runbook (cutover steps)
- [ ] 3-pattern deployment strategy
- [ ] Rollback procedures + checklist
- [ ] Post-cutover monitoring config
- [ ] Wave-control dashboard

---

## Recommended Next Steps (Priority Order)

### 🔴 Critical Path (Do First)

1. **Phase 1 Complete** (4 days)
   - Finalize workspace blueprint document
   - Publish canonical templates for new programs
   - → Unblocks Phases 2 and 3

2. **Phase 2 MVP** (5 days priority subset)
   - Implement per-entry failure isolation (continue on error)
   - Add batch resumption from checkpoint
   - → Enables reliable 10–50 app runs

3. **Phase 4 Gates** (3 days priority subset)
   - Structural validation gate (auto-fail on TMDL syntax errors)
   - Preceptor quality gate (fidelity thresholds)
   - → Minimum viable gating for production readiness

### 🟡 Important (Quick Wins)

4. **Phase 3 Lite** (2 days)
   - Security extraction review checklist
   - Image inventory process (automated extract)
   - → Satisfies most regulatory audits

5. **Phase 5 Runbook** (1.5 days)
   - Document promotion workflow
   - Create rollback checklist
   - → Operational readiness for cutover

---

## Dependencies and Sequencing

```
Ready ─→ Phase 1 Complete (4d) ─┬─→ Phase 2 MVP (5d) ─┐
                                 ├─→ Phase 3 Lite (2d) ┤
                                 └─→ Phase 4 Gates (3d)┘
                                         ↓
                                    ✅ Production Ready
                                        (10+ days)
                                        ↓
                                   Phase 5 Runbook (1.5d)
```

**Earliest production go-live:** ~17 days (if priority path only).

---

## Success Criteria for Closing Gaps

| Milestone | Definition | Evidence |
|---|---|---|
| Phase 1 Complete | New team can start migration from blueprint + template | Quickstart guide executed 2× with fresh team members |
| Phase 2 MVP | 10+ app manifest run tolerates 2–3 failures, resumes cleanly | Benchmark run with simulated failures completes |
| Phase 3 Evidence | Every app output includes auditable security/image/query artifacts | Audit report template generated and reviewed |
| Phase 4 Gates | Promotion blocked on fidelity <85% or validation failures | Failed test deployment rejected by gate |
| Phase 5 Cutover | Multi-wave cutover executed with rollback tested | Staging cutover completed, rollback verified |

---

## Estimated Effort Summary

| Category | Days | % of Total |
|---|---|---|
| Phase 1 completion | 4 | 11% |
| Phase 2 full | 8.5 | 23% |
| Phase 3 full | 8 | 21% |
| Phase 4 full | 8.5 | 23% |
| Phase 5 full | 8 | 21% |
| **Total** | **37** | **100%** |

---

## Appendix: Current vs. Target State

### Current State (Pre-Gap-Close)
- ✅ Manifest generation works
- ✅ Single app migration succeeds (100% fidelity on sample_sales)
- ✅ Ready-manifest filtering prevents bad runs
- ❌ No failure recovery strategy
- ❌ No quality gates
- ❌ No security audit trail
- ❌ No production deployment runbook

### Target State (Post-Roadmap)
- ✅ Multi-app manifest orchestration with resume
- ✅ Automatic quality gates block unready apps
- ✅ Security and image artifacts auditable
- ✅ Drift detection and validation dashboards
- ✅ Production cutover runbook with rollback tested
- ✅ Team can operationalize 50+ app migrations independently

---

**Document Date:** 2026-06-26  
**Next Review:** After Phase 1 completion (estimated 2026-07-03)
