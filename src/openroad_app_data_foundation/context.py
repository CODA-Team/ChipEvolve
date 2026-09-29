"""Deterministic DesignContextPack compilation for timing-path queries."""

from __future__ import annotations

from typing import Any

from .queries import timing_path
from .repository import DataStore
from .analysis_context import build_analysis_context, context_availability


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
    analysis_context = build_analysis_context(snapshot, path)
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
        "analysis_context": analysis_context,
        "target": {"type": "timing_path", "id": path_id},
        "observations": {key: path.get(key) for key in ("slack", "delay", "unit")
                         if path.get(key) is not None},
        "entities": entities,
        "relations": relations,
        "timing_context": {"path": path, "points": points},
        "physical_context": physical,
        "evidence": evidence,
        "availability": context_availability(analysis_context),
        "evidence_policy": {"relationship_source": "data_foundation",
                             "inference_performed": False},
    }


def object_context(store: DataStore, snapshot_id: str,
                   object_id: str) -> dict[str, Any]:
    """Compile one object and its explicit neighboring facts.

    The object ID is supplied by the indexed snapshot.  This function does
    not resolve a name, scan a host directory, or infer relationships.
    """
    snapshot = store.snapshot(snapshot_id)
    view = store.object(snapshot_id, object_id, expansion="full")
    entity = view["entity"]
    children = view.get("children", [])
    relations = list(view.get("relations", []))
    observations = list(view.get("observations", []))
    for child in children:
        child_view = store.object(snapshot_id, child["object_id"], expansion="full")
        relations.extend(child_view.get("relations", []))
        observations.extend(child_view.get("observations", []))
    relations = _unique_rows(relations, "relation_id")
    related_ids = _related_object_ids(entity, relations)
    entities = _unique_rows([entity, *children,
                             *(_entities(store, snapshot_id, related_ids))], "object_id")
    physical = _physical_rows(store, snapshot_id,
                              [row["object_id"] for row in entities])
    evidence = _evidence_rows(view, "objects", object_id)
    evidence.extend(_evidence_rows(observations, "observations", object_id))
    evidence.extend(_evidence_rows(relations, "relations", object_id))
    evidence.extend(_evidence_rows(physical, "physical_context", object_id))
    evidence.extend(_snapshot_evidence(snapshot, snapshot_id))
    return _object_pack(snapshot, entity, observations, entities, relations,
                        physical, evidence)


def net_context(store: DataStore, snapshot_id: str, net_id: str) -> dict[str, Any]:
    """Compile a net, its connected entities, physical route, and evidence."""
    snapshot = store.snapshot(snapshot_id)
    view = store.expand_net(snapshot_id, net_id)
    entity = view["entity"]
    connected = view.get("connected_entities", [])
    relations = list(view.get("relations", []))
    observations = list(view.get("observations", []))
    parent_ids = [str(row["parent_id"]) for row in connected
                  if row.get("parent_id")]
    parents = _entities(store, snapshot_id, list(dict.fromkeys(parent_ids)))
    for parent in parents:
        parent_view = store.object(snapshot_id, parent["object_id"], expansion="full")
        relations.extend(parent_view.get("relations", []))
        observations.extend(parent_view.get("observations", []))
    relations = _unique_rows(relations, "relation_id")
    entities = _unique_rows([entity, *connected, *parents], "object_id")
    physical = _physical_rows(store, snapshot_id,
                              [row["object_id"] for row in entities])
    evidence = _evidence_rows(entities, "objects", net_id)
    evidence.extend(_evidence_rows(observations, "observations", net_id))
    evidence.extend(_evidence_rows(relations, "relations", net_id))
    evidence.extend(_evidence_rows(physical, "physical_context", net_id))
    evidence.extend(_snapshot_evidence(snapshot, snapshot_id))
    return _object_pack(snapshot, entity, observations, entities, relations, physical,
                        evidence, target_type="net")


def _object_pack(snapshot: dict[str, Any], entity: dict[str, Any],
                 observations: list[dict[str, Any]], entities: list[dict[str, Any]],
                 relations: list[dict[str, Any]], physical: list[dict[str, Any]],
                 evidence: list[dict[str, Any]], *, target_type: str = "object") -> dict[str, Any]:
    return {
        "task": {"type": f"{target_type}_context"},
        "scope": {key: snapshot.get(key) for key in (
            "design_id", "revision_id", "run_id", "stage", "snapshot_id")},
        "target": {"type": target_type, "id": entity.get("object_id")},
        "observations": observations,
        "entities": entities,
        "relations": relations,
        "physical_context": physical,
        "evidence": evidence,
        "evidence_policy": {"relationship_source": "data_foundation",
                             "inference_performed": False},
    }


def _related_object_ids(entity: dict[str, Any], relations: list[dict[str, Any]]) -> list[str]:
    object_id = entity.get("object_id")
    return list(dict.fromkeys(
        str(relation[key]) for relation in relations
        for key in ("subject_id", "object_id")
        if relation.get(key) and relation.get(key) != object_id
    ))


def _entities(store: DataStore, snapshot_id: str,
              object_ids: list[str]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for object_id in object_ids:
        rows = store.records(snapshot_id, "entities", record_id=object_id, limit=1)
        result.extend(rows)
    return result


def _unique_rows(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for row in rows:
        value = row.get(key)
        if not isinstance(value, str) or value in seen:
            continue
        seen.add(value)
        result.append(row)
    return result


def _physical_rows(store: DataStore, snapshot_id: str,
                   object_ids: list[str]) -> list[dict[str, Any]]:
    return [row for object_id in object_ids
            for row in store.records(snapshot_id, "physical_context",
                                     record_id=object_id, limit=1)]


def _evidence_rows(rows: list[dict[str, Any]] | dict[str, Any],
                   record_type: str, default_id: str) -> list[dict[str, Any]]:
    values = rows if isinstance(rows, list) else [rows]
    result: list[dict[str, Any]] = []
    for row in values:
        record_id = row.get("object_id") or row.get("record_id") or default_id
        for item in row.get("evidence", []):
            if isinstance(item, dict):
                result.append({"record_type": record_type, "record_id": record_id,
                               **item})
    return result


def _snapshot_evidence(snapshot: dict[str, Any], snapshot_id: str) -> list[dict[str, Any]]:
    return [{"record_type": "snapshot", "record_id": snapshot_id, "artifact": artifact}
            for artifact in snapshot.get("source_artifacts", [])
            if isinstance(artifact, dict)]


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
