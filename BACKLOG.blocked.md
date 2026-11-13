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
- `q1e-decision-tree` Add an ICH Q1E decision summary to the report. Acceptance: the report states the decision (accept/reject/extrapolate) with reasons; tested. Demo: `python main.py q1e --input examples/stability_data.csv --limit 90 --json`. Files: stability_shelf_life/report.py, tests/test_report.py
  blocked: 3 attempts failed (2026-11-03)
- `q1a-significant-change` Implement ICH Q1A(R2) significant-change logic. Acceptance: a significant change is detected from the slope comparison and reported; tested. Demo: `python main.py q1e --input examples/stability_data.csv --limit 90 --significant-change`. Files: stability_shelf_life/model.py, tests/test_model.py
  blocked: 3 attempts failed (2026-11-03)
- `storage-zone-presets` Add storage-zone presets (I–IVb). Acceptance: `--zone IVb` selects the correct long-term and accelerated conditions; tested. Demo: `python main.py q1e --input examples/stability_data.csv --zone IVb`. Files: main.py, tests/test_cli.py
  blocked: 3 attempts failed (2026-11-03)
- `intermediate-condition` Support an intermediate storage condition. Acceptance: the intermediate condition is parsed and reported; tested. Demo: `python main.py q1e --input examples/stability_data.csv --condition intermediate`. Files: stability_shelf_life/io.py, tests/test_io.py
  blocked: 3 attempts failed (2026-11-06)
- `arrhenius-rate-ci` Add confidence intervals to Arrhenius predictions. Acceptance: the rate CI is finite and narrower with more points; tested. Demo: `python main.py arrhenius --input examples/accelerated_data.csv --storage-temp 25 --json`. Files: stability_shelf_life/model.py, tests/test_model.py
  blocked: 3 attempts failed (2026-11-09)
- `arrhenius-zero-order` Support zero-order accelerated kinetics. Acceptance: the zero-order path matches a known rate and is tested. Demo: `python main.py arrhenius --input examples/accelerated_data.csv --storage-temp 25 --model zero`. Files: stability_shelf_life/model.py, tests/test_model.py
  blocked: 3 attempts failed (2026-11-09)
- `overall-batch-shelf-life` Report one regulatory shelf life across batches. Acceptance: the overall value is the minimum lower bound and is tested. Demo: `python main.py q1e --input examples/stability_data.csv --limit 90 --overall`. Files: stability_shelf_life/pooling.py, stability_shelf_life/report.py, tests/test_pooling.py
  blocked: 3 attempts failed (2026-11-11)
- `q1e-storage-zone-report` Include the storage zone and conditions in the report. Acceptance: the JSON names the zone and both conditions; tested. Demo: `python main.py q1e --input examples/stability_data.csv --zone II --json`. Files: stability_shelf_life/report.py, tests/test_report.py
  blocked: 3 attempts failed (2026-11-11)
- `q1e-data-summary` Add per-batch descriptive statistics before fitting. Acceptance: n, mean, SD, min and max are printed per batch; tested. Demo: `python main.py q1e --input examples/stability_data.csv --limit 90`. Files: stability_shelf_life/report.py, tests/test_report.py
  blocked: 3 attempts failed (2026-11-11)
- `q1e-model-comparison` Report AIC/BIC for zero- and first-order fits. Acceptance: both criteria are reported and the selected model is the lower AIC; tested. Demo: `python main.py q1e --input examples/stability_data.csv --limit 90 --json`. Files: stability_shelf_life/model.py, tests/test_model.py
  blocked: 3 attempts failed (2026-11-12)
- `q1e-ci-level` Make the confidence level configurable. Acceptance: `--confidence 0.90` changes the bound and is tested against 0.95. Demo: `python main.py q1e --input examples/stability_data.csv --limit 90 --confidence 0.90`. Files: stability_shelf_life/model.py, tests/test_model.py
  blocked: 3 attempts failed (2026-11-12)
- `q1e-weighted-regression` Add optional regression weights. Acceptance: weights change the fit as expected and are tested. Demo: `python main.py q1e --input examples/stability_data.csv --limit 90 --weights 1,2,1,1`. Files: stability_shelf_life/model.py, tests/test_model.py
  blocked: 3 attempts failed (2026-11-12)
- `q1e-lack-of-fit` Add a lack-of-fit test for the kinetic model. Acceptance: a curved synthetic series is flagged and a linear one is not; tested. Demo: `python main.py q1e --input examples/stability_data.csv --limit 90 --diagnostics`. Files: stability_shelf_life/model.py, tests/test_model.py
  blocked: 3 attempts failed (2026-11-13)
