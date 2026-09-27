"""Run a system (rqaf | llm_self_check | single_pass_judge) over the
injected corpus and score detection against the injection gold.

Outputs per system:
  runs/rqaf/{system}.jsonl            raw per-report outputs
  results/rqaf/{system}_detection.csv per-error-type P/R/F1
  results/rqaf/{system}_dispo.csv     3x3 disposition confusion + accuracy + review load
  results/rqaf/rqaf_roc.csv           (rqaf only) RS vs has-critical-error, for ROC

Usage:
  python src/rqaf/evaluate.py --system rqaf
  python src/rqaf/evaluate.py --system llm_self_check
  python src/rqaf/evaluate.py --system single_pass_judge
"""
from __future__ import annotations
import argparse
import glob
import json
import os
import sys
import time
import yaml
from collections import defaultdict
from tqdm import tqdm

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rqaf.validators as V  # noqa: E402
import rqaf.baselines as BL  # noqa: E402

ERROR_TYPES = ["hallucinated_claim", "contradicted_claim", "omitted_required_fact",
               "invalid_citation", "unsupported_citation", "privacy_leak",
               "prompt_injection_artifact"]


def rqaf_run(report, cfg):
    t0 = time.time()
    claims, _ = V.extract_claims(report["text"], cfg["judge_model"])
    fact_states = V.check_numeric_claims(claims, report["source"])
    ev_states = V.judge_claims(claims, report["source"], cfg["judge_model"],
                               skip_ids=set(fact_states))
    states = {**ev_states, **fact_states}   # deterministic takes precedence
    missing = V.check_completeness(report["text"], report["source"], report["type"])
    cites = V.check_citations(report["text"], report["references"])
    privacy = V.check_privacy(report["text"])
    security = V.check_security(report["text"])
    risk = V.risk_engine(states, missing, cites, privacy, security,
                         cfg["risk_engine"]["thresholds"])
    detected = set()
    if any(s == "Contradicted" for s in states.values()):
        detected.add("contradicted_claim")
    if any(s == "Unsupported" for s in states.values()):
        detected.add("hallucinated_claim")
    if missing:
        detected.add("omitted_required_fact")
    if any(f["state"] == "invalid" for f in cites):
        detected.add("invalid_citation")
    if any(f["state"] == "unverifiable" for f in cites):
        detected.add("unsupported_citation")
    if privacy:
        detected.add("privacy_leak")
    if security:
        detected.add("prompt_injection_artifact")
    return {"detected_types": sorted(detected), "disposition": risk["disposition"],
            "risk": risk, "n_claims": len(claims),
            "latency_ms": int((time.time() - t0) * 1000)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--system", required=True,
                    choices=["rqaf", "llm_self_check", "single_pass_judge"])
    ap.add_argument("--config", default="config/prereg_rqaf.yaml")
    a = ap.parse_args()
    cfg = yaml.safe_load(open(a.config))
    os.makedirs("runs/rqaf", exist_ok=True)
    os.makedirs("results/rqaf", exist_ok=True)

    out_path = f"runs/rqaf/{a.system}.jsonl"
    done = set()
    if os.path.exists(out_path):
        done = {json.loads(l)["report_id"] for l in open(out_path)}

    rows = []
    for p in tqdm(sorted(glob.glob("data/rqaf/injected/*.json")), desc=a.system):
        report = json.load(open(p))
        rid = report["report_id"]
        if rid in done:
            continue
        if a.system == "rqaf":
            res = rqaf_run(report, cfg)
        elif a.system == "llm_self_check":
            res = BL.llm_self_check(report, cfg["generation_model"])
        else:
            res = BL.single_pass_judge(report, cfg["judge_model"])
        res["report_id"] = rid
        with open(out_path, "a") as f:
            f.write(json.dumps(res) + "\n")

    # ---- score against gold ----
    gold = {os.path.basename(p)[:-5]: json.load(open(p))
            for p in glob.glob("data/rqaf/gold/*.json")}
    outputs = {json.loads(l)["report_id"]: json.loads(l) for l in open(out_path)}

    det = defaultdict(lambda: dict(tp=0, fp=0, fn=0))
    dispo_rows, clean_fp = [], [0, 0]
    roc_rows = []
    for rid, g in gold.items():
        o = outputs.get(rid)
        if not o:
            continue
        injected = {i["type"] for i in g["injections"]}
        detected = set(o.get("detected_types") or [])
        for t in ERROR_TYPES:
            if t in injected and t in detected:
                det[t]["tp"] += 1
            elif t in detected:
                det[t]["fp"] += 1
            elif t in injected:
                det[t]["fn"] += 1
        dispo_rows.append(dict(report=rid, gold=g["gold_disposition"],
                               pred=o["disposition"]))
        if not injected:
            clean_fp[1] += 1
            clean_fp[0] += int(o["disposition"] != "approve")
        if a.system == "rqaf":
            roc_rows.append(dict(report=rid, RS=o["risk"]["RS"],
                                 has_critical=g["has_critical"]))

    det_rows = []
    for t in ERROR_TYPES:
        d = det[t]
        p = d["tp"] / (d["tp"] + d["fp"]) if d["tp"] + d["fp"] else None
        r = d["tp"] / (d["tp"] + d["fn"]) if d["tp"] + d["fn"] else None
        f1 = (2 * p * r / (p + r)) if p and r else (0.0 if (p is not None or r is not None) else None)
        det_rows.append(dict(error_type=t, **d, precision=p, recall=r, f1=f1))
    pd.DataFrame(det_rows).to_csv(f"results/rqaf/{a.system}_detection.csv", index=False)

    dd = pd.DataFrame(dispo_rows)
    conf = pd.crosstab(dd.gold, dd.pred)
    acc = float((dd.gold == dd.pred).mean())
    review_load = float((dd.pred == "review").mean())
    conf.to_csv(f"results/rqaf/{a.system}_dispo.csv")
    with open(f"results/rqaf/{a.system}_dispo.csv", "a") as f:
        f.write(f"\naccuracy,{acc}\nreview_load,{review_load}\n"
                f"clean_over_flag_rate,{clean_fp[0]/clean_fp[1] if clean_fp[1] else ''}\n")

    if roc_rows:
        pd.DataFrame(roc_rows).to_csv("results/rqaf/rqaf_roc.csv", index=False)
    print(f"{a.system}: disposition accuracy {acc:.3f}, review load {review_load:.3f}")


if __name__ == "__main__":
    main()
