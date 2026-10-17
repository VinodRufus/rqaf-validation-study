# Deviations log

Any change made after the prereg tag (prereg-rqaf-v1) or the gold tag (gold-rqaf-v1) is
recorded here with date, reason, and impact, and is reported in the paper. An empty log after
the run is the goal.

## 2026-09-27 Repository-wide study rename (non-substantive)
Letter slugs replaced by descriptive slugs before any model runs:
A->rqaf, B->peds_abstraction, delay->surgical_delay, dosing->peds_dosing,
rag->ehr_rag, phi->phi_leakage, ctx->long_context. Prompt files, config
filenames, data folders and internal paths renamed to match; flagship
record-id prefix changed from B- to REC- and the corpus regenerated from
the same seed (content identical, ids renamed). No design value in any
prereg config changed. Tags prereg-B-v1 and prereg-A-v1 were re-issued as
prereg-peds_abstraction-v1 and prereg-rqaf-v1 on the rename commit.
Zero API runs and zero gold review existed at the time of the rename.

## 2026-09-29 Operational note: audit exemption for the RQAF injected corpus
At the peds_abstraction results freeze, src/common/audit.py run over the whole repository
flagged 40 MRN-like hits in data/rqaf/injected and data/rqaf/gold. All are the RQAF study's
deliberately injected synthetic identifier string (privacy_leak error class,
src/rqaf/inject_errors.py: "Patient record MRN 84921736 was representative of the excluded
cases."), which that study's detectors are required to find; the number is fictitious and
identical in every injected record. The RQAF data, run, and result paths are added to the
identifier-pattern exemption that already covered the PHI-leakage study. The employer and
vendor blocklist remains enforced on every path. No data, run log, or result was changed.

## 2026-10-17 RQAF run logs committed to version control (no result change)
The RQAF run logs under runs/rqaf were present locally at the results freeze (results-rqaf-v1,
2026-09-27) and were the inputs to results/rqaf, but runs/ is git-ignored and they had not been
force-added. They are committed now, unchanged, so that the archival release promised in the
paper can include them. No prompt, configuration, output, or result was altered.

## 2026-10-17 Public release cut from the working repository (no content or result change)
This repository is a filtered mirror of the authors' working repository containing only the
RQAF study paths (`src/common`, `src/rqaf`, `data/rqaf`, `runs/rqaf`, `results/rqaf`, its
configuration, prompts, tools and tests). Commit dates and messages are preserved; author
metadata uses the GitHub no-reply address; the employer/vendor blocklist in `src/common/audit.py`
is published as SHA-256 digests; one test fixture string was replaced by a synthetic term.
The commit id printed in
`results/rqaf/REPORT.md` refers to the working repository at the results tag.

Scope note on the run logs: the paper states that raw model outputs are retained under version
control. The generated reports (`data/rqaf/reports/`) are retained verbatim; the evaluation
script recorded, per report and system, the parsed error types, disposition, risk score, latency
and parse outcome, but not the raw text of each claim-judge response or a per-call model-version
string. No number in the paper depends on those raw texts; all reported statistics regenerate
from the committed logs.
