"""Tests for the statistical core (stability_shelf_life.model)."""

import math

import pytest

from stability_shelf_life.model import (
    StabilityError,
    degradation_rates_by_temperature,
    estimate_shelf_life,
    fit_arrhenius,
    fit_kinetics,
    linear_fit,
    predict_arrhenius_rate,
    t_critical,
)


def test_linear_fit_recovers_known_line():
    xs = [0.0, 1.0, 2.0, 3.0, 4.0]
    ys = [3.0 + 2.0 * x for x in xs]
    r = linear_fit(xs, ys)
    assert r.slope == pytest.approx(2.0)
    assert r.intercept == pytest.approx(3.0)
    assert r.r_squared == pytest.approx(1.0)
    assert r.residual_std_error == pytest.approx(0.0)


def test_linear_fit_requires_three_points():
    with pytest.raises(StabilityError):
        linear_fit([0.0, 1.0], [1.0, 2.0])


def test_t_critical_table_and_normal_approx():
    assert t_critical(1) == pytest.approx(6.314)
    assert t_critical(30) == pytest.approx(1.697)
    assert t_critical(120) == pytest.approx(1.64485, abs=1e-4)


def test_first_order_kinetics_recovers_rate():
    k_true = 0.01
    times = [0.0, 3.0, 6.0, 9.0, 12.0]
    values = [100.0 * math.exp(-k_true * t) for t in times]
    fit = fit_kinetics(times, values, order=1)
    assert fit.rate == pytest.approx(k_true, rel=0.01)
    assert fit.initial == pytest.approx(100.0, rel=0.01)
    assert fit.r_squared > 0.999


def test_zero_order_kinetics_recovers_rate():
    k_true = 0.5
    times = [0.0, 3.0, 6.0, 9.0, 12.0]
    values = [100.0 - k_true * t for t in times]
    fit = fit_kinetics(times, values, order=0)
    assert fit.rate == pytest.approx(k_true, rel=0.01)
    assert fit.initial == pytest.approx(100.0, rel=0.01)


def test_kinetics_rejects_non_positive_values():
    with pytest.raises(StabilityError, match="positive"):
        fit_kinetics([0.0, 1.0, 2.0], [100.0, 0.0, 50.0], order=1)


def test_shelf_life_point_estimate_and_lower_bound():
    k_true = 0.0045
    times = [0.0, 3.0, 6.0, 9.0, 12.0, 18.0, 24.0]
    # Small assay noise so the residual error is non-zero (the realistic case).
    noise = [0.0, 0.15, -0.10, 0.05, -0.20, 0.10, -0.05]
    values = [100.0 * math.exp(-k_true * t) + n for t, n in zip(times, noise)]
    fit = fit_kinetics(times, values, order=1)
    shelf = estimate_shelf_life(fit, limit=90.0)

    point_expected = math.log(100.0 / 90.0) / k_true
    assert shelf.point_estimate_months == pytest.approx(point_expected, rel=0.02)
    # Uncertainty must shorten the shelf life, not lengthen it.
    assert shelf.lower_bound_months > 0
    assert shelf.lower_bound_months < shelf.point_estimate_months
    assert shelf.stable is True


def test_shelf_life_stable_flag_when_no_degradation():
    times = [0.0, 3.0, 6.0]
    values = [100.0, 100.0, 100.0]
    fit = fit_kinetics(times, values, order=1)
    shelf = estimate_shelf_life(fit, limit=90.0)
    assert shelf.stable is False
    assert shelf.point_estimate_months == math.inf


def test_arrhenius_fit_and_prediction():
    # Rates at 40/50/60 C, doubling per 10 C (activation energy consistent).
    temps = [40.0, 50.0, 60.0]
    rates = [0.01, 0.02, 0.04]
    fit = fit_arrhenius(temps, rates)
    assert fit.activation_energy_kj_mol > 0
    assert fit.r_squared > 0.99

    k_25 = predict_arrhenius_rate(fit, 25.0)
    # Extrapolation below the measured range must give a smaller rate.
    assert 0 < k_25 < rates[0]


def test_arrhenius_rejects_non_physical_slope():
    with pytest.raises(StabilityError, match="non-physical"):
        fit_arrhenius([40.0, 50.0, 60.0], [0.04, 0.02, 0.01])


def test_degradation_rates_by_temperature():
    temps = [40.0, 40.0, 40.0, 50.0, 50.0, 50.0]
    times = [0.0, 3.0, 6.0, 0.0, 3.0, 6.0]
    values = [
        100.0, 100 * math.exp(-0.01 * 3), 100 * math.exp(-0.01 * 6),
        100.0, 100 * math.exp(-0.02 * 3), 100 * math.exp(-0.02 * 6),
    ]
    fits = degradation_rates_by_temperature(times, temps, values)
    assert set(fits) == {40.0, 50.0}
    assert fits[40.0].rate == pytest.approx(0.01, rel=0.01)
    assert fits[50.0].rate == pytest.approx(0.02, rel=0.01)
