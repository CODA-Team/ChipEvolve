"""Deterministic comparison of structured metric observations."""

from __future__ import annotations

from typing import Any

from .repository import DataStore


def compare_metric(store: DataStore, from_snapshot_id: str,
                   to_snapshot_id: str, name: str,
                   scene: str | None = None) -> dict[str, Any]:
    """Compare one exact metric observation across two immutable snapshots."""
    left_snapshot = store.snapshot(from_snapshot_id)
    right_snapshot = store.snapshot(to_snapshot_id)
    reasons: list[dict[str, Any]] = []
    for field in ("design_id", "revision_id"):
        left, right = left_snapshot.get(field), right_snapshot.get(field)
        if left != right:
            reasons.append({"field": field, "reason": "mismatch",
                            "from": left, "to": right})
    left_rows = _metric_rows(store, from_snapshot_id, name, scene)
    right_rows = _metric_rows(store, to_snapshot_id, name, scene)
    if len(left_rows) != 1:
        reasons.append({"field": "from_observation", "reason": _cardinality(left_rows)})
    if len(right_rows) != 1:
        reasons.append({"field": "to_observation", "reason": _cardinality(right_rows)})
    if len(left_rows) != 1 or len(right_rows) != 1:
        return _incomparable(from_snapshot_id, to_snapshot_id, name, scene,
                             left_rows, right_rows, reasons)
    left, right = left_rows[0], right_rows[0]
    left_unit, right_unit = left.get("unit"), right.get("unit")
    if left_unit != right_unit:
        reasons.append({"field": "unit", "reason": "mismatch",
                        "from": left_unit, "to": right_unit})
    left_value, right_value = left.get("value"), right.get("value")
    if not _number(left_value) or not _number(right_value):
        reasons.append({"field": "value", "reason": "non_numeric",
                        "from": left_value, "to": right_value})
    if reasons:
        return _incomparable(from_snapshot_id, to_snapshot_id, name, scene,
                             left_rows, right_rows, reasons)
    return {
        "status": "COMPARABLE",
        "from_snapshot_id": from_snapshot_id,
        "to_snapshot_id": to_snapshot_id,
        "matching": {"basis": "exact metric name and scene",
                     "conditions": {"same_design": True, "same_revision": True,
                                    "same_unit": True, "one_observation_per_scope": True}},
        "metric": name,
        "scene": scene,
        "value": {"from": left_value, "to": right_value,
                  "delta": right_value - left_value},
        "unit": left_unit,
        "observations": {"from": left, "to": right},
        "evidence": {"from": left.get("evidence", []),
                     "to": right.get("evidence", [])},
    }


def _metric_rows(store: DataStore, snapshot_id: str, name: str,
                 scene: str | None) -> list[dict[str, Any]]:
    rows = store.records(snapshot_id, "observations", limit=10000)
    return [row for row in rows
            if row.get("kind") == "metric"
            and _value(row, "name") == name
            and (scene is None or _value(row, "scene") == scene)]


def _value(row: dict[str, Any], field: str) -> Any:
    if field == "name":
        return row.get("name") or row.get("metric") or str(
            row.get("observation_id", "")).removeprefix("metric:")
    if field == "scene":
        context = row.get("context")
        return context.get("scene") if isinstance(context, dict) else row.get(field)
    return row.get(field)


def _incomparable(from_id: str, to_id: str, name: str, scene: str | None,
                  left: list[dict[str, Any]], right: list[dict[str, Any]],
                  reasons: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "status": "INCOMPARABLE",
        "from_snapshot_id": from_id,
        "to_snapshot_id": to_id,
        "metric": name,
        "scene": scene,
        "matching": {"basis": "exact metric name and scene", "reasons": reasons},
        "observations": {"from": left, "to": right},
        "evidence": {"from": [item for row in left for item in row.get("evidence", [])],
                     "to": [item for row in right for item in row.get("evidence", [])]},
    }


def _cardinality(rows: list[dict[str, Any]]) -> str:
    return "missing" if not rows else "ambiguous"


def _number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)
