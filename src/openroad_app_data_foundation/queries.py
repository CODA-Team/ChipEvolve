"""Deterministic query operations exposed by the data service."""

from __future__ import annotations

from typing import Any

from .repository import DataStore


def list_timing_paths(store: DataStore, snapshot_id: str, query: dict[str, str]) -> dict[str, Any]:
    rows = store.records(snapshot_id, "timing_paths", limit=10000)
    filters = {key: query[key] for key in ("analysis", "check", "group") if query.get(key)}
    if filters:
        rows = [row for row in rows if all(row.get(key) == value for key, value in filters.items())]
    start = _offset(query)
    rows = rows[start:start + _limit(query)]
    return {"snapshot_id": snapshot_id, "timing_paths": rows, "count": len(rows),
            "filters": filters}


def timing_path(store: DataStore, snapshot_id: str, path_id: str) -> dict[str, Any]:
    rows = store.records(snapshot_id, "timing_paths", record_id=path_id, limit=1)
    if not rows:
        raise KeyError(f"timing path not found: {path_id}")
    path = rows[0]
    points = store.records(snapshot_id, "timing_points", limit=10000)
    selected = [row for row in points if row.get("path_id") == path_id]
    selected.sort(key=lambda row: row.get("ordinal", 0))
    return {"snapshot_id": snapshot_id, "timing_path": path, "timing_points": selected}


def path_points(store: DataStore, snapshot_id: str, path_id: str, query: dict[str, str]) -> dict[str, Any]:
    result = timing_path(store, snapshot_id, path_id)
    points = result["timing_points"]
    start = _offset(query)
    limit = _limit(query)
    return {"snapshot_id": snapshot_id, "path_id": path_id,
            "timing_points": points[start:start + limit], "count": len(points)}


def compare_timing_path(store: DataStore, from_snapshot_id: str,
                        to_snapshot_id: str, path_id: str) -> dict[str, Any]:
    """Compare one explicitly identical timing path across two snapshots."""
    before = timing_path(store, from_snapshot_id, path_id)
    after = timing_path(store, to_snapshot_id, path_id)
    before_path, after_path = before["timing_path"], after["timing_path"]
    before_ids = _point_ids(before["timing_points"])
    after_ids = _point_ids(after["timing_points"])
    shared_ids = before_ids & after_ids
    kinds = {row["object_id"]: row.get("kind") for row in store.records(
        from_snapshot_id, "entities", limit=10000)}
    physical = _physical_changes(store, from_snapshot_id, to_snapshot_id, shared_ids, kinds)
    return {
        "from_snapshot_id": from_snapshot_id,
        "to_snapshot_id": to_snapshot_id,
        "matching": {"basis": "exact path_id and object_id", "path_id": path_id},
        "timing": {name: _change(before_path.get(name), after_path.get(name))
                   for name in ("slack", "delay")},
        "connections": _net_changes(before["timing_points"], after["timing_points"]),
        "physical": physical,
        "evidence": {"from": [*before_path.get("evidence", []),
                              *store.snapshot(from_snapshot_id).get("source_artifacts", [])],
                     "to": [*after_path.get("evidence", []),
                            *store.snapshot(to_snapshot_id).get("source_artifacts", [])]},
    }


def _point_ids(points: list[dict[str, Any]]) -> set[str]:
    return {str(point[key]) for point in points for key in ("instance_id", "net_id", "object_id")
            if isinstance(point.get(key), str) and point[key]}


def _net_changes(before: list[dict[str, Any]], after: list[dict[str, Any]]) -> dict[str, list[str]]:
    before_nets = {str(point["net_id"]) for point in before if point.get("net_id")}
    after_nets = {str(point["net_id"]) for point in after if point.get("net_id")}
    return {"shared": sorted(before_nets & after_nets),
            "only_from": sorted(before_nets - after_nets),
            "only_to": sorted(after_nets - before_nets)}


def _physical_changes(store: DataStore, from_snapshot_id: str, to_snapshot_id: str,
                      object_ids: set[str], kinds: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    instances, nets = [], []
    for object_id in sorted(object_ids):
        before = _physical(store, from_snapshot_id, object_id)
        after = _physical(store, to_snapshot_id, object_id)
        if before is None or after is None:
            continue
        if kinds.get(object_id) == "instance" and all(
                isinstance(value.get(name), (int, float))
                for value in (before, after) for name in ("x", "y")):
            instances.append({"object_id": object_id,
                              "from": {name: before[name] for name in ("x", "y")},
                              "to": {name: after[name] for name in ("x", "y")},
                              "delta": {name: after[name] - before[name] for name in ("x", "y")}})
        if kinds.get(object_id) == "net":
            nets.append({"object_id": object_id,
                         "wire_length": _change(_wire_length(before), _wire_length(after))})
    return {"instances": instances, "nets": nets}


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
