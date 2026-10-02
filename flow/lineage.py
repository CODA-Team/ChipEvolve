"""Lineage and provenance helpers for DRP checkpoint clones.

The DRP slot id is not the identity of the physical run after a clone.  This module
captures the effective config and checkpoint that actually produced the downstream
result, then persists the stage records atomically for later history construction.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, MutableMapping, Optional

from config_recipe import canonical_sdc_sha256


CONFIG_PARAM_NAMES = (
    "SYNTH_FLATTEN",
    "CORE_UTILIZATION",
    "CELL_PAD_IN_SITES_GLOBAL_PLACEMENT",
    "CELL_PAD_IN_SITES_DETAIL_PLACEMENT",
    "ENABLE_DPO",
    "PLACE_DENSITY_LB_ADDON",
    "TNS_END_PERCENT",
    "FLOORPLAN_PIN_LAYER_ADJUST",
    "FLOORPLAN_ABOVE_LAYER_ADJUST",
    "CTS_CLUSTER_SIZE",
    "CTS_CLUSTER_DIAMETER",
    "PIN_LAYER_ADJUST",
    "ABOVE_LAYER_ADJUST",
)

STAGE_PARAM_NAMES = {
    "cts": ("CTS_CLUSTER_SIZE", "CTS_CLUSTER_DIAMETER"),
    "routing": ("PIN_LAYER_ADJUST", "ABOVE_LAYER_ADJUST"),
}

ROUTING_CONTEXT_NAMES = ("PIN_LAYER_ADJUST", "ABOVE_LAYER_ADJUST")
FLOORPLAN_ROUTING_NAMES = {
    "PIN_LAYER_ADJUST": "FLOORPLAN_PIN_LAYER_ADJUST",
    "ABOVE_LAYER_ADJUST": "FLOORPLAN_ABOVE_LAYER_ADJUST",
}

CHECKPOINT_FILES = {
    "place": "3_place.odb",
    "cts": "4_cts.odb",
}


def utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def file_sha256(path: Path, cache: Optional[MutableMapping] = None) -> str:
    """Hash a file, caching by path/size/mtime for repeated GWTW clone sources."""
    path = Path(path)
    stat = path.stat()
    key = (str(path.resolve()), stat.st_size, stat.st_mtime_ns)
    if cache is not None and key in cache:
        return cache[key]
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    value = digest.hexdigest()
    if cache is not None:
        cache[key] = value
    return value


def checkpoint_snapshot(path: Path, cache: Optional[MutableMapping] = None) -> Dict[str, Any]:
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"checkpoint file not found: {path}")
    stat = path.stat()
    sha256 = file_sha256(path, cache)
    return {
        "path": str(path),
        "name": path.name,
        "size_bytes": stat.st_size,
        "sha256": sha256,
        "identity": f"{path.name}:{sha256}",
    }


def _numeric_assignments(content: str, name: str) -> list[str]:
    pattern = rf"^\s*(?:export\s+)?{re.escape(name)}\s*=\s*([\d.eE+\-]+)"
    return re.findall(pattern, content, flags=re.MULTILINE)


def _resolve_sdc(config_path: Path, raw: str) -> Optional[Path]:
    raw = raw.strip().strip("'\"")
    literal = Path(raw).expanduser()
    # A backed-up config contains an obsolete absolute live path.  Its SDC is copied
    # beside the config under the same basename.  Prefer that immutable sibling:
    # run ids are reused every iteration, so the live absolute path may now name a
    # different iteration's SDC even though it still exists.
    archived_sibling = config_path.parent / literal.name
    candidates = [archived_sibling]
    if literal.is_absolute():
        candidates.append(literal)
    else:
        relative = config_path.parent / literal
        if relative != archived_sibling:
            candidates.append(relative)
    for candidate in candidates:
        try:
            if candidate.is_file():
                return candidate
        except OSError:
            continue
    return None


def _routing_context_from_config(content: str,
                                 params: Mapping[str, float]) -> Dict[str, Any]:
    """Return the routing adjustments that were consumed at floorplan.

    Older configs used PIN/ABOVE for both floorplan and final routing. Treating those
    values as an explicit fallback preserves their historical meaning while new configs
    can carry an independent floorplan context.
    """
    explicit: Dict[str, float] = {}
    for logical_name, config_name in FLOORPLAN_ROUTING_NAMES.items():
        values = _numeric_assignments(content, config_name)
        if values:
            explicit[logical_name] = float(values[-1])

    if len(explicit) == len(FLOORPLAN_ROUTING_NAMES):
        return {**explicit, "source": "explicit_floorplan"}
    fallback = {
        name: float(params[name])
        for name in ROUTING_CONTEXT_NAMES
        if name in params
    }
    return {**fallback, "source": "fallback_final"}


def _snapshot_routing_context(snapshot: Mapping[str, Any]) -> Dict[str, Any]:
    """Normalize an embedded context, with a fallback for schema-v1 snapshots."""
    context = snapshot.get("routing_context")
    if isinstance(context, Mapping):
        normalized: Dict[str, Any] = {}
        for name in ROUTING_CONTEXT_NAMES:
            try:
                normalized[name] = float(context[name])
            except (KeyError, TypeError, ValueError):
                break
        else:
            source = str(context.get("source") or "fallback_final")
            normalized["source"] = source
            return normalized

    params = snapshot.get("params") or {}
    fallback = {}
    for name in ROUTING_CONTEXT_NAMES:
        try:
            fallback[name] = float(params[name])
        except (KeyError, TypeError, ValueError):
            return {"source": "fallback_final"}
    fallback["source"] = "fallback_final"
    return fallback


def _routing_contexts_match(left: Mapping[str, Any],
                            right: Mapping[str, Any],
                            tolerance: float = 1.0e-4) -> bool:
    if left.get("source") != right.get("source"):
        return False
    for name in ROUTING_CONTEXT_NAMES:
        try:
            if abs(float(left[name]) - float(right[name])) > tolerance:
                return False
        except (KeyError, TypeError, ValueError):
            return False
    return True


def config_snapshot(config_path: Path, cache: Optional[MutableMapping] = None) -> Dict[str, Any]:
    """Read the tunable effective config plus the SDC/clock it resolves to."""
    config_path = Path(config_path)
    if not config_path.is_file():
        raise FileNotFoundError(f"config file not found: {config_path}")
    content = config_path.read_text(encoding="utf-8")
    params: Dict[str, float] = {}
    for name in CONFIG_PARAM_NAMES:
        values = _numeric_assignments(content, name)
        if values:
            params[name] = float(values[-1])

    routing_context = _routing_context_from_config(content, params)
    for logical_name, scoped_name in FLOORPLAN_ROUTING_NAMES.items():
        if scoped_name not in params and logical_name in routing_context:
            params[scoped_name] = float(routing_context[logical_name])

    sdc_values = re.findall(
        r"^\s*(?:export\s+)?SDC_FILE\s*=\s*(\S+)", content, flags=re.MULTILINE)
    configured_sdc = sdc_values[-1].strip("'\"") if sdc_values else None
    resolved_sdc = _resolve_sdc(config_path, configured_sdc) if configured_sdc else None
    sdc_info: Dict[str, Any] = {
        "configured_path": configured_sdc,
        "resolved_path": str(resolved_sdc) if resolved_sdc else None,
        "sha256": None,
        "recipe_sha256": None,
        "clk_period": None,
    }
    if resolved_sdc is not None:
        sdc_content = resolved_sdc.read_text(encoding="utf-8")
        matches = re.findall(
            r"set\s+clk_period\s+([\d.eE+\-]+)", sdc_content)
        if matches:
            params["clk_period"] = float(matches[-1])
            sdc_info["clk_period"] = params["clk_period"]
        sdc_info["sha256"] = file_sha256(resolved_sdc, cache)
        try:
            sdc_info["recipe_sha256"] = canonical_sdc_sha256(resolved_sdc)
        except ValueError:
            # Some non-optimization SDCs do not expose exactly one clk_period.
            # Their lineage snapshot remains useful, but no static replay recipe is
            # issued until the clock contract is unambiguous.
            pass

    return {
        "config_path": str(config_path),
        "config_sha256": file_sha256(config_path, cache),
        "params": params,
        "routing_context": routing_context,
        "effective_sdc": sdc_info,
    }


def expected_effective_params(source_params: Mapping[str, float],
                              generated_params: Mapping[str, float]) -> Dict[str, float]:
    merged = dict(source_params)
    for key, value in generated_params.items():
        try:
            merged[key] = float(value)
        except (TypeError, ValueError):
            merged[key] = value
    return merged


def params_match(expected: Mapping[str, float], actual: Mapping[str, float],
                 tolerance: float = 1.0e-4) -> bool:
    for name, expected_value in expected.items():
        if name not in actual:
            return False
        try:
            if abs(float(expected_value) - float(actual[name])) > tolerance:
                return False
        except (TypeError, ValueError):
            return False
    return True


def evaluate_trust(event: Dict[str, Any]) -> Dict[str, Any]:
    """Set trusted/reasons after all clone and optional mutation operations."""
    reasons = []
    status = event.get("status", {})
    if status.get("checkpoint_copy") != "ok":
        reasons.append("checkpoint_copy_not_ok")
    if status.get("config_copy") != "ok":
        reasons.append("config_copy_not_ok")

    source = event.get("source_config") or {}
    target = event.get("target_config") or {}
    source_params = source.get("params") or {}
    target_params = target.get("params") or {}
    source_routing_context = _snapshot_routing_context(source)
    target_routing_context = _snapshot_routing_context(target)
    missing = [name for name in (*CONFIG_PARAM_NAMES, "clk_period")
               if name not in source_params or name not in target_params]
    if missing:
        reasons.append("incomplete_effective_params:" + ",".join(missing))

    source_sdc = source.get("effective_sdc") or {}
    target_sdc = target.get("effective_sdc") or {}
    if not source_sdc.get("sha256") or source_sdc.get("clk_period") is None:
        reasons.append("source_sdc_or_clock_missing")
    if not target_sdc.get("sha256") or target_sdc.get("clk_period") is None:
        reasons.append("target_sdc_or_clock_missing")

    checkpoint = event.get("checkpoint") or {}
    if not checkpoint.get("sha256") or not checkpoint.get("identity"):
        reasons.append("checkpoint_identity_missing")

    mutation_expected = bool(event.get("mutation_expected", True))
    generated = event.get("generated_params")
    preserved = event.get("preserved_params") or {}
    if mutation_expected:
        if status.get("params_apply") != "ok":
            reasons.append("params_apply_not_ok")
        if not event.get("generated_param_count_matches", False):
            reasons.append("generated_param_count_mismatch")
        required = STAGE_PARAM_NAMES.get(event.get("next_stage"), ())
        if not isinstance(generated, dict):
            reasons.append("generated_params_missing")
            generated = {}
        else:
            absent = [name for name in required if name not in generated]
            if absent:
                reasons.append("generated_stage_params_missing:" + ",".join(absent))
            unexpected = [name for name in generated if name not in required]
            if unexpected:
                reasons.append("unexpected_generated_params:" + ",".join(unexpected))
        if not event.get("mutation_applied", False):
            reasons.append("expected_mutation_not_applied")
    else:
        if status.get("params_apply") != "not_required":
            reasons.append("frozen_clone_apply_status_invalid")
        if event.get("mutation_applied", False):
            reasons.append("unexpected_mutation_applied")
        generated = {}
        if event.get("stage") == "place":
            absent = [name for name in STAGE_PARAM_NAMES["routing"]
                      if name not in preserved]
            if absent:
                reasons.append("frozen_clone_routing_params_missing:" + ",".join(absent))
            if status.get("preserved_params_apply") != "ok":
                reasons.append("preserved_params_apply_not_ok")

    expected = expected_effective_params(source_params, generated or {})
    expected = expected_effective_params(expected, preserved)
    if not params_match(expected, target_params):
        reasons.append("target_effective_params_mismatch")
    if source_sdc.get("sha256") != target_sdc.get("sha256"):
        reasons.append("effective_sdc_mismatch")
    if not _routing_contexts_match(source_routing_context, target_routing_context):
        reasons.append("routing_context_mismatch")

    event["source_effective_params"] = source_params
    event["target_effective_params"] = target_params
    # Canonical consumer-facing alias. ``target_effective_params`` is retained for
    # schema clarity/backward compatibility; history and replay code use this name.
    event["effective_params"] = target_params
    event["source_effective_clock"] = source_params.get("clk_period")
    event["effective_clock"] = target_params.get("clk_period")
    event["preserved_params"] = preserved
    event["effective_sdc"] = target_sdc
    event["source_routing_context"] = source_routing_context
    event["effective_routing_context"] = target_routing_context
    event["config_sha256"] = target.get("config_sha256")
    event["trusted"] = not reasons
    event["trust_reasons"] = reasons
    event["updated_utc"] = utc_now()
    return event


def campaign_id(work_dir: Path, platform: str, design: str) -> Optional[str]:
    manifest = Path(work_dir) / "backup_dir" / platform / design / "campaign_manifest.json"
    try:
        value = json.loads(manifest.read_text(encoding="utf-8")).get("campaign_id")
        return str(value) if value else None
    except (OSError, json.JSONDecodeError, TypeError):
        return None


def atomic_write_json(path: Path, payload: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    try:
        with temp.open("w", encoding="utf-8") as stream:
            json.dump(payload, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        try:
            temp.unlink()
        except FileNotFoundError:
            pass


def write_stage_summary(work_dir: Path, platform: str, design: str,
                        iteration: int, stage: str,
                        events: Iterable[Dict[str, Any]]) -> Path:
    """Atomically replace one stage while preserving the other stage's events."""
    work_dir = Path(work_dir)
    output = work_dir / "tmp" / f"lineage_iter{iteration}.json"
    cid = campaign_id(work_dir, platform, design)
    payload: Dict[str, Any] = {}
    if output.is_file():
        try:
            candidate = json.loads(output.read_text(encoding="utf-8"))
            same_campaign = (candidate.get("campaign_id") == cid if cid is not None
                             else candidate.get("campaign_id") is None)
            if (same_campaign and candidate.get("iteration") == iteration
                    and candidate.get("platform") == platform
                    and candidate.get("design") == design):
                payload = candidate
        except (OSError, json.JSONDecodeError, TypeError):
            payload = {}

    payload.update({
        "schema_version": 1,
        "campaign_id": cid,
        "platform": platform,
        "design": design,
        "iteration": iteration,
        "updated_utc": utc_now(),
    })
    stages = payload.setdefault("stages", {})
    stages[stage] = list(events)
    atomic_write_json(output, payload)
    return output
