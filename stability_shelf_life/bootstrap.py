'''Bootstrap confidence bounds for shelf-life estimates.'''

from __future__ import annotations

import math
import random
from statistics import NormalDist
from typing import Optional, Sequence

from .model import StabilityError, estimate_shelf_life, fit_kinetics


def bootstrap_shelf_life_bca(
    times: Sequence[float],
    values: Sequence[float],
    order: int,
    limit: float,
    n_bootstrap: int = 1000,
    level: float = 0.95,
    random_seed: Optional[int] = None,
) -> float:
    '''Return a one-sided bootstrap BCa lower bound for shelf life.

    Residual resampling is performed on the model regression scale.  Each
    bootstrap sample is fitted with the same kinetic order and converted
    to a shelf-life point estimate.  The return value is the lower endpoint
    of a BCa interval with one-sided confidence ``level``, intended as a
    robustness check against the analytic ICH-style bound.
    '''
    if len(times) != len(values):
        raise ValueError('times and values must have the same length')
    if n_bootstrap < 2:
        raise ValueError('n_bootstrap must be at least 2')
    if not 0.0 < level < 1.0:
        raise ValueError('level must be between 0 and 1')

    original_fit = fit_kinetics(times, values, order)
    original_shelf = estimate_shelf_life(original_fit, limit)
    if not original_shelf.stable:
        return math.inf

    theta_hat = original_shelf.point_estimate_months
    intercept = original_fit.regression.intercept
    slope = original_fit.regression.slope
    if order == 0:
        transformed = list(values)
    else:
        transformed = [math.log(v) for v in values]
    fitted = [intercept + slope * t for t in times]
    residuals = [y - yhat for y, yhat in zip(transformed, fitted)]

    def fit_point_estimate(ts: Sequence[float], vs: Sequence[float]) -> float:
        try:
            sample_fit = fit_kinetics(ts, vs, order)
            sample_shelf = estimate_shelf_life(sample_fit, limit)
            return sample_shelf.point_estimate_months
        except (ArithmeticError, StabilityError, ValueError):
            return math.inf

    # BCa acceleration via the jackknife.  If any leave-one-out fit has no
    # finite shelf life, fall back to a bias-corrected interval (accel zero).
    accel = 0.0
    if len(times) >= 4:
        leave_one_out = []
        usable = True
        for i in range(len(times)):
            ts = times[:i] + times[i + 1:]
            vs = values[:i] + values[i + 1:]
            point = fit_point_estimate(ts, vs)
            if not math.isfinite(point):
                usable = False
                break
            leave_one_out.append(point)
        if usable and leave_one_out:
            theta_dot = sum(leave_one_out) / len(leave_one_out)
            centered = [theta_dot - point for point in leave_one_out]
            denom = 6.0 * (sum(c * c for c in centered) ** 1.5)
            if denom > 0.0:
                accel = sum(c * c * c for c in centered) / denom

    rng = random.Random(random_seed)
    bootstrap_stats = []
    for _ in range(n_bootstrap):
        sampled_errors = [rng.choice(residuals) for _ in times]
        transformed_star = [f + e for f, e in zip(fitted, sampled_errors)]
        if order == 1:
            try:
                values_star = [math.exp(y) for y in transformed_star]
            except OverflowError:
                bootstrap_stats.append(math.inf)
                continue
        else:
            values_star = transformed_star
        bootstrap_stats.append(fit_point_estimate(times, values_star))

    alpha = 1.0 - level
    normal = NormalDist()
    z_alpha = normal.inv_cdf(alpha)
    below = sum(1 for stat in bootstrap_stats if stat < theta_hat)
    ties = sum(1 for stat in bootstrap_stats if stat == theta_hat)
    below_prop = (below + 0.5 * ties) / n_bootstrap
    below_prop = min(max(below_prop, 1.0 / (n_bootstrap + 1)), 1.0 - 1.0 / (n_bootstrap + 1))
    z0 = normal.inv_cdf(below_prop)
    z_sum = z0 + z_alpha
    if 1.0 - accel * z_sum <= 0.0:
        accel = 0.0
    adjusted_alpha = normal.cdf(z0 + z_sum / (1.0 - accel * z_sum))
    adjusted_alpha = min(max(adjusted_alpha, 1.0 / (n_bootstrap + 1)), 1.0 - 1.0 / (n_bootstrap + 1))
    sorted_stats = sorted(bootstrap_stats)
    index = int(math.ceil(adjusted_alpha * n_bootstrap)) - 1
    index = max(0, min(n_bootstrap - 1, index))
    return sorted_stats[index]
