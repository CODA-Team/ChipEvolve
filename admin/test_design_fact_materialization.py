"""Batch facts stay complete for decisions; selected design objects load on demand."""

import zipfile
from argparse import Namespace
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

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
        "scope": {"design_id": "gcd", "run_id": frame["run_id"]},
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


def test_flow_delivers_every_finished_candidate_and_original_constraints(
    tmp_path, monkeypatch
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
    actual = professional.collect_flow(
        d, "gcd", experiment, Path(read(source)["objective"])
    )
    assert modes == [("orfs", "opensta"), ("orfs", "opensta")]
    assert len(actual["candidate_results"]) == 2
    assert actual["candidate_results"][1]["constraint_violations"] == [
        "power_total_w_max"
    ]
    assert actual["selected_source"] is None and not actual["adopted"]
