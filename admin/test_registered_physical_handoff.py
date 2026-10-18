"""Native ORFS defaults must not silently become a legacy Code delivery recipe."""

from pathlib import Path
from unittest.mock import patch

import pytest

from chip_evolve.config import Deployment, read, write
from chip_evolve.delivery import checkpoint, finish, layout_source
from chip_evolve.jobs import digest
from chip_evolve.lifecycle import WorkPending


def setup_source(tmp_path):
    source_path = tmp_path / "original/result.json"
    frame = {
        "run_id": "registered-orfs",
        "design_id": "example",
        "native_inputs": "original-inputs.json",
    }
    write(source_path, frame)
    experiment = tmp_path / "new-code-delivery"
    experiment.mkdir()
    config = tmp_path / "local.json"
    write(
        config,
        {
            "schema_version": "chip-evolve.local.v1",
            "state_root": str(tmp_path / "runtime"),
            "kernel_url": "http://localhost:1",
        },
    )
    return Deployment(config), source_path, frame, experiment


def prepare_registered(experiment, source_path, frame):
    source = experiment / "source"
    config = source / "flow/source-config.mk"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text("export DETAILED_ROUTE_END_ITERATION = 64\n")
    recipe = {
        "source_run_id": frame["run_id"],
        "design_id": frame["design_id"],
        "result_sha256": digest(source_path),
        "source": str(source),
        "config_path": str(config),
    }
    write(experiment / "recipe.json", recipe)
    return source


def test_fresh_orfs_handoff_uses_actual_registered_recipe_without_mutating_source(
    tmp_path,
):
    deployment, path, frame, experiment = setup_source(tmp_path)
    before = path.read_bytes()
    with patch(
        "chip_evolve.flow_recipe.prepare_flow_recipe",
        side_effect=lambda *args: prepare_registered(experiment, path, frame),
    ) as prepare:
        inherited = layout_source(deployment, experiment, path)
    prepare.assert_called_once_with(deployment, path, experiment)
    assert inherited["flow_recipe"] == str(experiment / "recipe.json")
    assert read(experiment / "recipe.json")["source_run_id"] == frame["run_id"]
    assert "= 64" in Path(inherited["native_config"]).read_text()
    assert path.read_bytes() == before


def test_existing_legacy_delivery_keeps_its_immutable_source(tmp_path):
    deployment, path, frame, experiment = setup_source(tmp_path)
    legacy = experiment / "source/flow/config.mk"
    legacy.parent.mkdir(parents=True)
    legacy.write_text("export DETAILED_ROUTE_END_ITERATION = 5\n")
    with patch("chip_evolve.flow_recipe.prepare_flow_recipe") as prepare:
        assert layout_source(deployment, experiment, path) == frame
    prepare.assert_not_called()
    assert legacy.read_text().endswith("= 5\n")


def test_preparation_pending_reconnects_same_native_preparation(tmp_path):
    deployment, path, frame, experiment = setup_source(tmp_path)

    def pending(*args):
        (experiment / "source").mkdir()
        write(experiment / "jobs/prepare-recipe/task.json", {"task_id": "same-prepare"})
        raise WorkPending({"reason": "same existing EF prepare run"})

    with (
        patch("chip_evolve.flow_recipe.prepare_flow_recipe", side_effect=pending),
        pytest.raises(WorkPending),
    ):
        layout_source(deployment, experiment, path)
    with patch(
        "chip_evolve.flow_recipe.prepare_flow_recipe",
        side_effect=lambda *args: prepare_registered(experiment, path, frame),
    ) as prepare:
        inherited = layout_source(deployment, experiment, path)
    assert prepare.call_count == 1
    assert inherited["flow_recipe"] == str(experiment / "recipe.json")


def test_completed_recipe_is_reused_and_other_source_is_rejected(tmp_path):
    deployment, path, frame, experiment = setup_source(tmp_path)
    prepare_registered(experiment, path, frame)
    with patch("chip_evolve.flow_recipe.prepare_flow_recipe") as prepare:
        assert layout_source(deployment, experiment, path)["flow_recipe"]
    prepare.assert_not_called()
    recipe = read(experiment / "recipe.json")
    recipe["source_run_id"] = "unrelated"
    write(experiment / "recipe.json", recipe)
    with pytest.raises(ValueError, match="another source"):
        layout_source(deployment, experiment, path)


@pytest.mark.parametrize("field", ["flow_recipe", "no_native_inputs"])
def test_prepared_flow_and_non_orfs_sources_keep_existing_path(tmp_path, field):
    deployment, path, frame, experiment = setup_source(tmp_path)
    if field == "flow_recipe":
        frame[field] = "already-qualified-recipe.json"
    else:
        frame.pop("native_inputs")
    write(path, frame)
    with patch("chip_evolve.flow_recipe.prepare_flow_recipe") as prepare:
        assert layout_source(deployment, experiment, path) == frame
    prepare.assert_not_called()


def test_delivery_finish_hands_registered_defaults_to_existing_physical_runner(
    tmp_path,
):
    deployment, path, frame, experiment = setup_source(tmp_path)
    odb = tmp_path / "actual-candidate.odb"
    odb.write_bytes(b"candidate layout")
    objective = tmp_path / "objective.json"
    write(objective, {"objective_id": "original"})
    checkpoint(
        experiment,
        design_id="example",
        odb=odb,
        producer="candidate-producer",
        objective=objective,
        source=path,
        native_method={"kind": "matched-control"},
    )
    with (
        patch(
            "chip_evolve.flow_recipe.prepare_flow_recipe",
            side_effect=lambda *args: prepare_registered(experiment, path, frame),
        ),
        patch(
            "chip_evolve.professional.resume_layout",
            return_value={"run_id": "measured"},
        ) as physical,
    ):
        result = finish(deployment, experiment)
    assert result["native_method"]["kind"] == "matched-control"
    received = physical.call_args.args[2]
    assert received["flow_recipe"] == str(experiment / "recipe.json")
    assert "= 64" in Path(received["native_config"]).read_text()
    assert physical.call_args.args[4] == "candidate-producer"
