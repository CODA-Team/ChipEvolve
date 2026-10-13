"""Local overnight service composition and public EF task receipts."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from qualify_common_toolchain import available_port, environment, http
from run_common_goalevolve import configure_adapter_ceiling
from run_dplevolve_native import digest, now, write_json

ROOT = Path(__file__).resolve().parents[1]
U1 = ROOT / "var/toolchains/common-u1-20261012-retry6"
U4 = ROOT / "var/code-agent/u4-goalevolve-common-20261013"


def start(state: Path) -> dict[str, Any]:
    """Use qualified installed wheels and a fresh, isolated pair of services."""
    if (state / "runtime.json").exists():
        raise FileExistsError("Keep the previous service receipt")
    kernel_port, data_port = available_port(), available_port()
    while data_port == kernel_port:
        data_port = available_port()
    prior = json.loads((U4 / "config.json").read_text())
    runtime = {
        "state_root": str(state),
        "image": prior["image"],
        "toolchain": prior["toolchain"],
        "client_python": prior["client_python"],
        "data_python": str(U1 / "envs/data-foundation/bin/python"),
        "sdk_python": str(U1 / "envs/data-interface/bin/python"),
        "kernel_url": f"http://127.0.0.1:{kernel_port}",
        "data_url": f"http://127.0.0.1:{data_port}",
        "adapter_timeout_ceiling_seconds": 14460,
        "service_capacity": {"cpu_cores": 32, "memory_bytes": 128 << 30, "workers": 4},
        "started_at": now(),
    }
    subprocess.run(
        [
            runtime["client_python"],
            "-m",
            "eda_toolkits",
            "configure",
            "--output",
            str(state / "plugins"),
            "--image",
            runtime["image"],
        ],
        env=environment(),
        check=True,
    )
    configure_adapter_ceiling(state, runtime)
    commands = {
        "execution": [
            runtime["client_python"],
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
            str(kernel_port),
            "--input-root",
            str(state),
            "--input-root",
            str(ROOT / "admin"),
            "--capacity-cpu-cores",
            "32",
            "--capacity-memory-bytes",
            str(128 << 30),
            "--platform-fraction",
            "1.0",
            "--worker-concurrency",
            "4",
        ],
        "data": [
            runtime["data_python"],
            "-m",
            "openroad_app_data_foundation",
            "--host",
            "127.0.0.1",
            "--port",
            str(data_port),
            "--db",
            str(state / "data/snapshots.sqlite"),
            "--kernel-url",
            runtime["kernel_url"],
            "--native-root",
            str(state / "native-flow"),
            "--no-auto-import",
        ],
    }
    runtime["services"] = {}
    write_json(state / "runtime.json", runtime)
    for name, command in commands.items():
        with (state / (name + ".log")).open("x") as log:
            process = subprocess.Popen(
                command,
                env=environment(),
                stdout=log,
                stderr=log,
                start_new_session=True,
            )
        runtime["services"][name] = {"pid": process.pid, "command": command}
        write_json(state / "runtime.json", runtime)
        end = time.monotonic() + 60
        endpoint = "/kernel/health" if name == "execution" else "/health"
        while True:
            try:
                http(
                    runtime["kernel_url" if name == "execution" else "data_url"]
                    + endpoint
                )
                break
            except OSError:
                if process.poll() is not None or time.monotonic() >= end:
                    raise RuntimeError("Service startup failed: " + name)
                time.sleep(0.2)
    return runtime


def submit(state: Path, key: str, spec: dict[str, Any]) -> str:
    from openroad_platform_client import KernelClient

    runtime = json.loads((state / "runtime.json").read_text())
    folder = state / "tasks" / key
    folder.mkdir(parents=True, exist_ok=False)
    write_json(folder / "spec.json", spec)
    client = KernelClient(runtime["kernel_url"], timeout=60)
    result = client.submit(
        spec, idempotent=True, idempotency_key=state.name + ":" + key
    )
    write_json(folder / "submission.json", result)
    return result["run"]["run_id"]


def collect(state: Path, key: str, *, wait: bool = True) -> dict[str, Any]:
    from openroad_platform_client import KernelClient

    runtime = json.loads((state / "runtime.json").read_text())
    folder = state / "tasks" / key
    run_id = json.loads((folder / "submission.json").read_text())["run"]["run_id"]
    client = KernelClient(runtime["kernel_url"], timeout=60)
    terminal = {"succeeded", "failed", "cancelled", "timed_out", "lost"}
    while True:
        row = client.run(run_id)
        if row["status"] in terminal or not wait:
            break
        time.sleep(1)
    result = {
        "run": row,
        "artifacts": client.artifacts(run_id),
        "resources": client.resources(run_id),
    }
    write_json(folder / "execution.json", result)
    if row["status"] in terminal:
        for item in result["artifacts"]:
            if item["kind"] == "data_snapshot":
                path = folder / (item["artifact_id"] + ".zip")
                client.materialize_artifact(run_id, item["artifact_id"], str(path))
    return result


def command(
    state: Path,
    key: str,
    argv: list[str],
    *,
    cwd: Path | None = None,
    timeout: int = 3600,
    memory_gib: int = 16,
    cpu: int = 8,
    capture: list[str] | None = None,
) -> dict[str, Any]:
    runtime = json.loads((state / "runtime.json").read_text())
    request = state / "requests" / (key + ".json")
    request.parent.mkdir(parents=True, exist_ok=True)
    write_json(
        request, {"command": argv, "cwd": str(cwd or state), "capture": capture or []}
    )
    spec = {
        "schema_version": 3,
        "task_id": state.name + "-" + key,
        "project_id": "overnight-gcd",
        "design_id": "gcd",
        "experiment_id": state.name,
        "plugin_id": "openroad-data",
        "labels": {"memory_approval": "manual"},
        "inputs": {
            "adapter": "command",
            "extractor_command": [
                runtime["client_python"],
                str(Path(__file__).resolve()),
                "leaf",
                "--request",
                "inputs/request.json",
            ],
        },
        "staged_inputs": [
            {"source": str(request), "destination": "inputs/request.json"}
        ],
        "timeout_seconds": timeout,
        "resources": {
            "cpu_cores": cpu,
            "memory_bytes": memory_gib << 30,
            "processes": 2048,
        },
        "max_attempts": 1,
        "expected_artifacts": ["data_snapshot"],
    }
    submit(state, key, spec)
    return collect(state, key)


def leaf(request_path: Path) -> int:
    """EDA command children stay in the EF attempt's supervised process tree."""
    request = json.loads(request_path.read_text())
    output = Path.cwd() / "query-data"
    output.mkdir()
    started = now()
    with (output / "stdout.log").open("w") as log, subprocess.Popen(
        request["command"],
        cwd=request["cwd"],
        env=environment(),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    ) as process:
        assert process.stdout is not None
        for line in process.stdout:
            log.write(line)
            log.flush()
            print(line, end="", flush=True)
        code = process.wait()
    artifacts = {}
    for number, name in enumerate(request["capture"]):
        source = Path(name)
        target = output / str(number) / source.name
        target.parent.mkdir()
        shutil.copyfile(source, target)
        artifacts[name] = digest(target)
    write_json(
        output / "manifest.json",
        {
            "evidence_only": True,
            "request": request,
            "returncode": code,
            "started_at": started,
            "ended_at": now(),
            "output_files": artifacts,
        },
    )
    return code


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("start", "leaf", "inventory"))
    parser.add_argument("--state", type=Path)
    parser.add_argument("--request", type=Path)
    args = parser.parse_args()
    if args.phase == "leaf":
        raise SystemExit(leaf(args.request))
    state = args.state.resolve()
    if args.phase == "start":
        print(json.dumps(start(state), indent=2))
    else:
        runtime = json.loads((state / "runtime.json").read_text())
        code = "import os,json;print(json.dumps({'asap7_designs':os.listdir('/OpenROAD-flow-scripts/flow/designs/asap7'),'nangate_designs':os.listdir('/OpenROAD-flow-scripts/flow/designs/nangate45')},indent=2))"
        result = command(
            state,
            "toolchain-inventory",
            [
                "apptainer",
                "exec",
                "--cleanenv",
                "--no-home",
                runtime["image"],
                "python3",
                "-c",
                code,
            ],
            timeout=120,
            memory_gib=4,
            cpu=1,
        )
        print(json.dumps(result["run"], indent=2))


if __name__ == "__main__":
    main()
