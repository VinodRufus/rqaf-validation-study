"""Pre-registered statistics for the RQAF validation study.

Implements exactly what config/prereg_rqaf.yaml commits to:
paired bootstrap (10,000 resamples, seed 20260923) for per-error-type
precision/recall/F1 and disposition accuracy, exact McNemar tests of RQAF
vs each baseline on per-report disposition correctness, Holm correction,
and a bootstrap CI for the risk-score ROC AUC.

Reads runs/rqaf/*.jsonl and data/rqaf/gold/*.json. Writes:
  results/rqaf/tableVI_detection_ci.csv
  results/rqaf/dispo_tests.csv
  results/rqaf/auc_ci.csv

Usage: python tools/rqaf_stats.py
"""
from __future__ import annotations
import glob
import json
import math
import os

import numpy as np
import pandas as pd

SEED = 20260923
N_BOOT = 10000
SYSTEMS = ["rqaf", "llm_self_check", "single_pass_judge"]
ERROR_TYPES = ["hallucinated_claim", "contradicted_claim", "omitted_required_fact",
               "invalid_citation", "unsupported_citation", "privacy_leak",
               "prompt_injection_artifact"]


def load():
    gold = {os.path.basename(p)[:-5]: json.load(open(p))
            for p in glob.glob("data/rqaf/gold/*.json")}
    runs = {}
    for s in SYSTEMS:
        path = f"runs/rqaf/{s}.jsonl"
        runs[s] = {json.loads(l)["report_id"]: json.loads(l) for l in open(path)}
    rids = sorted(set(gold) & set.intersection(*(set(r) for r in runs.values())))
    return gold, runs, rids


def prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else np.nan
    r = tp / (tp + fn) if tp + fn else np.nan
    f = 2 * p * r / (p + r) if (tp + fp) and (tp + fn) and (p + r) else (
        0.0 if (tp + fp) or (tp + fn) else np.nan)
    return p, r, f


def exact_mcnemar(b, c):
    """Two-sided exact binomial test on the discordant pairs."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(0, k + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def main():
    rng = np.random.default_rng(SEED)
    gold, runs, rids = load()
    n = len(rids)
    print(f"{n} reports scored by all {len(SYSTEMS)} systems.")

    # per-report contribution arrays: [report, error_type, (tp, fp, fn)]
    contrib = {s: np.zeros((n, len(ERROR_TYPES), 3), dtype=np.int32) for s in SYSTEMS}
    correct = {s: np.zeros(n, dtype=bool) for s in SYSTEMS}
    for i, rid in enumerate(rids):
        injected = {x["type"] for x in gold[rid]["injections"]}
        for s in SYSTEMS:
            o = runs[s][rid]
            detected = set(o.get("detected_types") or [])
            for j, t in enumerate(ERROR_TYPES):
                if t in injected and t in detected:
                    contrib[s][i, j, 0] = 1
                elif t in detected:
                    contrib[s][i, j, 1] = 1
                elif t in injected:
                    contrib[s][i, j, 2] = 1
            correct[s][i] = (o.get("disposition") == gold[rid]["gold_disposition"])

    idx = rng.integers(0, n, size=(N_BOOT, n))

    # --- Table VI with bootstrap CIs ---
    rows = []
    for s in SYSTEMS:
        boot = contrib[s][idx].sum(axis=1)          # [N_BOOT, type, 3]
        point = contrib[s].sum(axis=0)              # [type, 3]
        for j, t in enumerate(ERROR_TYPES):
            tp, fp, fn = point[j]
            p, r, f = prf(tp, fp, fn)
            bp, br, bf = [], [], []
            for k in range(N_BOOT):
                pp, rr, ff = prf(*boot[k, j])
                bp.append(pp); br.append(rr); bf.append(ff)
            lo = lambda a: float(np.nanpercentile(a, 2.5))
            hi = lambda a: float(np.nanpercentile(a, 97.5))
            rows.append(dict(system=s, error_type=t, tp=int(tp), fp=int(fp), fn=int(fn),
                             precision=p, precision_lo=lo(bp), precision_hi=hi(bp),
                             recall=r, recall_lo=lo(br), recall_hi=hi(br),
                             f1=f, f1_lo=lo(bf), f1_hi=hi(bf)))
    pd.DataFrame(rows).to_csv("results/rqaf/tableVI_detection_ci.csv", index=False)

    # --- disposition accuracy CIs + exact McNemar vs each baseline, Holm ---
    drows, pvals = [], []
    for s in SYSTEMS:
        accs = correct[s][idx].mean(axis=1)
        acc = float(correct[s].mean())
        row = dict(system=s, accuracy=acc,
                   acc_lo=float(np.percentile(accs, 2.5)),
                   acc_hi=float(np.percentile(accs, 97.5)))
        if s != "rqaf":
            b = int((correct["rqaf"] & ~correct[s]).sum())
            c = int((~correct["rqaf"] & correct[s]).sum())
            p = exact_mcnemar(b, c)
            row.update(mcnemar_b=b, mcnemar_c=c, p_raw=p)
            pvals.append((s, p))
        drows.append(row)
    pvals.sort(key=lambda x: x[1])
    holm = {}
    m = len(pvals)
    running = 0.0
    for rank, (s, p) in enumerate(pvals):
        adj = min(1.0, (m - rank) * p)
        running = max(running, adj)
        holm[s] = running
    for row in drows:
        if row["system"] in holm:
            row["p_holm"] = holm[row["system"]]
    pd.DataFrame(drows).to_csv("results/rqaf/dispo_tests.csv", index=False)

    # --- ROC AUC with bootstrap CI (rank-based) ---
    roc = pd.read_csv("results/rqaf/rqaf_roc.csv")
    y = roc["has_critical"].astype(bool).to_numpy()
    x = roc["RS"].to_numpy()

    def auc(xv, yv):
        pos, neg = xv[yv], xv[~yv]
        if not len(pos) or not len(neg):
            return np.nan
        gt = (pos[:, None] > neg[None, :]).sum()
        eq = (pos[:, None] == neg[None, :]).sum()
        return (gt + 0.5 * eq) / (len(pos) * len(neg))

    a0 = auc(x, y)
    nb = len(x)
    idx2 = rng.integers(0, nb, size=(N_BOOT, nb))
    aucs = [auc(x[i2], y[i2]) for i2 in idx2]
    pd.DataFrame([dict(auc=a0, auc_lo=float(np.nanpercentile(aucs, 2.5)),
                       auc_hi=float(np.nanpercentile(aucs, 97.5)),
                       n=nb, n_critical=int(y.sum()))]).to_csv(
        "results/rqaf/auc_ci.csv", index=False)

    print("\n=== disposition accuracy (95% CI), McNemar vs RQAF (Holm) ===")
    print(pd.DataFrame(drows).to_string(index=False))
    print(f"\nROC AUC = {a0:.3f} (95% CI {np.nanpercentile(aucs, 2.5):.3f}"
          f"-{np.nanpercentile(aucs, 97.5):.3f})")
    print("\nwrote results/rqaf/tableVI_detection_ci.csv, dispo_tests.csv, auc_ci.csv")


if __name__ == "__main__":
    main()
