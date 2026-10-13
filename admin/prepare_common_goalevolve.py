"""Prepare the authorized U4 runtime using pinned sources and installed wheels."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from qualify_common_toolchain import (
    IMAGE_SHA,
    OPENROAD,
    ORFS,
    available_port,
    environment,
)
from run_dplevolve_native import digest, write_json

ROOT = Path(__file__).resolve().parents[1]
U1 = ROOT / "var/toolchains/common-u1-20261012-retry6"
NATIVE_PYTHON = (
    ROOT
    / "var/code-agent/l3-goalevolve-20261011/source/outputs/toolchain/conda-env/bin/python"
)


def freeze_controller(state: Path, revision: str) -> Path:
    target = state / ("control-" + revision)
    if target.exists():
        raise FileExistsError(target)
    subprocess.run(
        [
            "git",
            "clone",
            "--quiet",
            "--no-hardlinks",
            "--no-checkout",
            str(ROOT / "goalevolve"),
            str(target),
        ],
        check=True,
    )
    # Historical published snapshots stay in the authoritative module. The
    # native common campaign consumes its explicit professional seed instead.
    subprocess.run(
        [
            "git",
            "sparse-checkout",
            "set",
            "goalevolve",
            "config",
            "experiments",
            "toolchain",
            "third_party/official_checker",
            "third_party/benchmarks/asap7",
            "third_party/benchmarks/benchmarks/aes_cipher_top",
            "knowledge",
            "scripts",
            "tests",
        ],
        cwd=target,
        check=True,
    )
    subprocess.run(["git", "checkout", "--quiet"], cwd=target, check=True)
    names = (
        subprocess.check_output(
            ["git", "diff", "--name-only", "-z", "HEAD"], cwd=ROOT / "goalevolve"
        )
        .decode()
        .split("\0")
    )
    names += (
        subprocess.check_output(
            ["git", "ls-files", "--others", "--exclude-standard", "-z"],
            cwd=ROOT / "goalevolve",
        )
        .decode()
        .split("\0")
    )
    for name in filter(None, names):
        source = ROOT / "goalevolve" / name
        if source.is_file():
            destination = target / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
    subprocess.run(["git", "add", "-A"], cwd=target, check=True)
    if subprocess.run(
        ["git", "diff", "--cached", "--quiet"], cwd=target, check=False
    ).returncode:
        subprocess.run(
            ["git", "commit", "--quiet", "-m", "[切片U4] 冻结本轮控制源码"],
            cwd=target,
            check=True,
        )
    return target


def install_environment(
    state: Path, name: str, python: str, packages: list[str], *, offline: bool
) -> Path:
    target = state / "envs" / name
    subprocess.run([python, "-m", "venv", "--without-pip", str(target)], check=True)
    command = [
        str(ROOT / "execution-foundation/.venv/bin/python"),
        "-m",
        "pip",
        "--python",
        str(target / "bin/python"),
        "install",
    ]
    if offline:
        command += [
            "--no-index",
            "--find-links",
            str(state / "wheels"),
            "--find-links",
            str(ROOT / "wheelhouse"),
        ]
    subprocess.run([*command, *packages], env=environment(), check=True)
    return target / "bin/python"


def prepare_source(state: Path) -> Path:
    """Apply exact professional patches to a private qualified common source."""
    source = state / "preparation/source-common"
    metadata = json.loads(
        (ROOT / "goalevolve/toolchain/common_toolchain.json").read_text()
    )
    if not source.exists():
        subprocess.run(
            ["cp", "-a", "--reflink=auto", str(U1 / "source/OpenROAD"), str(source)],
            check=True,
        )
        for name in ("rsz.patch", "rmp.patch", "build_api.patch"):
            patch_path = ROOT / "goalevolve/toolchain/common" / name
            if digest(patch_path) != metadata["patch_sha256"][name]:
                raise ValueError("Professional patch identity changed: " + name)
            subprocess.run(
                ["git", "apply", "--check", str(patch_path)], cwd=source, check=True
            )
            subprocess.run(["git", "apply", str(patch_path)], cwd=source, check=True)
    for name, sha in metadata["professional_files"].items():
        if digest(source / name) != sha:
            raise ValueError("Prepared professional source differs: " + name)
    return source


def prepare(state: Path, revision: str) -> dict[str, Any]:
    if (state / "config.json").exists():
        raise FileExistsError(
            "Frozen preparation exists; use a recorded profile revision"
        )
    baseline = json.loads((state / "baseline.json").read_text())
    image = Path("/home/wjyuan/projects/eda-toolchain/orfs-8e6ee7aac233da07.sif")
    if digest(image) != IMAGE_SHA:
        raise ValueError("Common SIF differs from the qualified image")
    source = prepare_source(state)
    controller = freeze_controller(state, revision)
    wheels = state / "wheels"
    shutil.copytree(U1 / "wheels", wheels, dirs_exist_ok=True)
    packages = sorted(map(str, wheels.glob("openroad_platform_*.whl"))) + sorted(
        map(str, wheels.glob("eda_toolkits-*.whl"))
    )
    client_python = install_environment(
        state, "client", sys.executable, packages, offline=True
    )
    agent_python = install_environment(
        state,
        "goal",
        str(NATIVE_PYTHON),
        ["-e", str(controller), "pytest", "pytest-subtests"],
        offline=False,
    )
    codex_settings = json.loads((controller / "config/codex.json").read_text())
    for role in ("teacher", "student"):
        codex_settings[role]["model"] = "gpt-6.1-sol"
    write_json(state / "codex.json", codex_settings)
    inputs = {
        str(p): digest(p)
        for folder in (
            controller / "third_party/benchmarks/benchmarks/aes_cipher_top",
            controller / "third_party/benchmarks/asap7",
            controller / "third_party/official_checker",
        )
        for p in folder.rglob("*")
        if p.is_file() and p.suffix != ".pyc"
    }
    profile = {
        "adapter_timeout_ceiling_seconds": 7260,
        "profile_path": str(state / "config.json"),
        "experiment_id": state.name,
        "design": "aes_cipher_top",
        "state_root": str(state),
        "agent_root": str(controller),
        "source_seed": str(source),
        "agent_python": str(agent_python),
        "client_python": str(client_python),
        "operations_root": str(state / "operations"),
        "image": str(image),
        "input_files": inputs,
        "controller_files": {
            str(p.relative_to(controller)): digest(p)
            for folder in (
                controller / "goalevolve",
                controller / "config",
                controller / "experiments",
                controller / "toolchain",
            )
            for p in folder.rglob("*")
            if p.is_file() and p.suffix in {".py", ".json", ".patch"}
        },
        "kernel_url": "http://127.0.0.1:" + str(available_port()),
        "deadline_epoch": baseline["deadline_epoch"],
        "codex": {
            "auth_mode": "existing_codex",
            "home": "/home/wjyuan/.codex",
            "config_path": str(state / "codex.json"),
        },
        "toolchain": {
            "image_sha256": IMAGE_SHA,
            "openroad_commit": OPENROAD,
            "orfs_commit": ORFS,
            "opensta_commit": "e983e15b2cb346badf8f23725fd3914d25312c44",
        },
        "resources": {
            "build": {"cpu_cores": 8, "memory_bytes": 64 << 30, "processes": 2048},
            "physical": {"cpu_cores": 8, "memory_bytes": 16 << 30, "processes": 512},
        },
        "read_roots": [str(controller)],
        "write_roots": [str(state)],
        "container_environment": {
            "OMP_NUM_THREADS": "8",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
        },
        "cmake_args": [
            "-DBUILD_GUI=OFF",
            "-DBUILD_PYTHON=ON",
            "-DBoost_DIR=/usr/local/lib/cmake/Boost-1.89.0",
            "-Dortools_ROOT=/opt/or-tools",
            "-DABSL_ROOT=/opt/or-tools",
            "-DFETCHCONTENT_SOURCE_DIR_FMT="
            + str(source / "third-party/slang-elab/third_party/fmt"),
            "-DFETCHCONTENT_FULLY_DISCONNECTED=ON",
            "-DCMAKE_EXE_LINKER_FLAGS=-flto=1",
        ],
        "wheel_sha256": {p.name: digest(p) for p in wheels.glob("*.whl")},
        "unified_data": False,
    }
    write_json(state / "config.json", profile)
    return profile


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--revision", default="r1")
    args = parser.parse_args()
    profile = prepare(args.state.resolve(), args.revision)
    print(
        json.dumps(
            {
                "profile": profile["profile_path"],
                "agent_python": profile["agent_python"],
            }
        )
    )


if __name__ == "__main__":
    main()
