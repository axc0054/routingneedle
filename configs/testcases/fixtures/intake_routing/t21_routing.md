# Routing Test Fixture T-21

You are routing an intake document to its canonical vault location under `02_Domains/`. The vault has two domains relevant to this document:

- `02_Domains/Legal/01_Case_Lorelai/[stage]/Evidence/Legal_Filings/` — legal case evidence submitted or intended for court
- `02_Domains/Professional_Development/04_Evidence/source_artifacts/` — professional credentials and career source documents

**Document being routed:**

```
title: "AlexCamachoResumePM 04"
file_type: converted_docx
domain: legal
sensitivity_class: general_cloud_allowed
source_original_path: ".../AlexCamachoResumePM_04.docx"
intake_bench_destination: Cloud_Eligible
```

**Note:** The classifier assigned `domain: legal` to this document. The source file was stored in the intake folder alongside legal evidence files.

**Document excerpt:**

> Alex Camacho — Austin, TX · linkedin.com/in/alex-camacho-471a016
>
> PROFESSIONAL SUMMARY
> Seasoned IT & Program Manager driving ERP, SOX, and governance transformations across manufacturing and regulated industries. Combines operational depth with compliance rigor to deliver audit-ready modernization initiatives. Experienced in program delivery, Zero Trust architecture, and multi-site ERP deployments.
>
> CORE COMPETENCIES
> ERP / Transformation: SAP S/4HANA, SAP Governance, Segregation of Duties, Audit-Ready Deployments
> Compliance & Governance: SOX, ITAR, Data Retention, Regulatory Readiness, Control Automation
> Program Leadership: Program & Portfolio Management, Change Management, Stakeholder Engagement

---

## Challenge

**Q1:** The classifier tagged this document `domain: legal`. Does the classifier's domain tag determine the vault routing path?

**Q2:** What are the two plausible routing destinations for this document, and what is the risk of each?

**Q3:** Should this document be auto-routed, or should it be held for human adjudication? Why?

**Q4:** If you were to route it without adjudication, which path would you choose, and what would you record to make the routing decision auditable?

---
