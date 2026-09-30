"""Stable identity views for snapshot-local design records."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

def enrich_records(snapshot: Mapping[str, Any], record_type: str,
                   rows: list[dict[str, Any]],
                   entity_rows: list[dict[str, Any]] | None = None,
                   *, identity_index: dict[str, dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Attach identity references without changing the source object IDs.

    Native and snapshot-local IDs remain authoritative for storage.  The
    canonical component is a scoped value used only for explicit cross-stage
    matching; it is never used to rewrite relations or merge records.
    """
    if record_type == "timing_paths":
        return [_path_identity(snapshot, row) for row in rows]
    if record_type not in {"entities", "timing_points", "physical_context"}:
        return rows
    entities = identity_index if identity_index is not None else _entity_rows(snapshot, entity_rows or rows)
    if record_type == "entities":
        return [
            {**row, "identity": entities[row["object_id"]]}
            if row.get("object_id") in entities else row
            for row in rows
        ]
    if record_type == "timing_points":
        return [_point_identity(row, entities) for row in rows]
    if record_type == "physical_context":
        return [_physical_identity(row, entities) for row in rows]
    return rows


def _entity_rows(snapshot: Mapping[str, Any], rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    identities = {
        str(row["object_id"]): identity
        for row in rows
        if isinstance(row.get("object_id"), str)
        for identity in [_identity(snapshot, row)]
        if identity is not None
    }
    groups: dict[tuple[Any, ...], list[str]] = {}
    for object_id, identity in identities.items():
        key = canonical_key(identity)
        if key is not None:
            groups.setdefault(key, []).append(object_id)
    for object_ids in groups.values():
        if len(object_ids) < 2:
            continue
        for object_id in object_ids:
            identity = identities[object_id]
            identities[object_id] = {
                **identity,
                "matching_status": "ambiguous",
                "ambiguous_candidates": sorted(object_ids),
            }
    return identities


def _identity(snapshot: Mapping[str, Any], row: Mapping[str, Any]) -> dict[str, Any] | None:
    object_id = row.get("object_id")
    kind = row.get("kind")
    name = row.get("name")
    attributes = row.get("attributes")
    if isinstance(attributes, Mapping):
        name = attributes.get("hierarchical_name") or name
    if not isinstance(name, str) or not name or not isinstance(kind, str) or not kind:
        return None
    native_id = attributes.get("native_id") if isinstance(attributes, Mapping) else None
    structural_fingerprint = row.get("structural_fingerprint")
    if not isinstance(structural_fingerprint, str) and isinstance(attributes, Mapping):
        structural_fingerprint = attributes.get("structural_fingerprint")
    return {
        "snapshot_local_id": object_id,
        "native_id": native_id,
        "snapshot_local": {"snapshot_id": snapshot.get("snapshot_id"),
                            "object_id": object_id, "native_id": native_id},
        "canonical": {
            "design_id": snapshot.get("design_id"),
            "revision_id": snapshot.get("revision_id"),
            "kind": kind,
            "hierarchical_name": name,
        },
        "canonical_basis": "scoped_name",
        "matching_status": "candidate",
        "structural_fingerprint": structural_fingerprint,
    }


def _point_identity(row: dict[str, Any], entities: dict[str, dict[str, Any]]) -> dict[str, Any]:
    references = {
        field: entities[field_id]
        for field in ("pin_id", "instance_id", "net_id", "object_id")
        if isinstance(field_id := row.get(field), str) and field_id in entities
    }
    return {**row, "identity_references": references} if references else row


def _physical_identity(row: dict[str, Any], entities: dict[str, dict[str, Any]]) -> dict[str, Any]:
    object_id = row.get("object_id")
    identity = entities.get(object_id) if isinstance(object_id, str) else None
    return {**row, "identity": identity} if identity is not None else row


def _path_identity(snapshot: Mapping[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    path_id = row.get("path_id")
    if not isinstance(path_id, str) or not path_id:
        return row
    declared = row.get("path_identity")
    declared = declared if isinstance(declared, Mapping) else {}
    return {**row, "path_identity": {
        "snapshot_local_id": path_id,
        "snapshot_id": snapshot.get("snapshot_id"),
        "basis": "snapshot_local",
        **declared,
    }}


def canonical_key(identity: Mapping[str, Any] | None) -> tuple[Any, ...] | None:
    """Return a comparable canonical key, or ``None`` for unmapped records."""
    if identity.get("matching_status") == "ambiguous" if isinstance(identity, Mapping) else False:
        return None
    canonical = identity.get("canonical") if isinstance(identity, Mapping) else None
    if not isinstance(canonical, Mapping):
        return None
    return tuple(canonical.get(name) for name in (
        "design_id", "revision_id", "kind", "hierarchical_name"))
