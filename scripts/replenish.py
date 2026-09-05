#!/usr/bin/env python3
"""Propose new backlog items when the active backlog runs low.

Runs weekly (see ``.github/workflows/replenish.yml``). If ``BACKLOG.md`` has
fewer than ``THRESHOLD`` undone items, it asks DeepSeek for a batch of new
items and writes them to ``BACKLOG.proposed.md`` for human review.

Proposals are NEVER auto-promoted: the human approves, then
``scripts/promote.py`` moves the approved items into the active backlog.
Pass ``--force`` to propose even when the backlog is not low (for a manual
top-up).
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKLOG = ROOT / "BACKLOG.md"
PROPOSED = ROOT / "BACKLOG.proposed.md"
THRESHOLD = 7

_ITEM_RE = re.compile(r"^- \[ \] `([^`]+)`")


def _run(cmd, **kwargs):
    return subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, **kwargs)


def undone_count() -> int:
    return sum(
        1 for line in BACKLOG.read_text(encoding="utf-8").splitlines() if _ITEM_RE.match(line)
    )


def commit_proposals() -> None:
    env = {**os.environ}
    name = env.get("GIT_AUTHOR_NAME", "Collins Amatu Gorgerat")
    email = env.get("GIT_AUTHOR_EMAIL", "133529715+wl5e@users.noreply.github.com")
    _run(["git", "config", "user.name", name])
    _run(["git", "config", "user.email", email])
    _run(["git", "add", "BACKLOG.proposed.md"])
    res = _run(["git", "commit", "-m", "chore: propose backlog replenishment"])
    if res.returncode != 0:
        return  # nothing new to commit (e.g. identical proposals) — fine
    _run(["git", "push"])


def main() -> int:
    force = "--force" in sys.argv
    if not os.environ.get("DEEPSEEK_API_KEY"):
        print("DEEPSEEK_API_KEY not set; cannot propose. Skipping.")
        return 0

    n = undone_count()
    if not force and n > THRESHOLD:
        print(f"{n} items pending (>{THRESHOLD}); no proposal needed.")
        return 0

    import llm
    items = llm.propose_items(10)
    if not items:
        print("DeepSeek returned no items.")
        return 1

    header = (
        "# Proposed items (awaiting review)\n"
        "# Promote the ones you want with: python scripts/promote.py [slug ...]\n\n"
    )
    lines = [header]
    for slug, title, why in items:
        suffix = f" — {why}" if why else ""
        lines.append(f"- [ ] `{slug}` {title}{suffix} | proposed\n")
    PROPOSED.write_text("".join(lines), encoding="utf-8")

    print(f"Proposed {len(items)} items into BACKLOG.proposed.md")
    commit_proposals()
    return 0


if __name__ == "__main__":
    sys.exit(main())
