"""Resume a saved business request through its original execution and delivery."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import Deployment, read, write
from . import delivery, environment, flow, goal, native_physical, physical
from .jobs import digest


def recover(deployment: Deployment, design_id: str, key: str) -> dict[str, Any]:
    """Reuse successful EDA tasks; never restart unfinished model searches."""
    experiment = deployment.state / "experiments" / design_id / key
    request = read(experiment / "request.json")
    if request["design"] != design_id:
        raise ValueError("Recovery request belongs to another design")
    status = experiment / "status.json"
    if status.exists():
        prior = read(status)
        completed = experiment / "result.json"
        if prior.get("status") == "succeeded" and completed.is_file():
            checkpoint_path = experiment / "delivery-checkpoint.json"
            if checkpoint_path.is_file():
                for name, sha in read(checkpoint_path)["input_hashes"].items():
                    if digest(Path(name)) != sha:
                        raise ValueError("Delivery input changed: " + name)
            result = read(completed)
            if result.get("design_id") != design_id:
                raise ValueError("Completed result belongs to another design")
            if (
                request.get("objective")
                and result.get("objective_id")
                != read(request["objective"])["objective_id"]
            ):
                raise ValueError(
                    "Completed result differs from original requested objective"
                )
            return result
        history = experiment / "status-before-recovery.json"
        if not history.exists():
            write(history, prior)
    pinned_image = deployment.value.get("toolchain", {}).get("image_sha256")
    if request.get("image_sha256") and request["image_sha256"] != pinned_image:
        raise ValueError("Recovery image differs from the original request")
    if request.get("environment"):
        environment_path = Path(request["environment"])
        if (
            request.get("environment_sha256")
            and digest(environment_path) != request["environment_sha256"]
        ):
            raise ValueError("Recovery environment differs from the original request")
        environment.check_environment(
            deployment,
            environment_path,
            design_id,
            request["capability"],
            Path(request["source"]) if request.get("source") else None,
            request.get("flow_recipe", "legacy"),
        )
    elif deployment.value.get("runtime") and pinned_image:
        environment.verify_runtime_image(deployment)
    if (experiment / "delivery-checkpoint.json").exists():
        result = delivery.finish(deployment, experiment)
    elif (
        request["capability"] == "orfs"
        and request.get("operation") == "replay"
        and request.get("source")
        and not (experiment / "jobs/orfs/task.json").exists()
    ):
        result = native_physical.repair(
            deployment,
            design_id,
            experiment,
            Path(request["source"]),
            request["seconds"],
            objective=Path(request["objective"]) if request.get("objective") else None,
        )
    elif request["capability"] == "orfs":
        result = physical.baseline(
            deployment,
            design_id,
            experiment,
            request["seconds"],
            objective=Path(request["objective"]) if request.get("objective") else None,
        )
    elif request["capability"] == "flow":
        objective = Path(read(experiment / "input-receipt.json")["objective"])
        result = flow.collect_flow(deployment, design_id, experiment, objective)
    elif (
        request["capability"] == "goal"
        and request.get("operation") == "evolve"
        # The Goal CLI writes this receipt after its native search returns.
        and (experiment / "campaign/toolchain.json").is_file()
    ):
        goal.restore_goal_checkpoint(experiment, design_id)
        result = delivery.finish(deployment, experiment)
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
