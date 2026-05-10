#!/usr/bin/env python3
"""
Council Matrix Test Runner — Scaffolded Condition
Runs T-01 through T-15 against both council tiers with
18_Council_Decision_Matrix.md sections as system context.

T1 responses tagged T1_degenerated:true when repetition-loop collapse is detected.
Degenerated responses are saved but should be scored as MISS(DEGEN), not DIVERGE.
See COUNCIL_BENCHMARK_WORKFLOW.md for full scoring and iteration process.
"""
import json, urllib.request, time, re, sys
from pathlib import Path

VAULT = Path("/home/alex/Documents/Remote Access Vault")
SUITE  = VAULT / "00_System/Logs/Vault_Defragmentation_Research/Council_Test_Suite"
MATRIX = VAULT / "00_System/Logs/Vault_Defragmentation_Research/18_Council_Decision_Matrix.md"
OUT    = VAULT / "00_System/Logs/Vault_Defragmentation_Research/Council_Test_Results_Scaffolded.json"

T1_URL = "http://127.0.0.1:8081/v1/chat/completions"  # DeepSeek
T2_URL = "http://127.0.0.1:8082/v1/chat/completions"  # Qwen

SECTION_MAP = {
    "T-01": ["Section 9", "Section 1"],
    "T-02": ["Section 9"],
    "T-03": ["Section 9"],
    "T-04": ["Section 3"],
    "T-05": ["Section 8"],
    "T-06": ["Section 3"],
    "T-07": ["Section 2"],
    "T-08": ["Section 5"],
    "T-09": ["Section 7", "Section 6"],
    "T-10": ["Section 6"],
    "T-11": ["Section 4"],
    "T-12": ["Section 8"],
    "T-13": ["Section 3"],
    "T-14": ["Section 9"],
    "T-15": ["Section 9", "Section 2"],
}


def extract_md_section(text, heading):
    """Extract ## heading ... up to next ## heading."""
    pattern = rf"(## {re.escape(heading)}.*?)(?=\n## |\Z)"
    m = re.search(pattern, text, re.DOTALL)
    return m.group(1).strip() if m else f"[{heading}: not found]"


def extract_test_prompt(path):
    """Return everything up to ## Target Finding (excludes answer guide)."""
    raw = path.read_text()
    cut = raw.find("## Target Finding")
    body = raw[:cut] if cut != -1 else raw
    # Strip frontmatter
    if body.startswith("---"):
        end = body.find("---", 3)
        body = body[end + 3:].strip()
    return body.strip()


def _is_degenerated(response: str, phrase_len: int = 40, max_repeats: int = 4) -> bool:
    """Repetition-loop and context-echo degeneration guard for T1 responses."""
    if not response or len(response) < phrase_len * (max_repeats + 1):
        return False
    sample_end = max(len(response) // 4, phrase_len * 2)
    for offset in range(0, min(sample_end, 600), 20):
        phrase = response[offset:offset + phrase_len]
        if phrase.strip() and response.count(phrase) > max_repeats:
            return True
    return False


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


def build_system(matrix_text, drift, qref, test_id):
    sections = SECTION_MAP.get(test_id, [])
    sec_bodies = [extract_md_section(matrix_text, s) for s in sections]
    return f"""You are a council member evaluating a vault restructure corrective solution.
All 22 adjudication decisions are binding. Evaluate execution feasibility — do not re-adjudicate.
Answer each question specifically and concisely.

VAULT STATE:
{drift}

RELEVANT CONTEXT:
{chr(10).join(sec_bodies)}

DECISION REFERENCE:
{qref}"""


def main():
    matrix_text = MATRIX.read_text()
    drift = extract_md_section(matrix_text, "Vault Drift Profile (Current State Summary)")
    qref  = extract_md_section(matrix_text, "Quick Reference: 22 Decisions at a Glance")

    test_files = sorted(SUITE.glob("T-*.md"))
    results = {}

    for tf in test_files:
        tid = tf.stem[:4]
        print(f"\n{'='*56}\n{tid}  {tf.name}")

        system  = build_system(matrix_text, drift, qref, tid)
        prompt  = extract_test_prompt(tf)

        print("  T1 DeepSeek ...", end=" ", flush=True)
        t = time.time()
        t1 = call_model(T1_URL, system, prompt, max_tokens=700)
        t1s = round(time.time() - t, 1)
        t1_degen = _is_degenerated(t1)
        print(f"{t1s}s  {len(t1)} chars{'  [DEGENERATED]' if t1_degen else ''}")

        print("  T2 Qwen     ...", end=" ", flush=True)
        t = time.time()
        t2 = call_model(T2_URL, system, prompt, max_tokens=900, no_think=True)
        t2s = round(time.time() - t, 1)
        print(f"{t2s}s  {len(t2)} chars")

        results[tid] = {
            "file":           tf.name,
            "T1_response":    t1,
            "T1_time_s":      t1s,
            "T1_degenerated": t1_degen,
            "T2_response":    t2,
            "T2_time_s":      t2s,
        }

    OUT.write_text(json.dumps(results, indent=2))
    print(f"\nSaved → {OUT}")


if __name__ == "__main__":
    main()
