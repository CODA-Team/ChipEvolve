"""Typed interpretation of the existing root handoff wire; no EF operations."""

from __future__ import annotations

from pathlib import Path

from .contracts import (
    BusinessInputError,
    DplInputs,
    EcoInputs,
    FlowLegacyInputs,
    FlowRecipe,
    FlowSourceInputs,
    GoalInputs,
    Handoff,
    JSONObject,
    PhysicalResult,
    ProfessionalInputs,
    RegisteredRecipeRef,
    SpecialistKind,
)
from .result_io import (
    read_document,
    identifier,
    object_at,
    path_value,
    registered_ref,
    required,
    sha256,
    text,
)


def parse_handoff(
    value: JSONObject,
    source: PhysicalResult,
    receiver: SpecialistKind,
    *,
    flow_recipe: FlowRecipe,
) -> Handoff:
    design = identifier(required(value, "design_id"), "$.design_id")
    run = identifier(required(value, "source_run_id"), "$.source_run_id")
    objective = sha256(required(value, "objective_id"), "$.objective_id")
    condition = sha256(required(value, "condition_id"), "$.condition_id")
    if required(value, "receiver") != receiver or (
        design,
        run,
        objective,
        condition,
    ) != (source.design_id, source.run_id, source.objective_id, source.condition_id):
        raise BusinessInputError(
            "identity_mismatch", "$.receiver", "handoff differs from source/receiver"
        )
    raw = object_at(required(value, "source_files"), "$.source_files")
    base = source.origin.path.parent

    def ref(key: str):
        return registered_ref(
            required(raw, key, "$.source_files"), "$.source_files." + key, base
        )

    inputs: ProfessionalInputs
    if receiver == "eco":
        inputs = EcoInputs(ref("odb"), ref("sdc"), ref("spef"))
    elif receiver == "goal":
        inputs = GoalInputs(ref("odb"), ref("sdc"), ref("v"), ref("def"))
    elif receiver == "dpl":
        inputs = DplInputs(ref("flow_archive"))
    elif flow_recipe == "legacy":
        inputs = FlowLegacyInputs(ref("sdc"))
    else:
        recipe = value.get("flow_recipe")
        inputs = FlowSourceInputs(
            source.origin,
            load_recipe_ref(path_value(recipe, base, "$.flow_recipe"))
            if recipe is not None
            else None,
        )
    return Handoff(
        run,
        design,
        objective,
        condition,
        receiver,
        inputs,
        text(required(value, "transformations"), "$.transformations"),
        text(required(value, "acceptance"), "$.acceptance"),
        value,
    )


def load_recipe_ref(path: Path) -> RegisteredRecipeRef:
    origin, value = read_document(path)
    if required(value, "schema_version") != "chip-evolve.flow-source-recipe.v1":
        raise BusinessInputError(
            "unsupported_schema",
            "$.flow_recipe.schema_version",
            "shared source recipe required",
        )
    return RegisteredRecipeRef(
        origin,
        identifier(required(value, "source_run_id"), "$.flow_recipe.source_run_id"),
        sha256(required(value, "result_sha256"), "$.flow_recipe.result_sha256"),
    )
