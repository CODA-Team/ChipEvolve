"""Bind validated business inputs and dispatch one typed specialist request."""

from __future__ import annotations

import subprocess
from http.client import HTTPException
from pathlib import Path
from dataclasses import dataclass

from .command_requests import NormalizedRunCommand
from .artifact_inputs import require_dispatch_inputs
from .config import Deployment, read, write
from .contracts import (
    BusinessInputError,
    DiagnosisContextRef,
    PhysicalResult,
    QualifiedEnvironmentRef,
    SpecialistReply,
    SpecialistRequest,
    SpecialistAdapter,
    SpecialistKind,
    ObjectiveRef,
    Handoff,
)
from . import dpl, eco, flow, goal
from .environment import verify_professional_toolchain
from .jobs import Jobs
from .physical import verify_measurement_conditions
from .result_io import (
    file_ref,
    load_context_ref,
    load_objective_ref,
    load_physical_result,
    physical_view,
    wire_object,
)


def bind_context(
    source: PhysicalResult, context: DiagnosisContextRef, *, snapshots: bool = True
) -> None:
    """A supported fact from another checkpoint cannot authorize this dispatch."""
    if (context.scope.design_id, context.scope.run_id) != (
        source.design_id,
        source.run_id,
    ):
        raise BusinessInputError(
            "identity_mismatch",
            "$.scope.run_id",
            "Professional diagnosis is not for the actual source design/run",
        )
    if snapshots and context.scope.snapshot_id not in source.snapshot_ids.values():
        raise BusinessInputError(
            "identity_mismatch",
            "$.scope.snapshot_id",
            "Professional diagnosis snapshot is not a source fact view",
        )
    # Query may additionally bind explicit input roles. Validate known fields
    # before using them; the packet's raw bytes remain the authority for its ID.
    from .result_io import identifier, object_at, required

    bindings = context.wire.get("identity_bindings")
    if bindings:
        row = object_at(bindings, "$.identity_bindings")
        bound = object_at(required(row, "source"), "$.identity_bindings.source")
        run = identifier(required(bound, "run_id"), "$.identity_bindings.source.run_id")
        if run != source.run_id:
            raise BusinessInputError(
                "identity_mismatch",
                "$.identity_bindings.source.run_id",
                "Structured Query source identity differs from the task",
            )


@dataclass(frozen=True)
class SpecialistPreflight:
    request: SpecialistRequest
    source: PhysicalResult
    objective: ObjectiveRef
    context: DiagnosisContextRef | None
    context_path: Path


@dataclass(frozen=True)
class PreparedSpecialist:
    request: SpecialistRequest
    source: PhysicalResult
    objective: ObjectiveRef
    context: DiagnosisContextRef
    handoff: Handoff


def inspect_inputs(
    deployment: Deployment, args: NormalizedRunCommand
) -> SpecialistPreflight:
    """Read and bind inputs; never materialize facts, diagnose or submit work."""
    if not args.source:
        raise BusinessInputError(
            "missing_field",
            "$.source",
            "A professional task needs a registered source result",
        )
    environment = None
    if args.environment:
        from .result_io import identifier, read_document, required

        origin, wire = read_document(args.environment)
        environment = QualifiedEnvironmentRef(
            origin, identifier(required(wire, "environment_id"), "$.environment_id")
        )
    request = args.specialist(environment)
    source = load_physical_result(args.source)
    if source.design_id != args.design:
        raise BusinessInputError(
            "identity_mismatch",
            "$.design_id",
            "Professional source belongs to another design",
        )
    objective = (
        load_objective_ref(args.objective) if args.objective else source.objective
    )
    if (objective.design_id, objective.objective_id, objective.condition_id) != (
        source.design_id,
        source.objective_id,
        source.condition_id,
    ):
        raise BusinessInputError(
            "identity_mismatch",
            "$.objective_id",
            "Professional objective differs from source",
        )
    receipt = args.source.parent / "diagnosis.json"
    context_path = args.context or (
        Path(read(receipt)["context"])
        if receipt.exists()
        else args.source.parent / "query/professional-context.json"
    )
    # Reject a supplied malformed context before ensure/diagnose can submit work.
    context = load_context_ref(context_path) if context_path.is_file() else None
    if args.context and context is None:
        raise BusinessInputError("missing_file", "$.context", str(context_path))
    if context is not None:
        bind_context(source, context, snapshots="deferred_facts" not in source.wire)
    verify_professional_toolchain(deployment, request.capability)
    verify_measurement_conditions(
        deployment,
        args.design,
        objective.path,
        Path(deployment.design(args.design)["sdc"]),
    )
    require_dispatch_inputs(source, request.capability, request.flow_recipe)
    if request.capability in {"flow", "dpl"}:
        from .flow_recipe import require_make_paths

        require_make_paths(deployment.state / "experiments" / args.design / args.key)
    return SpecialistPreflight(request, source, objective, context, context_path)


def prepare_inputs(
    deployment: Deployment, preflight: SpecialistPreflight, experiment: Path
) -> PreparedSpecialist:
    """Materialize scoped facts and persist the verified, unchanged handoff wire."""
    request, source, objective, context = (
        preflight.request,
        preflight.source,
        preflight.objective,
        preflight.context,
    )
    environment = request.environment
    frozen = (
        (source.origin, objective.origin)
        + ((context.origin,) if context is not None else ())
        + ((environment.origin,) if environment is not None else ())
    )
    for origin in frozen:
        if file_ref(origin.path) != origin:
            raise BusinessInputError(
                "changed_input",
                "$",
                "input changed after preflight: " + str(origin.path),
            )
    from .design_facts import ensure
    from .handoff import build_handoff

    source = physical_view(
        source.origin, ensure(deployment, source.origin.path, wire_object(source.wire))
    )
    if context is None:
        from .diagnosis import diagnose

        diagnostic = diagnose(
            deployment,
            source.origin.path,
            "Explain the current design bottleneck with evidence and suggest native professional optimization mechanisms. Distinguish hypotheses from facts.",
            600,
            6,
        )
        context = load_context_ref(Path(diagnostic["context"]))
    bind_context(source, context)
    require_dispatch_inputs(source, request.capability, request.flow_recipe)
    handoff = build_handoff(
        Jobs(deployment, request.design, experiment),
        source,
        request.capability,
        flow_recipe=request.flow_recipe,
    )
    # Bind the same bytes that passed the loaders to this dispatch receipt.
    origins = (source.origin, objective.origin, context.origin) + (
        (environment.origin,) if environment else ()
    )
    for origin in origins:
        if file_ref(origin.path) != origin:
            raise BusinessInputError("changed_input", "$", str(origin.path))
    write(experiment / "handoff-input.json", wire_object(handoff.wire))
    write(
        experiment / "input-receipt.json",
        {
            "source": str(source.origin.path),
            "source_run_id": source.run_id,
            "objective": str(objective.path),
            "context": str(context.path),
            "context_id": context.context_id,
            "budget": {
                "seconds": request.seconds,
                "rounds": request.rounds,
                "candidates": request.candidates,
            },
            "operation": request.operation,
            "handoff": str(experiment / "handoff-input.json"),
            "qualified_environment": {
                "path": str(environment.origin.path),
                "sha256": environment.origin.sha256,
            }
            if environment
            else None,
        },
    )
    return PreparedSpecialist(request, source, objective, context, handoff)


def select_adapter(capability: SpecialistKind) -> SpecialistAdapter:
    """Select one of the four explicit owners, without caching a callable."""
    adapters: dict[SpecialistKind, SpecialistAdapter] = {
        "flow": flow.run_flow,
        "dpl": dpl.run_dpl,
        "goal": goal.run_goal,
        "eco": eco.run_eco,
    }
    if capability not in adapters:
        raise BusinessInputError(
            "invalid_capability", "$.capability", "unknown specialist"
        )
    return adapters[capability]


def dispatch_prepared(
    deployment: Deployment, prepared: PreparedSpecialist, experiment: Path
) -> SpecialistReply:
    """Keep cancellation around the specialist call, outside preparation."""
    request = prepared.request
    adapter = select_adapter(request.capability)
    try:
        return adapter(
            deployment,
            request,
            experiment,
            prepared.source,
            prepared.objective,
            prepared.context,
        )
    except (subprocess.TimeoutExpired, KeyboardInterrupt):
        try:
            Jobs(deployment, request.design, experiment).cancel_active()
        except (OSError, RuntimeError, HTTPException) as error:
            write(
                experiment / "native-job-cancellation-error.json",
                {"error_type": type(error).__name__, "detail": str(error)},
            )
        raise


def execute(
    deployment: Deployment, args: NormalizedRunCommand, experiment: Path
) -> SpecialistReply:
    """Compatibility orchestration over the same three named transaction stages."""
    preflight = inspect_inputs(deployment, args)
    prepared = prepare_inputs(deployment, preflight, experiment)
    return dispatch_prepared(deployment, prepared, experiment)
