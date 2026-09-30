"""The CONTRACT section 1 response envelope.

Every tool response except ``/health`` is wrapped here, so a caller can read the
version, the scope the answer covers, and - most importantly - whether anything
is missing, without knowing each tool's payload shape.

``status`` is derived, never guessed:

* ``not_found``   the target does not exist in this boundary;
* ``truncated``   the response is a bounded view (a page, or a capped relation
                  set) and the payload says so;
* ``partial``     the payload declares an unavailable count or capability;
* ``unavailable`` the request could not be answered at all;
* ``available``   everything asked for is present.
"""

from __future__ import annotations

from typing import Any, Mapping

CONTRACT_VERSION = "0.1"

#: payload keys that belong to the envelope, not to the tool's own data
_ENVELOPE_FIELDS = ("scope", "target", "evidence", "limitations")


def tool_name_for(path: str) -> str:
    """The CONTRACT tool a route implements (extensions get a descriptive name)."""
    parts = [item for item in path.split("/") if item]
    if not parts:
        return "unknown"
    if parts[0] == "snapshots":
        if len(parts) == 1:
            return "list_snapshots"
        if "compare" in parts:
            return "compare_metric" if parts[-1] == "metrics" else "compare_timing_path"
        tail = parts[2:]
        if not tail:
            return "get_snapshot"
        if tail == ["summary"]:
            return "get_stage_summary"
        if tail == ["timing-paths"]:
            return "get_timing_paths"
        if tail[0] == "timing-paths":
            return "get_timing_path"
        if tail == ["instances"]:
            return "get_instance"
        if tail == ["nets"]:
            return "get_net_context" if tail[-1] == "context" else "get_net"
        if tail[0] == "nets":
            return "get_net_context" if tail[-1] == "context" else "expand_net"
        if tail[0] == "objects":
            return "get_object_context" if tail[-1] == "context" else "get_object"
        if tail[0] == "physical":
            return "get_physical_context"
        if tail == ["observations"]:
            return "list_observations"
        if tail == ["evidence"]:
            return "get_evidence"
        if "evidence" in tail:
            return "get_record_evidence"
    if parts[0] == "runs":
        return "get_run_summary" if parts[-1] == "summary" else "get_metrics"
    return "unknown"


def envelope(path: str, query: Mapping[str, str], payload: Any) -> dict[str, Any]:
    """Wrap ``payload`` in the CONTRACT envelope, lifting envelope fields out."""
    data = dict(payload) if isinstance(payload, Mapping) else {"value": payload}
    # scope and target are part of a context pack's documented structure, so they
    # are *mirrored* into the envelope rather than moved out of it; evidence and
    # limitations are provenance of the answer and are lifted (evidence runs to
    # tens of kilobytes, so duplicating it would be worse than useful).
    scope = data.get("scope")
    target = data.get("target")
    evidence = data.pop("evidence", None)
    limitations = data.pop("limitations", None)

    result: dict[str, Any] = {
        "contract_version": CONTRACT_VERSION,
        "tool": tool_name_for(path),
        "scope": _scope(path, query, data, scope),
    }
    if target is not None:
        result["target"] = target
    status, missing = _status(data, limitations)
    result["status"] = status
    result["missing"] = missing
    result["data"] = data
    result["evidence"] = evidence if evidence is not None else []
    result["limitations"] = limitations if isinstance(limitations, list) else []
    return result


def error_envelope(path: str, status: str, message: str,
                   *, missing: list[str] | None = None) -> dict[str, Any]:
    """An envelope for a request that could not be answered."""
    return {
        "contract_version": CONTRACT_VERSION,
        "tool": tool_name_for(path),
        "scope": _scope(path, {}, {}, None),
        "status": status,
        "missing": missing or [],
        "data": {"error": message},
        "evidence": [],
        "limitations": [{"reason": message}],
    }


#: context packs name their boundary in short form; the envelope uses the
#: CONTRACT 1 names so a caller reads one shape for every tool.
_SCOPE_ALIASES = {"design": "design_id", "revision": "revision_id",
                  "run": "run_id", "snapshot": "snapshot_id",
                  "view": "analysis"}


def _scope(path: str, query: Mapping[str, str], data: Mapping[str, Any],
           declared: Any) -> dict[str, Any]:
    """The fact boundary this answer covers; undeclared dimensions are omitted."""
    if isinstance(declared, Mapping):
        return {_SCOPE_ALIASES.get(str(key), str(key)): value
                for key, value in declared.items() if value is not None}
    scope: dict[str, Any] = {}
    snapshot = data.get("snapshot")
    if isinstance(snapshot, Mapping):
        for key in ("design_id", "revision_id", "run_id", "snapshot_id", "stage"):
            if snapshot.get(key) is not None:
                scope[key] = snapshot[key]
    for key in ("run_id", "snapshot_id", "design_id", "stage"):
        if scope.get(key) is None and data.get(key) is not None:
            scope[key] = data[key]
    if scope.get("snapshot_id") is None and path.startswith("/snapshots/"):
        parts = [item for item in path.split("/") if item]
        if len(parts) > 1 and parts[1] != "compare":
            scope["snapshot_id"] = parts[1]
    return scope


def _status(data: Mapping[str, Any],
            limitations: Any) -> tuple[str, list[str]]:
    """Derive the status and the missing-field list from the payload itself."""
    if data.get("count_status") == "unavailable":
        return "partial", list(data.get("missing_fields") or ["count"])
    if data.get("relations_truncated") is True:
        return "truncated", ["relations"]
    if data.get("truncated") is True:
        return "truncated", []
    if isinstance(limitations, list) and any(
            isinstance(item, Mapping) and item.get("status") == "truncated"
            for item in limitations):
        return "truncated", []
    if data.get("availability") and _declares_unavailable(data["availability"]):
        return "partial", []
    return "available", []


def _declares_unavailable(availability: Any) -> bool:
    if not isinstance(availability, Mapping):
        return False
    for value in availability.values():
        if isinstance(value, Mapping) and value.get("status") == "unavailable":
            return True
    return False
