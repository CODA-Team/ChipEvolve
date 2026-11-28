"""Bind Flow inputs, dispatch the native controller and deliver its outputs."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from .clock import flow_sdc
from .config import Deployment, read, write
from .contracts import (
    DiagnosisContextRef,
    ObjectiveRef,
    PhysicalResult,
    SpecialistReply,
    SpecialistRequest,
)
from .flow_delivery import collect_completed, recover_config as recover_config
from .flow_recipe import flow_source as flow_source
from .flow_recipe import tool_profile as tool_profile
from .native_process import invoke
from .physical import resume_layout as resume_layout
from .result_io import (
    check_specialist_call,
    load_objective_ref,
    specialist_reply,
    wire_object,
)
from .source_snapshot import environment, inventory


def run_flow(
    deployment: Deployment,
    request: SpecialistRequest,
    experiment: Path,
    source: PhysicalResult,
    objective: ObjectiveRef,
    context: DiagnosisContextRef,
) -> SpecialistReply:
    """Typed specialist boundary; native wire handling remains in its adapter."""
    check_specialist_call("flow", request, source, objective, context)
    from .artifact_inputs import require_dispatch_inputs

    require_dispatch_inputs(source, request.capability, request.flow_recipe)
    _run_flow_transport(
        deployment,
        request,
        experiment,
        wire_object(source.wire),
        objective.path,
        context.path,
        source.origin.path,
    )
    return specialist_reply("flow", experiment / "result.json")


def _run_flow_transport(
    deployment: Deployment,
    args: SpecialistRequest,
    experiment: Path,
    frame: dict[str, Any],
    objective: Path,
    context: Path,
    source_path: Path,
) -> dict[str, Any]:
    design = deployment.design(args.design)
    binding = deployment.value["professional"]["flow"]
    execution = binding.get("execution", {})
    seed = binding.get("seed", 42)
    if type(seed) is not int or seed < 0:
        raise ValueError("Flow seed must be a nonnegative integer")
    threads = execution.get("threads", 8)
    memory_gib = execution.get("memory_gib", 24)
    stage_seconds = execution.get("stage_timeout_seconds", 7200)
    clean_quota = execution.get("clean_identity_quota")
    if clean_quota is not None and (type(clean_quota) is not int or clean_quota < 1):
        raise ValueError("Flow clean_identity_quota must be a positive integer")
    for field, value in (
        ("threads", threads),
        ("memory_gib", memory_gib),
        ("stage_timeout_seconds", stage_seconds),
    ):
        if type(value) is not int or value <= 0:
            raise ValueError("Flow execution " + field + " must be a positive integer")
    stage_memory = execution.get("stage_memory_gib", {})
    stages = {"place", "cts", "route_finish", "eval_place", "eval_cts", "eval_final"}
    if not isinstance(stage_memory, dict) or any(
        stage not in stages or type(memory) is not int or memory <= 0
        for stage, memory in stage_memory.items()
    ):
        raise ValueError(
            "Flow execution stage_memory_gib needs valid stages and positive integers"
        )
    source_mode = args.flow_recipe == "source"
    if source_mode:
        from .flow_recipe import prepare_native_source

        source = prepare_native_source(deployment, source_path, experiment)
    else:
        source = flow_source(deployment, experiment, design_id=args.design)
    if clean_quota is not None:
        policy_path = source / "flow/drp_config.json"
        policy = read(policy_path)
        policy["gwtw"]["clean_identity_quota"] = clean_quota
        write(policy_path, policy)
    config_dir = source / "flow/designs" / design["platform"] / design["nickname"]
    # Use OpenSTA's unit-explicit serialization and expose the same clock as
    # the native tuner's variable. All remaining constraints stay verbatim.
    sdc_path = (
        Path(read(experiment / "recipe.json")["sdc"])
        if source_mode
        else Path(frame["files"]["sdc"])
    )
    sdc = sdc_path.read_text()
    (config_dir / "constraint.sdc").write_text(
        flow_sdc(
            sdc,
            design["clock_period_ns"],
            time_unit="ps" if design["platform"] == "asap7" else "ns",
        )
    )
    profile = tool_profile(deployment, source, experiment)
    wrappers = experiment / "identity-tools"
    wrappers.mkdir()
    declared = read(profile)["toolchain"]["binaries"]
    for name in ("openroad", "yosys"):
        target = wrappers / name
        target.write_text(
            '#!/bin/sh\ncase "$1" in -version|-V|--version) printf "%s\\n" "'
            + name
            + " sha256="
            + declared[name]["sha256"]
            + '";; *) exit 1;; esac\n'
        )
        target.chmod(0o755)
    (source / "config/env.local.sh").write_text(
        "export OPENROAD_EXE="
        + str(wrappers / "openroad")
        + "\nexport YOSYS_EXE="
        + str(wrappers / "yosys")
        + "\n"
    )
    settings = experiment / "platform.json"
    write(
        settings,
        {
            "kernel_url": deployment.value["kernel_url"],
            "data_url": deployment.value["data_url"],
            "state_root": str(experiment / "platform-state"),
            "profile_path": str(profile),
            "threads": threads,
            "timeout_seconds": args.seconds,
            "stage_timeout_seconds": stage_seconds,
            "deadline_epoch": time.time() + args.seconds,
            "resources": {"memory_bytes": memory_gib << 30, "processes": 2048},
            **(
                {
                    "stage_resources": {
                        stage: {"memory_bytes": memory << 30, "processes": 2048}
                        for stage, memory in stage_memory.items()
                    }
                }
                if stage_memory
                else {}
            ),
        },
    )
    env = environment(objective, context)
    env["PATH"] = (
        str(Path(deployment.value["professional"]["flow"]["python"]).parent)
        + os.pathsep
        + env["PATH"]
    )
    env.update(
        DRP_EXECUTION_BACKEND="platform",
        DRP_PLATFORM_CONFIG=str(settings),
        DRP_LLM_TRANSPORT="codex",
        DRP_CODEX_AUDIT_DIR=str(experiment / "model-audit"),
    )
    if source_mode:
        env["DRP_SOURCE_PARAMETERS"] = str(experiment / "baseline-parameters.json")
        identity = inventory(source)
        identity.pop("prepared-files.json", None)
        write(source / "prepared-files.json", identity)
    command = [
        "bash",
        "run.sh",
        "-p",
        design["platform"],
        "-d",
        design["nickname"],
        "-o",
        "TNS_EVAL",
        "-i",
        str(args.rounds),
        "-r",
        str(args.candidates),
        "-s",
        "gwtw",
        "-A",
        "-P",
        "-F",
        "--seed",
        str(seed),
        "--cpus",
        str(threads),
        "--timeout",
        str(stage_seconds) + "s",
    ]
    invoke(command, source, env, experiment, args.seconds)
    return collect_flow(deployment, args.design, experiment, objective)


def collect_flow(
    deployment: Deployment, design_id: str, experiment: Path, objective: Path
) -> dict[str, Any]:
    """Compatibility wire output from the guarded Flow delivery owner."""
    return wire_object(
        collect_completed(
            deployment, design_id, experiment, load_objective_ref(objective)
        ).wire
    )
