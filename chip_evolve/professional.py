"""Native capability dispatch; search and scoring remain inside each project."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tarfile
import time
import zipfile
from pathlib import Path
from typing import Any

from eda_toolkits.context import load_context

from .clock import flow_sdc
from .config import Deployment, read, write
from .jobs import Jobs, digest
from .physical import measure, publish


def freeze(source: Path, destination: Path, *, paths: list[str] | None = None) -> None:
    destination.mkdir(parents=True)
    archive = destination.parent / (destination.name + "-source.tar")
    roots = (
        subprocess.check_output(["git", "ls-tree", "--name-only", "HEAD"], cwd=source)
        .decode()
        .splitlines()
    )
    archived_paths = [name for name in paths or [] if name.split("/")[0] in roots]
    with archive.open("wb") as output:
        subprocess.run(
            ["git", "archive", "HEAD", *archived_paths],
            cwd=source,
            stdout=output,
            check=True,
            env=dict(os.environ, GIT_LFS_SKIP_SMUDGE="1"),
        )
    with tarfile.open(archive) as bundle:
        bundle.extractall(destination, filter="data")
    # Own authorized edits are frozen with their real hashes for this run.
    names = (
        subprocess.check_output(
            ["git", "diff", "--name-only", "-z", "HEAD"], cwd=source
        )
        .decode()
        .split("\0")
    )
    names += (
        subprocess.check_output(
            ["git", "ls-files", "--others", "--exclude-standard", "-z"], cwd=source
        )
        .decode()
        .split("\0")
    )
    for name in filter(None, names):
        if paths and not any(
            name == prefix or name.startswith(prefix + "/") for prefix in paths
        ):
            continue
        original = source / name
        if original.is_file():
            target = destination / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(original, target)


def inventory(source: Path) -> dict[str, str]:
    return {
        str(p.relative_to(source)): digest(p)
        for p in source.rglob("*")
        if p.is_file() and ".git" not in p.parts and "__pycache__" not in p.parts
    }


def environment(objective: Path, context: Path) -> dict[str, str]:
    return dict(
        os.environ,
        EDA_PLATFORM_OBJECTIVE=str(objective),
        EDA_PLATFORM_CONTEXT=str(context),
        NO_PROXY="127.0.0.1,localhost",
        no_proxy="127.0.0.1,localhost",
        PYTHONNOUSERSITE="1",
    )


def invoke(
    command: list[str], source: Path, env: dict[str, str], folder: Path, seconds: int
) -> None:
    with (folder / "controller.log").open("x") as log:
        result = subprocess.run(
            command,
            cwd=source,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            timeout=seconds,
            check=False,
        )
    if result.returncode:
        raise RuntimeError(
            "Native professional controller failed; evidence retained at " + str(folder)
        )


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
    for name in ("eval_tns.sh", "eval_tns.tcl"):
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
    with config.open("a") as stream:
        stream.write("\n" + design.get("baseline_overrides", ""))
    return source


def tool_profile(deployment: Deployment, source: Path, experiment: Path) -> Path:
    profile = read(deployment.value["flow_tool_profile"])
    profile["flow_dir"] = str(source / "flow")
    profile["makefile_sha256"] = digest(source / "flow/Makefile")
    profile["eval_tns_sha256"] = digest(source / "flow/eval_tns.tcl")
    path = experiment / "tool-profile.json"
    write(path, profile)
    return path


def execute(
    deployment: Deployment, args: argparse.Namespace, experiment: Path
) -> dict[str, Any]:
    if not args.source:
        raise ValueError("A professional task needs a registered source result")
    from .candidates import result_frame

    frame = result_frame(args.source)
    if frame["design_id"] != args.design:
        raise ValueError("Professional source belongs to another design")
    objective = (args.objective or Path(frame["objective"])).resolve()
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
    if args.capability == "flow":
        return run_flow(deployment, args, experiment, frame, objective, context)
    if args.capability == "dpl":
        return run_dpl(deployment, args, experiment, frame, objective, context)
    if args.capability == "goal":
        from .native import run_goal

        return run_goal(deployment, args, experiment, frame, objective, context)
    from .native import run_eco

    return run_eco(deployment, args, experiment, frame, objective, context)


def run_flow(
    deployment: Deployment,
    args: argparse.Namespace,
    experiment: Path,
    frame: dict[str, Any],
    objective: Path,
    context: Path,
) -> dict[str, Any]:
    design = deployment.design(args.design)
    source_mode = getattr(args, "flow_recipe", "legacy") == "source"
    if source_mode:
        from .flow_recipe import prepare_native_source

        source = prepare_native_source(deployment, args.source, experiment)
    else:
        source = flow_source(deployment, experiment, design_id=args.design)
    config_dir = source / "flow/designs" / design["platform"] / design["nickname"]
    # Use OpenSTA's unit-explicit serialization and expose the same clock as
    # the native tuner's variable. All remaining constraints stay verbatim.
    sdc_path = (
        Path(read(experiment / "recipe.json")["sdc"])
        if source_mode
        else Path(frame["files"]["sdc"])
    )
    sdc = sdc_path.read_text()
    (config_dir / "constraint.sdc").write_text(flow_sdc(sdc, design["clock_period_ns"]))
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
            "threads": 8,
            "timeout_seconds": args.seconds,
            "deadline_epoch": time.time() + args.seconds,
            "resources": {"memory_bytes": 24 << 30, "processes": 2048},
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
        "42",
        "--cpus",
        "8",
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
    jobs = Jobs(deployment, design_id, experiment)
    candidates = []
    for path in sorted(
        (experiment / "platform-state").glob("iteration-*/slot-*-route_finish.json")
    ):
        native = read(path)
        if native["status"] != "succeeded":
            continue
        record = {"run": native["terminal_run"], "artifacts": native["artifacts"]}
        folder = experiment / (path.parent.name + "-" + str(native["candidate_slot"]))
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
        candidate_frame = publish(jobs, measured, result_path=folder / "result.json")
        write(folder / "result.json", candidate_frame)
        candidates.append(candidate_frame)
    if not candidates:
        raise RuntimeError("No completed native Flow candidate")
    write(experiment / "candidates.json", candidates)
    from .candidates import deliver_candidates

    return deliver_candidates(
        experiment,
        [Path(row["native_config"]).parent / "result.json" for row in candidates],
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
    jobs: Jobs, placement: Path, frame: dict[str, Any], objective: Path, producer: str
) -> dict[str, Any]:
    from .handoff import placement_archive, verify_stage_archive

    deployment = jobs.deployment
    design = deployment.design(jobs.design_id)
    archive_path = frame.get("flow_archive") or read(frame["native_inputs"])["archive"]
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
    for phase in ("cts", "route_finish"):
        record = jobs.submit(
            phase,
            {
                "adapter": "a2_stage",
                "stage": phase,
                "threads": 8,
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
    return publish(jobs, measured)


def flatten_archive(original: Path, destination: Path) -> None:
    """Normalize the stock nested ORFS tree and A2's already-flat tree alike."""
    with (
        zipfile.ZipFile(original) as source,
        zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as result,
    ):
        names = set()
        for name in source.namelist():
            parts = Path(name).parts
            if (
                len(parts) < 3
                or parts[:2]
                not in {
                    ("flow", "results"),
                    ("flow", "logs"),
                    ("flow", "reports"),
                    ("flow", "objects"),
                }
                or name.endswith("/")
            ):
                continue
            target = "flow/" + parts[1] + "/" + parts[-1]
            if target in names:
                raise ValueError(
                    "Choose one design/revision checkpoint, not a mixed archive"
                )
            names.add(target)
            result.writestr(target, source.read(name))


def materialize_dpl_replay(installation: Path, state: Path, experiment: Path) -> Path:
    """Reuse the verified installation inside the already mounted experiment."""
    target = state / "replay-runtime/install/OpenROAD"
    shutil.copytree(installation, target)
    binary = target / "bin/openroad"
    write(
        experiment / "prebuilt-replay-identity.json",
        {
            "source_installation": str(installation),
            "materialized_installation": str(target),
            "binary_sha256": digest(binary),
            "build_receipt_sha256": digest(target / "bin/platform-build.json"),
        },
    )
    return binary


def run_dpl(
    deployment: Deployment,
    args: argparse.Namespace,
    experiment: Path,
    frame: dict[str, Any],
    objective: Path,
    context: Path,
) -> dict[str, Any]:
    from .dpl_case import prepare_case

    design = deployment.design(args.design)
    binding = deployment.value["professional"]["dpl"]
    template = read(binding["profile_template"])
    source = experiment / "controller"
    freeze(Path(binding["source"]), source)
    case_id = prepare_case(source, design)
    orfs = experiment / "orfs"
    shutil.copytree(
        Path(template["orfs_root"]) / "flow",
        orfs / "flow",
        ignore=shutil.ignore_patterns(
            "results", "logs", "reports", "objects", "backup_dir", "__pycache__"
        ),
    )
    namespace = orfs / "tools/OpenROAD/src/dpl_evolve"
    shutil.copytree(
        Path(template["orfs_root"]) / "tools/OpenROAD/src/dpl_evolve", namespace
    )
    subprocess.run(["git", "init", "--quiet"], cwd=namespace, check=True)
    subprocess.run(["git", "add", "-A"], cwd=namespace, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=ChipEvolve",
            "-c",
            "user.email=local@chipevolve.invalid",
            "commit",
            "--quiet",
            "-m",
            "Freeze native framework seed",
        ],
        cwd=namespace,
        check=True,
    )
    input_root = (
        orfs
        / "flow/results"
        / design["platform"]
        / design["nickname"]
        / experiment.name
    )
    input_root.mkdir(parents=True)
    original = Path(
        frame.get("flow_archive") or read(frame["native_inputs"])["archive"]
    )
    flat = experiment / "input-checkpoint.zip"
    flatten_archive(original, flat)
    with zipfile.ZipFile(flat) as archive:
        for name in archive.namelist():
            if name.startswith("flow/results/"):
                (input_root / Path(name).name).write_bytes(archive.read(name))
    profile_path = experiment / "profile.json"
    profile = {
        **template,
        "profile_path": str(profile_path),
        "agent_root": str(source),
        "orfs_root": str(orfs),
        "state_root": str(experiment / "native-state"),
        "operations_root": str(experiment / "operations"),
        "client_python": deployment.value["client_python"],
        "kernel_url": deployment.value["kernel_url"],
        "experiment_id": args.design + "-" + experiment.name,
        "platform": design["platform"],
        "design": design["nickname"],
        "case": case_id,
        "flow_variant": experiment.name,
        "deadline_epoch": time.time() + args.seconds,
        "controller_files": inventory(source),
        "flow_output_roots": [
            str(orfs / "flow" / name)
            for name in ("results", "reports", "logs", "objects")
        ],
        "objective_path": str(objective),
        "data_context": {
            "data_url": deployment.value["data_url"],
            "snapshot_id": frame["snapshot_ids"]["opendb"],
            "metrics_snapshot_id": frame["snapshot_ids"]["orfs"],
            "parent_run_id": frame["run_id"],
        },
    }
    profile["resources"]["physical"] = {
        "cpu_cores": 8,
        "memory_bytes": 24 << 30,
        "processes": 2048,
    }
    profile["container_environment"].update(
        DPL_EVOLVE_AGENT_ROOT=str(source),
        DPL_EVOLVE_STATE_ROOT=profile["state_root"],
        ORFS_ROOT=str(orfs),
        ORFS_BUILD_ROOT=str(orfs),
        FLOW_HOME=str(orfs / "flow"),
        DPL_EVOLVE_PLATFORM_PROFILE=str(profile_path),
        PYTHONPYCACHEPREFIX=str(experiment / "pycache"),
    )
    write(profile_path, profile)
    Path(profile["state_root"]).mkdir(parents=True)
    shutil.copytree(
        Path(template["state_root"]) / "seed_sources",
        Path(profile["state_root"]) / "seed_sources",
    )
    for root in profile["flow_output_roots"]:
        Path(root).mkdir(parents=True, exist_ok=True)
    env = environment(objective, context)
    env.update(profile["container_environment"])
    env.update(
        DPL_EVOLVE_PYTHON=deployment.value["client_python"], DPL_EVOLVE_SKIP_ENV_SH="1"
    )
    baseline_tags = [
        (method, "baseline_probe_" + method, profile["core_binary"])
        for method in (
            "openroad_dpl_flow",
            "openroad_dpl_negotiation",
            "evolve_default",
        )
    ]
    candidate = Path(binding["candidate_source"]) / "install/OpenROAD/bin/openroad"
    if args.operation == "replay" and not args.code_source:
        candidate = materialize_dpl_replay(
            candidate.parent.parent, Path(profile["state_root"]), experiment
        )
    if args.operation == "replay" and args.code_source:
        variant = Path(profile["state_root"]) / "replayed-code"
        freeze(args.code_source.resolve(), variant / "dpl_evolve")
        folder = experiment / "code-build"
        folder.mkdir()
        invoke(
            [
                deployment.value["client_python"],
                str(source / "scripts/workspace/build_openroad_variant_relink.py"),
                "--variant-root",
                str(variant),
                "--dpl-src",
                str(variant / "dpl_evolve"),
                "--core-root",
                profile["core_root"],
                "--threads",
                "8",
            ],
            source,
            env,
            folder,
            args.seconds,
        )
        candidate = variant / "install/OpenROAD/bin/openroad"
    if args.operation == "replay":
        baseline_tags.append(("evolve_default", "source-replay", str(candidate)))
    results = {}
    for method, tag, binary in baseline_tags:
        folder = experiment / tag
        folder.mkdir()
        command = [
            "bash",
            str(source / "baseline/run_baseline.sh"),
            "--line",
            method,
            "--case",
            case_id,
            "--flow-variant",
            experiment.name,
            "--input-stage",
            "3_4_place_resized",
            "--run-tag",
            tag,
            "--threads",
            "8",
            "--openroad-binary",
            binary,
        ]
        invoke(command, source, env, folder, args.seconds)
        root = (
            orfs
            / "flow/reports"
            / design["platform"]
            / design["nickname"]
            / experiment.name
            / "dpl_evolve_baseline"
            / tag
        )
        results[tag] = read(root / "metrics.json")
    if args.operation == "evolve":
        folder = experiment / "evolve"
        folder.mkdir()
        command = [
            deployment.value["client_python"],
            str(source / "scripts/optimize_case_with_codex.py"),
            "--case",
            case_id,
            "--flow-variant",
            experiment.name,
            "--round-id",
            experiment.name,
            "--iterations",
            str(args.rounds),
            "--children",
            str(args.candidates),
            "--max-parallel",
            "2",
            "--skip-core-build",
            "--reuse-baseline-preflight",
            "--launch",
        ]
        invoke(command, source, env, folder, args.seconds)
        subprocess.run(
            [
                deployment.value["client_python"],
                "-m",
                "scripts.platform.selection",
                "--case",
                case_id,
                "--flow-variant",
                experiment.name,
                "--round-id",
                experiment.name,
                "--output",
                str(experiment / "native-selection.json"),
            ],
            cwd=source,
            env=env,
            check=True,
        )
    write(experiment / "native-methods.json", results)
    choice = (
        read(experiment / "native-selection.json")
        if args.operation == "evolve"
        else {
            "accepted": True,
            "candidate": (
                "source-replay"
                if args.operation == "replay"
                else "baseline_probe_evolve_default"
            ),
        }
    )
    tag = choice["candidate"] if choice["accepted"] else "baseline_probe_evolve_default"
    placement = (
        orfs
        / "flow/results"
        / design["platform"]
        / design["nickname"]
        / experiment.name
        / "dpl_evolve_baseline"
        / tag
        / "legalized.odb"
    )
    producer = dpl_producer(experiment / "operations", placement, tag)
    native_method = {
        "kind": (
            "native-search"
            if args.operation == "evolve"
            else (
                "fixed-source-replay"
                if args.operation == "replay"
                else "native-framework"
            )
        ),
        "choice": choice,
        "native_search_verdicts": str(experiment / "native-state"),
    }
    from .delivery import checkpoint, finish

    checkpoint(
        experiment,
        design_id=args.design,
        odb=placement,
        producer=producer,
        objective=objective,
        source=args.source,
        native_method=native_method,
    )
    return finish(deployment, experiment)


def dpl_producer(operations: Path, placement: Path, tag: str) -> str:
    """Bind the measured placement to its successful native trial, not just its tag."""
    sha, matches = digest(placement), []
    for path in operations.glob("*/leaf.json"):
        row = read(path)
        argv = row["request"]["argv"]
        if (
            row["request"]["operation"] == "baseline"
            and "--run-tag" in argv
            and argv[argv.index("--run-tag") + 1] == tag
            and row["output_files"].get(str(placement)) == sha
        ):
            run = read(path.parent / "execution.json")["run"]
            if run["status"] == "succeeded":
                matches.append((run["ended_at"], run["run_id"]))
    if not matches:
        raise ValueError(
            "Selected DPL placement has no successful producer with matching content"
        )
    return max(matches)[1]
