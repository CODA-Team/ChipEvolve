"""Persist Codex adoption decisions with existing goal and fact boundaries."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from eda_toolkits.objectives import (
    load_objective,
    require_same_conditions,
    verify_conditions,
)

from .config import Deployment, adoption_lock, read, write
from .jobs import digest


def violations(frame: dict[str, Any]) -> list[str]:
    goal = read(frame["objective"])
    metrics, limits = frame["metrics"], goal["constraints"]
    pairs = {
        "max_slew_violations": "finish__timing__drv__max_slew",
        "max_cap_violations": "finish__timing__drv__max_cap",
        "placement_violations": "design__violations",
        "power_total_w_max": "finish__power__total",
        "cell_area_um2_max": "finish__design__instance__area",
        "core_area_um2_max": "finish__design__core__area",
        "die_area_um2_max": "finish__design__die__area",
    }
    failed = [
        limit for limit, metric in pairs.items() if metrics[metric] > limits[limit]
    ]
    failed += [
        name
        for name, metric in {
            "setup_tns_ns_min": "finish__timing__setup__tns",
            "hold_tns_ns_min": "finish__timing__hold__tns",
        }.items()
        if metrics[metric] < limits[name]
    ]
    if frame.get("route_drc") is None or frame["route_drc"] > limits["route_drc"]:
        failed.append("route_drc")
    return failed


def checked_validation(result_path: Path, validation: Path) -> dict[str, Any]:
    """Bind adoption to the existing proof, exact replay and frozen objective."""
    from .comparisons import METRICS

    candidate, receipt = read(result_path), read(validation)
    if receipt["result_sha256"] != digest(result_path):
        raise ValueError("Validation belongs to a different or changed result")
    reference_path = Path(receipt["reference"])
    if receipt["reference_sha256"] != digest(reference_path):
        raise ValueError("Validated reference changed")
    reference = read(reference_path)
    require_same_conditions(reference, candidate)
    goal = load_objective(candidate["objective"])
    verify_conditions(goal)
    if (
        reference["design_id"] != candidate["design_id"]
        or reference["objective_id"] != candidate["objective_id"]
        or goal["objective_id"] != candidate["objective_id"]
        or goal["design_id"] != candidate["design_id"]
    ):
        raise ValueError("Validation and candidate have different business goals")
    proof, replay = receipt["logic"], receipt["independent_replay"]
    if proof.get("engine") == "eqy":
        from .eqy import qualified_strategy

        qualified_strategy({"equivalence_strategy": proof.get("strategy", "sat")})
    if (
        not all(
            receipt[key] is True
            for key in ("passed", "replay_exact", "sdk_identity_passed")
        )
        or proof["proven_points"] <= 0
        or proof["unproven_points"] != 0
        or proof["proven_points"] != proof["top_output_bits"]
        or replay["reference_run_id"] != candidate["run_id"]
        or replay["condition_id"] != candidate["condition_id"]
        or replay["objective_id"] != candidate["objective_id"]
        or replay["constraint_violations"]
        or any(replay["deltas"][key]["delta"] != 0 for key in METRICS)
    ):
        raise ValueError("Adoption requires complete proof and exact feasible replay")
    for name, sha in proof["input_hashes"].items():
        if digest(Path(name)) != sha:
            raise ValueError("Validated proof input changed: " + name)
    return {
        "validation": str(validation.resolve()),
        "validation_sha256": digest(validation),
        "result_sha256": digest(result_path),
        "reference_run_id": reference["run_id"],
        "design_revision_sha256": digest(Path(reference["files"]["v"])),
        "objective_id": candidate["objective_id"],
        "condition_id": candidate["condition_id"],
    }


def select(
    deployment: Deployment, result_path: Path, reason: str, *, validation: Path
) -> dict[str, Any]:
    candidate = read(result_path)
    verified = checked_validation(result_path, validation)
    scope = {
        key: verified[key]
        for key in ("design_revision_sha256", "objective_id", "condition_id")
    }
    scope_id = hashlib.sha256(json.dumps(scope, sort_keys=True).encode()).hexdigest()
    directory = deployment.state / "designs" / candidate["design_id"]
    with adoption_lock(directory):
        # A result cannot change between validation and publication.
        if digest(result_path) != verified["result_sha256"]:
            raise ValueError("Candidate changed during adoption")
        return _select(directory, result_path, candidate, reason, verified, scope_id)


def _select(
    directory: Path,
    result_path: Path,
    candidate: dict[str, Any],
    reason: str,
    verified: dict[str, Any],
    scope_id: str,
) -> dict[str, Any]:
    failed = violations(candidate)
    pointer = directory / "scopes" / scope_id / "incumbent.json"
    if pointer.exists():
        saved = read(pointer)
        incumbent_path = saved["result"]
        if digest(Path(incumbent_path)) != saved["result_sha256"]:
            raise ValueError("Retained result changed after adoption")
        incumbent = read(incumbent_path)
        require_same_conditions(incumbent, candidate)
        if candidate["objective_id"] != incumbent["objective_id"]:
            raise ValueError("Adoption compares different business goals")
        # Codex chooses the tradeoff; this only prevents replacing an incumbent
        # with a result that is strictly worse on every requested PPA quantity.
        quantities = [
            "finish__timing__setup__tns",
            "finish__power__total",
            "finish__design__instance__area",
        ]
        old, new = incumbent["metrics"], candidate["metrics"]
        if (
            new[quantities[0]] <= old[quantities[0]]
            and all(new[k] >= old[k] for k in quantities[1:])
            and any(new[k] != old[k] for k in quantities)
        ):
            failed.append("dominated_incumbent")
    receipt = {
        "design_id": candidate["design_id"],
        "candidate": str(result_path),
        "codex_reason": reason,
        "adopted": not failed,
        "failed_conditions": failed,
        "incumbent": read(pointer)["result"] if pointer.exists() else None,
        "scope_id": scope_id,
        **verified,
    }
    if not failed:
        retained = {
            "result": str(result_path),
            "run_id": candidate["run_id"],
            "objective_id": candidate["objective_id"],
            "reason": reason,
            "scope_id": scope_id,
            **verified,
        }
        write(pointer, retained)
        # A convenience projection of the selected scope, not a cross-goal winner.
        write(directory / "incumbent.json", retained)
        receipt["incumbent"] = str(result_path)
    decision = directory / "decisions" / (uuid4().hex + ".json")
    receipt["decision"] = str(decision)
    write(decision, receipt)
    return receipt
