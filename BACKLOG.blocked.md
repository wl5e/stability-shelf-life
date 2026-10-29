# Blocked items

Moved here after three failed attempts. Fix the item (or split it) and move it
back to BACKLOG.md to retry.
- `q1e-residual-diagnostics` Wire the existing residual diagnostics into the Q1E report. Acceptance: the report exposes residual normality and runs-test results, covered by a test. Demo: `python main.py q1e --input examples/stability_data.csv --limit 90 --diagnostics`. Files: main.py, stability_shelf_life/report.py, tests/test_report.py
  blocked: 3 attempts failed (2026-10-20)
- `q1e-outlier-diagnostic` Flag outlier points in the Q1E fit. Acceptance: a synthetic outlier is flagged and the report lists it; a test covers the flag. Demo: `python main.py q1e --input examples/stability_data.csv --limit 90 --diagnostics`. Files: main.py, stability_shelf_life/model.py, tests/test_model.py
  blocked: 3 attempts failed (2026-10-20)
- `q1e-pooling-cli` Expose the existing batch pooling as `--pool-batches`. Acceptance: the flag returns a pooled estimate and per-batch results still print; a test covers both. Demo: `python main.py q1e --input examples/stability_data.csv --limit 90 --pool-batches`. Files: main.py, stability_shelf_life/pooling.py, tests/test_pooling.py
  blocked: 3 attempts failed (2026-10-20)
- `q1e-confidence-band-cli` Expose the existing ASCII confidence band as `--plot`. Acceptance: the command renders the band for every batch and a test checks the output contains the limit line. Demo: `python main.py q1e --input examples/stability_data.csv --limit 90 --plot`. Files: main.py, stability_shelf_life/ascii_plot.py, tests/test_ascii_plot.py
  blocked: 3 attempts failed (2026-10-22)
- `q1e-forced-model` Add `--model {auto,zero,first}`. Acceptance: forcing a model changes the fit and is reported; a test covers auto and forced. Demo: `python main.py q1e --input examples/stability_data.csv --limit 90 --model first`. Files: main.py, tests/test_cli.py
  blocked: 3 attempts failed (2026-10-28)
- `q1e-extrapolation-warning` Warn when shelf life exceeds the study duration. Acceptance: a short study triggers the warning and a long one does not; tested. Demo: `python main.py q1e --input examples/stability_data.csv --limit 90`. Files: main.py, stability_shelf_life/report.py, tests/test_report.py
  blocked: 3 attempts failed (2026-10-28)
- `q1e-parameter-validation` Validate limits and potency ranges. Acceptance: out-of-range limits raise a clear StabilityError and are tested. Demo: `python main.py q1e --input examples/stability_data.csv --limit 150`. Files: stability_shelf_life/io.py, tests/test_io.py
  blocked: 3 attempts failed (2026-10-29)
- `q1e-error-codes` Add stable error codes to StabilityError. Acceptance: each validation error carries a code and a test asserts the code. Demo: `python main.py q1e --input examples/stability_data.csv --limit 150`. Files: stability_shelf_life/io.py, tests/test_io.py
  blocked: 3 attempts failed (2026-10-29)
