"""Frozen placement handoff and actual downstream consumption checks."""

from __future__ import annotations

import hashlib
import re
import zipfile
from pathlib import Path
from typing import Any, Mapping

from .config import read
from .contracts import FlowRecipe, Handoff, PhysicalResult, SpecialistKind
from .handoff_io import parse_handoff
from .jobs import Jobs, digest
from .result_io import freeze, object_at, wire_object


def registered_files(
    jobs: Jobs,
    frame: dict[str, Any],
    names: tuple[str, ...],
    *,
    mode: str = "orfs",
    local: bool = True,
) -> dict[str, Any]:
    """Check the exact registered export and the files the receiver will read."""
    export = frame.get("exports", {}).get(mode, {}).get("execution")
    if not export:
        raise ValueError("Handoff source has no registered " + mode + " export")
    producer = export["run"]["run_id"]
    run = jobs.client.run(producer)
    if (
        run["status"] != "succeeded"
        or run["design_id"] != jobs.design_id
        or run["labels"].get("analysis_of_run_id") != frame["run_id"]
    ):
        raise ValueError("Handoff export belongs to another source run")
    registered = {row["artifact_id"]: row for row in jobs.client.artifacts(producer)}
    files = {}
    for name in names:
        suffix = ".json" if name == "metrics" else "." + name
        matches = [a for a in export["artifacts"] if a["store_key"].endswith(suffix)]
        if name == "metrics":
            matches = [a for a in matches if a["kind"] == "raw_flow_metadata"]
        if len(matches) != 1:
            raise ValueError("Handoff requires one registered source artifact: " + name)
        saved = matches[0]
        artifact = registered.get(saved["artifact_id"])
        if (
            not artifact
            or artifact["sha256"] != saved["sha256"]
            or artifact["store_key"] != saved["store_key"]
        ):
            raise ValueError("Handoff artifact differs from the EF registry: " + name)
        files[name] = {
            "run_id": producer,
            "artifact_id": artifact["artifact_id"],
            "sha256": artifact["sha256"],
        }
        if local:
            path = Path(frame["files"][name])
            if digest(path) != artifact["sha256"]:
                raise ValueError(
                    "Handoff source file differs from registered artifact: " + str(path)
                )
            files[name]["path"] = str(path)
    return files


def registered_archive(jobs: Jobs, frame: dict[str, Any]) -> dict[str, str]:
    if not (frame.get("flow_archive") or frame.get("native_inputs")):
        raise ValueError("Placement handoff requires a registered ORFS archive")
    producer = frame["physical_run_id"]
    measured = jobs.client.run(frame["run_id"])
    if (
        measured["status"] != "succeeded"
        or measured["design_id"] != jobs.design_id
        or measured["labels"].get("parent_run_id") != producer
    ):
        raise ValueError("Handoff archive belongs to another physical run")
    if frame.get("flow_archive"):
        path = Path(frame["flow_archive"])
    else:
        native = read(frame["native_inputs"])
        if native["run_id"] != producer:
            raise ValueError(
                "Handoff native input receipt belongs to another physical run"
            )
        path = Path(native["archive"])
    records = [
        a for a in jobs.client.artifacts(producer) if a["kind"] == "flow_archive"
    ]
    if len(records) != 1 or digest(path) != records[0]["sha256"]:
        raise ValueError(
            "Handoff archive differs from registered physical artifact: " + str(path)
        )
    return {
        "path": str(path),
        "run_id": producer,
        "artifact_id": records[0]["artifact_id"],
        "sha256": records[0]["sha256"],
    }


def input_contract(
    jobs: Jobs, frame: dict[str, Any], capability: str, *, flow_recipe: str = "legacy"
) -> dict[str, Any]:
    """Describe real source bytes and intentional transformations before dispatch."""
    transformations = {
        "flow": "reconstruct registered RTL/ORFS recipe; preserve native stage inheritance",
        "dpl": "consume actual pre-CTS placement from the source archive; continue CTS/route",
        "goal": "remove fillers and signal wires; preserve source cells/connections; run original optimization and routing",
        "eco": "consume routed ODB, SDC and SPEF; apply original local primitives and route calibration",
    }
    files: dict[str, Any] = {}
    if capability == "goal":
        files = registered_files(jobs, frame, ("odb", "sdc", "v", "def"))
    elif capability == "dpl":
        files["flow_archive"] = registered_archive(jobs, frame)
    elif capability == "eco":
        files = registered_files(
            jobs, frame, ("odb", "sdc", "spef"), mode="opendb", local=False
        )
    elif flow_recipe == "legacy":
        files = registered_files(jobs, frame, ("sdc",))
    return {
        "source_run_id": frame["run_id"],
        "design_id": frame["design_id"],
        "objective_id": frame["objective_id"],
        "condition_id": frame["condition_id"],
        "receiver": capability,
        "transformations": transformations[capability],
        "source_files": files,
        "flow_recipe": frame.get("flow_recipe"),
        "native_method": frame.get("native_method"),
        "acceptance": "exploratory input; original final constraints and native algorithm remain in force",
    }


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


def flatten_archive(original: Path, destination: Path) -> None:
    """Normalize the stock nested ORFS tree and A2's already-flat tree alike."""
    with (
        zipfile.ZipFile(original) as source,
        zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as result,
    ):
        names = set()
        for name in source.namelist():
            parts = Path(name).parts
            if (
                len(parts) < 3
                or parts[:2]
                not in {
                    ("flow", "results"),
                    ("flow", "logs"),
                    ("flow", "reports"),
                    ("flow", "objects"),
                }
                or name.endswith("/")
            ):
                continue
            target = "flow/" + parts[1] + "/" + parts[-1]
            if target in names:
                raise ValueError(
                    "Choose one design/revision checkpoint, not a mixed archive"
                )
            names.add(target)
            result.writestr(target, source.read(name))


def build_handoff(
    jobs: Jobs,
    source: PhysicalResult,
    receiver: SpecialistKind,
    *,
    flow_recipe: FlowRecipe = "legacy",
) -> Handoff:
    """Registry verification owns assembly; the reader owns field contracts."""
    wire = input_contract(
        jobs, wire_object(source.wire), receiver, flow_recipe=flow_recipe
    )
    return parse_handoff(
        object_at(freeze(wire), "$"), source, receiver, flow_recipe=flow_recipe
    )


def require_dispatch_inputs(
    source: PhysicalResult, receiver: SpecialistKind, recipe: FlowRecipe
) -> None:
    """Check required roles before any fact materialization or registry operation."""
    from .contracts import BusinessInputError
    from .result_io import read_document, path_value, required

    if receiver == "dpl":
        if source.physical_run_id is None:
            raise BusinessInputError(
                "missing_field", "$.physical_run_id", "placement producer required"
            )
        if not source.wire.get("flow_archive"):
            if source.native_inputs is None:
                raise BusinessInputError(
                    "missing_field",
                    "$.native_inputs",
                    "registered placement archive required",
                )
            _, native = read_document(source.native_inputs)
            path_value(
                required(native, "archive"),
                source.native_inputs.parent,
                "$.native_inputs.archive",
            )
            if required(native, "run_id") != source.physical_run_id:
                raise BusinessInputError(
                    "identity_mismatch",
                    "$.native_inputs.run_id",
                    "archive belongs to another physical run",
                )
        return
    if receiver == "flow" and recipe == "source":
        return  # prepare_native_source owns registered recipe reconstruction.
    roles = {
        "goal": ("odb", "sdc", "v", "def"),
        "eco": ("odb", "sdc", "spef"),
        "flow": ("sdc",),
    }[receiver]
    mode = "opendb" if receiver == "eco" else "orfs"
    if receiver != "eco":
        for role in roles:
            source.files.require(role)
    if mode not in source.exports:
        # Deferred publication can create this exact view, after input validation.
        deferred = source.wire.get("deferred_facts")
        if not (
            mode == "opendb" and isinstance(deferred, Mapping) and mode in deferred
        ):
            raise BusinessInputError(
                "missing_field",
                "$.exports." + mode,
                "registered source export required",
            )
