"""Tests for README documentation."""

from pathlib import Path


README = Path(__file__).resolve().parents[1] / "README.md"


def test_readme_lists_ten_shipped_commands():
    text = README.read_text(encoding="utf-8")
    assert "What shipped this quarter" in text
    section = text.split("What shipped this quarter", 1)[1].split("## ", 1)[0]
    commands = [
        line
        for line in section.splitlines()
        if line.strip().startswith(("python main.py", "stability-shelf-life "))
    ]
    assert len(commands) >= 10
