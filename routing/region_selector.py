"""Function-level patch-region selection from the patch surface atlas."""
from __future__ import annotations

from typing import Any


FAMILY_MODE_HINTS: dict[str, list[str]] = {
    "legalm_engine_initial": ["runtime_flag_wiring", "bounded_cli_plumbing"],
    "runtime_aware_net_family": [
        "selective_refinement_change",
        "runtime_efficiency_review",
    ],
    "runtime_aware_net_family_plus_priority_escape": [
        "stuck_cell_escape",
        "candidate_generation_change",
        "search_window_policy_change",
    ],
    "priority_escape": [
        "stuck_cell_escape",
        "candidate_generation_change",
        "search_window_policy_change",
    ],
    "hpwl_wide_postopt": [
        "objective_change",
        "localized_postopt_change",
        "localized_swap_change",
    ],
    "selective_refinement_budget": [
        "selective_refinement_change",
        "runtime_efficiency_review",
    ],
    "localized_swap": ["localized_swap_change", "objective_change"],
}


def _allowed_problem_files(problem: dict[str, Any]) -> set[str]:
    return {str(path) for path in problem.get("patch_surface", [])}


def _surface_score(surface: dict[str, Any], mode_hints: list[str]) -> int:
    modes = {str(item) for item in surface.get("allowed_patch_modes", [])}
    score = 0
    score += 5 * len(modes.intersection(mode_hints))
    symbol = str(surface.get("symbol", ""))
    if "negotiationCost" in symbol and any("objective" in mode for mode in mode_hints):
        score += 3
    if "findBestLocation" in symbol and any("escape" in mode or "candidate" in mode for mode in mode_hints):
        score += 3
    if "greedyImprove" in symbol and any("refinement" in mode or "postopt" in mode for mode in mode_hints):
        score += 3
    if "cellSwap" in symbol and any("swap" in mode for mode in mode_hints):
        score += 3
    if str(surface.get("risk")) == "high":
        score -= 1
    return score


def select_region(
    *,
    problem: dict[str, Any],
    patch_surface: dict[str, Any],
    family_id: str,
) -> dict[str, Any]:
    allowed_files = _allowed_problem_files(problem)
    surfaces = [
        item
        for item in patch_surface.get("surfaces", [])
        if isinstance(item, dict)
    ]
    problem_allowed = [
        item for item in surfaces if not allowed_files or str(item.get("file")) in allowed_files
    ]
    candidates = problem_allowed or surfaces
    mode_hints = FAMILY_MODE_HINTS.get(family_id, ["objective_change"])
    ranked = sorted(
        candidates,
        key=lambda item: (_surface_score(item, mode_hints), str(item.get("file")), str(item.get("symbol"))),
        reverse=True,
    )
    selected = ranked[0] if ranked else {}

    excluded_high_value = []
    for item in surfaces:
        if str(item.get("file")) in allowed_files:
            continue
        modes = set(map(str, item.get("allowed_patch_modes", [])))
        if modes.intersection(mode_hints):
            excluded_high_value.append(
                {
                    "file": item.get("file"),
                    "symbol": item.get("symbol"),
                    "reason": "matches family mode but is not currently allowed by problem.yaml",
                }
            )

    anchors = selected.get("anchors", {}) if isinstance(selected.get("anchors"), dict) else {}
    return {
        "file": selected.get("file"),
        "symbol": selected.get("symbol"),
        "signature": selected.get("signature"),
        "allowed_line_windows": anchors.get("allowed_line_windows", []),
        "allowed_patch_modes": selected.get("allowed_patch_modes", []),
        "risk": selected.get("risk"),
        "family_mode_hints": mode_hints,
        "selection_reason": [
            "selected from patch_surface.yaml",
            "problem.yaml patch_surface is treated as the hard file allowlist",
            f"matched family modes: {', '.join(mode_hints)}",
        ],
        "excluded_high_value_surfaces": excluded_high_value[:4],
    }
