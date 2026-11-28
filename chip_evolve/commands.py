"""Business command handlers for the Codex entry point."""

from __future__ import annotations

import json
from pathlib import Path
from dataclasses import dataclass
from typing import TypeAlias

from .command_requests import (
    CandidateFactsCommand,
    CompareCommand,
    ContinueGoalCommand,
    DesignCommand,
    DiagnoseCommand,
    ResultCommand,
    ResumeCommand,
    RunCommand,
    NormalizedRunCommand,
    SelectCommand,
    ValidateCommand,
    WatchCommand,
)
from .config import Deployment, business_lock, read, write
from .contracts import (
    BusinessInputError,
    JSONValue,
    JSONObject,
    FileRef,
    ObjectiveRef,
    PhysicalResult,
    NativeCheckpoint,
    Capability,
    ExecutionState,
    DeliveryState,
)
from . import professional
from .lifecycle import WorkPending
from .result_io import (
    load_context_ref,
    load_physical_result,
    load_physical_source,
    load_result,
    load_single_result,
    wire_object,
    file_ref,
    load_objective_ref,
    freeze,
    object_at,
    text,
    sequence,
    execution_state,
    delivery_state,
)


def candidates(deployment: Deployment, args: CandidateFactsCommand) -> int:
    from .candidate_facts import build_candidate_facts

    design_id = load_single_result(args.reference).design_id
    experiment = deployment.experiment(design_id, args.key)
    write(
        experiment / "request.json",
        {
            "design": design_id,
            "capability": "candidate-facts",
            "reference": str(args.reference.resolve()),
            "results": [str(p.resolve()) for p in args.result],
        },
    )
    with business_lock(experiment):
        try:
            brief = build_candidate_facts(
                deployment,
                args.reference.resolve(),
                [p.resolve() for p in args.result],
                experiment,
            )
        except WorkPending:
            raise
        except Exception as error:
            write(
                experiment / "status.json",
                {
                    "status": "failed",
                    "error_type": type(error).__name__,
                    "detail": str(error),
                },
            )
            raise
        write(experiment / "status.json", {"status": "succeeded"})
    print(
        json.dumps(
            {"brief": str(brief), "receipt": str(experiment / "facts-receipt.json")}
        )
    )
    return 0


def resume(deployment: Deployment, args: ResumeCommand) -> int:
    from .recovery import recover

    experiment = deployment.state / "experiments" / args.design / args.key
    with business_lock(experiment):
        result = recover(deployment, args.design, args.key)
    print(
        json.dumps(
            {
                "result": str(experiment / "result.json"),
                "run_id": result.get("run_id"),
                "candidate_results": result.get("candidate_results", []),
                "native_candidate_evidence": result.get("native_candidate_evidence"),
            }
        )
    )
    return 0


def continue_goal(deployment: Deployment, args: ContinueGoalCommand) -> int:
    from .continuation import run as continue_goal

    design_id = load_physical_result(args.result).design_id
    load_context_ref(args.context)
    experiment = deployment.state / "experiments" / design_id / args.key
    try:
        result = continue_goal(
            deployment,
            args.result.resolve().parent,
            args.context.resolve(),
            args.key,
            args.seconds,
        )
    except WorkPending:
        raise
    except Exception as error:
        if experiment.exists():
            write(
                experiment / "status.json",
                {
                    "status": "failed",
                    "error_type": type(error).__name__,
                    "detail": str(error),
                },
            )
        raise
    print(
        json.dumps(
            {
                "result": str(experiment / "result.json"),
                "run_id": result["run_id"],
                "metrics": result["metrics"],
                "native_candidate_evidence": result.get("native_candidate_evidence"),
            }
        )
    )
    return 0


def validate(deployment: Deployment, args: ValidateCommand) -> int:
    from .validation import validate

    receipt = validate(
        deployment, args.result.resolve(), args.against.resolve(), args.key
    )
    print(json.dumps(receipt))
    return 0 if receipt["passed"] else 2


def compare(deployment: Deployment, args: CompareCommand) -> int:
    from .comparison_facts import compare_results

    print(
        json.dumps(
            compare_results(
                load_physical_result(args.against), load_physical_result(args.result)
            )
        )
    )
    return 0


def collect_flow(deployment: Deployment, args: ResumeCommand) -> int:
    from .flow import collect_flow

    experiment = deployment.state / "experiments" / args.design / args.key
    objective = Path(read(experiment / "input-receipt.json")["objective"])
    result = collect_flow(deployment, args.design, experiment, objective)
    write(
        experiment / "delivery-recovery.json",
        {"status": "succeeded", "result": str(experiment / "result.json")},
    )
    print(
        json.dumps(
            {
                "result": str(experiment / "result.json"),
                "candidate_results": result["candidate_results"],
            }
        )
    )
    return 0


def watch(deployment: Deployment, args: WatchCommand) -> int:
    from .jobs import Jobs
    from .lifecycle import observe

    client = Jobs(deployment, args.design, deployment.state).client
    run = client.run(args.run_id)
    if run["design_id"] != args.design:
        raise ValueError("Run belongs to another design")
    print(json.dumps(observe(client, run, worker_stale=120), ensure_ascii=False))
    return 0


def status(deployment: Deployment, args: DesignCommand) -> int:
    from .jobs import Jobs
    from .progress import experiment_status, flow_progress

    client = Jobs(deployment, args.design, deployment.state).client
    rows = []
    design_root = deployment.state / "experiments" / args.design
    paths = set(design_root.glob("*/request.json")) | set(
        design_root.glob("*/validation-request.json")
    )
    for path in sorted(paths):
        result = path.parent / "result.json"
        current = experiment_status(path.parent)
        rows.append(
            {
                "experiment": path.parent.name,
                "capability": read(path).get("capability", "validation"),
                "status": current,
                "result": str(result) if result.exists() else None,
                "lifecycle": [
                    {
                        "receipt": str(p),
                        **{
                            key: state[key]
                            for key in (
                                "phase",
                                "status",
                                "state",
                                "run_id",
                                "reason",
                                "waiting_for",
                                "identity",
                            )
                            if key in state
                        },
                    }
                    for pattern in (
                        "jobs/*/lifecycle.json",
                        "imports/*.json",
                        "logic/jobs/*/lifecycle.json",
                        "replay/jobs/*/lifecycle.json",
                        "replay/imports/*.json",
                    )
                    for p in sorted(path.parent.glob(pattern))
                    for state in [read(p)]
                    if state.get("status") not in {"succeeded", "completed"}
                ],
            }
        )
        progress = flow_progress(client, path.parent)
        if progress is not None:
            rows[-1]["native_progress"] = progress
    active = [
        {
            "run_id": row["run_id"],
            "task_id": row["task_id"],
            "status": row["status"],
        }
        for phase in ("queued", "running")
        for row in client.runs(design_id=args.design, status=phase)
    ]
    print(
        json.dumps(
            {
                "design_id": args.design,
                "experiments": rows,
                "active_eda_jobs": active,
            },
            ensure_ascii=False,
        )
    )
    return 0


@dataclass(frozen=True)
class _RunBinding:
    command: NormalizedRunCommand
    environment: FileRef | None
    image_sha256: str | None
    has_runtime: bool


@dataclass(frozen=True)
class _BaselineRun(_RunBinding):
    objective: ObjectiveRef | None


@dataclass(frozen=True)
class _ReplayRun(_RunBinding):
    source: PhysicalResult | NativeCheckpoint
    objective: ObjectiveRef | None


@dataclass(frozen=True)
class _SpecialistRun(_RunBinding):
    inputs: professional.SpecialistPreflight


PreparedRun: TypeAlias = _BaselineRun | _ReplayRun | _SpecialistRun


@dataclass(frozen=True)
class RunNotice:
    """CLI transport projection; not another Result or a fabricated file origin."""

    result: Path
    design_id: str
    capability: Capability
    run_id: str | None
    metrics: JSONObject | None
    candidate_results: tuple[JSONValue, ...]
    native_candidate_evidence: JSONObject | None
    execution_state: ExecutionState
    delivery_state: DeliveryState

    def to_wire(self) -> dict[str, JSONValue]:
        return {
            "result": str(self.result),
            "design_id": self.design_id,
            "capability": self.capability,
            "run_id": self.run_id,
            "metrics": self.metrics,
            "execution_state": self.execution_state,
            "delivery_state": self.delivery_state,
            "candidate_results": list(self.candidate_results),
            "native_candidate_evidence": self.native_candidate_evidence,
        }


def _inspect_run(deployment: Deployment, args: RunCommand) -> PreparedRun:
    configured = deployment.value.get("qualified_environments", {}).get(args.design)
    command = args.normalized(Path(configured) if configured else None)
    if command.capability == "orfs":
        source = load_physical_source(command.source) if command.source else None
        objective = load_objective_ref(command.objective) if command.objective else None
        if command.context:
            load_context_ref(command.context)
        specialist = None
    else:
        specialist = professional.inspect_inputs(deployment, command)
        source, objective = None, None
    environment = None
    if command.environment:
        from .environment import check_environment

        environment = file_ref(command.environment)
        check_environment(
            deployment,
            command.environment,
            command.design,
            command.capability,
            command.source,
            command.flow_recipe,
        )
        if file_ref(command.environment) != environment:
            raise BusinessInputError(
                "changed_input",
                "$.environment",
                "environment changed during qualification",
            )
    elif deployment.value.get("runtime") and deployment.value.get("toolchain", {}).get(
        "image_sha256"
    ):
        from .environment import verify_runtime_image

        verify_runtime_image(deployment)
    image = deployment.value.get("toolchain", {}).get("image_sha256")
    binding = (command, environment, image, bool(deployment.value.get("runtime")))
    if specialist is not None:
        return _SpecialistRun(*binding, specialist)
    if command.operation == "replay":
        if source is None:
            raise BusinessInputError(
                "missing_field", "$.source", "ORFS replay requires a source"
            )
        return _ReplayRun(*binding, source, objective)
    return _BaselineRun(*binding, objective)


def _open_run(deployment: Deployment, prepared: PreparedRun) -> Path:
    command = prepared.command
    if (
        prepared.environment
        and file_ref(prepared.environment.path) != prepared.environment
    ):
        raise BusinessInputError(
            "changed_input", "$.environment", "environment changed after preflight"
        )
    experiment = deployment.experiment(command.design, command.key)
    request = command.to_wire()
    if prepared.environment:
        request["environment_sha256"] = prepared.environment.sha256
    if prepared.has_runtime:
        request["image_sha256"] = prepared.image_sha256
    write(experiment / "request.json", request)
    return experiment


def _notice(value: object, prepared: PreparedRun, experiment: Path) -> RunNotice:
    """Project original wire values without rewriting a measured result."""
    row = object_at(freeze(value), "$.run.output")
    return RunNotice(
        experiment / "result.json",
        prepared.command.design,
        prepared.command.capability,
        text(row["run_id"], "$.run.output.run_id")
        if row.get("run_id") is not None
        else None,
        object_at(row["metrics"], "$.run.output.metrics")
        if row.get("metrics") is not None
        else None,
        sequence(row.get("candidate_results", []), "$.run.output.candidate_results"),
        object_at(
            row["native_candidate_evidence"], "$.run.output.native_candidate_evidence"
        )
        if row.get("native_candidate_evidence") is not None
        else None,
        execution_state(row.get("execution_state", "succeeded")),
        delivery_state(row.get("delivery_state", "completed")),
    )


def _execute_run(
    deployment: Deployment, prepared: PreparedRun, experiment: Path
) -> RunNotice:
    command = prepared.command
    with business_lock(experiment):
        try:
            if isinstance(prepared, _BaselineRun):
                from .physical import baseline

                result = baseline(
                    deployment,
                    command.design,
                    experiment,
                    command.seconds,
                    objective=prepared.objective.path if prepared.objective else None,
                )
            elif isinstance(prepared, _ReplayRun):
                from .native_physical import repair

                result = repair(
                    deployment,
                    command.design,
                    experiment,
                    prepared.source.origin.path,
                    command.seconds,
                    objective=prepared.objective.path if prepared.objective else None,
                )
            else:
                inputs = professional.prepare_inputs(
                    deployment, prepared.inputs, experiment
                )
                reply = professional.dispatch_prepared(deployment, inputs, experiment)
                result = wire_object(reply.output.wire)
            notice = _notice(result, prepared, experiment)
            write(experiment / "status.json", {"status": "succeeded"})
        except WorkPending:
            raise
        except Exception as error:
            write(
                experiment / "status.json",
                {
                    "status": "failed",
                    "error_type": type(error).__name__,
                    "detail": str(error),
                },
            )
            raise
    return notice


def run_experiment(deployment: Deployment, args: RunCommand) -> int:
    prepared = _inspect_run(deployment, args)
    experiment = _open_run(deployment, prepared)
    notice = _execute_run(deployment, prepared, experiment)
    print(json.dumps(wire_object(notice.to_wire())))
    return 0


def diagnose(deployment: Deployment, args: DiagnoseCommand) -> int:
    from .diagnosis import diagnose

    print(
        json.dumps(
            diagnose(
                deployment,
                args.result.resolve(),
                args.question,
                args.seconds,
                args.steps,
                against=args.against,
                analyses=args.analyses,
            )
        )
    )
    return 0


def select(deployment: Deployment, args: SelectCommand) -> int:
    from .selection import select_result

    print(
        json.dumps(
            select_result(
                deployment,
                load_single_result(args.result.resolve()),
                args.reason,
                validation=args.validation.resolve(),
            )
        )
    )
    return 0


def show(deployment: Deployment, args: ResultCommand) -> int:
    result = wire_object(load_result(args.result).wire)
    if result.get("schema_version") == "chip-evolve.candidate-delivery.v1":
        print(json.dumps(result, indent=2))
        return 0
    print(
        json.dumps(
            {
                key: result.get(key)
                for key in [
                    "design_id",
                    "run_id",
                    "physical_run_id",
                    "objective_id",
                    "condition_id",
                    "metrics",
                    "snapshot_ids",
                ]
            },
            indent=2,
        )
    )
    return 0
