'''Tests for ICH Q1E batch pooling.'''

import math

import pytest

from stability_shelf_life.model import StabilityError
from stability_shelf_life.pooling import pool_batches


def _exp_series(c0, k, times):
    return [c0 * math.exp(-k * t) for t in times]


def test_pool_batches_accepts_common_slope():
    times = [0.0, 3.0, 6.0, 9.0, 12.0]
    result = pool_batches(
        {'A': times, 'B': times},
        {'A': _exp_series(100.0, 0.01, times),
         'B': _exp_series(96.0, 0.01, times)},
        order=1,
    )
    assert result.can_pool is True
    assert result.p_value == pytest.approx(1.0)
    assert result.common_slope == pytest.approx(-0.01)


def test_pool_batches_rejects_different_slopes():
    times = [0.0, 3.0, 6.0, 9.0, 12.0]
    result = pool_batches(
        {'A': times, 'B': times},
        {'A': _exp_series(100.0, 0.005, times),
         'B': _exp_series(100.0, 0.020, times)},
        order=1,
    )
    assert result.can_pool is False
    assert result.p_value < 1e-10


def test_pool_batches_zero_order_common_slope():
    times = [0.0, 3.0, 6.0, 9.0, 12.0]
    result = pool_batches(
        {'A': times, 'B': times},
        {'A': [100.0 - 0.5 * t for t in times],
         'B': [92.0 - 0.5 * t for t in times]},
        order=0,
    )
    assert result.can_pool is True
    assert result.p_value == pytest.approx(1.0)
    assert result.common_slope == pytest.approx(-0.5)


def test_pool_batches_requires_two_batches():
    with pytest.raises(StabilityError, match='at least two'):
        pool_batches({'A': [0.0, 3.0, 6.0]}, {'A': [100.0, 99.0, 98.0]})
