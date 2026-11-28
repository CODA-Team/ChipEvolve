"""Recovery keeps computation identity and formal checks reject unsafe models."""

from types import SimpleNamespace

import pytest

from chip_evolve.core.config import business_lock, read, write
from chip_evolve.execution.delivery import checkpoint, finish
from chip_evolve.core.jobs import Jobs, digest
from chip_evolve.execution.logic import interface_and_physical
from chip_evolve.workflow.recovery import recover
from tests.test_local_business import deployment


def test_unfinished_recovery_rejects_replaced_image_before_delivery(
    tmp_path, monkeypatch
):
    d = deployment(tmp_path)
    folder = d.experiment("gcd", "image-recovery")
    image = tmp_path / "pinned.sif"
    image.write_bytes(b"approved image")
    sha = digest(image)
    d.value.update(runtime={"image": str(image)}, toolchain={"image_sha256": sha})
    write(
        folder / "request.json",
        {"design": "gcd", "capability": "goal", "image_sha256": sha},
    )
    write(folder / "delivery-checkpoint.json", {"input_hashes": {}})
    monkeypatch.setattr(
        "chip_evolve.execution.delivery.finish",
        lambda *_: pytest.fail("An unfinished delivery reached the EDA boundary"),
    )
    image.write_bytes(b"different bytes at the original path")
    with pytest.raises(ValueError, match="Image differs from its pinned identity"):
        recover(d, "gcd", folder.name)
    d.value["toolchain"]["image_sha256"] = digest(image)
    with pytest.raises(ValueError, match="image differs from the original request"):
        recover(d, "gcd", folder.name)

    write(folder / "status.json", {"status": "succeeded"})
    result = {"design_id": "gcd", "run_id": "original-result"}
    write(folder / "result.json", result)
    assert recover(d, "gcd", folder.name) == result


def test_resume_never_restarts_an_unfinished_native_search(tmp_path):
    d = deployment(tmp_path)
    folder = d.experiment("aes", "unfinished")
    write(
        folder / "request.json",
        {"design": "aes", "capability": "goal", "operation": "evolve"},
    )
    write(folder / "campaign/parent.json", {"source_commit": "baseline"})
    write(folder / "status.json", {"status": "failed", "detail": "original"})
    with pytest.raises(ValueError, match="no completed delivery checkpoint"):
        recover(d, "aes", "unfinished")
    assert read(folder / "status.json")["detail"] == "original"


@pytest.mark.parametrize("promoted", [False, True])
def test_recovery_collects_a_finished_goal_search(tmp_path, monkeypatch, promoted):
    d = deployment(tmp_path)
    folder = d.experiment("gcd", "native-finished")
    objective = folder / "objective.json"
    pdk = folder / "pdk"
    pdk.mkdir()
    for name in ("setRC.tcl", "rcx_patterns.rules"):
        (pdk / name).write_text(name)
    write(objective, {"objective_id": "frozen"})
    write(
        folder / "request.json",
        {"design": "gcd", "capability": "goal", "operation": "evolve"},
    )
    write(
        folder / "input-receipt.json",
        {"source_run_id": "reference", "objective": str(objective)},
    )
    write(folder / "profile.json", {"design_id": "gcd", "pdk_root": str(pdk)})
    baseline = folder / "baseline" / "post_route.odb"
    baseline.parent.mkdir()
    baseline.write_bytes(b"baseline")
    write(
        baseline.with_name("baseline.json"),
        {
            "ok": True,
            "checks": [],
            "metrics": {},
            "artifacts": {"checkpoint_post_route_db": str(baseline)},
        },
    )
    campaign = folder / "campaign"
    source = "student-commit" if promoted else "baseline"
    parent = {"source_commit": source, "source_hash": source}
    write(campaign / "parent.json", parent)
    write(campaign / "toolchain.json", {"openroad_version": "registered"})
    selected = baseline
    original = baseline
    if promoted:
        parent["parent_id"] = "round_001:student_2"
        write(campaign / "parent.json", parent)
        selected = campaign / "parents" / source / "design_checkpoint.odb"
        selected.parent.mkdir(parents=True)
        selected.write_bytes(b"promoted")
        candidate = campaign / "rounds/round_001/students/student_2/artifacts"
        original = candidate / "post_route.odb"
        write(
            candidate / "candidate.json",
            {
                "source_commit": source,
                "artifacts": {"checkpoint_post_route_db": str(original)},
            },
        )
        original.write_bytes(selected.read_bytes())
        other = folder / "operations" / "wrong-student"
        write(
            other / "leaf.json",
            {
                "request": {"operation": "physical"},
                "output_files": {str(folder / "other.odb"): digest(selected)},
            },
        )
        write(other / "execution.json", {"run": {"run_id": "wrong-producer"}})
    operation = folder / "operations" / "physical"
    write(
        operation / "leaf.json",
        {
            "request": {"operation": "physical"},
            "output_files": {str(original): digest(selected)},
        },
    )
    write(operation / "execution.json", {"run": {"run_id": "native-producer"}})
    seen = []

    def qualify(jobs, odb, producer, goal, model):
        seen.append((odb, producer, goal, model))
        return {"design_id": "gcd", "run_id": "measured"}

    monkeypatch.setattr("chip_evolve.execution.physical.qualify", qualify)
    monkeypatch.setattr("chip_evolve.execution.delivery.maybe_collect", lambda *a: None)
    monkeypatch.setattr(
        "chip_evolve.workflow.goal.invoke", lambda *a: pytest.fail("native search restarted")
    )

    result = recover(d, "gcd", "native-finished")
    assert result["native_method"]["parent"] == parent
    assert recover(d, "gcd", "native-finished") == result
    assert seen == [(selected, "native-producer", objective, pdk)]


def test_recovery_keeps_native_verdict_and_failure_history(tmp_path, monkeypatch):
    d = deployment(tmp_path)
    folder = d.experiment("aes", "completed")
    odb, objective, pdk = (
        folder / "native.odb",
        folder / "objective.json",
        folder / "pdk",
    )
    odb.write_bytes(b"native")
    write(objective, {"goal": "unchanged"})
    pdk.mkdir()
    for name in ("setRC.tcl", "rcx_patterns.rules"):
        (pdk / name).write_text(name)
    write(folder / "request.json", {"design": "aes", "capability": "goal"})
    write(
        folder / "status.json", {"status": "failed", "detail": "delivery interrupted"}
    )
    checkpoint(
        folder,
        design_id="aes",
        odb=odb,
        producer="actual-native",
        objective=objective,
        pdk=pdk,
        native_method={"kind": "native-search"},
    )
    seen = []

    def qualify(jobs, selected, producer, goal, model):
        seen.append((selected.read_bytes(), producer))
        return {"run_id": "same-measurement", "design_id": "aes"}

    monkeypatch.setattr("chip_evolve.execution.physical.qualify", qualify)
    first = recover(d, "aes", "completed")
    assert first["native_method"] == {"kind": "native-search"}
    assert (
        read(folder / "status-before-recovery.json")["detail"] == "delivery interrupted"
    )
    assert not read(folder / "delivery-recovery.json")["native_search_restarted"]
    assert recover(d, "aes", "completed") == first
    odb.write_bytes(b"changed")
    with pytest.raises(ValueError, match="Delivery input changed"):
        recover(d, "aes", "completed")
    with pytest.raises(ValueError, match="Delivery input changed"):
        finish(d, folder)
    assert len(seen) == 1


@pytest.mark.parametrize("capability", ["orfs", "flow", "dpl", "goal", "eco"])
def test_completed_recovery_preserves_handoff_and_validation_hash(
    tmp_path, monkeypatch, capability
):
    d = deployment(tmp_path)
    folder = d.experiment("gcd", "finished")
    write(folder / "request.json", {"design": "gcd", "capability": capability})
    write(folder / "status.json", {"status": "succeeded"})
    frame = {
        "design_id": "gcd",
        "run_id": "immutable-run",
        "exports": {
            "orfs": {"execution": {"wait_seconds": 4.25}},
        },
    }
    if capability == "flow":
        frame = {"design_id": "gcd", "candidate_results": [{"run_id": "candidate"}]}
    path = folder / "result.json"
    write(path, frame)
    validated = digest(path)
    stamp = path.stat().st_mtime_ns
    monkeypatch.setattr(
        "chip_evolve.execution.physical.baseline",
        lambda *a, **k: pytest.fail("repeated physical delivery"),
    )
    monkeypatch.setattr(
        "chip_evolve.workflow.flow.collect_flow",
        lambda *a, **k: pytest.fail("repeated collection"),
    )
    assert recover(d, "gcd", "finished") == frame
    assert digest(path) == validated
    assert path.stat().st_mtime_ns == stamp


def test_completed_recovery_rejects_a_different_requested_goal(tmp_path):
    d = deployment(tmp_path)
    folder = d.experiment("gcd", "wrong-goal")
    goal = tmp_path / "original.json"
    write(goal, {"objective_id": "requested"})
    write(
        folder / "request.json",
        {"design": "gcd", "capability": "orfs", "objective": str(goal)},
    )
    write(folder / "status.json", {"status": "succeeded"})
    write(folder / "result.json", {"design_id": "gcd", "objective_id": "regenerated"})
    before = digest(folder / "result.json")
    with pytest.raises(ValueError, match="original requested objective"):
        recover(d, "gcd", "wrong-goal")
    assert digest(folder / "result.json") == before


def test_changed_staged_bytes_cannot_reuse_a_saved_job(tmp_path, monkeypatch):
    from tests.contract_fixtures import unit_admission

    unit_admission(monkeypatch)
    d = deployment(tmp_path)
    path = tmp_path / "input"
    path.write_bytes(b"first")
    calls = []

    def submit(task, **kwargs):
        calls.append(kwargs)
        return {"run": {"run_id": "existing"}}

    client = SimpleNamespace(
        submit=submit,
        run=lambda _: {"run_id": "existing", "status": "succeeded"},
        artifacts=lambda _: [],
        resources=lambda _: {},
    )
    monkeypatch.setattr("chip_evolve.core.jobs.KernelClient", lambda *args, **kwargs: client)
    jobs = Jobs(d, "aes", tmp_path / "experiment")
    staged = [{"source": str(path), "destination": "inputs/design"}]
    jobs.submit("route", {"adapter": "command"}, staged)
    jobs.submit("route", {"adapter": "command"}, staged)
    assert len(calls) == 1 and calls[0]["idempotent"]
    assert calls[0]["idempotency_key"] == "aes-experiment:route"
    path.write_bytes(b"changed")
    with pytest.raises(ValueError, match="staged content"):
        jobs.submit("route", {"adapter": "command"}, staged)
    assert len(calls) == 1


def test_active_business_driver_cannot_be_recovered_concurrently(tmp_path):
    with (
        business_lock(tmp_path),
        pytest.raises(RuntimeError, match="active business driver"),
        business_lock(tmp_path),
    ):
        pytest.fail("overlapping recovery")
    with business_lock(tmp_path):
        pass


def test_output_model_keeps_functional_cells_and_rejects_connected_physical_cells():
    model = {
        "modules": {
            "any_design": {
                "ports": {"out": {"direction": "output", "bits": [1, 2]}},
                "cells": {
                    "physical": {"type": "FILLER_TECH", "connections": {}},
                    "logic": {"type": "NAND_TECH", "connections": {"Y": [1]}},
                },
            }
        }
    }
    result = interface_and_physical(model, "any_design")
    assert result["zero_port_types"] == ["FILLER_TECH"]
    model["modules"]["any_design"]["cells"]["physical"]["connections"] = {"Y": [1]}
    with pytest.raises(ValueError, match="port connections"):
        interface_and_physical(model, "any_design")


def test_changed_command_fails_before_replacing_original_request(tmp_path, monkeypatch):
    d = deployment(tmp_path)
    d.value["client_python"] = "/python"
    jobs = Jobs(d, "aes", tmp_path)
    monkeypatch.setattr(jobs, "submit", lambda *args, **kwargs: {})
    jobs.command("operation", ["original"])
    with pytest.raises(ValueError, match="saved command"):
        jobs.command("operation", ["changed"])
    assert read(tmp_path / "requests/operation.json")["command"] == ["original"]


def test_validation_children_have_distinct_ef_identities(tmp_path):
    d = deployment(tmp_path)
    first = Jobs(d, "aes", d.state / "experiments/aes/first/logic")
    second = Jobs(d, "aes", d.state / "experiments/aes/second/logic")
    same = Jobs(d, "aes", d.state / "experiments/aes/first/logic")
    assert first.campaign != second.campaign
    assert first.campaign == same.campaign


def test_query_checks_source_values_without_confusing_ws_and_wns(tmp_path, monkeypatch):
    from chip_evolve.workflow.comparisons import METRICS
    from chip_evolve.workflow.validation import query_facts
    from tests.test_local_comparisons import result

    d = deployment(tmp_path)
    d.value["data_url"] = "http://localhost:2"
    frame = result(tmp_path)
    frame["metrics"]["finish__timing__setup__ws"] = 0.025
    frame["snapshot_ids"] = {"orfs": "snapshot", "opensta": "analysis-supplement"}
    canonical = [
        {
            "raw_key": key,
            "raw_value": frame["metrics"][key],
            "value": frame["metrics"][key],
        }
        for key in METRICS[:-2]
    ]
    canonical.append(
        {"raw_key": "finish__timing__setup__ws", "raw_value": 0.025, "value": 0}
    )
    response = {
        "data": {
            "metrics": canonical,
            "raw_metrics": [
                {"raw_key": key, "value": frame["metrics"][key]} for key in METRICS[-2:]
            ],
        }
    }
    client = SimpleNamespace(
        resolve_scope=lambda **kwargs: {
            "scope": {}
            if kwargs["snapshot_id"] == "analysis-supplement"
            and kwargs.get("origin", "flow") == "flow"
            else {"design_id": frame["design_id"], "run_id": frame["run_id"]}
        },
        get_metrics=lambda **kwargs: response,
    )
    monkeypatch.setattr("chip_evolve.facts.design_facts.EdaAiClient", lambda **kwargs: client)
    query_facts(d, frame)
    response["data"]["raw_metrics"][0]["value"] += 1
    with pytest.raises(ValueError, match="DF metrics differ"):
        query_facts(d, frame)


def test_validation_failure_is_visible_and_original_evidence_is_preserved(
    tmp_path, monkeypatch
):
    from chip_evolve.workflow.validation import validate

    d = deployment(tmp_path)
    candidate, reference = tmp_path / "candidate.json", tmp_path / "reference.json"
    from tests.test_business_contracts import result_file

    measured = read(result_file(tmp_path / "valid-result"))
    write(candidate, measured)
    write(reference, measured)
    before = candidate.read_bytes()

    def fail(*args):
        raise RuntimeError("Original EF proof failed")

    monkeypatch.setattr("chip_evolve.workflow.validation._validate", fail)
    with pytest.raises(RuntimeError, match="Original EF proof"):
        validate(d, candidate, reference, "proof")
    assert read(tmp_path / "experiments/gcd/proof/status.json")["status"] == "failed"
    assert candidate.read_bytes() == before
