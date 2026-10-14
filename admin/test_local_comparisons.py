"""Factual comparisons must not turn incompatible measurements into gains."""

from copy import deepcopy

import pytest

from chip_evolve.comparisons import METRICS, compare, proven_points
from chip_evolve.config import write


def result(tmp_path):
    objective = tmp_path / "objective.json"
    write(
        objective,
        {
            "constraints": {
                "setup_tns_ns_min": 0,
                "hold_tns_ns_min": 0,
                "max_slew_violations": 0,
                "max_cap_violations": 0,
                "placement_violations": 0,
                "route_drc": 0,
                "power_total_w_max": 1,
                "cell_area_um2_max": 10,
                "core_area_um2_max": 20,
                "die_area_um2_max": 30,
            }
        },
    )
    metrics = dict.fromkeys(METRICS, 0)
    metrics.update(
        {
            "finish__power__total": 1,
            "finish__design__instance__area": 10,
            "finish__design__core__area": 20,
            "finish__design__die__area": 30,
            "finish__timing__drv__max_slew": 0,
            "finish__timing__drv__max_cap": 0,
            "design__violations": 0,
        }
    )
    return {
        "design_id": "registered-design",
        "objective_id": "frozen-goal",
        "condition_id": "frozen-conditions",
        "run_id": "reference",
        "objective": str(objective),
        "route_drc": 0,
        "metrics": metrics,
    }


def test_lower_power_with_open_timing_is_reported_as_infeasible(tmp_path):
    reference = result(tmp_path)
    candidate = deepcopy(reference)
    candidate["run_id"] = "candidate"
    candidate["metrics"]["finish__power__total"] = 0.8
    candidate["metrics"]["finish__timing__setup__tns"] = -0.04
    receipt = compare(reference, candidate)
    assert receipt["deltas"]["finish__power__total"]["percent"] == pytest.approx(-20)
    assert receipt["deltas"]["finish__timing__setup__tns"]["percent"] is None
    assert receipt["constraint_violations"] == ["setup_tns_ns_min"]


@pytest.mark.parametrize("identity", ["design_id", "objective_id", "condition_id"])
def test_mismatched_comparison_is_rejected(tmp_path, identity):
    reference = result(tmp_path)
    candidate = deepcopy(reference)
    candidate[identity] = "different"
    with pytest.raises(ValueError):
        compare(reference, candidate)


def test_formal_receipt_requires_nonempty_complete_final_proof():
    successful = (
        "Found 1746 $equiv cells in equiv:\n"
        "  Of those cells 1746 are proven and 0 are unproven.\n"
        "  Equivalence successfully proven!\n"
    )
    assert proven_points(successful) == 1746
    for unsupported in (
        successful.replace("1746", "0"),
        successful.replace("0 are unproven", "1 are unproven"),
        "Yosys started but never reported equivalence",
        successful + "Of those cells 3 are proven and 4 are unproven.",
    ):
        with pytest.raises(ValueError, match="complete nonempty"):
            proven_points(unsupported)
