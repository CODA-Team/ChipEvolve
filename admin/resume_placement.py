"""Resume registered placement through the existing EF/Toolkit stage seam."""

from __future__ import annotations

import hashlib
import json
import re
import zipfile
from pathlib import Path

from overnight_runtime import collect, submit
from run_dplevolve_native import digest, write_json


def placement_archive(source: Path, odb: Path, destination: Path, sdc: Path) -> None:
    """Keep native predecessors, replace placement, and omit stale successors."""
    with (
        zipfile.ZipFile(source) as original,
        zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as output,
    ):
        for name in original.namelist():
            parts = Path(name).parts
            if len(parts) < 3 or parts[:2] not in {
                ("flow", "results"),
                ("flow", "logs"),
                ("flow", "reports"),
                ("flow", "objects"),
            }:
                continue
            if parts[1] != "objects" and parts[2].startswith(("4_", "5_", "6_")):
                continue
            if name in {
                "flow/results/3_5_place_dp.odb",
                "flow/results/3_place.odb",
                "flow/results/3_place.sdc",
            }:
                continue
            output.writestr(name, original.read(name))
        for name in ("3_5_place_dp.odb", "3_place.odb"):
            output.write(odb, "flow/results/" + name)
        output.write(sdc, "flow/results/3_place.sdc")


def verify_stage_archive(path: Path, expected_sha256: str, phase: str) -> list[str]:
    with zipfile.ZipFile(path) as bundle:
        for name in ("3_5_place_dp.odb", "3_place.odb"):
            if (
                hashlib.sha256(bundle.read("flow/results/" + name)).hexdigest()
                != expected_sha256
            ):
                raise ValueError("Predecessor placement was overwritten: " + name)
        log = bundle.read("flow/combined.log").decode()
    # CTS can run its own legal placement; it may not regenerate its predecessor.
    if (
        "Running detail_place.tcl, stage 3_5_place_dp" in log
        or "synth_canonicalize.tcl" in log
    ):
        raise ValueError("The stage restarted upstream synthesis/placement")
    predecessor = "3_place" if phase == "cts" else "4_cts"
    consumed = re.findall(r"[^\n]*read_db[^\n]*/" + predecessor + r"\.odb[^\n]*", log)
    if not consumed:
        raise ValueError("No evidence that the stage read its intended predecessor")
    return consumed


def stage(
    state: Path,
    key: str,
    *,
    design: str,
    phase: str,
    profile: Path,
    config: Path,
    sdc: Path,
    checkpoint: Path,
    parent_run: str,
    expected_placement_sha256: str,
    objective: Path | None = None,
) -> dict:
    from openroad_platform_client import KernelClient

    spec = {
        "schema_version": 3,
        "task_id": state.name + "-" + key,
        "project_id": "chip-evolve-handoff",
        "design_id": design,
        "experiment_id": state.name,
        "plugin_id": "openroad-data",
        "labels": {
            "parent_run_id": parent_run,
            "stage": phase,
            "memory_approval": "manual",
        },
        "inputs": {
            "adapter": "a2_stage",
            "stage": phase,
            "threads": 8,
            "profile_path": "inputs/profile.json",
            "config_path": "inputs/config.mk",
            "sdc_path": "inputs/constraints.sdc",
            "checkpoint_path": "inputs/checkpoint.zip",
        },
        "staged_inputs": [
            {"source": str(source), "destination": "inputs/" + name}
            for source, name in [
                (profile, "profile.json"),
                (config, "config.mk"),
                (sdc, "constraints.sdc"),
                (checkpoint, "checkpoint.zip"),
            ]
        ],
        "resources": {"cpu_cores": 8, "memory_bytes": 24 << 30, "processes": 2048},
        "timeout_seconds": 1800,
        "max_attempts": 1,
        "expected_artifacts": ["flow_archive"],
    }
    if objective is not None:
        from eda_toolkits.objectives import bind_task_objective

        bind_task_objective(spec, objective)
    submit(state, key, spec)
    record = collect(state, key)
    if record["run"]["status"] != "succeeded":
        raise RuntimeError("Native stage failed: " + key)
    client = KernelClient(
        json.loads((state / "runtime.json").read_text())["kernel_url"]
    )
    archive = next(a for a in record["artifacts"] if a["kind"] == "flow_archive")
    path = state / "tasks" / key / "flow.zip"
    client.materialize_artifact(
        record["run"]["run_id"], archive["artifact_id"], str(path)
    )
    consumed = verify_stage_archive(path, expected_placement_sha256, phase)
    record["checkpoint"] = {"path": str(path), "artifact": archive}
    record["placement_input_sha256"] = expected_placement_sha256
    record["consumption_log"] = consumed
    write_json(state / "tasks" / key / "handoff-verification.json", record)
    return record


def resume(
    state: Path,
    key: str,
    *,
    design: str,
    profile: Path,
    config: Path,
    sdc: Path,
    flow_archive: Path,
    placement: Path,
    parent_run: str,
    objective: Path | None = None,
) -> dict:
    if objective is not None:
        from eda_toolkits.objectives import load_objective, verify_conditions

        verify_conditions(load_objective(objective), sdc=sdc)
    output = state / "handoffs" / key
    output.mkdir(parents=True, exist_ok=False)
    checkpoint = output / "placement.zip"
    placement_archive(flow_archive, placement, checkpoint, sdc)
    sha = digest(placement)
    cts = stage(
        state,
        key + "-cts",
        design=design,
        phase="cts",
        profile=profile,
        config=config,
        sdc=sdc,
        checkpoint=checkpoint,
        parent_run=parent_run,
        expected_placement_sha256=sha,
        objective=objective,
    )
    route = stage(
        state,
        key + "-route",
        design=design,
        phase="route_finish",
        profile=profile,
        config=config,
        sdc=sdc,
        checkpoint=Path(cts["checkpoint"]["path"]),
        parent_run=cts["run"]["run_id"],
        expected_placement_sha256=sha,
        objective=objective,
    )
    with zipfile.ZipFile(route["checkpoint"]["path"]) as archive:
        for name in archive.namelist():
            if name.startswith("flow/results/") and not name.endswith("/"):
                target = output / "results" / Path(name).name
                target.parent.mkdir(exist_ok=True)
                target.write_bytes(archive.read(name))
    write_json(
        output / "handoff.json",
        {
            "parent_run_id": parent_run,
            "placement_sha256": sha,
            "cts_run_id": cts["run"]["run_id"],
            "route_run_id": route["run"]["run_id"],
            "predecessor_preserved": True,
            "sdc_sha256": digest(sdc),
            "shared_objective": str(objective) if objective else None,
        },
    )
    return route
