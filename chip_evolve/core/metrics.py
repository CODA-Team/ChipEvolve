"""Metric identities and numeric validity shared by result decision rules."""

from __future__ import annotations

import math
from typing import Any

METRICS = (
    "finish__timing__setup__tns",
    "finish__timing__setup__ws",
    "finish__timing__hold__tns",
    "finish__power__total",
    "finish__design__instance__area",
    "finish__design__core__area",
    "finish__design__die__area",
)

UPPER_BOUNDS = {
    "max_slew_violations": "finish__timing__drv__max_slew",
    "max_cap_violations": "finish__timing__drv__max_cap",
    "placement_violations": "design__violations",
    "power_total_w_max": "finish__power__total",
    "cell_area_um2_max": "finish__design__instance__area",
    "core_area_um2_max": "finish__design__core__area",
    "die_area_um2_max": "finish__design__die__area",
}
LOWER_BOUNDS = {
    "setup_tns_ns_min": "finish__timing__setup__tns",
    "hold_tns_ns_min": "finish__timing__hold__tns",
}
OPTIONAL_METRICS = (
    "finish__timing__hold__ws",
    "finish__timing__drv__max_fanout",
)


def metric_issue(name: str, value: Any) -> str | None:
    if value is None:
        return "missing_metric:" + name
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return "invalid_metric:" + name
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        return "non_finite_metric:" + name
    return None


def metric_issues(frame: dict[str, Any]) -> list[str]:
    """Require final PPA/constraint numbers and validate optional observed facts."""
    metrics = frame.get("metrics")
    if not isinstance(metrics, dict):
        return [
            "missing_metric:metrics" if metrics is None else "invalid_metric:metrics"
        ]
    names = dict.fromkeys((*METRICS, *UPPER_BOUNDS.values(), *LOWER_BOUNDS.values()))
    values = {name: metrics.get(name) for name in names}
    values.update({name: metrics[name] for name in OPTIONAL_METRICS if name in metrics})
    values["route_drc"] = frame.get("route_drc")
    failed = []
    for name, value in values.items():
        issue = metric_issue(name, value)
        if issue is not None:
            failed.append(issue)
    return failed
