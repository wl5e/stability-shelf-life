"""ASCII rendering of a fitted stability curve with its confidence band.

The renderer is deliberately dependency-free: the plot is plain text, so it
can be pasted into a terminal session, an e-mail or a GMP report without a
plotting stack.  Three things are drawn on a potency-versus-time canvas:

* the fitted mean response - the line the shelf life is read from,
* its 95% confidence band - the uncertainty of that line, and
* the acceptance criterion, drawn as a horizontal line.

Where the lower edge of the band meets the acceptance criterion the ICH Q1E
shelf-life lower bound is marked with ``X``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional

from .model import (
    KineticFit,
    ShelfLife,
    StabilityError,
    estimate_shelf_life,
    t_critical,
    t_critical_two_sided,
)

__all__ = [
    "BandPoint",
    "band_point_series",
    "confidence_band_point",
    "render_confidence_band",
]

_MAX_EXPONENT = 700.0  # exp() overflow guard for very wide first-order bands


@dataclass(frozen=True)
class BandPoint:
    """Fitted mean response and its 95% confidence band at one time point.

    All three values are on the original potency scale (percent of label
    claim); ``lower`` and ``upper`` bracket ``mean``.
    """

    time: float
    mean: float
    lower: float
    upper: float


def _potency(value: float) -> float:
    """Exponentiate a ln-potency, guarding against overflow."""
    return math.exp(min(value, _MAX_EXPONENT))


def confidence_band_point(
    fit: KineticFit, time: float, one_sided: bool = False
) -> BandPoint:
    """Evaluate the fitted line and its 95% confidence band at ``time``.

    On the regression scale the mean response is ``a + b*t`` with standard
    error ``s * sqrt(1/n + (t - x_mean)^2 / sxx)``; the band edges are that
    mean plus and minus ``t_crit * se``.  For the first-order model the
    result is transformed back to percent potency.

    ``one_sided`` selects the critical value: the one-sided 95% value is the
    ICH Q1E choice, and makes ``lower`` the confidence limit whose
    intersection with the acceptance criterion defines the shelf life.  The
    default (two-sided) value gives the conventional, wider 95% band.
    """
    if time < 0.0:
        raise StabilityError("time must be non-negative")

    reg = fit.regression
    critical = (
        t_critical(reg.n - 2) if one_sided else t_critical_two_sided(reg.n - 2)
    )
    mean_scaled = reg.intercept + reg.slope * time
    std_error = reg.residual_std_error * math.sqrt(
        1.0 / reg.n + (time - reg.x_mean) ** 2 / reg.sxx
    )
    half_width = critical * std_error
    lower_scaled = mean_scaled - half_width
    upper_scaled = mean_scaled + half_width

    if fit.order == 0:
        return BandPoint(time, mean_scaled, lower_scaled, upper_scaled)
    return BandPoint(
        time,
        _potency(mean_scaled),
        _potency(lower_scaled),
        _potency(upper_scaled),
    )


def _default_months(shelf: ShelfLife) -> float:
    """Time span used when the caller does not supply one."""
    if shelf.stable and math.isfinite(shelf.point_estimate_months):
        return max(1.0, math.ceil(shelf.point_estimate_months * 1.1))
    return 12.0


def band_point_series(
    fit: KineticFit,
    limit: float,
    count: int = 10,
    months: Optional[float] = None,
    one_sided: bool = True,
) -> List[BandPoint]:
    """Sample the fitted line and its confidence band at even time steps.

    The series spans ``months`` (or 10% beyond the point-estimate shelf life
    when omitted) in ``count`` evenly spaced points, starting at t = 0.  It is
    the data behind :func:`render_confidence_band`, exposed so callers such as
    the JSON report can serialise the band without re-deriving the statistics.
    """
    if count < 2:
        raise ValueError("count must be at least 2")
    shelf = estimate_shelf_life(fit, limit)
    span = _default_months(shelf) if months is None else months
    if span <= 0.0:
        raise StabilityError("time range must be positive")
    times = [span * index / (count - 1) for index in range(count)]
    return [confidence_band_point(fit, time, one_sided) for time in times]


def _tick_labels(span: float, width: int, count: int = 5) -> str:
    """Space ``count`` numeric tick labels evenly across the x-axis."""
    row = [" "] * width
    for index in range(count):
        value = span * index / (count - 1)
        text = f"{value:g}"
        centre = int(round(value / span * (width - 1)))
        start = max(0, min(width - len(text), centre - len(text) // 2))
        row[start:start + len(text)] = list(text)
    return "".join(row)


def render_confidence_band(
    fit: KineticFit,
    limit: float,
    months: Optional[float] = None,
    width: int = 61,
    height: int = 17,
    one_sided: bool = False,
) -> str:
    """Render the fitted line, its 95% confidence band and the limit as ASCII.

    ``fit`` is the kinetic model of one batch and ``limit`` the acceptance
    criterion in percent.  The x-axis runs from 0 to ``months``; when
    ``months`` is omitted the plot spans the fitted degradation, i.e. 10%
    beyond the point-estimate shelf life (or 12 months when no degradation
    is detected).  ``width`` and ``height`` give the size of the plot area
    in characters.

    The returned string has ``height + 4`` lines: a header, the plot rows,
    the axis, the tick labels and a legend.  ``'-'`` marks the fitted line,
    ``':'`` the edges of the 95% confidence band, ``'.'`` its interior,
    ``'='`` the acceptance criterion and ``'X'`` the shelf-life lower bound.
    """
    if limit <= 0.0:
        raise StabilityError("acceptance criterion must be positive")
    if width < 12:
        raise ValueError("width must be at least 12 characters")
    if height < 4:
        raise ValueError("height must be at least 4 rows")

    shelf = estimate_shelf_life(fit, limit)
    span = _default_months(shelf) if months is None else months
    if span <= 0.0:
        raise StabilityError("time range must be positive")

    times = [span * index / (width - 1) for index in range(width)]
    points = [confidence_band_point(fit, t, one_sided) for t in times]

    y_min = min([limit] + [point.lower for point in points])
    y_max = max([limit] + [point.upper for point in points])
    if y_max - y_min < 1e-9:
        y_min -= 1.0
        y_max += 1.0

    def row_of(value: float) -> int:
        scaled = (y_max - value) / (y_max - y_min) * (height - 1)
        return max(0, min(height - 1, int(round(scaled))))

    limit_row = row_of(limit)
    grid: List[List[str]] = [[" "] * width for _ in range(height)]
    for column in range(width):
        grid[limit_row][column] = "="

    for column, point in enumerate(points):
        top = row_of(point.upper)
        bottom = row_of(point.lower)
        for row in range(top, bottom + 1):
            grid[row][column] = "."
        grid[top][column] = ":"
        grid[bottom][column] = ":"
        grid[row_of(point.mean)][column] = "-"

    marked = (
        shelf.stable
        and math.isfinite(shelf.lower_bound_months)
        and shelf.lower_bound_months <= span
    )
    if marked:
        column = int(round(shelf.lower_bound_months / span * (width - 1)))
        grid[limit_row][column] = "X"

    band_label = "one-sided 95%" if one_sided else "two-sided 95%"
    model_label = "zero-order" if fit.order == 0 else "first-order"

    lines = [f"{model_label} fit with its {band_label} confidence band"]
    for row in range(height):
        value = y_max - (y_max - y_min) * row / (height - 1)
        lines.append(f"{value:8.2f} |" + "".join(grid[row]) + "|")
    lines.append(" " * 9 + "+" + "-" * width + "+")
    lines.append(" " * 10 + _tick_labels(span, width) + " months")

    legend = (
        f"'-' fitted line   ':' {band_label} confidence band   "
        f"'=' limit {limit:g}%"
    )
    if marked:
        legend += (
            f"   'X' shelf life {shelf.lower_bound_months:.1f} months "
            "(95% lower bound)"
        )
    lines.append(legend)
    return "\n".join(lines)
