"""Minimal, explicit timing-analysis context."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


CONTEXT_FIELDS = (
    "design", "revision", "run", "snapshot", "stage", "analysis", "check",
    "corner", "unit",
)
COMPARISON_FIELDS = ("design", "revision", "run", "analysis", "check", "corner", "unit")


def build_analysis_context(snapshot: Mapping[str, Any],
                           path: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Build the fixed context without supplying semantic defaults."""
    path = path or {}
    declared = snapshot.get("analysis_context")
    declared = declared if isinstance(declared, Mapping) else {}
    values = {
        "design": snapshot.get("design_id"),
        "revision": snapshot.get("revision_id"),
        "run": snapshot.get("run_id"),
        "snapshot": snapshot.get("snapshot_id"),
        "stage": snapshot.get("stage"),
        "analysis": _first(path, "analysis", "analysis_view", "view",
                            snapshot, "analysis", declared, "analysis"),
        "check": _first(path, "check", "analysis_check", snapshot, "check",
                         declared, "check"),
        "corner": _first(path, "corner", snapshot, "corner", declared, "corner"),
        "unit": _first(path, "unit", snapshot, "unit", declared, "unit"),
    }
    native = snapshot.get("run_summary", {}).get("timing_context")
    if isinstance(native, Mapping):
        values["rc_source"] = native.get("rc_script")
        values["parasitic_source"] = native.get("parasitics")
        values["parasitic_mode"] = native.get("parasitic_mode")
    missing = [name for name in CONTEXT_FIELDS if not _present(values[name])]
    return {**values, "status": "available" if not missing else "unavailable",
            "missing": missing}


def context_differences(left: Mapping[str, Any], right: Mapping[str, Any],
                        fields: tuple[str, ...] = COMPARISON_FIELDS) -> list[dict[str, Any]]:
    """Return missing or unequal context fields without coercing either side."""
    differences: list[dict[str, Any]] = []
    for field in fields:
        left_value, right_value = left.get(field), right.get(field)
        if not _present(left_value) or not _present(right_value):
            differences.append({"field": field, "reason": "missing",
                                "from": left_value, "to": right_value})
        elif left_value != right_value:
            differences.append({"field": field, "reason": "mismatch",
                                "from": left_value, "to": right_value})
    return differences


def unavailable_capability(name: str, reason: str) -> dict[str, str]:
    return {"capability": name, "status": "unavailable", "reason": reason}


def context_availability(context: Mapping[str, Any]) -> dict[str, Any]:
    corner = context.get("corner")
    return {
        "analysis_context": {"status": context.get("status"),
                             "missing": context.get("missing", [])},
        "corner": ({"status": "available", "value": corner}
                    if _present(corner) else unavailable_capability(
                        "corner", "analysis corner is missing")),
        "rc": ({"status": "available", "source": context["rc_source"]}
               if context.get("rc_source") else unavailable_capability("rc", "no indexed RC context")),
        "parasitic": ({"status": "available", "mode": context["parasitic_mode"],
                       "source": context.get("parasitic_source") or context.get("rc_source")}
                      if context.get("parasitic_mode") in {"spef", "placement"}
                      else unavailable_capability("parasitic", "no indexed parasitic context")),
    }


def _first(value: Mapping[str, Any], *names: Any) -> Any:
    for name in names:
        if isinstance(name, Mapping):
            value = name
            continue
        candidate = value.get(name)
        if _present(candidate):
            return candidate
    return None


def _present(value: Any) -> bool:
    return isinstance(value, str) and bool(value)
