"""Schema parsing and exact per-design resolution for campaign search policy."""
from __future__ import annotations

import math
from copy import deepcopy
from typing import Any, Dict, Mapping, Optional, Tuple


DEFAULT_SEARCH_POLICY: Dict[str, Any] = {
    "enabled": True,
    "objectives": ["TNS_EVAL"],
    "platform_designs": [],
    # State transitions.
    "min_full_iterations": 5,
    "full_stagnation_patience": 3,
    "reopen_min_full_iterations": 2,
    "focus_min_iterations": 4,
    "focus_stop_patience": 4,
    "min_iterations_before_stop": 25,
    "reopen_low_coverage_patience": 2,
    "significant_improvement_abs": 5.0,
    "significant_improvement_rel": 0.0005,
    "min_clean_count": 5,
    "min_clean_fraction": 0.20,
    # Routing-focused batch composition.
    "routing_focus_fraction": 0.75,
    "exact_replay_fraction": 0.15,
    "full_probe_fraction": 0.10,
    # A fraction alone silently shrinks exploration when other batch roles expand.
    # Enabled production policies therefore reserve at least this many full-space rows.
    "full_probe_min_count": 5,
    "anchor_count": 3,
    "routing_jitter_fraction": 0.08,
    "routing_novelty_fraction": 0.25,
    "routing_agentic_target_fraction": 0.65,
    "routing_agentic_family_cap": 0.60,
    "routing_agentic_diversity_weight": 0.20,
    "routing_candidate_pool_per_anchor": 128,
    "routing_model_min_total_observations": 12,
    "routing_model_min_family_observations": 4,
    "routing_model_full_confidence_observations": 8,
    "routing_model_min_cv_improvement": 0.05,
    "routing_acquisition": "ei",
    "routing_trust_min_fraction": 0.02,
    "routing_trust_max_fraction": 0.15,
    "routing_trust_expand_factor": 1.25,
    "routing_trust_shrink_factor": 0.50,
    "front_elite_count": 2,
    "pending_replay_limit": 12,
    "signature_decimals": 6,
    # Independent full-flow confirmations required for promotion.
    "config_replay_required_successes": 2,
    "config_replay_max_attempts": 3,
    "config_replay_abs_tolerance": 100.0,
    "config_replay_rel_tolerance": 0.01,
    # Data-weighted clock region within the configured hard range.
    "clock_top_k": 10,
    "clock_min_observations": 5,
    "clock_margin_fraction": 0.10,
    "clock_min_width_fraction": 0.08,
    "clock_region_fraction": 0.80,
    "clock_jitter_fraction": 0.04,
    # Directed CTS allocation while the full space is active.
    "cts_tns_100_fraction": 0.0,
    "cts_local_window_fraction": 0.50,
    "cts_cluster_size_window": [18, 20],
    "cts_cluster_diameter_window": [90, 94],
}

_HIERARCHICAL_POLICY_KEYS = {"defaults", "design_overrides"}
_HIERARCHICAL_ROOT_KEYS = {
    "enabled", "objectives", "defaults", "design_overrides", "description",
}
_HIERARCHICAL_SCOPE_KEYS = {"enabled", "calibration_status", "description"}
_DESIGN_CALIBRATION_KEYS = {
    "cts_cluster_size_window", "cts_cluster_diameter_window",
}


def _search_policy_block(
        config: Optional[Mapping[str, Any]]) -> Optional[Mapping[str, Any]]:
    """Extract the configured policy block without resolving a design scope."""
    if not config:
        return None
    if "search_policy" in config:
        raw = config.get("search_policy")
    elif (any(key in config for key in DEFAULT_SEARCH_POLICY)
          or any(key in config for key in _HIERARCHICAL_POLICY_KEYS)):
        raw = config
    else:
        return None
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        raise ValueError("search_policy must be an object")
    return raw


def _validate_effective_policy(policy: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize and validate one fully merged, executable policy."""
    policy = deepcopy(policy)
    for key in (
        "routing_focus_fraction", "exact_replay_fraction", "full_probe_fraction",
        "min_clean_fraction", "clock_region_fraction", "cts_tns_100_fraction",
        "cts_local_window_fraction", "routing_jitter_fraction",
        "routing_novelty_fraction", "routing_agentic_target_fraction",
        "routing_agentic_family_cap", "routing_agentic_diversity_weight",
        "routing_model_min_cv_improvement", "routing_trust_min_fraction",
        "routing_trust_max_fraction", "routing_trust_shrink_factor",
        "clock_margin_fraction", "clock_min_width_fraction", "clock_jitter_fraction",
    ):
        value = float(policy[key])
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"search_policy.{key} must be in [0, 1], got {value}")
        policy[key] = value
    composition = sum(policy[key] for key in (
        "routing_focus_fraction", "exact_replay_fraction", "full_probe_fraction"))
    if not math.isclose(composition, 1.0, rel_tol=0.0, abs_tol=1.0e-9):
        raise ValueError(
            "search_policy routing_focus/exact_replay/full_probe fractions must sum "
            f"to 1.0, got {composition}")
    for key in (
        "min_full_iterations", "full_stagnation_patience", "reopen_min_full_iterations",
        "focus_min_iterations", "focus_stop_patience", "min_iterations_before_stop",
        "reopen_low_coverage_patience", "anchor_count", "front_elite_count",
        "pending_replay_limit", "signature_decimals", "clock_top_k",
        "clock_min_observations", "min_clean_count", "full_probe_min_count",
        "routing_candidate_pool_per_anchor", "routing_model_min_total_observations",
        "routing_model_min_family_observations",
        "routing_model_full_confidence_observations",
        "config_replay_required_successes", "config_replay_max_attempts",
    ):
        policy[key] = int(policy[key])
        if policy[key] < 0:
            raise ValueError(f"search_policy.{key} must be non-negative")
    if policy["config_replay_required_successes"] < 1:
        raise ValueError("search_policy.config_replay_required_successes must be >= 1")
    if policy["config_replay_max_attempts"] < policy["config_replay_required_successes"]:
        raise ValueError(
            "search_policy.config_replay_max_attempts cannot be smaller than "
            "config_replay_required_successes")
    for key in ("config_replay_abs_tolerance", "config_replay_rel_tolerance"):
        policy[key] = float(policy[key])
        if policy[key] < 0:
            raise ValueError(f"search_policy.{key} must be non-negative")
    expand = float(policy["routing_trust_expand_factor"])
    if expand < 1.0:
        raise ValueError("search_policy.routing_trust_expand_factor must be >= 1")
    policy["routing_trust_expand_factor"] = expand
    if policy["routing_trust_min_fraction"] > policy["routing_jitter_fraction"]:
        raise ValueError("routing trust minimum cannot exceed the initial jitter fraction")
    if policy["routing_jitter_fraction"] > policy["routing_trust_max_fraction"]:
        raise ValueError("initial routing jitter cannot exceed the trust maximum")
    acquisitions = {"ei", "ucb", "pi", "augmented_ei"}
    if str(policy["routing_acquisition"]).lower() not in acquisitions:
        raise ValueError(
            "search_policy.routing_acquisition must be ei/ucb/pi/augmented_ei")
    policy["routing_acquisition"] = str(policy["routing_acquisition"]).lower()
    for key in _DESIGN_CALIBRATION_KEYS:
        try:
            window = list(policy[key])
            valid = len(window) == 2 and float(window[0]) <= float(window[1])
        except (TypeError, ValueError):
            valid = False
            window = []
        if not valid:
            raise ValueError(f"search_policy.{key} must be a numeric [low, high]")
        policy[key] = window
    return policy


def _hierarchical_policy_parts(
        raw: Mapping[str, Any]) -> Tuple[Dict[str, Any], Mapping[str, Any]]:
    """Validate the defaults/overrides schema and return its shared base."""
    unsupported = set(raw) - _HIERARCHICAL_ROOT_KEYS
    if unsupported:
        raise ValueError(
            "search_policy hierarchical schema has unsupported root keys: "
            f"{sorted(unsupported)}; move tunables under defaults")
    if "enabled" in raw and not isinstance(raw["enabled"], bool):
        raise ValueError("search_policy.enabled must be boolean")
    objectives = raw.get("objectives", DEFAULT_SEARCH_POLICY["objectives"])
    if (not isinstance(objectives, list)
            or not all(isinstance(item, str) for item in objectives)):
        raise ValueError("search_policy.objectives must be a list of strings")
    defaults = raw.get("defaults", {})
    overrides = raw.get("design_overrides")
    if not isinstance(defaults, Mapping):
        raise ValueError("search_policy.defaults must be an object")
    if not isinstance(overrides, Mapping):
        raise ValueError("search_policy.design_overrides must be an object")
    invalid_defaults = set(defaults) - set(DEFAULT_SEARCH_POLICY)
    if invalid_defaults:
        raise ValueError(
            "search_policy.defaults has unsupported keys: "
            f"{sorted(invalid_defaults)}")
    reserved = {"enabled", "objectives", "platform_designs"} & set(defaults)
    if reserved:
        raise ValueError(
            "search_policy scope keys must remain at the root, not defaults: "
            f"{sorted(reserved)}")

    base = deepcopy(DEFAULT_SEARCH_POLICY)
    base.update(dict(defaults))
    base["enabled"] = bool(raw.get("enabled", True))
    base["objectives"] = list(objectives)
    if "description" in raw:
        base["description"] = raw["description"]
    base = _validate_effective_policy(base)

    allowed = (
        set(DEFAULT_SEARCH_POLICY) - {"enabled", "objectives", "platform_designs"}
    ) | _HIERARCHICAL_SCOPE_KEYS
    for scope, override in overrides.items():
        if (not isinstance(scope, str) or scope.count("/") != 1
                or not all(scope.split("/"))):
            raise ValueError(
                "search_policy.design_overrides keys must be 'platform/design'")
        if not isinstance(override, Mapping):
            raise ValueError(
                f"search_policy.design_overrides.{scope} must be an object")
        if "enabled" not in override or not isinstance(override["enabled"], bool):
            raise ValueError(
                f"search_policy.design_overrides.{scope}.enabled must be boolean")
        unsupported_override = set(override) - allowed
        if unsupported_override:
            raise ValueError(
                f"search_policy.design_overrides.{scope} has unsupported keys: "
                f"{sorted(unsupported_override)}")
        if not override["enabled"]:
            continue
        missing = _DESIGN_CALIBRATION_KEYS - (set(defaults) | set(override))
        if missing:
            raise ValueError(
                f"enabled search_policy override {scope} must explicitly configure "
                f"{sorted(missing)} in defaults or the design override")
        effective = deepcopy(base)
        effective.update(dict(override))
        _validate_effective_policy(effective)
    return base, overrides


def load_search_policy_config(
        config: Optional[Mapping[str, Any]]) -> Optional[Dict[str, Any]]:
    """Return validated shared/legacy policy values, or ``None`` when disabled."""
    raw = _search_policy_block(config)
    if raw is None or not raw.get("enabled", True):
        return None
    if any(key in raw for key in _HIERARCHICAL_POLICY_KEYS):
        policy, _ = _hierarchical_policy_parts(raw)
        return policy
    policy = deepcopy(DEFAULT_SEARCH_POLICY)
    policy.update(dict(raw))
    return _validate_effective_policy(policy)


def policy_for_context(config: Optional[Mapping[str, Any]], objective: str,
                       platform: Optional[str] = None,
                       design: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Return the exact design policy without leaking calibrated overrides."""
    raw = _search_policy_block(config)
    policy = load_search_policy_config(config)
    if policy is None:
        return None
    if raw is not None and any(
            key in raw for key in _HIERARCHICAL_POLICY_KEYS):
        _, overrides = _hierarchical_policy_parts(raw)
        scope = f"{platform}/{design}" if platform and design else None
        override = overrides.get(scope) if scope else None
        if not isinstance(override, Mapping) or not override.get("enabled", True):
            return None
        policy.update(dict(override))
        policy["platform_designs"] = [scope]
        policy = _validate_effective_policy(policy)
    objectives = [str(item) for item in policy.get("objectives", [])]
    scopes = [str(item) for item in policy.get("platform_designs", [])]
    scope = f"{platform}/{design}" if platform and design else None
    if objectives and objective not in objectives:
        return None
    if scopes and scope not in scopes:
        return None
    return policy


__all__ = [
    "DEFAULT_SEARCH_POLICY", "load_search_policy_config", "policy_for_context",
]
