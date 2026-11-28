"""Native evidence must match the producer, not merely have a plausible name."""

import hashlib
import zipfile

import pytest

from chip_evolve.stage_facts import extract, matches_evaluation, observations


@pytest.mark.parametrize("changed", ["log", "cwd", "missing_checkpoint"])
def test_other_attempts_cannot_supply_current_stage_facts(changed):
    native = {
        "request": {"cwd": "/native/current"},
        "output_files": {"/native/current/evaluation.log": "current"},
    }
    measured = {
        "request": {
            "cwd": "/native/current",
            "inputs": {"/native/current/evaluation.log": "current"},
        },
        "output_files": {"/native/current/checkpoint_metrics.json": "metrics"},
    }
    assert matches_evaluation(native, measured)
    if changed == "log":
        measured["request"]["inputs"]["/native/current/evaluation.log"] = (
            "earlier-attempt"
        )
    elif changed == "cwd":
        measured["request"]["cwd"] = "/native/other"
    else:
        measured["output_files"] = {}
    assert not matches_evaluation(native, measured)


def test_extract_rejects_wrong_bytes_for_an_otherwise_correct_filename(tmp_path):
    archive = tmp_path / "native.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("0/checkpoint_metrics.json", b"wrong attempt")
    receipt = {
        "request": {"cwd": "/native/current"},
        "output_files": {
            "/native/current/checkpoint_metrics.json": hashlib.sha256(
                b"actual"
            ).hexdigest()
        },
    }
    with pytest.raises(ValueError, match="hash-matched"):
        extract(archive, receipt, "checkpoint_metrics.json", tmp_path / "facts.json")
    assert not (tmp_path / "facts.json").exists()


def test_equal_qor_and_equal_netlist_are_separate_observations():
    checkpoints = {
        "checkpoints": {
            "pre_repair": {"tns_abs_ns": 0.0, "total_power_pw": 1e9},
            "post_repair_design": {"tns_abs_ns": 0.0, "total_power_pw": 1e9},
            "post_repair_timing": {"tns_abs_ns": 0.0, "total_power_pw": 1e9},
            "post_route": {"tns_abs_ns": 0.0, "total_power_pw": 1.1e9},
        }
    }
    rows = observations(
        checkpoints,
        {
            "/native/pre_repair.v": "before",
            "/native/post_repair_design.v": "before",
            "/native/post_repair_timing.v": "changed",
            "/native/post_route.v": "changed",
        },
    )
    assert rows[0]["same_reported_metrics_as_previous"] is None
    assert rows[0]["same_netlist_as_previous"] is None
    assert rows[1]["same_reported_metrics_as_previous"] is True
    assert rows[1]["same_netlist_as_previous"] is True
    assert rows[2]["same_reported_metrics_as_previous"] is True
    assert rows[2]["same_netlist_as_previous"] is False
    assert rows[3]["same_reported_metrics_as_previous"] is False
    assert rows[3]["same_netlist_as_previous"] is True
    assert rows[3]["native_metrics"]["total_power_pw"] == 1.1e9


def test_missing_netlist_evidence_is_unknown_instead_of_no_change():
    rows = observations(
        {"checkpoints": {"a": {"tns_abs_ns": 0}, "b": {"tns_abs_ns": 0}}}, {}
    )
    assert rows[1]["same_reported_metrics_as_previous"] is True
    assert rows[1]["same_netlist_as_previous"] is None
