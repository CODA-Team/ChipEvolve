"""Persist Codex adoption decisions with existing goal and fact boundaries."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from eda_toolkits.objectives import require_same_conditions

from .config import Deployment, read, write


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


def select(deployment: Deployment, result_path: Path, reason: str) -> dict[str, Any]:
    candidate = read(result_path)
    failed = violations(candidate)
    pointer = deployment.state / "designs" / candidate["design_id"] / "incumbent.json"
    if pointer.exists():
        incumbent_path = read(pointer)["result"]
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
    }
    if not failed:
        write(
            pointer,
            {
                "result": str(result_path),
                "run_id": candidate["run_id"],
                "objective_id": candidate["objective_id"],
                "reason": reason,
            },
        )
        receipt["incumbent"] = str(result_path)
    write(result_path.parent / "adoption.json", receipt)
    return receipt
