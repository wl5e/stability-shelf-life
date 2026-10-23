"""End-to-end tests for the command-line interface."""

import json
import math
import subprocess
import sys
from pathlib import Path

import pytest

from stability_shelf_life import __version__

ROOT = Path(__file__).resolve().parent.parent


def _run_cli(*args):
    return subprocess.run(
        [sys.executable, "main.py", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )


def test_version_prints_package_version():
    res = _run_cli("--version")
    assert res.returncode == 0, res.stderr
    assert __version__ in res.stdout


def _write_summary_csv(path):
    """Write a small single-batch file whose statistics are known exactly."""
    path.write_text(
        "time_months,assay_percent,batch_id\n"
        "0,100.0,A01\n3,98.0,A01\n6,96.0,A01\n",
        encoding="utf-8",
    )
    return str(path)


def _write_first_order_csv(path, rate=0.01, initial=100.0, times=(0, 3, 6, 9, 12)):
    """Write a single batch whose exact first-order decay has a known rate."""
    lines = ["time_months,assay_percent,batch_id"]
    for t in times:
        lines.append(f"{t},{initial * math.exp(-rate * t):.6f},A01")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
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


def test_q1e_evaluates_multiple_limits_in_one_run():
    res = _run_cli(
        "q1e", "--input", "examples/stability_data.csv",
        "--limit", "90", "95", "--json",
    )
    assert res.returncode == 0, res.stderr
    report = json.loads(res.stdout)

    assert report["limits"] == [90.0, 95.0]
    # The first limit is still exposed for backward compatibility.
    assert report["limit"] == 90.0
    for batch in report["batches"]:
        by_limit = batch["shelf_life_by_limit"]
        assert [item["limit"] for item in by_limit] == [90.0, 95.0]
        shelf_90 = by_limit[0]["shelf_life_months"]
        shelf_95 = by_limit[1]["shelf_life_months"]
        assert shelf_90 > 0
        assert shelf_95 > 0
        # A stricter acceptance criterion shortens the shelf life.
        assert shelf_95 < shelf_90


def test_q1e_text_report_lists_each_limit():
    res = _run_cli(
        "q1e", "--input", "examples/stability_data.csv", "--limit", "90", "95"
    )
    assert res.returncode == 0, res.stderr
    assert "Specification limits: 90%, 95%" in res.stdout
    # Each limit is reported once per batch (two batches in the example data).
    assert res.stdout.count("limit 90%") >= 2
    assert res.stdout.count("limit 95%") >= 2


def test_q1e_reports_release_limit_for_target_shelf_life(tmp_path):
    # Exact first-order decay: k = 0.01 /month and C0 = 100%.
    path = _write_first_order_csv(tmp_path / "first_order.csv")
    res = _run_cli(
        "q1e", "--input", path, "--limit", "90",
        "--shelf-life", "24", "--json",
    )
    assert res.returncode == 0, res.stderr
    report = json.loads(res.stdout)
    assert report["release_limit_shelf_life_months"] == 24.0

    entry = report["batches"][0]
    assert entry["best_model"] == "first-order"
    release = entry["release_limits"]
    assert len(release) == 1
    item = release[0]
    # First-order back-calculation: release = limit * exp(k * shelf life).
    expected = 90.0 * math.exp(0.01 * 24.0)
    assert item["limit"] == 90.0
    assert item["release_limit_percent"] == pytest.approx(expected, rel=1e-3)
    assert item["fitted_initial_percent"] == pytest.approx(100.0, rel=1e-3)
    # 100% at release is not enough for a 24-month shelf life at 90%.
    assert item["meets_release_limit"] is False


def test_q1e_omits_release_limit_without_target_shelf_life():
    res = _run_cli(
        "q1e", "--input", "examples/stability_data.csv", "--limit", "90", "--json"
    )
    assert res.returncode == 0, res.stderr
    report = json.loads(res.stdout)
    assert report["release_limit_shelf_life_months"] is None
    assert report["batches"][0]["release_limits"] is None


def test_q1e_text_report_prints_release_limit(tmp_path):
    path = _write_first_order_csv(tmp_path / "first_order.csv")
    res = _run_cli(
        "q1e", "--input", path, "--limit", "90", "--shelf-life", "24",
    )
    assert res.returncode == 0, res.stderr
    assert "release limit for 90% at 24 months" in res.stdout
    assert "not satisfied" in res.stdout


def test_q1e_writes_ich_q1a_summary_table(tmp_path):
    table_path = tmp_path / "summary_table.txt"
    res = _run_cli(
        "q1e", "--input", "examples/stability_data.csv",
        "--limit", "90", "95", "--table", str(table_path),
    )
    assert res.returncode == 0, res.stderr
    text = table_path.read_text(encoding="utf-8")

    assert "ICH Q1A/Q1E stability summary" in text
    assert "Specification limits: 90%, 95%" in text
    assert "Shelf life (months)" in text
    assert "95% lower (months)" in text
    rows = [
        line for line in text.splitlines()
        if line.startswith("A01") or line.startswith("B02")
    ]
    # One row per batch per acceptance criterion (two batches, two limits).
    assert len(rows) == 4


def test_q1e_bootstrap_adds_finite_lower_bound():
    res = _run_cli(
        "q1e", "--input", "examples/stability_data.csv",
        "--limit", "90", "--bootstrap", "200", "--json",
    )
    assert res.returncode == 0, res.stderr
    report = json.loads(res.stdout)
    for batch in report["batches"]:
        lower = batch["shelf_life_by_limit"][0]["bootstrap_lower_95_months"]
        assert lower is not None
        assert math.isfinite(lower)


def test_q1e_release_limit_reported_independently():
    res = _run_cli(
        "q1e", "--input", "examples/stability_data.csv",
        "--limit", "90", "--release-limit", "95", "--json",
    )
    assert res.returncode == 0, res.stderr
    report = json.loads(res.stdout)
    # The shelf-life limit and the release limit are reported independently.
    assert report["limit"] == 90.0
    assert report["release_limit"] == 95.0
    for batch in report["batches"]:
        spec = batch["release_specification"]
        assert spec["release_limit"] == 95.0
        assert spec["fitted_initial_percent"] > 0
        assert isinstance(spec["meets_release_limit"], bool)


def test_q1e_release_limit_absent_by_default():
    res = _run_cli(
        "q1e", "--input", "examples/stability_data.csv", "--limit", "90", "--json"
    )
    assert res.returncode == 0, res.stderr
    report = json.loads(res.stdout)
    assert report["release_limit"] is None
    assert report["batches"][0]["release_specification"] is None


def test_q1e_text_reports_release_limit():
    res = _run_cli(
        "q1e", "--input", "examples/stability_data.csv",
        "--limit", "90", "--release-limit", "95",
    )
    assert res.returncode == 0, res.stderr
    assert "release limit 95%" in res.stdout
