"""Resolve parser source roles to execution-owned artifact identities."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


PLACEHOLDER_ARTIFACT_IDS = frozenset({"timing-report", "orfs-metadata"})


def resolve_records(snapshot: Mapping[str, Any],
                   values: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    """Attach an artifact identity only when the registered catalogue proves it.

    Adapters may know a source role and staged logical path before the runtime
    assigns an artifact ID. Resolution is exact-path first, then unique
    role/stage. Multiple candidates stay explicitly unresolved.
    """
    refs = [item for item in snapshot.get("source_artifacts", [])
            if isinstance(item, dict)]
    return {
        record_type: [_resolve_row(row, refs) for row in rows]
        for record_type, rows in values.items()
    }


def _resolve_row(row: dict[str, Any], refs: list[dict[str, Any]]) -> dict[str, Any]:
    raw = row.get("evidence")
    if not isinstance(raw, list):
        return row
    return {**row, "evidence": [_resolve_item(item, refs) for item in raw]}


def _resolve_item(item: Any, refs: list[dict[str, Any]]) -> Any:
    if not isinstance(item, dict):
        return item
    explicit_id = item.get("artifact_id")
    if explicit_id in PLACEHOLDER_ARTIFACT_IDS:
        item = {key: value for key, value in item.items() if key != "artifact_id"}
        explicit_id = None
    if isinstance(explicit_id, str) and explicit_id:
        exact_id = [ref for ref in refs if ref.get("artifact_id") == explicit_id]
        if len(exact_id) == 1:
            return _resolved(item, exact_id[0], resolution="exact_artifact")
        return {**item, "resolution": "unverified"}
    nested = item.get("artifact")
    if isinstance(nested, dict) and nested.get("artifact_id"):
        return item
    kind = item.get("artifact_kind") or item.get("category")
    path = item.get("logical_path") or item.get("store_key")
    stage = item.get("stage")
    candidates = [ref for ref in refs if _same(ref.get("category"), kind)]
    exact = [ref for ref in candidates if path and ref.get("logical_path") == path]
    if exact:
        candidates = exact
    elif stage:
        staged = [ref for ref in candidates if ref.get("stage") == stage]
        if staged:
            candidates = staged
    if len(candidates) != 1:
        bundle_candidates = [ref for ref in refs
                             if ref.get("category") in {"data_snapshot", "runtime_bundle"}]
        if len(bundle_candidates) == 1 and path:
            return _resolved({**item, "nested_path": path}, bundle_candidates[0],
                             resolution="bundle_member")
        return {**item, "resolution": "ambiguous" if candidates else "unresolved",
                "candidate_count": len(candidates)}
    ref = candidates[0]
    return _resolved(item, ref, resolution="exact_path" if exact else "unique_role")


def _resolved(item: dict[str, Any], ref: Mapping[str, Any], *, resolution: str) -> dict[str, Any]:
    return {
        **item,
        "artifact_id": ref.get("artifact_id"),
        "run_id": ref.get("run_id"),
        "attempt_id": ref.get("attempt_id"),
        "sha256": ref.get("sha256"),
        "size_bytes": ref.get("size_bytes"),
        "category": ref.get("category"),
        "stage": ref.get("stage"),
        "logical_path": ref.get("logical_path") or item.get("logical_path"),
        "resolution": resolution,
    }


def _same(left: Any, right: Any) -> bool:
    return isinstance(left, str) and left and left == right
