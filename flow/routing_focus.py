"""Parent-conditioned routing proposals for ROUTING_FOCUS.

The final routing knobs are only causal relative to the upstream checkpoint that
they mutate.  This module keeps that parent/child pairing explicit, optionally uses
one shared Inspect/Model configuration plus one cross-family Selection around
independent two-dimensional family GPs, and otherwise falls back to deterministic
maximin novelty inside an adaptive trust region.

NumPy/sklearn are optional.  Import or model failures deliberately return the
deterministic fallback so the campaign never depends on the surrogate being usable.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
import warnings
from collections import defaultdict
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from common import POWER_VIOLATION_PENALTY, tns_eval_obj
from config_recipe import routing_parent_family, validate_recipe


ROUTING_PARAMETERS = ("PIN_LAYER_ADJUST", "ABOVE_LAYER_ADJUST")
FLOORPLAN_CONTEXT_PARAMETERS = {
    "PIN_LAYER_ADJUST": "FLOORPLAN_PIN_LAYER_ADJUST",
    "ABOVE_LAYER_ADJUST": "FLOORPLAN_ABOVE_LAYER_ADJUST",
}


def _json_safe(value: Any) -> Any:
    """Convert inspection/model diagnostics into persistable batch-plan data."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "tolist"):
        return _json_safe(value.tolist())
    if hasattr(value, "item"):
        try:
            return _json_safe(value.item())
        except Exception:
            pass
    return str(value)


def _finite(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _bounds(spec: Mapping[str, Any]) -> Tuple[float, float]:
    values = spec.get("range", ())
    if not isinstance(values, Sequence) or len(values) != 2:
        raise ValueError(f"routing constraint has no [low, high] range: {spec}")
    low, high = float(values[0]), float(values[1])
    if not math.isfinite(low) or not math.isfinite(high) or low >= high:
        raise ValueError(f"invalid routing range {values}")
    return low, high


def _clip(value: Any, spec: Mapping[str, Any]) -> float:
    low, high = _bounds(spec)
    number = _finite(value)
    if number is None:
        number = (low + high) / 2.0
    number = min(high, max(low, number))
    return int(round(number)) if spec.get("type") == "int" else float(number)


def routing_family(params: Mapping[str, Any], decimals: int = 6,
                   scoped_params: Optional[Mapping[str, Any]] = None,
                   sdc_sha256: Any = None) -> Optional[str]:
    """Stable identity of the upstream parent seen by a routing mutation."""
    if scoped_params is None and isinstance(params.get("_FLOORPLAN_CONTEXT"), Mapping):
        scoped_params = params["_FLOORPLAN_CONTEXT"]
    if sdc_sha256 is None:
        sdc_sha256 = params.get("_SDC_RECIPE_SHA256")
    return routing_parent_family(
        params, scoped_params, sdc_sha256, decimals=decimals)


def _route(params: Mapping[str, Any], constraints: Mapping[str, Mapping[str, Any]]) -> Optional[Dict[str, float]]:
    if not all(name in params and name in constraints for name in ROUTING_PARAMETERS):
        return None
    return {name: _clip(params[name], constraints[name]) for name in ROUTING_PARAMETERS}


def _normalized_route(params: Mapping[str, Any],
                      constraints: Mapping[str, Mapping[str, Any]]) -> Tuple[float, float]:
    values = []
    for name in ROUTING_PARAMETERS:
        low, high = _bounds(constraints[name])
        values.append((_clip(params.get(name), constraints[name]) - low) / (high - low))
    return float(values[0]), float(values[1])


def _complete(upstream: Mapping[str, Any], route: Mapping[str, Any],
              constraints: Mapping[str, Mapping[str, Any]]) -> Dict[str, float]:
    merged = dict(upstream)
    merged.update(route)
    return {name: _clip(merged.get(name), spec) for name, spec in constraints.items()}


def _signature(params: Mapping[str, Any], decimals: int = 6) -> str:
    payload = json.dumps(
        {str(k): round(float(v), decimals) for k, v in sorted(params.items())},
        sort_keys=True, separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("ascii")).hexdigest()


def params_signature(params: Mapping[str, Any], decimals: int = 6) -> str:
    """Public complete-config signature used to deduplicate protected slots."""
    return _signature(params, decimals)


def _static_recipe(record: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    """Only a validated static recipe may seed a from-scratch routing proposal."""
    return validate_recipe(record.get("config_recipe"))


def prepare_observations(
    routing_history: Sequence[Mapping[str, Any]],
    objective_context: Mapping[str, Any],
    constraints: Mapping[str, Mapping[str, Any]],
    *,
    decimals: int = 6,
) -> List[Dict[str, Any]]:
    """Return trusted, CP0-comparable, power-feasible routing deltas."""
    power_budget = objective_context.get("power_budget")
    power_base = objective_context.get("power_base")
    observations: List[Dict[str, Any]] = []
    seen = set()
    for record in routing_history:
        if record.get("trusted") is False or record.get("stage", "routing") != "routing":
            continue
        recipe = _static_recipe(record)
        if recipe is None:
            continue
        source = record.get("source_effective_params")
        effective = record.get("effective_params")
        if not isinstance(source, Mapping) or not isinstance(effective, Mapping):
            continue
        route = _route(effective, constraints)
        if route is None:
            continue
        source_metrics = record.get("source_metrics")
        child_metrics = record.get("child_metrics", record.get("metrics"))
        if not isinstance(source_metrics, Mapping) or not isinstance(child_metrics, Mapping):
            continue
        if (source_metrics.get("tns_source") != "cp0_eval"
                or child_metrics.get("tns_source") != "cp0_eval"):
            continue
        parent_objective = tns_eval_obj(source_metrics, power_budget, power_base)
        child_objective = tns_eval_obj(child_metrics, power_budget, power_base)
        if (parent_objective is None or child_objective is None
                or parent_objective >= POWER_VIOLATION_PENALTY
                or child_objective >= POWER_VIOLATION_PENALTY):
            continue
        scoped = dict(recipe["scoped_params"])
        sdc_sha256 = recipe["sdc_sha256"]
        family = routing_family(source, decimals, scoped, sdc_sha256)
        if not family:
            continue
        point = _normalized_route(route, constraints)
        key = (str(family), round(point[0], decimals), round(point[1], decimals),
               int(record.get("iteration", 0)))
        if key in seen:
            continue
        seen.add(key)
        observations.append({
            "family": str(family),
            "iteration": int(record.get("iteration", 0)),
            "parent_objective": float(parent_objective),
            "child_objective": float(child_objective),
            "delta": float(child_objective - parent_objective),
            "route": route,
            "point": point,
            "upstream_params": dict(source),
            "effective_params": dict(effective),
            "scoped_params": scoped,
            "sdc_sha256": sdc_sha256,
            "record": record,
        })
    return observations


def select_anchors(observations: Sequence[Mapping[str, Any]], max_anchors: int) -> List[Dict[str, Any]]:
    """Choose at most one best routing child for each distinct parent family."""
    grouped: Dict[str, List[Mapping[str, Any]]] = defaultdict(list)
    for observation in observations:
        grouped[str(observation["family"])].append(observation)
    anchors = []
    for family, rows in grouped.items():
        best = min(rows, key=lambda row: (
            float(row["child_objective"]), float(row["delta"]),
            int(row.get("iteration", 0))))
        anchors.append({
            "family": family,
            "upstream_params": dict(best["upstream_params"]),
            "routing_params": dict(best["route"]),
            "effective_params": dict(best["effective_params"]),
            "scoped_params": dict(best.get("scoped_params") or {}),
            "sdc_sha256": best.get("sdc_sha256"),
            "parent_objective": float(best["parent_objective"]),
            "child_objective": float(best["child_objective"]),
            "delta": float(best["delta"]),
        })
    anchors.sort(key=lambda item: (item["child_objective"], item["delta"], item["family"]))
    return anchors[:max(0, int(max_anchors))]


def update_trust_regions(
    previous: Mapping[str, Any],
    observations: Sequence[Mapping[str, Any]],
    current_iteration: int,
    policy: Mapping[str, Any],
) -> Dict[str, Dict[str, Any]]:
    """Expand on significant improvement and shrink after a new stagnant batch."""
    initial = float(policy["routing_jitter_fraction"])
    minimum = float(policy["routing_trust_min_fraction"])
    maximum = float(policy["routing_trust_max_fraction"])
    expand = float(policy["routing_trust_expand_factor"])
    shrink = float(policy["routing_trust_shrink_factor"])
    grouped: Dict[str, List[Mapping[str, Any]]] = defaultdict(list)
    for observation in observations:
        grouped[str(observation["family"])].append(observation)

    result = {str(k): dict(v) for k, v in previous.items() if isinstance(v, Mapping)}
    for family, rows in grouped.items():
        best_delta = min(float(row["delta"]) for row in rows)
        latest = max(int(row.get("iteration", 0)) for row in rows)
        old = result.get(family)
        if not old:
            result[family] = {
                "fraction": min(maximum, max(minimum, initial)),
                "best_delta": best_delta,
                "last_observation_iteration": latest,
                "last_updated_iteration": int(current_iteration),
                "stagnation": 0,
                "reason": "initialized",
            }
            continue
        radius = min(maximum, max(minimum, float(old.get("fraction", initial))))
        old_latest = int(old.get("last_observation_iteration", 0))
        old_best = _finite(old.get("best_delta"))
        stagnation = int(old.get("stagnation", 0))
        reason = "unchanged_no_new_observation"
        if latest > old_latest:
            threshold = (float(policy["significant_improvement_abs"])
                         if old_best is None else max(
                             float(policy["significant_improvement_abs"]),
                             abs(old_best) * float(policy["significant_improvement_rel"]),
                         ))
            improved = old_best is None or best_delta < old_best - threshold
            if improved:
                radius = min(maximum, radius * expand)
                stagnation = 0
                reason = "expanded_after_improvement"
            else:
                radius = max(minimum, radius * shrink)
                stagnation += 1
                reason = "shrunk_after_stagnation"
        result[family] = {
            "fraction": radius,
            "best_delta": min(best_delta, old_best) if old_best is not None else best_delta,
            "last_observation_iteration": max(latest, old_latest),
            "last_updated_iteration": int(current_iteration),
            "stagnation": stagnation,
            "reason": reason,
        }
    return result


def _halton(index: int, base: int) -> float:
    result, fraction = 0.0, 1.0
    while index > 0:
        fraction /= base
        result += fraction * (index % base)
        index //= base
    return result


def _candidate_routes(anchor: Mapping[str, Any], count: int,
                      constraints: Mapping[str, Mapping[str, Any]],
                      radius_fraction: float, offset: int) -> List[Dict[str, float]]:
    routes = []
    center = anchor["routing_params"]
    for position in range(max(1, count)):
        index = offset + position + 1
        route = {}
        for name, unit in zip(ROUTING_PARAMETERS, (_halton(index, 2), _halton(index, 3))):
            low, high = _bounds(constraints[name])
            radius = (high - low) * radius_fraction
            route[name] = _clip(float(center[name]) + (2.0 * unit - 1.0) * radius,
                                constraints[name])
        routes.append(route)
    return routes


def _fit_family_model(
    observations: Sequence[Mapping[str, Any]],
    policy: Mapping[str, Any],
    *,
    model_config: Optional[Mapping[str, Any]] = None,
    feature_weights: Optional[Sequence[float]] = None,
) -> Dict[str, Any]:
    unique: Dict[Tuple[float, float], Mapping[str, Any]] = {}
    for row in observations:
        point = tuple(float(value) for value in row["point"])
        if point not in unique or float(row["delta"]) < float(unique[point]["delta"]):
            unique[point] = row
    rows = list(unique.values())
    minimum = int(policy["routing_model_min_family_observations"])
    full = max(minimum, int(policy["routing_model_full_confidence_observations"]))
    if len(rows) < minimum:
        return {"ready": False, "reason": "insufficient_family_observations",
                "n_observations": len(rows), "confidence": 0.0}
    try:
        import numpy as np
        from sklearn.gaussian_process import GaussianProcessRegressor
        from sklearn.gaussian_process.kernels import (
            ConstantKernel, Matern, RBF, WhiteKernel)
        from sklearn.model_selection import LeaveOneOut
        from sklearn.preprocessing import MinMaxScaler, RobustScaler, StandardScaler
    except Exception as exc:
        return {"ready": False, "reason": f"model_dependency_unavailable:{exc}",
                "n_observations": len(rows), "confidence": 0.0}

    X = np.asarray([row["point"] for row in rows], dtype=float)
    y = np.asarray([row["delta"] for row in rows], dtype=float)
    baseline_errors, model_errors = [], []
    config = dict(model_config or {})
    kernel_type = str(config.get("kernel_type", "matern")).lower()
    preprocessing = str(config.get("preprocessing", "none")).lower()
    weights = np.asarray(feature_weights if feature_weights is not None else [1.0, 1.0],
                         dtype=float)
    if weights.shape != (2,) or not np.all(np.isfinite(weights)) or np.max(weights) <= 0:
        weights = np.ones(2, dtype=float)
    weights = weights / max(float(np.mean(weights)), 1e-9)
    length_scales = np.clip(0.2 / np.clip(weights, 0.25, 4.0), 0.05, 0.8)

    def make_scaler():
        if preprocessing == "robust":
            return RobustScaler()
        if preprocessing == "standard":
            return StandardScaler()
        if preprocessing == "minmax":
            return MinMaxScaler()
        return None

    def make_model(train_y):
        base_kernel = (
            RBF(length_scale=length_scales,
                length_scale_bounds=[(1e-2, 2.0), (1e-2, 2.0)])
            if kernel_type == "rbf" else
            Matern(length_scale=length_scales,
                   length_scale_bounds=[(1e-2, 2.0), (1e-2, 2.0)], nu=2.5)
        )
        spread = float(np.std(train_y))
        kernel = (ConstantKernel(1.0, (1e-3, 1e3)) * base_kernel
                  + WhiteKernel(noise_level=max(1e-6, spread * 1e-3),
                                noise_level_bounds=(1e-8, max(1e-6, spread + 1e-6))))
        return GaussianProcessRegressor(
            kernel=kernel, normalize_y=True, alpha=1e-8,
            n_restarts_optimizer=0, random_state=0)

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            for train_idx, test_idx in LeaveOneOut().split(X):
                train_y = y[train_idx]
                baseline = float(np.median(train_y))
                scaler = make_scaler()
                train_X = scaler.fit_transform(X[train_idx]) if scaler is not None else X[train_idx]
                test_X = scaler.transform(X[test_idx]) if scaler is not None else X[test_idx]
                model = make_model(train_y)
                model.fit(train_X, train_y)
                prediction = float(model.predict(test_X)[0])
                truth = float(y[test_idx][0])
                baseline_errors.append(abs(truth - baseline))
                model_errors.append(abs(truth - prediction))
    except Exception as exc:
        return {"ready": False, "reason": f"cross_validation_failed:{exc}",
                "n_observations": len(rows), "confidence": 0.0}

    baseline_mae = float(sum(baseline_errors) / len(baseline_errors))
    model_mae = float(sum(model_errors) / len(model_errors))
    if baseline_mae <= 1e-12:
        return {"ready": False, "reason": "constant_family_response",
                "n_observations": len(rows), "confidence": 0.0,
                "cv_mae": model_mae, "baseline_mae": baseline_mae}
    improvement = 1.0 - model_mae / baseline_mae
    if improvement < float(policy["routing_model_min_cv_improvement"]):
        return {"ready": False, "reason": "cv_does_not_beat_anchor_median",
                "n_observations": len(rows), "confidence": 0.0,
                "cv_mae": model_mae, "baseline_mae": baseline_mae,
                "cv_improvement": improvement}
    count_confidence = min(1.0, max(0.0, (len(rows) - minimum + 1) / (full - minimum + 1)))
    try:
        scaler = make_scaler()
        fit_X = scaler.fit_transform(X) if scaler is not None else X
        model = make_model(y)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            model.fit(fit_X, y)
    except Exception as exc:
        return {"ready": False, "reason": f"final_fit_failed:{exc}",
                "n_observations": len(rows), "confidence": 0.0}
    return {
        "ready": True,
        "reason": "ready",
        "model": model,
        "scaler": scaler,
        "X": X,
        "y": y,
        "model_config": {
            "kernel_type": kernel_type,
            "preprocessing": preprocessing,
        },
        "n_observations": len(rows),
        "confidence": count_confidence,
        "cv_mae": model_mae,
        "baseline_mae": baseline_mae,
        "cv_improvement": improvement,
    }


def _score_routes(model_info: Mapping[str, Any], routes: Sequence[Mapping[str, Any]],
                  constraints: Mapping[str, Mapping[str, Any]], acquisition: str) -> List[float]:
    if not routes:
        return []
    import numpy as np
    from modelfuncs import create_acquisition_function
    X = np.asarray([_normalized_route(route, constraints) for route in routes], dtype=float)
    scaler = model_info.get("scaler")
    if scaler is not None:
        X = scaler.transform(X)
    mu, std = model_info["model"].predict(X, return_std=True)
    function = create_acquisition_function(acquisition)
    scores = np.asarray(function(mu, std, float(np.min(model_info["y"]))), dtype=float)
    return [float(value) for value in scores]


def _route_uncertainties(
    model_info: Mapping[str, Any],
    routes: Sequence[Mapping[str, Any]],
    constraints: Mapping[str, Mapping[str, Any]],
) -> List[float]:
    """Return candidate uncertainty for the shared cross-family Selection stage."""
    if not routes:
        return []
    import numpy as np
    X = np.asarray([_normalized_route(route, constraints) for route in routes], dtype=float)
    scaler = model_info.get("scaler")
    if scaler is not None:
        X = scaler.transform(X)
    _, std = model_info["model"].predict(X, return_std=True)
    return [float(value) for value in std]


def _route_distance(left: Mapping[str, Any], right: Mapping[str, Any],
                    constraints: Mapping[str, Mapping[str, Any]]) -> float:
    a, b = _normalized_route(left, constraints), _normalized_route(right, constraints)
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)


def _novelty_pick(anchor: Mapping[str, Any], candidates: Sequence[Mapping[str, Any]],
                  existing: Sequence[Mapping[str, Any]],
                  constraints: Mapping[str, Mapping[str, Any]]) -> Optional[Dict[str, float]]:
    if not candidates:
        return None
    family = str(anchor["family"])
    relevant = [item["route"] if "route" in item else item
                for item in existing if str(item.get("family", family)) == family]
    if not relevant:
        return dict(candidates[0])
    return dict(max(candidates, key=lambda route: min(
        _route_distance(route, other, constraints) for other in relevant)))


def _joint_agentic_summary(
    observations: Sequence[Mapping[str, Any]],
    anchors: Sequence[Mapping[str, Any]],
    state: Mapping[str, Any],
    policy: Mapping[str, Any],
) -> Dict[str, Any]:
    grouped: Dict[str, List[Mapping[str, Any]]] = defaultdict(list)
    for row in observations:
        grouped[str(row["family"])].append(row)
    family_summary = {}
    for anchor in anchors:
        family = str(anchor["family"])
        rows = grouped.get(family, [])
        deltas = sorted(float(row["delta"]) for row in rows)
        family_summary[family] = {
            "n_observations": len(rows),
            "n_unique_points": len({tuple(row["point"]) for row in rows}),
            "best_delta": min(deltas) if deltas else None,
            "median_delta": deltas[len(deltas) // 2] if deltas else None,
            "trust_radius": float(
                ((state.get("routing_trust_regions", {}).get(family, {}) or {}).get(
                    "fraction", policy["routing_jitter_fraction"])),
            ),
        }
    return {
        "stage": "routing_focus",
        "parameter_names": list(ROUTING_PARAMETERS),
        "n_observations": len(observations),
        "n_anchor_families": len(anchors),
        "families": family_summary,
        "model_gate": {
            "min_total_observations": int(policy["routing_model_min_total_observations"]),
            "min_family_observations": int(policy["routing_model_min_family_observations"]),
            "min_cv_improvement": float(policy["routing_model_min_cv_improvement"]),
        },
    }


def _run_joint_inspection(
    observations: Sequence[Mapping[str, Any]],
    inspect_config: Mapping[str, Any],
) -> Dict[str, Any]:
    """Run one numerical inspection over all families; family ids stay in the report."""
    grouped: Dict[str, List[Mapping[str, Any]]] = defaultdict(list)
    for row in observations:
        grouped[str(row["family"])].append(row)
    result: Dict[str, Any] = {
        "feature_names": list(ROUTING_PARAMETERS),
        "family_counts": {family: len(rows) for family, rows in grouped.items()},
    }
    if len(observations) < 3:
        return result
    try:
        import numpy as np
        from inspectfuncs import inspect_data_distribution, inspect_data_structure

        X = np.asarray([row["point"] for row in observations], dtype=float)
        y = np.asarray([row["delta"] for row in observations], dtype=float)
        distribution = inspect_data_distribution(X, y)
        structure = inspect_data_structure(X, y, config={
            "n_clusters": min(
                max(2, int(inspect_config.get("n_clusters", 4))), len(X)),
            "correlation_threshold": min(
                1.0, max(0.0, float(inspect_config.get("correlation_threshold", 0.3)))),
            "n_neighbors": min(20, len(X) - 1),
            "perplexity": min(30, max(2, len(X) // 2)),
        })
        recommendations = (
            structure.get("model_recommendations", {})
            if isinstance(structure, Mapping) else {})
        weights = recommendations.get("feature_weights")
        try:
            weights = [float(value) for value in weights]
            if len(weights) != len(ROUTING_PARAMETERS):
                weights = None
        except (TypeError, ValueError):
            weights = None
        result.update({
            "distribution": {
                key: value for key, value in distribution.items()
                if not str(key).startswith("feature_")},
            "structure": structure,
            "feature_weights": weights,
        })
    except Exception as exc:
        result["inspection_error"] = str(exc)
    return result


def _validated_model_config(
    configured: Optional[Mapping[str, Any]],
    policy: Mapping[str, Any],
) -> Dict[str, Any]:
    raw = dict(configured or {})
    kernel = str(raw.get("kernel_type", "matern")).lower()
    preprocessing = str(raw.get("preprocessing", "none")).lower()
    acquisition = str(raw.get("acquisition", policy.get("routing_acquisition", "ei"))).lower()
    if kernel not in {"matern", "rbf"}:
        kernel = "matern"
    if preprocessing not in {"robust", "standard", "minmax", "none"}:
        preprocessing = "none"
    if acquisition not in {"ei", "ucb", "pi", "augmented_ei"}:
        acquisition = str(policy.get("routing_acquisition", "ei"))
    explore = raw.get("explore_frac")
    try:
        explore = None if explore is None else min(1.0, max(0.0, float(explore)))
    except (TypeError, ValueError):
        explore = None
    return {
        "kernel_type": kernel,
        "preprocessing": preprocessing,
        "acquisition": acquisition,
        "explore_frac": explore,
    }


def _validated_selection_config(
    configured: Optional[Mapping[str, Any]],
    policy: Mapping[str, Any],
) -> Dict[str, Any]:
    raw = dict(configured or {})
    allocation = str(raw.get("family_allocation", "confidence")).lower()
    if allocation not in {"balanced", "confidence", "quality"}:
        allocation = "confidence"

    def bounded(name: str, default: float) -> float:
        try:
            return min(1.0, max(0.0, float(raw.get(name, default))))
        except (TypeError, ValueError):
            return default

    return {
        "family_allocation": allocation,
        "quality_weight": bounded("quality_weight", 1.0),
        "uncertainty_bonus": bounded("uncertainty_bonus", 0.0),
        "diversity_weight": bounded(
            "diversity_weight", float(policy["routing_agentic_diversity_weight"])),
        "family_cap": bounded(
            "family_cap", float(policy["routing_agentic_family_cap"])),
    }


def _prediction_landscape(
    candidates: Sequence[Mapping[str, Any]],
    models: Mapping[str, Mapping[str, Any]],
) -> Dict[str, Any]:
    def stats(values: Sequence[float]) -> Dict[str, Optional[float]]:
        clean = [float(value) for value in values if math.isfinite(float(value))]
        if not clean:
            return {"min": None, "mean": None, "max": None}
        return {
            "min": min(clean),
            "mean": sum(clean) / len(clean),
            "max": max(clean),
        }

    grouped: Dict[str, List[Mapping[str, Any]]] = defaultdict(list)
    for item in candidates:
        grouped[str(item["family"])].append(item)
    return {
        "n_candidates": len(candidates),
        "families": {
            family: {
                "n_candidates": len(rows),
                "model_confidence": float(models[family].get("confidence", 0.0)),
                "acquisition_score": stats([row["score"] for row in rows]),
                "raw_acquisition": stats([row.get("raw_score", row["score"])
                                           for row in rows]),
                "uncertainty": stats([row.get("uncertainty", 0.0) for row in rows]),
            }
            for family, rows in grouped.items()
        },
    }


def build_focus_proposals(
    routing_history: Sequence[Mapping[str, Any]],
    constraints: Mapping[str, Mapping[str, Any]],
    state: Mapping[str, Any],
    policy: Mapping[str, Any],
    focus_count: int,
    seed: Any,
    *,
    agentic_enabled: bool,
    excluded_signatures: Sequence[str] = (),
    fallback_anchors: Sequence[Mapping[str, Any]] = (),
    agentic_controller: Any = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Build exact-control, conditional-Agent2, and maximin-novelty rows."""
    if focus_count <= 0:
        return [], {"enabled": True, "counts": {"exact": 0, "agent2": 0, "novelty": 0}}
    observations = prepare_observations(
        routing_history, state.get("objective_context", {}), constraints,
        decimals=int(policy["signature_decimals"]))
    anchors = select_anchors(observations, int(policy["anchor_count"]))
    evidence_source = "trusted_routing_lineage"
    if not anchors:
        # Cold-start fallback: clean full-flow anchors are valid complete parents,
        # even though they provide no paired routing delta for model fitting yet.
        # They seed deterministic local novelty without inventing pseudo-labels.
        seen_families = set()
        for params in fallback_anchors:
            recipe = validate_recipe(params.get("_CONFIG_RECIPE"))
            if recipe is None:
                continue
            scoped = dict(recipe["scoped_params"])
            sdc_sha256 = recipe["sdc_sha256"]
            family = routing_family(
                params, int(policy["signature_decimals"]), scoped, sdc_sha256)
            route = _route(params, constraints)
            if not family or route is None or family in seen_families:
                continue
            seen_families.add(family)
            anchors.append({
                "family": family,
                "upstream_params": {
                    key: value for key, value in params.items()
                    if key != "_CONFIG_RECIPE"
                },
                "routing_params": route,
                "effective_params": {
                    key: value for key, value in params.items()
                    if key != "_CONFIG_RECIPE"
                },
                "scoped_params": scoped,
                "sdc_sha256": sdc_sha256,
            })
            if len(anchors) >= int(policy["anchor_count"]):
                break
        evidence_source = "clean_anchor_seed"
    if not anchors:
        return [], {"enabled": False, "reason": "no_routing_or_clean_anchor",
                    "counts": {"exact": 0, "agent2": 0, "novelty": 0}}

    rng_seed = int(hashlib.sha256(str(seed).encode("utf-8")).hexdigest()[:16], 16)
    excluded = set(excluded_signatures)
    selected: List[Dict[str, Any]] = []
    by_family: Dict[str, List[Mapping[str, Any]]] = defaultdict(list)
    for row in observations:
        by_family[str(row["family"])].append(row)

    shared_model_config = _validated_model_config(None, policy)
    selection_config = _validated_selection_config(None, policy)
    feature_weights: Optional[Sequence[float]] = None
    agentic_meta: Dict[str, Any] = {
        "enabled": bool(agentic_enabled),
        "configured": False,
        "reason": "controller_not_requested" if not agentic_enabled else "controller_unavailable",
        "tool_requests": {"inspect": 0, "model": 0, "selection": 0},
        "tool_calls": {"inspect": 0, "model": 0, "selection": 0},
        "tool_configs_applied": {"inspect": 0, "model": 0, "selection": 0},
    }
    family_can_fit = any(
        len({tuple(row["point"]) for row in by_family[anchor["family"]]})
        >= int(policy["routing_model_min_family_observations"])
        for anchor in anchors
    )
    controller_eligible = bool(
        agentic_enabled and agentic_controller is not None and family_can_fit
        and len(observations) >= int(policy["routing_model_min_total_observations"])
    )
    if controller_eligible:
        try:
            configured = agentic_controller.configure(
                summary=_joint_agentic_summary(observations, anchors, state, policy),
                inspection_runner=lambda cfg: _run_joint_inspection(observations, cfg),
                policy=policy,
            )
            configured = configured if isinstance(configured, Mapping) else {}
            shared_model_config = _validated_model_config(configured.get("model"), policy)
            inspection = configured.get("inspection")
            if isinstance(inspection, Mapping):
                weights = inspection.get("feature_weights")
                if isinstance(weights, Sequence) and not isinstance(weights, (str, bytes)):
                    feature_weights = list(weights)
            agentic_meta.update({
                "configured": True,
                "reason": "shared_inspect_model_configured",
                "inspection_config": _json_safe(
                    dict(configured.get("inspection_config") or {})),
                "inspection": _json_safe(
                    dict(inspection) if isinstance(inspection, Mapping) else {}),
                "model_config": dict(shared_model_config),
                "tool_requests": dict(configured.get("tool_requests") or {
                    "inspect": 1, "model": 1, "selection": 0}),
                "tool_calls": dict(configured.get("tool_calls") or {
                    "inspect": 1, "model": 1, "selection": 0}),
                "tool_configs_applied": dict(configured.get(
                    "tool_configs_applied") or {
                        "inspect": 1, "model": 1, "selection": 0}),
                "tool_audit": _json_safe(dict(configured.get("tool_audit") or {})),
            })
            if configured.get("fallback_reason"):
                agentic_meta["fallback_reason"] = str(configured["fallback_reason"])
        except Exception as exc:
            agentic_meta["reason"] = f"shared_inspect_model_failed:{exc}"
    elif agentic_enabled and agentic_controller is not None:
        agentic_meta["reason"] = "model_data_gate_not_met"

    # Exact controls are protected full-flow controls, unless an incumbent/replay
    # already executes the identical complete configuration.
    for anchor in anchors:
        complete = _complete(anchor["upstream_params"], anchor["routing_params"], constraints)
        signature = _signature(complete, int(policy["signature_decimals"]))
        if signature in excluded or len(selected) >= focus_count:
            continue
        excluded.add(signature)
        selected.append({
            "kind": "exact_anchor", "family": anchor["family"],
            "upstream_params": dict(anchor["upstream_params"]),
            "routing_params": dict(anchor["routing_params"]),
            "scoped_params": dict(anchor.get("scoped_params") or {}),
            "sdc_sha256": anchor.get("sdc_sha256"),
            "params": complete,
        })

    if agentic_meta["configured"]:
        models = {
            anchor["family"]: _fit_family_model(
                by_family[anchor["family"]], policy,
                model_config=shared_model_config,
                feature_weights=feature_weights,
            )
            for anchor in anchors
        }
    else:
        models = {
            anchor["family"]: _fit_family_model(by_family[anchor["family"]], policy)
            for anchor in anchors
        }
    total_ready = (len(observations) >= int(policy["routing_model_min_total_observations"]))
    ready = [anchor for anchor in anchors if total_ready and models[anchor["family"]].get("ready")]
    ready_families = {anchor["family"] for anchor in ready}
    # Unready anchor families contribute zero confidence.  This makes Agent2's
    # population share grow with both per-family model quality and basin coverage;
    # one mature local model cannot claim the full conditional budget while the
    # other active anchors still have no validated surrogate.
    confidence = (sum(
        float(models[anchor["family"]].get("confidence", 0.0))
        if anchor["family"] in ready_families else 0.0
        for anchor in anchors
    ) / len(anchors)) if anchors else 0.0
    remaining = focus_count - len(selected)
    novelty_floor = min(remaining, int(round(
        focus_count * float(policy["routing_novelty_fraction"]))))
    target_fraction = float(policy["routing_agentic_target_fraction"])
    if shared_model_config.get("explore_frac") is not None:
        target_fraction = min(
            target_fraction, 1.0 - float(shared_model_config["explore_frac"]))
    requested_agent2 = int(round(
        focus_count * target_fraction * confidence
    )) if agentic_enabled and ready else 0
    agent2_count = min(max(0, remaining - novelty_floor), requested_agent2)

    candidates = []
    pool_size = int(policy["routing_candidate_pool_per_anchor"])
    regions = state.get("routing_trust_regions", {})
    acquisition = str(shared_model_config.get(
        "acquisition", policy.get("routing_acquisition", "ei")))
    for anchor_index, anchor in enumerate(ready):
        radius = float((regions.get(anchor["family"], {}) or {}).get(
            "fraction", policy["routing_jitter_fraction"]))
        routes = _candidate_routes(
            anchor, pool_size, constraints, radius,
            offset=(rng_seed + 7919 * (anchor_index + 1)) % 100000)
        try:
            scores = _score_routes(models[anchor["family"]], routes, constraints, acquisition)
        except Exception:
            scores = []
        if not scores:
            continue
        low, high = min(scores), max(scores)
        span = high - low
        try:
            uncertainties = _route_uncertainties(
                models[anchor["family"]], routes, constraints)
        except Exception:
            uncertainties = [0.0] * len(routes)
        uncertainty_low = min(uncertainties) if uncertainties else 0.0
        uncertainty_span = ((max(uncertainties) - uncertainty_low)
                            if uncertainties else 0.0)
        for route, score, uncertainty in zip(routes, scores, uncertainties):
            complete = _complete(anchor["upstream_params"], route, constraints)
            signature = _signature(complete, int(policy["signature_decimals"]))
            if signature in excluded:
                continue
            candidates.append({
                "kind": "agent2", "family": anchor["family"],
                "upstream_params": dict(anchor["upstream_params"]),
                "routing_params": dict(route), "params": complete,
                "scoped_params": dict(anchor.get("scoped_params") or {}),
                "sdc_sha256": anchor.get("sdc_sha256"),
                "score": (score - low) / span if span > 1e-12 else 0.5,
                "raw_score": float(score),
                "uncertainty": (
                    (uncertainty - uncertainty_low) / uncertainty_span
                    if uncertainty_span > 1e-12 else 0.0),
                "raw_uncertainty": float(uncertainty),
            })

    # Shared Selection needs scores comparable across families. The legacy fixed
    # selector keeps its per-family normalization; the agentic controller uses one
    # global normalization after every independent family GP has been evaluated.
    if agentic_meta["configured"] and candidates:
        raw_scores = [float(item["raw_score"]) for item in candidates]
        score_low, score_high = min(raw_scores), max(raw_scores)
        score_span = score_high - score_low
        raw_uncertainties = [float(item["raw_uncertainty"]) for item in candidates]
        uncertainty_low = min(raw_uncertainties)
        uncertainty_span = max(raw_uncertainties) - uncertainty_low
        for item in candidates:
            item["score"] = (
                (float(item["raw_score"]) - score_low) / score_span
                if score_span > 1e-12 else 0.5)
            item["uncertainty"] = (
                (float(item["raw_uncertainty"]) - uncertainty_low) / uncertainty_span
                if uncertainty_span > 1e-12 else 0.0)

    if agentic_meta["configured"] and candidates:
        try:
            selected_config = agentic_controller.select(
                landscape=_prediction_landscape(candidates, models),
                model_config=shared_model_config,
                policy=policy,
            )
            selection_config = _validated_selection_config(selected_config, policy)
            agentic_meta["selection_config"] = dict(selection_config)
            requests = dict(agentic_meta.get("tool_requests") or {})
            requests["selection"] = int(bool(
                selected_config.get("_tool_requested", True)
                if isinstance(selected_config, Mapping) else True))
            agentic_meta["tool_requests"] = requests
            calls = dict(agentic_meta.get("tool_calls") or {})
            calls["selection"] = int(
                selected_config.get(
                    "_tool_call_count",
                    int(bool(selected_config.get("_tool_called", True))))
                if isinstance(selected_config, Mapping) else 1)
            agentic_meta["tool_calls"] = calls
            applied = dict(agentic_meta.get("tool_configs_applied") or {})
            applied["selection"] = int(bool(
                selected_config.get("_tool_config_applied", True)
                if isinstance(selected_config, Mapping) else True))
            agentic_meta["tool_configs_applied"] = applied
            if isinstance(selected_config, Mapping) and selected_config.get("_tool_audit"):
                audit = dict(agentic_meta.get("tool_audit") or {})
                audit["selection"] = _json_safe(selected_config["_tool_audit"])
                agentic_meta["tool_audit"] = audit
        except Exception as exc:
            agentic_meta["selection_config"] = dict(selection_config)
            agentic_meta["selection_fallback"] = str(exc)

    # Greedy quality + normalized routing diversity, with a per-family cap so one
    # optimistic local model cannot consume the entire conditional budget.
    family_counts: Dict[str, int] = defaultdict(int)
    family_cap = agent2_count if len(ready) <= 1 else max(
        1, int(math.ceil(agent2_count * float(selection_config["family_cap"]))))
    allocation = str(selection_config["family_allocation"])
    if not agentic_meta["configured"] or allocation in {"balanced", "confidence"}:
        for anchor in ready:
            if sum(item["kind"] == "agent2" for item in selected) >= agent2_count:
                break
            family_candidates = [
                item for item in candidates
                if item["params"] is not None and item["family"] == anchor["family"]
            ]
            if not family_candidates:
                continue
            chosen = max(family_candidates, key=lambda item: float(item["score"]))
            selected.append(chosen)
            family_counts[chosen["family"]] += 1
            excluded.add(_signature(chosen["params"], int(policy["signature_decimals"])))
            chosen["params"] = None
    while len([item for item in selected if item["kind"] == "agent2"]) < agent2_count:
        eligible = [item for item in candidates
                    if item["params"] is not None
                    and family_counts[item["family"]] < family_cap]
        if not eligible:
            break
        def utility(item):
            same_family = [prior for prior in selected if prior["family"] == item["family"]]
            diversity = (min(_route_distance(item["routing_params"], prior["routing_params"], constraints)
                             for prior in same_family) if same_family else 1.0)
            allocation_bonus = 0.0
            if allocation == "balanced":
                allocation_bonus = 0.25 / (1.0 + family_counts[item["family"]])
            elif allocation == "confidence":
                allocation_bonus = (
                    0.25 * float(models[item["family"]].get("confidence", 0.0))
                    / (1.0 + family_counts[item["family"]]))
            return (
                float(selection_config["quality_weight"]) * float(item["score"])
                + float(selection_config["uncertainty_bonus"])
                * float(item.get("uncertainty", 0.0))
                + float(selection_config["diversity_weight"]) * diversity
                + allocation_bonus
            )
        chosen = max(eligible, key=utility)
        selected.append(chosen)
        family_counts[chosen["family"]] += 1
        excluded.add(_signature(chosen["params"], int(policy["signature_decimals"])))
        chosen["params"] = None  # mark consumed without an O(n) identity side table

    # Deterministic maximin novelty fills every slot that the guarded model did not earn.
    novelty_offset = rng_seed % 100000 + 104729
    anchor_cursor = 0
    while len(selected) < focus_count:
        anchor = anchors[anchor_cursor % len(anchors)]
        anchor_cursor += 1
        radius = float((regions.get(anchor["family"], {}) or {}).get(
            "fraction", policy["routing_jitter_fraction"]))
        routes = _candidate_routes(
            anchor, max(16, pool_size // 2), constraints, radius,
            offset=novelty_offset + anchor_cursor * 3571)
        usable = []
        for route in routes:
            complete = _complete(anchor["upstream_params"], route, constraints)
            if _signature(complete, int(policy["signature_decimals"])) not in excluded:
                usable.append(route)
        existing = [
            {"family": row["family"], "route": row["route"]} for row in observations
        ] + [
            {"family": item["family"], "route": item["routing_params"]}
            for item in selected
        ]
        route = _novelty_pick(anchor, usable, existing, constraints)
        if route is None:
            # Extremely small/quantized spaces may exhaust the low-discrepancy pool.
            route = dict(anchor["routing_params"])
            name = ROUTING_PARAMETERS[(len(selected) + anchor_cursor) % 2]
            low, high = _bounds(constraints[name])
            route[name] = _clip(route[name] + (high - low) * 1e-4 * anchor_cursor,
                                constraints[name])
        complete = _complete(anchor["upstream_params"], route, constraints)
        excluded.add(_signature(complete, int(policy["signature_decimals"])))
        selected.append({
            "kind": "novelty", "family": anchor["family"],
            "upstream_params": dict(anchor["upstream_params"]),
            "routing_params": dict(route), "params": complete,
            "scoped_params": dict(anchor.get("scoped_params") or {}),
            "sdc_sha256": anchor.get("sdc_sha256"),
        })

    # Restore consumed Agent2 rows' complete params for callers.
    for item in selected:
        if item["kind"] == "agent2" and item.get("params") is None:
            item["params"] = _complete(item["upstream_params"], item["routing_params"], constraints)
    counts = {kind: sum(item["kind"] == kind for item in selected)
              for kind in ("exact_anchor", "agent2", "novelty")}
    family_agent2_counts = {
        family: sum(
            item["kind"] == "agent2" and item["family"] == family
            for item in selected)
        for family in sorted(ready_families)
    }
    return selected[:focus_count], {
        "enabled": True,
        "reason": "conditional" if counts["agent2"] else "deterministic_fallback",
        "evidence_source": evidence_source,
        "counts": counts,
        "observation_count": len(observations),
        "anchor_families": [anchor["family"] for anchor in anchors],
        "family_agent2_counts": family_agent2_counts,
        "model_confidence": confidence,
        "models": {
            family: {k: v for k, v in info.items()
                     if k not in {"model", "scaler", "X", "y"}}
            for family, info in models.items()
        },
        "agentic_tools": agentic_meta,
        "trust_regions": {
            anchor["family"]: float((regions.get(anchor["family"], {}) or {}).get(
                "fraction", policy["routing_jitter_fraction"]))
            for anchor in anchors
        },
    }


def propose_for_sources(
    source_params: Sequence[Mapping[str, Any]],
    routing_history: Sequence[Mapping[str, Any]],
    constraints: Mapping[str, Mapping[str, Any]],
    state: Mapping[str, Any],
    policy: Mapping[str, Any],
    seed: Any,
    *,
    agentic_enabled: bool,
) -> Tuple[List[Dict[str, float]], Dict[str, Any]]:
    """Return positional routing params conditioned on each actual clone source."""
    observations = prepare_observations(
        routing_history, state.get("objective_context", {}), constraints,
        decimals=int(policy["signature_decimals"]))
    grouped: Dict[str, List[Mapping[str, Any]]] = defaultdict(list)
    for row in observations:
        grouped[str(row["family"])].append(row)
    regions = state.get("routing_trust_regions", {})
    persisted_agentic = state.get("routing_focus_agentic", {})
    persisted_agentic = persisted_agentic if isinstance(persisted_agentic, Mapping) else {}
    model_config = _validated_model_config(persisted_agentic.get("model"), policy)
    feature_weights = persisted_agentic.get("feature_weights")
    if not isinstance(feature_weights, Sequence) or isinstance(feature_weights, (str, bytes)):
        feature_weights = None
    total_ready = len(observations) >= int(policy["routing_model_min_total_observations"])
    models: Dict[str, Dict[str, Any]] = {}
    used: Dict[str, List[Dict[str, float]]] = defaultdict(list)
    output, modes = [], []
    base_seed = int(hashlib.sha256(str(seed).encode("utf-8")).hexdigest()[:16], 16)
    rng = random.Random(base_seed)

    for index, source in enumerate(source_params):
        family = routing_family(source, int(policy["signature_decimals"])) or f"unknown-{index}"
        family_rows = grouped.get(family, [])
        if family not in models:
            if persisted_agentic.get("model"):
                models[family] = _fit_family_model(
                    family_rows, policy, model_config=model_config,
                    feature_weights=feature_weights)
            else:
                models[family] = _fit_family_model(family_rows, policy)
        model_info = models[family]
        if family_rows:
            best = min(family_rows, key=lambda row: (row["child_objective"], row["delta"]))
            center = {"family": family, "routing_params": dict(best["route"])}
        else:
            current = _route(source, constraints) or {
                name: sum(_bounds(constraints[name])) / 2.0 for name in ROUTING_PARAMETERS}
            center = {"family": family, "routing_params": current}
        radius = float((regions.get(family, {}) or {}).get(
            "fraction", policy["routing_jitter_fraction"]))
        routes = _candidate_routes(
            center, int(policy["routing_candidate_pool_per_anchor"]), constraints,
            radius, offset=(base_seed + 7919 * (index + 1)) % 100000)
        confidence = float(model_info.get("confidence", 0.0)) if total_ready else 0.0
        target_fraction = float(policy["routing_agentic_target_fraction"])
        if model_config.get("explore_frac") is not None:
            target_fraction = min(
                target_fraction, 1.0 - float(model_config["explore_frac"]))
        use_model = bool(
            agentic_enabled and model_info.get("ready")
            and rng.random() < target_fraction * confidence)
        route = None
        if use_model:
            try:
                scores = _score_routes(model_info, routes, constraints,
                                       str(model_config.get("acquisition",
                                           policy.get("routing_acquisition", "ei"))))
                order = sorted(range(len(routes)), key=lambda i: scores[i], reverse=True)
                route = next((dict(routes[i]) for i in order
                              if all(_route_distance(routes[i], old, constraints) > 1e-6
                                     for old in used[family])), None)
            except Exception:
                route = None
        if route is None:
            existing = [{"family": family, "route": row["route"]} for row in family_rows]
            existing += [{"family": family, "route": old} for old in used[family]]
            route = _novelty_pick(center, routes, existing, constraints) or dict(center["routing_params"])
            modes.append("novelty_fallback")
        else:
            modes.append("agent2")
        used[family].append(route)
        output.append({name: _clip(route[name], constraints[name]) for name in ROUTING_PARAMETERS})

    return output, {
        "counts": {"agent2": modes.count("agent2"),
                   "novelty": modes.count("novelty_fallback")},
        "modes": modes,
        "families": [routing_family(source, int(policy["signature_decimals"]))
                     for source in source_params],
        "observation_count": len(observations),
        "shared_model_config": dict(model_config),
    }


def deterministic_novelty_for_sources(
    source_params: Sequence[Mapping[str, Any]],
    constraints: Mapping[str, Mapping[str, Any]],
    seed: Any,
    *,
    radius_fraction: float = 0.08,
) -> Tuple[List[Dict[str, float]], Dict[str, Any]]:
    """Model-free novelty that remains positional to every actual clone source."""
    radius = min(1.0, max(0.0, float(radius_fraction)))
    base_seed = int(hashlib.sha256(str(seed).encode("utf-8")).hexdigest()[:16], 16)
    used: Dict[str, List[Dict[str, float]]] = defaultdict(list)
    output, families = [], []
    for index, source in enumerate(source_params):
        family = routing_family(source) or f"unknown-{index}"
        current = _route(source, constraints)
        if current is None:
            raise ValueError(f"source {index} has incomplete routing parameters")
        center = {"family": family, "routing_params": current}
        routes = _candidate_routes(
            center, 128, constraints, radius,
            offset=(base_seed + 7919 * (index + 1)) % 100000,
        )
        existing = [{"family": family, "route": current}]
        existing.extend({"family": family, "route": old} for old in used[family])
        route = _novelty_pick(center, routes, existing, constraints) or dict(current)
        used[family].append(route)
        output.append({name: _clip(route[name], constraints[name])
                       for name in ROUTING_PARAMETERS})
        families.append(family)
    return output, {
        "reason": "source_conditioned_deterministic_fallback",
        "counts": {"agent2": 0, "novelty": len(output)},
        "modes": ["novelty_fallback"] * len(output),
        "families": families,
        "observation_count": 0,
    }
