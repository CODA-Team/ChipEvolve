"""Deterministic query operations exposed by the data service."""

from __future__ import annotations

from typing import Any

from .analysis_context import (
    build_analysis_context, context_availability, context_differences,
)
from .identity import canonical_key
from .metrics import CANONICAL_METRICS, project_run
from .repository import RECORD_TYPES, DataStore, record_identifier


def list_timing_paths(store: DataStore, snapshot_id: str, query: dict[str, str]) -> dict[str, Any]:
    filters = {key: query[key] for key in ("analysis", "check", "group") if query.get(key)}
    where = " AND ".join(f"json_extract(payload, '$.{key}') = ?" for key in filters)
    params = list(filters.values())
    total = store.count_records(snapshot_id, "timing_paths", where=where, params=params)
    limit, offset = _limit(query), _offset(query)
    rows = store.filtered(snapshot_id, "timing_paths", where=where, params=params,
                          limit=limit, offset=offset)
    return {"snapshot_id": snapshot_id, "timing_paths": rows,
            **_page(total, len(rows), limit, offset), "filters": filters}


def list_observations(store: DataStore, snapshot_id: str,
                      query: dict[str, str]) -> dict[str, Any]:
    """List structured facts without exposing the records table.

    ``name``/``scene`` resolve through the observation payload fallback chain,
    so this filter stays in Python over the complete set (observations are
    small); the pagination envelope is still exact.
    """
    rows = store.fetch_all(snapshot_id, "observations")
    filters = {key: query[key] for key in ("name", "kind", "object_id", "status", "scene")
               if query.get(key)}
    rows = [row for row in rows if all(
        _observation_value(row, key) == value for key, value in filters.items())]
    limit, offset = _limit(query), _offset(query)
    page = rows[offset:offset + limit]
    return {"snapshot_id": snapshot_id, "observations": page,
            **_page(len(rows), len(page), limit, offset), "filters": filters}


def list_metrics_for_run(store: DataStore, run_id: str,
                         query: dict[str, str]) -> dict[str, Any]:
    """Canonical metrics for one run, plus raw keys on request.

    CONTRACT section 4.6: ``metrics`` holds only the declared canonical set,
    each with its authoritative source; everything else stays available under
    its original key in ``raw_metrics`` (``include_raw=1``) so the response
    stays small by default.
    """
    projection = project_run(store, store.snapshots(run_id=run_id))
    filters = {key: query[key]
               for key in ("stage", "name", "scene", "snapshot_id")
               if query.get(key)}
    rows = [row for row in projection["metrics"] if _metric_matches(row, filters)]
    limit, offset = _limit(query), _offset(query)
    page = rows[offset:offset + limit]
    result: dict[str, Any] = {
        "run_id": run_id, "metrics": page,
        **_page(len(rows), len(page), limit, offset),
        "canonical_names": sorted(CANONICAL_METRICS),
        # Scope this to the rows the response actually covers.  Reporting the
        # run-wide list here meant a snapshot-scoped request advertised WNS for a
        # stage whose report never declares it (cold audit finding).
        "canonical_names_available": sorted({row["name"] for row in rows
                                             if row.get("status") == "available"}),
        "units_declared": projection["units_declared"],
        "filters": filters,
    }
    if str(query.get("include_raw", "")).lower() in {"1", "true", "yes"}:
        raw = projection["raw_metrics"]
        if filters.get("stage"):
            raw = [row for row in raw if row.get("stage") == filters["stage"]]
        result["raw_metrics"] = raw[offset:offset + limit]
        result["raw_metric_count"] = len(raw)
    return result


def _metric_matches(row: dict[str, Any], filters: dict[str, str]) -> bool:
    for key, value in filters.items():
        if key == "name":
            if row.get("name") != value and row.get("raw_key") != value:
                return False
        elif row.get(key) != value:
            return False
    return True


def _observation_value(row: dict[str, Any], name: str) -> Any:
    if name == "name":
        value = row.get("name") or row.get("metric")
        if value is not None:
            return value
        observation_id = row.get("observation_id")
        return observation_id.removeprefix("metric:") if isinstance(observation_id, str) else None
    if name == "scene":
        context = row.get("context")
        return context.get("scene") if isinstance(context, dict) else row.get(name)
    return row.get(name)


def list_evidence(store: DataStore, snapshot_id: str,
                 query: dict[str, str]) -> dict[str, Any]:
    """Paged evidence index (CONTRACT section 5).

    The index is large - ibex has about 190k entries, which used to be one
    95 MB response - so records are streamed and the scan stops as soon as one
    page plus one item is collected.  ``count`` is the exact total only when the
    scan finished; otherwise it is reported as not computed instead of letting
    the page size masquerade as the total.
    """
    artifact_id = query.get("artifact_id")
    limit, offset = _limit(query), _offset(query)
    matched = 0
    page: list[dict[str, Any]] = []
    complete = True
    for record_type in RECORD_TYPES:
        for row in store.iter_records(snapshot_id, record_type):
            for item in row.get("evidence", []):
                if not isinstance(item, dict):
                    continue
                if artifact_id is not None and item.get("artifact_id") != artifact_id:
                    continue
                if matched < offset:
                    matched += 1
                    continue
                if len(page) >= limit:
                    complete = False
                    break
                page.append({"record_type": record_type,
                             "record_id": record_identifier(record_type, row),
                             "evidence": item})
                matched += 1
            if not complete:
                break
        if not complete:
            break
    result: dict[str, Any] = {"snapshot_id": snapshot_id, "evidence": page}
    if complete:
        result.update(_page(matched, len(page), limit, offset))
    else:
        result.update({"count": None, "count_status": "unavailable",
                       "count_reason": ("the index is larger than one page; the "
                                        "total is not computed"),
                       "returned": len(page), "limit": limit, "offset": offset,
                       "truncated": True, "next_offset": offset + len(page)})
    return result


def timing_path(store: DataStore, snapshot_id: str, path_id: str) -> dict[str, Any]:
    rows = store.records(snapshot_id, "timing_paths", record_id=path_id, limit=1)
    if not rows:
        raise KeyError(f"timing path not found: {path_id}")
    path = rows[0]
    selected = store.filtered(snapshot_id, "timing_points",
                              where="json_extract(payload, '$.path_id') = ?",
                              params=(path_id,))
    selected.sort(key=lambda row: row.get("ordinal", 0))
    return {"snapshot_id": snapshot_id, "timing_path": path, "timing_points": selected,
            "analysis_context": build_analysis_context(store.snapshot(snapshot_id), path)}


def path_points(store: DataStore, snapshot_id: str, path_id: str, query: dict[str, str]) -> dict[str, Any]:
    result = timing_path(store, snapshot_id, path_id)
    points = result["timing_points"]
    limit = _limit(query)
    offset = _offset(query)
    page = points[offset:offset + limit]
    return {"snapshot_id": snapshot_id, "path_id": path_id,
            "timing_points": page, **_page(len(points), len(page), limit, offset)}


def compare_timing_path(store: DataStore, from_snapshot_id: str,
                        to_snapshot_id: str, path_id: str,
                        to_path_id: str | None = None) -> dict[str, Any]:
    """Compare paths only after proving their semantic prerequisites."""
    from_snapshot = store.snapshot(from_snapshot_id)
    to_snapshot = store.snapshot(to_snapshot_id)
    before = timing_path(store, from_snapshot_id, path_id)
    target_path_id = to_path_id or path_id
    after = timing_path(store, to_snapshot_id, target_path_id)
    before_path, after_path = before["timing_path"], after["timing_path"]
    before_context = before["analysis_context"]
    after_context = after["analysis_context"]
    reasons = _comparison_reasons(
        before_context, after_context, before_path, after_path)
    path_basis, path_detail = _path_match(before_path, after_path)
    evidence = {"from": _path_evidence(store, from_snapshot_id, path_id, before_path),
                "to": _path_evidence(store, to_snapshot_id, target_path_id, after_path)}
    if reasons or path_basis == "unresolved":
        if path_basis == "unresolved":
            reasons.append({"field": "path_identity", "reason": "unresolved"})
        return _incomparable(
            from_snapshot_id, to_snapshot_id, path_id, target_path_id,
            before_context, after_context, before_path, after_path,
            reasons, path_detail, evidence,
        )

    matched, unresolved = _match_objects(
        store, from_snapshot_id, to_snapshot_id,
        before["timing_points"], after["timing_points"],
    )
    physical = _physical_changes(store, from_snapshot_id, to_snapshot_id, matched)
    return {
        "status": "COMPARABLE",
        "from_snapshot_id": from_snapshot_id,
        "to_snapshot_id": to_snapshot_id,
        "matching": {"basis": path_basis,
                     "path_id": {"from": path_id, "to": target_path_id,
                                 "scope": "snapshot-local"},
                     "path_identity": path_detail,
                     "conditions": {"analysis_context": "available and equal",
                                    "endpoints": "equal", "path_identity": path_basis}},
        "analysis_context": {"from": before_context, "to": after_context},
        "timing": {name: _change(before_path.get(name), after_path.get(name))
                   for name in ("slack", "delay")},
        "connections": _net_changes(before["timing_points"], after["timing_points"]),
        "physical": physical,
        "matched_objects": _matched_relations(matched),
        "unmatched_objects": unresolved,
        "relations": _matched_relations(matched),
        "availability": context_availability(before_context),
        "evidence": evidence,
    }


def _comparison_reasons(left: dict[str, Any], right: dict[str, Any],
                        left_path: dict[str, Any], right_path: dict[str, Any]
                        ) -> list[dict[str, Any]]:
    reasons = context_differences(left, right)
    for field in ("startpoint", "endpoint", "group"):
        left_value, right_value = left_path.get(field), right_path.get(field)
        if not _present(left_value) or not _present(right_value):
            reasons.append({"field": field, "reason": "missing",
                            "from": left_value, "to": right_value})
        elif left_value != right_value:
            reasons.append({"field": field, "reason": "mismatch",
                            "from": left_value, "to": right_value})
    return reasons


def _path_match(left: dict[str, Any], right: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    native_left = _path_identity_value(left, "native_path_id")
    native_right = _path_identity_value(right, "native_path_id")
    if native_left and native_right and native_left == native_right:
        return "native_exact", {"native_path_id": native_left}
    structural_left = _path_identity_value(left, "structural_fingerprint")
    structural_right = _path_identity_value(right, "structural_fingerprint")
    if structural_left and structural_right and structural_left == structural_right:
        return "structural_verified", {"structural_fingerprint": structural_left}
    fields = ("startpoint", "endpoint", "analysis", "check", "corner", "unit", "group")
    if all(_present(left.get(field)) and left.get(field) == right.get(field)
           for field in fields):
        return "scoped_name", {field: left.get(field) for field in fields}
    return "unresolved", {"from_path_id": left.get("path_id"),
                           "to_path_id": right.get("path_id")}


def _path_identity_value(path: dict[str, Any], name: str) -> str | None:
    value = path.get(name)
    if isinstance(value, str) and value:
        return value
    identity = path.get("path_identity")
    if isinstance(identity, dict):
        value = identity.get(name)
        return value if isinstance(value, str) and value else None
    return None


def _net_changes(before: list[dict[str, Any]], after: list[dict[str, Any]]) -> dict[str, list[str]]:
    before_nets = {str(point["net_id"]) for point in before if point.get("net_id")}
    after_nets = {str(point["net_id"]) for point in after if point.get("net_id")}
    return {"shared": sorted(before_nets & after_nets),
            "only_from": sorted(before_nets - after_nets),
            "only_to": sorted(after_nets - before_nets),
            "basis": "snapshot-local point references; not cross-stage identity"}


def _physical_changes(store: DataStore, from_snapshot_id: str, to_snapshot_id: str,
                      matched: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    instances, nets = [], []
    for item in matched:
        from_id = item["from_object_id"]
        to_id = item["to_object_id"]
        before = _physical(store, from_snapshot_id, from_id)
        after = _physical(store, to_snapshot_id, to_id)
        if before is None or after is None:
            continue
        if item.get("kind") == "instance" and all(
                isinstance(value.get(name), (int, float))
                for value in (before, after) for name in ("x", "y")):
            instances.append({"from_object_id": from_id, "to_object_id": to_id,
                              "matching_basis": item["matching_basis"],
                              "evidence": item["evidence"],
                              "from": {name: before[name] for name in ("x", "y")},
                              "to": {name: after[name] for name in ("x", "y")},
                              "delta": {name: after[name] - before[name] for name in ("x", "y")}})
        if item.get("kind") == "net":
            nets.append({"from_object_id": from_id, "to_object_id": to_id,
                         "matching_basis": item["matching_basis"],
                         "evidence": item["evidence"],
                         "wire_length": _change(_wire_length(before), _wire_length(after))})
    return {"instances": instances, "nets": nets}


def _matched_relations(matched: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{
        "predicate": "same_design_object_as",
        "from_object_id": item["from_object_id"],
        "to_object_id": item["to_object_id"],
        "identity": item["identity"],
        "matching_basis": item["matching_basis"],
        "evidence": item["evidence"],
    } for item in matched]


def _incomparable(from_snapshot_id: str, to_snapshot_id: str,
                  from_path_id: str, to_path_id: str,
                  from_context: dict[str, Any], to_context: dict[str, Any],
                  from_path: dict[str, Any], to_path: dict[str, Any],
                  reasons: list[dict[str, Any]], path_detail: dict[str, Any],
                  evidence: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    return {
        "status": "INCOMPARABLE",
        "from_snapshot_id": from_snapshot_id,
        "to_snapshot_id": to_snapshot_id,
        "matching": {"basis": "unresolved",
                     "path_id": {"from": from_path_id, "to": to_path_id,
                                 "scope": "snapshot-local"},
                     "path_identity": path_detail,
                     "reasons": reasons},
        "analysis_context": {"from": from_context, "to": to_context},
        "path_identity": {"from": _path_view(from_path),
                          "to": _path_view(to_path)},
        "availability": context_availability(from_context),
        "limitations": [{"status": "incomparable", "reasons": reasons}],
        "evidence": evidence,
    }


def _match_objects(store: DataStore, from_snapshot_id: str, to_snapshot_id: str,
                   from_points: list[dict[str, Any]],
                   to_points: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    from_objects = _path_objects(store, from_snapshot_id, from_points)
    to_objects = _path_objects(store, to_snapshot_id, to_points)
    by_native = _identity_candidates(to_objects, "native_id")
    by_structural = _identity_candidates(to_objects, "structural_fingerprint")
    by_canonical = _canonical_candidates(to_objects)
    matched: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    for source in from_objects:
        identity = source.get("identity") or {}
        candidates: list[dict[str, Any]] = []
        basis = "unresolved"
        native_id = identity.get("native_id")
        if isinstance(native_id, str) and native_id:
            candidates = by_native.get((source.get("kind"), native_id), [])
            basis = "native_exact"
        if not candidates:
            fingerprint = identity.get("structural_fingerprint")
            if isinstance(fingerprint, str) and fingerprint:
                candidates = by_structural.get((source.get("kind"), fingerprint), [])
                basis = "structural_verified"
        if not candidates:
            key = _canonical_tuple(identity)
            if key is not None:
                candidates = by_canonical.get(key, [])
                basis = "scoped_name"
        if len(candidates) == 1:
            target = candidates[0]
            item = {
                "from_object_id": source["object_id"],
                "to_object_id": target["object_id"],
                "kind": source.get("kind"),
                "matching_basis": basis,
                "identity": {"from": source.get("identity"),
                             "to": target.get("identity")},
            }
            item["evidence"] = {
                "from": _object_evidence(store, from_snapshot_id, source["object_id"]),
                "to": _object_evidence(store, to_snapshot_id, target["object_id"]),
            }
            matched.append(item)
            continue
        unresolved.append({
            "status": "ambiguous" if len(candidates) > 1 else "unresolved",
            "from_object_id": source["object_id"],
            "identity": source.get("identity"),
            "matching_basis": basis,
            "candidate_object_ids": [item["object_id"] for item in candidates],
            "evidence": {"from": _object_evidence(
                store, from_snapshot_id, source["object_id"])},
        })
    return matched, unresolved


def _path_objects(store: DataStore, snapshot_id: str,
                  points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    wanted: list[str] = []
    for point in points:
        for field in ("pin_id", "instance_id", "net_id", "object_id"):
            value = point.get(field)
            if isinstance(value, str) and value:
                wanted.append(value)
    entities = {row.get("object_id"): row
                for row in store.entities_by_ids(snapshot_id, wanted)}
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for point in points:
        for field in ("pin_id", "instance_id", "net_id", "object_id"):
            object_id = point.get(field)
            if not isinstance(object_id, str) or object_id in seen:
                continue
            seen.add(object_id)
            entity = entities.get(object_id)
            result.append({"object_id": object_id,
                           "kind": entity.get("kind") if entity else None,
                           "identity": entity.get("identity") if entity else None})
    return result


def _identity_candidates(objects: list[dict[str, Any]], field: str
                         ) -> dict[tuple[Any, Any], list[dict[str, Any]]]:
    result: dict[tuple[Any, Any], list[dict[str, Any]]] = {}
    for item in objects:
        value = (item.get("identity") or {}).get(field)
        if isinstance(value, str) and value:
            result.setdefault((item.get("kind"), value), []).append(item)
    return result


def _canonical_candidates(objects: list[dict[str, Any]]) -> dict[tuple[Any, ...], list[dict[str, Any]]]:
    result: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for item in objects:
        key = _canonical_tuple(item.get("identity"))
        if key is not None:
            result.setdefault(key, []).append(item)
    return result


def _canonical_tuple(identity: dict[str, Any] | None) -> tuple[Any, ...] | None:
    if not isinstance(identity, dict):
        return None
    canonical = identity.get("canonical")
    if not isinstance(canonical, dict) or identity.get("matching_status") == "ambiguous":
        return None
    return canonical_key(identity)


def _object_evidence(store: DataStore, snapshot_id: str,
                     object_id: str) -> list[dict[str, Any]]:
    entity = store.records(snapshot_id, "entities", record_id=object_id, limit=1)
    physical = store.records(snapshot_id, "physical_context", record_id=object_id, limit=1)
    result = [{"record_type": "entities", "record_id": object_id,
               "evidence": item}
              for item in (entity[0].get("evidence", []) if entity else [])
              if isinstance(item, dict)]
    result.extend({"record_type": "physical_context", "record_id": object_id,
                   "evidence": item}
                  for item in (physical[0].get("evidence", []) if physical else [])
                  if isinstance(item, dict))
    return result or [{"status": "unavailable", "reason": "no evidence reference",
                      "record_id": object_id}]


def _path_evidence(store: DataStore, snapshot_id: str, path_id: str,
                   path: dict[str, Any]) -> list[dict[str, Any]]:
    result = [{"record_type": "timing_paths", "record_id": path_id,
               "evidence": item}
              for item in path.get("evidence", []) if isinstance(item, dict)]
    if not result:
        result.append({"record_type": "timing_paths", "record_id": path_id,
                       "evidence": {"status": "unavailable",
                                    "reason": "no evidence reference"}})
    return result + [{"record_type": "snapshot", "record_id": snapshot_id,
                      "artifact": item}
                     for item in store.snapshot(snapshot_id).get("source_artifacts", [])
                     if isinstance(item, dict)]


def _path_view(path: dict[str, Any]) -> dict[str, Any]:
    return {name: path.get(name) for name in (
        "path_id", "startpoint", "endpoint", "analysis", "check", "corner", "unit")}


def _present(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def _physical(store: DataStore, snapshot_id: str, object_id: str) -> dict[str, Any] | None:
    rows = store.records(snapshot_id, "physical_context", record_id=object_id, limit=1)
    return rows[0] if rows else None


def _wire_length(physical: dict[str, Any]) -> int:
    return sum(abs(item["x_max"] - item["x_min"]) + abs(item["y_max"] - item["y_min"])
               for item in physical.get("routing", [])
               if item.get("routing_type") == "segment"
               and all(isinstance(item.get(name), (int, float))
                       for name in ("x_min", "x_max", "y_min", "y_max")))


def _change(before: Any, after: Any) -> dict[str, Any]:
    result = {"from": before, "to": after}
    if isinstance(before, (int, float)) and isinstance(after, (int, float)):
        result["delta"] = after - before
    return result


def _page(total: int, returned: int, limit: int, offset: int) -> dict[str, Any]:
    """Pagination envelope shared by every list tool (CONTRACT section 5)."""
    truncated = offset + returned < total
    return {"count": total, "returned": returned, "limit": limit, "offset": offset,
            "truncated": truncated,
            "next_offset": offset + returned if truncated else None}


def _limit(query: dict[str, str]) -> int:
    value = int(query.get("limit", "100"))
    if not 1 <= value <= 10000:
        raise ValueError("limit must be between 1 and 10000")
    return value


def _offset(query: dict[str, str]) -> int:
    value = int(query.get("offset", "0"))
    if value < 0:
        raise ValueError("offset must not be negative")
    return value
