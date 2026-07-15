<!-- DOC-SHINY-BANNER -->
![Documentation](https://img.shields.io/badge/Documentation-Shiny_Style-0A66C2?style=flat-square&logo=readthedocs&logoColor=white)
![Maintained](https://img.shields.io/badge/Maintained-2026-2EA44F?style=flat-square&logo=github&logoColor=white)
![Navigation](https://img.shields.io/badge/Navigation-Quick_Access-6F42C1?style=flat-square&logo=bookstack&logoColor=white)
# Multi-Wave Promotion Runbook

**Purpose:** Standardized procedures for safe, phased production deployment  
**Audience:** Migration teams, deployment coordinators, platform engineers  
**Duration:** ~2 days per wave (20–50 apps per wave)  

---

## Pre-Promotion Validation Checklist

**7 Days Before Wave 1:**

- [ ] All quality gates pass (Dev → Test → Prod gate requirements)
- [ ] Security audit complete (RLS/OLS verified)
- [ ] Power BI capacity provisioned (confirm provisioned capacity available)
- [ ] Support team trained on rollback procedures
- [ ] Stakeholder communication plan finalized
- [ ] Monitoring dashboards configured (Application Insights, Power BI Health)
- [ ] Runbook reviewed and approved by technical lead

**3 Days Before Each Wave:**

- [ ] Final gate re-check (fidelity, errors, security)
- [ ] User acceptance testing (UAT) completed
- [ ] Performance baseline captured
- [ ] Backup/snapshots created for rollback prep

---

## Wave Execution Timeline

### Phase 1: Pre-Promotion (08:00–10:00)

**Step 1.1: Deploy to Staging** (30 min)
```bash
# Deploy to staging Power BI workspace for final validation
python migrate.py --manifest wave_X_apps.json \
  --output-workspace "Staging-Wave-X" \
  --profile strict \
  --gate prod \
  --dry-run  # Preview only
```

- [ ] Command completed without errors
- [ ] Generated PBIP projects in staging workspace
- [ ] All apps visible in Power BI Service

**Step 1.2: Smoke Test in Staging** (45 min)
- [ ] Open 3 representative apps in Power BI
- [ ] Verify visuals render correctly
- [ ] Test RLS with test user account
- [ ] Check report refresh completes
- [ ] Confirm no data anomalies

**Step 1.3: Stakeholder Sign-off** (15 min)
- [ ] Show staging results to business stakeholder
- [ ] Get verbal approval: "___ approved Wave X for production"
- [ ] Document approval: who, when, date

---

### Phase 2: Production Deployment (10:00–14:00)

**Step 2.1: Deploy to Production** (30 min)
```bash
# Deploy to production workspace
python migrate.py --manifest wave_X_apps.json \
  --output-workspace "Production-Wave-X" \
  --profile strict \
  --gate prod \
  --continue-on-error  # Continue if app fails, report all
```

- [ ] Check exit code: 0 = success, 1 = partial success
- [ ] Review deployment log for any errors
- [ ] Document start time: _______
- [ ] Document end time: _______

**Step 2.2: Production Validation** (90 min)
```
Time: 10:30–12:00
```

For each application in wave:
- [ ] Open app in prod workspace
- [ ] Verify all sheets/pages load
- [ ] Check data (compare row counts to staging)
- [ ] Test filters/slicers
- [ ] Validate refresh completed
- [ ] Run 2–3 key reports, compare values

**Step 2.3: Monitoring Checks** (30 min)

In Application Insights:
- [ ] Check error rate: <1%
- [ ] Check response time: <2 seconds avg
- [ ] Check refresh success: 100%

In Power BI Service:
- [ ] Monitor dataset refresh jobs
- [ ] Check dataset size (not unexpectedly large)
- [ ] Monitor user access attempts

---

### Phase 3: Post-Promotion (14:00–16:00)

**Step 3.1: User Communication** (30 min)
```
Email to stakeholders:
Subject: Wave X Deployed to Production

Wave X (5 applications) successfully deployed to production at 10:00.

New applications:
- SalesAnalytics (production/SalesAnalytics)
- HRMetrics (production/HRMetrics)
- FinanceReports (production/FinanceReports)

Access:
- All users in [group_name] now have access
- Contact support@company.com for access requests

Known limitations:
- [if any, list here]

---

Please report issues to: migrate-support@company.com
```

- [ ] Email sent
- [ ] Stakeholders received notification

**Step 3.2: Documentation Update** (30 min)
- [ ] Update data catalog with new reports
- [ ] Add runbooks/user guides to wiki
- [ ] Link Power BI apps from hub/portal
- [ ] Update data lineage documentation

**Step 3.3: Close-Out** (30 min)
- [ ] Archive wave artifacts
- [ ] Create post-promotion summary
- [ ] Schedule retrospective meeting (24 hours post-promotion)

---

## Multi-Wave Sequencing

**Recommended Schedule for 50-App Migration:**

| Wave | Apps | Timing | Apps Deployed |
|------|------|--------|---|
| Wave 1 | 5 (pilot) | Week 1, Mon-Wed | SalesApp, ReportsApp, ... |
| Wave 2 | 8 | Week 1, Thu-Fri + Week 2, Mon | ... |
| Wave 3 | 10 | Week 2, Tue-Wed | ... |
| Wave 4 | 12 | Week 2, Thu-Fri | ... |
| Wave 5 | 15 (largest) | Week 3, Mon-Wed | ... |

**Rationale:**
- Wave 1 (pilot): Smallest, highest monitoring
- Wave 2–4: Medium, regular cadence
- Wave 5 (largest): After team comfortable with process

---

## Rollback Decision Tree

**During Production Deployment, if:**

1. **Data Anomaly Detected** (e.g., sums don't match Qlik)
   - Stop Wave immediately
   - Initiate Rollback Procedure 1 (Remove app from prod)
   - Root cause: Compare DAX formulas to Qlik expressions
   - Re-deploy after fix

2. **Critical Error** (app won't open, refresh fails)
   - Initiate Rollback Procedure 1
   - Root cause: Check error logs
   - Fix and re-deploy

3. **Performance Degradation** (response >5 seconds)
   - Monitor for 10 minutes
   - If persists: Initiate Rollback Procedure 2
   - Scale workspace capacity before retry

4. **User Reports Incorrect Results**
   - Mark as "Validation Issue" but DO NOT ROLLBACK
   - Create incident ticket
   - Hotfix deployed within 24 hours

---

## Post-Promotion Health Monitoring

**For 48 Hours Post-Promotion:**

| Metric | Check Frequency | Alert Threshold |
|--------|---|---|
| Refresh success rate | Every 30 min | <95% |
| Error rate | Every 15 min | >2% |
| Response time | Every 15 min | >5 sec avg |
| Dataset size | Every 2 hours | >150% baseline |

**Daily Retrospective** (08:00 next morning)
- [ ] Review overnight monitoring data
- [ ] Identify any issues
- [ ] Decide: ready for next wave? Yes / No / With Fixes

---

## Appendix: Wave Manifest Template

```json
{
  "wave_id": "Wave-1-Pilot",
  "scheduled_date": "2026-07-01",
  "apps": [
    {
      "app_id": "sales_001",
      "app_name": "Sales Analytics",
      "owner": "sales-team@company.com",
      "gate_status": "prod_pass",
      "fidelity": 92,
      "estimated_users": 25
    }
  ],
  "go_no_go_criteria": {
    "all_gates_pass": true,
    "no_critical_errors": true,
    "capacity_available": true,
    "support_ready": true
  },
  "escalation_contact": "migrate-lead@company.com"
}
```

---

**Version:** 1.0  
**Last Updated:** 2026-06-26  
**Next Review:** After Wave 1 completion

