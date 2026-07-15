<!-- DOC-SHINY-BANNER -->
![Documentation](https://img.shields.io/badge/Documentation-Shiny_Style-0A66C2?style=flat-square&logo=readthedocs&logoColor=white)
![Maintained](https://img.shields.io/badge/Maintained-2026-2EA44F?style=flat-square&logo=github&logoColor=white)
![Navigation](https://img.shields.io/badge/Navigation-Quick_Access-6F42C1?style=flat-square&logo=bookstack&logoColor=white)
# Security Audit Checklist for Qlik-to-Power BI Migration

**Purpose:** Standardized security review process for RLS/OLS mapping and compliance validation  
**Applies To:** All regulated workloads (healthcare, finance, government) and confidential data classifications  
**Duration:** 30–60 minutes per app  

---

## Pre-Audit Preparation

- [ ] **Notify Data Steward:** Send audit schedule to data_steward@company.com
- [ ] **Review Original Qlik App:** Open Qlik app and document Section Access rules
- [ ] **Get Power BI Output:** Have generated .pbip project available
- [ ] **Gather Documentation:** Section Access rules, role descriptions, data masking requirements
- [ ] **Assign Reviewer:** Identify person who understands data governance and Qlik security

---

## Section 1: Role and Section Access Analysis

### 1.1 Identify Qlik Security Model

- [ ] **Check Section Access Table**
  - Location: QVF metadata or load script
  - Command: `grep -i "section access" app.qvf`
  - Document: Which table contains Section Access rules

- [ ] **Document All Roles**
  - Count: _____ roles identified
  - List roles: ________________, ________________, ________________
  - Example: SALES_US, SALES_EMEA, FINANCE, ADMIN

- [ ] **Identify Reduction Fields**
  - Which fields are used to restrict data?
  - Example: REGION, DEPARTMENT, PRODUCT_LINE
  - Confirm these fields exist in target tables

- [ ] **Check for OMIT Keyword**
  - Any roles with OMIT statement? Yes / No
  - If yes, document which fields are omitted: ________________
  - Impact: Data hidden from this role

---

### 1.2 Review Qlik Row-Level Security (RLS)

**Sample Section Access Table:**
```
ACCESS  REGION      DEPARTMENT    NTNAME
USER    US-East    Sales         domain\user_jane
USER    US-West    Sales         domain\user_bob
ADMIN   *           *             domain\admin_sec
```

- [ ] **All users documented** — Complete list obtained: Yes / No
- [ ] **Wildcard rules reviewed** — Any * (all) access? Yes / No
  - If yes, is it restricted to ADMIN or privileged roles? Yes / No
- [ ] **NTNAME format verified** — Domain\username or email format? ________________
- [ ] **Role descriptions obtained** — Know what each role does? Yes / No

---

### 1.3 Confirm Power BI RLS Rules Generated

- [ ] **Open generated PBIP** — power_bi_project/model/model.tmdl
- [ ] **Search for DAX RLS rules** — Find `CALCULATE(..., USERPRINCIPALNAME()...)`
- [ ] **Document RLS measures/columns**
  - Count: _____ RLS expressions found
  - Example expressions:
    ```
    = [Msr_Sales] if USERPRINCIPALNAME() = "@company.com"
    ```

- [ ] **Verify each Qlik role has Power BI equivalent**
  - [ ] Qlik Role: SALES_US → Power BI: [Region] = "US-East"
  - [ ] Qlik Role: SALES_EMEA → Power BI: [Region] = "US-West"  
  - [ ] Qlik Role: ADMIN → Power BI: ALL() [no filters]
  - [ ] Qlik Role: ________________ → Power BI: ________________

---

## Section 2: Field-Level Security and Data Masking

### 2.1 Identify Sensitive Fields

- [ ] **PII Fields Detected:**
  - [ ] Customer IDs: ________________
  - [ ] Names: ________________
  - [ ] Email addresses: ________________
  - [ ] Phone numbers: ________________
  - [ ] Bank accounts: ________________
  - [ ] Social Security numbers: ________________

- [ ] **Business-Sensitive Fields:**
  - [ ] Financial amounts: ________________
  - [ ] Revenue/costs: ________________
  - [ ] Pricing: ________________
  - [ ] Commission rates: ________________

### 2.2 Check for Data Masking Rules

**In Qlik:**
- [ ] Any calculated columns with masking? Yes / No
  - Example: `IF(USERPRINCIPALNAME() = 'admin', [SSN], '***')`

**In Power BI:**
- [ ] Check for similar masking expressions: ________________
- [ ] If not found, document manual masking requirement in Power BI Desktop

---

## Section 3: Object-Level Security (OLS)

### 3.1 Identify Qlik OLS Requirements

- [ ] **Any app objects hidden by role?** Yes / No
- [ ] **Hidden sheets/visuals by section?** Yes / No
- [ ] **Drill-down restrictions?** Yes / No
  - Example: Users can only drill to REGION, not STORE

### 3.2 Verify Power BI OLS Configuration

**Power BI OLS annotation format:**
```
@@OLS_USER_RESTRICTION: [Table].[Column] = [Value]
```

- [ ] **Check model.tmdl for OLS annotations**
  - Found annotations: Count: _____
  - Example: ________________

- [ ] **If OLS not auto-generated:**
  - Document which objects need OLS: ________________
  - Manual configuration required in Power BI Desktop: Yes / No
  - Estimated effort: _____ hours

---

## Section 4: Administrative Access Verification

- [ ] **ADMIN/Super-User Role Exists**
  - Role name: ________________
  - Access level: Full (All data) / Limited (Specific regions)
  - Users assigned: ________________

- [ ] **Admin Access Scope Approved**
  - [ ] Finance admins can see all financial data
  - [ ] HR admins can see all HR data
  - [ ] Executive team: Restricted to approved metrics only
  - [ ] IT admin: Full access (audit only, no changes)

- [ ] **Audit Trail Enabled**
  - [ ] Power BI audit logging configured: Yes / No
  - [ ] Refresh history tracked: Yes / No
  - [ ] Access logs retained for: _____ months

---

## Section 5: Cross-Table Security Consistency

### 5.1 Verify Relationships Respect Security

**Scenario:** If SALES table has RLS by REGION:

- [ ] **Check related tables** (CUSTOMERS, ORDERS, PRODUCTS)
- [ ] **Confirm RLS cascades** — Filtering works across relationships
- [ ] **Test join safety** — No data leakage through joins
- [ ] **Verify hierarchy** — Region → Store → Employee is secure

**Test Query (in DAX Studio):**
```
EVALUATE FILTER(
  'Sales',
  ISBLANK('Sales'[Region]) || 'Sales'[Region] IN VALUES('User'[Allowed_Region])
)
```

- [ ] **Test ran successfully:** Yes / No
- [ ] **No unexpected records visible:** Yes / No

---

## Section 6: User and Role Assignment Validation

### 6.1 Verify Users Mapped Correctly

- [ ] **User list obtained from Qlik:** Count: _____
- [ ] **All users in Azure AD?** Yes / No
- [ ] **Any users no longer active?** Yes / No
  - If yes, mark for removal: ________________

- [ ] **Power BI role assignments match Qlik:**
  - [ ] Create Power BI security roles in target workspace
  - [ ] Assign users/groups to Power BI roles
  - [ ] Test: Log in as test user, verify filtered view

---

### 6.2 Test RLS End-to-End

**In Power BI Service:**

- [ ] **Create test users** (one per role):
  - [ ] test_sales_us@company.com
  - [ ] test_sales_emea@company.com
  - [ ] test_admin@company.com

- [ ] **Test each user's view:**
  - [ ] `test_sales_us` sees only US data: Yes / No
  - [ ] `test_sales_emea` sees only EMEA data: Yes / No
  - [ ] `test_admin` sees all data: Yes / No

- [ ] **Cross-test filters:**
  - [ ] User can see allowed regions only: Yes / No
  - [ ] User cannot see other regions (no leakage): Yes / No
  - [ ] Filtered view matches Qlik: Yes / No

---

## Section 7: Compliance and Governance

### 7.1 Data Classification Confirmation

- [ ] **Data classification assigned:**
  - [ ] PUBLIC: No PII, can be shared
  - [ ] INTERNAL: Company data, standard controls
  - [ ] CONFIDENTIAL: PII or sensitive business data, restricted access
  - [ ] HIGHLY_RESTRICTED: Executive/financial, audit trail required

- [ ] **Classification documented** in artifact manifest: Yes / No

### 7.2 Audit Trail and Logging

- [ ] **Audit events captured in Power BI:**
  - [ ] User login (USERPRINCIPALNAME): Yes / No
  - [ ] Report access (timestamp): Yes / No
  - [ ] Data refresh (status, duration): Yes / No
  - [ ] RLS rule changes: Yes / No

- [ ] **Logs retained for compliance:**
  - [ ] Retention period: _____ months (recommend 7 years for regulated)
  - [ ] Log location: ________________
  - [ ] Access restricted to: Data Steward, Compliance, IT

### 7.3 Change Control

- [ ] **RLS rules version controlled:** Yes / No
- [ ] **Git history includes security changes:** Yes / No
- [ ] **Change log document exists:** Yes / No
  - File: ________________

---

## Section 8: Known Security Gaps and Remediation

### 8.1 Identified Gaps

**Example gaps to check:**

- [ ] **Gap: OLS not fully replicated**
  - Reason: Power BI OLS annotation not available in this version
  - Workaround: Manual hiding in Power BI Desktop
  - Remediation priority: HIGH / MEDIUM / LOW

- [ ] **Gap: Dynamic dimension-based RLS**
  - Reason: Qlik allows dynamic role assignments, Power BI uses static mappings
  - Workaround: Quarterly manual role updates
  - Remediation priority: HIGH / MEDIUM / LOW

- [ ] **Gap: ________________**
  - Reason: ________________
  - Workaround: ________________
  - Remediation priority: HIGH / MEDIUM / LOW

### 8.2 Remediation Plan

- [ ] **Document all gaps:** Completed
- [ ] **Assign ownership:** Data Steward responsible for remediation
- [ ] **Set deadlines:** All gaps closed by ________________
- [ ] **Risk acceptance:** Interim workarounds approved by Compliance

---

## Section 9: Final Sign-Off

### 9.1 Reviewer Confirmation

- [ ] **Reviewer Name:** ________________
- [ ] **Review Date:** ________________
- [ ] **Reviewer Organization:** Data Steward / Compliance / Security

**Reviewer Assessment:**

- [ ] **RLS mapping is accurate:** Yes / No
- [ ] **Data security equivalent to Qlik:** Yes / No
- [ ] **No unexpected data exposure found:** Yes / No
- [ ] **Audit trail is adequate:** Yes / No
- [ ] **Ready for production deployment:** Yes / No

**If "No" to any above, document issues below:**
```
[Reviewer notes]

[Required actions before deployment]
```

### 9.2 Data Steward Sign-Off

- [ ] **Data Steward Name:** ________________
- [ ] **Approval Date:** ________________
- [ ] **Notes:** ________________

**Approved for production deployment: Yes / No**

If No, remediation required:
- [ ] Issue 1: ________________
- [ ] Issue 2: ________________
- [ ] Target resolution date: ________________

---

## Section 10: Post-Deployment Verification

### 10.1 Production Validation (After Deployment)

*Perform these checks one week after production deployment:*

- [ ] **RLS functioning correctly** in production: Yes / No
- [ ] **No unauthorized access reports:** Yes / No
- [ ] **Audit logs showing proper filtering:** Yes / No
- [ ] **User complaints or issues:** None / List: ________________

### 10.2 Ongoing Monitoring

- [ ] **Monthly audit trail review:** Scheduled for ________________
- [ ] **Quarterly role recertification:** Scheduled for ________________
- [ ] **Annual security assessment:** Scheduled for ________________

---

## Appendix A: Common RLS Patterns

### Pattern 1: Regional Filtering
```dax
= CALCULATE(
    [Msr_Sales],
    FILTER('Sales', 'Sales'[Region] IN VALUES('User'[Assigned_Region]))
)
```

### Pattern 2: Department Filtering
```dax
= CALCULATE(
    [Msr_HR_Data],
    FILTER('HRData', 'HRData'[Department] = USERPRINCIPALNAME())
)
```

### Pattern 3: Hierarchical (Region → Store → Employee)
```dax
= CALCULATE(
    [Msr_Sales],
    FILTER('Sales', 'Sales'[Store_ID] IN VALUES('StoreAllocation'[Store_ID]))
)
```

---

## Appendix B: Reference Links

- [Power BI RLS Documentation](https://learn.microsoft.com/power-bi/enterprise/service-admin-rls)
- [Azure AD Integration](https://learn.microsoft.com/azure/active-directory/)
- [USERPRINCIPALNAME Function](https://learn.microsoft.com/dax/userprincipalname-function)
- [Qlik Security Best Practices](https://help.qlik.com/en-US/sense/November2024/Content/Sense_QlikSense/ManagingDataAccess/security.htm)

---

**Checklist Version:** 1.0  
**Date:** 2026-06-26  
**Next Review:** Post-Phase 3 implementation (estimated 2026-08-26)

