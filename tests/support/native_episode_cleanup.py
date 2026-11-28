"""Retire explicitly owned EF scopes after a budgeted native episode stops."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from chip_evolve.config import Deployment
from chip_evolve.jobs import Jobs
from chip_evolve.lifecycle import TERMINAL


@dataclass
class CleanupPlan:
    deployment: Deployment
    experiments: list[tuple[str, Path]]
    settle_seconds: float


def prepare(spec: dict[str, Any]) -> CleanupPlan | None:
    value = spec.get("platform_timeout_cleanup")
    if value is None:
        return None
    config = Path(value["config"]).resolve()
    if str(config) not in spec["input_hashes"]:
        raise ValueError("Pin the timeout cleanup deployment in input_hashes")
    deployment = Deployment(config)
    experiments = []
    for row in value["experiments"]:
        design_id = row["design_id"]
        deployment.design(design_id)
        boundary = (deployment.state / "experiments" / design_id).resolve()
        path = (boundary / row["key"]).resolve()
        if path == boundary or not path.is_relative_to(boundary):
            raise ValueError("Timeout cleanup scope escapes its design boundary")
        if path.exists():
            raise ValueError(
                "Timeout cleanup requires fresh episode scopes: " + str(path)
            )
        experiments.append((design_id, path))
    settle_seconds = float(value.get("settle_seconds", 30))
    if not experiments or settle_seconds <= 0:
        raise ValueError(
            "Timeout cleanup needs explicit scopes and a positive settle window"
        )
    return CleanupPlan(deployment, experiments, settle_seconds)


def retire(plan: CleanupPlan) -> dict[str, Any]:
    started = time.monotonic()
    receipts, errors, runs = [], [], {}
    for design_id, path in plan.experiments:
        if not path.is_dir():
            continue
        try:
            jobs = Jobs(plan.deployment, design_id, path)
            receipt = jobs.cancel_active()
            receipts.append({"experiment": str(path), **receipt})
            for item in receipt["cancel_requests"]:
                runs[item["run_id"]] = jobs.client
        except Exception as error:
            errors.append(
                {
                    "experiment": str(path),
                    "error_type": type(error).__name__,
                    "error": str(error),
                }
            )
    pending, terminal = dict(runs), {}
    deadline = time.monotonic() + plan.settle_seconds
    while pending:
        for run_id, client in list(pending.items()):
            try:
                row = client.run(run_id)
            except Exception as error:
                errors.append(
                    {
                        "run_id": run_id,
                        "error_type": type(error).__name__,
                        "error": str(error),
                    }
                )
                del pending[run_id]
                continue
            if row["status"] in TERMINAL:
                terminal[run_id] = row
                del pending[run_id]
        if not pending or time.monotonic() >= deadline:
            break
        time.sleep(0.1)
    return {
        "status": "completed" if not pending and not errors else "incomplete",
        "cancel_receipts": receipts,
        "terminal_runs": terminal,
        "not_confirmed_terminal": list(pending),
        "errors": errors,
        "wall_seconds": time.monotonic() - started,
        "scope": "Explicit fresh business scopes only, including explicitly listed validation children. Existing Jobs.cancel_active also resolves native Flow campaign scopes. EF owns tool termination; requests alone are not terminal proof.",
        "cost": "Cleanup wall time is included in episode wall_seconds; EF attempts and service CPU remain separately metered, never added twice.",
    }
