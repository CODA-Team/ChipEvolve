"""Bind Flow inputs, dispatch the native controller and deliver its outputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import time
import zipfile
from pathlib import Path
from typing import Any

from .clock import flow_sdc
from .config import Deployment, read, write
from .controller import environment, inventory, invoke
from .handoff import flatten_archive
from .jobs import Jobs, digest
from .physical import measure, publish


def flow_source(deployment: Deployment, experiment: Path, *, design_id: str) -> Path:
    source = experiment / "source"
    shutil.copytree(
        deployment.value["flow_template"],
        source,
        ignore=shutil.ignore_patterns(
            ".git",
            ".venv",
            "results",
            "reports",
            "logs",
            "objects",
            "backup_dir",
            "__pycache__",
            "tmp",
        ),
    )
    formal = Path(deployment.value["professional"]["flow"]["source"])
    for file in (formal / "flow").glob("*.py"):
        shutil.copyfile(file, source / "flow" / file.name)
    for name in ("eval_tns.sh", "eval_tns.tcl", "maindriver.sh"):
        shutil.copyfile(formal / "flow" / name, source / "flow" / name)
    shutil.copyfile(formal / "run.sh", source / "run.sh")
    design = deployment.design(design_id)
    for library in design["libraries"]:
        target = (
            source
            / "flow/platforms"
            / design["platform"]
            / "lib/NLDM"
            / Path(library["path"]).name
        )
        shutil.copyfile(library["path"], target)
    config = source / "flow" / design["orfs_config"]
    overrides = design.get("baseline_overrides", "")
    for dependency in design.get("flow_dependencies", []):
        target = source / "flow/source-bindings" / dependency["destination"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(dependency["source"], target)
        overrides = overrides.replace("/work/" + dependency["destination"], str(target))
    with config.open("a") as stream:
        stream.write("\n" + overrides)
    return source


def tool_profile(deployment: Deployment, source: Path, experiment: Path) -> Path:
    profile = read(deployment.value["flow_tool_profile"])
    profile["flow_dir"] = str(source / "flow")
    profile["makefile_sha256"] = digest(source / "flow/Makefile")
    evaluator = source / "flow/eval_tns.tcl"
    if evaluator.is_file():
        profile["eval_tns_sha256"] = digest(evaluator)
    else:
        profile.pop("eval_tns_sha256", None)
    path = experiment / "tool-profile.json"
    write(path, profile)
    return path


def run_flow(
    deployment: Deployment,
    args: argparse.Namespace,
    experiment: Path,
    frame: dict[str, Any],
    objective: Path,
    context: Path,
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
    source_mode = getattr(args, "flow_recipe", "legacy") == "source"
    if source_mode:
        from .flow_recipe import prepare_native_source

        source = prepare_native_source(deployment, args.source, experiment)
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
    """Complete data delivery from saved native success without rerunning layout."""
    design = deployment.design(design_id)
    source = experiment / "source"
    summary = read(
        source
        / "flow/backup_dir"
        / design["platform"]
        / design["nickname"]
        / "llm_usage_summary.json"
    )
    if summary["exit_code"] != 0 or summary["status"] not in {
        "completed",
        "early_stop",
    }:
        raise ValueError("Collection requires a completed native Flow campaign")
    return _collect_flow_candidates(deployment, design_id, experiment, objective)


def _collect_flow_candidates(
    deployment: Deployment,
    design_id: str,
    experiment: Path,
    objective: Path,
    *,
    output: Path | None = None,
    native_campaign: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Deliver actual finished physical branches; the caller checks campaign state."""
    design = deployment.design(design_id)
    source = experiment / "source"
    output = output or experiment
    output.mkdir(exist_ok=True)
    jobs = Jobs(deployment, design_id, experiment)
    candidates = []
    for path in sorted(
        (experiment / "platform-state").glob("iteration-*/slot-*-route_finish.json")
    ):
        native = read(path)
        if native["status"] != "succeeded":
            continue
        record = {"run": native["terminal_run"], "artifacts": native["artifacts"]}
        folder = output / (path.parent.name + "-" + str(native["candidate_slot"]))
        folder.mkdir(exist_ok=True)
        files = {}
        for suffix, kind in {
            "odb": "raw_design_database",
            "spef": "raw_parasitics",
        }.items():
            file = folder / ("6_final." + suffix)
            jobs.materialize(record, kind, file, suffix="/6_final." + suffix)
            files[suffix] = file
        archive = folder / "flow.zip"
        jobs.materialize(record, "flow_archive", archive)
        measurement = experiment / (folder.name + "-common") / "measurement.json"
        measured = (
            read(measurement)
            if measurement.exists()
            else measure(
                jobs,
                folder.name + "-common",
                files["odb"],
                files["spef"],
                Path(design["sdc"]),
                native["run_id"],
                objective,
            )
        )
        if measured["physical_run_id"] != native["run_id"]:
            raise ValueError("Saved measurement belongs to another physical run")
        config = folder / "config.mk"
        recover_config(source / "flow", experiment / "platform-state", native, config)
        with zipfile.ZipFile(archive) as bundle:
            route = json.loads(bundle.read("flow/logs/5_2_route.json"))
        measured.update(
            route_drc=route["detailedroute__route__drc_errors"],
            flow_archive=str(archive),
            candidate_id=native["candidate_id"],
            native_config=str(config),
            native_flow_dir=str(source / "flow"),
            native_score="Retained in original Flow reports/CP0 feedback",
        )
        if (experiment / "recipe.json").is_file():
            measured["flow_recipe"] = str(experiment / "recipe.json")
        if native_campaign is not None:
            measured["native_campaign"] = native_campaign
            measured["native_method"] = {
                "kind": "completed-physical-evidence-of-failed-flow-search",
                "native_campaign": native_campaign,
                "native_search_completed": False,
            }
        candidate_frame = publish(
            jobs,
            measured,
            result_path=folder / "result.json",
            modes=("orfs", "opensta"),
        )
        write(folder / "result.json", candidate_frame)
        candidates.append(candidate_frame)
    if not candidates:
        raise RuntimeError("No completed native Flow candidate")
    write(output / "candidates.json", candidates)
    from .candidates import deliver_candidates

    return deliver_candidates(
        output,
        [Path(row["native_config"]).parent / "result.json" for row in candidates],
        native_campaign=native_campaign,
    )


def recover_config(
    flow: Path, state: Path, native: dict[str, Any], destination: Path
) -> None:
    """Later native rounds may replace config_N.mk; recover its frozen checkpoint."""
    name = "config_" + str(native["candidate_slot"]) + ".mk"
    wanted = native["input_hashes"]["config"]
    for path in flow.rglob(name):
        if digest(path) == wanted:
            shutil.copyfile(path, destination)
            return
    for path in (state / "checkpoints").glob("iteration-*/native-state.zip"):
        with zipfile.ZipFile(path) as bundle:
            for member in bundle.namelist():
                if Path(member).name == name:
                    content = bundle.read(member)
                    if hashlib.sha256(content).hexdigest() == wanted:
                        destination.write_bytes(content)
                        return
    raise ValueError("Cannot recover the actual native candidate configuration")


def resume_layout(
    jobs: Jobs,
    placement: Path,
    frame: dict[str, Any],
    objective: Path,
    producer: str,
    *,
    fact_modes: tuple[str, ...] = ("opendb", "orfs", "opensta"),
) -> dict[str, Any]:
    from .flow_recipe import require_make_paths
    from .handoff import placement_archive, registered_archive, verify_stage_archive

    deployment = jobs.deployment
    design = deployment.design(jobs.design_id)
    require_make_paths(jobs.experiment)
    archive_path = registered_archive(jobs, frame)["path"]
    flat = jobs.experiment / "source-checkpoint.zip"
    if not flat.exists():
        flatten_archive(Path(archive_path), flat)
    source = jobs.experiment / "source"
    if not source.exists():
        if frame.get("flow_recipe"):
            from .flow_recipe import inherit_prepared_source

            source = inherit_prepared_source(frame, jobs.experiment)
        else:
            source = flow_source(deployment, jobs.experiment, design_id=jobs.design_id)
    profile = tool_profile(deployment, source, jobs.experiment)
    config = jobs.experiment / "resume.mk"
    if frame.get("native_config"):
        config.write_text(
            Path(frame["native_config"])
            .read_text()
            .replace(frame["native_flow_dir"], str(source / "flow"))
        )
    else:
        config.write_text(
            "include " + str(source / "flow" / design["orfs_config"]) + "\n"
        )
    stage_sdc = Path(design["sdc"])
    if frame.get("flow_recipe"):
        # The native stage constraint belongs to the actual physical parent.
        # Replacing it with the global measurement SDC can undo the tuned clock
        # and change the units consumed by modern physical scripts.
        stage_sdc = jobs.experiment / "placement-source.sdc"
        with zipfile.ZipFile(flat) as bundle:
            stage_sdc.write_bytes(bundle.read("flow/results/3_place.sdc"))
    checkpoint = jobs.experiment / "placement.zip"
    if not checkpoint.exists():
        placement_archive(flat, placement, checkpoint, stage_sdc)
    sha = digest(placement)
    parent = producer
    record = None
    resources = design.get("orfs_execution", {})
    threads = resources.get("cpu_cores", 8)
    for phase in ("cts", "route_finish"):
        record = jobs.submit(
            phase,
            {
                "adapter": "a2_stage",
                "stage": phase,
                "threads": threads,
                "profile_path": "inputs/profile.json",
                "config_path": "inputs/config.mk",
                "sdc_path": "inputs/design.sdc",
                "checkpoint_path": "inputs/checkpoint.zip",
            },
            [
                {"source": str(p), "destination": "inputs/" + name}
                for p, name in [
                    (profile, "profile.json"),
                    (config, "config.mk"),
                    (stage_sdc, "design.sdc"),
                    (checkpoint, "checkpoint.zip"),
                ]
            ],
            parent=parent,
            objective=objective,
            cpu=threads,
            memory_gib=resources.get("memory_gib", 24),
        )
        checkpoint = jobs.experiment / (phase + ".zip")
        jobs.materialize(record, "flow_archive", checkpoint)
        consumed = verify_stage_archive(checkpoint, sha, phase)
        write(
            jobs.experiment / (phase + "-consumption.json"),
            {
                "run_id": record["run"]["run_id"],
                "placement_sha256": sha,
                "read_db": consumed,
            },
        )
        parent = record["run"]["run_id"]
    assert record is not None
    files = {}
    for suffix, kind in {
        "odb": "raw_design_database",
        "spef": "raw_parasitics",
    }.items():
        file = jobs.experiment / ("6_final." + suffix)
        jobs.materialize(record, kind, file, suffix="/6_final." + suffix)
        files[suffix] = file
    measured = measure(
        jobs,
        "common",
        files["odb"],
        files["spef"],
        Path(design["sdc"]),
        parent,
        objective,
    )
    with zipfile.ZipFile(checkpoint) as bundle:
        route = json.loads(bundle.read("flow/logs/5_2_route.json"))
    measured.update(
        route_drc=route["detailedroute__route__drc_errors"],
        flow_archive=str(checkpoint),
    )
    if frame.get("flow_recipe"):
        measured.update(
            flow_recipe=frame["flow_recipe"],
            native_config=str(config),
            native_flow_dir=str(source / "flow"),
            placement_source_sdc_sha256=digest(stage_sdc),
        )
    return publish(jobs, measured, modes=fact_modes)
