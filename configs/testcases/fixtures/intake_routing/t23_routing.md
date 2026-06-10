# Routing Test Fixture T-23

You are routing an intake document to its canonical vault location under `02_Domains/`. Within the Legal domain, two paths are plausible:

- `02_Domains/Legal/01_Case_Lorelai/[stage]/Evidence/` — evidence submitted or intended for submission in the active custody case
- `02_Domains/Legal/03_Reference/` — legal reference material: statutes, procedural rules, general legal doctrine not specific to any individual case

**Document being routed:**

```
title: "trcp-20150901"
file_type: converted_pdf
domain: legal
sensitivity_class: general_cloud_allowed
source_original_path: ".../trcp-20150901.pdf"
extraction_quality: clean
```

**Document excerpt (125,519 words):**

> Texas Rules of Civil Procedure
>
> PART I — GENERAL RULES
> RULE 1. OBJECTIVE OF RULES
> RULE 2. SCOPE OF RULES
> ...
> [Full 2015 edition of the Texas Rules of Civil Procedure — all parts, all rules]

---

## Challenge

**Q1:** Does this document belong in the Lorelai case evidence track or in Legal reference? What is the deciding factor?

**Q2:** The document is the 2015 edition of the TRCP, but the active case spans 2020–present. Does the edition year matter for routing?

**Q3:** What is the canonical vault path?

**Q4:** This document is 125,519 words — the largest document in the intake batch. Does size affect routing?

---
