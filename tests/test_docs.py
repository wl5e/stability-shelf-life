"""Tests that the contributor documentation is present and complete."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_contributing_guide_exists():
    assert (ROOT / "CONTRIBUTING.md").is_file()


def test_contributing_guide_covers_required_topics():
    text = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    lowered = text.lower()
    # Setup instructions.
    assert "## setup" in lowered
    assert "pip install" in lowered
    # How to run the tests.
    assert "## tests" in lowered
    assert "pytest" in lowered
    # The backlog item format.
    assert "backlog item format" in lowered
