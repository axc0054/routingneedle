"""
run_suite.py — RoutingNeedle full test suite runner.

Loads all tc*.toml files from configs/testcases/,
resolves corpus base paths from configs/corpora/,
runs each test case with document injection,
scores with council_scorer,
and produces a structured result table.

Usage (single-model):
  python3 bench/run_suite.py \
    --model configs/models/deepseek-v2-lite-wx9100.toml \
    --testcases configs/testcases/ \
    --corpora configs/corpora/ \
    [--tc TC-01 TC-03]

Usage (cascade — tier 1 then tier 2 on escalation):
  python3 bench/run_suite.py \
    --model configs/models/deepseek-v2-lite-wx9100.toml \
    --cascade configs/models/qwen3-30b-p5000.toml \
    --testcases configs/testcases/ \
    --corpora configs/corpora/ \
    [--queue /home/alex/logs/adjudicator_queue.jsonl]
"""

import argparse
import json
import pathlib
import sys
import time
import tomllib

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from run_testcase import run_testcase, load_testcase
from council_scorer import score
from cascade import cascade_run, cascade_summary_line


def load_corpus_configs(corpora_dir: str) -> dict[str, dict]:
    configs = {}
    for f in pathlib.Path(corpora_dir).glob("*.toml"):
        with open(f, "rb") as fh:
            cfg = tomllib.load(fh)
        if "corpus" not in cfg:
            continue  # skip legacy CodeNeedle [files]-style configs
        name = cfg["corpus"]["name"]
        configs[name] = cfg["corpus"]
    return configs


def load_testcases(testcases_dir: str,
                   filter_ids: list[str] | None = None) -> list[tuple[str, dict]]:
    tcs = []
    for f in sorted(pathlib.Path(testcases_dir).glob("tc*.toml")):
        with open(f, "rb") as fh:
            tc = tomllib.load(fh)
        tc_id = tc["testcase"]["id"]
        if filter_ids and tc_id not in filter_ids:
            continue
        tcs.append((str(f), tc))
    return tcs


def run_suite(model_config_path: str,
              testcases_dir: str,
              corpora_dir: str,
              filter_ids: list[str] | None = None,
              cascade_tier2: str | None = None,
              queue_path: str | None = None) -> list[dict]:
    corpora = load_corpus_configs(corpora_dir)
    testcases = load_testcases(testcases_dir, filter_ids)
    results = []

    for tc_path, tc in testcases:
        tc_id = tc["testcase"]["id"]
        corpus_name = tc["testcase"]["corpus"]

        if corpus_name not in corpora:
            results.append({
                "id": tc_id,
                "name": tc["testcase"].get("name", ""),
                "status": "ERROR",
                "reason": f"Corpus '{corpus_name}' not found in {corpora_dir}",
                "passed": False,
            })
            continue

        corpus_base = corpora[corpus_name]["base_path"]
        doc_path = pathlib.Path(corpus_base) / tc["testcase"]["document"]

        if not doc_path.exists():
            results.append({
                "id": tc_id,
                "name": tc["testcase"].get("name", ""),
                "status": "ERROR",
                "reason": f"Document not found: {doc_path}",
                "passed": False,
            })
            continue

        print(f"Running {tc_id}: {tc['testcase']['name']}", flush=True)
        t0 = time.time()

        if cascade_tier2:
            # Cascade mode: tier 1 → tier 2 on escalation → adjudicator queue
            _queue = queue_path or "/home/alex/logs/adjudicator_queue.jsonl"
            tier_configs = [model_config_path, cascade_tier2]
            cascade = cascade_run(tc_path, tier_configs, corpus_base, _queue)
            elapsed = round(time.time() - t0, 1)
            cascade_note = cascade_summary_line(cascade)

            if cascade.queued_for_adjudication:
                results.append({
                    "id": tc_id,
                    "name": tc["testcase"].get("name", ""),
                    "status": "QUEUED",
                    "reason": f"Escalated to adjudicator: {cascade_note}",
                    "passed": False,
                    "elapsed_s": elapsed,
                    "cascade": cascade_note,
                })
                print(f"  QUEUED — {cascade_note}", flush=True)
                continue

            result = cascade.final_result
        else:
            result = run_testcase(tc_path, model_config_path, corpus_base)
            cascade_note = None
            cascade = None

        elapsed = round(time.time() - t0, 1)

        if result.error:
            results.append({
                "id": tc_id,
                "name": tc["testcase"].get("name", ""),
                "status": "ERROR",
                "reason": result.error,
                "passed": False,
                "elapsed_s": elapsed,
            })
            continue

        council_score = score(result, tc, str(doc_path))

        results.append({
            "id": tc_id,
            "name": tc["testcase"]["name"],
            "scoring_mode": council_score.scoring_mode,
            "passed": council_score.passed,
            "evidence_recall": council_score.evidence_recall,
            "hallucination_flags": council_score.hallucination_flags,
            "missing_fields": council_score.missing_fields,
            "cloud_friendly_without_evidence":
                council_score.cloud_friendly_without_evidence,
            "notes": council_score.notes,
            "response_text": result.response_text,
            "response_excerpt": result.response_text[:200],
            "elapsed_s": elapsed,
            "model": result.model,
            **({"cascade": cascade_note} if cascade_note else {}),
            "lane": result.lane,
        })

        status = "PASS" if council_score.passed else "FAIL"
        print(f"  {status} — {council_score.notes[:100]}", flush=True)

    return results


def print_report(results: list[dict]) -> None:
    passed = sum(1 for r in results if r.get("passed"))
    total = len(results)
    errors = sum(1 for r in results if r.get("status") == "ERROR")

    queued = sum(1 for r in results if r.get("status") == "QUEUED")
    print("\n" + "=" * 60)
    print(f"ROUTINGNEEDLE SUITE — {passed}/{total} PASS  "
          f"({errors} ERROR, {queued} QUEUED)")
    print("=" * 60)

    for r in results:
        if r.get("status") == "ERROR":
            print(f"\n  ERROR | {r['id']} — {r.get('name', '')}")
            print(f"   {r['reason']}")
            continue

        if r.get("status") == "QUEUED":
            print(f"\n  QUEUED | {r['id']} — {r.get('name', '')}")
            print(f"   {r['reason']}")
            continue

        status = "PASS" if r.get("passed") else "FAIL"
        icon = "PASS" if r.get("passed") else "FAIL"
        print(f"\n{icon} | {r['id']} — {r['name']}")
        cascade_info = f" | Cascade: {r['cascade']}" if r.get("cascade") else ""
        print(f"   Mode: {r['scoring_mode']} | Recall: {r['evidence_recall']} | "
              f"Elapsed: {r.get('elapsed_s', '?')}s{cascade_info}")
        if r.get("hallucination_flags"):
            print(f"   Hallucinations: {r['hallucination_flags']}")
        if r.get("missing_fields"):
            print(f"   Missing: {r['missing_fields']}")
        if r.get("cloud_friendly_without_evidence") and not r.get("passed"):
            print(f"   HARD FAIL: cloud-friendly without evidence span")
        print(f"   Notes: {r['notes']}")
        print(f"   Response (200 chars): {r['response_excerpt']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True,
                        help="Tier-1 model config TOML")
    parser.add_argument("--cascade",
                        help="Tier-2 model config TOML (enables cascade mode)")
    parser.add_argument("--queue",
                        help="Adjudicator queue JSONL path "
                             "(default: /home/alex/logs/adjudicator_queue.jsonl)")
    parser.add_argument("--testcases", required=True)
    parser.add_argument("--corpora", required=True)
    parser.add_argument("--tc", nargs="*", help="Filter to specific TC IDs")
    parser.add_argument("--json-out", help="Write JSON results to file")
    args = parser.parse_args()

    results = run_suite(
        args.model, args.testcases, args.corpora, args.tc,
        cascade_tier2=args.cascade,
        queue_path=args.queue,
    )
    print_report(results)

    if args.json_out:
        pathlib.Path(args.json_out).write_text(
            json.dumps(results, indent=2), encoding="utf-8"
        )
        print(f"\nJSON results → {args.json_out}")
