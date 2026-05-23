"""
council_scorer.py — RoutingNeedle evidence-span scorer.

Replaces CodeNeedle's line-recall difflib scorer for council QA.

Scoring contract:
  CodeNeedle: did the model reproduce these exact lines?
  RoutingNeedle: did the model cite real evidence from the source document?

Five scoring modes:
  keyword_match    — expected value must appear in response verbatim
  multi_field      — all expected key=value pairs must appear in response
  evidence_span    — response must cite text present in source document
  routing_assertion — response routing decision matches expected routing class
  schema_validate  — response must contain required schema fields

Cloud-friendly routing rule:
  A classification of cloud-friendly without an evidence span is INVALID.
  Such responses score as FAIL regardless of other criteria.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from vault_extract import load_vault_document


@dataclass
class CouncilScore:
    testcase_id: str
    scoring_mode: str
    passed: bool
    evidence_recall: float              # 0.0–1.0: how much expected content found
    hallucination_flags: list[str]      # model claims not in source document
    missing_fields: list[str]           # expected fields absent from response
    cloud_friendly_without_evidence: bool  # hard fail condition
    notes: str = ""


def _normalize(text: str) -> str:
    """Normalize whitespace and case for comparison."""
    return re.sub(r"\s+", " ", text).strip().lower()


def _check_cloud_friendly_evidence(response: str, source: str) -> bool:
    """
    Returns True if response claims cloud-friendly routing WITHOUT
    citing a verbatim evidence span present in the source document.
    This is always a hard FAIL condition.

    Requires quoted text traceable to the source — reasoning conjunctions
    ("because", "since") alone are not sufficient evidence.
    """
    resp_lower = response.lower()
    if "cloud-friendly" not in resp_lower and "cloud_friendly" not in resp_lower:
        return False

    # Cloud-friendly claim found. Must have a real quoted span from source.
    quotes = re.findall(r'"([^"]{10,})"', response)
    if not quotes:
        return True  # claiming cloud-friendly with no quoted evidence → hard fail

    src_norm = _normalize(source)
    for q in quotes:
        if _normalize(q) in src_norm:
            return False  # found at least one real evidence span → OK
    return True  # all quotes are hallucinated → hard fail


def score_keyword_match(
    tc_id: str, response: str, source: str,
    expected: str, failure_signal: str = ""
) -> CouncilScore:
    """Expected value must appear verbatim in response."""
    resp_norm = _normalize(response)
    exp_norm = _normalize(expected)
    found = exp_norm in resp_norm
    cf_no_evidence = _check_cloud_friendly_evidence(response, source)

    return CouncilScore(
        testcase_id=tc_id,
        scoring_mode="keyword_match",
        passed=found and not cf_no_evidence,
        evidence_recall=1.0 if found else 0.0,
        hallucination_flags=[failure_signal] if not found and failure_signal else [],
        missing_fields=[] if found else [expected],
        cloud_friendly_without_evidence=cf_no_evidence,
        notes=f"Expected: '{expected}' — {'FOUND' if found else 'NOT FOUND'}",
    )


def score_multi_field(
    tc_id: str, response: str, source: str,
    expected_fields: dict[str, str],
) -> CouncilScore:
    """All expected key=value pairs must appear in response."""
    resp_norm = _normalize(response)
    found = []
    missing = []
    for key, val in expected_fields.items():
        if _normalize(val) in resp_norm:
            found.append(key)
        else:
            missing.append(key)

    recall = len(found) / len(expected_fields) if expected_fields else 0.0
    cf_no_evidence = _check_cloud_friendly_evidence(response, source)

    return CouncilScore(
        testcase_id=tc_id,
        scoring_mode="multi_field",
        passed=len(missing) == 0 and not cf_no_evidence,
        evidence_recall=recall,
        hallucination_flags=[],
        missing_fields=missing,
        cloud_friendly_without_evidence=cf_no_evidence,
        notes=f"Found {len(found)}/{len(expected_fields)} fields. Missing: {missing}",
    )


def score_evidence_span(
    tc_id: str, response: str, source: str,
    expected: str,
) -> CouncilScore:
    """
    Response must cite text present in source document.
    Checks: expected value present AND any quoted text is real.
    """
    resp_norm = _normalize(response)
    src_norm = _normalize(source)
    exp_norm = _normalize(expected)

    value_found = exp_norm in resp_norm
    cf_no_evidence = _check_cloud_friendly_evidence(response, source)

    quotes = re.findall(r'"([^"]{8,})"', response)
    hallucinations = []
    for q in quotes:
        if _normalize(q) not in src_norm:
            hallucinations.append(q[:60] + "..." if len(q) > 60 else q)

    return CouncilScore(
        testcase_id=tc_id,
        scoring_mode="evidence_span",
        passed=value_found and not hallucinations and not cf_no_evidence,
        evidence_recall=1.0 if value_found else 0.0,
        hallucination_flags=hallucinations,
        missing_fields=[] if value_found else [expected],
        cloud_friendly_without_evidence=cf_no_evidence,
        notes=(
            f"Value {'found' if value_found else 'missing'}. "
            f"Hallucinated quotes: {len(hallucinations)}"
        ),
    )


LOCAL_ONLY_SYNONYMS = [
    "local-only", "local_only", "on-premises", "on-prem", "on premises",
    "not route to cloud", "internal only", "keep local", "do not route",
    "quarantine", "sensitive", "pii", "legal-strict", "parenting-sensitive",
]

CLOUD_FRIENDLY_SYNONYMS = [
    "cloud-friendly", "cloud_friendly", "route to cloud", "cloud inference",
    "safe for cloud",
]

_NEGATION_RE = re.compile(r'\b(no|not|without|none|never)\b')
_SENTENCE_SPLIT_RE = re.compile(r'[.!?\n]')


def _find_non_negated(synonyms: list[str], text: str) -> str | None:
    """
    Return the first synonym found in text that is NOT in a negated sentence
    context. Searches back to the nearest sentence boundary to handle long
    negation spans like 'no X or Y that is classified as local-only'.
    """
    text_lower = text.lower()
    for syn in synonyms:
        pos = text_lower.find(syn)
        while pos != -1:
            # Find start of the current sentence
            sentence_start = max(
                (m.end() for m in _SENTENCE_SPLIT_RE.finditer(text_lower[:pos])),
                default=0,
            )
            sentence = text_lower[sentence_start:pos]
            if not _NEGATION_RE.search(sentence):
                return syn
            pos = text_lower.find(syn, pos + 1)
    return None


def score_routing_assertion(
    tc_id: str, response: str, source: str,
    expected_route: str, failure_signal: str = ""
) -> CouncilScore:
    """
    Response routing decision must match expected routing class.
    Highest-risk-wins: any non-negated risk synonym takes priority over
    cloud-friendly when expected is a restrictive class.
    Negation detection prevents 'no local-only content' from firing as a risk flag.
    """
    exp_lower = expected_route.lower()

    local_match = _find_non_negated(LOCAL_ONLY_SYNONYMS, response)
    cloud_match = _find_non_negated(CLOUD_FRIENDLY_SYNONYMS, response)
    cf_no_evidence = _check_cloud_friendly_evidence(response, source)

    # Expected: local-only (or equivalent restrictive class)
    if any(r in exp_lower for r in ["local", "quarantine", "sensitive", "pii", "strict"]):
        route_found = local_match is not None
        passed = route_found and not (cloud_match and not local_match)
        return CouncilScore(
            testcase_id=tc_id,
            scoring_mode="routing_assertion",
            passed=passed,
            evidence_recall=1.0 if route_found else 0.0,
            hallucination_flags=[failure_signal] if (cf_no_evidence and not passed) else [],
            missing_fields=[] if passed else [f"expected route: {expected_route}"],
            cloud_friendly_without_evidence=cf_no_evidence,
            notes=(
                f"Expected: '{expected_route}'. "
                f"Local match: {local_match}. "
                f"Cloud match: {cloud_match}"
            ),
        )

    # Expected: cloud-friendly
    route_found = cloud_match is not None
    # Local synonym (non-negated) overrides cloud-friendly via highest-risk-wins
    overridden_by_risk = local_match is not None
    passed = route_found and not overridden_by_risk and not cf_no_evidence
    return CouncilScore(
        testcase_id=tc_id,
        scoring_mode="routing_assertion",
        passed=passed,
        evidence_recall=1.0 if route_found else 0.0,
        hallucination_flags=[failure_signal] if cf_no_evidence else [],
        missing_fields=[] if passed else [f"expected route: {expected_route}"],
        cloud_friendly_without_evidence=cf_no_evidence,
        notes=(
            f"Expected: '{expected_route}'. "
            f"Cloud match: {cloud_match}. "
            f"Local override: {local_match}. "
            f"CF-no-evidence: {cf_no_evidence}"
        ),
    )


def score_peer_review(
    tc_id: str,
    response: str,
    source: str,
    reference_response: str,
) -> CouncilScore:
    """
    Blind cross-evaluation scorer for the Offline Peer Review Matrix.

    Evaluates `response` against the source document and a reference response
    from another model (model identifier must be stripped before calling).

    Scoring criteria:
      1. Evidence grounding  — response cites text present in source
      2. Hallucination check — quoted claims traceable to source
      3. Contradiction check — response makes no claims that directly contradict
                               the reference response on factual assertions
      4. Completeness delta  — reference response contains key spans absent from response

    Returns CouncilScore. The `notes` field carries the detailed cross-comparison.
    Evidence recall is based on shared key spans with the reference response.
    """
    resp_norm = _normalize(response)
    ref_norm  = _normalize(reference_response)
    src_norm  = _normalize(source)

    # Evidence grounding: quoted spans must be traceable to source
    quotes = re.findall(r'"([^"]{8,})"', response)
    hallucinations = []
    for q in quotes:
        if _normalize(q) not in src_norm:
            hallucinations.append(q[:60] + "..." if len(q) > 60 else q)

    # Completeness delta: extract key noun phrases (≥3 words) from reference
    # that are absent from the evaluated response — a rough coverage gap signal.
    ref_phrases = re.findall(r'[a-z][a-z0-9 ]{15,40}[a-z0-9]', ref_norm)
    missing_ref_spans = [p for p in ref_phrases if p not in resp_norm]
    coverage_gap = len(missing_ref_spans) / max(len(ref_phrases), 1)
    evidence_recall = round(1.0 - coverage_gap, 3)

    # Contradiction check: look for numeric or named facts in reference that
    # appear with a different value in the response.
    # Strategy: extract "word + digits" patterns; flag if they appear in reference
    # but a different digit sequence appears near the same word in response.
    contradictions: list[str] = []
    for m in re.finditer(r'(\b[a-z_]+\b)\s+(\d[\d.,]+)', ref_norm):
        label, ref_val = m.group(1), m.group(2)
        resp_match = re.search(rf'\b{re.escape(label)}\b\s+(\d[\d.,]+)', resp_norm)
        if resp_match and resp_match.group(1) != ref_val:
            contradictions.append(f"{label}: ref={ref_val}, response={resp_match.group(1)}")

    cf_no_evidence = _check_cloud_friendly_evidence(response, source)
    passed = (
        not hallucinations
        and not contradictions
        and not cf_no_evidence
        and evidence_recall >= 0.6
    )

    notes = (
        f"evidence_recall={evidence_recall:.2f} | "
        f"hallucinations={len(hallucinations)} | "
        f"contradictions={len(contradictions)} | "
        f"coverage_gap_phrases={len(missing_ref_spans)}"
    )
    if contradictions:
        notes += f" | contradictions_detail={contradictions[:3]}"

    return CouncilScore(
        testcase_id=tc_id,
        scoring_mode="peer_review",
        passed=passed,
        evidence_recall=evidence_recall,
        hallucination_flags=hallucinations,
        missing_fields=missing_ref_spans[:5],
        cloud_friendly_without_evidence=cf_no_evidence,
        notes=notes,
    )


def score(result, testcase: dict, source_path: str) -> CouncilScore:
    """
    Dispatch to correct scorer based on testcase scoring_mode.
    Entry point called by the test runner.
    """
    tc = testcase["testcase"]
    tc_id = tc["id"]
    mode = tc["scoring_mode"]
    response = result.response_text
    source = load_vault_document(source_path)

    if mode == "keyword_match":
        return score_keyword_match(
            tc_id, response, source,
            tc["expected_extraction"],
            tc.get("failure_signal", ""),
        )
    elif mode == "multi_field":
        fields = {k: v for k, v in tc.items() if k.startswith("expected_")}
        return score_multi_field(tc_id, response, source, fields)
    elif mode == "evidence_span":
        return score_evidence_span(
            tc_id, response, source,
            tc["expected_extraction"],
        )
    elif mode == "routing_assertion":
        return score_routing_assertion(
            tc_id, response, source,
            tc["expected_route"],
            tc.get("failure_signal", ""),
        )
    elif mode == "peer_review":
        return score_peer_review(
            tc_id, response, source,
            tc.get("reference_response", ""),
        )
    else:
        raise ValueError(f"Unknown scoring mode: {mode}")
