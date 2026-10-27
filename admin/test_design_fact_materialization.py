"""Batch facts stay complete for decisions; selected design objects load on demand."""

import zipfile
from argparse import Namespace
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from admin.test_query_objective_handoff import backend, inputs
from chip_evolve.config import read, write
from chip_evolve.jobs import Jobs, digest
from chip_evolve.physical import publish


def publication(tmp_path, monkeypatch):
    d, source, _ = inputs(tmp_path)
    d.value.update(openroad_launcher="/verified/openroad")
    d.value["designs"]["gcd"]["libraries"] = []
    frame = read(source)
    frame.pop("snapshot_ids")
    frame["files"] = {}
    for ext in ("odb", "spef", "sdc", "metrics", "v"):
        file = source.parent / ("final." + ext)
        file.write_text("actual immutable input " + ext)
        frame["files"][ext] = str(file)

    class Kernel:
        def __init__(self):
            self.tasks = []

        def submit(self, task, **kwargs):
            self.tasks.append(task)
            return {"run": {"run_id": task["inputs"]["adapter"]}}

        def run(self, run):
            return {"run_id": run, "status": "succeeded"}

        def artifacts(self, run):
            return [{"kind": "data_snapshot", "artifact_id": "artifact-" + run}]

        def resources(self, run):
            return {}

    kernel = Kernel()
    monkeypatch.setattr("chip_evolve.jobs.KernelClient", lambda *a, **k: kernel)
    monkeypatch.setattr(
        "chip_evolve.physical.EdaAiClient",
        lambda **k: SimpleNamespace(
            get_metrics=lambda **kw: {"scope": {"design_id": "gcd"}}
        ),
    )
    imported = []

    def import_snapshot(jobs, producer, artifact, snapshot, subject):
        imported.append((producer, artifact, snapshot, subject))
        return {"snapshot": {"snapshot_id": snapshot, "run_id": subject}}

    monkeypatch.setattr("chip_evolve.delivery.import_snapshot", import_snapshot)
    batch = d.experiment("gcd", "batch")
    jobs = Jobs(d, "gcd", batch)
    return d, source, frame, jobs, kernel, imported


def test_default_publication_keeps_all_three_fact_views(tmp_path, monkeypatch):
    _, source, frame, jobs, kernel, _ = publication(tmp_path, monkeypatch)
    result = publish(jobs, frame, result_path=source)
    assert set(result["snapshot_ids"]) == {"opendb", "orfs", "opensta"}
    assert "deferred_facts" not in result
    assert [task["inputs"]["adapter"] for task in kernel.tasks] == [
        "opendb",
        "orfs",
        "opensta",
    ]


def test_batch_keeps_final_facts_without_pretending_objects_exist(
    tmp_path, monkeypatch
):
    _, source, frame, jobs, kernel, _ = publication(tmp_path, monkeypatch)
    before = deepcopy(frame)
    result = publish(jobs, frame, result_path=source, modes=("orfs", "opensta"))
    assert set(result["snapshot_ids"]) == {"orfs", "opensta"}
    assert result["metrics"] == before["metrics"]
    assert result["files"] == before["files"]
    assert result["objective_id"] == before["objective_id"]
    assert result["deferred_facts"]["opendb"]["publication_root"] == str(
        jobs.experiment
    )
    assert [task["inputs"]["adapter"] for task in kernel.tasks] == ["orfs", "opensta"]
    assert frame == before


def test_selected_objects_reuse_original_run_and_saved_export(tmp_path, monkeypatch):
    from chip_evolve.design_facts import ensure

    d, source, frame, jobs, kernel, imported = publication(tmp_path, monkeypatch)
    thin = publish(jobs, frame, result_path=source, modes=("orfs", "opensta"))
    immutable = digest(source)
    first = ensure(d, source, thin)
    second = ensure(d, source, thin)
    assert digest(source) == immutable
    assert thin["snapshot_ids"] == read(source)["snapshot_ids"]
    assert first["run_id"] == second["run_id"] == thin["run_id"]
    assert first["metrics"] == thin["metrics"]
    assert set(first["snapshot_ids"]) == {"opendb", "orfs", "opensta"}
    assert first["exports"]["orfs"] == thin["exports"]["orfs"]
    assert "deferred_facts" not in first
    assert [task["inputs"]["adapter"] for task in kernel.tasks] == [
        "orfs",
        "opensta",
        "opendb",
    ]
    assert imported[-1][-1] == thin["run_id"]


def test_query_uses_materialized_objects_and_keeps_source_bytes(tmp_path, monkeypatch):
    from chip_evolve.diagnosis import diagnose

    d, source, _ = inputs(tmp_path)
    frame = read(source)
    frame["snapshot_ids"].pop("opendb")
    frame["deferred_facts"] = {"opendb": {"publication_root": str(tmp_path)}}
    write(source, frame)
    sha = digest(source)
    complete = deepcopy(frame)
    complete["snapshot_ids"]["opendb"] = "materialized-objects"
    seen = []
    monkeypatch.setattr("chip_evolve.design_facts.ensure", lambda *a: complete)
    backend(monkeypatch, [])
    import chip_evolve.diagnosis as module

    call = module.subprocess.run

    def run(command, **kwargs):
        seen.append(command)
        return call(command, **kwargs)

    monkeypatch.setattr(module.subprocess, "run", run)
    diagnose(d, source, "Explain this design", 60, 4)
    assert "materialized-objects" in seen[0]
    assert seen[1][seen[1].index("--snapshot") + 1] == "materialized-objects"
    assert digest(source) == sha


def test_professional_dispatch_consumes_materialized_scope(tmp_path, monkeypatch):
    from chip_evolve.professional import execute

    d, source, _ = inputs(tmp_path)
    frame = read(source)
    complete = deepcopy(frame)
    complete["snapshot_ids"]["opendb"] = "actual-objects"
    context = tmp_path / "context.json"
    context.write_text("{}")
    packet = {
        "confirmed_facts": ["fact"],
        "evidence": ["ref"],
        "context_id": "ctx",
        "scope": {
            "design_id": "gcd",
            "run_id": frame["run_id"],
            "snapshot_id": "actual-objects",
        },
    }
    monkeypatch.setattr("chip_evolve.professional.load_context", lambda _: packet)
    monkeypatch.setattr("chip_evolve.design_facts.ensure", lambda *a: complete)
    monkeypatch.setattr("chip_evolve.handoff.input_contract", lambda *a: {})
    seen = []

    def run(deployment, args, experiment, actual, *rest):
        seen.append(actual["snapshot_ids"]["opendb"])
        return actual

    monkeypatch.setattr("chip_evolve.professional.run_dpl", run)
    args = Namespace(
        source=source,
        design="gcd",
        objective=None,
        context=context,
        capability="dpl",
        seconds=60,
        rounds=1,
        candidates=3,
        operation="evolve",
    )
    execute(d, args, d.experiment("gcd", "downstream"))
    assert seen == ["actual-objects"]


def test_validation_requires_selected_object_scope_without_changing_result(
    tmp_path, monkeypatch
):
    from chip_evolve import validation

    d, source, _ = inputs(tmp_path)
    frame = read(source)
    frame["snapshot_ids"].pop("opendb")
    frame["deferred_facts"] = {"opendb": {"publication_root": str(tmp_path)}}
    write(source, frame)
    sha = digest(source)
    complete = deepcopy(frame)
    complete["snapshot_ids"]["opendb"] = "actual-objects"
    monkeypatch.setattr("chip_evolve.design_facts.ensure", lambda *a: complete)
    seen = []

    def facts(deployment, actual):
        seen.append(actual["snapshot_ids"]["opendb"])
        return {"scopes": actual["snapshot_ids"]}

    monkeypatch.setattr(validation, "query_facts", facts)
    monkeypatch.setattr(validation, "verify_outputs", lambda *a: {"unproven_points": 0})
    monkeypatch.setattr(validation, "replay", lambda *a: complete)
    receipt = validation.validate(d, source, source, "validation")
    assert receipt["passed"] and seen == ["actual-objects", "actual-objects"]
    assert digest(source) == sha


@pytest.mark.parametrize("terminal_evidence", [False, True, "timeout"])
def test_flow_delivers_every_finished_candidate_and_original_constraints(
    tmp_path, monkeypatch, terminal_evidence
):
    from chip_evolve import professional

    d, source, _ = inputs(tmp_path)
    d.value["designs"]["gcd"].update(
        platform="asap7", nickname="gcd", sdc=read(source)["files"]["v"]
    )
    experiment = d.experiment("gcd", "flow")
    write(
        experiment / "source/flow/backup_dir/asap7/gcd/llm_usage_summary.json",
        {"exit_code": 0, "status": "completed"},
    )
    failed_identity: str | None = None
    if terminal_evidence:
        write(
            experiment / "source/flow/backup_dir/asap7/gcd/llm_usage_summary.json",
            {"exit_code": 1, "status": "failed", "campaign_id": "actual-campaign"},
        )
        write(
            experiment / "platform-state/campaign.json",
            {
                "campaign_id": "actual-campaign",
                "owner": {"pid": 999999999, "start_ticks": "not-live"},
            },
        )
        write(experiment / "status.json", {"status": "failed", "detail": "native"})
        write(experiment / "result.json", {"original": "untouched"})
        if terminal_evidence == "timeout":
            write(
                experiment / "source/flow/backup_dir/asap7/gcd/llm_usage_summary.json",
                {
                    "exit_code": None,
                    "status": "running",
                    "campaign_id": "actual-campaign",
                    "completed_iterations": 1,
                },
            )
            write(
                experiment / "status.json",
                {"status": "failed", "error_type": "TimeoutExpired"},
            )
            write(
                experiment / "native-frontend-cleanup.json",
                {
                    "status": "completed",
                    "reason": "TimeoutExpired",
                    "owner_pid": 999999999,
                },
            )
        failed_identity = digest(experiment / "status.json")
    for slot in (1, 2):
        write(
            experiment / f"platform-state/iteration-1/slot-{slot}-route_finish.json",
            {
                "status": "succeeded",
                "run_id": f"physical-{slot}",
                "terminal_run": {"run_id": f"physical-{slot}"},
                "artifacts": [],
                "candidate_slot": slot,
                "candidate_id": f"candidate-{slot}",
            },
        )

    def materialize(self, record, kind, destination, **kwargs):
        if kind == "flow_archive":
            with zipfile.ZipFile(destination, "w") as archive:
                archive.writestr(
                    "flow/logs/5_2_route.json", '{"detailedroute__route__drc_errors":0}'
                )
        else:
            destination.write_text("actual retained native artifact")

    def measure(jobs, key, odb, spef, sdc, producer, objective):
        actual = deepcopy(read(source))
        actual.update(run_id=key, physical_run_id=producer)
        actual["metrics"]["finish__power__total"] = 1 if producer == "physical-1" else 3
        return actual

    modes = []

    def publish(jobs, measured, **kwargs):
        modes.append(kwargs["modes"])
        return measured

    monkeypatch.setattr(Jobs, "materialize", materialize)
    monkeypatch.setattr(professional, "measure", measure)
    monkeypatch.setattr(professional, "publish", publish)
    monkeypatch.setattr(
        professional,
        "recover_config",
        lambda a, b, c, p: p.write_text("evaluated config"),
    )
    if terminal_evidence:
        from chip_evolve.flow_evidence import collect

        actual = collect(d, "gcd", experiment, Path(read(source)["objective"]))
        assert digest(experiment / "status.json") == failed_identity
        assert read(experiment / "result.json") == {"original": "untouched"}
        assert actual["evidence_only"] and not actual["native_search_completed"]
        expected = "timed_out" if terminal_evidence == "timeout" else "failed"
        assert actual["native_campaign"]["status"] == expected
        if terminal_evidence == "timeout":
            witness = actual["native_campaign"]["terminal_evidence"]
            assert witness["reported_native_status"] == "running"
            for name, sha in witness["files"].items():
                assert digest(Path(name)) == sha
            assert actual["native_campaign"]["exit_code"] is None
            assert (
                read(
                    experiment
                    / "source/flow/backup_dir/asap7/gcd/llm_usage_summary.json"
                )["status"]
                == "running"
            )
        assert (experiment / "completed-evidence/result.json").is_file()
        for row in actual["candidate_results"]:
            candidate = read(Path(row["result"]))
            assert candidate["native_campaign"]["status"] == expected
            assert not candidate["native_method"]["native_search_completed"]
            assert "completed-evidence" in row["result"]
    else:
        actual = professional.collect_flow(
            d, "gcd", experiment, Path(read(source)["objective"])
        )
    assert modes == [("orfs", "opensta"), ("orfs", "opensta")]
    assert len(actual["candidate_results"]) == 2
    assert actual["candidate_results"][1]["constraint_violations"] == [
        "power_total_w_max"
    ]
    assert actual["selected_source"] is None and not actual["adopted"]


@pytest.mark.parametrize("state", ["running", "wrong-campaign", "live-owner"])
def test_partial_flow_evidence_does_not_collect_unfinished_or_mixed_campaigns(
    tmp_path, state
):
    import os

    from chip_evolve.flow_evidence import collect

    d, source, _ = inputs(tmp_path)
    d.value["designs"]["gcd"].update(platform="asap7", nickname="gcd")
    experiment = d.experiment("gcd", "partial")
    native = {"exit_code": 1, "status": "failed", "campaign_id": "actual"}
    owner = {"pid": 999999999, "start_ticks": "not-live"}
    if state == "running":
        native.update(status="running", exit_code=None)
    if state == "wrong-campaign":
        native["campaign_id"] = "different"
    if state == "live-owner":
        owner = {
            "pid": os.getpid(),
            "start_ticks": Path(f"/proc/{os.getpid()}/stat")
            .read_text()
            .rsplit(")", 1)[1]
            .split()[19],
        }
    write(
        experiment / "source/flow/backup_dir/asap7/gcd/llm_usage_summary.json", native
    )
    write(
        experiment / "platform-state/campaign.json",
        {"campaign_id": "actual", "owner": owner},
    )
    with pytest.raises(ValueError):
        collect(d, "gcd", experiment, Path(read(source)["objective"]))
    assert not (experiment / "completed-evidence").exists()


@pytest.mark.parametrize(
    "invalid",
    [
        "missing-cleanup",
        "unfinished-cleanup",
        "different-owner",
        "different-reason",
        "successful-business",
        "different-business-error",
        "live-owner",
        "different-campaign",
    ],
)
def test_timeout_evidence_requires_matching_terminal_witness(
    tmp_path, monkeypatch, invalid
):
    import os

    from chip_evolve.flow_evidence import collect

    d, source, _ = inputs(tmp_path)
    d.value["designs"]["gcd"].update(platform="asap7", nickname="gcd")
    experiment = d.experiment("gcd", "timeout")
    native = {"exit_code": None, "status": "running", "campaign_id": "actual"}
    owner = {"pid": 999999999, "start_ticks": "not-live"}
    status = {"status": "failed", "error_type": "TimeoutExpired"}
    cleanup = {
        "status": "completed",
        "reason": "TimeoutExpired",
        "owner_pid": owner["pid"],
    }
    if invalid == "unfinished-cleanup":
        cleanup["status"] = "running"
    elif invalid == "different-owner":
        cleanup["owner_pid"] = 999999998
    elif invalid == "different-reason":
        cleanup["reason"] = "KeyboardInterrupt"
    elif invalid == "successful-business":
        status["status"] = "succeeded"
    elif invalid == "different-business-error":
        status["error_type"] = "RuntimeError"
    elif invalid == "live-owner":
        owner = {
            "pid": os.getpid(),
            "start_ticks": Path(f"/proc/{os.getpid()}/stat")
            .read_text()
            .rsplit(")", 1)[1]
            .split()[19],
        }
        cleanup["owner_pid"] = owner["pid"]
    elif invalid == "different-campaign":
        native["campaign_id"] = "other"
    summary_path = (
        experiment / "source/flow/backup_dir/asap7/gcd/llm_usage_summary.json"
    )
    write(summary_path, native)
    write(
        experiment / "platform-state/campaign.json",
        {"campaign_id": "actual", "owner": owner},
    )
    write(experiment / "status.json", status)
    if invalid != "missing-cleanup":
        write(experiment / "native-frontend-cleanup.json", cleanup)
    originals = {str(path): digest(path) for path in experiment.rglob("*.json")}
    calls = []
    monkeypatch.setattr(
        "chip_evolve.professional._collect_flow_candidates",
        lambda *a, **k: calls.append(k),
    )
    with pytest.raises(ValueError):
        collect(d, "gcd", experiment, Path(read(source)["objective"]))
    assert calls == [] and not (experiment / "completed-evidence").exists()
    assert all(digest(Path(name)) == sha for name, sha in originals.items())
