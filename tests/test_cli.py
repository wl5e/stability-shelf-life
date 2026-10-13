"""End-to-end tests for the command-line interface."""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _run_cli(*args):
    return subprocess.run(
        [sys.executable, "main.py", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )


def _write_summary_csv(path):
    """Write a small single-batch file whose statistics are known exactly."""
    path.write_text(
        "time_months,assay_percent,batch_id\n"
        "0,100.0,A01\n3,98.0,A01\n6,96.0,A01\n",
        encoding="utf-8",
    )
    return str(path)


def test_q1e_json_roundtrip():
    res = _run_cli("q1e", "--input", "examples/stability_data.csv", "--limit", "90", "--json")
    assert res.returncode == 0, res.stderr
    report = json.loads(res.stdout)
    assert report["limit"] == 90.0
    assert {b["batch_id"] for b in report["batches"]} == {"A01", "B02"}
    for b in report["batches"]:
        assert b["best_model"] in ("zero-order", "first-order")
        assert b["shelf_life_months"] > 0
        assert b["shelf_life_lower_95_months"] <= b["shelf_life_months"]


def test_arrhenius_json_roundtrip():
    res = _run_cli("arrhenius", "--input", "examples/accelerated_data.csv", "--storage-temp", "25", "--json")
    assert res.returncode == 0, res.stderr
    report = json.loads(res.stdout)
    assert report["arrhenius"]["activation_energy_kj_mol"] > 0
    assert report["prediction"]["rate_1_per_month"] > 0


def test_q1e_json_report_includes_descriptive_statistics(tmp_path):
    path = _write_summary_csv(tmp_path / "summary.csv")
    res = _run_cli("q1e", "--input", path, "--limit", "90", "--json")
    assert res.returncode == 0, res.stderr
    report = json.loads(res.stdout)
    summary = report["batches"][0]["summary"]

    assert summary["n"] == 3
    assert summary["mean"] == 98.0
    assert summary["sd"] == 2.0
    assert summary["min"] == 96.0
    assert summary["max"] == 100.0


def test_q1e_text_report_prints_summary_before_models(tmp_path):
    path = _write_summary_csv(tmp_path / "summary.csv")
    res = _run_cli("q1e", "--input", path, "--limit", "90")
    assert res.returncode == 0, res.stderr
    assert "potency summary" in res.stdout
    # The descriptive statistics are reported before any model is fitted.
    assert res.stdout.index("potency summary") < res.stdout.index("zero-order")
