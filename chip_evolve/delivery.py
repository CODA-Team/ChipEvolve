"""Recover deterministic delivery after an original professional has finished."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import Deployment, read, write
from .jobs import Jobs, digest


def checkpoint(
    experiment: Path,
    *,
    design_id: str,
    odb: Path,
    producer: str,
    objective: Path,
    native_method: dict[str, Any],
    pdk: Path | None = None,
    source: Path | None = None,
) -> None:
    inputs = [odb, objective]
    if pdk:
        inputs += [pdk / "setRC.tcl", pdk / "rcx_patterns.rules"]
    if source:
        inputs.append(source)
    value = {
        "design_id": design_id,
        "kind": "layout" if source else "qualify",
        "odb": str(odb.resolve()),
        "producer": producer,
        "objective": str(objective.resolve()),
        "pdk": str(pdk.resolve()) if pdk else None,
        "source": str(source.resolve()) if source else None,
        "input_hashes": {str(p.resolve()): digest(p) for p in inputs},
        "native_method": native_method,
    }
    path = experiment / "delivery-checkpoint.json"
    if path.exists() and read(path) != value:
        raise ValueError("A completed professional delivery checkpoint cannot change")
    write(path, value)


def finish(deployment: Deployment, experiment: Path) -> dict[str, Any]:
    from .physical import qualify
    from .professional import resume_layout

    saved = read(experiment / "delivery-checkpoint.json")
    for name, sha in saved["input_hashes"].items():
        if digest(Path(name)) != sha:
            raise ValueError("Delivery input changed: " + name)
    jobs = Jobs(deployment, saved["design_id"], experiment)
    odb, objective = Path(saved["odb"]), Path(saved["objective"])
    if saved["kind"] == "layout":
        result = resume_layout(
            jobs, odb, read(saved["source"]), objective, saved["producer"]
        )
    else:
        result = qualify(jobs, odb, saved["producer"], objective, Path(saved["pdk"]))
    result["native_method"] = saved["native_method"]
    write(experiment / "result.json", result)
    return result


def recover(deployment: Deployment, design_id: str, key: str) -> dict[str, Any]:
    """Reuse successful EDA tasks; never restart unfinished model searches."""
    from .physical import baseline
    from .professional import collect_flow

    experiment = deployment.state / "experiments" / design_id / key
    request = read(experiment / "request.json")
    if request["design"] != design_id:
        raise ValueError("Recovery request belongs to another design")
    status = experiment / "status.json"
    if status.exists():
        prior = read(status)
        history = experiment / "status-before-recovery.json"
        if not history.exists():
            write(history, prior)
    if (experiment / "delivery-checkpoint.json").exists():
        result = finish(deployment, experiment)
    elif request["capability"] == "orfs":
        result = baseline(deployment, design_id, experiment, request["seconds"])
    elif request["capability"] == "flow":
        objective = Path(read(experiment / "input-receipt.json")["objective"])
        result = collect_flow(deployment, design_id, experiment, objective)
    else:
        raise ValueError(
            "Native professional has no completed delivery checkpoint; "
            "preserve its session instead of rerunning the search"
        )
    write(status, {"status": "succeeded", "delivery_recovered": True})
    write(
        experiment / "delivery-recovery.json",
        {
            "status": "succeeded",
            "result": str(experiment / "result.json"),
            "run_id": result.get("run_id"),
            "candidate_results": result.get("candidate_results", []),
            "native_search_restarted": False,
        },
    )
    return result
