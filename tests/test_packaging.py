"""Tests for the packaging metadata that makes the project pip-installable."""

from pathlib import Path

import pytest

from stability_shelf_life import __version__

tomllib = pytest.importorskip("tomllib")  # stdlib only on Python 3.11+

ROOT = Path(__file__).resolve().parent.parent


def _pyproject():
    path = ROOT / "pyproject.toml"
    assert path.exists(), "pyproject.toml is required for pip installation"
    with path.open("rb") as handle:
        return tomllib.load(handle)


def test_pyproject_declares_build_backend_and_package():
    data = _pyproject()
    assert data["build-system"]["build-backend"] == "setuptools.build_meta"
    assert data["project"]["name"] == "stability-shelf-life"
    includes = data["tool"]["setuptools"]["packages"]["find"]["include"]
    assert "stability_shelf_life*" in includes


def test_pyproject_version_matches_package():
    data = _pyproject()
    assert data["project"]["dynamic"] == ["version"]
    attr = data["tool"]["setuptools"]["dynamic"]["version"]["attr"]
    assert attr == "stability_shelf_life.__version__"
    assert __version__ == "2.0.0"
