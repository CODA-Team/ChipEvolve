"""Run the native GoalEvolve baseline and four-Student round on a registered GCD handoff."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

from overnight_runtime import command
from prepare_common_goalevolve import freeze_controller
from run_dplevolve_native import digest, write_json

ROOT = Path(__file__).resolve().parents[1]
U4 = ROOT / "var/code-agent/u4-goalevolve-common-20261013"


def prepare(state: Path, key: str, agent_key: str = "goal"):
    from openroad_platform_client import KernelClient

    run = state / "agents" / agent_key
    if (run / "profile.json").exists():
        raise FileExistsError("Prepared profile is frozen; use a new experiment")
    run.mkdir(parents=True, exist_ok=True)
    source = run / "control-gcd"
    if not source.exists():
        source = freeze_controller(run, "gcd")
    runtime = json.loads((state / "runtime.json").read_text())
    old = json.loads((U4 / "config.json").read_text())
    client = KernelClient(runtime["kernel_url"])
    data = json.loads((state / (key + "-data.json")).read_text())
    parent = data["opendb"]["execution"]["run"]["labels"]["analysis_of_run_id"]
    bench_root = run / "inputs/benchmarks"
    benchmark = bench_root / "gcd"
    benchmark.mkdir(parents=True, exist_ok=True)
    for kind, name in [
        ("raw_layout", "gcd.def"),
        ("raw_netlist", "gcd.v"),
        ("raw_constraints", "gcd.sdc"),
        ("raw_design_database", "gcd.odb"),
    ]:
        artifact = next(
            a for a in data["opendb"]["execution"]["artifacts"] if a["kind"] == kind
        )
        client.materialize_artifact(
            artifact["run_id"], artifact["artifact_id"], str(benchmark / name)
        )
    pdk = bench_root.parent / "asap7"
    if not pdk.exists():
        shutil.copytree(U4 / "control-r4/third_party/benchmarks/asap7", pdk)
        with (pdk / "setRC.tcl").open("a") as stream:
            stream.write(
                "\n# Actual ORFS GCD routing bounds.\nset route_signal_layers M2-M7\nset route_clock_layers M2-M7\n"
            )
    official = source / "third_party/official_checker"
    if not official.exists():
        shutil.copytree(U4 / "control-r4/third_party/official_checker", official)
    profile_path = run / "profile.json"
    profile = {
        **old,
        "profile_path": str(profile_path),
        "state_root": str(run),
        "agent_root": str(source),
        "experiment_id": state.name + "-" + agent_key,
        "design": "gcd",
        "kernel_url": runtime["kernel_url"],
        "client_python": runtime["client_python"],
        "operations_root": str(run / "operations"),
        "deadline_epoch": time.time() + 8 * 3600,
        "read_roots": [str(source), str(U4 / "preparation/source-common")],
        "write_roots": [str(run)],
        "controller_files": {
            name: digest(source / name)
            for name in subprocess.check_output(["git", "ls-files", "-z"], cwd=source)
            .decode()
            .split("\0")
            if name and (source / name).is_file()
        },
        "input_files": {
            str(p): digest(p) for p in (run / "inputs").rglob("*") if p.is_file()
        },
        "data_context": {
            "data_url": runtime["data_url"],
            "snapshot_id": data["opendb"]["snapshot_id"],
            "metrics_snapshot_id": data["orfs"]["snapshot_id"],
            "parent_run_id": parent,
        },
    }
    write_json(profile_path, profile)
    raw = json.loads(
        (U4 / "campaigns/aes_cipher_top/u4/config/evolve.json").read_text()
    )
    raw.update(
        design="gcd",
        benchmark_root=str(bench_root),
        state_root=str(run / "baseline"),
        baseline_evaluation_root=None,
        campaign_ready=False,
        max_campaign_rounds=1,
        source_root=old["source_seed"],
        baseline_metrics={
            "dynamic_power_pw": 1,
            "leakage_power_pw": 1,
            "tns_abs_ns": 1,
        },
        target_metrics={"dynamic_power_pw": 0, "leakage_power_pw": 0, "tns_abs_ns": 0},
    )
    # Placeholders are contract inputs only; they are replaced by measured
    # values before the native campaign is marked ready. Never publish them as facts.
    write_json(run / "baseline-config.json", raw)
    libs = sorted((pdk / "lib").glob("*.lib"))
    export_tcl = run / "export-input.tcl"
    export_tcl.write_text(
        "\n".join(
            [
                *[f"read_liberty {{{p}}}" for p in libs],
                f"read_db {{{benchmark / 'gcd.odb'}}}",
                "remove_fillers",
                "foreach net [[ord::get_db_block] getNets] { if {[$net getSigType] ni {POWER GROUND}} { set wire [$net getWire]; if {$wire ne {NULL}} { odb::dbWire_destroy $wire } } }",
                f"write_db {{{benchmark / 'gcd.odb'}}}",
                f"write_def {{{benchmark / 'gcd.def'}}}",
                f"write_verilog {{{benchmark / 'gcd.v'}}}",
                f"source {{{official / 'validity_check/OpenROAD_utils.tcl'}}}",
                f"write_node_and_net_files {{{benchmark / 'node.csv'}}} {{{benchmark / 'nets.csv'}}}",
                "exit",
            ]
        )
        + "\n"
    )
    result = command(
        state,
        agent_key + "-native-input-export",
        [
            "apptainer",
            "exec",
            "--cleanenv",
            "--no-home",
            "--bind",
            str(state) + ":" + str(state),
            runtime["image"],
            "/OpenROAD-flow-scripts/tools/install/OpenROAD/bin/openroad",
            "-exit",
            str(export_tcl),
        ],
        timeout=300,
        memory_gib=8,
        cpu=2,
    )
    if result["run"]["status"] != "succeeded":
        raise RuntimeError("Official node/net export failed")
    profile["input_files"] = {
        str(p): digest(p) for p in (run / "inputs").rglob("*") if p.is_file()
    }
    write_json(profile_path, profile)
    return profile_path


def native(state: Path, phase: str, agent_key: str = "goal"):
    run = state / "agents" / agent_key
    profile = json.loads((run / "profile.json").read_text())
    env = dict(os.environ)
    env.update(
        GOALEVOLVE_PLATFORM_PROFILE=str(run / "profile.json"),
        NO_PROXY="127.0.0.1,localhost",
        no_proxy="127.0.0.1,localhost",
        PYTHONNOUSERSITE="1",
    )
    if phase == "baseline":
        argv = [
            profile["agent_python"],
            "-m",
            "goalevolve.cli",
            "baseline",
            "--config",
            str(run / "baseline-config.json"),
        ]
    else:
        measured = json.loads((run / "baseline/baseline.json").read_text())
        if not measured["ok"]:
            raise ValueError("Only a real passing baseline makes a ready campaign")
        raw = json.loads((run / "baseline-config.json").read_text())
        metrics = measured["metrics"]
        contract_metrics = {name: metrics[name] for name in raw["baseline_metrics"]}
        raw.update(
            state_root=str(run / "campaign"),
            baseline_evaluation_root=str(run / "baseline"),
            campaign_ready=True,
            baseline_metrics=contract_metrics,
            target_metrics={
                name: (value if name == "tns_abs_ns" else value * 0.9)
                for name, value in metrics.items()
                if name in {"dynamic_power_pw", "leakage_power_pw", "tns_abs_ns"}
            },
        )
        write_json(run / "evolve-config.json", raw)
        argv = [
            profile["agent_python"],
            "-m",
            "goalevolve.cli",
            "run",
            "--config",
            str(run / "evolve-config.json"),
            "--rounds",
            "1",
            "--repository-graph",
            "on",
        ]
    with (run / (phase + ".log")).open("x") as log:
        process = subprocess.Popen(
            argv,
            cwd=profile["agent_root"],
            env=env,
            stdout=log,
            stderr=log,
            start_new_session=True,
        )
    write_json(
        run / (phase + "-launch.json"),
        {"pid": process.pid, "command": argv, "started_epoch": time.time()},
    )
    return process.pid


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "baseline", "evolve"])
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--data-key", default="dpl-routed")
    parser.add_argument("--agent-key", default="goal")
    args = parser.parse_args()
    state = args.state.resolve()
    print(
        prepare(state, args.data_key, args.agent_key)
        if args.action == "prepare"
        else native(state, args.action, args.agent_key)
    )
