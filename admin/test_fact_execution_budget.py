"""A larger fact export gets time without changing measured design evidence."""

from copy import deepcopy

import pytest

from admin.test_design_fact_materialization import publication
from chip_evolve.jobs import digest
from chip_evolve.physical import publish


@pytest.mark.parametrize("seconds", [300, 1800])
def test_design_export_budget_preserves_facts_and_reuses_its_tasks(
    tmp_path, monkeypatch, seconds
):
    deployment, source, frame, jobs, kernel, _ = publication(tmp_path, monkeypatch)
    if seconds != 300:
        deployment.value["designs"]["gcd"]["fact_execution"] = {
            "timeout_seconds": seconds
        }
    before = deepcopy(frame)
    first = publish(jobs, frame, result_path=source)
    second = publish(jobs, frame, result_path=source)
    assert len(kernel.tasks) == 3
    assert [task["timeout_seconds"] for task in kernel.tasks] == [seconds] * 3
    assert all(task["resources"]["memory_bytes"] == 8 << 30 for task in kernel.tasks)
    assert all(task["inputs"]["threads"] == 2 for task in kernel.tasks)
    assert all(
        task["task_id"].endswith("-t1800") == (seconds == 1800) for task in kernel.tasks
    )
    assert first["metrics"] == second["metrics"] == before["metrics"]
    assert first["snapshot_ids"] == second["snapshot_ids"]
    assert first["condition_id"] == before["condition_id"]
    assert first["objective_id"] == before["objective_id"]
    assert frame == before


def test_retired_short_export_is_retained_when_larger_budget_is_requested(
    tmp_path, monkeypatch
):
    deployment, source, frame, jobs, kernel, _ = publication(tmp_path, monkeypatch)
    original_run = kernel.run
    monkeypatch.setattr(
        kernel, "run", lambda run: {"run_id": run, "status": "timed_out"}
    )
    with pytest.raises(RuntimeError, match="EDA job failed"):
        publish(jobs, frame, result_path=source)
    original_task = next((jobs.experiment / "jobs").glob("*/task.json"))
    original_hash = digest(original_task)
    original_request = deepcopy(kernel.tasks[0])
    monkeypatch.setattr(kernel, "run", original_run)
    deployment.value["designs"]["gcd"]["fact_execution"] = {"timeout_seconds": 1800}
    result = publish(jobs, frame, result_path=source)
    assert len(kernel.tasks) == 4
    assert kernel.tasks[0] == original_request
    assert digest(original_task) == original_hash
    assert kernel.tasks[1]["task_id"] != original_request["task_id"]
    assert all(task["timeout_seconds"] == 1800 for task in kernel.tasks[1:])
    assert result["metrics"] == frame["metrics"]
    assert set(result["snapshot_ids"]) == {"opendb", "orfs", "opensta"}


def test_explicit_fact_memory_keeps_full_views_and_reuses_its_own_tasks(
    tmp_path, monkeypatch
):
    deployment, source, frame, jobs, kernel, imported = publication(
        tmp_path, monkeypatch
    )
    deployment.value["designs"]["gcd"]["fact_execution"] = {
        "timeout_seconds": 1800,
        "memory_gib": 4,
    }
    before = deepcopy(frame)
    first = publish(jobs, frame, result_path=source)
    second = publish(jobs, frame, result_path=source)
    assert len(kernel.tasks) == 3
    assert all(t["resources"]["memory_bytes"] == 4 << 30 for t in kernel.tasks)
    assert all(t["timeout_seconds"] == 1800 for t in kernel.tasks)
    assert all(t["task_id"].endswith("-t1800-m4") for t in kernel.tasks)
    assert [t["inputs"]["adapter"] for t in kernel.tasks] == [
        "opendb",
        "orfs",
        "opensta",
    ]
    assert len(imported) == 6
    assert first["snapshot_ids"] == second["snapshot_ids"]
    assert first["metrics"] == before["metrics"]
    assert first["condition_id"] == before["condition_id"]
    assert first["objective_id"] == before["objective_id"]
    assert frame == before


def test_measurement_memory_changes_only_reservation_and_explicit_task_key(tmp_path):
    from admin.test_final_fanout_facts import run_measurement
    from chip_evolve.physical import measure

    jobs, (odb, spef, sdc), _ = run_measurement(tmp_path, 0)
    jobs.deployment.value["designs"]["example"]["fact_execution"] = {"memory_gib": 4}
    calls = []

    class Submitted(Exception):
        pass

    def capture_command(key, command, **kwargs):
        calls.append((key, command, kwargs))
        raise Submitted

    jobs.command = capture_command
    with pytest.raises(Submitted):
        measure(jobs, "common", odb, spef, sdc, "same-physical")
    key, argv, task = calls[0]
    assert key == "common-m4"
    assert task["memory_gib"] == 4
    assert task["parent"] == task["analysis_parent"] == "same-physical"
    assert task["cpu"] == 2 and task["seconds"] == 300
    assert all(p in task["capture"] for p in (odb, spef, sdc))
    assert str(tmp_path / "common-m4/measure.tcl") in argv
