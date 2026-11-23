# Contributing to stability-shelf-life

Thanks for improving `stability-shelf-life`. This guide covers local setup,
how to run the tests, and the format for backlog items.

## Setup

Requires Python 3.9+. Install the package in editable mode with the test
extra:

```bash
git clone https://github.com/wl5e/stability-shelf-life.git
cd stability-shelf-life
python -m venv .venv
source .venv/bin/activate
pip install -e ".[test]"
```

The library uses only the Python standard library; `pytest` is the sole
development dependency.

## Tests

Run the full suite from the repository root:

```bash
PYTHONPATH=. pytest -v
```

Any production change must come with a test that exercises it. Keep tests
small, deterministic and free of new dependencies, following the style of
the existing `tests/` modules (synthetic data with known rate constants).

## Backlog item format

Each backlog item is a single, well-scoped change described as:

- **Name** — a short identifier (e.g. `contributing`).
- **Description** — one or two sentences stating what to build or fix.
- **Acceptance** — the observable outcome that proves the item is done,
  checked by a test wherever possible.
- **Files** — the files expected to change (1–3 per item).

Example:

```text
Backlog item `contributing`: Add a CONTRIBUTING guide.
Acceptance: the guide covers setup, tests and backlog item format;
checked by a test.
Files: CONTRIBUTING.md
```

## Pull requests

