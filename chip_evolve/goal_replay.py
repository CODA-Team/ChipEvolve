"""Bind an existing Goal source result to its original native evaluation mode."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import Deployment, read
from .environment import reference
from .jobs import digest


def descriptor(deployment: Deployment, result: Path) -> dict[str, Any]:
    frame = read(result)
    if frame["conditions"]["toolchain"] != deployment.value["toolchain"]:
        raise ValueError("Goal replay source uses a different common toolchain")
    method = frame.get("native_method") or {}
    if method.get("kind") != "native-search":
        raise ValueError(
            "Goal --code-source requires an explicit native-search result.json"
        )
    parent = method["parent"]
    mode = parent["evaluation_mode"]
    if mode not in {"power_only", "timing_only", "power_then_timing"}:
        raise ValueError("Goal replay has no supported original evaluation mode")
    source = result.parent / "campaign/parents" / parent["source_hash"] / "source"
    if (
        not source.is_dir()
        or not (source.parent / ".source_snapshot_complete").is_file()
    ):
        raise ValueError("Goal replay needs the original complete source snapshot")
    config = result.parent / "evolve-config.json"
    settings = read(config)
    saved = read(result.parent / "delivery-checkpoint.json")
    records = [
        p
        for p in (result.parent / "operations").glob("*/execution.json")
        if read(p)["run"]["run_id"] == saved["producer"]
    ]
    if len(records) != 1 or read(records[0])["run"]["status"] != "succeeded":
        raise ValueError("Goal source has no unique successful native producer")
    request = records[0].parent / "request.json"
    files = read(request)["source_files"]
    if not files or any(digest(source / name) != sha for name, sha in files.items()):
        raise ValueError("Goal source differs from its measured native producer")
    return {
        "original_result": reference(result),
        "origin_design_id": frame["design_id"],
        "original_config": reference(config),
        "source_root": str(source.resolve()),
        "source_identity": {
            "producer_run_id": saved["producer"],
            "request": reference(request),
            "checked_files": len(files),
        },
        "parent": parent,
        "evaluation_mode": mode,
        "timing_recipe_id": parent["timing_recipe_id"],
        "recipe_parameters": {
            k: settings[k]
            for k in (
                "power_reclaim_phase",
                "power_reclaim_proportion_percent",
                "power_reclaim_max_moves",
                "power_stage_tns_ceiling_ns",
            )
            if k in settings
        },
        "interpretation": "Fixed original source and recipe, not a new Student or promotion. Parent metrics belong to the original design experiment, not this target design.",
    }


def write_driver(path: Path) -> None:
    """The subprocess belongs to the native project; no peer imports in the root."""
    path.write_text("""from pathlib import Path
import json,sys
from goalevolve.config import load_config,build_runtime
from goalevolve.core.models import Parent
from goalevolve.core.io import atomic_json
from goalevolve.execution.workspace import clone_source_tree
config=load_config(Path(sys.argv[1]))
method=json.loads(Path(sys.argv[2]).read_text())
contract,registry=build_runtime(config)
output=config.state_root
source=output/'workspace/source'
clone_source_tree(Path(method['source_root']),source)
parent=Parent(**method['parent'])
result=registry.evaluator(config.evaluator).evaluate_parent(
    contract=contract,parent=parent,source=source,output=output,
    optimization_mode=method['evaluation_mode'],
    timing_recipe_id=method['timing_recipe_id'])
atomic_json(output/'baseline.json',result)
if not result['ok']:
    raise SystemExit('Native fixed-source evaluation failed; evidence retained')
""")
