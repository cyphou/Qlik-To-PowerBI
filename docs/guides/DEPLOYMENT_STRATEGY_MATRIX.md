<!-- DOC-SHINY-BANNER -->
![Documentation](https://img.shields.io/badge/Documentation-Shiny_Style-0A66C2?style=flat-square&logo=readthedocs&logoColor=white)
![Maintained](https://img.shields.io/badge/Maintained-2026-2EA44F?style=flat-square&logo=github&logoColor=white)
![Navigation](https://img.shields.io/badge/Navigation-Quick_Access-6F42C1?style=flat-square&logo=bookstack&logoColor=white)
# Deployment Strategy Matrix

**Purpose:** Choose optimal deployment pattern based on risk profile and resources  
**Applies To:** All multi-app deployments  

---

## Three Deployment Patterns

### Pattern A: Conservative (Pilot-First, Max Safety)

**When to Use:**
- First-time migrations (Wave 1 pilot)
- High-risk applications (finance, healthcare)
- Limited rollback capability
- Strict compliance requirements

**Timeline:** 3 weeks for 50 apps (5 waves × 1 week each)

**Process:**
```
Wave 1 (5 apps, 3 days) → Monitor 5 days → Wave 2 (8 apps, 3 days) → ...
```

**Characteristics:**
- Max 5 apps per wave
- 5–7 days monitoring between waves
- Daily stakeholder sign-offs
- Detailed runbooks for every wave

**Pros:** Maximum safety, easy rollback, low blast radius  
**Cons:** Longest timeline, higher overhead

**Suitable For:** Healthcare, government, financial institutions

---

### Pattern B: Moderate (Balanced)

**When to Use:**
- Mid-size migrations (20–50 apps)
- Medium-risk applications
- Some production incident response experience
- Standard compliance (SOC 2)

**Timeline:** 2 weeks for 50 apps (5 waves × 2–3 days each)

**Process:**
```
Wave 1 (10 apps, 2 days) → Monitor 3 days → Wave 2 (12 apps, 2 days) → ...
```

**Characteristics:**
- 10–15 apps per wave
- 3–5 days monitoring between waves
- Weekly stakeholder reviews
- Runbooks for major waves only

**Pros:** Reasonable speed, good safety, manageable overhead  
**Cons:** Slightly higher risk than conservative

**Suitable For:** Enterprise BI teams, regulated but not high-compliance

---

### Pattern C: Aggressive (Fast, Parallel)

**When to Use:**
- Re-migrations or refresh deployments
- Low-risk applications (exploratory analytics, dashboards)
- Mature incident response capabilities
- Non-regulated data

**Timeline:** 1 week for 50 apps (parallel execution)

**Process:**
```
Waves 1–2–3 deployed in parallel, continuous monitoring
```

**Characteristics:**
- 20–30 apps per wave
- 1–2 days monitoring between waves
- Automated gates and dashboards
- Incident response team on standby

**Pros:** Fastest deployment, automated monitoring  
**Cons:** Highest risk, complex orchestration

**Suitable For:** Internal analytics teams, non-critical systems

---

## Pattern Comparison Matrix

| Factor | Conservative | Moderate | Aggressive |
|--------|---|---|---|
| Apps per wave | 5 | 10–15 | 20–30 |
| Total timeline (50 apps) | 3 weeks | 2 weeks | 1 week |
| Risk level | Low | Medium | High |
| Monitoring days between waves | 5–7 | 3–5 | 1–2 |
| Automated gates required | No | Yes | Yes |
| Manual sign-offs per wave | Every wave | Weekly | Weekly |
| Runbook detail level | Comprehensive | Standard | Minimal |
| Rollback complexity | Simple | Moderate | Complex |
| Best for | First-time, regulated | Standard | Experienced teams |

---

## Pattern Selection Flowchart

```
Start: Planning deployment

Are you in a highly regulated industry?
├─ YES → Consider Conservative
│       └─ First migration? → CONSERVATIVE ✓
│       └─ Refresh? → MODERATE ✓
└─ NO ─ → Do you have automated gates?
          ├─ NO → CONSERVATIVE ✓
          └─ YES → Experienced with incident response?
                   ├─ NO → MODERATE ✓
                   └─ YES → AGGRESSIVE ✓
```

---

## Resource Requirements by Pattern

### Conservative Pattern

**Team:**
- 1 Migration Lead
- 2 QA Engineers (full-time)
- 1 Support Engineer (50%)
- 1 Data Steward (part-time)

**Infrastructure:**
- Staging workspace (full spec)
- Production workspace
- Monitoring dashboards
- Backup/snapshot capability

**Total Cost:** $50–75K

---

### Moderate Pattern

**Team:**
- 1 Migration Lead
- 1 QA Engineer (full-time)
- 1 Support Engineer (on-call)
- 1 Data Steward (on-call)

**Infrastructure:**
- Staging workspace (reduced spec)
- Production workspace
- Automated monitoring
- Automated backup

**Total Cost:** $35–50K

---

### Aggressive Pattern

**Team:**
- 1 Migration Coordinator (part-time)
- 1 Incident Response Engineer (on-call)
- Automated orchestration scripts

**Infrastructure:**
- Minimal staging (spot-checks only)
- Production workspace
- Automated gates + dashboards
- Automated backup/restore

**Total Cost:** $20–30K

---

## Risk Assessment by Pattern

### Conservative (Residual Risk: <1%)

- Wave 1: 0.1% risk (5 apps, heavily tested)
- Wave 5: 0.5% risk (25 apps cumulative, fully trained team)

**Mitigation:**
- Manual validation at every step
- 5–7 day observation period
- Multiple sign-offs

---

### Moderate (Residual Risk: 2–3%)

- Wave 1: 1% risk (10 apps, automated checks)
- Wave 5: 3% risk (50 apps, faster pace)

**Mitigation:**
- Automated gates catch 90% of issues
- 3–5 day observation
- Weekly stakeholder review

---

### Aggressive (Residual Risk: 5–8%)

- All waves: 5–8% risk (20–30 apps per wave)

**Mitigation:**
- Incident response team on standby 24/7
- Automated rollback capability
- High monitoring frequency

**When to Abort:**
- If >3 apps fail, halt and assess
- If incident response takes >2 hours, rollback
- If data corruption detected, immediate rollback

---

## Switching Patterns Mid-Migration

**Scenario:** Started Aggressive, discovered critical issues in Wave 2

**Decision:**
- Continue Aggressive if root cause fixable (<24 hours)
- Switch to Moderate if requiring 1–2 day fixes per wave
- Switch to Conservative if root cause requires architectural change

**Process:**
1. Complete current wave (let it stabilize)
2. Conduct root cause analysis
3. Decide on pattern switch
4. Extend timeline for remaining waves
5. Update stakeholder communication

---

## Recommended Pattern by Organization

| Organization Type | Pattern | Rationale |
|---|---|---|
| Healthcare | Conservative | HIPAA compliance, patient data |
| Finance | Conservative | SOX, PCI-DSS compliance |
| Government | Conservative | FedRAMP, highest security bar |
| Enterprise (non-regulated) | Moderate | Balanced safety and speed |
| Mid-market BI team | Moderate | Standard compliance, experienced |
| Startup/Internal BI | Aggressive | Speed prioritized, non-critical |
| Re-migration (refresh) | Aggressive | Proven migration, lower risk |

---

## Approval Gates by Pattern

### Conservative: Go/No-Go Decisions

**Before Wave 1:**
- [ ] Executive sponsor approval
- [ ] Chief Data Officer sign-off
- [ ] IT Security approval
- [ ] Business owner approval

**Before Each Wave:**
- [ ] QA lead: "Gate pass"
- [ ] Business owner: "Ready for deployment"
- [ ] Support lead: "Team trained"

---

### Moderate: Weekly Reviews

**Before Wave 1:**
- [ ] Director approval
- [ ] IT Security approval
- [ ] Business owner approval

**Weekly (Mon 9am):**
- [ ] Review previous week's metrics
- [ ] Approve next week's wave
- [ ] Address any issues

---

### Aggressive: Automated with Exceptions

**Before Wave 1:**
- [ ] Manager approval
- [ ] Incident response lead trained

**Continuous:**
- Automated gates approve/reject each app
- Manual intervention only if gate fails
- Escalation path: Support → Manager → Director

---

## Post-Deployment Pattern Validation

**72 Hours Post-Promotion:**

| Pattern | Success Criteria |
|---------|---|
| Conservative | 100% apps operational, 0 critical issues |
| Moderate | 99%+ apps operational, ≤1 critical issue |
| Aggressive | 95%+ apps operational, incident response time <2 hours |

---

**Version:** 1.0  
**Last Updated:** 2026-06-26  
**Next Review:** After first production deployment

