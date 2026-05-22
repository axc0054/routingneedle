#!/usr/bin/env python3
"""
Re-test partial-scoring scenarios after matrix additions.
Runs only the tests that scored PARTIAL in the scaffolded condition.
"""
import json, urllib.request, time, re, sys
from pathlib import Path

VAULT  = Path("/home/alex/Documents/Remote Access Vault")
SUITE  = VAULT / "00_System/System_Projects/Vault_Defragmentation_Research/Council_Test_Suite"
MATRIX = VAULT / "00_System/System_Projects/Vault_Defragmentation_Research/18_Council_Decision_Matrix.md"
OUT    = VAULT / "00_System/System_Projects/Vault_Defragmentation_Research/Council_Test_Results_Partial_Retest.json"

T1_URL = "http://127.0.0.1:8081/v1/chat/completions"
T2_URL = "http://127.0.0.1:8082/v1/chat/completions"

# Only the tests that scored PARTIAL for either model
PARTIAL_IDS = {"T-01", "T-02", "T-04", "T-08", "T-10", "T-12", "T-15"}

SECTION_MAP = {
    "T-01": ["Section 9", "Section 1"],
    "T-02": ["Section 9"],
    "T-04": ["Section 3"],
    "T-08": ["Section 5"],
    "T-10": ["Section 6"],
    "T-12": ["Section 8"],
    "T-15": ["Section 9", "Section 2"],
}


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

    test_files = sorted(
        tf for tf in SUITE.glob("T-*.md")
        if tf.stem[:4] in PARTIAL_IDS
    )

    print(f"Re-testing {len(test_files)} partial scenarios: {[tf.stem[:4] for tf in test_files]}")
    results = {}

    for tf in test_files:
        tid = tf.stem[:4]
        print(f"\n{'='*56}\n{tid}  {tf.name}")

        system = build_system(matrix_text, drift, qref, tid)
        prompt = extract_test_prompt(tf)

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

        results[tid] = {
            "file":        tf.name,
            "T1_response": t1,
            "T1_time_s":   t1s,
            "T2_response": t2,
            "T2_time_s":   t2s,
        }

    OUT.write_text(json.dumps(results, indent=2))
    print(f"\nSaved → {OUT}")


if __name__ == "__main__":
    main()
