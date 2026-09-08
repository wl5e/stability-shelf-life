"""Command-line interface for pharmaceutical stability analysis.

Two subcommands are provided:

    q1e       — ICH Q1E shelf-life estimation (zero/first-order kinetics,
                one-sided 95% lower confidence bound, per batch).
    arrhenius — Arrhenius extrapolation of accelerated-stability data to a
                chosen long-term storage temperature.

Examples:
    python main.py q1e --input examples/stability_data.csv --limit 90
    python main.py arrhenius --input examples/accelerated_data.csv --storage-temp 25
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from typing import Optional, Sequence

from stability_shelf_life import (
    StabilityError,
    degradation_rates_by_temperature,
    estimate_shelf_life,
    fit_arrhenius,
    fit_kinetics,
    load_accelerated_data,
    load_stability_data,
    predict_arrhenius_rate,
)


def _write_json_report(report, output_path: str) -> None:
    """Persist the JSON report to *output_path* (GMP audit-trail artifact)."""
    try:
        with open(output_path, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)
    except OSError as exc:
        raise StabilityError(
            f"could not write report file {output_path}: {exc}"
        ) from exc


def _select_model(fits):
    """Choose the best model by R²; prefer first-order on a tie."""
    zero, first = fits[0], fits[1]
    if first.r_squared >= zero.r_squared:
        return first, "first-order"
    return zero, "zero-order"


def _run_q1e(args) -> int:
    batches = load_stability_data(args.input)
    limit = args.limit

    report = {"limit": limit, "batches": []}
    for batch_id in sorted(batches):
        batch = batches[batch_id]
        fits = [fit_kinetics(batch.times, batch.values, o) for o in (0, 1)]
        best, best_name = _select_model(fits)
        shelf = estimate_shelf_life(best, limit)

        entry = {
            "batch_id": batch_id,
            "n_points": len(batch.times),
            "best_model": best_name,
            "best_rate": round(best.rate, 6),
            "best_rate_unit": "percent/month" if best.order == 0 else "1/month",
            "best_r_squared": round(best.r_squared, 5),
            "shelf_life_months": None,
            "shelf_life_lower_95_months": None,
            "models": [],
        }
        if shelf.stable:
            entry["shelf_life_months"] = round(shelf.point_estimate_months, 2)
            entry["shelf_life_lower_95_months"] = round(shelf.lower_bound_months, 2)

        for fit in fits:
            name = "zero-order" if fit.order == 0 else "first-order"
            entry["models"].append(
                {
                    "model": name,
                    "rate": round(fit.rate, 6),
                    "rate_unit": "percent/month" if fit.order == 0 else "1/month",
                    "initial_potency": round(fit.initial, 3),
                    "r_squared": round(fit.r_squared, 5),
                }
            )
        report["batches"].append(entry)

    if args.out:
        _write_json_report(report, args.out)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        _print_q1e_report(report)
    return 0


def _print_q1e_report(report) -> None:
    print("ICH Q1E stability analysis")
    print(f"Specification limit: {report['limit']}%")
    print()
    for entry in report["batches"]:
        print(f"Batch {entry['batch_id']} ({entry['n_points']} time points)")
        for m in entry["models"]:
            unit = " %/month" if m["model"] == "zero-order" else " /month"
            print(
                f"  {m['model']:>11}: k = {m['rate']:.5f}{unit}, "
                f"C0 = {m['initial_potency']:.2f}%, R² = {m['r_squared']:.4f}"
            )
        if entry["shelf_life_months"] is None:
            print("  -> no degradation detected (shelf life not estimable)")
        else:
            print(
                f"  -> best model: {entry['best_model']}, "
                f"shelf life = {entry['shelf_life_months']} months "
                f"(95% lower bound {entry['shelf_life_lower_95_months']} months)"
            )
        print()


def _run_arrhenius(args) -> int:
    data = load_accelerated_data(args.input)
    rates_by_temp = degradation_rates_by_temperature(
        data.times, data.temperatures, data.values
    )

    temps = sorted(rates_by_temp)
    fit = fit_arrhenius([t for t in temps], [rates_by_temp[t].rate for t in temps])
    k_storage = predict_arrhenius_rate(fit, args.storage_temp)
    shelf_months = (
        math.log(args.initial_potency / args.limit) / k_storage
        if args.initial_potency > args.limit
        else None
    )

    report = {
        "rates": [
            {
                "temperature_c": t,
                "rate_1_per_month": rates_by_temp[t].rate,
                "r_squared": round(rates_by_temp[t].r_squared, 5),
            }
            for t in temps
        ],
        "arrhenius": {
            "activation_energy_kj_mol": round(
                fit.activation_energy_kj_mol, 2
            ),
            "pre_exponential_factor": fit.pre_exponential_factor,
            "r_squared": round(fit.r_squared, 5),
        },
        "prediction": {
            "storage_temperature_c": args.storage_temp,
            "rate_1_per_month": k_storage,
            "shelf_life_months": (
                round(shelf_months, 2) if shelf_months is not None else None
            ),
        },
    }

    if args.out:
        _write_json_report(report, args.out)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print("Arrhenius stability extrapolation")
        print("Temperature  Rate (1/month)  R²")
        for t in temps:
            print(
                f"{t:>11.1f}  {rates_by_temp[t].rate:>14.6f}  "
                f"{rates_by_temp[t].r_squared:.4f}"
            )
        print()
        print(f"Activation energy: {fit.activation_energy_kj_mol:.2f} kJ/mol")
        print(f"Arrhenius R²: {fit.r_squared:.4f}")
        print()
        print(f"Storage temperature: {args.storage_temp:.2f} C")
        print(f"Predicted rate: {k_storage:.6f} /month")
        if shelf_months is not None:
            print(
                f"Predicted shelf life to {args.limit}%: "
                f"{shelf_months:.2f} months ({shelf_months / 12.0:.2f} years)"
            )
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="stability-shelf-life",
        description="Pharmaceutical stability shelf-life modelling (ICH Q1E + Arrhenius).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    q1e = sub.add_parser("q1e", help="ICH Q1E shelf-life estimation")
    q1e.add_argument("--input", required=True, help="CSV: time_months,assay_percent,batch_id")
    q1e.add_argument("--limit", type=float, required=True, help="acceptance criterion (percent)")
    q1e.add_argument("--json", action="store_true", help="emit JSON")
    q1e.add_argument("--out", metavar="FILE", help="write JSON report to FILE")

    arr = sub.add_parser("arrhenius", help="Arrhenius extrapolation of accelerated data")
    arr.add_argument("--input", required=True, help="CSV: temperature_c,time_months,potency")
    arr.add_argument("--storage-temp", type=float, default=25.0, help="long-term storage temperature C")
    arr.add_argument("--limit", type=float, default=90.0, help="acceptance criterion (percent)")
    arr.add_argument("--initial-potency", type=float, default=100.0, help="initial potency (percent)")
    arr.add_argument("--json", action="store_true", help="emit JSON")
    arr.add_argument("--out", metavar="FILE", help="write JSON report to FILE")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "q1e":
            return _run_q1e(args)
        return _run_arrhenius(args)
    except StabilityError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
