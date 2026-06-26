# Rollback Playbook

**Purpose:** Emergency procedures to safely undo production deployments  
**Audience:** Migration teams, incident commanders  
**Decision Time:** <15 minutes to decision, <60 minutes to rollback complete  

---

## When to Rollback

**Immediate Rollback (No Approval Needed):**

- [ ] Data corruption detected (e.g., negative sales figures, unrealistic row counts)
- [ ] Application won't open / 500 errors
- [ ] RLS not working (non-admin users see all data)
- [ ] Refresh stuck for >30 minutes

**Requires Approval (Escalate First):**

- [ ] Business reports different (reconciliation needed, likely correct in new system)
- [ ] Minor visual issues (cosmetic, can hotfix)
- [ ] Performance slower than expected (baseline may need adjustment)

---

## Rollback Procedures

### Procedure 1: Remove Single Application (5 min)

**Scenario:** One app has critical error, others fine

**Steps:**

1. **Stop Further Deployments**
   ```bash
   # If still deploying, cancel:
   Ctrl+C in migrate.py terminal
   ```

2. **Delete from Production Workspace**
   ```powershell
   # Using Power BI PowerShell
   Remove-PowerBIReport -Id "<app_id>" -Workspace "<prod_workspace>"
   ```
   - [ ] Confirm app deleted from prod workspace
   - [ ] Confirm backup still in staging

3. **Notify Users**
   ```
   Slack: [urgent] SalesApp temporarily removed from production
   pending root cause analysis. Will redeploy within 24 hours.
   Use cached reports or contact support@company.com
   ```
   - [ ] Posted by: _______
   - [ ] Time: _______

4. **Begin Root Cause Analysis**
   - Compare DAX between staging (working) and prod (failed)
   - Check data connector credentials
   - Review refresh logs
   - Estimate fix time

---

### Procedure 2: Restore from Backup (Entire Wave)

**Scenario:** Multiple apps corrupted or security breach, must revert wave

**Duration:** 30–45 minutes

**Prerequisites:**
- [ ] Daily backup exists in Azure Blob Storage
- [ ] Backup dated today or yesterday confirmed good
- [ ] Point-in-time recovery configured

**Steps:**

1. **Verify Backup**
   ```powershell
   # List available backups
   az storage blob list --container-name "pbi-backups" \
     --account-name "migrationstorage" \
     --query "[?contains(name, 'wave1')]"
   ```
   - [ ] Backup from correct date found
   - [ ] Backup size reasonable (not corrupted)

2. **Create Restore Workspace**
   ```powershell
   # Create temporary restore workspace
   New-PowerBIWorkspace -Name "Production-Wave1-Restore-$(Get-Date -f 'yyyyMMdd-HHmm')"
   ```
   - [ ] Workspace ID: __________________

3. **Restore PBIP Projects**
   ```bash
   # Download backup PBIP projects
   az storage blob download-batch --source "pbi-backups" \
     --destination ./restore/pbip_backup \
     --account-name "migrationstorage"
   
   # Deploy to restore workspace
   python migrate.py --pbip-source ./restore/pbip_backup \
     --output-workspace "Production-Wave1-Restore-XXXXXX" \
     --skip-extraction
   ```
   - [ ] All projects deployed to restore workspace
   - [ ] No errors in deployment log

4. **Validate Restored Data**
   For each application:
   - [ ] Open in Power BI
   - [ ] Check row counts match expectations
   - [ ] Run key report, verify results
   - [ ] Test RLS with sample user

5. **User Switchover** (High Risk, Plan Carefully)
   
   **Option A: Dual Access (Lower Risk)**
   - [ ] Update bookmarks/portals to link to restore workspace
   - [ ] Announce: "Temporary access from restore workspace"
   - [ ] Keep original prod workspace read-only (no refresh)
   - [ ] Users work from restore; production crew investigates original

   **Option B: Cut Over** (Higher Risk, Faster)
   - [ ] Delete corrupted production workspace
   - [ ] Rename restore workspace: `s/Restore//` → production
   - [ ] Update all links
   - [ ] Announce: "Service restored; temporary interruption occurred"

6. **Investigation & Root Cause**
   - Continue with corrupted backup offline
   - Document what went wrong
   - Create fix (usually DAX/M query correction)
   - Test fix in dev environment

7. **Re-deployment**
   - [ ] Once fix verified, redeploy to production
   - [ ] Proceed with next wave only after full analysis

---

### Procedure 3: Capacity Degradation Rollback

**Scenario:** Workspace performing slowly (<2s response time), not data corruption

**Duration:** 10–20 minutes

**Steps:**

1. **Investigate Root Cause**
   ```powershell
   # Check capacity usage
   Get-PowerBICapacity | Select-Object Id, Name, State, TotalProcessingUnit
   
   # Check refresh queue
   Get-PowerBIDataset -WorkspaceId "<workspace>" | Select-Object Name, RefreshSchedule
   ```

2. **Escalate Option 1: Scale Workspace Capacity**
   ```bash
   # Request capacity increase from admin
   # (May take 30 min–2 hours)
   ```
   - [ ] Escalation email sent
   - [ ] ETA for capacity increase: _______

3. **Escalate Option 2: Pause Refreshes**
   ```powershell
   # Temporarily disable scheduled refreshes
   Set-PowerBIDataset -Id "<dataset>" -RefreshSchedule @() -Workspace "<workspace>"
   ```
   - [ ] All scheduled refreshes paused
   - [ ] Announce to users: "Scheduled refreshes temporarily paused for performance tuning"

4. **Monitor**
   - Wait 10 minutes after pausing refreshes
   - Re-check response time
   - If still slow: proceed to Procedure 2 (full rollback)

5. **Resume**
   - [ ] Once capacity scaled or performance improves
   - [ ] Re-enable refreshes at lower frequency initially
   - [ ] Monitor for 24 hours

---

## Rollback Decision Matrix

```
Issue Detected?
├─ Data Corruption (wrong values, negative amounts, row mismatch)
│  └─ Severity: CRITICAL
│     Action: Immediate Procedure 2 (Restore from Backup)
│     Approval: Commander has authority
│
├─ Application Won't Open / 500 Errors
│  └─ Severity: CRITICAL
│     Action: Immediate Procedure 1 (Remove app) + Investigate
│     Approval: Commander has authority
│
├─ RLS Failure (non-admin sees all data)
│  └─ Severity: CRITICAL
│     Action: Immediate Procedure 1 (Remove app) + Security Review
│     Approval: Commander + Security lead
│
├─ Refresh Fails / Stuck
│  └─ Severity: HIGH
│     Action: Wait 30 min, then Procedure 1 or 2
│     Approval: Migration lead + Support
│
├─ Performance Slow (5+ sec response)
│  └─ Severity: MEDIUM
│     Action: Procedure 3 (Capacity tuning) + Scale if needed
│     Approval: Migration lead
│
├─ Business Results Differ (numbers don't match Qlik)
│  └─ Severity: MEDIUM
│     Action: Don't rollback yet; reconcile
│     Approval: Business owner + Migration lead
│     Next: Manual DAX fix
│
└─ Minor Visual/Cosmetic Issues
   └─ Severity: LOW
      Action: Log as enhancement; no rollback
      Approval: Product owner (can defer to next update)
```

---

## Roles & Responsibilities

### Incident Commander
- Makes go/no-go rollback decisions
- Declares "Rollback initiate" or "Stabilize and observe"
- Communicates status to leadership

### Migration Lead
- Executes rollback procedures
- Validates backup integrity
- Confirms restore completeness

### Data Steward
- Validates data correctness post-restore
- Signs off on data integrity

### Support Lead
- Communicates to users
- Updates status page
- Tracks incident ticket

---

## Communication Template

**Announce Rollback (immediately, <5 min):**

```
🚨 INCIDENT: [App Name] Rollback in Progress

We have detected a critical issue in [App Name].
Action: Rolling back production deployment immediately.

Expected impact:
- [App Name] will be unavailable for 30–45 minutes
- Other applications unaffected
- Cached data still available

We will provide updates every 15 minutes.
Incident ticket: [TICKET-123]
Status page: [link]
```

**Update 1 (15 min after announcement):**

```
UPDATE: Rollback 25% complete
- Backup verified ✓
- Restore workspace created ✓
- Data restore in progress...

ETA: 30 minutes to full restore
```

**Announce Restore Complete:**

```
✅ RESOLVED: [App Name] Restored

We have successfully restored [App Name] from backup.
- Service restored at 14:35 UTC
- All data integrity validated ✓
- All users restored access

Next steps:
- Root cause investigation ongoing
- Update coming within 24 hours
- Thank you for your patience

Incident ticket: [TICKET-123]
Post-mortem meeting: [tomorrow 10am]
```

---

## Post-Incident (Within 24 Hours)

- [ ] Incident report filed (RCA)
- [ ] Root cause documented
- [ ] Fix designed and tested
- [ ] Re-deployment date scheduled
- [ ] Retrospective meeting held (what could we have caught earlier?)
- [ ] Automation added (to prevent recurrence)

---

## Rollback Testing (Quarterly)

**Test Scenario:** Restore from 1-week-old backup

- [ ] Backup retrieval succeeds
- [ ] Restore workspace deployment succeeds
- [ ] Data integrity validates
- [ ] Time to full restore documented (< 1 hour target)

**Document Results:**
- Restore time: _______ min
- Data validation time: _______ min
- User switchover time: _______ min
- Total incident duration: _______ min

---

**Version:** 1.0  
**Last Updated:** 2026-06-26  
**Last Tested:** [to be filled after first test]  
**Next Test:** Q3 2026
