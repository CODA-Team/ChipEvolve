import json

import pytest
from eda_toolkits.objectives import (
    SCHEMA,
    append_objective,
    bind_task_objective,
    condition_id,
    file_sha256,
    load_objective,
    objective_id,
    objective_messages,
    require_same_conditions,
    verify_conditions,
)


@pytest.fixture
def objective(tmp_path):
    lib, sdc = tmp_path / "FF.lib", tmp_path / "common.sdc"
    lib.write_text("nom_voltage : 0.77;")
    sdc.write_text("set_cmd_units -time ns\ncreate_clock -period 0.31 clk")
    value = {
        "schema_version": SCHEMA,
        "design_id": "example",
        "reference_run_id": "run-reference",
        "conditions": {
            "libraries": [{"path": str(lib), "sha256": file_sha256(lib)}],
            "sdc": {"path": str(sdc), "sha256": file_sha256(sdc)},
            "corner": "FF",
        },
        "constraints": {"power_total_w_max": 0.01, "core_area_um2_max": 100},
    }
    value["objective_id"] = objective_id(value)
    path = tmp_path / "objective.json"
    path.write_text(json.dumps(value))
    return path, value, lib, sdc


def test_frozen_conditions_reject_same_name_library_and_different_sdc(objective):
    path, value, lib, sdc = objective
    assert load_objective(path) == value
    verify_conditions(value, sdc=sdc)
    lib.write_text("nom_voltage : 0.7;")
    with pytest.raises(ValueError, match="file changed"):
        verify_conditions(value)
    lib.write_text("nom_voltage : 0.77;")
    other = sdc.with_name("different.sdc")
    other.write_text("create_clock -period 0.45 clk")
    with pytest.raises(ValueError, match="SDC differs"):
        verify_conditions(value, sdc=other)


def test_changed_limits_and_conditions_have_distinct_identity(objective):
    path, value, _, _ = objective
    changed = json.loads(path.read_text())
    changed["constraints"]["core_area_um2_max"] = 200
    path.write_text(json.dumps(changed))
    with pytest.raises(ValueError, match="changed after"):
        load_objective(path)
    assert objective_id(changed) != value["objective_id"]
    assert condition_id(changed) == condition_id(value)
    changed["conditions"]["sdc"]["sha256"] = "different constraints"
    assert condition_id(changed) != condition_id(value)
    require_same_conditions(
        {"condition_id": condition_id(value)}, {"condition_id": condition_id(value)}
    )
    with pytest.raises(ValueError, match="different shared conditions"):
        require_same_conditions(
            {"condition_id": condition_id(value)},
            {"condition_id": condition_id(changed)},
        )


def test_prompt_and_replay_request_receive_goal_without_mutating_native(
    objective, monkeypatch
):
    path, value, _, _ = objective
    payload = {"model": "test", "messages": [{"role": "user", "content": "native"}]}
    monkeypatch.delenv("EDA_PLATFORM_OBJECTIVE", raising=False)
    assert append_objective("native") == "native"
    assert objective_messages(payload) is payload
    monkeypatch.setenv("EDA_PLATFORM_OBJECTIVE", str(path))
    received = objective_messages(payload)
    assert len(payload["messages"]) == 1
    assert value["objective_id"] in received["messages"][-1]["content"]
    assert "native search, scoring and promotion" in append_objective("native")
    assert append_objective("native").startswith("native")


def test_task_uses_existing_public_fields_and_rejects_wrong_design(
    objective, monkeypatch
):
    path, value, _, _ = objective
    spec = {"design_id": "example", "labels": {}, "inputs": {}, "staged_inputs": []}
    bind_task_objective(spec, path)
    assert spec["labels"]["objective_id"] == value["objective_id"]
    assert spec["staged_inputs"][0]["source"] == str(path)
    assert spec["inputs"]["shared_objective_path"] == "inputs/shared-objective.json"
    spec["design_id"] = "other-design"
    with pytest.raises(ValueError, match="different design"):
        bind_task_objective(spec, path)
    changed = json.loads(path.read_text())
    changed["constraints"]["power_total_w_max"] = 0.02
    changed["objective_id"] = objective_id(changed)
    other = path.with_name("other-objective.json")
    other.write_text(json.dumps(changed))
    monkeypatch.setenv("EDA_PLATFORM_OBJECTIVE", str(other))
    spec["design_id"] = "example"
    with pytest.raises(ValueError, match="different shared objectives"):
        bind_task_objective(spec, path)
