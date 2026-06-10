# Routing Test Fixture T-20

You are routing an intake document to its canonical vault location under `02_Domains/`. The Legal domain contains two separate case tracks:

- `02_Domains/Legal/01_Case_Lorelai/` — the active family law case involving Lorelai
- `02_Domains/Legal/02_Cases/02_Case_Estate_Planning/` — estate planning documents for Alex Camacho

Each case track has its own subfolder structure. `01_Raw/` within a case track holds unprocessed source documents.

**Document being routed:**

```
title: "Will   Testament   AC"
file_type: converted_docx
domain: legal
sensitivity_class: legal_strict
source_original_path: ".../Will - Testament - AC.docx"
```

**Document excerpt:**

> LAST WILL AND TESTAMENT OF ALEJANDRO CAMACHO JR.
>
> I, Alejandro Camacho, of Pflugerville, Texas, revoke my former Wills and Codicils and declare this to be my Last Will and Testament.
>
> ARTICLE I — IDENTIFICATION OF FAMILY
> I am not currently married to anyone.
> The name of my child is Lorelai Camacho-Guerra. All references in this Will to "my children" are references to the above-named child.
>
> ARTICLE II — PAYMENT OF DEBTS AND EXPENSES
> I direct that my just debts, funeral expenses and expenses of last illness be first paid from my estate.

---

## Challenge

**Q1:** This document names Lorelai as the sole heir. Does that make it part of the `01_Case_Lorelai` case track, or does it belong elsewhere?

**Q2:** What is the correct case track for this document, and why?

**Q3:** What is the canonical vault path?

**Q4:** The document has `sensitivity_class: legal_strict`. Does this affect the path within `02_Domains/Legal/`?

---
