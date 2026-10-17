# Roadmap — October 2026 to January 2027

The daily automation ships one real, tested item per weekday. Weekends are
rest days. `BACKLOG.md` is the executable version of this roadmap; each item
carries its own acceptance criterion, demo command and target files.

## Month 1 — expose what already exists

Six capabilities are implemented but invisible to users. Exposing them is the
highest-value work for a reviewer: new commands that work, not internal
refactors.

- `--version`.
- BCa bootstrap as `--bootstrap N`, in the text and JSON reports.
- Residual diagnostics and outlier flags in the report.
- Batch pooling as `--pool-batches`, with its report section.
- The ASCII confidence band as `--plot`, plus band points in JSON.
- A separate `--release-limit`.
- Multiple specification limits in one run.
- Forced kinetic model, extrapolation warning, positive-trend warning.
- Parameter validation, stable error codes, delimiter sniffing.
- API documentation and a showcase section in the README.

## Month 2 — ICH logic and data handling

- ICH Q1E decision summary.
- ICH Q1A(R2) significant-change logic.
- Storage-zone presets (I–IVb).
- Extrapolation factor from study duration.
- Minimum-data checks and intermediate conditions.
- Pooling decision reporting.
- Arrhenius rate confidence intervals and zero-order kinetics.
- Accelerated batch identity and a shelf-life matrix across temperatures.
- Overall batch shelf life, storage zone in the report, per-batch statistics.
- AIC/BIC model comparison, configurable confidence level, weighted regression.
- Lack-of-fit test, units, comma decimal separators.

## Month 3 — audit, reporting, packaging, performance

- Audit metadata (version, timestamp, input hash, CLI parameters).
- JSON schema version.
- Markdown and CSV exports, HTML provenance, Arrhenius table.
- Provenance and diagnostics in every output format.
- Bootstrap, pooling and outlier sections in every format.
- `py.typed`, CHANGELOG, CONTRIBUTING, CODE_OF_CONDUCT, CITATION.cff.
- README install matrix, CLI reference, more examples, limitations.
- Fit cache, streaming I/O, actionable error messages, batch labels.
- A quarterly showcase section in the README.

## Guardrails

- One item per weekday; weekends off.
- No commit unless the change is real, scoped to at most 3 files, carries a
  test when production code changes, and the full suite is green.
- An item that fails three attempts is moved to `BACKLOG.blocked.md`, not
  silently checked off.
- Visible CLI changes come before internal refactors.
