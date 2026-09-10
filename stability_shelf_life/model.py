"""Statistical core of pharmaceutical stability modelling.

Four capabilities are provided:

1. **Kinetic fitting** — zero-order (linear in potency) and first-order
   (linear in ln potency) degradation, following ICH Q1E.

2. **Shelf-life estimation** — time to the acceptance criterion, with a
   one-sided 95% lower confidence bound on the mean response, as ICH Q1E
   requires.  The lower bound is the intersection of the lower confidence
   limit of the fitted line with the acceptance criterion, solved exactly
   (a quadratic in time).

3. **Batch comparison** — an extra-sum-of-squares F test for equality of
   the degradation slopes of several batches, which ICH Q1E requires
   before the data of different batches may be pooled.

4. **Arrhenius extrapolation** — fits ``ln(k) = ln(A) - Ea/(R*T)`` to
   degradation rates measured at several elevated temperatures, then
   predicts the rate (and shelf life) at a chosen long-term storage
   temperature.

The module uses only the Python standard library.  The one-sided 95%
t-critical values are tabulated for 1..30 degrees of freedom and
approximated by the standard-normal quantile beyond that.
"""

from __future__ import annotations

import math
import warnings
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Sequence

GAS_CONSTANT = 8.31446261815324  # J/(mol*K)

# One-sided 95% t critical values, indexed by degrees of freedom (1..30).
_T_CRITICAL_TABLE: Dict[int, float] = {
    1: 6.314, 2: 2.920, 3: 2.353, 4: 2.132, 5: 2.015,
    6: 1.943, 7: 1.895, 8: 1.860, 9: 1.833, 10: 1.812,
    11: 1.796, 12: 1.782, 13: 1.771, 14: 1.761, 15: 1.753,
    16: 1.746, 17: 1.740, 18: 1.734, 19: 1.729, 20: 1.725,
    21: 1.721, 22: 1.717, 23: 1.714, 24: 1.711, 25: 1.708,
    26: 1.706, 27: 1.703, 28: 1.701, 29: 1.699, 30: 1.697,
}
_NORMAL_QUANTILE_95 = 1.6448536269514722  # Phi^-1(0.95)


class StabilityError(Exception):
    """Raised when stability data are invalid or physically inconsistent."""


@dataclass(frozen=True)
class RegressionResult:
    """Simple linear regression ``y = intercept + slope * x`` with diagnostics."""

    slope: float
    intercept: float
    r_squared: float
    residual_std_error: float
    n: int
    x_mean: float
    sxx: float
    slope_std_error: float
    intercept_std_error: float


@dataclass(frozen=True)
class KineticFit:
    """A single degradation model fitted to one batch / condition."""

    order: int
    regression: RegressionResult
    rate: float          # positive degradation rate (1/month)
    initial: float       # estimated potency at t = 0 (original scale)
    r_squared: float


@dataclass(frozen=True)
class ShelfLife:
    """Shelf-life estimate with the ICH Q1E one-sided 95% lower bound."""

    point_estimate_months: float
    lower_bound_months: float
    limit: float
    stable: bool          # False when no degradation is detected


@dataclass(frozen=True)
class SlopeDifference:
    """F test for equality of degradation slopes across several batches."""

    order: int
    slopes: List[float]      # per-batch regression slopes (model scale)
    rates: List[float]       # per-batch degradation rates (positive)
    f_statistic: float
    df_between: int
    df_within: int
    p_value: float
    slopes_differ: bool      # True when p_value < alpha


@dataclass(frozen=True)
class ArrheniusFit:
    """Arrhenius ``ln(k) = ln(A) - Ea/(R*T)`` fitted to several temperatures."""

    slope: float
    intercept: float
    r_squared: float
    activation_energy_kj_mol: float
    pre_exponential_factor: float
    temperatures_c: List[float]


def t_critical(df: int) -> float:
    """One-sided 95% critical value of Student's t for ``df`` degrees of freedom."""
    if df < 1:
        raise ValueError("degrees of freedom must be >= 1")
    return _T_CRITICAL_TABLE.get(df, _NORMAL_QUANTILE_95)


def _beta_continued_fraction(a: float, b: float, x: float) -> float:
    """Continued-fraction expansion of the incomplete beta (Lentz's method)."""
    max_iterations = 200
    epsilon = 3.0e-14
    tiny = 1.0e-300

    qab = a + b
    qap = a + 1.0
    qam = a - 1.0

    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < tiny:
        d = tiny
    d = 1.0 / d
    h = d

    for m in range(1, max_iterations + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        h *= d * c

        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < epsilon:
            break
    return h


def regularized_incomplete_beta(a: float, b: float, x: float) -> float:
    """Regularized incomplete beta function ``I_x(a, b)``."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    log_beta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    front = math.exp(log_beta + a * math.log(x) + b * math.log1p(-x))
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _beta_continued_fraction(a, b, x) / a
    return 1.0 - front * _beta_continued_fraction(b, a, 1.0 - x) / b


def f_test_p_value(f_statistic: float, df_between: int, df_within: int) -> float:
    """Upper-tail probability ``P(F > f_statistic)`` of an F distribution."""
    if df_between < 1 or df_within < 1:
        raise ValueError("degrees of freedom must be >= 1")
    if f_statistic <= 0.0:
        return 1.0
    if math.isinf(f_statistic):
        return 0.0
    x = df_within / (df_within + df_between * f_statistic)
    return regularized_incomplete_beta(0.5 * df_within, 0.5 * df_between, x)


def linear_fit(xs: Sequence[float], ys: Sequence[float]) -> RegressionResult:
    """Fit ``y = intercept + slope * x`` by ordinary least squares."""
    n = len(xs)
    if n != len(ys):
        raise ValueError("xs and ys must have the same length")
    if n < 3:
        raise StabilityError("at least 3 time points are required for regression")

    x_mean = sum(xs) / n
    y_mean = sum(ys) / n
    sxx = sum((x - x_mean) ** 2 for x in xs)
    sxy = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
    syy = sum((y - y_mean) ** 2 for y in ys)

    if sxx == 0:
        raise StabilityError("time points have zero variance")

    slope = sxy / sxx
    intercept = y_mean - slope * x_mean

    if syy == 0:
        return RegressionResult(
            slope=0.0, intercept=y_mean, r_squared=1.0, residual_std_error=0.0,
            n=n, x_mean=x_mean, sxx=sxx, slope_std_error=0.0,
            intercept_std_error=0.0,
        )

    ss_res = sum(
        (y - (intercept + slope * x)) ** 2 for x, y in zip(xs, ys)
    )
    r_squared = 1.0 - (ss_res / syy)
    residual_std_error = math.sqrt(ss_res / (n - 2))
    slope_std_error = residual_std_error / math.sqrt(sxx)
    intercept_std_error = residual_std_error * math.sqrt(1.0 / n + x_mean ** 2 / sxx)

    return RegressionResult(
        slope=slope,
        intercept=intercept,
        r_squared=r_squared,
        residual_std_error=residual_std_error,
        n=n,
        x_mean=x_mean,
        sxx=sxx,
        slope_std_error=slope_std_error,
        intercept_std_error=intercept_std_error,
    )


def fit_kinetics(times: Sequence[float], values: Sequence[float], order: int) -> KineticFit:
    """Fit a zero-order (``order=0``) or first-order (``order=1``) model.

    Zero-order  : ``potency = C0 - k*t``         (regress potency vs time)
    First-order : ``potency = C0 * exp(-k*t)``   (regress ln potency vs time)
    """
    if order not in (0, 1):
        raise ValueError("order must be 0 or 1")
    if len(times) < 3:
        raise StabilityError("at least 3 time points are required")
    if any(v <= 0 for v in values):
        raise StabilityError("potency values must be positive")

    ys = values if order == 0 else [math.log(v) for v in values]
    regression = linear_fit(times, ys)

    rate = -regression.slope
    initial = regression.intercept if order == 0 else math.exp(regression.intercept)

    if rate <= 0:
        # No degradation detected — model exists but shelf life is not bounded.
        return KineticFit(
            order=order, regression=regression, rate=0.0,
            initial=initial, r_squared=regression.r_squared,
        )

    return KineticFit(
        order=order, regression=regression, rate=rate,
        initial=initial, r_squared=regression.r_squared,
    )


def estimate_shelf_life(fit: KineticFit, limit: float) -> ShelfLife:
    """Estimate shelf life with a one-sided 95% lower confidence bound.

    The lower bound is the time at which the lower 95% confidence limit of
    the fitted mean response reaches ``limit``.  On the regressed scale the
    mean response is ``a + b*t`` and its lower confidence limit is
    ``a + b*t - t_crit*s*sqrt(1/n + (t - x_mean)^2 / sxx)``.  Equating this
    to the (possibly log-transformed) limit yields a quadratic in ``t`` whose
    smaller positive root is the shelf life.
    """
    reg = fit.regression
    if fit.rate <= 0:
        return ShelfLife(
            point_estimate_months=math.inf,
            lower_bound_months=math.inf,
            limit=limit,
            stable=False,
        )

    a = reg.intercept
    b = reg.slope  # negative for degradation
    target = limit if fit.order == 0 else math.log(limit)
    if a <= target:
        raise StabilityError("the acceptance criterion is not above the t=0 estimate")

    a_shift = a - target          # > 0
    tc = t_critical(reg.n - 2)
    s2 = reg.residual_std_error ** 2
    sxx = reg.sxx
    xm = reg.x_mean
    n = reg.n

    # Quadratic coefficients from squaring the equality (both sides positive).
    c2 = b * b - tc * tc * s2 / sxx
    c1 = 2.0 * a_shift * b + 2.0 * tc * tc * s2 * xm / sxx
    c0 = a_shift * a_shift - tc * tc * s2 / n - tc * tc * s2 * xm * xm / sxx

    disc = c1 * c1 - 4.0 * c2 * c0
    if disc < 0:
        # Fall back to the point estimate if the bound is numerically ill-defined.
        lower = (target - a) / b
    else:
        root_disc = math.sqrt(disc)
        r1 = (-c1 - root_disc) / (2.0 * c2)
        r2 = (-c1 + root_disc) / (2.0 * c2)
        positive_roots = [r for r in (r1, r2) if r > 0]
        lower = min(positive_roots) if positive_roots else math.inf

    point = (target - a) / b  # == a_shift / -b > 0
    return ShelfLife(
        point_estimate_months=point,
        lower_bound_months=lower,
        limit=limit,
        stable=True,
    )


def slope_difference_test(
    fits: Sequence[KineticFit], alpha: float = 0.05
) -> SlopeDifference:
    """Test whether the degradation slopes of several batches are equal.

    An extra-sum-of-squares F test compares a model with one slope per batch
    against a model with a single common slope.  ICH Q1E only allows the
    data of different batches to be pooled when their slopes do not differ
    significantly.

    ``fits`` must contain at least two :class:`KineticFit` objects fitted
    with the same kinetic order.  The statistic has ``k - 1`` and ``N - 2k``
    degrees of freedom for ``k`` batches and ``N`` observations in total.
    """
    k = len(fits)
    if k < 2:
        raise StabilityError("at least two batches are required to compare slopes")
    if len({fit.order for fit in fits}) != 1:
        raise StabilityError("all batches must be fitted with the same kinetic model")

    total_n = sum(fit.regression.n for fit in fits)
    df_between = k - 1
    df_within = total_n - 2 * k
    if df_within < 1:
        raise StabilityError("not enough observations to test slope differences")

    ss_separate = sum(
        fit.regression.residual_std_error ** 2 * (fit.regression.n - 2)
        for fit in fits
    )
    sxx_total = sum(fit.regression.sxx for fit in fits)
    common_slope = (
        sum(fit.regression.sxx * fit.regression.slope for fit in fits) / sxx_total
    )
    ss_common = ss_separate + sum(
        fit.regression.sxx * (fit.regression.slope - common_slope) ** 2
        for fit in fits
    )
    ss_difference = max(ss_common - ss_separate, 0.0)

    slopes = [fit.regression.slope for fit in fits]

    if ss_separate <= 0.0:
        # Perfect within-batch fits: the slopes either coincide or they do not.
        differ = ss_difference > 0.0
        f_statistic = math.inf if differ else 0.0
        p_value = 0.0 if differ else 1.0
    else:
        f_statistic = (ss_difference / df_between) / (ss_separate / df_within)
        p_value = f_test_p_value(f_statistic, df_between, df_within)
        differ = p_value < alpha

    return SlopeDifference(
        order=fits[0].order,
        slopes=slopes,
        rates=[-slope for slope in slopes],
        f_statistic=f_statistic,
        df_between=df_between,
        df_within=df_within,
        p_value=p_value,
        slopes_differ=differ,
    )


def fit_arrhenius(
    temperatures_c: Sequence[float], rates: Sequence[float]
) -> ArrheniusFit:
    """Fit ``ln(k) = ln(A) - Ea/(R*T)`` to degradation rates.

    ``temperatures_c`` and ``rates`` must be aligned, with at least two
    temperatures and strictly positive rates.
    """
    if len(temperatures_c) < 2:
        raise StabilityError("at least two temperatures are required")
    if len(temperatures_c) != len(rates):
        raise ValueError("temperatures_c and rates must have the same length")
    if any(r <= 0 for r in rates):
        raise StabilityError("degradation rates must be positive")

    xs = [1.0 / (t + 273.15) for t in temperatures_c]
    ys = [math.log(r) for r in rates]
    regression = linear_fit(xs, ys)

    if regression.slope >= 0:
        raise StabilityError(
            "Arrhenius fit is non-physical (rate did not increase with temperature)"
        )

    activation_energy_j = -regression.slope * GAS_CONSTANT
    return ArrheniusFit(
        slope=regression.slope,
        intercept=regression.intercept,
        r_squared=regression.r_squared,
        activation_energy_kj_mol=activation_energy_j / 1000.0,
        pre_exponential_factor=math.exp(regression.intercept),
        temperatures_c=sorted(temperatures_c),
    )


def predict_arrhenius_rate(fit: ArrheniusFit, storage_temp_c: float) -> float:
    """Predict the first-order degradation rate at a storage temperature.

    If ``storage_temp_c`` falls outside the temperature range used to fit
    ``fit``, a :class:`UserWarning` is emitted because the prediction is an
    extrapolation rather than an interpolation.
    """
    if storage_temp_c <= -273.15:
        raise StabilityError("storage temperature is below absolute zero")
    if fit.temperatures_c:
        measured_min_c = min(fit.temperatures_c)
        measured_max_c = max(fit.temperatures_c)
        if storage_temp_c < measured_min_c or storage_temp_c > measured_max_c:
            warnings.warn(
                f"storage temperature {storage_temp_c:.2f} C is outside the "
                f"measured temperature range [{measured_min_c:.2f}, "
                f"{measured_max_c:.2f}] C; Arrhenius prediction is an extrapolation",
                UserWarning,
                stacklevel=2,
            )
    ln_rate = fit.intercept + fit.slope * (1.0 / (storage_temp_c + 273.15))
    rate = math.exp(ln_rate)
    if rate <= 0:
        raise StabilityError("predicted degradation rate is not positive")
    return rate


def degradation_rates_by_temperature(
    times: Sequence[float], temperatures: Sequence[float], values: Sequence[float]
) -> Dict[float, KineticFit]:
    """Fit a first-order rate constant at each temperature in an accelerated study.

    ``times``, ``temperatures`` and ``values`` are aligned rows (long form).
    """
    grouped: Dict[float, List[float]] = defaultdict(list)
    for t, temp, v in zip(times, temperatures, values):
        grouped[temp].append((t, v))

    fits: Dict[float, KineticFit] = {}
    for temp, points in grouped.items():
        points.sort(key=lambda p: p[0])
        ts = [p[0] for p in points]
        vs = [p[1] for p in points]
        if len(points) < 3:
            raise StabilityError(
                f"temperature {temp} C has fewer than 3 time points"
            )
        fit = fit_kinetics(ts, vs, order=1)
        if fit.rate <= 0:
            raise StabilityError(
                f"temperature {temp} C shows no degradation"
            )
        fits[temp] = fit
    return fits
