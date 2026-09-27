"""Build the synthetic quality-measure database and the reference database.

All values are generated. None are taken from any real system. The reference
DB mixes well-formed-but-fictitious citations (fake DOIs that resolve
nowhere, flagged is_real=false) with real public standards (NIST, WHO) so
the citation validator has both valid and invalid targets.

Usage: python src/rqaf/make_source.py --config config/prereg_rqaf.yaml
"""
from __future__ import annotations
import argparse
import json
import os
import random
import yaml

MEASURES = [
    ("CLABSI-01", "Central line-associated bloodstream infection rate", "per 1,000 line-days"),
    ("READM-30", "30-day all-cause readmission rate", "percent"),
    ("SEP-B1", "Sepsis bundle compliance within 3 hours", "percent"),
    ("HAPI-02", "Hospital-acquired pressure injury rate", "percent"),
    ("MED-REC", "Medication reconciliation completion at discharge", "percent"),
]
PERIODS = ["2026-Q1", "2026-Q2"]

REAL_REFS = [
    {"ref_id": "R1", "is_real": True, "citation": "NIST AI 100-1, Artificial Intelligence Risk Management Framework (AI RMF 1.0), 2023.", "topic": "ai risk management"},
    {"ref_id": "R2", "is_real": True, "citation": "NIST AI 600-1, Generative Artificial Intelligence Profile, 2024.", "topic": "generative ai risk"},
    {"ref_id": "R3", "is_real": True, "citation": "NIST SP 800-53 Rev. 5, Security and Privacy Controls for Information Systems and Organizations, 2020.", "topic": "security controls"},
    {"ref_id": "R4", "is_real": True, "citation": "NIST SP 800-207, Zero Trust Architecture, 2020.", "topic": "zero trust"},
    {"ref_id": "R5", "is_real": True, "citation": "WHO, Ethics and Governance of Artificial Intelligence for Health, 2021.", "topic": "ai ethics health"},
    {"ref_id": "R6", "is_real": True, "citation": "NIST CSWP 29, The NIST Cybersecurity Framework (CSF) 2.0, 2024.", "topic": "cybersecurity framework"},
]

FAKE_AUTHORS = ["J. Ellison", "M. Okafor", "T. Lindqvist", "R. Deshmukh", "A. Marchetti",
                "K. Watanabe", "P. Novak", "S. Almeida", "D. Kowalczyk", "H. Bergstrom"]
FAKE_TOPICS = ["quality measure automation", "nurse staffing analytics", "sepsis surveillance",
               "readmission prediction", "infection control dashboards", "clinical audit sampling"]
FAKE_JOURNALS = ["Journal of Synthetic Health Informatics", "Annals of Simulated Quality",
                 "International Review of Fictitious Medicine"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/prereg_rqaf.yaml")
    a = ap.parse_args()
    cfg = yaml.safe_load(open(a.config))
    rng = random.Random(cfg["injection"]["seed"])
    os.makedirs("data/rqaf/source", exist_ok=True)

    # measure database
    db = []
    for mid, name, unit in MEASURES:
        for period in PERIODS:
            den = rng.randint(180, 1400)
            num = rng.randint(0, int(den * 0.25))
            exc = rng.randint(0, int(den * 0.08))
            db.append({
                "measure_id": mid, "name": name, "unit": unit, "period": period,
                "numerator": num, "denominator": den, "exclusions": exc,
                "rate": round(num / max(den - exc, 1) * (1000 if "1,000" in unit else 100), 2),
                "event_dates": sorted(f"{period[:4]}-{rng.randint(1,12):02d}-{rng.randint(1,28):02d}"
                                      for _ in range(min(num, 5))),
            })
    json.dump(db, open("data/rqaf/source/measure_db.json", "w"), indent=1)

    # reference database: 60 fake + real standards
    refs = list(REAL_REFS)
    for i in range(60):
        refs.append({
            "ref_id": f"F{i+1}", "is_real": False,
            "citation": (f"{rng.choice(FAKE_AUTHORS)} et al., \"{rng.choice(FAKE_TOPICS).capitalize()}: "
                         f"a multicenter study,\" {rng.choice(FAKE_JOURNALS)}, vol. {rng.randint(3,40)}, "
                         f"pp. {rng.randint(1,400)}-{rng.randint(401,900)}, {rng.randint(2018,2025)}, "
                         f"doi: 10.9999/synth.{rng.randint(100000,999999)}."),
            "topic": rng.choice(FAKE_TOPICS)})
    json.dump(refs, open("data/rqaf/source/reference_db.json", "w"), indent=1)
    print(f"wrote {len(db)} measure-period records and {len(refs)} references.")


if __name__ == "__main__":
    main()
