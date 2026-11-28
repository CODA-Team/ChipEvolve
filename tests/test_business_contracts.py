"""Business readers fail on malformed inputs while retaining original evidence."""

import hashlib
import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest
from eda_toolkits.objectives import condition_id, objective_id

from chip_evolve.contracts import (
    BusinessInputError,
    CandidateCollection,
    PhysicalResult,
)
from chip_evolve.result_io import load_physical_result, load_result, wire_object


def result_file(root: Path, name: str = "baseline", power: float = 1.0) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    lib, sdc = root / "library.lib", root / "design.sdc"
    lib.write_text("fixed library\n")
    sdc.write_text("create_clock -period 0.5 clk\n")

    def sha(p):
        return hashlib.sha256(p.read_bytes()).hexdigest()

    goal = {
        "schema_version": "chip-evolve.objective.v1",
        "design_id": "gcd",
        "reference_run_id": "run-baseline",
        "conditions": {
            "libraries": [{"path": str(lib), "sha256": sha(lib)}],
            "sdc": {"path": str(sdc), "sha256": sha(sdc)},
            "corner": "typical",
            "clock_period_ns": 0.5,
        },
        "constraints": {
            "setup_tns_ns_min": 0,
            "hold_tns_ns_min": 0,
            "max_slew_violations": 0,
            "max_cap_violations": 0,
            "placement_violations": 0,
            "route_drc": 0,
            "power_total_w_max": 2.0,
            "cell_area_um2_max": 20,
            "core_area_um2_max": 30,
            "die_area_um2_max": 40,
        },
    }
    goal["objective_id"] = objective_id(goal)
    objective = root / "objective.json"
    objective.write_text(json.dumps(goal))
    directory = root / name
    directory.mkdir(exist_ok=True)
    files = {}
    for ext in ("odb", "sdc", "v", "def", "spef", "metrics"):
        path = directory / ("final." + ext)
        path.write_text("frozen " + ext)
        files[ext] = str(path)
    value = {
        "design_id": "gcd",
        "run_id": "run-" + name,
        "physical_run_id": "run-physical-" + name,
        "objective": str(objective),
        "objective_id": goal["objective_id"],
        "condition_id": condition_id(goal),
        "route_drc": 0,
        "conditions": {"corner": "typical", "clock_period_ns": 0.5},
        "files": files,
        "snapshot_ids": {},
        "exports": {},
        "metrics": {
            "finish__timing__setup__tns": 0,
            "finish__timing__setup__ws": 0.1,
            "finish__timing__hold__tns": 0,
            "finish__timing__hold__ws": 0.2,
            "finish__power__total": power,
            "finish__design__instance__area": 10,
            "finish__design__core__area": 20,
            "finish__design__die__area": 30,
            "finish__timing__drv__max_slew": 0,
            "finish__timing__drv__max_cap": 0,
            "finish__timing__drv__max_fanout": 0,
            "design__violations": 0,
        },
    }
    result = directory / "result.json"
    result.write_text(json.dumps(value, indent=4) + "\n")
    return result


def test_physical_model_is_immutable_and_wire_bytes_are_untouched(tmp_path):
    path = result_file(tmp_path)
    before = path.read_bytes()
    result = load_physical_result(path)
    assert isinstance(result, PhysicalResult)
    assert result.metrics.power_w == 1.0
    assert result.files.require("odb").is_file()
    assert result.origin.sha256 == hashlib.sha256(before).hexdigest()
    assert wire_object(result.wire) == json.loads(before)
    with pytest.raises(FrozenInstanceError):
        result.run_id = "changed"
    with pytest.raises(TypeError):
        result.wire["run_id"] = "changed"
    assert path.read_bytes() == before


@pytest.mark.parametrize(
    "value", [None, True, "1", float("nan"), float("inf"), float("-inf"), -0.1]
)
def test_bad_power_fails_at_load_boundary(tmp_path, value):
    path = result_file(tmp_path)
    frame = json.loads(path.read_text())
    frame["metrics"]["finish__power__total"] = value
    path.write_text(json.dumps(frame))
    with pytest.raises(BusinessInputError, match="finish__power__total"):
        load_result(path)


@pytest.mark.parametrize(
    "field", ["design_id", "run_id", "objective", "metrics", "route_drc"]
)
def test_missing_fields_never_escape_as_keyerror(tmp_path, field):
    path = result_file(tmp_path)
    frame = json.loads(path.read_text())
    del frame[field]
    path.write_text(json.dumps(frame))
    with pytest.raises(BusinessInputError, match=field):
        load_result(path)


@pytest.mark.parametrize("count", [True, "0", None, -1, 0.5])
def test_invalid_counts_rejected(tmp_path, count):
    path = result_file(tmp_path)
    frame = json.loads(path.read_text())
    frame["route_drc"] = count
    path.write_text(json.dumps(frame))
    with pytest.raises(BusinessInputError, match="route_drc"):
        load_result(path)


def test_missing_optional_fact_stays_unknown_but_explicit_null_is_rejected(tmp_path):
    path = result_file(tmp_path)
    frame = json.loads(path.read_text())
    del frame["metrics"]["finish__timing__drv__max_fanout"]
    path.write_text(json.dumps(frame))
    assert load_physical_result(path).metrics.fanout is None
    frame["metrics"]["finish__timing__drv__max_fanout"] = None
    path.write_text(json.dumps(frame))
    with pytest.raises(BusinessInputError, match="max_fanout"):
        load_result(path)


def test_integral_legacy_count_and_finite_infeasible_result_remain_loadable(tmp_path):
    path = result_file(tmp_path, power=3.0)
    frame = json.loads(path.read_text())
    frame["route_drc"] = 2.0
    path.write_text(json.dumps(frame))
    result = load_result(path)
    assert not isinstance(result, CandidateCollection)
    assert result.route_drc == 2
    assert result.metrics.power_w == 3.0


@pytest.mark.parametrize("field", ["constraints", "conditions"])
def test_objective_shape_checked_before_downstream_consumption(tmp_path, field):
    path = result_file(tmp_path)
    frame = json.loads(path.read_text())
    objective = Path(frame["objective"])
    goal = json.loads(objective.read_text())
    del goal[field]
    goal["objective_id"] = objective_id(goal)
    objective.write_text(json.dumps(goal))
    with pytest.raises(BusinessInputError, match=field):
        load_result(path)


def test_unknown_schema_and_wrong_goal_identity_fail_closed(tmp_path):
    path = result_file(tmp_path)
    frame = json.loads(path.read_text())
    frame["schema_version"] = "unknown.v9"
    path.write_text(json.dumps(frame))
    with pytest.raises(BusinessInputError, match="schema"):
        load_result(path)
    del frame["schema_version"]
    frame["objective_id"] = "0" * 64
    path.write_text(json.dumps(frame))
    with pytest.raises(BusinessInputError, match="identity_mismatch"):
        load_result(path)


def test_typed_policy_matches_legacy_seven_deltas_and_limits(tmp_path):
    from chip_evolve.comparison_facts import compare, compare_results
    from chip_evolve.result_io import load_single_result
    from chip_evolve.selection import result_violations, violations

    old = result_file(tmp_path, "reference")
    new = result_file(tmp_path, "candidate", 2.5)
    reference, candidate = load_physical_result(old), load_physical_result(new)
    assert compare_results(reference, candidate) == compare(
        wire_object(reference.wire), wire_object(candidate.wire)
    )
    assert (
        result_violations(candidate)
        == violations(wire_object(candidate.wire))
        == ["power_total_w_max"]
    )
    assert load_single_result(new).metrics.power_w == 2.5


def test_collection_checks_bytes_summaries_and_explicit_branch(tmp_path):
    from chip_evolve.candidates import deliver_candidates
    from chip_evolve.result_io import load_single_result

    one = result_file(tmp_path, "one")
    two = result_file(tmp_path, "two", 1.5)
    target = tmp_path / "collection"
    target.mkdir()
    deliver_candidates(target, [one, two])
    path = target / "result.json"
    assert len(load_result(path).candidates) == 2
    with pytest.raises(BusinessInputError, match="candidate_collection"):
        load_single_result(path)
    two.write_text(two.read_text() + " ")
    with pytest.raises(BusinessInputError, match="sha256"):
        load_result(path)


def test_typed_handoff_preserves_legacy_wire_and_roles(tmp_path):
    from types import SimpleNamespace

    from chip_evolve.artifact_inputs import build_handoff, input_contract
    from chip_evolve.contracts import DplInputs, EcoInputs, FlowSourceInputs, GoalInputs
    from tests.test_professional_handoff_contract import registered_source

    path = result_file(tmp_path)
    frame = json.loads(path.read_text())
    client, _ = registered_source(tmp_path, frame)
    path.write_text(json.dumps(frame))
    source = load_physical_result(path)
    jobs = SimpleNamespace(design_id="gcd", client=client)
    for receiver, variant in (
        ("eco", EcoInputs),
        ("goal", GoalInputs),
        ("dpl", DplInputs),
        ("flow", FlowSourceInputs),
    ):
        handoff = build_handoff(
            jobs,
            source,
            receiver,
            flow_recipe="source" if receiver == "flow" else "legacy",
        )
        assert isinstance(handoff.inputs, variant)
        assert wire_object(handoff.wire) == input_contract(
            jobs,
            frame,
            receiver,
            flow_recipe="source" if receiver == "flow" else "legacy",
        )


def context_file(root, source):
    packet = {
        "schema_version": "chip-evolve.design-context.v1",
        "scope": {
            "design_id": source.design_id,
            "run_id": source.run_id,
            "snapshot_id": "snapshot-db",
        },
        "confirmed_facts": [{"text": "Measured fact", "evidence_ids": ["e"]}],
        "evidence": [
            {
                "evidence_id": "e",
                "scope": {
                    "design_id": source.design_id,
                    "run_id": source.run_id,
                    "snapshot_id": "snapshot-db",
                },
                "locator": {"uri": "artifact://measured"},
                "source_hash": "a" * 64,
            }
        ],
    }
    packet["context_id"] = hashlib.sha256(
        json.dumps(packet, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    path = root / "context.json"
    path.write_text(json.dumps(packet))
    return path


@pytest.mark.parametrize(
    "mutation", ["evidence", "scope", "citation", "locator", "hash"]
)
def test_bad_context_fails_with_field_error(tmp_path, mutation):
    from chip_evolve.result_io import load_context_ref

    source = load_physical_result(result_file(tmp_path))
    path = context_file(tmp_path, source)
    value = json.loads(path.read_text())
    if mutation == "evidence":
        value["evidence"] = {}
    elif mutation == "scope":
        del value["scope"]["run_id"]
    elif mutation == "citation":
        value["confirmed_facts"][0]["evidence_ids"] = ["missing"]
    elif mutation == "locator":
        value["evidence"][0]["locator"] = []
    else:
        value["context_id"] = "a" * 64
    path.write_text(json.dumps(value))
    with pytest.raises(BusinessInputError, match=r"\$\."):
        load_context_ref(path)
