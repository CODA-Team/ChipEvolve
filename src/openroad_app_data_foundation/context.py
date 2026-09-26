"""Deterministic DesignContextPack compilation for timing-path queries."""

from __future__ import annotations

from typing import Any

from .queries import timing_path
from .repository import DataStore


def timing_path_context(store: DataStore, snapshot_id: str,
                        path_id: str) -> dict[str, Any]:
    """Compile the smallest useful cross-domain context for one path.

    All links come from explicit record identifiers or stored relations. This
    function never matches names and never reads a raw host file.
    """
    snapshot = store.snapshot(snapshot_id)
    detail = timing_path(store, snapshot_id, path_id)
    path = detail["timing_path"]
    points = detail["timing_points"]
    entities: list[dict[str, Any]] = []
    relations: list[dict[str, Any]] = []
    physical: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    seen_entities: set[str] = set()
    seen_relations: set[str] = set()
    seen_physical: set[str] = set()

    for point in points:
        for object_id in _point_objects(point):
            if object_id in seen_entities:
                continue
            entity = _entity(store, snapshot_id, object_id)
            if entity is None:
                continue
            seen_entities.add(object_id)
            entities.append(entity)
            parent_id = entity.get("parent_id")
            if isinstance(parent_id, str) and parent_id and parent_id not in seen_entities:
                parent = _entity(store, snapshot_id, parent_id)
                if parent is not None:
                    seen_entities.add(parent_id)
                    entities.append(parent)
            for relation in store.records(snapshot_id, "relations", limit=10000):
                if relation.get("subject_id") in {object_id, parent_id} \
                        or relation.get("object_id") in {object_id, parent_id}:
                    relation_id = relation.get("relation_id")
                    if relation_id not in seen_relations:
                        seen_relations.add(str(relation_id))
                        relations.append(relation)
                    _append_related_entity(store, snapshot_id, relation, entities,
                                           seen_entities)
        for key in ("evidence",):
            for item in point.get(key, []):
                if isinstance(item, dict):
                    evidence.append({"record_type": "timing_points",
                                     "record_id": point.get("point_id"), **item})

    for entity in entities:
        object_id = entity.get("object_id")
        if not isinstance(object_id, str) or object_id in seen_physical:
            continue
        rows = store.records(snapshot_id, "physical_context", record_id=object_id, limit=1)
        if rows:
            seen_physical.add(object_id)
            physical.append(rows[0])

    for item in path.get("evidence", []):
        if isinstance(item, dict):
            evidence.append({"record_type": "timing_paths", "record_id": path_id, **item})
    for artifact in snapshot.get("source_artifacts", []):
        if isinstance(artifact, dict):
            evidence.append({"record_type": "snapshot", "record_id": snapshot_id,
                             "artifact": artifact})

    return {
        "task": {"type": "timing_analysis"},
        "scope": {"design": snapshot.get("design_id"),
                   "revision": snapshot.get("revision_id"),
                   "run": snapshot.get("run_id"), "stage": snapshot.get("stage"),
                   "snapshot": snapshot_id, "view": path.get("analysis"),
                   "corner": path.get("corner")},
        "target": {"type": "timing_path", "id": path_id},
        "observations": {key: path.get(key) for key in ("slack", "delay", "unit")
                         if path.get(key) is not None},
        "entities": entities,
        "relations": relations,
        "timing_context": {"path": path, "points": points},
        "physical_context": physical,
        "evidence": evidence,
        "evidence_policy": {"relationship_source": "data_foundation",
                             "inference_performed": False},
    }


def _point_objects(point: dict[str, Any]) -> list[str]:
    values = [point.get("pin_id"), point.get("instance_id"), point.get("net_id"),
              point.get("object_id")]
    return list(dict.fromkeys(value for value in values if isinstance(value, str) and value))


def _entity(store: DataStore, snapshot_id: str, object_id: str) -> dict[str, Any] | None:
    try:
        return store.records(snapshot_id, "entities", record_id=object_id, limit=1)[0]
    except IndexError:
        return None


def _append_related_entity(store: DataStore, snapshot_id: str,
                           relation: dict[str, Any], entities: list[dict[str, Any]],
                           seen: set[str]) -> None:
    for key in ("subject_id", "object_id"):
        object_id = relation.get(key)
        if not isinstance(object_id, str) or object_id in seen:
            continue
        entity = _entity(store, snapshot_id, object_id)
        if entity is not None:
            seen.add(object_id)
            entities.append(entity)
