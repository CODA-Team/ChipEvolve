"""Canonical metric projection (CONTRACT v0.1 section 4.6).

A flow stage writes ~66 raw keys.  Only a small declared set becomes a
first-class metric; everything else stays reachable by its original key so a
consumer never loses data, but nothing pretends to be a canonical concept
without an authoritative source.

Two rules this module exists to enforce:

* runtime is **not** a canonical design metric here - it is an execution fact
  owned by the execution foundation, so it is reported unavailable rather than
  re-derived from a flow stage JSON;
* units follow the producer of each metric. OpenSTA power metrics use SI Watts;
  Liberty leakage-table units are a separate declaration.
"""

from __future__ import annotations

from typing import Any

from .repository import DataStore

#: canonical name -> the raw key suffix it is projected from (the flow prefixes
#: raw names with the stage, e.g. ``finish__timing__setup__ws``).
CANONICAL_METRICS: dict[str, dict[str, Any]] = {
    "WS": {"raw_keys": ("timing__setup__ws",), "unit_family": "time",
           "kind": "timing", "analysis": "setup"},
    "WNS": {"raw_keys": ("timing__setup__ws",), "unit_family": "time",
            "kind": "timing", "analysis": "setup"},
    "TNS": {"raw_keys": ("timing__setup__tns",), "unit_family": "time",
            "kind": "timing", "analysis": "setup"},
    "HOLD_WS": {"raw_keys": ("timing__hold__ws",), "unit_family": "time",
                "kind": "timing", "analysis": "hold"},
    "HOLD_WNS": {"raw_keys": ("timing__hold__ws",), "unit_family": "time",
                 "kind": "timing", "analysis": "hold"},
    "HOLD_TNS": {"raw_keys": ("timing__hold__tns",), "unit_family": "time",
                 "kind": "timing", "analysis": "hold"},
    "SETUP_VIOLATIONS": {"raw_keys": ("timing__drv__setup_violation_count",),
                         "unit_family": "count", "kind": "timing", "analysis": "setup"},
    "AREA": {"raw_keys": ("design__instance__area",), "unit_family": "area",
             "kind": "physical"},
    "POWER_TOTAL": {"raw_keys": ("power__total",), "unit_family": "power",
                    "kind": "power"},
    "INSTANCE_COUNT": {"raw_keys": ("design__instance__count",),
                       "unit_family": "count", "kind": "design"},
}

#: unit family -> the flow's platform declaration key that carries its unit.
UNIT_DECLARATIONS = {
    "time": "time_units",
    "area": "distance_units",
    "power": "power_units",
    "count": None,
}

#: Fallback tokens when a family has no declaration in the snapshot.
UNIT_FALLBACK = {"time": "ns", "area": "um^2", "power": "nW", "count": "count"}

#: Runtime is owned by the execution foundation (EF run metrics), not here.
EXECUTION_OWNED = {
    "RUNTIME": "runtime is an execution fact owned by the execution foundation",
}


def observation_name(row: dict[str, Any]) -> str:
    value = row.get("name") or row.get("metric")
    if isinstance(value, str) and value:
        return value
    observation_id = row.get("observation_id")
    if isinstance(observation_id, str):
        return observation_id.removeprefix("metric:")
    return ""


def project_run(store: DataStore, snapshots: list[dict[str, Any]]) -> dict[str, Any]:
    """Project every metric observation of a run into canonical rows.

    ``snapshots`` are snapshot records as returned by ``DataStore.snapshots``.
    """
    canonical: list[dict[str, Any]] = []
    raw: list[dict[str, Any]] = []
    available_units: set[str] = set()
    # Unit declarations are a platform/run-level fact that ORFS writes in only
    # one of the stage reports, so collect them across the whole run and let a
    # snapshot-local declaration win.
    rows_by_snapshot: dict[str, list[dict[str, Any]]] = {}
    run_hints: dict[str, str] = {}
    for snapshot in snapshots:
        snapshot_id = snapshot.get("snapshot_id")
        rows = [row for row in store.fetch_all(snapshot_id, "observations")
                if row.get("kind") == "metric"]
        rows_by_snapshot[snapshot_id] = rows
        run_hints.update(_unit_hints(rows))
    for snapshot in snapshots:
        snapshot_id = snapshot.get("snapshot_id")
        stage = snapshot.get("stage")
        rows = rows_by_snapshot.get(snapshot_id, [])
        hints = {**run_hints, **_unit_hints(rows)}
        available_units.update(_resolved_units(hints).keys())
        consumed: set[int] = set()
        by_tail: dict[str, dict[str, Any]] = {}
        for row in rows:
            by_tail.setdefault(_tail(observation_name(row)), row)
        for name, spec in CANONICAL_METRICS.items():
            row = next((by_tail[key] for key in spec["raw_keys"] if key in by_tail), None)
            if row is None:
                continue
            consumed.add(id(row))
            canonical.append(_canonical_row(name, spec, row, snapshot, hints))
        for row in rows:
            if id(row) in consumed:
                continue
            name = observation_name(row)
            raw.append({
                "canonical": False,
                "raw_key": name,
                "value": row.get("value"),
                "stage": stage,
                "snapshot_id": snapshot_id,
                "scene": (row.get("context") or {}).get("scene")
                if isinstance(row.get("context"), dict) else None,
                "analysis": (row.get("context") or {}).get("analysis")
                if isinstance(row.get("context"), dict) else None,
                "evidence": row.get("evidence", []),
                "status": row.get("status", "parsed"),
            })
    for name, reason in EXECUTION_OWNED.items():
        canonical.append({"name": name, "canonical": True, "status": "unavailable",
                          "reason": reason, "authoritative_source": "execution_foundation",
                          "value": None, "unit": None, "corner": None,
                          "corner_status": "not_declared"})
    names = sorted({row["name"] for row in canonical if row.get("status") == "available"})
    return {"metrics": canonical, "raw_metrics": raw,
            "canonical_names_available": names,
            "units_declared": sorted(available_units)}


def _canonical_row(name: str, spec: dict[str, Any], row: dict[str, Any],
                   snapshot: dict[str, Any], hints: dict[str, str]) -> dict[str, Any]:
    unit, unit_note = _unit_for(spec["unit_family"], hints)
    status = "available"
    reason = None
    if unit is None:
        status, reason = "partial", unit_note or "unit is not declared by the source"
    if name == "POWER_TOTAL":
        # report_power_metric writes design_power's SI values directly, without
        # power-unit conversion. Native report_power confirms Watts on both designs.
        # The Liberty declaration (1nW) describes library leakage tables, not this metric.
        unit = "W"
        unit_note = "OpenSTA design_power SI Watts; library power declaration is not the metric unit"
        status, reason = "available", None
    context = row.get("context") if isinstance(row.get("context"), dict) else {}
    # CONTRACT 5 rule 3: a corner the source does not declare is *stated*, not
    # left as a bare null.  ORFS run-level reports carry no corner at all, so
    # marking every metric unavailable would destroy the metric surface; saying
    # "not_declared" keeps the value and keeps the gap visible.
    corner = context.get("corner")
    value = row.get("value")
    if name in ("WNS", "HOLD_WNS") and isinstance(value, (int, float)):
        value = min(0.0, value)
    return {
        "name": name,
        "canonical": True,
        "value": value,
        "raw_value": row.get("value"),
        "value_basis": "min(0, worst slack)" if name in ("WNS", "HOLD_WNS") else "source value",
        "corner_status": "declared" if corner else "not_declared",
        "unit": unit,
        "unit_declared": unit_note,
        "stage": snapshot.get("stage"),
        "snapshot_id": snapshot.get("snapshot_id"),
        "analysis": spec.get("analysis") or context.get("analysis"),
        "check": spec.get("analysis") or context.get("check"),
        "corner": corner,
        "scene": context.get("scene"),
        "kind": spec.get("kind"),
        "authoritative_source": "orfs_stage_report",
        "raw_key": observation_name(row),
        "status": status,
        "reason": reason,
        "evidence": row.get("evidence", []),
    }


def _tail(name: str) -> str:
    """``finish__timing__setup__ws`` -> ``timing__setup__ws``."""
    return name.split("__", 1)[1] if "__" in name else name


def _unit_hints(rows: list[dict[str, Any]]) -> dict[str, str]:
    hints: dict[str, str] = {}
    for row in rows:
        name = observation_name(row)
        marker = "__flow__platform__"
        if marker in name:
            hints[name.rsplit(marker, 1)[1]] = str(row.get("value"))
    return hints


def _resolved_units(hints: dict[str, str]) -> dict[str, str]:
    return {family: token for family, key in UNIT_DECLARATIONS.items()
            if key and (token := _token(hints.get(key)))}


def _unit_for(family: str, hints: dict[str, str]):
    if family == "count":
        return "count", None
    key = UNIT_DECLARATIONS.get(family)
    declared = hints.get(key) if key else None
    token = _token(declared)
    if token is None:
        return None, f"{key} is not declared in this snapshot"
    if family == "area":
        return f"{token}^2", declared
    return token, declared


def _token(value: str | None) -> str | None:
    """``1ns`` -> ``ns``; ``1um`` -> ``um``; unknown shapes are kept verbatim."""
    if not isinstance(value, str) or not value:
        return None
    text = value.strip()
    if text.startswith("1") and len(text) > 1:
        return text[1:]
    return text
