"""Tests for the standalone HTML report (stability_shelf_life.report)."""

import subprocess
import sys
from pathlib import Path

import pytest

from stability_shelf_life.report import render_html_report

ROOT = Path(__file__).resolve().parent.parent


def _run_cli(*args):
    return subprocess.run(
        [sys.executable, "main.py", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )


_Q1E_REPORT = {
    "limit": 90.0,
    "batches": [
        {
            "batch_id": "A01",
            "n_points": 5,
            "best_model": "first-order",
            "best_rate": 0.008543,
            "best_rate_unit": "1/month",
            "best_r_squared": 0.99712,
            "shelf_life_months": 24.35,
            "shelf_life_lower_95_months": 21.87,
            "models": [
                {
                    "model": "zero-order",
                    "rate": 0.812345,
                    "rate_unit": "percent/month",
                    "initial_potency": 100.123,
                    "r_squared": 0.98123,
                },
                {
                    "model": "first-order",
                    "rate": 0.008543,
                    "rate_unit": "1/month",
                    "initial_potency": 100.045,
                    "r_squared": 0.99712,
                },
            ],
        }
    ],
    "slope_difference": [
        {
            "model": "first-order",
            "batch_ids": ["A01", "B02"],
            "rates": [0.008543, 0.009211],
            "rate_unit": "1/month",
            "f_statistic": 1.234,
            "df_between": 1,
            "df_within": 6,
            "p_value": 0.30987,
            "slopes_differ": False,
        }
    ],
}


def test_render_q1e_report_is_standalone_html():
    document = render_html_report(_Q1E_REPORT)
    assert document.startswith("<!DOCTYPE html>")
    assert document.rstrip().endswith("</html>")
    assert "<style>" in document
    # No external assets: the document must be fully self-contained.
    assert "http://" not in document and "https://" not in document
    assert "A01" in document
    assert "first-order" in document
    assert "24.35" in document


def test_render_q1e_report_escapes_values():
    report = dict(_Q1E_REPORT)
    report["batches"] = [dict(_Q1E_REPORT["batches"][0], batch_id="<script>")]
    document = render_html_report(report)
    assert "<script>" not in document
    assert "&lt;script&gt;" in document


def test_render_q1e_report_flags_unstable_batch():
    report = {
        "limit": 90.0,
        "batches": [
            {
                "batch_id": "B02",
                "n_points": 3,
                "best_model": "zero-order",
                "best_rate": 0.0,
                "best_rate_unit": "percent/month",
                "best_r_squared": 0.0,
                "shelf_life_months": None,
                "shelf_life_lower_95_months": None,
                "models": [],
            }
        ],
        "slope_difference": [],
    }
    document = render_html_report(report)
    assert "No degradation detected" in document


def test_render_arrhenius_report_is_standalone_html():
    report = {
        "rates": [
            {"temperature_c": 40.0, "rate_1_per_month": 0.01, "r_squared": 0.999},
            {"temperature_c": 50.0, "rate_1_per_month": 0.02, "r_squared": 0.999},
        ],
        "arrhenius": {
            "activation_energy_kj_mol": 71.2,
            "pre_exponential_factor": 1.5e9,
            "r_squared": 0.9987,
        },
        "prediction": {
            "storage_temperature_c": 25.0,
            "rate_1_per_month": 0.00321,
            "shelf_life_months": 32.5,
        },
    }
    document = render_html_report(report)
    assert document.startswith("<!DOCTYPE html>")
    assert "Arrhenius" in document
    assert "32.5" in document


def test_render_html_report_rejects_unknown_structure():
    with pytest.raises(ValueError, match="unrecognised"):
        render_html_report({"unexpected": True})


def test_cli_q1e_writes_html_report(tmp_path):
    out = tmp_path / "q1e.html"
    res = _run_cli(
        "q1e",
        "--input",
        "examples/stability_data.csv",
        "--limit",
        "90",
        "--html",
        str(out),
    )
    assert res.returncode == 0, res.stderr
    document = out.read_text(encoding="utf-8")
    assert document.startswith("<!DOCTYPE html>")
    assert "A01" in document and "B02" in document


def test_cli_arrhenius_writes_html_report(tmp_path):
    out = tmp_path / "arrhenius.html"
    res = _run_cli(
        "arrhenius",
        "--input",
        "examples/accelerated_data.csv",
        "--storage-temp",
        "25",
        "--html",
        str(out),
    )
    assert res.returncode == 0, res.stderr
    document = out.read_text(encoding="utf-8")
    assert document.startswith("<!DOCTYPE html>")
    assert "Arrhenius" in document
