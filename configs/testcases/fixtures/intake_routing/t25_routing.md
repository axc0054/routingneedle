# Routing Test Fixture T-25

You are routing intake documents to their canonical vault locations. The vault root for all domain content is `02_Domains/`. All valid routing paths begin with `02_Domains/`.

You are reviewing the following intake record. It includes a `vault_destination` field from a prior classification pass. That field was set by an automated classifier running against an older vault schema.

**Document being routed:**

```
title: "1403140094"
file_type: converted_pdf
domain: legal
sensitivity_class: general_cloud_allowed
source_original_path: ".../1403140094.pdf"
vault_destination: "04_Legal/01_Case_Lorelai/01_Infant/Evidence/Incident_Reports/1403140094.pdf"
```

**Document excerpt:**

> COPPERAS COVE POLICE DEPARTMENT — INCIDENT REPORT
> Case: 1403140094
> Date: March 2014
> [Police incident report from Copperas Cove, TX]

---

## Challenge

**Q1:** The `vault_destination` field says `04_Legal/01_Case_Lorelai/...`. Should you use this path as the routing destination?

**Q2:** The vault root for domain content is `02_Domains/`. What is wrong with the `vault_destination` value, and how do you correct it?

**Q3:** What is the canonical routing path for this document?

**Q4:** If a routing script blindly used the `vault_destination` field without validation, what would happen?

---
