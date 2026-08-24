"""Tests for Arrhenius stability predictor model."""

import csv
import math

import pytest

from arrhenius_stability.model import (
    ArrheniusFit,
    StabilityDataError,
    TemperatureRate,
    estimate_rate_constants,
    fit_arrhenius,
    load_data,
    predict_shelf_life,
)


def _write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["temperature_c", "time_months", "potency"])
        writer.writerows(rows)


def test_load_data_parses_valid_csv(tmp_path):
    path = tmp_path / "data.csv"
    _write_csv(path, [(40, 0, 100), (40, 1, 98), (50, 0, 100), (50, 1, 96)])
    records = load_data(str(path))
    assert len(records) == 4
    assert records[0].temperature_c == 40.0
    assert records[0].time_months == 0.0
    assert records[0].potency == 100.0


def test_load_data_detects_missing_column(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("temperature_c,time_months\n40,0\n", encoding="utf-8")
    with pytest.raises(StabilityDataError, match="Missing CSV column"):
        load_data(str(path))


def test_estimate_rate_constants_fits_first_order_rates(tmp_path):
    rows = []
    for temp, k in [(40.0, 0.01), (50.0, 0.02)]:
        for time_months in [0, 1, 2, 3, 6]:
            rows.append((temp, time_months, 100.0 * math.exp(-k * time_months)))
    path = tmp_path / "data.csv"
    _write_csv(path, rows)
    rates = estimate_rate_constants(load_data(str(path)))
    assert set(rates) == {40.0, 50.0}
    assert rates[40.0].rate == pytest.approx(0.01, rel=0.005)
    assert rates[50.0].rate == pytest.approx(0.02, rel=0.005)
    assert rates[40.0].r_squared > 0.999
    assert rates[50.0].r_squared > 0.999


def test_estimate_rate_constants_rejects_no_degradation(tmp_path):
    rows = [
        (40.0, 0, 100),
        (40.0, 1, 100),
        (40.0, 2, 100),
        (50.0, 0, 100),
        (50.0, 1, 100),
        (50.0, 2, 100),
    ]
    path = tmp_path / "flat.csv"
    _write_csv(path, rows)
    with pytest.raises(StabilityDataError, match="no degradation"):
        estimate_rate_constants(load_data(str(path)))


def test_fit_arrhenius_returns_positive_activation_energy():
    rates = {
        40.0: TemperatureRate(40.0, rate=0.01, r_squared=1.0, n_points=3, intercept=math.log(100)),
        50.0: TemperatureRate(50.0, rate=0.02, r_squared=1.0, n_points=3, intercept=math.log(100)),
        60.0: TemperatureRate(60.0, rate=0.04, r_squared=1.0, n_points=3, intercept=math.log(100)),
    }
    fit = fit_arrhenius(rates)
    assert fit.activation_energy_kj_mol > 0
    assert fit.r_squared > 0.99
    assert fit.pre_exponential_factor > 0


def test_predict_shelf_life_returns_positive_values():
    fit = ArrheniusFit(
        slope=-8000.0,
        intercept=20.0,
        r_squared=0.999,
        activation_energy_kj_mol=66.5,
        pre_exponential_factor=math.exp(20.0),
        temperature_c_values=[40.0, 50.0],
    )
    rate, months = predict_shelf_life(fit, storage_temp_c=25.0)
    assert rate > 0
    assert months > 0


def test_predict_shelf_life_rejects_invalid_limit():
    fit = ArrheniusFit(
        slope=-8000.0,
        intercept=20.0,
        r_squared=0.999,
        activation_energy_kj_mol=66.5,
        pre_exponential_factor=math.exp(20.0),
        temperature_c_values=[40.0, 50.0],
    )
    with pytest.raises(StabilityDataError, match="Initial potency"):
        predict_shelf_life(fit, storage_temp_c=25.0, limit=100.0, initial_potency=100.0)
