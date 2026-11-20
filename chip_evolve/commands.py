"""Business command handlers for the Codex entry point."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import Deployment, business_lock, read, write
from .lifecycle import WorkPending


def candidates(deployment: Deployment, args: argparse.Namespace) -> int:
    from .candidate_facts import build_candidate_facts

    design_id = read(args.reference)["design_id"]
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


def resume(deployment: Deployment, args: argparse.Namespace) -> int:
    from .delivery import recover

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


def continue_goal(deployment: Deployment, args: argparse.Namespace) -> int:
    from .continuation import run as continue_goal

    design_id = read(args.result)["design_id"]
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


def validate(deployment: Deployment, args: argparse.Namespace) -> int:
    from .validation import validate

    receipt = validate(
        deployment, args.result.resolve(), args.against.resolve(), args.key
    )
    print(json.dumps(receipt))
    return 0 if receipt["passed"] else 2


def compare(deployment: Deployment, args: argparse.Namespace) -> int:
    from .comparisons import compare

    print(json.dumps(compare(read(args.against), read(args.result))))
    return 0


def collect_flow(deployment: Deployment, args: argparse.Namespace) -> int:
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


def watch(deployment: Deployment, args: argparse.Namespace) -> int:
    from .jobs import Jobs
    from .lifecycle import observe

    client = Jobs(deployment, args.design, deployment.state).client
    run = client.run(args.run_id)
    if run["design_id"] != args.design:
        raise ValueError("Run belongs to another design")
    print(json.dumps(observe(client, run, worker_stale=120), ensure_ascii=False))
    return 0


def status(deployment: Deployment, args: argparse.Namespace) -> int:
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


def run_experiment(
    deployment: Deployment, args: argparse.Namespace, parser: argparse.ArgumentParser
) -> int:
    if args.environment is None:
        configured = deployment.value.get("qualified_environments", {}).get(args.design)
        args.environment = Path(configured) if configured else None
    args.flow_recipe = args.flow_recipe or (
        "source" if args.capability == "flow" else "legacy"
    )
    if args.flow_recipe != "legacy" and args.capability != "flow":
        parser.error("--flow-recipe source applies to Flow only")
    if args.operation == "framework" and args.capability != "dpl":
        parser.error("--operation framework selects the original DPL framework only")
    if args.capability == "orfs" and bool(args.source) != (args.operation == "replay"):
        parser.error(
            "ORFS source handoff requires --operation replay and --source together"
        )
    if args.code_source and (
        args.capability not in {"dpl", "goal"} or args.operation != "replay"
    ):
        parser.error("--code-source requires DPL or Goal --operation replay")
    if args.environment:
        from .environment import check_environment

        check_environment(
            deployment,
            args.environment.resolve(),
            args.design,
            args.capability,
            args.source,
            args.flow_recipe,
        )
    elif deployment.value.get("runtime") and deployment.value.get("toolchain", {}).get(
        "image_sha256"
    ):
        from .environment import verify_runtime_image

        verify_runtime_image(deployment)
    if args.candidates is not None and args.capability not in {"flow", "dpl"}:
        parser.error("--candidates applies to Flow/DPL; Goal keeps four Students")
    args.seconds = (
        args.seconds
        if args.seconds is not None
        else (10800 if args.capability in {"flow", "dpl", "goal"} else 5400)
    )
    args.rounds = (
        args.rounds
        if args.rounds is not None
        else (2 if args.capability == "flow" else 1)
    )
    args.candidates = (
        args.candidates
        if args.candidates is not None
        else {"flow": 12, "dpl": 3, "goal": 4}.get(args.capability)
    )
    experiment = deployment.experiment(args.design, args.key)
    if args.objective:
        args.objective = args.objective.resolve()
    request = {
        key: str(value) if isinstance(value, Path) else value
        for key, value in vars(args).items()
    }
    write(experiment / "request.json", request)
    with business_lock(experiment):
        try:
            if args.capability == "orfs":
                if args.operation == "replay":
                    from .native_physical import repair

                    result = repair(
                        deployment,
                        args.design,
                        experiment,
                        args.source,
                        args.seconds,
                        objective=args.objective,
                    )
                else:
                    from .physical import baseline

                    result = baseline(
                        deployment,
                        args.design,
                        experiment,
                        args.seconds,
                        objective=args.objective.resolve() if args.objective else None,
                    )
            else:
                from .professional import execute

                result = execute(deployment, args, experiment)
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
    print(
        json.dumps(
            {
                "result": str(experiment / "result.json"),
                "design_id": args.design,
                "capability": args.capability,
                "run_id": result.get("run_id"),
                "metrics": result.get("metrics"),
                "execution_state": "succeeded",
                "delivery_state": "completed",
                "candidate_results": result.get("candidate_results", []),
                "native_candidate_evidence": result.get("native_candidate_evidence"),
            }
        )
    )
    return 0


def diagnose(deployment: Deployment, args: argparse.Namespace) -> int:
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


def select(deployment: Deployment, args: argparse.Namespace) -> int:
    from .selection import select

    print(
        json.dumps(
            select(
                deployment,
                args.result.resolve(),
                args.reason,
                validation=args.validation.resolve(),
            )
        )
    )
    return 0


def show(deployment: Deployment, args: argparse.Namespace) -> int:
    result = read(args.result)
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
