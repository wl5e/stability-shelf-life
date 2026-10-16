'''Pharmaceutical stability shelf-life modelling.

Provides ICH Q1E kinetics (zero- and first-order degradation), shelf-life
estimation with a one-sided 95% lower confidence bound, Arrhenius
extrapolation of accelerated-stability data, a bootstrap BCa lower bound
for robustness checks and an ASCII confidence-band plot.

Pure Python - no dependencies outside the standard library.
'''

from .ascii_plot import (
    BandPoint,
    confidence_band_point,
    render_confidence_band,
)
from .bootstrap import bootstrap_shelf_life_bca
from .io import (
    load_accelerated_data,
    load_stability_data,
)
from .model import (
    ArrheniusFit,
    KineticFit,
    OutlierDiagnostic,
    ResidualDiagnostics,
    ResidualNormality,
    RunsTest,
    ShelfLife,
    StabilityError,
    degradation_rates_by_temperature,
    estimate_shelf_life,
    fit_arrhenius,
    fit_kinetics,
    outlier_diagnostic,
    predict_arrhenius_rate,
    residual_diagnostics,
    residual_normality,
    runs_test,
)
from .pooling import (
    PooledBatchResult,
    pool_batches,
)

__version__ = '2.0.0'

__all__ = [
    'ArrheniusFit',
    'BandPoint',
    'KineticFit',
    'OutlierDiagnostic',
    'PooledBatchResult',
    'ResidualDiagnostics',
    'ResidualNormality',
    'RunsTest',
    'ShelfLife',
    'StabilityError',
    'bootstrap_shelf_life_bca',
    'confidence_band_point',
    'degradation_rates_by_temperature',
    'estimate_shelf_life',
    'fit_arrhenius',
    'fit_kinetics',
    'outlier_diagnostic',
    'pool_batches',
    'predict_arrhenius_rate',
    'render_confidence_band',
    'residual_diagnostics',
    'residual_normality',
    'runs_test',
    'load_accelerated_data',
    'load_stability_data',
    '__version__',
]
