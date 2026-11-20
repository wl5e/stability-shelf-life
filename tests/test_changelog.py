"""Tests for the project changelog."""

from pathlib import Path

from stability_shelf_life import __version__


CHANGELOG = Path(__file__).resolve().parents[1] / "CHANGELOG.md"


def test_changelog_follows_keep_a_changelog() -> None:
    text = CHANGELOG.read_text(encoding="utf-8")

    assert text.startswith("# Changelog")
    assert "Keep a Changelog" in text
    assert "## [Unreleased]" in text


def test_changelog_lists_current_version() -> None:
    text = CHANGELOG.read_text(encoding="utf-8")

    assert f"## [{__version__}]" in text
    assert "## [2.0.0]" in text


def test_changelog_links_release_versions() -> None:
    text = CHANGELOG.read_text(encoding="utf-8")

    assert "[Unreleased]:" in text
    assert "[2.0.0]:" in text
