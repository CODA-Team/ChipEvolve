"""Qualify one frozen common toolchain through existing public EF/DF interfaces."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tarfile
import time
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

from run_dplevolve_native import digest, now, write_json
from run_goalevolve_native import stop_native_tree

ROOT = Path(__file__).resolve().parents[1]
IMAGE_SHA = "8e6ee7aac233da078364649fa8111dac5de33a3589f5445dcffd96f9d6d8dd39"
OPENROAD = "27288f5c90265ae5296b2f5a9fa6e8714fa191ad"
ORFS = "5105b0a77fe8b3ae107bed67112eb5f83caca5d5"
TERMINAL = {"succeeded", "failed", "cancelled", "timed_out", "lost"}
EF_PACKAGES = (
    "contracts",
    "core/client",
    "core/runtime",
    "core/registry",
    "core/evaluator",
    "core/provenance",
    "gateway",
)


def environment() -> dict[str, str]:
    result = dict(os.environ)
    for key in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "CONDA_PREFIX"):
        result.pop(key, None)
    result.update(
        PYTHONNOUSERSITE="1",
        NO_PROXY="localhost,127.0.0.1,::1",
        no_proxy="localhost,127.0.0.1,::1",
    )
    return result


def git(path: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=path, text=True).strip()


def recorded(state: Path, name: str, command: list[str], *, timeout: int) -> None:
    """Preparation receipts are immutable; failed attempts remain inspectable."""
    receipt = state / "preparation" / (name + ".json")
    if receipt.exists():
        raise FileExistsError(receipt)
    started = time.monotonic()
    with receipt.with_suffix(".log").open("x") as log:
        try:
            result = subprocess.run(
                command,
                stdout=log,
                stderr=subprocess.STDOUT,
                env=environment(),
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            write_json(
                receipt,
                {
                    "command": command,
                    "exit_code": None,
                    "timed_out": True,
                    "elapsed_seconds": time.monotonic() - started,
                },
            )
            raise
    write_json(
        receipt,
        {
            "command": command,
            "exit_code": result.returncode,
            "elapsed_seconds": time.monotonic() - started,
        },
    )
    if result.returncode:
        raise RuntimeError(f"{name} failed; inspect {receipt.with_suffix('.log')}")


def source_identity(source: Path) -> dict[str, Any]:
    roots = [(".", source)]
    for line in git(source, "submodule", "status", "--recursive").splitlines():
        if line[0] in {"-", "+", "U"}:
            raise ValueError("Source submodule is absent or differs from its pin")
        relative = line.split()[1]
        roots.append((relative, source / relative))
    repositories = []
    for relative, path in roots:
        if git(path, "status", "--porcelain", "--untracked-files=no"):
            raise ValueError("Source contains tracked modifications: " + relative)
        files = {}
        rows = (
            subprocess.check_output(["git", "ls-tree", "-r", "-z", "HEAD"], cwd=path)
            .decode()
            .split("\0")
        )
        for row in filter(None, rows):
            fields, name = row.split("\t", 1)
            mode, kind, blob = fields.split()
            if kind != "blob":
                continue
            item = path / name
            data = (
                os.readlink(item).encode() if item.is_symlink() else item.read_bytes()
            )
            actual = hashlib.sha1(
                b"blob " + str(len(data)).encode() + b"\0" + data
            ).hexdigest()
            if actual != blob:
                # Git's declared checkout filters (ABC *.dsp uses CRLF) can
                # change worktree bytes without changing the source object.
                canonical = (
                    subprocess.check_output(
                        ["git", "hash-object", "--path=" + name, "--stdin"],
                        cwd=path,
                        input=data,
                    )
                    .decode()
                    .strip()
                )
                if canonical != blob:
                    raise ValueError("Source bytes differ from Git: " + str(item))
            files[name] = {
                "git_blob": blob,
                "mode": mode,
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        repositories.append(
            {
                "path": relative,
                "commit": git(path, "rev-parse", "HEAD"),
                "tree": git(path, "rev-parse", "HEAD^{tree}"),
                "files": files,
            }
        )
    if repositories[0]["commit"] != OPENROAD:
        raise ValueError("OpenROAD source is not the selected common version")
    selected = {
        "src/sta": "e983e15b2cb346badf8f23725fd3914d25312c44",
        "third-party/abc": "d527cfab4ad731b767ea0a2be2021d920d3afece",
        "third-party/slang-elab": "82effc8d9541be69e1ed3ec44759a4449f5d9247",
        "third-party/slang-elab/third_party/fmt": "553ec11ec06fbe0beebfbb45f9dc3c9eabd83d28",
        "third-party/slang-elab/third_party/slang": "f04e81565793c768b747a8fd058f3e7aeceee1b5",
    }
    if {r["path"]: r["commit"] for r in repositories[1:]} != selected:
        raise ValueError("Recursive dependencies differ from the selected pins")
    return {
        "repositories": repositories,
        "openroad_commit": OPENROAD,
        "orfs_commit": ORFS,
    }


def prepare(state: Path, image: Path, threads: int) -> dict[str, Any]:
    if (state / "config.json").exists():
        raise FileExistsError("Qualification is already frozen")
    if not 1 <= threads <= 8 or digest(image) != IMAGE_SHA:
        raise ValueError("Use the selected image and at most eight build threads")
    source = state / "source/OpenROAD"
    identity = source_identity(source)
    write_json(state / "source-manifest.json", identity)
    sources, wheels = state / "dependency-sources", state / "wheels"
    sources.mkdir()
    wheels.mkdir()
    commits = {}
    for name in (
        "execution-foundation",
        "toolkits",
        "data-foundation",
        "data-interface",
    ):
        destination = sources / name
        destination.mkdir()
        commits[name] = git(ROOT / name, "rev-parse", "HEAD")
        archive = subprocess.check_output(["git", "archive", "HEAD"], cwd=ROOT / name)
        path = state / "preparation" / (name + "-committed.tar")
        path.write_bytes(archive)
        with tarfile.open(path) as bundle:
            bundle.extractall(destination, filter="data")
    builder = str(ROOT / "execution-foundation/.venv/bin/python")
    packages = [sources / "execution-foundation" / name for name in EF_PACKAGES]
    packages += [
        sources / name for name in ("toolkits", "data-foundation", "data-interface")
    ]
    recorded(
        state,
        "wheels",
        [
            builder,
            "-m",
            "pip",
            "wheel",
            "--no-deps",
            "--no-build-isolation",
            "--wheel-dir",
            str(wheels),
            *map(str, packages),
        ],
        timeout=300,
    )
    specifications = {
        "execution-foundation": [
            "openroad-platform-gateway",
            "openroad-platform-client",
        ],
        "toolkits": ["eda-toolkits"],
        "data-foundation": ["openroad-app-data-foundation"],
        "data-interface": ["eda-ai-client"],
    }
    for name, requirements in specifications.items():
        selected_wheels = [
            next(wheels.glob(req.replace("-", "_") + "-*.whl")) for req in requirements
        ]
        if name != "data-interface":
            selected_wheels += list(wheels.glob("openroad_platform_*-*.whl"))
        venv = state / "envs" / name
        recorded(
            state,
            name + "-venv",
            [sys.executable, "-m", "venv", "--without-pip", str(venv)],
            timeout=60,
        )
        recorded(
            state,
            name + "-install",
            [
                builder,
                "-m",
                "pip",
                "--python",
                str(venv / "bin/python"),
                "install",
                "--pre",
                "--no-index",
                "--find-links",
                str(wheels),
                "--find-links",
                str(ROOT / "wheelhouse"),
                *map(str, dict.fromkeys(selected_wheels)),
            ],
            timeout=120,
        )
    with tarfile.open(state / "source.tar", "w") as bundle:
        bundle.add(source, arcname="source")
    native = state / "bin/official-openroad"
    native.parent.mkdir()
    native.write_text(
        "#!"
        + str(state / "envs/toolkits/bin/python")
        + "\nfrom eda_toolkits.launcher import main\nraise SystemExit(main())\n"
    )
    native.chmod(0o755)
    driver_files = {
        name: digest(ROOT / "admin" / name)
        for name in (
            "qualify_common_toolchain.py",
            "accept_common_toolchain.py",
            "run_dplevolve_native.py",
            "run_goalevolve_native.py",
        )
    }
    config = {
        "state": str(state),
        "image": str(image),
        "image_sha256": IMAGE_SHA,
        "openroad_commit": OPENROAD,
        "orfs_commit": ORFS,
        "threads": threads,
        "source_manifest_sha256": digest(state / "source-manifest.json"),
        "source_archive_sha256": digest(state / "source.tar"),
        "driver_files": driver_files,
        "dependency_commits": commits,
        "wheel_sha256": {p.name: digest(p) for p in wheels.glob("*.whl")},
        "cmake_args": [
            "-DCMAKE_BUILD_TYPE=Release",
            "-DBUILD_GUI=OFF",
            "-DBUILD_PYTHON=ON",
            "-DBoost_DIR=/usr/local/lib/cmake/Boost-1.89.0",
            "-Dortools_ROOT=/opt/or-tools",
            "-DABSL_ROOT=/opt/or-tools",
            "-DFETCHCONTENT_SOURCE_DIR_FMT=/work/source/third-party/slang-elab/third_party/fmt",
            "-DFETCHCONTENT_FULLY_DISCONNECTED=ON",
            "-DCMAKE_EXE_LINKER_FLAGS=-flto=1",
        ],
        "build_memory_bytes": 64 << 30,
        "build_process_limit": 2048,
        "budget_seconds": 10800,
        "created_at": now(),
    }
    write_json(state / "config.json", config)
    return config


def container(image: str, workspace: Path, *command: str) -> list[str]:
    scratch = workspace / "tmp"
    scratch.mkdir(exist_ok=True)
    return [
        "apptainer",
        "exec",
        "--cleanenv",
        "--containall",
        "--bind",
        str(workspace) + ":/work",
        "--bind",
        str(scratch) + ":/tmp",
        "--pwd",
        "/work",
        image,
        *command,
    ]


def extract_source(archive: Path, workspace: Path) -> None:
    """The hash-verified, locally made Git bundle must retain exact symlink text."""
    with tarfile.open(archive) as bundle:
        bundle.extractall(workspace, filter="fully_trusted")


def restore_checkpoint(
    archive: Path, workspace: Path, config: dict[str, Any]
) -> dict[str, Any]:
    """Reuse only the explicitly frozen checkpoint from this U1 EF build."""
    expected = config["build_checkpoint"]
    if digest(archive) != expected["sha256"]:
        raise ValueError("Build checkpoint archive changed")
    with tarfile.open(archive) as bundle:
        stream = bundle.extractfile("checkpoint.json")
        assert stream is not None
        manifest = json.load(stream)
        for key in ("source_archive_sha256", "source_manifest_sha256", "image_sha256"):
            if manifest[key] != config[key]:
                raise ValueError("Build checkpoint used a different input: " + key)
        if manifest["origin_run_id"] != expected["origin_run_id"]:
            raise ValueError("Build checkpoint has a different EF origin")
        args = [
            arg
            for arg in config["cmake_args"]
            if arg != "-DCMAKE_EXE_LINKER_FLAGS=-flto=1"
        ]
        if manifest["cmake_args"] != args:
            raise ValueError("Checkpoint compilation flags differ")
        bundle.extractall(workspace, filter="fully_trusted")
    return manifest


def leaf(phase: str) -> None:
    """Existing Toolkit command adapter owns this EF attempt's process group."""
    workspace = Path.cwd()
    config = json.loads((workspace / "inputs/config.json").read_text())
    if digest(Path(config["image"])) != config["image_sha256"]:
        raise ValueError("Configured image changed")
    output = workspace / "query-data"
    output.mkdir()
    if phase == "build":
        archive = workspace / "inputs/source.tar"
        if digest(archive) != config["source_archive_sha256"]:
            raise ValueError("Staged source archive changed")
        extract_source(archive, workspace)
        before = source_identity(workspace / "source")
        staged = json.loads((workspace / "inputs/source-manifest.json").read_text())
        if before != staged:
            raise ValueError("Extracted source differs from the frozen inventory")
        checkpoint = None
        if "build_checkpoint" in config:
            checkpoint = restore_checkpoint(
                workspace / "inputs/build-checkpoint.tar", workspace, config
            )
        commands = [
            container(
                config["image"],
                workspace,
                "cmake",
                "-S",
                "/work/source",
                "-B",
                "/work/build",
                *config["cmake_args"],
            ),
            container(
                config["image"],
                workspace,
                "cmake",
                "--build",
                "/work/build",
                "--target",
                "openroad",
                "--parallel",
                str(config["threads"]),
            ),
        ]
        for command in commands:
            subprocess.run(command, check=True)
        if source_identity(workspace / "source") != before:
            raise ValueError("Build changed tracked algorithm source")
        binary = workspace / "build/bin/openroad"
        shutil.copy2(binary, output / "openroad")
        shutil.copy2(workspace / "build/CMakeCache.txt", output / "CMakeCache.txt")
        record = {
            "phase": "build",
            "openroad_commit": OPENROAD,
            "image_sha256": config["image_sha256"],
            "commands": commands,
            "binary_sha256": digest(binary),
            "source_manifest_sha256": config["source_manifest_sha256"],
            "source_archive_sha256": digest(archive),
            "tracked_source_unchanged": True,
            "build_checkpoint": checkpoint,
        }
    else:
        with zipfile.ZipFile(workspace / "inputs/build.zip") as bundle:
            bundle.extractall(workspace / "candidate")
        built = json.loads((workspace / "candidate/qualification.json").read_text())
        binary = workspace / "candidate/openroad"
        if digest(binary) != built["binary_sha256"]:
            raise ValueError("Candidate binary differs from the registered build")
        binary.chmod(0o755)
        script = workspace / "check.tcl"
        script.write_text(
            "read_liberty /work/inputs/library.lib\nread_db /work/inputs/final.odb\n"
            "read_sdc /work/inputs/final.sdc\nread_spef /work/inputs/final.spef\n"
            "set_units -time ns\ncheck_placement -verbose\nset block [ord::get_db_block]\n"
            'puts "U1_DESIGN=[$block getName]"\n'
            'puts "U1_INSTANCES=[llength [$block getInsts]]"\n'
            'puts "U1_NETS=[llength [$block getNets]]"\n'
            'puts "U1_WNS=[sta::worst_slack -max]"\n'
            "write_db /work/query-data/roundtrip.odb\nexit\n"
        )
        command = container(
            config["image"],
            workspace,
            "/work/candidate/openroad",
            "-no_init",
            "-exit",
            "/work/check.tcl",
        )
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        print(result.stdout, end="", flush=True)
        print(result.stderr, end="", file=sys.stderr, flush=True)
        (output / "check.log").write_text(result.stdout + result.stderr)
        values = dict(re.findall(r"^U1_(\w+)=(.*)$", result.stdout, re.MULTILINE))
        record = {
            "phase": "check",
            "design": values["DESIGN"],
            "platform": "nangate45",
            "instances": int(values["INSTANCES"]),
            "nets": int(values["NETS"]),
            "wns_ns": float(values["WNS"]),
            "command": command,
            "binary_sha256": digest(binary),
            "image_sha256": config["image_sha256"],
            "input_odb_sha256": digest(workspace / "inputs/final.odb"),
            "roundtrip_sha256": digest(output / "roundtrip.odb"),
            "placement_check_passed": True,
        }
    write_json(output / "qualification.json", record)
    write_json(
        output / "manifest.json",
        {
            "purpose": "toolchain_qualification",
            "phase": phase,
            "import_as_design_snapshot": False,
        },
    )


def http(url: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(
        request, timeout=30
    ) as response:
        return json.load(response)


def available_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_run(client: Any, run_id: str, deadline: float) -> dict[str, Any]:
    while time.monotonic() < deadline:
        row = client.run(run_id)
        if row["status"] in TERMINAL:
            if row["status"] != "succeeded":
                raise RuntimeError(
                    "EF task did not succeed: " + run_id + " " + row["status"]
                )
            return row
        time.sleep(0.5)
    client.cancel(run_id)
    raise TimeoutError("Qualification execution budget exhausted")


def metric_task(
    flow: dict[str, Any],
    snapshot_id: str,
    *,
    report_name: str = "6_report.json",
    stage: str = "finish",
) -> dict[str, Any]:
    """Import the actual registered final ORFS report, keeping physical run ownership."""
    raw = next(a for a in flow["artifacts"] if Path(a["store_key"]).name == report_name)
    run = flow["run"]
    return {
        "schema_version": 3,
        "task_id": snapshot_id,
        "project_id": "common-toolchain-u1",
        "design_id": "gcd",
        "plugin_id": "openroad-data",
        "inputs": {
            "adapter": "orfs",
            "metadata_path": "inputs/" + report_name,
            "snapshot_id": snapshot_id,
            "design_id": "gcd",
            "revision_id": run["task_id"],
            "run_id": run["run_id"],
            "stage": stage,
            "created_at": now(),
        },
        "labels": {"run_type": "analysis", "analysis_of_run_id": run["run_id"]},
        "staged_inputs": [
            {"artifact_id": raw["artifact_id"], "destination": "inputs/" + report_name}
        ],
        "resources": {"cpu_cores": 1, "memory_bytes": 512 << 20, "processes": 64},
        "timeout_seconds": 120,
        "max_attempts": 1,
        "expected_artifacts": ["data_snapshot"],
    }


def controller(state: Path) -> None:
    from eda_toolkits.orfs import OrfsToolkit
    from openroad_platform_client import KernelClient

    config = json.loads((state / "config.json").read_text())
    for name, sha in config["driver_files"].items():
        if digest(ROOT / "admin" / name) != sha:
            raise ValueError("Qualification source changed after freeze: " + name)
    result_path = state / "runtime.json"
    if result_path.exists():
        raise FileExistsError(
            "Retain this attempt; do not overwrite its execution receipt"
        )
    start = time.monotonic()
    deadline = start + config["budget_seconds"]
    kernel_port, data_port = available_port(), available_port()
    while data_port == kernel_port:
        data_port = available_port()
    kernel_url, data_url = (
        f"http://127.0.0.1:{kernel_port}",
        f"http://127.0.0.1:{data_port}",
    )
    toolkit_python = str(state / "envs/toolkits/bin/python")
    subprocess.run(
        [
            toolkit_python,
            "-m",
            "eda_toolkits",
            "configure",
            "--output",
            str(state / "plugins"),
            "--image",
            config["image"],
        ],
        env=environment(),
        check=True,
    )
    commands = {
        "execution": [
            str(state / "envs/execution-foundation/bin/python"),
            "-m",
            "openroad_platform_gateway",
            "--state-root",
            str(state / "kernel"),
            "--plugins-root",
            str(state / "plugins"),
            "--admissions-root",
            str(state / "dependency-sources/execution-foundation/admissions"),
            "--host",
            "127.0.0.1",
            "--port",
            str(kernel_port),
            "--input-root",
            str(state),
            "--input-root",
            str(ROOT / "admin"),
            "--capacity-cpu-cores",
            "8",
            "--capacity-memory-bytes",
            str(config["build_memory_bytes"]),
            "--platform-fraction",
            "1.0",
            "--worker-concurrency",
            "1",
        ],
        "data": [
            str(state / "envs/data-foundation/bin/python"),
            "-m",
            "openroad_app_data_foundation",
            "--host",
            "127.0.0.1",
            "--port",
            str(data_port),
            "--db",
            str(state / "data/snapshots.sqlite"),
            "--kernel-url",
            kernel_url,
            "--native-root",
            str(state / "native-flow"),
            "--no-auto-import",
        ],
    }
    env = environment()
    env["EDA_ORFS_IMAGE"] = config["image"]
    runtime: dict[str, Any] = {
        "started_at": now(),
        "kernel_url": kernel_url,
        "data_url": data_url,
        "jobs": {},
        "status": "running",
        "service_commands": commands,
    }
    write_json(result_path, runtime)
    services = []
    handles = []
    client = KernelClient(kernel_url, timeout=60)
    active: str | None = None
    try:
        for name, command in commands.items():
            log = (state / (name + ".log")).open("x")
            handles.append(log)
            process = subprocess.Popen(
                command, env=env, stdout=log, stderr=log, start_new_session=True
            )
            services.append(process)
            health = (
                kernel_url + "/kernel/health"
                if name == "execution"
                else data_url + "/health"
            )
            ready = time.monotonic() + 60
            while True:
                try:
                    http(health)
                    break
                except OSError:
                    if process.poll() is not None or time.monotonic() >= ready:
                        raise RuntimeError(
                            "Qualification service failed to start: " + name
                        )
                    time.sleep(0.2)

        def complete(name: str, submitted: dict[str, Any]) -> dict[str, Any]:
            nonlocal active
            active = submitted["run"]["run_id"]
            runtime["jobs"][name] = {"submission": submitted}
            write_json(result_path, runtime)
            wait_run(client, active, deadline)
            record = {
                "run": client.run(active),
                "artifacts": client.artifacts(active),
                "resources": client.resources(active),
            }
            runtime["jobs"][name].update(record)
            write_json(result_path, runtime)
            active = None
            print(
                json.dumps(
                    {
                        "phase": name,
                        "run_id": record["run"]["run_id"],
                        "status": "succeeded",
                    }
                ),
                flush=True,
            )
            return record

        common = [
            {"source": str(state / "config.json"), "destination": "inputs/config.json"}
        ]
        common += [
            {"source": str(ROOT / "admin" / name), "destination": "inputs/" + name}
            for name in (
                "qualify_common_toolchain.py",
                "run_dplevolve_native.py",
                "run_goalevolve_native.py",
            )
        ]

        def command_task(phase: str, staged: list[dict[str, Any]]) -> dict[str, Any]:
            return {
                "schema_version": 3,
                "task_id": state.name + "-" + phase,
                "project_id": "common-toolchain-u1",
                "design_id": "gcd",
                "plugin_id": "openroad-data",
                "labels": {"memory_approval": "manual"},
                "inputs": {
                    "adapter": "command",
                    "extractor_command": [
                        toolkit_python,
                        "inputs/qualify_common_toolchain.py",
                        "leaf",
                        "--phase",
                        phase,
                    ],
                },
                "staged_inputs": common + staged,
                "timeout_seconds": 5400 if phase == "build" else 180,
                "resources": {
                    "cpu_cores": config["threads"],
                    "memory_bytes": config["build_memory_bytes"]
                    if phase == "build"
                    else 6 << 30,
                    "processes": config["build_process_limit"]
                    if phase == "build"
                    else 256,
                },
                "max_attempts": 1,
                "expected_artifacts": ["data_snapshot"],
            }

        checkpoint_inputs = []
        if "build_checkpoint" in config:
            checkpoint_inputs.append(
                {
                    "source": str(state / "build-checkpoint.tar"),
                    "destination": "inputs/build-checkpoint.tar",
                }
            )
        build = complete(
            "build",
            client.submit(
                command_task(
                    "build",
                    [
                        {
                            "source": str(state / "source.tar"),
                            "destination": "inputs/source.tar",
                        },
                        {
                            "source": str(state / "source-manifest.json"),
                            "destination": "inputs/source-manifest.json",
                        },
                    ]
                    + checkpoint_inputs,
                )
            ),
        )
        built = next(a for a in build["artifacts"] if a["kind"] == "data_snapshot")
        results = state / "results"
        results.mkdir()

        def retrieve(record: dict[str, Any], name: str) -> None:
            artifact = next(
                a for a in record["artifacts"] if a["kind"] == "data_snapshot"
            )
            destination = results / (name + ".zip")
            client.materialize_artifact(
                record["run"]["run_id"], artifact["artifact_id"], str(destination)
            )
            with zipfile.ZipFile(destination) as bundle:
                bundle.extractall(results / name)

        retrieve(build, "build")
        native_config = {
            "orfs_image": config["image"],
            "openroad_bin": str(state / "bin/official-openroad"),
            "container_runtime": "apptainer",
        }
        toolkit = OrfsToolkit(client, native_config, state / "assets")
        flow = complete("flow", toolkit.submit_flow(revision=state.name + "-gcd"))
        snapshot_id = state.name + "-finish"
        export = complete(
            "export", toolkit.export_flow(flow["run"]["run_id"], snapshot_id)
        )
        snapshot = next(a for a in export["artifacts"] if a["kind"] == "data_snapshot")
        imported = http(
            data_url + "/snapshots/from-run",
            {"run_id": export["run"]["run_id"], "artifact_id": snapshot["artifact_id"]},
        )
        runtime.update(snapshot_id=snapshot_id, imported=imported)
        unit_id = state.name + "-units"
        unit = complete(
            "units_export",
            client.submit(
                metric_task(
                    flow, unit_id, report_name="2_1_floorplan.json", stage="floorplan"
                )
            ),
        )
        unit_artifact = next(
            a for a in unit["artifacts"] if a["kind"] == "data_snapshot"
        )
        runtime.update(
            unit_snapshot_id=unit_id,
            unit_imported=http(
                data_url + "/snapshots/from-run",
                {
                    "run_id": unit["run"]["run_id"],
                    "artifact_id": unit_artifact["artifact_id"],
                },
            ),
        )
        metric_id = state.name + "-metrics"
        metric = complete("metrics_export", client.submit(metric_task(flow, metric_id)))
        metric_artifact = next(
            a for a in metric["artifacts"] if a["kind"] == "data_snapshot"
        )
        runtime.update(
            metric_snapshot_id=metric_id,
            metric_imported=http(
                data_url + "/snapshots/from-run",
                {
                    "run_id": metric["run"]["run_id"],
                    "artifact_id": metric_artifact["artifact_id"],
                },
            ),
        )
        write_json(result_path, runtime)
        staged = [
            {"artifact_id": built["artifact_id"], "destination": "inputs/build.zip"},
            {
                "source": str(state / "assets/NangateOpenCellLibrary_typical.lib"),
                "destination": "inputs/library.lib",
            },
        ]
        for stem, destination in (
            ("6_final.odb", "final.odb"),
            ("6_final.sdc", "final.sdc"),
            ("6_final.spef", "final.spef"),
        ):
            artifact = next(
                a for a in flow["artifacts"] if Path(a["store_key"]).name == stem
            )
            staged.append(
                {
                    "artifact_id": artifact["artifact_id"],
                    "destination": "inputs/" + destination,
                }
            )
        checked = complete("check", client.submit(command_task("check", staged)))
        retrieve(checked, "check")
        subprocess.run(
            [
                str(state / "envs/data-interface/bin/python"),
                str(ROOT / "admin/accept_common_toolchain.py"),
                "sdk",
                "--run-root",
                str(state),
            ],
            env=env,
            check=True,
        )
        runtime.update(
            status="succeeded", elapsed_seconds=time.monotonic() - start, ended_at=now()
        )
        write_json(result_path, runtime)
    except BaseException as error:
        runtime.update(
            status="failed",
            error=str(error),
            elapsed_seconds=time.monotonic() - start,
            ended_at=now(),
        )
        write_json(result_path, runtime)
        raise
    finally:
        if active is not None:
            client.cancel(active)
        for process in reversed(services):
            stop_native_tree(process)
        for handle in handles:
            handle.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "run", "controller", "leaf"))
    parser.add_argument("--run-root", type=Path)
    parser.add_argument("--image", type=Path)
    parser.add_argument("--threads", type=int, default=8)
    parser.add_argument("--phase", choices=("build", "check"))
    args = parser.parse_args()
    if args.action == "leaf":
        leaf(args.phase)
    elif args.action == "prepare":
        print(
            json.dumps(
                prepare(args.run_root.resolve(), args.image.resolve(), args.threads)
            )
        )
    elif args.action == "controller":
        controller(args.run_root.resolve())
    else:
        state = args.run_root.resolve()
        code = "import importlib.metadata as m,json;print(json.dumps(sorted((d.metadata['Name'],d.version) for d in m.distributions())))"
        inventories = {
            name: json.loads(
                subprocess.check_output(
                    [str(path / "bin/python"), "-c", code], env=environment()
                )
            )
            for name, path in ((p.name, p) for p in (state / "envs").iterdir())
        }
        write_json(state / "environment-packages.json", inventories)
        subprocess.run(
            [
                str(state / "envs/toolkits/bin/python"),
                str(Path(__file__).resolve()),
                "controller",
                "--run-root",
                str(state),
            ],
            env=environment(),
            check=True,
        )


if __name__ == "__main__":
    main()
