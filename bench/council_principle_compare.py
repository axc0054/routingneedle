#!/usr/bin/env python3
"""
Principle comparison test.
Runs T-15 and T-06 with two Section 9 / Section 3 variants:
  Variant A — current matrix wording (my formulation)
  Variant B — user's reformulation of Zero-Link and Routing Override principles

Both variants are injected into the same system prompt structure.
Results saved side-by-side for scoring.
"""
import json, urllib.request, time, re
from pathlib import Path

VAULT  = Path("/home/alex/Documents/Remote Access Vault")
SUITE  = VAULT / "00_System/System_Projects/Vault_Defragmentation_Research/Council_Test_Suite"
MATRIX = VAULT / "00_System/System_Projects/Vault_Defragmentation_Research/18_Council_Decision_Matrix.md"
OUT    = VAULT / "00_System/System_Projects/Vault_Defragmentation_Research/Council_Principle_Compare.json"

T1_URL = "http://127.0.0.1:8081/v1/chat/completions"
T2_URL = "http://127.0.0.1:8082/v1/chat/completions"

TARGET_TESTS = {"T-15", "T-06"}

SECTION_MAP = {
    "T-06": ["Section 3"],
    "T-15": ["Section 9", "Section 2"],
}

# ── Variant A: current matrix wording ────────────────────────────────────────
VARIANT_A_OVERRIDES = {}   # no overrides — uses live matrix sections as-is

# ── Variant B: user's reformulations ─────────────────────────────────────────
# These replace the principle blocks in the relevant sections.
VARIANT_B_ZERO_LINK = """\
**Zero-Link Safety Principle:**
Zero inbound links = zero link-break risk. A zone with 0 full-path inbound wikilinks \
can move without a link repair script because no vault link points to its current path. \
0 is not "less than 5." It is a different risk class: 0 = no links can break; \
>0 = links can break. CGG, with 804 inbound links, is the last zone to migrate \
because 804 >> 0 and represents the maximum-risk migration class."""

VARIANT_B_ROUTING_OVERRIDE = """\
**Routing Map Override Principle:**
Zero inbound links ≠ zero routing risk. Even if a zone has 0 wikilinks, any path \
referenced in model_dispatch_map.json must be updated before new intake runs.

Rule: old path in dispatch map + new files written to renamed path = routing failure

Example:
  07_Outputs/Legal_Packet_Assembly/ = legal_strict   (before rename)
  03_Outputs/Legal_Packet_Assembly/ = legal_strict   (after rename — dispatch map must reflect this)

Zone A can be link-safe and still routing-unsafe. \
0 links = safe to move links; >0 dispatch references = must repair routing paths."""


def extract_md_section(text, heading):
    pattern = rf"(## {re.escape(heading)}.*?)(?=\n## |\Z)"
    m = re.search(pattern, text, re.DOTALL)
    return m.group(1).strip() if m else f"[{heading}: not found]"


def extract_test_prompt(path):
    raw = path.read_text()
    cut = raw.find("## Target Finding")
    body = raw[:cut] if cut != -1 else raw
    if body.startswith("---"):
        end = body.find("---", 3)
        body = body[end + 3:].strip()
    return body.strip()


def apply_variant_b(section_text, test_id):
    """Inject user's principle formulations into the section text."""
    if test_id == "T-15":
        # Replace the zero-link principle block and routing verification block
        text = re.sub(
            r"\*\*Zero-link safety principle:\*\*.*?(?=\n\n\*\*|\n\n###|\Z)",
            VARIANT_B_ZERO_LINK,
            section_text,
            flags=re.DOTALL,
        )
        text = re.sub(
            r"\*\*Minimum verification after any zone migration.*?(?=\n\n###|\Z)",
            VARIANT_B_ROUTING_OVERRIDE,
            text,
            flags=re.DOTALL,
        )
        return text
    if test_id == "T-06":
        # Replace the legal_strict routing row in the feasibility rubric
        text = re.sub(
            r"\| `legal_strict` routing preservation \|.*?\|",
            "| `legal_strict` routing preservation | HIGH | " + VARIANT_B_ROUTING_OVERRIDE.replace("\n", " ") + " |",
            section_text,
        )
        return text
    return section_text


def build_system(matrix_text, drift, qref, test_id, variant):
    sections = SECTION_MAP.get(test_id, [])
    sec_bodies = []
    for s in sections:
        body = extract_md_section(matrix_text, s)
        if variant == "B":
            body = apply_variant_b(body, test_id)
        sec_bodies.append(body)
    return f"""You are a council member evaluating a vault restructure corrective solution.
All 22 adjudication decisions are binding. Evaluate execution feasibility — do not re-adjudicate.
Answer each question specifically and concisely.

VAULT STATE:
{drift}

RELEVANT CONTEXT:
{chr(10).join(sec_bodies)}

DECISION REFERENCE:
{qref}"""


def call_model(url, system, user, max_tokens=700, no_think=False):
    msg = user + "\n/no_think" if no_think else user
    payload = {
        "model": "local",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": msg},
        ],
        "max_tokens": max_tokens,
        "temperature": 0,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=150) as r:
            data = json.loads(r.read())
            m = data["choices"][0]["message"]
            return (m.get("content") or m.get("reasoning_content", "")).strip()
    except Exception as e:
        return f"ERROR: {e}"


def main():
    matrix_text = MATRIX.read_text()
    drift = extract_md_section(matrix_text, "Vault Drift Profile (Current State Summary)")
    qref  = extract_md_section(matrix_text, "Quick Reference: 22 Decisions at a Glance")

    test_files = sorted(
        tf for tf in SUITE.glob("T-*.md")
        if tf.stem[:4] in TARGET_TESTS
    )

    results = {}

    for tf in test_files:
        tid = tf.stem[:4]
        prompt = extract_test_prompt(tf)
        results[tid] = {"file": tf.name}

        for variant in ("A", "B"):
            label = f"Variant_{variant}"
            system = build_system(matrix_text, drift, qref, tid, variant)
            print(f"\n{'='*56}\n{tid}  {tf.name}  [{label}]")

            print("  T1 DeepSeek ...", end=" ", flush=True)
            t = time.time()
            t1 = call_model(T1_URL, system, prompt, max_tokens=700)
            t1s = round(time.time() - t, 1)
            print(f"{t1s}s  {len(t1)} chars")

            print("  T2 Qwen     ...", end=" ", flush=True)
            t = time.time()
            t2 = call_model(T2_URL, system, prompt, max_tokens=900, no_think=True)
            t2s = round(time.time() - t, 1)
            print(f"{t2s}s  {len(t2)} chars")

            results[tid][label] = {
                "T1_response": t1,
                "T1_time_s":   t1s,
                "T2_response": t2,
                "T2_time_s":   t2s,
            }

    OUT.write_text(json.dumps(results, indent=2))
    print(f"\nSaved → {OUT}")


if __name__ == "__main__":
    main()
