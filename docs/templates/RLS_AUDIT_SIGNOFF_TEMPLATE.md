# RLS Audit Sign-Off Template

## App Metadata

- Wave:
- App ID:
- App Name:
- Migration Profile:
- Business Owner:
- Migration Lead:
- Security Reviewer:
- Release Manager:
- Environment:
- Review Date:

---

## Required Artifacts

- [ ] `security/security_extract.csv` reviewed
- [ ] Target gate report reviewed
- [ ] Migration report reviewed
- [ ] Business intent confirmed with owner

Artifact paths:

- Security extract:
- Gate report JSON:
- Migration report JSON:

---

## Source Security Review

- Section Access present:
- Reduction fields identified:
- Omit fields identified:
- Special exception roles identified:

Notes:

---

## Generated RLS Review

- Expected roles present:
- Expected tables present:
- Filter expressions verified:
- Unexpected broad access found:

Notes:

---

## Business Validation

- Expected audience behavior confirmed:
- Known deviations accepted:
- Follow-up actions required:

Notes:

---

## Decision

- Decision: `Approved` / `Approved with follow-up` / `Rejected`
- Blocking issues:
- Remediation ticket(s):
- Follow-up due date:

---

## Approvals

- Migration Lead:
- Security Reviewer:
- Business Owner:
- Release Manager:

---

## Final Promotion Recommendation

- [ ] Ready for next environment
- [ ] Hold for remediation
