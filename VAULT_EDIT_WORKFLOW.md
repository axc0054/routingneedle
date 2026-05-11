# Vault Edit Workflow — Council Dev/Test/Prod Protocol

Defines the promotion chain for council-driven vault restructure edits.
Companion to `COUNCIL_BENCHMARK_WORKFLOW.md` (council QA benchmarking).

---

## Environment

Three git worktrees of `github.com/axc0054/obsidian-vault`:

| Path | Branch | Obsidian Sync | n8n Intake | Council Writes |
|------|--------|--------------|------------|----------------|
| `/home/alex/Documents/Remote Access Vault` | `prod` | **Yes** | **Yes** | **Never** |
| `/home/alex/vault-test` | `test` | Optional | No | **Never** |
| `/home/alex/vault-dev` | `dev` | No | No | **Yes — only here** |

## Role Map

| Actor | Scope | Access |
|-------|-------|--------|
| **n8n pipeline** | Ingests new documents | Read/write `prod` only |
| **Council (T2/Qwen)** | Proposes vault restructure edits | Write `dev` only; read `prod` for benchmarks |
| **Claude (adjudicator)** | Reviews council's `dev` diff; promotes or rejects | Read `dev`; write `test` |
| **User (final authority)** | Reviews `test` in Obsidian; promotes to `prod` | Merge `test` → `prod` |

---

## Rule: Council Only Touches Dev

Any script that performs filesystem mutations (create, move, rename, delete) on
vault content **must** use the dev path constant:

```python
VAULT_DEV = Path("/home/alex/vault-dev")
```

**Benchmark runners are exempt** — they read the authoritative test suite and
decision matrix from `prod` (read-only) and write result JSON to
`prod/00_System/Logs/` (system logs, not content edits). This is by design:
the matrix and test suite are governance documents that live in `prod`.

A runtime guard is added to any edit-class script:

```python
import os
from pathlib import Path

VAULT_DEV = Path("/home/alex/vault-dev")

def _assert_dev_target(path: Path) -> None:
    """Abort if a mutation is attempted outside the dev worktree."""
    resolved = path.resolve()
    if not str(resolved).startswith(str(VAULT_DEV.resolve())):
        raise RuntimeError(
            f"SAFETY ABORT: mutation target {resolved} is outside vault-dev.\n"
            f"Council scripts must only write to {VAULT_DEV}"
        )
```

---

## Ingestion Flow (new documents)

New content always enters through `prod`. The n8n pipeline is unaware of the
dev/test branches and should never be pointed elsewhere.

```
User drops file → prod/01_Inbox/ → n8n pipeline → routed to prod zone
```

`01_Inbox/` is the safe boundary: files in transit have not been routed to
zones yet and do not conflict with any restructuring work in `dev`.

---

## Council Edit Session Flow

```
1. SYNC       git -C /home/alex/vault-dev merge prod
              (picks up any new files ingested since last session)

2. COUNCIL    council edit scripts run against vault-dev only
              → propose moves, renames, new files
              → each operation committed to dev branch

3. REVIEW     Claude diffs dev against test
              → evaluates each change: governance rules, link integrity,
                chain-of-custody, wikilink blast radius
              → APPROVE / REJECT / ESCALATE TO USER

4. PROMOTE    approved changes cherry-picked or merged to test
              git -C /home/alex/vault-test merge dev   (or cherry-pick)

5. INSPECT    user opens vault-test in Obsidian; reviews diff visually
              git diff test..prod -- "*.md" | less

6. MERGE      user merges test → prod after final approval
              git -C "/home/alex/Documents/Remote Access Vault" merge test
              git push origin prod

7. PROPAGATE  push updated prod/test/dev refs
              git push origin prod test dev
```

---

## Merge Strategy

| Transition | Method | Notes |
|------------|--------|-------|
| `prod` → `dev` (sync) | `merge prod` | Before each council session; fast-forward if no conflicts |
| `dev` → `test` (promote) | `merge dev` or `cherry-pick` | Cherry-pick for selective promotion of reviewed commits |
| `test` → `prod` (release) | `merge test` | Only after user visual review in Obsidian |

If a conflict arises on `prod` → `dev` sync (new ingested file landed in a path
the council is restructuring), resolve in `dev` — `prod` is never rebased.

---

## Guard Rails

1. **CGG Lifecycle Validator** — pre-commit hook on the vault repo; blocks any
   commit with CGG governance violations. Runs on all three branches.

2. **Claude review gate** — no change moves from `dev` to `test` without Claude
   evaluating it against: governance rules, wikilink blast radius (06_Wikilink_Impact_Report),
   chain-of-custody requirements (04_Legal evidence handling), and the
   22 binding adjudication decisions (15_Adjudication_Decisions.md).

3. **User final gate** — no change moves from `test` to `prod` without the user
   reviewing in Obsidian. The graph view and backlinks panel are the visual
   verification tools.

4. **Dev path constant** — all council edit scripts import `VAULT_DEV` from a
   shared config and call `_assert_dev_target()` before any write.

---

## Benchmark Reads vs Edit Writes

| Operation | Target | Rationale |
|-----------|--------|-----------|
| Read test suite / decision matrix | `prod` | Authoritative governance docs live in prod |
| Write benchmark results JSON | `prod/00_System/Logs/` | System logs are governance records; belong in prod |
| Write benchmark reports (.md) | `prod/00_System/Logs/` | Same — governance audit trail |
| Move / rename / create / delete vault content | `dev` only | Never prod or test |

---

## Quick Reference: Paths

```bash
VAULT_PROD="/home/alex/Documents/Remote Access Vault"
VAULT_TEST="/home/alex/vault-test"
VAULT_DEV="/home/alex/vault-dev"

# Sync dev before a council session
git -C "$VAULT_DEV" merge prod

# Promote reviewed changes to test
git -C "$VAULT_TEST" merge dev

# Release to prod after user review
git -C "$VAULT_PROD" merge test && git push origin prod test dev
```

---

## File Index

| File | Purpose |
|------|---------|
| `VAULT_EDIT_WORKFLOW.md` | This document — promotion chain protocol |
| `COUNCIL_BENCHMARK_WORKFLOW.md` | Council QA benchmarking (T-01 through T-15) |
| `bench/council_blind_test.py` | Benchmark runner — reads prod, writes logs to prod |
| `bench/council_matrix_test.py` | Benchmark runner — reads prod, writes logs to prod |
| `bench/cascade.py` | Cascade routing for TC suite (not vault edit) |
