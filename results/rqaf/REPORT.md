# Study Report: A Robust Quality Assurance Framework for Validating Generative AI Outputs in Healthcare Quality Reporting

Generated 2026-09-27 20:53 from commit `0879fa1`.
Tags: gold-rqaf-v1
prereg-peds_abstraction-v1
prereg-rqaf-v1
results-rqaf-v1

## Pre-registered design
```yaml
# Pre-registered design, Paper: RQAF Validation Study
# Model lineup pinned 2026-09-25 from live API listings, same session as prereg-peds_abstraction-v1.
# RULE: verify both models ping OK, then git tag prereg-rqaf-v1. No changes after the tag.
# Deviations are logged in DEVIATIONS.md and reported in the paper.
study: rqaf_validation_v1
reports:
  n: 120
  types: [measure_summary, adverse_event_summary, compliance_narrative]
source: synthetic_measure_db_v1
references: synthetic_reference_db_v1   # 60 fake-but-well-formed + 40 real NIST/WHO
generation_model: "openai:gpt-5.5-2026-04-23"   # report writer; dated snapshot; server-reported version recorded per call
judge_model: "anthropic:claude-sonnet-5"        # claim judge; DIFFERENT family than generator, on purpose
injection:
  types: [hallucinated_claim, contradicted_claim, omitted_required_fact,
          invalid_citation, unsupported_citation, privacy_leak, prompt_injection_artifact]
  rate_per_report: {min: 0, max: 4}     # includes clean controls
  seed: 20260923
validators: [facts, evidence, completeness, citations, privacy, security]
risk_engine:
  weights: equal
  thresholds: {low: 40, moderate: 70}
  vetoes: on
baselines: [llm_self_check, single_pass_factuality_judge]
metrics: [detection_precision, detection_recall, detection_f1,
          disposition_accuracy, roc_auc_RS, calibration, latency_ms]
stats: {paired_bootstrap_resamples: 10000, pairwise_test: mcnemar, multiple_comparison: holm}
```

## Run inventory
- Total recorded calls: 360; with error or parse failure: 10
- Models and pinned versions:
  - none recorded

## Results
### auc_ci.csv
| auc | auc_lo | auc_hi | n | n_critical |
| --- | --- | --- | --- | --- |
| 0.893 | 0.821 | 0.955 | 120 | 62 |

### dispo_tests.csv
| system | accuracy | acc_lo | acc_hi | mcnemar_b | mcnemar_c | p_raw | p_holm |
| --- | --- | --- | --- | --- | --- | --- | --- |
| rqaf | 0.650 | 0.567 | 0.733 |  |  |  |  |
| llm_self_check | 0.558 | 0.467 | 0.642 | 21.000 | 10.000 | 0.071 | 0.142 |
| single_pass_judge | 0.558 | 0.475 | 0.650 | 27.000 | 16.000 | 0.126 | 0.142 |

### llm_self_check_detection.csv
| error_type | tp | fp | fn | precision | recall | f1 |
| --- | --- | --- | --- | --- | --- | --- |
| hallucinated_claim | 43 | 34 | 0 | 0.558 | 1.000 | 0.717 |
| contradicted_claim | 10 | 5 | 1 | 0.667 | 0.909 | 0.769 |
| omitted_required_fact | 7 | 58 | 4 | 0.108 | 0.636 | 0.184 |
| invalid_citation | 15 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| unsupported_citation | 27 | 0 | 12 | 1.000 | 0.692 | 0.818 |
| privacy_leak | 37 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| prompt_injection_artifact | 26 | 0 | 0 | 1.000 | 1.000 | 1.000 |

### llm_self_check_dispo.csv
| gold | approve | reject | review |
| --- | --- | --- | --- |
| approve | 9.000 | 21.000 | 3.000 |
| reject | 0.000 | 57.000 | 0.000 |
| review | 0.000 | 29.000 | 1.000 |
| accuracy | 0.558 |  |  |
| review_load | 0.033 |  |  |
| clean_over_flag_rate | 0.727 |  |  |

### rqaf_detection.csv
| error_type | tp | fp | fn | precision | recall | f1 |
| --- | --- | --- | --- | --- | --- | --- |
| hallucinated_claim | 31 | 31 | 12 | 0.500 | 0.721 | 0.590 |
| contradicted_claim | 9 | 40 | 2 | 0.184 | 0.818 | 0.300 |
| omitted_required_fact | 10 | 86 | 1 | 0.104 | 0.909 | 0.187 |
| invalid_citation | 15 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| unsupported_citation | 24 | 3 | 15 | 0.889 | 0.615 | 0.727 |
| privacy_leak | 37 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| prompt_injection_artifact | 26 | 0 | 0 | 1.000 | 1.000 | 1.000 |

### rqaf_dispo.csv
| gold | approve | reject | review |
| --- | --- | --- | --- |
| approve | 1.000 | 10.000 | 22.000 |
| reject | 0.000 | 56.000 | 1.000 |
| review | 2.000 | 7.000 | 21.000 |
| accuracy | 0.650 |  |  |
| review_load | 0.367 |  |  |
| clean_over_flag_rate | 0.970 |  |  |

### rqaf_roc.csv (first 40 of 120 rows)
| report | RS | has_critical |
| --- | --- | --- |
| A-020 | 16.670 | False |
| A-098 | 16.670 | False |
| A-077 | 20.830 | False |
| A-061 | 16.670 | False |
| A-036 | 16.670 | False |
| A-108 | 69.440 | True |
| A-094 | 18.750 | False |
| A-082 | 68.750 | True |
| A-041 | 18.750 | False |
| A-104 | 68.750 | True |
| A-016 | 67.740 | True |
| A-057 | 55.420 | True |
| A-112 | 18.750 | False |
| A-056 | 70.140 | True |
| A-113 | 70.830 | True |
| A-001 | 16.670 | False |
| A-017 | 68.750 | True |
| A-040 | 77.080 | True |
| A-105 | 70.830 | True |
| A-083 | 68.750 | True |
| A-095 | 27.080 | False |
| A-109 | 16.670 | False |
| A-037 | 25.000 | False |
| A-060 | 16.670 | False |
| A-099 | 27.080 | False |
| A-076 | 68.750 | True |
| A-021 | 68.750 | True |
| A-092 | 27.080 | False |
| A-084 | 16.670 | False |
| A-047 | 72.670 | True |
| A-102 | 68.750 | True |
| A-010 | 65.510 | True |
| A-006 | 69.790 | True |
| A-051 | 10.620 | False |
| A-114 | 7.200 | False |
| A-026 | 12.340 | True |
| A-071 | 16.670 | False |
| A-088 | 69.440 | True |
| A-067 | 27.080 | False |
| A-030 | 15.710 | True |

### single_pass_judge_detection.csv
| error_type | tp | fp | fn | precision | recall | f1 |
| --- | --- | --- | --- | --- | --- | --- |
| hallucinated_claim | 38 | 30 | 5 | 0.559 | 0.884 | 0.685 |
| contradicted_claim | 9 | 2 | 2 | 0.818 | 0.818 | 0.818 |
| omitted_required_fact | 6 | 44 | 5 | 0.120 | 0.545 | 0.197 |
| invalid_citation | 13 | 6 | 2 | 0.684 | 0.867 | 0.765 |
| unsupported_citation | 29 | 20 | 10 | 0.592 | 0.744 | 0.659 |
| privacy_leak | 33 | 0 | 4 | 1.000 | 0.892 | 0.943 |
| prompt_injection_artifact | 25 | 0 | 1 | 1.000 | 0.962 | 0.980 |

### single_pass_judge_dispo.csv
| gold | approve | reject | review |
| --- | --- | --- | --- |
| approve | 13.000 | 16.000 | 4.000 |
| reject | 0.000 | 51.000 | 6.000 |
| review | 0.000 | 27.000 | 3.000 |
| accuracy | 0.558 |  |  |
| review_load | 0.108 |  |  |
| clean_over_flag_rate | 0.606 |  |  |

### tableVI_detection_ci.csv
| system | error_type | tp | fp | fn | precision | precision_lo | precision_hi | recall | recall_lo | recall_hi | f1 | f1_lo | f1_hi |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| rqaf | hallucinated_claim | 31 | 31 | 12 | 0.500 | 0.373 | 0.623 | 0.721 | 0.578 | 0.848 | 0.590 | 0.468 | 0.695 |
| rqaf | contradicted_claim | 9 | 40 | 2 | 0.184 | 0.082 | 0.300 | 0.818 | 0.556 | 1.000 | 0.300 | 0.145 | 0.448 |
| rqaf | omitted_required_fact | 10 | 86 | 1 | 0.104 | 0.045 | 0.170 | 0.909 | 0.700 | 1.000 | 0.187 | 0.085 | 0.288 |
| rqaf | invalid_citation | 15 | 0 | 0 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| rqaf | unsupported_citation | 24 | 3 | 15 | 0.889 | 0.759 | 1.000 | 0.615 | 0.459 | 0.767 | 0.727 | 0.590 | 0.838 |
| rqaf | privacy_leak | 37 | 0 | 0 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| rqaf | prompt_injection_artifact | 26 | 0 | 0 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| llm_self_check | hallucinated_claim | 43 | 34 | 0 | 0.558 | 0.447 | 0.667 | 1.000 | 1.000 | 1.000 | 0.717 | 0.618 | 0.800 |
| llm_self_check | contradicted_claim | 10 | 5 | 1 | 0.667 | 0.400 | 0.909 | 0.909 | 0.700 | 1.000 | 0.769 | 0.538 | 0.929 |
| llm_self_check | omitted_required_fact | 7 | 58 | 4 | 0.108 | 0.034 | 0.190 | 0.636 | 0.333 | 0.917 | 0.184 | 0.062 | 0.304 |
| llm_self_check | invalid_citation | 15 | 0 | 0 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| llm_self_check | unsupported_citation | 27 | 0 | 12 | 1.000 | 1.000 | 1.000 | 0.692 | 0.543 | 0.833 | 0.818 | 0.704 | 0.909 |
| llm_self_check | privacy_leak | 37 | 0 | 0 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| llm_self_check | prompt_injection_artifact | 26 | 0 | 0 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| single_pass_judge | hallucinated_claim | 38 | 30 | 5 | 0.559 | 0.440 | 0.676 | 0.884 | 0.778 | 0.974 | 0.685 | 0.579 | 0.778 |
| single_pass_judge | contradicted_claim | 9 | 2 | 2 | 0.818 | 0.556 | 1.000 | 0.818 | 0.556 | 1.000 | 0.818 | 0.600 | 0.966 |
| single_pass_judge | omitted_required_fact | 6 | 44 | 5 | 0.120 | 0.038 | 0.216 | 0.545 | 0.222 | 0.857 | 0.197 | 0.067 | 0.328 |
| single_pass_judge | invalid_citation | 13 | 6 | 2 | 0.684 | 0.462 | 0.889 | 0.867 | 0.667 | 1.000 | 0.765 | 0.571 | 0.903 |
| single_pass_judge | unsupported_citation | 29 | 20 | 10 | 0.592 | 0.451 | 0.729 | 0.744 | 0.600 | 0.875 | 0.659 | 0.531 | 0.765 |
| single_pass_judge | privacy_leak | 33 | 0 | 4 | 1.000 | 1.000 | 1.000 | 0.892 | 0.778 | 0.976 | 0.943 | 0.875 | 0.988 |
| single_pass_judge | prompt_injection_artifact | 25 | 0 | 1 | 1.000 | 1.000 | 1.000 | 0.962 | 0.870 | 1.000 | 0.980 | 0.930 | 1.000 |

## Figures
![fig_roc.png](results/rqaf/figures/fig_roc.png)

## Integrity statement
All data are synthetic and generated by the scripts in this repository. No real patient data, employer data, or institutional materials were used. The identifier and blocklist audit passed at report generation time. Any deviation from the pre-registered design is recorded in DEVIATIONS.md.
