#!/usr/bin/env python3
"""Daily, backlog-driven increment for stability-shelf-life.

Reads the first not-yet-done item in ``BACKLOG.md``, implements it, runs the
full test suite, and — only if every test is green — checks the item off and
commits. A commit is therefore *only* made when the change is real and
verified; there is no filler.

Each item is implemented in one of two ways:

* **Deterministic handler** — an item whose backlog line names a ``handler:``
  function below. Fast, free, fully predictable.
* **LLM provider** — when the item has no handler and ``DEEPSEEK_API_KEY`` is
  set, the change is produced by DeepSeek (see ``llm.py``) and gated by the
  same test suite, with up to three fix-up attempts.

A change that stays green must also pass a free, deterministic scope gate:
at most three files, a test when production code changes, and at most 150
changed lines. An item that fails three attempts is moved to
``BACKLOG.blocked.md`` and the run tries the next item (up to ``MAX_ITEMS``).
There is deliberately no "skip" commit.

The "relevance" of the stream is guaranteed by the backlog: it is a human-
curated list of real, well-scoped improvements.

Modes:
    --dry-run   print the plan without touching anything
    --apply     apply the change and run tests, but do not commit (local check)
    (default)   apply + test + commit + push (used by GitHub Actions)

Exit codes: 0 = done or nothing left to do; 1 = no item shipped this run.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKLOG = ROOT / "BACKLOG.md"
BLOCKED = ROOT / "BACKLOG.blocked.md"

MAX_ITEMS = 3
MAX_FILES = 3
MAX_DIFF_LINES = 150

_ITEM_RE = re.compile(r"^- \[ \] `([^`]+)` (.*?)\s*\|\s*handler:\s*(\w*)\s*$")
_IGNORED_PREFIXES = ("BACKLOG", ".pytest_cache", "__pycache__")


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

def open_items():
    items = []
    for line in BACKLOG.read_text(encoding="utf-8").splitlines():
        m = _ITEM_RE.match(line)
        if m:
            items.append((m.group(1), m.group(2), m.group(3)))
    return items


def next_item():
    """Return ``(slug, title, handler_name)`` of the first undone item."""
    items = open_items()
    return items[0] if items else None


def mark_done(slug: str) -> None:
    lines = BACKLOG.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        m = _ITEM_RE.match(line)
        if m and m.group(1) == slug:
            lines[i] = line.replace("- [ ]", "- [x]", 1)
            break
    BACKLOG.write_text("\n".join(lines) + "\n", encoding="utf-8")


def block_item(slug: str, title: str, reason: str) -> None:
    """Move an item out of the active queue, with an audit trail."""
    lines = BACKLOG.read_text(encoding="utf-8").splitlines()
    kept = []
    for line in lines:
        m = _ITEM_RE.match(line)
        if m and m.group(1) == slug:
            continue
        kept.append(line)
    BACKLOG.write_text("\n".join(kept).rstrip() + "\n", encoding="utf-8")

    if not BLOCKED.exists():
        BLOCKED.write_text(
            "# Blocked items\n\n"
            "Moved here after three failed attempts. Fix the item (or split it)\n"
            "and move it back to BACKLOG.md to retry.\n\n",
            encoding="utf-8",
        )
    with BLOCKED.open("a", encoding="utf-8") as handle:
        handle.write(
            f"- `{slug}` {title}\n"
            f"  blocked: {reason} ({date.today().isoformat()})\n"
        )


def run_tests():
    env = {**os.environ, "PYTHONPATH": str(ROOT)}
    return _run([sys.executable, "-m", "pytest", "-q"], env=env)


def _revert(written) -> None:
    """Undo an implementation. Precise for LLM items, whole-tree otherwise."""
    if written:
        for rel, existed in written:
            p = ROOT / rel
            if existed:
                _run(["git", "checkout", "--", rel])
            elif p.exists():
                p.unlink()
    else:
        _run(["git", "checkout", "--", "."])
        _run(["git", "clean", "-fd", "--", "tests"])


def _changed_paths():
    tracked = _run(["git", "diff", "--name-only"]).stdout.splitlines()
    untracked = _run(["git", "ls-files", "--others", "--exclude-standard"]).stdout.splitlines()
    paths = [p for p in dict.fromkeys(tracked + untracked) if p]
    return [p for p in paths if not p.startswith(_IGNORED_PREFIXES)]


def _diff_lines() -> int:
    total = 0
    for line in _run(["git", "diff", "--numstat"]).stdout.splitlines():
        parts = line.split("\t")
        for value in parts[:2]:
            if value.isdigit():
                total += int(value)
    for rel in _run(["git", "ls-files", "--others", "--exclude-standard"]).stdout.splitlines():
        if rel.startswith(_IGNORED_PREFIXES):
            continue
        path = ROOT / rel
        if path.is_file():
            total += len(path.read_text(encoding="utf-8", errors="ignore").splitlines())
    return total


def _local_gate(written) -> tuple[bool, str]:
    """Free, deterministic scope gate."""
    paths = [rel for rel, _ in written] if written else _changed_paths()
    if not paths:
        return False, "no file changed"
    if len(paths) > MAX_FILES:
        return False, f"{len(paths)} files changed (max {MAX_FILES})"
    has_test = any(rel.startswith("tests/") for rel in paths)
    has_production = any(
        (rel.startswith("stability_shelf_life/") and rel.endswith(".py"))
        or rel == "main.py"
        for rel in paths
    )
    if has_production and not has_test:
        return False, "production code changed without a test"
    changed = _diff_lines()
    if changed > MAX_DIFF_LINES:
        return False, f"{changed} changed lines (max {MAX_DIFF_LINES})"
    return True, ""


def _commit_and_push(subject: str, body: str, add_args) -> None:
    env = {**os.environ}
    name = env.get("GIT_AUTHOR_NAME", "Collins Amatu Gorgerat")
    email = env.get("GIT_AUTHOR_EMAIL", "133529715+wl5e@users.noreply.github.com")
    _run(["git", "config", "user.name", name])
    _run(["git", "config", "user.email", email])
    _run(["git", "add", *add_args])
    res = _run(["git", "commit", "-m", subject, "-m", body])
    if res.returncode != 0:
        raise RuntimeError(f"git commit failed: {res.stderr.strip()}")
    push = _run(["git", "push"])
    if push.returncode != 0:
        # Surface the error instead of silently dropping the commit, and retry
        # once after rebasing in case main advanced since checkout.
        print(f"git push failed: {push.stderr.strip()}; rebasing and retrying.")
        rebase = _run(["git", "pull", "--rebase"])
        if rebase.returncode != 0:
            raise RuntimeError(f"git pull --rebase failed: {rebase.stderr.strip()}")
        push = _run(["git", "push"])
    if push.returncode != 0:
        raise RuntimeError(f"git push failed after retry: {push.stderr.strip()}")


def commit_and_push(subject: str, slug: str) -> None:
    body = f"Backlog item: {slug}\n\nAutomated daily increment — test suite green."
    _commit_and_push(subject, body, ["-A"])


def commit_blocked(slugs) -> None:
    body = "Blocked items moved to BACKLOG.blocked.md.\n\n" + "\n".join(
        f"- {slug}" for slug in slugs
    )
    _commit_and_push(
        f"chore: block {len(slugs)} backlog item(s) after 3 failed attempts",
        body,
        ["BACKLOG.md", "BACKLOG.blocked.md"],
    )


def _attempt(slug: str, title: str, handler_name: str, apply_only: bool) -> tuple[bool, str]:
    """Try one item. Returns (shipped, reason_if_not)."""
    written = []
    subject = ""

    if handler_name:
        fn = HANDLERS.get(handler_name)
        if fn is None:
            return False, f"unknown handler {handler_name!r}"
        try:
            subject = fn()
        except Exception as exc:  # noqa: BLE001 - handlers are trusted but may drift
            _revert([])
            return False, f"handler failed: {exc}"
        if not _changed_paths():
            return False, "handler produced no change"
        ok, reason = _local_gate([])
        if not ok:
            _revert([])
            return False, reason
        if run_tests().returncode != 0:
            _revert([])
            return False, "tests failed"
        mark_done(slug)
        if not apply_only:
            commit_and_push(subject, slug)
            print(f"Committed and pushed: {subject}")
        else:
            print("Tests green. (--apply: not committing.)")
        return True, ""

    if not os.environ.get("DEEPSEEK_API_KEY"):
        return False, "DEEPSEEK_API_KEY not set"

    import llm

    feedback = None
    for attempt in (1, 2, 3):
        try:
            subject, written = llm.implement(slug, title, feedback)
        except Exception as exc:  # noqa: BLE001 - fail the item cleanly
            print(f"LLM attempt {attempt} raised: {exc}")
            _revert(written)
            return False, f"LLM error: {exc}"

        if not written:
            print(f"Attempt {attempt}: the model changed nothing; retrying.")
            feedback = (
                "You must change at least one file. There is no 'already satisfied' "
                "answer: implement the item for real, with a test."
            )
            _revert(written)
            written = []
            continue

        workflow_touched = [rel for rel, _ in written if rel.startswith(".github/workflows/")]
        if workflow_touched:
            print(
                f"Attempt {attempt}: change touches {workflow_touched}; "
                "reverting and retrying (GITHUB_TOKEN cannot push workflow files)."
            )
            feedback = (
                "Do NOT modify or create any file under .github/workflows/ — the "
                "automation's push token is rejected by GitHub for workflow files. "
                "Re-implement the item without touching the workflows directory."
            )
            _revert(written)
            written = []
            continue

        if not _changed_paths():
            print("LLM produced no effective change; retrying.")
            feedback = "Your files were identical to the current content. Make a real change."
            _revert(written)
            written = []
            continue

        ok, reason = _local_gate(written)
        if not ok:
            print(f"Attempt {attempt}: local gate rejected the change: {reason}")
            feedback = (
                f"Your change was rejected by the local scope gate: {reason}. "
                "Keep it to at most 3 files, add or update a test when you change "
                "production code, and keep the diff under 150 lines."
            )
            _revert(written)
            written = []
            continue

        res = run_tests()
        if res.returncode != 0:
            print(f"Attempt {attempt}: tests failed; feeding output back and retrying.")
            feedback = res.stdout + res.stderr
            _revert(written)
            written = []
            continue

        mark_done(slug)
        if not apply_only:
            commit_and_push(subject, slug)
            print(f"Committed and pushed: {subject}")
        else:
            print("Tests green. (--apply: not committing.)")
        return True, ""

    return False, "3 attempts failed"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="print the plan only")
    parser.add_argument("--apply", action="store_true", help="apply + test, no commit")
    args = parser.parse_args(argv)

    items = open_items()
    if not items:
        print("No undone backlog item. Nothing to do.")
        return 0

    if args.dry_run:
        for slug, _, handler_name in items[:MAX_ITEMS]:
            if handler_name:
                mode = f"deterministic handler ({handler_name})"
            elif os.environ.get("DEEPSEEK_API_KEY"):
                mode = "LLM (DeepSeek)"
            else:
                mode = "none (no handler, no DEEPSEEK_API_KEY)"
            print(f"- {slug}: {mode}")
        return 0

    blocked = []
    for slug, title, handler_name in items[:MAX_ITEMS]:
        print(f"Selected backlog item: {slug}")
        shipped, reason = _attempt(slug, title, handler_name, args.apply)
        if shipped:
            return 0
        print(f"Blocking {slug}: {reason}")
        block_item(slug, title, reason)
        blocked.append(slug)

    if blocked and not args.apply:
        commit_blocked(blocked)
    print(f"No item shipped this run; blocked: {', '.join(blocked)}.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
