# stability-shelf-life

Pharmaceutical shelf-life modelling from stability data — kinetics, ICH Q1E
confidence bounds, and Arrhenius extrapolation. Pure Python, no dependencies
beyond the standard library.

## Why this exists

Before a drug product can be released, a manufacturer must demonstrate how
long it keeps its labelled potency under real storage conditions. That answer
comes out of a stability study: batches are stored at controlled conditions
and assayed over time, and the data are used to set an expiry date.

The two classical problems are:

1. **Shelf life from long-term data** — fit a degradation model to each batch
   and find the time at which the potency is *predicted with confidence* to
   remain above the specification limit. ICH Q1E requires reporting not a
   point estimate but a **one-sided 95% lower confidence bound**.

2. **Extrapolation from accelerated data** — you cannot wait three years, so
   samples are stored at elevated temperatures and the degradation rate at
   room temperature is estimated with the **Arrhenius equation**.

This tool implements both, with the statistics done properly rather than
approximated.

## Features

- **Zero-order and first-order kinetics**, with automatic best-model selection
  by R² (both models are always reported).
- **ICH Q1E shelf-life estimate**: point estimate *and* the one-sided 95%
  lower confidence bound on the mean response, solved exactly (a quadratic in
  time — not a numerical approximation).
- **Per-batch analysis** of multi-batch studies.
- **Arrhenius extrapolation** of accelerated-stability data, reporting
  activation energy and predicted long-term rate and shelf life.
- Human-readable and JSON output for GMP audit-trail needs.
- Defensive input validation (non-numeric values, duplicate time points,
  negative time, non-positive potency, non-physical fits).
- Standard library only; the one-sided t-critical values are tabulated for
  1–30 degrees of freedom and use the normal quantile beyond that.

## Installation

Requires Python 3.9+.

```bash
git clone https://github.com/wl5e/stability-shelf-life.git
cd stability-shelf-life
pip install .
```

This installs the `stability-shelf-life` command:

```bash
stability-shelf-life q1e --input examples/stability_data.csv --limit 90
```

For development, install the test extra and run pytest:

```bash
pip install -e ".[test]"
pytest
```

## Usage

### ICH Q1E shelf life (long-term / real-time data)

Input CSV columns: `time_months`, `assay_percent`, `batch_id`.

```bash
python main.py q1e --input examples/stability_data.csv --limit 90
```

```
ICH Q1E stability analysis
Specification limit: 90%

Batch A01 (7 time points)
   zero-order: k = 0.42964 %/month, C0 = 99.92%, R² = 0.9983
  first-order: k = 0.00453 /month, C0 = 99.99%, R² = 0.9993
  -> best model: first-order, shelf life = 23.24 months (95% lower bound 22.89 months)

Batch B02 (7 time points)
   zero-order: k = 0.47535 %/month, C0 = 99.70%, R² = 0.9996
  first-order: k = 0.00506 /month, C0 = 99.80%, R² = 1.0000
  -> best model: first-order, shelf life = 20.43 months (95% lower bound 20.37 months)
```

`--json` emits the same result as structured data for an audit trail.

### Arrhenius extrapolation (accelerated data)

Input CSV columns: `temperature_c`, `time_months`, `potency`.

```bash
python main.py arrhenius --input examples/accelerated_data.csv --storage-temp 25
```

```
Arrhenius stability extrapolation
Temperature  Rate (1/month)  R²
       40.0        0.011186  1.0000
       50.0        0.024584  1.0000
       60.0        0.053358  1.0000

Activation energy: 67.75 kJ/mol
Arrhenius R²: 0.9998

Storage temperature: 25.00 C
Predicted rate: 0.003004 /month
Predicted shelf life to 90%: 35.08 months (2.92 years)
```

## API

The public surface is re-exported from `stability_shelf_life` (see
`stability_shelf_life.__all__`). All functions are pure Python and use only
the standard library.

### Input loaders

- `load_stability_data(path: str) -> Dict[str, StabilityBatch]` — read the
  long-term stability CSV (`time_months`, `assay_percent`, `batch_id`) and
  return per-batch time/value series.
- `load_accelerated_data(path: str) -> AcceleratedData` — read the accelerated
  CSV (`temperature_c`, `time_months`, `potency`).

### Kinetics and shelf life

- `fit_kinetics(times, values, order: int) -> KineticFit` — least-squares fit
  for order `0` (zero-order) or `1` (first-order).
- `estimate_shelf_life(fit: KineticFit, limit: float) -> ShelfLife` — ICH Q1E
  point estimate and one-sided 95% lower confidence bound at `limit` percent.
- `bootstrap_shelf_life_bca(times, values, order, limit, ...) -> float` — BCa
  bootstrap one-sided 95% lower bound for the shelf life.
- `confidence_band_point(...) -> BandPoint` — evaluate the fitted confidence
  band at one time point.
- `render_confidence_band(...) -> str` — render an ASCII confidence-band plot.
- `outlier_diagnostic(...) -> OutlierDiagnostic` — per-point residual/outlier
  diagnostic.
- `residual_diagnostics(...) -> ResidualDiagnostics` — residual summary and
  normality/runs diagnostics.
- `residual_normality(...) -> ResidualNormality` — residual normality test
  result.
- `runs_test(...) -> RunsTest` — runs test for residual randomness.
- `pool_batches(...) -> PooledBatchResult` — pool compatible batches for a
  common slope estimate.

### Arrhenius extrapolation

- `degradation_rates_by_temperature(times, temperatures, values) ->`
  `Dict[float, KineticFit]` — fit first-order rates at each accelerated
  temperature.
- `fit_arrhenius(temperatures, rates) -> ArrheniusFit` — fit
  `ln(k) = ln(A) - Ea/(R T)`.
- `predict_arrhenius_rate(fit: ArrheniusFit, storage_temp) -> float` — predict
  the rate at a long-term storage temperature.

### Dataclasses and exceptions

- `StabilityBatch` — per-batch id, times, and assay values returned by
  `load_stability_data`.
- `AcceleratedData` — accelerated times, temperatures, and potency values.
- `KineticFit` — fitted kinetic order, rate, initial potency, R², and
  coefficient standard errors.
- `ShelfLife` — point estimate, lower bound, and stability flag for one limit.
- `ArrheniusFit` — activation energy, pre-exponential factor, and R².
- `BandPoint` — time, mean, and lower/upper confidence-band values.
- `OutlierDiagnostic` — residual, leverage, and outlier flag for one point.
- `ResidualDiagnostics` — residual summary and associated statistics.
- `ResidualNormality` — normality test statistic and p-value.
- `RunsTest` — runs statistic and p-value.
- `PooledBatchResult` — pooled slope/statistics for multiple compatible
  batches.
- `StabilityError` — exception raised for malformed input or non-physical
  fits.

`__version__` exposes the package version string.

## How the statistics work

For first-order kinetics, `ln(potency)` is regressed against time; for
zero-order, potency is regressed directly. Shelf life is the time at which
the fitted mean response reaches the acceptance criterion.

ICH Q1E requires a confidence statement, so the one-sided 95% lower
confidence limit of the mean response is constructed:

```
LCL(t) = a + b·t − t(0.05, n−2) · s · √(1/n + (t − x̄)² / Sxx)
```

Setting `LCL(t)` equal to the (log-transformed) limit gives a quadratic in
`t`; the smaller positive root is the reported shelf-life lower bound. The
result is therefore always *more conservative* than the naive point
estimate, as a regulated expiry date should be.

## Worked example

Run the ICH Q1E analysis on the bundled two-batch study:

```bash
python main.py q1e --input examples/stability_data.csv --limit 90
```

Batch **A01** fits best as **first-order** (k = 0.004532 /month, R² = 0.9993),
giving a shelf life of **23.24 months** with a one-sided 95% lower confidence
bound of **22.89 months**. Batch **B02** degrades slightly faster
(k = 0.005059 /month) and reaches the 90% limit at **20.43 months**
(lower bound **20.37 months**). Because ICH Q1E requires the *lower bound*,
the reportable shelf life is the shorter of the two bounds.

Accelerated data extrapolate to long-term storage with the Arrhenius model:

```bash
python main.py arrhenius --input examples/accelerated_data.csv --storage-temp 25
```

## Tests

```bash
PYTHONPATH=. pytest -v
```

Coverage includes synthetic data with known rate constants (the fitted rate
must be recovered to within 1%), the confidence-bound behaviour (lower bound
must fall below the point estimate), and the rejection of non-physical
Arrhenius fits and malformed inputs.

## License

MIT © Collins Amatu Gorgerat
