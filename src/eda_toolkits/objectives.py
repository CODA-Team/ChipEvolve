"""Frozen business goals shared by professional prompts and final measurements.

This module records conditions and constraints; it does not score or promote
candidates. Native professional search and Codex's final judgment stay separate.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

ENVIRONMENT_VARIABLE = "EDA_PLATFORM_OBJECTIVE"
SCHEMA = "chip-evolve.objective.v1"


def file_sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def objective_id(value: dict[str, Any]) -> str:
    body = {key: item for key, item in value.items() if key != "objective_id"}
    return hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def load_objective(path: str | Path) -> dict[str, Any]:
    value: dict[str, Any] = json.loads(Path(path).read_text())
    if value["schema_version"] != SCHEMA:
        raise ValueError("Unsupported shared objective schema")
    if value["objective_id"] != objective_id(value):
        raise ValueError("Shared objective changed after it was frozen")
    conditions = value["conditions"]
    if not conditions["libraries"] or not conditions["sdc"]:
        raise ValueError("Shared conditions require actual libraries and SDC")
    return value


def verify_conditions(value: dict[str, Any], *, sdc: Path | None = None) -> None:
    """Verify the actual files, including identically named different libraries."""
    conditions = value["conditions"]
    bindings = [*conditions["libraries"], conditions["sdc"]]
    for binding in bindings:
        path = Path(binding["path"])
        if file_sha256(path) != binding["sha256"]:
            raise ValueError("Shared condition file changed: " + str(path))
    if sdc is not None and file_sha256(sdc) != conditions["sdc"]["sha256"]:
        raise ValueError("Measurement SDC differs from the shared objective")


def condition_id(value: dict[str, Any]) -> str:
    """Comparison identity ignores machine paths, but includes actual contents."""
    conditions = dict(value["conditions"])
    conditions["libraries"] = sorted(row["sha256"] for row in conditions["libraries"])
    conditions["sdc"] = conditions["sdc"]["sha256"]
    return hashlib.sha256(
        json.dumps(conditions, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def require_same_conditions(left: dict[str, Any], right: dict[str, Any]) -> None:
    """Reject cross-condition comparisons; leave metric judgment to Codex."""
    if not left.get("condition_id") or left["condition_id"] != right.get(
        "condition_id"
    ):
        raise ValueError("Measurements have missing or different shared conditions")


def prompt_context(value: dict[str, Any]) -> str:
    """Expose the global goal without replacing the professional objective."""
    context = {
        "objective_id": value["objective_id"],
        "design_id": value["design_id"],
        "reference_run_id": value["reference_run_id"],
        "conditions": value["conditions"],
        "constraints": value["constraints"],
    }
    return (
        "\n<platform_shared_objective>\n"
        "These are the team's final PPA acceptance conditions. Preserve your "
        "native search, scoring and promotion rules. Exploratory intermediates "
        "may trade metrics; label native measurements separately from final "
        "measurements under these conditions. Codex decides final adoption, "
        "retaining the best feasible incumbent when a branch is worse.\n"
        + json.dumps(context, indent=2, sort_keys=True)
        + "\n</platform_shared_objective>\n"
    )


def append_objective(prompt: str) -> str:
    """Opt-in platform context; unset means the original prompt is unchanged."""
    path = os.environ.get(ENVIRONMENT_VARIABLE)
    return prompt + prompt_context(load_objective(path)) if path else prompt


def objective_messages(payload: dict[str, Any]) -> dict[str, Any]:
    path = os.environ.get(ENVIRONMENT_VARIABLE)
    if not path:
        return payload
    return {
        **payload,
        "messages": [
            *payload["messages"],
            {"role": "user", "content": prompt_context(load_objective(path))},
        ],
    }


def bind_task_objective(
    spec: dict[str, Any], path: str | Path | None = None
) -> dict[str, Any]:
    """Attach the same immutable goal using existing public TaskSpec fields."""
    path = path or os.environ.get(ENVIRONMENT_VARIABLE)
    if not path:
        return spec
    value = load_objective(path)
    environment_path = os.environ.get(ENVIRONMENT_VARIABLE)
    if (
        environment_path
        and load_objective(environment_path)["objective_id"] != value["objective_id"]
    ):
        raise ValueError("Model and execution refer to different shared objectives")
    if value["design_id"] != spec["design_id"]:
        raise ValueError("Shared objective belongs to a different design")
    spec["labels"].update(
        objective_id=value["objective_id"],
        final_condition_id=condition_id(value),
    )
    spec["inputs"]["shared_objective_path"] = "inputs/shared-objective.json"
    spec["staged_inputs"].append(
        {
            "source": str(Path(path).resolve()),
            "destination": "inputs/shared-objective.json",
        }
    )
    return spec
