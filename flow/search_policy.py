"""Shared campaign search policy for the plain and agentic optimizers.

The policy deliberately sits above candidate generation.  It tracks clean full-flow,
lineage-observed, routing-child, and independently config-reproduced notions of best,
decides when the campaign should focus on routing, and reshapes a candidate batch
while the inter-iteration optimizer emits only the 10-dimensional upstream space.

This module has no numpy, sklearn, OpenROAD, or LLM dependency. Both optimizers call
it after candidate generation; campaign orchestration remains with the caller.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
from collections import defaultdict
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from common import POWER_VIOLATION_PENALTY, tns_eval_obj
from config_recipe import recipe_from_scoped, routing_parent_family, validate_recipe
from search_policy_persistence import (
    STATE_VERSION,
    _atomic_write_json,
    load_optimization_state,
    persist_batch_plan,
    persist_optimization_state,
)
from search_policy_replay import (
    analyze_replays as _analyze_replays_impl,
    finite_float as _finite_float,
    is_lineage_candidate as _is_lineage_candidate,
    median as _median,
    record_metrics as _record_metrics,
    replay_tolerance as _replay_tolerance,
)
from search_policy_config import (
    DEFAULT_SEARCH_POLICY,
    load_search_policy_config,
    policy_for_context,
)

FULL_SEARCH = "FULL_SEARCH"
ROUTING_FOCUS = "ROUTING_FOCUS"

ROUTING_PARAMETERS = ("PIN_LAYER_ADJUST", "ABOVE_LAYER_ADJUST")
FLOORPLAN_CONTEXT_PARAMETERS = {
    "PIN_LAYER_ADJUST": "FLOORPLAN_PIN_LAYER_ADJUST",
    "ABOVE_LAYER_ADJUST": "FLOORPLAN_ABOVE_LAYER_ADJUST",
}
CTS_PARAMETERS = ("CTS_CLUSTER_SIZE", "CTS_CLUSTER_DIAMETER")
CLOCK_PARAMETER = "clk_period"

_CANDIDATE_METADATA_KEYS = (
    "_candidate_id",
    "_candidate_origin",
    "_candidate_parent",
)
_CANDIDATE_ORIGINS = {
    "llm", "bayes", "lhs", "exploit", "replay", "full_probe",
    "focus_exact", "focus_agent2", "focus_novelty",
}

_BEST_RECIPE_FIELDS = (
    "params",
    "signature",
    "upstream_signature",
    "config_recipe",
    "recipe_signature",
    "candidate_id",
)


def _confirmation_evidence(record: Mapping[str, Any],
                           objective: str) -> Tuple[bool, List[str]]:
    """Validate the strong provenance required by config-reproducible best."""
    reasons = []
    if record.get("full_flow_attributable") is not True:
        reasons.append("full_flow_provenance_unverified")
    if objective == "TNS_EVAL":
        source = _record_metrics(record).get("tns_source")
        if source != "cp0_eval":
            reasons.append(f"tns_source_{source or 'missing'}")
    return not reasons, reasons


def _record_params(record: Mapping[str, Any]) -> Dict[str, float]:
    # Stage-history rows use ``params`` for their local (CTS/routing-only) model,
    # but campaign bests and exact replays need the full lineage-resolved config.
    params = record.get("effective_params")
    if not isinstance(params, Mapping):
        params = record.get("params")
    if not isinstance(params, Mapping):
        return {}
    out: Dict[str, float] = {}
    for key, value in params.items():
        number = _finite_float(value)
        if number is not None:
            out[str(key)] = number
    return out


def _record_config_recipe(record: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    """Return a validated static, stage-scoped replay recipe when one exists."""
    recipe = record.get("config_recipe")
    if not isinstance(recipe, Mapping):
        stage_record = record.get("stage_record")
        if isinstance(stage_record, Mapping):
            recipe = stage_record.get("config_recipe")
    if not isinstance(recipe, Mapping):
        return None
    return validate_recipe(recipe)


def _record_replay_signature(record: Mapping[str, Any], decimals: int) -> str:
    recipe = _record_config_recipe(record)
    if recipe is not None:
        return str(recipe["signature"])
    return _param_signature(_record_params(record), decimals)


def _record_iteration(record: Mapping[str, Any]) -> int:
    try:
        return max(0, int(record.get("iteration", 0)))
    except (TypeError, ValueError):
        return 0


def _record_candidate_id(record: Mapping[str, Any]) -> Optional[str]:
    """Return the candidate identity represented by a persisted history row."""
    queue = [record]
    seen = set()
    while queue:
        current = queue.pop(0)
        if not isinstance(current, Mapping) or id(current) in seen:
            continue
        seen.add(id(current))
        for key in ("_candidate_id", "candidate_id", "target_candidate_id"):
            value = current.get(key)
            if value is not None and str(value).strip():
                return str(value).strip()
        for key in ("stage_record", "lineage_event", "record"):
            nested = current.get(key)
            if isinstance(nested, Mapping):
                queue.append(nested)
    return None


def _objective_value(
    record: Mapping[str, Any],
    objective: str,
    *,
    power_budget: Optional[float],
    power_base: Optional[float],
    wl_base: float,
    ecp_base: float,
    weight_wl: float,
    weight_ecp: float,
    objective_fn: Optional[Callable[[Mapping[str, Any]], Optional[float]]] = None,
) -> Optional[float]:
    if objective_fn is not None:
        return _finite_float(objective_fn(record))
    metrics = _record_metrics(record)
    if objective == "wl":
        return _finite_float(metrics.get("wl"))
    if objective == "ecp":
        return _finite_float(metrics.get("ecp"))
    if objective == "TNS_EVAL":
        if power_budget is not None and (power_base is None or power_base <= 0):
            return None
        value = tns_eval_obj(metrics, power_budget, power_base)
        value = _finite_float(value)
        if value is None or value >= POWER_VIOLATION_PENALTY:
            return None
        return value
    explicit = _finite_float(record.get("objective"))
    if explicit is not None:
        return explicit
    wl = _finite_float(metrics.get("wl"))
    ecp = _finite_float(metrics.get("ecp"))
    if wl is None or ecp is None or wl_base <= 0 or ecp_base <= 0:
        return None
    return weight_wl * wl / wl_base + weight_ecp * ecp / ecp_base


def _param_signature(params: Mapping[str, Any], decimals: int) -> str:
    normalized = []
    for key in sorted(params):
        number = _finite_float(params[key])
        if number is not None:
            normalized.append((str(key), round(number, decimals)))
    return hashlib.sha256(
        json.dumps(normalized, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _scoped_execution_signature(params: Mapping[str, Any],
                                scoped_params: Mapping[str, Any],
                                sdc_sha256: Any) -> str:
    recipe = recipe_from_scoped(params, scoped_params, sdc_sha256)
    if recipe is None:
        raise ValueError("cannot sign an incomplete stage-scoped config recipe")
    return str(recipe["signature"])


def _upstream_signature(params: Mapping[str, Any], decimals: int) -> str:
    upstream = {
        key: value for key, value in params.items()
        if key not in ROUTING_PARAMETERS
    }
    return _param_signature(upstream, decimals)


def _serialize_best(record: Optional[Mapping[str, Any]], objective_value: Optional[float],
                    source: str, decimals: int) -> Optional[Dict[str, Any]]:
    if record is None or objective_value is None:
        return None
    params = _record_params(record)
    recipe = _record_config_recipe(record)
    result = {
        "objective": objective_value,
        "iteration": _record_iteration(record),
        "run_id": record.get("run_id"),
        "source": source,
        "params": params,
        "signature": _param_signature(params, decimals),
        "upstream_signature": _upstream_signature(params, decimals),
    }
    if recipe is not None:
        result["config_recipe"] = recipe
        result["recipe_signature"] = str(recipe["signature"])
    candidate_id = _record_candidate_id(record)
    if candidate_id is not None:
        result["candidate_id"] = candidate_id
    return _attach_best_recipe_binding(result)


def _best_identity(best: Any) -> Optional[Tuple[str, int, str, float]]:
    """Identity of one historical objective observation within a campaign."""
    if not isinstance(best, Mapping) or best.get("run_id") is None:
        return None
    objective = _finite_float(best.get("objective"))
    if objective is None:
        return None
    try:
        iteration = int(best.get("iteration", 0))
    except (TypeError, ValueError):
        return None
    return (
        str(best.get("source") or ""),
        iteration,
        str(best.get("run_id")),
        objective,
    )


def _recipe_matches_params(recipe: Any, params: Any) -> bool:
    validated = validate_recipe(recipe)
    if validated is None or not isinstance(params, Mapping):
        return False
    for name, expected in validated["final_params"].items():
        actual = _finite_float(params.get(name))
        if actual is None or not math.isclose(
                actual, float(expected), rel_tol=0.0, abs_tol=1.0e-12):
            return False
    return True


def _attach_best_recipe_binding(best: Mapping[str, Any]) -> Dict[str, Any]:
    """Embed a self-checking objective-to-recipe binding in a serialized best."""
    result = deepcopy(dict(best))
    params = result.get("params") if isinstance(result.get("params"), Mapping) else {}
    recipe = validate_recipe(result.get("config_recipe"))
    if recipe is not None and not _recipe_matches_params(recipe, params):
        # A recipe that describes a different parameter vector is unsafe to replay.
        result.pop("config_recipe", None)
        result.pop("recipe_signature", None)
        recipe = None
    payload = {
        "schema_version": 1,
        "source": str(result.get("source") or ""),
        "iteration": int(result.get("iteration", 0)),
        "run_id": result.get("run_id"),
        "objective": _finite_float(result.get("objective")),
        "params_signature": result.get("signature"),
        "recipe_signature": (str(recipe["signature"]) if recipe else None),
        "sdc_sha256": (str(recipe["sdc_sha256"]) if recipe else None),
        "clk_period": _finite_float(params.get(CLOCK_PARAMETER)),
    }
    payload["binding_sha256"] = hashlib.sha256(json.dumps(
        payload, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")).hexdigest()
    result["immutable_recipe_binding"] = payload
    return result


def _preserve_previous_best_recipe(
    previous: Any,
    current: Optional[Mapping[str, Any]],
    best_key: str,
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """Keep the first recipe attached to an unchanged historical observation.

    History is reloaded on every optimizer invocation.  If an old config refers to a
    reused live SDC path, a loader bug or incomplete archive must not silently change
    the parameters/replay recipe attached to the same objective observation.
    """
    if current is None:
        return None, None
    result = deepcopy(dict(current))
    if not isinstance(previous, Mapping) or _best_identity(previous) != _best_identity(result):
        return _attach_best_recipe_binding(result), None

    changed: List[str] = []
    for field in _BEST_RECIPE_FIELDS:
        if field not in previous:
            continue
        prior_value = previous[field]
        if field == "config_recipe" and validate_recipe(prior_value) is None:
            continue
        if result.get(field) != prior_value:
            changed.append(field)
        result[field] = deepcopy(prior_value)

    # Do not combine a newly discovered recipe with older frozen parameters unless
    # they describe exactly the same complete execution vector.
    if ("config_recipe" not in previous
            and not _recipe_matches_params(
                result.get("config_recipe"), result.get("params"))):
        result.pop("config_recipe", None)
        result.pop("recipe_signature", None)
    result = _attach_best_recipe_binding(result)
    if not changed:
        return result, None
    return result, {
        "best_key": best_key,
        "source": result.get("source"),
        "iteration": result.get("iteration"),
        "run_id": result.get("run_id"),
        "objective": result.get("objective"),
        "changed_fields": changed,
        "action": "preserved_previous_immutable_recipe",
    }


def _meaningfully_better(new: float, reference: float, policy: Mapping[str, Any]) -> bool:
    threshold = max(
        float(policy["significant_improvement_abs"]),
        abs(reference) * float(policy["significant_improvement_rel"]),
    )
    return new < reference - threshold


def _rank_records(
    records: Sequence[Mapping[str, Any]], objective: str, context: Mapping[str, Any],
    objective_fn: Optional[Callable[[Mapping[str, Any]], Optional[float]]] = None,
) -> List[Tuple[float, Mapping[str, Any]]]:
    ranked: List[Tuple[float, Mapping[str, Any]]] = []
    for record in records:
        if not isinstance(record, Mapping) or not _record_params(record):
            continue
        value = _objective_value(
            record, objective,
            power_budget=context.get("power_budget"),
            power_base=context.get("power_base"),
            wl_base=float(context.get("wl_base", 1.0)),
            ecp_base=float(context.get("ecp_base", 1.0)),
            weight_wl=float(context.get("weight_wl", 0.5)),
            weight_ecp=float(context.get("weight_ecp", 0.5)),
            objective_fn=objective_fn,
        )
        if value is not None:
            ranked.append((value, record))
    ranked.sort(key=lambda item: (item[0], _record_iteration(item[1]),
                                  str(item[1].get("run_id", ""))))
    return ranked


def _best_and_last_significant(
    ranked: Sequence[Tuple[float, Mapping[str, Any]]], policy: Mapping[str, Any],
) -> Tuple[Optional[Tuple[float, Mapping[str, Any]]], int]:
    by_iteration: Dict[int, Tuple[float, Mapping[str, Any]]] = {}
    for value, record in ranked:
        iteration = _record_iteration(record)
        current = by_iteration.get(iteration)
        if current is None or value < current[0]:
            by_iteration[iteration] = (value, record)

    significant_reference: Optional[float] = None
    last_significant = 0
    absolute_best: Optional[Tuple[float, Mapping[str, Any]]] = None
    for iteration in sorted(by_iteration):
        candidate = by_iteration[iteration]
        if absolute_best is None or candidate[0] < absolute_best[0]:
            absolute_best = candidate
        if significant_reference is None or _meaningfully_better(
            candidate[0], significant_reference, policy
        ):
            significant_reference = candidate[0]
            last_significant = iteration
    return absolute_best, last_significant


def _recent_clean_coverage(clean_ranked: Sequence[Tuple[float, Mapping[str, Any]]],
                           current_iteration: int, window: int, num_runs: int,
                           policy: Mapping[str, Any]) -> Tuple[bool, Dict[str, int]]:
    counts: Dict[int, int] = {}
    for _, record in clean_ranked:
        iteration = _record_iteration(record)
        counts[iteration] = counts.get(iteration, 0) + 1
    required = max(
        int(policy["min_clean_count"]),
        int(math.ceil(max(0, num_runs) * float(policy["min_clean_fraction"]))),
    )
    start = max(1, current_iteration - max(1, window) + 1)
    recent = {str(it): counts.get(it, 0) for it in range(start, current_iteration + 1)}
    return bool(recent) and all(count >= required for count in recent.values()), recent


def _analyze_replays(
    clean_records: Sequence[Mapping[str, Any]],
    clean_ranked: Sequence[Tuple[float, Mapping[str, Any]]],
    resolved_ranked: Sequence[Tuple[float, Mapping[str, Any]]],
    routing_ranked: Sequence[Tuple[float, Mapping[str, Any]]],
    policy: Mapping[str, Any],
    objective: str,
    context: Mapping[str, Any],
    objective_fn: Optional[Callable[[Mapping[str, Any]], Optional[float]]] = None,
) -> Dict[str, Any]:
    """Classify lineage recipes while retaining facade-level monkeypatch hooks."""
    return _analyze_replays_impl(
        clean_records, clean_ranked, resolved_ranked, routing_ranked,
        policy, objective, context, objective_fn,
        is_lineage_candidate_fn=_is_lineage_candidate,
        record_params_fn=_record_params,
        record_recipe_fn=_record_config_recipe,
        record_iteration_fn=_record_iteration,
        replay_signature_fn=_record_replay_signature,
        meaningfully_better_fn=_meaningfully_better,
        serialize_best_fn=_serialize_best,
        replay_tolerance_fn=_replay_tolerance,
        confirmation_evidence_fn=_confirmation_evidence,
        objective_value_fn=_objective_value,
        median_fn=_median,
    )


def _pending_replays(
    clean_records: Sequence[Mapping[str, Any]],
    clean_ranked: Sequence[Tuple[float, Mapping[str, Any]]],
    resolved_ranked: Sequence[Tuple[float, Mapping[str, Any]]],
    routing_ranked: Sequence[Tuple[float, Mapping[str, Any]]],
    policy: Mapping[str, Any],
) -> List[Dict[str, Any]]:
    """Backward-compatible helper retained for unit-level policy callers."""
    return _analyze_replays(
        clean_records, clean_ranked, resolved_ranked, routing_ranked, policy,
        "TNS_EVAL", {"power_budget": None, "power_base": None},
    )["pending"]


def update_optimization_state(
    state_path: Path,
    *,
    current_iteration: int,
    objective: str,
    clean_history: Sequence[Mapping[str, Any]],
    resolved_history: Sequence[Mapping[str, Any]] = (),
    routing_history: Sequence[Mapping[str, Any]] = (),
    policy_config: Optional[Mapping[str, Any]] = None,
    power_budget: Optional[float] = None,
    power_base: Optional[float] = None,
    wl_base: float = 1.0,
    ecp_base: float = 1.0,
    weight_wl: float = 0.5,
    weight_ecp: float = 0.5,
    num_runs: int = 0,
    platform: Optional[str] = None,
    design: Optional[str] = None,
    campaign_id: Optional[str] = None,
    persist: bool = True,
    objective_fn: Optional[Callable[[Mapping[str, Any]], Optional[float]]] = None,
) -> Dict[str, Any]:
    """Recompute, transition, and atomically persist the campaign search state.

    ``clean_history`` must contain full-flow attributable observations.  The other two
    histories may contain lineage-resolved DRP children; they can become exact replay
    candidates but never replace ``best_clean_replay`` until a clean replay confirms
    them.
    """
    policy = policy_for_context(policy_config, objective, platform, design)
    if policy is None:
        disabled = {
            "state_version": STATE_VERSION, "enabled": False,
            "objective": objective, "platform": platform, "design": design,
            "mode": FULL_SEARCH, "current_iteration": int(current_iteration),
            "stop_requested": False,
            "campaign_id": campaign_id,
        }
        # Replace an enabled state from a different objective/scope so an interrupted
        # caller can never accidentally reuse its replay slots or search mode.
        if persist:
            _atomic_write_json(Path(state_path), disabled)
        return disabled

    context = {
        "power_budget": power_budget, "power_base": power_base,
        "wl_base": wl_base, "ecp_base": ecp_base,
        "weight_wl": weight_wl, "weight_ecp": weight_ecp,
    }
    clean_ranked = _rank_records(clean_history, objective, context, objective_fn)
    resolved_ranked = _rank_records(resolved_history, objective, context, objective_fn)
    routing_ranked = _rank_records(routing_history, objective, context, objective_fn)
    clean_best, clean_last = _best_and_last_significant(clean_ranked, policy)
    effective_best, effective_last = _best_and_last_significant(resolved_ranked, policy)
    routing_best, routing_last = _best_and_last_significant(routing_ranked, policy)

    previous = load_optimization_state(state_path)
    if previous is not None and previous.get("objective") not in (None, objective):
        previous = None
    if (previous is not None and campaign_id is not None
            and previous.get("campaign_id") not in (None, campaign_id)):
        previous = None
    mode = previous.get("mode", FULL_SEARCH) if previous else FULL_SEARCH
    mode_entered = int(previous.get("mode_entered_iteration", 1)) if previous else 1
    reopen_count = int(previous.get("reopen_count", 0)) if previous else 0
    stop_requested = False
    transition_reason = "state_updated"

    clean_stagnation = max(0, int(current_iteration) - clean_last) if clean_last else 0
    effective_stagnation = (
        max(0, int(current_iteration) - effective_last) if effective_last else clean_stagnation
    )
    routing_stagnation = (
        max(0, int(current_iteration) - routing_last) if routing_last else clean_stagnation
    )
    coverage_ok, recent_counts = _recent_clean_coverage(
        clean_ranked, int(current_iteration),
        int(policy["full_stagnation_patience"]), int(num_runs), policy,
    )
    replay_analysis = _analyze_replays(
        clean_history, clean_ranked, resolved_ranked, routing_ranked, policy,
        objective, context, objective_fn)
    pending = replay_analysis["pending"]
    config_reproducible = (
        replay_analysis["promoted"][0] if replay_analysis["promoted"] else None)

    decimals = int(policy["signature_decimals"])
    clean_serialized = _serialize_best(
        clean_best[1] if clean_best else None,
        clean_best[0] if clean_best else None, "clean_replay", decimals,
    )
    effective_serialized = _serialize_best(
        effective_best[1] if effective_best else None,
        effective_best[0] if effective_best else None, "observed_effective", decimals,
    )
    routing_serialized = _serialize_best(
        routing_best[1] if routing_best else None,
        routing_best[0] if routing_best else None, "routing_child", decimals,
    )

    if previous and previous.get("stop_requested"):
        # STOP is terminal for a campaign. A deliberate --fresh invalidation is the
        # explicit resume/restart mechanism and removes this state file.
        stop_requested = True
        transition_reason = str(
            previous.get("stop_reason")
            or previous.get("transition_reason")
            or "campaign_stop_is_sticky"
        )
    elif mode == FULL_SEARCH:
        min_full = int(policy["min_full_iterations"])
        after_reopen = previous is not None and previous.get("last_transition") == "REOPEN_FULL"
        enough_after_reopen = (
            int(current_iteration) - mode_entered >= int(policy["reopen_min_full_iterations"])
        )
        if (
            int(current_iteration) >= min_full
            and clean_best is not None
            and clean_stagnation >= int(policy["full_stagnation_patience"])
            and coverage_ok
            and (not after_reopen or enough_after_reopen)
        ):
            mode = ROUTING_FOCUS
            mode_entered = int(current_iteration)
            transition_reason = "clean_stagnation_enter_routing_focus"
    else:
        focus_age = max(0, int(current_iteration) - mode_entered)
        anchor_signatures = set(previous.get("focus_upstream_signatures", [])) if previous else set()
        clean_after_focus = [
            (value, record) for value, record in clean_ranked
            if _record_iteration(record) > mode_entered
        ]
        focus_entry_best = _finite_float(
            (previous or {}).get("focus_entry_clean_objective")
        )
        improved_new_upstream = False
        if focus_entry_best is not None:
            improved_new_upstream = any(
                _meaningfully_better(value, focus_entry_best, policy)
                and _upstream_signature(_record_params(record), decimals) not in anchor_signatures
                for value, record in clean_after_focus
            )
        low_coverage_window = int(policy["reopen_low_coverage_patience"])
        low_coverage, _ = _recent_clean_coverage(
            clean_ranked, int(current_iteration), low_coverage_window, int(num_runs), policy
        )
        if improved_new_upstream or (
            focus_age >= low_coverage_window and not low_coverage
        ):
            mode = FULL_SEARCH
            mode_entered = int(current_iteration)
            reopen_count += 1
            transition_reason = (
                "new_upstream_clean_improvement" if improved_new_upstream
                else "routing_focus_clean_coverage_low"
            )
        elif (
            int(current_iteration) >= int(policy["min_iterations_before_stop"])
            and focus_age >= int(policy["focus_min_iterations"])
            and clean_stagnation >= int(policy["focus_stop_patience"])
            and effective_stagnation >= int(policy["focus_stop_patience"])
            and routing_stagnation >= int(policy["focus_stop_patience"])
            and not pending
            and coverage_ok
        ):
            stop_requested = True
            transition_reason = "dual_best_stagnation_no_pending_replay"

    state = {
        "state_version": STATE_VERSION,
        "enabled": True,
        "objective": objective,
        "platform": platform,
        "design": design,
        "campaign_id": campaign_id,
        "objective_context": context,
        "current_iteration": int(current_iteration),
        "mode": mode,
        "mode_entered_iteration": mode_entered,
        "stop_requested": stop_requested,
        "transition_reason": transition_reason,
        "last_transition": (
            "STOP" if stop_requested
            else "REOPEN_FULL" if mode == FULL_SEARCH and transition_reason != "state_updated"
            else "ENTER_ROUTING_FOCUS" if mode == ROUTING_FOCUS and transition_reason.startswith("clean_")
            else (previous or {}).get("last_transition")
        ),
        "stop_reason": transition_reason if stop_requested else None,
        "reopen_count": reopen_count,
        "best_clean_replay": clean_serialized,
        "best_observed_effective": effective_serialized,
        "best_routing_child": routing_serialized,
        "best_config_reproducible": config_reproducible,
        "last_significant_clean_iteration": clean_last,
        "last_significant_effective_iteration": effective_last,
        "last_significant_routing_iteration": routing_last,
        "clean_stagnation_iterations": clean_stagnation,
        "effective_stagnation_iterations": effective_stagnation,
        "routing_stagnation_iterations": routing_stagnation,
        "clean_coverage_ok": coverage_ok,
        "recent_clean_counts": recent_counts,
        "pending_replays": pending,
        "config_replay_statuses": replay_analysis["statuses"],
        "policy": policy,
    }

    # Trust regions are campaign state, not transient generator state.  They only
    # move when a parent family receives a new trusted routing observation.
    try:
        from common import get_design_config, get_param_constraints
        from routing_focus import prepare_observations, update_trust_regions
        root_config = policy_config if isinstance(policy_config, Mapping) else {}
        design_config = get_design_config(root_config, platform, design)
        routing_constraints = get_param_constraints(
            root_config, "routing", design_config)
        routing_observations = prepare_observations(
            routing_history, context, routing_constraints,
            decimals=int(policy["signature_decimals"]))
        state["routing_trust_regions"] = update_trust_regions(
            (previous or {}).get("routing_trust_regions", {}),
            routing_observations, int(current_iteration), policy)
    except (KeyError, TypeError, ValueError):
        # Unit-level callers may pass only the search_policy subsection.  Preserve
        # existing campaign regions; shape-time still has the complete constraints.
        state["routing_trust_regions"] = dict(
            (previous or {}).get("routing_trust_regions", {}))

    # Preserve or establish the multi-anchor set at focus entry.  Shape-time may add
    # exact parameter dictionaries, while transition logic only needs signatures.
    if mode == ROUTING_FOCUS:
        ranked_clean = clean_ranked[: max(1, int(policy["anchor_count"]) * 4)]
        signatures: List[str] = []
        for _, record in ranked_clean:
            signature = _upstream_signature(_record_params(record), decimals)
            if signature not in signatures:
                signatures.append(signature)
            if len(signatures) >= int(policy["anchor_count"]):
                break
        if previous and previous.get("mode") == ROUTING_FOCUS:
            signatures = previous.get("focus_upstream_signatures", signatures)
        state["focus_upstream_signatures"] = signatures
        state["focus_entry_clean_objective"] = (
            (previous or {}).get("focus_entry_clean_objective")
            if previous and previous.get("mode") == ROUTING_FOCUS
            else clean_serialized.get("objective") if clean_serialized else None
        )

    if persist:
        _atomic_write_json(Path(state_path), state)
    return state


def _constraint_copy(constraints: Mapping[str, Mapping[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {str(name): deepcopy(dict(spec)) for name, spec in constraints.items()}


def _bounds(spec: Mapping[str, Any]) -> Tuple[float, float]:
    values = spec.get("range", ())
    if not isinstance(values, Sequence) or len(values) != 2:
        raise ValueError(f"constraint has no [low, high] range: {spec}")
    low, high = float(values[0]), float(values[1])
    if not math.isfinite(low) or not math.isfinite(high) or low > high:
        raise ValueError(f"invalid constraint range {values}")
    return low, high


def _clip_value(value: Any, spec: Mapping[str, Any]) -> float:
    low, high = _bounds(spec)
    number = _finite_float(value)
    if number is None:
        number = (low + high) / 2.0
    number = min(high, max(low, number))
    if spec.get("type") == "int":
        return int(round(number))
    return float(number)


def _complete_params(params: Mapping[str, Any], constraints: Mapping[str, Mapping[str, Any]],
                     fallback: Optional[Mapping[str, Any]] = None) -> Dict[str, float]:
    fallback = fallback or {}
    return {
        name: _clip_value(params.get(name, fallback.get(name)), spec)
        for name, spec in constraints.items()
    }


def _candidate_metadata(candidate: Mapping[str, Any]) -> Dict[str, Any]:
    """Read tracking metadata without making the search policy depend on its writer."""
    try:
        from candidate_tracking import metadata as tracking_metadata

        value = tracking_metadata(candidate)
        if isinstance(value, Mapping):
            return {
                key: value.get(key)
                for key in _CANDIDATE_METADATA_KEYS
                if value.get(key) is not None
            }
    except (ImportError, AttributeError, TypeError, ValueError):
        pass
    return {
        key: candidate.get(key)
        for key in _CANDIDATE_METADATA_KEYS
        if candidate.get(key) is not None
    }


def _make_policy_candidate_id(
    state: Mapping[str, Any], slot: int, origin: str, stable_key: str,
    parent: Optional[str] = None,
) -> str:
    """Create a stable proposal id, with a local fallback during mixed deployments."""
    campaign_id = str(state.get("campaign_id") or "campaign-unknown")
    target_iteration = int(state.get("current_iteration", 0)) + 1
    try:
        from candidate_tracking import make_candidate_id

        attempts = (
            lambda: make_candidate_id(
                campaign_id=campaign_id, iteration=target_iteration,
                stable_key=stable_key),
            lambda: make_candidate_id(campaign_id, target_iteration, stable_key),
            lambda: make_candidate_id(
                campaign_id, target_iteration, slot, origin,
                parent=parent, params=None),
        )
        for attempt in attempts:
            try:
                value = attempt()
                if value:
                    return str(value)
            except TypeError:
                continue
    except (ImportError, AttributeError):
        pass
    payload = json.dumps(
        [campaign_id, target_iteration, stable_key],
        separators=(",", ":"), ensure_ascii=True,
    )
    return hashlib.sha256(payload.encode("ascii")).hexdigest()[:24]


def _slot_metadata(
    state: Mapping[str, Any], slot: int, origin: str, stable_key: str,
    *, parent: Optional[str] = None, existing: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Normalize one final-slot identity while retaining an upstream candidate id."""
    current = dict(existing or {})
    normalized_origin = str(current.get("_candidate_origin") or origin)
    if normalized_origin not in _CANDIDATE_ORIGINS:
        normalized_origin = origin if origin in _CANDIDATE_ORIGINS else "lhs"
    candidate_parent = current.get("_candidate_parent", parent)
    candidate_id = current.get("_candidate_id") or _make_policy_candidate_id(
        state, slot, normalized_origin, stable_key,
        str(candidate_parent) if candidate_parent is not None else None,
    )
    return {
        "_candidate_id": str(candidate_id),
        "_candidate_origin": normalized_origin,
        "_candidate_parent": (
            str(candidate_parent) if candidate_parent is not None else None),
    }


def _history_context(state: Mapping[str, Any]) -> Dict[str, Any]:
    context = state.get("objective_context", {})
    return dict(context) if isinstance(context, Mapping) else {}


def _rank_for_state(records: Sequence[Mapping[str, Any]], state: Mapping[str, Any]
                    ) -> List[Tuple[float, Mapping[str, Any]]]:
    return _rank_records(records, str(state.get("objective", "TNS_EVAL")),
                         _history_context(state))


def _weighted_clock_region(
    constraints: Mapping[str, Mapping[str, Any]],
    ranked_records: Sequence[Tuple[float, Mapping[str, Any]]],
    policy: Mapping[str, Any],
) -> Dict[str, Any]:
    if CLOCK_PARAMETER not in constraints:
        return {"active": False, "anchors": [], "weights": []}
    hard_low, hard_high = _bounds(constraints[CLOCK_PARAMETER])
    observations: List[Tuple[float, float]] = []
    seen = set()
    for _, record in ranked_records:
        params = _record_params(record)
        signature = _param_signature(params, int(policy["signature_decimals"]))
        if signature in seen:
            continue
        seen.add(signature)
        clock = _finite_float(params.get(CLOCK_PARAMETER))
        if clock is not None:
            observations.append((clock, 1.0 / (len(observations) + 1.0)))
        if len(observations) >= int(policy["clock_top_k"]):
            break
    if len(observations) < int(policy["clock_min_observations"]):
        return {
            "active": False, "range": [hard_low, hard_high],
            "hard_range": [hard_low, hard_high],
            "anchors": [item[0] for item in observations],
            "weights": [item[1] for item in observations],
        }

    clocks = [item[0] for item in observations]
    total_weight = sum(item[1] for item in observations)
    weights = [item[1] / total_weight for item in observations]
    center = sum(clock * weight for clock, weight in zip(clocks, weights))
    data_low, data_high = min(clocks), max(clocks)
    hard_span = hard_high - hard_low
    min_width = hard_span * float(policy["clock_min_width_fraction"])
    data_span = max(data_high - data_low, min_width)
    margin = data_span * float(policy["clock_margin_fraction"])
    low, high = max(hard_low, data_low - margin), min(hard_high, data_high + margin)
    if high - low < min_width:
        low = max(hard_low, center - min_width / 2.0)
        high = min(hard_high, low + min_width)
        low = max(hard_low, high - min_width)
    return {
        "active": True, "range": [low, high], "hard_range": [hard_low, hard_high],
        "center": center, "anchors": clocks, "weights": weights,
    }


def build_search_space(
    full_constraints: Mapping[str, Mapping[str, Any]],
    *,
    clean_history: Sequence[Mapping[str, Any]],
    resolved_history: Sequence[Mapping[str, Any]] = (),
    routing_history: Sequence[Mapping[str, Any]] = (),
    state: Mapping[str, Any],
    policy_config: Optional[Mapping[str, Any]],
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Any]]:
    """Return effective generation constraints plus hard-bound metadata."""
    policy = policy_for_context(
        policy_config, str(state.get("objective", "")),
        state.get("platform"), state.get("design"))
    hard = _constraint_copy(full_constraints)
    if policy is None or not state.get("enabled", False):
        return hard, {"enabled": False, "mode": FULL_SEARCH}

    # Clock changes every upstream stage, so only attributable clean full-flow
    # observations may define its trust region. Routing children can guide routing
    # knobs but must not narrow the global clock space.
    ranked = _rank_for_state(clean_history, state)
    clock = _weighted_clock_region(hard, ranked, policy)
    effective = _constraint_copy(hard)
    if clock.get("active") and CLOCK_PARAMETER in effective:
        effective[CLOCK_PARAMETER]["range"] = list(clock["range"])

    active = list(effective)
    frozen: List[str] = []
    if (state.get("mode") == ROUTING_FOCUS
            and any(name in effective for name in ROUTING_PARAMETERS)):
        active = [name for name in ROUTING_PARAMETERS if name in effective]
        frozen = [name for name in effective if name not in active]
    return effective, {
        "enabled": True,
        "mode": state.get("mode", FULL_SEARCH),
        "active_parameters": active,
        "frozen_parameters": frozen,
        "clock_region": clock,
        "cts_directed_region": {
            "CTS_CLUSTER_SIZE": list(policy["cts_cluster_size_window"]),
            "CTS_CLUSTER_DIAMETER": list(policy["cts_cluster_diameter_window"]),
        },
    }


def _derive_seed(seed: Any, *parts: Any) -> int:
    text = "|".join(str(item) for item in (seed, *parts))
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:16], 16)


def _select_anchors(clean_history: Sequence[Mapping[str, Any]], state: Mapping[str, Any],
                    constraints: Mapping[str, Mapping[str, Any]],
                    policy: Mapping[str, Any]) -> List[Dict[str, float]]:
    ranked = _rank_for_state(clean_history, state)
    anchors: List[Dict[str, float]] = []
    signatures: set[str] = set()
    decimals = int(policy["signature_decimals"])
    for _, record in ranked:
        params = _complete_params(_record_params(record), constraints)
        recipe = _record_config_recipe(record)
        if recipe is not None:
            params.update({
                name: float(value)
                for name, value in recipe["scoped_params"].items()
                if name in FLOORPLAN_CONTEXT_PARAMETERS.values()
                and _finite_float(value) is not None
            })
            params["_CONFIG_RECIPE"] = recipe
        signature = _upstream_signature(params, decimals)
        if signature in signatures:
            continue
        anchors.append(params)
        signatures.add(signature)
        if len(anchors) >= max(1, int(policy["anchor_count"])):
            break
    if not anchors:
        best = state.get("best_clean_replay") or {}
        if isinstance(best.get("params"), Mapping):
            params = _complete_params(best["params"], constraints)
            recipe = best.get("config_recipe")
            if isinstance(recipe, Mapping) and isinstance(recipe.get("scoped_params"), Mapping):
                params.update({
                    name: float(value)
                    for name, value in recipe["scoped_params"].items()
                    if name in FLOORPLAN_CONTEXT_PARAMETERS.values()
                    and _finite_float(value) is not None
                })
                params["_CONFIG_RECIPE"] = dict(recipe)
            anchors.append(params)
    return anchors


def _select_routing_anchors(
    routing_history: Sequence[Mapping[str, Any]],
    resolved_history: Sequence[Mapping[str, Any]],
    state: Mapping[str, Any],
    constraints: Mapping[str, Mapping[str, Any]],
    policy: Mapping[str, Any],
) -> List[Dict[str, Any]]:
    """Select paired routing mutations and retain each mutation's own parent.

    A routing delta is only causal relative to the upstream checkpoint/config that it
    mutated. Returning the route knobs alone would allow shape-time to combine them
    with an unrelated clean anchor. The complete parent is therefore part of every
    anchor contract.
    """
    del resolved_history  # Clean/resolved rows are not paired routing evidence.
    best = state.get("best_routing_child") or {}
    best_signature = best.get("signature") if isinstance(best, Mapping) else None
    decimals = int(policy["signature_decimals"])

    candidates: List[Tuple[int, float, float, Mapping[str, Any]]] = []
    for child_objective, record in _rank_for_state(routing_history, state):
        if state.get("objective") == "TNS_EVAL":
            source_metrics = record.get("source_metrics", {})
            child_metrics = record.get("child_metrics", record.get("metrics", {}))
            if (not isinstance(source_metrics, Mapping)
                    or not isinstance(child_metrics, Mapping)
                    or source_metrics.get("tns_source") != "cp0_eval"
                    or child_metrics.get("tns_source") != "cp0_eval"):
                continue
        effective = _record_params(record)
        signature = _param_signature(effective, decimals) if effective else None
        delta = _finite_float(record.get("delta_abs_tns"))
        if delta is None:
            delta = math.inf
        candidates.append((0 if signature == best_signature else 1,
                           delta, child_objective, record))
    candidates.sort(key=lambda item: item[:3])

    anchors: List[Dict[str, Any]] = []
    seen = set()
    for _, delta, child_objective, record in candidates:
        recipe = _record_config_recipe(record)
        if recipe is None:
            continue
        effective = _record_params(record)
        source = record.get("source_effective_params")
        if not isinstance(source, Mapping):
            source = effective
        if not all(name in effective for name in ROUTING_PARAMETERS):
            continue
        route = {
            name: _clip_value(effective[name], constraints[name])
            for name in ROUTING_PARAMETERS if name in constraints
        }
        upstream = {
            name: _clip_value(source.get(name, effective.get(name)), spec)
            for name, spec in constraints.items() if name not in ROUTING_PARAMETERS
        }
        scoped = dict(recipe["scoped_params"])
        parent_identity = routing_parent_family(
            source, scoped, recipe["sdc_sha256"], decimals=decimals)
        signature = (parent_identity, _param_signature(route, decimals))
        if len(route) != len([n for n in ROUTING_PARAMETERS if n in constraints]):
            continue
        if signature in seen:
            continue
        seen.add(signature)
        anchors.append({
            "routing_params": route,
            "upstream_params": upstream,
            "effective_params": effective,
            "scoped_params": scoped,
            "recipe_signature": str(recipe["signature"]),
            "sdc_sha256": recipe["sdc_sha256"],
            "parent_family": parent_identity,
            "candidate_id": _record_candidate_id(record),
            "delta_abs_tns": None if math.isinf(delta) else delta,
            "child_objective": child_objective,
        })
        if len(anchors) >= max(1, int(policy["anchor_count"])):
            break
    return anchors


def _focus_parent_candidate_ids(
    routing_history: Sequence[Mapping[str, Any]],
    clean_history: Sequence[Mapping[str, Any]],
    state: Mapping[str, Any],
    constraints: Mapping[str, Mapping[str, Any]],
    policy: Mapping[str, Any],
) -> Dict[str, str]:
    """Map each focus family to the historical candidate that seeded it."""
    result: Dict[str, str] = {}
    try:
        from routing_focus import prepare_observations

        observations = prepare_observations(
            routing_history, state.get("objective_context", {}), constraints,
            decimals=int(policy["signature_decimals"]),
        )
    except (ImportError, KeyError, TypeError, ValueError):
        observations = []

    if observations:
        grouped: Dict[str, List[Mapping[str, Any]]] = defaultdict(list)
        for observation in observations:
            grouped[str(observation["family"])].append(observation)
        for family, members in grouped.items():
            best = min(members, key=lambda row: (
                float(row["child_objective"]), float(row["delta"]),
                int(row.get("iteration", 0)),
            ))
            source = best.get("record")
            candidate_id = (
                _record_candidate_id(source) if isinstance(source, Mapping) else None)
            if candidate_id is not None:
                result[family] = candidate_id
        return result

    # Cold-start focus uses clean full-flow anchors. Mirror their ranking/family
    # selection so any available clean candidate identity remains the true parent.
    decimals = int(policy["signature_decimals"])
    for _, record in _rank_for_state(clean_history, state):
        candidate_id = _record_candidate_id(record)
        recipe = _record_config_recipe(record)
        if candidate_id is None or recipe is None:
            continue
        params = _complete_params(_record_params(record), constraints)
        family = routing_parent_family(
            params, recipe["scoped_params"], recipe["sdc_sha256"],
            decimals=decimals,
        )
        if family:
            result.setdefault(str(family), candidate_id)
    return result


def _weighted_choice_index(weights: Sequence[float], rng: random.Random) -> int:
    if not weights or sum(weights) <= 0:
        return 0
    point = rng.random() * sum(weights)
    running = 0.0
    for index, weight in enumerate(weights):
        running += weight
        if point <= running:
            return index
    return len(weights) - 1


def _sample_clock(clock_region: Mapping[str, Any], fallback: float,
                  spec: Mapping[str, Any], policy: Mapping[str, Any],
                  rng: random.Random) -> float:
    if not clock_region.get("active"):
        return _clip_value(fallback, spec)
    anchors = list(clock_region.get("anchors", []))
    weights = list(clock_region.get("weights", []))
    center = anchors[_weighted_choice_index(weights, rng)] if anchors else fallback
    low, high = map(float, clock_region["range"])
    jitter = (high - low) * float(policy["clock_jitter_fraction"])
    return _clip_value(min(high, max(low, center + rng.uniform(-jitter, jitter))), spec)


def _sample_hard_probe(constraints: Mapping[str, Mapping[str, Any]],
                       rng: random.Random) -> Dict[str, float]:
    """Sample one deterministic full-space probe directly from hard bounds."""
    row: Dict[str, float] = {}
    for name, spec in constraints.items():
        low, high = _bounds(spec)
        if spec.get("type") == "int":
            row[name] = rng.randint(int(math.ceil(low)), int(math.floor(high)))
        else:
            row[name] = rng.uniform(low, high)
    return row


def _full_probe_target_count(num_runs: int, policy: Mapping[str, Any],
                             legal_capacity: int, scope: str) -> int:
    """Return the hard full-space probe quota or fail before shaping a batch.

    ``full_probe_fraction`` expresses the desired mix, while
    ``full_probe_min_count`` prevents other protected roles from quietly reducing
    full-space coverage.  The latter is deliberately fail-closed: callers that use
    a small population must explicitly lower the policy rather than unknowingly run
    an exploration-free campaign.
    """
    capacity = max(0, int(legal_capacity))
    fraction = float(policy.get("full_probe_fraction", 0.0))
    minimum = policy.get("full_probe_min_count", 0)
    if isinstance(minimum, bool):
        raise ValueError("search_policy.full_probe_min_count must be an integer")
    try:
        minimum = int(minimum)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "search_policy.full_probe_min_count must be an integer") from exc
    if minimum < 0:
        raise ValueError("search_policy.full_probe_min_count must be non-negative")
    fractional = (
        max(1, int(round(max(0, int(num_runs)) * fraction)))
        if fraction > 0.0 and capacity else 0
    )
    requested = max(fractional, minimum)
    if requested > capacity:
        raise RuntimeError(
            f"{scope} cannot reserve full_probe_min_count={minimum}: only "
            f"{capacity} legal full-probe slots are available. Increase --runs "
            "or explicitly lower search_policy.full_probe_min_count.")
    return requested

def _apply_cts_quotas(rows: List[Dict[str, float]], modifiable: Sequence[int],
                      constraints: Mapping[str, Mapping[str, Any]],
                      policy: Mapping[str, Any], rng: random.Random) -> Dict[str, int]:
    indices = list(modifiable)
    if (not indices
            or not any(name in constraints for name in CTS_PARAMETERS)):
        return {"tns_100": 0, "local_window": 0}
    n_tns = 0
    n_local = min(
        len(indices), int(round(len(rows) * float(policy["cts_local_window_fraction"])))
    )
    size_window = policy["cts_cluster_size_window"]
    diameter_window = policy["cts_cluster_diameter_window"]
    for index in indices[-n_local:] if n_local else []:
        if "CTS_CLUSTER_SIZE" in constraints:
            value = rng.randint(int(math.ceil(size_window[0])), int(math.floor(size_window[1])))
            rows[index]["CTS_CLUSTER_SIZE"] = _clip_value(
                value, constraints["CTS_CLUSTER_SIZE"]
            )
        if "CTS_CLUSTER_DIAMETER" in constraints:
            value = rng.randint(
                int(math.ceil(diameter_window[0])), int(math.floor(diameter_window[1]))
            )
            rows[index]["CTS_CLUSTER_DIAMETER"] = _clip_value(
                value, constraints["CTS_CLUSTER_DIAMETER"]
            )
    return {"tns_100": n_tns, "local_window": n_local}


def _routing_focus_slot_quotas(
    num_runs: int,
    policy: Mapping[str, Any],
    *,
    pending_replays: int,
) -> Dict[str, Any]:
    """Apportion the complete focus batch; the incumbent occupies one replay slot."""
    names = ("routing_focus", "exact_replay", "full_probe")
    fractions = {
        "routing_focus": float(policy["routing_focus_fraction"]),
        "exact_replay": float(policy["exact_replay_fraction"]),
        "full_probe": float(policy["full_probe_fraction"]),
    }
    raw = {name: max(0, int(num_runs)) * fractions[name] for name in names}
    target = {name: int(math.floor(raw[name])) for name in names}
    remainder = max(0, int(num_runs)) - sum(target.values())
    order = sorted(names, key=lambda name: (-(raw[name] - target[name]), names.index(name)))
    for name in order[:remainder]:
        target[name] += 1

    # Slot 1 is the confirmed incumbent and is counted in the replay/control quota.
    # For tiny batches, preserve one pending replay and one focus experiment whenever
    # all three can coexist; probes yield first because they are least informative here.
    effective = dict(target)
    if num_runs > 0 and effective["exact_replay"] == 0:
        donors = sorted(
            ("full_probe", "routing_focus"),
            key=lambda name: (effective[name], fractions[name]), reverse=True)
        donor = next((name for name in donors if effective[name] > 0), None)
        if donor is not None:
            effective[donor] -= 1
            effective["exact_replay"] = 1
    small_batch_replay_override = False
    if (pending_replays > 0 and effective["exact_replay"] <= 1
            and effective["routing_focus"] >= 2):
        effective["routing_focus"] -= 1
        effective["exact_replay"] += 1
        small_batch_replay_override = True

    # A focus batch needs its incumbent plus at least one local experiment. The
    # remaining slots can satisfy the full-space floor by taking capacity from focus
    # first and replay controls second, never by silently dropping exploration.
    minimum_probe = int(policy.get("full_probe_min_count", 0))
    max_probe = max(0, int(num_runs) - 2)
    if minimum_probe > max_probe:
        raise RuntimeError(
            "ROUTING_FOCUS cannot reserve "
            f"full_probe_min_count={minimum_probe}: {num_runs} runs leave only "
            f"{max_probe} slots after the incumbent and one focus experiment. "
            "Increase --runs or explicitly lower search_policy.full_probe_min_count.")
    deficit = max(0, minimum_probe - int(effective["full_probe"]))
    for donor in ("routing_focus", "exact_replay"):
        # Retain an actual focus proposal and the clean incumbent/replay control.
        reducible = max(0, int(effective[donor]) - 1)
        moved = min(deficit, reducible)
        effective[donor] -= moved
        effective["full_probe"] += moved
        deficit -= moved
    if deficit:
        raise RuntimeError(
            "ROUTING_FOCUS cannot satisfy full_probe_min_count without removing "
            "the clean incumbent or every focus experiment")

    replay_capacity = max(0, effective["exact_replay"] - (1 if num_runs else 0))
    actual_pending_replays = min(max(0, int(pending_replays)), replay_capacity)
    replay_shortfall = replay_capacity - actual_pending_replays
    # Never inflate local focus beyond its configured quota just because a replay is
    # unavailable. Convert that unused experimental budget into global escape probes.
    actual = {
        "routing_focus": effective["routing_focus"],
        "exact_replay": (1 if num_runs else 0) + actual_pending_replays,
        "full_probe": effective["full_probe"] + replay_shortfall,
    }
    if sum(actual.values()) != max(0, int(num_runs)):
        raise RuntimeError(f"routing-focus slot apportionment failed: {actual}")
    return {
        "target": target,
        "effective_target": effective,
        "actual": actual,
        "pending_replay_count": actual_pending_replays,
        "replay_shortfall_to_probe": replay_shortfall,
        "small_batch_replay_override": small_batch_replay_override,
        "full_probe_min_count": minimum_probe,
    }


def shape_next_batch(
    candidate_batch: Sequence[Mapping[str, Any]],
    *,
    clean_history: Sequence[Mapping[str, Any]],
    resolved_history: Sequence[Mapping[str, Any]] = (),
    routing_history: Sequence[Mapping[str, Any]] = (),
    state: Mapping[str, Any],
    full_constraints: Mapping[str, Mapping[str, Any]],
    num_runs: int,
    seed: Any,
    policy_config: Optional[Mapping[str, Any]],
    routing_agentic: bool = False,
    routing_agentic_controller: Any = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Reshape an optimizer batch according to the shared deterministic policy.

    Every enabled-policy row contains every key in ``full_constraints``.  In routing
    focus, most rows freeze upstream parameters to several clean anchors, exact replay
    rows validate promising DRP children, and a small hard-range full probe remains.
    """
    policy = policy_for_context(
        policy_config, str(state.get("objective", "")),
        state.get("platform"), state.get("design"))
    if policy is None or not state.get("enabled", False):
        return [dict(row) for row in candidate_batch[:num_runs]], {
            "enabled": False, "mode": FULL_SEARCH, "stop_requested": False,
        }
    if num_runs <= 0:
        return [], {"enabled": True, "mode": state.get("mode"), "counts": {}}

    hard = _constraint_copy(full_constraints)
    routing_deferred = (
        state.get("mode") == ROUTING_FOCUS
        and not any(name in hard for name in ROUTING_PARAMETERS)
    )
    if routing_deferred:
        state = {**dict(state), "mode": FULL_SEARCH}
    effective, space_meta = build_search_space(
        hard, clean_history=clean_history, resolved_history=resolved_history,
        routing_history=routing_history, state=state, policy_config=policy,
    )
    rng = random.Random(_derive_seed(seed, state.get("current_iteration", 0),
                                     state.get("mode", FULL_SEARCH), "shape"))
    if routing_deferred:
        space_meta["routing_focus_deferred_to_post_cts"] = True
    anchors = _select_anchors(clean_history, state, hard, policy)
    routing_anchors = _select_routing_anchors(
        routing_history, resolved_history, state, hard, policy)
    focus_parent_ids = (
        _focus_parent_candidate_ids(
            routing_history, clean_history, state, hard, policy)
        if state.get("mode") == ROUTING_FOCUS else {}
    )
    fallback = anchors[0] if anchors else {}

    raw_candidates = list(candidate_batch[:num_runs])
    rows = [_complete_params(row, hard, fallback) for row in raw_candidates]
    slot_metadata: List[Dict[str, Any]] = []
    slot_details: List[Dict[str, Any]] = []
    for index, candidate in enumerate(raw_candidates):
        existing = _candidate_metadata(candidate)
        origin = str(existing.get("_candidate_origin") or "lhs")
        if origin not in _CANDIDATE_ORIGINS:
            origin = "lhs"
        slot_metadata.append(_slot_metadata(
            state, index + 1, origin,
            f"optimizer-input:{existing.get('_candidate_id') or index + 1}",
            existing=existing,
        ))
        slot_details.append({
            "source_slot": index + 1,
            "transformations": list(candidate.get("_gpr_shape_roles", []))
            if isinstance(candidate.get("_gpr_shape_roles"), Sequence)
            and not isinstance(candidate.get("_gpr_shape_roles"), (str, bytes))
            else [],
        })
    while len(rows) < num_runs:
        anchor = anchors[len(rows) % len(anchors)] if anchors else fallback
        index = len(rows)
        rows.append(_complete_params(anchor, hard, fallback))
        slot_metadata.append(_slot_metadata(
            state, index + 1, "exploit", f"anchor-fill:{index + 1}"))
        slot_details.append({
            "source_slot": None,
            "transformations": ["anchor_fill"],
        })

    # Slot 1 is always the confirmed clean incumbent. Slot 2 is reserved for the
    # strongest unconfirmed observed replay when one exists; maindriver protects it
    # through both DRP decisions so the replay reaches final reporting.
    slot_contexts: Dict[int, Dict[str, Any]] = {}
    clean_best = state.get("best_clean_replay") or {}
    if isinstance(clean_best, Mapping) and isinstance(clean_best.get("params"), Mapping):
        parent = _record_candidate_id(clean_best)
        rows[0] = _complete_params(clean_best["params"], hard, fallback)
        slot_metadata[0] = _slot_metadata(
            state, 1, "replay",
            f"clean-incumbent:{clean_best.get('signature') or 'best'}",
            parent=str(parent) if parent else None,
        )
        slot_details[0] = {
            "source_slot": None,
            "transformations": ["clean_incumbent_override"],
            "role": "clean_incumbent",
        }
        recipe = clean_best.get("config_recipe")
        if isinstance(recipe, Mapping) and isinstance(recipe.get("scoped_params"), Mapping):
            slot_contexts[0] = {
                "recipe_signature": str(
                    recipe.get("signature", recipe.get("recipe_signature", ""))),
                "scoped_params": dict(recipe["scoped_params"]),
                "sdc_sha256": recipe.get("sdc_sha256"),
                "role": "clean_incumbent",
            }

    pending = [item for item in state.get("pending_replays", [])
               if isinstance(item, Mapping) and isinstance(item.get("params"), Mapping)]
    front = min(num_runs, int(policy["front_elite_count"]))
    replay_target = min(
        len(pending), max(1 if pending else 0,
                          int(round(num_runs * float(policy["exact_replay_fraction"]))))
    )
    replay_indices: List[int] = []
    probe_indices: List[int] = []
    focus_indices: List[int] = []
    focus_control_indices: List[int] = []
    focus_experiment_indices: List[int] = []
    focus_experiment_families: List[str] = []
    missing_focus_experiment_families: List[str] = []
    hard_clock_indices: List[int] = []
    routing_quota: Dict[str, Any] = {}
    focus_meta: Dict[str, Any] = {
        "enabled": False,
        "counts": {"exact_anchor": 0, "agent2": 0, "novelty": 0},
    }

    if state.get("mode") == ROUTING_FOCUS:
        routing_quota = _routing_focus_slot_quotas(
            num_runs, policy, pending_replays=len(pending))
        pending_replay_count = int(routing_quota["pending_replay_count"])
        replay_indices = list(range(1, 1 + pending_replay_count))
        probe_count = int(routing_quota["actual"]["full_probe"])
        probe_indices = (list(range(num_runs - probe_count, num_runs))
                         if probe_count else [])
        for index in probe_indices:
            rows[index] = _sample_hard_probe(hard, rng)
            slot_metadata[index] = _slot_metadata(
                state, index + 1, "full_probe",
                f"routing-focus-full-probe:{index + 1}",
                parent=None,
            )
            slot_details[index] = {
                "source_slot": None,
                "transformations": ["whole_row_full_probe"],
                "role": "full_probe",
            }
        reserved = {0, *replay_indices, *probe_indices}
        focus_indices = [index for index in range(num_runs) if index not in reserved]
        if len(focus_indices) != int(routing_quota["actual"]["routing_focus"]):
            raise RuntimeError(
                "routing-focus slot layout disagrees with configured quota: "
                f"layout={len(focus_indices)}, quota={routing_quota['actual']}")

        proposals: List[Dict[str, Any]] = []
        try:
            from routing_focus import build_focus_proposals, params_signature
            excluded = []
            if rows:
                excluded.append(params_signature(
                    rows[0], int(policy["signature_decimals"])))
            for item in pending[:len(replay_indices)]:
                excluded.append(params_signature(
                    _complete_params(item["params"], hard, fallback),
                    int(policy["signature_decimals"])))
            proposals, focus_meta = build_focus_proposals(
                routing_history, hard, state, policy, len(focus_indices),
                _derive_seed(seed, state.get("current_iteration", 0), "routing-focus"),
                agentic_enabled=bool(routing_agentic),
                excluded_signatures=excluded,
                fallback_anchors=anchors,
                agentic_controller=routing_agentic_controller,
            )
        except Exception as exc:
            focus_meta = {
                "enabled": False,
                "reason": f"conditional_selector_failed:{exc}",
                "counts": {"exact_anchor": 0, "agent2": 0, "novelty": 0},
            }

        if proposals:
            experiment_candidates: Dict[str, Dict[str, List[int]]] = defaultdict(
                lambda: {"agent2": [], "novelty": []})
            exact_candidates: Dict[str, List[int]] = defaultdict(list)
            for index, proposal in zip(focus_indices, proposals):
                rows[index] = _complete_params(proposal["params"], hard, fallback)
                kind = str(proposal.get("kind") or "novelty")
                family = str(proposal.get("family") or "unknown")
                parent = (_record_candidate_id(proposal)
                          or focus_parent_ids.get(family))
                origin = {
                    "exact_anchor": "focus_exact",
                    "agent2": "focus_agent2",
                    "novelty": "focus_novelty",
                }.get(kind, "focus_novelty")
                slot_metadata[index] = _slot_metadata(
                    state, index + 1, origin,
                    f"routing-focus:{kind}:{family}:{index + 1}",
                    parent=str(parent) if parent else None,
                )
                slot_details[index] = {
                    "source_slot": None,
                    "transformations": ["routing_focus_override"],
                    "role": origin,
                    "family": family,
                    "kind": kind,
                }
                scoped = proposal.get("scoped_params")
                if (isinstance(scoped, Mapping)
                        and (proposal.get("recipe_signature")
                             or proposal.get("sdc_sha256"))):
                    slot_contexts[index] = {
                        "recipe_signature": str(proposal.get("recipe_signature", "")),
                        "scoped_params": dict(scoped),
                        "sdc_sha256": proposal.get("sdc_sha256"),
                        "role": "routing_focus",
                    }
                if kind == "exact_anchor":
                    focus_control_indices.append(index)
                    exact_candidates[family].append(index)
                elif kind in {"agent2", "novelty"}:
                    experiment_candidates[family][kind].append(index)

            anchor_families = [str(value) for value in focus_meta.get(
                "anchor_families", experiment_candidates.keys())]
            for family in dict.fromkeys(anchor_families):
                choices = experiment_candidates.get(family, {})
                selected = list(choices.get("agent2", [])) or list(
                    choices.get("novelty", []))
                if not selected:
                    exact = exact_candidates.get(family, [])
                    if not exact:
                        missing_focus_experiment_families.append(family)
                        continue
                    # A tight focus budget may contain only an exact control for a
                    # family. Convert that slot into a real local experiment rather
                    # than silently claiming family coverage from an unchanged row.
                    index = exact[0]
                    changed = False
                    for name in ROUTING_PARAMETERS:
                        if name not in hard:
                            continue
                        low, high = _bounds(hard[name])
                        span = high - low
                        if span <= 0:
                            continue
                        old_value = float(rows[index][name])
                        delta = max(
                            span * float(policy["routing_jitter_fraction"]) * 0.25,
                            span * 1.0e-4,
                        )
                        candidate = old_value + delta
                        if candidate > high:
                            candidate = old_value - delta
                        new_value = _clip_value(candidate, hard[name])
                        if abs(float(new_value) - old_value) <= 1.0e-12:
                            continue
                        rows[index][name] = new_value
                        changed = True
                        break
                    if not changed:
                        missing_focus_experiment_families.append(family)
                        continue
                    parent = str(slot_metadata[index]["_candidate_id"])
                    slot_metadata[index] = _slot_metadata(
                        state, index + 1, "focus_novelty",
                        f"routing-focus:promoted-novelty:{family}:{index + 1}",
                        parent=parent,
                    )
                    slot_details[index].update({
                        "role": "focus_novelty",
                        "kind": "novelty",
                    })
                    slot_details[index].setdefault("transformations", []).append(
                        "focus_exact_promoted_to_novelty")
                    focus_control_indices.remove(index)
                    counts = focus_meta.setdefault("counts", {})
                    counts["exact_anchor"] = max(
                        0, int(counts.get("exact_anchor", 0)) - 1)
                    counts["novelty"] = int(counts.get("novelty", 0)) + 1
                    selected = [index]
                index = selected[0]
                focus_experiment_indices.append(index)
                focus_experiment_families.append(family)
            if missing_focus_experiment_families:
                raise RuntimeError(
                    "ROUTING_FOCUS cannot allocate an Agent2/novelty experiment "
                    "for anchor family/families "
                    f"{sorted(set(missing_focus_experiment_families))}; "
                    f"focus_slots={len(focus_indices)}, "
                    f"anchor_families={len(set(anchor_families))}")
        else:
            # Fail-closed compatibility path: retain the previous paired-parent
            # deterministic behavior when no trusted routing lineage is available.
            upstream_keys = [name for name in hard if name not in ROUTING_PARAMETERS]
            fallback_experiments: Dict[str, List[int]] = defaultdict(list)
            for position, index in enumerate(focus_indices):
                anchor = anchors[position % len(anchors)] if anchors else fallback
                route_entry = (routing_anchors[position % len(routing_anchors)]
                               if routing_anchors else None)
                family = str((route_entry or {}).get("parent_family") or "")
                anchor_recipe = (
                    validate_recipe(anchor.get("_CONFIG_RECIPE"))
                    if isinstance(anchor, Mapping) else None)
                if not family and anchor_recipe is not None:
                    family = str(routing_parent_family(
                        anchor, anchor_recipe["scoped_params"],
                        anchor_recipe["sdc_sha256"],
                        decimals=int(policy["signature_decimals"]),
                    ) or "")
                if not family:
                    family = f"fallback-{position % max(1, len(anchors))}"
                if route_entry:
                    anchor = _complete_params(
                        route_entry["upstream_params"], hard, anchor)
                for name in upstream_keys:
                    rows[index][name] = _clip_value(anchor.get(name), hard[name])
                if route_entry:
                    for name in ROUTING_PARAMETERS:
                        if name not in hard:
                            continue
                        low, high = _bounds(hard[name])
                        value = route_entry["routing_params"][name]
                        if position >= len(routing_anchors):
                            jitter = (high - low) * float(policy["routing_jitter_fraction"])
                            value += rng.uniform(-jitter, jitter)
                        rows[index][name] = _clip_value(value, hard[name])
                parent = ((route_entry or {}).get("candidate_id")
                          or focus_parent_ids.get(family))
                slot_metadata[index] = _slot_metadata(
                    state, index + 1, "focus_novelty",
                    f"routing-focus:fallback-novelty:{family}:{index + 1}",
                    parent=str(parent) if parent else None,
                )
                slot_details[index] = {
                    "source_slot": None,
                    "transformations": ["routing_focus_fallback_override"],
                    "role": "focus_novelty",
                    "family": family,
                    "kind": "novelty",
                }
                fallback_experiments[family].append(index)
                context_recipe = None
                if route_entry:
                    scoped = route_entry.get("scoped_params")
                    if isinstance(scoped, Mapping) and route_entry.get("sdc_sha256"):
                        context_recipe = {
                            "scoped_params": dict(scoped),
                            "sdc_sha256": route_entry["sdc_sha256"],
                        }
                if context_recipe is None and isinstance(anchor, Mapping):
                    context_recipe = validate_recipe(anchor.get("_CONFIG_RECIPE"))
                if context_recipe is not None:
                    # rows[index] may contain a jittered route, so the anchor's old
                    # signature is never reusable. The final canonical pass re-signs
                    # replay this exact 10D row with its preserved parent context.
                    slot_contexts[index] = {
                        "recipe_signature": "",
                        "scoped_params": dict(context_recipe["scoped_params"]),
                        "sdc_sha256": context_recipe["sdc_sha256"],
                        "role": "routing_focus_fallback",
                    }
            for family, indices in fallback_experiments.items():
                if indices:
                    focus_experiment_indices.append(indices[0])
                    focus_experiment_families.append(family)
            required_fallback_families = {
                str(item.get("parent_family"))
                for item in routing_anchors
                if item.get("parent_family")
            }
            missing_fallback = sorted(
                required_fallback_families - set(fallback_experiments))
            if missing_fallback:
                missing_focus_experiment_families.extend(missing_fallback)
                raise RuntimeError(
                    "ROUTING_FOCUS fallback cannot cover routing anchor "
                    f"family/families {missing_fallback}; "
                    f"focus_slots={len(focus_indices)}, "
                    f"anchor_families={len(required_fallback_families)}")
        if not focus_indices:
            raise RuntimeError(
                "ROUTING_FOCUS has zero experiment slots; increase num_runs or "
                "reduce replay/probe quotas")
        if not focus_experiment_indices:
            raise RuntimeError(
                "ROUTING_FOCUS produced no Agent2/novelty experiment; refusing "
                "an exact-control-only focus batch")
    else:
        replay_pool = list(range(1, num_runs))
        replay_indices = replay_pool[:replay_target]

        # Preserve a deterministic whole-row exploration quota in FULL_SEARCH.
        # LHS/full-probe rows are already sampled from the hard search space; moving
        # one of those proposals into a protected tail slot retains its identity and
        # avoids spending another sample.  If the optimizer supplied no suitable
        # proposal, materialize a fresh hard-range probe for the missing slot.
        probe_pool = [
            index for index in range(num_runs)
            if index >= front and index not in replay_indices
        ]
        probe_count = _full_probe_target_count(
            num_runs, policy, len(probe_pool), "FULL_SEARCH")
        probe_indices = probe_pool[-probe_count:] if probe_count else []
        donor_indices = [
            index for index in probe_pool
            if index not in probe_indices
            and slot_metadata[index].get("_candidate_origin") in {"lhs", "full_probe"}
        ]
        for index in probe_indices:
            if slot_metadata[index].get("_candidate_origin") not in {
                    "lhs", "full_probe"}:
                if donor_indices:
                    donor = donor_indices.pop()
                    rows[index], rows[donor] = rows[donor], rows[index]
                    slot_metadata[index], slot_metadata[donor] = (
                        slot_metadata[donor], slot_metadata[index])
                    slot_details[index], slot_details[donor] = (
                        slot_details[donor], slot_details[index])
                    slot_details[index].setdefault("transformations", []).append(
                        "moved_to_full_probe_slot")
                else:
                    rows[index] = _sample_hard_probe(hard, rng)
                    slot_metadata[index] = _slot_metadata(
                        state, index + 1, "full_probe",
                        f"full-search-hard-probe:{index + 1}",
                        parent=None,
                    )
                    slot_details[index] = {
                        "source_slot": None,
                        "transformations": ["hard_probe_replacement"],
                    }
            if slot_metadata[index].get("_candidate_origin") == "lhs":
                # Promotion changes semantic provenance, so it must create a child
                # identity rather than relabel the original LHS candidate in place.
                parent = str(slot_metadata[index]["_candidate_id"])
                slot_metadata[index] = _slot_metadata(
                    state, index + 1, "full_probe",
                    f"full-search-lhs-probe:{parent}:slot{index + 1}",
                    parent=parent,
                )
                slot_details[index].setdefault("transformations", []).append(
                    "lhs_promoted_to_full_probe")
            slot_details[index].setdefault("transformations", []).append(
                "whole_row_full_probe")
            slot_details[index]["role"] = "full_probe"

        available = [index for index in range(front, num_runs)
                     if index not in replay_indices and index not in probe_indices]
        scored_shape_indices = {
            index for index in available
            if index < len(raw_candidates)
            and raw_candidates[index].get("_gpr_scored_effective_config") is True
        }
        shape_available = [
            index for index in available if index not in scored_shape_indices]
        # Most full-search clocks use the weighted region; the remainder stay hard-range probes.
        clock_region = space_meta.get("clock_region", {})
        local_clock_count = int(round(
            len(shape_available) * float(policy["clock_region_fraction"])
        ))
        for index in shape_available[:local_clock_count]:
            if CLOCK_PARAMETER in hard:
                rows[index][CLOCK_PARAMETER] = _sample_clock(
                    clock_region, rows[index][CLOCK_PARAMETER], hard[CLOCK_PARAMETER],
                    policy, rng,
                )
                slot_details[index].setdefault("transformations", []).append(
                    "clock_region_resample")
        hard_clock_indices = shape_available[local_clock_count:]
        if CLOCK_PARAMETER in hard:
            clock_low, clock_high = _bounds(hard[CLOCK_PARAMETER])
            for index in hard_clock_indices:
                rows[index][CLOCK_PARAMETER] = rng.uniform(clock_low, clock_high)
                slot_details[index].setdefault("transformations", []).append(
                    "clock_hard_resample")

    for index, item in zip(replay_indices, pending):
        parent = _record_candidate_id(item)
        rows[index] = _complete_params(item["params"], hard, fallback)
        replay_signature = (
            item.get("recipe_signature") or item.get("signature") or "unknown")
        slot_metadata[index] = _slot_metadata(
            state, index + 1, "replay",
            "config-replay:"
            f"{replay_signature}:iter{item.get('iteration', 'unknown')}:"
            f"run{item.get('run_id', 'unknown')}",
            parent=str(parent) if parent else None,
        )
        slot_details[index] = {
            "source_slot": None,
            "transformations": ["config_replay_override"],
            "role": "exact_replay",
        }
        recipe = item.get("config_recipe")
        if isinstance(recipe, Mapping) and isinstance(recipe.get("scoped_params"), Mapping):
            slot_details[index]["role"] = "config_replay"
            slot_contexts[index] = {
                "recipe_signature": str(
                    item.get("recipe_signature")
                    or recipe.get("signature", recipe.get("recipe_signature", ""))),
                "scoped_params": dict(recipe["scoped_params"]),
                "sdc_sha256": recipe.get("sdc_sha256"),
                "role": "config_replay",
                "origin_iteration": item.get("iteration"),
                "origin_run_id": item.get("run_id"),
                "reference_objective": item.get("objective"),
            }

    protected = (set(range(front)) | set(replay_indices) | set(probe_indices)
                 | set(focus_control_indices) | set(focus_experiment_indices))
    pre_scored_indices = {
        index for index, candidate in enumerate(raw_candidates)
        if candidate.get("_gpr_scored_effective_config") is True
    }
    cts_modifiable = [
        index for index in range(num_runs)
        if index not in protected and index not in pre_scored_indices
    ]
    if state.get("mode") == ROUTING_FOCUS:
        # Focus rows already inherit CTS from clean anchors; only full-space probes remain free.
        cts_modifiable = []
    expected_local_count = min(
        len(cts_modifiable),
        int(round(len(rows) * float(policy["cts_local_window_fraction"])))
    )
    expected_local_indices = (
        cts_modifiable[-expected_local_count:] if expected_local_count else [])
    cts_counts = _apply_cts_quotas(rows, cts_modifiable, hard, policy, rng)
    pre_local = sum(
        "pre_gpr_cts_local_window" in details.get("transformations", [])
        for details in slot_details
    )
    cts_counts["local_window"] += pre_local
    if "CTS_CLUSTER_SIZE" in hard or "CTS_CLUSTER_DIAMETER" in hard:
        for index in expected_local_indices:
            slot_details[index].setdefault("transformations", []).append(
                "cts_local_window_quota")

    # One final hard-bound pass protects against malformed candidate or history values.
    rows = [_complete_params(row, hard, fallback) for row in rows]
    config_replay_slots = []
    for index, payload in sorted(slot_contexts.items()):
        entry = dict(payload, run_id=index + 1)
        if not entry.get("recipe_signature"):
            if not entry.get("sdc_sha256"):
                raise RuntimeError(
                    f"slot {index + 1} has scoped floorplan context but no SDC identity")
            entry["recipe_signature"] = _scoped_execution_signature(
                rows[index], entry["scoped_params"], entry["sdc_sha256"])
        entry.pop("sdc_sha256", None)
        config_replay_slots.append(entry)

    protected_candidate_indices = sorted(set(focus_experiment_indices))
    protected_candidate_ids = [
        str(slot_metadata[index]["_candidate_id"])
        for index in protected_candidate_indices
    ]
    protected_candidate_families = list(dict.fromkeys(
        str(slot_details[index].get("family"))
        for index in protected_candidate_indices
        if slot_details[index].get("family")
    ))
    candidate_slots = []
    for index, (row, candidate_meta, details) in enumerate(
            zip(rows, slot_metadata, slot_details)):
        entry: Dict[str, Any] = {
            "run_id": index + 1,
            **candidate_meta,
            "parameter_signature": _param_signature(
                {name: row[name] for name in hard},
                int(policy["signature_decimals"]),
            ),
            "source_slot": details.get("source_slot"),
            "transformations": list(dict.fromkeys(
                details.get("transformations", []))),
            "role": details.get(
                "role", candidate_meta.get("_candidate_origin")),
            "_drp_rewrite_protected": index in protected_candidate_indices,
        }
        for key in ("family", "kind"):
            if details.get(key) is not None:
                entry[key] = details[key]
        candidate_slots.append(entry)

    # `_complete_params` intentionally emits only executable dimensions. Reattach
    # immutable proposal identity after the final hard-bound pass so downstream
    # selection can audit origin/parent without letting shaping create a new ID.
    for index, row in enumerate(rows):
        row.update(slot_metadata[index])
        if index in protected_candidate_indices:
            row["_drp_rewrite_protected"] = True

    plan = {
        "enabled": True,
        "mode": state.get("mode", FULL_SEARCH),
        "stop_requested": bool(state.get("stop_requested", False)),
        "counts": {
            "routing_focus": len(focus_indices),
            "routing_focus_exact": int(
                focus_meta.get("counts", {}).get("exact_anchor", 0)),
            "routing_focus_agent2": int(
                focus_meta.get("counts", {}).get("agent2", 0)),
            "routing_focus_novelty": int(
                focus_meta.get("counts", {}).get("novelty", 0)),
            "exact_replay": len(replay_indices),
            "replay_control_total": (
                int(routing_quota.get("actual", {}).get("exact_replay", 0))
                if state.get("mode") == ROUTING_FOCUS else len(replay_indices)),
            "full_probe": len(probe_indices),
            "clock_hard_probe": (
                len(hard_clock_indices) if state.get("mode") != ROUTING_FOCUS else 0),
            "cts_tns_100": cts_counts["tns_100"],
            "cts_local_window": cts_counts["local_window"],
        },
        "full_probe_min_count": int(policy.get("full_probe_min_count", 0)),
        "replay_signatures": [
            item.get("recipe_signature", item.get("signature"))
            for item in pending[:len(replay_indices)]
        ],
        "protected_replay_slots": [index + 1 for index in replay_indices],
        "protected_config_replay_slots": [
            item["run_id"] for item in config_replay_slots
            if item.get("role") == "config_replay"
        ],
        "config_replay_slots": config_replay_slots,
        "candidate_slots": candidate_slots,
        "protected_probe_slots": [index + 1 for index in probe_indices],
        "protected_focus_control_slots": [index + 1 for index in focus_control_indices],
        "protected_focus_experiment_slots": [
            index + 1 for index in protected_candidate_indices],
        "protected_candidate_slots": [
            index + 1 for index in protected_candidate_indices],
        "protected_candidate_ids": protected_candidate_ids,
        "protected_candidate_families": protected_candidate_families,
        "missing_focus_experiment_families": list(dict.fromkeys(
            missing_focus_experiment_families)),
        "anchor_count": len(anchors),
        "routing_anchor_count": len(routing_anchors),
        "routing_focus_model": focus_meta,
        "routing_focus_quota": routing_quota,
        "search_space": space_meta,
        "seed": _derive_seed(seed, state.get("current_iteration", 0),
                             state.get("mode", FULL_SEARCH), "shape"),
    }
    return rows, plan


def shape_stage_params(
    candidate_batch: Sequence[Mapping[str, Any]],
    *,
    stage: str,
    objective: str,
    platform: str,
    design: str,
    constraints: Mapping[str, Mapping[str, Any]],
    seed: Any,
    policy_config: Optional[Mapping[str, Any]],
) -> Tuple[List[Dict[str, float]], Dict[str, Any]]:
    """Apply evidence-backed CTS quotas to the final intra-iteration batch."""
    rows = [dict(row) for row in candidate_batch]
    policy = policy_for_context(policy_config, objective, platform, design)
    if policy is None or stage != "cts" or not rows:
        return rows, {"enabled": False, "stage": stage}
    completed = [_complete_params(row, constraints) for row in rows]
    rng = random.Random(_derive_seed(seed, platform, design, stage, "stage-shape"))
    counts = _apply_cts_quotas(
        completed, list(range(len(completed))), constraints, policy, rng,
    )
    completed = [_complete_params(row, constraints) for row in completed]
    return completed, {
        "enabled": True,
        "stage": stage,
        "counts": counts,
        "seed": _derive_seed(seed, platform, design, stage, "stage-shape"),
    }
