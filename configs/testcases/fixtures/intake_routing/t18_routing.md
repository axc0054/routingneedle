# Routing Test Fixture T-18

You are routing an intake document to its canonical location in a personal knowledge vault. The vault has two domains that can both relate to Lorelai:

- `02_Domains/Legal/01_Case_Lorelai/` — legal case evidence: court filings, orders, incident reports, communications used as exhibits
- `02_Domains/Parenting/Lorelai/` — operational parenting records: schedules, behavioral logs, development records, day-to-day parenting activity

Lorelai developmental stages: `01_Infant` (Fall 2020–Spring 2022), `02_Toddler` (Spring 2022–Fall 2025), `03_Elementary` (Fall 2025 onward).

**Document being routed:**

```
title: "Visitation 2025 2026 FullYear"
file_type: converted_pdf
domain: parenting
sensitivity_class: local_parenting_sensitive
source_original_path: ".../Visitation_2025-2026_FullYear.pdf"
```

**Document excerpt:**

> Visitation Schedule — 2025–2026 School Year
>
> This schedule is based on the October 14, 2021 court order (1st, 3rd, and 5th weekends, plus Thursdays) and the 2025–2026 Killeen ISD school calendar. Exchanges occur at the start and end of the school day during the school year. Holidays and student breaks override regular weekends where applicable.
>
> August 2025
> Aug 13 (Wed) — First day of school, school-year schedule begins
> Aug 15–18 (Fri–Mon) — 3rd weekend possession
> ...

---

## Challenge

**Q1:** Does this document belong in `02_Domains/Legal/` or `02_Domains/Parenting/`? What is the deciding factor?

**Q2:** The document references the October 14, 2021 court order. Does that legal origin change the domain assignment?

**Q3:** Which stage folder applies, and which subcategory within that stage?

**Q4:** What is the full canonical vault path?

---
