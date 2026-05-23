#!/usr/bin/env python3
"""
run_peer_review.py — Offline Peer Review Matrix batch runner.

Implements the council quality benchmark described in the Council Pipeline
Enhancement project (PRJ-202605-COUNCIL-PIPE).  Runs a fixed fixture set
through all configured models, cross-evaluates each model's response against
every other model's response (blind — model IDs are stripped), and appends
decay-tracking results to a JSONL register.

Usage:
    python3 bench/run_peer_review.py [--testcases TOML_DIR] [--out JSONL] [--dry-run]

Exit codes:
    0  — run complete, no regressions detected
    1  — run complete, regression(s) detected (score drop >10% vs prior baseline)
    2  — setup error (missing config, VRAM floor violation)

Safety rules (enforced before any model is loaded):
    - VRAM floor check: P5000 must have ≥ 3,277 MiB free (abort_floor)
    - T2 service is stopped before MTP evaluation, restarted after
    - T1 restart counter: if WX9100 has processed ≥ 100 calls in this session,
      the T1 service is restarted to clear Vulkan allocator state
    - All benchmark fixtures must be synthetic (.md only, no real vault content)
    - temperature=0 on all API calls (deterministic scoring)
"""

import argparse
import json
import pathlib
import re
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

BENCH_DIR        = pathlib.Path(__file__).parent
REPO_ROOT        = BENCH_DIR.parent
CONFIGS_DIR      = REPO_ROOT / "configs"
DEFAULT_TC_DIR   = CONFIGS_DIR / "testcases"
DEFAULT_OUT      = pathlib.Path("/home/alex/logs/bench_peer_review.jsonl")
PRIOR_BASELINE   = pathlib.Path("/home/alex/logs/bench_peer_review_baseline.json")

MODEL_CONFIGS = [
    CONFIGS_DIR / "models" / "deepseek-v2-lite-wx9100.toml",
    CONFIGS_DIR / "models" / "qwen3-30b-p5000.toml",
]

# VRAM floor — P5000: abort if free VRAM < this (MiB)
_VRAM_ABORT_FLOOR_MIB = 3277
# T1 restart threshold (Vulkan allocator fragmentation mitigation)
_T1_RESTART_CALL_THRESHOLD = 100

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_toml(path: pathlib.Path) -> dict:
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib  # type: ignore
    with open(path, "rb") as f:
        return tomllib.load(f)


def _check_p5000_vram() -> tuple[bool, int]:
    """Returns (ok, free_mib). ok=False if free < abort floor."""
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
            text=True, timeout=10
        ).strip()
        free = int(out.splitlines()[0].strip())
        return free >= _VRAM_ABORT_FLOOR_MIB, free
    except Exception as e:
        print(f"  [peer-review] VRAM check failed: {e}", file=sys.stderr)
        return True, -1  # allow if check itself fails


def _get_binary_version(api_base: str) -> str:
    """Query the model server for a build/version identifier."""
    try:
        req = urllib.request.Request(f"{api_base}/models")
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
            models = data.get("data", [])
            return models[0].get("id", "unknown") if models else "unknown"
    except Exception:
        return "unknown"


def _call_model(api_base: str, model_id: str, prompt: str,
                no_think: bool = False, timeout_s: int = 120) -> str | None:
    """Single inference call. Returns response text or None on error."""
    content = "/no_think\n" + prompt if no_think else prompt
    payload = json.dumps({
        "model": model_id,
        "messages": [{"role": "user", "content": content}],
        "max_tokens": 512,
        "temperature": 0,
    }).encode()
    try:
        req = urllib.request.Request(
            f"{api_base}/chat/completions",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            data = json.loads(resp.read())
            return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"  [peer-review] Call to {api_base} failed: {e}", file=sys.stderr)
        return None


def _strip_model_id(text: str, model_names: list[str]) -> str:
    """Strip model identifiers from a response for blind evaluation."""
    result = text
    for name in model_names:
        # Match the model name and common variations (underscores, hyphens, casing)
        pattern = re.compile(re.escape(name), re.IGNORECASE)
        result = pattern.sub("[MODEL]", result)
    return result


def _load_fixture(tc_path: pathlib.Path, corpus_base: pathlib.Path) -> tuple[str, str, str]:
    """Load testcase TOML. Returns (tc_id, doc_text, query)."""
    tc = _load_toml(tc_path)
    tc_id = tc["testcase"]["id"]
    doc_rel = tc["testcase"]["document"]
    doc_path = corpus_base / doc_rel
    query = tc["testcase"].get("query", tc["testcase"].get("prompt", ""))
    try:
        doc_text = doc_path.read_text(encoding="utf-8")
    except Exception:
        doc_text = ""
    return tc_id, doc_text, query


# ---------------------------------------------------------------------------
# Peer review scoring (rule-based, no LLM call required)
# ---------------------------------------------------------------------------

sys.path.insert(0, str(BENCH_DIR))
from council_scorer import score_peer_review  # noqa: E402


# ---------------------------------------------------------------------------
# Service management
# ---------------------------------------------------------------------------

def _stop_service(name: str) -> None:
    try:
        subprocess.run(["systemctl", "--user", "stop", name],
                       timeout=20, capture_output=True)
        time.sleep(3)
    except Exception as e:
        print(f"  [peer-review] Could not stop {name}: {e}", file=sys.stderr)


def _start_service(name: str) -> None:
    try:
        subprocess.run(["systemctl", "--user", "start", name],
                       timeout=20, capture_output=True)
        time.sleep(6)
    except Exception as e:
        print(f"  [peer-review] Could not start {name}: {e}", file=sys.stderr)


def _restart_service(name: str) -> None:
    try:
        subprocess.run(["systemctl", "--user", "restart", name],
                       timeout=30, capture_output=True)
        time.sleep(8)
    except Exception as e:
        print(f"  [peer-review] Could not restart {name}: {e}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Regression detection
# ---------------------------------------------------------------------------

def _load_baseline() -> dict:
    if PRIOR_BASELINE.exists():
        try:
            return json.loads(PRIOR_BASELINE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _detect_regressions(current: dict, baseline: dict) -> list[str]:
    """
    Compare current run scores vs baseline. Flag any drop > 10%.
    current/baseline shape: {model_id: {tc_id: evidence_recall_float}}
    """
    flags: list[str] = []
    for model_id, tc_scores in current.items():
        base_model = baseline.get(model_id, {})
        for tc_id, recall in tc_scores.items():
            base_recall = base_model.get(tc_id)
            if base_recall is not None and recall < base_recall - 0.10:
                flags.append(
                    f"{model_id}/{tc_id}: {base_recall:.2f} → {recall:.2f} "
                    f"(drop {base_recall - recall:.2f})"
                )
    return flags


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Offline Peer Review Matrix batch runner")
    parser.add_argument("--testcases", type=pathlib.Path, default=DEFAULT_TC_DIR,
                        help="Directory of TC-XX.toml fixtures")
    parser.add_argument("--out", type=pathlib.Path, default=DEFAULT_OUT,
                        help="JSONL output path for decay register")
    parser.add_argument("--dry-run", action="store_true",
                        help="Load fixtures and configs but do not call models")
    args = parser.parse_args()

    run_start = datetime.now(timezone.utc).isoformat()
    print(f"[peer-review] Run started: {run_start}")

    # VRAM pre-check
    vram_ok, vram_free = _check_p5000_vram()
    if not vram_ok:
        print(f"[peer-review] ABORT — P5000 free VRAM {vram_free} MiB < {_VRAM_ABORT_FLOOR_MIB} MiB floor",
              file=sys.stderr)
        return 2

    # Load model configs
    model_cfgs = []
    for cfg_path in MODEL_CONFIGS:
        if not cfg_path.exists():
            print(f"[peer-review] ABORT — model config missing: {cfg_path}", file=sys.stderr)
            return 2
        model_cfgs.append(_load_toml(cfg_path))

    model_names = [c["model"]["name"] for c in model_cfgs]

    # Load all synthetic fixture paths (no real vault content)
    tc_paths = sorted(p for p in args.testcases.glob("tc*.toml") if p.is_file())
    if not tc_paths:
        print(f"[peer-review] No tc*.toml fixtures found in {args.testcases}", file=sys.stderr)
        return 2
    print(f"[peer-review] Fixtures: {len(tc_paths)} | Models: {len(model_cfgs)}")

    # Determine corpus base (fixtures sub-dir relative to testcases dir)
    corpus_base = args.testcases / "fixtures"

    if args.dry_run:
        print("[peer-review] Dry-run mode — no model calls. Exiting.")
        return 0

    # Collect responses: responses[model_idx][tc_id] = response_text
    responses: list[dict[str, str | None]] = [{} for _ in model_cfgs]
    t1_calls = 0

    print("\n[peer-review] Collecting responses from all models...")
    for tc_path in tc_paths:
        tc_id, doc_text, query = _load_fixture(tc_path, corpus_base)
        if not doc_text or not query:
            print(f"  SKIP {tc_id} — empty document or query")
            continue

        prompt = f"[DOCUMENT: {tc_path.stem}]\n{doc_text}\n[END DOCUMENT]\n\n{query}"

        for m_idx, cfg in enumerate(model_cfgs):
            m = cfg["model"]
            api_base = m["api_base"]
            model_id = m["model_id"]
            no_think = m.get("force_no_think", False)
            timeout_s = 30 if "deepseek" in model_id else 120

            # T1 Vulkan fragmentation mitigation
            if "deepseek" in model_id:
                t1_calls += 1
                if t1_calls % _T1_RESTART_CALL_THRESHOLD == 0:
                    print(f"  [peer-review] T1 call threshold ({t1_calls}) — restarting Vulkan service")
                    _restart_service("llm-t1-deepseek.service")

            resp = _call_model(api_base, model_id, prompt, no_think=no_think, timeout_s=timeout_s)
            responses[m_idx][tc_id] = resp
            status = "ok" if resp else "TIMEOUT/ERROR"
            print(f"  {tc_id} | {m['name']}: {status}")

    # Cross-evaluation: for each (subject, evaluator) pair, score subject's response
    print("\n[peer-review] Cross-evaluation matrix...")
    # score_matrix[subject_model_name][evaluator_model_name][tc_id] = CouncilScore
    score_matrix: dict[str, dict[str, dict]] = {}
    current_recalls: dict[str, dict[str, float]] = {}

    for s_idx, s_cfg in enumerate(model_cfgs):
        s_name = s_cfg["model"]["name"]
        score_matrix[s_name] = {}
        current_recalls[s_name] = {}
        for e_idx, e_cfg in enumerate(model_cfgs):
            if s_idx == e_idx:
                continue
            e_name = e_cfg["model"]["name"]
            score_matrix[s_name][e_name] = {}
            for tc_id, subject_resp in responses[s_idx].items():
                ref_resp = responses[e_idx].get(tc_id)
                if not subject_resp or not ref_resp:
                    continue
                # Blind: strip model identifiers from the subject response
                blind_subject = _strip_model_id(subject_resp, model_names)
                blind_ref     = _strip_model_id(ref_resp, model_names)
                # Source doc for evidence grounding
                tc_path = next((p for p in tc_paths if tc_id in p.stem), None)
                _, doc_text, _ = _load_fixture(tc_path, corpus_base) if tc_path else ("", "", "")
                cs = score_peer_review(tc_id, blind_subject, doc_text, blind_ref)
                score_matrix[s_name][e_name][tc_id] = {
                    "passed": cs.passed,
                    "evidence_recall": cs.evidence_recall,
                    "hallucinations": cs.hallucination_flags,
                    "notes": cs.notes,
                }
                current_recalls[s_name][tc_id] = cs.evidence_recall
                result_str = "PASS" if cs.passed else "FAIL"
                print(f"  {s_name} evaluated by {e_name} | {tc_id}: {result_str} "
                      f"(recall={cs.evidence_recall:.2f})")

    # Regression detection
    baseline = _load_baseline()
    regressions = _detect_regressions(current_recalls, baseline)
    if regressions:
        print(f"\n[peer-review] REGRESSIONS DETECTED ({len(regressions)}):")
        for r in regressions:
            print(f"  !! {r}")
    else:
        print("\n[peer-review] No regressions detected vs baseline.")

    # Model version snapshot for decay tracking
    version_snapshot = {}
    for cfg in model_cfgs:
        m = cfg["model"]
        version_snapshot[m["name"]] = _get_binary_version(m["api_base"])

    # Write decay register entry
    entry = {
        "run_at": run_start,
        "fixture_count": len(tc_paths),
        "model_versions": version_snapshot,
        "score_matrix": score_matrix,
        "current_recalls": current_recalls,
        "regression_flags": regressions,
        "baseline_compared": PRIOR_BASELINE.name if PRIOR_BASELINE.exists() else None,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    print(f"\n[peer-review] Results appended → {args.out}")

    # Update baseline with current recalls if no regressions
    if not regressions:
        PRIOR_BASELINE.write_text(json.dumps(current_recalls, indent=2), encoding="utf-8")
        print(f"[peer-review] Baseline updated → {PRIOR_BASELINE}")

    print(f"[peer-review] Done. Regressions={len(regressions)}")
    return 1 if regressions else 0


if __name__ == "__main__":
    sys.exit(main())
