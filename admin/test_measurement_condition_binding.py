"""The files actually measured must match the frozen comparison conditions."""

from argparse import Namespace
from copy import deepcopy
from pathlib import Path

import pytest
from eda_toolkits.objectives import objective_id

from admin.test_final_fanout_facts import run_measurement
from chip_evolve import physical, professional
from chip_evolve.config import write
from chip_evolve.jobs import digest


def bound_measurement(tmp_path):
    jobs, (odb, spef, sdc), _ = run_measurement(tmp_path, 0)
    design = jobs.deployment.design("example")
    design["sdc"] = str(sdc)
    conditions = {
        "libraries": deepcopy(design["libraries"]),
        "sdc": {"path": str(sdc), "sha256": digest(sdc)},
        "corner": design["corner"],
        "clock_period_ns": design["clock_period_ns"],
        "toolchain": deepcopy(jobs.deployment.value["toolchain"]),
    }
    goal = {
        "schema_version": "chip-evolve.objective.v1",
        "design_id": "example",
        "conditions": conditions,
        "constraints": {},
    }
    goal["objective_id"] = objective_id(goal)
    objective = tmp_path / "objective.json"
    write(objective, goal)
    return jobs, odb, spef, sdc, objective, goal


def change_condition(tmp_path, jobs, field):
    design = jobs.deployment.design("example")
    if field == "libraries":
        other = tmp_path / "another-corner/FF.lib"
        other.parent.mkdir()
        other.write_text("different library with the same basename")
        design["libraries"] = [{"path": str(other), "sha256": digest(other)}]
    elif field == "toolchain":
        jobs.deployment.value["toolchain"] = {"identity": "different"}
    else:
        design[field] = "TT" if field == "corner" else 0.9


@pytest.mark.parametrize(
    "field", ["libraries", "corner", "clock_period_ns", "toolchain"]
)
def test_mismatched_actual_measurement_cannot_receive_the_old_condition_id(
    tmp_path, field
):
    jobs, odb, spef, sdc, objective, _ = bound_measurement(tmp_path)
    change_condition(tmp_path, jobs, field)
    with pytest.raises(ValueError, match=field):
        physical.measure(jobs, "common", odb, spef, sdc, "physical", objective)


@pytest.mark.parametrize("relocate_library", [False, True])
def test_matching_contents_keep_the_original_goal_and_measurement(
    tmp_path, relocate_library
):
    jobs, odb, spef, sdc, objective, goal = bound_measurement(tmp_path)
    if relocate_library:
        binding = jobs.deployment.design("example")["libraries"][0]
        relocated = tmp_path / "relocated.lib"
        relocated.write_bytes(Path(binding["path"]).read_bytes())
        binding["path"] = str(relocated)
    measured = physical.measure(jobs, "common", odb, spef, sdc, "physical", objective)
    assert measured["objective_id"] == goal["objective_id"]
    assert measured["metrics"]["finish__power__total"] == 0.003003


@pytest.mark.parametrize("entry", ["baseline", "qualify"])
def test_wrong_conditions_stop_before_physical_qualification_or_full_baseline(
    tmp_path, monkeypatch, entry
):
    jobs, odb, _spef, _sdc, objective, _goal = bound_measurement(tmp_path)
    change_condition(tmp_path, jobs, "libraries")

    def forbidden(*_args, **_kwargs):
        pytest.fail("Mismatched task must stop before physical execution")

    monkeypatch.setattr("chip_evolve.jobs.Jobs.command", forbidden)
    monkeypatch.setattr("chip_evolve.jobs.Jobs.submit", forbidden)
    jobs.deployment.design("example")["orfs_config"] = "designs/example/config.mk"
    jobs.command = forbidden
    with pytest.raises(ValueError, match="libraries"):
        if entry == "baseline":
            physical.baseline(
                jobs.deployment, "example", tmp_path, 60, objective=objective
            )
        else:
            physical.qualify(jobs, odb, "physical", objective, tmp_path)


@pytest.mark.parametrize("capability", ["flow", "dpl", "goal", "eco"])
def test_wrong_conditions_stop_before_diagnosis_and_professional_dispatch(
    tmp_path, monkeypatch, capability
):
    jobs, _odb, _spef, _sdc, objective, _goal = bound_measurement(tmp_path)
    change_condition(tmp_path, jobs, "libraries")
    source = tmp_path / "source/result.json"
    write(
        source,
        {"design_id": "example", "run_id": "source", "objective": str(objective)},
    )

    def forbidden(*_args, **_kwargs):
        pytest.fail("Mismatched task must stop before diagnosis/model/EDA work")

    monkeypatch.setattr("chip_evolve.diagnosis.diagnose", forbidden)
    args = Namespace(
        source=source,
        design="example",
        objective=None,
        context=None,
        capability=capability,
    )
    with pytest.raises(ValueError, match="libraries"):
        professional.execute(jobs.deployment, args, tmp_path)
