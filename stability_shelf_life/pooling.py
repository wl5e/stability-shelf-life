'''ICH Q1E batch-pooling (common-slope) utilities.

This module implements the ANCOVA F-test used by ICH Q1E to decide whether
several batches share a common degradation slope.  A failure to reject the
null hypothesis (by convention p > 0.25) is the first condition for pooling
batches before estimating a shelf life.
'''

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Sequence

from .model import StabilityError


@dataclass(frozen=True)
class PooledBatchResult:
    '''Outcome of the ICH Q1E ANCOVA common-slope test.'''

    order: int
    alpha: float
    can_pool: bool
    f_statistic: float
    df1: int
    df2: int
    p_value: float
    common_slope: float


def _betacf(a: float, b: float, x: float) -> float:
    '''Continued-fraction evaluation of the incomplete beta function.'''
    maxit = 200
    eps = 3.0e-12
    fpmin = 1.0e-300
    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < fpmin:
        d = fpmin
    d = 1.0 / d
    h = d
    for m in range(1, maxit + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            break
    return h


def _betai(a: float, b: float, x: float) -> float:
    '''Regularized incomplete beta function I_x(a, b).'''
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    factor = math.exp(
        math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
        + a * math.log(x) + b * math.log1p(-x)
    )
    if x < (a + 1.0) / (a + b + 2.0):
        return factor * _betacf(a, b, x) / a
    return 1.0 - factor * _betacf(b, a, 1.0 - x) / b


def _f_sf(f: float, df1: int, df2: int) -> float:
    '''Upper tail of the F distribution.'''
    if f <= 0.0:
        return 1.0
    if math.isinf(f):
        return 0.0
    num = df1 * f
    if math.isinf(num):
        return 0.0
    x = num / (num + df2)
    return 1.0 - _betai(df1 / 2.0, df2 / 2.0, x)


def pool_batches(
    times_by_batch: Dict[str, Sequence[float]],
    values_by_batch: Dict[str, Sequence[float]],
    order: int = 1,
    alpha: float = 0.25,
) -> PooledBatchResult:
    '''Test whether several batches share a common degradation slope.

    The test compares a full model with one regression line per batch with a
    reduced model that uses a common slope but keeps batch-specific
    intercepts.  The resulting F test is an ANCOVA for the batch-by-time
    interaction.  ICH Q1E accepts pooling of slopes when p > alpha.
    '''
    if order not in (0, 1):
        raise ValueError('order must be 0 or 1')
    if not 0.0 < alpha < 1.0:
        raise ValueError('alpha must be strictly between 0 and 1')

    batch_ids = sorted(times_by_batch)
    if len(batch_ids) < 2:
        raise StabilityError('at least two batches are required for pooling')
    if set(batch_ids) != set(values_by_batch):
        raise ValueError('times_by_batch and values_by_batch must have the same batch ids')

    total_n = 0
    total_sxx = 0.0
    total_sxy = 0.0
    total_syy = 0.0
    separate_sse = 0.0

    for batch_id in batch_ids:
        xs = list(times_by_batch[batch_id])
        raw_values = list(values_by_batch[batch_id])
        if len(xs) != len(raw_values):
            raise ValueError(f'batch {batch_id!r}: times and values differ in length')
        if len(xs) < 3:
            raise StabilityError(f'batch {batch_id!r}: at least 3 time points are required')
        if order == 1 and any(v <= 0 for v in raw_values):
            raise StabilityError('potency values must be positive')

        ys = raw_values if order == 0 else [math.log(v) for v in raw_values]
        n = len(xs)
        x_mean = sum(xs) / n
        y_mean = sum(ys) / n
        sxx = sum((x - x_mean) ** 2 for x in xs)
        if sxx == 0:
            raise StabilityError(f'batch {batch_id!r}: time points have zero variance')
        sxy = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
        syy = sum((y - y_mean) ** 2 for y in ys)

        total_n += n
        total_sxx += sxx
        total_sxy += sxy
        total_syy += syy
        separate_sse += max(0.0, syy - (sxy * sxy) / sxx)

    df1 = len(batch_ids) - 1
    df2 = total_n - 2 * len(batch_ids)
    if df2 <= 0:
        raise StabilityError('not enough observations for the slope test')

    common_slope = total_sxy / total_sxx
    common_sse = max(0.0, total_syy - (total_sxy * total_sxy) / total_sxx)
    if common_sse < separate_sse:
        common_sse = separate_sse

    sse_diff = common_sse - separate_sse
    if sse_diff <= 1e-12 * max(1.0, common_sse):
        f_stat = 0.0
        p_value = 1.0
    elif separate_sse == 0.0:
        f_stat = math.inf
        p_value = 0.0
    else:
        f_stat = (sse_diff / df1) / (separate_sse / df2)
        p_value = _f_sf(f_stat, df1, df2)

    can_pool = p_value > alpha
    return PooledBatchResult(
        order=order,
        alpha=alpha,
        can_pool=can_pool,
        f_statistic=f_stat,
        df1=df1,
        df2=df2,
        p_value=p_value,
        common_slope=common_slope,
    )


__all__ = ['PooledBatchResult', 'pool_batches']
