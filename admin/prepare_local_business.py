"""Register explicit local tool/design assets and start isolated existing services."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import time
import urllib.request
from pathlib import Path

from qualify_common_toolchain import available_port, environment
from run_dplevolve_native import digest, write_json


def setup(bindings: Path, output: Path, toolkit_wheel: Path, query_wheel: Path) -> Path:
    source = json.loads(bindings.read_text())
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    envs = {}
    builder = source["builder_python"]
    for name in ("client", "query", "goal"):
        target = output / "envs" / name
        shutil.copytree(source["environment_templates"][name], target, symlinks=True)
        python = str(target / "bin/python")
        wheels = [str(toolkit_wheel.resolve())] + (
            [str(query_wheel.resolve())] if name == "query" else []
        )
        subprocess.run(
            [
                builder,
                "-m",
                "pip",
                "--python",
                python,
                "install",
                "--no-deps",
                "--force-reinstall",
                *wheels,
            ],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        envs[name] = python
    assets = output / "assets"
    assets.mkdir()
    value = {
        **source,
        "schema_version": "chip-evolve.local.v1",
        "state_root": str(output),
        "client_python": envs["client"],
        "query_python": envs["query"],
        "goal_python": envs["goal"],
        "openroad_launcher": str(Path(envs["client"]).parent / "eda-openroad"),
    }
    for design_id, design in value["designs"].items():
        folder = assets / design_id
        folder.mkdir()
        target_sdc = folder / "constraints.sdc"
        target_sdc.write_text(Path(design["sdc"]).read_text())
        design["sdc"] = str(target_sdc)
        copied = []
        for row in design["libraries"]:
            original = Path(row["path"])
            if digest(original) != row["sha256"]:
                raise ValueError("Declared library differs from actual input")
            target = folder / original.name
            shutil.copyfile(original, target)
            copied.append({"path": str(target), "sha256": digest(target)})
        design["libraries"] = copied
    value["runtime"]["bind_roots"] = [str(output), *source["runtime"]["bind_roots"]]
    kernel_port, data_port = available_port(), available_port()
    while data_port == kernel_port:
        data_port = available_port()
    value.update(
        kernel_url=f"http://127.0.0.1:{kernel_port}",
        data_url=f"http://127.0.0.1:{data_port}",
    )
    subprocess.run(
        [
            envs["client"],
            "-m",
            "eda_toolkits",
            "configure",
            "--output",
            str(output / "plugins"),
            "--image",
            source["runtime"]["image"],
        ],
        check=True,
        stdout=subprocess.DEVNULL,
    )
    # Only the existing plugin time ceiling is configured; native algorithms and
    # per-task resources are still controlled by their explicit requests.
    for manifest in (output / "plugins").rglob("*.plugin.json"):
        data = json.loads(manifest.read_text())
        data["default_timeout_seconds"] = 14460
        data.setdefault("environment", {}).pop("EDA_ACTIVITY_LOCK", None)
        manifest.write_text(json.dumps(data, indent=2) + "\n")
    native = output / "native"
    native.mkdir()
    services = {
        "execution": [
            envs["client"],
            "-m",
            "openroad_platform_gateway",
            "--state-root",
            str(output / "kernel"),
            "--plugins-root",
            str(output / "plugins"),
            "--admissions-root",
            source["admissions_root"],
            "--host",
            "127.0.0.1",
            "--port",
            str(kernel_port),
            "--input-root",
            str(output),
            "--input-root",
            str(Path(__file__).resolve().parents[1]),
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
            source["data_python"],
            "-m",
            "openroad_app_data_foundation",
            "--host",
            "127.0.0.1",
            "--port",
            str(data_port),
            "--db",
            str(output / "data/snapshots.sqlite"),
            "--kernel-url",
            value["kernel_url"],
            "--native-root",
            str(native),
            "--no-auto-import",
        ],
    }
    path = output / "local.json"
    write_json(path, value)
    value["services"] = {}
    for name, command in services.items():
        with (output / (name + ".log")).open("x") as log:
            process = subprocess.Popen(
                command,
                env=environment(),
                stdout=log,
                stderr=log,
                start_new_session=True,
            )
        value["services"][name] = {"pid": process.pid, "command": command}
        write_json(path, value)
        endpoint = (
            value["kernel_url"] + "/kernel/health"
            if name == "execution"
            else value["data_url"] + "/health"
        )
        deadline = time.monotonic() + 30
        while True:
            try:
                with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(
                    endpoint, timeout=2
                ):
                    break
            except OSError:
                if process.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError("Local service start failed: " + name)
                time.sleep(0.2)
    write_json(
        output / "wheel-identities.json",
        {str(p): digest(p) for p in (toolkit_wheel, query_wheel)},
    )
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bindings", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--toolkit-wheel", type=Path, required=True)
    parser.add_argument("--query-wheel", type=Path, required=True)
    args = parser.parse_args()
    print(setup(args.bindings, args.output, args.toolkit_wheel, args.query_wheel))
