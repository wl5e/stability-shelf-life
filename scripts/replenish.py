#!/usr/bin/env python3
"""Propose and promote new backlog items when the active queue runs low.

Runs weekly (see ``.github/workflows/replenish.yml``). When ``BACKLOG.md`` has
at most ``THRESHOLD`` open items, it asks DeepSeek for a batch, keeps only
proposals that carry the required metadata (``Acceptance:``, ``Demo:``,
``Files:``), appends them to ``BACKLOG.proposed.md``, then automatically
promotes the conforming ones with ``backlog.promote_safe()``.

The old design required a human to run ``promote.py`` every week and overwrote
the proposal file on every run. Both are fixed here. Pass ``--force`` to
replenish even when the queue is healthy.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKLOG = ROOT / "BACKLOG.md"
PROPOSED = ROOT / "BACKLOG.proposed.md"
THRESHOLD = 15
BATCH = 30


def _run(cmd, **kwargs):
    return subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, **kwargs)


def undone_count() -> int:
    import backlog

    return len(backlog.parse_items(BACKLOG.read_text(encoding="utf-8")))


def commit() -> None:
    env = {**os.environ}
    name = env.get("GIT_AUTHOR_NAME", "Collins Amatu Gorgerat")
    email = env.get("GIT_AUTHOR_EMAIL", "133529715+wl5e@users.noreply.github.com")
    _run(["git", "config", "user.name", name])
    _run(["git", "config", "user.email", email])
    _run(["git", "add", "BACKLOG.md", "BACKLOG.proposed.md"])
    res = _run(["git", "commit", "-m", "chore: replenish backlog"])
    if res.returncode != 0:
        print("Nothing to commit.")
        return
    push = _run(["git", "push"])
    if push.returncode != 0:
        print(f"git push failed: {push.stderr.strip()}; rebasing and retrying.")
        rebase = _run(["git", "pull", "--rebase"])
        if rebase.returncode != 0:
            raise RuntimeError(f"git pull --rebase failed: {rebase.stderr.strip()}")
        push = _run(["git", "push"])
    if push.returncode != 0:
        raise RuntimeError(f"git push failed after retry: {push.stderr.strip()}")
    print("Backlog replenished and pushed.")


def main() -> int:
    force = "--force" in sys.argv
    if not os.environ.get("DEEPSEEK_API_KEY"):
        print("DEEPSEEK_API_KEY not set; cannot propose. Skipping.")
        return 0

    n = undone_count()
    if not force and n > THRESHOLD:
        print(f"{n} items pending (>{THRESHOLD}); no proposal needed.")
        return 0

    import backlog
    import llm

    items = llm.propose_items(BATCH)
    if not items:
        print("DeepSeek returned no items.")
        return 1

    existing = backlog.open_slugs() | backlog.proposed_slugs()
    accepted = []
    rejected = []
    for slug, title, why in items:
        if slug in existing:
            continue
        errors = backlog.validate_title(slug, title)
        if errors:
            rejected.append((slug, errors))
            continue
        accepted.append((slug, title, why))
        existing.add(slug)

    header = (
        "# Proposed items (awaiting promotion)\n"
        "# Conforming proposals are promoted automatically by scripts/replenish.py\n\n"
    )
    if not PROPOSED.exists() or not PROPOSED.read_text(encoding="utf-8").strip():
        PROPOSED.write_text(header, encoding="utf-8")

    with PROPOSED.open("a", encoding="utf-8") as handle:
        for slug, title, why in accepted:
            suffix = f" — {why}" if why else ""
            handle.write(f"- [ ] `{slug}` {title}{suffix} | proposed\n")

    promoted = backlog.promote_safe()
    print(
        f"Proposed {len(accepted)} item(s) ({len(rejected)} rejected for missing "
        f"metadata); promoted {promoted}."
    )
    for slug, errors in rejected:
        print(f"  rejected {slug}: {'; '.join(errors)}")

    if accepted or promoted:
        commit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
