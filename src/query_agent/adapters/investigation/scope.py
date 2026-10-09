"""Selectors resolve before investigation effects; ambiguity never picks latest."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, cast

from eda_ai_client import EdaAiClient
from pydantic import TypeAdapter


def resolve_requests(
    client: EdaAiClient, selectors: object, *, question: str, output: Path
) -> dict[str, Any]:
    choices = TypeAdapter(list[dict[str, str]]).validate_python(selectors, strict=True)
    if not 1 <= len(choices) <= 2:
        raise ValueError("scope request needs one or two selector objects")
    allowed = {"snapshot_id", "design_id", "revision_id", "run_id", "stage", "origin"}
    resolutions: list[dict[str, Any]] = []
    ids: list[str] = []
    for selector in choices:
        if set(selector) - allowed:
            raise ValueError("unknown scope selector")
        if not all(value for value in selector.values()):
            raise ValueError("scope selectors must be nonempty strings")
        response = client.read_query("/scope", parameters={"origin": "all", **selector})
        resolutions.append(response)
        snapshot = cast(dict[str, Any] | None, response.get("data", {}).get("snapshot"))
        if isinstance(snapshot, dict) and isinstance(snapshot.get("snapshot_id"), str):
            ids.append(snapshot["snapshot_id"])
    request_id = "scope-" + uuid.uuid4().hex
    result: dict[str, Any] = {
        "request_id": request_id,
        "question": question,
        "selectors": choices,
        "status": "resolved" if len(ids) == len(choices) else "needs_scope",
        "snapshot_ids": ids if len(ids) == len(choices) else [],
        "resolutions": resolutions,
        "next_step": "Create investigation at exact snapshots"
        if len(ids) == len(choices)
        else "Clarify design, revision, run or exact snapshot; no analysis submitted",
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / (request_id + ".json")).write_text(json.dumps(result, indent=2) + "\n")
    return result
