"""Re-route a selected Flow candidate from its recorded native placement."""

from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Any

from .config import Deployment, read, write
from .jobs import Jobs, digest
from .flow_recipe import tool_profile
from .physical import measure
from .design_facts import publish
import json


def replay(
    deployment: Deployment, result_path: Path, experiment: Path
) -> dict[str, Any]:
    from .delivery import checkpoint, finish
    from .artifact_inputs import flatten_archive

    frame = read(result_path)
    paths = [result_path] + [
        Path(frame[key])
        for key in ("flow_archive", "native_config", "flow_recipe", "objective")
    ]
    identity = {"input_hashes": {str(path): digest(path) for path in paths}}
    saved = experiment / "flow-replay-inputs.json"
    if saved.exists() and read(saved) != identity:
        raise ValueError("Flow replay inputs changed after the first attempt")
    inputs = experiment / "inputs"
    inputs.mkdir(parents=True, exist_ok=True)
    write(saved, identity)
    archive = experiment / "source-checkpoint.zip"
    if not archive.exists():
        flatten_archive(Path(frame["flow_archive"]), archive)
    placement = inputs / "placement.odb"
    if not placement.exists():
        with zipfile.ZipFile(archive) as bundle:
            placement.write_bytes(bundle.read("flow/results/3_place.odb"))
    checkpoint(
        experiment,
        design_id=frame["design_id"],
        odb=placement,
        producer=frame["physical_run_id"],
        objective=Path(frame["objective"]),
        source=result_path,
        native_method={
            "kind": "independent-flow-routing-replay",
            "original_result": str(result_path),
            "candidate_id": frame["candidate_id"],
            "scope": "native pre-CTS placement through CTS, full route, RCX and common measurement",
            "native_search_restarted": False,
        },
    )
    return finish(deployment, experiment)


def qualify_prepared_recipe(
    deployment: Deployment, experiment: Path, *, seconds: int = 3600
) -> dict[str, Any]:
    """Run the unchanged physical recipe; this does not qualify native knobs."""
    recipe = read(experiment / "recipe.json")
    reference = read(recipe["source_result"])
    source = Path(recipe["source"])
    config = Path(recipe["config_path"])
    if digest(config) != recipe["resolved_config_sha256"]:
        raise ValueError("Prepared source configuration changed")
    jobs = Jobs(deployment, recipe["design_id"], experiment)
    profile = tool_profile(deployment, source, experiment)
    parent = recipe["physical_run_id"]
    checkpoint: Path | None = None
    objective = Path(reference["objective"])
    record: dict[str, Any] = {}
    for stage in ("place", "cts", "route_finish"):
        inputs = {
            "adapter": "a2_stage",
            "stage": stage,
            "threads": 8,
            "profile_path": "inputs/profile.json",
            "config_path": "inputs/config.mk",
            "sdc_path": "inputs/design.sdc",
        }
        staged = [
            {"source": str(p), "destination": "inputs/" + name}
            for p, name in (
                (profile, "profile.json"),
                (config, "config.mk"),
                (source / "flow/source-bindings/design.sdc", "design.sdc"),
            )
        ]
        if checkpoint:
            inputs["checkpoint_path"] = "inputs/checkpoint.zip"
            staged.append(
                {"source": str(checkpoint), "destination": "inputs/checkpoint.zip"}
            )
        record = jobs.submit(
            stage,
            inputs,
            staged,
            parent=parent,
            objective=objective,
            seconds=seconds,
            memory_gib=deployment.design(recipe["design_id"])
            .get("orfs_execution", {})
            .get("memory_gib", 24),
        )
        checkpoint = experiment / (stage + ".zip")
        jobs.materialize(record, "flow_archive", checkpoint)
        parent = record["run"]["run_id"]
    files = {}
    for suffix, kind in (("odb", "raw_design_database"), ("spef", "raw_parasitics")):
        path = experiment / ("6_final." + suffix)
        jobs.materialize(record, kind, path, suffix="/6_final." + suffix)
        files[suffix] = path
    measured = measure(
        jobs,
        "common",
        files["odb"],
        files["spef"],
        Path(deployment.design(recipe["design_id"])["sdc"]),
        parent,
        objective,
    )
    assert checkpoint is not None
    with zipfile.ZipFile(checkpoint) as archive:
        route = json.loads(archive.read("flow/logs/5_2_route.json"))
    measured.update(
        route_drc=route["detailedroute__route__drc_errors"],
        flow_archive=str(checkpoint),
        flow_recipe=str(experiment / "recipe.json"),
        native_config=str(config),
        native_flow_dir=str(source / "flow"),
        native_method={
            "kind": "unchanged-source-physical-qualification",
            "source_run_id": recipe["source_run_id"],
            "native_search_executed": False,
        },
    )
    result = publish(jobs, measured)
    write(experiment / "result.json", result)
    return result
