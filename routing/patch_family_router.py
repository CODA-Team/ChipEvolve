"""Small first-pass patch-family router.

This module keeps the current hand-written family wisdom, but exposes it as a
structured decision so packets can explain *why* a family was selected.
"""
from __future__ import annotations

from typing import Any


def _case_id(problem: dict[str, Any]) -> str:
    return f"{problem.get('design')}_{problem.get('platform')}"


def _matches_use_for(case_id: str, use_for: list[Any]) -> bool:
    for item in use_for:
        text = str(item)
        if text == case_id:
            return True
        if case_id.startswith("ariane") and "ariane" in text:
            return True
        if case_id.startswith("jpeg") and "jpeg" in text:
            return True
        if "large" in text and any(case_id.startswith(x) for x in ("ariane", "jpeg", "megaboom", "swerv")):
            return True
    return False


def select_family(
    *,
    problem: dict[str, Any],
    design_profile: dict[str, Any],
    effective_families: dict[str, Any],
    family_registry: dict[str, Any],
) -> dict[str, Any]:
    case_id = _case_id(problem)
    matched: dict[str, Any] | None = None
    for item in effective_families.get("effective_families", []):
        if not isinstance(item, dict):
            continue
        if _matches_use_for(case_id, item.get("use_for", [])):
            matched = item
            break

    if matched is None:
        recommended = design_profile.get("recommended_playbooks", [])
        if any("postopt" in str(x) for x in recommended):
            recipe = "selective_refinement_budget"
        elif any("negotiation" in str(x) for x in recommended):
            recipe = "runtime_aware_net_family"
        else:
            recipe = "runtime_aware_net_family"
        return {
            "id": recipe,
            "registry_id": recipe,
            "start_line": "evolve_line",
            "variant_family": None,
            "regime": "default_negotiation",
            "reason": [
                "no exact effective-family regime matched this case",
                "fall back to a negotiation-family source patch with bounded runtime risk",
            ],
            "watch_out": [],
            "source": "fallback",
        }

    return {
        "id": matched.get("start_with"),
        "registry_id": matched.get("variant_family") or matched.get("start_with"),
        "start_line": matched.get("start_line", "evolve_line"),
        "variant_family": matched.get("variant_family"),
        "regime": matched.get("regime"),
        "reason": matched.get("keep_because", []),
        "watch_out": matched.get("watch_out", []),
        "source": "effective_families",
    }


def startpoint_from_family(selection: dict[str, Any]) -> dict[str, Any]:
    return {
        "start_line": selection.get("start_line", "evolve_line"),
        "family_base": selection.get("id"),
        "variant_family": selection.get("variant_family"),
        "selection_source": selection.get("source"),
        "reason": selection.get("reason", []),
        "watch_out": selection.get("watch_out", []),
    }
