"""Core calculations for Arrhenius stability prediction."""

from __future__ import annotations

import csv
import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

GAS_CONSTANT = 8.31446261815324  # J/(mol*K)


class StabilityDataError(Exception):
    """Raised when stability data are invalid or physically inconsistent."""


@dataclass(frozen=True)
class StabilityRecord:
    temperature_c: float
    time_months: float
    potency: float


@dataclass
class TemperatureRate:
    temperature_c: float
    rate: float
    r_squared: float
    n_points: int
    intercept: float


@dataclass
class ArrheniusFit:
    slope: float
    intercept: float
    r_squared: float
    activation_energy_kj_mol: float
    pre_exponential_factor: float
    temperature_c_values: List[float]


def linear_fit(xs: Sequence[float], ys: Sequence[float]) -> Tuple[float, float, float]:
    """Return slope, intercept, and R² for simple linear regression."""
    n = len(xs)
    if n != len(ys):
        raise ValueError("xs and ys must have the same length")
    if n < 2:
        raise StabilityDataError("At least two data points are required for regression")

    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    ss_xx = sum((x - mean_x) ** 2 for x in xs)
    ss_xy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    ss_yy = sum((y - mean_y) ** 2 for y in ys)

    if ss_xx == 0:
        raise StabilityDataError("Independent variable has no variance")
    if ss_yy == 0:
        return 0.0, mean_y, 1.0

    slope = ss_xy / ss_xx
    intercept = mean_y - slope * mean_x
    ss_res = sum((y - (intercept + slope * x)) ** 2 for x, y in zip(xs, ys))
    r_squared = 1.0 - (ss_res / ss_yy)
    return slope, intercept, r_squared


def load_data(path: str) -> List[StabilityRecord]:
    data_file = Path(path)
    if not data_file.exists():
        raise StabilityDataError(f"Data file not found: {path}")

    try:
        handle = data_file.open("r", encoding="utf-8", newline="")
    except OSError as exc:
        raise StabilityDataError(f"Could not open data file: {exc}") from exc

    with handle:
        reader = csv.DictReader(handle)
        required = {"temperature_c", "time_months", "potency"}
        if reader.fieldnames is None:
            raise StabilityDataError("CSV header is missing")
        missing = required - set(reader.fieldnames)
        if missing:
            raise StabilityDataError(f"Missing CSV column(s): {', '.join(sorted(missing))}")

        records: List[StabilityRecord] = []
        for row_num, row in enumerate(reader, start=2):
            try:
                temperature_c = float(row["temperature_c"])
                time_months = float(row["time_months"])
                potency = float(row["potency"])
            except (TypeError, ValueError) as exc:
                raise StabilityDataError(
                    f"Invalid numeric value in row {row_num}; expected "
                    "temperature_c, time_months, and potency"
                ) from exc

            if temperature_c <= -273.15:
                raise StabilityDataError(f"Temperature in row {row_num} is below absolute zero")
            if time_months < 0:
                raise StabilityDataError(f"Time in row {row_num} cannot be negative")
            if potency <= 0:
                raise StabilityDataError(f"Potency in row {row_num} must be positive")

            records.append(
                StabilityRecord(
                    temperature_c=temperature_c,
                    time_months=time_months,
                    potency=potency,
                )
            )

    if not records:
        raise StabilityDataError("No data rows found in CSV")
    return records


def estimate_rate_constants(records: Sequence[StabilityRecord]) -> Dict[float, TemperatureRate]:
    grouped: Dict[float, List[StabilityRecord]] = defaultdict(list)
    for record in records:
        grouped[record.temperature_c].append(record)

    if len(grouped) < 2:
        raise StabilityDataError("At least two storage temperatures are required")

    rates: Dict[float, TemperatureRate] = {}
    for temperature_c, points in grouped.items():
        points.sort(key=lambda row: row.time_months)
        if len(points) < 2:
            raise StabilityDataError(
                f"Temperature {temperature_c} C has fewer than 2 data points; "
                "need at least 2 for regression"
            )

        xs = [p.time_months for p in points]
        ys = [math.log(p.potency) for p in points]
        slope, intercept, r_squared = linear_fit(xs, ys)

        if slope >= 0:
            raise StabilityDataError(
                f"Temperature {temperature_c} C: no degradation detected "
                "(rate is non-positive); check data order"
            )

        rate = -slope
        rates[temperature_c] = TemperatureRate(
            temperature_c=temperature_c,
            rate=rate,
            r_squared=r_squared,
            n_points=len(points),
            intercept=intercept,
        )

    return rates


def fit_arrhenius(rates: Dict[float, TemperatureRate]) -> ArrheniusFit:
    if len(rates) < 2:
        raise StabilityDataError(
            "At least two temperatures with positive degradation rates are required"
        )

    temperatures = sorted(rates)
    xs: List[float] = []
    ys: List[float] = []

    for temperature_c in temperatures:
        rate_info = rates[temperature_c]
        if rate_info.rate <= 0:
            raise StabilityDataError(
                f"Rate for {temperature_c} C is not positive"
            )

        temp_kelvin = temperature_c + 273.15
        if temp_kelvin <= 0:
            raise StabilityDataError(
                f"Temperature {temperature_c} C is too low for Arrhenius model"
            )

        xs.append(1.0 / temp_kelvin)
        ys.append(math.log(rate_info.rate))

    slope, intercept, r_squared = linear_fit(xs, ys)

    if slope >= 0:
        raise StabilityDataError(
            "Arrhenius fit produced non-physical slope "
            "(higher temperature did not increase degradation); check data"
        )

    activation_energy_j = -slope * GAS_CONSTANT
    return ArrheniusFit(
        slope=slope,
        intercept=intercept,
        r_squared=r_squared,
        activation_energy_kj_mol=activation_energy_j / 1000.0,
        pre_exponential_factor=math.exp(intercept),
        temperature_c_values=temperatures,
    )


def predict_shelf_life(
    fit: ArrheniusFit,
    storage_temp_c: float,
    limit: float = 90.0,
    initial_potency: float = 100.0,
) -> Tuple[float, float]:
    """Predict degradation rate and shelf life at a desired storage temperature."""
    if storage_temp_c <= -273.15:
        raise StabilityDataError("Storage temperature is below absolute zero")
    if limit <= 0:
        raise StabilityDataError("Shelf-life limit must be positive")
    if initial_potency <= limit:
        raise StabilityDataError("Initial potency must be greater than the shelf-life limit")

    temp_kelvin = storage_temp_c + 273.15
    ln_rate = fit.intercept + fit.slope * (1.0 / temp_kelvin)
    rate = math.exp(ln_rate)

    if rate <= 0:
        raise StabilityDataError("Predicted degradation rate is not positive")

    shelf_life_months = math.log(initial_potency / limit) / rate
    return rate, shelf_life_months
