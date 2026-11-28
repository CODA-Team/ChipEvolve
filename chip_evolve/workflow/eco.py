"""Timing ECO specialist adapter; native algorithms stay upstream."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from chip_evolve.core.resources import preset
from chip_evolve.core.config import Deployment, read, write
from chip_evolve.core.contracts import (
    DiagnosisContextRef,
    ObjectiveRef,
    PhysicalResult,
    SpecialistReply,
    SpecialistRequest,
)
from chip_evolve.core.jobs import Jobs, digest
from chip_evolve.core.native_process import invoke
from chip_evolve.execution.physical import container
from chip_evolve.core.resources import ensure_specialist_plan, admit_native_profile
from chip_evolve.core.result_io import (
    check_specialist_call,
    specialist_reply,
    wire_object,
)
from chip_evolve.facts.source_snapshot import environment, freeze, inventory


def run_eco(
    deployment: Deployment,
    request: SpecialistRequest,
    experiment: Path,
    source: PhysicalResult,
    objective: ObjectiveRef,
    context: DiagnosisContextRef,
) -> SpecialistReply:
    """Typed specialist boundary; native wire handling remains in its adapter."""
    check_specialist_call("eco", request, source, objective, context)
    from chip_evolve.core.artifact_inputs import require_dispatch_inputs

    require_dispatch_inputs(source, request.capability, request.flow_recipe)
    ensure_specialist_plan(deployment, request, experiment)
    _run_eco_transport(
        deployment,
        request,
        experiment,
        wire_object(source.wire),
        objective.path,
        context.path,
    )
    return specialist_reply("eco", experiment / "result.json")


def _run_eco_transport(
    deployment: Deployment,
    args: SpecialistRequest,
    experiment: Path,
    frame: dict[str, Any],
    objective: Path,
    context: Path,
) -> dict[str, Any]:
    binding = deployment.value["professional"]["eco"]
    design = deployment.design(args.design)
    threads = design.get("orfs_execution", {}).get(
        "cpu_cores", preset("eco-session")["cpu_cores"]
    )
    source = experiment / "source"
    freeze(
        Path(binding["source"]),
        source,
        paths=[
            "src",
            "OpenROAD_utils",
            "prompts",
            "README.md",
            "AGENTS.md",
            "LICENSE",
            "NOTICE",
            "PLATFORM.md",
            "requirements.txt",
        ],
    )
    pdk = Path(binding.get("pdk_template", Path(binding["source"]) / "asap7"))
    shutil.copytree(pdk, source / "asap7")
    (source / "asap7/lib/NLDM").mkdir(parents=True, exist_ok=True)
    for row in design["libraries"]:
        shutil.copyfile(row["path"], source / "asap7/lib/NLDM" / Path(row["path"]).name)
    wrapper = experiment / "openroad"
    base = container(deployment, [])
    wrapper.write_text(
        "#!/usr/bin/python3\nimport os,sys\nargs="
        + repr(base + ["env"])
        + "\nfor key in ('ASAP7_PDK','DESIGN_DIR','TOP','BACKTRACE_ODB','TIMINGECO_LIB_FILES'):\n if key in os.environ: args.append(key+'='+os.environ[key])\nargs += "
        + repr([deployment.value["tools"]["openroad"], "-threads", str(threads)])
        + "+sys.argv[1:]\nos.execvp(args[0],args)\n"
    )
    wrapper.chmod(0o755)
    artifacts = {}
    for ext in ("odb", "sdc", "spef"):
        records = frame["exports"]["opendb"]["execution"]["artifacts"]
        matching = [a for a in records if a["store_key"].endswith("." + ext)]
        if len(matching) != 1:
            raise ValueError("ECO requires one registered input per extension")
        artifacts[ext] = matching[0]["artifact_id"]
    python = binding["python"]
    env = environment(objective, context)
    env.update(
        OPENROAD_BIN=str(wrapper),
        ASAP7_PDK=str(source / "asap7"),
        ASAP7_PDK_LIB=str(source / "asap7/lib/NLDM"),
        TIMINGECO_LIB_CORNER=design.get("corner", "FF"),
        TIMINGECO_LIB_FILES="\n".join(
            str(source / "asap7/lib/NLDM" / Path(row["path"]).name)
            for row in design["libraries"]
        ),
        TIMINGECO_MODEL_BACKEND="codex",
        TIMINGECO_CODEX_BIN=shutil.which("codex") or "codex",
        DRT_EVERY_ITER="1" if binding.get("drt_every_iter", True) else "0",
        TIMINGECO_MAX_ITERATIONS=str(args.rounds),
        OMP_NUM_THREADS=str(threads),
        OPENBLAS_NUM_THREADS=str(threads),
        MPLBACKEND="Agg",
    )
    profile = {
        "kernel_url": deployment.value["kernel_url"],
        "data_url": deployment.value["data_url"],
        "state_root": str(experiment / "session"),
        "snapshot_id": frame["snapshot_ids"]["opendb"],
        "metrics_snapshot_id": frame["snapshot_ids"]["orfs"],
        "input_artifacts": artifacts,
        "input_route_drc": frame.get("route_drc"),
        "cpu_cores": threads,
        "memory_gib": binding.get(
            "session_memory_gib", preset("eco-session")["memory_gib"]
        ),
        "parent_run_id": frame["run_id"],
        "python": python,
        "design_id": args.design,
        "experiment_id": args.design + "-" + experiment.name,
        "timeout_seconds": args.seconds,
        "objective_path": str(objective),
        "context_path": str(context),
        "environment": {
            key: value
            for key, value in env.items()
            if key.startswith(("TIMINGECO_", "ASAP7_", "EDA_PLATFORM_"))
            or key
            in {
                "OPENROAD_BIN",
                "DRT_EVERY_ITER",
                "OMP_NUM_THREADS",
                "OPENBLAS_NUM_THREADS",
                "MPLBACKEND",
                "PATH",
                "PYTHONNOUSERSITE",
                "HTTP_PROXY",
                "HTTPS_PROXY",
                "http_proxy",
                "https_proxy",
                "ALL_PROXY",
                "all_proxy",
                "NO_PROXY",
                "no_proxy",
            }
        },
        "toolchain": deployment.value["toolchain"],
        "source_files": inventory(source),
    }
    path = experiment / "profile.json"
    write(path, profile)
    jobs = Jobs(deployment, args.design, experiment)
    jobs.command(
        "liberty-tables",
        [python, str(source / "src/extract_liberty_tables.py")],
        cwd=source,
        seconds=preset("specialist-input")["seconds"],
        memory_gib=preset("specialist-input")["memory_gib"],
        cpu=preset("specialist-input")["cpu_cores"],
        environment={
            key: env[key]
            for key in ("ASAP7_PDK", "TIMINGECO_LIB_CORNER", "TIMINGECO_LIB_FILES")
        },
        kind="specialist-input",
    )
    admit_native_profile(deployment, args, profile)
    invoke(
        [
            python,
            str(source / "src/platform_execution.py"),
            "submit",
            "--profile",
            str(path),
        ],
        source,
        env,
        experiment,
        args.seconds + 60,
    )
    native = read(experiment / "session/execution.json")
    odb = experiment / "native.odb"
    jobs.materialize(native, "raw_design_database", odb, suffix="/final_eco.odb")
    evidence_path = experiment / "native-route-evidence.json"
    evidence_artifact = jobs.materialize(
        native, "raw_flow_metadata", evidence_path, suffix="/route-evidence.json"
    )
    route_evidence = read(evidence_path)
    if route_evidence["checkpoint_sha256"] != digest(odb):
        raise ValueError("Native route DRC evidence belongs to another checkpoint")
    native_method = {
        "kind": "native-ECO",
        "physical_stage": "detailed_route",
        "route_drc": route_evidence["route_drc"],
        "route_drc_evidence": evidence_artifact,
        "iterations": args.rounds,
        "execution": str(experiment / "session/execution.json"),
    }
    from chip_evolve.execution.delivery import checkpoint, finish

    checkpoint(
        experiment,
        design_id=args.design,
        odb=odb,
        producer=native["run"]["run_id"],
        objective=objective,
        pdk=source / "asap7",
        native_method=native_method,
    )
    return finish(deployment, experiment)
