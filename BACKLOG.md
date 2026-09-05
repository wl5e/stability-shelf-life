# Backlog

The daily automation (`scripts/daily.py`) consumes this list top-to-bottom:
it takes the first undone item that has an implemented `handler:` and ships it
only if the full test suite stays green. Items without a handler are planned
next steps — each needs a handler (or the future LLM provider) before it runs.

Keep entries concrete: what changes, and why it matters for GMP/ICH work.

## Ready (implemented handlers)

- [x] `reject_nonfinite_inputs` Reject NaN/Inf in CSV loaders so bad data cannot corrupt a fit. | handler: reject_nonfinite_inputs
- [ ] `cli_end_to_end_test` Add the first end-to-end tests covering the CLI (q1e + arrhenius). | handler: cli_end_to_end_test
- [ ] `readme_worked_example` Add a worked example with real numbers to the README. | handler: readme_worked_example

## Planned (need a handler)

- [ ] `bootstrap_confidence` Bootstrap BCa lower bound for the shelf life as a robustness check against the analytic bound. | handler:
- [ ] `pooled_batches` Pool batches that share a common slope (ICH Q1E batch pooling) with an ANCOVA test. | handler:
- [ ] `arrhenius_extrapolation_guard` Warn when the storage temperature falls outside the measured range. | handler:
- [ ] `json_report_file` Add `--out FILE` to persist the JSON report (GMP audit-trail artifact). | handler:
- [ ] `csv_encoding_bom` Accept UTF-8 with BOM in CSV inputs. | handler:
- [ ] `slope_difference_test` Report a statistical test for slope differences between batches. | handler:
- [ ] `outlier_diagnostic` Flag high-leverage / studentized-residual outliers in the fit. | handler:
- [ ] `html_report` Emit a standalone HTML report of the stability analysis. | handler:
- [ ] `pyproject_packaging` Add `pyproject.toml` so the package is pip-installable. | handler:
- [ ] `ci_matrix` Expand CI across Python 3.10–3.13. | handler:
