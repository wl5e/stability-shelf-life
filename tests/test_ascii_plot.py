"""Tests for the ASCII confidence-band renderer."""

import math

import pytest

from stability_shelf_life.ascii_plot import (
    BandPoint,
    confidence_band_point,
    render_confidence_band,
)
from stability_shelf_life.model import (
    StabilityError,
    estimate_shelf_life,
    fit_kinetics,
)


def _noisy_first_order_fit():
    """Fit a realistic first-order batch with small assay noise."""
    k_true = 0.0045
    times = [0.0, 3.0, 6.0, 9.0, 12.0, 18.0, 24.0]
    noise = [0.0, 0.15, -0.10, 0.05, -0.20, 0.10, -0.05]
    values = [100.0 * math.exp(-k_true * t) + n for t, n in zip(times, noise)]
    return fit_kinetics(times, values, order=1)


def test_band_point_mean_follows_the_fitted_line():
    fit = _noisy_first_order_fit()
    point = confidence_band_point(fit, 12.0)

    assert isinstance(point, BandPoint)
    assert point.time == 12.0
    assert point.mean == pytest.approx(fit.initial * math.exp(-fit.rate * 12.0))
    assert point.lower < point.mean < point.upper


def test_band_lower_edge_crosses_the_limit_at_the_shelf_life_bound():
    fit = _noisy_first_order_fit()
    shelf = estimate_shelf_life(fit, limit=90.0)

    at_bound = confidence_band_point(
        fit, shelf.lower_bound_months, one_sided=True
    )
    at_point = confidence_band_point(fit, shelf.point_estimate_months)

    # The one-sided 95% lower confidence limit meets the criterion at the
    # reported shelf-life bound ...
    assert at_bound.lower == pytest.approx(90.0, rel=1e-6)
    # ... while the fitted mean meets it at the longer point estimate.
    assert at_point.mean == pytest.approx(90.0, rel=1e-6)
    # At the conservative bound the fitted line is still above the criterion.
    assert at_bound.mean > at_point.mean
    assert shelf.lower_bound_months < shelf.point_estimate_months


def test_two_sided_band_is_wider_than_the_one_sided_bound():
    fit = _noisy_first_order_fit()
    shelf = estimate_shelf_life(fit, limit=90.0)

    one_sided = confidence_band_point(fit, 12.0, one_sided=True)
    two_sided = confidence_band_point(fit, 12.0)

    assert one_sided.mean == two_sided.mean
    assert two_sided.lower < one_sided.lower
    assert two_sided.upper > one_sided.upper
    # The wider band therefore crosses the criterion later than the bound.
    assert confidence_band_point(fit, shelf.lower_bound_months).lower < 90.0


def test_render_contains_line_band_limit_and_shelf_life():
    fit = _noisy_first_order_fit()
    text = render_confidence_band(fit, 90.0)
    lines = text.splitlines()

    assert lines[0].startswith("first-order fit")
    assert "two-sided 95%" in lines[0]
    # Header, plot rows, axis, tick labels and legend.
    assert len(lines) == 17 + 4
    assert "'-'" in text
    assert "':'" in text
    assert "limit 90%" in text
    assert "X" in text  # shelf-life intersection marker
    assert "months" in text


def test_render_layout_is_rectangular():
    fit = _noisy_first_order_fit()
    text = render_confidence_band(fit, 90.0, months=24.0, width=41, height=9)
    lines = text.splitlines()
    plot_lines = lines[1:10]

    assert len(plot_lines) == 9
    assert len({len(line) for line in plot_lines}) == 1
    assert len(plot_lines[0]) == 11 + 41
    # The criterion is a horizontal '=' line and the fit a '-' line.
    assert any("=" in line for line in plot_lines)
    assert any("-" in line for line in plot_lines)


def test_render_accepts_one_sided_band_and_custom_range():
    fit = _noisy_first_order_fit()
    text = render_confidence_band(fit, 90.0, months=12.0, one_sided=True)

    assert "one-sided 95%" in text
    assert "limit 90%" in text


def test_render_handles_zero_order_model():
    times = [0.0, 3.0, 6.0, 9.0, 12.0]
    values = [100.0 - 0.35 * t for t in times]
    fit = fit_kinetics(times, values, order=0)
    text = render_confidence_band(fit, 90.0)

    assert text.startswith("zero-order fit")
    assert "limit 90%" in text


def test_render_handles_no_degradation():
    times = [0.0, 3.0, 6.0, 9.0]
    values = [100.0, 100.0, 100.0, 100.0]
    fit = fit_kinetics(times, values, order=1)
    assert estimate_shelf_life(fit, 90.0).stable is False

    text = render_confidence_band(fit, 90.0)

    # No shelf life to mark, but the criterion is still drawn.
    assert "X" not in text
    assert "limit 90%" in text


def test_confidence_band_point_rejects_negative_time():
    fit = _noisy_first_order_fit()
    with pytest.raises(StabilityError, match="non-negative"):
        confidence_band_point(fit, -1.0)


def test_render_validates_arguments():
    fit = _noisy_first_order_fit()

    with pytest.raises(StabilityError, match="criterion"):
        render_confidence_band(fit, 0.0)
    with pytest.raises(ValueError, match="width"):
        render_confidence_band(fit, 90.0, width=5)
    with pytest.raises(ValueError, match="height"):
        render_confidence_band(fit, 90.0, height=2)
    with pytest.raises(StabilityError, match="time range"):
        render_confidence_band(fit, 90.0, months=0.0)
