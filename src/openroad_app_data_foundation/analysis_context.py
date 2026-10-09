"""Minimal, explicit timing-analysis context."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


CONTEXT_FIELDS = (
    "design", "revision", "run", "snapshot", "stage", "analysis", "check",
    "corner", "unit",
)
COMPARISON_FIELDS = ("design", "revision", "run", "analysis", "check", "corner", "unit")
EXPERIMENT_COMPARISON_FIELDS = ("design", "analysis", "check", "corner", "unit")


def input_identities(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """Registered bytes, separated from experiment-local indexing identity."""
    categories = {
        "database": "raw_design_database", "netlist": "raw_netlist",
        "constraints": "raw_constraints", "libraries": "raw_library",
        "parasitics": "raw_parasitics",
    }
    refs = snapshot.get("source_artifacts", [])
    native = snapshot.get("run_summary", {}).get("timing_context", {})
    declared_sdc = native.get("constraints")
    return {
        role: [{key: ref.get(key) for key in ("logical_path", "sha256", "artifact_id", "run_id")}
               for ref in refs if ref.get("category") == category
               and (role != "constraints" or not declared_sdc or ref.get("logical_path") == declared_sdc)]
        for role, category in categories.items()
    }


def experiment_conditions(left: Mapping[str, Any], right: Mapping[str, Any]) -> dict[str, Any]:
    before, after = input_identities(left), input_identities(right)
    result = {}
    for role in before:
        a, b = before[role], after[role]
        hashes_a = sorted(row["sha256"] for row in a if row.get("sha256"))
        hashes_b = sorted(row["sha256"] for row in b if row.get("sha256"))
        result[role] = {
            "status": "unknown" if not a or not b or len(hashes_a) != len(a) or len(hashes_b) != len(b)
                      else "same" if hashes_a == hashes_b else "changed",
            "from": a, "to": b,
            "basis": "registered source SHA256; input equality alone does not prove causal uniqueness",
        }
        if role == "constraints":
            result[role]["selection"] = "declared loaded SDC when recorded; effective SDC exports are derived observations, not additional execution inputs"
    return result


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
        values["parasitic_source"] = native.get("parasitics") or native.get("global_routing_segments")
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
                      if context.get("parasitic_mode") in {"spef", "placement", "global_routing"}
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
