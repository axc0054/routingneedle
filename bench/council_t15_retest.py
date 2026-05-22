#!/usr/bin/env python3
"""
T-15 targeted retest — validates two new Section 9 additions:
  1. Head-to-head priority rule (Zone A 0 links > Zone B <5 links)
  2. Routing tag caveat (zero-link ≠ zero routing risk; dispatch map update required)
Results saved to Council_T15_Retest.json
"""
import json, urllib.request, time, re
from pathlib import Path

VAULT  = Path("/home/alex/Documents/Remote Access Vault")
SUITE  = VAULT / "00_System/System_Projects/Vault_Defragmentation_Research/Council_Test_Suite"
MATRIX = VAULT / "00_System/System_Projects/Vault_Defragmentation_Research/18_Council_Decision_Matrix.md"
OUT    = VAULT / "00_System/System_Projects/Vault_Defragmentation_Research/Council_T15_Retest.json"

T1_URL = "http://127.0.0.1:8081/v1/chat/completions"
T2_URL = "http://127.0.0.1:8082/v1/chat/completions"


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


def build_system(matrix_text):
    drift = extract_md_section(matrix_text, "Vault Drift Profile (Current State Summary)")
    qref  = extract_md_section(matrix_text, "Quick Reference: 22 Decisions at a Glance")
    sec9  = extract_md_section(matrix_text, "Section 9")
    sec2  = extract_md_section(matrix_text, "Section 2")
    return f"""You are a council member evaluating a vault restructure corrective solution.
All 22 adjudication decisions are binding. Evaluate execution feasibility — do not re-adjudicate.
Answer each question specifically and concisely.

VAULT STATE:
{drift}

RELEVANT CONTEXT:
{sec9}

{sec2}

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
    system = build_system(matrix_text)

    tf = next(SUITE.glob("T-15*.md"))
    prompt = extract_test_prompt(tf)

    print(f"\n{'='*56}\nT-15  {tf.name}")

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

    result = {
        "T-15": {
            "file": tf.name,
            "T1_response": t1,
            "T1_time_s":   t1s,
            "T2_response": t2,
            "T2_time_s":   t2s,
        }
    }

    OUT.write_text(json.dumps(result, indent=2))
    print(f"\nSaved → {OUT}")
    print("\n--- T2 Response ---\n")
    print(t2)


if __name__ == "__main__":
    main()
