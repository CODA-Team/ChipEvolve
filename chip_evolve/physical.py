"""Native ORFS and common physical facts, parameterized by design bindings."""

from __future__ import annotations

import json
import re
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from eda_ai_client import EdaAiClient
from eda_toolkits.objectives import (
    SCHEMA,
    condition_id,
    objective_id,
    verify_conditions,
)

from .config import Deployment, read, write
from .jobs import Jobs, digest


def now() -> str:
    return datetime.now(UTC).isoformat()


def qualify(
    jobs: Jobs,
    odb: Path,
    parent: str,
    objective: Path,
    pdk: Path,
    *,
    fact_modes: tuple[str, ...] = ("opendb", "orfs", "opensta"),
) -> dict[str, Any]:
    """Complete a native GRT/ECO checkpoint without applying extra optimization."""
    design = jobs.deployment.design(jobs.design_id)
    output = jobs.experiment / "qualification"
    output.mkdir(exist_ok=True)
    script = output / "route.tcl"
    script.write_text(
        "\n".join(
            [
                *[f"read_liberty {{{row['path']}}}" for row in design["libraries"]],
                f"read_db {{{odb}}}",
                f"read_sdc {{{design['sdc']}}}",
                f"source {{{pdk / 'setRC.tcl'}}}",
                "remove_fillers",
                "foreach net [[ord::get_db_block] getNets] { if {[$net getSigType] ni {POWER GROUND}} { set wire [$net getWire]; if {$wire ne {NULL}} { odb::dbWire_destroy $wire } } }",
                "set_routing_layers -signal "
                + design.get("signal_layers", "M2-M7")
                + " -clock "
                + design.get("clock_layers", "M2-M7"),
                "global_route -congestion_iterations 50",
                f"detailed_route -output_drc {{{output / 'drc.rpt'}}}",
                "define_process_corner -ext_model_index 0 X",
                f"extract_parasitics -ext_model_file {{{pdk / 'rcx_patterns.rules'}}}",
                f"write_spef {{{output / 'final.spef'}}}",
                f"write_db {{{output / 'final.odb'}}}",
                "exit",
            ]
        )
        + "\n"
    )
    record = jobs.command(
        "qualification",
        container(
            jobs.deployment,
            [
                jobs.deployment.value["tools"]["openroad"],
                "-threads",
                "8",
                "-metrics",
                str(output / "native-metrics.json"),
                "-exit",
                str(script),
            ],
        ),
        capture=[
            odb,
            script,
            output / "final.odb",
            output / "final.spef",
            output / "native-metrics.json",
            output / "drc.rpt",
        ],
        parent=parent,
        objective=objective,
    )
    metrics = read(output / "native-metrics.json")
    measured = measure(
        jobs,
        "common",
        output / "final.odb",
        output / "final.spef",
        Path(design["sdc"]),
        record["run"]["run_id"],
        objective,
    )
    measured.update(
        route_drc=metrics["route__drc_errors"],
        qualification={
            "input_odb_sha256": digest(odb),
            "producer_run_id": parent,
            "full_drt_rcx": True,
        },
    )
    return publish(jobs, measured, modes=fact_modes)


def container(deployment: Deployment, command: list[str]) -> list[str]:
    runtime = deployment.value["runtime"]
    result = [runtime["executable"], "exec", "--cleanenv", "--no-home"]
    for path in runtime["bind_roots"]:
        result += ["--bind", path + ":" + path]
    return [*result, runtime["image"], *command]


def baseline(
    deployment: Deployment,
    design_id: str,
    experiment: Path,
    seconds: int,
    *,
    objective: Path | None = None,
) -> dict[str, Any]:
    design = deployment.design(design_id)
    jobs = Jobs(deployment, design_id, experiment)
    config = experiment / "inputs/design.mk"
    config.parent.mkdir(exist_ok=True)
    config.write_text(
        "include /OpenROAD-flow-scripts/flow/"
        + design["orfs_config"]
        + "\n"
        + design.get("baseline_overrides", "")
    )
    inputs = {
        "adapter": "orfs_flow",
        "orfs_image": deployment.value["runtime"]["image"],
        "design_config": design["orfs_config"],
        "config_path": "inputs/design.mk",
        "sdc_path": "inputs/design.sdc",
        "revision_id": experiment.name,
        "threads": 8,
    }
    staged = [
        {"source": str(config), "destination": "inputs/design.mk"},
        {"source": design["sdc"], "destination": "inputs/design.sdc"},
    ]
    # Explicit source scripts are frozen inputs, just like the SDC and libraries.
    staged += design.get("flow_dependencies", [])
    inputs["liberty_paths"] = []
    for i, lib in enumerate(design["libraries"]):
        destination = "inputs/libraries/" + str(i) + "-" + Path(lib["path"]).name
        staged.append({"source": lib["path"], "destination": destination})
        inputs["liberty_paths"].append(destination)
    result = jobs.submit(
        "orfs",
        inputs,
        staged,
        seconds=seconds,
        memory_gib=design.get("orfs_execution", {}).get("memory_gib", 24),
    )
    archive = experiment / "orfs.zip"
    jobs.materialize(result, "flow_archive", archive)
    files: dict[str, Path] = {}
    refs = {}
    for suffix, kind in {
        "odb": "raw_design_database",
        "sdc": "raw_constraints",
        "spef": "raw_parasitics",
        "v": "raw_netlist",
        "def": "raw_layout",
    }.items():
        file = experiment / "native" / ("6_final." + suffix)
        refs[suffix] = jobs.materialize(result, kind, file, suffix="/6_final." + suffix)
        files[suffix] = file
    write(
        experiment / "native-inputs.json",
        {"run_id": result["run"]["run_id"], "archive": str(archive), "artifacts": refs},
    )
    measured = measure(
        jobs,
        "common",
        files["odb"],
        files["spef"],
        Path(design["sdc"]),
        result["run"]["run_id"],
        objective,
    )
    with zipfile.ZipFile(archive) as bundle:
        route_name = next(
            name for name in bundle.namelist() if name.endswith("/5_2_route.json")
        )
        route = json.loads(bundle.read(route_name))
    measured["route_drc"] = route["detailedroute__route__drc_errors"]
    goal = objective or freeze_goal(deployment, design_id, experiment, measured)
    measured["objective"] = str(goal)
    # This is the same measured fact, now bound to the baseline-derived limits.
    annotate(measured, read(goal))
    write(experiment / "measurement.json", measured)
    return publish(jobs, measured)


def freeze_goal(
    deployment: Deployment, design_id: str, experiment: Path, measured: dict[str, Any]
) -> Path:
    design = deployment.design(design_id)
    metrics = measured["metrics"]
    goal = {
        "schema_version": SCHEMA,
        "design_id": design_id,
        "reference_run_id": measured["run_id"],
        "conditions": {
            "toolchain": deployment.value["toolchain"],
            "libraries": design["libraries"],
            "sdc": {"path": design["sdc"], "sha256": digest(Path(design["sdc"]))},
            "corner": design["corner"],
            "clock_period_ns": design["clock_period_ns"],
            "propagated_clock": True,
            "analysis": "post_route",
            "parasitics": "full detailed-route extracted SPEF for each candidate",
            "units": {"time": "ns", "power": "W", "area": "um^2"},
        },
        "constraints": {
            "setup_tns_ns_min": 0,
            "hold_tns_ns_min": 0,
            "max_slew_violations": 0,
            "max_cap_violations": 0,
            "placement_violations": 0,
            "route_drc": 0,
            "power_total_w_max": metrics["finish__power__total"],
            "cell_area_um2_max": metrics["finish__design__instance__area"],
            "core_area_um2_max": metrics["finish__design__core__area"],
            "die_area_um2_max": metrics["finish__design__die__area"],
        },
    }
    goal["constraints"].update(design.get("goal_limits", {}))
    goal["objective_id"] = objective_id(goal)
    path = experiment / "objective.json"
    write(path, goal)
    return path


def annotate(measured: dict[str, Any], goal: dict[str, Any]) -> None:
    measured["objective_id"] = goal["objective_id"]
    measured["condition_id"] = condition_id(goal)
    measured["conditions"].update(
        objective_id=goal["objective_id"], condition_id=condition_id(goal)
    )
    write(
        Path(measured["files"]["metrics"]),
        {
            "metrics": measured["metrics"],
            "metric_context": {
                "corner": goal["conditions"]["corner"],
                "analysis": "post_route",
                "authoritative_source": "common native OpenROAD routed-checkpoint measurement",
                "evaluation_conditions": measured["conditions"],
            },
        },
    )


def measure(
    jobs: Jobs,
    key: str,
    odb: Path,
    spef: Path,
    sdc: Path,
    parent: str,
    objective: Path | None = None,
) -> dict[str, Any]:
    deployment = jobs.deployment
    design = deployment.design(jobs.design_id)
    if objective:
        verify_conditions(read(objective), sdc=sdc)
    folder = jobs.experiment / key
    identity = {
        "parent": parent,
        "files": {str(p): digest(p) for p in (odb, spef, sdc)},
        "objective": str(objective) if objective else None,
    }
    saved = folder / "measurement-inputs.json"
    if saved.exists() and read(saved) != identity:
        raise ValueError("A saved measurement cannot change inputs")
    folder.mkdir(exist_ok=True)
    write(saved, identity)
    script = folder / "measure.tcl"
    libraries = [Path(row["path"]) for row in design["libraries"]]
    if any(
        digest(path) != row["sha256"]
        for path, row in zip(libraries, design["libraries"], strict=True)
    ):
        raise ValueError("Frozen design libraries changed")
    script.write_text(
        "\n".join(
            [
                *[f"read_liberty {{{p}}}" for p in libraries],
                f"read_db {{{odb}}}",
                f"read_sdc {{{sdc}}}",
                "set_cmd_units -time ns -power W -distance um",
                f"read_spef {{{spef}}}",
                "set_propagated_clock [all_clocks]",
                "check_placement -verbose",
                "report_units",
                "report_clock_properties [all_clocks]",
                "report_power -digits 10",
                "utl::metric_float finish__timing__setup__tns [total_negative_slack -max]",
                "utl::metric_float finish__timing__setup__ws [worst_slack -max]",
                "utl::metric_float finish__timing__hold__tns [total_negative_slack -min]",
                "utl::metric_float finish__timing__hold__ws [worst_slack -min]",
                "utl::metric_integer finish__timing__drv__max_slew [sta::max_slew_violation_count]",
                "utl::metric_integer finish__timing__drv__max_cap [sta::max_capacitance_violation_count]",
                "utl::metric_float finish__design__instance__area [expr {[rsz::design_area] * 1e12}]",
                "set block [ord::get_db_block]",
                "set scale [$block getDbUnitsPerMicron]",
                "foreach {kind rect} [list core [$block getCoreArea] die [$block getDieArea]] { utl::metric_float finish__design__${kind}__area [expr {[$rect dx]*double([$rect dy])/$scale/$scale}] }",
                f"write_db {{{folder / 'final.odb'}}}",
                f"write_def {{{folder / 'final.def'}}}",
                f"write_verilog {{{folder / 'final.v'}}}",
                "set_cmd_units -time ps",
                f"write_sdc {{{folder / 'serialized.sdc'}}}",
                f"set fd [open {{{folder / 'serialized.sdc'}}} r]",
                "set text [read $fd]; close $fd",
                f"set fd [open {{{folder / 'final.sdc'}}} w]",
                'puts $fd "set_cmd_units -time ps"',
                "puts -nonewline $fd $text; close $fd",
                "exit",
            ]
        )
        + "\n"
    )
    result = jobs.command(
        key,
        container(
            deployment,
            [
                deployment.value["tools"]["openroad"],
                "-threads",
                "2",
                "-metrics",
                str(folder / "native-metrics.json"),
                "-exit",
                str(script),
            ],
        ),
        capture=[
            odb,
            spef,
            sdc,
            script,
            folder / "final.odb",
            folder / "final.sdc",
            folder / "final.def",
            folder / "final.v",
            folder / "native-metrics.json",
        ],
        parent=parent,
        cpu=2,
        memory_gib=8,
        seconds=300,
        objective=objective,
    )
    log = jobs.log(result, folder / "execution.log")
    totals = re.findall(
        r"^Total\s+([\deE.+-]+)\s+([\deE.+-]+)\s+([\deE.+-]+)\s+([\deE.+-]+)",
        log,
        re.MULTILINE,
    )
    if len(totals) != 1:
        raise ValueError("Need one native authoritative power total")
    metrics = read(folder / "native-metrics.json")
    metrics.update(
        finish__power__total=float(totals[0][3]),
        run__flow__platform__time_units="1ns",
        run__flow__platform__power_units="1W",
        run__flow__platform__distance_units="1um",
    )
    files = {
        suffix: str(folder / ("final." + suffix))
        for suffix in ("odb", "sdc", "v", "def")
    }
    files.update(spef=str(spef), metrics=str(folder / "metrics.json"))
    measured = {
        "run_id": result["run"]["run_id"],
        "physical_run_id": parent,
        "design_id": jobs.design_id,
        "metrics": metrics,
        "files": files,
        "conditions": {
            "corner": design["corner"],
            "clock_period_ns": design["clock_period_ns"],
            "sdc_sha256": digest(sdc),
            "library_sha256": sorted(row["sha256"] for row in design["libraries"]),
            "toolchain": deployment.value["toolchain"],
            "propagated_clock": True,
            "parasitics": "full-route SPEF of this candidate",
            "units": {"time": "ns", "power": "W", "area": "um^2"},
        },
    }
    if objective:
        measured["objective"] = str(objective)
        annotate(measured, read(objective))
    write(folder / "measurement.json", measured)
    return measured


def publish(
    jobs: Jobs,
    measured: dict[str, Any],
    *,
    result_path: Path | None = None,
    modes: tuple[str, ...] = ("opendb", "orfs", "opensta"),
) -> dict[str, Any]:
    from .delivery import import_snapshot

    snapshot_ids = dict(measured.get("snapshot_ids", {}))
    exports = dict(measured.get("exports", {}))
    deployment = jobs.deployment
    for mode, field, source in (
        ("opendb", "odb_path", measured["files"]["odb"]),
        ("orfs", "metadata_path", measured["files"]["metrics"]),
        ("opensta", "odb_path", measured["files"]["odb"]),
    ):
        if mode not in modes:
            continue
        snapshot = "local-" + measured["run_id"] + "-" + mode
        files = {name: Path(value) for name, value in measured["files"].items()}
        inputs = {
            "adapter": mode,
            field: "inputs/" + Path(source).name,
            "snapshot_id": snapshot,
            "design_id": jobs.design_id,
            "revision_id": jobs.experiment.name,
            "run_id": measured["run_id"],
            "stage": "finish" if mode != "opensta" else "timing",
            "created_at": now(),
            "threads": 2,
            "openroad_bin": deployment.value["openroad_launcher"],
            "native_extra_paths": ["inputs/" + p.name for p in files.values()],
        }
        if mode == "opensta":
            inputs.update(
                analysis="post_route",
                corner=measured.get("conditions", {}).get("corner"),
                # OpenSTA report_checks JSON emits SI values, independently
                # of the Tcl display/metric time unit selected by the caller.
                unit="s",
                sdc_path="inputs/final.sdc",
                spef_path="inputs/" + files["spef"].name,
                liberty_paths=[
                    "inputs/lib/" + str(i) + "-" + Path(row["path"]).name
                    for i, row in enumerate(
                        deployment.design(jobs.design_id)["libraries"]
                    )
                ],
                include_hold=True,
            )
        staged = [
            {"source": str(p), "destination": "inputs/" + p.name}
            for p in files.values()
        ]
        if mode == "opensta":
            staged += [
                {"source": row["path"], "destination": inputs["liberty_paths"][i]}
                for i, row in enumerate(deployment.design(jobs.design_id)["libraries"])
            ]
        key = "publish-v3-" + measured["run_id"][-8:] + "-" + mode
        saved = jobs.experiment / "jobs" / key / "task.json"
        if saved.exists():
            prior = read(saved)["inputs"]
            inputs["created_at"] = prior["created_at"]
            if mode == "opensta":
                # Resume the original immutable export. Legacy context remains
                # unknown; a supplemental export needs its own task/snapshot.
                for name in ("analysis", "corner", "unit"):
                    if name not in prior:
                        inputs.pop(name, None)
        record = jobs.submit(
            key,
            inputs,
            staged,
            seconds=300,
            cpu=2,
            memory_gib=8,
            parent=measured["run_id"],
            analysis_parent=measured["run_id"],
            objective=Path(measured["objective"]),
        )
        artifact = next(a for a in record["artifacts"] if a["kind"] == "data_snapshot")
        imported = import_snapshot(
            jobs,
            record["run"]["run_id"],
            artifact["artifact_id"],
            snapshot,
            measured["run_id"],
        )
        snapshot_ids[mode], exports[mode] = (
            snapshot,
            {"execution": record, "import": imported},
        )
    data = EdaAiClient(
        data_url=deployment.value["data_url"], kernel_url=deployment.value["kernel_url"]
    )
    facts = data.get_metrics(snapshot_id=snapshot_ids["orfs"])
    if facts["scope"]["design_id"] != jobs.design_id:
        raise ValueError("Returned facts belong to another design")
    frame = {
        **measured,
        "snapshot_ids": snapshot_ids,
        "exports": exports,
        "native_inputs": str(jobs.experiment / "native-inputs.json")
        if (jobs.experiment / "native-inputs.json").exists()
        else None,
    }
    if "opendb" not in snapshot_ids:
        frame["deferred_facts"] = {
            "opendb": {"publication_root": str(jobs.experiment.resolve())}
        }
    else:
        frame.pop("deferred_facts", None)
    destination = result_path or jobs.experiment / "result.json"
    write(destination, frame)
    write(destination.parent / "queried-facts.json", facts)
    return frame
