#!/usr/bin/env python3
"""
Council MTP Assessment Runner — T2 Candidacy Evaluation
Runs T-01 through T-15 against Qwen3.6-27B MTP on port 8083 (temporary seat).
Covers both blind and scaffolded conditions to compare against T2 baseline
(Qwen3-30B-A3B scaffolded: 14/15 MATCH, blind: 4/15 MATCH — Run 2, 2026-05-10).

MTP server must be running on port 8083 before executing this script.
Start command:
  numactl --cpunodebind=0 --membind=0 \\
    /home/alex/llama.cpp/build-cuda-mtp/bin/llama-server \\
    -m /home/alex/models/llm/media/qwen3.6-27b/Qwen3.6-27B-Q4_K_M.gguf \\
    -ngl 46 -c 8192 --reasoning off \\
    --spec-type draft-mtp --spec-draft-n-max 1 \\
    --host 127.0.0.1 --port 8083
"""
import json, urllib.request, time, re
from pathlib import Path

VAULT  = Path("/home/alex/Documents/Remote Access Vault")
SUITE  = VAULT / "00_System/System_Projects/Vault_Defragmentation_Research/Council_Test_Suite"
MATRIX = VAULT / "00_System/System_Projects/Vault_Defragmentation_Research/18_Council_Decision_Matrix.md"
OUT    = VAULT / "00_System/System_Projects/Vault_Defragmentation_Research/Council_MTP_Assessment.json"

MTP_URL = "http://127.0.0.1:8083/v1/chat/completions"

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

SYSTEM_BLIND = """You are a council member evaluating a vault restructure corrective solution.
All 22 adjudication decisions are binding. Evaluate execution feasibility — do not re-adjudicate.
Answer each question specifically and concisely."""


def extract_section(text, heading):
    m = re.search(rf"(## {re.escape(heading)}.*?)(?=\n## |\Z)", text, re.DOTALL)
    return m.group(1).strip() if m else f"[{heading}: not found]"


def extract_test_prompt(path):
    raw = path.read_text()
    cut = raw.find("## Target Finding")
    body = raw[:cut] if cut != -1 else raw
    if body.startswith("---"):
        end = body.find("---", 3)
        body = body[end + 3:].strip()
    return body.strip()


def call_model(url, system, user, max_tokens=900):
    payload = {
        "model": "local",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
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
        with urllib.request.urlopen(req, timeout=600) as r:
            data = json.loads(r.read())
            m = data["choices"][0]["message"]
            return (m.get("content") or m.get("reasoning_content", "")).strip()
    except Exception as e:
        return f"ERROR: {e}"


def build_scaffolded_system(matrix_text, drift, qref, test_id):
    sections = SECTION_MAP.get(test_id, [])
    sec_bodies = [extract_section(matrix_text, s) for s in sections]
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
    drift = extract_section(matrix_text, "Vault Drift Profile (Current State Summary)")
    qref  = extract_section(matrix_text, "Quick Reference: 22 Decisions at a Glance")

    test_files = sorted(SUITE.glob("T-*.md"))
    results = {}

    print(f"Council MTP Assessment — {len(test_files)} test cases")
    print(f"Model: Qwen3.6-27B MTP @ {MTP_URL}")
    print("=" * 60)

    for tf in test_files:
        tid = tf.stem[:4]
        prompt = extract_test_prompt(tf)
        print(f"\n{'='*56}\n{tid}  {tf.name}")

        # Blind condition
        print("  [blind]      ...", end=" ", flush=True)
        t = time.time()
        blind_resp = call_model(MTP_URL, SYSTEM_BLIND, prompt, max_tokens=900)
        blind_s = round(time.time() - t, 1)
        print(f"{blind_s}s  {len(blind_resp)} chars")

        # Scaffolded condition
        system_scaffolded = build_scaffolded_system(matrix_text, drift, qref, tid)
        print("  [scaffolded] ...", end=" ", flush=True)
        t = time.time()
        scaff_resp = call_model(MTP_URL, system_scaffolded, prompt, max_tokens=900)
        scaff_s = round(time.time() - t, 1)
        print(f"{scaff_s}s  {len(scaff_resp)} chars")

        results[tid] = {
            "file":              tf.name,
            "blind_response":    blind_resp,
            "blind_time_s":      blind_s,
            "scaffolded_response": scaff_resp,
            "scaffolded_time_s": scaff_s,
        }

    OUT.write_text(json.dumps(results, indent=2))
    print(f"\nSaved → {OUT}")
    print("\nNext: score each response against target findings in the test suite.")
    print("Compare blind/scaffolded uplift against T2 baseline (Run 2, 2026-05-10):")
    print("  T2 blind:       4/15 MATCH")
    print("  T2 scaffolded: 14/15 MATCH")


if __name__ == "__main__":
    main()
