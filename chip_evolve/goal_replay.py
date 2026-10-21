"""Bind an existing Goal source result to its original native evaluation mode."""

from __future__ import annotations

import hashlib
import json
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
    origin = result.parent
    candidate_evidence = None
    if method.get("kind") == "native-search":
        parent = method["parent"]
        source = origin / "campaign/parents" / parent["source_hash"] / "source"
        if (
            not source.is_dir()
            or not (source.parent / ".source_snapshot_complete").is_file()
        ):
            raise ValueError("Goal replay needs the original complete source snapshot")
    elif (
        method.get("kind") == "native-candidate" and method.get("capability") == "goal"
    ):
        origin = Path(method["origin_experiment"])
        parent, source, candidate_evidence = candidate_binding(method["candidate"])
    else:
        raise ValueError(
            "Goal --code-source requires a native-search or measured Goal native-candidate result.json"
        )
    mode = parent["evaluation_mode"]
    if mode not in {"power_only", "timing_only", "power_then_timing"}:
        raise ValueError("Goal replay has no supported original evaluation mode")
    config = origin / "evolve-config.json"
    settings = read(config)
    saved = read(result.parent / "delivery-checkpoint.json")
    records = [
        p
        for p in (origin / "operations").glob("*/execution.json")
        if read(p)["run"]["run_id"] == saved["producer"]
    ]
    if len(records) != 1 or read(records[0])["run"]["status"] != "succeeded":
        raise ValueError("Goal source has no unique successful native producer")
    request = records[0].parent / "request.json"
    files = read(request)["source_files"]
    if not files or any(digest(source / name) != sha for name, sha in files.items()):
        raise ValueError("Goal source differs from its measured native producer")
    if (
        candidate_evidence
        and Path(read(request)["source"]).resolve() != source.resolve()
    ):
        raise ValueError("Goal candidate source does not belong to its native producer")
    return {
        "original_result": reference(result),
        "origin_design_id": frame["design_id"],
        "original_config": reference(config),
        "source_root": str(source.resolve()),
        "source_identity": {
            "producer_run_id": saved["producer"],
            "request": reference(request),
            "checked_files": len(files),
            **(
                {"candidate_evidence": candidate_evidence} if candidate_evidence else {}
            ),
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


def candidate_binding(
    candidate: dict[str, Any],
) -> tuple[dict[str, Any], Path, dict[str, Any]]:
    """Recover a measured candidate's exact source/recipe without promoting it."""
    for role in ("native_record", "native_verdict_record"):
        ref = candidate[role]
        if digest(Path(ref["path"])) != ref["sha256"]:
            raise ValueError("Goal candidate evidence changed: " + role)
    record_path = Path(candidate["native_record"]["path"])
    record = read(record_path)
    checks = {row["name"]: row["passed"] for row in record["checks"]}
    if record.get("evaluation_error") or not all(
        checks.get(name) is True
        for name in ("build", "flow", "metrics", "placement", "lec")
    ):
        raise ValueError("Goal candidate has no complete successful native evaluation")
    source = Path(record["artifacts"]["candidate_source"])
    if not source.is_dir() or record["source_commit"] != candidate["source_ref"]:
        raise ValueError(
            "Goal candidate source identity differs from its measured record"
        )
    manifest = read(record_path.parent.parent / "workspace_manifest.json")
    # Same persisted identity formula as the native controller, without changing
    # its parent pointer, Teacher decision, EPD or promotion state.
    identity = {
        "parent": manifest["parent_source_hash"],
        "diff": record["implementation_diff"],
        "commit": record["source_commit"],
    }
    source_hash = hashlib.sha256(
        json.dumps(
            identity,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode()
    ).hexdigest()
    verdict = read(candidate["native_verdict_record"]["path"])
    parent = {
        "parent_id": "fixed-candidate:" + candidate["candidate_id"],
        "metrics": record["metrics"],
        "source_commit": record["source_commit"],
        "source_hash": source_hash,
        "goal_distance": verdict["goal_distance"],
        "evaluation_mode": record["hypothesis"]["evaluation_mode"],
        "timing_recipe_id": record["hypothesis"]["timing_recipe_id"],
    }
    evidence = {
        "candidate_record": reference(record_path),
        "verdict_record": reference(Path(candidate["native_verdict_record"]["path"])),
        "workspace_manifest": reference(
            record_path.parent.parent / "workspace_manifest.json"
        ),
        "native_promotion_changed": False,
    }
    return parent, source, evidence


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
