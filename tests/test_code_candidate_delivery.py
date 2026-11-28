"""Completed Code branches retain native verdicts and use common EF delivery."""

import json
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from chip_evolve.facts import code_evidence
from chip_evolve.execution import delivery
from chip_evolve.workflow import recovery
from chip_evolve.core.config import read, write
from chip_evolve.core.jobs import digest
from chip_evolve.core.lifecycle import WorkPending
from tests.test_adoption_consistency import frame_at
from tests.test_local_business import deployment


def inputs(tmp_path, monkeypatch):
    d = deployment(tmp_path)
    d.value["designs"]["gcd"] = {"nickname": "gcd", "top": "gcd_top", "platform": "pdk"}
    experiment = tmp_path / "professional"
    experiment.mkdir()
    result_path = frame_at(experiment, "selected")
    selected = read(result_path)
    write(experiment / "result.json", selected)
    write(experiment / "status.json", {"status": "succeeded"})
    write(experiment / "request.json", {"capability": "dpl", "operation": "evolve"})
    profile = {
        "design": "gcd",
        "platform": "pdk",
        "case": "gcd_case",
        "experiment_id": "native-experiment",
        "flow_variant": experiment.name,
        "operations_root": str(experiment / "operations"),
    }
    write(experiment / "profile.json", profile)
    rows, runs, artifacts = [], {}, {}
    for number in range(2):
        odb = experiment / f"candidate-{number}.odb"
        odb.write_bytes(f"checkpoint-{number}".encode())
        native = experiment / f"candidate-{number}.json"
        write(native, {"original_local_verdict": "not-promoted"})
        rows.append(
            {
                "candidate_id": f"candidate-{number}",
                "checkpoint": str(odb),
                "checkpoint_sha256": digest(odb),
                "native_record": {"path": str(native), "sha256": digest(native)},
                "eligible_for_common_measurement": True,
                "native_artifact_problems": [],
            }
        )
        folder = experiment / "operations" / str(number)
        rid = f"native-{number}"
        write(
            folder / "leaf.json",
            {
                "request": {"operation": "baseline"},
                "exit_code": 0,
                "output_files": {str(odb): digest(odb)},
            },
        )
        write(
            folder / "execution.json", {"run": {"run_id": rid, "status": "succeeded"}}
        )
        runs[rid] = {
            "run_id": rid,
            "status": "succeeded",
            "project_id": "dplevolve-common-u3",
            "design_id": "gcd",
            "experiment_id": "native-experiment",
        }
        artifacts[rid] = [
            {
                "kind": "raw_design_database",
                "artifact_id": "artifact-" + str(number),
                "store_key": "outputs/2/" + odb.name,
                "sha256": digest(odb),
            }
        ]
    delivery.checkpoint(
        experiment,
        design_id="gcd",
        odb=experiment / "candidate-0.odb",
        producer="native-0",
        objective=Path(selected["objective"]),
        source=result_path,
        native_method={"kind": "native-search"},
    )
    exported = {
        "capability": "dpl",
        "design": "gcd",
        "platform": "pdk",
        "case": "gcd_case",
        "round_id": experiment.name,
        "candidates": rows,
    }
    exports, measured = [], []

    def export(deployment, experiment, capability, output):
        exports.append(capability)
        write(output, exported)

    def finish(deployment, child):
        measured.append(child)
        value = {
            **selected,
            "run_id": "common-" + child.name,
            "native_method": read(child / "delivery-checkpoint.json")["native_method"],
        }
        write(child / "result.json", value)
        return value

    client = SimpleNamespace(
        run=lambda rid: runs[rid], artifacts=lambda rid: artifacts[rid]
    )
    monkeypatch.setattr(code_evidence, "_export", export)
    monkeypatch.setattr(delivery, "Jobs", lambda *args: SimpleNamespace(client=client))
    monkeypatch.setattr(delivery, "finish", finish)
    return d, experiment, selected, exported, runs, artifacts, exports, measured


def collect(data):
    d, experiment, selected, *_ = data
    return delivery.collect_code_candidates(
        d, experiment, selected, read(experiment / "delivery-checkpoint.json")
    )


def test_all_additional_complete_candidates_are_delivered_without_native_promotion(
    tmp_path, monkeypatch
):
    data = inputs(tmp_path, monkeypatch)
    _, experiment, _, exported, _, _, exports, measured = data
    invalid = {
        **exported["candidates"][1],
        "candidate_id": "source-only",
        "eligible_for_common_measurement": False,
        "native_artifact_problems": ["missing_private_binary"],
    }
    exported["candidates"].append(invalid)
    hashes = {
        p: digest(p) for p in [experiment / "result.json", experiment / "status.json"]
    }
    metadata = collect(data)
    index = read(metadata["inventory"]["path"])
    assert [row["status"] for row in index["candidates"]] == [
        "already_delivered",
        "completed",
        "native_rejected",
    ]
    assert len(measured) == 1 and exports == ["dpl"]
    assert measured[0].name.startswith(experiment.name + "--")
    result = read(metadata["additional_results"]["path"])
    assert result["selected_source"] is None and not result["adopted"]
    assert all(digest(p) == sha for p, sha in hashes.items())
    assert collect(data) == metadata
    assert len(measured) == 1 and exports == ["dpl"]
    (experiment / "candidate-1.odb").write_bytes(b"changed")
    with pytest.raises(ValueError, match="changed"):
        collect(data)


@pytest.mark.parametrize("fault", ["wrong_design", "failed_producer", "artifact_hash"])
def test_identity_failure_prevents_any_additional_eda(tmp_path, monkeypatch, fault):
    data = inputs(tmp_path, monkeypatch)
    _, _, _, exported, runs, artifacts, _, measured = data
    if fault == "wrong_design":
        exported["design"] = "foreign"
    elif fault == "failed_producer":
        runs["native-1"]["status"] = "failed"
    else:
        artifacts["native-1"][0]["sha256"] = "wrong"
    with pytest.raises(ValueError):
        collect(data)
    assert measured == []


def test_historical_pending_delivery_points_to_new_output_not_original_experiment(
    tmp_path, monkeypatch
):
    data = inputs(tmp_path, monkeypatch)
    d, experiment, selected, *_ = data
    original_status = digest(experiment / "status.json")

    def pending(deployment, child):
        raise WorkPending({"reason": "worker_busy", "run_id": "same-run"})

    monkeypatch.setattr(delivery, "finish", pending)
    output = tmp_path / "isolated-output"
    with pytest.raises(WorkPending) as error:
        delivery.collect_code_candidates(
            d,
            experiment,
            selected,
            read(experiment / "delivery-checkpoint.json"),
            output=output,
        )
    assert error.value.receipt["experiment"] == str(output)
    assert error.value.receipt["origin_experiment"] == str(experiment)
    assert digest(experiment / "status.json") == original_status


def test_pending_delivery_reconnects_same_candidate_without_exporting_again(
    tmp_path, monkeypatch
):
    data = inputs(tmp_path, monkeypatch)
    d, experiment, selected, _, _, _, exports, measured = data
    calls = []

    def finish(deployment, child):
        calls.append(child)
        if len(calls) == 1:
            raise WorkPending({"reason": "worker_busy", "run_id": "already-submitted"})
        write(
            child / "result.json",
            {
                **selected,
                "run_id": "common-resumed",
                "native_method": read(child / "delivery-checkpoint.json")[
                    "native_method"
                ],
            },
        )
        return read(child / "result.json")

    monkeypatch.setattr(delivery, "finish", finish)
    with pytest.raises(WorkPending) as pending:
        collect(data)
    assert pending.value.receipt["experiment"] == str(experiment)
    metadata = collect(data)
    assert calls[0] == calls[1] and exports == ["dpl"]
    assert read(metadata["inventory"]["path"])["status"] == "completed"
    assert measured == []


@pytest.mark.parametrize(
    "fault", [None, "changed_local_receipt", "wrong_snapshot_checkpoint"]
)
def test_goal_producer_uses_registered_snapshot_bytes_not_only_local_receipt(
    tmp_path, fault
):
    odb = tmp_path / "post_route.odb"
    odb.write_bytes(b"actual completed checkpoint")
    operation = tmp_path / "operations/physical"
    operation.mkdir(parents=True)
    leaf = {
        "request": {"operation": "physical"},
        "returncode": 0,
        "timed_out": False,
        "output_files": {str(odb): digest(odb)},
    }
    write(operation / "leaf.json", leaf)
    write(operation / "execution.json", {"run": {"run_id": "native"}})
    archive = operation / "evidence.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("manifest.json", json.dumps({"receipt": leaf}))
        bundle.writestr(
            "0/post_route.odb",
            b"wrong bytes"
            if fault == "wrong_snapshot_checkpoint"
            else odb.read_bytes(),
        )
    if fault == "changed_local_receipt":
        leaf["request"]["source_files"] = {"source.cc": "invented"}
        write(operation / "leaf.json", leaf)
    client = SimpleNamespace(
        run=lambda rid: {
            "run_id": rid,
            "status": "succeeded",
            "project_id": "goalevolve-common-u4",
            "design_id": "gcd",
            "experiment_id": "native-experiment",
        },
        artifacts=lambda rid: [
            {
                "kind": "data_snapshot",
                "artifact_id": "snapshot",
                "sha256": digest(archive),
            }
        ],
    )
    from chip_evolve.core.contracts import NativeCampaignBinding, NativeCandidateEvidence
    from chip_evolve.core.result_io import file_ref, freeze, object_at

    binding = NativeCampaignBinding(
        "goal", "gcd", "gcd_top", "native-experiment", tmp_path / "operations"
    )
    row = NativeCandidateEvidence(
        "student",
        file_ref(operation / "leaf.json"),
        None,
        file_ref(odb),
        True,
        (),
        object_at(freeze({}), "$"),
    )
    if fault:
        with pytest.raises(ValueError):
            code_evidence.verify_candidate_producer(
                client, binding, row, tmp_path / "cache"
            )
    else:
        assert (
            code_evidence.verify_candidate_producer(
                client, binding, row, tmp_path / "cache"
            ).producer_run_id
            == "native"
        )


def test_root_finish_collects_once_and_child_uses_deferred_facts(tmp_path, monkeypatch):
    from chip_evolve.execution import physical as professional

    real_finish = delivery.finish
    data = inputs(tmp_path, monkeypatch)
    d, experiment, selected, *_ = data
    (experiment / "status.json").unlink()
    calls, modes = [], []

    def resume(*args, **kwargs):
        modes.append(kwargs)
        return dict(selected)

    monkeypatch.setattr(professional, "resume_layout", resume)
    monkeypatch.setattr(
        delivery,
        "collect_code_candidates",
        lambda *args, **kwargs: calls.append(args[1]) or {"verified": True},
    )
    result = real_finish(d, experiment)
    assert result["native_candidate_evidence"] == {"verified": True}
    assert modes == [{}] and calls == [experiment]
    saved = read(experiment / "delivery-checkpoint.json")
    child = experiment / "child"
    child.mkdir()
    saved["native_method"] = {"kind": "native-candidate"}
    write(child / "delivery-checkpoint.json", saved)
    result = real_finish(d, child)
    assert modes[-1] == {"fact_modes": ("orfs", "opensta")}
    assert calls == [experiment]


def test_failed_extra_delivery_is_visible_and_does_not_retry_or_adopt(
    tmp_path, monkeypatch
):
    data = inputs(tmp_path, monkeypatch)
    calls = []

    def failed(deployment, child):
        calls.append(child)
        raise RuntimeError("EDA job failed; evidence retained: actual-run")

    monkeypatch.setattr(delivery, "finish", failed)
    metadata = collect(data)
    assert metadata["additional_results"] is None
    assert not metadata["all_eligible_candidates_delivered"]
    assert metadata["candidate_counts"]["delivery_failed"] == 1
    assert not read(metadata["inventory"]["path"])["adopted"]
    assert collect(data) == metadata and len(calls) == 1


@pytest.mark.parametrize("command", ["run", "resume"])
def test_business_cli_returns_candidate_inventory_without_directory_hunting(
    tmp_path, monkeypatch, capsys, command
):
    from tests.contract_fixtures import unit_admission

    unit_admission(monkeypatch, orchestration=True)
    from chip_evolve.workflow.cli import main

    if command == "run":
        from tests.test_professional_snapshot_binding import prepare

        d, request, _, _ = prepare(tmp_path, monkeypatch, "dpl", "db")
        write(d.path, d.value)
    else:
        d = deployment(tmp_path)
        request = None
    metadata = {
        "inventory": {"path": "/registered/inventory.json", "sha256": "sha"},
        "candidate_counts": {"completed": 3},
        "all_eligible_candidates_delivered": True,
    }
    value = {"run_id": "selected", "metrics": {}, "native_candidate_evidence": metadata}
    from chip_evolve.core.result_io import specialist_reply
    from tests.test_business_contracts import result_file

    output = result_file(tmp_path / "typed-output")
    frame = read(output)
    frame["native_candidate_evidence"] = metadata
    write(output, frame)
    monkeypatch.setattr(
        "chip_evolve.workflow.dpl.run_dpl",
        lambda *args: specialist_reply("dpl", output),
    )
    monkeypatch.setattr(recovery, "recover", lambda *args: value)
    argv = [
        "chip-evolve",
        "--config",
        str(d.path),
        command,
        "--design",
        "gcd",
        "--key",
        "same-task",
    ]
    if command == "run":
        argv += [
            "--capability",
            "dpl",
            "--source",
            str(request.source),
            "--context",
            str(request.context),
        ]
    else:
        (tmp_path / "experiments/gcd/same-task").mkdir(parents=True)
    monkeypatch.setattr("sys.argv", argv)
    assert main() == 0
    assert json.loads(capsys.readouterr().out)["native_candidate_evidence"] == metadata


def test_original_goal_continuation_is_covered_by_same_delivery_hook(
    tmp_path, monkeypatch
):
    data = inputs(tmp_path, monkeypatch)
    d, experiment, selected, *_ = data
    write(experiment / "request.json", {"capability": "goal-continuation"})
    saved = read(experiment / "delivery-checkpoint.json")
    saved["native_method"] = {"kind": "native-timing-continuation"}
    calls = []
    monkeypatch.setattr(
        delivery,
        "collect_code_candidates",
        lambda *args: calls.append(args[1]) or {"same_delivery": True},
    )
    delivery.maybe_collect(d, experiment, selected, saved)
    assert calls == [experiment]
    assert selected["native_candidate_evidence"] == {"same_delivery": True}


def test_finished_legacy_result_is_not_implicitly_upgraded_on_recovery(
    tmp_path, monkeypatch
):
    from chip_evolve.execution import physical as professional

    real_finish = delivery.finish
    data = inputs(tmp_path, monkeypatch)
    d, experiment, selected, *_ = data
    selected["native_method"] = read(experiment / "delivery-checkpoint.json")[
        "native_method"
    ]
    write(experiment / "result.json", selected)
    original = digest(experiment / "result.json")
    monkeypatch.setattr(
        professional, "resume_layout", lambda *args, **kwargs: dict(selected)
    )
    monkeypatch.setattr(
        delivery,
        "collect_code_candidates",
        lambda *args: pytest.fail("historical automatic upgrade"),
    )
    result = real_finish(d, experiment)
    assert "native_candidate_evidence" not in result
    assert digest(experiment / "result.json") == original
