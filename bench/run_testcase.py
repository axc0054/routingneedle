"""
run_testcase.py — RoutingNeedle document injection pipeline.

Implements the core change from CodeNeedle:
  CodeNeedle: model answers from training knowledge
  RoutingNeedle: model answers from injected document context

Pipeline per test case:
  1. Load corpus document via vault_extract.load_vault_document()
  2. Build prompt: [DOCUMENT] {content} [END DOCUMENT] + {query}
  3. Optionally append /no_think suffix (per model config)
  4. Call OpenAI-compatible chat endpoint
  5. Return response text for scoring

All corpus inputs must be .md files.
vault_extract.load_vault_document() enforces this with a hard reject.
"""

import json
import pathlib
import tomllib
import urllib.request
from dataclasses import dataclass
from typing import Optional

from vault_extract import load_vault_document


DOCUMENT_WRAPPER = """\
[DOCUMENT: {name}]
{content}
[END DOCUMENT]

{query}"""


@dataclass
class TestCaseResult:
    testcase_id: str
    query: str
    document_path: str
    response_text: str
    model: str
    lane: str
    tok_per_sec: Optional[float]
    error: Optional[str]


def load_testcase(toml_path: str | pathlib.Path) -> dict:
    """Load a RoutingNeedle test case from TOML."""
    with open(toml_path, "rb") as f:
        return tomllib.load(f)


def load_model_config(toml_path: str | pathlib.Path) -> dict:
    """Load a model config TOML."""
    with open(toml_path, "rb") as f:
        return tomllib.load(f)


def build_prompt(document_path: str, document_name: str,
                 query: str, no_think: bool = False) -> str:
    """
    Build the document-injected prompt.
    Document content is prepended before the query (KV cache warm path).
    """
    content = load_vault_document(document_path)
    prompt = DOCUMENT_WRAPPER.format(
        name=document_name,
        content=content,
        query=query,
    )
    if no_think:
        prompt = prompt + " /no_think"
    return prompt


def call_api(api_base: str, model_id: str,
             prompt: str, max_tokens: int = 256) -> tuple[str, Optional[float]]:
    """
    Call the OpenAI-compatible chat endpoint.
    Returns (response_text, tokens_per_second).
    """
    payload = json.dumps({
        "model": model_id,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0,
    }).encode()

    req = urllib.request.Request(
        f"{api_base}/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read())

    msg = data["choices"][0]["message"]
    text = msg.get("content") or ""
    if not text.strip():
        # Qwen3 thinking mode: answer is in reasoning_content when content is empty
        text = msg.get("reasoning_content", "")
    tps = data.get("timings", {}).get("predicted_per_second")
    return text, tps


def run_testcase(
    testcase_path: str | pathlib.Path,
    model_config_path: str | pathlib.Path,
    corpus_base: str | pathlib.Path,
) -> TestCaseResult:
    """
    Run a single RoutingNeedle test case with document injection.

    Args:
        testcase_path: path to TC-XX.toml
        model_config_path: path to model TOML config
        corpus_base: base directory for corpus documents

    Returns:
        TestCaseResult with raw response for scoring
    """
    tc = load_testcase(testcase_path)
    model = load_model_config(model_config_path)

    doc_rel = tc["testcase"]["document"]
    doc_path = pathlib.Path(corpus_base) / doc_rel
    query = tc["testcase"]["query"]
    # model-level force_no_think overrides TC setting (prevents Qwen3 thinking mode)
    no_think = tc["testcase"].get("no_think", False) or model["model"].get("force_no_think", False)
    max_tokens = model["model"].get("max_tokens", 256)

    try:
        prompt = build_prompt(str(doc_path), doc_rel, query, no_think)
        response, tps = call_api(
            model["model"]["api_base"],
            model["model"]["model_id"],
            prompt,
            max_tokens,
        )
        return TestCaseResult(
            testcase_id=tc["testcase"]["id"],
            query=query,
            document_path=str(doc_path),
            response_text=response,
            model=model["model"]["name"],
            lane=model["model"]["lane"],
            tok_per_sec=tps,
            error=None,
        )
    except Exception as e:
        return TestCaseResult(
            testcase_id=tc["testcase"]["id"],
            query=query,
            document_path=str(doc_path),
            response_text="",
            model=model["model"].get("name", "unknown"),
            lane=model["model"].get("lane", "unknown"),
            tok_per_sec=None,
            error=str(e),
        )


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 4:
        print("Usage: run_testcase.py <testcase.toml> <model.toml> <corpus_base>")
        sys.exit(1)

    result = run_testcase(sys.argv[1], sys.argv[2], sys.argv[3])
    print(f"TC: {result.testcase_id}")
    print(f"Model: {result.model} ({result.lane})")
    if result.error:
        print(f"ERROR: {result.error}")
    else:
        print(f"Response ({len(result.response_text)} chars):")
        print(result.response_text[:500])
