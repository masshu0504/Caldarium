# Security Checklist & Action Plan
**Last Updated**: 2025-10-10
**Status**: Aligned with Dependency Security Register

---

## Risk Summary

This is a high-level overview of the dependency risk assessment. For full details, see the `dependency_security_register.md`.

### Low Risk Dependencies (5)
* `pdfplumber` (0.9.0)
* `great-expectations` (0.18.12)
* `pandas` (2.2.2)
* `jpype1` (1.5.0)
* `postgres` (15.7)

### Medium Risk Dependencies (4)
* `numpy` (1.26.4) - Patched, but has a CVE history.
* `minio` (RELEASE.2025-10-08...) - **AGPL license review needed.**
* `label-studio` (1.13.0) - Network-facing service.
* `camelot-py` (0.11.0) - Low maintenance activity.

### High Risk Dependencies (1)
* **`PyPDF2` (3.0.1)** - **Vulnerable to CVE-2023-36464. Immediate update required.**

---

##  actionable tasks Action Items

This plan is prioritized based on the findings in the security register.

### Immediate Priority (This Week)
- [ ] **Update `PyPDF2`**: Upgrade from `3.0.1` to a patched version (`>=3.12.0`) to fix the critical vulnerability.
- [ ] **Review AGPL-3.0 License**: Discuss the implications of using MinIO with the project lead.

### Next Steps (This Month)
- [ ] **Implement Automated Scanning**: Integrate a tool like `pip-audit` to catch these issues automatically in the future.
- [ ] **Monitor `camelot-py`**: Evaluate replacing this dependency if its maintenance remains low.
- [ ] **Document Security Procedures**: Create a formal process for responding to new vulnerabilities.

---

## Ongoing Monitoring

This schedule ensures the project remains secure over time.

### Weekly
- [ ] Check for security advisories for high and medium-risk dependencies.

### Monthly
- [ ] Review all dependency versions and update the security register.
- [ ] Monitor dependency update release notes.

### Quarterly
- [ ] Conduct a full security reassessment of all dependencies.
- [ ] Perform a license compliance review.