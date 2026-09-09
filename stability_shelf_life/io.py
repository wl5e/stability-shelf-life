"""CSV input handling and validation for stability data."""

from __future__ import annotations

import csv
import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from .model import StabilityError


@dataclass(frozen=True)
class StabilityBatch:
    batch_id: str
    times: List[float]
    values: List[float]


@dataclass(frozen=True)
class AcceleratedData:
    times: List[float]
    temperatures: List[float]
    values: List[float]


def _open_csv(path: str):
    data_file = Path(path)
    if not data_file.exists():
        raise StabilityError(f"data file not found: {path}")
    try:
        handle = data_file.open("r", encoding="utf-8-sig", newline="")
    except OSError as exc:
        raise StabilityError(f"could not open data file: {exc}") from exc
    return handle


def _require_columns(fieldnames, required, path):
    if fieldnames is None:
        raise StabilityError(f"{path}: CSV header is missing")
    missing = set(required) - set(fieldnames)
    if missing:
        raise StabilityError(f"{path}: missing column(s): {', '.join(sorted(missing))}")


def load_stability_data(path: str) -> Dict[str, StabilityBatch]:
    """Load single-condition stability data (ICH Q1E layout).

    Expected columns: ``time_months``, ``assay_percent``, ``batch_id``.
    Returns a mapping of batch id to time/value series.
    """
    with _open_csv(path) as handle:
        reader = csv.DictReader(handle)
        _require_columns(reader.fieldnames, {"time_months", "assay_percent", "batch_id"}, path)

        data: Dict[str, List[List[float]]] = defaultdict(lambda: [[], []])
        for row_num, row in enumerate(reader, start=2):
            try:
                t = float(row["time_months"])
                v = float(row["assay_percent"])
            except (TypeError, ValueError) as exc:
                raise StabilityError(
                    f"{path} row {row_num}: non-numeric time or assay value"
                ) from exc

            batch_id = (row["batch_id"] or "").strip()
            if not batch_id:
                raise StabilityError(f"{path} row {row_num}: empty batch_id")
            if not (math.isfinite(t) and math.isfinite(v)):
                raise StabilityError(f"{path} row {row_num}: non-finite time or assay value")
            if t < 0:
                raise StabilityError(f"{path} row {row_num}: negative time")
            if v <= 0:
                raise StabilityError(f"{path} row {row_num}: assay value must be positive")

            data[batch_id][0].append(t)
            data[batch_id][1].append(v)

    if not data:
        raise StabilityError(f"{path}: no data rows found")

    result: Dict[str, StabilityBatch] = {}
    for batch_id, (times, values) in data.items():
        if len(set(times)) != len(times):
            raise StabilityError(f"batch {batch_id}: duplicate time points")
        result[batch_id] = StabilityBatch(
            batch_id=batch_id, times=times, values=values
        )
    return result


def load_accelerated_data(path: str) -> AcceleratedData:
    """Load multi-temperature accelerated data (Arrhenius layout).

    Expected columns: ``temperature_c``, ``time_months``, ``potency``.
    """
    with _open_csv(path) as handle:
        reader = csv.DictReader(handle)
        _require_columns(
            reader.fieldnames, {"temperature_c", "time_months", "potency"}, path
        )

        times: List[float] = []
        temperatures: List[float] = []
        values: List[float] = []
        for row_num, row in enumerate(reader, start=2):
            try:
                temp = float(row["temperature_c"])
                t = float(row["time_months"])
                v = float(row["potency"])
            except (TypeError, ValueError) as exc:
                raise StabilityError(
                    f"{path} row {row_num}: non-numeric value"
                ) from exc

            if not math.isfinite(temp):
                raise StabilityError(f"{path} row {row_num}: non-finite temperature")
            if temp <= -273.15:
                raise StabilityError(f"{path} row {row_num}: temperature below absolute zero")
            if not (math.isfinite(t) and math.isfinite(v)):
                raise StabilityError(f"{path} row {row_num}: non-finite time or assay value")
            if t < 0:
                raise StabilityError(f"{path} row {row_num}: negative time")
            if v <= 0:
                raise StabilityError(f"{path} row {row_num}: potency must be positive")

            times.append(t)
            temperatures.append(temp)
            values.append(v)

    if not times:
        raise StabilityError(f"{path}: no data rows found")
    return AcceleratedData(times=times, temperatures=temperatures, values=values)
