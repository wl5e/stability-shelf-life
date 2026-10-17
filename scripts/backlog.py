#!/usr/bin/env python3
"""Validate and promote backlog items.

Item format (one line, parsed by ``daily.py``):

    - [ ] `slug` <outcome>. Acceptance: <criterion>. Demo: `<command>`. \
Files: <path1>, <path2>. | handler:

``Files:`` lists the files the item is expected to touch (at most 3). The
linter also enforces the metadata so the daily run always receives a testable
definition of done.

Usage:
    python scripts/backlog.py --check
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKLOG = ROOT / "BACKLOG.md"
PROPOSED = ROOT / "BACKLOG.proposed.md"

ITEM_RE = re.compile(r"^- \[ \] `([^`]+)` (.*?)\s*\|\s*handler:\s*(\w*)\s*$")
PROP_RE = re.compile(r"^- \[ \] `([^`]+)` (.*?)\s*\|\s*proposed\s*$")
FILES_RE = re.compile(r"Files:\s*(.+)$")

MAX_FILES = 3
REQUIRED_MARKERS = ("Acceptance:", "Demo:", "Files:")


def parse_items(text: str):
    """Return ``(slug, title, handler)`` for every open backlog line."""
    items = []
    for line in text.splitlines():
        m = ITEM_RE.match(line)
        if m:
            items.append((m.group(1), m.group(2), m.group(3)))
    return items


def parse_proposals(text: str):
    items = []
    for line in text.splitlines():
        m = PROP_RE.match(line)
        if m:
            items.append((m.group(1), m.group(2)))
    return items


def validate_title(slug: str, title: str) -> list[str]:
    errors = []
    for marker in REQUIRED_MARKERS:
        if marker not in title:
            errors.append(f"{slug}: missing {marker}")
    match = FILES_RE.search(title)
    if match:
        files = [f.strip().rstrip(".") for f in match.group(1).split(",") if f.strip()]
        if len(files) > MAX_FILES:
            errors.append(f"{slug}: {len(files)} files listed (max {MAX_FILES})")
    return errors


def open_slugs() -> set[str]:
    return {slug for slug, _, _ in parse_items(BACKLOG.read_text(encoding="utf-8"))}


def proposed_slugs() -> set[str]:
    if not PROPOSED.exists():
        return set()
    return {slug for slug, _ in parse_proposals(PROPOSED.read_text(encoding="utf-8"))}


def check() -> int:
    errors = []
    seen = set()
    for slug, title, _ in parse_items(BACKLOG.read_text(encoding="utf-8")):
        if slug in seen:
            errors.append(f"{slug}: duplicate slug in BACKLOG.md")
        seen.add(slug)
        errors.extend(validate_title(slug, title))
    if PROPOSED.exists():
        for slug, title in parse_proposals(PROPOSED.read_text(encoding="utf-8")):
            if slug in seen:
                errors.append(f"{slug}: already in BACKLOG.md")
            seen.add(slug)
            errors.extend(validate_title(slug, title))
    if errors:
        print("Backlog validation failed:")
        for error in errors:
            print(f"  - {error}")
        return 1
    print(f"Backlog OK: {len(seen)} unique item(s).")
    return 0


def promote_safe() -> int:
    """Promote every conforming proposal; leaves invalid/duplicate ones alone."""
    if not PROPOSED.exists():
        return 0
    existing = open_slugs()
    chosen = []
    kept = []
    for line in PROPOSED.read_text(encoding="utf-8").splitlines():
        m = PROP_RE.match(line)
        if not m:
            kept.append(line)
            continue
        slug, title = m.group(1), m.group(2)
        if slug in existing or validate_title(slug, title):
            kept.append(line)
            continue
        chosen.append(f"- [ ] `{slug}` {title} | handler:")
        existing.add(slug)
    if chosen:
        with BACKLOG.open("a", encoding="utf-8") as handle:
            handle.write("\n" + "\n".join(chosen) + "\n")
    PROPOSED.write_text("\n".join(kept).rstrip() + "\n", encoding="utf-8")
    return len(chosen)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="validate the backlogs")
    args = parser.parse_args(argv)
    if args.check:
        return check()
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
