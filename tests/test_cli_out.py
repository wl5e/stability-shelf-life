"""Tests for the --out JSON report file option."""

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


def test_q1e_out_file_writes_json(tmp_path):
    input_csv = tmp_path / "stability.csv"
    input_csv.write_text(
        """time_months,assay_percent,batch_id
0,100.1,A01
3,98.9,A01
6,97.6,A01
0,99.8,B02
3,98.4,B02
6,96.9,B02
""",
        encoding="utf-8",
    )
    out = tmp_path / "report.json"
    result = _run_cli(
        "q1e",
        "--input", str(input_csv),
        "--limit", "90",
        "--out", str(out),
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["limit"] == 90.0
    assert {b["batch_id"] for b in report["batches"]} == {"A01", "B02"}


def test_arrhenius_out_file_writes_json(tmp_path):
    input_csv = tmp_path / "accelerated.csv"
    input_csv.write_text(
        """temperature_c,time_months,potency
40,0,100.0
40,3,97.0
40,6,94.1
50,0,100.0
50,3,94.2
50,6,88.8
60,0,100.0
60,3,88.9
60,6,79.0
""",
        encoding="utf-8",
    )
    out = tmp_path / "arrhenius-report.json"
    result = _run_cli(
        "arrhenius",
        "--input", str(input_csv),
        "--storage-temp", "25",
        "--out", str(out),
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["arrhenius"]["activation_energy_kj_mol"] > 0
    assert report["prediction"]["rate_1_per_month"] > 0
