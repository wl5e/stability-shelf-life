"""Tests for UTF-8 BOM acceptance in CSV input loaders."""

import pytest

from stability_shelf_life.io import (
    load_accelerated_data,
    load_stability_data,
)


def _write(path, text):
    path.write_text(text, encoding="utf-8")


def test_load_stability_data_accepts_utf8_bom(tmp_path):
    p = tmp_path / "stability_bom.csv"
    _write(p, "\ufefftime_months,assay_percent,batch_id\n0,100,A01\n3,97,A01\n6,94,A01\n")
    batches = load_stability_data(str(p))
    assert set(batches) == {"A01"}
    assert batches["A01"].values[0] == pytest.approx(100.0)


def test_load_accelerated_data_accepts_utf8_bom(tmp_path):
    p = tmp_path / "accelerated_bom.csv"
    _write(p, "\ufefftemperature_c,time_months,potency\n40,0,100\n40,3,97\n40,6,94\n")
    data = load_accelerated_data(str(p))
    assert data.temperatures == [40.0, 40.0, 40.0]
