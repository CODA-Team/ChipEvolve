"""Explicit original ORFS GRT successors, separate from pure qualification."""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any

from eda_ai_client import EdaAiClient

from .candidates import result_frame
from .config import Deployment, read, write
from .delivery import checkpoint, finish, import_snapshot
from .jobs import Jobs, digest
from .physical import container, now, verify_measurement_conditions
from .stage_facts import bundle


def timing_facts(log: str) -> dict[str, Any]:
    timing = re.findall(r"^CHIPEVOLVE_GRT_TIMING_NS ([^\n]+)$", log, re.MULTILINE)
    electrical = re.findall(
        r"^CHIPEVOLVE_GRT_ELECTRICAL (\d+) (\d+) (\d+)$", log, re.MULTILINE
    )
    if len(timing) != 1 or len(electrical) != 1:
        raise ValueError("Native GRT did not produce one complete final observation")
    ws, tns, hold_ws, hold_tns = map(float, timing[0].split())
    slew, cap, fanout = map(int, electrical[0])
    return {
        "run__flow__platform__time_units": "1ns",
        "globalroute__timing__setup__ws": ws,
        "globalroute__timing__setup__tns": tns,
        "globalroute__timing__hold__ws": hold_ws,
        "globalroute__timing__hold__tns": hold_tns,
        "globalroute__timing__drv__max_slew": slew,
        "globalroute__timing__drv__max_cap": cap,
        "globalroute__timing__drv__max_fanout": fanout,
    }


def prepare(
    jobs: Jobs, source: Path, original: dict[str, Any], objective: Path, seconds: int
) -> Path:
    """Freeze the native recipe; recovery consumes the same scripts and inputs."""
    d, design = jobs.deployment, jobs.deployment.design(jobs.design_id)
    root = jobs.experiment / "native-physical"
    identity = {
        "source": str(source),
        "source_sha256": digest(source),
        "odb": original["odb"],
        "odb_sha256": digest(Path(original["odb"])),
        "objective": str(objective),
        "objective_sha256": digest(objective),
        "design": design,
        "runtime": d.value["runtime"],
        "tools": d.value["tools"],
        "seconds": seconds,
    }
    manifest = root / "inputs.json"
    if manifest.exists():
        saved = read(manifest)
        if saved["identity"] != identity:
            raise ValueError("Explicit physical successor inputs changed")
        for name, sha in saved["input_hashes"].items():
            if digest(Path(name)) != sha:
                raise ValueError("Frozen native repair input changed: " + name)
        return root
    if (
        digest(Path(d.value["runtime"]["image"]))
        != d.value["toolchain"]["image_sha256"]
    ):
        raise ValueError("Native repair image differs from the pinned toolchain")
    inputs, work = root / "inputs", root / "orfs"
    inputs.mkdir(parents=True, exist_ok=True)
    for name in ("results", "logs", "reports", "objects"):
        (work / name).mkdir(parents=True, exist_ok=True)
    copied = []
    for row in design.get("flow_dependencies", []):
        target = root / row["destination"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(row["source"], target)
        copied += [Path(row["source"]), target]
    config = inputs / "design.mk"
    text = (
        Path(design["orfs_config_template"]).read_text()
        if design.get("orfs_config_template")
        else "include /OpenROAD-flow-scripts/flow/" + design["orfs_config"] + "\n"
    )
    config.write_text(
        (text + design.get("baseline_overrides", "")).replace(
            "/work/inputs/", str(inputs) + "/"
        )
    )
    shutil.copyfile(original["odb"], work / "results/4_cts.odb")
    shutil.copyfile(design["sdc"], work / "results/4_cts.sdc")
    period_seconds = float(design["clock_period_ns"]) * 1e-9
    clock_check = f"foreach clk [all_clocks] {{ if {{abs([sta::time_ui_sta [get_property $clk period]]-{period_seconds!r}) > 1e-15}} {{error {{Physical successor clock changed}}}} }}"
    before = root / "before-grt.tcl"
    before.write_text(
        "\n".join(
            [
                "if {[llength [all_clocks]] == 0} {error {Physical successor needs its source clocks}}",
                clock_check,
                "set block [ord::get_db_block]",
                "foreach net [$block getNets] {if {[$net getSigType] ni {POWER GROUND} && [$net getWire] ne {NULL}} {error {Use an unrouted post-CTS or GRT checkpoint for explicit repair}}}",
                f"source {{{root / 'routing-init.tcl'}}}",
                'puts "CHIPEVOLVE_GRT_INPUT_BOUNDS [$block getMinRoutingLayer] [$block getMaxRoutingLayer] [$block getMinLayerForClock] [$block getMaxLayerForClock]"',
                "check_placement -verbose",
                f"write_verilog {{{root / 'admitted.v'}}}",
            ]
        )
        + "\n"
    )
    after = root / "after-grt.tcl"
    after.write_text(
        "\n".join(
            [
                clock_check,
                'puts "CHIPEVOLVE_GRT_TIMING_NS [expr {[sta::time_ui_sta [worst_slack -max]]*1e9}] [expr {[sta::time_ui_sta [total_negative_slack -max]]*1e9}] [expr {[sta::time_ui_sta [worst_slack -min]]*1e9}] [expr {[sta::time_ui_sta [total_negative_slack -min]]*1e9}]"',
                "report_check_types -max_slew -max_capacitance -max_fanout -violators",
                'puts "CHIPEVOLVE_GRT_ELECTRICAL [sta::max_slew_violation_count] [sta::max_capacitance_violation_count] [sta::max_fanout_violation_count]"',
                "check_placement -verbose",
                f"write_verilog {{{root / 'repaired.v'}}}",
            ]
        )
        + "\n"
    )
    flow = "/OpenROAD-flow-scripts/flow"
    command = [
        "make",
        "-C",
        flow,
        f"FLOW_HOME={flow}",
        f"DESIGN_CONFIG={config}",
        f"WORK_HOME={work}",
        f"RESULTS_DIR={work / 'results'}",
        f"LOG_DIR={work / 'logs'}",
        f"REPORTS_DIR={work / 'reports'}",
        f"OBJECTS_DIR={work / 'objects'}",
        f"SDC_FILE={work / 'results/4_cts.sdc'}",
        "NUM_CORES=8",
        "OPENROAD_EXE=" + d.value["tools"]["openroad"],
        "YOSYS_EXE=" + d.value["tools"]["yosys"],
        "LIB_FILES=" + " ".join(row["path"] for row in design["libraries"]),
        "DETAIL_PLACEMENT_ARGS=-use_diamond_legalizer",
        "DETAILED_METRICS=1",
        f"PRE_GLOBAL_ROUTE_TCL={before}",
        f"POST_GLOBAL_ROUTE_TCL={after}",
        "do-grt",
    ]
    write(root / "command.json", {"command": command})
    helper = root / "read-routing-env.py"
    helper.write_text(
        "import json, os, re\nfrom pathlib import Path\n"
        "root = Path(__file__).resolve().parent\n"
        "names = ['MIN_ROUTING_LAYER','MAX_ROUTING_LAYER','MIN_CLK_ROUTING_LAYER','ROUTING_LAYER_ADJUSTMENT','FASTROUTE_TCL','PLATFORM_DIR']\n"
        "settings = {key: os.environ[key] for key in names}\n"
        "routing_text = Path(settings['FASTROUTE_TCL']).read_text()\n"
        "used = re.findall(r'::env\\((\\w+)\\)', routing_text)\n"
        "settings.update({key: os.environ[key] for key in used if key in os.environ})\n"
        "(root / 'routing-settings.json').write_text(json.dumps(settings, indent=2))\n"
        "lines = ['set ::env(' + key + ') {' + value + '}' for key,value in settings.items()]\n"
        "lines += ['source {' + settings['FASTROUTE_TCL'] + '}']\n"
        "lines += ['set_routing_layers -clock $::env(MIN_CLK_ROUTING_LAYER)-$::env(MAX_ROUTING_LAYER) -signal $::env(MIN_ROUTING_LAYER)-$::env(MAX_ROUTING_LAYER)']\n"
        "(root / 'routing-init.tcl').write_text('\\n'.join(lines)+'\\n')\n"
        "(root / 'native-routing-source.tcl').write_bytes(Path(settings['FASTROUTE_TCL']).read_bytes())\n"
    )
    makefile = root / "read-routing-env.mk"
    makefile.write_text("chipevolve-routing-context:\n\t@python3 " + str(helper) + "\n")
    staged = [
        source,
        Path(original["odb"]),
        objective,
        Path(design["sdc"]),
        Path(original["pdk"]) / "setRC.tcl",
        Path(original["pdk"]) / "rcx_patterns.rules",
        *[Path(row["path"]) for row in design["libraries"]],
        *copied,
        *[p for p in root.rglob("*") if p.is_file()],
    ]
    write(
        manifest,
        {"identity": identity, "input_hashes": {str(p): digest(p) for p in staged}},
    )
    return root


def repair(
    deployment: Deployment,
    design_id: str,
    experiment: Path,
    source: Path,
    seconds: int,
    *,
    objective: Path | None = None,
) -> dict[str, Any]:
    """Run one explicit successor; original professional selection stays frozen."""
    from .validation import query_facts, replay_checkpoint

    source = source.resolve()
    frame = result_frame(source)
    if frame["design_id"] != design_id:
        raise ValueError("Physical repair source belongs to another design")
    objective = objective or Path(frame["objective"])
    design = deployment.design(design_id)
    verify_measurement_conditions(deployment, design_id, objective, Path(design["sdc"]))
    if frame.get("kind") == "qualify" and "input_hashes" in frame:
        # An existing delivery checkpoint can be handed off before expensive
        # final PPA. It still needs registered, scoped native-stage facts.
        original = frame
        for name, expected in original["input_hashes"].items():
            if digest(Path(name)) != expected:
                raise ValueError("Native stage source changed: " + name)
        data = EdaAiClient(
            deployment.value["data_url"], kernel_url=deployment.value["kernel_url"]
        )
        scope = data.resolve_scope(
            snapshot_id=original["native_method"].get("stage_snapshot_id"),
            run_id=original["producer"],
            design_id=design_id,
            stage=original["native_method"].get("physical_stage"),
            origin="all",
        )["scope"]
        if scope["run_id"] != original["producer"] or scope["design_id"] != design_id:
            raise ValueError("Native stage facts belong to another source")
        facts = data.get_metrics(snapshot_id=scope["snapshot_id"])
        if not facts["data"]["metrics"]:
            raise ValueError("Native stage source has no registered readable metrics")
        frame = {
            **frame,
            "run_id": original["producer"],
            "snapshot_ids": {"orfs": scope["snapshot_id"]},
        }
    else:
        query_facts(deployment, frame)
        original = replay_checkpoint(source)
    if (
        original["kind"] != "qualify"
        or original["native_method"].get("physical_stage") == "detailed_route"
    ):
        raise ValueError(
            "Explicit GRT repair needs a post-CTS/GRT professional checkpoint"
        )
    jobs = Jobs(deployment, design_id, experiment)
    _, evidence = bundle(jobs, original["producer"], experiment)
    native = evidence.get("receipt", evidence)
    sha = digest(Path(original["odb"]))
    if not any(
        name.endswith(".odb") and value == sha
        for name, value in native["output_files"].items()
    ):
        raise ValueError("Native producer does not own the selected checkpoint bytes")
    if "qualification" in frame and (
        frame["qualification"]["input_odb_sha256"] != sha
        or frame["qualification"]["producer_run_id"] != original["producer"]
    ):
        raise ValueError("Selected physical checkpoint differs from the source result")
    root = prepare(jobs, source, original, objective, seconds)
    command = read(root / "command.json")["command"]
    prepared = jobs.command(
        "native-routing-context",
        container(
            deployment,
            [
                *command[:-1],
                "-f",
                "/OpenROAD-flow-scripts/flow/Makefile",
                "-f",
                str(root / "read-routing-env.mk"),
                "chipevolve-routing-context",
            ],
        ),
        capture=[
            root / name
            for name in (
                "read-routing-env.py",
                "read-routing-env.mk",
                "command.json",
                "routing-settings.json",
                "routing-init.tcl",
                "native-routing-source.tcl",
            )
        ],
        cpu=1,
        memory_gib=2,
        seconds=120,
        parent=original["producer"],
        objective=objective,
    )
    _, manifest = bundle(jobs, prepared["run"]["run_id"], experiment)
    for path, expected in manifest["output_files"].items():
        if digest(Path(path)) != expected:
            raise ValueError("Registered native routing initializer changed")
    record = jobs.command(
        "native-GRT-repair",
        container(deployment, command),
        capture=[
            root / name
            for name in (
                "command.json",
                "before-grt.tcl",
                "after-grt.tcl",
                "routing-init.tcl",
                "routing-settings.json",
                "admitted.v",
                "repaired.v",
                "orfs/results/5_1_grt.odb",
                "orfs/results/5_1_grt.sdc",
                "orfs/logs/5_1_grt.log",
                "orfs/logs/5_1_grt.json",
            )
        ],
        cpu=8,
        memory_gib=design.get("orfs_execution", {}).get("memory_gib", 24),
        seconds=seconds,
        parent=original["producer"],
        objective=objective,
    )
    log = jobs.log(record, root / "native-stage.log")
    producer = record["run"]["run_id"]
    metadata = root / "stage-facts.json"
    write(
        metadata,
        {
            "metrics": timing_facts(log),
            "metric_context": {
                "corner": design["corner"],
                "analysis": "global_route",
                "parasitic_mode": "native_ORFS_GRT_estimate",
            },
            "evidence_refs": {
                "source_result": str(source),
                "source_result_sha256": digest(source),
                "source_run_id": frame["run_id"],
                "source_snapshot_ids": frame["snapshot_ids"],
                "origin_producer": original["producer"],
                "physical_successor": producer,
                "routing_context_run": prepared["run"]["run_id"],
                "routing_settings": read(root / "routing-settings.json"),
                "native_log_sha256": digest(root / "native-stage.log"),
            },
        },
    )
    snapshot = "local-" + producer + "-native-grt"
    inputs = {
        "adapter": "orfs",
        "metadata_path": "inputs/stage-facts.json",
        "snapshot_id": snapshot,
        "design_id": design_id,
        "revision_id": experiment.name + "-native-grt",
        "run_id": producer,
        "stage": "global_route",
        "created_at": now(),
        "native_extra_paths": ["inputs/stage-facts.json", "inputs/native-stage.log"],
    }
    saved = experiment / "jobs/publish-native-grt/task.json"
    if saved.exists():
        inputs["created_at"] = read(saved)["inputs"]["created_at"]
    exported = jobs.submit(
        "publish-native-grt",
        inputs,
        [
            {"source": str(p), "destination": "inputs/" + p.name}
            for p in (metadata, root / "native-stage.log")
        ],
        cpu=1,
        memory_gib=2,
        seconds=120,
        parent=producer,
        analysis_parent=producer,
    )
    artifact = next(a for a in exported["artifacts"] if a["kind"] == "data_snapshot")
    import_snapshot(
        jobs, exported["run"]["run_id"], artifact["artifact_id"], snapshot, producer
    )
    frozen = read(root / "inputs.json")["input_hashes"]
    checkpoint(
        experiment,
        design_id=design_id,
        odb=root / "orfs/results/5_1_grt.odb",
        producer=producer,
        objective=objective,
        pdk=Path(original["pdk"]),
        extra_inputs=tuple(
            [Path(p) for p in frozen]
            + [root / "inputs.json", root / "routing-init.tcl", metadata]
        ),
        native_method={
            "kind": "native-ORFS-physical-repair",
            "physical_stage": "global_route",
            "origin_result": str(source),
            "origin_result_sha256": digest(source),
            "origin_run_id": frame["run_id"],
            "origin_snapshot_ids": frame["snapshot_ids"],
            "origin_producer": original["producer"],
            "origin_native_method": frame.get("native_method"),
            "routing_context_run": prepared["run"]["run_id"],
            "global_route_run": producer,
            "stage_snapshot_id": snapshot,
            "recipe": str(root / "command.json"),
            "native_promotion_changed": False,
        },
    )
    return finish(deployment, experiment)
