"""JSON tool schemas for function calling.

One schema per CONTRACT v0.2 tool, in the shape model runtimes expect::

    {"type": "function",
     "function": {"name": ..., "description": ..., "parameters": {...}}}

They ship with the client so a partner can hand them straight to a model:
``python -m eda_ai_client.schemas > tools.json``.  ``tests/test_eda_ai_client.py``
asserts that the schema names and the client methods stay in step.
"""

from __future__ import annotations

import json
from typing import Any

_STRING: dict[str, Any] = {"type": "string"}
_PAGE: dict[str, Any] = {"type": "integer", "minimum": 1, "maximum": 10000}
_OFFSET: dict[str, Any] = {"type": "integer", "minimum": 0}
_BOOL: dict[str, Any] = {"type": "boolean"}


def _tool(name: str, description: str, properties: dict[str, Any],
          required: tuple[str, ...] = ()) -> dict[str, Any]:
    return {"type": "function",
            "function": {"name": name,
                         "description": description,
                         "parameters": {"type": "object",
                                        "properties": properties,
                                        "required": list(required),
                                        "additionalProperties": False}}}


TOOL_SCHEMAS: list[dict[str, Any]] = [
    _tool("list_designs", "Designs the interface knows about, with their revisions.",
          {}),
    _tool("resolve_scope", "Resolve a unique snapshot or return ambiguous candidates; never picks latest.",
          {"snapshot_id": _STRING, "design_id": _STRING, "revision_id": _STRING,
           "run_id": _STRING, "stage": _STRING, "origin": {"type": "string", "enum": ["flow", "query", "all"]}}),
    _tool("get_object_context", "Exact object name or explicit ID, resolved by Data Foundation.",
          {"snapshot_id": _STRING, "kind": {"type": "string", "enum": ["instance", "net", "pin"]},
           "name": _STRING, "object_id": _STRING}, ("snapshot_id", "kind")),
    _tool("list_runs", "Execution runs, optionally filtered by design or status.",
          {"design_id": _STRING, "status": _STRING,
           "limit": _PAGE, "offset": _OFFSET}),
    _tool("get_run_summary", "Every indexed stage snapshot of one run, with record counts.",
          {"run_id": _STRING}, ("run_id",)),
    _tool("get_stage_summary",
          "One immutable stage snapshot: record counts, per-domain coverage and source artifacts.",
          {"snapshot_id": _STRING}, ("snapshot_id",)),
    _tool("list_artifacts", "Registered raw artifacts of one run.",
          {"run_id": _STRING, "kind": _STRING}, ("run_id",)),
    _tool("get_metrics",
          "Canonical metrics (WNS, TNS, AREA, POWER_TOTAL, INSTANCE_COUNT, "
          "SETUP_VIOLATIONS) with the authoritative source of each value. "
          "status=partial means the unit or corner is unresolved; status=unavailable "
          "means the fact is not indexed - never substitute a neighbouring value.",
          {"run_id": _STRING, "snapshot_id": _STRING, "stage": _STRING, "name": _STRING,
           "include_raw": _BOOL, "limit": _PAGE, "offset": _OFFSET}),
    _tool("get_timing_paths",
          "Timing path summaries; check is setup or hold. sort=slack with order=worst "
          "returns the worst paths first, so the worst five need one call, not every path.",
          {"snapshot_id": _STRING, "check": _STRING, "sort": _STRING, "order": _STRING,
           "limit": _PAGE, "offset": _OFFSET,
           "detail": {"type": "string", "enum": ["summary", "full"]}},
          ("snapshot_id",)),
    _tool("get_timing_points",
          "Timing points across the snapshot, rankable: sort=slew with order=worst "
          "returns the worst slew first, without walking every path.",
          {"snapshot_id": _STRING, "path_id": _STRING, "sort": _STRING, "order": _STRING,
           "limit": _PAGE, "offset": _OFFSET},
          ("snapshot_id",)),
    _tool("get_timing_path",
          "One timing path: summary, its ordered points, or the compiled context with "
          "objects, physical facts and evidence.",
          {"snapshot_id": _STRING, "path_id": _STRING,
           "include": {"type": "string", "enum": ["summary", "points", "context"]}},
          ("snapshot_id", "path_id")),
    _tool("get_instance",
          "One instance by exact hierarchical name, with physical facts and relations. "
          "Zero matches is not_found and several is partial - neither is an exception.",
          {"snapshot_id": _STRING, "name": _STRING}, ("snapshot_id", "name")),
    _tool("get_net_context",
          "A net by explicit object ID or exact name: connected pins, driver and loads, route and evidence.",
          {"snapshot_id": _STRING, "net": _STRING, "by": {"type": "string", "enum": ["name", "object_id"]}}, ("snapshot_id", "net")),
    _tool("get_physical_context",
          "Location, bounding box, geometry and routing for one object ID.",
          {"snapshot_id": _STRING, "object_id": _STRING}, ("snapshot_id", "object_id")),
    _tool("get_evidence",
          "Source locations behind the facts, back to artifact, run, sha256 and logical path. "
          "With record_type and record_id it answers for one record; otherwise it pages the "
          "snapshot index, where count may be reported as unavailable when the index is large.",
          {"snapshot_id": _STRING, "record_type": _STRING, "record_id": _STRING,
           "artifact_id": _STRING, "limit": _PAGE, "offset": _OFFSET},
          ("snapshot_id",)),
]

TOOL_NAMES: list[str] = [item["function"]["name"] for item in TOOL_SCHEMAS]

if __name__ == "__main__":  # pragma: no cover - CLI convenience
    print(json.dumps(TOOL_SCHEMAS, indent=2, ensure_ascii=False))
