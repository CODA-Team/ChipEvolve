"""Canonical stage-scoped static-config recipe helpers.

The clock value is already a first-class parameter, so the SDC identity normalizes
only that numeric token. Semantically equal ``235.50`` and ``235.5`` SDCs therefore
share a recipe identity while every other constraint remains byte-sensitive.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, Dict, Mapping, Optional


SCHEMA_VERSION = 1
FINAL_PARAM_NAMES = (
    "SYNTH_FLATTEN",
    "CORE_UTILIZATION",
    "CELL_PAD_IN_SITES_GLOBAL_PLACEMENT",
    "CELL_PAD_IN_SITES_DETAIL_PLACEMENT",
    "ENABLE_DPO",
    "PLACE_DENSITY_LB_ADDON",
    "CTS_CLUSTER_SIZE",
    "CTS_CLUSTER_DIAMETER",
    "TNS_END_PERCENT",
    "PIN_LAYER_ADJUST",
    "ABOVE_LAYER_ADJUST",
    "clk_period",
)
SCOPED_PARAM_NAMES = (
    "FLOORPLAN_PIN_LAYER_ADJUST",
    "FLOORPLAN_ABOVE_LAYER_ADJUST",
)
FLOORPLAN_CONTEXT_NAMES = {
    "PIN_LAYER_ADJUST": "FLOORPLAN_PIN_LAYER_ADJUST",
    "ABOVE_LAYER_ADJUST": "FLOORPLAN_ABOVE_LAYER_ADJUST",
}

_CLOCK_TOKEN = re.compile(
    r"(?m)^(?P<prefix>[ \t]*set[ \t]+clk_period[ \t]+)"
    r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
)


def canonical_sdc_sha256(path: Path) -> str:
    """Hash an SDC after replacing only the clk_period numeric token."""
    content = Path(path).read_text(encoding="utf-8").replace("\r\n", "\n")
    normalized, count = _CLOCK_TOKEN.subn(r"\g<prefix><CLOCK>", content)
    if count != 1:
        raise ValueError(f"expected exactly one set clk_period in {path}, found {count}")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _finite_number(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def canonical_final_params(value: Any) -> Optional[Dict[str, float]]:
    if not isinstance(value, Mapping):
        return None
    result: Dict[str, float] = {}
    for name in FINAL_PARAM_NAMES:
        number = _finite_number(value.get(name))
        if number is None:
            return None
        result[name] = number
    return result


def canonical_scoped_params(value: Any) -> Optional[Dict[str, float]]:
    if not isinstance(value, Mapping) or set(map(str, value)) != set(SCOPED_PARAM_NAMES):
        return None
    result: Dict[str, float] = {}
    for name in SCOPED_PARAM_NAMES:
        number = _finite_number(value.get(name))
        if number is None or not 0.0 <= number <= 1.0:
            return None
        result[name] = number
    return result


def build_recipe(final_params: Any, floorplan_routing_context: Any,
                 sdc_sha256: Any) -> Optional[Dict[str, Any]]:
    final = canonical_final_params(final_params)
    if not isinstance(floorplan_routing_context, Mapping):
        return None
    scoped = {}
    context = {}
    for logical, target in FLOORPLAN_CONTEXT_NAMES.items():
        raw = floorplan_routing_context.get(
            logical, floorplan_routing_context.get(target))
        number = _finite_number(raw)
        if number is None or not 0.0 <= number <= 1.0:
            return None
        context[logical] = number
        scoped[target] = number
    sdc_hash = str(sdc_sha256).strip() if sdc_sha256 is not None else ""
    if final is None or not sdc_hash:
        return None
    canonical = {
        "schema_version": SCHEMA_VERSION,
        "final_params": final,
        "floorplan_routing_context": context,
        "scoped_params": scoped,
        "sdc_sha256": sdc_hash,
    }
    signature = hashlib.sha256(json.dumps(
        canonical, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")).hexdigest()
    return {**canonical, "signature": signature}


def recipe_from_scoped(final_params: Any, scoped_params: Any,
                       sdc_sha256: Any) -> Optional[Dict[str, Any]]:
    scoped = canonical_scoped_params(scoped_params)
    if scoped is None:
        return None
    context = {
        logical: scoped[target]
        for logical, target in FLOORPLAN_CONTEXT_NAMES.items()
    }
    return build_recipe(final_params, context, sdc_sha256)


def validate_recipe(value: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(value, Mapping) or value.get("schema_version") != SCHEMA_VERSION:
        return None
    rebuilt = recipe_from_scoped(
        value.get("final_params"), value.get("scoped_params"),
        value.get("sdc_sha256"))
    if rebuilt is None or str(value.get("signature")) != rebuilt["signature"]:
        return None
    if value.get("floorplan_routing_context") != rebuilt["floorplan_routing_context"]:
        return None
    return rebuilt


def routing_parent_family(
    params: Any,
    floorplan_context: Any = None,
    sdc_sha256: Any = None,
    *,
    decimals: int = 6,
) -> Optional[str]:
    """Identify the complete physical parent basin seen by final routing."""
    if not isinstance(params, Mapping):
        return None
    upstream = {}
    ignored = {"PIN_LAYER_ADJUST", "ABOVE_LAYER_ADJUST", *SCOPED_PARAM_NAMES}
    for name, raw in params.items():
        if str(name) in ignored:
            continue
        number = _finite_number(raw)
        if number is not None:
            upstream[str(name)] = round(number, decimals)
    if not upstream:
        return None
    source = floorplan_context if isinstance(floorplan_context, Mapping) else params
    floorplan = {}
    for logical, scoped in FLOORPLAN_CONTEXT_NAMES.items():
        raw = source.get(logical, source.get(scoped))
        number = _finite_number(raw)
        if number is None:
            return None
        floorplan[logical] = round(number, decimals)
    payload = {
        "upstream_params": upstream,
        "floorplan_routing_context": floorplan,
        "sdc_sha256": str(sdc_sha256 or ""),
    }
    return hashlib.sha256(json.dumps(
        payload, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")).hexdigest()[:16]
