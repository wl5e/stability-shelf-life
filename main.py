"""Command-line interface for Arrhenius Stability Predictor."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Dict, Optional, Sequence

from arrhenius_stability.model import (
    ArrheniusFit,
    StabilityDataError,
    TemperatureRate,
    estimate_rate_constants,
    fit_arrhenius,
    load_data,
    predict_shelf_life,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Predict pharmaceutical shelf life from accelerated stability data "
                    "using the Arrhenius equation."
    )
    parser.add_argument(
        "--data",
        required=True,
        help="Path to CSV with columns temperature_c,time_months,potency",
    )
    parser.add_argument(
        "--storage-temp",
        type=float,
        default=25.0,
        help="Desired storage temperature in degrees C (default: 25.0)",
    )
    parser.add_argument(
        "--limit",
        type=float,
        default=90.0,
        help="Shelf-life potency limit (default: 90.0)",
    )
    parser.add_argument(
        "--initial-potency",
        type=float,
        default=100.0,
        help="Initial potency at t=0 (default: 100.0)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit results as JSON",
    )
    return parser


def _format_output(
    data_path: str,
    storage_temp: float,
    limit: float,
    initial_potency: float,
    rates: Dict[float, TemperatureRate],
    fit: ArrheniusFit,
    k_storage: float,
    shelf_life_months: float,
) -> str:
    lines = [
        "Arrhenius Stability Predictor",
        f"Data file: {data_path}",
        "",
        "Temperature  Rate (1/month)  R²",
    ]
    for temperature_c in sorted(rates):
        rate = rates[temperature_c]
        lines.append(
            f"{temperature_c:>11.1f}  {rate.rate:>14.6f}  {rate.r_squared:.4f}"
        )
    lines.extend([
        "",
        f"Arrhenius fit: ln(k) = {fit.intercept:.4f} + ({fit.slope:.4f}) * (1/T)",
        f"Activation energy: {fit.activation_energy_kj_mol:.2f} kJ/mol",
        f"Arrhenius R²: {fit.r_squared:.4f}",
        "",
        f"Storage temperature: {storage_temp:.2f} C",
        f"Predicted degradation rate: {k_storage:.6f} 1/month",
        (
            f"Predicted shelf life to {limit:.2f}%: "
            f"{shelf_life_months:.2f} months ({shelf_life_months / 12.0:.2f} years)"
        ),
    ])
    return "\n".join(lines)


def _json_result(
    data_path: str,
    storage_temp: float,
    limit: float,
    initial_potency: float,
    rates: Dict[float, TemperatureRate],
    fit: ArrheniusFit,
    k_storage: float,
    shelf_life_months: float,
) -> dict:
    return {
        "data_file": data_path,
        "storage_temperature_c": storage_temp,
        "limit": limit,
        "initial_potency": initial_potency,
        "rates": [
            {
                "temperature_c": temperature_c,
                "rate_1_per_month": rates[temperature_c].rate,
                "r_squared": rates[temperature_c].r_squared,
                "n_points": rates[temperature_c].n_points,
            }
            for temperature_c in sorted(rates)
        ],
        "arrhenius": {
            "slope": fit.slope,
            "intercept": fit.intercept,
            "r_squared": fit.r_squared,
            "activation_energy_kj_mol": fit.activation_energy_kj_mol,
            "pre_exponential_factor_1_per_month": fit.pre_exponential_factor,
        },
        "prediction": {
            "rate_1_per_month": k_storage,
            "shelf_life_months": shelf_life_months,
            "shelf_life_years": shelf_life_months / 12.0,
        },
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        records = load_data(args.data)
        rates = estimate_rate_constants(records)
        fit = fit_arrhenius(rates)
        k_storage, shelf_life_months = predict_shelf_life(
            fit,
            storage_temp_c=args.storage_temp,
            limit=args.limit,
            initial_potency=args.initial_potency,
        )
    except StabilityDataError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        result = _json_result(
            args.data,
            args.storage_temp,
            args.limit,
            args.initial_potency,
            rates,
            fit,
            k_storage,
            shelf_life_months,
        )
        print(json.dumps(result, indent=2))
    else:
        print(
            _format_output(
                args.data,
                args.storage_temp,
                args.limit,
                args.initial_potency,
                rates,
                fit,
                k_storage,
                shelf_life_months,
            )
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
