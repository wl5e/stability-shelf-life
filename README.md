# Arrhenius Stability Predictor

Predict pharmaceutical shelf life from accelerated stability data using the Arrhenius equation.

## Features

- Parses CSV stability data with columns `temperature_c`, `time_months`, and `potency`
- Fits first-order degradation rate constants at each storage temperature
- Fits the Arrhenius equation by linear regression of ln(k) vs 1/T
- Reports activation energy (kJ/mol) and pre-exponential factor
- Predicts degradation rate and shelf life at a chosen storage temperature
- Human-readable and JSON output modes
- Includes automated unit tests

## Install

```bash
git clone https://github.com/collinsamatu/arrhenius-stability-predictor.git
cd arrhenius-stability-predictor
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

```bash
python main.py --data stability_data.csv --storage-temp 25 --limit 90 --initial-potency 100
```

JSON output:

```bash
python main.py --data stability_data.csv --storage-temp 25 --json
```

## CSV format

The input CSV must contain a header row with these exact columns:

| column        | description                        |
|---------------|------------------------------------|
| temperature_c | storage temperature in degrees C    |
| time_months   | timepoint in months                |
| potency       | observed potency or label claim     |

Example:

```csv
temperature_c,time_months,potency
40,0,100
40,1,98.9
40,2,97.8
40,3,96.7
50,0,100
50,1,97.6
50,2,95.2
50,3,92.9
60,0,100
60,1,94.8
60,2,89.9
60,3,85.2
```

## How it works

1. For each storage temperature, the tool fits `ln(potency) = ln(P0) - k*t`.
2. The resulting `k` values are fit to `ln(k) = ln(A) - Ea/(R*T)`.
3. The fitted Arrhenius line is used to predict `k` at the desired storage temperature.
4. Shelf life is calculated as `ln(initial_potency / limit) / k`.
