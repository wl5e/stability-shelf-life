# Blocked items

Moved here after three failed attempts. Fix the item (or split it) and move it
back to BACKLOG.md to retry.
- `q1e-residual-diagnostics` Wire the existing residual diagnostics into the Q1E report. Acceptance: the report exposes residual normality and runs-test results, covered by a test. Demo: `python main.py q1e --input examples/stability_data.csv --limit 90 --diagnostics`. Files: main.py, stability_shelf_life/report.py, tests/test_report.py
  blocked: 3 attempts failed (2026-10-20)
- `q1e-outlier-diagnostic` Flag outlier points in the Q1E fit. Acceptance: a synthetic outlier is flagged and the report lists it; a test covers the flag. Demo: `python main.py q1e --input examples/stability_data.csv --limit 90 --diagnostics`. Files: main.py, stability_shelf_life/model.py, tests/test_model.py
  blocked: 3 attempts failed (2026-10-20)
- `q1e-pooling-cli` Expose the existing batch pooling as `--pool-batches`. Acceptance: the flag returns a pooled estimate and per-batch results still print; a test covers both. Demo: `python main.py q1e --input examples/stability_data.csv --limit 90 --pool-batches`. Files: main.py, stability_shelf_life/pooling.py, tests/test_pooling.py
  blocked: 3 attempts failed (2026-10-20)
