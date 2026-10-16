"""Recovery keeps computation identity and formal checks reject unsafe models."""

from types import SimpleNamespace

import pytest

from admin.test_local_business import deployment
from chip_evolve.config import business_lock, read, write
from chip_evolve.delivery import checkpoint, finish, recover
from chip_evolve.jobs import Jobs
from chip_evolve.logic import interface_and_physical


def test_resume_never_restarts_an_unfinished_native_search(tmp_path):
    d = deployment(tmp_path)
    folder = d.experiment("aes", "unfinished")
    write(folder / "request.json", {"design": "aes", "capability": "goal"})
    write(folder / "status.json", {"status": "failed", "detail": "original"})
    with pytest.raises(ValueError, match="no completed delivery checkpoint"):
        recover(d, "aes", "unfinished")
    assert read(folder / "status.json")["detail"] == "original"


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
        return {"run_id": "same-measurement"}

    monkeypatch.setattr("chip_evolve.physical.qualify", qualify)
    first = recover(d, "aes", "completed")
    assert first["native_method"] == {"kind": "native-search"}
    assert (
        read(folder / "status-before-recovery.json")["detail"] == "delivery interrupted"
    )
    assert not read(folder / "delivery-recovery.json")["native_search_restarted"]
    odb.write_bytes(b"changed")
    with pytest.raises(ValueError, match="Delivery input changed"):
        finish(d, folder)
    assert len(seen) == 1


def test_changed_staged_bytes_cannot_reuse_a_saved_job(tmp_path, monkeypatch):
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
    monkeypatch.setattr("chip_evolve.jobs.KernelClient", lambda *args, **kwargs: client)
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
    from admin.test_local_comparisons import result
    from chip_evolve.comparisons import METRICS
    from chip_evolve.validation import query_facts

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
    monkeypatch.setattr("chip_evolve.validation.EdaAiClient", lambda **kwargs: client)
    query_facts(d, frame)
    response["data"]["raw_metrics"][0]["value"] += 1
    with pytest.raises(ValueError, match="DF metrics differ"):
        query_facts(d, frame)


def test_validation_failure_is_visible_and_original_evidence_is_preserved(
    tmp_path, monkeypatch
):
    from chip_evolve.validation import validate

    d = deployment(tmp_path)
    candidate, reference = tmp_path / "candidate.json", tmp_path / "reference.json"
    write(candidate, {"design_id": "aes"})
    write(reference, {"design_id": "aes"})

    def fail(*args):
        raise RuntimeError("Original EF proof failed")

    monkeypatch.setattr("chip_evolve.validation._validate", fail)
    with pytest.raises(RuntimeError, match="Original EF proof"):
        validate(d, candidate, reference, "proof")
    assert read(tmp_path / "experiments/aes/proof/status.json")["status"] == "failed"
    assert read(candidate) == {"design_id": "aes"}
