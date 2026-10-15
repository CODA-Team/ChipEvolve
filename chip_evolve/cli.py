"""Business commands return compact facts, not environment assembly instructions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import Deployment, business_lock, read, write


def main() -> int:
    parser = argparse.ArgumentParser(prog="chip-evolve")
    parser.add_argument("--config", type=Path)
    commands = parser.add_subparsers(dest="command", required=True)
    child = commands.add_parser("leaf")
    child.add_argument("--request", type=Path, required=True)
    run = commands.add_parser("run")
    run.add_argument("--design", required=True)
    run.add_argument(
        "--capability", choices=["orfs", "flow", "dpl", "goal", "eco"], required=True
    )
    run.add_argument("--key", required=True)
    run.add_argument("--source", type=Path)
    run.add_argument("--objective", type=Path)
    run.add_argument("--context", type=Path)
    run.add_argument("--code-source", type=Path)
    run.add_argument("--seconds", type=int)
    run.add_argument("--rounds", type=int)
    run.add_argument("--candidates", type=int)
    run.add_argument(
        "--operation", choices=["replay", "evolve", "framework"], default="evolve"
    )
    query = commands.add_parser("diagnose")
    query.add_argument("--result", type=Path, required=True)
    query.add_argument("--against", type=Path)
    query.add_argument(
        "--question",
        default="Explain current timing, power and area limits with cited design evidence. Distinguish observed facts from hypotheses; suggest mechanisms for the professional agents.",
    )
    query.add_argument("--seconds", type=int, default=600)
    query.add_argument("--steps", type=int, default=6)
    for name in ["show", "select"]:
        sub = commands.add_parser(name)
        sub.add_argument("--result", type=Path, required=True)
        if name == "select":
            sub.add_argument("--reason", required=True)
    status = commands.add_parser("status")
    status.add_argument("--design", required=True)
    collect = commands.add_parser("collect-flow")
    collect.add_argument("--design", required=True)
    collect.add_argument("--key", required=True)
    resume = commands.add_parser("resume")
    resume.add_argument("--design", required=True)
    resume.add_argument("--key", required=True)
    continuation = commands.add_parser("continue-goal")
    continuation.add_argument("--result", type=Path, required=True)
    continuation.add_argument("--context", type=Path, required=True)
    continuation.add_argument("--key", required=True)
    continuation.add_argument("--seconds", type=int, default=21600)
    validation = commands.add_parser("validate")
    validation.add_argument("--result", type=Path, required=True)
    validation.add_argument("--against", type=Path, required=True)
    validation.add_argument("--key", required=True)
    comparison = commands.add_parser("compare")
    comparison.add_argument("--result", type=Path, required=True)
    comparison.add_argument("--against", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "leaf":
        from .jobs import leaf

        return leaf(args.request)
    if not args.config:
        parser.error("--config identifies the local deployment")
    deployment = Deployment(args.config)
    if args.command == "resume":
        from .delivery import recover

        experiment = deployment.state / "experiments" / args.design / args.key
        with business_lock(experiment):
            result = recover(deployment, args.design, args.key)
        print(
            json.dumps(
                {"result": str(experiment / "result.json"), "run_id": result["run_id"]}
            )
        )
    elif args.command == "continue-goal":
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
                }
            )
        )
    elif args.command == "validate":
        from .validation import validate

        receipt = validate(
            deployment, args.result.resolve(), args.against.resolve(), args.key
        )
        print(json.dumps(receipt))
        return 0 if receipt["passed"] else 2
    elif args.command == "compare":
        from .comparisons import compare

        print(json.dumps(compare(read(args.against), read(args.result))))
    elif args.command == "collect-flow":
        from .professional import collect_flow

        experiment = deployment.state / "experiments" / args.design / args.key
        objective = Path(read(experiment / "input-receipt.json")["objective"])
        result = collect_flow(deployment, args.design, experiment, objective)
        write(
            experiment / "delivery-recovery.json",
            {"status": "succeeded", "result": str(experiment / "result.json")},
        )
        print(
            json.dumps(
                {"result": str(experiment / "result.json"), "run_id": result["run_id"]}
            )
        )
    elif args.command == "status":
        from .jobs import Jobs

        rows = []
        design_root = deployment.state / "experiments" / args.design
        paths = set(design_root.glob("*/request.json")) | set(
            design_root.glob("*/validation-request.json")
        )
        for path in sorted(paths):
            status_file = path.parent / "status.json"
            result = path.parent / "result.json"
            current = (
                read(status_file) if status_file.exists() else {"status": "in_progress"}
            )
            if (path.parent / "delivery-recovery.json").exists():
                current = {
                    "status": "succeeded",
                    "delivery_recovered": True,
                    "prior_failure": current,
                }
            rows.append(
                {
                    "experiment": path.parent.name,
                    "capability": read(path).get("capability", "validation"),
                    "status": current,
                    "result": str(result) if result.exists() else None,
                }
            )
        client = Jobs(deployment, args.design, deployment.state).client
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
    elif args.command == "run":
        if args.operation == "framework" and args.capability != "dpl":
            parser.error(
                "--operation framework selects the original DPL framework only"
            )
        if args.code_source and (
            args.capability != "dpl" or args.operation != "replay"
        ):
            parser.error("--code-source requires DPL --operation replay")
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
        request = {
            key: str(value) if isinstance(value, Path) else value
            for key, value in vars(args).items()
        }
        write(experiment / "request.json", request)
        with business_lock(experiment):
            try:
                if args.capability == "orfs":
                    from .physical import baseline

                    result = baseline(deployment, args.design, experiment, args.seconds)
                else:
                    from .professional import execute

                    result = execute(deployment, args, experiment)
                write(experiment / "status.json", {"status": "succeeded"})
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
                    "run_id": result["run_id"],
                    "metrics": result["metrics"],
                }
            )
        )
    elif args.command == "diagnose":
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
                )
            )
        )
    elif args.command == "select":
        from .selection import select

        print(json.dumps(select(deployment, args.result.resolve(), args.reason)))
    else:
        result = read(args.result)
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
