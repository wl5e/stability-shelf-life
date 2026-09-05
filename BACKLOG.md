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
- [ ] `pooled_batches` Pool batches that share a common slope (ICH Q1E batch pooling) with an ANCOVA test. | handler:
- [ ] `arrhenius_extrapolation_guard` Warn when the storage temperature falls outside the measured range. | handler:
- [ ] `json_report_file` Add `--out FILE` to persist the JSON report (GMP audit-trail artifact). | handler:
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
