"""Deterministic DesignContextPack compilation for timing-path queries."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from .queries import timing_path
from .repository import DataStore
from .analysis_context import build_analysis_context, context_availability


#: Provenance entries one context pack returns.  Bounded because the list grows with
#: the fanout of whatever object was asked about, not with the question.
EVIDENCE_LIMIT = 200

#: Rows of each neighbouring collection one pack returns before it hands back a
#: cursor.  Measured on ariane136 net:194943 (fanout 336): the pack was 782,204 B
#: - the net's own 1,970 wire segments 310,603 B, 674 neighbour physical rows
#: 99,101 B, 675 entities 243,281 B - for a question that needs the net, its
#: driver and the load count.  A packet's cost has to grow with the question, not
#: with the fanout of what the question happens to touch.
FIRST_SCREEN_LIMIT = 200

#: Wire segments kept on a physical row in a summary.  1,970 of them were 310 KB
#: of one 782 KB pack; ``routing_total`` states the real count and
#: ``GET /snapshots/{s}/physical/{id}`` returns all of them.
ROUTING_LIMIT = 50


def timing_path_context(store: DataStore, snapshot_id: str,
                        path_id: str, detail: str = "summary",
                        relation_limit: int = 200) -> dict[str, Any]:
    """Compile the smallest useful cross-domain context for one path.

    All links come from explicit record identifiers or stored relations. This
    function never matches names and never reads a raw host file.
    """
    snapshot = store.snapshot(snapshot_id)
    # note: `detail` is this function's verbosity argument, so the path record
    # needs its own name here.
    path_detail = timing_path(store, snapshot_id, path_id)
    path = path_detail["timing_path"]
    points = path_detail["timing_points"]
    analysis_context = build_analysis_context(snapshot, path)
    entities: list[dict[str, Any]] = []
    relations: list[dict[str, Any]] = []
    physical: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    seen_entities: set[str] = set()
    seen_relations: set[str] = set()

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
        for key in ("evidence",):
            for item in point.get(key, []):
                if isinstance(item, dict):
                    evidence.append({"record_type": "timing_points",
                                     "record_id": point.get("point_id"), **item})

    # One indexed relation query for every object collected above.  The old
    # per-object full-table scan was O(points x relations) and stopped at the
    # 10000-row ceiling, which silently dropped relations on real designs.
    for relation in store.relations_touching(
            snapshot_id, [row["object_id"] for row in entities]):
        relation_id = relation.get("relation_id")
        if relation_id in seen_relations:
            continue
        seen_relations.add(str(relation_id))
        relations.append(relation)
    _append_related_entities(store, snapshot_id, relations, entities, seen_entities)

    # Batched like the rest: this loop was one point query per entity, and a path
    # through high-fanout nets has thousands of entities.
    physical.extend(_physical_rows(
        store, snapshot_id,
        [str(row["object_id"]) for row in entities
         if isinstance(row.get("object_id"), str)]))

    for item in path.get("evidence", []):
        if isinstance(item, dict):
            evidence.append({"record_type": "timing_paths", "record_id": path_id, **item})
    for artifact in snapshot.get("source_artifacts", []):
        if isinstance(artifact, dict):
            evidence.append({"record_type": "snapshot", "record_id": snapshot_id,
                             "artifact": artifact})

    return _summarize({
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
    }, path_id, detail, relation_limit)


def object_context(store: DataStore, snapshot_id: str,
                   object_id: str, detail: str = "summary",
                   relation_limit: int = 200) -> dict[str, Any]:
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
                        physical, evidence, detail=detail,
                        relation_limit=relation_limit)


def net_context(store: DataStore, snapshot_id: str, net_id: str,
                detail: str = "summary", relation_limit: int = 200) -> dict[str, Any]:
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
    pack = _object_pack(snapshot, entity, observations, entities, relations, physical,
                        evidence, target_type="net", detail=detail,
                        relation_limit=relation_limit,
                        neighbour_total=view.get("connected_total"))
    # Carry the bound the net expansion applied, so the answer says how much of the
    # fanout it actually looked at instead of just stopping.
    for key in ("connected_total", "connected_truncated", "connected_limit"):
        if key in view:
            pack[key] = view[key]
    if view.get("connected_truncated") is True:
        pack["truncated"] = True
    return pack


def _object_pack(snapshot: dict[str, Any], entity: dict[str, Any],
                 observations: list[dict[str, Any]], entities: list[dict[str, Any]],
                 relations: list[dict[str, Any]], physical: list[dict[str, Any]],
                 evidence: list[dict[str, Any]], *, target_type: str = "object",
                 detail: str = "summary", relation_limit: int = 200,
                 neighbour_total: int | None = None) -> dict[str, Any]:
    return _summarize({
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
    }, entity.get("object_id"), detail, relation_limit, neighbour_total)


def _summarize(pack: dict[str, Any], target_id: str | None,
               detail: str = "summary", relation_limit: int = 200,
               neighbour_total: int | None = None) -> dict[str, Any]:
    """Project a context pack so a partner can actually afford it.

    Measured composition of one gcd net context (269,892 B in total):
    ``physical_context`` 89 KB (identity 30 KB + per-record evidence 33 KB),
    ``relations`` 85 KB (the repeated ``snapshot_id`` alone 14 KB),
    ``entities`` 54 KB (identity 30 KB, geometry 11 KB) and the pack-level
    ``evidence`` list 41 KB.  Geometry - the first thing this projection removed
    - was only 8 KB, which is why the first attempt saved 9%.

    So summary removes the *duplicated* parts: the snapshot-local identity echo,
    the per-row ``snapshot_id`` (the pack's ``scope`` carries it), the
    per-record evidence copies (the pack-level list still carries them) and
    neighbour geometry.  ``detail=full`` returns the unprojected pack.
    """
    if detail not in {"summary", "full"}:
        raise ValueError("detail must be summary or full")
    if relation_limit < 0:
        raise ValueError("relation_limit must not be negative")
    pack["detail"] = detail
    pack["relation_limit"] = relation_limit
    # The caps apply in both modes: they are fetch bounds, not formatting
    # choices.  One gcd path context merged 178 relations and one ibex path 401
    # (a 12-point path whose nets carry every load), so a caller needs a bound
    # and needs to be told when it bit.  A zero relation_limit means unlimited.
    #
    # Every collection a pack grows with the *neighbourhood* is bounded here, in
    # one place, and every bound names the route that carries the rest: a bound
    # without a way back is a capability cut, and this one is not.
    snapshot_id = _scope_snapshot(pack)
    target_type = (pack.get("target") or {}).get("type")
    for field, limit in (
            ("relations", relation_limit),
            ("entities", FIRST_SCREEN_LIMIT),
            ("physical_context", FIRST_SCREEN_LIMIT),
            ("observations", FIRST_SCREEN_LIMIT)):
        rows = pack.get(field)
        if not limit or not isinstance(rows, list) or len(rows) <= limit:
            continue
        pack[field] = rows[:limit]
        pack[f"{field}_truncated"] = True
        pack[f"{field}_total"] = len(rows)
        pack[f"{field}_returned"] = limit
        pack.setdefault("limitations", []).append({
            "field": field, "status": "truncated",
            "returned": limit, "total": len(rows), "next_offset": limit,
            **_continuation(field, snapshot_id, target_id, target_type, limit,
                            len(pack[field]), neighbour_total)})
    if detail == "full":
        return pack
    timing = pack.get("timing_context")
    if isinstance(timing, dict):
        for point in timing.get("points") or []:
            if not isinstance(point, dict):
                continue
            point.pop("evidence", None)
            # The same snapshot-wide echo `_trim_identity` already removes from
            # entities sits one level deeper on a point: 271,515 B of one
            # 388,983 B point list was ``design_id``/``revision_id``/
            # ``snapshot_id``/``canonical_basis``/``matching_status`` repeated per
            # reference, and the point itself already carries pin_id, instance_id
            # and net_id.  ``detail=full`` and GET /objects/{id} keep them.
            references = point.get("identity_references")
            if isinstance(references, dict):
                point["identity_references"] = {
                    key: _trim_identity(value) if isinstance(value, dict) else value
                    for key, value in references.items()}
        _bound_points(pack, timing, snapshot_id, target_id, target_type)
    for collection in ("entities", "physical_context", "relations", "observations"):
        for row in pack.get(collection, []):
            if isinstance(row, dict):
                row.pop("snapshot_id", None)
                # The docstring above has always claimed the per-record evidence
                # copies are removed, but only physical rows actually were: on one
                # ibex timing path the 232 entities carried 130,810 B of evidence
                # - 34% of the whole 380 KB pack - while the same descriptors sat
                # in the pack-level list.  Each record keeps its compact
                # ``source_ref`` and ``locator``, and
                # GET /snapshots/{s}/records/{type}/{id}/evidence returns the
                # resolved entry, so nothing becomes unreachable.
                row.pop("evidence", None)
    for entity in pack.get("entities", []):
        if not isinstance(entity, dict):
            continue
        identity = entity.get("identity")
        if isinstance(identity, dict):
            entity["identity"] = _trim_identity(identity)
        attributes = entity.get("attributes")
        if isinstance(attributes, dict) and "geometry" in attributes:
            trimmed = dict(attributes)
            trimmed.pop("geometry", None)
            entity["attributes"] = trimmed
    for record in pack.get("physical_context", []):
        if not isinstance(record, dict):
            continue
        record.pop("identity", None)
        record.pop("evidence", None)
        if record.get("object_id") != target_id:
            record.pop("geometry", None)
            record.pop("routing", None)
        else:
            _bound_routing(pack, record, snapshot_id, target_id)
    for relation in pack.get("relations", []):
        if isinstance(relation, dict):
            relation.pop("attributes", None)
    # The pack-level evidence list is what the envelope hands back as the answer's
    # provenance, and nothing bounded it: a synthetic high-fanout net returned
    # 31.26 MB of which 31.22 MB was this list (764x the payload it describes).
    evidence = pack.get("evidence")
    if isinstance(evidence, list) and len(evidence) > EVIDENCE_LIMIT:
        pack["evidence"] = evidence[:EVIDENCE_LIMIT]
        pack["evidence_truncated"] = True
        pack["evidence_total"] = len(evidence)
        pack["evidence_returned"] = EVIDENCE_LIMIT
        pack.setdefault("limitations", []).append({
            "field": "evidence", "status": "truncated",
            "returned": EVIDENCE_LIMIT, "total": len(evidence),
            "next_offset": EVIDENCE_LIMIT,
            **_continuation("evidence", snapshot_id, target_id, target_type, EVIDENCE_LIMIT)})
    pack.setdefault("limitations", []).append({
        "field": "records[].evidence",
        "status": "projected",
        "reason": "summary keeps each record's compact source_ref and locator; "
                  "GET /snapshots/{snapshot_id}/records/{record_type}/{record_id}"
                  "/evidence returns the resolved entry, and detail=full inlines it"})
    return pack


def _scope_snapshot(pack: dict[str, Any]) -> str | None:
    """The snapshot a pack's scope names; the two pack shapes spell it differently."""
    scope = pack.get("scope")
    if not isinstance(scope, dict):
        return None
    return scope.get("snapshot_id") or scope.get("snapshot")


def _continuation(field: str, snapshot_id: str | None, target_id: str | None,
                  target_type: str | None, limit: int,
                  returned: int | None = None,
                  neighbour_total: int | None = None) -> dict[str, Any]:
    """The routes that carry the rest of a collection a first screen cut.

    Every step is an existing tool on the same snapshot, and the steps are written
    out rather than implied because a bound whose continuation cannot actually be
    followed is a capability cut.  A pack's collections are *merged* views - one
    net context lists the target, its neighbours and the neighbours' parents -
    so ``next_offset`` counts rows of the *paged* source, which is what the first
    route pages, and the rows that are not from that source are named by the
    route that reaches them instead of being lumped under one offset.
    """
    target = quote(target_id, safe="") if target_id else None
    is_object = target_type in {"object", "net"}
    if field == "entities":
        return _entity_continuation(snapshot_id, target, target_type, limit, returned,
                                    neighbour_total)
    if field == "relations" and snapshot_id and target and is_object:
        return {"next": [
            f"/snapshots/{snapshot_id}/objects/{target}/context?relation_limit=0",
            f"and /snapshots/{snapshot_id}/objects/{{object_id}}/context?relation_limit=0 for "
            f"every other object the pack lists: the pack merges their relations"]}
    if field == "physical_context" and snapshot_id:
        return {"next": [
            f"/snapshots/{snapshot_id}/physical/{{object_id}} for each object_id the entities "
            f"page returns, and /snapshots/{snapshot_id}/objects/{{object_id}} for the object"]}
    if field == "physical_context[].routing" and snapshot_id and target:
        return {"next": [f"/snapshots/{snapshot_id}/physical/{target}"]}
    if field == "timing_context.points" and snapshot_id and target:
        return {"next": [f"/snapshots/{snapshot_id}/timing-paths/{target}/points"
                         f"?limit={limit}&offset={limit}"]}
    if field == "evidence":
        return {"next": [
            "/snapshots/{snapshot_id}/records/{record_type}/{record_id}/evidence for the "
            "record_type and record_id each entry carries"]}
    if field == "observations" and snapshot_id:
        return {"next": [
            f"/snapshots/{snapshot_id}/observations?limit={limit}&offset={limit}"]}
    return {}


def _entity_continuation(snapshot_id: str | None, target: str | None,
                         target_type: str | None, limit: int,
                         returned: int | None, neighbour_total: int | None) -> dict[str, Any]:
    """The route that carries the rest of the entity sample, and where to resume.

    The screen is ``[target] + neighbours + neighbours' parents``.  The neighbour
    part can be re-enumerated in full with ``connected_to``, but *not* from a row
    offset: the pack walks the relations while the paged route walks the store's
    key order, so "199 rows in, resume at 199" would silently skip and repeat
    rows.  The route is therefore given from offset 0 and the caller skips ids it
    already holds - one page of overlap, no gap.  When the count says every
    neighbour is already on screen, no neighbour route is offered at all, because
    the only rows still missing are the parents each row already names.
    """
    if not snapshot_id:
        return {}
    parents = (f"/snapshots/{snapshot_id}/objects/{{parent_id}} for the parent_id a neighbour "
               f"row carries, and /snapshots/{snapshot_id}/objects/{{object_id}} for one row")
    if target_type in {"object", "net"} and target:
        if neighbour_total is not None and neighbour_total <= (returned or 0) - 1:
            return {"next_offset": None, "next": [
                f"all {neighbour_total} neighbours are in this screen; the rows still missing "
                f"are their parents - {parents}"]}
        return {"next_offset": 0, "next": [
            f"/snapshots/{snapshot_id}/objects?connected_to={target}&limit={limit}&offset=0 "
            f"walks the whole neighbourhood, in a different order than the pack, so skip the ids "
            f"already returned",
            parents]}
    return {"next_offset": 0, "next": [
        f"/snapshots/{snapshot_id}/timing-paths/{target}/points?limit={limit}&offset=0",
        f"then /snapshots/{snapshot_id}/objects?connected_to={{net_id}}&limit={limit}&offset=0 "
        f"for each net_id on that page, skipping ids already returned"]}


def _bound_points(pack: dict[str, Any], timing: dict[str, Any], snapshot_id: str | None,
                  target_id: str | None, target_type: str | None) -> None:
    """Sample the path's own points: the one collection that grows with the path.

    190 points were 388,983 B of a 628,423 B pack - 62% of the answer - while the
    questions those paths were fetched for needed the nets they name, not all of
    them.  ``/timing-paths/{id}/points`` is already a paged tool, so the sample is
    bounded and the rest is one request away.
    """
    points = timing.get("points")
    if not isinstance(points, list) or len(points) <= FIRST_SCREEN_LIMIT:
        return
    timing["points"] = points[:FIRST_SCREEN_LIMIT]
    timing["points_returned"] = FIRST_SCREEN_LIMIT
    timing["points_total"] = len(points)
    pack.setdefault("limitations", []).append({
        "field": "timing_context.points", "status": "truncated",
        "returned": FIRST_SCREEN_LIMIT, "total": len(points),
        "next_offset": FIRST_SCREEN_LIMIT,
        **_continuation("timing_context.points", snapshot_id, target_id, target_type,
                        FIRST_SCREEN_LIMIT, FIRST_SCREEN_LIMIT, None)})


def _bound_routing(pack: dict[str, Any], record: dict[str, Any],
                   snapshot_id: str | None, target_id: str | None) -> None:
    """Sample the target's own wire segments instead of inlining all of them.

    The rest of a pack is bounded by row count; this one is a list *inside* a
    row, and it is the largest single term measured - 1,970 segments, 310,603 B
    of a 782,204 B net context.
    """
    routing = record.get("routing")
    if not isinstance(routing, list) or len(routing) <= ROUTING_LIMIT:
        return
    record["routing"] = routing[:ROUTING_LIMIT]
    record["routing_returned"] = ROUTING_LIMIT
    record["routing_total"] = len(routing)
    pack.setdefault("limitations", []).append({
        "field": "physical_context[].routing", "status": "truncated",
        "returned": ROUTING_LIMIT, "total": len(routing), "next_offset": ROUTING_LIMIT,
        "reason": "the target's own routing grows with the net, not with the question",
        **_continuation("physical_context[].routing", snapshot_id, target_id, None,
                        ROUTING_LIMIT)})


def _trim_identity(identity: dict[str, Any]) -> dict[str, Any]:
    """Keep the IDs that identify the object; drop the snapshot-wide echo.

    ``design_id``, ``revision_id``, ``canonical_basis`` and the default
    ``matching_status`` are identical on every record of a snapshot and already
    appear in the pack's ``scope``, so repeating them on all 232 entities of one
    timing path cost 67 KB for nothing.  ``detail=full`` and the per-record
    endpoint still return the untrimmed identity.
    """
    trimmed: dict[str, Any] = {}
    for key in ("native_id", "structural_fingerprint"):
        if identity.get(key) is not None:
            trimmed[key] = identity[key]
    if identity.get("matching_status") not in (None, "candidate"):
        trimmed["matching_status"] = identity["matching_status"]
    canonical = identity.get("canonical")
    if isinstance(canonical, dict):
        trimmed["canonical"] = {key: canonical[key] for key in
                                ("kind", "hierarchical_name") if key in canonical}
    return trimmed


def _related_object_ids(entity: dict[str, Any], relations: list[dict[str, Any]]) -> list[str]:
    object_id = entity.get("object_id")
    return list(dict.fromkeys(
        str(relation[key]) for relation in relations
        for key in ("subject_id", "object_id")
        if relation.get(key) and relation.get(key) != object_id
    ))


def _entities(store: DataStore, snapshot_id: str,
              object_ids: list[str]) -> list[dict[str, Any]]:
    return _rows_by_id(store, snapshot_id, "entities", object_ids)


def _rows_by_id(store: DataStore, snapshot_id: str, record_type: str,
                object_ids: list[str]) -> list[dict[str, Any]]:
    """Records for many ids in batches of 250, in the order they were asked for.

    One point query per id is what made these endpoints unusable on a real
    design: a path context resolved every related object and every physical row
    separately.  ``records`` is keyed by ``(snapshot, record_type, record_id)``,
    so one ``IN`` per batch is an index seek each, and the same batching is what
    ``expand_net`` already does for its neighbours.
    """
    ids = list(dict.fromkeys(object_ids))
    rows: list[dict[str, Any]] = []
    for start in range(0, len(ids), 250):
        chunk = ids[start:start + 250]
        marks = ", ".join("?" for _ in chunk)
        rows.extend(store.filtered(snapshot_id, record_type,
                                   where=f"record_id IN ({marks})", params=chunk))
    by_id = {row.get("object_id") or row.get("record_id"): row for row in rows}
    return [by_id[object_id] for object_id in ids if object_id in by_id]


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
    return _rows_by_id(store, snapshot_id, "physical_context", object_ids)


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


def _append_related_entities(store: DataStore, snapshot_id: str,
                             relations: list[dict[str, Any]],
                             entities: list[dict[str, Any]],
                             seen: set[str]) -> None:
    """Add the far end of every relation, batched: one query per 250, not per id."""
    related = [str(relation[key]) for relation in relations
               for key in ("subject_id", "object_id")
               if relation.get(key) and relation.get(key) not in seen]
    for entity in _rows_by_id(store, snapshot_id, "entities", related):
        object_id = entity.get("object_id")
        if isinstance(object_id, str) and object_id not in seen:
            seen.add(object_id)
            entities.append(entity)
