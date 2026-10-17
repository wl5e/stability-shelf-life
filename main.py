"""Command-line interface for pharmaceutical stability analysis.

Two subcommands are provided:

    q1e       — ICH Q1E shelf-life estimation (zero/first-order kinetics,
                one-sided 95% lower confidence bound, per batch) together
                with an F test for slope differences between batches.  One
                or more specification limits may be evaluated in one run.
    arrhenius — Arrhenius extrapolation of accelerated-stability data to a
                chosen long-term storage temperature.

Examples:
    python main.py q1e --input examples/stability_data.csv --limit 90 95
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
from stability_shelf_life.model import (
    SlopeDifference,
    descriptive_statistics,
    information_criterion,
    rate_confidence_interval,
    release_limit,
    slope_difference_test,
)
from stability_shelf_life.report import render_html_report


def _write_json_report(report, output_path: str) -> None:
    """Persist the JSON report to *output_path* (GMP audit-trail artifact)."""
    try:
        with open(output_path, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)
    except OSError as exc:
        raise StabilityError(
            f"could not write report file {output_path}: {exc}"
        ) from exc


def _write_text_report(content: str, output_path: str, label: str) -> None:
    """Persist a text artefact (e.g. a standalone HTML report) to disk."""
    try:
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(content)
    except OSError as exc:
        raise StabilityError(
            f"could not write {label} file {output_path}: {exc}"
        ) from exc


def _table_cell(value) -> str:
    """Format a report value for the ICH summary table."""
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def _render_q1e_table(report) -> str:
    """Render an ICH Q1A/Q1E-style plain-text regulatory summary table."""
    batches = report.get("batches") or []
    limits = report.get("limits") or [report.get("limit")]
    include_release = any(batch.get("release_limits") for batch in batches)

    header = [
        "Batch",
        "n",
        "Model",
        "Limit (%)",
        "Rate",
        "Rate unit",
        "Initial (%)",
        "R²",
        "Shelf life (months)",
        "95% lower (months)",
    ]
    if include_release:
        header.append("Release limit (%)")

    rows = []
    for batch in batches:
        models = batch.get("models") or []
        best_model = batch.get("best_model")
        best_initial = next(
            (
                model.get("initial_potency")
                for model in models
                if model.get("model") == best_model
            ),
            None,
        )
        shelf_lives = batch.get("shelf_life_by_limit")
        if not shelf_lives:
            shelf_lives = [
                {
                    "limit": report.get("limit"),
                    "shelf_life_months": batch.get("shelf_life_months"),
                    "shelf_life_lower_95_months": batch.get(
                        "shelf_life_lower_95_months"
                    ),
                }
            ]
        release_by_limit = {
            item.get("limit"): item
            for item in (batch.get("release_limits") or [])
        }
        for item in shelf_lives:
            row = [
                _table_cell(batch.get("batch_id")),
                _table_cell(batch.get("n_points")),
                _table_cell(best_model),
                _table_cell(item.get("limit")),
                _table_cell(batch.get("best_rate")),
                _table_cell(batch.get("best_rate_unit")),
                _table_cell(best_initial),
                _table_cell(batch.get("best_r_squared")),
                _table_cell(item.get("shelf_life_months")),
                _table_cell(item.get("shelf_life_lower_95_months")),
            ]
            if include_release:
                release = release_by_limit.get(item.get("limit"))
                row.append(
                    _table_cell(release.get("release_limit_percent"))
                    if release is not None
                    else "N/A"
                )
            rows.append(row)

    lines = ["ICH Q1A/Q1E stability summary", ""]
    if limits:
        if len(limits) == 1:
            lines.append(f"Specification limit: {_table_cell(limits[0])}%")
        else:
            listed = ", ".join(f"{_table_cell(limit)}%" for limit in limits)
            lines.append(f"Specification limits: {listed}")
        lines.append("")
    if not rows:
        return "\n".join(lines).rstrip() + "\n"

    widths = [len(column) for column in header]
    for row in rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(cell))

    separator = "  "
    lines.append(
        separator.join(
            column.ljust(widths[index]) for index, column in enumerate(header)
        )
    )
    lines.append(separator.join("-" * width for width in widths))
    for row in rows:
        lines.append(
            separator.join(
                cell.ljust(widths[index]) for index, cell in enumerate(row)
            )
        )
    return "\n".join(lines) + "\n"


def _select_model(fits, times, values):
    """Choose between the zero- and first-order models by AIC.

    The information criteria are evaluated on the common potency scale, so
    the two models are compared on equal footing (their residuals on the
    transformed scale are not comparable).  Lower AIC wins; on a tie the
    first-order model is preferred.
    """
    zero, first = fits[0], fits[1]
    zero_aic = information_criterion(zero, times, values).aic
    first_aic = information_criterion(first, times, values).aic
    if first_aic <= zero_aic:
        return first, "first-order"
    return zero, "zero-order"


def _slope_difference_entry(
    order: int, batch_ids: Sequence[str], comparison: SlopeDifference
) -> dict:
    """Serialise an F test for equal slopes between batches."""
    return {
        "model": "zero-order" if order == 0 else "first-order",
        "batch_ids": list(batch_ids),
        "rates": [round(rate, 6) for rate in comparison.rates],
        "rate_unit": "percent/month" if order == 0 else "1/month",
        "f_statistic": (
            round(comparison.f_statistic, 4)
            if math.isfinite(comparison.f_statistic)
            else None
        ),
        "df_between": comparison.df_between,
        "df_within": comparison.df_within,
        "p_value": round(comparison.p_value, 5),
        "slopes_differ": comparison.slopes_differ,
    }


def _run_q1e(args) -> int:
    batches = load_stability_data(args.input)
    limits = [float(limit) for limit in args.limit]

    report = {
        "limit": limits[0],
        "limits": limits,
        "release_limit_shelf_life_months": args.shelf_life,
        "batches": [],
        "slope_difference": [],
    }
    fits_by_order = {0: [], 1: []}
    ids_by_order = {0: [], 1: []}

    for batch_id in sorted(batches):
        batch = batches[batch_id]
        stats = descriptive_statistics(batch.values)
        fits = [fit_kinetics(batch.times, batch.values, o) for o in (0, 1)]
        best, best_name = _select_model(fits, batch.times, batch.values)
        best_ci = rate_confidence_interval(best)

        shelf_lives = []
        release_limits = []
        for limit in limits:
            shelf = estimate_shelf_life(best, limit)
            if shelf.stable:
                shelf_lives.append(
                    {
                        "limit": limit,
                        "shelf_life_months": round(
                            shelf.point_estimate_months, 2
                        ),
                        "shelf_life_lower_95_months": round(
                            shelf.lower_bound_months, 2
                        ),
                    }
                )
            else:
                shelf_lives.append(
                    {
                        "limit": limit,
                        "shelf_life_months": None,
                        "shelf_life_lower_95_months": None,
                    }
                )
            if args.shelf_life is not None:
                required = release_limit(best, limit, args.shelf_life)
                release_limits.append(
                    {
                        "limit": limit,
                        "release_limit_percent": round(required, 3),
                        "fitted_initial_percent": round(best.initial, 3),
                        "meets_release_limit": best.initial >= required,
                    }
                )

        entry = {
            "batch_id": batch_id,
            "n_points": len(batch.times),
            "summary": {
                "n": stats.n,
                "mean": round(stats.mean, 3),
                "sd": round(stats.sd, 4),
                "min": round(stats.minimum, 3),
                "max": round(stats.maximum, 3),
            },
            "best_model": best_name,
            "best_rate": round(best.rate, 6),
            "best_rate_unit": "percent/month" if best.order == 0 else "1/month",
            "best_rate_ci_95_lower": round(best_ci.lower, 6),
            "best_rate_ci_95_upper": round(best_ci.upper, 6),
            "best_rate_one_sided_95_lower": round(best_ci.one_sided_lower, 6),
            "best_r_squared": round(best.r_squared, 5),
            # First limit repeated at the batch level for backward compatibility.
            "shelf_life_months": shelf_lives[0]["shelf_life_months"],
            "shelf_life_lower_95_months": shelf_lives[0][
                "shelf_life_lower_95_months"
            ],
            "shelf_life_by_limit": shelf_lives,
            "release_limits": release_limits or None,
            "models": [],
        }

        for fit in fits:
            fits_by_order[fit.order].append(fit)
            ids_by_order[fit.order].append(batch_id)
            name = "zero-order" if fit.order == 0 else "first-order"
            ci = rate_confidence_interval(fit)
            entry["models"].append(
                {
                    "model": name,
                    "rate": round(fit.rate, 6),
                    "rate_unit": "percent/month" if fit.order == 0 else "1/month",
                    "rate_ci_95_lower": round(ci.lower, 6),
                    "rate_ci_95_upper": round(ci.upper, 6),
                    "rate_one_sided_95_lower": round(ci.one_sided_lower, 6),
                    "initial_potency": round(fit.initial, 3),
                    "r_squared": round(fit.r_squared, 5),
                }
            )
        report["batches"].append(entry)

    for order in (0, 1):
        order_fits = fits_by_order[order]
        if len(order_fits) < 2:
            continue
        comparison = slope_difference_test(order_fits)
        report["slope_difference"].append(
            _slope_difference_entry(order, ids_by_order[order], comparison)
        )

    if args.out:
        _write_json_report(report, args.out)

    if args.html:
        _write_text_report(
            render_html_report(report), args.html, "HTML report"
        )

    if args.table:
        _write_text_report(
            _render_q1e_table(report), args.table, "summary table"
        )

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        _print_q1e_report(report)
    return 0


def _print_q1e_report(report) -> None:
    print("ICH Q1E stability analysis")
    limits = report.get("limits") or [report["limit"]]
    if len(limits) == 1:
        print(f"Specification limit: {limits[0]}%")
    else:
        listed = ", ".join(f"{limit:g}%" for limit in limits)
        print(f"Specification limits: {listed}")
    print()
    for entry in report["batches"]:
        print(f"Batch {entry['batch_id']} ({entry['n_points']} time points)")
        summary = entry.get("summary")
        if summary is not None:
            print(
                f"  potency summary: n = {summary['n']}, "
                f"mean = {summary['mean']:.3f}%, sd = {summary['sd']:.3f}, "
                f"min = {summary['min']:.3f}%, max = {summary['max']:.3f}%"
            )
        for m in entry["models"]:
            unit = " %/month" if m["model"] == "zero-order" else " /month"
            print(
                f"  {m['model']:>11}: k = {m['rate']:.5f}{unit}, "
                f"C0 = {m['initial_potency']:.2f}%, R² = {m['r_squared']:.4f}"
            )
            print(
                "                95% CI for k: "
                f"[{m['rate_ci_95_lower']:.5f}, {m['rate_ci_95_upper']:.5f}]"
                f"{unit} (one-sided lower {m['rate_one_sided_95_lower']:.5f})"
            )
        shelf_lives = entry.get("shelf_life_by_limit")
        if not shelf_lives:
            # Backward-compatible fallback for reports without the per-limit list.
            shelf_lives = [
                {
                    "limit": report["limit"],
                    "shelf_life_months": entry.get("shelf_life_months"),
                    "shelf_life_lower_95_months": entry.get(
                        "shelf_life_lower_95_months"
                    ),
                }
            ]
        if len(shelf_lives) == 1:
            item = shelf_lives[0]
            if item["shelf_life_months"] is None:
                print("  -> no degradation detected (shelf life not estimable)")
            else:
                print(
                    f"  -> best model: {entry['best_model']}, "
                    f"shelf life = {item['shelf_life_months']} months "
                    f"(95% lower bound "
                    f"{item['shelf_life_lower_95_months']} months)"
                )
        else:
            print(f"  -> best model: {entry['best_model']}")
            for item in shelf_lives:
                if item["shelf_life_months"] is None:
                    print(
                        f"     limit {item['limit']:g}%: no degradation "
                        "detected (shelf life not estimable)"
                    )
                else:
                    print(
                        f"     limit {item['limit']:g}%: shelf life = "
                        f"{item['shelf_life_months']} months "
                        f"(95% lower bound "
                        f"{item['shelf_life_lower_95_months']} months)"
                    )
        release_limits = entry.get("release_limits")
        if release_limits:
            target = report.get("release_limit_shelf_life_months")
            for item in release_limits:
                verdict = (
                    "satisfied"
                    if item["meets_release_limit"]
                    else "not satisfied"
                )
                print(
                    f"     release limit for {item['limit']:g}% at "
                    f"{target:g} months: {item['release_limit_percent']:g}% "
                    f"(fitted initial {item['fitted_initial_percent']:g}%, "
                    f"{verdict})"
                )
        print()

    slope_tests = report.get("slope_difference") or []
    if slope_tests:
        print("Slope comparison between batches (extra-sum-of-squares F test)")
        for entry in slope_tests:
            f_text = (
                "inf"
                if entry["f_statistic"] is None
                else f"{entry['f_statistic']:.3f}"
            )
            verdict = (
                "differ significantly"
                if entry["slopes_differ"]
                else "do not differ significantly"
            )
            print(
                f"  {entry['model']:>11}: F({entry['df_between']}, "
                f"{entry['df_within']}) = {f_text}, p = {entry['p_value']:.4f}"
                f" -> slopes {verdict}"
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

    if args.html:
        _write_text_report(
            render_html_report(report), args.html, "HTML report"
        )

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
    q1e.add_argument(
        "--limit",
        type=float,
        nargs="+",
        required=True,
        metavar="PCT",
        help="acceptance criterion/criteria in percent (one or more, e.g. --limit 90 95)",
    )
    q1e.add_argument(
        "--shelf-life",
        type=float,
        default=None,
        metavar="MONTHS",
        help=(
            "target shelf life in months; when given, the release limit "
            "(minimum t=0 potency that still meets each acceptance criterion "
            "at this shelf life) is computed and reported"
        ),
    )
    q1e.add_argument("--json", action="store_true", help="emit JSON")
    q1e.add_argument("--out", metavar="FILE", help="write JSON report to FILE")
    q1e.add_argument("--html", metavar="FILE", help="write standalone HTML report to FILE")
    q1e.add_argument(
        "--table",
        metavar="FILE",
        help="write an ICH Q1A/Q1E-style summary table to FILE",
    )

    arr = sub.add_parser("arrhenius", help="Arrhenius extrapolation of accelerated data")
    arr.add_argument("--input", required=True, help="CSV: temperature_c,time_months,potency")
    arr.add_argument("--storage-temp", type=float, default=25.0, help="long-term storage temperature C")
    arr.add_argument("--limit", type=float, default=90.0, help="acceptance criterion (percent)")
    arr.add_argument("--initial-potency", type=float, default=100.0, help="initial potency (percent)")
    arr.add_argument("--json", action="store_true", help="emit JSON")
    arr.add_argument("--out", metavar="FILE", help="write JSON report to FILE")
    arr.add_argument("--html", metavar="FILE", help="write standalone HTML report to FILE")
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
