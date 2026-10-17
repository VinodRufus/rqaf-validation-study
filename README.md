# RQAF Validation Study

Code, synthetic data, run logs, and results for the paper

> **A Robust Quality Assurance Framework for Validating Generative AI Outputs in Healthcare Quality Reporting**
> Vinod Rufus Motani and Bharathi Sesha Sai Varanasi

Everything here is synthetic. No real patient data, protected health information, or
institutional material was used at any stage.

## Milestone tags

| Tag | Meaning |
|---|---|
| `prereg-rqaf-v1` | design frozen (`config/prereg_rqaf.yaml`, prompts, thresholds 40/70, model lineup, statistical plan) before the first model call |
| `gold-rqaf-v1` | synthetic measure database, 120 clean reports, injected corpus and injection log frozen (`data/rqaf/`) |
| `results-rqaf-v1` | pre-registered analysis complete (`results/rqaf/`) |

Every change after a tag is recorded in `DEVIATIONS.md`.

## Layout

- `config/prereg_rqaf.yaml` - pre-registration (corpus design, injection mix, thresholds, models, metrics, statistics)
- `prompts/` - the exact generation, claim-extraction and judge prompts
- `src/rqaf/` - `make_source.py` (synthetic measure and reference databases), `generate_reports.py`, `inject_errors.py` (seeded, logged injection), `validators.py` (deterministic validators, claim judge, risk engine and disposition), `baselines.py` (LLM self-check, single-pass judge), `evaluate.py`, `report.py` (tables and ROC figure)
- `src/common/` - provider adapters (`runner.py`), statistics (`stats.py`), identifier/institution audit (`audit.py`)
- `data/rqaf/` - `source/` (measure and reference databases), `reports/` (120 clean generated reports), `injected/` (the evaluated corpus), `gold/` (per-report injection log and gold disposition)
- `runs/rqaf/` - one JSON line per report per system (`rqaf`, `llm_self_check`, `single_pass_judge`; 3 x 120 = 360): detected error types, disposition, risk score (RQAF), latency, parse outcome
- `results/rqaf/` - every table and figure behind the paper, including `REPORT.md` generated at the results tag
- `tools/rqaf_stats.py`, `tools/rqaf_secondary_stats.py` - pre-registered and declared secondary statistics (offline)
- `tests/` - unit tests; `DEVIATIONS.md` - the post-tag change log

## Reproduce

```
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m pytest tests/ -q
python src/common/audit.py                 # identifier and institution audit: must print 0 finding(s)
python tools/rqaf_stats.py                 # bootstrap CIs, exact McNemar with Holm, AUC CI  -> results/rqaf/*.csv
python tools/rqaf_secondary_stats.py       # class-level metrics, exact binomial CIs, semantic-critical ROC
python src/rqaf/report.py                  # Table VI and the ROC figure
```

Every CSV result regenerates from the run logs. On Linux (including the GitHub Actions check) the
files are byte-identical. On macOS, `detection_exact_ci.csv` differs in the last floating-point
digit of some exact binomial bounds (largest difference 4.4e-16, i.e. identical to 15 significant
figures); every value quoted in the paper is unchanged. `figures/fig_roc.png` re-renders with the
same content; the PNG bytes differ across matplotlib versions. Re-running
`src/rqaf/evaluate.py --system ...` needs API keys in `.env` (see `.env.example`) and produces
new model outputs; the paper's numbers come from the logged runs in `runs/`.

## What the run logs do and do not contain

The logs hold the per-report outcome of each system (the parsed error types, the disposition,
the RQAF risk score, latency and whether the output parsed). The 120 generated reports in
`data/rqaf/reports/` are the raw generation-model outputs. The evaluation script did not write
the raw text of the individual claim-judge responses or a per-call server-reported model
version, so those cannot be inspected here; see `DEVIATIONS.md` (2026-10-17).

## Known discrepancy in the published figure

In the paper's Fig. 5 the threshold-40 marker is drawn at the nearest realized score cut
(false-positive rate 0.12). The policy threshold's actual operating point, computed from
`results/rqaf/rqaf_roc.csv`, is a true-positive rate of 0.839 at a false-positive rate of 0.000.
The AUC (0.893) is unaffected.

## Licences

Code: MIT (`LICENSE`). Data, run logs and results: CC BY 4.0 (`LICENSE-DATA`). Cite with `CITATION.cff`.
