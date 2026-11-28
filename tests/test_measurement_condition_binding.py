"""The files actually measured must match the frozen comparison conditions."""

from copy import deepcopy
from pathlib import Path

import pytest
from eda_toolkits.objectives import objective_id

from chip_evolve.workflow import commands, professional
from chip_evolve.execution import physical
from chip_evolve.core.command_requests import RunCommand
from chip_evolve.core.config import read, write
from chip_evolve.core.jobs import digest
from tests.test_final_fanout_facts import run_measurement


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
        "reference_run_id": "reference",
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


def test_run_rejects_replaced_tool_image_before_submitting(tmp_path, monkeypatch):
    jobs, *_ = bound_measurement(tmp_path)
    image = tmp_path / "toolchain.sif"
    image.write_bytes(b"first image")
    jobs.deployment.value["runtime"] = {"image": str(image)}
    jobs.deployment.value["toolchain"] = {"image_sha256": digest(image)}
    image.write_bytes(b"replacement at the same path")
    monkeypatch.setattr(
        physical, "baseline", lambda *a, **kw: pytest.fail("submitted with wrong image")
    )
    args = RunCommand(
        config=jobs.deployment.path,
        key="condition-test",
        capability="orfs",
        design="example",
        environment=None,
        flow_recipe=None,
        operation="evolve",
        source=None,
        code_source=None,
    )

    with pytest.raises(ValueError, match="Image differs from its pinned identity"):
        commands.run_experiment(jobs.deployment, args)

    assert not (jobs.deployment.state / "experiments").exists()


@pytest.mark.parametrize("capability", ["flow", "dpl", "goal"])
def test_specialist_profile_must_use_the_deployment_image(tmp_path, capability):
    from chip_evolve.workflow.environment import verify_professional_toolchain

    jobs, *_ = bound_measurement(tmp_path)
    profile = tmp_path / "profile.json"
    jobs.deployment.value.update(
        toolchain={"image_sha256": "common", "openroad_commit": "base"},
        flow_tool_profile=str(profile),
        professional={capability: {"profile_template": str(profile)}},
    )
    write(
        profile,
        {"toolchain": {"image_sha256": "stale", "openroad_base_commit": "base"}},
    )
    with pytest.raises(ValueError, match=f"{capability} profile.*image_sha256"):
        verify_professional_toolchain(jobs.deployment, capability)

    write(
        profile,
        {"toolchain": {"image_sha256": "common", "openroad_base_commit": "base"}},
    )
    verify_professional_toolchain(jobs.deployment, capability)


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


def test_native_qualification_reserves_the_configured_threads(tmp_path):
    jobs, odb, _spef, _sdc, objective, _goal = bound_measurement(tmp_path)
    jobs.deployment.design("example")["orfs_execution"] = {
        "cpu_cores": 4,
        "memory_gib": 12,
    }

    class ReachedExecution(Exception):
        pass

    def capture(key, command, **options):
        assert key == "qualification"
        assert command[command.index("-threads") + 1] == "4"
        assert options["cpu"] == 4
        assert options["memory_gib"] == 12
        raise ReachedExecution

    jobs.command = capture
    with pytest.raises(ReachedExecution):
        physical.qualify(jobs, odb, "native-source", objective, tmp_path)


@pytest.mark.parametrize("entry", ["baseline", "qualify"])
def test_wrong_conditions_stop_before_physical_qualification_or_full_baseline(
    tmp_path, monkeypatch, entry
):
    jobs, odb, _spef, _sdc, objective, _goal = bound_measurement(tmp_path)
    change_condition(tmp_path, jobs, "libraries")

    def forbidden(*_args, **_kwargs):
        pytest.fail("Mismatched task must stop before physical execution")

    monkeypatch.setattr("chip_evolve.core.jobs.Jobs.command", forbidden)
    monkeypatch.setattr("chip_evolve.core.jobs.Jobs.submit", forbidden)
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
    from eda_toolkits.objectives import condition_id

    from tests.test_business_contracts import result_file

    frame = read(result_file(tmp_path / "valid-fixture"))
    goal = read(objective)
    goal["constraints"] = read(Path(frame["objective"]))["constraints"]
    goal["objective_id"] = objective_id(goal)
    write(objective, goal)
    frame.update(
        design_id="example",
        run_id="source",
        objective=str(objective),
        objective_id=goal["objective_id"],
        condition_id=condition_id(goal),
        conditions={k: goal["conditions"][k] for k in ("corner", "clock_period_ns")},
    )
    write(source, frame)

    def forbidden(*_args, **_kwargs):
        pytest.fail("Mismatched task must stop before diagnosis/model/EDA work")

    monkeypatch.setattr("chip_evolve.workflow.diagnosis.diagnose", forbidden)
    args = RunCommand(
        config=jobs.deployment.path,
        key="condition-test",
        source=source,
        design="example",
        objective=None,
        context=None,
        capability=capability,
    ).normalized()
    with pytest.raises(ValueError, match="libraries"):
        professional.execute(jobs.deployment, args, tmp_path)
