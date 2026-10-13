"""Local U3 verification controller; native Teacher/Student remain authoritative."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from qualify_common_toolchain import available_port, environment, git, http
from run_dplevolve_native import digest, now, source_inventory, write_json

ROOT = Path(__file__).resolve().parents[1]
U1 = ROOT / "var/toolchains/common-u1-20261012-retry6"
U2 = ROOT / "var/flow-agent/u2-common-20261012"


def freeze_controller(state: Path, name: str) -> Path:
    source = state / name
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
    paths = (
        subprocess.check_output(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            cwd=ROOT / "dplevolve",
        )
        .decode()
        .split("\0")
    )
    for relative in filter(None, paths):
        item = ROOT / "dplevolve" / relative
        if item.is_file():
            target = source / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(item, target)
    subprocess.run(["git", "add", "-A"], cwd=source, check=True)
    subprocess.run(
        ["git", "commit", "--quiet", "-m", "[切片U3] 冻结本次平台控制源码"],
        cwd=source,
        check=True,
    )
    return source


def prepare(state: Path, image: Path) -> dict[str, Any]:
    if (state / "config.json").exists():
        raise FileExistsError(
            "Preparation is frozen; retain it and use an explicit new profile revision"
        )
    state.mkdir(parents=True, exist_ok=True)
    (state / "preparation").mkdir(exist_ok=True)
    if not (state / "preparation/baseline.json").exists():
        write_json(
            state / "preparation/baseline.json",
            {
                "created_at": now(),
                "root_head": git(ROOT, "rev-parse", "HEAD"),
                "root_status": git(
                    ROOT, "status", "--short", "--ignore-submodules=all"
                ),
                "module_heads": {
                    p.name: git(p, "rev-parse", "HEAD")
                    for p in [
                        ROOT / n
                        for n in (
                            "execution-foundation",
                            "data-foundation",
                            "data-interface",
                            "query-agent",
                            "toolkits",
                            "flow-agent",
                            "dplevolve",
                            "goalevolve",
                        )
                    ]
                },
            },
        )
    source = freeze_controller(state, "control-r1")
    metadata = json.loads((source / "metadata/common_toolchain.json").read_text())
    if digest(image) != metadata["image_sha256"]:
        raise ValueError("Common image SHA mismatch")
    orfs = state / "orfs"
    if not (orfs / ".git").is_dir():
        orfs.mkdir(exist_ok=True)
        subprocess.run(["git", "init", "--quiet", str(orfs)], check=True)
        subprocess.run(
            [
                "git",
                "remote",
                "add",
                "origin",
                "https://github.com/The-OpenROAD-Project/OpenROAD-flow-scripts.git",
            ],
            cwd=orfs,
            check=True,
        )
        git_env = environment()
        git_env.update(
            GIT_CONFIG_COUNT="1",
            GIT_CONFIG_KEY_0="http.version",
            GIT_CONFIG_VALUE_0="HTTP/1.1",
        )
        if os.environ.get("HTTPS_PROXY"):
            git_env.update(
                GIT_CONFIG_COUNT="2",
                GIT_CONFIG_KEY_1="http.proxy",
                GIT_CONFIG_VALUE_1=os.environ["HTTPS_PROXY"],
            )
        subprocess.run(
            [
                "git",
                "fetch",
                "--depth=1",
                "origin",
                metadata["workspace_model"]["orfs_base_commit"],
            ],
            cwd=orfs,
            env=git_env,
            check=True,
            timeout=120,
        )
        subprocess.run(
            ["git", "checkout", "--detach", "FETCH_HEAD"], cwd=orfs, check=True
        )
        shutil.copytree(
            U1 / "source/OpenROAD",
            orfs / "tools/OpenROAD",
            symlinks=True,
            dirs_exist_ok=True,
        )
    if not (state / "state/seed_sources/framework_dpl_evolve").is_dir():
        env = environment()
        env.update(
            DPL_EVOLVE_PLATFORM_PROFILE=str(state / "config.json"),
            DPL_EVOLVE_AGENT_ROOT=str(source),
            DPL_EVOLVE_SKIP_ENV_SH="1",
            DPL_EVOLVE_STATE_ROOT=str(state / "state"),
            DPL_EVOLVE_PYTHON=str(ROOT / "dplevolve/.venv/bin/python"),
            ORFS_ROOT=str(orfs),
            DPL_EVOLVE_OPENROAD_URL=str(U1 / "source/OpenROAD"),
        )
        with (state / "preparation/native-prepare.log").open("x") as log:
            subprocess.run(
                ["bash", str(source / "scripts/workspace/prepare_workspace.sh")],
                env=env,
                check=True,
                stdout=log,
                stderr=log,
                timeout=180,
            )
    core = (
        state
        / "state/openroad_core"
        / git(orfs / "tools/OpenROAD", "rev-parse", "--short", "HEAD")
    )
    core.mkdir(parents=True, exist_ok=True)
    client = state / "envs/client"
    subprocess.run(
        [sys.executable, "-m", "venv", "--without-pip", str(client)], check=True
    )
    wheels = state / "wheels"
    shutil.copytree(U2 / "wheels", wheels)
    packages = list(wheels.glob("openroad_platform_*.whl")) + list(
        wheels.glob("eda_toolkits-*.whl")
    )
    subprocess.run(
        [
            str(ROOT / "execution-foundation/.venv/bin/python"),
            "-m",
            "pip",
            "--python",
            str(client / "bin/python"),
            "install",
            "--no-index",
            "--find-links",
            str(wheels),
            "--find-links",
            str(ROOT / "wheelhouse"),
            *map(str, packages),
        ],
        env=environment(),
        check=True,
    )
    for part in ("results", "reports", "logs", "objects"):
        (orfs / "flow" / part).mkdir(exist_ok=True)
    files = (
        subprocess.check_output(["git", "ls-files", "-z"], cwd=source)
        .decode()
        .split("\0")
    )
    prepared = (
        subprocess.check_output(["git", "ls-files", "-z"], cwd=orfs / "tools/OpenROAD")
        .decode()
        .split("\0")
    )
    prepared_files = {
        p: digest(orfs / "tools/OpenROAD" / p)
        for p in filter(None, prepared)
        if (orfs / "tools/OpenROAD" / p).is_file()
    }
    write_json(
        state / "prepared-source.json",
        {
            "base": metadata,
            "prepared_openroad_commit": git(
                orfs / "tools/OpenROAD", "rev-parse", "HEAD"
            ),
            "prepared_orfs_commit": git(orfs, "rev-parse", "HEAD"),
            "files": prepared_files,
        },
    )
    profile = {
        "profile_path": str(state / "config.json"),
        "experiment_id": state.name,
        "agent_root": str(source),
        "orfs_root": str(orfs),
        "state_root": str(state / "state"),
        "operations_root": str(state / "operations"),
        "core_root": str(core),
        "core_binary": str(core / "install/OpenROAD/bin/openroad"),
        "client_python": str(client / "bin/python"),
        "container_python": "/usr/bin/python3",
        "image": str(image),
        "platform": "nangate45",
        "design": "gcd",
        "case": "gcd_nangate45",
        "flow_variant": "u3_gcd_common_20261013",
        "round_id": "u3_gcd_source_20261013",
        "toolchain": {
            "image_sha256": metadata["image_sha256"],
            **metadata["workspace_model"],
            "opensta_commit": metadata["opensta_commit"],
        },
        "prepared_source_sha256": digest(state / "prepared-source.json"),
        "controller_files": {
            p: digest(source / p) for p in filter(None, files) if (source / p).is_file()
        },
        "flow_output_roots": [
            str(orfs / "flow" / p) for p in ("results", "reports", "logs", "objects")
        ],
        "resources": {
            "build": {"cpu_cores": 8, "memory_bytes": 64 << 30, "processes": 2048},
            "physical": {"cpu_cores": 8, "memory_bytes": 8 << 30, "processes": 256},
        },
        "deadline_epoch": datetime.fromisoformat(
            json.loads((state / "preparation/baseline.json").read_text())["created_at"]
        ).timestamp()
        + 14400,
        "created_at": now(),
        "kernel_url": "http://127.0.0.1:" + str(available_port()),
        "wheel_sha256": {p.name: digest(p) for p in wheels.glob("*.whl")},
        "cmake_args": [
            "-DCMAKE_BUILD_TYPE=Release",
            "-DBUILD_GUI=OFF",
            "-DBUILD_PYTHON=ON",
            "-DBoost_DIR=/usr/local/lib/cmake/Boost-1.89.0",
            "-Dortools_ROOT=/opt/or-tools",
            "-DABSL_ROOT=/opt/or-tools",
            "-DFETCHCONTENT_SOURCE_DIR_FMT="
            + str(orfs / "tools/OpenROAD/third-party/slang-elab/third_party/fmt"),
            "-DFETCHCONTENT_FULLY_DISCONNECTED=ON",
            "-DCMAKE_EXE_LINKER_FLAGS=-flto=1",
        ],
    }
    profile["container_environment"] = {
        "DPL_EVOLVE_AGENT_ROOT": str(source),
        "DPL_EVOLVE_STATE_ROOT": profile["state_root"],
        "ORFS_ROOT": str(orfs),
        "ORFS_BUILD_ROOT": str(orfs),
        "FLOW_HOME": str(orfs / "flow"),
        "DPL_EVOLVE_PYTHON": "/usr/bin/python3",
        "DPL_EVOLVE_PLATFORM_PROFILE": profile["profile_path"],
        "OPENROAD_EXE": profile["core_binary"],
        "YOSYS_EXE": "/OpenROAD-flow-scripts/tools/install/yosys/bin/yosys",
        "OMP_NUM_THREADS": "8",
        "OPENBLAS_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "PYTHONPYCACHEPREFIX": str(state / "state/pycache"),
    }
    write_json(state / "config.json", profile)
    return profile


def start_service(state: Path) -> None:
    if (state / "service.json").exists():
        raise FileExistsError(
            "Service receipt already exists; reopen this exact service explicitly"
        )
    profile = json.loads((state / "config.json").read_text())
    python = profile["client_python"]
    subprocess.run(
        [
            python,
            "-m",
            "eda_toolkits",
            "configure",
            "--output",
            str(state / "plugins"),
            "--image",
            profile["image"],
        ],
        check=True,
        env=environment(),
    )
    command = [
        python,
        "-m",
        "openroad_platform_gateway",
        "--state-root",
        str(state / "kernel"),
        "--plugins-root",
        str(state / "plugins"),
        "--admissions-root",
        str(U1 / "dependency-sources/execution-foundation/admissions"),
        "--host",
        "127.0.0.1",
        "--port",
        profile["kernel_url"].rsplit(":", 1)[1],
        "--input-root",
        str(state),
        "--capacity-cpu-cores",
        "8",
        "--capacity-memory-bytes",
        str(64 << 30),
        "--platform-fraction",
        "1.0",
        "--worker-concurrency",
        "1",
    ]
    with (state / "kernel.log").open("a") as log:
        process = subprocess.Popen(
            command, env=environment(), stdout=log, stderr=log, start_new_session=True
        )
    write_json(
        state / "service.json",
        {
            "pid": process.pid,
            "command": command,
            "kernel_url": profile["kernel_url"],
            "started_at": now(),
        },
    )
    deadline = time.monotonic() + 60
    while True:
        try:
            http(profile["kernel_url"] + "/kernel/health")
            return
        except OSError:
            if process.poll() is not None or time.monotonic() > deadline:
                raise RuntimeError("U3 EF startup failed; inspect kernel.log")
            time.sleep(0.2)


def host_environment(profile: dict[str, Any]) -> dict[str, str]:
    env = environment()
    env.update(profile["container_environment"])
    env.update(
        DPL_EVOLVE_PYTHON=str(ROOT / "dplevolve/.venv/bin/python"),
        DPL_EVOLVE_SKIP_ENV_SH="1",
    )
    return env


def step(state: Path, name: str, command: list[str], *, timeout: int) -> None:
    profile = json.loads((state / "config.json").read_text())
    folder = state / "steps" / name
    folder.mkdir(parents=True, exist_ok=False)
    receipt: dict[str, Any] = {
        "command": command,
        "started_at": now(),
        "status": "running",
        "config_sha256": digest(state / "config.json"),
    }
    write_json(folder / "receipt.json", receipt)
    with (folder / "output.log").open("x") as log:
        process = subprocess.Popen(
            command,
            cwd=profile["agent_root"],
            env=host_environment(profile),
            stdout=log,
            stderr=log,
            start_new_session=True,
        )
        receipt["pid"] = process.pid
        write_json(folder / "receipt.json", receipt)
        try:
            code = process.wait(
                timeout=min(timeout, max(1, profile["deadline_epoch"] - time.time()))
            )
        except (subprocess.TimeoutExpired, KeyboardInterrupt):
            from run_dplevolve_native import stop_session

            stop_session(process)
            cancelled = []
            for submission in (state / "operations").glob("*/submission.json"):
                run_id = json.loads(submission.read_text())["run_id"]
                row = http(profile["kernel_url"] + "/kernel/runs/" + run_id)["run"]
                if row["status"] not in {
                    "succeeded",
                    "failed",
                    "cancelled",
                    "timed_out",
                    "lost",
                }:
                    http(
                        profile["kernel_url"] + "/kernel/runs/" + run_id + "/cancel", {}
                    )
                    cancelled.append(run_id)
            receipt.update(
                status="interrupted", finished_at=now(), cancelled_ef_runs=cancelled
            )
            write_json(folder / "receipt.json", receipt)
            raise
    receipt.update(
        status="succeeded" if code == 0 else "failed", exit_code=code, finished_at=now()
    )
    write_json(folder / "receipt.json", receipt)
    if code:
        raise RuntimeError("Native step failed: " + name)


def run(state: Path, phase: str) -> None:
    profile = json.loads((state / "config.json").read_text())
    source = Path(profile["agent_root"])
    python = str(ROOT / "dplevolve/.venv/bin/python")
    if phase == "core":
        step(
            state,
            "configure-core",
            [
                "bash",
                str(source / "scripts/workspace/configure_openroad_core.sh"),
                "--core-root",
                profile["core_root"],
            ],
            timeout=60,
        )
        step(
            state,
            "build-core",
            [
                "bash",
                str(source / "scripts/workspace/build_openroad_core.sh"),
                "--threads",
                "8",
            ],
            timeout=5500,
        )
    elif phase == "placement":
        env = host_environment(profile)
        command = [
            profile["client_python"],
            str(source / "scripts/platform/execution.py"),
            "delegate",
            "placement",
            "--",
            "make",
            "-C",
            str(Path(profile["orfs_root"]) / "flow"),
            "DESIGN_CONFIG=designs/nangate45/gcd/config.mk",
            "FLOW_VARIANT=" + profile["flow_variant"],
            "NUM_CORES=8",
            "3_4_place_resized",
        ]
        subprocess.run(command, env=env, check=True)
    elif phase == "baselines":
        for line in ("openroad_dpl_flow", "openroad_dpl_negotiation", "evolve_default"):
            step(
                state,
                "baseline-" + line,
                [
                    "bash",
                    str(source / "baseline/run_baseline.sh"),
                    "--line",
                    line,
                    "--case",
                    profile["case"],
                    "--flow-variant",
                    profile["flow_variant"],
                    "--threads",
                    "8",
                    "--openroad-binary",
                    profile["core_binary"],
                    "--run-tag",
                    profile["round_id"] + "_baseline_probe_" + line,
                ],
                timeout=900,
            )
    elif phase == "smoke":
        step(
            state,
            "release-smoke",
            [
                "bash",
                str(source / "scripts/repo/check_release_readiness.sh"),
                "--case",
                profile["case"],
                "--round-id",
                "u3_smoke",
                "--flow-variant",
                profile["flow_variant"],
            ],
            timeout=180,
        )
    elif phase == "evolve":
        step(
            state,
            "teacher-student",
            [
                python,
                str(source / "scripts/optimize_case_with_codex.py"),
                "--case",
                profile["case"],
                "--flow-variant",
                profile["flow_variant"],
                "--round-id",
                profile["round_id"],
                "--iterations",
                "1",
                "--children",
                "1",
                "--max-parallel",
                "1",
                "--threads",
                "8",
                "--skip-core-build",
                "--reuse-baseline-preflight",
                "--launch",
            ],
            timeout=5400,
        )
    elif phase == "replay":
        record_path = (
            Path(profile["state_root"])
            / profile["round_id"]
            / "teacher_rounds/students/student_01/iter_01/artifacts/source_commit.json"
        )
        record = json.loads(record_path.read_text())
        original_source = Path(record["source_repo"])
        replay = Path(profile["state_root"]) / "replay/variant"
        replay.mkdir(parents=True, exist_ok=False)
        target = replay / "dpl_evolve"
        subprocess.run(
            [
                "git",
                "clone",
                "--quiet",
                "--no-hardlinks",
                "--branch",
                record["source_candidate_ref"],
                str(original_source),
                str(target),
            ],
            check=True,
        )
        step(
            state,
            "configure-replay",
            [
                "bash",
                str(source / "scripts/workspace/configure_openroad_variant_relink.sh"),
                "--variant-root",
                str(replay),
                "--dpl-src",
                str(target),
                "--core-root",
                profile["core_root"],
            ],
            timeout=60,
        )
        step(
            state,
            "build-replay",
            [
                python,
                str(source / "scripts/workspace/build_openroad_variant_relink.py"),
                "--variant-root",
                str(replay),
                "--dpl-src",
                str(target),
                "--core-root",
                profile["core_root"],
                "--threads",
                "8",
            ],
            timeout=5400,
        )
        report_root = (
            Path(profile["orfs_root"])
            / "flow/reports"
            / profile["platform"]
            / profile["design"]
            / profile["flow_variant"]
            / "dpl_evolve_baseline"
        )
        baseline = json.loads(
            (
                report_root
                / (profile["round_id"] + "_baseline_probe_openroad_dpl_flow")
                / "metrics.json"
            ).read_text()
        )
        import math

        step(
            state,
            "evaluate-replay",
            [
                "bash",
                str(source / "baseline/run_baseline.sh"),
                "--line",
                "evolve_default",
                "--case",
                profile["case"],
                "--flow-variant",
                profile["flow_variant"],
                "--run-tag",
                "u3_fixed_source_replay",
                "--threads",
                "8",
                "--openroad-binary",
                str(replay / "install/OpenROAD/bin/openroad"),
                "--legalize-timeout-seconds",
                str(math.ceil(2 * baseline["runtime_seconds"])),
            ],
            timeout=900,
        )
        required = []
        for folder in sorted((state / "operations").iterdir()):
            path = folder / "execution.json"
            if (
                path.is_file()
                and json.loads(path.read_text())["run"]["status"] == "succeeded"
            ):
                required.append(folder.name)
        write_json(
            state / "evidence.json",
            {
                "required_operations": required,
                "required_steps": [
                    "release-smoke",
                    "teacher-student",
                    "configure-replay",
                    "build-replay",
                    "evaluate-replay",
                ],
                "baselines": {
                    line: str(
                        report_root
                        / (profile["round_id"] + "_baseline_probe_" + line)
                        / "metrics.json"
                    )
                    for line in (
                        "openroad_dpl_flow",
                        "openroad_dpl_negotiation",
                        "evolve_default",
                    )
                },
                "candidate": {
                    "source": str(original_source),
                    "source_base_commit": record["source_base_commit"],
                    "source_commit": record["source_commit"],
                    "candidate_ref": record["source_candidate_ref"],
                    "metrics": str(report_root / record["run_tag"] / "metrics.json"),
                    "binary": str(
                        original_source.parent / "install/OpenROAD/bin/openroad"
                    ),
                    "native_final_status": record["final_status"],
                    "source_files": source_inventory(original_source),
                    "binary_sha256": digest(
                        original_source.parent / "install/OpenROAD/bin/openroad"
                    ),
                    "metrics_sha256": digest(
                        report_root / record["run_tag"] / "metrics.json"
                    ),
                },
                "replay": {
                    "source": str(target),
                    "binary": str(replay / "install/OpenROAD/bin/openroad"),
                    "metrics": str(report_root / "u3_fixed_source_replay/metrics.json"),
                    "source_files": source_inventory(target),
                    "binary_sha256": digest(replay / "install/OpenROAD/bin/openroad"),
                    "metrics_sha256": digest(
                        report_root / "u3_fixed_source_replay/metrics.json"
                    ),
                },
            },
        )
    else:
        raise ValueError("Unknown phase: " + phase)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "start", "run"])
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--image", type=Path)
    parser.add_argument(
        "--phase",
        choices=["core", "placement", "baselines", "smoke", "evolve", "replay"],
        default="core",
    )
    args = parser.parse_args()
    state = args.run_root.resolve()
    if args.action == "prepare":
        if args.image is None:
            parser.error("prepare requires --image")
        prepare(state, args.image.resolve())
    elif args.action == "start":
        start_service(state)
    else:
        run(state, args.phase)


if __name__ == "__main__":
    main()
