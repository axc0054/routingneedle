# Routing Test Fixture T-22

You are routing an intake document to its canonical vault location under `02_Domains/`. Two domains are plausible:

- `02_Domains/Professional_Development/` — career knowledge, professional reference material, program delivery methodologies used in Alex Camacho's work history. Subdirectories include `01_Inventory/` (reference documents, articles, templates).
- `02_Domains/Capital_Grade_Governance/` — governance frameworks, compendiums, and doctrine artifacts related to the Capital-Grade Governance (CGG) project. This domain holds formal governance methodology, not general professional reference.

**Document being routed:**

```
title: "Analytics ERP Team Structure"
file_type: converted_docx
domain: framework
sensitivity_class: general_cloud_allowed
source_original_path: ".../Analytics_ERP_Team_Structure.docx"
```

**Document excerpt:**

> Analytics & ERP Transformation — Multi-Site / Multi-Region Team Structure
>
> Program Context: This team structure represents a scaled, multi-site, multi-region ERP & Analytics transformation program with embedded SOX compliance, data governance, and operational readiness. The delivery model aligns Implementation Partner, IT Delivery, and Business & Process Owners, with strong emphasis on Analytics for Supply Chain, Manufacturing, and FP&A.
>
> Key Principles:
> — Clear accountability across partner, IT, and business domains
> — Embedded SOX and compliance from design through hypercare
> — Strong data governance and analytics integration at every layer
> — Structured delivery for wave-based rollouts and regional enablement

---

## Challenge

**Q1:** The classifier tagged this `domain: framework`. Does that mean it belongs in `Capital_Grade_Governance/`?

**Q2:** What distinguishes a professional reference document from a Capital_Grade_Governance artifact?

**Q3:** What is the canonical vault path?

---
