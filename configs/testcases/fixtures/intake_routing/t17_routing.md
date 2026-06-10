# Routing Test Fixture T-17

You are routing an intake document to its canonical location in a personal knowledge vault. The vault uses `02_Domains/` as the root for all domain content. Lorelai was born Fall 2020. Developmental stages:

- `01_Infant` — Fall 2020 through Spring 2022
- `02_Toddler` — Spring 2022 through Fall 2025
- `03_Elementary` — Fall 2025 onward

The active case folder is `02_Domains/Legal/01_Case_Lorelai/[stage]/Evidence/[category]/`. The court filing subfolder is `Legal_Filings/`.

**Document being routed:**

```
title: "10.14.2021 Signed order in suit affecting the P-C relationship"
file_type: converted_pdf
domain: legal
sensitivity_class: legal_strict
source_original_path: "...10.14.2021 Signed order in suit affecting the P-C  relationship.pdf"
```

**Document excerpt:**

> SIGNED ORDER IN SUIT AFFECTING THE PARENT-CHILD RELATIONSHIP
> Filed: October 14, 2021
> Court: [Texas family court]
> Parties: [Petitioner] and [Respondent]
> RE: Possession and Access — subject child Lorelai
> Standard possession order established. First, third, and fifth weekends, plus Thursday possession.

---

## Challenge

**Q1:** Which stage folder does this document belong in, and how do you determine that?

**Q2:** Which evidence subcategory within the stage folder applies?

**Q3:** What is the full canonical vault path?

**Q4:** The `sensitivity_class` is `legal_strict`. What does this mean for storage location vs. processing pipeline?

---
