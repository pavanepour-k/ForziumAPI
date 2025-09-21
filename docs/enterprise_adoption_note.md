# Enterprise Adoption Scope Note

## Purpose

Large enterprises frequently require additional governance measures before software can ship to production.  This note clarifies that the ForziumAPI performance validation program **does not** cover organization-specific security, compliance, or operational readiness processes.  Those responsibilities remain with the adopting organization and must be satisfied using their internal tooling and review gates.

## Out-of-Scope Processes

| Domain | Typical Owner | Expectation |
| --- | --- | --- |
| Software Bill of Materials (SBOM) generation and attestation | Security / Compliance Engineering | Produce SBOMs using the organization’s approved tooling (e.g., Syft, CycloneDX) and attach them to the release package. |
| License compliance scanning and obligations tracking | Open Source Program Office (OSPO) | Execute existing license scanners, review obligations (copyleft, notices), and archive reports alongside standard compliance evidence. |
| Secrets management and rotation | Platform / DevOps | Confirm secrets are provisioned through the enterprise vault solution and document rotation cadences. |
| Audit logging, retention, and evidence trails | Compliance / Internal Audit | Integrate ForziumAPI deployments with centralized audit pipelines and ensure retention windows satisfy regulatory requirements. |
| Backup, disaster recovery, and business continuity exercises | Site Reliability Engineering (SRE) | Align ForziumAPI workloads with the enterprise DR plan, including restore tests and recovery point / time objectives (RPO/RTO). |
| Vulnerability management (SAST/DAST, container scans) | Security Operations | Schedule scans per enterprise policy and track remediation in the standard risk register. |

## Enterprise Readiness Checklist

> Complete this checklist prior to production rollout.  Each item must be satisfied using the organization’s canonical processes and recorded in the relevant governance system (e.g., GRC portal, change management tracker).

- [ ] SBOM generated, reviewed, and archived according to enterprise policy.
- [ ] License scan completed with any obligations or exceptions documented.
- [ ] Secrets managed through approved vault solution with documented rotation schedule.
- [ ] Deployment integrated with centralized audit logging and retention controls.
- [ ] Backup/DR plan validated, including restore drills meeting RPO/RTO commitments.
- [ ] Vulnerability scans executed (SAST, DAST, container) with remediation tracked to closure.
- [ ] Sign-off captured from Security, Compliance, and SRE stakeholders indicating the above processes are owned outside the ForziumAPI validation program.

## Communication Template

Share the following statement with governance stakeholders to clarify scope boundaries:

> “The ForziumAPI validation initiative covers functional, performance, and observability guarantees for the runtime.  Enterprise adoption controls—SBOM, license, secrets, audit, DR, and vulnerability management—are handled by our existing corporate processes.  We have completed the Enterprise Readiness Checklist to document ownership and completion status.”

Archiving this document with release artifacts ensures downstream teams understand the separation of responsibilities and can audit completion of enterprise-mandated controls.