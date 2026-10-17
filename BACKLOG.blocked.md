# Blocked items

Moved here after three failed attempts. Fix the item (or split it) and move it
back to BACKLOG.md to retry.
- `cli-version` Add `--version` to the CLI. Acceptance: the command prints the package version and exits 0; a subprocess test checks it. Demo: `python main.py --version`. Files: main.py, tests/test_cli.py
  blocked: 3 attempts failed (2026-10-17)
- `q1e-bootstrap-cli` Expose the existing BCa bootstrap as `--bootstrap N`. Acceptance: `--bootstrap 200` adds a bootstrap lower bound to the report and a test asserts it is finite. Demo: `python main.py q1e --input examples/stability_data.csv --limit 90 --bootstrap 200`. Files: main.py, tests/test_cli.py
  blocked: 3 attempts failed (2026-10-17)
- `q1e-bootstrap-report` Add a bootstrap section to the text and JSON reports. Acceptance: both formats include the bootstrap bound when requested; a test checks both. Demo: `python main.py q1e --input examples/stability_data.csv --limit 90 --bootstrap 200 --json`. Files: stability_shelf_life/report.py, tests/test_report.py
  blocked: 3 attempts failed (2026-10-17)
