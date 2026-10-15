"""A counterfactual must preserve inputs; native ranking is not final PPA."""

from copy import deepcopy

import pytest

from admin.proxy_final_audit import flow_deployment, matched_inputs, rank_reversals
from admin.test_local_business import deployment
from admin.test_local_comparisons import result
from chip_evolve.config import read, write


def test_declared_recipe_change_cannot_hide_a_changed_design_or_sdc():
    before = {"rtl": "actual-rtl-sha", "sdc": "actual-sdc-sha", "SYNTH_USE_SYN": 1}
    after = dict(before, SYNTH_USE_SYN=0)
    assert matched_inputs(before, after, {"SYNTH_USE_SYN"}) == ["SYNTH_USE_SYN"]
    after["sdc"] = "changed-period"
    with pytest.raises(ValueError, match="sdc"):
        matched_inputs(before, after, {"SYNTH_USE_SYN"})
    with pytest.raises(ValueError, match="no actual"):
        matched_inputs(before, before, {"SYNTH_USE_SYN"})


def test_control_keeps_original_libraries_objective_limits_and_other_designs(tmp_path):
    d = deployment(tmp_path)
    d.value["designs"]["registered-design"] = {
        "libraries": [{"path": "fixed.lib", "sha256": "original"}],
        "goal_limits": {"power_total_w_max": 1.0},
    }
    d.value["designs"]["registered-design"]["baseline_overrides"] = (
        "export OTHER_VT = LVT SLVT\n"
    )
    original = deepcopy(d.value)
    new = flow_deployment(d, "registered-design", "yosys", {"SYNTH_USE_SYN": "0"})
    assert d.value == original
    observed = read(new.path)
    before = observed["designs"]["registered-design"].pop("baseline_overrides")
    assert before == "export OTHER_VT = LVT SLVT\nexport SYNTH_USE_SYN = 0\n"
    expected = deepcopy(original)
    expected["designs"]["registered-design"].pop("baseline_overrides")
    assert observed == expected
    with pytest.raises(ValueError, match="already frozen"):
        flow_deployment(d, "registered-design", "yosys", {"SYNTH_USE_SYN": "1"})


def test_rank_reversal_exposes_proxy_disagreement_and_keeps_ties_out():
    rows = [
        {"name": "framework", "hpwl_um": 100, "power_w": 1.0},
        {"name": "student", "hpwl_um": 90, "power_w": 1.1},
        {"name": "power-tie", "hpwl_um": 95, "power_w": 1.0},
    ]
    assert rank_reversals(rows) == [
        {"lower_hpwl": "student", "lower_final_power": "framework"},
        {"lower_hpwl": "student", "lower_final_power": "power-tie"},
    ]


def test_new_physical_control_keeps_the_frozen_reference_objective(
    tmp_path, monkeypatch
):
    from admin import proxy_final_audit as audit

    d = deployment(tmp_path)
    frame = result(tmp_path)
    d.value["designs"][frame["design_id"]] = {}
    reference = tmp_path / "reference.json"
    write(reference, frame)
    received = []

    def physical(deployment, design, experiment, seconds, *, objective):
        received.append((design, objective, seconds))
        return {**frame, "run_id": "control"}

    monkeypatch.setattr(audit, "baseline", physical)
    monkeypatch.setattr(audit, "query_facts", lambda *_: {"verified": True})
    audit.flow_control(d, reference, "control", {"SYNTH_USE_SYN": "0"}, 7200)
    assert received == [(frame["design_id"], tmp_path / "objective.json", 7200)]
    request = read(
        tmp_path / "experiments" / frame["design_id"] / "control/request.json"
    )
    assert request["design"] == frame["design_id"]
    assert request["reference_sha256"] == audit.digest(reference)


def test_client_failure_is_recorded_instead_of_leaving_business_in_progress(
    tmp_path, monkeypatch
):
    from admin import proxy_final_audit as audit

    d = deployment(tmp_path)
    reference = tmp_path / "reference.json"
    write(reference, {"design_id": "aes"})

    def interrupted(*_):
        (tmp_path / "experiments/aes/probe").mkdir(parents=True)
        raise TimeoutError("snapshot import response timed out")

    monkeypatch.setattr(audit, "dpl_control", interrupted)
    monkeypatch.setattr(
        "sys.argv",
        [
            "audit",
            "--config",
            str(d.path),
            "--reference",
            str(reference),
            "dpl",
            "--key",
            "probe",
            "--native",
            "native",
            "--student",
            "1",
        ],
    )
    with pytest.raises(TimeoutError):
        audit.main()
    assert read(tmp_path / "experiments/aes/probe/status.json") == {
        "status": "failed",
        "error_type": "TimeoutError",
        "detail": "snapshot import response timed out",
    }
