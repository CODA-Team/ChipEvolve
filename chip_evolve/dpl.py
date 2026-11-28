"""Bind DPLEvolve inputs and deliver the native placement checkpoint."""

from __future__ import annotations

import shutil
import subprocess
import time
import zipfile
from pathlib import Path
from typing import Any

from .artifact_inputs import flatten_archive
from .config import Deployment, read, write
from .contracts import (
    DiagnosisContextRef,
    ObjectiveRef,
    PhysicalResult,
    SpecialistReply,
    SpecialistRequest,
)
from .jobs import digest
from .native_process import invoke
from .result_io import check_specialist_call, specialist_reply, wire_object
from .source_snapshot import environment, freeze, inventory


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


def dpl_search_command(
    binding: dict[str, Any],
    python: str,
    source: Path,
    args: SpecialistRequest,
    case_id: str,
    key: str,
    threads: int,
) -> list[str]:
    command = [
        python,
        str(source / "scripts/optimize_case_with_codex.py"),
        "--case",
        case_id,
        "--flow-variant",
        key,
        "--round-id",
        key,
        "--iterations",
        str(args.rounds),
        "--children",
        str(args.candidates),
        "--threads",
        str(threads),
        "--max-parallel",
        "2",
        "--skip-core-build",
        "--reuse-baseline-preflight",
        "--launch",
    ]
    for name in (
        "model",
        "reasoning_effort",
        "teacher_model",
        "teacher_reasoning_effort",
        "student_model",
        "student_reasoning_effort",
    ):
        if binding.get(name) is not None:
            command += ["--" + name.replace("_", "-"), binding[name]]
    return command


def run_dpl(
    deployment: Deployment,
    request: SpecialistRequest,
    experiment: Path,
    source: PhysicalResult,
    objective: ObjectiveRef,
    context: DiagnosisContextRef,
) -> SpecialistReply:
    """Typed specialist boundary; native wire handling remains in its adapter."""
    check_specialist_call("dpl", request, source, objective, context)
    from .artifact_inputs import require_dispatch_inputs

    require_dispatch_inputs(source, request.capability, request.flow_recipe)
    _run_dpl_transport(
        deployment,
        request,
        experiment,
        wire_object(source.wire),
        objective.path,
        context.path,
        source.origin.path,
    )
    return specialist_reply("dpl", experiment / "result.json")


def _run_dpl_transport(
    deployment: Deployment,
    args: SpecialistRequest,
    experiment: Path,
    frame: dict[str, Any],
    objective: Path,
    context: Path,
    source_path: Path,
) -> dict[str, Any]:
    from .dpl_case import prepare_case

    deadline = time.time() + args.seconds
    design = deployment.design(args.design)
    binding = deployment.value["professional"]["dpl"]
    python = binding.get("python") or str(Path(binding["source"]) / ".venv/bin/python")
    if not Path(python).is_absolute() or not Path(python).is_file():
        raise ValueError(
            "Set professional.dpl.python to the installed DPLEvolve Python"
        )
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
        "deadline_epoch": deadline,
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
    resources = profile["resources"]
    physical_threads = resources.get("physical", {}).get("cpu_cores", 8)
    variant_threads = resources.get("variant_build", resources.get("build", {})).get(
        "cpu_cores", 8
    )
    resources["physical"] = {
        "cpu_cores": physical_threads,
        "memory_bytes": int(binding.get("physical_memory_gib", 24)) << 30,
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
        DPL_EVOLVE_PYTHON=python,
        DPL_EVOLVE_SKIP_ENV_SH="1",
        EDA_PLATFORM_DEADLINE_EPOCH=str(deadline),
    )
    baseline_tags = [
        (method, "baseline_probe_" + method, profile["core_binary"])
        for method in (
            "openroad_dpl_flow",
            "openroad_dpl_negotiation",
            "evolve_default",
        )
    ]
    if args.operation == "replay" and not args.code_source:
        installation = Path(binding["candidate_source"]) / "install/OpenROAD"
        candidate = materialize_dpl_replay(
            installation, Path(profile["state_root"]), experiment
        )
    if args.operation == "replay" and args.code_source:
        variant = Path(profile["state_root"]) / "replayed-code"
        freeze(args.code_source.resolve(), variant / "dpl_evolve", git_metadata=True)
        folder = experiment / "code-build"
        folder.mkdir()
        invoke(
            [
                python,
                str(source / "scripts/workspace/build_openroad_variant_relink.py"),
                "--variant-root",
                str(variant),
                "--dpl-src",
                str(variant / "dpl_evolve"),
                "--core-root",
                profile["core_root"],
                "--threads",
                str(variant_threads),
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
            str(physical_threads),
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
        command = dpl_search_command(
            binding,
            python,
            source,
            args,
            case_id,
            experiment.name,
            min(physical_threads, variant_threads),
        )
        invoke(command, source, env, folder, args.seconds)
        subprocess.run(
            [
                python,
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
        source=source_path,
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
