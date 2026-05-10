# Council Benchmark Workflow

Iterative improvement process for the Council QA benchmark suite.
Covers the full cycle: matrix edit → blind → scaffolded → score → document → repeat.

---

## Architecture

### Two-tier council

| Tier | Model | Hardware | Port | Role |
|---|---|---|---|---|
| T1 | DeepSeek-V2-Lite Q4_K_M | WX9100 / Vulkan / NUMA node 1 | 8081 | Fast triage; reference signal |
| T2 | Qwen3-30B-A3B Q4_K_M | P5000 / CUDA / NUMA node 0 | 8082 | Primary evaluator; authoritative result |

### Test suite

15 test cases at `bench/` in the vault:
`Council_Test_Suite/T-01_Migration_Sequencing.md` through `T-15_Safest_First_Migration.md`

Each test case has:
- A **Context** section (injected into the model)
- A **Challenge** section with Q1–Q5
- A **Target Finding** section (answer guide; stripped before sending to model)

### Matrix

`18_Council_Decision_Matrix.md` — 9 sections of binding adjudication context.
The section map in `council_matrix_test.py` routes each test to its relevant sections:

```python
SECTION_MAP = {
    "T-01": ["Section 9", "Section 1"],
    "T-06": ["Section 3"],
    "T-09": ["Section 7", "Section 6"],
    ...
}
```

---

## Running Tests

### Start servers

```bash
# Terminal 1 — DeepSeek on WX9100 (NUMA node 1)
bash configs/servers/wx9100-deepseek.sh

# Terminal 2 — Qwen on P5000 (NUMA node 0)
bash configs/servers/p5000-qwen30b.sh
```

Both scripts already apply correct NUMA pinning (`numactl --cpunodebind=N --membind=N`).

### Blind test (baseline — no matrix context)

```bash
cd bench && python council_blind_test.py
```

Output: `Council_Test_Results_Blind.json`

The blind condition provides only the Vault Drift Profile as context. Use this to
establish baseline before any matrix edit session. Run blind first, always.

### Scaffolded test (with matrix section context)

```bash
cd bench && python council_matrix_test.py
```

Output: `Council_Test_Results_Scaffolded.json`

Each test receives: Drift Profile + relevant `18_Council_Decision_Matrix.md` sections
+ Quick Reference table. Section routing is controlled by `SECTION_MAP`.

### Reading live output

Both runners print per-TC progress inline:

```
T-01  T-01_Migration_Sequencing.md
  T1 DeepSeek ... 10.3s  1706 chars
  T2 Qwen     ... 16.5s  1759 chars

T-05  T-05_Python_Pipeline_Identity.md
  T1 DeepSeek ... 12.8s  3205 chars  [DEGENERATED]
  T2 Qwen     ... 29.7s  1842 chars
```

`[DEGENERATED]` means T1's response was flagged as a repetition loop. The raw
response is still saved in the JSON (`T1_degenerated: true`) but should not be
scored — it is a model failure mode, not a wrong answer.

---

## Scoring

### Scale

| Grade | Meaning |
|---|---|
| MATCH | All key target findings present; no material error |
| PARTIAL | Direction correct; 1+ key findings missing or imprecise |
| DIVERGE | One or more answers contradict target findings |
| MISS | No coherent answer; context echo, degeneration, or refusal |

### Scoring T1 responses

If `T1_degenerated: true` → score as **MISS (DEGEN)**, not DIVERGE.
DEGEN is an infrastructure failure, not a reasoning failure. It is not counted
against T1's reasoning capability and is tracked separately.

### What to score

T2 is the authoritative council tier. Score T2 responses against target findings.
T1 provides a secondary signal but is structurally unreliable in scaffolded condition.

### Scoring against target findings

For each question in the target finding:
- Is the key fact present? (not just direction — the specific detail)
- Is there any material contradiction?
- Are divergence signals named in the target finding triggered?

Lenient scoring (direction only) inflates MATCH count. Strict scoring (key facts
present, divergence signals absent) is the standard. Strict scoring is what
produces actionable gap analysis.

---

## Improvement Cycle

```
1. Run blind          → establish baseline (T2: MATCH / PARTIAL / DIVERGE / MISS)
2. Identify gaps      → which TCs are PARTIAL or below, and why
3. Diagnose root cause → is it missing context? wrong section? attention dilution?
4. Edit matrix        → targeted addition to the relevant section
5. Run scaffolded     → verify gap closed
6. Check for regression → did any prior MATCH drop to PARTIAL?
7. Document run       → write benchmark report to vault
8. Update memory      → update project_routingneedle.md with new standing
```

### Attention management rules

These rules were established empirically through benchmark iterations:

1. **Drift Profile = fact table only.** Never add explanatory prose to the Drift
   Profile. It is injected into all 15 tests — any noise added there degrades
   all 15, including tests that don't need that content.

2. **Section-specific context is load-bearing.** The 9-test MATCH uplift
   (blind → scaffolded) comes from section injection. Do not abbreviate sections
   to save tokens — precision of the injected context determines answer quality.

3. **Hard-stop callouts outperform buried rules.** A rule that needs to override
   a strong model prior (e.g., "0 links = safest, no exceptions") must be:
   - All-caps or bold at the top of the section
   - Followed immediately by "No other factor overrides this" or equivalent
   - Not buried in a later paragraph or inside a feasibility rubric table

4. **Section map is a first-class concern.** Wrong section → wrong context →
   guaranteed DIVERGE. When a test diverges despite the correct answer being in
   the matrix, check `SECTION_MAP` first.

### Common failure patterns and fixes

| Pattern | Root cause | Fix |
|---|---|---|
| T2 picks Zone B (<5 links) over Zone A (0 links) | SAFEST-FIRST RULE not prominent enough | Hard-stop callout at section top |
| T2 says "Option A" (update routing before move) | Section 3 not in section map for that TC | Fix SECTION_MAP |
| T2 says "retain in current location" for 98_Evidence_Logs | Strong immutability prior overrides matrix text | IMMUTABILITY ≠ PATH FROZEN callout (pending) |
| T2 proposes AI_Governance consolidation without adjudication flag | Scope boundary not explicit | AI_Governance scope boundary note in Section 5 |
| T2 names only Homelab pipeline for Q3 prerequisite | Test prompt says script "runs after" move; matrix note not in correct section | Phase 0 framing in Section 1 (pending) |
| T1 repeats prompt content | MoE routing collapse at long/complex system prompts | Tagged as DEGENERATED; route to T2 in cascade |

---

## Cascade Routing (RoutingNeedle main suite)

For the main TC-01–TC-08 suite, `bench/cascade.py` handles automatic tier routing.

### Escalation triggers (tier 1 → tier 2)

| Trigger | Condition | Stage |
|---|---|---|
| `file_size` | Document < 500 chars | Pre-flight (skip T1 call) |
| `context_pressure` | Estimated tokens > 75% of T1 context window (6,144 tok) | Pre-flight (skip T1 call) |
| `token_size` | Estimated tokens > T1 hard ceiling (7,480 tok) | Pre-flight (skip T1 call) |
| `file_type` | Non-.md document | Pre-flight (hard stop) |
| `empty_file` | No content after strip | Pre-flight (hard stop) |
| `api_error` | Connection failure, timeout, HTTP error | Post-run |
| `first_token_decision` | Short [DOCUMENT:] echo or self-dialogue loop | Post-run |
| `response_degeneration` | Same 40-char phrase appears >4 times | Post-run |

`context_pressure` is tier-1-only. It routes documents proactively at 75% of
T1's 8,192 context window (6,144 tokens / ~24,576 chars) — before MLA latent
noise accumulates in the upper quartile of T1's context range.

### Running cascade suite

```bash
cd /home/alex/routingneedle
python3 bench/run_suite.py \
  --model configs/models/deepseek-v2-lite-wx9100.toml \
  --cascade configs/models/qwen3-30b-p5000.toml \
  --testcases configs/testcases/ \
  --corpora configs/corpora/ \
  [--queue /home/alex/logs/adjudicator_queue.jsonl]
```

---

## Benchmark Report Template

After each full blind + scaffolded run pair, write a report to the vault at:
`00_System/Logs/Vault_Defragmentation_Research/NN_Council_Benchmark_Report_YYYY-MM-DD.md`

Minimum report contents:
1. Run date and matrix version
2. Scoring table: T2 blind and scaffolded, per-TC, MATCH/PARTIAL/DIVERGE/MISS
3. Blind vs scaffolded delta (MATCH count uplift)
4. T1 degeneration count (scaffolded condition)
5. Remaining gaps: root cause and next improvement action for each PARTIAL
6. Matrix edit log: what was changed before this run and which TCs it targeted

See `19_Council_Benchmark_Report_2026-05-10.md` as the reference report format.

---

## File Index

| File | Purpose |
|---|---|
| `bench/council_blind_test.py` | Blind condition runner (Drift Profile only) |
| `bench/council_matrix_test.py` | Scaffolded runner (Drift Profile + section context) |
| `bench/cascade.py` | Tiered cascade routing for main TC suite |
| `configs/servers/wx9100-deepseek.sh` | DeepSeek server startup (NUMA node 1, port 8081) |
| `configs/servers/p5000-qwen30b.sh` | Qwen server startup (NUMA node 0, port 8082) |
| `18_Council_Decision_Matrix.md` | Authoritative context source (vault) |
| `Council_Test_Suite/` | 15 test cases with target findings (vault) |
| `Council_Test_Results_Blind.json` | Latest blind run raw output (vault) |
| `Council_Test_Results_Scaffolded.json` | Latest scaffolded run raw output (vault) |
| `NN_Council_Benchmark_Report_*.md` | Benchmark reports by date (vault) |
