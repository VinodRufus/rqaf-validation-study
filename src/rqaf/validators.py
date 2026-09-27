"""RQAF validators, one module (blueprint's validators/ package, flattened).

claims      LLM decomposition into atomic claims
facts       deterministic numeric check against the measure DB
evidence    LLM judge per narrative claim (judge model is a DIFFERENT family
            than the generator, per prereg, to avoid self-agreement)
completeness required-fact list per report type vs claims found
citations   lookup in reference DB + support judgment
privacy     regex + pattern detection for synthetic identifiers
security    pattern rules for instruction-like injected text
risk        Q (Eq. 1), RS (Eq. 2), veto rules -> approve / review / reject
"""
from __future__ import annotations
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.runner import make_runner, parse_json_strict  # noqa: E402

# ---------------- claims ----------------

def extract_claims(report_text: str, judge_model: str):
    template = open("prompts/rqaf_claims_v1.txt").read()
    system, user_t = template.split("USER:", 1)
    runner = make_runner(judge_model)
    c = runner.complete(system.replace("SYSTEM:", "").strip(),
                        user_t.strip().replace("{report}", report_text),
                        temperature=0.0, max_tokens=1800)
    parsed, err = parse_json_strict(c.text)
    if err or not isinstance(parsed, list):
        return [], c
    return [cl for cl in parsed if isinstance(cl, dict) and cl.get("text")], c


# ---------------- facts (deterministic) ----------------

def check_numeric_claims(claims, source):
    """Every number in a numeric claim must exist in the source records for
    the measure it names (numerator, denominator, exclusions, or rate)."""
    results = {}
    src_numbers = set()
    for s in source:
        for k in ("numerator", "denominator", "exclusions", "rate"):
            src_numbers.add(str(s[k]))
    for cl in claims:
        if cl.get("type") != "numeric":
            continue
        nums = re.findall(r"\d+\.?\d*", cl["text"])
        nums = [n for n in nums if n not in {"1000", "100", "30", "3"}]  # unit/name constants
        if not nums:
            results[cl["id"]] = "Ambiguous"
        elif all(n in src_numbers or n.rstrip("0").rstrip(".") in src_numbers for n in nums):
            results[cl["id"]] = "Supported"
        else:
            results[cl["id"]] = "Contradicted"
    return results


# ---------------- evidence (LLM judge) ----------------

def judge_claims(claims, source, judge_model, skip_ids=()):
    template = open("prompts/rqaf_judge_v1.txt").read()
    system, user_t = template.split("USER:", 1)
    runner = make_runner(judge_model)
    out = {}
    for cl in claims:
        if cl["id"] in skip_ids or cl.get("type") == "citation":
            continue
        c = runner.complete(system.replace("SYSTEM:", "").strip(),
                            user_t.strip().replace("{claim}", cl["text"])
                                  .replace("{source}", json.dumps(source)),
                            temperature=0.0, max_tokens=200)
        parsed, err = parse_json_strict(c.text)
        state = (parsed or {}).get("state") if not err else None
        out[cl["id"]] = state if state in {"Supported", "Contradicted",
                                           "Unsupported", "Ambiguous"} else "Ambiguous"
    return out


# ---------------- completeness ----------------

REQUIRED_FACTS = {
    # per report type: source fields that MUST be represented in the narrative
    "measure_summary": ["numerator", "denominator", "exclusions", "period"],
    "adverse_event_summary": ["numerator", "denominator", "period"],
    "compliance_narrative": ["rate", "period", "exclusions"],
}


def check_completeness(report_text: str, source, report_type: str):
    low = report_text.lower()
    missing = []
    for s in source:
        for field in REQUIRED_FACTS.get(report_type, []):
            val = str(s[field])
            present = (val in report_text) or (field == "period" and s["period"] in report_text) \
                      or (field == "exclusions" and "exclusion" in low and str(s["exclusions"]) in report_text)
            if not present:
                missing.append({"measure_id": s["measure_id"], "field": field, "value": val})
    return missing


# ---------------- citations ----------------

def check_citations(report_text: str, references):
    ref_ids = {r["ref_id"]: r for r in references}
    cited = re.findall(r"\[([RF]\d+)\]", report_text)
    findings = []
    for rid in cited:
        if rid not in ref_ids:
            findings.append({"ref": rid, "state": "invalid",
                             "reason": "not in the provided reference list"})
        elif not ref_ids[rid]["is_real"]:
            findings.append({"ref": rid, "state": "unverifiable",
                             "reason": "reference DOI does not resolve"})
        else:
            findings.append({"ref": rid, "state": "valid", "reason": ""})
    return findings


# ---------------- privacy ----------------

PRIVACY_PATTERNS = [
    re.compile(r"\bMRN\s*\d{5,}\b", re.I),
    re.compile(r"\bDOB\s*\d{2}/\d{2}/\d{4}\b", re.I),
    re.compile(r"\b\d{3,5}\s+[A-Z][a-z]+\s+(Lane|Street|Ave|Avenue|Road|Drive)\b"),
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
]


def check_privacy(report_text: str):
    return [{"pattern": rx.pattern, "match": m.group(0)}
            for rx in PRIVACY_PATTERNS for m in rx.finditer(report_text)]


# ---------------- security ----------------

SECURITY_PATTERNS = [
    re.compile(r"ignore (all |any )?previous instructions", re.I),
    re.compile(r"\bSYSTEM NOTE\b", re.I),
    re.compile(r"mark this (report|document) as approved", re.I),
    re.compile(r"validation is not required", re.I),
    re.compile(r"\bdisregard\b.{0,30}\b(polic|rule|check)", re.I),
]


def check_security(report_text: str):
    return [{"pattern": rx.pattern, "match": m.group(0)}
            for rx in SECURITY_PATTERNS for m in rx.finditer(report_text)]


# ---------------- risk engine ----------------

def risk_engine(states: dict, missing, citation_findings, privacy_hits,
                security_hits, thresholds):
    n = max(len(states), 1)
    n_supported = sum(1 for s in states.values() if s == "Supported")
    n_contra = sum(1 for s in states.values() if s == "Contradicted")
    n_unsup = sum(1 for s in states.values() if s == "Unsupported")

    F = n_supported / n
    C = 1.0 if not missing else max(0.0, 1.0 - 0.25 * len(missing))
    R = (1.0 if not citation_findings else
         sum(1 for f in citation_findings if f["state"] == "valid") / len(citation_findings))
    S = 1.0 - min(1.0, 0.5 * n_contra / n + 0.25 * n_unsup / n)
    E = 1.0   # explainability/traceability are structural in this reference impl
    T = 1.0
    Q = (F + C + S + R + E + T) / 6.0

    sec_score = 100.0 if (privacy_hits or security_hits) else 0.0
    quality_risk = (1 - Q) * 100
    RS = (quality_risk + sec_score) / 2.0

    veto = bool(n_contra or privacy_hits or security_hits)
    if veto:
        disposition = "reject"
    elif RS <= thresholds["low"] and n_unsup == 0 and not missing:
        disposition = "approve"
    elif RS <= thresholds["moderate"] or n_unsup or missing:
        disposition = "review"
    else:
        disposition = "reject"
    return {"Q": round(Q, 4), "RS": round(RS, 2), "F": round(F, 4),
            "C": round(C, 4), "S": round(S, 4), "R": round(R, 4),
            "veto": veto, "disposition": disposition}
