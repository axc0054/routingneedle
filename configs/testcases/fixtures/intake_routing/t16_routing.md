# Routing Test Fixture T-16

You are routing an intake document to its canonical location in a personal knowledge vault. The vault uses `02_Domains/` as the root for all domain content. The active legal case in this vault is `02_Domains/Legal/01_Case_Lorelai/`, organized by the subject's developmental stage at the time of the evidence:

- `01_Infant` — Fall 2020 through Spring 2022
- `02_Toddler` — Spring 2022 through Fall 2025
- `03_Elementary` — Fall 2025 onward

Evidence subfolders within each stage include: `Legal_Filings/`, `Incident_Reports/`, `Communications/`, `Financial_Obligations/`, `Visitation_Records/`, `Medical/`, `Education/`.

**Document being routed:**

```
title: "13 2300"
file_type: converted_pdf
domain: legal
sensitivity_class: general_cloud_allowed
source_original_path: "/home/alex/local_intake_raw/classified/13-2300.pdf"
```

**Document excerpt:**

> COPPERAS COVE POLICE DEPARTMENT — MISDEMEANOR REPORT
> Case 13-2300
> Date Occurred: 07/03/14–07/04/14 · Offense: BURG VEH (30.04-001PC)
> Location: Residence, 909 Saratoga Ln, Copperas Cove, TX 76522
> Victim: Petty, Brandy Nicholl — DOB 08/23/1982
> Prepared By: Hunter, Douglas Jr — 07/05/2014

---

## Challenge

**Q1:** What vault domain does this document belong to, and why?

**Q2:** The incident date is July 2014 — approximately six years before the active legal case subject (Lorelai) was born. Does this affect domain assignment? What stage folder, if any, should this file land in?

**Q3:** What is the full canonical vault path for this document?

**Q4:** Does the `sensitivity_class: general_cloud_allowed` affect where the document is stored, or only how it is processed?

---
