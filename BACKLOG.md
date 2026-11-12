# Backlog

The daily automation (`scripts/daily.py`) consumes this list top-to-bottom on
weekdays. Each item carries its own definition of done:

- `Acceptance:` — the testable criterion the change must satisfy;
- `Demo:` — the command a reviewer can run to see the result;
- `Files:` — the files the change is expected to touch (at most 3).

`scripts/backlog.py --check` validates the format. An item that fails three
attempts is moved to `BACKLOG.blocked.md`; it is never silently checked off.

The order is deliberate: expose what already exists first, then add ICH logic,
then audit/reporting/packaging. Visible CLI changes come before internal
refactors.

## Month 1 — expose the six capabilities that are already coded

- [x] `cli-version` Add `--version` to the CLI. Acceptance: the command prints the package version and exits 0; a subprocess test checks it. Demo: `python main.py --version`. Files: main.py, tests/test_cli.py | handler:
- [x] `q1e-bootstrap-cli` Expose the existing BCa bootstrap as `--bootstrap N`. Acceptance: `--bootstrap 200` adds a bootstrap lower bound to the report and a test asserts it is finite. Demo: `python main.py q1e --input examples/stability_data.csv --limit 90 --bootstrap 200`. Files: main.py, tests/test_cli.py | handler:
- [x] `q1e-bootstrap-report` Add a bootstrap section to the text and JSON reports. Acceptance: both formats include the bootstrap bound when requested; a test checks both. Demo: `python main.py q1e --input examples/stability_data.csv --limit 90 --bootstrap 200 --json`. Files: stability_shelf_life/report.py, tests/test_report.py | handler:
- [x] `q1e-pooling-report` Add a pooling section to the report. Acceptance: the report explains the pooling decision and the pooled shelf life; tested. Demo: `python main.py q1e --input examples/stability_data.csv --limit 90 --pool-batches --json`. Files: stability_shelf_life/report.py, tests/test_report.py | handler:
- [x] `q1e-confidence-band-json` Add band points to the JSON report. Acceptance: the JSON includes time/potency band points when plotting is requested; tested. Demo: `python main.py q1e --input examples/stability_data.csv --limit 90 --plot --json`. Files: stability_shelf_life/report.py, stability_shelf_life/ascii_plot.py, tests/test_report.py | handler:
- [x] `q1e-release-limit-cli` Add a separate `--release-limit` option. Acceptance: the release limit and the shelf-life limit are reported independently; tested. Demo: `python main.py q1e --input examples/stability_data.csv --limit 90 --release-limit 95`. Files: main.py, tests/test_cli.py | handler:
- [x] `q1e-release-limit-report` Report the release limit alongside the shelf life. Acceptance: the JSON and text outputs name both limits; tested. Demo: `python main.py q1e --input examples/stability_data.csv --limit 90 --release-limit 95 --json`. Files: stability_shelf_life/report.py, tests/test_report.py | handler:
- [x] `q1e-multi-limit` Evaluate several specification limits in one run. Acceptance: repeated `--limit` values produce one result per limit; tested. Demo: `python main.py q1e --input examples/stability_data.csv --limit 90 --limit 95`. Files: main.py, tests/test_cli.py | handler:
- [x] `q1e-positive-trend-warning` Warn when the fitted slope is positive. Acceptance: a rising synthetic series is flagged before clamping; tested. Demo: `python main.py q1e --input examples/stability_data.csv --limit 90`. Files: stability_shelf_life/model.py, tests/test_model.py | handler:
- [x] `csv-delimiter-sniffing` Accept semicolon- and tab-delimited CSVs. Acceptance: both delimiters load correctly and are tested. Demo: `python main.py q1e --input examples/stability_data_semicolon.csv --limit 90`. Files: stability_shelf_life/io.py, tests/test_io.py | handler:
- [x] `readme-api-docs` Document the public API and its dataclasses. Acceptance: README has an API section covering every public function; checked by a test or a grep. Demo: `grep -q "## API" README.md`. Files: README.md | handler:
- [x] `readme-showcase` Add a "What shipped this quarter" section with the new commands. Acceptance: the section lists at least 10 commands and is checked by a test. Demo: `grep -q "What shipped this quarter" README.md`. Files: README.md, tests/test_readme.py | handler:

## Month 2 — ICH logic, validation, data handling

- [x] `extrapolation-factor` Compute the Q1E extrapolation factor from study duration. Acceptance: the factor follows the guideline table and is tested at boundary durations. Demo: `python main.py q1e --input examples/stability_data.csv --limit 90 --json`. Files: stability_shelf_life/model.py, tests/test_model.py | handler:
- [x] `minimum-data-check` Enforce the minimum timepoints and batches. Acceptance: too-short studies raise a clear error and valid ones pass; tested. Demo: `python main.py q1e --input examples/stability_data.csv --limit 90`. Files: stability_shelf_life/io.py, tests/test_io.py | handler:
- [x] `batch-pooling-decision` Report the pooled-vs-individual decision. Acceptance: the report explains why batches were pooled or not; tested. Demo: `python main.py q1e --input examples/stability_data.csv --limit 90 --pool-batches --json`. Files: stability_shelf_life/pooling.py, tests/test_pooling.py | handler:
- [x] `accelerated-batch-identity` Accept an optional batch_id in accelerated data. Acceptance: the column is optional and grouped results are tested. Demo: `python main.py arrhenius --input examples/accelerated_data.csv --storage-temp 25 --json`. Files: stability_shelf_life/io.py, tests/test_io.py | handler:
- [x] `accelerated-shelf-life-matrix` Output a shelf-life matrix across temperatures. Acceptance: the matrix covers the requested temperatures and is tested. Demo: `python main.py arrhenius --input examples/accelerated_data.csv --temperatures 5,25,30 --json`. Files: main.py, stability_shelf_life/report.py, tests/test_report.py | handler:
- [ ] `q1e-lack-of-fit` Add a lack-of-fit test for the kinetic model. Acceptance: a curved synthetic series is flagged and a linear one is not; tested. Demo: `python main.py q1e --input examples/stability_data.csv --limit 90 --diagnostics`. Files: stability_shelf_life/model.py, tests/test_model.py | handler:
- [ ] `q1e-units` Carry units through input and output. Acceptance: the report names months/%/temperature units and is tested. Demo: `python main.py q1e --input examples/stability_data.csv --limit 90 --json`. Files: stability_shelf_life/io.py, stability_shelf_life/report.py, tests/test_io.py | handler:
- [ ] `q1e-locale-decimals` Accept comma decimal separators. Acceptance: a comma-decimal CSV loads correctly and is tested. Demo: `python main.py q1e --input examples/stability_data_comma.csv --limit 90`. Files: stability_shelf_life/io.py, tests/test_io.py | handler:

## Month 3 — audit, reporting, packaging, performance

- [ ] `audit-metadata` Add audit metadata to every JSON report. Acceptance: version, timestamp, input hash and CLI parameters are present; tested. Demo: `python main.py q1e --input examples/stability_data.csv --limit 90 --json`. Files: stability_shelf_life/report.py, tests/test_report.py | handler:
- [ ] `json-schema-version` Add a schema version to JSON output. Acceptance: the field is present and stable across runs; tested. Demo: `python main.py q1e --input examples/stability_data.csv --limit 90 --json`. Files: stability_shelf_life/report.py, tests/test_report.py | handler:
- [ ] `markdown-export` Add `--format markdown`. Acceptance: the report renders a valid Markdown table and is tested. Demo: `python main.py q1e --input examples/stability_data.csv --limit 90 --format markdown`. Files: stability_shelf_life/report.py, tests/test_report.py | handler:
- [ ] `csv-export` Add `--format csv`. Acceptance: the report emits one row per batch with the expected columns; tested. Demo: `python main.py q1e --input examples/stability_data.csv --limit 90 --format csv`. Files: stability_shelf_life/report.py, tests/test_report.py | handler:
- [ ] `html-provenance` Add provenance to the HTML report. Acceptance: the HTML names the tool version, input and parameters; tested. Demo: `python main.py q1e --input examples/stability_data.csv --limit 90 --format html`. Files: stability_shelf_life/report.py, tests/test_report.py | handler:
- [ ] `arrhenius-table` Add an Arrhenius summary table. Acceptance: the table lists temperature, rate and predicted shelf life; tested. Demo: `python main.py arrhenius --input examples/accelerated_data.csv --storage-temp 25 --format markdown`. Files: stability_shelf_life/report.py, tests/test_report.py | handler:
- [ ] `q1e-table-provenance` Add provenance to the Q1A/Q1E summary table. Acceptance: the table names the source file and parameters; tested. Demo: `python main.py q1e --input examples/stability_data.csv --limit 90 --format markdown`. Files: stability_shelf_life/report.py, tests/test_report.py | handler:
- [ ] `report-diagnostics` Include residual diagnostics in every output format. Acceptance: text, JSON and Markdown carry the diagnostics; tested. Demo: `python main.py q1e --input examples/stability_data.csv --limit 90 --diagnostics --json`. Files: stability_shelf_life/report.py, tests/test_report.py | handler:
- [ ] `report-outliers` Include outlier flags in every output format. Acceptance: flagged points appear in text, JSON and Markdown; tested. Demo: `python main.py q1e --input examples/stability_data.csv --limit 90 --diagnostics --json`. Files: stability_shelf_life/report.py, tests/test_report.py | handler:
- [ ] `report-pooling` Include the pooling section in every output format. Acceptance: the pooled decision appears in text, JSON and Markdown; tested. Demo: `python main.py q1e --input examples/stability_data.csv --limit 90 --pool-batches --json`. Files: stability_shelf_life/report.py, tests/test_report.py | handler:
- [ ] `report-bootstrap` Include the bootstrap section in every output format. Acceptance: the bound appears in text, JSON and Markdown; tested. Demo: `python main.py q1e --input examples/stability_data.csv --limit 90 --bootstrap 200 --json`. Files: stability_shelf_life/report.py, tests/test_report.py | handler:
- [ ] `py-typed` Add the `py.typed` marker. Acceptance: the package ships `py.typed` and the packaging test checks it. Demo: `python -c "import stability_shelf_life, pathlib; print(pathlib.Path(stability_shelf_life.__file__).with_name('py.typed').exists())"`. Files: pyproject.toml, stability_shelf_life/py.typed | handler:
- [ ] `changelog` Add a CHANGELOG covering releases and backlog items. Acceptance: the file follows Keep a Changelog and lists the current version; checked by a test. Demo: `grep -q "## \[2.0.0\]" CHANGELOG.md`. Files: CHANGELOG.md | handler:
- [ ] `contributing` Add a CONTRIBUTING guide. Acceptance: the guide covers setup, tests and backlog item format; checked by a test. Demo: `test -f CONTRIBUTING.md`. Files: CONTRIBUTING.md | handler:
- [ ] `code-of-conduct` Add a CODE_OF_CONDUCT. Acceptance: the file exists and names the reporting contact; checked by a test. Demo: `test -f CODE_OF_CONDUCT.md`. Files: CODE_OF_CONDUCT.md | handler:
- [ ] `citation-cff` Add citation metadata. Acceptance: CITATION.cff validates and names the author and version; checked by a test. Demo: `python -c "import yaml; print(yaml.safe_load(open('CITATION.cff'))['title'])"`. Files: CITATION.cff | handler:
- [ ] `readme-install-matrix` Document the supported Python versions and install options. Acceptance: the README lists 3.9–3.13 and pip/PyPI installs; checked by a grep test. Demo: `grep -q "Python 3.9" README.md`. Files: README.md | handler:
- [ ] `readme-cli-reference` Add a complete CLI reference. Acceptance: every flag of both subcommands is documented; checked by a test. Demo: `grep -q "q1e --input" README.md`. Files: README.md | handler:
- [ ] `readme-examples` Add more end-to-end examples. Acceptance: at least three commands with real output are documented; checked by a test. Demo: `grep -c "^python main.py" README.md`. Files: README.md | handler:
- [ ] `performance-fit-cache` Cache repeated fits within a run. Acceptance: a repeated fit returns the cached result and the test asserts it. Demo: `python main.py q1e --input examples/stability_data.csv --limit 90 --limit 95`. Files: stability_shelf_life/model.py, tests/test_model.py | handler:
- [ ] `io-streaming` Stream large CSV inputs instead of loading them twice. Acceptance: a large file is read once and the result is unchanged; tested. Demo: `python main.py q1e --input examples/stability_data.csv --limit 90`. Files: stability_shelf_life/io.py, tests/test_io.py | handler:
- [ ] `error-messages` Make validation errors actionable. Acceptance: each error names the file, row, column and expected value; tested. Demo: `python main.py q1e --input examples/stability_data.csv --limit 150`. Files: stability_shelf_life/io.py, tests/test_io.py | handler:
- [ ] `q1e-batch-label` Add human-readable batch labels to output. Acceptance: labels appear in text and JSON and fall back to batch_id; tested. Demo: `python main.py q1e --input examples/stability_data.csv --limit 90 --json`. Files: stability_shelf_life/report.py, tests/test_report.py | handler:
- [ ] `readme-limitations` Document assumptions, limits and rounding rules. Acceptance: the README has a limitations section covering all public calculations; checked by a test. Demo: `grep -q "## Limitations" README.md`. Files: README.md | handler:
- [ ] `readme-showcase-q1` Refresh the showcase section with the quarter's new commands. Acceptance: the section lists the month 1–3 commands and is checked by a test. Demo: `grep -q "What shipped this quarter" README.md`. Files: README.md, tests/test_readme.py | handler:
