"""Candidate shaping, quota selection, and audit helpers for Agent2.

The module contains only deterministic candidate operations plus NumPy-backed
sampling.  LLM calls, surrogate construction, and lifecycle I/O remain in
``optimize_agentic.py``, which re-exports these helpers for compatibility.
"""
from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Mapping, Optional

import numpy as np

from candidate_tracking import CANDIDATE_ID_KEY, CANDIDATE_ORIGIN_KEY
from search_policy import FULL_SEARCH, build_search_space, policy_for_context


def _vectorize(params: Dict[str, Any], param_names: List[str],
               constraints: Dict[str, dict]) -> List[float]:
    vec = []
    for n in param_names:
        v = params.get(n)
        if v is None:
            lo, hi = constraints[n]["range"]
            v = (lo + hi) / 2.0
        vec.append(float(v))
    return vec


def _normalized_vector(params: Dict[str, Any], param_names: List[str],
                       constraints: Dict[str, dict]) -> List[float]:
    """Map every dimension to [0, 1] for distance/diversity calculations."""
    result = []
    for name in param_names:
        low, high = map(float, constraints[name]["range"])
        value = params.get(name)
        if value is None:
            value = (low + high) / 2.0
        normalized = 0.0 if high == low else (float(value) - low) / (high - low)
        result.append(min(1.0, max(0.0, normalized)))
    return result


def _rescale_between_ranges(value: Any, source: Dict[str, Any],
                            target_low: float, target_high: float) -> float:
    source_low, source_high = map(float, source["range"])
    number = float(value if value is not None else (source_low + source_high) / 2.0)
    fraction = (0.5 if source_high == source_low else
                (number - source_low) / (source_high - source_low))
    shaped = target_low + min(1.0, max(0.0, fraction)) * (target_high - target_low)
    if source.get("type") == "int":
        return int(round(shaped))
    return round(shaped, 4)


def _shape_pool_before_gpr(
        candidates: List[Dict[str, Any]], *,
        history: List[Dict], resolved_history: List[Dict],
        routing_history: List[Dict], optimization_state: Optional[Dict[str, Any]],
        constraints: Dict[str, dict], policy_config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Apply the executable upstream clock policy before surrogate scoring.

    The final batch shaper recognizes ``_gpr_scored_effective_config`` and will not
    mutate these dimensions again.  Whole-row probes remain untouched so they still
    cover the hard space; they are selected through a separate hard quota.
    """
    if (not optimization_state
            or optimization_state.get("mode") != FULL_SEARCH
            or not optimization_state.get("enabled", False)):
        return [dict(candidate) for candidate in candidates]
    policy = policy_for_context(
        policy_config, str(optimization_state.get("objective", "")),
        optimization_state.get("platform"), optimization_state.get("design"))
    if policy is None:
        return [dict(candidate) for candidate in candidates]
    effective, _ = build_search_space(
        constraints,
        clean_history=history,
        resolved_history=resolved_history,
        routing_history=routing_history,
        state=optimization_state,
        policy_config=policy_config,
    )
    rows = [dict(candidate) for candidate in candidates]
    eligible = [
        index for index, candidate in enumerate(rows)
        if candidate.get(CANDIDATE_ORIGIN_KEY) not in {"replay", "full_probe"}
    ]
    eligible.sort(key=lambda index: (
        rows[index].get(CANDIDATE_ORIGIN_KEY) != "exploit",
        hashlib.sha256(
            str(rows[index].get(CANDIDATE_ID_KEY, index)).encode("utf-8")
        ).hexdigest(),
    ))
    # Match the executable policy's denominator (the complete batch/pool), not the
    # smaller eligible subset. In a large Agent2 pool this preserves the configured
    # proportions; final selection below enforces the execution-batch targets.
    n_clock = min(len(eligible), int(round(
        len(rows) * float(policy["clock_region_fraction"]))))
    clock_indices = set(eligible[:n_clock])
    clock_range = (effective.get("clk_period") or {}).get("range")

    for index, row in enumerate(rows):
        roles: List[str] = []
        if index in clock_indices and clock_range and "clk_period" in constraints:
            row["clk_period"] = _rescale_between_ranges(
                row.get("clk_period"), constraints["clk_period"],
                float(clock_range[0]), float(clock_range[1]))
            roles.append("pre_gpr_clock_region")
        row["_gpr_scored_effective_config"] = True
        row["_gpr_shape_roles"] = roles
    return rows


def _enforce_origin_quotas(indices: List[int], candidates: List[Dict[str, Any]],
                           quality: np.ndarray, need: int,
                           quotas: Dict[str, int]) -> List[int]:
    """Keep scored exploitation and whole-row probes in the selected batch."""
    if need <= 0:
        return []
    chosen: List[int] = []
    for origin, requested in quotas.items():
        pool = [
            index for index, candidate in enumerate(candidates)
            if candidate.get(CANDIDATE_ORIGIN_KEY) == origin
        ]
        pool.sort(key=lambda index: float(quality[index]), reverse=True)
        chosen.extend(index for index in pool[:max(0, requested)] if index not in chosen)
    for index in indices:
        if index not in chosen:
            chosen.append(index)
        if len(chosen) >= need:
            break
    if len(chosen) < need:
        ranked = sorted(range(len(candidates)),
                        key=lambda index: float(quality[index]), reverse=True)
        chosen.extend(index for index in ranked if index not in chosen)
    return chosen[:need]


def full_probe_target_count(num_runs: int, policy: Mapping[str, Any]) -> int:
    """Return Agent2's pre-selection full-probe quota.

    The final policy shaper owns the protected tail slots, but Agent2 must reserve
    the same number of whole-row probes before GPR/Agglom selection.  Otherwise an
    apparently valid five-probe plan can lose every probe before it reaches CSV.
    """
    runs = max(0, int(num_runs))
    fraction = max(0.0, float(policy.get("full_probe_fraction", 0.10)))
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
    fractional = max(1, int(round(runs * fraction))) if fraction > 0.0 and runs else 0
    return max(fractional, minimum)


def _bounded_origin_quotas(num_runs: int, need: int,
                           policy: Dict[str, Any],
                           kept: Optional[List[Dict[str, Any]]] = None
                           ) -> Dict[str, int]:
    """Fit mandatory origins into the selectable portion of a batch.

    Full probes get first claim on a scarce small-batch slot because the shared
    policy cannot recover hard-space coverage from an exploit-only selection.
    Exploitation is enabled at five runs, matching optimize.py's feasible-history
    quota. Existing origins in the fixed front count toward both targets.
    """
    capacity = max(0, int(need))
    selected = list(kept or [])
    desired_probe = full_probe_target_count(num_runs, policy)
    desired_exploit = max(2, int(num_runs) // 5) if num_runs >= 5 else 0
    have_probe = sum(
        item.get(CANDIDATE_ORIGIN_KEY) == "full_probe" for item in selected)
    have_exploit = sum(
        item.get(CANDIDATE_ORIGIN_KEY) == "exploit" for item in selected)
    missing_probe = max(0, desired_probe - have_probe)
    if missing_probe > capacity:
        raise RuntimeError(
            "Agent2 cannot satisfy full_probe_min_count="
            f"{policy.get('full_probe_min_count', 0)}: needs {desired_probe} "
            f"full_probe candidates but only {have_probe + capacity} output slots "
            "remain after fixed elites. Increase --runs or explicitly lower the "
            "policy minimum.")
    probe = missing_probe
    exploit = min(max(0, desired_exploit - have_exploit), capacity - probe)
    return {"exploit": exploit, "full_probe": probe}


def _bounded_role_quotas(num_runs: int, need: int,
                         policy: Dict[str, Any],
                         origin_quotas: Dict[str, int],
                         kept: Optional[List[Dict[str, Any]]] = None
                         ) -> Dict[str, int]:
    """Inter-iteration Agent2 has no CTS roles; CTS is generated post-place."""
    del num_runs, need, policy, origin_quotas, kept
    return {}


def _enforce_selection_quotas(
    indices: List[int], candidates: List[Dict[str, Any]], quality: np.ndarray,
    need: int, origin_quotas: Dict[str, int], role_quotas: Dict[str, int],
) -> List[int]:
    """Select a scored batch satisfying overlapping origin and shaping quotas."""
    if need <= 0:
        return []
    requirements = {
        **{f"origin:{name}": max(0, int(count))
           for name, count in origin_quotas.items()},
        **{f"role:{name}": max(0, int(count))
           for name, count in role_quotas.items()},
    }

    def tags(index: int) -> set:
        candidate = candidates[index]
        values = {f"origin:{candidate.get(CANDIDATE_ORIGIN_KEY)}"}
        values.update(f"role:{role}" for role in candidate.get(
            "_gpr_shape_roles", []))
        return values

    chosen: List[int] = []
    available = set(range(len(candidates)))
    while available and len(chosen) < need and any(requirements.values()):
        ranked = []
        for index in available:
            candidate_tags = tags(index)
            covered = sum(
                requirements.get(tag, 0) > 0 for tag in candidate_tags)
            if covered <= 0:
                continue
            overshoot = sum(
                tag.startswith("role:") and requirements.get(tag, 0) == 0
                for tag in candidate_tags)
            ranked.append((covered, -overshoot, float(quality[index]), -index, index))
        if not ranked:
            break
        index = max(ranked)[-1]
        chosen.append(index)
        available.remove(index)
        for tag in tags(index):
            if requirements.get(tag, 0) > 0:
                requirements[tag] -= 1

    preferred = []
    for index in indices:
        if 0 <= int(index) < len(candidates) and int(index) not in preferred:
            preferred.append(int(index))
    preferred.extend(
        index for index in sorted(
            available, key=lambda item: float(quality[item]), reverse=True)
        if index not in preferred)

    # Once a role target is met, prefer unshaped fill rows so execution keeps the
    # requested 70%/50% mix instead of silently expanding it toward 100%.
    role_targets = {
        role: int(count) for role, count in role_quotas.items()
    }
    role_counts = {
        role: sum(role in candidates[index].get("_gpr_shape_roles", [])
                  for index in chosen)
        for role in role_targets
    }

    def validated() -> List[int]:
        selected = chosen[:need]
        shortfalls = {}
        for origin, required in origin_quotas.items():
            actual = sum(
                candidates[index].get(CANDIDATE_ORIGIN_KEY) == origin
                for index in selected)
            if actual < required:
                shortfalls[f"origin:{origin}"] = {
                    "required": required, "actual": actual}
        for role, required in role_quotas.items():
            actual = sum(
                role in candidates[index].get("_gpr_shape_roles", [])
                for index in selected)
            if actual < required:
                shortfalls[f"role:{role}"] = {
                    "required": required, "actual": actual}
        if shortfalls:
            raise RuntimeError(
                f"Agent2 candidate pool cannot satisfy execution quotas: {shortfalls}")
        return selected

    for allow_overshoot in (False, True):
        for index in preferred:
            if index in chosen:
                continue
            roles = set(candidates[index].get("_gpr_shape_roles", []))
            if (not allow_overshoot and any(
                    role in roles and role_counts[role] >= role_targets[role]
                    for role in role_targets)):
                continue
            chosen.append(index)
            for role in role_targets:
                role_counts[role] += int(role in roles)
            if len(chosen) >= need:
                return validated()
    return validated()


def _probes_last(batch: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Place selected whole-row probes in the tail slots without changing values."""
    return ([item for item in batch
             if item.get(CANDIDATE_ORIGIN_KEY) != "full_probe"]
            + [item for item in batch
               if item.get(CANDIDATE_ORIGIN_KEY) == "full_probe"])


def _origin_counts(batch: List[Dict[str, Any]]) -> Dict[str, int]:
    origins = {str(item.get(CANDIDATE_ORIGIN_KEY)) for item in batch}
    return {
        origin: sum(str(item.get(CANDIDATE_ORIGIN_KEY)) == origin for item in batch)
        for origin in sorted(origins)
    }


def _quota_forced_ids(selected: List[Dict[str, Any]],
                      baseline: List[Dict[str, Any]],
                      quotas: Dict[str, int]) -> set:
    """Return quota-origin candidates absent from the unforced selection."""
    baseline_ids = {
        item.get(CANDIDATE_ID_KEY) for item in baseline
        if item.get(CANDIDATE_ID_KEY) is not None
    }
    quota_origins = {origin for origin, count in quotas.items() if count > 0}
    return {
        item.get(CANDIDATE_ID_KEY) for item in selected
        if item.get(CANDIDATE_ID_KEY) is not None
        and item.get(CANDIDATE_ID_KEY) not in baseline_ids
        and item.get(CANDIDATE_ORIGIN_KEY) in quota_origins
    }


def _selection_event_details(
    selected: List[Dict[str, Any]], method: str,
    audit_by_id: Optional[Mapping[str, Mapping[str, Any]]] = None,
    quota_forced_ids: Optional[set] = None,
    front_ids: Optional[set] = None,
) -> List[Dict[str, Any]]:
    """Persist the scored reason for every Agent2 selection decision."""
    audit = audit_by_id or {}
    forced = quota_forced_ids or set()
    fixed_front = front_ids or set()
    details = []
    for rank, item in enumerate(selected, start=1):
        candidate_id = item.get(CANDIDATE_ID_KEY)
        scored = dict(audit.get(candidate_id, {}))
        scored.pop("candidate_id", None)
        scored.pop("origin", None)
        details.append({
            "selection_method": method,
            "selection_rank": rank,
            "front_elite": candidate_id in fixed_front,
            "quota_forced": candidate_id in forced,
            "quota_origin": (
                item.get(CANDIDATE_ORIGIN_KEY) if candidate_id in forced else None),
            **scored,
        })
    return details


def _fallback_select_with_quotas(
    kept: List[Dict[str, Any]], rest: List[Dict[str, Any]], num_runs: int,
    policy: Dict[str, Any], origin_quotas: Optional[Dict[str, int]] = None,
    role_quotas: Optional[Dict[str, int]] = None,
) -> List[Dict[str, Any]]:
    """Deterministic fallback that preserves the same origin quotas as Agglom."""
    need = max(0, int(num_runs) - len(kept))
    origins = (origin_quotas if origin_quotas is not None
               else _bounded_origin_quotas(num_runs, need, policy, kept))
    roles = (role_quotas if role_quotas is not None
             else _bounded_role_quotas(
                 num_runs, need, policy, origins, kept))
    # Earlier pool positions win ties, preserving the old elitist fallback after
    # mandatory origin rows have been installed.
    quality = -np.arange(len(rest), dtype=float)
    indices = _enforce_selection_quotas(
        list(range(len(rest))), rest, quality, need, origins, roles)
    selected = list(kept) + [rest[index] for index in indices]
    return _probes_last(selected[:num_runs])


def _uniform_hard_samples(count: int, constraints: Dict[str, dict],
                          seed: int) -> List[Dict[str, Any]]:
    """Dependency-light hard-space fallback when the optional LHS helper is absent."""
    rng = np.random.default_rng(int(seed))
    rows: List[Dict[str, Any]] = []
    for _ in range(max(0, int(count))):
        row: Dict[str, Any] = {}
        for name, spec in constraints.items():
            low, high = spec["range"]
            if spec.get("type") == "int":
                row[name] = int(rng.integers(int(np.ceil(low)), int(np.floor(high)) + 1))
            else:
                row[name] = float(rng.uniform(float(low), float(high)))
        rows.append(row)
    return rows


__all__ = [
    "_bounded_origin_quotas",
    "_bounded_role_quotas",
    "_enforce_origin_quotas",
    "_enforce_selection_quotas",
    "_fallback_select_with_quotas",
    "full_probe_target_count",
    "_normalized_vector",
    "_origin_counts",
    "_probes_last",
    "_quota_forced_ids",
    "_rescale_between_ranges",
    "_selection_event_details",
    "_shape_pool_before_gpr",
    "_uniform_hard_samples",
    "_vectorize",
]
