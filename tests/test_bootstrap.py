'''Tests for bootstrap BCa shelf-life lower bounds.'''

import math

import pytest

from stability_shelf_life.bootstrap import bootstrap_shelf_life_bca
from stability_shelf_life.model import estimate_shelf_life, fit_kinetics


def test_bootstrap_bca_lower_bound_is_reproducible_and_conservative():
    k_true = 0.0045
    times = [0.0, 3.0, 6.0, 9.0, 12.0, 18.0, 24.0]
    noise = [0.0, 0.15, -0.10, 0.05, -0.20, 0.10, -0.05]
    values = [100.0 * math.exp(-k_true * t) + err
              for t, err in zip(times, noise)]
    fit = fit_kinetics(times, values, order=1)
    shelf = estimate_shelf_life(fit, limit=90.0)

    lower = bootstrap_shelf_life_bca(
        times,
        values,
        order=1,
        limit=90.0,
        n_bootstrap=200,
        random_seed=12345,
    )
    again = bootstrap_shelf_life_bca(
        times,
        values,
        order=1,
        limit=90.0,
        n_bootstrap=200,
        random_seed=12345,
    )

    assert lower == pytest.approx(again)
    assert 0.0 < lower < shelf.point_estimate_months


def test_bootstrap_bca_returns_inf_for_stable_data():
    times = [0.0, 3.0, 6.0]
    values = [100.0, 100.0, 100.0]
    assert bootstrap_shelf_life_bca(
        times,
        values,
        order=1,
        limit=90.0,
        n_bootstrap=50,
        random_seed=1,
    ) == math.inf
