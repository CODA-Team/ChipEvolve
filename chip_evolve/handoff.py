"""Frozen placement handoff and actual downstream consumption checks."""

from __future__ import annotations

import hashlib
import re
import zipfile
from pathlib import Path
from typing import Any

from .jobs import digest


def input_contract(frame: dict[str, Any], capability: str) -> dict[str, Any]:
    """Describe real source bytes and intentional transformations before dispatch."""
    transformations = {
        "flow": "reconstruct registered RTL/ORFS recipe; preserve native stage inheritance",
        "dpl": "consume actual pre-CTS placement from the source archive; continue CTS/route",
        "goal": "remove fillers and signal wires; preserve source cells/connections; run original optimization and routing",
        "eco": "consume routed ODB, SDC and SPEF; apply original local primitives and route calibration",
    }
    paths = {key: Path(value) for key, value in frame["files"].items()}
    if frame.get("flow_archive"):
        paths["flow_archive"] = Path(frame["flow_archive"])
    return {
        "source_run_id": frame["run_id"],
        "design_id": frame["design_id"],
        "objective_id": frame["objective_id"],
        "condition_id": frame["condition_id"],
        "receiver": capability,
        "transformations": transformations[capability],
        "source_files": {
            key: {"path": str(path), "sha256": digest(path)}
            for key, path in paths.items()
        },
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
