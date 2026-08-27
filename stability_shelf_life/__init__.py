"""Pharmaceutical stability shelf-life modelling.

Provides ICH Q1E kinetics (zero- and first-order degradation), shelf-life
estimation with a one-sided 95% lower confidence bound, and Arrhenius
extrapolation of accelerated-stability data.

Pure Python — no dependencies outside the standard library.
"""

from .model import (
    ArrheniusFit,
    KineticFit,
    ShelfLife,
    StabilityError,
    degradation_rates_by_temperature,
    estimate_shelf_life,
    fit_arrhenius,
    fit_kinetics,
    predict_arrhenius_rate,
)
from .io import (
    load_accelerated_data,
    load_stability_data,
)

__version__ = "2.0.0"

__all__ = [
    "ArrheniusFit",
    "KineticFit",
    "ShelfLife",
    "StabilityError",
    "degradation_rates_by_temperature",
    "estimate_shelf_life",
    "fit_arrhenius",
    "fit_kinetics",
    "predict_arrhenius_rate",
    "load_accelerated_data",
    "load_stability_data",
    "__version__",
]
