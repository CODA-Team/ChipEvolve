"""Validate and dispatch a professional handoff from Codex."""

from __future__ import annotations

import argparse
import subprocess
from http.client import HTTPException
from pathlib import Path
from typing import Any

from eda_toolkits.context import load_context

from .config import Deployment, read, write
from .dpl import run_dpl
from .environment import verify_professional_toolchain
from .flow import run_flow
from .jobs import Jobs, digest
from .physical import verify_measurement_conditions


def execute(
    deployment: Deployment, args: argparse.Namespace, experiment: Path
) -> dict[str, Any]:
    if not args.source:
        raise ValueError("A professional task needs a registered source result")
    verify_professional_toolchain(deployment, args.capability)
    from .candidates import result_frame

    frame = result_frame(args.source)
    if frame["design_id"] != args.design:
        raise ValueError("Professional source belongs to another design")
    objective = (args.objective or Path(frame["objective"])).resolve()
    verify_measurement_conditions(
        deployment, args.design, objective, Path(deployment.design(args.design)["sdc"])
    )
    receipt = args.source.parent / "diagnosis.json"
    context = args.context or (
        Path(read(receipt)["context"])
        if receipt.exists()
        else args.source.parent / "query/professional-context.json"
    )
    if not context.is_file():
        from .diagnosis import diagnose

        diagnostic = diagnose(
            deployment,
            args.source.resolve(),
            "Explain the current design bottleneck with evidence and suggest native professional optimization mechanisms. Distinguish hypotheses from facts.",
            600,
            6,
        )
        context = Path(diagnostic["context"])
    context = context.resolve()
    packet = load_context(context)
    if not packet["confirmed_facts"] or not packet["evidence"]:
        raise ValueError("Professional context requires actual supported design facts")
    if (
        packet["scope"]["design_id"] != args.design
        or packet["scope"]["run_id"] != frame["run_id"]
    ):
        raise ValueError(
            "Professional diagnosis is not for the actual source design/run"
        )
    if (
        packet.get("identity_bindings")
        and packet["identity_bindings"]["source"]["run_id"] != frame["run_id"]
    ):
        raise ValueError("Structured Query source identity differs from the task")
    from .design_facts import ensure

    frame = ensure(deployment, args.source, frame)
    if packet["scope"]["snapshot_id"] not in frame["snapshot_ids"].values():
        raise ValueError("Professional diagnosis snapshot is not a source fact view")
    from .handoff import input_contract

    handoff = input_contract(frame, args.capability)
    write(experiment / "handoff-input.json", handoff)
    write(
        experiment / "input-receipt.json",
        {
            "source": str(args.source.resolve()),
            "source_run_id": frame["run_id"],
            "objective": str(objective),
            "context": str(context),
            "context_id": packet["context_id"],
            "budget": {
                "seconds": args.seconds,
                "rounds": args.rounds,
                "candidates": args.candidates,
            },
            "operation": args.operation,
            "handoff": str(experiment / "handoff-input.json"),
            "qualified_environment": (
                {"path": str(args.environment), "sha256": digest(args.environment)}
                if getattr(args, "environment", None)
                else None
            ),
        },
    )
    try:
        if args.capability == "flow":
            return run_flow(deployment, args, experiment, frame, objective, context)
        if args.capability == "dpl":
            return run_dpl(deployment, args, experiment, frame, objective, context)
        if args.capability == "goal":
            from .native import run_goal

            return run_goal(deployment, args, experiment, frame, objective, context)
        from .native import run_eco

        return run_eco(deployment, args, experiment, frame, objective, context)
    except (subprocess.TimeoutExpired, KeyboardInterrupt):
        try:
            Jobs(deployment, args.design, experiment).cancel_active()
        except (OSError, RuntimeError, HTTPException) as error:
            write(
                experiment / "native-job-cancellation-error.json",
                {"error_type": type(error).__name__, "detail": str(error)},
            )
        raise
