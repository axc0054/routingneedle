"""
cascade.py — RoutingNeedle tiered cascade routing.

Implements failure propagation across model tiers:
  Tier 1: DeepSeek-V2-Lite (WX9100 Vulkan, fast triage)
  Tier 2: Qwen3-30B-A3B   (P5000 CUDA,    generalist reasoner)
  Tier 3+: Adjudicator queue (frontier models + user — not called live)

Propagation triggers (any one fires escalation to next tier):
  file_size          document below minimum viable size for this tier
  token_size         estimated tokens exceed model context ceiling
  file_type          non-.md extension (vault_extract enforces upstream)
  empty_file         document has no content after strip
  api_error          connection failure, timeout, or HTTP error from server
  first_token_decision  response echoes document header without reading content

Adjudicator queue: unresolved cases are appended as JSONL.
Frontier model API calls are NOT made here — cases are queued for external
orchestration or human review.
"""

import json
import pathlib
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from run_testcase import (
    TestCaseResult,
    load_testcase,
    load_model_config,
    run_testcase,
)
from vault_extract import load_vault_document


class EscalationReason(str, Enum):
    FILE_SIZE          = "file_size"
    TOKEN_SIZE         = "token_size"
    FILE_TYPE          = "file_type"
    EMPTY_FILE         = "empty_file"
    API_ERROR          = "api_error"
    FIRST_TOKEN_DECISION = "first_token_decision"


# Minimum document size (chars) for reliable tier-1 triage.
# Below this, DeepSeek-V2-Lite pattern-matches [DOCUMENT:] tags instead of reading.
_MIN_DOC_CHARS_TIER1 = 500

# Rough chars-per-token for technical Markdown (conservative; avoids false negatives)
_CHARS_PER_TOKEN = 4

# Token overhead reserved for output + routing metadata per API call
_OVERHEAD_TOKENS = 200

# Response length ceiling for first-token-decision detection
_ECHO_RESPONSE_MAX_CHARS = 80


@dataclass
class TierResult:
    tier: int
    model: str
    lane: str
    result: Optional[TestCaseResult]
    escalation_reasons: list[EscalationReason]
    elapsed_s: float
    skipped: bool = False


@dataclass
class CascadeResult:
    testcase_id: str
    tiers: list[TierResult]
    final_result: Optional[TestCaseResult]
    final_tier: int                           # 0 = no clean result from any tier
    queued_for_adjudication: bool
    adjudication_reasons: list[EscalationReason]


# ---------------------------------------------------------------------------
# Detection helpers
# ---------------------------------------------------------------------------

def _estimate_tokens(text: str) -> int:
    return len(text) // _CHARS_PER_TOKEN


def _is_first_token_decision(response: str) -> bool:
    """
    True when the model pattern-matched on document structure without reading content.

    Two forms:
    1. Short echo — DeepSeek-V2-Lite treats [DOCUMENT:] tags as conversation
       markers on short fixtures, producing a sub-80-char header echo in ~0.8s.
    2. Self-dialogue loop — model generates an alternating User:/Assistant:
       conversation instead of answering the query; occurs at temperature=0
       when document is short and ambiguous.
    """
    stripped = response.strip()
    if not stripped:
        return False
    # Short [DOCUMENT:] echo
    if len(stripped) < _ECHO_RESPONSE_MAX_CHARS and "[DOCUMENT:" in stripped:
        return True
    if stripped.startswith("[DOCUMENT:") and "\n" not in stripped:
        return True
    # Self-dialogue loop: model fabricates a Q&A conversation WITHOUT giving a real answer first.
    # Only fires if the first dialogue marker appears within 150 chars — meaning
    # the response began with a one-liner "decision" rather than a genuine answer.
    # Responses that give a real answer and then continue with dialogue are not flagged.
    if "\nUser:" in response and "\nAssistant:" in response:
        first_marker = min(
            response.find("\nUser:"),
            response.find("\nAssistant:"),
        )
        if first_marker < 150:
            return True
    return False


def detect_escalation(
    result: Optional[TestCaseResult],
    doc_content: str,
    doc_path: str,
    context_window: int,
    max_tokens: int,
    tier: int = 1,
) -> list[EscalationReason]:
    """
    Evaluate all propagation triggers for a given tier result.

    Pass result=None to run pre-flight checks before the API call.
    Returns list of EscalationReason values that fired (empty = no escalation).
    """
    reasons: list[EscalationReason] = []

    # file_type: non-.md hard stop — vault_extract blocks these, but cascade
    # checks at the boundary to produce a structured reason rather than an exception
    if not doc_path.endswith(".md"):
        reasons.append(EscalationReason.FILE_TYPE)
        return reasons  # nothing else to check

    # empty_file: no content after whitespace strip
    if not doc_content or not doc_content.strip():
        reasons.append(EscalationReason.EMPTY_FILE)
        return reasons

    # token_size: document would overflow context (checked before API call)
    token_budget = context_window - max_tokens - _OVERHEAD_TOKENS
    if _estimate_tokens(doc_content) > token_budget:
        reasons.append(EscalationReason.TOKEN_SIZE)

    # file_size: below tier-1 minimum; tier 2+ is more robust to short documents
    if tier == 1 and len(doc_content) < _MIN_DOC_CHARS_TIER1:
        reasons.append(EscalationReason.FILE_SIZE)

    if result is None:
        return reasons

    # api_error: any exception from the inference server, or empty response
    # (Qwen3 strips <think> blocks — if only thinking was produced, content is "")
    if result.error:
        reasons.append(EscalationReason.API_ERROR)
        return reasons  # no point checking response if it's empty
    if not result.response_text or not result.response_text.strip():
        reasons.append(EscalationReason.API_ERROR)
        return reasons

    # first_token_decision: model pattern-matched on structure without reading content
    if _is_first_token_decision(result.response_text):
        reasons.append(EscalationReason.FIRST_TOKEN_DECISION)

    return reasons


# ---------------------------------------------------------------------------
# Core cascade logic
# ---------------------------------------------------------------------------

def cascade_run(
    testcase_path: str | pathlib.Path,
    tier_model_configs: list[str | pathlib.Path],
    corpus_base: str | pathlib.Path,
    queue_path: str | pathlib.Path,
) -> CascadeResult:
    """
    Run a test case through the tier cascade.

    Each tier is attempted in order. If any propagation trigger fires, the
    case is escalated to the next tier. If all tiers are exhausted without a
    clean result, the case is appended to the adjudicator JSONL queue.

    Args:
        testcase_path:     path to TC-XX.toml
        tier_model_configs: ordered model config TOMLs (tier 1 first)
        corpus_base:       base directory for corpus documents
        queue_path:        JSONL file for adjudicator queue (appended)

    Returns:
        CascadeResult with per-tier results and final disposition
    """
    tc = load_testcase(testcase_path)
    tc_id = tc["testcase"]["id"]
    doc_rel = tc["testcase"]["document"]
    doc_path = str(pathlib.Path(corpus_base) / doc_rel)

    try:
        doc_content = load_vault_document(doc_path)
    except Exception:
        doc_content = ""

    tier_results: list[TierResult] = []
    final_result: Optional[TestCaseResult] = None
    final_tier = 0

    for tier_idx, model_config_path in enumerate(tier_model_configs, start=1):
        model = load_model_config(model_config_path)
        context_window = model["model"].get("context_window", 8192)
        max_tokens = model["model"].get("max_tokens", 256)
        model_name = model["model"].get("name", "unknown")
        lane = model["model"].get("lane", "unknown")

        # Pre-flight: check triggers that skip the API call entirely
        pre_reasons = detect_escalation(
            None, doc_content, doc_path, context_window, max_tokens, tier=tier_idx
        )

        hard_skip_triggers = {
            EscalationReason.FILE_TYPE,
            EscalationReason.EMPTY_FILE,
            EscalationReason.TOKEN_SIZE,
        }
        # file_size only skips tier 1 (tier 2+ handles short docs)
        if tier_idx == 1:
            hard_skip_triggers.add(EscalationReason.FILE_SIZE)

        if any(r in hard_skip_triggers for r in pre_reasons):
            tier_results.append(TierResult(
                tier=tier_idx,
                model=model_name,
                lane=lane,
                result=None,
                escalation_reasons=pre_reasons,
                elapsed_s=0.0,
                skipped=True,
            ))
            continue

        # Run the tier
        t0 = time.time()
        result = run_testcase(str(testcase_path), str(model_config_path), str(corpus_base))
        elapsed = round(time.time() - t0, 1)

        # Post-run trigger check
        post_reasons = detect_escalation(
            result, doc_content, doc_path, context_window, max_tokens, tier=tier_idx
        )

        tier_results.append(TierResult(
            tier=tier_idx,
            model=model_name,
            lane=lane,
            result=result,
            escalation_reasons=post_reasons,
            elapsed_s=elapsed,
        ))

        if not post_reasons:
            # No triggers fired — this tier's result is authoritative
            final_result = result
            final_tier = tier_idx
            break

    # All tiers exhausted without a clean result → adjudicator queue
    queued = final_result is None
    last_reasons = tier_results[-1].escalation_reasons if tier_results else []

    if queued:
        _enqueue_adjudicator(queue_path, tc_id, testcase_path, tier_results, last_reasons)

    return CascadeResult(
        testcase_id=tc_id,
        tiers=tier_results,
        final_result=final_result,
        final_tier=final_tier,
        queued_for_adjudication=queued,
        adjudication_reasons=last_reasons,
    )


# ---------------------------------------------------------------------------
# Adjudicator queue
# ---------------------------------------------------------------------------

def _enqueue_adjudicator(
    queue_path: str | pathlib.Path,
    tc_id: str,
    testcase_path: str | pathlib.Path,
    tier_results: list[TierResult],
    reasons: list[EscalationReason],
) -> None:
    """Append an unresolved case to the adjudicator JSONL queue."""
    entry = {
        "tc_id": tc_id,
        "testcase_path": str(testcase_path),
        "queued_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "escalation_reasons": [r.value for r in reasons],
        "tiers": [
            {
                "tier": tr.tier,
                "model": tr.model,
                "lane": tr.lane,
                "skipped": tr.skipped,
                "elapsed_s": tr.elapsed_s,
                "escalation_reasons": [r.value for r in tr.escalation_reasons],
                "response_excerpt": (
                    tr.result.response_text[:200]
                    if tr.result and tr.result.response_text else None
                ),
                "error": tr.result.error if tr.result else None,
            }
            for tr in tier_results
        ],
    }
    p = pathlib.Path(queue_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


# ---------------------------------------------------------------------------
# Cascade summary for reporting
# ---------------------------------------------------------------------------

def cascade_summary_line(cr: CascadeResult) -> str:
    """One-line human-readable summary for a CascadeResult."""
    if cr.queued_for_adjudication:
        reasons = ", ".join(r.value for r in cr.adjudication_reasons)
        return f"QUEUED ({reasons}) — exhausted {len(cr.tiers)} tier(s)"

    tier_note = ""
    if cr.final_tier > 1:
        skips = [f"T{tr.tier}:{','.join(r.value for r in tr.escalation_reasons)}"
                 for tr in cr.tiers if tr.escalation_reasons]
        tier_note = f" [escalated from {'; '.join(skips)}]"

    model = cr.final_result.model if cr.final_result else "unknown"
    lane = cr.final_result.lane if cr.final_result else "unknown"
    return f"T{cr.final_tier} ({model}/{lane}){tier_note}"
