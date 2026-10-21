"""Paper lineage must preserve negative branches and real conditions."""

import json

import pytest

from admin.paper_relay_paths import attach_deltas, measured_node


def frame(path, **updates):
    value = {
        "design_id": "gcd",
        "run_id": "run-one",
        "condition_id": "condition",
        "objective_id": "objective",
        "metrics": {
            "finish__power__total": 0.001,
            "finish__design__instance__area": 40,
            "finish__timing__setup__ws": -0.05,
            "finish__timing__hold__ws": 0.02,
        },
        "route_drc": 3,
    }
    value.update(updates)
    path.write_text(json.dumps(value))


def test_negative_result_and_unknown_facts_are_not_replaced_with_passes(tmp_path):
    path = tmp_path / "result.json"
    frame(path)
    row = measured_node(
        path, design="gcd", pdk="asap7", node="bad", agent="ECO", decision="rejected"
    )
    assert row["power_mw"] == 1
    assert row["setup_ws_ps"] == -50 and row["hold_ws_ps"] == 20
    assert row["setup_wns_ps"] == -50 and row["hold_wns_ps"] == 0
    assert row["route_drc"] == 3 and row["fanout_violations"] == ""
    assert row["decision"] == "rejected"


def test_changed_curated_result_cannot_be_silently_exported(tmp_path):
    path = tmp_path / "result.json"
    frame(path)
    with pytest.raises(ValueError, match="Curated source changed"):
        measured_node(
            path,
            design="gcd",
            pdk="asap7",
            node="one",
            agent="Goal",
            decision="",
            expected_sha256="wrong",
        )


def test_deltas_require_actual_parent_and_same_measurement_conditions(tmp_path):
    path = tmp_path / "result.json"
    frame(path)
    parent = measured_node(
        path, design="gcd", pdk="asap7", node="parent", agent="DPL", decision=""
    )
    child = dict(
        parent, node="child", parent="parent", power_mw=0.8, instance_area_um2=36
    )
    attach_deltas([parent, child])
    assert child["parent_power_change_pct"] == pytest.approx(-20)
    assert child["parent_area_change_pct"] == pytest.approx(-10)
    child.update(condition_id="different")
    attach_deltas([parent, child])
    assert child["same_condition_parent"] is False
    assert child["parent_power_change_pct"] == ""
    child["parent"] = "nonexistent"
    with pytest.raises(ValueError, match="actual exported measurement"):
        attach_deltas([parent, child])


def test_ibex_terminal_proof_error_does_not_remain_pending_or_become_adoption(tmp_path):
    from admin.paper_relay_paths import ibex_validation_state

    assert ibex_validation_state(tmp_path, "candidate") is None
    (tmp_path / "ibex-native-continuation-terminal-error.json").write_text(
        json.dumps(
            {"type": "RuntimeError", "detail": "Original proof budget exhausted"}
        )
    )
    state = ibex_validation_state(tmp_path, "candidate")
    assert "not adopted" in state and "did not pass/finish" in state


def test_ibex_full_proof_alone_cannot_be_reported_as_adopted(tmp_path):
    from admin.paper_relay_paths import ibex_validation_state

    case = tmp_path / "runtime/experiments/ibex"
    proof = (
        case / "a29-ibex-ip3-final-cell-variant-proof-r1/final-functional-proof.json"
    )
    proof.parent.mkdir(parents=True)
    value = {
        "passed": True,
        "candidate_sha256": "candidate",
        "proof": {
            "proven_points": 106,
            "proven_partitions": 2046,
            "unproven_points": 0,
        },
    }
    proof.write_text(json.dumps(value))
    assert "not yet established" in ibex_validation_state(tmp_path, "candidate")
    validation = case / "a29-ibex-ip3-final-delivery-replay-r3/validation.json"
    validation.parent.mkdir()
    validation.write_text(
        json.dumps(
            {
                "result_sha256": "candidate",
                "passed": True,
                "replay_exact": True,
                "sdk_identity_passed": True,
            }
        )
    )
    pointer = tmp_path / "runtime/designs/ibex/incumbent.json"
    pointer.parent.mkdir(parents=True)
    pointer.write_text(json.dumps({"result_sha256": "candidate"}))
    assert "validated and adopted" in ibex_validation_state(tmp_path, "candidate")
    value["proof"]["proven_points"] = 105
    proof.write_text(json.dumps(value))
    assert "not adopted" in ibex_validation_state(tmp_path, "candidate")
