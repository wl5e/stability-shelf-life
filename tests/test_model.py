"""Tests for the statistical core (stability_shelf_life.model)."""

import math

import pytest

from stability_shelf_life.model import (
    StabilityError,
    degradation_rates_by_temperature,
    estimate_shelf_life,
    f_test_p_value,
    fit_arrhenius,
    fit_kinetics,
    linear_fit,
    outlier_diagnostic,
    predict_arrhenius_rate,
    regularized_incomplete_beta,
    slope_difference_test,
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

    with pytest.warns(UserWarning, match="outside the measured"):
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


def test_regularized_incomplete_beta_and_f_tail():
    # I_x(a, a) is 0.5 at x = 0.5 by symmetry.
    assert regularized_incomplete_beta(2.5, 2.5, 0.5) == pytest.approx(0.5, abs=1e-9)
    assert f_test_p_value(1.0, 1, 1) == pytest.approx(0.5, abs=1e-6)
    assert f_test_p_value(1.0, 5, 5) == pytest.approx(0.5, abs=1e-6)
    # Upper tail of F(1, 1) at 5.05 equals 2 * P(T_1 > sqrt(5.05)) ~ 0.2665.
    assert f_test_p_value(5.05, 1, 1) == pytest.approx(0.2665, abs=1e-3)
    assert f_test_p_value(0.0, 3, 10) == 1.0


def test_slope_difference_test_does_not_flag_equal_slopes():
    times = [0.0, 3.0, 6.0, 9.0, 12.0]
    noise = [0.0, 0.15, -0.10, 0.05, -0.20]
    k_true = 0.01
    batch_a = [100.0 * math.exp(-k_true * t) + n for t, n in zip(times, noise)]
    batch_b = [
        100.0 * math.exp(-k_true * t) + n for t, n in zip(times, reversed(noise))
    ]
    comparison = slope_difference_test(
        [
            fit_kinetics(times, batch_a, order=1),
            fit_kinetics(times, batch_b, order=1),
        ]
    )
    assert comparison.order == 1
    assert comparison.df_between == 1
    assert comparison.df_within == 6  # 2 batches * (5 - 2)
    assert comparison.slopes_differ is False
    assert comparison.p_value > 0.05


def test_slope_difference_test_detects_different_slopes():
    times = [0.0, 3.0, 6.0, 9.0, 12.0]
    noise = [0.0, 0.15, -0.10, 0.05, -0.20]
    fast = [100.0 * math.exp(-0.03 * t) + n for t, n in zip(times, noise)]
    slow = [
        100.0 * math.exp(-0.005 * t) + n for t, n in zip(times, reversed(noise))
    ]
    comparison = slope_difference_test(
        [
            fit_kinetics(times, fast, order=1),
            fit_kinetics(times, slow, order=1),
        ]
    )
    assert comparison.slopes_differ is True
    assert comparison.p_value < 0.05
    assert comparison.f_statistic > 1.0
    # The faster-degrading batch has the larger positive rate.
    assert comparison.rates[0] > comparison.rates[1]


def test_slope_difference_test_validates_inputs():
    times = [0.0, 3.0, 6.0, 9.0]
    values = [100.0 * math.exp(-0.01 * t) for t in times]
    first_order = fit_kinetics(times, values, order=1)
    zero_order = fit_kinetics(times, values, order=0)

    with pytest.raises(StabilityError, match="at least two"):
        slope_difference_test([first_order])
    with pytest.raises(StabilityError, match="same kinetic model"):
        slope_difference_test([first_order, zero_order])


def test_outlier_diagnostic_flags_studentized_residual():
    xs = [0.0, 1.0, 2.0, 3.0, 4.0, 5.0]
    ys = [10.1, 9.9, 10.2, 9.8, 10.0, 14.0]
    reg = linear_fit(xs, ys)
    diag = outlier_diagnostic(reg, xs, ys)
    assert diag.is_outlier == [False, False, False, False, False, True]
    assert abs(diag.studentized_residuals[-1]) > 2.5
    assert len(diag.residuals) == len(xs)
    assert len(diag.leverage) == len(xs)


def test_outlier_diagnostic_flags_high_leverage_point():
    xs = [float(x) for x in range(10)] + [100.0]
    ys = [2.0 * x + 1.0 for x in range(10)] + [201.0]
    reg = linear_fit(xs, ys)
    diag = outlier_diagnostic(reg, xs, ys)
    assert diag.leverage[-1] > diag.leverage_cutoff
    assert diag.is_outlier[-1] is True


def test_outlier_diagnostic_clean_data_has_no_flags():
    xs = [float(x) for x in range(10)]
    ys = [3.0 + 2.0 * x for x in xs]
    reg = linear_fit(xs, ys)
    diag = outlier_diagnostic(reg, xs, ys)
    assert not any(diag.is_outlier)


def test_outlier_diagnostic_validates_inputs():
    xs = [0.0, 1.0, 2.0, 3.0, 4.0]
    ys = [2.0 * x + 1.0 for x in xs]
    reg = linear_fit(xs, ys)
    with pytest.raises(ValueError, match="same length"):
        outlier_diagnostic(reg, xs, ys[:-1])
    with pytest.raises(StabilityError, match="at least 4"):
        outlier_diagnostic(
            linear_fit([0.0, 1.0, 2.0], [1.0, 2.0, 3.0]),
            [0.0, 1.0, 2.0],
            [1.0, 2.0, 3.0],
        )
