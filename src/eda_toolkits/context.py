"""Transport Query evidence into professional prompts and public EF tasks."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

ENVIRONMENT_VARIABLE = "EDA_PLATFORM_CONTEXT"


def load_context(path: str | Path) -> dict[str, Any]:
    value: dict[str, Any] = json.loads(Path(path).read_text())
    if value["schema_version"] != "chip-evolve.design-context.v1":
        raise ValueError("Unsupported professional context schema")
    body = {key: item for key, item in value.items() if key != "context_id"}
    actual = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if value["context_id"] != actual:
        raise ValueError("Frozen professional context changed")
    return value


def prompt_context(value: dict[str, Any]) -> str:
    return (
        "\n<platform_design_diagnosis>\n"
        "Query supplied these scoped facts and cited diagnoses for your actual input design. "
        "Use them when choosing mechanisms and explaining actions. Hypotheses remain hypotheses; "
        "retain native live queries and professional scoring. This packet grants no additional edit permissions.\n"
        + json.dumps(value, sort_keys=True, indent=2)
        + "\n</platform_design_diagnosis>\n"
    )


def append_context(prompt: str) -> str:
    path = os.environ.get(ENVIRONMENT_VARIABLE)
    return prompt + prompt_context(load_context(path)) if path else prompt


def context_messages(payload: dict[str, Any]) -> dict[str, Any]:
    path = os.environ.get(ENVIRONMENT_VARIABLE)
    if not path:
        return payload
    return {
        **payload,
        "messages": [
            *payload["messages"],
            {"role": "user", "content": prompt_context(load_context(path))},
        ],
    }


def bind_task_context(
    spec: dict[str, Any], path: str | Path | None = None
) -> dict[str, Any]:
    path = path or os.environ.get(ENVIRONMENT_VARIABLE)
    if not path:
        return spec
    value = load_context(path)
    if spec["design_id"] != value["scope"]["design_id"]:
        raise ValueError("Professional context belongs to another design")
    spec["labels"].update(
        design_context_id=value["context_id"],
        input_snapshot_id=value["scope"]["snapshot_id"],
    )
    spec["inputs"]["design_context_path"] = "inputs/design-context.json"
    spec["staged_inputs"].append(
        {
            "source": str(Path(path).resolve()),
            "destination": "inputs/design-context.json",
        }
    )
    return spec
