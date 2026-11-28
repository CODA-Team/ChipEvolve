"""Qualified physical inputs cannot silently drift back to defaults."""

import pytest

from chip_evolve.config import read, write
from chip_evolve.environment import (
    SCHEMA,
    check_environment,
    deployment_binding,
    identity,
    reference,
)
from tests.test_adoption_consistency import frame_at
from tests.test_local_business import deployment


def frozen(tmp_path):
    deployment_config = deployment(tmp_path)
    image = tmp_path / "image.sif"
    image.write_bytes(b"fixed toolchain image")
    deployment_config.value["toolchain"] = {"openroad_commit": "fixed"}
    source = frame_at(tmp_path, "reference")
    frame = read(source)
    value = {
        "schema_version": SCHEMA,
        "design_id": "gcd",
        "objective_id": frame["objective_id"],
        "condition_id": frame["condition_id"],
        "toolchain": deployment_config.value["toolchain"],
        "image": reference(image),
        "source": reference(source),
        "source_run_id": frame["run_id"],
        "deployment_binding": deployment_binding(deployment_config, "gcd"),
        "probe": reference(image),
        "qualification": [],
        "source_inputs": [],
        "measurement_inputs": [],
        "configuration_inputs": [],
        "professionals": {},
    }
    value["environment_id"] = identity(value)
    path = tmp_path / "environment.json"
    write(path, value)
    return deployment_config, source, image, path


def test_changed_actual_image_is_rejected_before_any_task(tmp_path):
    d, source, image, path = frozen(tmp_path)
    assert (
        check_environment(d, path, "gcd", "flow", source, "source")["source_run_id"]
        == "reference"
    )
    image.write_bytes(b"new latest image at the same path")
    with pytest.raises(ValueError, match="Frozen environment file changed"):
        check_environment(d, path, "gcd", "flow", source, "source")


def test_legacy_and_other_design_cannot_claim_source_qualification(tmp_path):
    d, source, _, path = frozen(tmp_path)
    with pytest.raises(ValueError, match="source mode"):
        check_environment(d, path, "gcd", "flow", source, "legacy")
    with pytest.raises(ValueError, match="another design"):
        check_environment(d, path, "aes", "flow", source, "source")


def test_new_physical_branch_keeps_conditions_but_is_not_a_flow_recipe(tmp_path):
    d, _, _, path = frozen(tmp_path)
    branch = frame_at(tmp_path, "branch", 0.8)
    assert check_environment(d, path, "gcd", "dpl", branch, "legacy")
    with pytest.raises(ValueError, match="explicitly qualified source"):
        check_environment(d, path, "gcd", "flow", branch, "source")


def test_changing_executable_paths_cannot_reuse_old_probe(tmp_path):
    d, source, _, path = frozen(tmp_path)
    d.value["tools"] = {"openroad": "/different/openroad"}
    with pytest.raises(ValueError, match="Deployment tools"):
        check_environment(d, path, "gcd", "flow", source, "source")


@pytest.mark.parametrize("changed", ["agent_commit", "seed_commit", "seed_dirty"])
def test_professional_source_revision_and_seed_cannot_drift(
    tmp_path, monkeypatch, changed
):
    d, source, _, path = frozen(tmp_path)
    d.value["professional"] = {"goal": {"source": str(tmp_path / "agent")}}
    value = read(path)
    value["deployment_binding"] = deployment_binding(d, "gcd")
    value["professionals"] = {
        "goal": {
            "commit": "fixed",
            "files": [],
            "source_seed": str(tmp_path / "seed"),
            "source_seed_commit": "fixed",
        }
    }
    value["environment_id"] = identity(value)
    write(path, value)

    def git(command, *, cwd, text):
        if command[1] == "rev-parse":
            return "changed" if changed == cwd.name + "_commit" else "fixed"
        return " M algorithm.cc" if changed == cwd.name + "_dirty" else ""

    monkeypatch.setattr("chip_evolve.environment.subprocess.check_output", git)
    with pytest.raises(ValueError, match="professional repository changed"):
        check_environment(d, path, "gcd", "flow", source, "source")


@pytest.mark.parametrize("explicit,expected", [(None, "source"), ("legacy", "legacy")])
def test_flow_default_uses_source_and_legacy_is_explicit(
    tmp_path, monkeypatch, explicit, expected
):
    from chip_evolve.cli import main

    from tests.test_professional_snapshot_binding import prepare
    from chip_evolve.result_io import specialist_reply, wire_object

    d, request, _, _ = prepare(tmp_path, monkeypatch, "flow", "db")
    write(d.path, d.value)
    seen = []

    def execute(deployment, args, experiment, source, objective, context):
        seen.append(args.flow_recipe)
        write(experiment / "result.json", wire_object(source.wire))
        return specialist_reply("flow", experiment / "result.json")

    monkeypatch.setattr("chip_evolve.flow.run_flow", execute)
    argv = [
        "chip-evolve",
        "--config",
        str(d.path),
        "run",
        "--design",
        "gcd",
        "--capability",
        "flow",
        "--source",
        str(request.source),
        "--context",
        str(request.context),
        "--key",
        "new",
    ]
    if explicit:
        argv += ["--flow-recipe", explicit]
    monkeypatch.setattr("sys.argv", argv)
    assert main() == 0
    assert seen == [expected]
