"""New read-only measurements are analysis; immutable legacy jobs retain identity."""

import pytest

from admin.test_final_fanout_facts import run_measurement
from chip_evolve.config import write


@pytest.mark.parametrize("legacy", [False, True])
def test_measurement_classifies_new_tasks_without_changing_saved_tasks(
    tmp_path, legacy
):
    jobs, _, measure = run_measurement(tmp_path, 0)
    calls = []
    original = jobs.command

    def command(*args, **kwargs):
        calls.append(kwargs)
        return original(*args, **kwargs)

    jobs.command = command
    if legacy:
        write(
            tmp_path / "jobs/common/task.json",
            {"labels": {"parent_run_id": "original-physical"}},
        )
    measured = measure()
    assert measured["physical_run_id"] == "original-physical"
    assert calls[0]["parent"] == "original-physical"
    assert calls[0]["analysis_parent"] == (None if legacy else "original-physical")


def test_resumed_new_measurement_retains_analysis_parent(tmp_path):
    jobs, _, measure = run_measurement(tmp_path, 0)
    calls = []
    original = jobs.command

    def command(*args, **kwargs):
        calls.append(kwargs)
        return original(*args, **kwargs)

    jobs.command = command
    write(
        tmp_path / "jobs/common/task.json",
        {
            "labels": {
                "parent_run_id": "original-physical",
                "analysis_of_run_id": "original-physical",
                "run_type": "analysis",
            }
        },
    )
    measure()
    assert calls[0]["analysis_parent"] == "original-physical"
