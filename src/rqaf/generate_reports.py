"""Generate the clean synthetic quality reports from the measure DB.

Each report draws 2-3 measure-period records and 1-3 references (mixed
real/fake by design), and the writer model is instructed to write strictly
from source. The clean reports are the substrate for controlled error
injection; residual generation errors are themselves detectable later and
are labeled during gold labeling.

Usage: python src/rqaf/generate_reports.py --config config/prereg_rqaf.yaml
"""
from __future__ import annotations
import argparse
import json
import os
import random
import sys
import yaml
from tqdm import tqdm

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.runner import make_runner, append_jsonl, completion_record  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/prereg_rqaf.yaml")
    a = ap.parse_args()
    cfg = yaml.safe_load(open(a.config))
    rng = random.Random(cfg["injection"]["seed"])

    db = json.load(open("data/rqaf/source/measure_db.json"))
    refs = json.load(open("data/rqaf/source/reference_db.json"))
    template = open("prompts/rqaf_generate_v1.txt").read()
    system, user_t = template.split("USER:", 1)
    system = system.replace("SYSTEM:", "").strip()
    runner = make_runner(cfg["generation_model"])

    os.makedirs("data/rqaf/reports", exist_ok=True)
    n = cfg["reports"]["n"]
    types = cfg["reports"]["types"]
    for i in tqdm(range(1, n + 1), desc="generate reports"):
        rid = f"A-{i:03d}"
        out = f"data/rqaf/reports/{rid}.json"
        if os.path.exists(out):
            continue
        rtype = types[(i - 1) % len(types)]
        source = rng.sample(db, rng.randint(2, 3))
        ref_pick = rng.sample(refs, rng.randint(1, 3))
        ref_list = "\n".join(f"[{r['ref_id']}] {r['citation']}" for r in ref_pick)
        user = (user_t.strip()
                .replace("{report_type}", rtype.replace("_", " "))
                .replace("{source}", json.dumps(source, indent=1))
                .replace("{references}", ref_list))
        c = runner.complete(system, user, temperature=0.2, max_tokens=900)
        json.dump({"report_id": rid, "type": rtype, "text": c.text,
                   "source": source, "references": ref_pick,
                   "gen_meta": completion_record(c)},
                  open(out, "w"), indent=1)
    print("clean reports in data/rqaf/reports/. Next: inject_errors.py")


if __name__ == "__main__":
    main()
