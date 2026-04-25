#!/usr/bin/env python3
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


@dataclass(frozen=True)
class FamilyMutation:
    """A materializable dpl_evolve source recipe.

    This module is intentionally a thin registry around the existing matrix
    mutator while the family bring-up harness is being unified.  New robust
    base work should move concrete mutation bodies here instead of adding more
    one-off local archives.
    """

    family: str
    source_kind: str
    source_family: str = "clean_evolve_base"
    matrix_variant: str | None = None
    patch_file: str | None = None
    status: str = "implemented"
    summary: str = ""
    aliases: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


BRINGUP_ALIASES: dict[str, FamilyMutation] = {
    # R6 is the next real implementation target.  Until its mutation body is
    # committed, the harness aliases it to r5 so build/eval plumbing can be
    # validated without pretending this is a promoted R6 result.
    "negotiation_row_bucket_quality_frontier_r6_twopass": FamilyMutation(
        family="negotiation_row_bucket_quality_frontier_r6_twopass",
        source_kind="generated_matrix_variant",
        matrix_variant="negotiation_row_bucket_quality_frontier_r5",
        status="bringup_alias_not_algorithm_promotion",
        summary="Bring-up alias for R6 harness validation; uses current r5 generator.",
    ),
    "negotiation_row_bucket_quality_frontier_r6_twopass_rowindex": FamilyMutation(
        family="negotiation_row_bucket_quality_frontier_r6_twopass_rowindex",
        source_kind="generated_matrix_variant",
        matrix_variant="negotiation_row_bucket_quality_frontier_r5",
        status="bringup_alias_not_algorithm_promotion",
        summary="Compatibility alias for the planned R6 two-pass row-index target.",
    ),
    "netaware14_rowedge_shortlist_hpwl": FamilyMutation(
        family="netaware14_rowedge_shortlist_hpwl",
        source_kind="generated_matrix_variant",
        matrix_variant="netaware03_row_guard_frontier",
        status="bringup_alias_not_algorithm_promotion",
        summary="Bring-up alias for clean/generator netaware14; uses current row-guard frontier variant.",
    ),
    "priority_escape_telemetry_first": FamilyMutation(
        family="priority_escape_telemetry_first",
        source_kind="generated_matrix_variant",
        matrix_variant="priority_escape_scale_safe_base",
        status="bringup_alias_not_algorithm_promotion",
        summary="Bring-up alias for telemetry-first priority repair; uses scale-safe priority base.",
    ),
    "localized_swap_transactional_polish": FamilyMutation(
        family="localized_swap_transactional_polish",
        source_kind="generated_matrix_variant",
        matrix_variant="localswap01_bounded_local_polish",
        status="bringup_alias_not_algorithm_promotion",
        summary="Bring-up alias for transactional polish; uses current bounded local-polish recipe.",
    ),
    "legalm_r6_relaxed_scanline_alm": FamilyMutation(
        family="legalm_r6_relaxed_scanline_alm",
        source_kind="generated_matrix_variant",
        source_family="legalm_engine",
        matrix_variant="legalm_base_bounded_stage1",
        status="bringup_alias_not_algorithm_promotion",
        summary="Bring-up alias for LEGALM relaxed Stage1; uses current bounded Stage1 variant.",
    ),
}


def _load_matrix_module():
    # Imported lazily to avoid paying the large matrix registry cost for simple
    # metadata calls and to keep this module usable from materializer CLIs.
    import run_variant_experiment_matrix as matrix  # type: ignore

    return matrix


def _matrix_spec(name: str):
    matrix = _load_matrix_module()
    try:
        return matrix.VARIANTS[name]
    except KeyError as exc:
        raise KeyError(f"Unknown matrix variant: {name}") from exc


def matrix_variant_names() -> list[str]:
    matrix = _load_matrix_module()
    return sorted(matrix.VARIANTS)


def resolve_family_mutation(family: str) -> FamilyMutation:
    if family == "clean_evolve_base":
        return FamilyMutation(
            family=family,
            source_kind="clean_base",
            status="base_copy_only",
            summary="Clean prepared dpl_evolve base with no mutation.",
        )
    if family == "legalm_engine":
        return FamilyMutation(
            family=family,
            source_kind="materialized_sidecar",
            source_family="clean_evolve_base",
            patch_file="family_variants/legalm_engine/dpl_evolve.patch",
            status="implemented",
            summary="Committed LEGALM sidecar patch over clean dpl_evolve.",
        )
    if family in BRINGUP_ALIASES:
        return BRINGUP_ALIASES[family]
    if family in matrix_variant_names():
        spec = _matrix_spec(family)
        return FamilyMutation(
            family=family,
            source_kind="generated_matrix_variant",
            source_family=getattr(spec, "source_family", "clean_evolve_base"),
            matrix_variant=family,
            status="implemented",
            summary=getattr(spec, "summary", ""),
            metadata={
                "matrix_family": getattr(spec, "family", ""),
                "touched_symbol": getattr(spec, "touched_symbol", ""),
                "algorithmic_changes": list(getattr(spec, "algorithmic_changes", ())),
            },
        )
    raise KeyError(f"Unsupported family: {family}")


def list_supported_families() -> list[FamilyMutation]:
    families: dict[str, FamilyMutation] = {
        "clean_evolve_base": resolve_family_mutation("clean_evolve_base"),
        "legalm_engine": resolve_family_mutation("legalm_engine"),
    }
    for family in BRINGUP_ALIASES:
        families[family] = resolve_family_mutation(family)
    for name in matrix_variant_names():
        families.setdefault(name, resolve_family_mutation(name))
    return [families[key] for key in sorted(families)]


def apply_matrix_mutation(family: str, source_dir: Path) -> tuple[list[str], dict[str, Any]]:
    recipe = resolve_family_mutation(family)
    if recipe.matrix_variant is None:
        return [], {
            "family": family,
            "source_kind": recipe.source_kind,
            "status": recipe.status,
            "summary": recipe.summary,
        }

    spec = _matrix_spec(recipe.matrix_variant)
    touched = sorted(set(spec.apply(source_dir)))
    metadata = {
        "family": family,
        "source_kind": recipe.source_kind,
        "status": recipe.status,
        "summary": recipe.summary or getattr(spec, "summary", ""),
        "matrix_variant": recipe.matrix_variant,
        "matrix_family": getattr(spec, "family", ""),
        "source_family": getattr(spec, "source_family", "clean_evolve_base"),
        "touched_symbol": getattr(spec, "touched_symbol", ""),
        "algorithmic_changes": list(getattr(spec, "algorithmic_changes", ())),
        "touched_files": touched,
    }
    return touched, metadata


def write_mutation_metadata(path: Path, metadata: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
