"""Build the RQAF manuscript artifacts:

  results/rqaf/tables/tableVI_detection.md   RQAF vs baselines per error type
  results/rqaf/figures/fig_roc.png           ROC of RS vs has-critical-error,
                                          with the 40/70 thresholds marked
"""
from __future__ import annotations
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import roc_curve, auc


def main():
    os.makedirs("results/rqaf/tables", exist_ok=True)
    os.makedirs("results/rqaf/figures", exist_ok=True)

    frames = []
    for system in ["rqaf", "llm_self_check", "single_pass_judge"]:
        path = f"results/rqaf/{system}_detection.csv"
        if os.path.exists(path):
            d = pd.read_csv(path)
            d.insert(0, "system", system)
            frames.append(d)
    if frames:
        alld = pd.concat(frames)
        pivot = alld.pivot_table(index="error_type", columns="system",
                                 values="f1")
        pivot.round(3).to_csv("results/rqaf/tables/tableVI_detection.csv")
        lines = ["| Error type | " + " | ".join(pivot.columns) + " |",
                 "|---" * (len(pivot.columns) + 1) + "|"]
        for et, row in pivot.iterrows():
            lines.append("| " + et + " | " +
                         " | ".join("" if pd.isna(v) else f"{v:.3f}" for v in row.values) + " |")
        open("results/rqaf/tables/tableVI_detection.md", "w").write("\n".join(lines) + "\n")

    roc_path = "results/rqaf/rqaf_roc.csv"
    if os.path.exists(roc_path):
        d = pd.read_csv(roc_path)
        fpr, tpr, thr = roc_curve(d.has_critical.astype(int), d.RS)
        a = auc(fpr, tpr)
        fig, ax = plt.subplots(figsize=(4.2, 4))
        ax.plot(fpr, tpr, color="black", lw=1.2, label=f"RS (AUC = {a:.3f})")
        ax.plot([0, 1], [0, 1], ls="--", color="gray", lw=0.8)
        for cut, marker in [(40, "o"), (70, "s")]:
            idx = int(np.argmin(np.abs(thr - cut)))
            ax.plot(fpr[idx], tpr[idx], marker, color="black", ms=6,
                    label=f"threshold {cut}")
        ax.set_xlabel("False positive rate")
        ax.set_ylabel("True positive rate")
        ax.legend(fontsize=7, frameon=False, loc="lower right")
        ax.spines[["top", "right"]].set_visible(False)
        fig.tight_layout()
        fig.savefig("results/rqaf/figures/fig_roc.png", dpi=300)
        print(f"ROC AUC = {a:.3f}")
    print("RQAF tables and figures written to results/rqaf/")


if __name__ == "__main__":
    main()
