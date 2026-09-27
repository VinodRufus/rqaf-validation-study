"""The two pre-registered baselines RQAF is compared against.

llm_self_check: the GENERATING model is asked whether its own report is
accurate and complete (the naive approach RQAF replaces).
single_pass_factuality_judge: one call to the judge model with report +
source, asked to list errors; no retrieval, no deterministic checks, no
citation or privacy modules.

Both return the same finding shape as the RQAF evaluate step so detection
metrics are computed identically.
"""
from __future__ import annotations
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.runner import make_runner, parse_json_strict  # noqa: E402

SELF_CHECK_SYS = (
    "You previously wrote the healthcare quality report below from the source "
    "records. Review your report for problems. Respond with JSON only: "
    '{"findings": [{"type": "hallucinated_claim" | "contradicted_claim" | '
    '"omitted_required_fact" | "invalid_citation" | "unsupported_citation" | '
    '"privacy_leak" | "prompt_injection_artifact", "detail": "..."}], '
    '"disposition": "approve" | "review" | "reject"}')

JUDGE_SYS = (
    "You are a factuality judge for healthcare quality reports. Compare the "
    "report against the source records and list every error you find. "
    "Respond with JSON only, same shape: "
    '{"findings": [{"type": "hallucinated_claim" | "contradicted_claim" | '
    '"omitted_required_fact" | "invalid_citation" | "unsupported_citation" | '
    '"privacy_leak" | "prompt_injection_artifact", "detail": "..."}], '
    '"disposition": "approve" | "review" | "reject"}')


def _run(system: str, model_id: str, report: dict):
    runner = make_runner(model_id)
    user = ("REPORT:\n" + report["text"] + "\n\nSOURCE RECORDS (JSON):\n"
            + json.dumps(report["source"]) + "\n\nREFERENCE LIST:\n"
            + "\n".join(f"[{r['ref_id']}] {r['citation']}" for r in report["references"]))
    c = runner.complete(system, user, temperature=0.0, max_tokens=900)
    parsed, err = parse_json_strict(c.text)
    findings = (parsed or {}).get("findings") or []
    detected = {f.get("type") for f in findings if isinstance(f, dict)}
    dispo = (parsed or {}).get("disposition")
    if dispo not in {"approve", "review", "reject"}:
        dispo = "review"
    return {"detected_types": sorted(t for t in detected if t),
            "disposition": dispo, "latency_ms": c.latency_ms,
            "parse_error": err}


def llm_self_check(report: dict, generation_model: str):
    return _run(SELF_CHECK_SYS, generation_model, report)


def single_pass_judge(report: dict, judge_model: str):
    return _run(JUDGE_SYS, judge_model, report)
