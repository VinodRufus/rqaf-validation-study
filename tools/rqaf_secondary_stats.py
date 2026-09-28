"""Secondary analyses for the RQAF validation study (offline, no API calls).

1. Three-class confusion matrices and per-class precision/recall/F1 with
   macro-F1 for each system (Approve / Review / Reject).
2. Exact Clopper-Pearson 95% intervals for every detection precision and
   recall cell, including the cells where the bootstrap is degenerate.
3. Secondary ROC: reports containing deterministic security injections
   (privacy leak, prompt-injection artifact) are excluded, and the risk
   score is evaluated against the presence of a semantic critical error
   (contradicted claim or omitted required fact) among the remainder.

Writes: results/rqaf/class_metrics.csv, detection_exact_ci.csv,
        secondary_roc.csv
Usage:  python tools/rqaf_secondary_stats.py
"""
from __future__ import annotations
import glob
import json
import math
import os

import numpy as np
import pandas as pd

SEED = 20260923
SYSTEMS = ["rqaf", "llm_self_check", "single_pass_judge"]
CLASSES = ["approve", "review", "reject"]
ERROR_TYPES = ["hallucinated_claim", "contradicted_claim", "omitted_required_fact",
               "invalid_citation", "unsupported_citation", "privacy_leak",
               "prompt_injection_artifact"]
SEC_TYPES = {"privacy_leak", "prompt_injection_artifact"}
SEM_CRIT = {"contradicted_claim", "omitted_required_fact"}


def binom_cdf(k, n, p):
    if p <= 0:
        return 1.0
    if p >= 1:
        return 0.0 if k < n else 1.0
    return sum(math.comb(n, i) * p**i * (1 - p)**(n - i) for i in range(0, k + 1))


def cp_interval(x, n, alpha=0.05):
    """Exact Clopper-Pearson interval by bisection."""
    if n == 0:
        return (float("nan"), float("nan"))
    if x == 0:
        lo = 0.0
    else:
        a, b = 0.0, 1.0
        for _ in range(80):
            m = (a + b) / 2
            if 1 - binom_cdf(x - 1, n, m) < alpha / 2:
                a = m
            else:
                b = m
        lo = (a + b) / 2
    if x == n:
        hi = 1.0
    else:
        a, b = 0.0, 1.0
        for _ in range(80):
            m = (a + b) / 2
            if binom_cdf(x, n, m) > alpha / 2:
                a = m
            else:
                b = m
        hi = (a + b) / 2
    return (lo, hi)


def main():
    gold = {os.path.basename(p)[:-5]: json.load(open(p))
            for p in glob.glob("data/rqaf/gold/*.json")}
    runs = {}
    for s in SYSTEMS:
        runs[s] = {json.loads(l)["report_id"]: json.loads(l)
                   for l in open(f"runs/rqaf/{s}.jsonl")}
    rids = sorted(set(gold) & set.intersection(*(set(r) for r in runs.values())))
    print(f"{len(rids)} reports scored by all systems.")

    # ---- 1. class-level metrics ----
    rows = []
    for s in SYSTEMS:
        conf = {(g, p): 0 for g in CLASSES for p in CLASSES}
        for rid in rids:
            g = gold[rid]["gold_disposition"]
            p = runs[s][rid].get("disposition")
            if p not in CLASSES:
                p = "reject"   # unparseable treated as most conservative
            conf[(g, p)] += 1
        f1s = []
        for c in CLASSES:
            tp = conf[(c, c)]
            pred = sum(conf[(g, c)] for g in CLASSES)
            act = sum(conf[(c, p)] for p in CLASSES)
            P = tp / pred if pred else float("nan")
            R = tp / act if act else float("nan")
            F = 2 * P * R / (P + R) if pred and act and (P + R) else 0.0
            f1s.append(F)
            rows.append(dict(system=s, cls=c, tp=tp, predicted=pred, actual=act,
                             precision=P, recall=R, f1=F))
        rows.append(dict(system=s, cls="MACRO", tp="", predicted="", actual="",
                         precision="", recall="", f1=float(np.nanmean(f1s))))
        print(f"\n{s} confusion (rows=gold, cols=pred approve/review/reject):")
        for g in CLASSES:
            print("  ", g.ljust(8), [conf[(g, p)] for p in CLASSES])
    pd.DataFrame(rows).to_csv("results/rqaf/class_metrics.csv", index=False)

    # ---- 2. exact CIs for detection P and R ----
    det_rows = []
    for s in SYSTEMS:
        counts = {t: dict(tp=0, fp=0, fn=0) for t in ERROR_TYPES}
        for rid in rids:
            injected = {i["type"] for i in gold[rid]["injections"]}
            detected = set(runs[s][rid].get("detected_types") or [])
            for t in ERROR_TYPES:
                if t in injected and t in detected:
                    counts[t]["tp"] += 1
                elif t in detected:
                    counts[t]["fp"] += 1
                elif t in injected:
                    counts[t]["fn"] += 1
        for t in ERROR_TYPES:
            c = counts[t]
            np_, nr = c["tp"] + c["fp"], c["tp"] + c["fn"]
            plo, phi = cp_interval(c["tp"], np_) if np_ else (float("nan"),) * 2
            rlo, rhi = cp_interval(c["tp"], nr) if nr else (float("nan"),) * 2
            det_rows.append(dict(system=s, error_type=t, tp=c["tp"], fp=c["fp"],
                                 fn=c["fn"],
                                 precision=c["tp"] / np_ if np_ else float("nan"),
                                 precision_exact_lo=plo, precision_exact_hi=phi,
                                 recall=c["tp"] / nr if nr else float("nan"),
                                 recall_exact_lo=rlo, recall_exact_hi=rhi))
    pd.DataFrame(det_rows).to_csv("results/rqaf/detection_exact_ci.csv", index=False)
    perf = [r for r in det_rows if r["system"] == "rqaf" and r["precision"] == 1.0
            and r["recall"] == 1.0]
    print("\nExact 95% lower bounds for RQAF perfect cells:")
    for r in perf:
        print(f"  {r['error_type']}: recall >= {r['recall_exact_lo']:.3f} "
              f"(n={r['tp']})")

    # ---- 3. secondary ROC ----
    rng = np.random.default_rng(SEED)
    keep, y, x = [], [], []
    for rid in rids:
        injected = {i["type"] for i in gold[rid]["injections"]}
        if injected & SEC_TYPES:
            continue
        risk = runs["rqaf"][rid].get("risk") or {}
        if "RS" not in risk:
            continue
        keep.append(rid)
        y.append(bool(injected & SEM_CRIT))
        x.append(float(risk["RS"]))
    y = np.array(y); x = np.array(x)

    def auc(xv, yv):
        pos, neg = xv[yv], xv[~yv]
        if not len(pos) or not len(neg):
            return float("nan")
        gt = (pos[:, None] > neg[None, :]).sum()
        eq = (pos[:, None] == neg[None, :]).sum()
        return (gt + 0.5 * eq) / (len(pos) * len(neg))

    a0 = auc(x, y)
    nb = len(x)
    idx = rng.integers(0, nb, size=(10000, nb))
    aucs = [auc(x[i], y[i]) for i in idx]
    lo, hi = np.nanpercentile(aucs, 2.5), np.nanpercentile(aucs, 97.5)
    pd.DataFrame([dict(analysis="semantic_critical_excl_security", auc=a0,
                       auc_lo=float(lo), auc_hi=float(hi), n=nb,
                       n_positive=int(y.sum()))]).to_csv(
        "results/rqaf/secondary_roc.csv", index=False)
    print(f"\nSECONDARY ROC (security-injection reports excluded, n={nb}, "
          f"{int(y.sum())} semantic-critical):")
    print(f"  AUC = {a0:.3f} (95% CI {lo:.3f}-{hi:.3f})")
    print("\nwrote results/rqaf/class_metrics.csv, detection_exact_ci.csv, "
          "secondary_roc.csv")


if __name__ == "__main__":
    main()
