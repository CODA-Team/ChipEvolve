"""Goal specialist adapter and checkpoint provenance; native algorithms stay upstream."""

from __future__ import annotations

import gzip
import re
import shutil
import time
from pathlib import Path
from typing import Any

from .config import Deployment, read, write
from .contracts import (
    DiagnosisContextRef,
    ObjectiveRef,
    PhysicalResult,
    SpecialistReply,
    SpecialistRequest,
)
from .jobs import Jobs, digest
from .native_process import invoke
from .physical import container
from .result_io import check_specialist_call, specialist_reply, wire_object
from .source_snapshot import environment, freeze, inventory


def _goal_targets(targets: dict[str, float], objective: Path) -> dict[str, float]:
    tns_limit = read(objective)["constraints"]["setup_tns_ns_min"]
    return {
        name: max(0.0, -tns_limit) if name == "tns_abs_ns" else value
        for name, value in targets.items()
    }


def _goal_output(
    experiment: Path,
    baseline: dict[str, Any],
    *,
    evolved: bool,
    fixed: dict[str, Any] | None = None,
) -> tuple[Path, dict[str, Any]]:
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
    if not evolved:
        return odb, verdict
    campaign = experiment / "campaign"
    parent = read(campaign / "parent.json")
    candidate = campaign / "parents" / parent["source_hash"] / "design_checkpoint.odb"
    if candidate.exists():
        odb = candidate
    elif parent["source_commit"] != "baseline":
        raise ValueError("Promoted native Goal parent has no frozen routed checkpoint")
    return odb, {"kind": "native-search", "parent": parent, "baseline": verdict}


def restore_goal_checkpoint(experiment: Path, design_id: str) -> None:
    """Collect the native result after the controller has finished writing it."""
    from .delivery import checkpoint

    receipt = read(experiment / "input-receipt.json")
    profile = read(experiment / "profile.json")
    baseline = read(experiment / "baseline/baseline.json")
    if profile["design_id"] != design_id or not baseline["ok"]:
        raise ValueError(
            "Completed Goal campaign has no valid baseline for this design"
        )
    odb, verdict = _goal_output(experiment, baseline, evolved=True)
    checkpoint(
        experiment,
        design_id=design_id,
        odb=odb,
        producer=goal_producer(experiment, odb, verdict, baseline),
        objective=Path(receipt["objective"]),
        pdk=Path(profile["pdk_root"]),
        native_method=verdict,
    )


def run_goal(
    deployment: Deployment,
    request: SpecialistRequest,
    experiment: Path,
    source: PhysicalResult,
    objective: ObjectiveRef,
    context: DiagnosisContextRef,
) -> SpecialistReply:
    """Typed specialist boundary; native wire handling remains in its adapter."""
    check_specialist_call("goal", request, source, objective, context)
    from .artifact_inputs import require_dispatch_inputs

    require_dispatch_inputs(source, request.capability, request.flow_recipe)
    _run_goal_transport(
        deployment,
        request,
        experiment,
        wire_object(source.wire),
        objective.path,
        context.path,
    )
    return specialist_reply("goal", experiment / "result.json")


def _run_goal_transport(
    deployment: Deployment,
    args: SpecialistRequest,
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
        # The CSVs are produced by this command, so a pre-run glob omits them.
        capture=[
            script,
            *[
                bench / (design["top"] + "." + ext)
                for ext in ("def", "v", "sdc", "odb")
            ],
            bench / "node.csv",
            bench / "nets.csv",
        ],
        parent=frame["run_id"],
        seconds=300,
        memory_gib=8,
        cpu=2,
        objective=objective,
    )
    profile_path = experiment / "profile.json"
    profile = read(binding["profile_template"])
    config = read(binding["campaign_template"])
    build_seed = config.get("build_seed_root") or profile["source_seed"]
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
        read_roots=list(
            dict.fromkeys([str(source), profile["source_seed"], build_seed])
        ),
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
    resources = profile["resources"]
    threads = resources.get("physical", {}).get(
        "cpu_cores", resources.get("build", {}).get("cpu_cores", 8)
    )
    resources["physical"] = {
        "cpu_cores": threads,
        "memory_bytes": int(binding.get("physical_memory_gib", 24)) << 30,
        "processes": 2048,
    }
    if fixed:
        profile["read_roots"].append(fixed["source_root"])
    write(profile_path, profile)
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
            build_seed_root=build_seed,
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
    odb, verdict = _goal_output(
        experiment, baseline, evolved=args.operation == "evolve", fixed=fixed
    )
    producer = goal_producer(experiment, odb, verdict, baseline)
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


def goal_checkpoint_origin(
    campaign: Path, checkpoint: Path, parent: dict[str, Any]
) -> Path | None:
    """Resolve the original file for a checkpoint copied into a Goal parent."""
    sha = digest(checkpoint)
    staged = set()
    for path in (campaign / "stage_baselines").glob("*/parent_stage_baseline.json"):
        row = read(path)
        if row["parent_after"] == parent:
            artifact = row["baseline"]["artifacts"].get("checkpoint_post_route_db")
            if artifact and Path(artifact).is_file() and digest(Path(artifact)) == sha:
                staged.add(Path(artifact).resolve())
    if len(staged) > 1:
        raise ValueError("Goal checkpoint has ambiguous stage baseline origins")
    if staged:
        return staged.pop()

    match = re.fullmatch(r"(round_\d+):(student_\d+)", parent.get("parent_id", ""))
    if not match:
        return None
    round_id, student_id = match.groups()
    candidate = (
        campaign
        / "rounds"
        / round_id
        / "students"
        / student_id
        / "artifacts/candidate.json"
    )
    if not candidate.is_file():
        return None
    result = read(candidate)
    origin = Path(result["artifacts"]["checkpoint_post_route_db"])
    if result["source_commit"] != parent["source_commit"] or digest(origin) != sha:
        raise ValueError("Promoted Goal checkpoint differs from its Student result")
    return origin


def goal_producer(
    experiment: Path, odb: Path, verdict: dict[str, Any], baseline: dict[str, Any]
) -> str:
    parent = verdict.get("parent")
    origin = (
        goal_checkpoint_origin(experiment / "campaign", odb, parent) if parent else None
    )
    if origin is None and parent and parent["source_commit"] == "baseline":
        original = Path(baseline["artifacts"]["checkpoint_post_route_db"])
        if digest(original) != digest(odb):
            raise ValueError(
                "Retained Goal checkpoint differs from its baseline result"
            )
        origin = original
    return latest_producer(experiment / "operations", odb, origin=origin)


def latest_producer(
    operations: Path,
    checkpoint: Path,
    *,
    origin: Path | None = None,
    expected_run_id: str | None = None,
) -> str:
    """Use a recorded EF operation which actually captured the selected file."""
    sha = digest(checkpoint)
    registered_path = str((origin or checkpoint).resolve())
    direct = set()
    matches = set()
    for path in operations.rglob("leaf.json"):
        row = read(path)
        if (
            row["request"]["operation"] == "physical"
            and row.get("exit_code", row.get("returncode", 0)) == 0
            and not row.get("timed_out")
            and sha in row["output_files"].values()
        ):
            run = read(path.parent / "execution.json")["run"]
            run_id = run["run_id"]
            if run.get("status", "succeeded") != "succeeded" or (
                expected_run_id and run_id != expected_run_id
            ):
                continue
            if row["output_files"].get(registered_path) == sha:
                direct.add(run_id)
            matches.add(run_id)
    producers = direct if origin is not None else direct or matches
    if not producers:
        raise ValueError("Native checkpoint has no EF producer with matching content")
    if len(producers) != 1:
        raise ValueError(
            "Native checkpoint has ambiguous EF producers with matching content"
        )
    return producers.pop()
