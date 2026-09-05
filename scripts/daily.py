#!/usr/bin/env python3
"""Daily, backlog-driven increment for stability-shelf-life.

Reads the first not-yet-done item in ``BACKLOG.md`` that has an implemented
handler, applies the handler, runs the full test suite, and — only if every
test is green — checks the item off and commits. A commit is therefore *only*
made when the change is real and verified; there is no filler.

The "relevance" of the stream is guaranteed by the backlog: it is a human-
curated list of real, well-scoped improvements. Each item is implemented by a
handler function below. Items in the backlog without a handler are planned
next steps (to be given a handler, or produced by an LLM provider later).

Modes:
    --dry-run   print the plan without touching anything
    --apply     apply the change and run tests, but do not commit (local check)
    (default)   apply + test + commit + push (used by GitHub Actions)

Exit codes: 0 = done or nothing left to do; 1 = tests failed (nothing committed).
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKLOG = ROOT / "BACKLOG.md"

_ITEM_RE = re.compile(r"^- \[ \] `([^`]+)`.*?handler: (\w*)\s*$")


def _replace(path: Path, old: str, new: str, count: int = 1) -> None:
    """Replace ``old`` with ``new`` in ``path``; fail loudly on anchor drift."""
    text = path.read_text(encoding="utf-8")
    found = text.count(old)
    if found != count:
        raise RuntimeError(
            f"{path.name}: expected {count} occurrence(s) of anchor, found {found}"
        )
    path.write_text(text.replace(old, new), encoding="utf-8")


def _run(cmd, **kwargs):
    return subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, **kwargs)


# --------------------------------------------------------------------------- #
# Handlers — one per backlog item. Each returns the commit subject.
# --------------------------------------------------------------------------- #

def reject_nonfinite_inputs() -> str:
    """Reject NaN/Inf CSV inputs instead of letting them corrupt the fit."""
    io = ROOT / "stability_shelf_life" / "io.py"

    _replace(
        io,
        "import csv\nfrom collections import defaultdict",
        "import csv\nimport math\nfrom collections import defaultdict",
    )

    # Both loaders share this exact block (stability + accelerated): insert a
    # finiteness guard before each `if t < 0:` check.
    _replace(
        io,
        (
            "            if t < 0:\n"
            '                raise StabilityError(f"{path} row {row_num}: negative time")'
        ),
        (
            "            if not (math.isfinite(t) and math.isfinite(v)):\n"
            '                raise StabilityError(f"{path} row {row_num}: non-finite time or assay value")\n'
            "            if t < 0:\n"
            '                raise StabilityError(f"{path} row {row_num}: negative time")'
        ),
        count=2,
    )

    # Temperature must be finite too (accelerated loader).
    _replace(
        io,
        "            if temp <= -273.15:",
        (
            "            if not math.isfinite(temp):\n"
            '                raise StabilityError(f"{path} row {row_num}: non-finite temperature")\n'
            "            if temp <= -273.15:"
        ),
    )

    tests = ROOT / "tests" / "test_io.py"
    tests.write_text(
        tests.read_text(encoding="utf-8")
        + '''

def test_load_stability_data_rejects_non_finite(tmp_path):
    p = tmp_path / "nan.csv"
    p.write_text(
        "time_months,assay_percent,batch_id\\n0,100,A01\\n3,nan,A01\\n6,97,A01\\n",
        encoding="utf-8",
    )
    with pytest.raises(StabilityError, match="non-finite"):
        load_stability_data(str(p))


def test_load_accelerated_data_rejects_non_finite(tmp_path):
    p = tmp_path / "inf.csv"
    p.write_text(
        "temperature_c,time_months,potency\\n40,0,100\\n50,3,inf\\n60,6,80\\n",
        encoding="utf-8",
    )
    with pytest.raises(StabilityError, match="non-finite"):
        load_accelerated_data(str(p))
''',
        encoding="utf-8",
    )
    return "fix(io): reject non-finite (NaN/Inf) CSV inputs"


def cli_end_to_end_test() -> str:
    """Add the first end-to-end test covering the CLI (q1e + arrhenius)."""
    test = ROOT / "tests" / "test_cli.py"
    test.write_text(
        '''"""End-to-end tests for the command-line interface."""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _run_cli(*args):
    return subprocess.run(
        [sys.executable, "main.py", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )


def test_q1e_json_roundtrip():
    res = _run_cli("q1e", "--input", "examples/stability_data.csv", "--limit", "90", "--json")
    assert res.returncode == 0, res.stderr
    report = json.loads(res.stdout)
    assert report["limit"] == 90.0
    assert {b["batch_id"] for b in report["batches"]} == {"A01", "B02"}
    for b in report["batches"]:
        assert b["best_model"] in ("zero-order", "first-order")
        assert b["shelf_life_months"] > 0
        assert b["shelf_life_lower_95_months"] <= b["shelf_life_months"]


def test_arrhenius_json_roundtrip():
    res = _run_cli("arrhenius", "--input", "examples/accelerated_data.csv", "--storage-temp", "25", "--json")
    assert res.returncode == 0, res.stderr
    report = json.loads(res.stdout)
    assert report["arrhenius"]["activation_energy_kj_mol"] > 0
    assert report["prediction"]["rate_1_per_month"] > 0
''',
        encoding="utf-8",
    )
    return "test(cli): add end-to-end test for q1e and arrhenius"


def readme_worked_example() -> str:
    """Add a worked example (real numbers) to the README."""
    readme = ROOT / "README.md"
    section = (
        "## Worked example\n"
        "\n"
        "Run the ICH Q1E analysis on the bundled two-batch study:\n"
        "\n"
        "```bash\n"
        "python main.py q1e --input examples/stability_data.csv --limit 90\n"
        "```\n"
        "\n"
        "Batch **A01** fits best as **first-order** (k = 0.004532 /month, R² = 0.9993),\n"
        "giving a shelf life of **23.24 months** with a one-sided 95% lower confidence\n"
        "bound of **22.89 months**. Batch **B02** degrades slightly faster\n"
        "(k = 0.005059 /month) and reaches the 90% limit at **20.43 months**\n"
        "(lower bound **20.37 months**). Because ICH Q1E requires the *lower bound*,\n"
        "the reportable shelf life is the shorter of the two bounds.\n"
        "\n"
        "Accelerated data extrapolate to long-term storage with the Arrhenius model:\n"
        "\n"
        "```bash\n"
        "python main.py arrhenius --input examples/accelerated_data.csv --storage-temp 25\n"
        "```\n"
        "\n"
    )
    _replace(readme, "## Tests\n", section + "## Tests\n")
    return "docs(readme): add worked example"


HANDLERS = {
    "reject_nonfinite_inputs": reject_nonfinite_inputs,
    "cli_end_to_end_test": cli_end_to_end_test,
    "readme_worked_example": readme_worked_example,
}


# --------------------------------------------------------------------------- #
# Engine
# --------------------------------------------------------------------------- #

def next_item() -> tuple[str, str] | None:
    """Return ``(slug, handler_name)`` of the first undone item with a handler."""
    for line in BACKLOG.read_text(encoding="utf-8").splitlines():
        m = _ITEM_RE.match(line)
        if m and m.group(2):
            return m.group(1), m.group(2)
    return None


def mark_done(slug: str) -> None:
    lines = BACKLOG.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        m = _ITEM_RE.match(line)
        if m and m.group(1) == slug:
            lines[i] = line.replace("- [ ]", "- [x]", 1)
            break
    BACKLOG.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_tests() -> bool:
    env = {**os.environ, "PYTHONPATH": str(ROOT)}
    res = _run([sys.executable, "-m", "pytest", "-q"], env=env)
    return res.returncode == 0


def commit_and_push(subject: str, slug: str) -> None:
    env = {**os.environ}
    name = env.get("GIT_AUTHOR_NAME", "Collins Amatu Gorgerat")
    email = env.get("GIT_AUTHOR_EMAIL", "133529715+wl5e@users.noreply.github.com")
    _run(["git", "config", "user.name", name])
    _run(["git", "config", "user.email", email])
    _run(["git", "add", "-A"])
    body = f"Backlog item: {slug}\n\nAutomated daily increment — test suite green."
    res = _run(["git", "commit", "-m", subject, "-m", body])
    if res.returncode != 0:
        raise RuntimeError(f"git commit failed: {res.stderr.strip()}")
    _run(["git", "push"])


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="print the plan only")
    parser.add_argument("--apply", action="store_true", help="apply + test, no commit")
    args = parser.parse_args(argv)

    item = next_item()
    if item is None:
        print("No undone backlog item with an implemented handler. Nothing to do.")
        return 0

    slug, handler_name = item
    print(f"Selected backlog item: {slug} (handler: {handler_name})")

    if args.dry_run:
        print("Dry run — no changes made.")
        return 0

    handler = HANDLERS[handler_name]
    subject = handler()

    print("Running test suite...")
    if not run_tests():
        print("Tests FAILED — nothing committed. Reverting working tree.")
        _run(["git", "checkout", "--", "."])
        return 1

    mark_done(slug)
    if args.apply:
        print("Tests green. (--apply: not committing.)")
        return 0

    commit_and_push(subject, slug)
    print(f"Committed and pushed: {subject}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
