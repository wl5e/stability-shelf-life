"""Statistical core of pharmaceutical stability modelling.

Six capabilities are provided:

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

5. **Outlier diagnostics** — leverage and externally studentized residuals
   that flag observations exerting undue influence on a fitted model.

6. **Residual diagnostics** — a D'Agostino-Pearson normality test and a
   Wald-Wolfowitz runs test that flag a kinetic model whose residuals
   contradict the assumptions behind the confidence bounds.

The module uses only the Python standard library.  The one-sided 95%
   t-critical values are tabulated for 1..30 degrees of freedom and
   approximated by the standard-normal quantile beyond that.
"""

from __future__ import annotations

import math
import warnings
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

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

# Two-sided 95% t critical values (97.5% quantile), indexed by df (1..30).
_T_CRITICAL_TABLE_TWO_SIDED: Dict[int, float] = {
    1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571,
    6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228,
    11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145, 15: 2.131,
    16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093, 20: 2.086,
    21: 2.080, 22: 2.074, 23: 2.069, 24: 2.064, 25: 2.060,
    26: 2.056, 27: 2.052, 28: 2.048, 29: 2.045, 30: 2.042,
}
_NORMAL_QUANTILE_975 = 1.959963984540054  # Phi^-1(0.975)


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
class RateConfidenceInterval:
    """Confidence bounds for a fitted degradation rate.

    ``lower`` and ``upper`` delimit the two-sided 95% confidence interval of
    the degradation rate, while ``one_sided_lower`` is the one-sided 95%
    lower confidence bound that ICH Q1E relies on.  The interval is symmetric
    on the regressed scale (potency for zero-order, ln potency for
    first-order), so its half-width is ``t * slope_std_error``.
    """

    rate: float
    lower: float
    upper: float
    one_sided_lower: float
    std_error: float
    df: int


@dataclass(frozen=True)
class InformationCriterion:
    """Akaike/Bayesian information criteria for a fitted kinetic model.

    ``sse`` is the residual sum of squares of the model's predictions in the
    original potency units (not the transformed scale), so the zero- and
    first-order models can be compared on equal footing.  ``k`` is the number
    of fitted parameters (initial potency and rate) and is 2 for both models.
    ``aic`` and ``bic`` are ``-inf`` when the fit is numerically perfect.
    """

    order: int
    n: int
    k: int
    sse: float
    aic: float
    bic: float


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


def t_critical_two_sided(df: int) -> float:
    """Two-sided 95% critical value of Student's t for ``df`` degrees of freedom."""
    if df < 1:
        raise ValueError("degrees of freedom must be >= 1")
    return _T_CRITICAL_TABLE_TWO_SIDED.get(df, _NORMAL_QUANTILE_975)


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


def rate_confidence_interval(fit: KineticFit) -> RateConfidenceInterval:
    """Two-sided 95% CI and one-sided 95% lower bound for a degradation rate.

    The degradation rate is the negated regression slope (``rate = -slope``),
    so its standard error equals the slope standard error.  The two-sided
    interval is ``rate +/- t_two_sided(df) * se`` and the ICH Q1E one-sided
    bound is ``rate - t_one_sided(df) * se``; as ``t_two_sided > t_one_sided``
    the one-sided bound always lies inside the two-sided interval.
    """
    reg = fit.regression
    df = reg.n - 2
    rate = -reg.slope
    std_error = reg.slope_std_error
    half_width = t_critical_two_sided(df) * std_error
    one_sided_half_width = t_critical(df) * std_error
    return RateConfidenceInterval(
        rate=rate,
        lower=rate - half_width,
        upper=rate + half_width,
        one_sided_lower=rate - one_sided_half_width,
        std_error=std_error,
        df=df,
    )


def information_criterion(
    fit: KineticFit, times: Sequence[float], values: Sequence[float]
) -> InformationCriterion:
    """Compute AIC and BIC for a kinetic fit on the original potency scale.

    Zero-order and first-order models are fitted on different scales (potency
    and ln potency), so their transformed residuals are not directly
    comparable.  Both criteria are therefore derived from the residual sum of
    squares of the *potency-scale* predictions, which puts the two models on
    equal footing and lets them be ranked directly.

    With ``n`` observations and ``k = 2`` parameters:

        AIC = n * ln(SSE / n) + 2 * k
        BIC = n * ln(SSE / n) + k * ln(n)

    A numerically perfect fit (``SSE`` at or below floating-point noise
    relative to the data) sends both criteria to ``-inf``.
    """
    n = len(times)
    if n != len(values):
        raise ValueError("times and values must have the same length")
    if n != fit.regression.n:
        raise ValueError("times/values length does not match the fit")

    if fit.order == 0:
        predicted = [fit.initial - fit.rate * t for t in times]
    else:
        predicted = [fit.initial * math.exp(-fit.rate * t) for t in times]
    sse = sum((v - p) ** 2 for v, p in zip(values, predicted))

    k = 2
    scale = sum(v * v for v in values)
    if sse <= 0.0 or (scale > 0.0 and sse <= 1e-12 * scale):
        aic = -math.inf
        bic = -math.inf
    else:
        log_term = n * math.log(sse / n)
        aic = log_term + 2 * k
        bic = log_term + k * math.log(n)

    return InformationCriterion(
        order=fit.order, n=n, k=k, sse=sse, aic=aic, bic=bic
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


@dataclass(frozen=True)
class OutlierDiagnostic:
    """Per-observation regression diagnostics for outlier detection.

    ``studentized_residuals`` holds the externally studentized ("deleted")
    residuals and ``leverage`` the diagonal of the hat matrix.  An
    observation is flagged when its studentized residual exceeds
    ``threshold`` in absolute value or its leverage exceeds
    ``leverage_cutoff``.
    """

    residuals: List[float]
    leverage: List[float]
    studentized_residuals: List[float]
    is_outlier: List[bool]
    threshold: float
    leverage_cutoff: float


def outlier_diagnostic(
    regression: RegressionResult,
    xs: Sequence[float],
    ys: Sequence[float],
    threshold: float = 2.5,
) -> OutlierDiagnostic:
    """Flag high-leverage and studentized-residual outliers in a fit.

    ``xs`` and ``ys`` must be the data used to produce ``regression``.
    Leverage is the diagonal of the hat matrix,
    ``h_i = 1/n + (x_i - x_mean)^2 / sxx``.  The externally studentized
    (deleted) residual is ``e_i / (s_i * sqrt(1 - h_i))``, where ``s_i`` is
    the residual standard error of the fit with observation ``i`` removed.

    A point is flagged when ``abs(studentized residual) > threshold`` or
    when its leverage exceeds the conventional ``2p/n`` cut-off for ``p = 2``
    regression parameters.
    """
    n = len(xs)
    if n != len(ys):
        raise ValueError("xs and ys must have the same length")
    if n != regression.n:
        raise ValueError("xs/ys length does not match the regression")
    if n < 4:
        raise StabilityError(
            "at least 4 points are required for outlier diagnostics"
        )

    residuals = [
        y - (regression.intercept + regression.slope * x)
        for x, y in zip(xs, ys)
    ]
    leverage = [
        1.0 / n + (x - regression.x_mean) ** 2 / regression.sxx for x in xs
    ]
    sse = sum(r * r for r in residuals)
    deleted_df = n - 3  # n observations minus 2 parameters minus the deleted point

    studentized: List[float] = []
    for r, h in zip(residuals, leverage):
        if h >= 1.0:
            studentized.append(0.0 if r == 0.0 else math.copysign(math.inf, r))
            continue
        sse_deleted = sse - r * r / (1.0 - h)
        if sse_deleted <= 0.0:
            # Removing the point leaves a perfect fit: it is an extreme outlier.
            studentized.append(0.0 if r == 0.0 else math.copysign(math.inf, r))
            continue
        s_deleted = math.sqrt(sse_deleted / deleted_df)
        studentized.append(r / (s_deleted * math.sqrt(1.0 - h)))

    leverage_cutoff = 2.0 * 2.0 / n
    is_outlier = [
        abs(sr) > threshold or h > leverage_cutoff
        for sr, h in zip(studentized, leverage)
    ]

    return OutlierDiagnostic(
        residuals=residuals,
        leverage=leverage,
        studentized_residuals=studentized,
        is_outlier=is_outlier,
        threshold=threshold,
        leverage_cutoff=leverage_cutoff,
    )


@dataclass(frozen=True)
class ResidualNormality:
    """D'Agostino-Pearson omnibus test for the normality of residuals.

    ``skewness`` is the third sample moment and ``excess_kurtosis`` the
    fourth (relative to 3); both are zero for normally distributed errors.
    ``skewness_z`` and ``kurtosis_z`` standardize them, and ``statistic`` is
    their sum of squares, which follows a chi-square distribution with two
    degrees of freedom under the null hypothesis of normality.  ``is_normal``
    is False when the residuals depart significantly from normality, which
    indicates that the kinetic model misses structure in the data.
    """

    n: int
    skewness: float
    excess_kurtosis: float
    skewness_z: float
    kurtosis_z: float
    statistic: float
    p_value: float
    is_normal: bool


@dataclass(frozen=True)
class RunsTest:
    """Wald-Wolfowitz runs test on the signs of a residual series.

    A model that fits well leaves residuals whose signs alternate
    unpredictably.  Structure the model cannot explain (curvature, a lag
    phase, drift) instead clusters residuals of equal sign, so ``runs``
    falls short of ``expected_runs`` and ``is_random`` becomes False.
    """

    positive: int
    negative: int
    runs: int
    expected_runs: float
    z_statistic: float
    p_value: float
    is_random: bool


@dataclass(frozen=True)
class ResidualDiagnostics:
    """Residual normality and runs-test diagnostics for a kinetic fit.

    ``normality`` is None when the residual series is too short for the
    D'Agostino-Pearson test (fewer than 8 points), in which case only the
    runs test can flag the model.  ``poor_fit`` is True when either test
    rejects its null hypothesis, and ``reasons`` lists the failures (it is
    empty for a satisfactory fit).
    """

    normality: Optional[ResidualNormality]
    runs: RunsTest
    poor_fit: bool
    reasons: List[str]


def _dagostino_skewness_z(skewness: float, n: int) -> float:
    """Standardized skewness of the D'Agostino-Pearson statistic."""
    y = skewness * math.sqrt(((n + 1.0) * (n + 3.0)) / (6.0 * (n - 2.0)))
    beta2 = (
        3.0 * (n * n + 27.0 * n - 70.0) * (n + 1.0) * (n + 3.0)
        / ((n - 2.0) * (n + 5.0) * (n + 7.0) * (n + 9.0))
    )
    w2 = -1.0 + math.sqrt(2.0 * (beta2 - 1.0))
    delta = 1.0 / math.sqrt(0.5 * math.log(w2))
    alpha = math.sqrt(2.0 / (w2 - 1.0))
    return delta * math.asinh(y / alpha)


def _dagostino_kurtosis_z(kurtosis: float, n: int) -> float:
    """Standardized kurtosis of the D'Agostino-Pearson statistic."""
    expected = 3.0 * (n - 1.0) / (n + 1.0)
    variance = (
        24.0 * n * (n - 2.0) * (n - 3.0)
        / ((n + 1.0) ** 2 * (n + 3.0) * (n + 5.0))
    )
    x = (kurtosis - expected) / math.sqrt(variance)
    sqrt_beta1 = (
        6.0 * (n * n - 5.0 * n + 2.0) / ((n + 7.0) * (n + 9.0))
        * math.sqrt(6.0 * (n + 3.0) * (n + 5.0) / (n * (n - 2.0) * (n - 3.0)))
    )
    a = 6.0 + (8.0 / sqrt_beta1) * (
        2.0 / sqrt_beta1 + math.sqrt(1.0 + 4.0 / sqrt_beta1 ** 2)
    )
    denominator = 1.0 + x * math.sqrt(2.0 / (a - 4.0))
    ratio = (1.0 - 2.0 / a) / denominator
    cube_root = math.copysign(abs(ratio) ** (1.0 / 3.0), ratio)
    return (1.0 - 2.0 / (9.0 * a) - cube_root) / math.sqrt(2.0 / (9.0 * a))


def residual_normality(
    residuals: Sequence[float], alpha: float = 0.05
) -> ResidualNormality:
    """Test a residual series for normality (D'Agostino-Pearson omnibus test).

    At least 8 residuals are required because the standardized skewness
    statistic is unreliable for shorter series; fewer raises
    :class:`StabilityError`.  ``is_normal`` is False when the residuals
    depart significantly from a normal distribution, which signals that the
    kinetic model does not explain the data it was fitted to.
    """
    n = len(residuals)
    if n < 8:
        raise StabilityError(
            "at least 8 residuals are required for the normality test"
        )

    mean = sum(residuals) / n
    m2 = sum((r - mean) ** 2 for r in residuals) / n
    if m2 <= 0.0:
        raise StabilityError("residuals have zero variance")
    m3 = sum((r - mean) ** 3 for r in residuals) / n
    m4 = sum((r - mean) ** 4 for r in residuals) / n

    skewness = m3 / m2 ** 1.5
    kurtosis = m4 / (m2 * m2)
    skewness_z = _dagostino_skewness_z(skewness, n)
    kurtosis_z = _dagostino_kurtosis_z(kurtosis, n)
    statistic = skewness_z ** 2 + kurtosis_z ** 2
    p_value = math.exp(-0.5 * statistic)  # upper tail of chi-square(2)

    return ResidualNormality(
        n=n,
        skewness=skewness,
        excess_kurtosis=kurtosis - 3.0,
        skewness_z=skewness_z,
        kurtosis_z=kurtosis_z,
        statistic=statistic,
        p_value=p_value,
        is_normal=p_value >= alpha,
    )


def runs_test(residuals: Sequence[float], alpha: float = 0.05) -> RunsTest:
    """Wald-Wolfowitz runs test on the signs of a residual series.

    Residuals equal to zero carry no sign and are dropped.  Under the null
    hypothesis of a random sequence the number of runs is approximately
    normal with mean ``2*n1*n2/(n1+n2) + 1`` and the variance given by Wald
    and Wolfowitz (1940); the statistic carries the conventional continuity
    correction of 0.5.  ``is_random`` is False when the observed number of
    runs is significantly above or below the expectation (two-sided), i.e.
    when the residuals show a systematic pattern.
    """
    signs = [1 if r > 0.0 else -1 for r in residuals if r != 0.0]
    if not signs:
        raise StabilityError("runs test needs at least one non-zero residual")

    n1 = signs.count(1)
    n2 = signs.count(-1)
    if n1 == 0 or n2 == 0:
        raise StabilityError(
            "runs test needs both positive and negative residuals"
        )

    total = n1 + n2
    runs = 1 + sum(1 for a, b in zip(signs, signs[1:]) if a != b)
    expected = 2.0 * n1 * n2 / total + 1.0
    variance = (
        2.0 * n1 * n2 * (2.0 * n1 * n2 - total)
        / (total * total * (total - 1.0))
    )

    if variance <= 0.0:
        return RunsTest(
            positive=n1, negative=n2, runs=runs, expected_runs=expected,
            z_statistic=0.0, p_value=1.0, is_random=True,
        )

    std_error = math.sqrt(variance)
    if runs > expected:
        z_statistic = (runs - expected - 0.5) / std_error
    elif runs < expected:
        z_statistic = (runs - expected + 0.5) / std_error
    else:
        z_statistic = 0.0
    p_value = math.erfc(abs(z_statistic) / math.sqrt(2.0))

    return RunsTest(
        positive=n1,
        negative=n2,
        runs=runs,
        expected_runs=expected,
        z_statistic=z_statistic,
        p_value=p_value,
        is_random=p_value >= alpha,
    )


def residual_diagnostics(
    fit: KineticFit,
    times: Sequence[float],
    values: Sequence[float],
    alpha: float = 0.05,
) -> ResidualDiagnostics:
    """Test the residuals of a kinetic fit for normality and randomness.

    ``times`` and ``values`` must be the observations behind ``fit``.  The
    residuals are taken on the scale of the regression (potency for the
    zero-order model, ln potency for the first-order model) because that is
    the scale on which the ICH Q1E confidence bounds assume independent,
    normally distributed errors.

    ``poor_fit`` is True when either the D'Agostino-Pearson normality test
    or the Wald-Wolfowitz runs test rejects its null hypothesis at ``alpha``.
    The normality test needs at least 8 residuals and is skipped for shorter
    series (``normality`` is None); the runs test always applies but has
    little power below roughly eight points.
    """
    if len(times) != len(values):
        raise ValueError("times and values must have the same length")
    if len(times) != fit.regression.n:
        raise ValueError("times/values length does not match the fit")

    if fit.order == 0:
        ys = list(values)
    else:
        if any(v <= 0.0 for v in values):
            raise StabilityError("potency values must be positive")
        ys = [math.log(v) for v in values]

    regression = fit.regression
    residuals = [
        y - (regression.intercept + regression.slope * t)
        for t, y in zip(times, ys)
    ]

    normality = (
        residual_normality(residuals, alpha) if len(residuals) >= 8 else None
    )
    runs = runs_test(residuals, alpha)

    reasons: List[str] = []
    if normality is not None and not normality.is_normal:
        reasons.append(
            "residuals are not normally distributed "
            f"(D'Agostino-Pearson p = {normality.p_value:.4f})"
        )
    if not runs.is_random:
        reasons.append(
            "residuals are not randomly ordered "
            f"(runs test p = {runs.p_value:.4f})"
        )

    return ResidualDiagnostics(
        normality=normality,
        runs=runs,
        poor_fit=bool(reasons),
        reasons=reasons,
    )
