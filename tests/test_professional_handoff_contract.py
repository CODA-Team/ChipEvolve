"""Handoff and role identities belong to actual inputs, not Query prose."""

from types import SimpleNamespace

import pytest

from tests.test_adoption_consistency import frame_at
from tests.test_local_business import deployment
from tests.test_professional_snapshot_binding import prepare
from chip_evolve.core.config import read, write
from chip_evolve.workflow.diagnosis import identity_bindings
from chip_evolve.workflow.handoff import input_contract
from chip_evolve.core.jobs import digest
from chip_evolve.workflow.professional import execute


def registered_source(tmp_path, frame):
    frames = {}
    for name in ("odb", "sdc", "v", "def", "spef"):
        path = tmp_path / ("registered." + name)
        path.write_bytes(name.encode())
        frame.setdefault("files", {})[name] = str(path)
        frames[name] = path
    archive = tmp_path / "registered.zip"
    archive.write_bytes(b"routed archive")
    frame["physical_run_id"] = "routed-source"
    native = tmp_path / "native-inputs.json"
    write(native, {"run_id": "routed-source", "archive": str(archive)})
    frame["native_inputs"] = str(native)
    raw = [
        {"artifact_id": name, "store_key": path.name, "sha256": digest(path)}
        for name, path in frames.items()
    ]
    export = {"run": {"run_id": "fact-export"}, "artifacts": raw}
    frame["exports"] = {mode: {"execution": export} for mode in ("orfs", "opendb")}
    registry = {
        "fact-export": raw,
        "routed-source": [
            {
                "kind": "flow_archive",
                "artifact_id": "archive",
                "sha256": digest(archive),
            }
        ],
    }
    client = SimpleNamespace(
        run=lambda run_id: {
            "design_id": "gcd",
            "status": "succeeded",
            "labels": (
                {"analysis_of_run_id": frame["run_id"]}
                if run_id == "fact-export"
                else {"parent_run_id": "routed-source"}
            ),
        },
        artifacts=registry.__getitem__,
    )
    return client, archive


def test_handoff_records_registered_source_for_each_specialist(tmp_path):
    frame = read(frame_at(tmp_path, "reference"))
    client, archive = registered_source(tmp_path, frame)
    jobs = SimpleNamespace(design_id="gcd", client=client)
    goal = input_contract(jobs, frame, "goal")
    assert "remove fillers" in goal["transformations"]
    assert goal["source_run_id"] == frame["run_id"]
    assert goal["objective_id"] == frame["objective_id"]
    assert goal["source_files"]["v"]["sha256"] == digest(tmp_path / "registered.v")

    eco = input_contract(jobs, frame, "eco")
    assert eco["source_files"]["spef"]["artifact_id"] == "spef"
    assert "path" not in eco["source_files"]["spef"]

    dpl = input_contract(jobs, frame, "dpl")
    assert "pre-CTS" in dpl["transformations"]
    assert dpl["source_files"]["flow_archive"]["sha256"] == digest(archive)
    archive.write_bytes(b"not the registered archive")
    with pytest.raises(ValueError, match="archive differs"):
        input_contract(jobs, frame, "dpl")


def test_replaced_odb_is_rejected_before_professional_dispatch(tmp_path, monkeypatch):
    d, args, experiment, dispatched = prepare(tmp_path, monkeypatch, "goal", "db")
    monkeypatch.setattr("chip_evolve.workflow.handoff.input_contract", input_contract)
    frame = read(args.source)
    client, _ = registered_source(tmp_path, frame)
    write(args.source, frame)
    monkeypatch.setattr("chip_evolve.core.jobs.KernelClient", lambda *a, **kw: client)
    (tmp_path / "registered.odb").write_bytes(b"unrelated design")
    with pytest.raises(ValueError, match="source file differs from registered"):
        execute(d, args, experiment)
    assert dispatched == []
    assert not (experiment / "handoff-input.json").exists()


def test_roles_use_explicit_reference_and_verified_retained_record(tmp_path):
    d = deployment(tmp_path)
    reference = read(frame_at(tmp_path, "reference"))
    candidate = read(frame_at(tmp_path, "candidate", 0.9))
    roles = identity_bindings(d, candidate, reference)
    assert roles["reference"]["run_id"] == "reference"
    assert roles["source"]["run_id"] == "candidate"
    assert roles["retained"] is None
    write(
        tmp_path / "designs/gcd/incumbent.json",
        {
            "run_id": "actual-goal",
            "result": str(tmp_path / "candidate/result.json"),
            "result_sha256": digest(tmp_path / "candidate/result.json"),
            "objective_id": candidate["objective_id"],
            "condition_id": candidate["condition_id"],
        },
    )
    roles = identity_bindings(d, candidate, reference)
    assert roles["retained"]["run_id"] == "actual-goal"
    assert roles["reference"]["run_id"] != roles["retained"]["run_id"]
