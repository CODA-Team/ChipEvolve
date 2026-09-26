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
