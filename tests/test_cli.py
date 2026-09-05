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
