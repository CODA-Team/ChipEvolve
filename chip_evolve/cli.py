"""Business commands return compact facts, not environment assembly instructions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import Deployment, write


def main() -> int:
    try:
        return _main()
    except Exception as error:
        from .lifecycle import WorkPending

        if not isinstance(error, WorkPending):
            raise
        receipt = error.receipt
        if receipt.get("experiment"):
            write(Path(receipt["experiment"]) / "status.json", receipt)
        print(json.dumps(receipt, ensure_ascii=False))
        return 3


def _main() -> int:
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
    run.add_argument("--flow-recipe", choices=["legacy", "source"], default=None)
    run.add_argument("--environment", type=Path)
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
            sub.add_argument("--validation", type=Path, required=True)
    status = commands.add_parser("status")
    status.add_argument("--design", required=True)
    watch = commands.add_parser("watch")
    watch.add_argument("--design", required=True)
    watch.add_argument("--run-id", required=True)
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
    candidates = commands.add_parser("candidates")
    candidates.add_argument("--reference", type=Path, required=True)
    candidates.add_argument("--result", type=Path, action="append", required=True)
    candidates.add_argument("--key", required=True)
    args = parser.parse_args()
    if args.command == "leaf":
        from .jobs import leaf

        return leaf(args.request)
    if not args.config:
        parser.error("--config identifies the local deployment")
    deployment = Deployment(args.config)
    from . import commands as handlers

    if args.command == "run":
        return handlers.run_experiment(deployment, args, parser)
    command = {
        "candidates": handlers.candidates,
        "resume": handlers.resume,
        "continue-goal": handlers.continue_goal,
        "validate": handlers.validate,
        "compare": handlers.compare,
        "collect-flow": handlers.collect_flow,
        "watch": handlers.watch,
        "status": handlers.status,
        "diagnose": handlers.diagnose,
        "select": handlers.select,
        "show": handlers.show,
    }[args.command]
    return command(deployment, args)
