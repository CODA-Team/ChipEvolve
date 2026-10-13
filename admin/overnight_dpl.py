"""Measure the preserved DPL source algorithms on the actual Flow handoff."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

from overnight_runtime import command
from run_dplevolve_native import digest, source_inventory, write_json

ROOT = Path(__file__).resolve().parents[1]
U3 = ROOT / "var/code-agent/u3-dplevolve-common-20261013"


def prepare(state: Path) -> Path:
    run = state / "agents/dpl"
    run.mkdir(parents=True, exist_ok=False)
    runtime = json.loads((state / "runtime.json").read_text())
    old = json.loads((U3 / "config.json").read_text())
    source = run / "source"
    subprocess.run(
        [
            "git",
            "clone",
            "--quiet",
            "--no-hardlinks",
            str(ROOT / "dplevolve"),
            str(source),
        ],
        check=True,
    )
    orfs = run / "orfs"
    orfs.mkdir()
    subprocess.run(
        ["cp", "-a", "--reflink=auto", str(U3 / "orfs/flow"), str(orfs / "flow")],
        check=True,
    )
    for name in ("results", "reports", "logs", "objects"):
        p = orfs / "flow" / name
        if p.exists():
            shutil.rmtree(p)
        p.mkdir()
    namespace = orfs / "tools/OpenROAD/src/dpl_evolve"
    namespace.parent.mkdir(parents=True)
    shutil.copytree(U3 / "orfs/tools/OpenROAD/src/dpl_evolve", namespace)
    result = orfs / "flow/results/asap7/gcd/overnight"
    result.mkdir(parents=True)
    for path in (state / "handoffs/flow/flow/results").iterdir():
        if path.is_file():
            shutil.copyfile(path, result / path.name)
    # A fresh source-optimized binary was already built and independently
    # reproduced in U3. Reuse those exact bytes, without claiming a new build.
    variant = run / "state/candidate"
    variant.parent.mkdir()
    subprocess.run(
        ["cp", "-a", "--reflink=auto", str(U3 / "state/replay/variant"), str(variant)],
        check=True,
    )
    data = json.loads((state / "flow-selected-data.json").read_text())
    parent = json.loads((state / "flow-selection.json").read_text())["run_id"]
    path = run / "profile.json"
    profile = {
        **old,
        "profile_path": str(path),
        "experiment_id": state.name + "-dpl",
        "agent_root": str(source),
        "orfs_root": str(orfs),
        "state_root": str(run / "state"),
        "operations_root": str(run / "operations"),
        "client_python": runtime["client_python"],
        "kernel_url": runtime["kernel_url"],
        "deadline_epoch": time.time() + 8 * 3600,
        "platform": "asap7",
        "design": "gcd",
        "case": "gcd_asap7",
        "flow_variant": "overnight",
        "controller_files": source_inventory(source),
        "flow_output_roots": [
            str(orfs / "flow" / n) for n in ("results", "reports", "logs", "objects")
        ],
        "data_context": {
            "data_url": runtime["data_url"],
            "snapshot_id": data["opendb"]["snapshot_id"],
            "metrics_snapshot_id": data["orfs"]["snapshot_id"],
            "parent_run_id": parent,
        },
    }
    profile["resources"]["physical"] = {
        "cpu_cores": 8,
        "memory_bytes": 24 << 30,
        "processes": 2048,
    }
    env = profile["container_environment"]
    env.update(
        DPL_EVOLVE_AGENT_ROOT=str(source),
        DPL_EVOLVE_STATE_ROOT=profile["state_root"],
        ORFS_ROOT=str(orfs),
        ORFS_BUILD_ROOT=str(orfs),
        FLOW_HOME=str(orfs / "flow"),
        DPL_EVOLVE_PLATFORM_PROFILE=str(path),
        PYTHONPYCACHEPREFIX=str(run / "state/pycache"),
    )
    write_json(path, profile)
    write_json(
        run / "input-receipt.json",
        {
            "parent_run_id": parent,
            "stage": "3_4_place_resized",
            "files": {p.name: digest(p) for p in result.iterdir() if p.is_file()},
            "candidate_binary_reused_from": str(
                U3 / "state/replay/variant/install/OpenROAD/bin/openroad"
            ),
        },
    )
    return path


def measure(state: Path):
    run = state / "agents/dpl"
    profile = json.loads((run / "profile.json").read_text())
    env = dict(os.environ)
    env.update(profile["container_environment"])
    env.update(
        DPL_EVOLVE_PLATFORM_PROFILE=profile["profile_path"],
        DPL_EVOLVE_PYTHON=profile["client_python"],
        NO_PROXY="127.0.0.1,localhost",
        no_proxy="127.0.0.1,localhost",
        PYTHONNOUSERSITE="1",
        DPL_EVOLVE_SKIP_ENV_SH="1",
    )
    for line, label, binary in [
        ("openroad_dpl_flow", "diamond", profile["core_binary"]),
        ("openroad_dpl_negotiation", "negotiation", profile["core_binary"]),
        ("evolve_default", "framework", profile["core_binary"]),
        (
            "evolve_default",
            "candidate",
            str(run / "state/candidate/install/OpenROAD/bin/openroad"),
        ),
    ]:
        with (run / (label + ".log")).open("x") as log:
            subprocess.run(
                [
                    "bash",
                    str(Path(profile["agent_root"]) / "baseline/run_baseline.sh"),
                    "--line",
                    line,
                    "--case",
                    "gcd_asap7",
                    "--flow-variant",
                    "overnight",
                    "--input-stage",
                    "3_4_place_resized",
                    "--run-tag",
                    label,
                    "--threads",
                    "8",
                    "--openroad-binary",
                    binary,
                ],
                env=env,
                stdout=log,
                stderr=log,
                check=True,
            )
    metrics = {
        label: json.loads(
            (
                Path(profile["orfs_root"])
                / "flow/reports/asap7/gcd/overnight/dpl_evolve_baseline"
                / label
                / "metrics.json"
            ).read_text()
        )
        for label in ("diamond", "negotiation", "framework", "candidate")
    }
    write_json(run / "measurements.json", metrics)
    return metrics


def finish(state: Path, key: str = "dpl-routed"):
    """Resume CTS/routing from the actual source-optimized placement."""
    run = state / "agents/dpl"
    profile = json.loads((run / "profile.json").read_text())
    runtime = json.loads((state / "runtime.json").read_text())
    work = state / "handoffs" / key
    results = work / "results/asap7/gcd/base"
    results.mkdir(parents=True, exist_ok=False)
    for path in (state / "handoffs/flow/flow/results").iterdir():
        if path.is_file() and path.name[0] in "123":
            shutil.copyfile(path, results / path.name)
    native = (
        Path(profile["orfs_root"])
        / "flow/results/asap7/gcd/overnight/dpl_evolve_baseline/candidate/legalized.odb"
    )
    for name in ("3_5_place_dp.odb", "3_place.odb"):
        shutil.copyfile(native, results / name)
    flow = state / "agents/flow-r5/source/flow"
    original = flow / "backup_dir/asap7/gcd/result_dump_2/config_6.mk"
    config = work / "config.mk"
    # Preserve the selected candidate's full actual config and constraints.
    shutil.copy2(original, config)
    parents = [
        json.loads(p.read_text())["run"]["run_id"]
        for p in (run / "operations").glob("*/execution.json")
    ]
    write_json(
        work / "handoff.json",
        {
            "flow_run_id": profile["data_context"]["parent_run_id"],
            "dpl_run_ids": parents,
            "dpl_odb_sha256": digest(native),
            "config_sha256": digest(config),
            "resume_stage": "cts",
            "built_source_candidate": "U3 independently replayed source",
        },
    )
    result = command(
        state,
        key + "-finish",
        [
            "apptainer",
            "exec",
            "--cleanenv",
            "--no-home",
            "--bind",
            str(state) + ":" + str(state),
            "--pwd",
            str(flow),
            runtime["image"],
            "make",
            "DESIGN_CONFIG=" + str(config),
            "WORK_HOME=" + str(work),
            "FLOW_VARIANT=base",
            "NUM_CORES=8",
            "OPENROAD_EXE=/OpenROAD-flow-scripts/tools/install/OpenROAD/bin/openroad",
            "YOSYS_EXE=/OpenROAD-flow-scripts/tools/install/yosys/bin/yosys",
            "PYTHON_EXE=/usr/bin/python3",
            "finish",
        ],
        timeout=1800,
        memory_gib=24,
        cpu=8,
    )
    if result["run"]["status"] != "succeeded":
        raise RuntimeError("DPL checkpoint to real CTS/route failed")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "measure", "finish"])
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--key", default="dpl-routed")
    args = parser.parse_args()
    state = args.state.resolve()
    if args.action == "prepare":
        print(prepare(state))
    elif args.action == "measure":
        print(list(measure(state)))
    else:
        print(finish(state, args.key)["run"]["status"])
