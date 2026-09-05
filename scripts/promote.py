#!/usr/bin/env python3
"""Promote approved proposed items into the active backlog.

Reads ``BACKLOG.proposed.md`` and moves the requested (or, by default, all)
items into ``BACKLOG.md`` as active items. Run this AFTER a human has reviewed
the proposals — this is the approval step. This only edits the files; commit
them afterwards (or run it from a checked-out repo and commit separately).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKLOG = ROOT / "BACKLOG.md"
PROPOSED = ROOT / "BACKLOG.proposed.md"

_PROP_RE = re.compile(r"^- \[ \] `([^`]+)` (.*?)\s*\|\s*proposed\s*$")


def main() -> int:
    slugs = set(sys.argv[1:])
    if not PROPOSED.exists():
        print("No BACKLOG.proposed.md; nothing to promote.")
        return 0

    chosen = []
    kept = []
    for line in PROPOSED.read_text(encoding="utf-8").splitlines():
        m = _PROP_RE.match(line)
        if not m:
            kept.append(line)
            continue
        slug, title = m.group(1), m.group(2)
        if slugs and slug not in slugs:
            kept.append(line)  # not selected — leave it proposed
            continue
        chosen.append(f"- [ ] `{slug}` {title} | handler:")

    if not chosen:
        print("Nothing selected to promote.")
        return 0

    with BACKLOG.open("a", encoding="utf-8") as handle:
        handle.write("\n" + "\n".join(chosen) + "\n")

    PROPOSED.write_text("\n".join(kept).rstrip() + "\n", encoding="utf-8")

    print(f"Promoted {len(chosen)} item(s) into BACKLOG.md.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
