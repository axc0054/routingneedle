# Routing Test Fixture T-19

You are routing an intake document to its canonical vault location under `02_Domains/`. The vault separates legal case evidence (`02_Domains/Legal/`) from operational parenting records (`02_Domains/Parenting/`). The `Parenting/Lorelai/` branch is organized by developmental stage:

- `01_Infant` — Fall 2020 – Spring 2022
- `02_Toddler` — Spring 2022 – Fall 2025
- `03_Elementary` — Fall 2025 onward

Subcategories within each stage include: `Disputes/`, `Communications/`, `Development/`, `Behavioral/`, `Visitation/`, `Media/`.

**Document being routed:**

```
title: "master dispute log draft"
file_type: converted_pdf
domain: parenting
sensitivity_class: local_parenting_sensitive
source_original_path: ".../master_dispute_log_draft.pdf"
```

**Document excerpt:**

> Master Dispute Log — Alex Camacho (Working Draft)
> For Internal Use — Not Final
>
> CURRENT FINANCIAL CONTEXT
> Income: $200/day × 5 days/week = $1,000/week, approx $4,000/month gross
> Hard Monthly Expenses: Rent $1,100 ...
>
> [Contains dispute entries spanning multiple dates and parenting events]

---

## Challenge

**Q1:** What vault domain does this document belong to?

**Q2:** The document is marked "Working Draft" and "For Internal Use — Not Final." Does draft status affect domain assignment or storage path?

**Q3:** The document spans multiple dispute entries across what appears to be more than one developmental stage. How should the stage be assigned when content is multi-stage?

**Q4:** What is the canonical vault path?

---
