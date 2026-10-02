"""Shared objective, PDK, and design context for every parameter decision."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Mapping, Optional


def _design_config(config: Mapping[str, Any], platform: str,
                   design: str) -> Optional[Mapping[str, Any]]:
    for entry in config.get("configurations", ()):
        if (isinstance(entry, Mapping)
                and entry.get("platform") == platform
                and entry.get("design") == design):
            return entry
    return None


def _current_best(evidence: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    rows = evidence.get("top_successful_configs")
    if not isinstance(rows, list) or not rows or not isinstance(rows[0], Mapping):
        return None
    best = rows[0]
    return {
        key: deepcopy(best[key])
        for key in (
            "iteration", "run_id", "candidate_id", "objective_value",
            "abs_tns_at_cp0", "power", "power_margin", "params",
        )
        if key in best
    }


def _objective_priority(objective: str) -> list[str]:
    if objective == "TNS_EVAL":
        return [
            "complete the flow and produce comparable final metrics",
            "satisfy the configured power-feasibility contract",
            "minimize abs(TNS) at the shared CP_0",
            "use WNS, congestion, DRV, and intermediate timing only as supporting evidence",
        ]
    if objective == "combo":
        return [
            "complete the flow",
            "minimize the configured normalized wirelength/ECP combination",
            "avoid congestion and DRV regressions that threaten final feasibility",
        ]
    return [
        "complete the flow",
        f"minimize {objective}",
        "avoid intermediate regressions that threaten final feasibility",
    ]


def build_shared_prompt_context(
    config: Mapping[str, Any],
    platform: str,
    design: str,
    objective: str,
    evidence: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Dict[str, Any]]:
    """Build static campaign context plus the current feasible reference point."""
    evidence = evidence if isinstance(evidence, Mapping) else {}
    design_cfg = _design_config(config, platform, design) or {}

    pdk_profiles = config.get("pdk_profiles")
    raw_pdk = (pdk_profiles.get(platform)
               if isinstance(pdk_profiles, Mapping) else None)
    pdk_context = deepcopy(raw_pdk) if isinstance(raw_pdk, Mapping) else {}
    pdk_context.setdefault("name", platform)
    if not raw_pdk:
        pdk_context["status"] = "profile_not_configured"

    design_profiles = config.get("design_profiles")
    raw_design = (design_profiles.get(design)
                  if isinstance(design_profiles, Mapping) else None)
    design_context = deepcopy(raw_design) if isinstance(raw_design, Mapping) else {}
    local_profile = design_cfg.get("design_profile")
    if isinstance(local_profile, Mapping):
        design_context.update(deepcopy(local_profile))
    design_context.setdefault("name", design)
    if not raw_design and not isinstance(local_profile, Mapping):
        design_context["status"] = "profile_not_configured"
    design_context.update({
        "platform": platform,
        "clock_period_range": deepcopy(design_cfg.get("clock_period_range")),
        "clock_period_unit": design_cfg.get("clock_period_unit"),
        "default_clock_period": design_cfg.get("default_clock_period"),
        "baseline_reference": deepcopy(design_cfg.get("baseline", {})),
    })

    contract = evidence.get("objective_contract")
    optimization_context: Dict[str, Any] = {
        "active_objective": objective,
        "direction": "minimize",
        "decision_priority": _objective_priority(objective),
        "scope": {"platform": platform, "design": design},
        "objective_contract_is_authoritative": True,
        "current_best_feasible": _current_best(evidence),
        "baseline_reference": {
            **deepcopy(design_cfg.get("baseline", {})),
            "default_clock_period": design_cfg.get("default_clock_period"),
            "clock_period_unit": design_cfg.get("clock_period_unit"),
        },
    }
    if isinstance(contract, Mapping):
        optimization_context["comparison_clock"] = contract.get("comparison_clock")
        optimization_context["power_limit"] = contract.get("power_limit")
        optimization_context["exact_objective"] = contract.get("exact_objective")

    return {
        "optimization_context": optimization_context,
        "pdk_context": pdk_context,
        "design_context": design_context,
    }


__all__ = ["build_shared_prompt_context"]
