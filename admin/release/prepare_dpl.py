"""Prepare and build DPLEvolve's common OpenROAD core for the GCD demo."""

import argparse
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path

from native_toolchain import checkout, openroad_build_args
from stack import configuration, get, write


def git_head(path):
    return subprocess.check_output(
        ["git", "-C", path, "rev-parse", "HEAD"], text=True
    ).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True, help="running GCD stack")
    parser.add_argument("--build-memory-gib", type=int, default=64)
    args = parser.parse_args()
    stack = configuration(args.config)
    if not 8 <= args.build_memory_gib <= stack.get("memory_gib", 24):
        parser.error("Set build memory within the stack capacity, with at least 8 GiB")
    root = Path(stack["workspace"])
    state = Path(stack["state_root"])
    deployment = json.loads((state / "local.json").read_text())
    get(deployment["kernel_url"] + "/kernel/health")
    module = root / "agent/dplevolve"
    python = module / ".venv/bin/python"
    if not python.is_file():
        parser.error("Install DPLEvolve's environment using bootstrap.py")
    metadata = json.loads((module / "metadata/common_toolchain.json").read_text())
    pins = metadata["workspace_model"]
    output = state / "dpl-preparation"
    output.mkdir(exist_ok=False)
    orfs, native_state = output / "orfs", output / "state"
    checkout(
        orfs,
        "https://github.com/The-OpenROAD-Project/OpenROAD-flow-scripts.git",
        pins["orfs_base_commit"],
        submodules=("tools/OpenROAD",),
    )
    openroad = orfs / "tools/OpenROAD"
    if git_head(openroad) != pins["openroad_base_commit"]:
        raise ValueError("ORFS and DPLEvolve declare different OpenROAD source pins")
    workspace_scripts = module / "scripts/workspace"
    profile_path = output / "profile.json"
    env = dict(
        os.environ,
        PYTHONNOUSERSITE="1",
        GIT_TERMINAL_PROMPT="0",
        GIT_LFS_SKIP_SMUDGE="1",
    )
    for key in (
        "PYTHONPATH",
        "PYTHONHOME",
        "VIRTUAL_ENV",
        "CONDA_PREFIX",
        "DPL_EVOLVE_OPENROAD_URL",
    ):
        env.pop(key, None)
    env.update(
        DPL_EVOLVE_AGENT_ROOT=str(module),
        DPL_EVOLVE_STATE_ROOT=str(native_state),
        DPL_EVOLVE_PYTHON=str(python),
        DPL_EVOLVE_PLATFORM_PROFILE=str(profile_path),
        DPL_EVOLVE_SKIP_ENV_SH="1",
        ORFS_ROOT=str(orfs),
        GIT_AUTHOR_NAME="ChipEvolve",
        GIT_AUTHOR_EMAIL="local@chipevolve.invalid",
        GIT_COMMITTER_NAME="ChipEvolve",
        GIT_COMMITTER_EMAIL="local@chipevolve.invalid",
    )
    subprocess.run(
        ["bash", workspace_scripts / "prepare_workspace.sh"],
        env=env,
        cwd=module,
        check=True,
    )
    manifest = output / "prepared-source.json"
    write(
        manifest,
        {
            "orfs": git_head(orfs),
            "openroad": git_head(openroad),
            "dplevolve": git_head(module),
        },
    )
    cpu = stack.get("cpu_cores", 8)
    core = native_state / "core"
    core_binary = core / "install/OpenROAD/bin/openroad"
    flow = orfs / "flow"
    flow_outputs = [flow / name for name in ("results", "reports", "logs", "objects")]
    for folder in flow_outputs:
        folder.mkdir(exist_ok=True)
    resources = {"cpu_cores": cpu, "processes": 2048}
    profile = {
        "profile_path": str(profile_path),
        "experiment_id": state.name + "-dpl-core",
        "agent_root": str(module),
        "orfs_root": str(orfs),
        "state_root": str(native_state),
        "operations_root": str(output / "operations"),
        "core_root": str(core),
        "core_binary": str(core_binary),
        "client_python": deployment["client_python"],
        "container_python": "/usr/bin/python3",
        "kernel_url": deployment["kernel_url"],
        "image": deployment["runtime"]["image"],
        "design": "gcd",
        "toolchain": {
            **deployment["toolchain"],
            **pins,
            "opensta_commit": metadata["opensta_commit"],
        },
        "prepared_source_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
        "controller_files": {
            str(path.relative_to(module)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in workspace_scripts.glob("*.sh")
        },
        "flow_output_roots": list(map(str, flow_outputs)),
        "deadline_epoch": time.time() + 5400,
        "resources": {
            "build": {**resources, "memory_bytes": args.build_memory_gib << 30},
            "variant_build": {
                **resources,
                "memory_bytes": min(24, args.build_memory_gib) << 30,
            },
            "physical": {**resources, "memory_bytes": 8 << 30},
        },
        "cmake_args": ["-DCMAKE_BUILD_TYPE=Release", *openroad_build_args(openroad)],
        "container_environment": {
            **{
                key: env[key]
                for key in (
                    "DPL_EVOLVE_AGENT_ROOT",
                    "DPL_EVOLVE_STATE_ROOT",
                    "DPL_EVOLVE_PLATFORM_PROFILE",
                    "ORFS_ROOT",
                )
            },
            "DPL_EVOLVE_PYTHON": "/usr/bin/python3",
            "OPENROAD_EXE": str(core_binary),
            "ORFS_BUILD_ROOT": str(orfs),
            "FLOW_HOME": str(flow),
            "YOSYS_EXE": "/OpenROAD-flow-scripts/tools/install/yosys/bin/yosys",
            "OMP_NUM_THREADS": str(cpu),
        },
    }
    write(profile_path, profile)
    subprocess.run(
        ["bash", workspace_scripts / "configure_openroad_core.sh", "--core-root", core],
        env=env,
        cwd=module,
        check=True,
    )
    subprocess.run(
        [
            "bash",
            workspace_scripts / "build_openroad_core.sh",
            "--core-root",
            core,
            "--threads",
            str(cpu),
        ],
        env=env,
        cwd=module,
        check=True,
    )
    if not (core_binary.parent / "platform-build.json").is_file():
        raise RuntimeError("Execution Foundation did not produce a core build receipt")
    deployment.setdefault("professional", {})["dpl"] = {
        "source": str(module),
        "python": str(python),
        "profile_template": str(profile_path),
        "physical_memory_gib": 8,
    }
    deployment["designs"]["gcd"].update(
        dpl_case="gcd_nangate45",
        signal_layers="metal2-metal10",
        clock_layers="metal4-metal10",
    )
    write(state / "local.json", deployment)
    print(profile_path)


if __name__ == "__main__":
    main()
