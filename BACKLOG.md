# Backlog

The daily automation (`scripts/daily.py`) consumes this list top-to-bottom:
it takes the first undone item that has an implemented `handler:` and ships it
only if the full test suite stays green. Items without a handler are
implemented by the DeepSeek provider (`scripts/llm.py`), gated by the same
test suite. Replenishment is handled by `scripts/replenish.py` (propose) and
`scripts/promote.py` (approve).

Keep entries concrete: what changes, and why it matters for GMP/ICH work.

## Ready (implemented handlers)

- [x] `reject_nonfinite_inputs` Reject NaN/Inf in CSV loaders so bad data cannot corrupt a fit. | handler: reject_nonfinite_inputs
- [x] `cli_end_to_end_test` Add the first end-to-end tests covering the CLI (q1e + arrhenius). | handler: cli_end_to_end_test
- [x] `readme_worked_example` Add a worked example with real numbers to the README. | handler: readme_worked_example

## Planned (need a handler)

- [x] `bootstrap_confidence` Bootstrap BCa lower bound for the shelf life as a robustness check against the analytic bound. | handler:
- [x] `pooled_batches` Pool batches that share a common slope (ICH Q1E batch pooling) with an ANCOVA test. | handler:
- [x] `arrhenius_extrapolation_guard` Warn when the storage temperature falls outside the measured range. | handler:
- [x] `json_report_file` Add `--out FILE` to persist the JSON report (GMP audit-trail artifact). | handler:
- [ ] `csv_encoding_bom` Accept UTF-8 with BOM in CSV inputs. | handler:
- [ ] `slope_difference_test` Report a statistical test for slope differences between batches. | handler:
- [ ] `outlier_diagnostic` Flag high-leverage / studentized-residual outliers in the fit. | handler:
- [ ] `html_report` Emit a standalone HTML report of the stability analysis. | handler:
- [ ] `pyproject_packaging` Add `pyproject.toml` so the package is pip-installable. | handler:
- [ ] `ci_matrix` Expand CI across Python 3.10–3.13. | handler:
- [ ] `two_sided_ci` Report the two-sided 95% CI for the degradation rate alongside the one-sided bound. | handler:
- [ ] `aic_model_selection` Replace the R² tie-break with AIC/BIC for zero- vs first-order selection. | handler:
- [ ] `residual_diagnostics` Add residual normality and runs tests to flag a poor kinetic fit. | handler:
- [ ] `data_summary_report` Print per-batch descriptive statistics (n, mean, sd, min, max) before fitting. | handler:
- [ ] `multi_limit_analysis` Evaluate shelf life at several specification limits (e.g. 90/95%) in one run. | handler:
- [ ] `release_limit` Compute and report the release limit separately from the shelf life. | handler:
- [ ] `ascii_confidence_band` Render the fitted line, its 95% confidence band and the limit as ASCII. | handler:
- [ ] `ich_q1a_table` Emit an ICH Q1A/Q1E-style summary table for regulatory reporting. | handler:
- [ ] `accelerated_shelf_life_matrix` Output a matrix of predicted shelf lives across storage temperatures. | handler:
- [ ] `validation_dataset` Add a zero-order-dominated example dataset to exercise both kinetic models. | handler:
- [ ] `error_codes` Give StabilityError a stable error code to aid GMP audit logging. | handler:
- [ ] `readme_api_docs` Document the public Python API (functions and dataclasses) in the README. | handler:

- [ ] `arrhenius_rate_confidence_interval` Add confidence intervals to Arrhenius predictions — The Arrhenius command currently reports only a point prediction for the storage temperature, so no uncertainty is available for risk assessment. A 95% interval for the extrapolated rate would give a conservative upper rate basis for shelf-life decisions under ICH Q1E. | handler:
- [ ] `overall_batch_shelf_life_summary` Summarize the recommended shelf life across batches — ICH Q1E ultimately assigns one regulatory shelf life; the CLI currently prints per-batch results only, requiring the user to manually identify the smallest lower bound and leaving no audit trace of that final decision. | handler:
- [ ] `zero_order_arrhenius_support` Support zero-order kinetics in the Arrhenius workflow — Accelerated data are hard-coded to first-order rates, but zero-order degradation is equally accepted by ICH Q1E. Without this option, zero-order products will get systematically biased Arrhenius predictions and invalid extrapolated shelf lives. | handler:
- [ ] `q1e_forced_model` Add a --model flag to force zero- or first-order in Q1E analysis — Regulatory stability protocols often prespecify the kinetic model; automatically picking the best R² fit can introduce post-hoc model selection, which is less defensible in GMP submissions and change control. | handler:
- [ ] `audit_metadata` Embed audit metadata in JSON reports — GMP archives need software version, run timestamp, input-file hash and CLI parameters next to results; the current JSON output has no context to trace the analysis back to the exact files and settings used. | handler:
- [ ] `q1e_extrapolation_warning` Warn when the Q1E shelf life exceeds the study time span — A shelf life projected beyond the longest measured time point is an extrapolation that ICH restricts; the report should flag when an estimated lower bound falls outside the covered stability data period. | handler:
- [ ] `csv_delimiter_sniffing` Detect CSV delimiter automatically — Real-world stability exports are often semicolon- or tab-separated, especially from European Excel locales; hard-coded comma parsing can silently merge or split fields and corrupt a GMP dataset before any statistics run. | handler:
- [ ] `accelerated_batch_identity` Accept optional batch_id in accelerated data and prevent silent pooling — The current accelerated loader pools all rows at a temperature as if from one batch; if a multi-batch accelerated study is loaded, batch-to-batch differences are hidden and the GMP analysis becomes invalid. | handler:
- [ ] `validate_analysis_parameters` Reject physically impossible limits and potencies — Options such as --limit or --initial-potency are currently accepted without range checks, allowing nonsensical inputs (e.g., limit above 100 or zero initial potency) to produce fitted shelf lives that should never enter a regulatory report. | handler:
- [ ] `positive_trend_warning` Warn when fitted model has a positive slope before truncating to zero rate — Current kinetic fitting clamps non-positive degradation rates to 0 and labels the batch stable, which can hide a rising potency trend that is physically implausible and should be investigated as assay or sample error. | handler:
