"""Tests for CSV input handling (stability_shelf_life.io)."""

import pytest

from stability_shelf_life.io import (
    load_accelerated_data,
    load_stability_data,
)
from stability_shelf_life.model import StabilityError


def _write(path, text):
    path.write_text(text, encoding="utf-8")


def test_load_stability_data_multiple_batches(tmp_path):
    p = tmp_path / "data.csv"
    _write(
        p,
        "time_months,assay_percent,batch_id\n"
        "0,100.1,A01\n3,98.9,A01\n6,97.6,A01\n"
        "0,99.8,B02\n3,98.4,B02\n6,96.9,B02\n",
    )
    batches = load_stability_data(str(p))
    assert set(batches) == {"A01", "B02"}
    assert len(batches["A01"].times) == 3
    assert batches["B02"].values[0] == pytest.approx(99.8)


def test_load_stability_data_missing_column(tmp_path):
    p = tmp_path / "bad.csv"
    _write(p, "time_months,assay_percent\n0,100\n")
    with pytest.raises(StabilityError, match="missing column"):
        load_stability_data(str(p))


def test_load_stability_data_duplicate_time(tmp_path):
    p = tmp_path / "dup.csv"
    _write(p, "time_months,assay_percent,batch_id\n0,100,A01\n0,99,A01\n3,97,A01\n")
    with pytest.raises(StabilityError, match="duplicate"):
        load_stability_data(str(p))


def test_load_accelerated_data(tmp_path):
    p = tmp_path / "acc.csv"
    _write(
        p,
        "temperature_c,time_months,potency\n"
        "40,0,100\n40,3,97\n40,6,94\n"
        "50,0,100\n50,3,94\n50,6,88\n",
    )
    data = load_accelerated_data(str(p))
    assert len(data.times) == 6
    assert set(data.temperatures) == {40.0, 50.0}
