#!/usr/bin/env python3
"""
Council Edit Session — vault restructure edit proposal engine.

T2 (Qwen3-30B) proposes filesystem operations for a given migration phase.
All operations execute against vault-dev only; never prod or test.
Each batch is committed to the dev branch for Claude adjudicator review.

Usage:
    python bench/council_edit_session.py --phase 0 [--dry-run] [--skip-sync]
    python bench/council_edit_session.py --phase 1 --dry-run
    python bench/council_edit_session.py --phase 2 --force   # high-risk: evidence files
"""
import argparse, json, re, subprocess, sys, urllib.request
from pathlib import Path

VAULT_DEV  = Path("/home/alex/vault-dev")
VAULT_PROD = Path("/home/alex/Documents/Remote Access Vault")
VAULT_TEST = Path("/home/alex/vault-test")

T2_URL = "http://127.0.0.1:8082/v1/chat/completions"

MATRIX = VAULT_PROD / "00_System/Logs/Vault_Defragmentation_Research/18_Council_Decision_Matrix.md"
LOG_DIR = VAULT_PROD / "00_System/Logs/Vault_Defragmentation_Research"

# Which matrix sections supply context per phase
PHASE_SECTIONS = {
    0: ["Section 7", "Section 6"],       # Archive structure gaps, root file rename
    1: ["Section 9", "Section 2"],       # Zero-link zones (07_Outputs, 06_Media)
    2: ["Section 3"],                    # Legal and Parenting migrations
    3: ["Section 4", "Section 5", "Section 8"],  # Homelab, AI, incubation zones
    4: ["Section 9"],                    # CGG migration (804 inbound links)
    5: [],                               # Post-migration validation (no T2 edits)
}

PHASE_NAMES = {
    0: "Preparation — create scaffold dirs + in-place renames (ADJ-019: rename emoji file); no zone migrations",
    1: "Low-Risk Renumbers — zero-link zones (07_Outputs→03_Outputs, 06_Media→02_Domains/Media)",
    2: "Domain Migrations — Parenting and Legal",
    3: "Framework Dissolution — Homelab, AI split, build projects",
    4: "CGG Migration — highest risk; 804 inbound path-form wikilinks",
    5: "Post-Migration Validation — no filesystem edits",
}

# Phases 2+ touch evidence files or mass-move zones; require --force
HIGH_RISK_PHASES = {2, 3, 4}


# ---------------------------------------------------------------------------
# Safety guard
# ---------------------------------------------------------------------------

def _assert_dev_target(path: Path) -> None:
    """Abort if a mutation is attempted outside the dev worktree."""
    resolved = path.resolve()
    if not str(resolved).startswith(str(VAULT_DEV.resolve())):
        raise RuntimeError(
            f"SAFETY ABORT: mutation target {resolved} is outside vault-dev.\n"
            f"Council scripts must only write to {VAULT_DEV}"
        )


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------

def sync_dev_from_prod() -> None:
    print("→ Syncing vault-dev from prod ...", flush=True)
    r = subprocess.run(
        ["git", "-C", str(VAULT_DEV), "merge", "prod", "--no-edit"],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        print(f"  WARN — merge conflict or error:\n{r.stderr.strip()}")
        print("  Continuing with current dev state.")
    else:
        msg = r.stdout.strip() or "Already up to date."
        print(f"  {msg}")


def git_stage_all() -> None:
    subprocess.run(
        ["git", "-C", str(VAULT_DEV), "add", "-A"],
        capture_output=True,
    )


def git_commit_dev(phase: int) -> None:
    r = subprocess.run(
        ["git", "-C", str(VAULT_DEV), "diff", "--cached", "--quiet"],
        capture_output=True,
    )
    if r.returncode == 0:
        print("\n  No staged changes to commit.")
        return
    msg = f"Council Phase {phase}: {PHASE_NAMES[phase]}"
    r = subprocess.run(
        ["git", "-C", str(VAULT_DEV), "commit", "-m", msg],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        print(f"  git commit error: {r.stderr.strip()}")
    else:
        print(f"\n  ✓ Committed to dev: {r.stdout.strip()}")


# ---------------------------------------------------------------------------
# Vault snapshot
# ---------------------------------------------------------------------------

def vault_tree(vault: Path, max_depth: int = 3) -> str:
    """Compact directory-only tree for T2 context."""
    SKIP = {".git", "__pycache__", ".obsidian", ".pytest_cache"}
    lines = [vault.name + "/"]

    def walk(dir_path: Path, depth: int, prefix: str) -> None:
        try:
            children = sorted(
                d for d in dir_path.iterdir()
                if d.is_dir() and d.name not in SKIP
            )
        except PermissionError:
            return
        for i, child in enumerate(children):
            last = i == len(children) - 1
            lines.append(prefix + ("└── " if last else "├── ") + child.name + "/")
            if depth < max_depth:
                walk(child, depth + 1, prefix + ("    " if last else "│   "))

    walk(vault, 1, "")
    return "\n".join(lines)


def root_files(vault: Path) -> str:
    """List non-hidden files at vault root (not directories)."""
    files = sorted(f.name for f in vault.iterdir() if f.is_file() and not f.name.startswith("."))
    return "\n".join(files) if files else "(none)"


# ---------------------------------------------------------------------------
# T2 interaction
# ---------------------------------------------------------------------------

def extract_md_section(text: str, heading: str) -> str:
    pattern = rf"(## {re.escape(heading)}.*?)(?=\n## |\Z)"
    m = re.search(pattern, text, re.DOTALL)
    return m.group(1).strip() if m else f"[{heading}: not found]"


def build_prompt(phase: int, matrix_text: str) -> str:
    sections = PHASE_SECTIONS.get(phase, [])
    section_bodies = "\n\n".join(extract_md_section(matrix_text, s) for s in sections)
    drift = extract_md_section(matrix_text, "Vault Drift Profile (Current State Summary)")
    qref  = extract_md_section(matrix_text, "Quick Reference: 22 Decisions at a Glance")
    tree  = vault_tree(VAULT_DEV, max_depth=3)
    rfiles = root_files(VAULT_DEV)

    op_schema = """Allowed "op" values and required fields:
  {"op": "create_dir", "path": "relative/from/vault/root/", "rationale": "..."}
  {"op": "move",       "src":  "relative/src/path",  "dst": "relative/dst/path", "rationale": "..."}
  {"op": "rename",     "src":  "old_name",            "dst": "new_name",          "rationale": "..."}
  {"op": "delete_file","path": "relative/path",                                   "rationale": "..."}
All paths are relative to vault root. No absolute paths. No leading slash."""

    return f"""You are a council member proposing vault filesystem operations.

Phase {phase}: {PHASE_NAMES[phase]}

CURRENT VAULT-DEV DIRECTORY STRUCTURE:
{tree}

ROOT-LEVEL FILES IN VAULT-DEV:
{rfiles}

VAULT DRIFT PROFILE:
{drift}

RELEVANT MATRIX SECTIONS:
{section_bodies}

QUICK REFERENCE — 22 BINDING DECISIONS:
{qref}

CONSTRAINTS:
- Propose ONLY operations for Phase {phase}. Do not propose future-phase work.
- Do NOT propose link repair (that is a separate script).
- Do NOT propose content edits inside .md files.
- Do NOT propose operations already complete (check current vault state above).
- Paths are relative to vault root.

{op_schema}

Output ONLY a valid JSON object — nothing before or after the JSON:
{{
  "phase": {phase},
  "phase_name": "{PHASE_NAMES[phase]}",
  "rationale": "...",
  "operations": [ ... ]
}}"""


def call_t2(prompt: str, max_tokens: int = 1800) -> str:
    payload = {
        "model": "local",
        "messages": [{"role": "user", "content": prompt + "\n/no_think"}],
        "max_tokens": max_tokens,
        "temperature": 0,
    }
    req = urllib.request.Request(
        T2_URL,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            data = json.loads(r.read())
            m = data["choices"][0]["message"]
            return (m.get("content") or m.get("reasoning_content", "")).strip()
    except Exception as e:
        return f"ERROR: {e}"


def parse_proposal(raw: str) -> dict:
    """Extract the JSON proposal from T2's response."""
    text = raw.strip()
    # Strip markdown code fences
    if text.startswith("```"):
        lines = text.split("\n")
        end_fence = next((i for i, l in enumerate(lines[1:], 1) if l.strip() == "```"), None)
        text = "\n".join(lines[1:end_fence] if end_fence else lines[1:])
    # Find outermost JSON object
    start = text.find("{")
    end   = text.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError(f"No JSON object in response:\n{raw[:600]}")
    return json.loads(text[start:end])


# ---------------------------------------------------------------------------
# Operation executor
# ---------------------------------------------------------------------------

def execute_operation(op: dict, dry_run: bool) -> bool:
    """Execute one operation against vault-dev. Returns True on success."""
    kind = op.get("op", "")
    note = op.get("rationale", "")

    if kind == "create_dir":
        rel  = op["path"].lstrip("/").rstrip("/")
        dest = VAULT_DEV / rel
        _assert_dev_target(dest)
        exists = dest.exists()
        status = "EXISTS" if exists else "CREATE"
        print(f"  {status:10s} {rel}/  — {note}")
        if not dry_run and not exists:
            dest.mkdir(parents=True, exist_ok=True)
            (dest / ".gitkeep").touch()
        return True

    elif kind in ("move", "rename"):
        src_rel = op["src"].lstrip("/").rstrip("/")
        dst_rel = op["dst"].lstrip("/").rstrip("/")
        src = VAULT_DEV / src_rel
        dst = VAULT_DEV / dst_rel
        _assert_dev_target(src)
        _assert_dev_target(dst)
        if not src.exists():
            print(f"  SKIP       {src_rel}  (not found)")
            return False
        if dst.exists():
            print(f"  SKIP       {src_rel}  (destination already exists: {dst_rel})")
            return False
        print(f"  {kind.upper():10s} {src_rel}  →  {dst_rel}  — {note}")
        if not dry_run:
            dst.parent.mkdir(parents=True, exist_ok=True)
            r = subprocess.run(
                ["git", "-C", str(VAULT_DEV), "mv",
                 str(src.relative_to(VAULT_DEV)),
                 str(dst.relative_to(VAULT_DEV))],
                capture_output=True, text=True,
            )
            if r.returncode != 0:
                print(f"    git mv error: {r.stderr.strip()}")
                return False
        return True

    elif kind == "delete_file":
        rel  = op["path"].lstrip("/")
        target = VAULT_DEV / rel
        _assert_dev_target(target)
        if not target.exists():
            print(f"  SKIP       {rel}  (not found)")
            return False
        print(f"  DELETE     {rel}  — {note}")
        if not dry_run:
            r = subprocess.run(
                ["git", "-C", str(VAULT_DEV), "rm", "-f",
                 str(target.relative_to(VAULT_DEV))],
                capture_output=True, text=True,
            )
            if r.returncode != 0:
                print(f"    git rm error: {r.stderr.strip()}")
                return False
        return True

    else:
        print(f"  UNKNOWN    op={kind!r} — skipping")
        return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Council vault edit session runner")
    parser.add_argument("--phase", type=int, required=True, metavar="N",
                        help="Migration phase to execute (0–5)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print proposed operations without executing")
    parser.add_argument("--skip-sync", action="store_true",
                        help="Skip git merge prod before session")
    parser.add_argument("--force", action="store_true",
                        help="Required for high-risk phases (2, 3, 4)")
    args = parser.parse_args()

    if args.phase not in PHASE_NAMES:
        sys.exit(f"Unknown phase {args.phase}. Valid: {sorted(PHASE_NAMES)}")

    if args.phase == 5:
        sys.exit("Phase 5 is validation — no filesystem edits. Run link audit manually.")

    if args.phase in HIGH_RISK_PHASES and not args.force and not args.dry_run:
        sys.exit(
            f"Phase {args.phase} is high-risk (evidence files / chain-of-custody required).\n"
            f"Preview with --dry-run, then execute with --force after review."
        )

    print(f"\n{'='*64}")
    print(f"Council Edit Session — Phase {args.phase}")
    print(f"  {PHASE_NAMES[args.phase]}")
    print(f"  Target: {VAULT_DEV}")
    if args.dry_run:
        print("  Mode: DRY RUN — no changes will be made")
    print(f"{'='*64}")

    if not args.skip_sync and not args.dry_run:
        sync_dev_from_prod()

    matrix_text = MATRIX.read_text()
    prompt = build_prompt(args.phase, matrix_text)

    print(f"\nQuerying T2 (Qwen3-30B @ {T2_URL}) ...", end=" ", flush=True)
    raw = call_t2(prompt)

    if raw.startswith("ERROR:"):
        sys.exit(f"\nT2 call failed: {raw}")

    print(f"{len(raw)} chars received")

    try:
        proposal = parse_proposal(raw)
    except (json.JSONDecodeError, ValueError) as e:
        print(f"\nFailed to parse T2 response as JSON: {e}")
        print("\n--- Raw T2 response ---")
        print(raw)
        sys.exit(1)

    ops = proposal.get("operations", [])
    rationale = proposal.get("rationale", "—")

    print(f"\nProposed {len(ops)} operation(s)")
    print(f"Rationale: {rationale}\n")

    success, skipped, failed = 0, 0, 0
    for op in ops:
        try:
            ok = execute_operation(op, dry_run=args.dry_run)
            if ok:
                success += 1
            else:
                skipped += 1
        except RuntimeError as e:
            print(f"  ABORT: {e}")
            sys.exit(1)
        except KeyError as e:
            print(f"  MALFORMED op (missing field {e}): {op}")
            failed += 1

    print(f"\n  {success} executed, {skipped} skipped, {failed} failed"
          f"{'  (dry run — nothing written)' if args.dry_run else ''}")

    if not args.dry_run and success > 0:
        git_stage_all()
        git_commit_dev(args.phase)

    # Save proposal JSON to prod governance log
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    out = LOG_DIR / f"Council_Edit_Phase{args.phase}_Proposal.json"
    out.write_text(json.dumps({"raw_response": raw, "parsed": proposal}, indent=2))
    print(f"\n  Proposal saved → {out}")


if __name__ == "__main__":
    main()
