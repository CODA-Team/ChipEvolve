"""Build bounded, JSON-safe evidence for the DRP LLM prompts.

The optimizer has several history views with deliberately different provenance.
This module keeps those views separate while deriving one shared objective contract,
outcome classifications, parameter-space coverage, and clone-edge context.  It has
no dependency on NumPy or the optimizer modules so it can also be used by focused
unit tests and stage-level agents.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


_OUTCOMES = ("feasible", "power_infeasible", "flow_failed")
_CP0_SOURCES = {"cp0", "cp0_eval", "shared_cp0"}
_DEFAULT_HISTORICAL_EDGE_LIMIT = 24


def _finite(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _json_safe(value: Any) -> Any:
    """Recursively remove non-JSON numeric values and stringify opaque objects."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    number = _finite(value)
    return number if number is not None else str(value)


def _confidence_observation(
    value: Any, source: str, *, definition: str,
    calibrated_probability: bool = False,
    **extra: Any,
) -> Optional[Dict[str, Any]]:
    number = _finite(value)
    if number is None:
        return None
    return {
        "value": min(1.0, max(0.0, number)),
        "source": str(source),
        "definition": definition,
        "calibrated_probability": bool(calibrated_probability),
        **{key: _json_safe(item) for key, item in extra.items()},
    }


def load_model_score_evidence(
    backup_dir: Any,
    platform: str,
    design: str,
    max_iters: int,
) -> List[Dict[str, Any]]:
    """Load model evidence only when it can be tied to the final candidate identity.

    Agent2 scores candidate-pool entities before execution, while DRP may later replace
    a run slot with a different child.  Joining by run id alone would therefore assign
    a parent's confidence to its child.  The finalized candidate lifecycle supplies the
    immutable identity needed to fail closed. Every finalized slot contributes its
    identity/config mapping; model observations are attached only when the scored
    candidate id is still the final candidate in that run slot.

    GPR standard deviation is converted to a bounded *relative confidence signal* via
    ``1 / (1 + std)``.  It is explicitly marked as non-calibrated.  Transformer
    ``promising_score`` values are retained directly, also without claiming calibration.
    Missing or legacy lifecycle artifacts simply produce no evidence.
    """
    root = Path(backup_dir) / str(platform) / str(design)
    try:
        iteration_limit = max(0, int(max_iters))
    except (TypeError, ValueError):
        iteration_limit = 0
    output: List[Dict[str, Any]] = []

    for iteration in range(1, iteration_limit + 1):
        iter_dir = root / f"result_dump_{iteration}"
        lifecycle_path = iter_dir / f"candidate_lifecycle_iter{iteration}.json"
        try:
            lifecycle = json.loads(lifecycle_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError):
            continue
        if not isinstance(lifecycle, Mapping):
            continue

        observations: Dict[str, List[Dict[str, Any]]] = {}
        for event in lifecycle.get("events", ()):
            if not isinstance(event, Mapping) or event.get("stage") != "agent2_selected":
                continue
            candidate_id = str(event.get("candidate_id") or "").strip()
            details = event.get("details")
            if not candidate_id or not isinstance(details, Mapping):
                continue
            uncertainty = _finite(details.get("uncertainty"))
            if uncertainty is None or uncertainty < 0.0:
                continue
            observation = _confidence_observation(
                1.0 / (1.0 + uncertainty),
                "agent2_gpr_uncertainty",
                definition="1 / (1 + predictive_std); relative, not calibrated",
                predictive_std=uncertainty,
                predicted_objective=details.get("predicted_objective"),
                acquisition=details.get("acquisition"),
                selection_rank=details.get("selection_rank"),
            )
            if observation is not None:
                observations.setdefault(candidate_id, []).append(observation)

        # Predictor scores are attached only through explicit candidate edges.  This
        # covers clone sources without guessing the identity of every run at the stage.
        for stage in ("place", "cts"):
            drp_path = iter_dir / f"drp_{stage}_iter{iteration}.json"
            try:
                drp_payload = json.loads(drp_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError, TypeError):
                continue
            if not isinstance(drp_payload, Mapping):
                continue
            source_ids: Dict[str, str] = {}
            for edge in drp_payload.get("candidate_edges", ()):
                if not isinstance(edge, Mapping):
                    continue
                run_id = edge.get("source_run_id")
                candidate_id = str(edge.get("source_candidate_id") or "").strip()
                if run_id is not None and candidate_id:
                    source_ids[str(run_id)] = candidate_id
            scores = drp_payload.get("predictor_scores")
            if not isinstance(scores, Mapping):
                continue
            for run_id, raw_score in scores.items():
                candidate_id = source_ids.get(str(run_id))
                if not candidate_id or not isinstance(raw_score, Mapping):
                    continue
                promising = _finite(raw_score.get("promising_score"))
                if promising is None:
                    continue
                observation = _confidence_observation(
                    promising,
                    f"drp_{stage}_transformer_promising_score",
                    definition=(
                        "transformer promising_score for the unchanged clone source; "
                        "not asserted to be calibrated"
                    ),
                    rank_mode=drp_payload.get("rank_mode"),
                    model_sha256=drp_payload.get("model_sha256"),
                    predictor_stage=stage,
                )
                if observation is not None:
                    observations.setdefault(candidate_id, []).append(observation)

        for slot in lifecycle.get("slots", ()):
            if not isinstance(slot, Mapping):
                continue
            candidate_id = str(slot.get("candidate_id") or "").strip()
            candidate_observations = observations.get(candidate_id, [])
            final = slot.get("final")
            if not candidate_id or not isinstance(final, Mapping):
                continue
            params = final.get("effective_params")
            if not isinstance(params, Mapping):
                params = slot.get("current_params")
            output.append({
                "iteration": iteration,
                "run_id": slot.get("run_id"),
                "candidate_id": candidate_id,
                "params": dict(params) if isinstance(params, Mapping) else {},
                "model_confidence_observations": candidate_observations,
            })
    return _json_safe(output)


def _metrics(record: Mapping[str, Any]) -> Mapping[str, Any]:
    nested = record.get("metrics")
    return nested if isinstance(nested, Mapping) else record


def _lookup(record: Mapping[str, Any], *keys: str) -> Any:
    metrics = _metrics(record)
    for key in keys:
        if key in metrics and metrics.get(key) is not None:
            return metrics.get(key)
        if metrics is not record and record.get(key) is not None:
            return record.get(key)
    return None


def _params(record: Mapping[str, Any], names: Sequence[str] = ()) -> Dict[str, float]:
    for key in ("effective_params", "params", "target_effective_params"):
        raw = record.get(key)
        if isinstance(raw, Mapping):
            break
    else:
        raw = record
    allowed = set(names)
    result = {}
    for key, value in raw.items():
        if allowed and key not in allowed:
            continue
        number = _finite(value)
        if number is not None:
            result[str(key)] = number
    return result


def _flatten_constraints(constraints: Optional[Mapping[str, Any]]) -> Dict[str, Tuple[float, float]]:
    """Accept either one flat constraint map or the configured stage hierarchy."""
    result: Dict[str, Tuple[float, float]] = {}

    def visit(node: Any, name: Optional[str] = None) -> None:
        if isinstance(node, Mapping):
            raw_range = node.get("range")
            if name is not None and isinstance(raw_range, Sequence) and not isinstance(
                    raw_range, (str, bytes)) and len(raw_range) >= 2:
                low, high = _finite(raw_range[0]), _finite(raw_range[1])
                if low is not None and high is not None:
                    result[name] = (min(low, high), max(low, high))
                    return
            for child_name, child in node.items():
                if child_name in {"type", "description"}:
                    continue
                visit(child, str(child_name))
            return
        if name is not None and isinstance(node, Sequence) and not isinstance(
                node, (str, bytes)) and len(node) >= 2:
            low, high = _finite(node[0]), _finite(node[1])
            if low is not None and high is not None:
                result[name] = (min(low, high), max(low, high))

    visit(constraints or {})
    return result


def _record_stage(record: Mapping[str, Any], fallback: str = "clean") -> str:
    stage_record = record.get("stage_record")
    stage = record.get("stage", record.get("lineage_kind"))
    if stage is None and isinstance(stage_record, Mapping):
        stage = stage_record.get("stage")
    text = str(stage or fallback).strip().lower()
    return "clean" if text in {"", "none", "clean_replay"} else text


def _run_id(record: Mapping[str, Any]) -> Any:
    return record.get("run_id", record.get("target_run_id"))


def _iteration(record: Mapping[str, Any]) -> int:
    try:
        return max(0, int(record.get("iteration", 0)))
    except (TypeError, ValueError):
        return 0


def _lineage_identity(record: Mapping[str, Any], *keys: str) -> Any:
    """Read candidate identity from resolved rows and legacy nested lineage events."""
    containers: List[Mapping[str, Any]] = [record]
    stage_record = record.get("stage_record")
    if isinstance(stage_record, Mapping):
        containers.append(stage_record)
        lineage_event = stage_record.get("lineage_event")
        if isinstance(lineage_event, Mapping):
            containers.append(lineage_event)
    lineage_event = record.get("lineage_event")
    if isinstance(lineage_event, Mapping):
        containers.append(lineage_event)
    for container in containers:
        for key in keys:
            value = container.get(key)
            if value not in (None, ""):
                return value
    return None


def _record_identity(record: Mapping[str, Any]) -> Dict[str, Any]:
    candidate_id = _lineage_identity(
        record, "candidate_id", "target_candidate_id")
    return {
        "iteration": _iteration(record),
        "run_id": _run_id(record),
        "stage": _record_stage(record),
        "candidate_id": candidate_id,
        "source_candidate_id": _lineage_identity(record, "source_candidate_id"),
        "target_candidate_id": _lineage_identity(
            record, "target_candidate_id", "candidate_id"),
        "replaced_target_candidate_id": _lineage_identity(
            record, "replaced_target_candidate_id", "replaced_candidate_id"),
    }


def _attach_candidate_model_evidence(
    records: Sequence[Mapping[str, Any]],
    score_records: Sequence[Mapping[str, Any]],
    names: Sequence[str],
) -> List[Dict[str, Any]]:
    """Join lifecycle identity/model evidence only after exact config matching.

    The iteration/run pair narrows the lookup, but it is never sufficient by itself:
    a DRP clone changes the candidate occupying a run slot.  Requiring the archived
    final effective configuration to match prevents a pre-clone score from being
    attributed to the clone child.
    """
    by_run: Dict[Tuple[int, str], List[Mapping[str, Any]]] = {}
    for evidence in score_records or ():
        if not isinstance(evidence, Mapping):
            continue
        run_id = _run_id(evidence)
        if run_id is None:
            continue
        by_run.setdefault((_iteration(evidence), str(run_id)), []).append(evidence)

    joined: List[Dict[str, Any]] = []
    for raw in records or ():
        record = dict(raw)
        run_id = _run_id(record)
        candidates = by_run.get((_iteration(record), str(run_id)), []) \
            if run_id is not None else []
        record_params = _complete_params(record, names)
        matched: List[Mapping[str, Any]] = []
        for evidence in candidates:
            evidence_params = _complete_params(evidence, names)
            if record_params is None or evidence_params is None:
                continue
            if _signature(record_params, names) == _signature(evidence_params, names):
                matched.append(evidence)
        # One finalized lifecycle has one slot per run. Multiple exact matches indicate
        # conflicting artifacts, so fail closed instead of choosing one arbitrarily.
        if len(matched) == 1:
            evidence = matched[0]
            candidate_id = str(evidence.get("candidate_id") or "").strip()
            existing_id = _lineage_identity(
                record, "candidate_id", "target_candidate_id")
            if not existing_id or str(existing_id) == candidate_id:
                if candidate_id:
                    record["candidate_id"] = candidate_id
                    record.setdefault("target_candidate_id", candidate_id)
                observations = evidence.get("model_confidence_observations")
                if isinstance(observations, list) and observations:
                    record["model_confidence_observations"] = list(observations)
        joined.append(record)
    return joined


def _canonical_records(
    history: Sequence[Mapping[str, Any]],
    resolved_history: Sequence[Mapping[str, Any]],
    routing_history: Sequence[Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    """Merge overlapping clean/resolved/routing views without double counting."""
    merged: Dict[Tuple[Any, ...], Dict[str, Any]] = {}
    serial = 0
    for records, fallback in (
        (history, "clean"),
        (resolved_history, "observed"),
        (routing_history, "routing"),
    ):
        for raw in records or ():
            if not isinstance(raw, Mapping):
                continue
            record = dict(raw)
            stage = _record_stage(record, fallback)
            # Resolved history repeats clean history; treat it as the same execution.
            if stage == "observed" and record.get("lineage_kind") in (None, "clean"):
                stage = "clean"
            run_id = _run_id(record)
            if run_id is None:
                key = ("anonymous", serial)
                serial += 1
            else:
                key = (_iteration(record), run_id, stage)
            record["_evidence_view"] = fallback
            record["_evidence_stage"] = stage
            if key in merged:
                previous = merged[key]
                # Later lineage views tend to contain effective configs and recipes.
                previous.update({key_: value for key_, value in record.items()
                                 if value is not None})
            else:
                merged[key] = record
    return list(merged.values())


def _objective_value(record: Mapping[str, Any], objective: str) -> Optional[float]:
    if objective == "TNS_EVAL":
        value = _finite(_lookup(record, "tns", "TNS_EVAL", "setup_tns_ns"))
        return abs(value) if value is not None else None
    if objective == "wl":
        return _finite(_lookup(record, "wl"))
    if objective == "ecp":
        return _finite(_lookup(record, "ecp"))
    explicit = _finite(record.get("objective_value", record.get("objective")))
    return explicit if explicit is not None else _finite(_lookup(record, "combo"))


def _tns_at_shared_cp0(record: Mapping[str, Any], cp0: Any) -> Tuple[bool, str]:
    source = _lookup(record, "tns_source")
    if source is not None:
        normalized = str(source).strip().lower()
        if normalized not in _CP0_SOURCES:
            return False, f"tns_source_{normalized or 'missing'}"
    expected = _finite(cp0)
    actual = _finite(_lookup(
        record, "eval_cp0", "evaluation_cp0", "CP_0", "cp0"))
    if expected is not None and actual is not None and not math.isclose(
            expected, actual, rel_tol=0.0, abs_tol=1.0e-9):
        return False, "cp0_mismatch"
    if source is None and actual is None and record.get("shared_cp0") is not True:
        return False, "cp0_provenance_missing"
    return True, "cp0_verified" if source is not None or actual is not None else "shared_cp0_flag"


def _flow_failure_flag(record: Mapping[str, Any]) -> Optional[str]:
    metrics = _metrics(record)
    if record.get("flow_failed") is True or metrics.get("flow_failed") is True:
        return "explicit_flow_failed"
    if record.get("completed") is False or metrics.get("completed") is False:
        return "flow_not_completed"
    explicit = _lookup(record, "classification", "outcome_class")
    if str(explicit).strip().lower() == "flow_failed":
        return "explicit_flow_failed"
    status = str(_lookup(record, "flow_status", "status") or "").strip().lower()
    if status in {"failed", "failure", "error", "timeout", "killed"}:
        return f"flow_status_{status}"
    return None


def _classify_record(
    record: Mapping[str, Any],
    objective: str,
    power_limit: Optional[float],
    cp0: Any,
) -> Tuple[str, Dict[str, Any]]:
    value = _objective_value(record, objective)
    power = _finite(_lookup(record, "power", "power_total_w"))
    reason = _flow_failure_flag(record)
    if reason is None and value is None:
        reason = "missing_objective_metric"
    if reason is None and objective == "TNS_EVAL":
        comparable, cp0_reason = _tns_at_shared_cp0(record, cp0)
        if not comparable:
            reason = cp0_reason

    if reason is not None:
        classification = "flow_failed"
    elif objective == "TNS_EVAL" and power_limit is not None and power is None:
        classification, reason = "power_infeasible", "missing_cp0_power"
    elif objective == "TNS_EVAL" and power_limit is not None and power > power_limit:
        classification, reason = "power_infeasible", "power_above_limit"
    else:
        classification, reason = "feasible", "objective_contract_satisfied"

    signed_tns = _finite(_lookup(record, "tns", "setup_tns_ns"))
    detail = {
        **_record_identity(record),
        "classification": classification,
        "reason": reason,
        "objective_value": value,
        "tns_at_cp0": signed_tns,
        "abs_tns_at_cp0": abs(signed_tns) if signed_tns is not None else (
            value if objective == "TNS_EVAL" else None),
        "power": power,
        "power_margin": (
            power_limit - power
            if power_limit is not None and power is not None else None
        ),
    }
    return classification, detail


def _classify_records(
    records: Sequence[Mapping[str, Any]],
    objective: str,
    power_limit: Optional[float],
    cp0: Any,
) -> List[Tuple[Mapping[str, Any], str, Dict[str, Any]]]:
    return [
        (record, *_classify_record(record, objective, power_limit, cp0))
        for record in records
    ]


def _signature(params: Mapping[str, Any], names: Sequence[str]) -> str:
    payload = [(name, _finite(params.get(name))) for name in names]
    return hashlib.sha256(
        json.dumps(payload, separators=(",", ":"), sort_keys=False).encode("utf-8")
    ).hexdigest()


def _complete_params(record: Mapping[str, Any], names: Sequence[str]) -> Optional[Dict[str, float]]:
    params = _params(record, names)
    if names and any(name not in params for name in names):
        return None
    return params or None


def _result_record(
    record: Mapping[str, Any], detail: Mapping[str, Any], names: Sequence[str]
) -> Dict[str, Any]:
    params = _params(record, names)
    return {
        **_record_identity(record),
        "source_view": record.get("_evidence_view", _record_stage(record)),
        "parent_family": record.get("parent_family", record.get("upstream_family")),
        "objective_value": detail.get("objective_value"),
        "tns_at_cp0": detail.get("tns_at_cp0"),
        "abs_tns_at_cp0": detail.get("abs_tns_at_cp0"),
        "power": detail.get("power"),
        "power_margin": detail.get("power_margin"),
        "params": params,
    }


def _top_successful(
    classified: Sequence[Tuple[Mapping[str, Any], str, Dict[str, Any]]],
    names: Sequence[str],
    top_k: int,
) -> List[Dict[str, Any]]:
    grouped: Dict[str, Dict[str, Any]] = {}
    for record, classification, detail in classified:
        params = _complete_params(record, names)
        value = detail.get("objective_value")
        if classification != "feasible" or params is None or value is None:
            continue
        signature = _signature(params, names or sorted(params))
        item = _result_record(record, detail, names)
        item["config_signature"] = signature
        existing = grouped.get(signature)
        if existing is None:
            item["observation_count"] = 1
            item["observed_sources"] = [item["source_view"]]
            grouped[signature] = item
        else:
            existing["observation_count"] += 1
            sources = set(existing["observed_sources"])
            sources.add(item["source_view"])
            existing["observed_sources"] = sorted(sources)
            if float(value) < float(existing["objective_value"]):
                count, sources = existing["observation_count"], existing["observed_sources"]
                grouped[signature] = item
                grouped[signature]["observation_count"] = count
                grouped[signature]["observed_sources"] = sources
    ranked = sorted(grouped.values(), key=lambda item: (
        float(item["objective_value"]), item.get("iteration", 0),
        str(item.get("run_id"))))
    result = []
    for rank, item in enumerate(ranked[:max(0, int(top_k))], 1):
        result.append(dict(item, rank=rank, complete_parameter_count=len(item["params"])))
    return result


def _best_from_records(
    records: Sequence[Mapping[str, Any]],
    objective: str,
    power_limit: Optional[float],
    cp0: Any,
    names: Sequence[str],
) -> Optional[Dict[str, Any]]:
    ranked = []
    for record, classification, detail in _classify_records(
            records, objective, power_limit, cp0):
        if classification == "feasible" and detail.get("objective_value") is not None:
            ranked.append((float(detail["objective_value"]), record, detail))
    if not ranked:
        return None
    _, record, detail = min(ranked, key=lambda item: (
        item[0], _iteration(item[1]), str(_run_id(item[1]))))
    return _result_record(record, detail, names)


def _state_best(
    state_record: Any,
    records: Sequence[Mapping[str, Any]],
    objective: str,
    power_limit: Optional[float],
    cp0: Any,
    names: Sequence[str],
) -> Optional[Dict[str, Any]]:
    if not isinstance(state_record, Mapping):
        return None
    iteration, run_id = _iteration(state_record), _run_id(state_record)
    matches = [record for record in records
               if _iteration(record) == iteration and _run_id(record) == run_id]
    enriched = _best_from_records(matches, objective, power_limit, cp0, names)
    base = _json_safe(state_record)
    if enriched is not None:
        base.update(enriched)
    elif "objective" in base and "objective_value" not in base:
        base["objective_value"] = base.get("objective")
    base["persistence_status"] = "persisted_in_optimization_state"
    return base


def _stratified_bests(
    objective: str,
    history: Sequence[Mapping[str, Any]],
    resolved_history: Sequence[Mapping[str, Any]],
    routing_history: Sequence[Mapping[str, Any]],
    state: Mapping[str, Any],
    power_limit: Optional[float],
    cp0: Any,
    names: Sequence[str],
) -> Dict[str, Any]:
    views = {
        "clean": (
            "full-flow attributable clean/replay observation",
            history,
            "best_clean_replay",
        ),
        "observed": (
            "trusted lineage-resolved effective observation (may be a DRP child)",
            resolved_history or history,
            "best_observed_effective",
        ),
        "routing": (
            "trusted post-CTS routing-child observation",
            routing_history,
            "best_routing_child",
        ),
        "config_reproducible": (
            "lineage recipe independently reproduced by complete static config runs",
            (),
            "best_config_reproducible",
        ),
    }
    output = {}
    for label, (definition, records, state_key) in views.items():
        persisted = _state_best(
            state.get(state_key), records, objective, power_limit, cp0, names)
        derived = _best_from_records(records, objective, power_limit, cp0, names)
        output[label] = {
            "definition": definition,
            "best": persisted if persisted is not None else derived,
            "source": "optimization_state" if persisted is not None else "derived_history",
        }
    return output


def _normalized_distance(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
    bounds: Mapping[str, Tuple[float, float]],
) -> Tuple[Optional[float], int]:
    squared = []
    for name, (low, high) in bounds.items():
        a, b = _finite(left.get(name)), _finite(right.get(name))
        if a is None or b is None:
            continue
        span = high - low
        delta = abs(a - b) / span if span > 0 else (0.0 if a == b else 1.0)
        squared.append(delta * delta)
    if not squared:
        return None, 0
    return math.sqrt(sum(squared) / len(squared)), len(squared)


def _quantile(values: Sequence[float], fraction: float) -> Optional[float]:
    if not values:
        return None
    ordered = sorted(float(value) for value in values)
    position = (len(ordered) - 1) * fraction
    lower, upper = int(math.floor(position)), int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _numeric_summary(values: Sequence[float]) -> Dict[str, Any]:
    finite = [value for value in (_finite(item) for item in values) if value is not None]
    if not finite:
        return {"count": 0, "min": None, "q25": None, "median": None,
                "mean": None, "q75": None, "max": None}
    return {
        "count": len(finite),
        "min": min(finite),
        "q25": _quantile(finite, 0.25),
        "median": _quantile(finite, 0.5),
        "mean": sum(finite) / len(finite),
        "q75": _quantile(finite, 0.75),
        "max": max(finite),
    }


def annotate_candidate_distances(
    candidates: Sequence[Mapping[str, Any]],
    history: Sequence[Mapping[str, Any]],
    constraints: Mapping[str, Any],
    incumbent: Optional[Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    """Return candidate copies annotated with normalized history/incumbent distance.

    The input objects are never mutated.  Metadata lives under ``_distance_info`` so
    callers can remove it before emitting the fixed 12-column execution CSV.
    """
    bounds = _flatten_constraints(constraints)
    names = list(bounds)
    history_rows = []
    for index, record in enumerate(history or ()):
        if not isinstance(record, Mapping):
            continue
        params = _params(record, names)
        if params:
            history_rows.append((index, record, params))
    incumbent_params = _params(incumbent or {}, names)
    annotated = []
    for candidate in candidates or ():
        copied = dict(candidate)
        params = _params(candidate, names)
        nearest = None
        nearest_record = None
        dimensions = 0
        for index, record, historical_params in history_rows:
            distance, used = _normalized_distance(params, historical_params, bounds)
            if distance is not None and (nearest is None or distance < nearest):
                nearest, dimensions = distance, used
                nearest_record = {"history_index": index, **_record_identity(record)}
        incumbent_distance, incumbent_dimensions = _normalized_distance(
            params, incumbent_params, bounds)
        copied["_distance_info"] = {
            "metric": "rms_euclidean_over_parameter_ranges",
            "distance_to_nearest_history": nearest,
            "nearest_history": nearest_record,
            "distance_to_incumbent": incumbent_distance,
            "normalized_dimensions": max(dimensions, incumbent_dimensions),
            "configured_dimensions": len(bounds),
            "status": "ok" if bounds else "constraints_unavailable",
        }
        annotated.append(_json_safe(copied))
    return annotated


def _distance_context(
    records: Sequence[Mapping[str, Any]],
    classified: Sequence[Tuple[Mapping[str, Any], str, Dict[str, Any]]],
    bounds: Mapping[str, Tuple[float, float]],
) -> Dict[str, Any]:
    names = list(bounds)
    configurations = []
    seen = set()
    for record in records:
        params = _complete_params(record, names)
        if params is None:
            continue
        signature = _signature(params, names)
        if signature not in seen:
            seen.add(signature)
            configurations.append((record, params))
    nearest_distances = []
    if len(configurations) > 1:
        for index, (_, params) in enumerate(configurations):
            distances = [
                distance for other_index, (_, other) in enumerate(configurations)
                if other_index != index
                for distance, _ in [_normalized_distance(params, other, bounds)]
                if distance is not None
            ]
            if distances:
                nearest_distances.append(min(distances))

    feasible = [(record, detail) for record, label, detail in classified
                if label == "feasible" and detail.get("objective_value") is not None]
    incumbent_record = min(feasible, key=lambda item: float(item[1]["objective_value"])) \
        if feasible else None
    incumbent_payload = None
    distances_to_incumbent = []
    if incumbent_record is not None:
        record, detail = incumbent_record
        incumbent_params = _params(record, names)
        incumbent_payload = {
            **_record_identity(record),
            "objective_value": detail.get("objective_value"),
            "params": incumbent_params,
        }
        for _, params in configurations:
            distance, _ = _normalized_distance(params, incumbent_params, bounds)
            if distance is not None:
                distances_to_incumbent.append(distance)
    return {
        "metric": "RMS Euclidean distance after scaling each parameter by its configured range",
        "configured_parameters": names,
        "unique_complete_history_configs": len(configurations),
        "nearest_neighbor_distance_summary": _numeric_summary(nearest_distances),
        "distance_to_incumbent_summary": _numeric_summary(distances_to_incumbent),
        "incumbent": incumbent_payload,
        "candidate_annotation_field": "_distance_info",
        "status": "ok" if bounds else "constraints_unavailable",
    }


def _parameter_distributions(
    classified: Sequence[Tuple[Mapping[str, Any], str, Dict[str, Any]]],
    names: Sequence[str],
) -> Dict[str, Any]:
    chronological = sorted(classified, key=lambda item: (
        _iteration(item[0]), str(_run_id(item[0])), _record_stage(item[0])))
    improving_ids = set()
    running_best = None
    for index, (_, classification, detail) in enumerate(chronological):
        value = detail.get("objective_value")
        if classification == "feasible" and value is not None and (
                running_best is None or float(value) < running_best):
            improving_ids.add(index)
            running_best = float(value)

    groups: Dict[str, List[Mapping[str, Any]]] = {name: [] for name in (
        "feasible", "improving", "flow_failed", "power_infeasible")}
    for index, (record, classification, _) in enumerate(chronological):
        groups[classification].append(record)
        if index in improving_ids:
            groups["improving"].append(record)

    output = {}
    for name in names:
        output[name] = {}
        for group_name, rows in groups.items():
            values = []
            for row in rows:
                value = _params(row, names).get(name)
                if value is not None:
                    values.append(value)
            stats = _numeric_summary(values)
            stats["sample_count"] = len(rows)
            stats["missing_count"] = len(rows) - len(values)
            output[name][group_name] = stats
    return {
        "improving_definition": (
            "feasible observations that establish or strictly improve the running "
            "campaign best in iteration/run order"
        ),
        "group_counts": {name: len(rows) for name, rows in groups.items()},
        "by_parameter": output,
    }


def _model_confidence_observations(record: Mapping[str, Any]) -> List[Dict[str, Any]]:
    observations = record.get("model_confidence_observations")
    result = []
    if isinstance(observations, Sequence) and not isinstance(observations, (str, bytes)):
        for observation in observations:
            if not isinstance(observation, Mapping):
                continue
            value = _finite(observation.get("value"))
            if value is None:
                continue
            result.append({
                **dict(observation),
                "value": min(1.0, max(0.0, value)),
                "source": str(observation.get("source") or "model_confidence"),
            })
    for container in (record, _metrics(record)):
        for key in ("model_confidence", "predictor_confidence", "prediction_confidence"):
            value = _finite(container.get(key))
            if value is not None:
                result.append({
                    "value": min(1.0, max(0.0, value)),
                    "source": key,
                    "definition": "model-reported confidence",
                    "calibrated_probability": False,
                })
    return result


def _basin_summary(
    records: Sequence[Mapping[str, Any]],
    classified: Sequence[Tuple[Mapping[str, Any], str, Dict[str, Any]]],
    bounds: Mapping[str, Tuple[float, float]],
    recent_window: int,
) -> Dict[str, Any]:
    names = list(bounds)
    feasible = []
    seen = set()
    detail_by_id = {id(record): (label, detail)
                    for record, label, detail in classified}
    for record, label, detail in classified:
        params = _complete_params(record, names)
        if label != "feasible" or params is None or detail.get("objective_value") is None:
            continue
        signature = _signature(params, names)
        if signature in seen:
            continue
        seen.add(signature)
        feasible.append((record, params, detail))
    feasible.sort(key=lambda item: (
        float(item[2]["objective_value"]), _iteration(item[0]), str(_run_id(item[0]))))
    if not bounds or not feasible:
        return {
            "status": "insufficient_feasible_configs" if bounds else "constraints_unavailable",
            "distance_metric": "rms_euclidean_over_parameter_ranges",
            "basin_count": 0,
            "basins": [],
        }

    target_count = min(3, len(feasible))
    seeds = [0]
    while len(seeds) < target_count:
        best_index, best_distance = None, -1.0
        for index, (_, params, _) in enumerate(feasible):
            if index in seeds:
                continue
            distances = [
                _normalized_distance(params, feasible[seed][1], bounds)[0]
                for seed in seeds
            ]
            distance = min(value for value in distances if value is not None)
            if distance > best_distance:
                best_index, best_distance = index, distance
        if best_index is None or best_distance <= 1.0e-12:
            break
        seeds.append(best_index)

    assignments: Dict[int, List[Mapping[str, Any]]] = {index: [] for index in range(len(seeds))}
    for record in records:
        params = _complete_params(record, names)
        if params is None:
            continue
        distances = [
            _normalized_distance(params, feasible[seed][1], bounds)[0]
            for seed in seeds
        ]
        finite_distances = [value if value is not None else float("inf") for value in distances]
        assignments[min(range(len(seeds)), key=lambda index: finite_distances[index])].append(record)

    max_iteration = max((_iteration(record) for record in records), default=0)
    cutoff = max(0, max_iteration - max(1, int(recent_window)) + 1)
    basins = []
    for basin_index, seed_index in enumerate(seeds):
        assigned = assignments[basin_index]
        assigned_classified = []
        for record in assigned:
            label_detail = detail_by_id.get(id(record))
            if label_detail is not None:
                assigned_classified.append((record, *label_detail))
        basin_feasible = [item for item in assigned_classified
                          if item[1] == "feasible" and item[2].get("objective_value") is not None]
        best = min(basin_feasible, key=lambda item: float(item[2]["objective_value"]))
        recent_values = [float(detail["objective_value"])
                         for record, _, detail in basin_feasible
                         if _iteration(record) >= cutoff]
        prior_values = [float(detail["objective_value"])
                        for record, _, detail in basin_feasible
                        if _iteration(record) < cutoff]
        recent_best = min(recent_values) if recent_values else None
        prior_best = min(prior_values) if prior_values else None
        improvement = (prior_best - recent_best
                       if prior_best is not None and recent_best is not None else None)
        class_counts = {name: 0 for name in _OUTCOMES}
        model_values, model_sources, model_definitions = [], set(), set()
        model_values_by_source: Dict[str, List[float]] = {}
        model_candidate_ids = set()
        for record, label, _ in assigned_classified:
            class_counts[label] += 1
            observations = _model_confidence_observations(record)
            for observation in observations:
                value = float(observation["value"])
                source = str(observation.get("source") or "model_confidence")
                model_values.append(value)
                model_sources.add(source)
                model_values_by_source.setdefault(source, []).append(value)
                if observation.get("definition"):
                    model_definitions.add(str(observation["definition"]))
                candidate_id = _record_identity(record).get("candidate_id")
                if candidate_id is not None:
                    model_candidate_ids.add(str(candidate_id))
        support = len(basin_feasible)
        feasibility_rate = support / len(assigned_classified) if assigned_classified else 0.0
        empirical = min(1.0, math.sqrt(support / 8.0)) * feasibility_rate
        representative_record, _, representative_detail = best
        basins.append({
            "basin_id": f"basin_{basin_index + 1}",
            "sample_count": len(assigned_classified),
            "unique_feasible_config_count": support,
            "classification_counts": class_counts,
            "representative": _result_record(
                representative_record, representative_detail, names),
            "anchor_params": feasible[seed_index][1],
            "best_objective": representative_detail.get("objective_value"),
            "recent_window": {
                "iteration_start": cutoff,
                "iteration_end": max_iteration,
                "prior_best": prior_best,
                "recent_best": recent_best,
                "improvement": improvement,
                "improvement_definition": "prior_best - recent_best; positive is better",
            },
            "empirical_confidence": {
                "value": empirical,
                "calibrated_probability": False,
                "definition": "sqrt(feasible_support/8), capped at 1, times feasibility rate",
            },
            "model_confidence": {
                "value": sum(model_values) / len(model_values) if model_values else None,
                "value_semantics": (
                    "heterogeneous non-calibrated signal mean; do not interpret as a "
                    "probability or compare sources without their definitions"
                ),
                "sample_count": len(model_values),
                "candidate_count": len(model_candidate_ids),
                "sources": sorted(source for source in model_sources if source),
                "by_source": {
                    source: {
                        key: summary[key] for key in ("count", "min", "mean", "max")
                    }
                    for source, values in sorted(model_values_by_source.items())
                    for summary in (_numeric_summary(values),)
                },
                "definitions": sorted(model_definitions),
                "calibrated_probability": False,
                "status": "reported_by_model" if model_values else "not_available",
            },
        })
    return {
        "status": "ok",
        "distance_metric": "rms_euclidean_over_parameter_ranges",
        "selection": "best feasible seed followed by normalized farthest-first seeds",
        "basin_count": len(basins),
        "basins": basins,
    }


def _source_target_edges(
    resolved_history: Sequence[Mapping[str, Any]],
    routing_history: Sequence[Mapping[str, Any]],
    limit: int = _DEFAULT_HISTORICAL_EDGE_LIMIT,
) -> Dict[str, Any]:
    edges: Dict[Tuple[Any, ...], Dict[str, Any]] = {}
    for record in list(resolved_history or ()) + list(routing_history or ()):
        if not isinstance(record, Mapping):
            continue
        nested = record.get("stage_record")
        source = nested if isinstance(nested, Mapping) else record
        source_run_id = source.get("source_run_id", record.get("source_run_id"))
        target_run_id = source.get(
            "target_run_id", record.get("target_run_id", record.get("run_id")))
        if source_run_id is None or target_run_id is None:
            continue
        stage = str(source.get("stage", _record_stage(record, "unknown")))
        iteration = _iteration(source) or _iteration(record)
        key = (iteration, stage, source_run_id, target_run_id)
        generated = source.get("generated_params")
        if not isinstance(generated, Mapping):
            generated = record.get("params") if isinstance(record.get("params"), Mapping) else {}
        edge = {
            "iteration": iteration,
            "stage": stage,
            "source_run_id": source_run_id,
            "target_run_id": target_run_id,
            "mapping": f"iter{iteration}:{stage}:run{source_run_id}->run{target_run_id}",
            "source_candidate_id": _lineage_identity(
                record, "source_candidate_id"),
            "target_candidate_id": _lineage_identity(
                record, "target_candidate_id", "candidate_id"),
            "replaced_target_candidate_id": _lineage_identity(
                record, "replaced_target_candidate_id", "replaced_candidate_id"),
            "parent_family": source.get(
                "parent_family", record.get("parent_family", record.get("upstream_family"))),
            "generated_params": dict(generated),
            "trusted": source.get("trusted", record.get("trusted")),
            "provenance": source.get("provenance", record.get("provenance")),
        }
        edges[key] = edge
    ordered = sorted(edges.values(), key=lambda edge: (
        edge["iteration"], edge["stage"], str(edge["source_run_id"]),
        str(edge["target_run_id"])))
    total = len(ordered)
    bounded_limit = max(0, int(limit))
    retained = ordered[-bounded_limit:] if bounded_limit else []
    indexed = [
        dict(edge, edge_index=total - len(retained) + index)
        for index, edge in enumerate(retained)
    ]
    return {
        "scope": "historical_clone_edges",
        "selection": "most recent edges in iteration/stage/source/target order",
        "limit": bounded_limit,
        "total_count": total,
        "returned_count": len(indexed),
        "omitted_count": total - len(indexed),
        "edges": indexed,
    }


def _classification_context(
    classified: Sequence[Tuple[Mapping[str, Any], str, Dict[str, Any]]],
    max_rows_per_class: int,
) -> Dict[str, Any]:
    groups = {name: [] for name in _OUTCOMES}
    for _, classification, detail in classified:
        groups[classification].append(detail)
    rows = {}
    omitted = {}
    limit = max(1, int(max_rows_per_class))
    for name, items in groups.items():
        if name == "feasible":
            items = sorted(items, key=lambda item: (
                float(item["objective_value"]) if item["objective_value"] is not None
                else float("inf"), -int(item["iteration"])))
        else:
            items = sorted(items, key=lambda item: (
                -int(item["iteration"]), str(item.get("run_id"))))
        rows[name] = items[:limit]
        omitted[name] = max(0, len(items) - limit)
    return {
        "classification_order": list(_OUTCOMES),
        "counts": {name: len(groups[name]) for name in _OUTCOMES},
        "rows": rows,
        "omitted_row_counts": omitted,
        "row_limit_per_class": limit,
    }


def build_prompt_evidence(
    objective: str,
    history: Sequence[Mapping[str, Any]],
    resolved_history: Sequence[Mapping[str, Any]] = (),
    routing_history: Sequence[Mapping[str, Any]] = (),
    optimization_state: Optional[Mapping[str, Any]] = None,
    constraints: Optional[Mapping[str, Any]] = None,
    power_base: Optional[float] = None,
    power_budget: Optional[float] = None,
    cp0: Optional[float] = None,
    *,
    top_k: int = 5,
    recent_window: int = 3,
    max_classification_rows: int = 24,
    max_historical_edges: int = _DEFAULT_HISTORICAL_EDGE_LIMIT,
    model_score_records: Sequence[Mapping[str, Any]] = (),
) -> Dict[str, Any]:
    """Return the eight structured context fields accepted by prompt builders.

    For ``TNS_EVAL``, completed observations are feasible only when their TNS is
    attributable to the shared ``cp0`` and their power is no greater than
    ``power_base * (1 + power_budget)``.  Missing CP0 TNS is a flow failure; valid
    CP0 TNS with missing/violating power is power-infeasible.
    """
    history = tuple(history or ())
    resolved_history = tuple(resolved_history or ())
    routing_history = tuple(routing_history or ())
    state = optimization_state if isinstance(optimization_state, Mapping) else {}
    bounds = _flatten_constraints(constraints)
    records = _canonical_records(history, resolved_history, routing_history)
    if bounds:
        names = list(bounds)
    else:
        parameter_sets = [_params(record) for record in records]
        names = sorted(max(parameter_sets, key=len, default={}).keys())
    if model_score_records:
        history = tuple(_attach_candidate_model_evidence(
            history, model_score_records, names))
        resolved_history = tuple(_attach_candidate_model_evidence(
            resolved_history, model_score_records, names))
        routing_history = tuple(_attach_candidate_model_evidence(
            routing_history, model_score_records, names))
        records = _canonical_records(history, resolved_history, routing_history)

    base, budget = _finite(power_base), _finite(power_budget)
    power_limit = base * (1.0 + budget) if base is not None and budget is not None else None
    contract = {
        "objective": objective,
        "direction": "minimize",
        "exact_objective": (
            "minimize abs(TNS evaluated at shared CP_0), subject to power <= power_limit"
            if objective == "TNS_EVAL" else f"minimize {objective}"
        ),
        "metric": "abs(TNS@CP0)" if objective == "TNS_EVAL" else objective,
        "comparison_clock": cp0,
        "comparison_clock_name": "CP_0" if objective == "TNS_EVAL" else None,
        "same_cp0_required": objective == "TNS_EVAL",
        "power_base": base,
        "power_budget_fraction": budget,
        "power_limit": power_limit,
        "power_limit_formula": "power_base * (1 + power_budget_fraction)",
        "power_margin_definition": "power_limit - observed_power; non-negative is feasible",
        "feasibility_rule": (
            "flow completed AND TNS source is shared CP_0 AND power <= power_limit"
            if objective == "TNS_EVAL" and power_limit is not None
            else "required objective metric is present and flow completed"
        ),
        "missing_power_rule": (
            "power_infeasible" if objective == "TNS_EVAL" and power_limit is not None
            else "power constraint inactive"
        ),
    }
    classified = _classify_records(records, objective, power_limit, cp0)
    top = _top_successful(classified, names, top_k)
    if top and top[0].get("power_margin") is not None:
        contract["incumbent_power_margin"] = top[0]["power_margin"]

    evidence = {
        "objective_contract": contract,
        "top_successful_configs": top,
        "stratified_bests": _stratified_bests(
            objective, history, resolved_history, routing_history, state,
            power_limit, cp0, names),
        "basin_summary": _basin_summary(
            records, classified, bounds, recent_window),
        "parameter_distributions": _parameter_distributions(classified, names),
        "distance_info": _distance_context(records, classified, bounds),
        "run_classifications": _classification_context(
            classified, max_classification_rows),
        "source_target_edges": _source_target_edges(
            resolved_history, routing_history, max_historical_edges),
    }
    return _json_safe(evidence)


def budget_prompt_evidence(
    evidence: Mapping[str, Any],
    *,
    candidate_examples: Sequence[Mapping[str, Any]] = (),
    top_limit: int = 5,
    basin_limit: int = 3,
    classification_limit_per_class: int = 4,
    historical_edge_limit: int = 12,
    candidate_limit: int = 16,
) -> Dict[str, Any]:
    """Build a compact, valid-JSON evidence object in decision-priority order.

    Callers must serialize the returned object as a whole; slicing serialized JSON can
    remove candidate distances or leave malformed JSON. Objective semantics, four-way
    bests, basins, and scored candidate examples are intentionally placed first.
    Lower-priority large fields retain counts and explicit omission metadata.
    """
    source = evidence if isinstance(evidence, Mapping) else {}
    result: Dict[str, Any] = {}

    if source.get("objective_contract") is not None:
        result["objective_contract"] = source.get("objective_contract")

    for context_field in (
            "optimization_context", "pdk_context", "design_context"):
        if source.get(context_field) is not None:
            result[context_field] = source.get(context_field)

    stratified = source.get("stratified_bests")
    if isinstance(stratified, Mapping):
        compact_stratified = {}
        best_fields = {
            "iteration", "run_id", "stage", "candidate_id", "source_candidate_id",
            "target_candidate_id", "replaced_target_candidate_id", "objective",
            "objective_value", "tns_at_cp0", "abs_tns_at_cp0", "power",
            "power_margin", "params", "source", "confirmation_count",
            "persistence_status", "config_signature", "parent_family",
        }
        for label, view in stratified.items():
            if not isinstance(view, Mapping):
                compact_stratified[str(label)] = view
                continue
            compact_view = {
                key: value for key, value in view.items() if key != "best"
            }
            best = view.get("best")
            compact_view["best"] = ({
                key: value for key, value in best.items() if key in best_fields
            } if isinstance(best, Mapping) else best)
            compact_stratified[str(label)] = compact_view
        result["stratified_bests"] = compact_stratified
    elif stratified is not None:
        result["stratified_bests"] = stratified

    top = source.get("top_successful_configs")
    if isinstance(top, Sequence) and not isinstance(top, (str, bytes)):
        retained = list(top)[:max(0, int(top_limit))]
        result["top_successful_configs"] = retained
        result["top_successful_configs_summary"] = {
            "total_count": len(top),
            "returned_count": len(retained),
            "omitted_count": len(top) - len(retained),
        }

    basins = source.get("basin_summary")
    if isinstance(basins, Mapping):
        compact_basins = dict(basins)
        rows = basins.get("basins")
        if isinstance(rows, Sequence) and not isinstance(rows, (str, bytes)):
            retained = list(rows)[:max(0, int(basin_limit))]
            compact_basins["basins"] = retained
            compact_basins["prompt_returned_count"] = len(retained)
            compact_basins["prompt_omitted_count"] = len(rows) - len(retained)
        result["basin_summary"] = compact_basins

    candidates = [dict(row) for row in candidate_examples
                  if isinstance(row, Mapping)]
    retained_candidates = candidates[:max(0, int(candidate_limit))]
    if candidate_examples or retained_candidates:
        result["candidate_examples"] = retained_candidates
        result["candidate_examples_summary"] = {
            "selection": "union of highest acquisition and highest normalized novelty",
            "total_supplied": len(candidates),
            "returned_count": len(retained_candidates),
            "omitted_count": len(candidates) - len(retained_candidates),
            "required_distance_fields": [
                "distance_to_nearest_history", "distance_to_incumbent",
            ],
        }

    # Keep the definition/incumbent and aggregate distance coverage after the actual
    # scored candidates; this ordering prevents generic summaries from crowding them out.
    if source.get("distance_info") is not None:
        result["distance_info"] = source.get("distance_info")

    classifications = source.get("run_classifications")
    if isinstance(classifications, Mapping):
        compact_classes = {
            key: value for key, value in classifications.items() if key != "rows"
        }
        rows = classifications.get("rows")
        if isinstance(rows, Mapping):
            row_limit = max(0, int(classification_limit_per_class))
            compact_rows, prompt_omitted = {}, {}
            for label in _OUTCOMES:
                items = rows.get(label)
                items = list(items) if isinstance(items, list) else []
                compact_rows[label] = items[:row_limit]
                prompt_omitted[label] = len(items) - len(compact_rows[label])
            compact_classes["rows"] = compact_rows
            compact_classes["prompt_row_limit_per_class"] = row_limit
            compact_classes["prompt_omitted_from_supplied_rows"] = prompt_omitted
        result["run_classifications"] = compact_classes

    distributions = source.get("parameter_distributions")
    if isinstance(distributions, Mapping):
        compact_distributions = {
            key: value for key, value in distributions.items() if key != "by_parameter"
        }
        compact_distributions["prompt_stat_fields"] = [
            "count", "sample_count", "missing_count", "min", "median", "mean", "max",
        ]
        by_parameter = distributions.get("by_parameter")
        compact_by_parameter = {}
        if isinstance(by_parameter, Mapping):
            for name, groups in by_parameter.items():
                if not isinstance(groups, Mapping):
                    continue
                compact_by_parameter[str(name)] = {}
                for label, stats in groups.items():
                    if not isinstance(stats, Mapping):
                        continue
                    compact_by_parameter[str(name)][str(label)] = {
                        key: stats.get(key) for key in compact_distributions[
                            "prompt_stat_fields"] if key in stats
                    }
        compact_distributions["by_parameter"] = compact_by_parameter
        result["parameter_distributions"] = compact_distributions

    edges = source.get("source_target_edges")
    edge_limit = max(0, int(historical_edge_limit))
    if isinstance(edges, Mapping):
        compact_edges = dict(edges)
        rows = edges.get("edges")
        if isinstance(rows, list):
            retained = rows[-edge_limit:] if edge_limit else []
            compact_edges["edges"] = retained
            compact_edges["prompt_returned_count"] = len(retained)
            compact_edges["prompt_omitted_from_supplied_edges"] = len(rows) - len(retained)
        result["source_target_edges"] = compact_edges
    elif isinstance(edges, list):
        # Current-stage positional edges should not use this helper. If a caller passes
        # them accidentally, retain the complete list rather than breaking output[i].
        result["source_target_edges"] = {
            "scope": "current_stage_positional_edges",
            "total_count": len(edges),
            "returned_count": len(edges),
            "omitted_count": 0,
            "edges": list(edges),
        }

    result["prompt_budget"] = {
        "method": "field_level_structural_budget",
        "serialized_json_must_not_be_sliced": True,
        "priority_order": [
            "objective_contract", "optimization_context", "pdk_context",
            "design_context", "stratified_bests", "top_successful_configs",
            "basin_summary", "candidate_examples", "distance_info",
            "run_classifications", "parameter_distributions",
            "source_target_edges",
        ],
    }
    return _json_safe(result)


__all__ = [
    "annotate_candidate_distances",
    "budget_prompt_evidence",
    "build_prompt_evidence",
    "load_model_score_evidence",
]
