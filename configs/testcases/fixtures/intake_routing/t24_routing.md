# Routing Test Fixture T-24

You are routing an intake document to its canonical vault location under `02_Domains/`. Two domains are plausible:

- `02_Domains/AI_Operations/Claude/` — operational records of Claude usage: prompts, results, build notes, projects using Claude as a tool
- `02_Domains/Capital_Grade_Governance/` — the CGG project and its governance artifacts, compendiums, and process accountability records created specifically within the CGG project lifecycle

**Document being routed:**

```
title: "Claude AI Build Log"
file_type: converted_pdf
domain: professional_development
sensitivity_class: general_cloud_allowed
source_original_path: ".../Claude_AI_Build_Log.pdf"
```

**Document excerpt:**

> Claude AI Build Log
>
> Purpose: This log records each instance where Claude is used to analyze governance artifacts.
> It preserves: Intent · Context · Constraints · Traceability
> This log is not an analysis artifact. It is a process accountability record.
>
> Build Entry
> Build ID: CGG-AI-CLAUDE-###
> build_purpose: leakage_detection | targeted_stress_test
> framework_version: <canonical_version>
> preamble_applied: AI_Leakage_Stress_Test_Preamble.md
>
> Operating Rules:
> — Every Claude run must have a log entry
> — Builds are immutable once recorded
> — Outputs without a log entry are invalid
> — Logs do not evaluate results — Logs exist independently of findings
>
> Audit and Review: This log supports AI governance audits, ISO 42001 style review,
> post-incident reconstruction, and executive accountability.

---

## Challenge

**Q1:** The classifier tagged this `domain: professional_development`. Does that tag route it to `Professional_Development/`?

**Q2:** This document uses "CGG-AI-CLAUDE-###" build IDs and references the `AI_Leakage_Stress_Test_Preamble.md`. What does that tell you about the document's project affiliation?

**Q3:** Between `AI_Operations/Claude/` and `Capital_Grade_Governance/`, which is the correct home, and why?

**Q4:** What is the canonical vault path?

---
