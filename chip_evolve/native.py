"""Design-bound native Goal/ECO controllers; algorithms stay in their modules."""

from __future__ import annotations

import argparse
import gzip
import shutil
import time
from pathlib import Path
from typing import Any

from .config import Deployment, read, write
from .jobs import Jobs, digest
from .physical import container
from .professional import environment, freeze, inventory, invoke


def _goal_targets(targets: dict[str, float], objective: Path) -> dict[str, float]:
    tns_limit = read(objective)["constraints"]["setup_tns_ns_min"]
    return {
        name: max(0.0, -tns_limit) if name == "tns_abs_ns" else value
        for name, value in targets.items()
    }


def run_goal(
    deployment: Deployment,
    args: argparse.Namespace,
    experiment: Path,
    frame: dict[str, Any],
    objective: Path,
    context: Path,
) -> dict[str, Any]:
    from .goal_replay import descriptor, write_driver

    deadline = time.time() + args.seconds
    fixed = None
    if args.code_source:
        if args.operation != "replay":
            raise ValueError("Goal --code-source currently selects fixed replay only")
        fixed = descriptor(deployment, args.code_source.resolve())
        write(experiment / "fixed-source.json", fixed)
    design = deployment.design(args.design)
    binding = deployment.value["professional"]["goal"]
    source = experiment / "controller"
    freeze(
        Path(binding["source"]),
        source,
        paths=[
            "goalevolve",
            "config",
            "experiments",
            "toolchain",
            "knowledge",
            "scripts",
            "pyproject.toml",
            "README.md",
        ],
    )
    official = source / "third_party/official_checker"
    shutil.copytree(binding["official_checker"], official)
    bench_root = experiment / "inputs/benchmarks"
    bench = bench_root / design["top"]
    bench.mkdir(parents=True)
    for ext in ("def", "v", "sdc", "odb"):
        shutil.copyfile(frame["files"][ext], bench / (design["top"] + "." + ext))
    pdk = experiment / "inputs" / design["platform"]
    shutil.copytree(binding["pdk_template"], pdk)
    for row in design["libraries"]:
        path = Path(row["path"])
        target = pdk / "lib" / path.name.removesuffix(".gz")
        if path.suffix == ".gz":
            with gzip.open(path, "rb") as original, target.open("wb") as output:
                shutil.copyfileobj(original, output)
        else:
            shutil.copyfile(path, target)
    with (pdk / "setRC.tcl").open("a") as stream:
        stream.write(
            "\nset route_signal_layers "
            + design.get("signal_layers", "M2-M7")
            + "\nset route_clock_layers "
            + design.get("clock_layers", "M2-M7")
            + "\n"
        )
    jobs = Jobs(deployment, args.design, experiment)
    script = experiment / "prepare.tcl"
    script.write_text(
        "\n".join(
            [
                *[f"read_liberty {{{row['path']}}}" for row in design["libraries"]],
                f"read_db {{{bench / (design['top'] + '.odb')}}}",
                "remove_fillers",
                "[ord::get_db_block] setDefUnits [[ord::get_db_block] getDbUnitsPerMicron]",
                "foreach net [[ord::get_db_block] getNets] { if {[$net getSigType] ni {POWER GROUND}} { set wire [$net getWire]; if {$wire ne {NULL}} { odb::dbWire_destroy $wire } } }",
                *[
                    f"write_{cmd} {{{bench / (design['top'] + '.' + ext)}}}"
                    for cmd, ext in [("db", "odb"), ("def", "def"), ("verilog", "v")]
                ],
                f"source {{{official / 'validity_check/OpenROAD_utils.tcl'}}}",
                f"write_node_and_net_files {{{bench / 'node.csv'}}} {{{bench / 'nets.csv'}}}",
                "exit",
            ]
        )
        + "\n"
    )
    jobs.command(
        "prepare",
        container(
            deployment, [deployment.value["tools"]["openroad"], "-exit", str(script)]
        ),
        capture=[script, *bench.glob("*")],
        parent=frame["run_id"],
        seconds=300,
        memory_gib=8,
        cpu=2,
        objective=objective,
    )
    profile_path = experiment / "profile.json"
    profile = read(binding["profile_template"])
    profile.update(
        profile_path=str(profile_path),
        state_root=str(experiment),
        agent_root=str(source),
        experiment_id=jobs.campaign,
        design_id=args.design,
        design=design["top"],
        kernel_url=deployment.value["kernel_url"],
        client_python=deployment.value["client_python"],
        agent_python=deployment.value["goal_python"],
        operations_root=str(experiment / "operations"),
        deadline_epoch=deadline,
        read_roots=[str(source), profile["source_seed"]],
        write_roots=[str(experiment)],
        controller_files=inventory(source),
        input_files={
            str(experiment / "inputs" / name): sha
            for name, sha in inventory(experiment / "inputs").items()
        },
        objective_path=str(objective),
        data_context={
            "data_url": deployment.value["data_url"],
            "snapshot_id": frame["snapshot_ids"]["opendb"],
            "metrics_snapshot_id": frame["snapshot_ids"]["orfs"],
            "parent_run_id": frame["run_id"],
        },
    )
    profile["pdk_root"] = str(pdk)
    if (pdk / "equivalent_cells.csv").exists():
        profile["equivalent_cells"] = str(pdk / "equivalent_cells.csv")
    profile["resources"]["physical"] = {
        "cpu_cores": 8,
        "memory_bytes": int(binding.get("physical_memory_gib", 24)) << 30,
        "processes": 2048,
    }
    if fixed:
        profile["read_roots"].append(fixed["source_root"])
    write(profile_path, profile)
    config = read(binding["campaign_template"])
    native_targets = dict(config["target_metrics"])
    config.update(
        design=design["top"],
        benchmark_root=str(bench_root),
        state_root=str(experiment / "baseline"),
        baseline_evaluation_root=None,
        campaign_ready=False,
        max_campaign_rounds=args.rounds,
        source_root=profile["source_seed"],
        baseline_metrics={
            "dynamic_power_pw": 1,
            "leakage_power_pw": 1,
            "tns_abs_ns": 1,
        },
        target_metrics={"dynamic_power_pw": 0, "leakage_power_pw": 0, "tns_abs_ns": 0},
    )
    config_path = experiment / "baseline-config.json"
    if fixed:
        config.update(
            source_root=fixed["source_root"],
            build_seed_root=profile["source_seed"],
            **fixed["recipe_parameters"],
        )
    write(config_path, config)
    env = environment(objective, context)
    env["GOALEVOLVE_PLATFORM_PROFILE"] = str(profile_path)
    env["EDA_PLATFORM_DEADLINE_EPOCH"] = str(deadline)
    folder = experiment / "baseline-controller"
    folder.mkdir()
    command = [
        profile["agent_python"],
        "-m",
        "goalevolve.cli",
        "baseline",
        "--config",
        str(config_path),
    ]
    if fixed:
        script = experiment / "replay-fixed-source.py"
        write_driver(script)
        command = [
            profile["agent_python"],
            "-c",
            "import runpy; runpy.run_path(" + repr(str(script)) + ")",
            str(config_path),
            str(experiment / "fixed-source.json"),
        ]
    invoke(
        command,
        source,
        env,
        folder,
        args.seconds,
    )
    baseline = read(experiment / "baseline/baseline.json")
    if not baseline["ok"]:
        raise RuntimeError("Native Goal baseline rejected its actual design inputs")
    odb = Path(baseline["artifacts"]["checkpoint_post_route_db"])
    verdict = {
        "kind": "native-fixed-source" if fixed else "native-baseline",
        "checks": baseline["checks"],
        "metrics": baseline["metrics"],
    }
    if fixed:
        verdict.update(
            fixed_source=fixed,
            evaluation_mode=fixed["evaluation_mode"],
            timing_recipe_id=fixed["timing_recipe_id"],
        )
    if args.operation == "evolve":
        metrics = {
            name: baseline["metrics"][name] for name in config["baseline_metrics"]
        }
        config.update(
            state_root=str(experiment / "campaign"),
            baseline_evaluation_root=str(experiment / "baseline"),
            campaign_ready=True,
            baseline_metrics=metrics,
            target_metrics=_goal_targets(native_targets, objective),
        )
        campaign_path = experiment / "evolve-config.json"
        write(campaign_path, config)
        folder = experiment / "evolve-controller"
        folder.mkdir()
        invoke(
            [
                profile["agent_python"],
                "-m",
                "goalevolve.cli",
                "run",
                "--config",
                str(campaign_path),
                "--rounds",
                str(args.rounds),
                "--repository-graph",
                "on",
            ],
            source,
            env,
            folder,
            args.seconds,
        )
        parent = read(experiment / "campaign/parent.json")
        candidate = (
            experiment
            / "campaign/parents"
            / parent["source_hash"]
            / "design_checkpoint.odb"
        )
        if candidate.exists():
            odb = candidate
        elif parent["source_commit"] != "baseline":
            raise ValueError(
                "Promoted native Goal parent has no frozen routed checkpoint"
            )
        verdict = {"kind": "native-search", "parent": parent, "baseline": verdict}
    producer = latest_producer(experiment / "operations", odb, frame["run_id"])
    from .delivery import checkpoint, finish

    checkpoint(
        experiment,
        design_id=args.design,
        odb=odb,
        producer=producer,
        objective=objective,
        pdk=pdk,
        native_method=verdict,
    )
    return finish(deployment, experiment)


def latest_producer(operations: Path, checkpoint: Path, fallback: str) -> str:
    """Use a recorded EF operation which actually captured the selected file."""
    matches = []
    for path in operations.rglob("leaf.json"):
        row = read(path)
        if (
            row["request"]["operation"] == "physical"
            and digest(checkpoint) in row["output_files"].values()
        ):
            matches.append(read(path.parent / "execution.json")["run"]["run_id"])
    if not matches:
        raise ValueError("Native checkpoint has no EF producer with matching content")
    return matches[-1]


def run_eco(
    deployment: Deployment,
    args: argparse.Namespace,
    experiment: Path,
    frame: dict[str, Any],
    objective: Path,
    context: Path,
) -> dict[str, Any]:
    binding = deployment.value["professional"]["eco"]
    design = deployment.design(args.design)
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
        + repr([deployment.value["tools"]["openroad"], "-threads", "8"])
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
        OMP_NUM_THREADS="8",
        OPENBLAS_NUM_THREADS="8",
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
        "memory_gib": binding.get("session_memory_gib", 24),
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
        seconds=300,
        memory_gib=8,
        cpu=2,
        environment={
            key: env[key]
            for key in ("ASAP7_PDK", "TIMINGECO_LIB_CORNER", "TIMINGECO_LIB_FILES")
        },
    )
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
    from .delivery import checkpoint, finish

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
