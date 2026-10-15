"""CP0 retains the baseline minimum-period meaning across report formats."""

import json

import pytest
from extract_metrics import reference_ecp


def test_legacy_clock_period_remains_primary(tmp_path):
    log = tmp_path / "combined.log"
    log.write_text("Report metrics stage 6, finish\nclock period_min = 300.25\n")
    (tmp_path / "6_report.json").write_text(json.dumps({"finish__timing__fmax": 2e9}))
    assert reference_ecp(log, tmp_path) == 300.25


@pytest.mark.parametrize("unit,expected", [("ps", 500), ("ns", 0.5)])
def test_modern_fmax_preserves_native_clock_units(tmp_path, unit, expected):
    log = tmp_path / "combined.log"
    log.write_text("Running final_report.tcl\n")
    (tmp_path / "6_report.json").write_text(json.dumps({"finish__timing__fmax": 2e9}))
    assert reference_ecp(log, tmp_path, time_unit=unit) == expected


@pytest.mark.parametrize("fmax", [0, -1, float("nan"), None])
def test_missing_or_invalid_fmax_cannot_generate_cp0(tmp_path, fmax):
    log = tmp_path / "combined.log"
    log.write_text("no legacy timing report\n")
    (tmp_path / "6_report.json").write_text(json.dumps({"finish__timing__fmax": fmax}))
    assert reference_ecp(log, tmp_path) is None
