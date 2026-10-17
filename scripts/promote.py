#!/usr/bin/env python3
"""Promote proposed items into the active backlog.

Usage:
    python scripts/promote.py slug1 slug2     # promote selected items
    python scripts/promote.py --all --safe    # promote every conforming item
    python scripts/promote.py --all           # promote everything (no validation)

Promotion refuses duplicate slugs and, with ``--safe``, items that do not carry
``Acceptance:``, ``Demo:`` and ``Files:``. ``scripts/replenish.py`` uses the
same helpers to auto-promote conforming proposals.
"""

from __future__ import annotations

import sys

import backlog

PROPOSED = backlog.PROPOSED


def main() -> int:
    args = sys.argv[1:]
    promote_all = "--all" in args
    safe = "--safe" in args
    slugs = {a for a in args if not a.startswith("-")}

    if not promote_all and not slugs:
        print(__doc__)
        return 2
    if not PROPOSED.exists():
        print("No BACKLOG.proposed.md; nothing to promote.")
        return 0

    existing = backlog.open_slugs()
    chosen = []
    kept = []
    for line in PROPOSED.read_text(encoding="utf-8").splitlines():
        m = backlog.PROP_RE.match(line)
        if not m:
            kept.append(line)
            continue
        slug, title = m.group(1), m.group(2)
        if not promote_all and slug not in slugs:
            kept.append(line)
            continue
        if slug in existing:
            print(f"skip {slug}: already in BACKLOG.md")
            kept.append(line)
            continue
        if safe and backlog.validate_title(slug, title):
            print(f"skip {slug}: {backlog.validate_title(slug, title)}")
            kept.append(line)
            continue
        chosen.append(f"- [ ] `{slug}` {title} | handler:")
        existing.add(slug)

    if not chosen:
        print("Nothing selected to promote.")
        return 0

    with backlog.BACKLOG.open("a", encoding="utf-8") as handle:
        handle.write("\n" + "\n".join(chosen) + "\n")
    PROPOSED.write_text("\n".join(kept).rstrip() + "\n", encoding="utf-8")

    print(f"Promoted {len(chosen)} item(s) into BACKLOG.md.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
