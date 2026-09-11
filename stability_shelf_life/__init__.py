'''Pharmaceutical stability shelf-life modelling.

Provides ICH Q1E kinetics (zero- and first-order degradation), shelf-life
estimation with a one-sided 95% lower confidence bound, Arrhenius
extrapolation of accelerated-stability data, and a bootstrap BCa lower
bound for robustness checks.

Pure Python - no dependencies outside the standard library.
'''

from .bootstrap import bootstrap_shelf_life_bca
from .io import (
    load_accelerated_data,
    load_stability_data,
)
from .model import (
    ArrheniusFit,
    KineticFit,
    OutlierDiagnostic,
    ShelfLife,
    StabilityError,
    degradation_rates_by_temperature,
    estimate_shelf_life,
    fit_arrhenius,
    fit_kinetics,
    outlier_diagnostic,
    predict_arrhenius_rate,
)
from .pooling import (
    PooledBatchResult,
    pool_batches,
)

__version__ = '2.0.0'

__all__ = [
    'ArrheniusFit',
    'KineticFit',
    'OutlierDiagnostic',
    'PooledBatchResult',
    'ShelfLife',
    'StabilityError',
    'bootstrap_shelf_life_bca',
    'degradation_rates_by_temperature',
    'estimate_shelf_life',
    'fit_arrhenius',
    'fit_kinetics',
    'outlier_diagnostic',
    'pool_batches',
    'predict_arrhenius_rate',
    'load_accelerated_data',
    'load_stability_data',
    '__version__',
]
